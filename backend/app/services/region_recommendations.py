from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import ExternalSourceRecord
from app.repositories import external_sources as external_source_repository
from app.schemas.recommendations import RegionRecommendation
from app.services.profile_preferences import ProfilePreferenceError, normalize_preferred_regions
from app.services import stay_discount_aliases


ENDING_SOON_DAYS = 14
NATIONWIDE_REGION = "전국"
RegionRecommendationError = ProfilePreferenceError


@dataclass
class _RegionStats:
    region: str
    policy_count: int = 0
    ending_soon_count: int = 0
    estimated_value_krw: int = 0
    style_matched_count: int = 0
    profile_region_match: bool = False
    nationwide: bool = False


def recommend_regions(
    db: Session,
    *,
    today: date | None = None,
    style: str | None = None,
    region: str | None = None,
    preferred_regions: list[str] | None = None,
    limit: int = 3,
) -> list[RegionRecommendation]:
    run_date = today or date.today()
    selected_regions = normalize_preferred_regions(preferred_regions)
    preferred_region = None if selected_regions else _normalize_region(region)
    selected_region_set = set(selected_regions or [])
    records = external_source_repository.list_regional_benefit_recommendation_records(db)
    regional_stats: dict[str, _RegionStats] = {}
    nationwide_stats = _RegionStats(region=NATIONWIDE_REGION, nationwide=True)

    for record in _iter_recommendation_records(records):
        target = nationwide_stats if _is_nationwide(record) else _stats_for_region(regional_stats, record.region)
        if target is None:
            continue
        _add_record(target, record, today=run_date, style=style)

    for stats in regional_stats.values():
        stats.profile_region_match = stats.region in selected_region_set or (preferred_region is not None and stats.region == preferred_region)

    ranked = sorted(
        regional_stats.values(),
        key=_ranking_key,
        reverse=True,
    )
    if selected_regions and len(selected_regions) > 1:
        ranked = _reserve_preferred_region_slots(ranked, selected_regions)
    if len(ranked) < limit and nationwide_stats.policy_count > 0:
        ranked = [*ranked, nationwide_stats]

    return [_to_recommendation(stats) for stats in ranked[:limit]]


def _reserve_preferred_region_slots(
    ranked: list[_RegionStats],
    preferred_regions: list[str],
) -> list[_RegionStats]:
    reserved: list[_RegionStats] = []
    reserved_regions: set[str] = set()
    for preferred_region in preferred_regions:
        match = next((stats for stats in ranked if stats.region == preferred_region), None)
        if match is None:
            continue
        reserved.append(match)
        reserved_regions.add(match.region)
    return [*reserved, *[stats for stats in ranked if stats.region not in reserved_regions]]


def _stats_for_region(
    stats_by_region: dict[str, _RegionStats],
    region: str | None,
) -> _RegionStats | None:
    if not region:
        return None
    if region == NATIONWIDE_REGION:
        return None
    if region not in stats_by_region:
        stats_by_region[region] = _RegionStats(region=region)
    return stats_by_region[region]


def _iter_recommendation_records(records: list[ExternalSourceRecord]):
    for record in records:
        alias_records = stay_discount_aliases.alias_records_for_record(record)
        if alias_records:
            yield from alias_records
        elif record.source_category != stay_discount_aliases.SOURCE_CATEGORY:
            yield record


def _is_nationwide(record) -> bool:
    return bool(record.is_nationwide) or record.region == NATIONWIDE_REGION


def _add_record(
    stats: _RegionStats,
    record,
    *,
    today: date,
    style: str | None,
) -> None:
    stats.policy_count += 1
    if record.end_date is not None and today <= record.end_date <= today + timedelta(days=ENDING_SOON_DAYS):
        stats.ending_soon_count += 1
    if record.extracted_amount_krw:
        stats.estimated_value_krw += int(record.extracted_amount_krw)
    if style and style in _string_values(record.inferred_travel_styles):
        stats.style_matched_count += 1


def _string_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _normalize_region(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _ranking_key(stats: _RegionStats) -> tuple[int, int, int, int, int, str]:
    return (
        stats.policy_count,
        stats.ending_soon_count,
        stats.estimated_value_krw,
        1 if stats.profile_region_match else 0,
        stats.style_matched_count,
        _reverse_string_sort(stats.region),
    )


def _reverse_string_sort(value: str) -> str:
    return "".join(chr(0x10FFFF - ord(char)) for char in value)


def _to_recommendation(stats: _RegionStats) -> RegionRecommendation:
    score = min(
        100,
        stats.policy_count * 25
        + stats.ending_soon_count * 10
        + min(stats.estimated_value_krw // 10000, 25)
        + min(stats.style_matched_count * 3, 6),
    )
    return RegionRecommendation(
        region=stats.region,
        title=f"{stats.region}이 지금 좋아요",
        reason=_reason(stats),
        policyCount=stats.policy_count,
        endingSoonCount=stats.ending_soon_count,
        estimatedValueKrw=stats.estimated_value_krw,
        score=score,
        styleMatchedCount=stats.style_matched_count,
    )


def _reason(stats: _RegionStats) -> str:
    if stats.nationwide:
        return "전국 혜택 추천"
    if stats.style_matched_count:
        return f"{stats.region} 맞춤 혜택 {stats.style_matched_count}개"
    if stats.ending_soon_count:
        return f"마감 임박 {stats.ending_soon_count}개"
    return f"{stats.region} 혜택 {stats.policy_count}개"
