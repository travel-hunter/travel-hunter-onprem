# CHECKLIST

## Current status

- Active task/status: 숙박세일페스타 정책 저장구조를 지역별 실제 `policies` row 기준으로 전환했고, dev 서버에 반영했다.
- Scope guard: 변경 범위는 stay_discount 정책 정규화, 정책/일정 연결 API, 링크 보정 스크립트, 관련 계약/DB 문서로 제한한다.

## Recent validation

- PASS: RED 확인 — `python -m pytest tests/test_policy_normalization.py::test_policies_external_source_record_id_is_not_unique -q` failed before schema model change.
- PASS: RED 확인 — `python -m pytest tests/test_policy_normalization.py::test_promotes_active_fresh_stay_discount_as_area_policy_rows -q` failed before stay_discount area row normalization.
- PASS: `cd backend && python -m pytest tests/test_policy_normalization.py -q` — 44 passed.
- PASS: `cd backend && python -m pytest tests/test_policy_db_service.py -q` — 46 passed.
- PASS: `cd backend && python -m pytest tests/test_trip_db_service.py -q` — 84 passed.
- PASS: `cd backend && python -m pytest tests/test_stay_discount_area_link_migration.py -q` — 1 passed.
- PASS: `cd backend && python -m pytest tests/test_db_schema.py -q` — 4 passed.
- PASS: `cd backend && python -m pytest tests/test_policy_normalization.py tests/test_policy_db_service.py tests/test_trip_db_service.py tests/test_stay_discount_area_link_migration.py -q` — 176 passed.
- PASS: `cd backend && python -m pytest` — 662 passed, 17 skipped.
- PASS: `cd backend && alembic upgrade head --sql` output includes `0035_stay_policy_identity`, dropping the unique index and recreating `ix_policies_external_source_record_id` as non-unique.
- PASS: dev 서버 `/home/deploy/travel-hunter-onprem` `develop@d5c091d` 배포, backend/frontend 이미지 rebuild, backend health `healthy`.
- PASS: dev DB Alembic head `0035_stay_policy_identity`, `ix_policies_external_source_record_id` non-unique 확인.
- PASS: dev 보정 스크립트 재실행 결과 `trip_links_moved=0`, `missing_area_targets=0`; canonical stay_discount trip link count `0`.
- PASS: dev `/trips/27` linked policy는 `stay-discount-gangwon-jeongseon` 1건, `/trips/13` linked policy는 `stay-discount-gyeongnam-geochang` 1건으로 확인.
- PASS: `curl -fsS https://dev.travel-hunter.co.kr/api/health`; `curl -fsS -I https://dev.travel-hunter.co.kr/trips/27`; `curl -fsS -I https://dev.travel-hunter.co.kr/trips/13`; `curl -fsS -I https://dev.travel-hunter.co.kr/policies/stay-discount-jeonnam-gangjin`.
- PASS: `git diff --check`.
- PASS: UTF-8/U+FFFD check for changed and untracked files — 19 files OK.

## Active risks

- Frontend typecheck/build was not rerun because no frontend source changed.
- Canonical trip/user link 보정은 원래 요청 alias slug를 별도 보존하지 않고, 일정 문맥에 가장 맞는 지역 정책 row를 선택한다.
- Alembic revision ID는 dev DB의 `alembic_version.version_num varchar(32)` 제한을 넘어가면 배포 중 실패하므로 32자 이하로 유지해야 한다.
- 중복 수집 canonical 숙박세일 source에 같은 source id의 지역 row가 없으면, 링크 보정 스크립트는 active 숙박세일 지역 row 전체에서 일정 문맥에 맞는 지역 정책을 고른다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
