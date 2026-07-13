from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.core.config import Settings
from app.services import notification_scheduler

KST = ZoneInfo("Asia/Seoul")


def test_parse_run_at_accepts_hour_minute_and_seconds() -> None:
    assert notification_scheduler.parse_run_at("09:30") == time(9, 30)
    assert notification_scheduler.parse_run_at("09:30:15") == time(9, 30, 15)


def test_parse_run_at_rejects_invalid_values() -> None:
    for value in ["9", "aa:00", "25:00"]:
        try:
            notification_scheduler.parse_run_at(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{value!r} should be rejected")


def test_scheduler_due_run_uses_disabled_dispatch_summary() -> None:
    calls: list[date] = []
    scheduler = notification_scheduler.NotificationScheduler(
        run_at=time(9, 0),
        poll_seconds=60,
        now_provider=lambda: datetime(2026, 5, 1, 9, 1, tzinfo=KST),
        calculate_targets=lambda today: calls.append(today) or [],
    )

    assert scheduler.run_once_if_due() is True
    assert scheduler.run_once_if_due() is False
    assert calls == [date(2026, 5, 1)]


def test_start_notification_scheduler_is_hard_disabled_even_if_setting_enabled() -> None:
    assert notification_scheduler.start_notification_scheduler(
        Settings(notification_scheduler_enabled=True, database_url="postgresql://example/db")
    ) is None
