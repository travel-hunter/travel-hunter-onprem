from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import re

from sqlalchemy.orm import Session

from app.data.travel_areas import TravelArea, list_travel_areas, make_policy_region_area, resolve_municipality_sido
from app.models import ExternalSourceRecord
from app.repositories import external_sources as external_source_repository
from app.repositories import policies as policy_repository
from app.schemas.recommendations import (
    TravelAreaRecommendation,
    TravelAreaRecommendationResponse,
)
from app.services import stay_discount_aliases


ENDING_SOON_DAYS = 14
NATIONWIDE_REGION = "전국"
_TRAVEL_AREA_SUMMARY_REPLACEMENTS = (
    ("대표 여행권역", "추천 라인"),
    ("대표 권역", "추천 라인"),
    ("여행권역", ""),
    ("권역", ""),
    ("  ", " "),
)


@dataclass(frozen=True)
class _AreaStats:
    city_policy_count: int = 0
    sido_policy_count: int = 0
    text_policy_count: int = 0
    nationwide_policy_count: int = 0
    ending_soon_count: int = 0
    estimated_value_krw: int = 0
    style_matched_count: int = 0

    @property
    def local_policy_count(self) -> int:
        return self.city_policy_count + self.sido_policy_count + self.text_policy_count

    @property
    def policy_count(self) -> int:
        return self.local_policy_count + self.nationwide_policy_count


@dataclass(frozen=True)
class _RankedArea:
    area: TravelArea
    recommendation: TravelAreaRecommendation
    stats: _AreaStats


def recommend_travel_areas(
    db: Session,
    *,
    sido: str | None = None,
    query: str | None = None,
    mode: str | None = None,
    style: str | None = None,
    limit: int = 6,
    today: date | None = None,
) -> TravelAreaRecommendationResponse:
    normalized_sido = _normalize(sido)
    normalized_query = _normalize(query)
    selected_mode = "search" if normalized_query else "sido" if normalized_sido else "nationwide"
    capped_limit = max(1, min(limit, 20))
    areas = list(list_travel_areas())
    policy_area_counts: dict[str, int] = {}

    if selected_mode == "sido":
        areas = [area for area in areas if area.sido == normalized_sido]
        if not areas:
            return TravelAreaRecommendationResponse(
                mode="sido",
                sido=normalized_sido,
                query=None,
                items=[],
                emptyReason="unsupported_sido",
            )
    elif selected_mode == "search":
        if normalized_sido:
            areas = [area for area in areas if area.sido == normalized_sido]
        areas = [area for area in areas if _matches_query(area, normalized_query or "")]
        if not areas:
            policy_areas = _policy_region_areas_for_query(db, query=normalized_query or "", sido=normalized_sido)
            areas = [area for area, _count in policy_areas]
            policy_area_counts = {area.id: count for area, count in policy_areas}
        if not areas:
            fallback_area = _municipality_fallback_area(query=normalized_query, sido=normalized_sido)
            if fallback_area:
                areas = [fallback_area]
        if not areas:
            return TravelAreaRecommendationResponse(
                mode="search",
                sido=normalized_sido,
                query=normalized_query,
                items=[],
                emptyReason="no_match",
            )

    records = external_source_repository.list_regional_benefit_recommendation_records(db)
    recommendation_records = list(_iter_recommendation_records(records))
    run_date = today or date.today()
    ranked = [
        _rank_policy_area(area, policy_area_counts[area.id])
        if area.id in policy_area_counts
        else _rank_area(area, recommendation_records, style=style, today=run_date)
        for area in areas
    ]
    ranked.sort(key=_ranking_key, reverse=True)

    return TravelAreaRecommendationResponse(
        mode=selected_mode,
        sido=normalized_sido,
        query=normalized_query,
        items=[item.recommendation for item in ranked[:capped_limit]],
        emptyReason=None,
    )


def _rank_area(
    area: TravelArea,
    records: list[object],
    *,
    style: str | None,
    today: date,
) -> _RankedArea:
    stats = _stats_for_area(area, records, style=style, today=today)
    recommendation = _to_recommendation(area, stats)
    return _RankedArea(area=area, recommendation=recommendation, stats=stats)


