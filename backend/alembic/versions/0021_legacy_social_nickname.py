"""backfill legacy social users into nickname confirmation step

Revision ID: 0021_legacy_social_nickname
Revises: 0020_oauth_onboarding_state
Create Date: 2026-06-17 14:05:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0021_legacy_social_nickname"
down_revision: Union[str, None] = "0020_oauth_onboarding_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET nickname_setup_completed = false
        WHERE onboarding_completed = false
          AND EXISTS (
              SELECT 1
              FROM social_accounts
              WHERE social_accounts.user_id = users.id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE users
        SET nickname_setup_completed = true
        WHERE onboarding_completed = false
          AND EXISTS (
              SELECT 1
              FROM social_accounts
              WHERE social_accounts.user_id = users.id
          )
        """
    )
