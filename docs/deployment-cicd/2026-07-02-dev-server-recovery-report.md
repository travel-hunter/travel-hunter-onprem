# 개발 서버 접속 장애 복구 보고서

작성일: 2026-07-02
대상 환경: 개발 서버 `dev.travel-hunter.co.kr`
범위: 정책 수집 실행 이전의 서버 접속 장애 확인 및 복구 과정

## 1. 요약

2026-07-02 개발 서버 `https://dev.travel-hunter.co.kr/` 접속 시 Cloudflare `530` 오류가 발생했다. 확인 결과 애플리케이션 빌드 자체가 실패한 것이 아니라, 개발 서버 실행 구성이 문서화된 Cloudflare Tunnel 배포 구성과 달라져 있었다.

복구 전 서버는 `compose.yaml` 기준으로 `frontend`, `backend`, `db`만 실행 중이었다. 개발 도메인 접속에 필요한 `caddy`와 `cloudflared`가 실행 중이지 않았고, 서버 runtime 환경 파일 `deploy/.env.prod`도 현재 repo 위치에 없었다. 이로 인해 Cloudflare가 개발 서버의 origin 서비스로 정상 연결하지 못해 530 오류가 발생한 것으로 판단했다.

복구는 문서 기준 배포 형태인 `compose.tunnel.yaml` stack으로 되돌리는 방식으로 진행했다. 서버 repo를 `develop@a6140e2`로 정렬하고, recovery env를 `deploy/.env.prod`로 복원한 뒤, `db/backend/frontend/caddy/cloudflared` stack을 다시 빌드·기동했다. 이후 `https://dev.travel-hunter.co.kr/`, `/login`, `/api/health` 및 seed 계정 기반 핵심 화면 smoke가 정상 통과했다.

## 2. 최초 증상

다음 public URL에서 Cloudflare 530 오류가 확인됐다.

- `https://dev.travel-hunter.co.kr/`
- `https://dev.travel-hunter.co.kr/api/health`
- `https://dev.travel-hunter.co.kr/login`

Cloudflare 530은 Cloudflare가 origin 서버와 정상적으로 통신하지 못할 때 나타나는 오류다. 따라서 단순 프론트엔드 화면 문제라기보다, Cloudflare Tunnel 또는 origin 연결 구성을 우선 점검했다.

## 3. 확인된 서버 상태

점검 당시 개발 서버 상태는 다음과 같았다.

| 항목 | 문서 기준 | 실제 확인 상태 |
| --- | --- | --- |
| 서버 repo 경로 | `/home/deploy/travel-hunter-app` | `/home/deploy/travelhunterapp` |
| 서버 branch | `develop` | `master@a6140e2` |
| remote 기준 | `origin/develop` | `origin/develop@a6140e2`와 동일 SHA |
| 실행 compose | `compose.tunnel.yaml` | `compose.yaml` |
| 실행 서비스 | `db/backend/frontend/caddy/cloudflared` | `db/backend/frontend` |
| runtime env | `deploy/.env.prod` | active repo에 없음 |
| public 접속 | 정상이어야 함 | Cloudflare 530 |

추가로 서버 Docker build를 확인한 결과, 빌드 자체는 통과했다. 따라서 원인을 “애플리케이션 빌드 실패”가 아니라 “개발 도메인용 tunnel 배포 구성 이탈”로 분류했다.

## 4. 원인 판단

주요 원인은 세 가지였다.

1. **Cloudflare Tunnel stack 미실행**
   개발 도메인은 `cloudflared`가 Cloudflare와 tunnel을 맺고, `caddy`가 내부 `frontend/backend`로 reverse proxy하는 구성이 필요하다. 그러나 당시 서버는 `compose.yaml`로 실행되어 `caddy`와 `cloudflared`가 없었다.

2. **runtime env 파일 부재**
   `compose.tunnel.yaml` 실행에 필요한 `deploy/.env.prod`가 active repo 위치에 없었다. 이 파일에는 DB 연결, 앱 public URL, CORS, OAuth, Cloudflare tunnel token 등 개발 서버 runtime 설정이 들어가며, 값은 출력하거나 commit하면 안 된다.

3. **문서와 실제 서버 경로/branch 불일치**
   문서에는 `/home/deploy/travel-hunter-app`, `develop` 기준으로 되어 있었으나, 실제 서버는 `/home/deploy/travelhunterapp`, `master@a6140e2`였다. 다만 `a6140e2`는 `origin/develop`과 동일 SHA였으므로 코드 내용 자체는 remote develop과 맞았다.

## 5. 복구 과정

복구는 데이터 삭제 없이 진행했다. secret 값은 출력하지 않았고, production 도메인 `travel-hunter.co.kr` 설정은 변경하지 않았다.

### 5.1 복구 전 백업

서버 변경 전 다음 정보를 `/home/deploy/.travel-hunter-recovery/20260702T050921Z-pre-tunnel-restore` 아래에 기록했다.

- 서버 metadata
- git 상태
- branch/SHA
- Docker container 목록
- Docker volume 목록
- env 파일 key 목록 및 권한 정보

비밀값은 저장하거나 출력하지 않고, 필요한 경우 key 이름과 파일 권한만 확인했다.

### 5.2 repo 기준 정렬

서버 repo를 `develop@a6140e2`로 정렬했다.

- 복구 전: local `master@a6140e2`
- 복구 후: `develop@a6140e2`, `origin/develop` tracking

이 조치로 문서상 개발 서버 기준 branch와 실제 서버 branch를 맞췄다.

### 5.3 runtime env 복원

기존 recovery 디렉터리에 보관되어 있던 env 파일을 active repo의 `deploy/.env.prod`로 복원했다.

