from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import ExternalSourceRecord
from app.repositories import external_sources as external_source_repository
from app.schemas.ops import ExternalCollectionQualityReport, ExternalCollectionRegionQuality
from app.services.region_recommendations import NATIONWIDE_REGION, recommend_regions


SOURCE_CATEGORY = "local_half_trip"
SOURCE_NAME = "대한민국 반값여행"
ENDING_SOON_DAYS = 14


@dataclass
class _RegionQualityStats:
    region: str
    total_records: int = 0
    active_fresh_records: int = 0
    ending_soon_records: int = 0
    records_with_amount: int = 0
    estimated_value_krw: int = 0
    style_counts: Counter[str] = field(default_factory=Counter)


def get_external_collection_quality_report(
    db: Session,
    *,
    today: date | None = None,
    style: str | None = None,
    region: str | None = None,
    limit: int = 3,
    source_category: str | None = None,
) -> ExternalCollectionQualityReport:
    run_date = today or date.today()
    target_source_category = source_category or SOURCE_CATEGORY
    records = external_source_repository.list_external_source_records_by_category(
        db,
        source_category=target_source_category,
    )
    source_name = str(records[0].source_name) if records else str(SOURCE_NAME)
    region_stats: dict[str, _RegionQualityStats] = {}

    for record in records:
        if not _is_nationwide(record) and record.region:
            _add_region_record(
                region_stats.setdefault(
                    str(record.region),
                    _RegionQualityStats(region=str(record.region)),
                ),
                record,
                today=run_date,
            )

    return ExternalCollectionQualityReport(
        sourceName=source_name,
        sourceCategory=target_source_category,
        totalRecords=len(records),
        freshRecords=sum(1 for record in records if record.freshness_status == "fresh"),
        activeRecords=sum(1 for record in records if record.status == "active"),
        regionalRecords=sum(
            1 for record in records if not _is_nationwide(record) and record.region
        ),
        nationwideRecords=sum(1 for record in records if _is_nationwide(record)),
        recordsWithAmount=sum(
            1 for record in records if record.extracted_amount_krw is not None
        ),
        recordsWithStyles=sum(
            1 for record in records if _string_values(record.inferred_travel_styles)
        ),
        latestFetchedAt=_latest(record.last_fetched_at for record in records),
        latestVerifiedAt=_latest(record.last_verified_at for record in records),
        regions=[
            ExternalCollectionRegionQuality(
                region=stats.region,
                totalRecords=stats.total_records,
                activeFreshRecords=stats.active_fresh_records,
                endingSoonRecords=stats.ending_soon_records,
                recordsWithAmount=stats.records_with_amount,
                estimatedValueKrw=stats.estimated_value_krw,
                styleCounts=dict(sorted(stats.style_counts.items())),
            )
            for stats in sorted(region_stats.values(), key=lambda item: item.region)
        ],
        recommendationPreview=recommend_regions(
            db,
            today=run_date,
            style=style,
            region=region,
            limit=limit,
        ),
    )


def _add_region_record(
    stats: _RegionQualityStats,
    record: ExternalSourceRecord,
    *,
    today: date,
) -> None:
    stats.total_records += 1
    if record.status == "active" and record.freshness_status == "fresh":
        stats.active_fresh_records += 1
    if (
        record.end_date is not None
        and today <= record.end_date <= today + timedelta(days=ENDING_SOON_DAYS)
    ):
        stats.ending_soon_records += 1
    if record.extracted_amount_krw is not None:
        stats.records_with_amount += 1
        stats.estimated_value_krw += int(record.extracted_amount_krw)
    stats.style_counts.update(_string_values(record.inferred_travel_styles))


def _is_nationwide(record: ExternalSourceRecord) -> bool:
    return bool(record.is_nationwide) or record.region == NATIONWIDE_REGION


def _string_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _latest(values) -> datetime | None:
    dated_values = [value for value in values if value is not None]
    if not dated_values:
        return None
    return max(dated_values)
