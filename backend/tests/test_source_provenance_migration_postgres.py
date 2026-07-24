from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest


MIGRATION_PATH = Path(__file__).resolve().parents[1] / "alembic/versions/0027_source_provenance_keys.py"
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_MIGRATION_TESTS") != "1",
    reason="set RUN_POSTGRES_MIGRATION_TESTS=1 for PostgreSQL migration tests",
)


def _migration():
    spec = importlib.util.spec_from_file_location("source_provenance_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _url() -> str:
    return os.getenv(
        "POSTGRES_MIGRATION_TEST_DATABASE_URL",
        "postgresql://travelhunter:travelhunter@127.0.0.1:55432/travelhunter",
    ).replace("postgresql+psycopg://", "postgresql://", 1)


class PsycopgOp:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql):
        self.connection.execute(sql)

    def add_column(self, table, column):
        nullable = "" if column.nullable else " NOT NULL"
        self.connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column.name} varchar({column.type.length}){nullable}"
        )

    def create_index(self, name, table, columns, unique=False):
        self.connection.execute(
            f"CREATE {'UNIQUE ' if unique else ''}INDEX {name} ON {table} ({','.join(columns)})"
        )

    def drop_index(self, name, table_name=None):
        self.connection.execute(f"DROP INDEX {name}")

    def drop_column(self, table, column):
        self.connection.execute(f"ALTER TABLE {table} DROP COLUMN {column}")


