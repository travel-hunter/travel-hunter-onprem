# CHECKLIST

## Current Status

- Active task/status: B-plan worktree preservation is being split into separate test-infrastructure and documentation branches.
- Scope guard: PR A contains only the container E2E review harness. PR B contains only local-runtime documentation, preserved planning docs, and current active risks.

## Recent Validation

- PASS: root `develop` was synchronized with `origin/develop` before splitting work.
- PASS: PR A `npm.cmd run typecheck`.
- PASS: PR A `npm.cmd run test:e2e:containers -- --list` listed 12 Playwright tests.
- PASS: PR A `docker compose --env-file <root>/.env -f compose.yaml -f compose.review.yaml config --quiet`.
- PASS: PR A `docker compose --env-file <root>/.env -f compose.yaml -f compose.review.yaml build backend`.
- FAIL: PR A `npm.cmd run test:e2e:containers` entered the Playwright suite and ran 3 tests successfully, then failed on the existing `backend-mode.spec.ts` expected official URL mismatch. This is tracked as a separate E2E expectation/data issue, not a container harness wiring failure.

## Active Risks

- Backend full pytest is not fully green on this Windows workspace: 669 passed, 22 skipped, 1 failed.
- Container E2E now has a runnable harness branch, but the full browser suite still has an existing official URL expectation/data mismatch.
- `frontend/src/app/__tests__/policies.test.tsx`, `frontend/src/app/__tests__/trip-create.test.tsx`, and `frontend/e2e-backend/backend-mode.spec.ts` flaky-test changes remain a separate follow-up decision.
- dgtour canonical slug changes remain out of this cleanup scope until the team decides the canonical-vs-legacy slug source of truth.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, and active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
