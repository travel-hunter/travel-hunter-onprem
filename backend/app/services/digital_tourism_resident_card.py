from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

from app.data import digital_tourism_resident_card as data
from app.data.source_provenance import CANONICAL_KEY_VERSION, logical_key_for_source
from app.schemas.external_sources import ExternalBenefitSource
from app.services.travelmonth_normalizer import stable_hash

SOURCE_CATEGORY = data.SOURCE_CATEGORY
SOURCE_NAME = data.SOURCE_NAME
SOURCE_URL = data.SOURCE_URL
TITLE_SUFFIX = data.TITLE_SUFFIX
OFFICIAL_PARTICIPATING_REGIONS_SOURCE_URL = data.OFFICIAL_PARTICIPATING_REGIONS_SOURCE_URL
OFFICIAL_PARTICIPATING_REGIONS_VERIFIED_ON = data.OFFICIAL_PARTICIPATING_REGIONS_VERIFIED_ON
HAENAM_REGIONAL_URL = data.HAENAM_REGIONAL_URL
HADONG_REGIONAL_URL = data.HADONG_REGIONAL_URL
WANDO_REGIONAL_URL = data.WANDO_REGIONAL_URL
VISITKOREA_DGTOURCARD_HOST = data.VISITKOREA_DGTOURCARD_HOST
VISITKOREA_DGTOURCARD_PATH_PREFIX = data.VISITKOREA_DGTOURCARD_PATH_PREFIX
PARTICIPATING_REGIONS = data.PARTICIPATING_REGIONS
PARTICIPATING_CITY_REGIONS = data.PARTICIPATING_CITY_REGIONS
PARTICIPATING_CITIES = data.PARTICIPATING_CITIES
REGIONAL_URLS = data.REGIONAL_URLS


DGTOURCARD_CONTEXT_PATH = "/dgtourcard"
REGIONAL_MEMBER_BENEFIT_ENDPOINT = (
    "https://korean.visitkorea.or.kr/dgtourcard/biz/regn/getRegnMbrbList.json"
)
REGIONAL_VISIT_TIP_ENDPOINT = (
    "https://korean.visitkorea.or.kr/dgtourcard/biz/regn/getRegnVstTipList.json"
)
REGIONAL_BENEFIT_PAGE_SIZE = 8
MAX_DISPLAY_PARTNER_BENEFITS = 8
PARTNER_BENEFIT_CATEGORY_ORDER = (
    ("FDRK", "식음료"),
    ("STAYNG", "숙박"),
    ("VWNG", "관람"),
    ("EXPRN", "체험"),
    ("SHPN", "쇼핑"),
    ("FEST", "축제"),
    ("TRNS", "교통"),
    ("ETC", "기타"),
)
_PARTNER_BENEFIT_CATEGORY_RANK = {
    name: index for index, (_code, name) in enumerate(PARTNER_BENEFIT_CATEGORY_ORDER)
}
_PARTNER_BENEFIT_CATEGORY_CODE_BY_NAME = {
    name: code for code, name in PARTNER_BENEFIT_CATEGORY_ORDER
}
_PARTNER_BENEFIT_CATEGORY_LABELS = {
    "식음료": "🍽️",
    "숙박": "🏨",
    "관람": "🎟️",
    "체험": "🎡",
    "쇼핑": "🛍️",
    "축제": "🎉",
    "교통": "🚌",
    "기타": "📌",
}
MEMBER_BENEFIT_DETAIL_URL_PREFIX = (
    "https://korean.visitkorea.or.kr/dgtourcard/biz/mbrb/mbrbPtcl.do?mbrbId="
)


class _HtmlTextStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts).strip()


def clean_dgtour_text(value: object) -> str:
    raw = str(value or "").replace("\r", "\n")
    if "<" in raw and ">" in raw:
        stripper = _HtmlTextStripper()
        stripper.feed(raw)
        raw = stripper.text()
    return " ".join(raw.split())


def regional_url_codes_for_city(city: str | None) -> tuple[str, str] | None:
    display_city = display_city_name(city)
    for row_city, _region, mtpc_do_cd, signgu_cd in data.REGIONAL_URL_CODE_ROWS:
        if row_city == display_city:
            return mtpc_do_cd, signgu_cd
    return None


