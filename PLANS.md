# Travel Hunter Current Plan

## Current Phase

The MVP is DB-backed-only and runtime mock mode has been removed. The current priority is Weekend Public v1 release execution. The development domain `dev.travel-hunter.co.kr` now has Cloudflare Tunnel, Brevo SMTP, Google OAuth, Kakao OAuth, Kakao email scope, and Kakao Local/Maps runtime configuration smoke evidence. The next priority is production-server readiness and `travel-hunter.co.kr` public release evidence.

## Source Of Truth

- Product requirements: `docs/requirements.md`
- Implemented feature/status inventory: `docs/implemented-feature-spec.md`
- API contract: `docs/mvp-api-contract.md`
- Current DB schema: `docs/db-schema-current.md`, `docs/db-schema-current.sql`
- Next priority and execution queue: `docs/next-work-plan.md`
- Spec navigation index: `docs/specs/spec-index.md`
- Deployment/CICD: `docs/deployment-cicd/README.md`

## Guardrails

- Do not add `trips.slug`.
- Keep DB mode `Trip.id` as `str(trips.id)`.
- Keep trip route handles numeric string ids only.
- Keep API DTO fields `camelCase` and DB fields `snake_case`.
- Keep frontend pages behind the `AppDataApi` boundary.
- Keep backend routes thin and push business behavior into services.
- Do not reintroduce runtime mock mode.
- Do not commit real `.env` files, tunnel tokens, DB passwords, Kakao secrets, or auth secrets.

## Fast Lane Verification

```bash
cd frontend
npm run typecheck
npm test

cd ../backend
python -m pytest
```

Run only when a migration changes:

```bash
cd backend
alembic upgrade head --sql
```

## Release Gate

```bash
cd frontend
npm run test:e2e
npm run build

cd ..
docker compose -f compose.yaml config
docker compose -f compose.yaml build
docker compose -f compose.yaml run --rm backend alembic upgrade head
docker compose -f compose.yaml run --rm backend python -m app.db.seed
docker compose --env-file deploy/.env.tunnel.example -f compose.tunnel.yaml config
```
