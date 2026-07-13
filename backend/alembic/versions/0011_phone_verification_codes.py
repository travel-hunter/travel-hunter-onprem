"""add phone verification codes

Revision ID: 0011_phone_verification_codes
Revises: 0010_external_source_records
Create Date: 2026-05-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0011_phone_verification_codes"
down_revision: str | None = "0010_external_source_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "phone_verification_codes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("phone_number", sa.String(length=30), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_phone_verification_codes_user_id", "phone_verification_codes", ["user_id"])
    op.create_index("ix_phone_verification_codes_phone_number", "phone_verification_codes", ["phone_number"])
    op.create_index("ix_phone_verification_codes_expires_at", "phone_verification_codes", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_phone_verification_codes_expires_at", table_name="phone_verification_codes")
    op.drop_index("ix_phone_verification_codes_phone_number", table_name="phone_verification_codes")
    op.drop_index("ix_phone_verification_codes_user_id", table_name="phone_verification_codes")
    op.drop_table("phone_verification_codes")
