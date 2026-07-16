# CHECKLIST

## Current Status

- Active task/status: Preparing `feature/signup-verify-state-fix` from `origin/develop` in `travel-hunter-onprem`.
- Scope guard: Include only signup verify frontend fix, regression test, Semi-Trunk strategy docs/guard, and local Codex/OMX skill.
- Excluded from this branch: backend policy/data/schema/migration changes, secrets/env, `main` update, direct `develop` push, PR merge, and production promotion.

## Latest Validation Evidence

- Frontend typecheck passed: `cd frontend && npm run typecheck`.
- Targeted auth regression passed: `cd frontend && npx vitest run src/app/__tests__/auth.test.tsx -t "keeps signup verification progressing"`.
- Frontend `npm test` did not complete: mojibake precheck passed, then `scripts/run-backend-command.cjs` started compose PostgreSQL but Alembic failed in the local Python environment with `No module named alembic.__main__; 'alembic' is a package and cannot be directly executed`. The test compose container/volume/network were removed with `docker compose down -v --remove-orphans`.
- External dev smoke evidence provided for the source fix: public `/api/health` OK, synthetic `POST /api/auth/signup/verify` 200, and Playwright public verify page showed password input plus completion button.

## Remaining Risks

- Full frontend `npm test` is blocked by the local backend Alembic executable environment above; e2e, backend pytest, and Jenkins dev status were not run for this narrow frontend/docs branch.
- PR is for review into `develop`; merge and production promotion remain intentionally out of scope.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
