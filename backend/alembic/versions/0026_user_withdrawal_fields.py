"""add user withdrawal fields

Revision ID: 0026_user_withdrawal_fields
Revises: 0025_prune_contact_notify
Create Date: 2026-07-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0026_user_withdrawal_fields"
down_revision: str | None = "0025_prune_contact_notify"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("withdrawn_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("withdrawn_email_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_users_withdrawn_email_hash", "users", ["withdrawn_email_hash"])


def downgrade() -> None:
    op.drop_index("ix_users_withdrawn_email_hash", table_name="users")
    op.drop_column("users", "withdrawn_email_hash")
    op.drop_column("users", "withdrawn_at")
