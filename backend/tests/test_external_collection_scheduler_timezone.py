from __future__ import annotations

import os
import time as time_module
from collections.abc import Callable, Iterator
from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.services import external_collection_scheduler
from app.services.travelmonth_collection import CollectionResult


pytestmark = pytest.mark.skipif(
    not hasattr(time_module, "tzset"),
    reason="process TZ changes require time.tzset support",
)


@pytest.fixture
def set_process_timezone() -> Iterator[Callable[[str], None]]:
    original_tz = os.environ.get("TZ")

    def apply(tz_name: str) -> None:
        os.environ["TZ"] = tz_name
        time_module.tzset()

    try:
        yield apply
    finally:
        if original_tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original_tz
        time_module.tzset()


def make_result(parsed_count: int = 1) -> CollectionResult:
    return CollectionResult(
        source_name="여행가는 달",
        source_category="regional_benefit",
        parsed_count=parsed_count,
        created_or_updated_count=parsed_count,
    )


def assert_close_to_zero(delta: timedelta, *, tolerance_seconds: float = 2.0) -> None:
    assert abs(delta.total_seconds()) <= tolerance_seconds


def test_kst_now_returns_seoul_aware_datetime_independent_of_process_timezone(
    set_process_timezone: Callable[[str], None],
) -> None:
    for tz_name in ("UTC", "America/Los_Angeles"):
        set_process_timezone(tz_name)

        kst_value = external_collection_scheduler.kst_now()
        expected = datetime.now(timezone.utc).astimezone(external_collection_scheduler.KST)

        assert kst_value.tzinfo is external_collection_scheduler.KST
        assert kst_value.utcoffset() == timedelta(hours=9)
        assert_close_to_zero(kst_value - expected)


def test_due_check_uses_injected_kst_wall_clock_independent_of_process_timezone(
    set_process_timezone: Callable[[str], None],
) -> None:
    for tz_name in ("UTC", "America/Los_Angeles"):
        set_process_timezone(tz_name)
        calls: list[date] = []
        now_values = [
            datetime(2026, 1, 2, 2, 59, 59, tzinfo=external_collection_scheduler.KST),
            datetime(2026, 1, 2, 3, 0, 0, tzinfo=external_collection_scheduler.KST),
        ]
        scheduler = external_collection_scheduler.ExternalCollectionScheduler(
            run_at=time(3, 0),
            poll_seconds=60,
            now_provider=lambda: now_values.pop(0),
            collect=lambda today: calls.append(today) or make_result(),
        )

        assert scheduler.run_once_if_due() is False
        assert scheduler.run_once_if_due() is True
        assert calls == [date(2026, 1, 2)]
