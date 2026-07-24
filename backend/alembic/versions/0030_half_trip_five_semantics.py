"""correct scoped local half-trip policy semantics

Revision ID: 0030_half_trip_five_semantics
Revises: 0029_stay_discount_semantics
Create Date: 2026-07-16

This data migration is intentionally scoped to the five KTO-backed
travelmonth local_half_trip policies reviewed in
backend/app/data/policy_corrections/local_half_trip_five_20260716.json.
It updates display semantics and conservative visibility only; policy identity,
slugs, external_source_record_id, and saved/trip relations are not mutated.
Downgrade is a guarded data no-op because exact rollback requires the restricted
pre-migration data snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence
import json

from alembic import op


revision: str = "0030_half_trip_five_semantics"
down_revision: str | None = "0029_stay_discount_semantics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_CATEGORY = "local_half_trip"
SCOPED_RECORDS = [{'slug': 'travelmonth-20',
  'external_source_record_id': 20,
  'status': 'active',
  'verification_status': 'fresh',
  'target_condition': '거창을 여행하고 싶은 타지역 거주 관광객으로, 관내 당일 또는 숙박 관광 일정을 사전 신청하여 승인받은 사람.\n'
                      '거창군, 김천시, 함양군, 산청군, 합천군, 무주군 거주자는 제외한다.',
  'structured_detail': {'supportContent': [{'title': '지원내용',
                                            'description': '거창 여행 중 사용한 경비의 50%를 모바일 거창반값여행 정책발행용 '
                                                           '상품권으로 지급한다.'},
                                           {'title': '지원내용',
                                            'description': '최소 소비금액은 10만원이며 개인 최대 10만원, 2인 이상 팀 최대 '
                                                           '20만원, 가족 최대 50만원, 청년 개인 최대 14만원 한도를 '
                                                           '적용한다.'}],
                        'periods': [{'title': '사전신청 기간',
                                     'description': '전체 사전신청 기간. 4차는 2026-07-10 10:00부터 접수 중이며 예산 '
                                                    '소진 시 조기 마감될 수 있다.',
                                     'type': 'application',
                                     'startDate': '2026-04-13',
                                     'endDate': '2026-08-30'},
                                    {'title': '여행 기간',
                                     'description': '전체 거창 여행 기간. 4차 여행기간은 '
                                                    '2026-07-14~2026-08-31이다.',
                                     'type': 'travel',
                                     'startDate': '2026-04-14',
                                     'endDate': '2026-08-31'}],
                        'applicationTarget': [{'title': '신청대상',
                                               'description': '거창을 여행하고 싶은 타지역 거주 관광객으로, 관내 당일 또는 '
                                                              '숙박 관광 일정을 사전 신청하여 승인받은 사람.'},
                                              {'title': '신청대상',
                                               'description': '거창군, 김천시, 함양군, 산청군, 합천군, 무주군 거주자는 '
                                                              '제외한다.'}],
                        'requiredDocuments': [{'title': '필요서류',
                                               'description': '지정 관광지 2개소 이상 방문 인증 사진.'},
                                              {'title': '필요서류',
                                               'description': '거창군 관내 제로페이 가맹점 2개소 이상에서 정책발행용 상품권을 '
                                                              '사용한 영수증.'},
                                              {'title': '필요서류',
                                               'description': '숙박은 예외적으로 신용카드 또는 현금영수증을 인정하며 '
                                                              '숙박영수증, 숙박예약 또는 이용완료 내역 캡처본, 숙박업소 이용 '
                                                              '확인서가 필요하다.'}],
                        'notes': [{'title': '비고',
                                   'description': '선착순 마감 기준은 사전 신청 순이 아니라 경비 신청 순이며, 환급 예산 소진 시 '
                                                  '마감된다.'},
                                  {'title': '비고',
                                   'description': '거창반값여행 재방문 관광객 특별이벤트는 별도 안내 확인 대상으로 둔다.'}]}},
 {'slug': 'travelmonth-24',
  'external_source_record_id': 24,
  'status': 'active',
  'verification_status': 'fresh',
  'target_condition': '영광 관외 거주 사전신청 관광객 누구나.\n함평군, 장성군, 무안군, 고창군 거주자는 제외한다.',
  'structured_detail': {'supportContent': [{'title': '지원내용',
                                            'description': '영광 여행 비용의 최대 50%를 모바일 영광사랑상품권으로 지급한다.'},
                                           {'title': '지원내용',
                                            'description': '최소 소비금액은 10만원이며 개인 최대 10만원, 청년 70% 최대 '
                                                           '14만원, 2인 이상 최대 20만원, 가족단체는 최대 5명까지 1인당 '
                                                           '최대 10만원 기준을 적용한다.'}],
                        'periods': [{'title': '4차 사전신청 시작',
                                     'description': 'KTO는 4차 신청접수를 2026-06-23 10:00부터로 표시한다. 세부 '
                                                    '안내는 여행 최소 1일 전 17:30까지 사전신청하라고 안내한다.',
                                     'type': 'application',
                                     'startDate': '2026-06-23'},
                                    {'title': '4차 여행 기간',
                                     'description': 'KTO가 표시한 4차 여행 기간. 세부 안내는 사전 신청 시 지정한 여행일자를 '
                                                    '기준으로 한다.',
                                     'type': 'travel',
                                     'startDate': '2026-07-01',
                                     'endDate': '2026-07-31'},
                                    {'title': '정산 신청 기간',
                                     'description': '영광 여행 후 다음 날부터 7일 이내 정산 신청한다.',
                                     'type': 'settlement'}],
                        'applicationTarget': [{'title': '신청대상',
                                               'description': '영광 관외 거주 사전신청 관광객 누구나.'},
                                              {'title': '신청대상',
                                               'description': '함평군, 장성군, 무안군, 고창군 거주자는 제외한다.'}],
                        'requiredDocuments': [{'title': '필요서류',
                                               'description': '사전신청 시 신분증 및 주민등록등본 등 영광 관외 거주 확인 '
                                                              '서류. 주민등록번호 뒷자리는 마스킹한다.'},
                                              {'title': '필요서류',
                                               'description': '정산 시 관광지 2개소 방문사진. 모든 참가자의 얼굴이 '
                                                              '확인되어야 한다.'},
                                              {'title': '필요서류',
                                               'description': '최소 10만원 이상 소비를 증빙하는 신청자 명의 카드 영수증, '
                                                              '신청자 휴대전화번호가 기재된 현금영수증, 또는 그리고 앱/카드 '
                                                              '거래 영수증.'}],
                        'notes': [{'title': '비고',
                                   'description': '법인카드, 타인 명의 카드 등 신청자 명의가 아닌 결제 증빙은 인정하지 않는 것으로 '
                                                  '정리한다.'},
                                  {'title': '비고',
                                   'description': '지원금은 그리고 앱으로 지급되며 영광사랑상품권 사용 기한은 2026-12-31까지로 '
                                                  '안내되어 있다.'},
                                  {'title': '비고',
                                   'description': '본인인증 게이트 뒤 신청 화면은 공개 스크래핑만으로 세부 입력 상태를 확인하지 '
                                                  '못했다.'}]}},
 {'slug': 'travelmonth-32',
  'external_source_record_id': 32,
  'status': 'hidden',
  'verification_status': 'needs_review',
  'target_condition': '고창 관외 지역에 거주하는 관광객 누구나.\n정읍시, 부안군, 장성군, 영광군 거주자는 제외한다.',
  'structured_detail': {'supportContent': [{'title': '지원내용',
                                            'description': '고창 여행 비용의 50%를 모바일 고창사랑상품권으로 지급한다.'},
                                           {'title': '지원내용',
                                            'description': '최소 소비금액은 10만원이며 개인 최대 10만원, 팀 최대 20만원, '
                                                           '가족 최대 50만원, 청년 70% 최대 14만원 한도를 안내한다.'}],
                        'periods': [{'title': '전체 여행 기간',
                                     'description': '고창 세부 URL이 표시한 전체 여행 기간이다.',
                                     'type': 'travel',
                                     'startDate': '2026-04-18',
                                     'endDate': '2026-08-31'},
                                    {'title': 'KTO 4차 신청 표시',
                                     'description': 'KTO는 4차 신청일을 2026-07-16으로 표시하지만 실행일 현재 상태는 '
                                                    '마감으로 표시한다. 고창 신청 페이지는 2026-07-16 10:00부터라는 '
                                                    '안내만 확인되고 현재 open 여부는 확정하지 못했다.',
                                     'type': 'application',
                                     'startDate': '2026-07-16'},
                                    {'title': 'KTO 4차 여행 기간',
                                     'description': 'KTO가 표시한 4차 여행 일정이다.',
                                     'type': 'travel',
                                     'startDate': '2026-07-20',
                                     'endDate': '2026-08-31'}],
                        'applicationTarget': [{'title': '신청대상',
                                               'description': '고창 관외 지역에 거주하는 관광객 누구나.'},
                                              {'title': '신청대상',
                                               'description': '정읍시, 부안군, 장성군, 영광군 거주자는 제외한다.'}],
                        'requiredDocuments': [{'title': '필요서류',
                                               'description': '사전신청 시 신분증 등 관외 거주 확인 서류. 가족 단위는 '
                                                              '주민등록등본 등 가족관계 확인 서류가 필요하다.'},
                                              {'title': '필요서류',
                                               'description': '정산 시 관광지 2개소 방문사진. 모든 팀원의 얼굴이 확인되어야 '
                                                              '한다.'},
                                              {'title': '필요서류',
                                               'description': '신청자 명의 개인 신용카드 영수증 또는 고창사랑카드 영수증.'},
                                              {'title': '필요서류',
                                               'description': '숙박 이용 시 숙박 플랫폼 이용완료 화면, 카드 결제영수증, '
                                                              '숙박업소 이용 확인서 등 숙박 완료 증빙.'}],
                        'notes': [{'title': '비고',
                                   'description': '간이영수증, 계좌이체, 현금영수증은 인정하지 않는 것으로 안내되어 있다.'},
                                  {'title': '비고',
                                   'description': '예산 소진 시 마감될 수 있으며 KTO 실행일 상태가 마감이므로 공개 노출 전 '
                                                  '재확인이 필요하다.'}]}},
 {'slug': 'travelmonth-21',
  'external_source_record_id': 21,
  'status': 'active',
  'verification_status': 'fresh',
  'target_condition': '영월 반값여행 사전신청 승인을 받은 관외 관광객.\n신청 유형에 따라 개인, 팀, 가족, 청년 유형을 구분한다.',
  'structured_detail': {'supportContent': [{'title': '지원내용',
                                            'description': '영월 여행 비용의 50%를 환급하며 청년 유형은 70%를 적용한다.'},
                                           {'title': '지원내용',
                                            'description': '최소 소비금액은 1인당 10만원이며 개인 최대 10만원, 2인 이상 '
                                                           '최대 20만원, 가족 최대 50만원, 청년 개인 최대 14만원 한도를 '
                                                           '안내한다.'}],
                        'periods': [{'title': '전체 사전신청 기간',
                                     'description': '2026-08-31 18시까지, 여행 최소 5일 전 신청해야 하며 선착순 조기 '
                                                    '마감될 수 있다.',
                                     'type': 'application',
                                     'startDate': '2026-04-07',
                                     'endDate': '2026-08-31'},
                                    {'title': '8월 여행 사전신청 오픈',
                                     'description': '2026-07-14 10:00부터 8월 여행 사전신청이 열린 것으로 공지·신청 '
                                                    '화면·KTO가 확인한다.',
                                     'type': 'application',
                                     'startDate': '2026-07-14'},
                                    {'title': '4차 여행 기간',
                                     'description': 'KTO와 영월 공지의 8월 여행 기간이다.',
                                     'type': 'travel',
                                     'startDate': '2026-08-01',
                                     'endDate': '2026-08-31'},
                                    {'title': '정산 신청 기간',
                                     'description': '여행 종료 후 15일 이내 정산 신청한다.',
                                     'type': 'settlement'}],
                        'applicationTarget': [{'title': '신청대상',
                                               'description': '영월 반값여행 사전신청 승인을 받은 관외 관광객.'},
                                              {'title': '신청대상',
                                               'description': '신청 유형에 따라 개인, 팀, 가족, 청년 유형을 구분한다.'}],
                        'requiredDocuments': [{'title': '필요서류',
                                               'description': '사전신청 시 주민등록증 등 신분증. 가족 유형은 가족관계증명서 '
                                                              '또는 주민등록등본 등 가족 확인 서류가 필요하다.'},
                                              {'title': '필요서류',
                                               'description': '숙박시설 입실 전·후 참가자 얼굴 확인 사진.'},
                                              {'title': '필요서류', 'description': '전통시장 방문 및 결제 증빙.'},
                                              {'title': '필요서류',
                                               'description': '숙박 카드 영수증, 여행경비 카드 영수증, 지역화폐 실물 '
                                                              '카드번호 등 정산 증빙.'}],
                        'notes': [{'title': '비고',
                                   'description': '숙박 필수 및 전통시장 방문 필수 조건을 notes/requiredDocuments로 '
                                                  '분리하고 신청대상에는 넣지 않는다.'},
                                  {'title': '비고',
                                   'description': '신청자명, 승인 여행기간, 증빙 명의가 일치해야 하며 온라인 숙박 카드 결제도 별도 '
                                                  '기준에 따라 인정된다.'}]}},
 {'slug': 'travelmonth-27',
  'external_source_record_id': 27,
  'status': 'active',
  'verification_status': 'fresh',
  'target_condition': '남해군, 사천시, 하동군 외 거주자 중 사전신청한 국민 누구나.\n연내 2회 참여 제한을 안내한다.',
  'structured_detail': {'supportContent': [{'title': '지원내용',
                                            'description': '국민쉼터 반반남해 여행비의 50%를 반반남해 전용상품권 등 안내 '
                                                           '기준에 따라 지원한다.'},
                                           {'title': '지원내용',
                                            'description': '개인 최대 10만원, 팀 최대 20만원, 가족 최대 50만원, 청년은 '
                                                           '70%로 개인 최대 14만원·팀 최대 28만원 한도를 안내한다.'},
                                           {'title': '지원내용',
                                            'description': '최소 소비금액 합산 10만원 이상 조건이 있다.'}],
                        'periods': [{'title': '3차 사전신청 시작',
                                     'description': '2026-07-20 10:00 시작. 실행일 2026-07-16에는 현재 '
                                                    '접수기간이 아니라고 표시된다.',
                                     'type': 'application',
                                     'startDate': '2026-07-20'},
                                    {'title': '3차 여행 기간',
                                     'description': '남해군 세부 URL과 KTO가 모두 확인한 3차 여행 기간이다.',
                                     'type': 'travel',
                                     'startDate': '2026-08-01',
                                     'endDate': '2026-08-31'}],
                        'applicationTarget': [{'title': '신청대상',
                                               'description': '남해군, 사천시, 하동군 외 거주자 중 사전신청한 국민 '
                                                              '누구나.'},
                                              {'title': '신청대상',
                                               'description': '연내 2회 참여 제한을 안내한다.'}],
                        'requiredDocuments': [{'title': '필요서류',
                                               'description': '가족 유형은 주민등록등본 등 가족관계 확인 서류. 주민등록번호 '
                                                              '뒷자리는 마스킹한다.'},
                                              {'title': '필요서류',
                                               'description': '지정 관광지 방문 인증 자료. 남해군 인증 관광지 목록을 별도 '
                                                              '페이지에서 확인한다.'},
                                              {'title': '필요서류',
                                               'description': '숙박소비 증빙: 숙박업체명, 이용일, 결제금액이 확인되는 '
                                                              '결제내역과 숙박 플랫폼 이용완료 화면 또는 날인된 숙박업소 '
                                                              '이용완료 확인서.'}],
                        'notes': [{'title': '비고',
                                   'description': '상품권 결제는 비플페이의 국민쉼터 반반남해 전용상품권을 기준으로 하며 일반 화전상품권 '
                                                  '또는 비플머니는 인정하지 않는다.'},
                                  {'title': '비고',
                                   'description': '숙박소비는 상품권, 신용카드, 숙박 플랫폼 결제를 인정하지만 계좌이체·현금 결제는 '
                                                  '인정하지 않는다.'},
                                  {'title': '비고',
                                   'description': '평일 운영 및 예산 소진 시 환급 불가 가능성을 안내한다.'}]}}]


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_sql(value: object, tag: str) -> str:
    return f"${tag}${_json(value)}${tag}$::jsonb"


def _text_sql(value: str | None, tag: str) -> str:
    if value is None:
        return "NULL"
    return f"${tag}${value}${tag}$"


def _slug_list() -> str:
    return ", ".join(f"'{record['slug']}'" for record in SCOPED_RECORDS)


def _identity_values() -> str:
    return ",\n      ".join(
        f"('{record['slug']}', {record['external_source_record_id']})"
        for record in SCOPED_RECORDS
    )


def _case_json(column: str) -> str:
    return "CASE slug\n" + "\n".join(
        f"        WHEN '{record['slug']}' THEN {_json_sql(record[column], 'json' + str(index))}"
        for index, record in enumerate(SCOPED_RECORDS)
    ) + "\n        ELSE structured_detail\n      END"


def _case_text(column: str) -> str:
    return "CASE slug\n" + "\n".join(
        f"        WHEN '{record['slug']}' THEN {_text_sql(record[column], column + str(index))}"
        for index, record in enumerate(SCOPED_RECORDS)
    ) + f"\n        ELSE {column}\n      END"


IDENTITY_GUARD_SQL = f"""
DO $$
DECLARE
  matched_count integer;
  relation_count_before integer;
  relation_count_after integer;
