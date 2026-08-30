from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_migration() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0031_digital_tourism_resident_card_identity.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0031_dgtour_identity", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_structured_migration() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0032_dgtour_structured_detail.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0032_dgtour_structured", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_participant_scope_migration() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0033_dgtour_participant_scope.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0033_dgtour_scope", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_detail_url_migration() -> ModuleType:
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0034_dgtour_detail_url_cleanup.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0034_dgtour_detail_urls", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_digital_tourism_identity_migration_metadata_and_scope() -> None:
    migration = _load_migration()
    upgrade_sql = "\n".join(migration.UPGRADE_SQL)

    assert migration.revision == "0031_dgtour_identity"
    assert migration.down_revision == "0030_half_trip_five_semantics"
    assert "digital_tourism_resident_card" in upgrade_sql
    assert "디지털관광주민증" in upgrade_sql
    assert "https://korean.visitkorea.or.kr/dgtourcard/" in upgrade_sql
    assert (
        "https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?"
        "mtpcDoCd=12&signguCd=12790"
    ) in upgrade_sql
    assert "https://www.haenam50.kr/index" in upgrade_sql
    assert "p.official_url LIKE 'https://korean.visitkorea.or.kr/dgtourcard/%'" in upgrade_sql
    assert "r.detail_url LIKE 'https://korean.visitkorea.or.kr/dgtourcard/%'" in upgrade_sql
    assert "ELSE 'https://korean.visitkorea.or.kr/dgtourcard/'" in upgrade_sql
    assert "p.slug LIKE 'dgtour-%'" in upgrade_sql
    assert "r.source_category = 'local_half_trip'" in upgrade_sql
    assert "r.title ILIKE '%디지털관광주민증%'" in upgrade_sql
    assert "r.title ILIKE '%대한민국 반값여행%'" in upgrade_sql
    assert "NOT EXISTS" in upgrade_sql


def test_digital_tourism_identity_migration_executes_all_statements(monkeypatch) -> None:
    migration = _load_migration()
    executed: list[str] = []

    monkeypatch.setattr(migration.op, "execute", executed.append)

    migration.upgrade()
    assert executed == migration.UPGRADE_SQL

    executed.clear()
    migration.downgrade()
    assert executed == [migration.DOWNGRADE_GUARD_SQL]
    assert "no-op" in migration.DOWNGRADE_GUARD_SQL
    assert "DELETE" not in migration.DOWNGRADE_GUARD_SQL.upper()
    assert "INSERT" not in migration.DOWNGRADE_GUARD_SQL.upper()


def test_digital_tourism_structured_detail_migration_replaces_conflated_json(
    monkeypatch,
) -> None:
    migration = _load_structured_migration()
    executed: list[str] = []

    assert migration.revision == "0032_dgtour_structured"
    assert migration.down_revision == "0031_dgtour_identity"
    assert "structured_detail" in migration.STRUCTURED_DETAIL_SQL
    assert "supportContent" in migration.STRUCTURED_DETAIL_SQL
    assert "applicationTarget" in migration.STRUCTURED_DETAIL_SQL
    assert "requiredDocuments" in migration.STRUCTURED_DETAIL_SQL
    assert "notes" in migration.STRUCTURED_DETAIL_SQL
    assert "별도 제출 서류 없음 · 디지털관광주민증 발급/제시 기준으로 적용" in (
        migration.STRUCTURED_DETAIL_SQL
    )
    assert "대한민국 반값여행" not in migration.STRUCTURED_DETAIL_SQL
    assert "links" not in migration.STRUCTURED_DETAIL_SQL

    monkeypatch.setattr(migration.op, "execute", executed.append)
    migration.upgrade()
    assert executed == [migration.STRUCTURED_DETAIL_SQL]

    executed.clear()
    migration.downgrade()
    assert executed == [migration.DOWNGRADE_GUARD_SQL]


def test_digital_tourism_participant_scope_migration_hides_nonparticipants(
    monkeypatch,
) -> None:
    migration = _load_participant_scope_migration()
    upgrade_sql = "\n".join(migration.UPGRADE_SQL)
    executed: list[str] = []

    assert migration.revision == "0033_dgtour_scope"
    assert migration.down_revision == "0032_dgtour_structured"
    assert "dgtour-강진-7" not in upgrade_sql
    assert "강진" not in migration.OFFICIAL_CITY_VALUES
    assert "남해" not in migration.OFFICIAL_CITY_VALUES
    assert "영암" not in migration.OFFICIAL_CITY_VALUES
    assert "횡성" not in migration.OFFICIAL_CITY_VALUES
    assert "하동" in migration.OFFICIAL_CITY_VALUES
    assert "해남" in migration.OFFICIAL_CITY_VALUES
    assert "status = 'hidden'" in migration.POLICY_SCOPE_SQL
    assert "freshness_status = 'stale'" in migration.EXTERNAL_RECORD_SCOPE_SQL
    assert "source_category = 'digital_tourism_resident_card'" in upgrade_sql
    assert "NOT IN (SELECT city_name FROM official)" in upgrade_sql

    monkeypatch.setattr(migration.op, "execute", executed.append)

    migration.upgrade()
    assert executed == migration.UPGRADE_SQL

    executed.clear()
    migration.downgrade()
    assert executed == [migration.DOWNGRADE_GUARD_SQL]
    assert "no-op" in migration.DOWNGRADE_GUARD_SQL


def test_digital_tourism_detail_url_migration_rewrites_half_trip_copy_and_urls(
    monkeypatch,
) -> None:
    migration = _load_detail_url_migration()
    upgrade_sql = "\n".join(migration.UPGRADE_SQL)
    executed: list[str] = []

    assert migration.revision == "0034_dgtour_detail_urls"
    assert migration.down_revision == "0033_dgtour_scope"
    assert "structured_detail" in migration.POLICY_DETAIL_URL_SQL
    assert "숙박·식음·체험·관광지 제휴 혜택" in upgrade_sql
    assert "VisitKorea/대한민국 구석구석에서 디지털관광주민증을 발급" in upgrade_sql
    assert "mtpcDoCd=48&signguCd=48850" in upgrade_sql
    assert "mtpcDoCd=12&signguCd=12850" in upgrade_sql
    assert "mtpcDoCd=26&signguCd=26140" in upgrade_sql
    assert "official_url = digital.official_url" in migration.POLICY_DETAIL_URL_SQL
    assert "apply_url = NULL" in migration.POLICY_DETAIL_URL_SQL
    assert "raw_payload = r.raw_payload || jsonb_build_object" in migration.EXTERNAL_RECORD_DETAIL_URL_SQL
    assert "hadongtrip.kr" not in upgrade_sql
    assert "wandotrip.kr" not in upgrade_sql
    assert "haenam50.kr" not in upgrade_sql
    assert "tour50.do" not in upgrade_sql
    assert "대한민국 반값여행" not in upgrade_sql
    assert "50% 환급" not in upgrade_sql
    assert "최대 20만원" not in upgrade_sql

    monkeypatch.setattr(migration.op, "execute", executed.append)

    migration.upgrade()
    assert executed == migration.UPGRADE_SQL

    executed.clear()
    migration.downgrade()
    assert executed == [migration.DOWNGRADE_GUARD_SQL]
    assert "no-op" in migration.DOWNGRADE_GUARD_SQL
