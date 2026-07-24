"""separate digital tourism resident card policy identity

Revision ID: 0031_dgtour_identity
Revises: 0030_half_trip_five_semantics
Create Date: 2026-07-24

This is an idempotent data migration. It corrects existing dgtour seed rows
and conservative VisitKorea digital-tourism external records in place so saved
policies and trip attachments keep their stable policy ids/slugs.

Downgrade is a guarded data no-op because reverting source-family identity
would knowingly restore incorrect half-trip/digital-tourism conflation.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0031_dgtour_identity"
down_revision: str | None = "0030_half_trip_five_semantics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIGITAL_SOURCE_CATEGORY = "digital_tourism_resident_card"
DIGITAL_SOURCE_NAME = "디지털관광주민증"
DIGITAL_SOURCE_URL = "https://korean.visitkorea.or.kr/dgtourcard/"
HAENAM_REGIONAL_URL = (
    "https://korean.visitkorea.or.kr/dgtourcard/biz/regn/regnMain.do?"
    "mtpcDoCd=12&signguCd=12790"
)
FORBIDDEN_HALF_TRIP_HAENAM_URL = "https://www.haenam50.kr/index"

POLICY_IDENTITY_SQL = f"""
WITH known_dgtour(slug, region_name, city_name, display_title, source_canonical_key) AS (
  VALUES
    ('dgtour-밀양-1', '경남', '밀양', '[밀양] 디지털관광주민증 혜택', 'digital-tourism-resident-card:경남:밀양'),
    ('dgtour-평창-2', '강원', '평창', '[평창] 디지털관광주민증 혜택', 'digital-tourism-resident-card:강원:평창'),
    ('dgtour-하동-3', '경남', '하동', '[하동] 디지털관광주민증 혜택', 'digital-tourism-resident-card:경남:하동'),
    ('dgtour-거창-4', '경남', '거창', '[거창] 디지털관광주민증 혜택', 'digital-tourism-resident-card:경남:거창'),
    ('dgtour-영월-5', '강원', '영월', '[영월] 디지털관광주민증 혜택', 'digital-tourism-resident-card:강원:영월'),
    ('dgtour-제천-6', '충북', '제천', '[제천] 디지털관광주민증 혜택', 'digital-tourism-resident-card:충북:제천'),
    ('dgtour-강진-7', '전남', '강진', '[강진] 디지털관광주민증 혜택', 'digital-tourism-resident-card:전남:강진'),
    ('dgtour-영광-8', '전남', '영광', '[영광] 디지털관광주민증 혜택', 'digital-tourism-resident-card:전남:영광'),
    ('dgtour-합천-9', '경남', '합천', '[합천] 디지털관광주민증 혜택', 'digital-tourism-resident-card:경남:합천'),
    ('dgtour-해남-10', '전남', '해남', '[해남] 디지털관광주민증 혜택', 'digital-tourism-resident-card:전남:해남'),
    ('dgtour-남해-11', '경남', '남해', '[남해] 디지털관광주민증 혜택', 'digital-tourism-resident-card:경남:남해'),
    ('dgtour-영암-12', '전남', '영암', '[영암] 디지털관광주민증 혜택', 'digital-tourism-resident-card:전남:영암'),
    ('dgtour-고흥-13', '전남', '고흥', '[고흥] 디지털관광주민증 혜택', 'digital-tourism-resident-card:전남:고흥'),
    ('dgtour-횡성-14', '강원', '횡성', '[횡성] 디지털관광주민증 혜택', 'digital-tourism-resident-card:강원:횡성'),
    ('dgtour-완도-15', '전남', '완도', '[완도] 디지털관광주민증 혜택', 'digital-tourism-resident-card:전남:완도'),
    ('dgtour-고창-16', '전북', '고창', '[고창] 디지털관광주민증 혜택', 'digital-tourism-resident-card:전북:고창')
),
matched AS (
  SELECT p.id, k.slug, k.region_name, k.display_title, k.source_canonical_key
  FROM policies p
  LEFT JOIN known_dgtour k ON k.slug = p.slug
  WHERE p.slug LIKE 'dgtour-%'
     OR p.title ILIKE '%디지털관광주민증%'
     OR p.title ILIKE '%디지털 관광주민증%'
)
UPDATE policies p
SET
  title = COALESCE(m.display_title, p.title),
  region = COALESCE(m.region_name, p.region),
  source_type = COALESCE(p.source_type, 'official_campaign'),
  source_name = '{DIGITAL_SOURCE_NAME}',
  source_category = '{DIGITAL_SOURCE_CATEGORY}',
  source_url = '{DIGITAL_SOURCE_URL}',
  source_canonical_key = COALESCE(m.source_canonical_key, p.source_canonical_key),
  official_url = CASE
    WHEN p.slug = 'dgtour-해남-10' THEN '{HAENAM_REGIONAL_URL}'
    WHEN p.official_url = '{FORBIDDEN_HALF_TRIP_HAENAM_URL}' THEN '{DIGITAL_SOURCE_URL}'
    WHEN p.official_url LIKE '{DIGITAL_SOURCE_URL}%' THEN p.official_url
    ELSE '{DIGITAL_SOURCE_URL}'
  END,
  apply_url = CASE
    WHEN p.apply_url = '{FORBIDDEN_HALF_TRIP_HAENAM_URL}' THEN NULL
    WHEN p.apply_url LIKE '{DIGITAL_SOURCE_URL}%' THEN p.apply_url
    ELSE NULL
  END,
  description = NULLIF(
    replace(
      replace(COALESCE(p.description, ''), '디지털관광주민증 또는 대한민국 반값여행', '디지털관광주민증'),
      '대한민국 반값여행',
      '디지털관광주민증'
    ),
    ''
  ),
  target_condition = NULLIF(
    replace(
      replace(COALESCE(p.target_condition, ''), '디지털관광주민증 발급 또는 지역별 신청 조건 확인', '디지털관광주민증 발급 및 제시'),
      '디지털관광주민증 또는 지역별 신청 확인',
      '디지털관광주민증 발급 및 제시'
    ),
    ''
  ),
  policy_comment = NULLIF(
    replace(
      replace(COALESCE(p.policy_comment, ''), '디지털관광주민증 또는 대한민국 반값여행', '디지털관광주민증'),
      '대한민국 반값여행',
      '디지털관광주민증'
    ),
    ''
  ),
  updated_at = now()