BEGIN
  SELECT count(*) INTO matched_count
  FROM policies p
  JOIN external_source_records e ON e.id = p.external_source_record_id
  JOIN (VALUES
      {_identity_values()}
  ) AS scoped(slug, external_source_record_id)
    ON scoped.slug = p.slug AND scoped.external_source_record_id = p.external_source_record_id
  WHERE p.source_category = '{SOURCE_CATEGORY}'
    AND e.source_category = '{SOURCE_CATEGORY}';

  IF matched_count = 0 THEN
    RETURN;
  ELSIF matched_count <> {len(SCOPED_RECORDS)} THEN
    RAISE EXCEPTION 'local half-trip five identity prestate mismatch: expected %, matched %', {len(SCOPED_RECORDS)}, matched_count;
  END IF;

  SELECT count(*) INTO relation_count_before
  FROM (
    SELECT policy_id FROM user_saved_policies WHERE policy_id IN (SELECT id FROM policies WHERE slug IN ({_slug_list()}))
    UNION ALL
    SELECT policy_id FROM trip_policies WHERE policy_id IN (SELECT id FROM policies WHERE slug IN ({_slug_list()}))
  ) relations;

  SELECT count(*) INTO relation_count_after
  FROM (
    SELECT policy_id FROM user_saved_policies WHERE policy_id IN (SELECT id FROM policies WHERE slug IN ({_slug_list()}))
    UNION ALL
    SELECT policy_id FROM trip_policies WHERE policy_id IN (SELECT id FROM policies WHERE slug IN ({_slug_list()}))
  ) relations;

  IF relation_count_before <> relation_count_after THEN
    RAISE EXCEPTION 'local half-trip relation count changed during guard';
  END IF;
