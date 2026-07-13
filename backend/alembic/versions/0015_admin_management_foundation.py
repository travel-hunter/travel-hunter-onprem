"""admin management foundation

Revision ID: 0015_admin_management_foundation
Revises: 0014_add_trip_participant_count
Create Date: 2026-05-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0015_admin_management_foundation"
down_revision = "0014_add_trip_participant_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), server_default="user", nullable=False),
    )
    op.create_check_constraint(
        "ck_users_role_user_admin",
        "users",
        "role IN ('user', 'admin')",
    )
    op.add_column(
        "policies",
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
    )
    op.create_check_constraint(
        "ck_policies_status_active_hidden",
        "policies",
        "status IN ('active', 'hidden')",
    )
    op.add_column(
        "policies",
        sa.Column("admin_override_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "policies",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("admin_user_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=300), nullable=True),
        sa.Column("before_json", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("after_json", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"]),
    )
    op.create_index("ix_admin_audit_logs_admin_user_id", "admin_audit_logs", ["admin_user_id"])
    op.create_index("ix_admin_audit_logs_action", "admin_audit_logs", ["action"])
    op.create_index("ix_admin_audit_logs_target_type", "admin_audit_logs", ["target_type"])
    op.create_index("ix_admin_audit_logs_target_id", "admin_audit_logs", ["target_id"])


def downgrade() -> None:
    op.drop_index("ix_admin_audit_logs_target_id", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_target_type", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_action", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_admin_user_id", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
    op.drop_column("policies", "updated_at")
    op.drop_column("policies", "admin_override_enabled")
    op.drop_constraint("ck_policies_status_active_hidden", "policies", type_="check")
    op.drop_column("policies", "status")
    op.drop_constraint("ck_users_role_user_admin", "users", type_="check")
    op.drop_column("users", "role")
