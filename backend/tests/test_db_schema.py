import ast
import importlib.util
import io
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

import app.models  # noqa: F401
from app.db.base import Base


ALEMBIC_VERSION_NUM_MAX_LENGTH = 32


def test_current_schema_tables_are_registered() -> None:
    expected_tables = {
        "users",
        "auth_refresh_tokens",
        "password_reset_tokens",
        "pending_signups",
        "pending_social_signups",
        "social_accounts",
        "policies",
        "policy_documents",
        "external_source_records",
        "trips",
        "trip_days",
        "trip_places",
        "trip_members",
        "trip_policies",
        "trip_invites",
        "user_saved_policies",
        "notification_deliveries",
        "recommendations",
        "eligible_island_catalogs",
        "eligible_island_catalog_snapshots",
        "eligible_island_snapshot_entries",
        "eligible_islands",
        "photo_review_targets",
        "photo_review_candidates",
        "public_places",
        "public_place_sync_state",
    }

    assert expected_tables.issubset(set(Base.metadata.tables))


def test_current_schema_decision_columns_are_registered() -> None:
    users = Base.metadata.tables["users"]
    policies = Base.metadata.tables["policies"]
    trips = Base.metadata.tables["trips"]
    trip_invites = Base.metadata.tables["trip_invites"]
    notification_deliveries = Base.metadata.tables["notification_deliveries"]
    password_reset_tokens = Base.metadata.tables["password_reset_tokens"]
    pending_signups = Base.metadata.tables["pending_signups"]
    pending_social_signups = Base.metadata.tables["pending_social_signups"]
    external_source_records = Base.metadata.tables["external_source_records"]
    social_accounts = Base.metadata.tables["social_accounts"]

    assert "preferred_regions" in users.c
    removed_user_columns = {
        "birth_date",
        "gender",
        "region",
        "residence_area",
        "phone_number",
        "phone_verified_at",
    }
    assert removed_user_columns.isdisjoint(set(users.c.keys()))
    assert "travel_style" in users.c
    assert "travel_budget" in users.c
    assert "terms_accepted" in users.c
    assert "terms_accepted_at" in users.c
    assert "terms_version" in users.c
    assert "privacy_accepted" in users.c
    assert "privacy_accepted_at" in users.c
    assert "privacy_version" in users.c
    assert "withdrawn_at" in users.c
    assert "withdrawn_email_hash" in users.c
    assert users.c["withdrawn_email_hash"].type.length == 64
    user_saved_policies = Base.metadata.tables["user_saved_policies"]
    assert "saved_at" in user_saved_policies.c
    assert "slug" in policies.c
    assert "apply_url" in policies.c
    expected_policy_source_columns = {
        "source_type",
        "source_name",
        "source_category",
        "external_source_record_id",
        "source_url",
        "source_canonical_key",
        "normalized_at",
        "last_verified_at",
        "verification_status",
    }
    assert expected_policy_source_columns.issubset(set(policies.c.keys()))
    policy_external_source_fks = {
        fk.column.table.name
        for fk in policies.c["external_source_record_id"].foreign_keys
    }
    assert "external_source_records" in policy_external_source_fks
    assert "invite_token" in trip_invites.c
    assert "role" in trip_invites.c
    assert "token_hash" in password_reset_tokens.c
    assert "expires_at" in password_reset_tokens.c
    assert "used_at" in password_reset_tokens.c
    assert "email" in pending_signups.c
    assert "token_hash" in pending_signups.c
    assert "terms_accepted" in pending_signups.c
    assert "terms_accepted_at" in pending_signups.c
    assert "terms_version" in pending_signups.c
    assert "privacy_accepted" in pending_signups.c
    assert "privacy_accepted_at" in pending_signups.c
    assert "privacy_version" in pending_signups.c
    assert "password_hash" not in pending_signups.c
    assert "token_hash" in pending_social_signups.c
    assert "provider" in pending_social_signups.c
    assert "provider_id" in pending_social_signups.c
    assert "email" in pending_social_signups.c
    assert "expires_at" in pending_social_signups.c
    assert social_accounts.c["provider_id"].type.length == 255
    assert "revision" in trips.c
    assert "phone_verification_codes" not in Base.metadata.tables
    assert "user_notification_settings" not in Base.metadata.tables
    assert "region" in policies.c
    assert "region" in trips.c
    expected_external_source_columns = {
        "source_name",
        "source_type",
        "source_url",
        "source_category",
        "external_id",
        "canonical_key",
        "detail_url",
        "collected_page_url",
        "title",
        "organizer_text",
        "organizers",
        "region",
        "city",
        "is_nationwide",
        "status_text",
        "status",
        "start_date",
        "end_date",
        "benefit_text",
        "benefit_value_text",
        "extracted_amount_krw",
        "extracted_discount_percent",
        "benefit_value_type",
        "tags",
        "contact_text",
        "inferred_travel_styles",
        "confidence",
        "field_completeness",
        "raw_list_text",
        "raw_detail_text",
        "raw_payload",
        "last_fetched_at",
        "last_verified_at",
        "freshness_status",
        "created_at",
        "updated_at",
    }
    assert expected_external_source_columns.issubset(set(external_source_records.c.keys()))
    assert "lead_day" in notification_deliveries.c
    assert "target_deadline_date" in notification_deliveries.c
    assert "status" in notification_deliveries.c
    notification_unique_columns = {
        column.name
        for constraint in notification_deliveries.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
        for column in constraint.columns
    }
    assert {
        "user_id",
        "policy_id",
        "channel",
        "lead_day",
        "target_deadline_date",
    }.issubset(notification_unique_columns)
    assert "trips_days" not in Base.metadata.tables
    assert "trips_members" not in Base.metadata.tables
    assert "trips_policies" not in Base.metadata.tables


