from __future__ import annotations

from datetime import date, datetime
from typing import Final
from zoneinfo import ZoneInfo

POLICY_STATUS_ACTIVE: Final = "active"
POLICY_STATUS_HIDDEN: Final = "hidden"

PUBLIC_POLICY_STATUSES: Final[frozenset[str]] = frozenset({POLICY_STATUS_ACTIVE})
KNOWN_POLICY_STATUSES: Final[frozenset[str]] = frozenset(
    {POLICY_STATUS_ACTIVE, POLICY_STATUS_HIDDEN}
)
KST: Final = ZoneInfo("Asia/Seoul")


def policy_visibility_date(now: datetime | None = None) -> date:
    instant = now or datetime.now(KST)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=KST)
    return instant.astimezone(KST).date()


def normalize_policy_status(value: str | None) -> str:
    """Return the effective policy status used by legacy rows.

    Existing app behavior treats missing/empty status as active for compatibility with
    older in-memory fixtures and rows created before the explicit status column.
    """

    return (value or POLICY_STATUS_ACTIVE).strip() or POLICY_STATUS_ACTIVE


def is_active_policy_status(value: str | None) -> bool:
    return normalize_policy_status(value) == POLICY_STATUS_ACTIVE


def is_hidden_policy_status(value: str | None) -> bool:
    return normalize_policy_status(value) == POLICY_STATUS_HIDDEN


def is_public_policy_status(value: str | None) -> bool:
    return normalize_policy_status(value) in PUBLIC_POLICY_STATUSES


def is_public_policy_on_date(
    status: str | None,
    end_date: date | None,
    *,
    today: date | None = None,
) -> bool:
    return is_public_policy_status(status) and is_policy_deadline_current(
        end_date,
        today=today,
    )


def is_policy_deadline_current(
    end_date: date | None,
    *,
    today: date | None = None,
) -> bool:
    effective_today = today or policy_visibility_date()
    return end_date is None or end_date >= effective_today


__all__ = [
    "KNOWN_POLICY_STATUSES",
    "POLICY_STATUS_ACTIVE",
    "POLICY_STATUS_HIDDEN",
    "PUBLIC_POLICY_STATUSES",
    "is_active_policy_status",
    "is_hidden_policy_status",
    "is_public_policy_status",
    "is_public_policy_on_date",
    "is_policy_deadline_current",
    "normalize_policy_status",
    "policy_visibility_date",
]
