# CHECKLIST

## Current Status

- Active task/status: PR #1 signup verify state fix retention WATCH resolved on `feature/signup-verify-state-fix` in `travel-hunter-onprem`.
- Scope guard: Include only signup verify frontend cache retention fix, focused regression test, and this checklist update.
- Excluded from this branch: backend policy/data/schema/migration changes, secrets/env, `main` update, direct `develop` push, PR merge, and production promotion.

## Latest Validation Evidence

- Signup verify cache now keeps same-token in-flight single-flight behavior, keeps successful same-token reuse briefly with a 30초 TTL, deletes expired success entries, and clears the current token entry after `completeSignup` succeeds.
- Frontend typecheck passed after retention hardening: `cd frontend && npm run typecheck`.
- Targeted auth regression passed and asserts one same-token verify request through session bootstrap rerender: `cd frontend && npx vitest run src/app/__tests__/auth.test.tsx -t "keeps signup verification progressing"`.
- New targeted auth regression passed and asserts completing signup clears the token cache so a later same-token page entry verifies again: `cd frontend && npx vitest run src/app/__tests__/auth.test.tsx -t "clears signup verification cache"`.
- Diff hygiene passed: `git diff --check origin/develop`, `git diff --check origin/develop -- CHECKLIST.md`, UTF-8/U+FFFD scan for changed text files, and excluded backend/deploy/env/compose diff check.
- Frontend `npm test` did not complete: mojibake precheck passed, then `scripts/run-backend-command.cjs` started compose PostgreSQL but Alembic failed in the local Python environment with `No module named alembic.__main__; 'alembic' is a package and cannot be directly executed`. The test compose container/volume/network were removed with `docker compose down -v --remove-orphans`.
- Full auth test file was not used as a release gate for this narrow fix; a local run of `cd frontend && npx vitest run src/app/__tests__/auth.test.tsx` still fails on the pre-existing live-backend login-dependent cases, while the two signup verification targeted cases pass.
- External dev smoke evidence provided for the source fix: public `/api/health` OK, synthetic `POST /api/auth/signup/verify` 200, and Playwright public verify page showed password input plus completion button.

## Remaining Risks

- Full frontend `npm test` is blocked by the local backend Alembic executable environment above; e2e, backend pytest, and Jenkins dev status were not run for this narrow frontend/docs branch.
- PR is for review into `develop`; merge and production promotion remain intentionally out of scope.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
