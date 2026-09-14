"""add approved eligible island catalog

Revision ID: 0040_eligible_island_catalog
Revises: 0039_external_source_status_text
Create Date: 2026-09-14

Inserts no rows: the island_visit_2026 catalog row is code-owned by the repository.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0040_eligible_island_catalog"
down_revision: str | None = "0039_external_source_status_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eligible_island_catalogs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("key", sa.String(80), nullable=False, unique=True),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("notice_list_url", sa.String(500), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("approved_snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_eligible_island_catalogs_key", "eligible_island_catalogs", ["key"])

    op.create_table(
        "eligible_island_catalog_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("catalog_id", sa.BigInteger(), sa.ForeignKey("eligible_island_catalogs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notice_url", sa.String(500), nullable=True),
        sa.Column("notice_title", sa.String(300), nullable=True),
        sa.Column("attachment_url", sa.String(500), nullable=True),
        sa.Column("attachment_filename", sa.String(255), nullable=True),
        sa.Column("attachment_fingerprint", sa.String(64), nullable=True),
        sa.Column("attachment_documents", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False, server_default="[]"),
        sa.Column("parser_version", sa.String(40), nullable=False, server_default="v1"),
        sa.Column("fetched_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("entry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("added_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("removed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("changed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("review_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected', 'superseded')",
            name="ck_eligible_island_catalog_snapshots_review_status",
        ),
    )
    op.create_index("ix_eligible_island_catalog_snapshots_catalog_id", "eligible_island_catalog_snapshots", ["catalog_id"])
    op.create_index("ix_eligible_island_catalog_snapshots_attachment_fingerprint", "eligible_island_catalog_snapshots", ["attachment_fingerprint"])
    op.create_index("ix_eligible_island_catalog_snapshots_reviewed_by_user_id", "eligible_island_catalog_snapshots", ["reviewed_by_user_id"])

    op.create_table(
        "eligible_island_snapshot_entries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("snapshot_id", sa.BigInteger(), sa.ForeignKey("eligible_island_catalog_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("normalized_name", sa.String(120), nullable=False),
        sa.Column("jurisdiction_name", sa.String(120), nullable=False),
        sa.Column("raw_region_text", sa.String(300), nullable=True),
        sa.Column("row_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "snapshot_id", "normalized_name", "jurisdiction_name",
            name="uq_eligible_island_snapshot_entries_snapshot_name_jurisdiction",
        ),
    )
    op.create_index("ix_eligible_island_snapshot_entries_snapshot_id", "eligible_island_snapshot_entries", ["snapshot_id"])

    op.create_table(
        "eligible_islands",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("catalog_id", sa.BigInteger(), sa.ForeignKey("eligible_island_catalogs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_id", sa.BigInteger(), sa.ForeignKey("eligible_island_catalog_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("normalized_name", sa.String(120), nullable=False),
        sa.Column("jurisdiction_name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "catalog_id", "normalized_name", "jurisdiction_name",
            name="uq_eligible_islands_catalog_name_jurisdiction",
        ),
    )
    op.create_index("ix_eligible_islands_catalog_id", "eligible_islands", ["catalog_id"])
    op.create_index("ix_eligible_islands_snapshot_id", "eligible_islands", ["snapshot_id"])
    op.create_index("ix_eligible_islands_normalized_name", "eligible_islands", ["normalized_name"])


def downgrade() -> None:
    op.drop_index("ix_eligible_islands_normalized_name", table_name="eligible_islands")
    op.drop_index("ix_eligible_islands_snapshot_id", table_name="eligible_islands")
    op.drop_index("ix_eligible_islands_catalog_id", table_name="eligible_islands")
    op.drop_table("eligible_islands")
    op.drop_index("ix_eligible_island_snapshot_entries_snapshot_id", table_name="eligible_island_snapshot_entries")
    op.drop_table("eligible_island_snapshot_entries")
    op.drop_index("ix_eligible_island_catalog_snapshots_reviewed_by_user_id", table_name="eligible_island_catalog_snapshots")
    op.drop_index("ix_eligible_island_catalog_snapshots_attachment_fingerprint", table_name="eligible_island_catalog_snapshots")
    op.drop_index("ix_eligible_island_catalog_snapshots_catalog_id", table_name="eligible_island_catalog_snapshots")
    op.drop_table("eligible_island_catalog_snapshots")
    op.drop_index("ix_eligible_island_catalogs_key", table_name="eligible_island_catalogs")
    op.drop_table("eligible_island_catalogs")
