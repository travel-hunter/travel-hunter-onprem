from dataclasses import dataclass
from datetime import date
from typing import Sequence

from sqlalchemy.orm import Session

DEFAULT_NOTIFICATION_CHANNEL = "disabled"
STATUS_PENDING = "pending"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"
DEADLINE_LEAD_DAYS = (7, 1)


@dataclass(frozen=True)
class NotificationDeliveryTarget:
    deliveryId: int
    userId: int
    userName: str
    policyId: int
    policyTitle: str
    policySlug: str | None
    leadDay: int
    targetDeadlineDate: date
    channel: str
    deliveryStatus: str


def calculate_deadline_notification_targets(
    db: Session,
    *,
    today: date,
    lead_days: Sequence[int] = DEADLINE_LEAD_DAYS,
    channel: str = DEFAULT_NOTIFICATION_CHANNEL,
    scheduled_at=None,
) -> list[NotificationDeliveryTarget]:
    """Notification runtime is intentionally disabled; history table is inert."""
    _ = (db, today, lead_days, channel, scheduled_at)
    return []


def target_from_delivery(_delivery) -> NotificationDeliveryTarget | None:
    return None


def deadline_enabled_for_user(_user) -> bool:
    return False