@pytest.fixture
def cloned_schema():
    schema = f"g003_{uuid4().hex}"
    with psycopg.connect(_url(), autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
        connection.execute(
            f'CREATE TABLE "{schema}".external_source_records AS TABLE public.external_source_records'
        )
        connection.execute(f'CREATE TABLE "{schema}".policies AS TABLE public.policies')
        connection.execute(f'ALTER TABLE "{schema}".external_source_records DROP COLUMN logical_key')
        connection.execute(
            f'ALTER TABLE "{schema}".external_source_records DROP COLUMN canonical_key_version'
        )
        connection.execute(
            f'''UPDATE "{schema}".external_source_records
                SET canonical_key='stay-discount:2026-summer' WHERE id=35'''
        )
        connection.execute(
            f'''UPDATE "{schema}".policies
                SET source_type=NULL, verification_status=NULL,
                    source_name='대한민국 반값여행', source_category='local_half_trip'
                WHERE slug LIKE 'dgtour-%' AND slug <> 'dgtour-하동-3' '''
        )
        connection.execute(
            f'''UPDATE "{schema}".policies SET source_canonical_key='stay-discount:2026-summer'
                WHERE id=23'''
        )
    try:
        yield schema
    finally:
        with psycopg.connect(_url(), autocommit=True) as connection:
            connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


@pytest.fixture
def cloned_schema_33():
    schema = f"g003_33_{uuid4().hex}"
    with psycopg.connect(_url(), autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
        connection.execute(
            f'CREATE TABLE "{schema}".external_source_records AS TABLE public.external_source_records'
        )
        connection.execute(f'CREATE TABLE "{schema}".policies AS TABLE public.policies')
        connection.execute(f'ALTER TABLE "{schema}".external_source_records DROP COLUMN logical_key')
        connection.execute(
            f'ALTER TABLE "{schema}".external_source_records DROP COLUMN canonical_key_version'
        )
        connection.execute(f'DELETE FROM "{schema}".policies WHERE id IN (24,25,26)')
        connection.execute(f'DELETE FROM "{schema}".external_source_records WHERE id IN (34,35)')
        connection.execute(
            f'''UPDATE "{schema}".policies
                SET external_source_record_id=33,
                    source_canonical_key='c6f2eb4e3807ec83df2c95fbed2de11c'
                WHERE id=23 AND slug='travelmonth-33' '''
        )
        connection.execute(
            f'''UPDATE "{schema}".policies
                SET source_type=NULL, verification_status=NULL,
                    source_name='대한민국 반값여행', source_category='local_half_trip'
                WHERE slug LIKE 'dgtour-%' AND slug <> 'dgtour-하동-3' '''
        )
    try:
        yield schema
    finally:
        with psycopg.connect(_url(), autocommit=True) as connection:
            connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


def _raw_digest(connection) -> str:
    return connection.execute(
        """
        SELECT md5(string_agg(
          id::text || ':' || md5(raw_list_text) || ':' || md5(raw_detail_text) || ':' || md5(raw_payload::text),
          '|' ORDER BY id
        )) FROM external_source_records
        """
    ).fetchone()[0]


def test_upgrade_downgrade_reupgrade_preserves_raw_and_expected_collisions(
    cloned_schema: str, monkeypatch
) -> None:
    migration = _migration()
    with psycopg.connect(_url()) as connection:
        connection.execute(f'SET search_path TO "{cloned_schema}"')
        monkeypatch.setattr(migration, "op", PsycopgOp(connection))
        before = _raw_digest(connection)

        migration.upgrade()
        assert _raw_digest(connection) == before
        assert connection.execute(
            "SELECT canonical_key,logical_key,canonical_key_version FROM external_source_records WHERE id=35"
        ).fetchone() == (
            migration.STAY_SOURCE_35_SNAPSHOT_KEY,
            migration.STAY_LOGICAL_KEY,
            migration.SNAPSHOT_KEY_VERSION,
        )
        collisions = connection.execute(
            "SELECT logical_key,array_agg(id ORDER BY id) FROM external_source_records "
            "GROUP BY logical_key HAVING count(*)>1 ORDER BY logical_key"
        ).fetchall()
        assert collisions == [
            ("local-half-trip:2026:경남:하동", [19, 34]),
            (migration.STAY_LOGICAL_KEY, [33, 35]),
        ]
        assert connection.execute(
            "SELECT count(*) FROM policies WHERE source_type='legacy_source' "
            "AND verification_status='needs_review'"
        ).fetchone() == (15,)

        migration.downgrade()
        assert connection.execute(
            "SELECT canonical_key FROM external_source_records WHERE id=35"
        ).fetchone() == (migration.STAY_LOGICAL_KEY,)
        migration.upgrade()
        assert _raw_digest(connection) == before
        connection.rollback()


def test_23_33_upgrade_downgrade_reupgrade_preserves_single_snapshot(
    cloned_schema_33: str, monkeypatch
) -> None:
    migration = _migration()
    with psycopg.connect(_url()) as connection:
        connection.execute(f'SET search_path TO "{cloned_schema_33}"')
        monkeypatch.setattr(migration, "op", PsycopgOp(connection))
        before = _raw_digest(connection)

        migration.upgrade()
        assert _raw_digest(connection) == before
        assert connection.execute(
            "SELECT canonical_key,logical_key,canonical_key_version "
            "FROM external_source_records WHERE id=33"
        ).fetchone() == (
            "c6f2eb4e3807ec83df2c95fbed2de11c",
            migration.STAY_LOGICAL_KEY,
            migration.SNAPSHOT_KEY_VERSION,
        )
        assert connection.execute(
            "SELECT logical_key,array_agg(id ORDER BY id) FROM external_source_records "
            "GROUP BY logical_key HAVING count(*)>1 ORDER BY logical_key"
        ).fetchall() == []
        assert connection.execute(
            "SELECT external_source_record_id,source_canonical_key FROM policies WHERE id=23"
        ).fetchone() == (33, "c6f2eb4e3807ec83df2c95fbed2de11c")
        assert connection.execute(
            "SELECT count(*) FROM policies WHERE source_type='legacy_source' "
            "AND verification_status='needs_review'"
        ).fetchone() == (15,)

        migration.downgrade()
        assert connection.execute(
            "SELECT canonical_key FROM external_source_records WHERE id=33"
        ).fetchone() == ("c6f2eb4e3807ec83df2c95fbed2de11c",)
        migration.upgrade()
        assert _raw_digest(connection) == before
        connection.rollback()


def test_wrong_snapshot_identity_aborts_transaction_without_schema_mutation(
    cloned_schema: str, monkeypatch
) -> None:
    migration = _migration()
    with psycopg.connect(_url()) as connection:
        connection.execute(f'SET search_path TO "{cloned_schema}"')
        connection.execute(
            "UPDATE external_source_records SET canonical_key='unexpected' WHERE id=33"
        )
        connection.commit()
        monkeypatch.setattr(migration, "op", PsycopgOp(connection))

        with pytest.raises(psycopg.errors.RaiseException, match="prestate mismatch"):
            migration.upgrade()
        connection.rollback()
        columns = connection.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema=%s AND table_name='external_source_records'",
            (cloned_schema,),
        ).fetchall()
        assert ("logical_key",) not in columns


def test_operator_policy_metadata_aborts_without_partial_overwrite(
    cloned_schema: str, monkeypatch
) -> None:
    migration = _migration()
    with psycopg.connect(_url()) as connection:
        connection.execute(f'SET search_path TO "{cloned_schema}"')
        connection.execute(
            "UPDATE policies SET source_type='operator_override', verification_status='verified' "
            "WHERE slug='dgtour-밀양-1'"
        )
        connection.commit()
        monkeypatch.setattr(migration, "op", PsycopgOp(connection))

        with pytest.raises(psycopg.errors.RaiseException, match="prestate mismatch"):
            migration.upgrade()
        connection.rollback()
        assert connection.execute(
            "SELECT source_type,verification_status FROM policies WHERE slug='dgtour-밀양-1'"
        ).fetchone() == ("operator_override", "verified")
        columns = {
            row[0]
            for row in connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name='external_source_records'",
                (cloned_schema,),
            ).fetchall()
        }
        assert "logical_key" not in columns


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE policies SET source_type=NULL WHERE slug='dgtour-하동-3'",
        "DELETE FROM policies WHERE slug='dgtour-하동-3'",
    ],
)
def test_missing_or_null_hadong_identity_aborts_without_schema_mutation(
    cloned_schema: str, monkeypatch, mutation: str
) -> None:
    migration = _migration()
    with psycopg.connect(_url()) as connection:
        connection.execute(f'SET search_path TO "{cloned_schema}"')
        connection.execute(mutation)
        connection.commit()
        monkeypatch.setattr(migration, "op", PsycopgOp(connection))

        with pytest.raises(psycopg.errors.RaiseException, match="prestate mismatch"):
            migration.upgrade()
        connection.rollback()
        columns = {
            row[0]
            for row in connection.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name='external_source_records'",
                (cloned_schema,),
            ).fetchall()
        }
        assert "logical_key" not in columns


