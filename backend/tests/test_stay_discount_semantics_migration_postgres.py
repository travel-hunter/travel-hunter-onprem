from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from scripts import stay_discount_semantics_snapshot as snapshot_cli


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic/versions/0029_stay_discount_semantics.py"
)
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_MIGRATION_TESTS") != "1",
    reason="set RUN_POSTGRES_MIGRATION_TESTS=1 for local PostgreSQL migration tests",
)


def _migration():
    spec = importlib.util.spec_from_file_location("stay_semantics_pg_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _base_url() -> str:
    value = os.getenv(
        "POSTGRES_MIGRATION_TEST_DATABASE_URL",
        "postgresql://travelhunter:travelhunter@127.0.0.1:55432/travelhunter",
    ).replace("postgresql+psycopg://", "postgresql://", 1)
    parsed = urlsplit(value)
    if parsed.hostname not in LOCAL_HOSTS or not parsed.path.strip("/"):
        raise RuntimeError("0029 PostgreSQL tests require an explicit loopback database")
    return value


def _url_for(database: str) -> str:
    parsed = urlsplit(_base_url())
    return urlunsplit((parsed.scheme, parsed.netloc, f"/{database}", parsed.query, parsed.fragment))


@contextmanager
def _database() -> Iterator[tuple[str, str]]:
    name = f"travelhunter_test_g003_{uuid4().hex[:16]}"
    admin_url = _url_for("postgres")
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
    try:
        yield name, _url_for(name)
    finally:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()",
                (name,),
            )
            connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))


DDL = """
CREATE TABLE alembic_version (version_num varchar(64) PRIMARY KEY);
INSERT INTO alembic_version VALUES ('0027_source_provenance_keys');
CREATE TABLE external_source_records (
  id bigint PRIMARY KEY, source_name varchar(100) NOT NULL, source_type varchar(50) NOT NULL,
  source_url varchar(500) NOT NULL, source_category varchar(80) NOT NULL,
  external_id varchar(160) NOT NULL, canonical_key varchar(160) NOT NULL,
  logical_key varchar(200), canonical_key_version varchar(30), detail_url varchar(500),
  collected_page_url varchar(500) NOT NULL, title varchar(300) NOT NULL,
  contact_text varchar(200), raw_list_text text NOT NULL, raw_detail_text text NOT NULL,
  raw_payload jsonb NOT NULL, status varchar(30) NOT NULL
);
CREATE TABLE policies (
  id bigint PRIMARY KEY, slug varchar(160) UNIQUE, title varchar(200) NOT NULL,
  source_name varchar(100), source_category varchar(80), external_source_record_id bigint UNIQUE,
  source_canonical_key varchar(160), official_url varchar(500), source_url varchar(500),
  status varchar(20) NOT NULL, target_condition text, structured_detail jsonb,
  FOREIGN KEY (external_source_record_id) REFERENCES external_source_records(id)
);
CREATE TABLE user_saved_policies (
  id bigint PRIMARY KEY, user_id bigint NOT NULL, policy_id bigint NOT NULL REFERENCES policies(id)
);
CREATE TABLE trip_policies (
  id bigint PRIMARY KEY, trip_id bigint NOT NULL, policy_id bigint NOT NULL REFERENCES policies(id)
);
CREATE TABLE policy_documents (
  id bigint PRIMARY KEY, policy_id bigint NOT NULL REFERENCES policies(id),
  document_name varchar(100) NOT NULL
);
CREATE TABLE notification_deliveries (
  id bigint PRIMARY KEY, user_id bigint NOT NULL, policy_id bigint NOT NULL REFERENCES policies(id),
  status varchar(20) NOT NULL
);
"""


def _payload(migration, source_id: int) -> dict[str, object]:
    current = source_id == 35
    return {
        "discountTiers": migration._TIERS,
        "issuePeriod": migration.SOURCE_35_ISSUE_PERIOD if current else migration.SOURCE_33_ISSUE_PERIOD,
        "stayPeriod": migration.SOURCE_35_STAY_PERIOD if current else migration.SOURCE_33_STAY_PERIOD,
        "usageArea": migration._USAGE_AREA,
        "usagePlace": migration._USAGE_PLACE,
        "usageMethod": migration._USAGE_METHOD,
        "earlyCloseWarning": True,
        "unrelatedEvidence": {"preserved": source_id},
    }


