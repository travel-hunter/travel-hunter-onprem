"""add user profile preferences

Revision ID: 0002_user_profile_prefs
Revises: 0001_create_v0_3_schema
Create Date: 2026-05-04 00:00:00.000000
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_user_profile_prefs"
down_revision: str | None = "0001_create_v0_3_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("travel_style", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("travel_budget", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "travel_budget")
    op.drop_column("users", "travel_style")
