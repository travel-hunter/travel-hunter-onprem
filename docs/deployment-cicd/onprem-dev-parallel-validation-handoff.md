# 온프레미스 개발 서버 병렬 검증 인수인계

작성일: 2026-07-18
대상 환경: 개발 도메인 `dev.travel-hunter.co.kr` 전환 후보
범위: 온프레미스 repo 병렬 검증 결과, 전환/롤백 명령 초안, 검증 근거, 남은 위험 기록
상태: 실제 cutover는 별도 승인 전까지 실행 금지

## 1. 요약

`feature/deploy-alembic-onprem-hardening` 작업은 기존 개발 서버 stack을 보존한 상태에서 온프레미스 repo를 병렬 검증하는 데 초점을 맞췄다. 현재 운영 중인 기존 개발서버 running stack과 기존 app 배포는 그대로 두고, `/home/deploy/travel-hunter-onprem` 쪽에서 compose/Alembic 전환 가능성만 확인했다.

이번 문서는 실행 지시서가 아니라 handoff 문서다. `dev.travel-hunter.co.kr`를 새 온프레미스 stack으로 넘기는 cutover, 기존 앱 중지, DB 볼륨 삭제 또는 초기화, secret 변경, production 서버 변경, PR merge는 모두 별도 승인 대상이다.

## 2. 현재 확인된 사실

- 기존 개발서버 running stack `travelhunterapp2` 및 기존 app 배포는 보존되어 있다.
- 서버에서 `docker compose ls`로 확인한 running project는 `travelhunterapp2`이며, running config path는 `/home/deploy/travelhunterapp2/compose.tunnel.yaml`이다.
- `/home/deploy/travelhunterapp2`는 `travel-hunter-app.git` repo이고 `develop...origin/develop`, HEAD `ad3d7d94e29f32a304aa0719f8b226b98567b72e`이며, `.github/workflows/ci.yml` 삭제 상태가 dirty로 남아 있다.
- `/home/deploy/travelhunterapp`도 존재하지만 running stack config path가 아니다. 이 경로는 별도 `travel-hunter-app.git` repo이고 `develop...origin/develop`, HEAD `ad3d7d94e29f32a304aa0719f8b226b98567b72e`이며, `compose.tunnel.yaml` 수정 상태가 dirty로 남아 있다.
- 두 기존 app repo 모두 `compose.tunnel.yaml` 파일을 가지고 있으므로, 기존 app stack에 대한 cutover/rollback 명령은 running config path인 `/home/deploy/travelhunterapp2/compose.tunnel.yaml`와 명시 project name `travelhunterapp2`를 기준으로만 실행해야 한다.
- `/home/deploy/travel-hunter-onprem`은 clean 상태로 검증됐고, 기준은 `develop` HEAD `0114b0b40f934716543d8df9bdae91831d064549`이다.
- 온프레미스 변경은 PR #2에 올라가 있다: <https://github.com/travel-hunter/travel-hunter-onprem/pull/2>
- GitHub HTTPS credential이 없어 서버에서 clone/fetch가 실패했고, 검증에는 bundle 경로를 사용했다.
- 실제 image build, migration 실행, 새 stack 기동, 개발 도메인 cutover는 수행하지 않았다.

## 3. 별도 승인 대상과 금지 사항

다음 작업은 이 handoff만으로 실행하면 안 된다.

- 기존 app 배포 중지.
- `dev.travel-hunter.co.kr` 개발 도메인 cutover.
- DB volume 삭제 또는 DB init.
- secret, token, password, OAuth, SMTP, tunnel 값 변경.
- production 서버 또는 production 도메인 변경.
- PR #2 merge.

특히 DB volume을 삭제하거나 초기화하는 명령은 전환 초안에 포함하지 않는다. rollback도 destructive DB rollback을 기본값으로 두지 않는다.

## 4. Pre-cutover 체크리스트

