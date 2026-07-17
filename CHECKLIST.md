# CHECKLIST

## Current Status

- Active task/status: Final verifier re-run on `feature/policy-detail-url-unification` is clean with an explicit environment note: backend-mode e2e passed by using the script-supported `SKIP_E2E_DB_START` + `DATABASE_URL` override against a temporary isolated Postgres container on `127.0.0.1:56432`, because the default compose host port `55432` is occupied by the foreign `travel-hunter-app-db-1` container.
- Scope guard: cleanup stayed inside the current git diff; no commits, pushes, deploy/env/auth changes, parser overhaul, DB batch conversion, or production operations.
- Behavior result: policy slug resolution checks active canonical direct lookup, active persisted alias, inactive direct hidden-policy guard, virtual stay-discount alias, then raw fallback; trip creation echoes persisted/virtual alias request slugs in the returned linked policy payload.

## Latest Validation Evidence

- Backend full tests passed with the local repo venv: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/python -m pytest` (`539 passed`, one existing Starlette/httpx deprecation warning).
- Alembic offline SQL generation passed through head `0027_policy_slug_aliases`: `cd backend && /home/hp/projects/travel-hunter-onprem/.venv/bin/alembic upgrade head --sql`.
- Frontend typecheck passed: `cd frontend && npm run typecheck`.
- Frontend Vitest passed on the first full re-run: `cd frontend && npx vitest run` (`22 passed` test files, `217 passed` tests); no flaky-test rerun was needed.
- Frontend build passed: `cd frontend && npm run build`.
- Frontend backend-mode e2e passed without stopping or reusing foreign containers: a temporary verifier-owned Postgres `postgres:16-alpine` container ran on `127.0.0.1:56432`, then `cd frontend && SKIP_E2E_DB_START=1 PYTHON=/home/hp/projects/travel-hunter-onprem/.venv/bin/python DATABASE_URL=postgresql+psycopg://travelhunter:travelhunter@127.0.0.1:56432/travelhunter E2E_API_PORT=8001 E2E_FRONTEND_PORT=5174 npm run test:e2e` passed (`11 passed`). Inspection found the e2e script supports `DATABASE_URL`, `SKIP_E2E_DB_START`, `E2E_API_PORT`, and `E2E_FRONTEND_PORT`; `compose.yaml` still hardcodes `55432:5432` with no `POSTGRES_PORT`/`DB_PORT` interpolation.
- Compose config passed: `docker compose -f compose.yaml config`.
- Diff and encoding checks passed: `git diff --check`, `git diff --check -- CHECKLIST.md`, and UTF-8/U+FFFD scan of 25 changed tracked/untracked text files.

## Remaining Risks

- Existing Starlette/httpx deprecation warning remains unrelated to this change.
- The default unmodified e2e DB startup path still targets hardcoded host port `55432`; in this environment that port belongs to the foreign `travel-hunter-app-db-1` container, so the verifier used the supported isolated DB override instead of stopping or mutating that container.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
