"""hide digital tourism policies outside official participating regions

Revision ID: 0033_dgtour_scope
Revises: 0032_dgtour_structured
Create Date: 2026-07-24

Digital tourism resident card policies are public only when their municipality
is present in the VisitKorea participating-region list verified on 2026-07-24.
Existing rows are hidden instead of deleted so saved policies, trip policy
links, and notification references keep referential integrity.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "0033_dgtour_scope"
down_revision: str | None = "0032_dgtour_structured"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIGITAL_SOURCE_CATEGORY = "digital_tourism_resident_card"

OFFICIAL_CITY_VALUES = """
    ('철원'), ('양양'), ('정선'), ('삼척'), ('태백'), ('홍천'), ('평창'), ('영월'),
    ('연천'), ('가평'), ('강화'), ('태안'), ('제천'), ('단양'), ('괴산'), ('예산'),
    ('옥천'), ('영동'), ('보령'), ('보은'), ('김제'), ('무주'), ('고창'), ('임실'),
    ('영광'), ('남원'), ('함평'), ('곡성'), ('신안'), ('해남'), ('장흥'), ('구례'),
    ('담양'), ('순창'), ('고흥'), ('완도'), ('영주'), ('안동'), ('영덕'), ('청도'),
    ('부산동구'), ('부산영도'), ('부산서구'), ('밀양'), ('하동'), ('합천'), ('거창'),
    ('고령'), ('의성'), ('울진'), ('함양'), ('산청')
""".strip()

POLICY_SCOPE_SQL = f"""
WITH official(city_name) AS (
  VALUES
    {OFFICIAL_CITY_VALUES}
),
scoped AS (
  SELECT
    p.id,
    COALESCE(
      NULLIF(substring(p.title from '\\[([^\\]]+)\\]'), ''),
      NULLIF((string_to_array(p.source_canonical_key, ':'))[array_length(string_to_array(p.source_canonical_key, ':'), 1)], ''),
      NULLIF(regexp_replace(COALESCE(p.slug, ''), '^dgtour-([^-]+)-.*$', '\\1'), COALESCE(p.slug, '')),
      ''
    ) AS raw_city
  FROM policies p
  WHERE p.source_category = '{DIGITAL_SOURCE_CATEGORY}'
     OR p.slug LIKE 'dgtour-%'
     OR p.title ILIKE '%디지털관광주민증%'
     OR p.title ILIKE '%디지털 관광주민증%'
),
normalized AS (
  SELECT
    id,
    CASE
      WHEN raw_city IN (SELECT city_name FROM official) THEN raw_city
      WHEN regexp_replace(raw_city, '(시|군|구)$', '') IN (SELECT city_name FROM official)
        THEN regexp_replace(raw_city, '(시|군|구)$', '')
      ELSE raw_city
    END AS city_name
  FROM scoped
)
UPDATE policies p
SET
  status = 'hidden',
  updated_at = now()
FROM normalized n
WHERE p.id = n.id
  AND n.city_name <> ''
  AND n.city_name NOT IN (SELECT city_name FROM official)
  AND p.status <> 'hidden';
""".strip()

EXTERNAL_RECORD_SCOPE_SQL = f"""
WITH official(city_name) AS (
  VALUES
    {OFFICIAL_CITY_VALUES}
),
scoped AS (
  SELECT
    r.id,
    COALESCE(
      NULLIF(r.city, ''),
      NULLIF(substring(r.title from '\\[([^\\]]+)\\]'), ''),
      NULLIF((string_to_array(r.logical_key, ':'))[array_length(string_to_array(r.logical_key, ':'), 1)], ''),
      ''
    ) AS raw_city
  FROM external_source_records r
  WHERE r.source_category = '{DIGITAL_SOURCE_CATEGORY}'
),
normalized AS (
  SELECT
    id,
    CASE
      WHEN raw_city IN (SELECT city_name FROM official) THEN raw_city
      WHEN regexp_replace(raw_city, '(시|군|구)$', '') IN (SELECT city_name FROM official)
        THEN regexp_replace(raw_city, '(시|군|구)$', '')
      ELSE raw_city
    END AS city_name
  FROM scoped
)
UPDATE external_source_records r
SET
  status = CASE WHEN r.status IN ('active', 'scheduled') THEN 'ended' ELSE r.status END,
  freshness_status = 'stale',
  updated_at = now()
FROM normalized n
WHERE r.id = n.id
  AND n.city_name <> ''
  AND n.city_name NOT IN (SELECT city_name FROM official)
  AND (
    r.status IN ('active', 'scheduled')
    OR r.freshness_status <> 'stale'
  );
""".strip()

DOWNGRADE_GUARD_SQL = """
DO $$
BEGIN
  RAISE NOTICE '0033_dgtour_scope downgrade is a guarded data no-op; restoring non-participant public digital tourism rows is unsafe.';
END $$;
""".strip()

UPGRADE_SQL = [POLICY_SCOPE_SQL, EXTERNAL_RECORD_SCOPE_SQL]


def upgrade() -> None:
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade() -> None:
    op.execute(DOWNGRADE_GUARD_SQL)
