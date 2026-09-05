# Travel Hunter Agent Harness

## Project Goal

Travel Hunter is an MVP that helps users find domestic travel support policies and connect those benefits to trip planning. The current app is a React/Vite frontend plus FastAPI backend with a shared API contract and PostgreSQL-backed policy, auth, profile, saved policy, trip, and invite flows.

## Current Phase

- The frontend must depend on the `AppDataApi` boundary and must not couple pages directly to seed data or backend client details.
- The frontend always calls the FastAPI backend through `AppDataApi`; mock mode has been removed.
- The backend always uses PostgreSQL-backed behavior for user-facing data. Static profile options and seed constants live under `app/data`, but there is no runtime mock API mode.
- Policy, auth, profile, saved policy, trip list/detail/create, trip policy attachment, recommendations, invite state, invite acceptance, and policy official links are implemented.
- The active product, implementation/status, execution-priority, and API sources of truth are `docs/requirements.md`, `docs/implemented-feature-spec.md`, `docs/next-work-plan.md`, and `docs/mvp-api-contract.md`.
- ERD source material lives outside this repo at `../files`; the current repo schema reference is `docs/db-schema-current.md` and `docs/db-schema-current.sql`.

## Source Priority

When instructions conflict, use this order:

1. The user's latest explicit request.
2. This `AGENTS.md`.
3. The nearest nested `AGENTS.md` for the files being changed.
4. `PLANS.md`.
5. `docs/requirements.md`.
6. `docs/implemented-feature-spec.md`.
7. `docs/next-work-plan.md`.
8. `docs/mvp-api-contract.md`.
9. ERD and requirement source files under `../files`.

## Required Orientation Loop

At the start of non-trivial work:

1. Check `git status --short`.
2. Read this file, then any nested `AGENTS.md` in the target area.
3. Read `PLANS.md` and the relevant `.agent/skills/*/SKILL.md`.
4. Check the relevant contract, schema, route, type, and test files before editing.
5. Record validation results and remaining risks in `CHECKLIST.md` when the work affects project state.

## Non-Negotiable Rules

- Do not revert or overwrite existing worktree changes unless the user explicitly asks.
- Keep API DTO fields in `camelCase`; keep database and SQL fields in `snake_case`.
- Policy detail routes use `policySlug` / `policies.slug`.
- Trip routes use an internal trip id. Do not introduce public trip slugs unless a later plan explicitly changes the contract.
- Frontend pages and components must access app data through `frontend/src/api/AppDataApi` and related API boundary files.
- Backend routes must stay thin. Put request/response shapes in `app/schemas`, business behavior in `app/services`, DB queries in `app/repositories`, and seed/static data in `app/data`.
- **Secrets: never commit, and never print.** `.env` 값, DB 비밀번호, `DATABASE_URL`,
  Cloudflare 터널 토큰, OAuth/SMTP secret, `AUTH_SECRET_KEY`, 관리자 액세스 토큰은
  커밋뿐 아니라 콘솔·로그·PR·Slack 어디에도 출력하지 않는다.
  - 값을 그대로 뱉는 명령을 쓰지 않는다: `docker compose config`, `docker inspect <container>`,
    필터 없는 `env`, 명령줄에 비밀번호가 들어가는 `psql "postgresql://user:pw@..."`.
  - 확인이 필요하면 키 이름만 보거나(`sed 's/=.*/=/' .env`) 해시 지문으로 비교한다
    (`sha256sum`, SQL 은 `left(md5(col),12)`). 컨테이너 DB 접속은 변수를 안에서 펼친다:
    `docker exec <db> sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "..."'`.
  - 구성 검증은 출력을 버린다: `docker compose --env-file <env> config > /dev/null`.
  - 이미 노출됐다면 교체 외에 방법이 없다. 스크롤백과 로그에 남으므로 교체 대상을 명시해 보고한다.
    `POSTGRES_PASSWORD` 는 `.env` 수정만으로 바뀌지 않는다. `ALTER USER ... WITH PASSWORD` 가 필요하다.
  - 덤프·백업 파일은 `chmod 600` 으로 저장소 밖에 둔다.
  - Keep `.env.example` documented and safe.
- Any API shape change must update the API contract, frontend types, backend schemas/routes/services, tests, and `.agent/evals` together.
- **Encoding (UTF-8 Korean text).** All source, docs, tests, and config files are UTF-8 and must stay UTF-8:
  - Do not rewrite Korean-bearing files through PowerShell `Set-Content` / `Out-File` or shell redirection; use `apply_patch` or a UTF-8-explicit tool (e.g. Node `fs.readFileSync(path, "utf8")` / `fs.writeFileSync(path, text, "utf8")`) for mechanical rewrites.
  - Treat garbled Korean in PowerShell `Get-Content` output as display-only; verify with a UTF-8-aware diff or parser before using it as source text for edits.
  - Before finishing, verify changed diffs stay valid UTF-8: no replacement characters (`U+FFFD`) and no unexpected Hanja or otherwise garbled text in Korean-only files, confirmed with a UTF-8-aware diff and `git diff --check`.
- Schema creation must use Alembic. Do not use SQLAlchemy `create_all()` for app schema.
- Before merging to main, complete the required security review and resolve all HIGH findings. Run each verification command and record pass/fail in `CHECKLIST.md`.

## Standard Commands

Frontend:

```bash
cd frontend
npm run typecheck
npm test
npm run test:e2e
npm run build
```

Backend:

```bash
cd backend
python -m pytest
alembic upgrade head --sql
```

Compose:

```bash
docker compose -f compose.yaml config
```

## Done Criteria

A task is done only when:

- The implementation matches `docs/mvp-api-contract.md` or that contract was intentionally updated.
- Relevant frontend/backend tests and evals have been updated.
- The required validation commands were run, or a clear blocker is recorded.
- README, env examples, `PLANS.md`, or `CHECKLIST.md` were updated when the task changes usage, setup, API, or workflow.
- Before finishing a task that touches project state, keep `CHECKLIST.md` slim: update only current status, recent validation evidence, and active remaining risks; remove stale historical task logs instead of appending long chronology.
- Update `CHECKLIST.md` when the branch is ready to merge, not while work is in progress. This file records one current state; when several live branches each rewrite `Current Status` and `Recent Validation`, they collide on the same lines every time. Two draft PRs conflicted this way on 2026-09-05 while branches that left the file alone merged clean. Keep branch-specific narrative in the pull request body.
- Validate checklist cleanup with `git diff --check -- CHECKLIST.md` when `CHECKLIST.md` changes.
- When Korean text files are edited, they were verified UTF-8-clean per the Encoding rule in "Non-Negotiable Rules" (no replacement characters, no unexpected garbled Hanja).
- Remaining risks are explicit.
