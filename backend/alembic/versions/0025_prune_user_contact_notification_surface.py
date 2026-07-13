"""prune user contact and notification settings surface

Revision ID: 0025_prune_contact_notify
Revises: 0024_local_kst_time_shift
Create Date: 2026-07-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0025_prune_contact_notify"
down_revision: str | None = "0024_local_kst_time_shift"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("phone_verification_codes")
    op.drop_table("user_notification_settings")
    op.drop_column("users", "birth_date")
    op.drop_column("users", "gender")
    op.drop_column("users", "region")
    op.drop_column("users", "residence_area")
    op.drop_column("users", "phone_number")
    op.drop_column("users", "phone_verified_at")


def downgrade() -> None:
    op.add_column("users", sa.Column("phone_verified_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("phone_number", sa.String(length=30), nullable=True))
    op.add_column("users", sa.Column("residence_area", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("region", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("gender", sa.String(length=10), nullable=True))
    op.add_column("users", sa.Column("birth_date", sa.Date(), nullable=True))

    op.create_table(
        "user_notification_settings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("deadline_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
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
