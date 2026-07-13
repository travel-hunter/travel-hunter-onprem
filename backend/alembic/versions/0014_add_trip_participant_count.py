"""add trip participant count

Revision ID: 0014_add_trip_participant_count
Revises: 0013_add_trip_travel_area_id
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_add_trip_participant_count"
down_revision = "0013_add_trip_travel_area_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trips",
        sa.Column("participant_count", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("trips", "participant_count")
