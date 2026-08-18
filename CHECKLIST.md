# CHECKLIST

## Current status

- Active task/status: 친구 초대 흐름을 editor-only로 정리했다. `/friend-invite`는 편집 링크 하나만 표시하고, 초대 생성/메일/수락 API도 editor 초대만 허용한다.
- Scope guard: 기존 `trip_members.role="viewer"` 멤버의 읽기 전용 권한은 유지한다. 새 viewer 초대 생성, 표시, 메일 발송, 토큰 수락만 비활성화했다.

## Recent validation

- PASS: `cd backend && .venv/bin/python -m pytest tests/test_trip_db_routes.py::test_db_recommendation_and_invite_routes tests/test_trip_db_service.py -k "invite" tests/test_invite_db_routes.py tests/test_trip_auth_edge_cases.py -q` — 24 passed, 75 deselected.
- PASS: `cd backend && .venv/bin/alembic upgrade head --sql`.
- PASS: `cd frontend && npm run typecheck`.
- PASS: `cd frontend && npx vitest run invite-oauth.test.tsx` — 22 passed.
- PASS: `cd frontend && npm run build`.
- PASS: `docker compose -f compose.yaml config`.
- PASS: `python3 -m json.tool .agent/evals/api-contract-golden.json`.
- PASS: `git diff --check`.
- PASS: UTF-8/U+FFFD check for changed Korean-bearing files.
- PASS: Mocked Playwright preview smokes confirmed one editor invite card, removed card helper copy, and title copy `여수·순천 3일 여행에 함께할 친구를 초대하세요`.
- BLOCKED: `cd backend && .venv/bin/python -m pytest -q` currently fails outside this change scope in `tests/test_local_half_trip_five_semantics_migration.py::test_frozen_migration_semantics_equal_runtime_mapper_for_scoped_records`.
- BLOCKED: `cd frontend && npm test -- invite-oauth.test.tsx --runInBand` is blocked by the local compose DB Alembic state: `Can't locate revision identified by '0034_dgtour_detail_urls'`.

## Active risks

- Legacy active viewer invite rows may remain in the database, but token lookup ignores non-editor invites so those URLs behave as missing or expired.
- The frontend `npm test` wrapper still needs the local compose DB migration state fixed before it can be used as a broad gate.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
