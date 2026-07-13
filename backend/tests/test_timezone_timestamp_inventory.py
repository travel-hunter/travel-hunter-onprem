from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
INVENTORY_PATH = FIXTURES_DIR / "timestamp_inventory_db_timezone_impact_20260710.md"
TIMESTAMP_SCHEMA_PATH = FIXTURES_DIR / "final_alembic_head_timestamp_columns.sql"
EXPECTED_TIMESTAMP_COLUMN_COUNT = 46
ALLOWED_BUCKETS = frozenset({"adjust", "keep", "investigate"})
EXPECTED_MIGRATION_ADJUST_COLUMNS = frozenset(
    {
        ("users", "updated_at"),
        ("user_notification_settings", "created_at"),
        ("user_notification_settings", "updated_at"),
        ("notification_deliveries", "scheduled_at"),
        ("notification_deliveries", "updated_at"),
        ("external_source_records", "last_fetched_at"),
        ("external_source_records", "last_verified_at"),
    }
)
STALE_FUTURE_SCHEMA_IDENTIFIERS = frozenset()
EXPECTED_BUCKETS_BY_COLUMN: dict[tuple[str, str], str] = {
    ("users", "created_at"): "investigate",
    ("users", "updated_at"): "adjust",
    ("policies", "created_at"): "investigate",
    ("auth_refresh_tokens", "created_at"): "keep",
    ("auth_refresh_tokens", "expires_at"): "keep",
    ("auth_refresh_tokens", "revoked_at"): "keep",
    ("social_accounts", "created_at"): "investigate",
    ("trips", "created_at"): "investigate",
    ("trips", "updated_at"): "investigate",
    ("trip_members", "joined_at"): "investigate",
    ("trip_policies", "added_at"): "investigate",
    ("trip_invites", "accepted_at"): "keep",
    ("trip_invites", "expires_at"): "keep",
    ("trip_invites", "created_at"): "keep",
    ("recommendations", "created_at"): "investigate",
    ("user_saved_policies", "saved_at"): "investigate",
    ("user_notification_settings", "created_at"): "adjust",
    ("user_notification_settings", "updated_at"): "adjust",
    ("users", "phone_verified_at"): "keep",
    ("notification_deliveries", "scheduled_at"): "adjust",
    ("notification_deliveries", "sent_at"): "investigate",
    ("notification_deliveries", "failed_at"): "investigate",
    ("notification_deliveries", "created_at"): "investigate",
    ("notification_deliveries", "updated_at"): "adjust",
    ("password_reset_tokens", "created_at"): "keep",
    ("password_reset_tokens", "expires_at"): "keep",
    ("password_reset_tokens", "used_at"): "keep",
    ("external_source_records", "last_fetched_at"): "adjust",
    ("external_source_records", "last_verified_at"): "adjust",
    ("external_source_records", "created_at"): "investigate",
    ("external_source_records", "updated_at"): "investigate",
    ("phone_verification_codes", "expires_at"): "keep",
    ("phone_verification_codes", "verified_at"): "keep",
    ("phone_verification_codes", "created_at"): "keep",
    ("policies", "normalized_at"): "investigate",
    ("policies", "last_verified_at"): "investigate",
    ("policies", "updated_at"): "investigate",
    ("admin_audit_logs", "created_at"): "keep",
    ("pending_signups", "created_at"): "keep",
    ("pending_signups", "expires_at"): "keep",
    ("users", "terms_accepted_at"): "keep",
    ("users", "privacy_accepted_at"): "keep",
    ("pending_signups", "terms_accepted_at"): "keep",
    ("pending_signups", "privacy_accepted_at"): "keep",
    ("pending_social_signups", "created_at"): "keep",
    ("pending_social_signups", "expires_at"): "keep",
}
SECURITY_EXPIRY_PATTERN = re.compile(
    r"auth|security|token|expires?|expiry|password|otp|phone_verified|verification|invite",
    re.IGNORECASE,
)
APPROVAL_MARKER = "APPROVED-SECURITY-EXPIRY-TIMESTAMP-ADJUST"


@dataclass(frozen=True)
class InventoryRow:
    table: str
    column: str
    bucket: str
    evidence_source: str
    approval_marker: str

    @property
    def key(self) -> tuple[str, str]:
        return self.table, self.column