def test_policy_auto_publish_columns_are_registered() -> None:
    candidates = Base.metadata.tables["policy_review_candidates"]
    sources = Base.metadata.tables["policy_collection_sources"]
    assert "review_reason" in candidates.c
    assert candidates.c["review_reason"].nullable is True
    assert "last_parsed_count" in sources.c
    assert sources.c["last_parsed_count"].nullable is True


def test_trip_policy_application_columns_are_registered() -> None:
    trip_policies = Base.metadata.tables["trip_policies"]
    for column in ("application_status", "application_checklist", "application_updated_at", "application_updated_by_user_id"):
        assert column in trip_policies.c
        assert trip_policies.c[column].nullable is True
    assert {fk.column.table.name for fk in trip_policies.c["application_updated_by_user_id"].foreign_keys} == {"users"}
    check_names = {constraint.name for constraint in trip_policies.constraints if constraint.__class__.__name__ == "CheckConstraint"}
    assert "ck_trip_policies_application_status" in check_names


def test_policies_external_source_record_id_is_not_unique() -> None:
    policies = Base.metadata.tables["policies"]

    assert policies.c["external_source_record_id"].unique is not True


def test_alembic_revision_ids_fit_version_table() -> None:
    versions_dir = Path(__file__).parents[1] / "alembic" / "versions"
    revisions: list[tuple[str, str]] = []

    for migration_path in sorted(versions_dir.glob("*.py")):
        module = ast.parse(migration_path.read_text(encoding="utf-8"))
        for node in module.body:
            if not isinstance(node, ast.AnnAssign | ast.Assign):
                continue
            target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0]
            if not isinstance(target, ast.Name) or target.id != "revision":
                continue
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                revisions.append((migration_path.name, value.value))
                break

    assert revisions
    assert [
        (filename, revision)
        for filename, revision in revisions
        if len(revision) > ALEMBIC_VERSION_NUM_MAX_LENGTH
    ] == []


def test_external_source_status_text_preserves_long_official_notice() -> None:
    external_source_records = Base.metadata.tables["external_source_records"]
    assert isinstance(external_source_records.c["status_text"].type, sa.Text)


def _check_names(table: sa.Table) -> set[str]:
    return {constraint.name for constraint in table.constraints if constraint.__class__.__name__ == "CheckConstraint"}


