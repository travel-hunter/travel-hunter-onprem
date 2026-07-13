"""add policy source tracking

Revision ID: 0012_policy_source_tracking
Revises: 0011_phone_verification_codes
Create Date: 2026-05-22
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0012_policy_source_tracking"
down_revision: str | None = "0011_phone_verification_codes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("policies", sa.Column("source_type", sa.String(length=50), nullable=True))
    op.add_column("policies", sa.Column("source_name", sa.String(length=100), nullable=True))
    op.add_column("policies", sa.Column("source_category", sa.String(length=80), nullable=True))
    op.add_column(
        "policies",
        sa.Column("external_source_record_id", sa.BigInteger(), nullable=True),
    )
    op.add_column("policies", sa.Column("source_url", sa.String(length=500), nullable=True))
    op.add_column(
        "policies",
        sa.Column("source_canonical_key", sa.String(length=160), nullable=True),
    )
    op.add_column("policies", sa.Column("normalized_at", sa.DateTime(), nullable=True))
    op.add_column("policies", sa.Column("last_verified_at", sa.DateTime(), nullable=True))
    op.add_column(
        "policies",
        sa.Column("verification_status", sa.String(length=30), nullable=True),
    )
    op.create_foreign_key(
        "fk_policies_external_source_record_id_external_source_records",
        "policies",
        "external_source_records",
        ["external_source_record_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_policies_source_type", "policies", ["source_type"])
    op.create_index("ix_policies_source_name", "policies", ["source_name"])
    op.create_index("ix_policies_source_category", "policies", ["source_category"])
    op.create_index(
        "ix_policies_external_source_record_id",
        "policies",
        ["external_source_record_id"],
        unique=True,
    )
    op.create_index("ix_policies_source_canonical_key", "policies", ["source_canonical_key"])


def downgrade() -> None:
    op.drop_index("ix_policies_source_canonical_key", table_name="policies")
    op.drop_index("ix_policies_external_source_record_id", table_name="policies")
    op.drop_index("ix_policies_source_category", table_name="policies")
    op.drop_index("ix_policies_source_name", table_name="policies")
    op.drop_index("ix_policies_source_type", table_name="policies")
    op.drop_constraint(
        "fk_policies_external_source_record_id_external_source_records",
        "policies",
        type_="foreignkey",
    )
    op.drop_column("policies", "verification_status")
    op.drop_column("policies", "last_verified_at")
    op.drop_column("policies", "normalized_at")
    op.drop_column("policies", "source_canonical_key")
    op.drop_column("policies", "source_url")
    op.drop_column("policies", "external_source_record_id")
    op.drop_column("policies", "source_category")
    op.drop_column("policies", "source_name")
    op.drop_column("policies", "source_type")
