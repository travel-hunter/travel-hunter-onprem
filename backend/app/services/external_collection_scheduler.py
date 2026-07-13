import asyncio
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, settings
from app.db.session import get_session_factory
from app.services.external_benefit_collection import (
    ExternalBenefitCollectionResult,
    collect_external_benefits_from_live_sources,
)
from app.services.travelmonth_collection import CollectionResult
from app.services.notification_scheduler import parse_run_at

KST = ZoneInfo("Asia/Seoul")
logger = logging.getLogger(__name__)
_ACTIVE_EXTERNAL_COLLECTION_SCHEDULER_LOCK = threading.Lock()
_active_external_collection_scheduler: "ExternalCollectionScheduler | None" = None


@dataclass
class ExternalCollectionSchedulerStatus:
    last_attempted_run_date: date | None = None
    last_successful_run_date: date | None = None
    last_parsed_count: int | None = None
    last_outcome: str | None = None
    last_error: str | None = None


def get_active_external_collection_scheduler() -> "ExternalCollectionScheduler | None":
    with _ACTIVE_EXTERNAL_COLLECTION_SCHEDULER_LOCK:
        return _active_external_collection_scheduler


def set_active_external_collection_scheduler(
    scheduler: "ExternalCollectionScheduler | None",
) -> None:
    with _ACTIVE_EXTERNAL_COLLECTION_SCHEDULER_LOCK:
        global _active_external_collection_scheduler
        _active_external_collection_scheduler = scheduler


def kst_now() -> datetime:
    return datetime.now(KST)


def run_external_collection_once(
    *,
    today: date | None = None,
    session_factory: sessionmaker[Session] | None = None,
) -> ExternalBenefitCollectionResult:
    run_date = today or kst_now().date()
    factory = session_factory or get_session_factory()
    db = factory()
    try:
        return collect_external_benefits_from_live_sources(db, today=run_date)
    finally:
        db.close()


class ExternalCollectionScheduler:
    def __init__(
        self,
        *,
        run_at: time,
        poll_seconds: int,
        min_parsed_count: int = 1,
        now_provider: Callable[[], datetime] = kst_now,
        collect: Callable[[date], CollectionResult] | None = None,
        sleep: Callable[[float], object] = asyncio.sleep,
    ) -> None:
        self.run_at = run_at
        self.poll_seconds = poll_seconds
        self.min_parsed_count = min_parsed_count
        self.now_provider = now_provider
        self.collect = collect or (lambda today: run_external_collection_once(today=today))
        self.sleep = sleep
        self.last_successful_run_date: date | None = None
        self.status = ExternalCollectionSchedulerStatus()

    def run_once_if_due(self) -> bool:
        now = self.now_provider()
        today = now.date()
        if self.last_successful_run_date == today:
            return False
        if now.timetz().replace(tzinfo=None) < self.run_at:
            return False

        self.status.last_attempted_run_date = today
        try:
            result = self.collect(today)
        except Exception as exc:
            self.status.last_parsed_count = None
            self.status.last_outcome = "error"
            self.status.last_error = str(exc)
            logger.exception("External collection failed.")
            return False

        if result.parsed_count < self.min_parsed_count:
            self.status.last_parsed_count = result.parsed_count
            self.status.last_outcome = "below_threshold"
            self.status.last_error = (
                f"parsed {result.parsed_count} records, "
                f"below minimum {self.min_parsed_count}"
            )
            logger.error(
                "External collection parsed %s records for %s, below minimum %s.",
                result.parsed_count,
                today.isoformat(),
                self.min_parsed_count,
            )
            return False

        outcome = getattr(result, "outcome", "success")
        self.last_successful_run_date = today
        self.status.last_successful_run_date = today
        self.status.last_parsed_count = result.parsed_count
        self.status.last_outcome = outcome
        self.status.last_error = (
            _format_source_errors(result)
            if outcome == "partial_success"
            and isinstance(result, ExternalBenefitCollectionResult)
            else None
        )
        logger.info(
            "External collection completed for %s with %s parsed records.",
            today.isoformat(),
            result.parsed_count,
        )
        return True

    async def run_forever(self) -> None:
        try:
            while True:
                await asyncio.to_thread(self.run_once_if_due)
                await self.sleep(self.poll_seconds)
        except asyncio.CancelledError:
            logger.info("External collection scheduler stopped.")
            raise


def validate_external_collection_scheduler_settings(
    settings_obj: Settings = settings,
) -> None:
    if not settings_obj.external_collection_scheduler_enabled:
        return
    if not settings_obj.database_url:
        raise RuntimeError(
            "DATABASE_URL is required when EXTERNAL_COLLECTION_SCHEDULER_ENABLED=true."
        )
    try:
        parse_run_at(settings_obj.external_collection_run_at)
    except ValueError as exc:
        raise ValueError(
            "EXTERNAL_COLLECTION_RUN_AT must use HH:MM or HH:MM:SS format."
        ) from exc
    if settings_obj.external_collection_poll_seconds < 1:
        raise ValueError("EXTERNAL_COLLECTION_POLL_SECONDS must be greater than 0.")
    if settings_obj.external_collection_min_parsed_count < 0:
        raise ValueError("EXTERNAL_COLLECTION_MIN_PARSED_COUNT must be 0 or greater.")


def get_external_collection_ops_health(
    settings_obj: Settings = settings,
) -> dict[str, object]:
    active_scheduler = get_active_external_collection_scheduler()
    status = active_scheduler.status if active_scheduler is not None else ExternalCollectionSchedulerStatus()
    return {
        "schedulerEnabled": settings_obj.external_collection_scheduler_enabled,
        "runAt": settings_obj.external_collection_run_at,
        "pollSeconds": settings_obj.external_collection_poll_seconds,
        "minParsedCount": settings_obj.external_collection_min_parsed_count,
        "lastAttemptedRunDate": status.last_attempted_run_date,
        "lastSuccessfulRunDate": status.last_successful_run_date,
        "lastParsedCount": status.last_parsed_count,
        "lastOutcome": status.last_outcome,
        "lastError": status.last_error,
    }


def build_external_collection_scheduler(
    settings_obj: Settings = settings,
) -> ExternalCollectionScheduler:
    return ExternalCollectionScheduler(
        run_at=parse_run_at(settings_obj.external_collection_run_at),
        poll_seconds=settings_obj.external_collection_poll_seconds,
        min_parsed_count=settings_obj.external_collection_min_parsed_count,
    )


def _format_source_errors(result: ExternalBenefitCollectionResult) -> str | None:
    errors = [
        f"{source.source_category}: {source.error}"
        for source in result.sources
        if source.error
    ]
    return "; ".join(errors) if errors else None


def start_external_collection_scheduler(
    settings_obj: Settings = settings,
) -> asyncio.Task[None] | None:
    if not settings_obj.external_collection_scheduler_enabled:
        set_active_external_collection_scheduler(None)
        return None

    validate_external_collection_scheduler_settings(settings_obj)
    scheduler = build_external_collection_scheduler(settings_obj)
    set_active_external_collection_scheduler(scheduler)
    return asyncio.create_task(
        scheduler.run_forever(),
        name="travel-hunter-external-collection-scheduler",
    )


async def stop_external_collection_scheduler(task: asyncio.Task[None] | None) -> None:
    if task is None:
        set_active_external_collection_scheduler(None)
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    set_active_external_collection_scheduler(None)
