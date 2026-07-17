# CHECKLIST

## Current Status

- Active task/status: G007 architect WATCH 해소 변경 후 mandatory ai-slop-cleaner 재검증을 완료했다.
- Completed scope: `docs/deployment-cicd/onprem-dev-parallel-validation-handoff.md`, `compose.tunnel.yaml`, `CHECKLIST.md`에서 manual migration, destructive command, wrong-stack, secret 노출, 승인 없는 cutover/rollback 문구를 재점검했다. `CHECKLIST.md`는 최신 검증 근거만 남기도록 유지했다.
- Scope guard: 실제 서버 lifecycle 명령, 실제 Alembic migration, DB volume 삭제/초기화, secret 변경, dev domain cutover, production 서버 변경, PR merge는 실행하지 않았다.

## Latest Validation Evidence

- Compose validation: `docker compose --env-file deploy/.env.prod.example -f compose.tunnel.yaml config -q` passed.
- Compose services: `docker compose -p travel-hunter-onprem-dev --env-file deploy/.env.prod.example -f compose.tunnel.yaml config --services` passed and listed `db`, `backend`, `frontend`, `caddy`, `cloudflared`.
- Diff hygiene: `git diff --check` passed.
- UTF-8/U+FFFD scan for all scoped files passed with zero replacement characters.
- Destructive command scan passed for volume-removal, DB-drop, env-print, and secret-echo patterns.
- Migration command scan passed: no manual run command remains; the remaining migration phrase is confined to the backend startup command and its handoff explanation.

## Remaining Risks

- GitHub HTTPS credentials are still a known server-side risk because clone/fetch failed and the previous validation used a bundle path.
- Actual image build, Alembic migration, compose up, and dev domain cutover remain intentionally unrun.
- Until PR #2 is merged and `develop` is updated, the onprem `develop` branch lacks the cutover target changes.
- Compose project/config path checks reduce wrong-stack risk, but operators must still confirm live server `docker compose ls` output before any stop/up command.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
