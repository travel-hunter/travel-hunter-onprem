import asyncio
from datetime import date, datetime, time

import anyio
import pytest

from app.core.config import Settings
from app.services import external_collection_scheduler
from app.services.travelmonth_collection import CollectionResult


def make_result(parsed_count: int = 1) -> CollectionResult:
    return CollectionResult(
        source_name="여행가는 달",
        source_category="regional_benefit",
        parsed_count=parsed_count,
        created_or_updated_count=parsed_count,
    )


def test_disabled_scheduler_does_not_create_task() -> None:
    settings = Settings(external_collection_scheduler_enabled=False)

    assert external_collection_scheduler.start_external_collection_scheduler(settings) is None


def test_enabled_scheduler_requires_database_url() -> None:
    settings = Settings(
        database_url="",
        external_collection_scheduler_enabled=True,
        external_collection_run_at="03:00",
        external_collection_poll_seconds=60,
    )

    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        external_collection_scheduler.validate_external_collection_scheduler_settings(settings)


def test_invalid_run_at_is_rejected_when_enabled() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://example",
        external_collection_scheduler_enabled=True,
        external_collection_run_at="invalid",
        external_collection_poll_seconds=60,
    )

    with pytest.raises(ValueError, match="EXTERNAL_COLLECTION_RUN_AT"):
        external_collection_scheduler.validate_external_collection_scheduler_settings(settings)


def test_invalid_poll_seconds_is_rejected_when_enabled() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://example",
        external_collection_scheduler_enabled=True,
        external_collection_poll_seconds=0,
    )

    with pytest.raises(ValueError, match="EXTERNAL_COLLECTION_POLL_SECONDS"):
        external_collection_scheduler.validate_external_collection_scheduler_settings(settings)


def test_run_time_after_target_runs_once_per_kst_date() -> None:
    calls: list[date] = []
    now_values = [
        datetime(2026, 5, 21, 3, 0, 0),
        datetime(2026, 5, 21, 12, 0, 0),
        datetime(2026, 5, 22, 3, 1, 0),
    ]

    scheduler = external_collection_scheduler.ExternalCollectionScheduler(
        run_at=time(3, 0),
        poll_seconds=60,
        now_provider=lambda: now_values.pop(0),
        collect=lambda today: calls.append(today) or make_result(),
    )

    assert scheduler.run_once_if_due() is True
    assert scheduler.run_once_if_due() is False
    assert scheduler.run_once_if_due() is True
    assert calls == [date(2026, 5, 21), date(2026, 5, 22)]


def test_failed_collection_does_not_mark_date_as_successful() -> None:
    calls: list[date] = []

    def collect(today: date) -> CollectionResult:
        calls.append(today)
        if len(calls) == 1:
            raise RuntimeError("official source is unavailable")
        return make_result()

    scheduler = external_collection_scheduler.ExternalCollectionScheduler(
        run_at=time(3, 0),
        poll_seconds=60,
        now_provider=lambda: datetime(2026, 5, 21, 3, 0, 0),
        collect=collect,
    )

    assert scheduler.run_once_if_due() is False
    assert scheduler.run_once_if_due() is True
    assert calls == [date(2026, 5, 21), date(2026, 5, 21)]


def test_parse_count_below_threshold_does_not_mark_date_as_successful() -> None:
    calls: list[date] = []

    def collect(today: date) -> CollectionResult:
        calls.append(today)
        if len(calls) == 1:
            return make_result(parsed_count=0)
        return make_result(parsed_count=58)

    scheduler = external_collection_scheduler.ExternalCollectionScheduler(
        run_at=time(3, 0),
        poll_seconds=60,
        now_provider=lambda: datetime(2026, 5, 21, 3, 0, 0),
        collect=collect,
        min_parsed_count=1,
    )

    assert scheduler.run_once_if_due() is False
    assert scheduler.run_once_if_due() is True
    assert calls == [date(2026, 5, 21), date(2026, 5, 21)]


