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
- `/home/deploy/travelhunterapp`의 origin은 `travel-hunter-app.git`이다.
- 기존 repo의 dirty `compose.tunnel.yaml`에는 Alembic 관련 command line이 3개 남아 있다.
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
- [ ] compose project name, volume name, network name이 기존 `travelhunterapp2` stack과 충돌하지 않는지 확인한다.
- [ ] DB backup 또는 snapshot이 확보됐는지 확인한다.
- [ ] 기존 개발서버 running stack의 app-facing 서비스(`cloudflared/caddy/frontend/backend`)를 멈추는 시점과 rollback 판단 기준을 승인받는다.
- [ ] SMTP/OAuth/Kakao/Cloudflare provider 환경값이 현재 개발 도메인 기준과 맞는지 key 단위로만 확인한다.

## 5. Cutover 명령 초안

아래는 별도 승인 후 운영자가 실행할 수 있도록 남기는 초안이다. 지금 실행하지 않는다. secret 값은 출력하지 않는다. DB volume 삭제나 초기화 명령은 포함하지 않는다.

```bash
# 0) 사전 확인: 값 출력 금지, 상태와 key/권한만 확인
cd /home/deploy/travel-hunter-onprem
git status --short
git branch --show-current
git rev-parse HEAD
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml config --services

# 1) 별도 승인 후 기존 개발서버 app-facing 서비스 정지: DB/volume은 건드리지 않음
cd /home/deploy/travelhunterapp2
# 전제: config --services에서 아래 서비스명이 확인되어야 한다.
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml stop cloudflared caddy frontend backend

# 2) 새 온프레미스 DB만 먼저 기동
cd /home/deploy/travel-hunter-onprem
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml up -d db

# 3) Alembic migration 확인 실행
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml run --rm backend python -m alembic upgrade head

# 4) 새 온프레미스 stack 기동
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml up -d

# 5) 로그 확인: secret 값 출력 금지
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 backend
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 caddy
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 cloudflared

# 6) public smoke
curl -fsS https://dev.travel-hunter.co.kr/api/health
curl -fsS https://dev.travel-hunter.co.kr/
curl -fsS https://dev.travel-hunter.co.kr/login
```

주의:

- backend service command가 Alembic을 자동 실행하도록 구성된 경우에도, 위 초안의 별도 migration command는 승인된 cutover 절차에서 idempotent 확인용으로만 사용한다.
- migration 실패, health 실패, login route 실패, provider callback 실패가 발생하면 즉시 rollback 초안을 검토한다.
- `curl` 결과에 secret, token, cookie 값을 붙여 기록하지 않는다.

## 6. Rollback 명령 초안

아래는 별도 승인 후 rollback이 필요할 때의 초안이다. 지금 실행하지 않는다. rollback은 기존 앱 stack을 되살리고 온프레미스 stack을 멈추는 데 한정한다. DB를 파괴적으로 되돌리는 작업은 포함하지 않는다.

```bash
# 1) 온프레미스 app-facing 서비스 정지: DB/volume은 건드리지 않음
cd /home/deploy/travel-hunter-onprem
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml stop cloudflared caddy frontend backend

# 2) 기존 app 배포 stack 복구
cd /home/deploy/travelhunterapp2
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml up -d
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 backend
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 caddy
docker compose --env-file deploy/.env.prod -f compose.tunnel.yaml logs --tail=100 cloudflared

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
- 기존 app repo origin 확인: `/home/deploy/travelhunterapp` origin이 `travel-hunter-app.git`이다.
- dirty compose 확인: 기존 `compose.tunnel.yaml`에 Alembic command line 3개가 남아 있다.
- PR 기준: PR #2 <https://github.com/travel-hunter/travel-hunter-onprem/pull/2>.
- 실행하지 않은 범위: 실제 build, migration, up, domain cutover, DB volume 삭제/init, secret 변경, production 서버 변경.

## 9. 남은 위험

- 서버 GitHub HTTPS credential이 없어 clone/fetch가 실패했고, 이번 검증은 bundle 경로를 사용했다.
- 실제 image build, Alembic migration, compose up은 실행하지 않았다.
- PR #2가 merge되기 전까지 온프레미스 `develop`에는 cutover 대상 변경이 없다.
- 기존 dirty `compose.tunnel.yaml`의 Alembic command line 3개가 운영자 판단을 혼동시킬 수 있다.
- compose project, volume, network 이름 충돌은 cutover 전 실제 서버 상태로 다시 확인해야 한다.
- DB backup/snapshot이 확인되기 전에는 migration을 실행하면 안 된다.
- SMTP/OAuth smoke는 provider env가 준비되지 않으면 완료 판정할 수 없다.
