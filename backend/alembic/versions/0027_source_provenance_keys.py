"""add external source logical provenance keys

Revision ID: 0027_source_provenance_keys
Revises: 0026_user_withdrawal_fields
Create Date: 2026-07-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0027_source_provenance_keys"
down_revision: str | None = "0026_user_withdrawal_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SNAPSHOT_KEY_VERSION = "snapshot-v1"
STAY_DISCOUNT_LOGICAL_KEY = "stay-discount:2026-summer"


def upgrade() -> None:
    op.add_column(
        "external_source_records",
        sa.Column("logical_key", sa.String(200), nullable=True),
    )
    op.add_column(
        "external_source_records",
        sa.Column("canonical_key_version", sa.String(30), nullable=True),
    )
    op.create_index(
        "ix_external_source_records_logical_key",
        "external_source_records",
        ["logical_key"],
        unique=False,
    )
    op.execute(
        f"""
        UPDATE external_source_records
        SET logical_key = CASE
              WHEN source_category = 'stay_discount'
                THEN '{STAY_DISCOUNT_LOGICAL_KEY}'
              WHEN source_category = 'local_half_trip'
                   AND COALESCE(end_date, start_date) IS NOT NULL
                   AND region IS NOT NULL
                   AND city IS NOT NULL
                THEN 'local-half-trip:' || EXTRACT(YEAR FROM COALESCE(end_date, start_date))::integer || ':' || region || ':' || city
              WHEN source_category = 'regional_benefit'
                   AND COALESCE(end_date, start_date) IS NOT NULL
                   AND region IS NOT NULL
                   AND city IS NOT NULL
                THEN 'travelmonth:regional-benefit:' || EXTRACT(YEAR FROM COALESCE(end_date, start_date))::integer || ':' || region || ':' || city
              WHEN source_category = 'traffic_benefit'
                   AND COALESCE(end_date, start_date) IS NOT NULL
                   AND region IS NOT NULL
                   AND city IS NOT NULL
                THEN 'travelmonth:traffic-benefit:' || EXTRACT(YEAR FROM COALESCE(end_date, start_date))::integer || ':' || region || ':' || city
            END,
            canonical_key_version = '{SNAPSHOT_KEY_VERSION}'
        WHERE source_category IN ('regional_benefit', 'traffic_benefit', 'local_half_trip', 'stay_discount')
        """
    )


def downgrade() -> None:
    op.drop_index("ix_external_source_records_logical_key", table_name="external_source_records")
    op.drop_column("external_source_records", "canonical_key_version")
    op.drop_column("external_source_records", "logical_key")
