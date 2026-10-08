"""geo reference tables (building · parcel jibun) for address fill + trip_places geo provenance

Revision ID: 0050_geo_reference
Revises: 0049_trip_place_public_category
Create Date: 2026-10-08

방식1 '주소 채움'(계획 docs/superpowers/plans/2026-10-07-place-add-address-fill.md)이 쓴다.
- postgis 확장 · geo 스키마: 국토교통부 GIS건물통합정보(건물) · 연속지적도(땅, 농지 · 임야 제외)의 도형과 고유번호(PNU).
  데이터는 적재 도구(backend/scripts/geo_load.py)가 월 1회 새 표(*_next)에 넣고 바꿔치기한다. 이 마이그레이션은 빈 표만 만든다.
  앱 데이터와 다른 스키마라 백업 · 로컬 복사에서 뺄 수 있다(원본 파일에서 다시 넣을 수 있다).
- id 는 두 표가 함께 쓰는 시퀀스에서 받는다 - 판을 바꿔도 같은 id 가 다른 건물 · 땅을 가리키지 않는다(옛 geoRef 는 404).
- 확장은 없을 때만 만든다. AWS RDS 는 프로비저닝 때 마스터 사용자(rds_superuser)가 먼저 설치한다 - 그러면 여기서는 건너뛴다.
- trip_places.geo_kind · geo_pnu: 나만의 장소의 주소 · 좌표를 건물 · 땅 지번에서 채웠을 때 그 출처. nullable.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0050_geo_reference"
down_revision: str | None = "0049_trip_place_public_category"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SHAPE_COLUMNS = (
    "id bigint PRIMARY KEY DEFAULT nextval('geo.feature_id_seq'), feature_key varchar(40) NOT NULL, pnu varchar(19) NOT NULL, "
    "la double precision NOT NULL, lo double precision NOT NULL, rx double precision NOT NULL, ry double precision NOT NULL, "
    "geom geometry(Geometry, 5186) NOT NULL"
)


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis') THEN CREATE EXTENSION postgis; END IF; END $$"
    )
    op.execute("CREATE SCHEMA IF NOT EXISTS geo")
    op.execute("CREATE SEQUENCE geo.feature_id_seq")
    op.execute(f"CREATE TABLE geo.building ({SHAPE_COLUMNS})")
    op.execute(f"CREATE TABLE geo.parcel ({SHAPE_COLUMNS}, jimok varchar(4))")
    for table in ("building", "parcel"):
        op.execute(f"CREATE INDEX {table}_geom_gix ON geo.{table} USING gist (geom)")
        op.execute(f"CREATE INDEX {table}_pnu_ix ON geo.{table} (pnu)")
    op.execute("CREATE TABLE geo.legal_dong (code varchar(10) PRIMARY KEY, name varchar(100) NOT NULL)")
    op.execute(
        "CREATE TABLE geo.load_run (id bigserial PRIMARY KEY, finished_at timestamptz NOT NULL DEFAULT now(), "
        "building_rows bigint NOT NULL, parcel_rows bigint NOT NULL, building_base_date varchar(8), parcel_base_date varchar(8))"
    )
    op.add_column("trip_places", sa.Column("geo_kind", sa.String(length=10), nullable=True))
    op.add_column("trip_places", sa.Column("geo_pnu", sa.String(length=19), nullable=True))
    op.create_check_constraint("ck_trip_places_geo_kind", "trip_places", "geo_kind IS NULL OR geo_kind IN ('building', 'parcel')")


def downgrade() -> None:
    op.drop_constraint("ck_trip_places_geo_kind", "trip_places", type_="check")
    op.drop_column("trip_places", "geo_pnu")
    op.drop_column("trip_places", "geo_kind")
    op.execute("DROP SCHEMA IF EXISTS geo CASCADE")
