# CHECKLIST

## Current Status

- Active task/status: Ultragoal G006 final gate의 mandatory ai-slop-cleaner pass를 범위 파일 3개에 대해 완료했다.
- Completed scope: `compose.tunnel.yaml`과 handoff 문서는 동작/의미 보존 기준에서 추가 수정이 필요 없었고, 이 checklist만 현재 cleanup gate 결과로 갱신했다.
- Scope guard: 실제 server command, `docker compose up/down/restart/build`, 실제 Alembic migration, DB volume 삭제/초기화, secret 변경, dev domain cutover, production 서버 변경, PR merge는 실행하지 않았다.

## Latest Validation Evidence

- Compose validation: `docker compose --env-file deploy/.env.prod.example -f compose.tunnel.yaml config -q` passed.
- Diff hygiene: `git diff --check` passed.
- UTF-8/U+FFFD scan for `compose.tunnel.yaml`, `CHECKLIST.md`, and `docs/deployment-cicd/onprem-dev-parallel-validation-handoff.md` passed.
- Destructive command scan found no compose down-with-volumes shorthand in the scoped docs.
- Fallback/slop scan found no masking fallback, DB deletion/init command, secret value output, production-change instruction, unapproved cutover instruction, or obsolete single-app service assumption in the scope.

## Remaining Risks

- GitHub HTTPS credentials are still a known server-side risk because clone/fetch failed and the previous validation used a bundle path.
- Actual image build, Alembic migration, compose up, and dev domain cutover remain intentionally unrun.
- Until PR #2 is merged and `develop` is updated, the onprem `develop` branch lacks the cutover target changes.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