def test_public_places_table_is_registered() -> None:
    places = Base.metadata.tables["public_places"]
    assert [column.name for column in places.primary_key.columns] == ["source", "source_id"]
    for column in ("name", "name_key", "latitude", "longitude", "category", "synced_at"):
        assert places.c[column].nullable is False
    for column in ("address", "sido", "city", "photo_url", "photo_license"):
        assert places.c[column].nullable is True
    index_columns = {index.name: [column.name for column in index.columns] for index in places.indexes}
    assert index_columns["ix_public_places_lat_lng"] == ["latitude", "longitude"]
    assert index_columns["ix_public_places_name_key"] == ["name_key"]
    assert {"ck_public_places_source", "ck_public_places_category"} <= _check_names(places)


def test_public_place_sync_state_table_is_registered() -> None:
    state = Base.metadata.tables["public_place_sync_state"]
    assert [column.name for column in state.primary_key.columns] == ["source"]
    assert state.c["last_success_at"].nullable is True
    assert state.c["last_attempt_at"].nullable is False
    assert {"ck_public_place_sync_state_source", "ck_public_place_sync_state_outcome"} <= _check_names(state)


def test_trip_place_public_origin_columns_are_registered() -> None:
    trip_places = Base.metadata.tables["trip_places"]
    for column in ("place_origin", "public_source", "public_source_id", "photo_url", "photo_license"):
        assert column in trip_places.c
        assert trip_places.c[column].nullable is True
    assert "ck_trip_places_place_origin" in _check_names(trip_places)


def test_trip_place_columns_and_area_index_are_registered() -> None:
    trip_places = Base.metadata.tables["trip_places"]
    assert trip_places.c["public_category"].nullable is True
    assert trip_places.c["public_category"].type.length == 20
    assert "ck_trip_places_public_category" in _check_names(trip_places)
    assert trip_places.c["user_label"].nullable is True
    assert trip_places.c["user_label"].type.length == 100
    places = Base.metadata.tables["public_places"]
    index_columns = {index.name: [column.name for column in index.columns] for index in places.indexes}
    assert index_columns["ix_public_places_sido_city"] == ["sido", "city"]


def test_alembic_0049_follows_0048() -> None:
    backend = Path(__file__).parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_revision("0049_trip_place_public_category").down_revision == "0048_public_places"


def test_alembic_0052_follows_0051_and_is_the_only_head() -> None:
    backend = Path(__file__).parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0052_pg_prewarm"]
    assert script.get_revision("0052_pg_prewarm").down_revision == "0051_public_place_name_trgm"
    assert script.get_revision("0051_public_place_name_trgm").down_revision == "0050_geo_reference"
    assert script.get_revision("0050_geo_reference").down_revision == "0049_trip_place_public_category"


