"""add kakao place metadata

Revision ID: 0016_kakao_place_metadata
Revises: 0015_admin_management_foundation
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_kakao_place_metadata"
down_revision = "0015_admin_management_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trip_places", sa.Column("source_provider", sa.String(length=40), nullable=True))
    op.add_column("trip_places", sa.Column("external_place_id", sa.String(length=80), nullable=True))
    op.add_column("trip_places", sa.Column("category_group_code", sa.String(length=20), nullable=True))
    op.add_column("trip_places", sa.Column("category_group_name", sa.String(length=80), nullable=True))
    op.add_column("trip_places", sa.Column("place_url", sa.String(length=500), nullable=True))
    op.create_index("ix_trip_places_external_place_id", "trip_places", ["external_place_id"])


def downgrade() -> None:
    op.drop_index("ix_trip_places_external_place_id", table_name="trip_places")
    op.drop_column("trip_places", "place_url")
    op.drop_column("trip_places", "category_group_name")
    op.drop_column("trip_places", "category_group_code")
    op.drop_column("trip_places", "external_place_id")
    op.drop_column("trip_places", "source_provider")