def _rank_policy_area(area: TravelArea, policy_count: int) -> _RankedArea:
    stats = _AreaStats(city_policy_count=policy_count)
    recommendation = _to_recommendation(area, stats)
    return _RankedArea(area=area, recommendation=recommendation, stats=stats)


def _policy_region_areas_for_query(db: Session, *, query: str, sido: str | None) -> list[tuple[TravelArea, int]]:
    folded_query = _fold(query)
    if not folded_query:
        return []
    counts: dict[tuple[str, str], int] = {}
    for policy in policy_repository.list_policies(db):
        policy_sido = _normalize(getattr(policy, "region", None))
        city = _policy_city(policy)
        if not policy_sido or not city or policy_sido == NATIONWIDE_REGION:
            continue
        if sido and policy_sido != sido:
            continue
        if folded_query not in _fold(city):
            continue
        key = (policy_sido, city)
        counts[key] = counts.get(key, 0) + 1

    return [(make_policy_region_area(policy_sido, city), count) for (policy_sido, city), count in sorted(counts.items())]


def _municipality_fallback_area(*, query: str | None, sido: str | None) -> TravelArea | None:
    if not query:
        return None
    resolved_sido = resolve_municipality_sido(query, sido=sido)
    if not resolved_sido:
        return None
    if sido and sido != resolved_sido:
        return None
    return make_policy_region_area(resolved_sido, query)


def _policy_city(policy: object) -> str | None:
    title = str(getattr(policy, "title", "") or "")
    bracketed = re.match(r"^\s*\[([^\]]+)\]", title)
    if bracketed:
        return _normalize_policy_city(bracketed.group(1))

    dgtour_title = re.match(r"^\s*([가-힣]{2,}(?:[·∙][가-힣]{2,})?)\s+디지털관광주민증\s+혜택", title)
    if dgtour_title:
        return _normalize_policy_city(dgtour_title.group(1))

    for requirement in getattr(policy, "requirements", []) or []:
        requirement_text = str(requirement)
        visit_match = re.search(r"(?:^|\s)([가-힣]{2,}(?:시|군|구)?)(?:\s+방문|방문)", requirement_text)
        if visit_match:
            return _normalize_policy_city(visit_match.group(1))
    return None


def _normalize_policy_city(value: str | None) -> str | None:
    normalized = _normalize(value)
    if not normalized or normalized == NATIONWIDE_REGION:
        return None
    return normalized.removesuffix("시").removesuffix("군").removesuffix("구")


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _matches_query(area: TravelArea, query: str) -> bool:
    folded_query = _fold(query)
    if not folded_query:
        return False
    return any(folded_query in _fold(value) for value in _search_values(area))


def _search_values(area: TravelArea) -> tuple[str, ...]:
    return (
        area.id,
        area.name,
        area.sido,
        *area.included_cities,
        *area.aliases,
        *area.tags,
        *area.styles,
    )


def _fold(value: str) -> str:
    return value.strip().casefold().replace(" ", "").replace("?", "")


def _stats_for_area(
    area: TravelArea,
    records: list[object],
    *,
    style: str | None,
    today: date,
) -> _AreaStats:
    city_count = 0
    sido_count = 0
    text_count = 0
    nationwide_count = 0
    ending_soon = 0
    amount = 0
    style_matches = 0

    for record in records:
        match_kind = _record_match_kind(area, record)
        if match_kind is None:
            continue
        if match_kind == "city":
            city_count += 1
        elif match_kind == "sido":
            sido_count += 1
        elif match_kind == "text":
            text_count += 1
        else:
            nationwide_count += 1
        if record.end_date is not None and today <= record.end_date <= today + timedelta(days=ENDING_SOON_DAYS):
            ending_soon += 1
        if record.extracted_amount_krw:
            amount += int(record.extracted_amount_krw)
        if _style_matches(record, style):
            style_matches += 1

    return _AreaStats(
        city_policy_count=city_count,
        sido_policy_count=sido_count,
        text_policy_count=text_count,
        nationwide_policy_count=nationwide_count,
        ending_soon_count=ending_soon,
        estimated_value_krw=amount,
        style_matched_count=style_matches,
    )