@dataclass(frozen=True)
class SourceColumn:
    table: str
    column: str
    line_number: int

    @property
    def key(self) -> tuple[str, str]:
        return self.table, self.column


def _strip_cell_markup(value: str) -> str:
    value = value.strip()
    if value in {"—", "-"}:
        return ""
    if value.startswith("`") and value.endswith("`"):
        value = value[1:-1]
    return value.strip()


def parse_inventory(markdown: str) -> list[InventoryRow]:
    rows: list[InventoryRow] = []
    in_table = False

    for line_number, line in enumerate(markdown.splitlines(), start=1):
        if not line.startswith("|"):
            if in_table:
                break
            continue

        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        normalized_cells = [_strip_cell_markup(cell).lower() for cell in cells]
        if normalized_cells[:6] == [
            "table",
            "column",
            "bucket",
            "evidence source",
            "rationale",
            "approval marker",
        ]:
            in_table = True
            continue
        if in_table and all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        if not in_table:
            continue

        if len(cells) != 6:
            raise AssertionError(
                f"inventory row at line {line_number} must have 6 cells, found {len(cells)}: {line}"
            )

        bucket_cell = _strip_cell_markup(cells[2]).lower()
        bucket_hits = [bucket for bucket in ALLOWED_BUCKETS if re.search(rf"\b{bucket}\b", bucket_cell)]
        if len(bucket_hits) != 1 or bucket_cell not in ALLOWED_BUCKETS:
            raise AssertionError(
                f"inventory row at line {line_number} must have exactly one allowed bucket; "
                f"found {bucket_cell!r}"
            )

        rows.append(
            InventoryRow(
                table=_strip_cell_markup(cells[0]),
                column=_strip_cell_markup(cells[1]),
                bucket=bucket_cell,
                evidence_source=_strip_cell_markup(cells[3]),
                approval_marker=_strip_cell_markup(cells[5]),
            )
        )

    if not rows:
        raise AssertionError("timestamp inventory table was not found")
    return rows


def parse_timestamp_columns(sql: str) -> list[SourceColumn]:
    columns: list[SourceColumn] = []
    current_table: str | None = None

    for line_number, line in enumerate(sql.splitlines(), start=1):
        table_match = re.match(
            r"\s*CREATE TABLE (?:IF NOT EXISTS )?(?:public\.)?([A-Za-z_][A-Za-z0-9_]*) \(,?",
            line,
            re.IGNORECASE,
        )
        if table_match:
            current_table = table_match.group(1)
            continue

        alter_match = re.match(
            r"\s*ALTER TABLE (?:public\.)?([A-Za-z_][A-Za-z0-9_]*) "
            r"ADD COLUMN (?:IF NOT EXISTS )?([A-Za-z_][A-Za-z0-9_]*) "
            r"TIMESTAMP WITHOUT TIME ZONE\b",
            line,
            re.IGNORECASE,
        )
        if alter_match:
            columns.append(SourceColumn(alter_match.group(1), alter_match.group(2), line_number))
            continue

        if current_table and line.strip().startswith(");"):
            current_table = None
            continue
        if current_table and "timestamp without time zone" in line.lower():
            column_match = re.match(
                r"\s*([A-Za-z_][A-Za-z0-9_]*)\s+timestamp without time zone\b",
                line,
                re.IGNORECASE,
            )
            if not column_match:
                raise AssertionError(f"could not parse timestamp column at line {line_number}: {line}")
            columns.append(SourceColumn(current_table, column_match.group(1), line_number))

    return columns


def load_source_timestamp_columns() -> list[SourceColumn]:
    """Load the current tracked offline-Alembic-head fixture used by the inventory."""

    return parse_timestamp_columns(TIMESTAMP_SCHEMA_PATH.read_text(encoding="utf-8"))


