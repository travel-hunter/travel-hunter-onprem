"""add trip revision for optimistic editing

Revision ID: 0018_add_trip_revision
Revises: 0017_widen_social_provider_id
Create Date: 2026-06-11
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_add_trip_revision"
down_revision = "0017_widen_social_provider_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trips",
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("trips", "revision")
