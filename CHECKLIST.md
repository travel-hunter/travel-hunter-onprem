# CHECKLIST

## Current Status

- Active task/status: ktostay 공식 숙박세일페스타 발급기간/입실기간 변경을 로컬 코드와 테스트에 `2026.6.11~2026.8.31` 기준으로 반영했다.
- Scope guard: 변경 범위는 `stay_discount` 파서 fixture, semantic mapping fixture, 정책 상세 service fixture, 최신 snapshot 선택 회귀 테스트, 현재 검증 기록으로 제한한다.

## Recent Validation

- PASS: Baseline `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest tests/test_travelmonth_stay_parser.py -q` — 5 passed before edits.
- PASS: RED 확인 — ktostay fixture가 `7.31`인 상태에서 `8.31` 기대값을 넣자 `test_travelmonth_stay_parser.py` 2개 테스트가 expected end date mismatch로 실패했다.
- PASS: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest tests/test_travelmonth_stay_parser.py -q` — 5 passed after ktostay fixture update.
- PASS: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest tests/test_policy_normalization.py -k stay -q` — 9 passed.
- PASS: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest tests/test_policy_semantic_mapping.py tests/test_policy_db_service.py -k "stay_discount or ktostay" -q` — 10 passed after current period fixture updates.
- PASS: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest tests/test_travelmonth_stay_parser.py tests/test_policy_semantic_mapping.py tests/test_policy_normalization.py tests/test_policy_db_service.py -q` — 136 passed.
- PASS: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest -k "stay_discount or travelmonth_stay or external_collection" -q` — 64 passed, 10 skipped.
- PASS: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest tests/test_external_benefit_collection.py tests/test_ops_routes.py -q` — 18 passed.
- PASS: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest -q` — 662 passed, 17 skipped.
- PASS: `git diff --check`.
- PASS: UTF-8/U+FFFD scan for `.py`, `.md`, `.json`, `.tsx`, `.ts`, `.css` files.

## Active Risks

- dev 서버 live collection and normalization refresh have not been run in this branch.
- `backend/tests/test_stay_discount_semantics_migration.py` and `backend/tests/test_stay_discount_semantics_snapshot.py` intentionally keep historical `7.31`/`8.17` frozen prestate examples.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
