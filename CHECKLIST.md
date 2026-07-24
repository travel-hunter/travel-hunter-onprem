# CHECKLIST

## Current status

- Active task/status: `/trips/new` disabled CTA guidance and copy update implemented; member withdrawal first-step modal danger button copy updated.
- Scope guard: frontend UX copy/state guidance only; no API, schema, backend, or data-contract changes.

## Recent validation

- PASS: `cd frontend && npx vitest run src/app/__tests__/trip-create.test.tsx src/app/__tests__/mypage.test.tsx --reporter=dot` — 42 passed.
- PASS: `cd frontend && npm run test:mojibake` — no mojibake-like frontend text found.
- PASS: `cd frontend && npm run typecheck`.
- PASS: `cd frontend && npm run build`.
- BLOCKED: `cd frontend && npm test` stopped before Vitest because `scripts/run-backend-command.cjs` resolved system Python 3.14 and failed with `No module named alembic.__main__`; focused Vitest above was run directly and passed.

## Active risks

- Full frontend `npm test` needs a backend Python environment with Alembic installed or `PYTHON` pointed at a valid backend venv.
- Frontend e2e was not run for this small copy/state-guidance change; covered with focused component tests, typecheck, and production build.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
