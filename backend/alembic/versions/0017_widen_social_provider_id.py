"""widen social account provider id

Revision ID: 0017_widen_social_provider_id
Revises: 0016_kakao_place_metadata
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_widen_social_provider_id"
down_revision = "0016_kakao_place_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "social_accounts",
        "provider_id",
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "social_accounts",
        "provider_id",
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=False,
    )
