# CHECKLIST

## Current status

- Active task/status: hotfix branch `hotfix/allow-partial-half-trip-prestate` allows migration `0030_half_trip_five_semantics` to update the scoped local-half-trip policies that actually exist on the onprem server.
- Scope guard: migration identity guard, regression test expectation, server dry-run evidence, and PR delivery only.
- Out of scope: creating missing policies, changing desired five-section semantics, manual production data mutation outside Alembic, frontend/e2e work, direct `develop` push, PR merge, and Jenkins rerun.

## Recent validation

- PASS: `cd backend && .venv/bin/python -m pytest tests/test_local_half_trip_five_semantics_migration.py tests/test_stay_discount_semantics_migration.py` — 6 passed.
- PASS: `cd backend && .venv/bin/alembic upgrade head --sql`.
- PASS: server DB dry-run with patched `0027` + `0029` + `0030` SQL inside `BEGIN ... ROLLBACK`; result `hotfix 0030 server dry-run passed` and 3 existing scoped policies updated in the dry-run.
- PASS: `cd backend && .venv/bin/python -m pytest` — 603 passed, 17 skipped, 1 warning.

## Active risks

- Jenkins deployment was not rerun; run it after this hotfix PR is merged.
- Server dry-run rolled back intentionally, so the live DB remains at `0026_user_withdrawal_fields` until Jenkins reruns Alembic.
- The server currently has 3 of the 5 scoped local-half-trip policy rows (`travelmonth-20`, `travelmonth-24`, `travelmonth-32`); this hotfix updates existing rows only and does not create the missing `travelmonth-21`/`travelmonth-27` policy rows.
- Frontend/e2e suites were not run because this branch changes backend data migration guard/tests only.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
