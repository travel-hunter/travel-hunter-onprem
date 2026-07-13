"""add external source records

Revision ID: 0010_external_source_records
Revises: 0009_add_trip_status
Create Date: 2026-05-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0010_external_source_records"
down_revision: str | None = "0009_add_trip_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_source_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("source_category", sa.String(length=80), nullable=False),
        sa.Column("external_id", sa.String(length=160), nullable=False),
        sa.Column("canonical_key", sa.String(length=160), nullable=False),
        sa.Column("detail_url", sa.String(length=500), nullable=True),
        sa.Column("collected_page_url", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("organizer_text", sa.String(length=300), nullable=False),
        sa.Column("organizers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("city", sa.String(length=80), nullable=True),
        sa.Column("is_nationwide", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status_text", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("benefit_text", sa.Text(), nullable=False),
        sa.Column("benefit_value_text", sa.String(length=300), nullable=True),
        sa.Column("extracted_amount_krw", sa.Integer(), nullable=True),
        sa.Column("extracted_discount_percent", sa.Integer(), nullable=True),
        sa.Column("benefit_value_type", sa.String(length=30), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("contact_text", sa.String(length=200), nullable=True),
        sa.Column(
            "inferred_travel_styles",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("field_completeness", sa.Integer(), nullable=False),
        sa.Column("raw_list_text", sa.Text(), nullable=False),
        sa.Column("raw_detail_text", sa.Text(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("freshness_status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_name", "source_category", "canonical_key"),
    )
    op.create_index(
        "ix_external_source_records_source_name",
        "external_source_records",
        ["source_name"],
    )
    op.create_index(
        "ix_external_source_records_source_category",
        "external_source_records",
        ["source_category"],
    )
    op.create_index(
        "ix_external_source_records_external_id",
        "external_source_records",
        ["external_id"],
    )
    op.create_index(
        "ix_external_source_records_canonical_key",
        "external_source_records",
        ["canonical_key"],
    )
    op.create_index(
        "ix_external_source_records_region",
        "external_source_records",
        ["region"],
    )
    op.create_index(
        "ix_external_source_records_status",
        "external_source_records",
        ["status"],
    )
    op.create_index(
        "ix_external_source_records_end_date",
        "external_source_records",
        ["end_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_external_source_records_end_date", table_name="external_source_records")
    op.drop_index("ix_external_source_records_status", table_name="external_source_records")
    op.drop_index("ix_external_source_records_region", table_name="external_source_records")
    op.drop_index("ix_external_source_records_canonical_key", table_name="external_source_records")
    op.drop_index("ix_external_source_records_external_id", table_name="external_source_records")
    op.drop_index(
        "ix_external_source_records_source_category",
        table_name="external_source_records",
    )
    op.drop_index("ix_external_source_records_source_name", table_name="external_source_records")
    op.drop_table("external_source_records")
