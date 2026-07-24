"""clean digital tourism resident card detail text and official URLs

Revision ID: 0034_dgtour_detail_urls
Revises: 0033_dgtour_scope
Create Date: 2026-07-25

Digital tourism resident card rows must not render half-trip campaign copy or
half-trip CTA URLs. This data migration rewrites existing normalized/seed rows
with digital-only structured detail and VisitKorea dgtourcard region URLs
confirmed from the rendered VisitKorea dgtourcard map.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0034_dgtour_detail_urls"
down_revision: str | None = "0033_dgtour_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIGITAL_SOURCE_CATEGORY = "digital_tourism_resident_card"
SOURCE_URL = "https://korean.visitkorea.or.kr/dgtourcard/"
SUPPORT_CONTENT_TEXT = "디지털관광주민증 발급 지역의 숙박·식음·체험·관광지 제휴 혜택"
BENEFIT_VALUE_TEXT = "지역 제휴 혜택"
USAGE_CONDITION_TEXT = "VisitKorea/대한민국 구석구석에서 디지털관광주민증을 발급하고 제휴처에서 제시해야 합니다."
REQUIRED_DOCUMENTS_TEXT = "별도 제출 서류 없음 · 디지털관광주민증 발급/제시 기준으로 적용"
OFFICIAL_CONFIRMATION_NOTE = "제휴처별 할인율, 운영 기간, 이용 조건은 VisitKorea 공식 안내에서 최종 확인하세요."
BENEFIT_VARIATION_NOTE = "지역별 제휴처와 혜택은 변동될 수 있습니다."

REGIONAL_URL_VALUES = """
    ('철원', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=51&signguCd=51780'),
    ('양양', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=51&signguCd=51830'),
    ('정선', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=51&signguCd=51770'),
    ('삼척', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=51&signguCd=51230'),
    ('태백', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=51&signguCd=51190'),
    ('홍천', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=51&signguCd=51720'),
    ('평창', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=51&signguCd=51760'),
    ('영월', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=51&signguCd=51750'),
    ('연천', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=41&signguCd=41800'),
    ('가평', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=41&signguCd=41820'),
    ('강화', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=28&signguCd=28710'),
    ('태안', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=44&signguCd=44825'),
    ('제천', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=43&signguCd=43150'),
    ('단양', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=43&signguCd=43800'),
    ('괴산', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=43&signguCd=43760'),
    ('예산', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=44&signguCd=44810'),
    ('옥천', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=43&signguCd=43730'),
    ('영동', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=43&signguCd=43740'),
    ('보령', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=44&signguCd=44180'),
    ('보은', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=43&signguCd=43720'),
    ('김제', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=52&signguCd=52210'),
    ('무주', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=52&signguCd=52730'),
    ('고창', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=52&signguCd=52790'),
    ('임실', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=52&signguCd=52750'),
    ('영광', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=12&signguCd=12830'),
    ('남원', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=52&signguCd=52190'),
    ('함평', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=12&signguCd=12820'),
    ('곡성', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=12&signguCd=12720'),
    ('신안', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=12&signguCd=12870'),
    ('해남', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=12&signguCd=12790'),
    ('장흥', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=12&signguCd=12770'),
    ('구례', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=12&signguCd=12730'),
    ('담양', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=12&signguCd=12710'),
    ('순창', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=52&signguCd=52770'),
    ('고흥', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=12&signguCd=12740'),
    ('완도', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=12&signguCd=12850'),
    ('영주', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=47&signguCd=47210'),
    ('안동', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=47&signguCd=47170'),
    ('영덕', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=47&signguCd=47770'),
    ('청도', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=47&signguCd=47820'),
    ('부산동구', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=26&signguCd=26170'),
    ('부산영도', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=26&signguCd=26200'),
    ('부산서구', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=26&signguCd=26140'),
    ('밀양', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=48&signguCd=48270'),
    ('하동', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=48&signguCd=48850'),
    ('합천', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=48&signguCd=48890'),
    ('거창', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=48&signguCd=48880'),
    ('고령', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=47&signguCd=47830'),
    ('의성', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=47&signguCd=47730'),
    ('울진', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=47&signguCd=47930'),
    ('함양', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=48&signguCd=48870'),
    ('산청', 'https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?mtpcDoCd=48&signguCd=48860')
""".strip()

CITY_SQL = """
COALESCE(
  NULLIF(substring(title from '\\[([^\\]]+)\\]'), ''),
  NULLIF((string_to_array(source_canonical_key, ':'))[array_length(string_to_array(source_canonical_key, ':'), 1)], ''),
  NULLIF(regexp_replace(COALESCE(slug, ''), '^dgtour-([^-]+)-.*$', '\\1'), COALESCE(slug, '')),
  '해당 지역'
)
""".strip()

POLICY_DETAIL_URL_SQL = f"""
WITH regional_url(city_name, url) AS (
  VALUES
    {REGIONAL_URL_VALUES}
),
digital AS (
  SELECT
    p.id,
    {CITY_SQL} AS display_city,
    COALESCE(u.url, '{SOURCE_URL}') AS official_url
  FROM policies p
  LEFT JOIN regional_url u ON u.city_name = {CITY_SQL}
  WHERE p.source_category = '{DIGITAL_SOURCE_CATEGORY}'
     OR p.slug LIKE 'dgtour-%'
     OR p.title ILIKE '%디지털관광주민증%'
     OR p.title ILIKE '%디지털 관광주민증%'
)
UPDATE policies p
SET
  description = digital.display_city || ' 디지털관광주민증을 발급하고 지역 제휴 혜택을 확인할 수 있습니다.',
  benefit_detail = '{BENEFIT_VALUE_TEXT}',
  structured_detail = jsonb_build_object(
    'supportContent', jsonb_build_array(
      jsonb_build_object('title', '혜택', 'amount', '{BENEFIT_VALUE_TEXT}', 'description', '{SUPPORT_CONTENT_TEXT}')
    ),
    'periods', CASE
      WHEN p.end_date IS NULL THEN '[]'::jsonb
      ELSE jsonb_build_array(jsonb_build_object('title', '기간', 'description', '~ ' || to_char(p.end_date, 'YYYY-MM-DD')))
    END,
    'applicationTarget', jsonb_build_array(
      jsonb_build_object('title', '신청대상', 'description', digital.display_city || ' 디지털관광주민증을 발급한 여행자'),
      jsonb_build_object('title', '이용조건', 'description', '{USAGE_CONDITION_TEXT}')
    ),
    'requiredDocuments', jsonb_build_array(
      jsonb_build_object('title', '필요서류', 'description', '{REQUIRED_DOCUMENTS_TEXT}')
    ),
    'notes', jsonb_build_array(
      jsonb_build_object('title', '비고', 'description', '{OFFICIAL_CONFIRMATION_NOTE}'),
      jsonb_build_object('title', '비고', 'description', '{BENEFIT_VARIATION_NOTE}')
    )
  ),
  target_condition = digital.display_city || ' 디지털관광주민증을 발급한 여행자\n{USAGE_CONDITION_TEXT}',
  official_url = digital.official_url,
  apply_url = NULL,
  source_url = digital.official_url,
  policy_comment = digital.display_city || ' 디지털관광주민증을 발급하고 지역 제휴 혜택을 확인할 수 있습니다.',
  updated_at = now()
FROM digital
WHERE p.id = digital.id;
""".strip()

EXTERNAL_RECORD_DETAIL_URL_SQL = f"""
WITH regional_url(city_name, url) AS (
  VALUES
    {REGIONAL_URL_VALUES}
),
digital AS (
  SELECT
    r.id,
    COALESCE(NULLIF(r.city, ''), NULLIF(substring(r.title from '\\[([^\\]]+)\\]'), ''), '해당 지역') AS display_city,
    COALESCE(u.url, '{SOURCE_URL}') AS detail_url
  FROM external_source_records r
  LEFT JOIN regional_url u ON u.city_name = COALESCE(NULLIF(r.city, ''), NULLIF(substring(r.title from '\\[([^\\]]+)\\]'), ''))
  WHERE r.source_category = '{DIGITAL_SOURCE_CATEGORY}'
)
UPDATE external_source_records r
SET
  source_url = '{SOURCE_URL}',
  detail_url = digital.detail_url,
  collected_page_url = '{SOURCE_URL}',
  benefit_text = '{SUPPORT_CONTENT_TEXT}을 이용할 수 있습니다.',
  benefit_value_text = '{BENEFIT_VALUE_TEXT}',
  raw_detail_text = '{SUPPORT_CONTENT_TEXT}을 이용할 수 있습니다.',
  raw_payload = r.raw_payload || jsonb_build_object(
    'supportContent', '{SUPPORT_CONTENT_TEXT}',
    'applicationTarget', digital.display_city || ' 디지털관광주민증을 발급한 여행자',
    'usageCondition', '{USAGE_CONDITION_TEXT}',
    'requiredDocuments', '{REQUIRED_DOCUMENTS_TEXT}',
    'notes', jsonb_build_array('{OFFICIAL_CONFIRMATION_NOTE}', '{BENEFIT_VARIATION_NOTE}')
  ),
  updated_at = now()
FROM digital
WHERE r.id = digital.id;
""".strip()

DOWNGRADE_GUARD_SQL = """
DO $$
BEGIN
  RAISE NOTICE '0034_dgtour_detail_urls downgrade is a guarded data no-op; restoring half-trip conflated digital tourism detail is unsafe.';
END $$;
""".strip()

UPGRADE_SQL = [POLICY_DETAIL_URL_SQL, EXTERNAL_RECORD_DETAIL_URL_SQL]


def upgrade() -> None:
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade() -> None:
    op.execute(DOWNGRADE_GUARD_SQL)
