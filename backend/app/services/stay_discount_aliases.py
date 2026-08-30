from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import re
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import ExternalSourceRecord, Policy as PolicyModel
from app.repositories import external_sources as external_source_repository
from app.data.stay_discount_campaign import select_current_stay_discount_record
from app.services.policy_semantics import format_benefit_amount

ALIAS_PREFIX = "stay-discount"
SOURCE_CATEGORY = "stay_discount"
_DISCOUNT_AMOUNT_PATTERN = re.compile(r"(?P<amount>\d[\d,]*)\s*(?P<unit>만원|원)\s*할인")

_SIDO_SLUGS = {
    "강원": "gangwon",
    "경남": "gyeongnam",
    "경북": "gyeongbuk",
    "대구": "daegu",
    "부산": "busan",
    "전남": "jeonnam",
    "전북": "jeonbuk",
    "충남": "chungnam",
    "충북": "chungbuk",
}

_CITY_SLUGS = {
    "고성군": "goseong",
    "삼척시": "samcheok",
    "양구군": "yanggu",
    "양양군": "yangyang",
    "영월군": "yeongwol",
    "정선군": "jeongseon",
    "철원군": "cheorwon",
    "태백시": "taebaek",
    "평창군": "pyeongchang",
    "홍천군": "hongcheon",
    "화천군": "hwacheon",
    "횡성군": "hoengseong",
    "거창군": "geochang",
    "남해군": "namhae",
    "밀양시": "miryang",
    "산청군": "sancheong",
    "의령군": "uiryeong",
    "창녕군": "changnyeong",
    "하동군": "hadong",
    "함안군": "haman",
    "함양군": "hamyang",
    "합천군": "hapcheon",
    "고령군": "goryeong",
    "문경시": "mungyeong",
    "봉화군": "bonghwa",
    "상주시": "sangju",
    "성주군": "seongju",
    "안동시": "andong",
    "영덕군": "yeongdeok",
    "영양군": "yeongyang",
    "영주시": "yeongju",
    "영천시": "yeongcheon",
    "울릉군": "ulleung",
    "울진군": "uljin",
    "의성군": "uiseong",
    "청도군": "cheongdo",
    "청송군": "cheongsong",
    "군위군": "gunwi",
    "남구": "namgu",
    "서구": "seogu",
    "동구": "donggu",
    "영도구": "yeongdo",
    "강진군": "gangjin",
    "고흥군": "goheung",
    "곡성군": "gokseong",
    "구례군": "gurye",
    "담양군": "damyang",
    "보성군": "boseong",
    "신안군": "sinan",
    "순천시": "suncheon",
    "영광군": "yeonggwang",
    "영암군": "yeongam",
    "여수시": "yeosu",
    "완도군": "wando",
    "장성군": "jangseong",
    "장흥군": "jangheung",
    "진도군": "jindo",
    "함평군": "hampyeong",
    "해남군": "haenam",
    "화순군": "hwasun",
    "고창군": "gochang",
    "김제시": "gimje",
    "남원시": "namwon",
    "무주군": "muju",
    "부안군": "buan",
    "순창군": "sunchang",
    "임실군": "imsil",
    "장수군": "jangsu",
    "정읍시": "jeongeup",
    "진안군": "jinan",
    "공주시": "gongju",
    "금산군": "geumsan",
    "논산시": "nonsan",
    "보령시": "boryeong",
    "부여군": "buyeo",
    "서천군": "seocheon",
    "예산군": "yesan",
    "청양군": "cheongyang",
    "태안군": "taean",
    "괴산군": "goesan",
    "단양군": "danyang",
    "보은군": "boeun",
    "영동군": "yeongdong",
    "옥천군": "okcheon",
    "제천시": "jecheon",
}


@dataclass(frozen=True)
class StayDiscountAliasArea:
    sido: str
    city: str
    slug: str


@dataclass(frozen=True)
class StayDiscountAliasResolution:
    request_slug: str
    canonical_policy: PolicyModel
    alias_area: StayDiscountAliasArea | None = None


@dataclass(frozen=True)
class StayDiscountAliasRecord:
    source_category: str
    title: str
    organizer_text: str | None
    benefit_text: str | None
    raw_list_text: str | None
    raw_detail_text: str | None
    region: str
    city: str
    is_nationwide: bool
    end_date: date | None
    extracted_amount_krw: int | None
    inferred_travel_styles: object
    tags: object


