# CHECKLIST

## Current Status

- Merge-ready: 역추적용 구조화 로그의 영구 보존. 로그를 컨테이너 수명에서 분리해 재배포·재부팅 후에도 남긴다(`feature/durable-logs`).
- Scope: 백엔드 로깅 설정(파일 핸들러 병행), Caddy 접근 로그 파일 출력, compose 로그 볼륨 `travelhunter-logs`, 조회 스크립트 `scripts/trace.py`·래퍼. API 계약·DB 스키마 변경 없음.

## Recent Validation

- PASS: backend full suite 1,125 passed, 19 skipped(Linux 백엔드 이미지). 로그 관련 112 passed(trace.py 50, 요청 로그 35, 디버그 캡처 27).
- BASELINE: Windows 호스트 venv 에서는 `test_stay_discount_semantics_snapshot.py::test_restricted_atomic_artifact_and_sidecar_round_trip` 1건이 임시 폴더 ACL 검사로 실패한다. 손대지 않은 develop 에서도 동일.
- PASS: 결함 되돌리기(변이) 확인 — `--since` 무시, Caddy 회전 파일명, 읽기 실패의 빈 결과, 3.12 전용 f-string, 셸 문자 파일명, 메시지 없는 목록 실패, U+2028 줄 분리, 요약의 시각 없는 레코드, 잘린 첫 줄 버리기를 각각 다시 심으면 해당 테스트가 실패한다.
- PASS: `trace.py` Python 3.11 파싱(python:3.11 컨테이너), Caddy validate(두 파일), compose config(두 파일), `git diff --check`, 변경 파일 U+FFFD·제어문자 0건.
- PASS: 재부팅 후 볼륨 로그 보존 — 9/23 기록이 9/28 재기동 후에도 조회됨. `docker logs` 에는 없음.
- BASELINE: frontend vitest 2건(`home.test.tsx`, `trip-create.test.tsx`)은 손대지 않은 develop 에서도 동일하게 실패. 이 브랜치는 프런트 변경 없음.
- NOT RUN: 개발서버 `--dev` 조회 — SSH 연결 시간 초과로 미확인.

## Active Risks

### 역추적 로그(`feature/durable-logs`)

- **`docker compose down -v` 금지.** `-v` 가 `travelhunter-logs` 볼륨을 DB 와 함께 지워 로그 이력이 사라진다. 운영·개발서버에서는 `down` 만 쓴다.
- Caddy 접근 로그는 파일로만 간다(Caddy 는 한 곳에만 쓸 수 있다). Dozzle·`docker logs caddy` 에는 기동·오류 줄만 보인다. 엣지 기록은 `scripts/trace.py` 로 본다.
- `RotatingFileHandler` 는 다중 프로세스 안전하지 않다. 지금은 uvicorn 워커 1개다. 워커를 늘리면 회전이 경합하므로 그때 핸들러를 바꿔야 한다.
- 개발서버에서 `trace.py --dev` 실동작을 확인하지 못했다(SSH 시간 초과). 배포 후 재확인 필요.
- 회전본 읽기 파이프라인에 `pipefail` 이 없다(백엔드 `sh` 는 dash). 목록 조회와 읽기 사이에 회전이 일어나면 그 파일을 건너뛰거나 두 번 읽을 수 있다. 일시적이다.
- `LOG_FILE_MAX_MB=0` 이면 백엔드 로그 파일이 회전하지 않고 커진다. 값 검증이 없다.

### #54 운영 DB 이전

- Kakao 소셜연결은 앱별 사용자 ID 체계 때문에 이전하지 않고 2건을 삭제했다. 최초 Kakao 로그인 시 검증 이메일 경로(`backend/app/services/oauth.py:310`)로 자동 재연결되어야 하며, 자동 연결이 실패하면 플레이스홀더 계정이 새로 생성된다. 브라우저 스모크로 반드시 확인할 것.
- 활성 정책 139건 중 87건의 마감일이 `2026-08-31` 이다. 목록은 `status='active'` 로만 필터링하고 `end_date` 를 보지 않으므로(`backend/app/repositories/policies.py:9`) 만료 후에도 지난 마감일이 그대로 노출된다.
- 수집 스케줄러가 개발/운영 모두 비활성이다. 운영 관리자 승격으로 수동 실행 경로는 열렸으나, 자동 갱신 활성화 여부와 임계값 조정은 미결이다. 현재 `EXTERNAL_COLLECTION_MIN_PARSED_COUNT=1` 은 평상시 파싱량(70건) 대비 과도하게 낮고, `EXTERNAL_COLLECTION_POLL_SECONDS=60` 은 실패 시 당일 성공까지 60초 간격 재시도를 유발한다.
- 전환 직전 운영에 있던 동일자 가입 계정 3건과 소셜연결 3건은 이번 전환으로 제거되었다. 백업 `prod-before-20260830-1824.dump` 와 `travelhunter_before_20260830_1824` DB 에 보존되어 있다.
- 롤백 자산(이전 운영 DB, 덤프 2개)은 안정화 기간 종료 전까지 삭제하지 않는다.
- 운영 배포 Jenkins job 의 SCM 브랜치 지정이 아직 `*/ci/prod-jenkins` 다. `main` 머지가 운영 자동 배포로 이어지지 않는 상태이며, 별도 확인이 필요하다.

