# CHECKLIST

## Current Status

- Active task/status: Ultragoal `G004-alembic-yaml` Alembic 자동 마이그레이션 compose 반영을 완료했다.
- Completed scope: `feature/deploy-alembic-onprem-hardening`에서 `compose.tunnel.yaml` backend service가 DB health 이후 `python -m alembic upgrade head`를 실행한 뒤 uvicorn을 시작하도록 최소 변경했다.
- Scope guard: source 변경은 `compose.tunnel.yaml`과 이 checklist에 한정했다. 실제 `docker compose up/down/restart/build`, 실제 `alembic upgrade`, DB volume 삭제/초기화, cloudflared/caddy 공개 dev 도메인 전환은 실행하지 않았다.

## Latest Validation Evidence

- Local compose validation: `docker compose --env-file deploy/.env.tunnel.example -f compose.tunnel.yaml config -q` passed.
- Server env compatibility validation: temporary `/tmp/travel-hunter-onprem-compose-g004.yaml` with `/home/deploy/travelhunterapp/deploy/.env.prod` and `--project-directory /home/deploy/travel-hunter-onprem` ran `config -q` and passed.
- Server running stack check: only `travelhunterapp2` remains running, with config `/home/deploy/travelhunterapp2/compose.tunnel.yaml`.
- Static command check: `compose.tunnel.yaml` contains `python -m alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- Diff hygiene: `git diff --check -- compose.tunnel.yaml CHECKLIST.md` passed.
- UTF-8/U+FFFD scan for `compose.tunnel.yaml` and `CHECKLIST.md` passed.

## Remaining Risks

- Actual image build and Alembic migration execution remain intentionally unrun for this goal; readiness is proven by compose config and static command/file checks only.
- Server GitHub HTTPS credentials issue is handled by the G003 bundle fallback path rather than direct server-side git fetch/pull.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