def _iter_recommendation_records(records: list[ExternalSourceRecord]):
    for record in records:
        alias_records = stay_discount_aliases.alias_records_for_record(record)
        if alias_records:
            yield from alias_records
        elif record.source_category != stay_discount_aliases.SOURCE_CATEGORY:
            yield record


def _record_match_kind(area: TravelArea, record) -> str | None:
    if _is_nationwide(record):
        return "nationwide"
    if getattr(record, "source_category", None) == stay_discount_aliases.SOURCE_CATEGORY and record.city:
        if record.region != area.sido:
            return None
        return "city" if _normalize_city(record.city) in {_normalize_city(city) for city in area.included_cities} else None
    if record.city and _normalize_city(record.city) in {_normalize_city(city) for city in area.included_cities}:
        return "city"
    if record.region == area.sido:
        return "sido"
    if _contains_city_text(area, record):
        return "text"
    return None


def _is_nationwide(record) -> bool:
    return bool(record.is_nationwide) or record.region == NATIONWIDE_REGION


def _normalize_city(value: str) -> str:
    return value.strip().removesuffix("특별시").removesuffix("광역시").removesuffix("시").removesuffix("군").removesuffix("구")


def _contains_city_text(area: TravelArea, record) -> bool:
    text = " ".join(
        value or ""
        for value in (
            record.title,
            record.organizer_text,
            record.benefit_text,
            record.raw_list_text,
            record.raw_detail_text,
        )
    )
    return any(city and city in text for city in area.included_cities)


def _style_matches(record, style: str | None) -> bool:
    normalized_style = _normalize(style)
    if normalized_style is None:
        return False
    record_styles = _string_values(record.inferred_travel_styles) + _string_values(record.tags)
    return normalized_style in record_styles


def _string_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _score(area: TravelArea, stats: _AreaStats) -> int:
    raw_score = (
        stats.city_policy_count * 35
        + stats.sido_policy_count * 20
        + stats.text_policy_count * 8
        + stats.ending_soon_count * 8
        + min(stats.estimated_value_krw // 10000, 20)
        + stats.style_matched_count * 5
        + stats.nationwide_policy_count * 2
        + area.priority // 5
    )
    return max(0, min(100, raw_score))


def _ranking_key(item: _RankedArea) -> tuple[int, int, int, int, int, int, int, str]:
    stats = item.stats
    return (
        stats.city_policy_count,
        stats.sido_policy_count,
        stats.ending_soon_count,
        min(stats.estimated_value_krw, 1_000_000_000),
        stats.style_matched_count,
        stats.nationwide_policy_count,
        item.area.priority,
        _reverse_string_sort(item.area.name),
    )


def _reverse_string_sort(value: str) -> str:
    return "".join(chr(0x10FFFF - ord(char)) for char in value)


def _normalize_travel_area_summary(summary: str) -> str:
    normalized = summary.strip()
    for old, new in _TRAVEL_AREA_SUMMARY_REPLACEMENTS:
        normalized = normalized.replace(old, new)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _reason(area: TravelArea, stats: _AreaStats) -> str:
    if stats.city_policy_count:
        return f"{area.name}에 포함된 도시 혜택이 있어 여행 동선과 잘 맞아요."
    if stats.sido_policy_count:
        return f"{area.sido} 지역 혜택과 {area.name} 여행 동선이 잘 맞아요."
    if stats.nationwide_policy_count:
        return f"전국 공통 혜택과 {area.name} 기본 추천도를 함께 고려했어요."
    return f"{area.name}은 {', '.join(area.tags[:3])} 테마에 맞는 대표 여행권역이에요."


def _to_recommendation(area: TravelArea, stats: _AreaStats) -> TravelAreaRecommendation:
    return TravelAreaRecommendation(
        travelAreaId=area.id,
        travelAreaName=area.name,
        sido=area.sido,
        includedCities=list(area.included_cities),
        summary=_normalize_travel_area_summary(area.summary),
        tags=list(area.tags),
        reason=_reason(area, stats),
        policyCount=stats.policy_count,
        localPolicyCount=stats.local_policy_count,
        nationwidePolicyCount=stats.nationwide_policy_count,
        endingSoonCount=stats.ending_soon_count,
        estimatedValueKrw=stats.estimated_value_krw,
        score=_score(area, stats),
    )