### #53 e2e·Jenkins

- **Jenkinsfile 변경은 파이프라인에서 검증되지 않았다.** Jenkins 에이전트가 개발서버에 있어 조작 금지 대상이다. 반영 시 ① 잡이 `Pipeline script from SCM`인지 인라인인지 확인하고 ② **일부러 실패하는 테스트를 넣어 배포가 실제로 멈추는지** 한 번 확인해야 한다.
- **CI에 프론트 테스트가 여전히 없다.** `npm test`(vitest)와 `test:e2e`가 `run-backend-command.cjs`/`run-backend-e2e.cjs`를 타는데, 두 스크립트 모두 **호스트 python**으로 alembic·seed·uvicorn을 띄운다. Jenkins 에이전트에는 python이 없다. 컨테이너용 러너로 고치는 작업이 선행돼야 한다. (`tsc`는 프론트 이미지 빌드가 `npm run typecheck && vite build`를 돌아 이미 강제된다.)
- **`backend-mode.spec.ts` 12개 중 3건이 낡았다.** ① 정책 `officialUrl` 기대값이 시드 변경(`f12efc2`)을 못 따라감 ② 초대 버튼 문구 `보기만 가능 링크 준비 완료`가 소스에서 사라짐 ③ 장소 수동 입력이 add 시트에서 제거됨(`place-label`이 `mode === "edit"` 전용). ②③은 **백엔드는 기능을 유지하는데 UI 진입점만 사라진** 형태라 "의도된 제거인가 유실인가" 판단이 필요하다. 이번 작업에서는 손대지 않았다.
- **기본 러너를 그냥 쓰면 로컬 DB가 오염된다.** `npm run test:e2e`는 `docker compose up -d db`로 돌고 있는 db 컨테이너를 재생성할 수 있고 `travelhunter` 본 DB에 시딩한다. 반드시 `SKIP_E2E_DB_START=1` + `DATABASE_URL`을 별도 DB로 지정해 실행한다.
- `npm ci` reports 4 audit findings from existing frontend dependencies (2 moderate, 2 high) — 이번 실행에서도 동일하게 확인됨.
- `backend/tests/test_stay_discount_semantics_migration.py`와 `backend/tests/test_stay_discount_semantics_snapshot.py`는 의도적으로 과거 `7.31`/`8.17` 동결 prestate 예시를 유지한다.

### develop 에서 이어지는 것

- **실기기·브라우저 확인 미완.** 운영자 몫이다. 5173 에서 아래를 본다.
  - [ ] 경기를 고르면 권역 4줄로 접혀 있고, 펼쳐 연천군까지 고를 수 있다
  - [ ] 대전·제주처럼 작은 시도는 접기 없이 평평하다
  - [ ] 행정지역 버튼에 이름만 나오고, 추천 권역에는 포함 도시가 보인다
  - [ ] 편집 화면에서 저장된 지역이 든 권역이 펼쳐진 채로 열린다
  - [ ] 제주 동부 일정을 제주 서부로 바꿔 저장된다. 장소·Day·연결 정책이 그대로다
  - [ ] 제목만 바꿔 저장하면 지역이 그대로다
  - [ ] 생성·직접 편집·상세 기간 수정의 달력이 같고, 역순 선택이 정방향으로 저장된다
  - [ ] 기간을 줄일 때 장소 처리 선택 UI 가 그대로 뜬다
  - [ ] day 스트립을 마우스로 밀 수 있고, 그냥 클릭하면 날짜가 바뀐다
  - [ ] 30일 일정에서 카드를 잡아도 탭 폭이 흔들리지 않는다
  - [ ] 360×780, 390×844, 430×932, 1024×768, 1440×900 에서 잘림·이탈이 없다

- **미해결 버그.** 카드를 잡고 좌우 이동영역으로 날짜를 옮긴 뒤 위로 올리면 스크롤 고정이 듣지 않는다.
  자동 스크롤 제동은 `autoScrollBrakedRef` 로 한 번만 `autoScrollBrakeTick` 을 올려 dnd-kit 의
  `canScroll` 정체성을 바꾸는 구조다. 날짜 전환 시 그 상태가 어떻게 되는지가 다음 확인 지점이다 —
  `ItineraryDetailPage.tsx:2439` 의 타이머 effect 와 `:2149` 의 `canScroll`.

- **상세의 `여행기간 수정` 시트는 열 방법이 없다.** `openDateEditor` 가 어디서도 호출되지 않는다.
  HEAD 이전부터 그렇다. 공통 달력으로 교체만 해뒀고, 진입점을 만들지 시트를 지울지는 제품 판단이다.

- **권역 배정은 판단이 갈릴 수 있다.** 빠짐·중복만 테스트로 막았다(9개 시도 190개 단위가 정확히 분할).
  옮기려면 `backend/app/data/administrative_areas.py` 의 `ADMINISTRATIVE_GROUPS_BY_SIDO` 한 곳만 고치면 되고,
  옮기다 빠뜨리면 테스트가 잡는다.

- **해소됨(2026-09-05).** dgtour 슬러그 근본 수정은 #52 로 병합됐다. 로컬에만 있던 가지 8개는
  모두 push 돼 원격에 사본이 생겼고 #53~#56 으로 올라가 있다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