def assert_inventory_is_complete(
    rows: list[InventoryRow],
    source_columns: list[SourceColumn],
    *,
    expected_count: int = EXPECTED_TIMESTAMP_COLUMN_COUNT,
    expected_buckets: dict[tuple[str, str], str] | None = None,
) -> None:
    assert len(rows) == expected_count
    assert len(source_columns) == expected_count

    row_keys = [row.key for row in rows]
    duplicate_keys = sorted({key for key in row_keys if row_keys.count(key) > 1})
    assert duplicate_keys == []

    source_keys = {column.key for column in source_columns}
    inventory_keys = set(row_keys)
    assert sorted(source_keys - inventory_keys) == []
    assert sorted(inventory_keys - source_keys) == []

    actual_buckets = {row.key: row.bucket for row in rows}
    if expected_buckets is not None:
        assert actual_buckets == expected_buckets

    for row in rows:
        assert row.bucket in ALLOWED_BUCKETS
        assert row.evidence_source, f"{row.table}.{row.column} is missing evidence provenance"
        security_or_expiry = SECURITY_EXPIRY_PATTERN.search(f"{row.table}.{row.column}")
        approved = APPROVAL_MARKER in row.approval_marker
        assert not (security_or_expiry and row.bucket == "adjust" and not approved), (
            f"{row.table}.{row.column} is security/expiry/auth/token/verification-like "
            f"and cannot be adjust without {APPROVAL_MARKER}"
        )


def test_timestamp_inventory_is_complete_and_policy_safe() -> None:
    inventory_markdown = INVENTORY_PATH.read_text(encoding="utf-8")
    fixture_sql = TIMESTAMP_SCHEMA_PATH.read_text(encoding="utf-8")
    rows = parse_inventory(inventory_markdown)
    source_columns = load_source_timestamp_columns()

    assert_inventory_is_complete(rows, source_columns, expected_buckets=EXPECTED_BUCKETS_BY_COLUMN)

    stale_hits = {
        identifier
        for identifier in STALE_FUTURE_SCHEMA_IDENTIFIERS
        if identifier in fixture_sql or identifier in inventory_markdown
    }
    assert stale_hits == set()

    actual_buckets = {row.key: row.bucket for row in rows}
    assert {key for key, bucket in actual_buckets.items() if bucket == "adjust"} == EXPECTED_MIGRATION_ADJUST_COLUMNS
    assert EXPECTED_MIGRATION_ADJUST_COLUMNS <= {column.key for column in source_columns}


@pytest.mark.parametrize(
    ("replacement", "match"),
    [
        ("| `users` | `updated_at` | `adjust, keep` | source | rationale | — |", "exactly one allowed bucket"),
        ("| `users` | `updated_at` | `defer` | source | rationale | — |", "exactly one allowed bucket"),
    ],
)
def test_inventory_parser_rejects_invalid_or_multiple_buckets(replacement: str, match: str) -> None:
    malformed = "\n".join(
        [
            "| table | column | bucket | evidence source | rationale | approval marker |",
            "| --- | --- | --- | --- | --- | --- |",
            replacement,
        ]
    )

    with pytest.raises(AssertionError, match=match):
        parse_inventory(malformed)


def test_inventory_completeness_rejects_duplicates_missing_rows_and_missing_evidence() -> None:
    valid_rows = [
        InventoryRow("users", "created_at", "investigate", "schema:1", ""),
        InventoryRow("users", "updated_at", "adjust", "runtime:1", ""),
    ]
    source_columns = [
        SourceColumn("users", "created_at", 1),
        SourceColumn("users", "updated_at", 2),
    ]

    with pytest.raises(AssertionError):
        assert_inventory_is_complete(valid_rows[:1], source_columns, expected_count=2)
    with pytest.raises(AssertionError):
        assert_inventory_is_complete([valid_rows[0], valid_rows[0]], source_columns, expected_count=2)
    with pytest.raises(AssertionError, match="missing evidence"):
        assert_inventory_is_complete(
            [valid_rows[0], InventoryRow("users", "updated_at", "adjust", "", "")],
            source_columns,
            expected_count=2,
        )


def test_inventory_completeness_rejects_security_adjust_without_marker() -> None:
    rows = [InventoryRow("auth_refresh_tokens", "expires_at", "adjust", "schema:1", "")]
    source_columns = [SourceColumn("auth_refresh_tokens", "expires_at", 1)]

    with pytest.raises(AssertionError, match=APPROVAL_MARKER):
        assert_inventory_is_complete(rows, source_columns, expected_count=1)
