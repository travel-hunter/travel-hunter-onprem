# CHECKLIST

## Current Status

- Active task/status: G008 existing app path inconsistency 해소 후 mandatory ai-slop-cleaner 검증을 완료했다.
- Completed scope: `docs/deployment-cicd/onprem-dev-parallel-validation-handoff.md`에서 `/home/deploy/travelhunterapp2`가 running project/config path이고 `/home/deploy/travelhunterapp`는 별도 app repo/dirty 확인 대상임을 구분했다. 기존 app stop/up/log 명령은 `/home/deploy/travelhunterapp2`와 `-p travelhunterapp2 -f compose.tunnel.yaml` 기준으로만 실행하도록 명시했다.
- Scope guard: 지정된 문서, 체크리스트, compose 파일만 검토했다. 실제 서버 lifecycle command, 실제 Alembic migration, DB volume 삭제/초기화, secret 변경, dev domain cutover, production 서버 변경, PR merge, commit/push는 실행하지 않았다.

## Latest Validation Evidence

- Compose config: `docker compose --env-file deploy/.env.prod.example -f compose.tunnel.yaml config -q` passed.
- Compose services: `docker compose -p travel-hunter-onprem-dev --env-file deploy/.env.prod.example -f compose.tunnel.yaml config --services` passed and listed `db`, `backend`, `frontend`, `caddy`, `cloudflared`.
- Diff hygiene: scoped `git diff --check` passed.
- UTF-8/U+FFFD scan: scoped files passed with zero replacement characters.
- Forbidden command scans: scoped files contain no forbidden volume-removal or one-off manual migration command.
- Fallback/slop scan: no fallback-like cleanup finding required code or document changes beyond this checklist refresh.
- Self-check: `/home/deploy/travelhunterapp2` usage consistently refers to the running project/config path `/home/deploy/travelhunterapp2/compose.tunnel.yaml`; `/home/deploy/travelhunterapp` is documented only as a separate app repo/dirty confirmation target.

## Remaining Risks

- GitHub HTTPS credentials are still a known server-side risk because clone/fetch failed and the previous validation used a bundle path.
- Actual image build, Alembic migration, compose up, and dev domain cutover remain intentionally unrun.
- Until PR #2 is merged and `develop` is updated, the onprem `develop` branch lacks the cutover target changes.
- `/home/deploy/travelhunterapp` and `/home/deploy/travelhunterapp2` both exist, so operators must stop if `docker compose ls` does not confirm `travelhunterapp2` config path as `/home/deploy/travelhunterapp2/compose.tunnel.yaml` before any existing app stop/up/log command.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
