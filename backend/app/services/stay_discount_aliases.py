from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import re
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import ExternalSourceRecord, Policy as PolicyModel
from app.repositories import external_sources as external_source_repository

ALIAS_PREFIX = "stay-discount"
SOURCE_CATEGORY = "stay_discount"
DISPLAY_SUMMARY = "비수도권 인구감소지역 숙박 예약 시 결제 금액과 숙박 조건에 따라 2만~7만원 할인권을 제공합니다."
DISPLAY_AMOUNT = "최대 7만원"
DISPLAY_REQUIREMENTS = [
    "7만원 미만 국내 숙박상품: 2만원 할인 (1박 이상)",
    "7만원 이상 국내 숙박상품: 3만원 할인 (1박 이상)",
    "14만원 미만 국내 숙박상품: 5만원 할인 (연박 이상)",
    "14만원 이상 국내 숙박상품: 7만원 할인 (연박 이상)",
    "참여 온라인 여행사에서 매일 오전 10시부터 선착순 발급",
    "입실기간: 2026.6.11~7.31",
]

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
    "영광군": "yeonggwang",
    "영암군": "yeongam",
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
    return (policy.source_category or "") == SOURCE_CATEGORY and policy.external_source_record_id is not None


def apply_detail_display_fields(payload: dict[str, object]) -> dict[str, object]:
    payload["tag"] = DISPLAY_AMOUNT
    payload["amount"] = DISPLAY_AMOUNT
    payload["summary"] = DISPLAY_SUMMARY
    payload["requirements"] = [*DISPLAY_REQUIREMENTS]
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
    for policy in candidate_policies:
        for alias_area in alias_areas_for_policy(db, policy):
            if alias_area.slug == slug:
                return StayDiscountAliasResolution(
                    request_slug=slug,
                    canonical_policy=policy,
                    alias_area=alias_area,
                )
    return None


def _slug_part(value: str, mapping: dict[str, str]) -> str:
    mapped = mapping.get(value)
    if mapped:
        return mapped
    ascii_like = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    if ascii_like:
        return ascii_like
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"u{digest}"
