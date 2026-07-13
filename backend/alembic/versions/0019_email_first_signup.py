"""ensure email-first pending signup table

Revision ID: 0019_email_first_signup
Revises: 0018_add_trip_revision
Create Date: 2026-06-15 13:06:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0019_email_first_signup"
down_revision: Union[str, None] = "0018_add_trip_revision"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_signups (
            id BIGSERIAL PRIMARY KEY,
            email VARCHAR(255) NOT NULL UNIQUE,
            token_hash VARCHAR(255) NOT NULL UNIQUE,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
            expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
        )
        """
    )
    op.execute("ALTER TABLE pending_signups DROP COLUMN IF EXISTS password_hash")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pending_signups_email ON pending_signups (email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pending_signups_token_hash ON pending_signups (token_hash)")


def downgrade() -> None:
    # Keep the table on downgrade because earlier 0010 owns its lifecycle for
    # fresh databases. This revision is an idempotent compatibility guard.
    pass
