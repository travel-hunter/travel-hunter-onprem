"""draft guarded local KST timestamp data shift

Revision ID: 0024_local_kst_time_shift
Revises: 0023_policy_structured_detail
Create Date: 2026-07-10

This is a local-only data adjustment draft for timestamp columns whose runtime
provenance is an approved UTC-naive instant. It intentionally does not touch
security, token, invite, verification, or expiry timestamps.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from urllib.parse import urlparse

from alembic import context, op


revision: str = "0024_local_kst_time_shift"
down_revision: str | None = "0023_policy_structured_detail"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALLOW_ENV_VAR = "TRAVEL_HUNTER_ALLOW_LOCAL_TIMEZONE_DATA_SHIFT"
LOCAL_APP_ENVS = frozenset({"local", "docker", "development", "dev", "test"})
LOCAL_DATABASE_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "db", "postgres", "postgresql"})
SHIFT_INTERVAL_SQL = "INTERVAL '9 hours'"

# Approved G005 adjustment inventory. Do not broaden without updating the
# timestamp inventory, this guarded draft, and its tests together.
ADJUST_ALLOWLIST: tuple[tuple[str, str], ...] = (
    ("users", "updated_at"),
    ("user_notification_settings", "created_at"),
    ("user_notification_settings", "updated_at"),
    ("notification_deliveries", "scheduled_at"),
    ("notification_deliveries", "updated_at"),
    ("external_source_records", "last_fetched_at"),
    ("external_source_records", "last_verified_at"),
)

CHECK_QUERIES: tuple[str, ...] = tuple(
    f"""
    SELECT
        'before/after review: {table}.{column}' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN({column}) AS min_value,
        MAX({column}) AS max_value
    FROM {table}
    WHERE {column} IS NOT NULL
    """.strip()
    for table, column in ADJUST_ALLOWLIST
)

ROLLBACK_CHECK_QUERIES: tuple[str, ...] = tuple(
    f"""
    SELECT
        'rollback review: {table}.{column}' AS review_scope,
        COUNT(*) AS non_null_count,
        MIN({column}) AS min_value,
        MAX({column}) AS max_value
    FROM {table}
    WHERE {column} IS NOT NULL
    """.strip()
    for table, column in ADJUST_ALLOWLIST
)


class LocalTimezoneDataShiftGuardError(RuntimeError):
    """Raised when the local-only data shift guard fails closed."""


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _database_url_from_context() -> str:
    bind = op.get_bind()
    url = getattr(getattr(bind, "engine", None), "url", None) or getattr(bind, "url", None)
    if url is not None:
        return str(url)
    return context.config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL", "")


def _is_local_database_url(database_url: str) -> bool:
    parsed = urlparse(database_url)
    if not parsed.scheme.startswith("postgresql"):
        return False
    return parsed.hostname in LOCAL_DATABASE_HOSTS


def _is_shift_opted_in() -> bool:
    return os.environ.get(ALLOW_ENV_VAR) == "1"


def _assert_local_runtime_guard() -> None:
    """Require a local app env and local PostgreSQL URL for opted-in shifts."""

    app_env = os.environ.get("APP_ENV", "local").strip().lower()
    if app_env not in LOCAL_APP_ENVS:
        raise LocalTimezoneDataShiftGuardError(
            "Refusing local timezone data shift outside local/docker/dev/test APP_ENV; "
            f"got APP_ENV={app_env!r}."
        )

    database_url = _database_url_from_context()
    if not _is_local_database_url(database_url):
        raise LocalTimezoneDataShiftGuardError(
            "Refusing local timezone data shift against a non-local PostgreSQL URL. "
            "Allowed hosts are localhost, 127.0.0.1, ::1, db, postgres, and postgresql."
        )


def _should_run_shift() -> bool:
    # Alembic --sql mode must remain reviewable and include the audit/update SQL
    # without requiring local secrets or opt-in flags. Online execution is a safe
    # no-op by default; the data shift runs only with explicit local opt-in.
    if context.is_offline_mode():
        return True
    if not _is_shift_opted_in():
        return False
    _assert_local_runtime_guard()
    return True


def _update_sql(table: str, column: str, operator: str) -> str:
    quoted_table = _quote_identifier(table)
    quoted_column = _quote_identifier(column)
    return (
        f"UPDATE {quoted_table} "
        f"SET {quoted_column} = {quoted_column} {operator} {SHIFT_INTERVAL_SQL} "
        f"WHERE {quoted_column} IS NOT NULL"
    )


def _run_review_queries(queries: tuple[str, ...]) -> None:
    for query in queries:
        op.execute(query)


def _run_shift(operator: str) -> None:
    for table, column in ADJUST_ALLOWLIST:
        op.execute(_update_sql(table, column, operator))


def upgrade() -> None:
    if not _should_run_shift():
        return
    _run_review_queries(CHECK_QUERIES)
    _run_shift("+")
    _run_review_queries(CHECK_QUERIES)


def downgrade() -> None:
    if not _should_run_shift():
        return
    _run_review_queries(ROLLBACK_CHECK_QUERIES)
    _run_shift("-")
    _run_review_queries(ROLLBACK_CHECK_QUERIES)
