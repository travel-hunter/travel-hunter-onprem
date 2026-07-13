"""add notification delivery foundation

Revision ID: 0007_notification_delivery
Revises: 0006_user_notification_settings
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_notification_delivery"
down_revision = "0006_user_notification_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone_number", sa.String(length=30), nullable=True))
    op.add_column("users", sa.Column("phone_verified_at", sa.DateTime(), nullable=True))

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("policy_id", sa.BigInteger(), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("lead_day", sa.Integer(), nullable=False),
        sa.Column("target_deadline_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("provider_message_id", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "policy_id",
            "channel",
            "lead_day",
            "target_deadline_date",
        ),
    )
    op.create_index(
        op.f("ix_notification_deliveries_policy_id"),
        "notification_deliveries",
        ["policy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_deliveries_user_id"),
        "notification_deliveries",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_deliveries_user_id"), table_name="notification_deliveries")
    op.drop_index(op.f("ix_notification_deliveries_policy_id"), table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "phone_number")