def render_migration(filename: str, direction: str) -> str:
    """마이그레이션의 upgrade · downgrade 가 내는 Postgres SQL - 오프라인이라 DB 에 닿지 않는다."""

    path = Path(__file__).parents[1] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(f"migration_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    buffer = io.StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buffer})
    with Operations.context(context):
        getattr(module, direction)()
    return buffer.getvalue()


def render_0049(direction: str) -> str:
    return render_migration("0049_trip_place_public_category.py", direction)


def test_alembic_0050_creates_postgis_geo_tables_with_stable_ids_and_trip_place_geo_columns() -> None:
    up = render_migration("0050_geo_reference.py", "upgrade")
    down = render_migration("0050_geo_reference.py", "downgrade")
    # 확장은 없을 때만 만든다 - RDS 처럼 미리 설치된 곳에서는 권한 없이 지나간다
    assert "pg_extension WHERE extname = 'postgis'" in up and "CREATE EXTENSION postgis" in up
    assert up.index("CREATE EXTENSION postgis") < up.index("CREATE SCHEMA IF NOT EXISTS geo") < up.index("CREATE SEQUENCE geo.feature_id_seq")
    for table in ("geo.building", "geo.parcel", "geo.legal_dong", "geo.load_run"):
        assert f"CREATE TABLE {table}" in up
    # 판이 바뀌어도 id 를 다시 쓰지 않는다 - 옛 화면의 geoRef 가 다른 건물을 가리키지 않게(코덱스 HIGH)
    assert up.count("DEFAULT nextval('geo.feature_id_seq')") == 2 and "feature_key varchar(40) NOT NULL" in up
    assert "geometry(Geometry, 5186)" in up and "USING gist (geom)" in up and "jimok varchar(4)" in up
    assert "ADD COLUMN geo_kind VARCHAR(10)" in up and "ADD COLUMN geo_pnu VARCHAR(19)" in up and "ck_trip_places_geo_kind" in up
    # 되돌리기는 geo 스키마와 열만 지운다 - postgis 확장은 남긴다
    assert "DROP SCHEMA IF EXISTS geo CASCADE" in down and "DROP EXTENSION" not in down
    assert "DROP COLUMN geo_pnu" in down and "DROP COLUMN geo_kind" in down


def test_trip_place_geo_columns_are_registered() -> None:
    places = Base.metadata.tables["trip_places"]
    assert places.c.geo_kind.type.length == 10 and places.c.geo_kind.nullable
    assert places.c.geo_pnu.type.length == 19 and places.c.geo_pnu.nullable
    assert "ck_trip_places_geo_kind" in {constraint.name for constraint in places.constraints if constraint.name}


def test_alembic_0049_builds_the_area_index_concurrently_outside_the_transaction() -> None:
    up, down = render_0049("upgrade"), render_0049("downgrade")
    leftover = "DROP INDEX CONCURRENTLY IF EXISTS ix_public_places_sido_city"
    index = "CREATE INDEX CONCURRENTLY ix_public_places_sido_city ON public_places (sido, city)"
    # 트랜잭션 밖에서 만든다 - public_places 쓰기를 막지 않는다. 앞선 시도가 남긴 INVALID 색인은 먼저 지워 다시 돌리기가 풀린다
    assert up.index("COMMIT") < up.index(leftover) < up.index(index) < up.index("BEGIN")
    assert "ADD COLUMN public_category VARCHAR(20)" in up and "ADD COLUMN user_label VARCHAR(100)" in up
    assert down.index("COMMIT") < down.index("DROP INDEX CONCURRENTLY IF EXISTS ix_public_places_sido_city") < down.index("BEGIN")
    assert "DROP COLUMN user_label" in down and "DROP COLUMN public_category" in down


def test_public_places_name_trigram_index_is_registered() -> None:
    places = Base.metadata.tables["public_places"]
    index = next(index for index in places.indexes if index.name == "ix_public_places_name_trgm")
    assert [column.name for column in index.columns] == ["name"]
    assert index.dialect_options["postgresql"]["using"] == "gin"
    assert index.dialect_options["postgresql"]["ops"] == {"name": "gin_trgm_ops"}


def test_alembic_0051_builds_the_name_trigram_index_concurrently_outside_the_transaction() -> None:
    up = render_migration("0051_public_place_name_trgm.py", "upgrade")
    down = render_migration("0051_public_place_name_trgm.py", "downgrade")
    leftover = "DROP INDEX CONCURRENTLY IF EXISTS ix_public_places_name_trgm"
    index = "CREATE INDEX CONCURRENTLY ix_public_places_name_trgm ON public_places USING gin (name gin_trgm_ops)"
    # 확장은 트랜잭션 안에서 먼저 - 색인만 autocommit 블록으로 나간다. 앞선 시도가 남긴 INVALID 색인은 먼저 지워 다시 돌리기가 풀린다
    assert up.index("CREATE EXTENSION IF NOT EXISTS pg_trgm") < up.index("COMMIT") < up.index(leftover) < up.index(index) < up.index("BEGIN")
    # 되돌리기는 색인만 지운다 - pg_trgm 확장은 다른 객체가 쓸 수 있어 남긴다
    assert down.index("COMMIT") < down.index(leftover) < down.index("BEGIN")
    assert "DROP EXTENSION" not in down


def test_alembic_0052_only_adds_the_prewarm_extension() -> None:
    # 데우기 함수만 들인다 - 표 · 색인은 그대로. 되돌리면 확장도 지운다(이 확장에 기대는 객체가 없다)
    assert "CREATE EXTENSION IF NOT EXISTS pg_prewarm" in render_migration("0052_pg_prewarm.py", "upgrade")
    assert "DROP EXTENSION IF EXISTS pg_prewarm" in render_migration("0052_pg_prewarm.py", "downgrade")