def regional_url_codes_from_url(url: str | None) -> tuple[str, str] | None:
    if not url:
        return None
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    mtpc_do_cd = (query.get("mtpcDoCd") or [""])[0]
    signgu_cd = (query.get("signguCd") or [""])[0]
    if mtpc_do_cd and signgu_cd:
        return mtpc_do_cd, signgu_cd
    return None


def partner_benefit_from_api_row(row: dict[str, object]) -> dict[str, object] | None:
    member_id = clean_dgtour_text(row.get("mbrbId"))
    name = clean_dgtour_text(row.get("mbrbNm"))
    category_name = clean_dgtour_text(row.get("mbrbBnefClCdNm"))
    summary = clean_dgtour_text(row.get("svcCn"))
    detail = clean_dgtour_text(row.get("bnefCn"))
    intro = clean_dgtour_text(row.get("mbrbIntroWordsCn"))
    if not member_id or not name or not (summary or detail):
        return None
    benefit: dict[str, object] = {
        "memberId": member_id,
        "categoryCode": clean_dgtour_text(row.get("mbrbBnefClCd")),
        "categoryName": category_name or "기타",
        "name": name,
        "intro": intro,
        "summary": summary or detail,
        "detail": detail or summary,
    }
    exposure_id = clean_dgtour_text(row.get("mbrbExpsrId"))
    if exposure_id:
        benefit["couponExposureId"] = exposure_id
    usage_count = row.get("utztCnt")
    if isinstance(usage_count, int):
        benefit["usageCount"] = usage_count
    total_count = row.get("totCnt")
    if isinstance(total_count, int):
        benefit["totalCount"] = total_count
    return benefit


