"""add card_summary to policies and review_scope to review candidates

Revision ID: 0043_policy_card_summary
Revises: 0042_trip_policy_application
Create Date: 2026-09-22

Three columns, no data changes. card_summary is nullable and is NOT backfilled - existing policies keep
showing their amount at read time until an admin approves a card copy. review_scope defaults to
'full_policy' so every existing candidate behaves as before.

Downgrade drops the two columns only. If any card_summary has been approved, export it first
(scripts/audit_policy_card_copy.py writes counts and hashes; the values themselves live only in this column).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0043_policy_card_summary"
down_revision: str | None = "0042_trip_policy_application"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REVIEW_SCOPE_CHECK = "ck_policy_review_candidates_review_scope"


def upgrade() -> None:
    op.add_column("policies", sa.Column("card_summary", sa.Text(), nullable=True))
    op.add_column(
        "policy_review_candidates",
        sa.Column("review_scope", sa.String(24), nullable=False, server_default="full_policy"),
    )
    op.add_column("policy_review_candidates", sa.Column("detail_fingerprint", sa.String(64), nullable=True))
    op.create_check_constraint(
        REVIEW_SCOPE_CHECK,
        "policy_review_candidates",
        "review_scope IN ('full_policy', 'card_copy_only')",
    )


def downgrade() -> None:
    op.drop_constraint(REVIEW_SCOPE_CHECK, "policy_review_candidates", type_="check")
    op.drop_column("policy_review_candidates", "detail_fingerprint")
    op.drop_column("policy_review_candidates", "review_scope")
    op.drop_column("policies", "card_summary")
