# CHECKLIST

## Current Status

- Active task/status: PR #102 was merged to `develop` and deployed to the development server.
- Development server SHA: `7b8be51` (`Merge pull request #102 from travel-hunter/agent/policies-table-cleanup-hardening`).
- Scope guard: The deployment used clean `develop` on `/home/deploy/travelhunterapp`; secrets were not printed.

## Latest Validation Evidence

- GitHub PR #102 CI passed before merge: Backend fast lane, Frontend DB-backed fast lane, and CodeRabbit.
- Local final gate before merge passed: backend full pytest 528 passed, Alembic SQL generation, frontend typecheck/test/build, compose config, diff/UTF-8 checks, independent code-reviewer APPROVE, and architect CLEAR.
- Development server deploy passed: `docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml config`, build, `up -d db`, `alembic upgrade head`, and `up -d`.
- Development server Alembic version is `0026_user_withdrawal_fields`; `users.withdrawn_at` and `users.withdrawn_email_hash` exist.
- Development server smoke passed: `/api/health`, `/login`, `/api/policies?limit=1`, and unauthenticated account lifecycle endpoint guards returning 401.

## Remaining Risks

- Fresh PostgreSQL `pg_dump` regeneration was not performed; `docs/db-schema-current.sql` remains a schema reference updated from Alembic 0026 SQL evidence.
- Authenticated browser smoke on the development server remains manual because it requires runtime login credentials.
- Jenkins build status was not checked from this environment.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
