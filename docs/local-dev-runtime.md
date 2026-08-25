# Travel Hunter Local Development Runtime

## Purpose

Use this runtime for local code review, regression testing, and final UI checks
before asking for development-server or production-server work.

The development default is:

- PostgreSQL, FastAPI backend, and React frontend all run in Docker Compose.
- React frontend is served from the Docker production-build preview on port `4173`.
- Vite dev server on port `5173` is optional for fast UI iteration only, not the
  default review runtime.
- LAN/classroom sharing is not enabled during normal development.

## Default Local Review Runtime

Start the same three-container stack used by the handoff workflow:

```powershell
cd C:\dev\travel-hunter\travel-hunter-onprem
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml up -d --build db backend frontend
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml ps
```

Apply schema and seed data against the local Docker PostgreSQL database:

```powershell
cd C:\dev\travel-hunter\travel-hunter-onprem
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml run --rm backend alembic upgrade head
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml run --rm backend python -m app.db.seed
```

Confirm backend health and frontend rendering:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:4173/
```

Open the app:

```text
http://127.0.0.1:4173/
```

### Isolated Worktree Runtime

The default commands assume the current repository directory is clean and is the source intended for review. When that root worktree contains unrelated dirty work or is behind the target branch, create or reuse a clean isolated worktree and run all three services from that one directory.

Use the same explicit project name and root env file for every command:

```powershell
cd C:\dev\travel-hunter\travel-hunter-onprem\.superpowers\worktrees\develop-runtime
docker compose --env-file C:\dev\travel-hunter\travel-hunter-onprem\.env -p travel-hunter-onprem -f compose.local.yaml up -d --build --force-recreate db backend frontend
```

Do not run the same `travel-hunter-onprem` Compose project alternately from the root worktree and an isolated worktree. That mixes container `project.config_files` and `project.working_dir` provenance. Before review, inspect all three container labels and confirm they point to one worktree.

The isolated worktree changes code provenance only. It does not copy development-server policy data or enable Kakao Maps/Local, OAuth, or SMTP credentials.

## Optional Fast UI Iteration

```powershell
cd C:\dev\travel-hunter\travel-hunter-onprem
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml up -d db backend

cd C:\dev\travel-hunter\travel-hunter-onprem\frontend
npm.cmd run dev
```

Use this optional flow only when changing frontend UI rapidly:

```text
http://127.0.0.1:5173/
```

## Why This Is The Default

The Docker frontend uses the same production-build path that reviewers see in
the containerized runtime.

Vite dev server updates the browser almost immediately after saving frontend
files, but it is not the default evidence path for local code review because it
does not prove the Docker frontend image.

## Rebuild Frontend After UI Changes

After UI work changes, rebuild and restart the Docker frontend before visual
review:

```powershell
cd C:\dev\travel-hunter\travel-hunter-onprem
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml up -d --build frontend
```

Then check:

```text
http://127.0.0.1:4173/
```


## Auth Checks: Default No-Secret Flow

Use this path for normal local auth UI checks. It does not require real SMTP,
Google, or Kakao credentials.

For local UI checks, use the dev-only auth helper instead of real email delivery or Google/Kakao callbacks. It refuses to run when `APP_ENV` is `staging`, `production`, or `prod`. Run Alembic first so the latest pending signup tables exist.

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

Open the printed URL in the local frontend. By default the helper uses `http://127.0.0.1:4173`, matching the Docker frontend. If you intentionally switch to the optional Vite frontend on `5173`, temporarily set `TRAVEL_HUNTER_PUBLIC_BASE_URL=http://127.0.0.1:5173` before running the helper or replace the port in the printed URL.

The latest generated URL is also saved to `.omx/tmp/dev-auth-helper/latest-url.txt` unless `--no-file` is passed. Use a fresh test email/provider id for each run; the helper rejects already-created users/social accounts so existing accounts are not modified accidentally.

## Auth Checks: Opt-In Real SMTP/OAuth Config

Use this path only when you deliberately want the local backend to detect real
SMTP or Google/Kakao OAuth settings. Do not put real secrets in tracked files,
shell history, screenshots, or handoff notes.

