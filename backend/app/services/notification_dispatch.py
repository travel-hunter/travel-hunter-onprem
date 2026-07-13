from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.config import Settings, settings


@dataclass(frozen=True)
class NotificationDispatchSummary:
    candidates: int
    sent: int
    failed: int
    skipped: int
    retryCandidates: int
    deferredRetries: int
    providerEnabled: bool

    def __len__(self) -> int:
        return self.candidates

    @property
    def hasDeferredRetries(self) -> bool:
        return False


def dispatch_deadline_notifications(
    db: Session,
    *,
    today: date,
    settings_obj: Settings = settings,
    provider=None,
    now: datetime | None = None,
) -> NotificationDispatchSummary:
    """Notification dispatch is disabled; do not create deliveries or call providers."""
    _ = (db, today, settings_obj, provider, now)
    return NotificationDispatchSummary(
        candidates=0,
        sent=0,
        failed=0,
        skipped=0,
        retryCandidates=0,
        deferredRetries=0,
        providerEnabled=False,
    )


def list_retry_targets(*_args, **_kwargs) -> tuple[list, int]:
    return [], 0
