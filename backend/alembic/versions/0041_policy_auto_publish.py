"""add review reason and last parsed count for the auto-publish gate

Revision ID: 0041_policy_auto_publish
Revises: 0040_eligible_island_catalog
Create Date: 2026-09-14

Two nullable columns, no rows. publication_mode stays 'review' for every source.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0041_policy_auto_publish"
down_revision: str | None = "0040_eligible_island_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("policy_review_candidates", sa.Column("review_reason", sa.String(40), nullable=True))
    op.add_column("policy_collection_sources", sa.Column("last_parsed_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("policy_collection_sources", "last_parsed_count")
    op.drop_column("policy_review_candidates", "review_reason")