def test_fresh_empty_database_runs_full_alembic_base_to_head() -> None:
    database = f"g003_fresh_{uuid4().hex}"
    admin_url = _url().rsplit("/", 1)[0] + "/postgres"
    database_url = _url().rsplit("/", 1)[0] + f"/{database}"
    backend_dir = Path(__file__).resolve().parents[1]
    alembic = backend_dir / ".venv/bin/alembic"
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    try:
        environment = {**os.environ, "DATABASE_URL": database_url.replace("postgresql://", "postgresql+psycopg://", 1)}
        subprocess.run([str(alembic), "upgrade", "head"], cwd=backend_dir, env=environment, check=True)
        with psycopg.connect(database_url) as connection:
            assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
                "0030_half_trip_five_semantics",
            )
            columns = {
                row[0]
                for row in connection.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name='external_source_records'"
                ).fetchall()
            }
            assert {"logical_key", "canonical_key_version"}.issubset(columns)
            assert connection.execute(
                "SELECT count(*) FROM pg_indexes WHERE schemaname='public' "
                "AND indexname='ix_external_source_records_logical_key'"
            ).fetchone() == (1,)
        subprocess.run(
            [str(alembic), "downgrade", "0026_user_withdrawal_fields"],
            cwd=backend_dir, env=environment, check=True,
        )
        subprocess.run([str(alembic), "upgrade", "head"], cwd=backend_dir, env=environment, check=True)
    finally:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s",
                (database,),
            )
            connection.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(database)))