cutover 승인 전 아래 항목을 먼저 확인한다.

- [ ] PR #2를 merge하고 `develop`을 최신화한다.
- [ ] 서버의 온프레미스 repo에서 `origin` fetch/pull이 되는지 확인한다.
  - credential 문제가 계속 있으면 GitHub HTTPS credential을 해결하거나, 승인된 bundle/아티팩트 경로를 다시 사용한다.
- [ ] `deploy/.env.prod`는 key 존재 여부와 파일 권한만 확인한다.
  - 값은 출력하지 않는다.
  - 권장 권한은 소유자만 읽고 쓸 수 있는 설정이다.
- [ ] `docker compose ls`로 기존 app stack과 온프레미스 후보 stack의 project name, config path, 상태를 확인한다.
- [ ] `docker compose ls`에서 `travelhunterapp2`의 config path가 `/home/deploy/travelhunterapp2/compose.tunnel.yaml`인지 확인하지 못하면 즉시 중단한다.
- [ ] `/home/deploy/travelhunterapp`는 별도 app repo/dirty 확인 대상일 뿐 running stack config path가 아니므로, 기존 app stop/up/log 명령의 작업 경로로 사용하지 않는다.
- [ ] 온프레미스 전환 명령은 명시 project name `travel-hunter-onprem-dev`를 사용하고, 기존 app stack 명령은 `/home/deploy/travelhunterapp2`에서 `-p travelhunterapp2 -f compose.tunnel.yaml`로만 실행한다.
- [ ] compose project name, volume name, network name이 기존 `travelhunterapp2` stack과 충돌하지 않는지 확인한다.
- [ ] DB backup 또는 snapshot이 확보됐는지 확인한다.
- [ ] 기존 개발서버 running stack의 app-facing 서비스(`cloudflared/caddy/frontend/backend`)를 멈추는 시점과 rollback 판단 기준을 승인받는다.
- [ ] SMTP/OAuth/Kakao/Cloudflare provider 환경값이 현재 개발 도메인 기준과 맞는지 key 단위로만 확인한다.

## 5. Cutover 명령 초안

아래는 별도 승인 후 운영자가 실행할 수 있도록 남기는 초안이다. 지금 실행하지 않는다. secret 값은 출력하지 않는다. DB volume 삭제나 초기화 명령은 포함하지 않는다.