- Create a local-only `backend/.env.local` from the safe placeholder file
  `backend/.env.local.example`, then replace placeholders with your own local
  integration values.
- `backend/.env.local` is ignored by git and by the backend Docker build. Keep
  it local to your machine.
- Do not copy `backend/.env.local` into `deploy/.env.*` or a server environment
  unless you are intentionally setting up that server with reviewed production
  or staging values.
- Docker Compose loads backend env in this order:
  1. root `.env` for Compose variable interpolation
  2. explicit non-secret defaults in `compose.local.yaml`
  3. optional process environment overrides
- `compose.local.yaml` sets safe Docker defaults such as
  `TRAVEL_HUNTER_PUBLIC_BASE_URL=http://127.0.0.1:4173` and disabled Kakao
  Local settings.
- For the default three-container review runtime, keep
  `TRAVEL_HUNTER_PUBLIC_BASE_URL=http://127.0.0.1:4173`.
- If you intentionally switch to the optional Vite flow, temporarily override
  `TRAVEL_HUNTER_PUBLIC_BASE_URL=http://127.0.0.1:5173` for auth links.
- `backend/.env.local` can provide auth integration variables such as
  `SMTP_*`, `GOOGLE_*`, and OAuth `KAKAO_*`.
- `backend/.env.local` can also opt in Kakao Local settings such as
  `KAKAO_LOCAL_ENABLED=true` and `KAKAO_LOCAL_REST_API_KEY=...`.
- Non-Docker backend runs also read `backend/.env.local`; already-exported
  process environment variables still win.

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
- Tunnel, VPS, and deploy entrypoint files were not changed in this pass.
- `deploy/container/entrypoint.sh` already has separate deploy-time timezone behavior; it is out of scope for this local runtime note.

This does not change the API contract or the timestamp column types. Timestamp data changes must still go through Alembic.

## Guarded Local Timestamp Data Shift

Alembic revision `0024_local_kst_time_shift` is a guarded local data-adjustment draft for the approved KST migration pass.

- Offline SQL review remains available with the standard backend Alembic SQL command.
- Normal online `alembic upgrade head` is safe/no-op by default for this revision.
- Set `TRAVEL_HUNTER_ALLOW_LOCAL_TIMEZONE_DATA_SHIFT=1` only for an intentional local data shift; that opt-in enforces local/dev/test `APP_ENV` and a local PostgreSQL URL host before running the seven-column update.
- Do not enable the opt-in for staging or production.
- Take a local DB backup and review the migration's before/after queries before running the guarded shift online.

## Classroom Sharing Policy

Do not enable LAN/classroom sharing during normal UI development.

When development is complete and other people need to view the app from their devices, use the Cloudflare Tunnel wrapper flow in `compose.yaml` with an approved runtime env file. That step may require public hostname, CORS, and secret/env settings.

## Quick Checks

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:4173/
```

## Kakao Local Candidate Smoke

With `KAKAO_LOCAL_ENABLED=true` and `KAKAO_LOCAL_REST_API_KEY` configured, this checks representative travel areas against Kakao Local and prints only counts/metadata/sample titles:

```powershell
cd C:\dev\travel-hunter\travel-hunter-onprem\backend
.\.venv\Scripts\python.exe -m app.scripts.smoke_kakao_local_candidates --min-candidates 6
```

Without Kakao Local credentials, the same command runs catalog fallback smoke. To require live Kakao Local credentials, add `--require-kakao`.

## Local Code Review Gate

Use this sequence before reporting local review/test evidence:

```powershell
cd C:\dev\travel-hunter\travel-hunter-onprem
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml config
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml up -d --build db backend frontend
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml run --rm backend alembic upgrade head
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml run --rm backend python -m app.db.seed

cd C:\dev\travel-hunter\travel-hunter-onprem
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml run --rm backend python -m pytest

cd C:\dev\travel-hunter\travel-hunter-onprem\frontend
npm.cmd run typecheck
npm.cmd test
npm.cmd run test:e2e:containers
npm.cmd run build

cd C:\dev\travel-hunter\travel-hunter-onprem
git diff --check
```
