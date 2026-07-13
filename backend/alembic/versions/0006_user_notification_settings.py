"""add user notification settings

Revision ID: 0006_user_notification_settings
Revises: 0005_add_trip_invite_role
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_user_notification_settings"
down_revision = "0005_add_trip_invite_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_table("user_notification_settings")