```bash
# 0) 사전 확인: 값 출력 금지, 상태와 key/권한/project identity만 확인
docker compose ls

# docker compose ls에서 running project travelhunterapp2의 config path가
# /home/deploy/travelhunterapp2/compose.tunnel.yaml로 확인되지 않으면 중단한다.
# /home/deploy/travelhunterapp는 별도 app repo/dirty 확인 대상이며, running stack config path가 아니다.

cd /home/deploy/travel-hunter-onprem
git status --short
git branch --show-current
git rev-parse HEAD
docker compose -p travel-hunter-onprem-dev --env-file deploy/.env.prod -f compose.tunnel.yaml config --services

cd /home/deploy/travelhunterapp2
docker compose -p travelhunterapp2 --env-file deploy/.env.prod -f compose.tunnel.yaml config --services

# 위 docker compose ls/config 출력에서 기존 app project name이 travelhunterapp2이고,
# config path가 /home/deploy/travelhunterapp2/compose.tunnel.yaml인지 확인한 뒤 다음 단계로 진행한다.
# 확인하지 못하면 wrong-stack 위험이 있으므로 stop/up/log 명령을 실행하지 않는다.

# 1) 별도 승인 후 기존 개발서버 app-facing 서비스 정지: DB/volume은 건드리지 않음
cd /home/deploy/travelhunterapp2
# 전제: config --services에서 아래 서비스명이 확인되어야 한다.
docker compose -p travelhunterapp2 --env-file deploy/.env.prod -f compose.tunnel.yaml stop cloudflared caddy frontend backend

# 2) 새 온프레미스 DB만 먼저 기동
cd /home/deploy/travel-hunter-onprem
docker compose -p travel-hunter-onprem-dev --env-file deploy/.env.prod -f compose.tunnel.yaml up -d db

# 3) 새 온프레미스 backend 기동
# compose backend command가 "python -m alembic upgrade head && exec uvicorn ..." 순서로 실행한다.
# migration의 단일 authoritative entrypoint는 backend startup command다. 별도 manual migration command는 실행하지 않는다.
docker compose -p travel-hunter-onprem-dev --env-file deploy/.env.prod -f compose.tunnel.yaml up -d backend

# 4) backend health/log와 migration 현재 revision 진단: 진단만 수행하고 migration은 재실행하지 않음
docker compose -p travel-hunter-onprem-dev --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 backend
docker compose -p travel-hunter-onprem-dev --env-file deploy/.env.prod -f compose.tunnel.yaml exec backend python -m alembic current
docker compose -p travel-hunter-onprem-dev --env-file deploy/.env.prod -f compose.tunnel.yaml exec backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"

# 5) frontend/caddy/cloudflared 기동
docker compose -p travel-hunter-onprem-dev --env-file deploy/.env.prod -f compose.tunnel.yaml up -d frontend caddy cloudflared

# 6) 로그 확인: secret 값 출력 금지
docker compose -p travel-hunter-onprem-dev --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 caddy
docker compose -p travel-hunter-onprem-dev --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 cloudflared

# 7) public smoke
curl -fsS https://dev.travel-hunter.co.kr/api/health
curl -fsS https://dev.travel-hunter.co.kr/
curl -fsS https://dev.travel-hunter.co.kr/login
```

주의:

- backend service command가 Alembic과 uvicorn을 순서대로 실행한다. migration 확인이 필요하면 `alembic current` 같은 진단 명령만 사용한다.
- migration 실패, health 실패, login route 실패, provider callback 실패가 발생하면 즉시 rollback 초안을 검토한다.
- `curl` 결과에 secret, token, cookie 값을 붙여 기록하지 않는다.

## 6. Rollback 명령 초안

아래는 별도 승인 후 rollback이 필요할 때의 초안이다. 지금 실행하지 않는다. rollback은 기존 앱 stack을 되살리고 온프레미스 stack을 멈추는 데 한정한다. DB를 파괴적으로 되돌리는 작업은 포함하지 않는다.

```bash
# 0) rollback 전 wrong-stack 방지 확인: project name과 config path를 먼저 확인
docker compose ls

# docker compose ls에서 running project travelhunterapp2의 config path가
# /home/deploy/travelhunterapp2/compose.tunnel.yaml로 확인되지 않으면 중단한다.
# /home/deploy/travelhunterapp는 별도 app repo/dirty 확인 대상이며, running stack config path가 아니다.

cd /home/deploy/travel-hunter-onprem
docker compose -p travel-hunter-onprem-dev --env-file deploy/.env.prod -f compose.tunnel.yaml config --services

cd /home/deploy/travelhunterapp2
docker compose -p travelhunterapp2 --env-file deploy/.env.prod -f compose.tunnel.yaml config --services

# 위 docker compose ls/config 출력에서 기존 app project name이 travelhunterapp2이고,
# config path가 /home/deploy/travelhunterapp2/compose.tunnel.yaml인지 확인한 뒤 다음 단계로 진행한다.
# 확인하지 못하면 wrong-stack 위험이 있으므로 stop/up/log 명령을 실행하지 않는다.

# 1) 온프레미스 app-facing 서비스 정지: DB/volume은 건드리지 않음
cd /home/deploy/travel-hunter-onprem
docker compose -p travel-hunter-onprem-dev --env-file deploy/.env.prod -f compose.tunnel.yaml stop cloudflared caddy frontend backend

# 2) 기존 app 배포 stack 복구
cd /home/deploy/travelhunterapp2
docker compose -p travelhunterapp2 --env-file deploy/.env.prod -f compose.tunnel.yaml up -d
docker compose -p travelhunterapp2 --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 backend
docker compose -p travelhunterapp2 --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 caddy
docker compose -p travelhunterapp2 --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 cloudflared

# 3) rollback smoke
curl -fsS https://dev.travel-hunter.co.kr/api/health
curl -fsS https://dev.travel-hunter.co.kr/
curl -fsS https://dev.travel-hunter.co.kr/login
```

