from __future__ import annotations

import os
import time as time_module
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone

import pytest

from app.core import security


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


def assert_close_to_zero(delta: timedelta, *, tolerance_seconds: float = 2.0) -> None:
    assert abs(delta.total_seconds()) <= tolerance_seconds


def assert_close_to_nine_hours(delta: timedelta, *, tolerance_seconds: float = 2.0) -> None:
    assert abs(delta.total_seconds() - timedelta(hours=9).total_seconds()) <= tolerance_seconds


def test_process_timezone_controls_naive_datetime_now(
    set_process_timezone: Callable[[str], None],
) -> None:
    set_process_timezone("UTC")
    utc_local_naive = datetime.now()
    utc_aware_now = datetime.now(timezone.utc)

    set_process_timezone("Asia/Seoul")
    seoul_local_naive = datetime.now()
    seoul_aware_now = datetime.now(timezone.utc)

    assert utc_local_naive.tzinfo is None
    assert seoul_local_naive.tzinfo is None
    assert_close_to_zero(utc_local_naive - utc_aware_now.replace(tzinfo=None))
    assert_close_to_nine_hours(seoul_local_naive - seoul_aware_now.replace(tzinfo=None))
    assert_close_to_nine_hours(seoul_local_naive - utc_local_naive)


def test_aware_utc_now_stays_utc_across_process_timezones(
    set_process_timezone: Callable[[str], None],
) -> None:
    set_process_timezone("UTC")
    utc_process_value = datetime.now(timezone.utc)

    set_process_timezone("Asia/Seoul")
    seoul_process_value = datetime.now(timezone.utc)

    assert utc_process_value.tzinfo is timezone.utc
    assert seoul_process_value.tzinfo is timezone.utc
    assert utc_process_value.utcoffset() == timedelta(0)
    assert seoul_process_value.utcoffset() == timedelta(0)
    assert_close_to_zero(seoul_process_value - utc_process_value)


def test_utc_now_naive_is_naive_utc_semantic_independent_of_process_timezone(
    set_process_timezone: Callable[[str], None],
) -> None:
    set_process_timezone("Asia/Seoul")

    helper_value = security.utc_now_naive()
    aware_utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
    process_local_now = datetime.now()

    assert helper_value.tzinfo is None
    assert_close_to_zero(helper_value - aware_utc_now)
    assert_close_to_nine_hours(process_local_now - helper_value)

    set_process_timezone("UTC")
    utc_process_helper_value = security.utc_now_naive()
    aware_utc_after_switch = datetime.now(timezone.utc).replace(tzinfo=None)

    assert utc_process_helper_value.tzinfo is None
    assert_close_to_zero(utc_process_helper_value - aware_utc_after_switch)
