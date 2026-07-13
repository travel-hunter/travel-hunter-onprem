"""add trip travel area id

Revision ID: 0013_add_trip_travel_area_id
Revises: 0012_policy_source_tracking
Create Date: 2026-05-26
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_add_trip_travel_area_id"
down_revision = "0012_policy_source_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("trips", sa.Column("travel_area_id", sa.String(length=120), nullable=True))
    op.create_index("ix_trips_travel_area_id", "trips", ["travel_area_id"])


def downgrade() -> None:
    op.drop_index("ix_trips_travel_area_id", table_name="trips")
    op.drop_column("trips", "travel_area_id")
