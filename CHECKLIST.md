# CHECKLIST

## Current Status

- Active task/status: D-day 마감 배지 중복 표시 수정과 ktostay 공식 숙박세일페스타 발급기간/입실기간 `2026.6.11~2026.8.31` 변경을 개발서버 반영 후보 브랜치에 통합했다.
- Scope guard: 변경 범위는 프론트 정책 마감 배지 formatter/test, `stay_discount` 파서 fixture, semantic mapping fixture, 정책 상세 service fixture, 최신 snapshot 선택 회귀 테스트, 현재 검증 기록으로 제한한다.

## Recent Validation

- PASS: `cd frontend && npm ci` — dependencies installed for the integration worktree; npm reported 4 audit findings (2 moderate, 2 high).
- PASS: `cd frontend && npx vitest run src/utils.test.ts` — 1 passed for the D-day duplicate deadline regression.
- PASS: `cd frontend && npm run typecheck`.
- PASS: `cd frontend && npm run test:mojibake`.
- PASS: `cd frontend && npm run build`.
- PASS: Baseline `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest tests/test_travelmonth_stay_parser.py -q` — 5 passed before edits.
- PASS: RED 확인 — ktostay fixture가 `7.31`인 상태에서 `8.31` 기대값을 넣자 `test_travelmonth_stay_parser.py` 2개 테스트가 expected end date mismatch로 실패했다.
- PASS: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest tests/test_travelmonth_stay_parser.py -q` — 5 passed after ktostay fixture update.
- PASS: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest tests/test_policy_normalization.py -k stay -q` — 9 passed.
- PASS: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest tests/test_policy_semantic_mapping.py tests/test_policy_db_service.py -k "stay_discount or ktostay" -q` — 10 passed after current period fixture updates.
- PASS: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest tests/test_travelmonth_stay_parser.py tests/test_policy_semantic_mapping.py tests/test_policy_normalization.py tests/test_policy_db_service.py -q` — 136 passed.
- PASS: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest -k "stay_discount or travelmonth_stay or external_collection" -q` — 64 passed, 10 skipped.
- PASS: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest tests/test_external_benefit_collection.py tests/test_ops_routes.py -q` — 18 passed.
- PASS: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest -q` — 662 passed, 17 skipped.
- PASS: RED 확인 — D-day formatter 수정 전 `cd frontend && npx vitest run src/utils.test.ts` failed with expected `마감`, received `마감 마감`.
- PASS: `docker compose -f compose.yaml config`.
- FAIL: `cd frontend && npm test -- --run` — first run blocked by missing `node_modules`, then compose DB port `55432` was already allocated by the existing local stack; isolated compose resources were cleaned up.
- FAIL: `cd frontend && SKIP_E2E_DB_START=1 PYTHON=/home/hp/projects/travel-hunter-onprem/.venv/bin/python npm test` — 3 files failed / 7 tests failed after reusing the existing local DB. Failures are centered on seeded policy slug collisions such as expected `dgtour-영광` vs actual `dgtour-영광-8`, plus one trip-create flow blocked before the title field.
- PASS: `git diff --check`.
- PASS: UTF-8/U+FFFD scan for `.py`, `.md`, `.json`, `.tsx`, `.ts`, `.css` files.

## Active Risks

- dev 서버 live collection and normalization refresh have not been run in this branch.
- frontend full `npm test` is not green under the reused local DB state; rerun against a clean test DB before treating the branch as fully release-ready.
- `npm ci` reports 4 audit findings from existing frontend dependencies (2 moderate, 2 high).
- `backend/tests/test_stay_discount_semantics_migration.py` and `backend/tests/test_stay_discount_semantics_snapshot.py` intentionally keep historical `7.31`/`8.17` frozen prestate examples.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
