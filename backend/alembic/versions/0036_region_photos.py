"""add policies.city and region_photos lookup table

Revision ID: 0036_region_photos
Revises: 0035_stay_policy_identity
Create Date: 2026-09-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0036_region_photos"
down_revision: str | None = "0035_stay_policy_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("policies", sa.Column("city", sa.String(80), nullable=True))
    op.create_table(
        "region_photos",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("provider", sa.String(30), nullable=False),
        # sido stores the same abbreviated form as policies.region (전남/경북).
        sa.Column("sido", sa.String(50), nullable=False),
        # '' is the sido-level representative photo sentinel; NULL would defeat
        # the unique constraint and let upserts insert duplicates.
        sa.Column("city", sa.String(80), nullable=False, server_default=""),
        sa.Column("provider_content_id", sa.String(60), nullable=True),
        sa.Column("content_title", sa.String(200), nullable=True),
        sa.Column("hero_image_url", sa.String(500), nullable=True),
        sa.Column("thumb_image_url", sa.String(500), nullable=True),
        sa.Column("provider_image_url", sa.String(500), nullable=True),
        sa.Column(
            "storage_kind", sa.String(20), nullable=False, server_default="remote"
        ),
        sa.Column(
            "attribution_text",
            sa.String(120),
            nullable=False,
            server_default="사진: 한국관광공사",
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("provider", "sido", "city"),
    )


def downgrade() -> None:
    op.drop_table("region_photos")
    op.drop_column("policies", "city")
