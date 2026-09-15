"""add approved policy collection source catalog

Revision ID: 0038_policy_source_catalog
Revises: 0037_policy_photos
Create Date: 2026-09-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0038_policy_source_catalog"
down_revision: str | None = "0037_policy_photos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_collection_sources",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("key", sa.String(80), nullable=False, unique=True),
        sa.Column("adapter_key", sa.String(80), nullable=False),
        sa.Column("official_url", sa.String(500), nullable=False),
        sa.Column("source_category", sa.String(80), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("publication_mode", sa.String(40), nullable=False, server_default="review"),
        sa.Column("expected_min_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_outcome", sa.String(40), nullable=True),
        sa.Column("last_collected_at", sa.DateTime(), nullable=True),
        sa.Column("last_successful_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "publication_mode IN ('review', 'auto_after_reviewed_baseline')",
            name="ck_policy_collection_sources_publication_mode",
        ),
    )
    op.create_index("ix_policy_collection_sources_key", "policy_collection_sources", ["key"])
    op.create_index(
        "ix_policy_collection_sources_source_category",
        "policy_collection_sources",
        ["source_category"],
    )

    op.create_table(
        "policy_review_candidates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("external_source_record_id", sa.BigInteger(), sa.ForeignKey("external_source_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("change_kind", sa.String(20), nullable=False),
        sa.Column("evidence_fingerprint", sa.String(64), nullable=False),
        sa.Column("reviewed_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("published_policy_id", sa.BigInteger(), sa.ForeignKey("policies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("review_status IN ('pending', 'approved', 'rejected', 'superseded')", name="ck_policy_review_candidates_review_status"),
        sa.CheckConstraint("change_kind IN ('new', 'material_change')", name="ck_policy_review_candidates_change_kind"),
    )
    op.create_index("ix_policy_review_candidates_external_source_record_id", "policy_review_candidates", ["external_source_record_id"])
    op.create_index("ix_policy_review_candidates_reviewed_by_user_id", "policy_review_candidates", ["reviewed_by_user_id"])
    op.create_index("ix_policy_review_candidates_published_policy_id", "policy_review_candidates", ["published_policy_id"])


def downgrade() -> None:
    op.drop_index("ix_policy_review_candidates_published_policy_id", table_name="policy_review_candidates")
    op.drop_index("ix_policy_review_candidates_reviewed_by_user_id", table_name="policy_review_candidates")
    op.drop_index("ix_policy_review_candidates_external_source_record_id", table_name="policy_review_candidates")
    op.drop_table("policy_review_candidates")
    op.drop_index("ix_policy_collection_sources_source_category", table_name="policy_collection_sources")
    op.drop_index("ix_policy_collection_sources_key", table_name="policy_collection_sources")
    op.drop_table("policy_collection_sources")