def is_stay_discount_canonical_policy(policy: PolicyModel) -> bool:
    return (
        (policy.source_category or "") == SOURCE_CATEGORY
        and policy.external_source_record_id is not None
        and not is_stay_discount_area_slug(policy.slug)
    )


def is_stay_discount_area_slug(slug: str | None) -> bool:
    return bool(slug and slug.startswith(f"{ALIAS_PREFIX}-"))


def is_stay_discount_area_policy(policy: PolicyModel) -> bool:
    return (policy.source_category or "") == SOURCE_CATEGORY and is_stay_discount_area_slug(
        policy.slug
    )


def area_source_canonical_key(record_key: str | None, alias_slug: str) -> str:
    base_key = (record_key or ALIAS_PREFIX).strip() or ALIAS_PREFIX
    return f"{base_key}:{alias_slug}"


def _section_descriptions(structured_detail: object, section: str) -> list[str]:
    if not isinstance(structured_detail, dict):
        return []
    items = structured_detail.get(section)
    if not isinstance(items, list):
        return []
    return [
        str(item["description"]).strip()
        for item in items
        if isinstance(item, dict) and str(item.get("description") or "").strip()
    ]


def _maximum_structured_discount(benefits: list[str]) -> int | None:
    amounts: list[int] = []
    for benefit in benefits:
        for match in _DISCOUNT_AMOUNT_PATTERN.finditer(benefit):
            amount = int(match.group("amount").replace(",", ""))
            amounts.append(amount * 10_000 if match.group("unit") == "만원" else amount)
    return max(amounts) if amounts else None


def _alias_application_targets(alias_area: StayDiscountAliasArea) -> list[dict[str, str]]:
    city = display_city_name(alias_area.city)
    return [
        {
            "title": "신청대상",
            "description": f"{alias_area.sido} {city} 등 숙박세일페스타 대상 지역 숙박 이용자",
        },
        {
            "title": "신청대상",
            "description": "참여 온라인 여행사를 통해 국내 숙박상품을 예약하는 사용자",
        },
        {
            "title": "신청대상",
            "description": "할인권 발급 후 지정 기간 내 입실 가능한 사용자",
        },
    ]


def _default_required_documents() -> list[dict[str, str]]:
    return [
        {
            "title": "필요서류",
            "description": "별도 제출 서류 없음 · 온라인 할인권 발급 및 예약 기준으로 적용",
        }
    ]


def _append_note_once(structured_detail: dict[str, object], description: str) -> None:
    notes = structured_detail.get("notes")
    if not isinstance(notes, list):
        notes = []
        structured_detail["notes"] = notes
    if not any(isinstance(item, dict) and item.get("description") == description for item in notes):
        notes.append({"title": "비고", "description": description})


def apply_alias_structured_detail(
    payload: dict[str, object],
    alias_area: StayDiscountAliasArea,
) -> dict[str, object]:
    """Project canonical stay-discount detail into the approved five-section alias UI."""
    structured_detail = payload.get("structuredDetail")
    if not isinstance(structured_detail, dict):
        return payload

    projected = dict(structured_detail)
    projected["applicationTarget"] = _alias_application_targets(alias_area)
    documents = projected.get("requiredDocuments")
    if not isinstance(documents, list) or not documents:
        projected["requiredDocuments"] = _default_required_documents()
    _append_note_once(projected, "세부 기준은 공식 안내에서 최종 확인하세요.")
    payload["structuredDetail"] = projected
    return apply_detail_display_fields(payload)


def apply_detail_display_fields(
    payload: dict[str, object],
    *,
    benefit_amount: int | None = None,
) -> dict[str, object]:
    structured_detail = payload.get("structuredDetail")
    benefits = _section_descriptions(structured_detail, "supportContent") or _section_descriptions(structured_detail, "benefits")
    conditions = _section_descriptions(structured_detail, "applicationTarget") or _section_descriptions(structured_detail, "conditions")
    display_amount = format_benefit_amount(
        benefit_amount if benefit_amount is not None else _maximum_structured_discount(benefits)
    ) or ""
    payload["tag"] = display_amount
    payload["amount"] = display_amount
    summary_sections = []
    if benefits:
        summary_sections.append("혜택: " + " / ".join(benefits))
    if conditions:
        summary_sections.append("이용 조건: " + " / ".join(conditions))
    payload["summary"] = " · ".join(summary_sections)
    payload["requirements"] = conditions
    return payload