DB migration rollback은 자동으로 가정하지 않는다. 데이터 손실 가능성이 있으면 backup restore 또는 별도 downgrade 계획을 먼저 승인받아야 한다.

## 7. Smoke 목록

cutover 또는 rollback 후 최소 smoke는 다음과 같다.

- `GET https://dev.travel-hunter.co.kr/api/health`
- `GET https://dev.travel-hunter.co.kr/`
- `GET https://dev.travel-hunter.co.kr/login`
- 회원가입 verify 흐름.
- 로그인 성공/실패 메시지.
- 정책 목록과 정책 상세.
- 여행 목록과 여행 상세.
- SMTP password reset smoke.
- Google/Kakao OAuth callback smoke.

SMTP와 OAuth smoke는 provider env가 준비된 경우에만 수행한다. provider 비밀번호, secret, token, cookie는 파일, 채팅, 로그, 문서에 남기지 않는다.

## 8. 검증 근거

- 온프레미스 repo clean 기준: `/home/deploy/travel-hunter-onprem` `develop` HEAD `0114b0b40f934716543d8df9bdae91831d064549`.
- 기존 running stack 보존: 기존 개발서버 running stack `travelhunterapp2` 및 기존 app 배포를 멈추지 않은 상태로 병렬 검증했다.
- 기존 running stack identity: `docker compose ls`에서 project `travelhunterapp2`, config path `/home/deploy/travelhunterapp2/compose.tunnel.yaml`로 확인됐다.
- 기존 app repo 확인: `/home/deploy/travelhunterapp2`와 `/home/deploy/travelhunterapp` 모두 `travel-hunter-app.git` repo이며 HEAD는 `ad3d7d94e29f32a304aa0719f8b226b98567b72e`다.
- dirty 상태 구분: `/home/deploy/travelhunterapp2`는 `.github/workflows/ci.yml` 삭제 상태, `/home/deploy/travelhunterapp`는 `compose.tunnel.yaml` 수정 상태다. `/home/deploy/travelhunterapp`는 running stack config path가 아니라 별도 app repo/dirty 확인 대상이다.
- PR 기준: PR #2 <https://github.com/travel-hunter/travel-hunter-onprem/pull/2>.
- 실행하지 않은 범위: 실제 build, migration, up, domain cutover, DB volume 삭제/init, secret 변경, production 서버 변경.

## 9. 남은 위험

- 서버 GitHub HTTPS credential이 없어 clone/fetch가 실패했고, 이번 검증은 bundle 경로를 사용했다.
- 실제 image build, Alembic migration, compose up은 실행하지 않았다.
- PR #2가 merge되기 전까지 온프레미스 `develop`에는 cutover 대상 변경이 없다.
- `/home/deploy/travelhunterapp`와 `/home/deploy/travelhunterapp2`가 모두 존재하므로, 기존 app stack 조작 전에 running config path가 `/home/deploy/travelhunterapp2/compose.tunnel.yaml`인지 확인하지 못하면 중단해야 한다.
- compose project, volume, network 이름 충돌과 config path 오인은 cutover 전 실제 서버 상태와 `docker compose ls`로 다시 확인해야 한다.
- DB backup/snapshot이 확인되기 전에는 migration을 실행하면 안 된다.
- SMTP/OAuth smoke는 provider env가 준비되지 않으면 완료 판정할 수 없다.
