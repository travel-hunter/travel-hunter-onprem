from __future__ import annotations

from datetime import date, datetime
from urllib.parse import urlparse

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

SUPPORT_CONTENT_TEXT = "디지털관광주민증 발급 지역의 숙박·식음·체험·관광지 제휴 혜택"
DEFAULT_BENEFIT_TEXT = f"{SUPPORT_CONTENT_TEXT}을 이용할 수 있습니다."
DEFAULT_BENEFIT_VALUE_TEXT = "지역 제휴 혜택"
USAGE_CONDITION_TEXT = (
    "VisitKorea/대한민국 구석구석에서 디지털관광주민증을 발급하고 제휴처에서 제시해야 합니다."
)
REQUIRED_DOCUMENTS_TEXT = "별도 제출 서류 없음 · 디지털관광주민증 발급/제시 기준으로 적용"
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
                organizer_text=f"{city} 지자체 · 한국관광공사",
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
