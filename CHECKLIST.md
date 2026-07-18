# CHECKLIST

## Current Status

- Active task/status: dgtour seed policy slugs are now ASCII canonical values; the 16 existing Korean dgtour slugs are retained only as `legacySlugs`/`policy_slug_aliases` compatibility aliases.
- Scope guard: changes are limited to seed slug migration, alias seeding, crawler slug generation, focused tests, frontend fixtures/e2e literals, docs/eval contract examples, and this checklist; no migrations, deploy/env/auth changes, or commits were made.
- Behavior result: `seed_policies` can migrate an existing Korean legacy dgtour policy row to its canonical slug while preserving that policy id and linked saved/trip references, then creates/updates active seed aliases so old detail URLs redirect to canonical slugs.

## Latest Validation Evidence

- Backend targeted tests passed: `cd backend && ../.venv/bin/python -m pytest tests/test_policy_source_audit.py tests/test_crawl_dgtourcard.py tests/test_travel_areas.py tests/test_validate_policy_data.py tests/test_policy_data_validation.py -q` (`35 passed`, one existing Starlette/httpx warning, plus `../.venv` sys.prefix runtime warnings from the relative venv path).
- Frontend targeted tests passed: `cd frontend && npx vitest run src/app/__tests__/policy-detail.test.tsx src/app/__tests__/policies.test.tsx src/app/__tests__/trip-create.test.tsx src/app/__tests__/trip-detail.test.tsx src/app/__tests__/trips-list.test.tsx src/app/__tests__/mypage.test.tsx` (`6` files, `108 passed`).
- Frontend typecheck passed: `cd frontend && npm run typecheck` (`tsc --noEmit`).
- API contract golden JSON parse passed, dgtour seed canonical/legacy mapping check passed for 16 rows, and canonical slug grep checks found no `"slug": "dgtour-{한글}` or `examplePolicySlug = "dgtour-{한글}` remnants.
- Diff and encoding checks passed: `git diff --check`, `git diff --check -- CHECKLIST.md`, and U+FFFD scan over changed Korean-bearing files.

## Remaining Risks

- Full backend pytest, full frontend Vitest, e2e, and production build were not rerun in this final pass; targeted tests covered the changed seed/slug/frontend fixture paths.
- Existing Starlette/httpx deprecation warning remains unrelated to this change.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
