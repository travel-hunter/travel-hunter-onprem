"""Add policy structured detail JSON.

Revision ID: 0023_policy_structured_detail
Revises: 0022_signup_terms_agreements
Create Date: 2026-06-30 12:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0023_policy_structured_detail"
down_revision = "0022_signup_terms_agreements"
branch_labels = None
depends_on = None


structured_detail_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column(
        "policies",
        sa.Column("structured_detail", structured_detail_type, nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE policies
            SET structured_detail = jsonb_build_object(
                'benefits', CASE
                    WHEN NULLIF(BTRIM(COALESCE(benefit_detail, policy_comment, description, '')), '') IS NULL THEN '[]'::jsonb
                    ELSE jsonb_build_array(jsonb_strip_nulls(jsonb_build_object(
                        'title', '혜택',
                        'description', NULLIF(BTRIM(COALESCE(benefit_detail, policy_comment, description)), ''),
                        'amount', NULLIF(BTRIM(benefit_detail), '')
                    )))
                END,
                'conditions', '[]'::jsonb,
                'periods', CASE
                    WHEN NULLIF(BTRIM(COALESCE(policy_period, '')), '') IS NOT NULL THEN jsonb_build_array(jsonb_build_object(
                        'title', '기간',
                        'description', BTRIM(policy_period)
                    ))
                    WHEN start_date IS NOT NULL OR end_date IS NOT NULL THEN jsonb_build_array(jsonb_strip_nulls(jsonb_build_object(
                        'title', '신청 기간',
                        'description', CONCAT_WS(' ~ ', start_date::text, end_date::text),
                        'startDate', start_date::text,
                        'endDate', end_date::text
                    )))
                    ELSE '[]'::jsonb
                END,
                'links', (
                    SELECT COALESCE(jsonb_agg(link_item), '[]'::jsonb)
                    FROM (
                        SELECT jsonb_build_object('label', '신청하기', 'url', apply_url) AS link_item
                        WHERE NULLIF(BTRIM(COALESCE(apply_url, '')), '') IS NOT NULL
                        UNION ALL
                        SELECT jsonb_build_object('label', '공식 안내', 'url', official_url) AS link_item
                        WHERE NULLIF(BTRIM(COALESCE(official_url, '')), '') IS NOT NULL
                          AND COALESCE(official_url, '') <> COALESCE(apply_url, '')
                    ) links
                ),
                'documents', (
                    SELECT COALESCE(jsonb_agg(jsonb_build_object('title', '필요 서류', 'description', pd.document_name) ORDER BY pd.id), '[]'::jsonb)
                    FROM policy_documents pd
                    WHERE pd.policy_id = policies.id
                      AND NULLIF(BTRIM(COALESCE(pd.document_name, '')), '') IS NOT NULL
                ),
                'notices', CASE
                    WHEN NULLIF(BTRIM(COALESCE(policy_comment, '')), '') IS NOT NULL
                         AND COALESCE(policy_comment, '') <> COALESCE(benefit_detail, '') THEN jsonb_build_array(jsonb_build_object(
                        'title', '확인 필요 사항',
                        'description', BTRIM(policy_comment)
                    ))
                    ELSE '[]'::jsonb
                END
            )
            WHERE structured_detail IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("policies", "structured_detail")
