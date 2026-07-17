"""add policy slug aliases

Revision ID: 0027_policy_slug_aliases
Revises: 0026_user_withdrawal_fields
Create Date: 2026-07-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0027_policy_slug_aliases"
down_revision: str | None = "0026_user_withdrawal_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_slug_aliases",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("old_slug", sa.String(length=160), nullable=False),
        sa.Column("policy_id", sa.BigInteger(), nullable=False),
        sa.Column("canonical_slug", sa.String(length=160), nullable=False),
        sa.Column(
            "alias_kind",
            sa.String(length=50),
            server_default="legacy",
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("old_slug"),
    )
    op.create_index(
        op.f("ix_policy_slug_aliases_policy_id"),
        "policy_slug_aliases",
        ["policy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_policy_slug_aliases_canonical_slug"),
        "policy_slug_aliases",
        ["canonical_slug"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_policy_slug_aliases_canonical_slug"),
        table_name="policy_slug_aliases",
    )
    op.drop_index(op.f("ix_policy_slug_aliases_policy_id"), table_name="policy_slug_aliases")
    op.drop_table("policy_slug_aliases")
