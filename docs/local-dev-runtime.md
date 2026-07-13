# Travel Hunter Local Development Runtime

## Purpose

Use this runtime while frontend UI work is still changing frequently.

The development default is:

- PostgreSQL and FastAPI backend run in Docker.
- React frontend runs through Vite dev server on port `5173`.
- Docker frontend on port `4173` is reserved for final production-build verification.
- LAN/classroom sharing is not enabled during normal development.

## Default Development Flow

Start only the database and backend containers:

```powershell
cd C:\Users\HP\Documents\프로젝트\진행중\travel-hunter-app
docker compose up -d db backend
docker compose ps
```

Confirm backend health:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health
```

Start the frontend in dev mode:

```powershell
cd C:\Users\HP\Documents\프로젝트\진행중\travel-hunter-app\frontend
npm run dev
```

Open the app:

```text
http://127.0.0.1:5173/
```

## Why This Is The Default

Vite dev server updates the browser almost immediately after saving frontend files.

Running `docker compose up -d --build frontend` for every UI change is slower because it performs a production build, image export, and container restart. Use it only when checking final Docker behavior.

## Final Docker Frontend Check

After the UI work is ready, run:

```powershell
cd C:\Users\HP\Documents\프로젝트\진행중\travel-hunter-app
docker compose up -d --build frontend
```

Then check:

```text
http://127.0.0.1:4173/
```


## Auth flow UI without real SMTP/OAuth

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

Open the printed URL in the local frontend. By default the helper uses `http://127.0.0.1:5173`, matching the Vite dev server. If you are checking the Docker production frontend on `4173`, either set `TRAVEL_HUNTER_PUBLIC_BASE_URL=http://127.0.0.1:4173` before running the helper or replace the port in the printed URL.

The latest generated URL is also saved to `.omx/tmp/dev-auth-helper/latest-url.txt` unless `--no-file` is passed. Use a fresh test email/provider id for each run; the helper rejects already-created users/social accounts so existing accounts are not modified accidentally.

## Port Standard

- `5173`: Vite dev frontend, fast UI iteration.
- `4173`: Docker production frontend, final verification.
- `8000`: FastAPI backend.
- `55432`: PostgreSQL exposed from Docker.

## Local Timezone Behavior

This pass changed only the local `compose.yaml` runtime to use KST for database and backend checks:

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

When development is complete and other people need to view the app from their devices, use the Cloudflare Tunnel flow described in `compose.tunnel.yaml` and `deploy/.env.tunnel.example`. That step may require public hostname, CORS, and secret/env settings.

## Quick Checks

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173/
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health
```

## Kakao Local Candidate Smoke

With `KAKAO_LOCAL_ENABLED=true` and `KAKAO_LOCAL_REST_API_KEY` configured, this checks representative travel areas against Kakao Local and prints only counts/metadata/sample titles:

```powershell
cd C:\Users\HP\Documents\프로젝트\진행중\travel-hunter-app\backend
python -m app.scripts.smoke_kakao_local_candidates --min-candidates 6
```

Without Kakao Local credentials, the same command runs catalog fallback smoke. To require live Kakao Local credentials, add `--require-kakao`.

Before committing frontend work:

```powershell
cd C:\Users\HP\Documents\프로젝트\진행중\travel-hunter-app\frontend
npm run typecheck
npm test -- --run
npm run build

cd ..
git diff --check
```
