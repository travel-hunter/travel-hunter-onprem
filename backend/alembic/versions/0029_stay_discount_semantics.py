"""correct stay-discount campaign semantic classification

Revision ID: 0029_stay_discount_semantics
Revises: 0027_source_provenance_keys
Create Date: 2026-07-16

The desired JSON values are frozen here deliberately.  Runtime mapping code is not
imported by a migration.  Downgrade only verifies the exact corrected state and is
a data no-op; exact rollback requires the restricted pre-0029 snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence
import json

from alembic import op


revision: str = "0029_stay_discount_semantics"
down_revision: str | None = "0027_source_provenance_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_NAME = "대한민국 숙박세일 페스타"
SOURCE_CATEGORY = "stay_discount"
LOGICAL_KEY = "stay-discount:2026-summer"
KEY_VERSION = "snapshot-v1"
SOURCE_33_KEY = "c6f2eb4e3807ec83df2c95fbed2de11c"
SOURCE_35_KEY = "b91482f3261cef2deda9641746478d31"
OFFICIAL_URL = "https://ktostay.visitkorea.or.kr/"

_TIERS = [
    "7만원 미만* 국내 숙박상품 예약 시 2만원 할인 (1박 이상",
    "7만원 이상 국내 숙박상품 예약 시 3만원 할인 (1박 이상",
    "14만원 미만** 국내 숙박상품 예약 시 5만원 할인 (연박 이상",
    "14만원 이상 국내 숙박상품 예약 시 7만원 할인 (연박 이상",
]
_USAGE_AREA = "비수도권 인구감소지역 (85개 지자체)"
_USAGE_PLACE = (
    "사용처 국내숙박 업소 * 관광진흥법, 공중위생관리법 등에 등록된 숙박업소 * 대실 사용 불가"
)
_USAGE_METHOD = (
    "참여 온라인 여행사를 통한 숙박 할인권 발급 후 사용 * 1인 1매 사용(선착순) "
    "* 위 사업기간은 정부정책의 긴급 변동사항에 따라 변동될 수 있음"
)


def _desired(*, end_date: str, issue_period: str, stay_period: str) -> dict[str, object]:
    return {
        "supportContent": [
            {"title": "할인 혜택", "description": "7만원 미만 국내 숙박상품 예약 시 2만원 할인"},
            {"title": "할인 혜택", "description": "7만원 이상 국내 숙박상품 예약 시 3만원 할인"},
            {"title": "할인 혜택", "description": "14만원 미만 국내 숙박상품 예약 시 5만원 할인"},
            {"title": "할인 혜택", "description": "14만원 이상 국내 숙박상품 예약 시 7만원 할인"},
        ],
        "applicationTarget": [
            {"title": "신청대상", "description": "숙박세일페스타 대상 지역 숙박 이용자"},
            {"title": "신청대상", "description": "참여 온라인 여행사를 통해 국내 숙박상품을 예약하는 사용자"},
            {"title": "신청대상", "description": "할인권 발급 후 지정 기간 내 입실 가능한 사용자"},
        ],
        "periods": [
            {
                "title": "쿠폰 발급 기간",
                "description": issue_period,
                "type": "application",
                "startDate": "2026-06-11",
                "endDate": end_date,
            },
            {
                "title": "입실 기간",
                "description": stay_period,
                "type": "usage",
                "startDate": "2026-06-11",
                "endDate": end_date,
            },
        ],
        "requiredDocuments": [
            {
                "title": "필요서류",
                "description": "별도 제출 서류 없음 · 온라인 할인권 발급 및 예약 기준으로 적용",
            }
        ],
        "notes": [
            {"title": "비고", "description": "할인권은 선착순으로 발급됩니다."},
            {"title": "비고", "description": "예산 소진 시 조기 종료될 수 있습니다."},
            {"title": "비고", "description": "세부 기준은 공식 안내에서 최종 확인하세요."},
        ],
    }


SOURCE_33_ISSUE_PERIOD = (
    "2026.6.11 (목) ~7.31 (금) * 매일 오전 10시부터 선착순 발급 "
    "(단, 기한 내 소진 시 발급 불가)"
)
SOURCE_33_STAY_PERIOD = "2026. 6.11 (목) ~7.31 (금)"
SOURCE_35_ISSUE_PERIOD = (
    "2026.6.11 (목) ~8.17 (월) * 매일 오전 10시부터 선착순 발급 "
    "(단, 기한 내 소진 시 발급 불가)"
)
SOURCE_35_STAY_PERIOD = "2026. 6.11 (목) ~8.17 (월)"
_POLLUTED_PREFIX = (
    "할인혜택: 7만원 미만* 국내 숙박상품 예약 시 2만원 할인 (1박 이상 / "
    "7만원 이상 국내 숙박상품 예약 시 3만원 할인 (1박 이상 / "
    "14만원 미만** 국내 숙박상품 예약 시 5만원 할인 (연박 이상 / "
    "14만원 이상 국내 숙박상품 예약 시 7만원 할인 (연박 이상"
)
POLLUTED_SOURCE_33_CONTACT = (
    f"{_POLLUTED_PREFIX}\n발급기간: 2026.6.11 (목) ~7.31 (금) * 매일 오전 10시부터 선착…"
)
POLLUTED_SOURCE_35_CONTACT = (
    f"{_POLLUTED_PREFIX}\n발급기간: 2026.6.11 (목) ~8.17 (월) * 매일 오전 10시부터 선착…"
)
POLLUTED_POLICY_33_TARGET = POLLUTED_SOURCE_33_CONTACT.replace("\n", " ")
POLLUTED_POLICY_35_TARGET = POLLUTED_SOURCE_35_CONTACT.replace("\n", " ")

DESIRED_33 = _desired(
    end_date="2026-07-31",
    issue_period=SOURCE_33_ISSUE_PERIOD,
    stay_period=SOURCE_33_STAY_PERIOD,
)
DESIRED_35 = _desired(
    end_date="2026-08-17",
    issue_period=SOURCE_35_ISSUE_PERIOD,
    stay_period=SOURCE_35_STAY_PERIOD,
)


def _polluted(*, end_date: str, issue_period: str, stay_period: str) -> dict[str, object]:
    return {
        "supportContent": [
            {"title": "혜택", "amount": "2/3/5/7만원 할인권", "description": "2/3/5/7만원 할인권"}
        ],
        "applicationTarget": [],
        "periods": [
            {
                "title": "쿠폰 발급기간",
                "description": issue_period,
                "type": "issue",
                "startDate": "2026-06-11",
                "endDate": end_date,
            },
            {
                "title": "입실기간",
                "description": stay_period,
                "type": "usage",
                "startDate": "2026-06-11",
                "endDate": end_date,
            },
        ],
        "requiredDocuments": [],
        "notes": [
            {
                "title": "비고",
                "description": (
                    "7만원 미만* 국내 숙박상품 예약 시 2만원 할인 (1박 이상 / "
                    "7만원 이상 국내 숙박상품 예약 시 3만원 할인 (1박 이상 / "
                    "14만원 미만** 국내 숙박상품 예약 시 5만원 할인 (연박 이상 / "
                    "14만원 이상 국내 숙박상품 예약 시 7만원 할인 (연박 이상"
                ),
            },
            {"title": "비고", "description": "예산 소진 시 조기 종료"},
        ],
    }


POLLUTED_33 = _polluted(
    end_date="2026-07-31",
    issue_period=SOURCE_33_ISSUE_PERIOD,
    stay_period=SOURCE_33_STAY_PERIOD,
)
POLLUTED_35 = _polluted(
    end_date="2026-08-17",
    issue_period=SOURCE_35_ISSUE_PERIOD,
    stay_period=SOURCE_35_STAY_PERIOD,
)


def _legacy_old_detail(*, end_date: str, issue_period: str, stay_period: str) -> dict[str, object]:
    return {
        "benefits": [
            {"title": "혜택", "amount": "2/3/5/7만원 할인권", "description": "2/3/5/7만원 할인권"}
        ],
        "conditions": [],
        "periods": [
            {
                "title": "쿠폰 발급기간",
                "description": issue_period,
                "type": "issue",
                "startDate": "2026-06-11",
                "endDate": end_date,
            },
            {
                "title": "입실기간",
                "description": stay_period,
                "type": "usage",
                "startDate": "2026-06-11",
                "endDate": end_date,
            },
        ],
        "documents": [],
        "notices": [
            {
                "title": "확인 필요 사항",
                "description": (
                    "7만원 미만* 국내 숙박상품 예약 시 2만원 할인 (1박 이상 / "
                    "7만원 이상 국내 숙박상품 예약 시 3만원 할인 (1박 이상 / "
                    "14만원 미만** 국내 숙박상품 예약 시 5만원 할인 (연박 이상 / "
                    "14만원 이상 국내 숙박상품 예약 시 7만원 할인 (연박 이상"
                ),
            },
            {"title": "확인 필요 사항", "description": "예산 소진 시 조기 종료"},
        ],
        "links": [{"label": "공식 안내", "url": OFFICIAL_URL}],
    }


LEGACY_OLD_33 = _legacy_old_detail(
    end_date="2026-07-31",
    issue_period=SOURCE_33_ISSUE_PERIOD,
    stay_period=SOURCE_33_STAY_PERIOD,
)
LEGACY_OLD_35 = _legacy_old_detail(
    end_date="2026-08-17",
    issue_period=SOURCE_35_ISSUE_PERIOD,
    stay_period=SOURCE_35_STAY_PERIOD,
)


def _server_legacy_detail(*, end_date: str) -> dict[str, object]:
    """Legacy shape observed on the onprem dev DB before 0029 was deployed."""

    return {
        "benefits": [
            {"title": "혜택", "amount": "2/3/5/7만원 할인권", "description": "2/3/5/7만원 할인권"}
        ],
        "conditions": [],
        "documents": [],
        "links": [{"label": "공식 안내", "url": OFFICIAL_URL}],
        "notices": [
            {
                "title": "확인 필요 사항",
                "description": (
                    "7만원 미만* 국내 숙박상품 예약 시 2만원 할인 (1박 이상 / "
                    "7만원 이상 국내 숙박상품 예약 시 3만원 할인 (1박 이상 / "
                    "14만원 미만** 국내 숙박상품 예약 시 5만원 할인 (연박 이상 / "
                    "14만원 이상 국내 숙박상품 예약 시 7만원 할인 (연박 이상"
                ),
            }
        ],
        "periods": [
            {
                "title": "신청 기간",
                "description": f"2026-06-11 ~ {end_date}",
                "startDate": "2026-06-11",
                "endDate": end_date,
            }
        ],
    }


SERVER_LEGACY_33 = _server_legacy_detail(end_date="2026-07-31")
SERVER_LEGACY_35 = _server_legacy_detail(end_date="2026-08-17")


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_sql(value: object, tag: str) -> str:
    return f"${tag}${_json(value)}${tag}$::jsonb"


_TIERS_SQL = _json_sql(_TIERS, "tiers")
_DESIRED_33_SQL = _json_sql(DESIRED_33, "desired33")
_DESIRED_35_SQL = _json_sql(DESIRED_35, "desired35")
_POLLUTED_33_SQL = _json_sql(POLLUTED_33, "polluted33")
_POLLUTED_35_SQL = _json_sql(POLLUTED_35, "polluted35")
_LEGACY_OLD_33_SQL = _json_sql(LEGACY_OLD_33, "legacyOld33")
_LEGACY_OLD_35_SQL = _json_sql(LEGACY_OLD_35, "legacyOld35")
_SERVER_LEGACY_33_SQL = _json_sql(SERVER_LEGACY_33, "serverLegacy33")
_SERVER_LEGACY_35_SQL = _json_sql(SERVER_LEGACY_35, "serverLegacy35")


def _raw_guard(source_id: int, issue_period: str, stay_period: str) -> str:
    return f"""
      AND raw_payload->'discountTiers' = {_TIERS_SQL}
      AND raw_payload->>'issuePeriod' = '{issue_period}'
      AND raw_payload->>'stayPeriod' = '{stay_period}'
      AND raw_payload->>'usageArea' = '{_USAGE_AREA}'
      AND raw_payload->>'usagePlace' = '{_USAGE_PLACE}'
      AND raw_payload->>'usageMethod' = '{_USAGE_METHOD}'
      AND raw_payload->'earlyCloseWarning' = 'true'::jsonb
      AND detail_url = '{OFFICIAL_URL}'
      AND collected_page_url = '{OFFICIAL_URL}'
      AND source_url = '{OFFICIAL_URL}'
      AND id = {source_id}
    """.strip()


IDENTITY_AND_PRESTATE_GUARD_SQL = f"""
DO $$
DECLARE
  source_count integer;
  policy_count integer;
  single_state boolean;
  merged_state boolean;
  empty_state boolean;