FROM matched m
WHERE p.id = m.id;
""".strip()

DOCUMENT_IDENTITY_SQL = f"""
UPDATE policy_documents d
SET document_name = '디지털관광주민증'
FROM policies p
WHERE d.policy_id = p.id
  AND p.source_category = '{DIGITAL_SOURCE_CATEGORY}'
  AND (p.slug LIKE 'dgtour-%' OR p.title ILIKE '%디지털관광주민증%')
  AND (
    d.document_name ILIKE '%반값여행%'
    OR d.document_name ILIKE '%지역별 신청%'
    OR d.document_name ILIKE '%디지털관광주민증%'
  );
""".strip()

EXTERNAL_RECORD_IDENTITY_SQL = f"""
UPDATE external_source_records r
SET
  source_name = '{DIGITAL_SOURCE_NAME}',
  source_category = '{DIGITAL_SOURCE_CATEGORY}',
  source_url = '{DIGITAL_SOURCE_URL}',
  title = CASE
    WHEN r.city IS NOT NULL AND r.city <> '' AND r.title NOT LIKE '[%' THEN '[' || regexp_replace(r.city, '(시|군|구)$', '') || '] 디지털관광주민증 혜택'
    ELSE replace(r.title, '디지털 관광주민증', '디지털관광주민증')
  END,
  benefit_value_text = COALESCE(r.benefit_value_text, '지역 제휴 혜택'),
  extracted_discount_percent = NULL,
  benefit_value_type = CASE WHEN r.benefit_value_type = 'refund' THEN 'unknown' ELSE r.benefit_value_type END,
  logical_key = CASE
    WHEN r.region IS NOT NULL AND r.city IS NOT NULL
      THEN 'digital-tourism-resident-card:'
        || EXTRACT(YEAR FROM COALESCE(r.end_date, r.start_date, r.last_fetched_at::date, DATE '2026-01-01'))::integer
        || ':' || r.region || ':' || regexp_replace(r.city, '(시|군|구)$', '')
    ELSE r.logical_key
  END,
  canonical_key_version = COALESCE(r.canonical_key_version, 'snapshot-v1'),
  detail_url = CASE
    WHEN r.city IN ('해남', '해남군') THEN '{HAENAM_REGIONAL_URL}'
    WHEN r.detail_url = '{FORBIDDEN_HALF_TRIP_HAENAM_URL}' THEN '{DIGITAL_SOURCE_URL}'
    WHEN r.detail_url LIKE '{DIGITAL_SOURCE_URL}%' THEN r.detail_url
    ELSE '{DIGITAL_SOURCE_URL}'
  END,
  updated_at = now()
WHERE r.source_category = 'local_half_trip'
  AND (r.source_url LIKE '%/dgtourcard/%' OR r.collected_page_url LIKE '%/dgtourcard/%')
  AND (
    r.title ILIKE '%디지털관광주민증%'
    OR r.title ILIKE '%디지털 관광주민증%'
    OR r.raw_list_text ILIKE '%디지털관광주민증%'
    OR r.raw_detail_text ILIKE '%디지털관광주민증%'
  )
  AND NOT (
    r.title ILIKE '%대한민국 반값여행%'
    OR r.raw_list_text ILIKE '%대한민국 반값여행%'
    OR r.raw_detail_text ILIKE '%대한민국 반값여행%'
  )
  AND NOT EXISTS (
    SELECT 1
    FROM external_source_records existing
    WHERE existing.source_name = '{DIGITAL_SOURCE_NAME}'
      AND existing.source_category = '{DIGITAL_SOURCE_CATEGORY}'
      AND existing.canonical_key = r.canonical_key
      AND existing.id <> r.id
  );
""".strip()

DOWNGRADE_GUARD_SQL = """
DO $$
BEGIN
  RAISE NOTICE '0031_digital_tourism_resident_card_identity downgrade is a guarded data no-op; source-family rollback is unsafe.';
END $$;
""".strip()

UPGRADE_SQL = [POLICY_IDENTITY_SQL, DOCUMENT_IDENTITY_SQL, EXTERNAL_RECORD_IDENTITY_SQL]


def upgrade() -> None:
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade() -> None:
    op.execute(DOWNGRADE_GUARD_SQL)
