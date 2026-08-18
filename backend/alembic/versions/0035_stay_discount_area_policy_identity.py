"""allow stay discount area policies per source record

Revision ID: 0035_stay_policy_identity
Revises: 0034_dgtour_detail_urls
Create Date: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0035_stay_policy_identity"
down_revision: str | None = "0034_dgtour_detail_urls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_policies_external_source_record_id", table_name="policies")
    op.create_index(
        "ix_policies_external_source_record_id",
        "policies",
        ["external_source_record_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_policies_external_source_record_id", table_name="policies")
    op.create_index(
        "ix_policies_external_source_record_id",
        "policies",
        ["external_source_record_id"],
        unique=True,
    )
