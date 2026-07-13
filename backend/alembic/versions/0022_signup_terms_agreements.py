"""Add signup agreement tracking.

Revision ID: 0022_signup_terms_agreements
Revises: 0021_legacy_social_nickname
Create Date: 2026-06-26 14:55:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0022_signup_terms_agreements"
down_revision = "0021_legacy_social_nickname"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("terms_accepted", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("terms_version", sa.String(length=32), nullable=True))
    op.add_column(
        "users",
        sa.Column("privacy_accepted", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("users", sa.Column("privacy_accepted_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("privacy_version", sa.String(length=32), nullable=True))

    op.add_column(
        "pending_signups",
        sa.Column("terms_accepted", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("pending_signups", sa.Column("terms_accepted_at", sa.DateTime(), nullable=True))
    op.add_column("pending_signups", sa.Column("terms_version", sa.String(length=32), nullable=True))
    op.add_column(
        "pending_signups",
        sa.Column("privacy_accepted", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("pending_signups", sa.Column("privacy_accepted_at", sa.DateTime(), nullable=True))
    op.add_column("pending_signups", sa.Column("privacy_version", sa.String(length=32), nullable=True))

    op.create_table(
        "pending_social_signups",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("email_verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("nickname", sa.String(length=100), nullable=True),
        sa.Column("redirect_path", sa.String(length=500), server_default="/home", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_pending_social_signups_token_hash",
        "pending_social_signups",
        ["token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pending_social_signups_token_hash", table_name="pending_social_signups")
    op.drop_table("pending_social_signups")

    op.drop_column("pending_signups", "privacy_version")
    op.drop_column("pending_signups", "privacy_accepted_at")
    op.drop_column("pending_signups", "privacy_accepted")
    op.drop_column("pending_signups", "terms_version")
    op.drop_column("pending_signups", "terms_accepted_at")
    op.drop_column("pending_signups", "terms_accepted")

    op.drop_column("users", "privacy_version")
    op.drop_column("users", "privacy_accepted_at")
    op.drop_column("users", "privacy_accepted")
    op.drop_column("users", "terms_version")
    op.drop_column("users", "terms_accepted_at")
    op.drop_column("users", "terms_accepted")