def _seed(connection: psycopg.Connection, kind: str, detail_shape: str = "canonical") -> None:
    migration = _migration()
    source_ids = [33] if kind == "single_23_33" else [33, 35]
    for source_id in source_ids:
        current = source_id == 35
        connection.execute(
            "INSERT INTO external_source_records VALUES "
            "(%s,%s,'official_campaign',%s,'stay_discount','stay-discount',%s,%s,'snapshot-v1',%s,%s,%s,%s,%s,%s,%s,'active')",
            (
                source_id,
                migration.SOURCE_NAME,
                migration.OFFICIAL_URL,
                migration.SOURCE_35_KEY if current else migration.SOURCE_33_KEY,
                migration.LOGICAL_KEY,
                migration.OFFICIAL_URL,
                migration.OFFICIAL_URL,
                f"Stay source {source_id}",
                migration.POLLUTED_SOURCE_35_CONTACT if current else migration.POLLUTED_SOURCE_33_CONTACT,
                f"raw-list-{source_id}",
                f"raw-detail-{source_id}",
                Jsonb(_payload(migration, source_id)),
            ),
        )
    desired_source = 33 if kind == "single_23_33" else 35
    if detail_shape == "legacy_old_links":
        polluted = migration.LEGACY_OLD_33 if kind == "single_23_33" else migration.LEGACY_OLD_35
    else:
        polluted = migration.POLLUTED_33 if kind == "single_23_33" else migration.POLLUTED_35
    target = (
        migration.POLLUTED_POLICY_33_TARGET
        if kind == "single_23_33"
        else migration.POLLUTED_POLICY_35_TARGET
    )
    connection.execute(
        "INSERT INTO policies VALUES (23,'travelmonth-33','canonical stay',%s,'stay_discount',%s,%s,%s,%s,'active',%s,%s)",
        (
            migration.SOURCE_NAME,
            desired_source,
            migration.SOURCE_33_KEY if kind == "single_23_33" else migration.SOURCE_35_KEY,
            migration.OFFICIAL_URL,
            migration.OFFICIAL_URL,
            target,
            Jsonb(polluted),
        ),
    )
    if kind == "merged_26_35":
        connection.execute(
            "INSERT INTO policies VALUES (26,'travelmonth-35','hidden stay',%s,'stay_discount',NULL,%s,%s,%s,'hidden',%s,%s)",
            (
                migration.SOURCE_NAME,
                migration.SOURCE_35_KEY,
                migration.OFFICIAL_URL,
                migration.OFFICIAL_URL,
                target,
                Jsonb(polluted),
            ),
        )
    connection.execute(
        "INSERT INTO external_source_records VALUES "
        "(99,'unrelated','internal','https://unrelated.test','other','other','other-key',NULL,NULL,NULL,"
        "'https://unrelated.test','Unrelated','keep-contact','keep-list','keep-detail','{}','active')"
    )
    connection.execute(
        "INSERT INTO policies VALUES "
        "(99,'unrelated-policy','Unrelated',NULL,'other',99,'other-key','https://unrelated.test',"
        "'https://unrelated.test','active','keep-target','{\"conditions\":[]}'::jsonb)"
    )
    connection.execute("INSERT INTO user_saved_policies VALUES (1,7,23)")
    connection.execute("INSERT INTO trip_policies VALUES (1,8,23)")
    connection.execute("INSERT INTO policy_documents VALUES (1,23,'예약 확인')")
    connection.execute("INSERT INTO notification_deliveries VALUES (1,7,23,'sent')")
    connection.commit()


def _all_rows(connection: psycopg.Connection) -> dict[str, list[object]]:
    result = {}
    for table in (
        "external_source_records",
        "policies",
        "user_saved_policies",
        "trip_policies",
        "policy_documents",
        "notification_deliveries",
    ):
        result[table] = [row[0] for row in connection.execute(
            f"SELECT to_jsonb(t) FROM {table} t ORDER BY id"
        ).fetchall()]
    return result


def _run(connection: psycopg.Connection, statements: tuple[str, ...]) -> None:
    for statement in statements:
        connection.execute(statement)


