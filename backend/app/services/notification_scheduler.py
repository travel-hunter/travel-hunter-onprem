import asyncio
import logging
from collections.abc import Callable, Sequence
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, settings
from app.db.session import get_session_factory
from app.services.notification_delivery import (
    NotificationDeliveryTarget,
    calculate_deadline_notification_targets,
)
from app.services.notification_dispatch import (
    NotificationDispatchSummary,
    dispatch_deadline_notifications,
)

KST = ZoneInfo("Asia/Seoul")
logger = logging.getLogger(__name__)


def parse_run_at(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) not in {2, 3}:
        raise ValueError("NOTIFICATION_RUN_AT must use HH:MM or HH:MM:SS format.")

    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
    except ValueError as exc:
        raise ValueError("NOTIFICATION_RUN_AT must contain numeric time parts.") from exc

    return time(hour=hour, minute=minute, second=second)


def kst_now() -> datetime:
    return datetime.now(KST)


def run_notification_target_calculation_once(
    *,
    today: date | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> list[NotificationDeliveryTarget]:
    run_date = today or kst_now().date()
    factory = session_factory or get_session_factory()
    db = factory()
    try:
        return calculate_deadline_notification_targets(db, today=run_date)
    finally:
        db.close()


def run_notification_dispatch_once(
    *,
    today: date | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> NotificationDispatchSummary:
    run_date = today or kst_now().date()
    factory = session_factory or get_session_factory()
    db = factory()
    try:
        return dispatch_deadline_notifications(db, today=run_date)
    finally:
        db.close()


class NotificationScheduler:
    def __init__(
        self,
        *,
        run_at: time,
        poll_seconds: int,
        now_provider: Callable[[], datetime] = kst_now,
        calculate_targets: Callable[
            [date], Sequence[NotificationDeliveryTarget] | NotificationDispatchSummary
        ]
        | None = None,
        sleep: Callable[[float], object] = asyncio.sleep,
    ) -> None:
        self.run_at = run_at
        self.poll_seconds = poll_seconds
        self.now_provider = now_provider
        self.calculate_targets = calculate_targets or (
            lambda today: run_notification_dispatch_once(today=today)
        )
        self.sleep = sleep
        self.last_successful_run_date: date | None = None

    def run_once_if_due(self) -> bool:
        now = self.now_provider()
        today = now.date()
        if self.last_successful_run_date == today:
            return False
        if now.timetz().replace(tzinfo=None) < self.run_at:
            return False

        try:
            targets = self.calculate_targets(today)
        except Exception:
            logger.exception("Notification target calculation failed.")
            return False

        if getattr(targets, "hasDeferredRetries", False):
            logger.info(
                "Notification dispatch for %s has deferred retries and will run again.",
                today.isoformat(),
            )
            return False

        self.last_successful_run_date = today
        logger.info(
            "Notification target calculation completed for %s with %s targets.",
            today.isoformat(),
            len(targets),
        )
        return True

    async def run_forever(self) -> None:
        try:
            while True:
                await asyncio.to_thread(self.run_once_if_due)
                await self.sleep(self.poll_seconds)
        except asyncio.CancelledError:
            logger.info("Notification scheduler stopped.")
            raise


def validate_notification_scheduler_settings(settings_obj: Settings = settings) -> None:
    if not settings_obj.notification_scheduler_enabled:
        return
    if not settings_obj.database_url:
        raise RuntimeError(
            "DATABASE_URL is required when NOTIFICATION_SCHEDULER_ENABLED=true."
        )
    parse_run_at(settings_obj.notification_run_at)
    if settings_obj.notification_poll_seconds < 1:
        raise ValueError("NOTIFICATION_POLL_SECONDS must be greater than 0.")
    if settings_obj.notification_retry_max_attempts < 1:
        raise ValueError("NOTIFICATION_RETRY_MAX_ATTEMPTS must be greater than 0.")
    if settings_obj.notification_retry_delay_seconds < 0:
        raise ValueError("NOTIFICATION_RETRY_DELAY_SECONDS must be 0 or greater.")


def build_notification_scheduler(
    settings_obj: Settings = settings,
) -> NotificationScheduler:
    return NotificationScheduler(
        run_at=parse_run_at(settings_obj.notification_run_at),
        poll_seconds=settings_obj.notification_poll_seconds,
    )


def start_notification_scheduler(
    settings_obj: Settings = settings,
) -> asyncio.Task[None] | None:
    """Deadline notification scheduler is intentionally hard-disabled."""
    _ = settings_obj
    return None


async def stop_notification_scheduler(task: asyncio.Task[None] | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
