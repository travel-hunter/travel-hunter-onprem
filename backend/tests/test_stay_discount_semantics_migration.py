from __future__ import annotations

from datetime import datetime
import importlib.util
from pathlib import Path

from app.models import ExternalSourceRecord
from app.services.policy_semantic_mapping import map_external_source_semantics


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/0029_stay_discount_semantics.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("stay_semantics_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _record(migration, source_id: int) -> ExternalSourceRecord:
    current = source_id == 35
    return ExternalSourceRecord(
        id=source_id,
        source_name=migration.SOURCE_NAME,
        source_type="official_campaign",
        source_url=migration.OFFICIAL_URL,
        source_category=migration.SOURCE_CATEGORY,
        external_id="stay-discount",
        canonical_key=migration.SOURCE_35_KEY if current else migration.SOURCE_33_KEY,
        logical_key=migration.LOGICAL_KEY,
        canonical_key_version=migration.KEY_VERSION,
        detail_url=migration.OFFICIAL_URL,
        collected_page_url=migration.OFFICIAL_URL,
        title="2026 대한민국 숙박세일 페스타",
        organizer_text="한국관광공사",
        organizers=["한국관광공사"],
        status="active",
        benefit_text="숙박 할인권",
        benefit_value_text="2/3/5/7만원 할인권",
        benefit_value_type="fixed_amount",
        tags=[],
        inferred_travel_styles=[],
        confidence=100,
        field_completeness=100,
        raw_list_text="원문 목록",
        raw_detail_text="원문 상세",
        raw_payload={
            "discountTiers": migration._TIERS,
            "issuePeriod": migration.SOURCE_35_ISSUE_PERIOD if current else migration.SOURCE_33_ISSUE_PERIOD,
            "stayPeriod": migration.SOURCE_35_STAY_PERIOD if current else migration.SOURCE_33_STAY_PERIOD,
            "usageArea": migration._USAGE_AREA,
            "usagePlace": migration._USAGE_PLACE,
            "usageMethod": migration._USAGE_METHOD,
            "earlyCloseWarning": True,
        },
        last_fetched_at=datetime(2026, 7, 14),
        freshness_status="fresh",
    )


def test_frozen_migration_semantics_equal_runtime_mapper_for_both_prestates() -> None:
    migration = _migration()

    assert map_external_source_semantics(_record(migration, 33)).structured_detail == migration.DESIRED_33
    assert map_external_source_semantics(_record(migration, 35)).structured_detail == migration.DESIRED_35


def test_revision_is_guarded_and_mutates_only_three_semantic_columns() -> None:
    migration = _migration()
    mutation = "\n".join(migration.MUTATION_SQL)

    assert migration.LEGACY_OLD_35["links"] == [{"label": "공식 안내", "url": migration.OFFICIAL_URL}]
    assert "legacyOld35" in migration.UPGRADE_SQL[0]
    assert migration.down_revision == "0027_source_provenance_keys"
    assert migration.UPGRADE_SQL[0].startswith("DO $$")
    assert "identity/raw/semantic prestate mismatch" in migration.UPGRADE_SQL[0]
    assert "source_category='stay_discount'" in migration.UPGRADE_SQL[0]
    assert "logical_key='stay-discount:2026-summer'" in migration.UPGRADE_SQL[0]
    assert "SET contact_text=NULL" in mutation
    assert "SET target_condition=NULL" in mutation
    assert "structured_detail=CASE" in mutation
    for protected in (
        "SET canonical_key=",
        "SET logical_key=",
        "SET external_source_record_id=",
        "SET official_url=",
        "SET source_url=",
        "SET status=",
        "SET raw_payload=",
        "SET policy_id=",
    ):
        assert protected not in mutation


def test_downgrade_is_an_explicit_guarded_data_noop(monkeypatch) -> None:
    migration = _migration()
    executed: list[str] = []
    monkeypatch.setattr(migration.op, "execute", executed.append)

    migration.downgrade()

    assert executed == [migration.DOWNGRADE_GUARD_SQL]
    assert "UPDATE " not in migration.DOWNGRADE_GUARD_SQL
    assert "DELETE " not in migration.DOWNGRADE_GUARD_SQL
    assert "INSERT " not in migration.DOWNGRADE_GUARD_SQL
