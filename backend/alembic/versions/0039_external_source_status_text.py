"""widen external source status text

Revision ID: 0039_external_source_status_text
Revises: 0038_policy_source_catalog
Create Date: 2026-09-14

Official source status notices are evidence, not fixed status labels.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0039_external_source_status_text"
down_revision: str | None = "0038_policy_source_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "external_source_records",
        "status_text",
        existing_type=sa.String(length=50),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "external_source_records",
        "status_text",
        existing_type=sa.Text(),
        type_=sa.String(length=50),
        existing_nullable=True,
        postgresql_using="left(status_text, 50)",
    )
