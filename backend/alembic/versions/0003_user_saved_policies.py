"""add user saved policies

Revision ID: 0003_user_saved_policies
Revises: 0002_user_profile_prefs
Create Date: 2026-05-06
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_user_saved_policies"
down_revision = "0002_user_profile_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_saved_policies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("policy_id", sa.BigInteger(), nullable=False),
        sa.Column("saved_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "policy_id"),
    )
    op.create_index(
        op.f("ix_user_saved_policies_policy_id"),
        "user_saved_policies",
        ["policy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_saved_policies_user_id"),
        "user_saved_policies",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_saved_policies_user_id"), table_name="user_saved_policies")
    op.drop_index(op.f("ix_user_saved_policies_policy_id"), table_name="user_saved_policies")
    op.drop_table("user_saved_policies")