END $$;
""".strip()

MUTATION_SQL = f"""
UPDATE policies
SET
  structured_detail = {_case_json('structured_detail')},
  target_condition = {_case_text('target_condition')},
  status = {_case_text('status')},
  verification_status = {_case_text('verification_status')},
  updated_at = NOW()
WHERE (slug, external_source_record_id) IN (
  {_identity_values()}
)
  AND source_category = '{SOURCE_CATEGORY}';
""".strip()

DOWNGRADE_GUARD_SQL = f"""
DO $$
DECLARE
  matched_count integer;
BEGIN
  SELECT count(*) INTO matched_count
  FROM policies p
  JOIN (VALUES
      {_identity_values()}
  ) AS scoped(slug, external_source_record_id)
    ON scoped.slug = p.slug AND scoped.external_source_record_id = p.external_source_record_id
  WHERE p.source_category = '{SOURCE_CATEGORY}';

  IF matched_count = 0 THEN
    RETURN;
  ELSIF matched_count <> {len(SCOPED_RECORDS)} THEN
    RAISE EXCEPTION 'local half-trip five downgrade guard mismatch: expected %, matched %', {len(SCOPED_RECORDS)}, matched_count;
  END IF;
END $$;
""".strip()

UPGRADE_SQL = [IDENTITY_GUARD_SQL, MUTATION_SQL]


def upgrade() -> None:
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade() -> None:
    op.execute(DOWNGRADE_GUARD_SQL)
