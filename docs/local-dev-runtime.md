# Travel Hunter Local Development Runtime

## Purpose

Use this runtime for local code review, regression testing, and final UI checks
before asking for development-server or production-server work.

The default local review runtime is:

- PostgreSQL, FastAPI backend, and React frontend all run in Docker Compose.
- React frontend is served from the Docker production-build preview on port `4173`.
- Vite dev server on port `5173` is optional for fast UI iteration only.
- LAN/classroom sharing is not enabled during normal development.

## Default Local Review Runtime

Start all three services from one worktree with one explicit Compose project
name:

```powershell
cd <repo-root>
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml up -d --build db backend frontend
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml ps
```

Apply schema migrations against the preserved local PostgreSQL volume:

```powershell
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml run --rm backend alembic upgrade head
```

Do not run `python -m app.db.seed` as a routine startup step against a preserved
local volume. Seed is for a new or disposable database. Before intentionally
reseeding an existing DB, take a backup and review the expected policy-status
changes.

Confirm backend health and frontend rendering:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:4173/
```

Open the app:

```text
http://127.0.0.1:4173/
```

## Isolated Worktree Runtime

When the root worktree contains unrelated dirty work or is behind the target
branch, run all three services from one clean isolated worktree. Use the same
project name and the root env file for every command:

```powershell
cd <feature-worktree>
docker compose --env-file <repo-root>\.env -p travel-hunter-onprem -f compose.local.yaml up -d --build --force-recreate db backend frontend
```

Do not run the same `travel-hunter-onprem` Compose project alternately from the
root worktree and an isolated worktree. That mixes the containers'
`com.docker.compose.project.config_files` and
`com.docker.compose.project.working_dir` provenance.

Before review, inspect all three container labels and confirm they resolve to
the same worktree.

Changing worktree provenance does not copy development-server policy data or
enable Kakao Maps/Local, OAuth, or SMTP credentials.

## Optional Fast UI Iteration

```powershell
cd <repo-root>
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml up -d db backend

cd frontend
npm.cmd run dev
```

Use this only for rapid UI iteration and open the Vite frontend at:

```text
http://127.0.0.1:5173/
```

The final evidence path remains the Docker frontend on `4173`.

## Rebuild Frontend After UI Changes

After UI work is ready, run:

```powershell
cd <repo-root>
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml up -d --build frontend
```

Then check:

```text
http://127.0.0.1:4173/
```

## Auth Checks: Default No-Secret Flow

Use this path for normal local auth UI checks. It does not require real SMTP,
Google, or Kakao credentials.

For local UI checks, use the dev-only auth helper instead of real email
delivery or Google/Kakao callbacks. It refuses to run when `APP_ENV` is
`staging`, `production`, or `prod`. Run Alembic first so the latest pending
signup tables exist.

```bash
cd backend
.venv/bin/alembic upgrade head

# Email signup: creates a pending signup with required agreement metadata and prints /signup/verify URL.
.venv/bin/python -m app.scripts.dev_auth_helper email \
  --email local-email-$(date +%s)@example.com

# Social new signup: creates pending_social_signups and prints /signup/social-agreement URL.
.venv/bin/python -m app.scripts.dev_auth_helper social \
  --provider google \
  --email local-social-$(date +%s)@example.com \
  --provider-id local-google-$(date +%s)
```

Open the printed URL in the local frontend. The default fallback is
`http://127.0.0.1:4173`, matching the Docker frontend. If you intentionally use
Vite on `5173`, set `TRAVEL_HUNTER_PUBLIC_BASE_URL=http://127.0.0.1:5173` for
that helper process.

The latest generated URL is also saved to
`.omx/tmp/dev-auth-helper/latest-url.txt` unless `--no-file` is passed. Use a
fresh test email/provider id for each run; the helper rejects already-created
users/social accounts so existing accounts are not modified accidentally.

## Auth Checks: Opt-In Real SMTP/OAuth Config

Use this path only when you deliberately want the local backend to detect real
SMTP or Google/Kakao OAuth settings. Do not put real secrets in tracked files,
shell history, screenshots, or handoff notes.

