# CHECKLIST

## Current status

- Active task/status: #10 local auth env injection work has been rebased and validated after #9 merged into current onprem `develop`.
- Scope guard: local Docker/non-Docker backend auth env loading, safe local env examples, local runtime docs, validation evidence, and PR cleanup only.
- Out of scope: real secrets, email delivery smoke, OAuth callback completion, deploy/tunnel/prod env strategy changes, API shape changes, auth business logic changes, direct `develop` push, PR merge, and production promotion.

## Recent validation

- PASS: `cd backend && .venv/bin/python -m pytest tests/test_config.py` — 5 passed.
- PASS: `cd backend && .venv/bin/python -m pytest` — 603 passed, 16 skipped, 1 warning.
- PASS: `cd backend && .venv/bin/alembic upgrade head --sql`.
- PASS: `docker compose -f compose.yaml config --quiet`.
- PASS: temporary `backend/.env.local` override smoke with `docker compose -f compose.yaml config --format json` for public base URL, SMTP, Google/Kakao OAuth, and Kakao Local variables.

## Active risks

- Frontend/e2e suites were not run because this branch changes backend config, Compose env loading, and local runtime docs only.
- Real email delivery, OAuth callback completion, Jenkins dev deployment, merge, and production promotion remain out of scope.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
