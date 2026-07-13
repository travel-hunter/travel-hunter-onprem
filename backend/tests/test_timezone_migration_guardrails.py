from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "backend/alembic/versions/0024_local_kst_timestamp_data_shift.py"
EXPECTED_ALLOWLIST = (
    ("users", "updated_at"),
    ("user_notification_settings", "created_at"),
    ("user_notification_settings", "updated_at"),
    ("notification_deliveries", "scheduled_at"),
    ("notification_deliveries", "updated_at"),
    ("external_source_records", "last_fetched_at"),
    ("external_source_records", "last_verified_at"),
)
FORBIDDEN_COLUMN_PATTERN = re.compile(
    r"auth|security|token|expires?|expiry|password|otp|phone_verified|verification|invite",
    re.IGNORECASE,
)


def load_migration():
    spec = importlib.util.spec_from_file_location("timezone_shift_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_adjust_allowlist_matches_approved_inventory_exactly() -> None:
    migration = load_migration()

    assert migration.revision == "0024_local_kst_time_shift"
    assert len(migration.revision) <= 32
    assert migration.down_revision == "0023_policy_structured_detail"
    assert migration.ADJUST_ALLOWLIST == EXPECTED_ALLOWLIST


def test_no_security_expiry_token_or_verification_columns_are_adjusted() -> None:
    migration = load_migration()

    adjusted_names = [f"{table}.{column}" for table, column in migration.ADJUST_ALLOWLIST]

    assert not [name for name in adjusted_names if FORBIDDEN_COLUMN_PATTERN.search(name)]
    assert all("expires_at" not in name for name in adjusted_names)
    assert all("token" not in name for name in adjusted_names)


def test_update_sql_is_limited_to_allowlist_and_never_blanket_table_wide() -> None:
    migration = load_migration()

    for table, column in migration.ADJUST_ALLOWLIST:
        sql = migration._update_sql(table, column, "+")
        quoted_table = f'"{table}"'
        quoted_column = f'"{column}"'

        assert sql == (
            f"UPDATE {quoted_table} "
            f"SET {quoted_column} = {quoted_column} + INTERVAL '9 hours' "
            f"WHERE {quoted_column} IS NOT NULL"
        )
        assert "*" not in sql
        assert " WHERE " in sql
        assert re.search(r"SET\s+\*", sql, re.IGNORECASE) is None
        assert re.search(r"UPDATE\s+\S+\s+SET\s+\S+\s*=\s*\S+\s*[+]", sql, re.IGNORECASE)

    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert source.count("def _update_sql") == 1
    assert source.count("op.execute(_update_sql(table, column, operator))") == 1
    assert "UPDATE {table}" not in source
    assert "+ INTERVAL '9 hours'" not in source.replace("{SHIFT_INTERVAL_SQL}", "")


def test_default_online_upgrade_and_downgrade_are_safe_noops(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = load_migration()
    executed: list[str] = []
    monkeypatch.delenv(migration.ALLOW_ENV_VAR, raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(migration.op, "execute", executed.append)

    migration.upgrade()
    migration.downgrade()

    assert executed == []


def test_opt_in_local_runtime_guard_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = load_migration()
    fake_bind = SimpleNamespace(engine=SimpleNamespace(url="postgresql+psycopg://u:p@127.0.0.1:55432/db"))
    monkeypatch.setattr(migration.op, "get_bind", lambda: fake_bind)
    monkeypatch.setenv(migration.ALLOW_ENV_VAR, "1")
    monkeypatch.setenv("APP_ENV", "local")

    migration._assert_local_runtime_guard()


def test_guard_rejects_remote_or_protected_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = load_migration()
    monkeypatch.setenv(migration.ALLOW_ENV_VAR, "1")

    remote_bind = SimpleNamespace(engine=SimpleNamespace(url="postgresql+psycopg://u:p@db.example.com/app"))
    monkeypatch.setattr(migration.op, "get_bind", lambda: remote_bind)
    monkeypatch.setenv("APP_ENV", "local")
    with pytest.raises(migration.LocalTimezoneDataShiftGuardError, match="non-local PostgreSQL URL"):
        migration._assert_local_runtime_guard()

    local_bind = SimpleNamespace(engine=SimpleNamespace(url="postgresql+psycopg://u:p@127.0.0.1:55432/app"))
    monkeypatch.setattr(migration.op, "get_bind", lambda: local_bind)
    monkeypatch.setenv("APP_ENV", "staging")
    with pytest.raises(migration.LocalTimezoneDataShiftGuardError, match="outside local/docker/dev/test"):
        migration._assert_local_runtime_guard()


def test_offline_sql_generation_is_not_blocked_by_runtime_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = load_migration()
    monkeypatch.delenv(migration.ALLOW_ENV_VAR, raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: True)

    assert migration._should_run_shift() is True


def test_opt_in_local_upgrade_executes_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = load_migration()
    executed: list[str] = []
    fake_bind = SimpleNamespace(engine=SimpleNamespace(url="postgresql+psycopg://u:p@127.0.0.1:55432/db"))
    monkeypatch.setenv(migration.ALLOW_ENV_VAR, "1")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(migration.op, "get_bind", lambda: fake_bind)
    monkeypatch.setattr(migration.op, "execute", executed.append)

    migration.upgrade()

    update_sql = [sql for sql in executed if sql.startswith("UPDATE")]
    assert update_sql == [migration._update_sql(table, column, "+") for table, column in EXPECTED_ALLOWLIST]
    assert all("+ INTERVAL '9 hours'" in sql for sql in update_sql)


def test_rollback_and_check_query_strings_exist_for_each_allowlisted_column() -> None:
    migration = load_migration()

    assert len(migration.CHECK_QUERIES) == len(EXPECTED_ALLOWLIST)
    assert len(migration.ROLLBACK_CHECK_QUERIES) == len(EXPECTED_ALLOWLIST)

    joined_check_queries = "\n".join(migration.CHECK_QUERIES)
    joined_rollback_queries = "\n".join(migration.ROLLBACK_CHECK_QUERIES)
    for table, column in EXPECTED_ALLOWLIST:
        assert f"before/after review: {table}.{column}" in joined_check_queries
        assert f"rollback review: {table}.{column}" in joined_rollback_queries
        assert f"FROM {table}" in joined_check_queries
        assert f"WHERE {column} IS NOT NULL" in joined_check_queries
        assert f"FROM {table}" in joined_rollback_queries
        assert f"WHERE {column} IS NOT NULL" in joined_rollback_queries


def test_opt_in_downgrade_subtracts_nine_hours_for_same_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = load_migration()
    executed: list[str] = []
    fake_bind = SimpleNamespace(engine=SimpleNamespace(url="postgresql+psycopg://u:p@127.0.0.1:55432/db"))
    monkeypatch.setenv(migration.ALLOW_ENV_VAR, "1")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(migration.op, "get_bind", lambda: fake_bind)
    monkeypatch.setattr(migration.op, "execute", executed.append)

    migration.downgrade()

    update_sql = [sql for sql in executed if sql.startswith("UPDATE")]
    assert update_sql == [migration._update_sql(table, column, "-") for table, column in EXPECTED_ALLOWLIST]
    assert all("- INTERVAL '9 hours'" in sql for sql in update_sql)
