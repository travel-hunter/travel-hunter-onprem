from __future__ import annotations

from typing import Final

POLICY_STATUS_ACTIVE: Final = "active"
POLICY_STATUS_HIDDEN: Final = "hidden"

PUBLIC_POLICY_STATUSES: Final[frozenset[str]] = frozenset({POLICY_STATUS_ACTIVE})
KNOWN_POLICY_STATUSES: Final[frozenset[str]] = frozenset(
    {POLICY_STATUS_ACTIVE, POLICY_STATUS_HIDDEN}
)


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


__all__ = [
    "KNOWN_POLICY_STATUSES",
    "POLICY_STATUS_ACTIVE",
    "POLICY_STATUS_HIDDEN",
    "PUBLIC_POLICY_STATUSES",
    "is_active_policy_status",
    "is_hidden_policy_status",
    "is_public_policy_status",
    "normalize_policy_status",
]