BEGIN
  SELECT count(*) INTO source_count
  FROM external_source_records
  WHERE source_category='{SOURCE_CATEGORY}'
     OR logical_key='{LOGICAL_KEY}'
     OR id IN (33,35);
  SELECT count(*) INTO policy_count
  FROM policies
  WHERE source_category='{SOURCE_CATEGORY}'
     OR external_source_record_id IN (33,35)
     OR id IN (23,26)
     OR slug IN ('travelmonth-33','travelmonth-35');

  SELECT (SELECT count(*) FROM policies)=0
     AND (SELECT count(*) FROM external_source_records)=0
  INTO empty_state;

  SELECT source_count=1 AND policy_count=1
    AND EXISTS (
      SELECT 1 FROM external_source_records
      WHERE id=33 AND source_name='{SOURCE_NAME}' AND source_category='{SOURCE_CATEGORY}'
        AND canonical_key='{SOURCE_33_KEY}' AND logical_key='{LOGICAL_KEY}'
        AND canonical_key_version='{KEY_VERSION}'
        {_raw_guard(33, SOURCE_33_ISSUE_PERIOD, SOURCE_33_STAY_PERIOD)}
        AND (contact_text IS NULL OR md5(contact_text)='3c3c044408c6ca36d43630fb90d02bbd')
    )
    AND EXISTS (
      SELECT 1 FROM policies
      WHERE id=23 AND slug='travelmonth-33' AND status='active'
        AND source_name='{SOURCE_NAME}' AND source_category='{SOURCE_CATEGORY}'
        AND external_source_record_id=33 AND source_canonical_key='{SOURCE_33_KEY}'
        AND official_url='{OFFICIAL_URL}' AND source_url='{OFFICIAL_URL}'
        AND (target_condition IS NULL OR md5(target_condition)='a57ba6f2019c3935338fcf6261e44516')
        AND (structured_detail={_POLLUTED_33_SQL} OR structured_detail={_LEGACY_OLD_33_SQL} OR structured_detail={_SERVER_LEGACY_33_SQL} OR structured_detail={_DESIRED_33_SQL})
    )
  INTO single_state;

  SELECT source_count=2 AND policy_count=2
    AND EXISTS (
      SELECT 1 FROM external_source_records
      WHERE id=33 AND source_name='{SOURCE_NAME}' AND source_category='{SOURCE_CATEGORY}'
        AND canonical_key='{SOURCE_33_KEY}' AND logical_key='{LOGICAL_KEY}'
        AND canonical_key_version='{KEY_VERSION}'
        {_raw_guard(33, SOURCE_33_ISSUE_PERIOD, SOURCE_33_STAY_PERIOD)}
        AND (contact_text IS NULL OR md5(contact_text)='3c3c044408c6ca36d43630fb90d02bbd')
    )
    AND EXISTS (
      SELECT 1 FROM external_source_records
      WHERE id=35 AND source_name='{SOURCE_NAME}' AND source_category='{SOURCE_CATEGORY}'
        AND canonical_key='{SOURCE_35_KEY}' AND logical_key='{LOGICAL_KEY}'
        AND canonical_key_version='{KEY_VERSION}'
        {_raw_guard(35, SOURCE_35_ISSUE_PERIOD, SOURCE_35_STAY_PERIOD)}
        AND (contact_text IS NULL OR md5(contact_text)='370a58b0bf74540219081ee32e4f16e0')
    )
    AND EXISTS (
      SELECT 1 FROM policies
      WHERE id=23 AND slug='travelmonth-33' AND status='active'
        AND source_name='{SOURCE_NAME}' AND source_category='{SOURCE_CATEGORY}'
        AND external_source_record_id=35 AND source_canonical_key='{SOURCE_35_KEY}'
        AND official_url='{OFFICIAL_URL}' AND source_url='{OFFICIAL_URL}'
        AND (target_condition IS NULL OR md5(target_condition)='6151a9bb9de8a357a1a595803930aedf')
        AND (structured_detail={_POLLUTED_35_SQL} OR structured_detail={_LEGACY_OLD_35_SQL} OR structured_detail={_SERVER_LEGACY_35_SQL} OR structured_detail={_DESIRED_35_SQL})
    )
    AND EXISTS (
      SELECT 1 FROM policies
      WHERE id=26 AND slug='travelmonth-35' AND status='hidden'
        AND source_name='{SOURCE_NAME}' AND source_category='{SOURCE_CATEGORY}'
        AND external_source_record_id IS NULL AND source_canonical_key='{SOURCE_35_KEY}'
        AND official_url='{OFFICIAL_URL}' AND source_url='{OFFICIAL_URL}'
        AND (target_condition IS NULL OR md5(target_condition)='6151a9bb9de8a357a1a595803930aedf')
        AND (structured_detail={_POLLUTED_35_SQL} OR structured_detail={_LEGACY_OLD_35_SQL} OR structured_detail={_SERVER_LEGACY_35_SQL} OR structured_detail={_DESIRED_35_SQL})
    )
  INTO merged_state;

  IF NOT empty_state AND NOT single_state AND NOT merged_state THEN
    RAISE EXCEPTION '0029 stay-discount identity/raw/semantic prestate mismatch';
  END IF;
