"""add trip status

Revision ID: 0009_add_trip_status
Revises: 0008_password_reset_tokens
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_add_trip_status"
down_revision = "0008_password_reset_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trips",
        sa.Column("status", sa.String(length=20), nullable=True, server_default="draft"),
    )
    op.execute("UPDATE trips SET status = 'confirmed' WHERE status IS NULL OR status = 'draft'")
    op.alter_column("trips", "status", nullable=False)


def downgrade() -> None:
    op.drop_column("trips", "status")