- 복원 위치: `/home/deploy/travelhunterapp/deploy/.env.prod`
- 권한: `600`
- 값 출력: 하지 않음

이후 `compose.tunnel.yaml` 기준 서비스 구성이 `db`, `backend`, `frontend`, `caddy`, `cloudflared`로 정상 해석되는지 확인했다.

### 5.4 tunnel stack 빌드

`compose.tunnel.yaml` 기준으로 backend/frontend 이미지를 빌드했다.

- backend image build 통과
- frontend production build 통과
- frontend build 과정에서 `npm run typecheck && vite build` 실행 확인

이 단계에서 빌드 실패는 확인되지 않았다.

### 5.5 DB 연결 정렬 및 migration

복구 중 Alembic migration 실행 시 DB 인증 오류가 한 차례 발생했다. 원인은 현재 compose project의 DB user password와 복원된 `DATABASE_URL` password가 일치하지 않는 상태였다.

DB volume 삭제나 초기화는 하지 않았다. 대신 기존 DB user password를 복원된 `DATABASE_URL` 기준으로 맞춘 뒤 SQLAlchemy 연결 smoke를 재확인했다.

그 후 Alembic migration을 실행했고 정상 완료됐다.

### 5.6 seed 실행

복구된 DB는 비어 있는 상태였다.

확인된 초기 count:

- users: 0
- policies: 0
- trips: 0

개발 서버 smoke에 필요한 기본 계정과 화면 데이터를 확보하기 위해 seed를 실행했다. 실행 후 다음 count를 확인했다.

- users: 3
- policies: 16
- trips: 1

### 5.7 tunnel stack 기동

최종적으로 `compose.tunnel.yaml` stack을 기동했다.

실행 서비스:

- `db`
- `backend`
- `frontend`
- `caddy`
- `cloudflared`

Cloudflared 로그에서 `dev.travel-hunter.co.kr` hostname 설정을 수신하고 tunnel connection이 등록된 것을 확인했다.

## 6. 복구 검증 결과

복구 후 다음 smoke를 확인했다.

| 검증 항목 | 결과 |
| --- | --- |
| `https://dev.travel-hunter.co.kr/` | 200 HTML |
| `https://dev.travel-hunter.co.kr/login` | 200 HTML |
| `https://dev.travel-hunter.co.kr/api/health` | 200, `database=connected` |
| seed 계정 로그인 | 성공 |
| `/api/policies` | 200 |
| 정책 상세 API | 200 |
| `/api/trips` | 200 |
| 여행 상세 API | 200 |
| `/home` | 200 HTML |
| `/policies` | 200 HTML |
| 정책 상세 route | 200 HTML |
| `/trips` | 200 HTML |
| 여행 상세 route | 200 HTML |
| backend/caddy/cloudflared 반복 오류 | 없음 |

Cloudflared에는 UDP receive-buffer warning이 있었지만, tunnel 등록과 public smoke는 정상 통과했다.

## 7. 현재 상태

현재 개발 서버는 다음 상태다.

- 서버: `deploy@192.168.32.15`
- hostname: `dev-server`
- repo: `/home/deploy/travelhunterapp`
- branch/SHA: `develop@a6140e2`
- compose: `compose.tunnel.yaml`
- runtime env: `/home/deploy/travelhunterapp/deploy/.env.prod`
- public domain: `https://dev.travel-hunter.co.kr`
- 실행 stack: `db/backend/frontend/caddy/cloudflared`

개발 도메인 접속과 핵심 smoke는 정상화됐다.

## 8. 남은 리스크 및 후속 조치

1. **로컬 미배포 커밋 존재**
   로컬 `develop@3fa274e`는 `origin/develop@a6140e2`보다 1커밋 앞서 있다. 이 커밋은 현재 개발 서버에 배포되지 않았다. 배포가 필요하면 별도 push/merge 후 서버 반영이 필요하다.

2. **이전 compose project 잔여물 존재**
   예전 `travel-hunter-app_*` stopped containers와 `travel-hunter-app_travelhunter-db` volume이 남아 있다. 이번 복구에서는 데이터 손실 위험을 피하기 위해 삭제하지 않았다. 정리가 필요하면 별도 백업/삭제 계획이 필요하다.

3. **env 복원본 사용**
   `deploy/.env.prod`는 recovery material에서 복원했다. 값은 출력하지 않았지만, 장기 운영 관점에서는 secret rotation 여부를 검토할 수 있다.

4. **선택 smoke 미실행**
   Google/Kakao OAuth, SMTP 실제 수신, Kakao Maps/Local provider smoke, admin bearer route smoke, full e2e는 이번 복구 범위에서 제외했다.

5. **운영 도메인 변경 없음**
   production 도메인 `travel-hunter.co.kr` 관련 설정은 변경하지 않았다.

## 9. 커뮤니케이션용 결론

이번 장애는 애플리케이션 코드나 빌드 실패가 아니라, 개발 서버 실행 구성이 Cloudflare Tunnel 배포 기준에서 벗어나 발생한 접속 장애였다. 개발 도메인에 필요한 `caddy`와 `cloudflared`가 실행되지 않았고, runtime env 파일도 active repo 위치에 없어 Cloudflare가 origin 서비스에 연결하지 못했다.

복구는 서버를 문서 기준 tunnel stack으로 되돌리는 방식으로 진행했다. repo branch를 `develop` 기준으로 맞추고, runtime env를 복원했으며, tunnel compose stack을 빌드·기동했다. DB는 삭제하지 않고 연결 정보를 정렬한 뒤 migration과 seed를 수행했다. 이후 개발 도메인, API health, 로그인, 정책/여행 핵심 화면 smoke가 정상 통과했다.
