"""add policy-specific photo assignments

Revision ID: 0037_policy_photos
Revises: 0036_region_photos
Create Date: 2026-09-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0037_policy_photos"
down_revision: str | None = "0036_region_photos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_photos",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column(
            "policy_id",
            sa.BigInteger(),
            sa.ForeignKey("policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_content_id", sa.String(60), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=False),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        sa.Column("alt_text", sa.String(200), nullable=False),
        sa.Column("attribution_text", sa.String(120), nullable=False),
        sa.Column("relevance_score", sa.Integer(), nullable=False),
        sa.Column("assignment_reason", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("policy_id"),
    )


def downgrade() -> None:
    op.drop_table("policy_photos")