def partner_benefits_from_api_rows(rows: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    benefits: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        benefit = partner_benefit_from_api_row(row)
        if benefit is None:
            continue
        member_id = str(benefit["memberId"])
        if member_id in seen:
            continue
        seen.add(member_id)
        benefits.append(benefit)
    return benefits


def summarize_partner_benefit_categories(
    benefits: Iterable[dict[str, object]],
) -> dict[str, int]:
    summary: dict[str, int] = {}
    for benefit in benefits:
        category = clean_dgtour_text(benefit.get("categoryName")) or "기타"
        summary[category] = summary.get(category, 0) + 1
    return dict(
        sorted(
            summary.items(),
            key=lambda item: (
                _PARTNER_BENEFIT_CATEGORY_RANK.get(item[0], len(_PARTNER_BENEFIT_CATEGORY_RANK)),
                item[0],
            ),
        )
    )


def _partner_benefit_usage_count(benefit: dict[str, object]) -> int:
    value = benefit.get("usageCount")
    return value if isinstance(value, int) else 0


def _partner_benefit_category_total(benefits: list[dict[str, object]]) -> int:
    return len(benefits)


def partner_benefit_category_highlights(
    benefits: Iterable[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for benefit in benefits:
        category = clean_dgtour_text(benefit.get("categoryName")) or "기타"
        grouped.setdefault(category, []).append(benefit)

    highlights: list[dict[str, object]] = []
    for category, category_benefits in sorted(
        grouped.items(),
        key=lambda item: (
            _PARTNER_BENEFIT_CATEGORY_RANK.get(item[0], len(_PARTNER_BENEFIT_CATEGORY_RANK)),
            item[0],
        ),
    ):
        sorted_benefits = sorted(
            category_benefits,
            key=lambda benefit: (-_partner_benefit_usage_count(benefit), clean_dgtour_text(benefit.get("name"))),
        )
        representative = sorted_benefits[0]
        total_count = _partner_benefit_category_total(sorted_benefits)
        category_code = clean_dgtour_text(representative.get("categoryCode"))
        if not category_code:
            category_code = _PARTNER_BENEFIT_CATEGORY_CODE_BY_NAME.get(category, "")
        highlights.append(
            {
                "categoryCode": category_code,
                "categoryName": category,
                "totalCount": total_count,
                "remainingCount": max(0, total_count - 1),
                "representative": representative,
            }
        )
    return highlights


def partner_benefit_summary_text(city: str | None, benefits: list[dict[str, object]]) -> str:
    display_city = display_city_name(city)
    if not benefits:
        return f"{display_city} 지역 제휴처별 숙박, 식음, 체험, 관광지 혜택을 공식 안내에서 확인할 수 있습니다."
    category_summary = summarize_partner_benefit_categories(benefits)
    category_text = ", ".join(f"{name} {count}곳" for name, count in category_summary.items())
    return f"{display_city} 제휴처 {len(benefits)}곳의 디지털관광주민증 혜택을 제공합니다. 주요 분야: {category_text}."


def partner_benefit_category_label(category: str | None) -> str:
    normalized = clean_dgtour_text(category) or "기타"
    return _PARTNER_BENEFIT_CATEGORY_LABELS.get(normalized, "📌")


def format_partner_benefit_for_display(benefit: dict[str, object]) -> str:
    category = clean_dgtour_text(benefit.get("categoryName")) or "기타"
    category_label = partner_benefit_category_label(category)
    name = clean_dgtour_text(benefit.get("name"))
    summary = clean_dgtour_text(benefit.get("summary")) or clean_dgtour_text(benefit.get("detail"))
    intro = clean_dgtour_text(benefit.get("intro"))
    if summary and intro:
        return f"{category_label} {name}: {summary}\n{intro}"
    description = summary or intro
    if description:
        return f"{category_label} {name}: {description}"
    return f"{category_label} {name}"


def format_partner_benefit_highlight_for_display(highlight: dict[str, object]) -> str:
    representative = highlight.get("representative")
    if not isinstance(representative, dict):
        return ""
    return format_partner_benefit_for_display(representative)


def official_member_benefit_url(benefit: dict[str, object]) -> str | None:
    member_id = clean_dgtour_text(benefit.get("memberId"))
    if not member_id:
        return None
    return f"{MEMBER_BENEFIT_DETAIL_URL_PREFIX}{member_id}"


def apply_partner_benefit_enrichment(
    source: ExternalBenefitSource,
    partner_benefits: list[dict[str, object]],
) -> ExternalBenefitSource:
    payload = dict(source.raw_payload if isinstance(source.raw_payload, dict) else {})
    payload["partnerBenefits"] = partner_benefits
    highlights = partner_benefit_category_highlights(partner_benefits)
    payload["partnerBenefitSummary"] = {
        "totalCount": len(partner_benefits),
        "categoryCounts": summarize_partner_benefit_categories(partner_benefits),
        "displayLimit": MAX_DISPLAY_PARTNER_BENEFITS,
    }
    payload["partnerBenefitCategoryHighlights"] = highlights
    payload["collectionMode"] = (
        "allowlist-materialized+partner-benefit-api"
        if partner_benefits
        else payload.get("collectionMode", "allowlist-materialized")
    )
    raw_detail_parts = [partner_benefit_summary_text(source.city, partner_benefits)]
    raw_detail_parts.extend(
        text
        for text in (format_partner_benefit_highlight_for_display(highlight) for highlight in highlights)
        if text
    )
    return source.model_copy(
        update={
            "raw_payload": payload,
            "raw_detail_text": "\n".join(raw_detail_parts),
            "field_completeness": 95 if partner_benefits else source.field_completeness,
        }
    )


def apply_partner_benefit_enrichment_by_city(
    sources: Iterable[ExternalBenefitSource],
    benefits_by_city: dict[str, list[dict[str, object]]],
) -> list[ExternalBenefitSource]:
    enriched: list[ExternalBenefitSource] = []
    for source in sources:
        city = display_city_name(source.city)
        enriched.append(
            apply_partner_benefit_enrichment(
                source,
                benefits_by_city.get(city, []),
            )
        )
    return enriched

SUPPORT_CONTENT_TEXT = "디지털관광주민증 발급 지역의 숙박, 식음, 체험, 관광지 제휴 혜택"
DEFAULT_BENEFIT_TEXT = f"{SUPPORT_CONTENT_TEXT}을 이용할 수 있습니다."
DEFAULT_BENEFIT_VALUE_TEXT = "지역 제휴 혜택"
USAGE_CONDITION_TEXT = (
    "VisitKorea/대한민국 구석구석에서 디지털관광주민증을 발급하고 제휴처에서 제시해야 합니다."
)
REQUIRED_DOCUMENTS_TEXT = "별도 제출 서류 없음, 디지털관광주민증 발급 및 제시 기준으로 적용"
OFFICIAL_CONFIRMATION_NOTE = "제휴처별 할인율, 운영 기간, 이용 조건은 VisitKorea 공식 안내에서 최종 확인하세요."
BENEFIT_VARIATION_NOTE = "지역별 제휴처와 혜택은 변동될 수 있습니다."
FORBIDDEN_HALF_TRIP_URLS = {
    "https://www.haenam50.kr/index",
    "https://hadongtrip.kr/index.php",
    "https://www.wandotrip.kr/index.php",
    "https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
}
FORBIDDEN_HALF_TRIP_TERMS = ("반값여행", "50% 환급", "최대 20만원", "여행경비 50%")


def display_city_name(city: str | None) -> str:
    if not city:
        return ""
    normalized = city.strip()
    compact = normalized.replace(" ", "")
    if normalized in data.CITY_ALIASES:
        return data.CITY_ALIASES[normalized]
    if compact in data.CITY_ALIASES:
        return data.CITY_ALIASES[compact]
    if compact in PARTICIPATING_CITY_REGIONS:
        return compact
    if len(compact) > 1 and compact.endswith(("시", "군", "구")):
        trimmed = compact[:-1]
        if trimmed in PARTICIPATING_CITY_REGIONS:
            return trimmed
    return compact


def is_participating_city(city: str | None) -> bool:
    return display_city_name(city) in PARTICIPATING_CITY_REGIONS


def region_for_city(city: str | None) -> str | None:
    return PARTICIPATING_CITY_REGIONS.get(display_city_name(city))


def title_with_city_prefix(city: str | None) -> str:
    display_city = display_city_name(city)
    if not display_city:
        return TITLE_SUFFIX
    return f"[{display_city}] {TITLE_SUFFIX}"


def application_target_text(city: str | None) -> str:
    display_city = display_city_name(city)
    if display_city:
        return f"{display_city} 디지털관광주민증을 발급한 여행자"
    return "디지털관광주민증을 발급한 여행자"


def city_from_title(title: str) -> str:
    title = title.strip()
    if title.startswith("[") and "]" in title:
        return display_city_name(title[1 : title.index("]")].strip())
    if title.endswith(TITLE_SUFFIX):
        return display_city_name(title[: -len(TITLE_SUFFIX)].strip())
    return ""


def canonical_policy_slug_for_city(city: str | None) -> str | None:
    display_city = display_city_name(city)
    if not is_participating_city(display_city):
        return None
    return f"dgtour-{display_city}"


def city_from_policy_slug(slug: str | None) -> str:
    if not slug or not slug.startswith("dgtour-"):
        return ""
    suffix = slug.removeprefix("dgtour-").strip()
    if not suffix:
        return ""
    if "-" in suffix:
        city_candidate, numeric_suffix = suffix.rsplit("-", 1)
        if numeric_suffix.isdigit():
            suffix = city_candidate
    city = display_city_name(suffix)
    return city if is_participating_city(city) else ""


def is_visitkorea_dgtourcard_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url.strip())
    return (
        parsed.scheme in {"http", "https"}
        and parsed.netloc == VISITKOREA_DGTOURCARD_HOST
        and parsed.path.startswith(VISITKOREA_DGTOURCARD_PATH_PREFIX)
        and parsed.path != "/dgtourcard/tour50.do"
    )


def contains_forbidden_half_trip_text(value: str | None) -> bool:
    text = value or ""
    return any(term in text for term in FORBIDDEN_HALF_TRIP_TERMS)


def official_url_for_city(city: str | None, fallback: str | None = None) -> str | None:
    display_city = display_city_name(city)
    if display_city in REGIONAL_URLS:
        return REGIONAL_URLS[display_city]
    if fallback and is_visitkorea_dgtourcard_url(fallback):
        return fallback
    return SOURCE_URL if is_participating_city(display_city) else None


def canonical_key_for_city(city: str) -> str:
    region = region_for_city(city) or ""
    return f"digital-tourism-resident-card:{region}:{display_city_name(city)}"


def logical_key_for_city(city: str, *, campaign_year: int) -> str | None:
    return logical_key_for_source(
        source_category=SOURCE_CATEGORY,
        region=region_for_city(city),
        city=display_city_name(city),
        campaign_year=campaign_year,
    )


def materialize_participating_region_sources(
    *,
    fetched_at: datetime,
    today: date,
) -> list[ExternalBenefitSource]:
    del today
    campaign_year = fetched_at.year
    sources: list[ExternalBenefitSource] = []
    for item in PARTICIPATING_REGIONS:
        city = item.city
        region = item.region
        canonical_key = canonical_key_for_city(city)
        official_url = official_url_for_city(city) or SOURCE_URL
        payload: dict[str, object] = {
            "verifiedAt": OFFICIAL_PARTICIPATING_REGIONS_VERIFIED_ON,
            "participatingRegionsSourceUrl": OFFICIAL_PARTICIPATING_REGIONS_SOURCE_URL,
            "collectionMode": "allowlist-materialized",
            "supportContent": SUPPORT_CONTENT_TEXT,
            "applicationTarget": application_target_text(city),
            "usageCondition": USAGE_CONDITION_TEXT,
            "requiredDocuments": REQUIRED_DOCUMENTS_TEXT,
            "notes": [OFFICIAL_CONFIRMATION_NOTE, BENEFIT_VARIATION_NOTE],
        }
        sources.append(
            ExternalBenefitSource(
                source_name=SOURCE_NAME,
                source_type="official_campaign",
                source_url=SOURCE_URL,
                source_category=SOURCE_CATEGORY,
                external_id=stable_hash(canonical_key),
                canonical_key=canonical_key,
                logical_key=logical_key_for_city(city, campaign_year=campaign_year),
                canonical_key_version=CANONICAL_KEY_VERSION,
                detail_url=official_url,
                collected_page_url=SOURCE_URL,
                title=title_with_city_prefix(city),
                organizer_text=f"{city} 지자체, 한국관광공사",
                organizers=[f"{city} 지자체", "한국관광공사"],
                region=region,
                city=city,
                is_nationwide=False,
                status_text="공식 참여지역",
                status="active",
                start_date=None,
                end_date=None,
                benefit_text=DEFAULT_BENEFIT_TEXT,
                benefit_value_text=DEFAULT_BENEFIT_VALUE_TEXT,
                extracted_amount_krw=None,
                extracted_discount_percent=None,
                benefit_value_type="mixed",
                tags=["디지털관광주민증", "지역혜택", city],
                contact_text=None,
                inferred_travel_styles=["체험"],
                confidence=90,
                field_completeness=75,
                raw_list_text=f"{city} 디지털관광주민증 공식 참여지역",
                raw_detail_text=DEFAULT_BENEFIT_TEXT,
                raw_payload=payload,
                last_fetched_at=fetched_at,
                last_verified_at=fetched_at,
                freshness_status="fresh",
            )
        )
    return sources


def merge_materialized_and_parsed_sources(
    materialized: list[ExternalBenefitSource],
    parsed: list[ExternalBenefitSource],
) -> list[ExternalBenefitSource]:
    by_city: dict[str, ExternalBenefitSource] = {
        display_city_name(source.city): source
        for source in materialized
        if is_participating_city(source.city)
    }
    for source in parsed:
        city = display_city_name(source.city) or city_from_title(source.title)
        if not is_participating_city(city):
            continue
        fallback = by_city[city]
        detail_url = official_url_for_city(city, source.detail_url) or fallback.detail_url
        payload = dict(fallback.raw_payload)
        payload.update(source.raw_payload if isinstance(source.raw_payload, dict) else {})
        payload["collectionMode"] = "allowlist-materialized+live-enriched"
        raw_detail_text = (
            source.raw_detail_text
            if source.raw_detail_text
            and not contains_forbidden_half_trip_text(source.raw_detail_text)
            else fallback.raw_detail_text
        )
        by_city[city] = fallback.model_copy(
            update={
                "detail_url": detail_url,
                "title": title_with_city_prefix(city),
                "status_text": source.status_text or fallback.status_text,
                "raw_list_text": source.raw_list_text or fallback.raw_list_text,
                "raw_detail_text": raw_detail_text,
                "raw_payload": payload,
                "last_fetched_at": source.last_fetched_at,
                "last_verified_at": source.last_verified_at or fallback.last_verified_at,
                "freshness_status": source.freshness_status or fallback.freshness_status,
            }
        )
    return [by_city[item.city] for item in PARTICIPATING_REGIONS]
