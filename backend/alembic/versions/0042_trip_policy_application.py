"""add per-trip island support application progress

Revision ID: 0042_trip_policy_application
Revises: 0041_policy_auto_publish
Create Date: 2026-09-14

Four nullable columns on trip_policies, no rows. The checklist holds document readiness flags only.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0042_trip_policy_application"
down_revision: str | None = "0041_policy_auto_publish"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUS_CHECK = (
    "application_status IS NULL OR application_status IN "
    "('not_started', 'applied', 'selected', 'not_selected', 'traveled', 'documents_submitted', 'paid')"
)


def upgrade() -> None:
    op.add_column("trip_policies", sa.Column("application_status", sa.String(24), nullable=True))
    op.add_column(
        "trip_policies",
        sa.Column("application_checklist", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
    )
    op.add_column("trip_policies", sa.Column("application_updated_at", sa.DateTime(), nullable=True))
    op.add_column("trip_policies", sa.Column("application_updated_by_user_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_trip_policies_application_updated_by_user_id",
        "trip_policies",
        "users",
        ["application_updated_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint("ck_trip_policies_application_status", "trip_policies", _STATUS_CHECK)


def downgrade() -> None:
    op.drop_constraint("ck_trip_policies_application_status", "trip_policies", type_="check")
    op.drop_constraint("fk_trip_policies_application_updated_by_user_id", "trip_policies", type_="foreignkey")
    op.drop_column("trip_policies", "application_updated_by_user_id")
    op.drop_column("trip_policies", "application_updated_at")
    op.drop_column("trip_policies", "application_checklist")
    op.drop_column("trip_policies", "application_status")
