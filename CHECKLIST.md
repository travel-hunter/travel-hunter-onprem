# CHECKLIST

## Current Status

- Active task/status: local-auth-env-injection branch is prepared on `feature/local-auth-env-injection` in `travel-hunter-onprem`.
- Scope guard: Include only local Docker/non-Docker backend auth env loading, safe local env examples, local runtime docs, and this checklist update.
- Excluded from this branch: real secrets, email delivery smoke, OAuth callback completion, deploy/tunnel/prod env strategy changes, API shape changes, auth business logic changes, direct `develop` push, PR merge, and production promotion.

## Latest Validation Evidence

- Compose config passed for the scoped local runtime chain: `docker compose -f compose.yaml config --quiet`.
- Config syntax passed: `cd backend && python3 -m py_compile app/core/config.py`.
- Diff hygiene passed for scoped files: `.gitignore`, `CHECKLIST.md`, `backend/.dockerignore`, `backend/app/core/config.py`, `compose.yaml`, `docs/local-dev-runtime.md`, `backend/.env.local.example`, and `backend/compose.defaults.env`.
- UTF-8/U+FFFD scan passed for all changed scoped text files.
- Secret hygiene: `backend/.env.local` is ignored, excluded from backend Docker build context, and absent after validation; tracked env files contain placeholders/defaults only.
- Source validation from the originating local smoke: placeholder-only non-Docker and Docker one-off settings detection passed; Google OAuth start returned `302` to `accounts.google.com`; Kakao OAuth start returned `302` to `kauth.kakao.com`; real email sending and OAuth callback completion were intentionally not executed.

## Remaining Risks

- Long-running compose services were not restarted; validation used compose config and syntax/diff checks in this onprem branch.
- Full backend/frontend suites, live email sending, OAuth provider callback, Jenkins dev deployment, merge, and production promotion remain out of scope.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
