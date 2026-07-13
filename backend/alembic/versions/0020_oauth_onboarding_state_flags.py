"""add oauth onboarding state flags

Revision ID: 0020_oauth_onboarding_state
Revises: 0019_email_first_signup
Create Date: 2026-06-17 13:45:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0020_oauth_onboarding_state"
down_revision: Union[str, None] = "0019_email_first_signup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS nickname_setup_completed BOOLEAN NOT NULL DEFAULT true
        """
    )
    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS profile_setup_skipped BOOLEAN NOT NULL DEFAULT false
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS profile_setup_skipped")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS nickname_setup_completed")
