from __future__ import annotations

import importlib.util
from pathlib import Path

from app.models import ExternalSourceRecord
from app.services.policy_semantic_mapping import map_external_source_semantics


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/0030_half_trip_five_semantics.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("local_half_trip_five_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record(source_id: int) -> ExternalSourceRecord:
    return ExternalSourceRecord(
        id=source_id,
        source_name="여행가는 달",
        source_type="official_campaign",
        source_category="local_half_trip",
        external_id=f"tour50-{source_id}",
        canonical_key=f"tour50-{source_id}",
        detail_url="https://example.com/detail",
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        title=f"대한민국 구석구석 반값여행 {source_id}",
        status="active",
        benefit_text="대한민국 구석구석 반값여행",
        benefit_value_text="여행비 50% 환급",
        raw_detail_text="legacy polluted detail",
        raw_payload={"notes": "영수증과 인증사진이 섞인 legacy 원문"},
        freshness_status="fresh",
    )


def test_frozen_migration_semantics_equal_runtime_mapper_for_scoped_records() -> None:
    migration = _migration()

    for frozen in migration.SCOPED_RECORDS:
        result = map_external_source_semantics(_record(frozen["external_source_record_id"]))
        assert result.structured_detail == frozen["structured_detail"]
        assert result.target_condition == frozen["target_condition"]
        assert result.policy_status == frozen["status"]
        assert result.verification_status == frozen["verification_status"]


def test_revision_is_scoped_guarded_and_mutates_only_allowed_policy_columns() -> None:
    migration = _migration()
    mutation = migration.MUTATION_SQL
    guard = migration.IDENTITY_GUARD_SQL

    assert migration.revision == "0030_half_trip_five_semantics"
    assert migration.down_revision == "0029_stay_discount_semantics"
    assert guard.startswith("DO $$")
    assert "local half-trip scoped identity prestate mismatch" in guard
    assert "candidate_count" in guard
    assert "IF matched_count = 0 THEN" in guard
    assert "matched_count <> 5" not in guard
    assert "JOIN external_source_records" in guard
    assert "source_category = 'local_half_trip'" in guard
    for slug in ("travelmonth-20", "travelmonth-24", "travelmonth-32", "travelmonth-21", "travelmonth-27"):
        assert slug in mutation
        assert slug in guard
    assert "dgtour-" not in mutation
    assert "SET\n  structured_detail =" in mutation
    assert "target_condition =" in mutation
    assert "status =" in mutation
    assert "verification_status =" in mutation
    for protected in (
        "SET id",
        "SET slug",
        "SET external_source_record_id",
        "SET source_canonical_key",
        "SET source_category",
        "SET source_url",
        "SET official_url",
        "SET raw_payload",
        "SET policy_id",
    ):
        assert protected not in mutation


def test_downgrade_is_explicit_guarded_data_noop(monkeypatch) -> None:
    migration = _migration()
    executed: list[str] = []
    monkeypatch.setattr(migration.op, "execute", executed.append)

    migration.downgrade()

    assert executed == [migration.DOWNGRADE_GUARD_SQL]
    assert "UPDATE " not in migration.DOWNGRADE_GUARD_SQL
    assert "DELETE " not in migration.DOWNGRADE_GUARD_SQL
    assert "INSERT " not in migration.DOWNGRADE_GUARD_SQL
