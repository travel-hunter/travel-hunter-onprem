"""add role to trip invites

Revision ID: 0005_add_trip_invite_role
Revises: 0004_policy_apply_url
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_add_trip_invite_role"
down_revision = "0004_policy_apply_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trip_invites",
        sa.Column("role", sa.String(20), nullable=False, server_default="editor"),
    )


def downgrade() -> None:
    op.drop_column("trip_invites", "role")
