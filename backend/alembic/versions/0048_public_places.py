"""public places: our own place base from public data (Kakao Local policy, stage 2)

Revision ID: 0048_public_places
Revises: 0047_photo_review
Create Date: 2026-10-04

카카오 로컬 값(장소명 · 주소 · 좌표)을 저장하지 않으려고 공공데이터로 우리 장소 기반을 만든다(설계
docs/superpowers/specs/2026-10-03-public-place-storage-design.md). public_places 는 TourAPI 6개 유형과 상가정보
음식 · 숙박 · 예술·스포츠를 담는다(적재: scripts/sync_public_places_tourapi.py · scripts/load_public_places_sangga.py).
public_place_sync_state 는 출처마다 마지막 시도(running 포함)와 끝까지 받은 마지막 시각을 둔다. trip_places 에는 담는 값의
출처 열을 더한다 - 3단계 담는 흐름부터 채운다. 표와 nullable 열을 더하기만 하므로 앞 버전 코드가 그대로 돈다. downgrade 는 모두 지운다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0048_public_places"
down_revision: str | None = "0047_photo_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_places",
        sa.Column("source", sa.String(length=10), primary_key=True),
        sa.Column("source_id", sa.String(length=40), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_key", sa.String(length=200), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("sido", sa.String(length=20), nullable=True),
        sa.Column("city", sa.String(length=40), nullable=True),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("photo_license", sa.String(length=20), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("source IN ('tourapi', 'sangga')", name="ck_public_places_source"),
        sa.CheckConstraint(
            "category IN ('sight', 'culture', 'leisure', 'stay', 'shopping', 'food', 'cafe')",
            name="ck_public_places_category",
        ),
    )
    op.create_index("ix_public_places_lat_lng", "public_places", ["latitude", "longitude"])
    op.create_index("ix_public_places_name_key", "public_places", ["name_key"])
    op.create_table(
        "public_place_sync_state",
        sa.Column("source", sa.String(length=10), primary_key=True),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("last_outcome", sa.String(length=20), nullable=False),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("received_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("written_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pruned_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.CheckConstraint("source IN ('tourapi', 'sangga')", name="ck_public_place_sync_state_source"),
        sa.CheckConstraint(
            "last_outcome IN ('running', 'success', 'partial', 'error')", name="ck_public_place_sync_state_outcome"
        ),
    )
    op.add_column("trip_places", sa.Column("place_origin", sa.String(length=20), nullable=True))
    op.add_column("trip_places", sa.Column("public_source", sa.String(length=10), nullable=True))
    op.add_column("trip_places", sa.Column("public_source_id", sa.String(length=40), nullable=True))
    op.add_column("trip_places", sa.Column("photo_url", sa.String(length=500), nullable=True))
    op.add_column("trip_places", sa.Column("photo_license", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        "ck_trip_places_place_origin",
        "trip_places",
        "place_origin IS NULL OR place_origin IN ('public', 'custom', 'needs_review')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_trip_places_place_origin", "trip_places", type_="check")
    for column in ("photo_license", "photo_url", "public_source_id", "public_source", "place_origin"):
        op.drop_column("trip_places", column)
    op.drop_table("public_place_sync_state")
    op.drop_index("ix_public_places_name_key", table_name="public_places")
    op.drop_index("ix_public_places_lat_lng", table_name="public_places")
    op.drop_table("public_places")
