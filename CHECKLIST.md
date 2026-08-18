# CHECKLIST

## Current status

- Active task/status: 숙박세일페스타 정책 저장구조를 지역별 실제 `policies` row 기준으로 전환했고, dev DB 배포 중 발견된 Alembic revision 길이 제한을 보정했다.
- Scope guard: 변경 범위는 stay_discount 정책 정규화, 정책/일정 연결 API, 링크 보정 스크립트, 관련 계약/DB 문서로 제한한다.

## Recent validation

- PASS: RED 확인 — `python -m pytest tests/test_policy_normalization.py::test_policies_external_source_record_id_is_not_unique -q` failed before schema model change.
- PASS: RED 확인 — `python -m pytest tests/test_policy_normalization.py::test_promotes_active_fresh_stay_discount_as_area_policy_rows -q` failed before stay_discount area row normalization.
- PASS: `cd backend && python -m pytest tests/test_policy_normalization.py -q` — 44 passed.
- PASS: `cd backend && python -m pytest tests/test_policy_db_service.py -q` — 46 passed.
- PASS: `cd backend && python -m pytest tests/test_trip_db_service.py -q` — 84 passed.
- PASS: `cd backend && python -m pytest tests/test_stay_discount_area_link_migration.py -q` — 1 passed.
- PASS: `cd backend && python -m pytest tests/test_db_schema.py -q` — 4 passed.
- PASS: `cd backend && python -m pytest tests/test_policy_normalization.py tests/test_policy_db_service.py tests/test_trip_db_service.py tests/test_stay_discount_area_link_migration.py -q` — 175 passed.
- PASS: `cd backend && python -m pytest` — 661 passed, 17 skipped.
- PASS: `cd backend && alembic upgrade head --sql` output includes `0035_stay_policy_identity`, dropping the unique index and recreating `ix_policies_external_source_record_id` as non-unique.
- PENDING: dev 서버 Alembic 적용, 숙박세일 지역 정책 정규화, trip policy 링크 보정 스크립트 실행.
- PASS: `git diff --check`.
- PASS: UTF-8/U+FFFD check for changed and untracked files — 19 files OK.

## Active risks

- Frontend typecheck/build was not rerun because no frontend source changed.
- Existing canonical trip/user links lose the original requested alias slug in DB; the migration script picks the best matching area policy from trip context, otherwise the first area row.
- Alembic revision ID는 dev DB의 `alembic_version.version_num varchar(32)` 제한을 넘어가면 배포 중 실패하므로 32자 이하로 유지해야 한다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