def alias_slug_for_area(sido: str, city: str) -> str:
    return f"{ALIAS_PREFIX}-{_slug_part(sido, _SIDO_SLUGS)}-{_slug_part(city, _CITY_SLUGS)}"


def display_city_name(city: str) -> str:
    city = city.strip()
    if len(city) > 1 and city.endswith(("시", "군")):
        return city[:-1]
    return city


def alias_title(base_title: str, alias_area: StayDiscountAliasArea) -> str:
    return f"[{display_city_name(alias_area.city)}] {base_title}"


def alias_areas_from_payload(raw_payload: object) -> list[StayDiscountAliasArea]:
    if not isinstance(raw_payload, dict):
        return []
    groups = raw_payload.get("eligibleAreas")
    if not isinstance(groups, list):
        return []
    aliases: list[StayDiscountAliasArea] = []
    seen: set[str] = set()
    for group in groups:
        if not isinstance(group, dict):
            continue
        sido = str(group.get("sido") or "").strip()
        cities = group.get("cities")
        if not sido or not isinstance(cities, list):
            continue
        for raw_city in cities:
            city = str(raw_city or "").strip()
            if not city:
                continue
            slug = alias_slug_for_area(sido, city)
            if slug in seen:
                continue
            seen.add(slug)
            aliases.append(StayDiscountAliasArea(sido=sido, city=city, slug=slug))
    return aliases


def alias_areas_for_policy(db: Session, policy: PolicyModel) -> list[StayDiscountAliasArea]:
    if not is_stay_discount_canonical_policy(policy):
        return []
    record = external_source_repository.get_external_source_record_by_id(
        db,
        policy.external_source_record_id,
    )
    return alias_areas_for_record(record)


def alias_areas_for_record(record: ExternalSourceRecord | None) -> list[StayDiscountAliasArea]:
    if record is None or record.source_category != SOURCE_CATEGORY:
        return []
    return alias_areas_from_payload(record.raw_payload)


def alias_records_for_record(record: ExternalSourceRecord | None) -> list[StayDiscountAliasRecord]:
    aliases = alias_areas_for_record(record)
    if record is None or not aliases:
        return []
    return [
        StayDiscountAliasRecord(
            source_category=SOURCE_CATEGORY,
            title=alias_title(record.title, alias),
            organizer_text=record.organizer_text,
            benefit_text=record.benefit_text,
            raw_list_text=record.raw_list_text,
            raw_detail_text=record.raw_detail_text,
            region=alias.sido,
            city=alias.city,
            is_nationwide=False,
            end_date=record.end_date,
            extracted_amount_krw=record.extracted_amount_krw,
            inferred_travel_styles=record.inferred_travel_styles,
            tags=record.tags,
        )
        for alias in aliases
    ]


def resolve_stay_discount_alias_slug(
    db: Session,
    slug: str,
    policies: Iterable[PolicyModel] | None = None,
) -> StayDiscountAliasResolution | None:
    if not slug.startswith(f"{ALIAS_PREFIX}-"):
        return None
    candidate_policies = list(policies) if policies is not None else []
    if not candidate_policies:
        from app.repositories import policies as policy_repository

        candidate_policies = [
            policy
            for policy in policy_repository.list_policies(db)
            if is_stay_discount_canonical_policy(policy)
        ]
    current_policy = select_current_stay_discount_policy(db, candidate_policies)
    for policy in ([current_policy] if current_policy is not None else []):
        for alias_area in alias_areas_for_policy(db, policy):
            if alias_area.slug == slug:
                return StayDiscountAliasResolution(
                    request_slug=slug,
                    canonical_policy=policy,
                    alias_area=alias_area,
                )
    return None


def select_current_stay_discount_policy(
    db: Session,
    policies: list[PolicyModel],
) -> PolicyModel | None:
    policies_by_record_id = {
        int(policy.external_source_record_id): policy
        for policy in policies
        if is_stay_discount_canonical_policy(policy)
        and policy.external_source_record_id is not None
    }
    records = [
        record
        for record_id in policies_by_record_id
        if (record := external_source_repository.get_external_source_record_by_id(db, record_id))
        is not None
    ]
    current_record = select_current_stay_discount_record(records)
    if current_record is None or current_record.id is None:
        return None
    return policies_by_record_id.get(int(current_record.id))


def _slug_part(value: str, mapping: dict[str, str]) -> str:
    mapped = mapping.get(value)
    if mapped:
        return mapped
    ascii_like = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if ascii_like:
        return ascii_like
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"u{digest}"