@pytest.mark.parametrize(
    ("kind", "detail_shape"),
    [
        ("single_23_33", "canonical"),
        ("merged_26_35", "canonical"),
        ("merged_26_35", "legacy_old_links"),
    ],
)
def test_dual_prestate_success_idempotency_exact_scope_and_snapshot_restore(
    kind: str, detail_shape: str, tmp_path: Path
) -> None:
    migration = _migration()
    with _database() as (database, url), psycopg.connect(url) as connection:
        connection.execute(DDL)
        _seed(connection, kind, detail_shape)
        before = _all_rows(connection)
        artifact = tmp_path / f"{kind}.json"
        export = snapshot_cli.export_snapshot(url, database, artifact)

        _run(connection, migration.UPGRADE_SQL)
        connection.commit()
        after_first = _all_rows(connection)
        _run(connection, migration.UPGRADE_SQL)
        connection.commit()
        assert _all_rows(connection) == after_first

        desired = migration.DESIRED_33 if kind == "single_23_33" else migration.DESIRED_35
        assert connection.execute(
            "SELECT id,target_condition,structured_detail FROM policies WHERE id IN (23,26) ORDER BY id"
        ).fetchall() == [
            (policy_id, None, desired)
            for policy_id in ([23] if kind == "single_23_33" else [23, 26])
        ]
        assert connection.execute(
            "SELECT id,contact_text FROM external_source_records WHERE id IN (33,35) ORDER BY id"
        ).fetchall() == [
            (source_id, None)
            for source_id in ([33] if kind == "single_23_33" else [33, 35])
        ]
        for table in (
            "user_saved_policies",
            "trip_policies",
            "policy_documents",
            "notification_deliveries",
        ):
            assert after_first[table] == before[table]
            assert connection.execute(
                f"SELECT count(*) FROM {table} child LEFT JOIN policies parent "
                "ON parent.id=child.policy_id WHERE parent.id IS NULL"
            ).fetchone() == (0,)
        assert next(row for row in after_first["policies"] if row["id"] == 99) == next(
            row for row in before["policies"] if row["id"] == 99
        )
        assert next(row for row in after_first["external_source_records"] if row["id"] == 99) == next(
            row for row in before["external_source_records"] if row["id"] == 99
        )

        assert snapshot_cli.verify_snapshot(url, database, artifact)["database_state"] == "post"
        connection.execute(migration.DOWNGRADE_GUARD_SQL)
        connection.commit()
        restored = snapshot_cli.restore_snapshot(url, database, artifact)
        assert restored["database_state"] == "restored"
        assert snapshot_cli.verify_snapshot(url, database, artifact)["database_state"] == "pre"
        assert _all_rows(connection) == before
        assert export["digest"] == restored["digest"]


@pytest.mark.parametrize(
    "drift_sql",
    [
        "DELETE FROM policies WHERE id=26",
        "UPDATE policies SET slug='identity-drift' WHERE id=23",
        "UPDATE external_source_records SET raw_payload=jsonb_set(raw_payload,'{usageMethod}','\"drift\"') WHERE id=35",
        "UPDATE policies SET target_condition='operator semantic override' WHERE id=23",
        "INSERT INTO external_source_records SELECT 36,source_name,source_type,source_url,source_category,"
        "external_id,'unexpected',logical_key,canonical_key_version,detail_url,collected_page_url,title,"
        "contact_text,raw_list_text,raw_detail_text,raw_payload,status FROM external_source_records WHERE id=35",
    ],
    ids=["missing", "identity", "raw", "semantic", "ambiguous"],
)
def test_guard_failures_abort_before_any_mutation(drift_sql: str) -> None:
    migration = _migration()
    with _database() as (_, url), psycopg.connect(url) as connection:
        connection.execute(DDL)
        _seed(connection, "merged_26_35")
        connection.execute(drift_sql)
        connection.commit()
        before = _all_rows(connection)

        with pytest.raises(psycopg.errors.RaiseException, match="prestate mismatch"):
            _run(connection, migration.UPGRADE_SQL)
        connection.rollback()

        assert _all_rows(connection) == before


def test_downgrade_guard_rejects_drift_without_data_mutation() -> None:
    migration = _migration()
    with _database() as (_, url), psycopg.connect(url) as connection:
        connection.execute(DDL)
        _seed(connection, "merged_26_35")
        _run(connection, migration.UPGRADE_SQL)
        connection.commit()
        connection.execute("UPDATE policies SET structured_detail='{}'::jsonb WHERE id=26")
        connection.commit()
        before = _all_rows(connection)

        with pytest.raises(psycopg.errors.RaiseException, match="exact corrected"):
            connection.execute(migration.DOWNGRADE_GUARD_SQL)
        connection.rollback()

        assert _all_rows(connection) == before