END $$
""".strip()

MUTATION_SQL: tuple[str, ...] = (
    f"""
    UPDATE external_source_records
    SET contact_text=NULL
    WHERE id IN (33,35)
      AND source_name='{SOURCE_NAME}'
      AND source_category='{SOURCE_CATEGORY}'
      AND logical_key='{LOGICAL_KEY}'
    """.strip(),
    f"""
    UPDATE policies
    SET target_condition=NULL,
        structured_detail=CASE
          WHEN EXISTS (SELECT 1 FROM external_source_records WHERE id=35)
            THEN {_DESIRED_35_SQL}
          ELSE {_DESIRED_33_SQL}
        END
    WHERE id IN (23,26)
      AND source_name='{SOURCE_NAME}'
      AND source_category='{SOURCE_CATEGORY}'
    """.strip(),
)

POSTCONDITION_SQL = f"""
DO $$
DECLARE source_count integer; policy_count integer;
BEGIN
  SELECT count(*) INTO source_count FROM external_source_records
  WHERE source_category='{SOURCE_CATEGORY}' OR logical_key='{LOGICAL_KEY}' OR id IN (33,35);
  SELECT count(*) INTO policy_count FROM policies
  WHERE source_category='{SOURCE_CATEGORY}' OR external_source_record_id IN (33,35)
     OR id IN (23,26) OR slug IN ('travelmonth-33','travelmonth-35');
  IF NOT ((SELECT count(*) FROM policies)=0 AND (SELECT count(*) FROM external_source_records)=0)
     AND NOT (
       (source_count=1 AND policy_count=1
        AND (SELECT contact_text IS NULL FROM external_source_records WHERE id=33)
        AND EXISTS (SELECT 1 FROM policies WHERE id=23 AND target_condition IS NULL
                    AND structured_detail={_DESIRED_33_SQL}))
       OR
       (source_count=2 AND policy_count=2
        AND (SELECT count(*) FROM external_source_records WHERE id IN (33,35) AND contact_text IS NULL)=2
        AND (SELECT count(*) FROM policies WHERE id IN (23,26) AND target_condition IS NULL
             AND structured_detail={_DESIRED_35_SQL})=2)
     ) THEN
    RAISE EXCEPTION '0029 stay-discount postcondition mismatch';
  END IF;
END $$
""".strip()

UPGRADE_SQL = (IDENTITY_AND_PRESTATE_GUARD_SQL, *MUTATION_SQL, POSTCONDITION_SQL)
DOWNGRADE_GUARD_SQL = POSTCONDITION_SQL.replace(
    "0029 stay-discount postcondition mismatch",
    "0029 downgrade requires exact corrected semantic state",
)


def upgrade() -> None:
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade() -> None:
    op.execute(DOWNGRADE_GUARD_SQL)
