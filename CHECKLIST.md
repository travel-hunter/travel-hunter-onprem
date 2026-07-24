# CHECKLIST

## Current status

- Ready for review: selectively ported `4dbdc29` policy detail five-section semantics onto onprem `develop` in `agent/policy-detail-five-section-port`.
- Added onprem-compatible source provenance support (`0027_source_provenance_keys`) so the guarded `0029`/`0030` semantic migrations have a valid Alembic chain from current onprem head.

## Recent validation

- PASS: `backend/.venv/bin/python -m compileall backend/app backend/alembic/versions backend/scripts`
- PASS: focused backend semantic/policy tests — 127 passed.
- PASS: `cd backend && .venv/bin/alembic upgrade head --sql`
- PASS: `cd backend && .venv/bin/python -m pytest` — 601 passed, 16 skipped, 1 warning.
- PASS: `cd frontend && npm run typecheck`
- PASS: `cd frontend && npx vitest run src/app/__tests__/policy-detail.test.tsx` — 20 passed.
- PASS: `cd frontend && npm run build`
- PASS: `docker compose -f compose.yaml config`
- BLOCKED: `cd frontend && npm test -- --run src/app/__tests__/policy-detail.test.tsx` wrapper could not start its compose DB because local port `55432` is already allocated by an existing Docker container; direct Vitest policy-detail test passed instead.

## Active risks

- `0029`/`0030` are source-data guarded migrations. Empty databases pass, and known reviewed identities pass; deployment databases with partially drifted collected policy rows will intentionally stop before mutation and need data review.
- Frontend dependency install reported 2 moderate npm audit findings in existing dependency tree; not changed or remediated in this policy-detail port.
