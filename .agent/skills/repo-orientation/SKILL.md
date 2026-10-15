---
name: repo-orientation
description: Use when the user says "repo orientation" or "/repo", right after a PR is merged, when resuming Travel Hunter work, or before starting non-trivial work.
---

# Repo Orientation

## Overview

Start from the actual repository, runtime, and server state instead of memory. This is a read-only check that ends with a report and a question about the next task. `git fetch` is allowed (it only updates remote refs). Anything that changes files, branches, containers, data, or servers is proposed, never done.

## Checklist (run all; record what you could not check)

1. **Sources** - read `AGENTS.md`, the nested `AGENTS.md` for the target area, `PLANS.md`, `CHECKLIST.md` top sections. Authoritative docs: `docs/requirements.md`, `docs/implemented-feature-spec.md`, `docs/next-work-plan.md`, `docs/mvp-api-contract.md`. Local procedure: `.codex/local-workflow.md`.
2. **develop** - `git fetch origin --prune`; `git log --oneline -5 origin/develop`.
3. **Recent merges** - for the PR the user just merged (or the latest merged PRs): `gh pr view <n> --json state,mergeCommit`, and confirm each of its commits with `git merge-base --is-ancestor <sha> origin/develop`.
4. **Open PRs** - `gh pr list --state open`.
5. **Worktrees** - `git worktree list`; classify each branch: merged into `origin/develop` / commits not in develop (count) / dirty files. Root checkout: branch and `git status --short` count. Never treat `develop`, `main`, `ci/prod-jenkins` or backup branches as cleanup targets.
6. **CHECKLIST freshness** - does `Current Status` mention every PR merged since it was last updated? List missing PRs.
7. **Local runtime** - `com.docker.compose.project.working_dir` of `travel-hunter-onprem-{db,backend,frontend}-1` (all three must match one worktree); `http://127.0.0.1:8000/api/health`, `:4173`, `:5173`; which branch/commit that worktree is on.
8. **Local vs dev server** - frontend: compare `/assets/index-*.css` names from `https://dev.travel-hunter.co.kr/` and `http://127.0.0.1:4173/` (JS hashes always differ - ignore them); backend: byte-compare `/openapi.json` from both; DB: local `alembic current` inside the backend container. Server DB checks only with user approval.
9. **Pending server work** - deploy-time items listed in `CHECKLIST.md` Active Risks (review-queue approvals, data migrations, one-off server SQL).

## Report (Korean, in this order)

1. develop 과 방금 머지된 PR 확인 결과
2. 열린 PR · 워크트리 분류 · 루트 상태
3. CHECKLIST 최신 여부
4. 로컬 런타임 출처와 개발서버 버전 비교(같음/다름, 근거)
5. 남은 서버 작업
6. 하지 못한 점검과 이유

Then ask the next task with options, recommended first. Include these when they apply:
- **CHECKLIST 맞추기** when step 6 found missing PRs.
- **로컬을 개발서버에 맞추기** when step 8 differs: rebuild backend/frontend from `origin/develop` in a worktree (`docker compose --env-file <repo>/.env -p travel-hunter-onprem -f compose.local.yaml build backend frontend` then `up -d --no-deps`), `alembic upgrade head`, then copy policy data with the out-of-repo script `D:/travel-hunter-tools/sync-local-policies-from-dev.sh <db container>` (needs matching alembic versions).
- **머지된 워크트리 정리** (remove the `frontend/node_modules` junction with `rmdir` first).

## Common Mistakes

- Skipping `git fetch` as "not read-only" - the report is then stale.
- Comparing JS bundle hashes to decide drift.
- Reading `docs/current-work-spec.md` - it no longer exists.
- Printing `.env` values or using `docker compose config` / `docker inspect` without filters.
