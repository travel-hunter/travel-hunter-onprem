"""add apply_url to policies

Revision ID: 0004_policy_apply_url
Revises: 0003_user_saved_policies
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_policy_apply_url"
down_revision = "0003_user_saved_policies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("policies", sa.Column("apply_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("policies", "apply_url")
