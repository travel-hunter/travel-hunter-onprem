# CHECKLIST

## Current status

- Active task/status: hotfix branch `hotfix/allow-server-stay-discount-prestate` allows the onprem server's observed legacy stay-discount `structured_detail` prestate in migration `0029_stay_discount_semantics`.
- Scope guard: migration prestate guard, regression tests, server dry-run evidence, and PR delivery only.
- Out of scope: changing desired policy semantics, manual production data mutation outside Alembic, frontend/e2e work, direct `develop` push, PR merge, and Jenkins rerun.

## Recent validation

- PASS: `cd backend && .venv/bin/python -m pytest tests/test_stay_discount_semantics_migration.py tests/test_config.py` — 8 passed.
- PASS: `cd backend && RUN_POSTGRES_MIGRATION_TESTS=1 .venv/bin/python -m pytest tests/test_stay_discount_semantics_migration_postgres.py` — 10 passed.
- PASS: `cd backend && .venv/bin/alembic upgrade head --sql`.
- PASS: server DB dry-run with patched `0027` + `0029` SQL inside `BEGIN ... ROLLBACK`; result `hotfix 0029 server dry-run passed`.
- PASS: `cd backend && .venv/bin/python -m pytest` — 603 passed, 17 skipped, 1 warning.

## Active risks

- Jenkins deployment was not rerun; run it after this hotfix PR is merged.
- Server dry-run rolled back intentionally, so the live DB remains at `0026_user_withdrawal_fields` until Jenkins reruns Alembic.
- Frontend/e2e suites were not run because this branch changes backend data migration guard/tests only.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
