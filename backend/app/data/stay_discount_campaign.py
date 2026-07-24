from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import Protocol, TypeVar

from app.data.source_provenance import STAY_DISCOUNT_LOGICAL_KEY


STAY_DISCOUNT_SOURCE_CATEGORY = "stay_discount"
STAY_DISCOUNT_CAMPAIGN_KEY = STAY_DISCOUNT_LOGICAL_KEY


class StayDiscountRecord(Protocol):
    source_category: str
    canonical_key: str
    logical_key: str | None
    end_date: date | None
    last_fetched_at: datetime
    last_verified_at: datetime | None
    id: int | None


RecordT = TypeVar("RecordT", bound=StayDiscountRecord)


def select_current_stay_discount_record(records: Iterable[RecordT]) -> RecordT | None:
    candidates = [
        record
        for record in records
        if record.source_category == STAY_DISCOUNT_SOURCE_CATEGORY
    ]
    if not candidates:
        return None

    logical_campaign_matches = [
        record
        for record in candidates
        if getattr(record, "logical_key", None) == STAY_DISCOUNT_CAMPAIGN_KEY
        or (
            getattr(record, "logical_key", None) is None
            and record.canonical_key == STAY_DISCOUNT_CAMPAIGN_KEY
        )
    ]
    if not logical_campaign_matches:
        return max(candidates, key=_current_snapshot_rank)
    return max(logical_campaign_matches, key=_current_snapshot_rank)


def _normalized_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min
    if value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def _current_snapshot_rank(
    record: StayDiscountRecord,
) -> tuple[datetime, datetime, date, int]:
    return (
        _normalized_datetime(getattr(record, "last_verified_at", None)),
        _normalized_datetime(record.last_fetched_at),
        record.end_date or date.min,
        int(record.id or 0),
    )
