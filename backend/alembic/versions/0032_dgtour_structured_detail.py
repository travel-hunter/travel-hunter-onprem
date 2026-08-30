"""normalize digital tourism resident card structured detail

Revision ID: 0032_dgtour_structured
Revises: 0031_dgtour_identity
Create Date: 2026-07-24

Existing development databases may already contain old dgtour structured_detail
JSON copied from the half-trip conflation era. The public policy detail page
renders structured_detail before top-level fallback fields, so source identity
correction must also replace that JSON.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0032_dgtour_structured"
down_revision: str | None = "0031_dgtour_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIGITAL_SOURCE_CATEGORY = "digital_tourism_resident_card"

STRUCTURED_DETAIL_SQL = f"""
WITH digital AS (
  SELECT
    id,
    COALESCE(
      NULLIF(substring(title from '\\[([^\\]]+)\\]'), ''),
      NULLIF(regexp_replace(title, '\\s*디지털관광주민증\\s*혜택.*$', ''), ''),
      NULLIF(city_name, ''),
      NULLIF(region, ''),
      '해당 지역'
    ) AS display_city,
    COALESCE(NULLIF(benefit_detail, ''), '지역 제휴 혜택') AS benefit_text,
    end_date
  FROM (
    SELECT
      p.*,
      CASE
        WHEN p.source_canonical_key LIKE 'digital-tourism-resident-card:%'
          THEN split_part(p.source_canonical_key, ':', 3)
        ELSE NULL
      END AS city_name
    FROM policies p
    WHERE p.source_category = '{DIGITAL_SOURCE_CATEGORY}'
       OR p.slug LIKE 'dgtour-%'
       OR p.title ILIKE '%디지털관광주민증%'
       OR p.title ILIKE '%디지털 관광주민증%'
  ) scoped
)
UPDATE policies p
SET
  structured_detail = jsonb_build_object(
    'supportContent',
    jsonb_build_array(
      jsonb_build_object(
        'title', '혜택',
        'amount', digital.benefit_text,
        'description', digital.benefit_text
      )
    ),
    'periods',
    CASE
      WHEN digital.end_date IS NULL THEN '[]'::jsonb
      ELSE jsonb_build_array(
        jsonb_build_object(
          'title', '기간',
          'description', '~ ' || to_char(digital.end_date, 'YYYY-MM-DD')
        )
      )
    END,
    'applicationTarget',
    jsonb_build_array(
      jsonb_build_object(
        'title', '신청 대상',
        'description', digital.display_city || ' 디지털관광주민증을 발급하고 해당 지역을 방문·이용하는 여행자'
      ),
      jsonb_build_object(
        'title', '이용 조건',
        'description', 'VisitKorea 디지털관광주민증 발급 및 지역 제휴처 이용 조건을 충족해야 합니다.'
      )
    ),
    'requiredDocuments',
    jsonb_build_array(
      jsonb_build_object(
        'title', '필요서류',
        'description', '별도 제출 서류 없음 · 디지털관광주민증 발급/제시 기준으로 적용'
      )
    ),
    'notes',
    jsonb_build_array(
      jsonb_build_object(
        'title', '비고',
        'description', '제휴 혜택, 운영 기간, 이용 조건은 VisitKorea 공식 안내에서 최종 확인하세요.'
      )
    )
  ),
  updated_at = now()
FROM digital
WHERE p.id = digital.id;
""".strip()

DOWNGRADE_GUARD_SQL = """
DO $$
BEGIN
  RAISE NOTICE '0032_dgtour_structured downgrade is a guarded data no-op; restoring conflated structured_detail is unsafe.';
END $$;
""".strip()


def upgrade() -> None:
    op.execute(STRUCTURED_DETAIL_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_GUARD_SQL)