def test_scheduler_status_records_success() -> None:
    scheduler = external_collection_scheduler.ExternalCollectionScheduler(
        run_at=time(3, 0),
        poll_seconds=60,
        now_provider=lambda: datetime(2026, 5, 21, 3, 0, 0),
        collect=lambda _today: make_result(parsed_count=58),
    )

    assert scheduler.run_once_if_due() is True

    assert scheduler.status.last_attempted_run_date == date(2026, 5, 21)
    assert scheduler.status.last_successful_run_date == date(2026, 5, 21)
    assert scheduler.status.last_parsed_count == 58
    assert scheduler.status.last_outcome == "success"
    assert scheduler.status.last_error is None


def test_scheduler_status_records_parse_threshold_failure() -> None:
    scheduler = external_collection_scheduler.ExternalCollectionScheduler(
        run_at=time(3, 0),
        poll_seconds=60,
        now_provider=lambda: datetime(2026, 5, 21, 3, 0, 0),
        collect=lambda _today: make_result(parsed_count=0),
        min_parsed_count=1,
    )

    assert scheduler.run_once_if_due() is False

    assert scheduler.status.last_attempted_run_date == date(2026, 5, 21)
    assert scheduler.status.last_successful_run_date is None
    assert scheduler.status.last_parsed_count == 0
    assert scheduler.status.last_outcome == "below_threshold"
    assert scheduler.status.last_error == "parsed 0 records, below minimum 1"


def test_scheduler_status_records_collection_error() -> None:
    def collect(_today: date) -> CollectionResult:
        raise RuntimeError("official source timeout")

    scheduler = external_collection_scheduler.ExternalCollectionScheduler(
        run_at=time(3, 0),
        poll_seconds=60,
        now_provider=lambda: datetime(2026, 5, 21, 3, 0, 0),
        collect=collect,
    )

    assert scheduler.run_once_if_due() is False

    assert scheduler.status.last_attempted_run_date == date(2026, 5, 21)
    assert scheduler.status.last_successful_run_date is None
    assert scheduler.status.last_parsed_count is None
    assert scheduler.status.last_outcome == "error"
    assert scheduler.status.last_error == "official source timeout"


def test_enabled_scheduler_rejects_negative_minimum_parse_count() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://example",
        external_collection_scheduler_enabled=True,
        external_collection_min_parsed_count=-1,
    )

    with pytest.raises(ValueError, match="EXTERNAL_COLLECTION_MIN_PARSED_COUNT"):
        external_collection_scheduler.validate_external_collection_scheduler_settings(settings)


def test_run_forever_exits_cleanly_on_cancel() -> None:
    async def run() -> bool:
        async def cancel_on_sleep(_seconds: float) -> None:
            raise asyncio.CancelledError

        scheduler = external_collection_scheduler.ExternalCollectionScheduler(
            run_at=time(3, 0),
            poll_seconds=60,
            now_provider=lambda: datetime(2026, 5, 21, 3, 0, 0),
            collect=lambda _today: make_result(parsed_count=0),
            sleep=cancel_on_sleep,
        )

        try:
            await scheduler.run_forever()
        except asyncio.CancelledError:
            return True
        return False

    assert anyio.run(run) is True


def test_run_external_collection_once_opens_and_closes_session(monkeypatch) -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    session = FakeSession()
    calls: list[tuple[object, date]] = []

    def collect(db, *, today):
        calls.append((db, today))
        return make_result()

    monkeypatch.setattr(
        external_collection_scheduler,
        "collect_external_benefits_from_live_sources",
        collect,
    )

    result = external_collection_scheduler.run_external_collection_once(
        today=date(2026, 5, 21),
        session_factory=lambda: session,
    )

    assert result.parsed_count == 1
    assert calls == [(session, date(2026, 5, 21))]
    assert session.closed is True