- Copy root `.env.example` to the ignored root `.env`, then replace placeholders
  only with local values needed for the current machine.
- Docker Compose uses root `.env` for interpolation and `compose.local.yaml`
  supplies safe non-secret defaults such as the `4173` public base URL and
  disabled Kakao Local settings.
- Do not restore the deprecated `backend/.env.local.example` or
  `backend/compose.defaults.env` workflow.
- Do not copy root `.env` into deploy files or a server environment.
- Export process-specific overrides explicitly when intentionally using Vite or
  a non-Docker backend. Existing process environment variables remain highest
  priority.

Success boundary for this local opt-in is intentionally narrow:

- You can verify settings detection without sending email.
- You can verify OAuth start behavior reaches provider redirect (`302`) instead
  of missing-config (`503`) when provider settings are present.
- Actual email delivery and full provider callback completion are out of scope
  unless you deliberately perform those external checks.

## Port Standard

- `4173`: Docker production frontend, default local review runtime.
- `5173`: optional Vite dev frontend, fast UI iteration only.
- `8000`: FastAPI backend.
- `55432`: PostgreSQL exposed from Docker.

## Local Timezone Behavior

The local `compose.local.yaml` runtime uses KST for database and backend checks:

- PostgreSQL starts with `timezone=Asia/Seoul` and `log_timezone=Asia/Seoul`.
- The `db` and `backend` services set `TZ=Asia/Seoul`.
- Tunnel, VPS, and deploy entrypoint files are separate deployment concerns.

This does not change the API contract or timestamp column types. Timestamp data
changes must still go through Alembic.

## Guarded Local Timestamp Data Shift

Alembic revision `0024_local_kst_time_shift` is a guarded local data-adjustment
draft for the approved KST migration pass.

- Offline SQL review remains available with the standard backend Alembic SQL
  command.
- Normal online `alembic upgrade head` is safe/no-op by default for this
  revision.
- Set `TRAVEL_HUNTER_ALLOW_LOCAL_TIMEZONE_DATA_SHIFT=1` only for an intentional
  local data shift; that opt-in enforces local/dev/test `APP_ENV` and a local
  PostgreSQL URL host before running the seven-column update.
- Do not enable the opt-in for staging or production.
- Take a local DB backup and review the migration's before/after queries before
  running the guarded shift online.

## Classroom Sharing Policy

Do not enable LAN/classroom sharing during normal UI development.

When development is complete and other people need to view the app from their
devices, use the Cloudflare Tunnel wrapper in `compose.yaml` with an approved
runtime env file. That step may require public hostname, CORS, and secret/env
settings.

## Quick Checks

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:4173/
```

## Kakao Local Candidate Smoke

With `KAKAO_LOCAL_ENABLED=true` and `KAKAO_LOCAL_REST_API_KEY` configured, this
checks representative travel areas against Kakao Local and prints only
counts/metadata/sample titles:

```powershell
cd <repo-root>\backend
python -m app.scripts.smoke_kakao_local_candidates --min-candidates 6
```

Without Kakao Local credentials, the same command runs catalog fallback smoke.
To require live Kakao Local credentials, add `--require-kakao`.

## Local Code Review Gate

Run static configuration and non-mutating checks before reporting local
evidence:

```powershell
cd <repo-root>
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml -f compose.review.yaml config
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml -f compose.review.yaml run --rm backend python -m pytest -p no:cacheprovider tests/test_config.py -q

cd frontend
npm.cmd run typecheck
npm.cmd run test:mojibake
npm.cmd run build

cd ..
git diff --check
```

`npm.cmd test` invokes `scripts/run-backend-command.cjs`, which migrates and
reseeds the PostgreSQL database on port `55432`. Run it only against a
disposable test DB or after taking and verifying a restorable backup of the
preserved local DB.

The same backup rule applies to `npm.cmd run test:e2e:containers`, because
backend-mode browser tests create local test records even though that command
does not reseed the database.
