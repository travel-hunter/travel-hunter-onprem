# CHECKLIST

## Current Status

- Merge-ready: 정책·시군 사진 검토와 원본 보관(`feature/photo-collection-criteria`). 수집은 기준(공공누리 유형 · 시설 · 크기 · 겹침)을 거친
  후보만 넣고, 관리자가 '사진 검토'(`/admin/photo-review`)에서 확정한 한 장만 앱에 나간다. 확정 때 원본을 볼륨 `travelhunter-media` 에 받아
  백엔드가 `/api/media` 로 내보낸다. 로그인 사진 8장 돌리기 · 앱 전체 '사진 출처', 홈 → 정책 탭 예전 화면 버그 수정 포함.
  계획: `docs/superpowers/plans/2026-10-01-photo-collection-criteria.md` · `2026-10-02-photo-review-stage.md`.
- Scope: backend(Alembic 0046 · 0047, 관리자 API, `/api/media`) · frontend · compose 볼륨 · 문서. 공개 `Policy.photo` 모양은 그대로(`imageUrl` 이 상대 주소).
- 보류: `feature/error-alerts`(에러 알림, 로그 작업 뒤로).

## Recent Validation

- PASS: backend `python -m pytest`(stay-discount 스냅샷 제외) 1189 passed · 24 skipped, `alembic upgrade 0045_traffic_detail:head --sql`, `downgrade 0047_photo_review:0045_traffic_detail --sql`.
- PASS: `npm run typecheck`, `npm run test:mojibake`, `npx vitest run` 45파일 493개, `npm run build`, `npm run test:e2e:containers` 13/13.
- PASS: 4173 실측 - 로컬 DB 에 0046·0047 적용 · 후보 수집(898장), 확정 → 원본 저장 → `/api/media` 200 · immutable 캐시 → 정책 상세 사진. 로그인 사진 6초 돌기(동작 줄이기면 멈춤), '사진 출처' 홈 · 내 정보 · 넓은 화면, 홈 '전국 공통' → 지도.
- PASS: 코드 리뷰(BASE `ad25771`, HEAD `503e551`, backend · frontend 두 갈래) - HIGH 없음. MEDIUM 3건(수집 중 같은 사진 고유키 오류로 수집 전체 중단, 확정과 수집의 잠금 대기, 넓은 화면 불러오는 동안 '목록에 없어요') 과 LOW 다수(받는 주소 제한 · 넘겨주기, 설정 누락 500, 디스크 오류 500, 확정 503 문구, 수집 진행 묻기 멈춤, 끝날 때 고른 후보 지움, 두 번 누르기, 경로 순회 시험)를 고치고 시험 보강.
- PASS: `git diff --check`, 변경 파일 U+FFFD 0건, diff 의 비밀값·로컬 경로·서버 주소 검색 0건.

## Active Risks

### 로그 장기 보관(PR #84 + `logarchive` 컨테이너)

- 개발서버는 cron 으로 돌던 보관을 컨테이너로 넘기고 crontab 을 지워야 한다(#85 머지 후, 서버 쓰기라 승인 받아 진행 - 진행 여부 확인 필요).
- 보관본은 같은 PC 의 다른 디스크(D:)다. WSL·Docker 고장은 견디지만 PC 다운·D: 고장은 못 막는다. 다음 단계는 다른 기계(NAS)나 S3 로 한 번 더 복사.
- 개발 배포가 D: 에 의존한다. `/mnt/d` 가 없으면 `logarchive` 가 못 떠 `up --wait` 가 실패한다.
- `logarchive` 는 root 로 돈다(Caddy 접근 로그가 0600). 대신 네트워크 없음·특수 권한 없음·권한 상승 금지·읽기 전용으로 묶었다. 개발서버 D: 는 drvfs 라 소유자를 저장하지 않는다.
- 보관본(사용자 ID·IP 앞자리·경로)은 그 PC 에 로그인하는 누구나 읽을 수 있다. 보관 기간(12개월)과 열람 범위는 팀이 정한다.
- profile 로 꺼진 서비스는 `--remove-orphans` 로 안 지워진다. 끌 때는 `--profile logarchive rm -sf logarchive`.
- 5분 주기다. 볼륨 보관 한도(스트림당 200MB)를 넘길 만큼 멈춰 있으면 그 사이는 잃는다. `docker logs` 로 회차 기록을 본다.
- AWS 로 옮기면 빼 오는 곳이 CloudWatch 로 바뀐다(ASG·private subnet). 보관 형식은 그대로 둔다.

### 사진 검토 · 원본 보관(`feature/photo-collection-criteria`)

- 배포 직후 홈 시군 카드 · 정책 상세 머리가 모두 혜택 그림이 된다(0047 이 기존 자동 사진을 `review` 로 내림). Jenkins 는 `alembic upgrade head` 만 한다 -
  관리자 사진 검토의 '후보 채우기'를 한 번 누르고 시군부터 확정한다(시군·도 약 70곳 + 정책 약 100건).
- `travelhunter-media` 볼륨은 DB 볼륨처럼 백업 대상이다. `docker compose down -v` 금지. 지워지면 다시 확정할 때 원본을 다시 받는다.
- `region_photos` · `policy_photos` 는 더 읽지도 쓰지도 않는다. 배포가 확인되면 지우는 마이그레이션을 따로 둔다.
- 0047 은 배포 전이라 제자리에서 고쳤다(`stored_path` 등). 고치기 전 0047 을 적용한 DB 가 있으면 내렸다 다시 올려야 한다 - 개발서버는 0045.
- 수집 진행 상태는 서버 프로세스 안에 있다(uvicorn 1개 전제). 워커를 늘리면 '이미 도는 중' 막기가 프로세스마다 따로다.
- Pixabay 설정 · `app/services/pixabay.py` 는 이제 쓰이지 않는다(정리는 따로).

### 화면 개편(`feature/screen-redesign`)

- 로컬 4173 은 루트 `.env` 의 `VITE_ADMIN_BASE_URL` 이 4173 이라 관리자 주소로 보여, 로그인의 가입·비밀번호 찾기·카카오·구글 입구가 숨는다. 실제 사용자 주소에선 보인다(vitest 로 확인).
- 예전 클래스(`prototype-stat-card`·`prototype-menu-row`·`ds-favorite-policy-*` 등) CSS 는 이제 안 쓰이지만 지우지 않았다 - 죽은 CSS 정리는 따로(화면 상태별 확인 먼저).
- 홈 배너 사진은 전남·숙박·제휴·환급·교통 다섯 장뿐이다. 사진이 없는 지역 장은 색 바탕. CC BY · BY-SA 사진의 출처 문구는 화면에서 빼면 안 된다.
- 넓은 화면 판은 가운데 최대 1440px(정책 탭 지도만 전체 폭). 시안 캔버스(1280)보다 넓은 화면은 시안으로 정한 적이 없다.
- 수집 데이터 확인 필요: 합천 반값여행(`travelmonth-102`)은 마감 2026-10-11 인데 본문 신청 기간은 07-31 에 끝났고, 금액도 본문 최대 50만원 · 카드 20만원으로 다르다. 홈 마감 칸 첫 장에 나온다.
- 반값여행 묶음 머리의 공통 문구(`PROGRAM_GROUP_COPY`)는 고정 문구라 지역마다 조건이 다르면 그 지역을 틀리게 말한다. 장흥처럼 '관광지 2개소 또는 1개소 + 가맹점' 조건은 목록 줄에 첫 숫자만 나온다.
- e2e 의 수동 장소 저장 확인은 예전부터 낡아(추가 시트에서 직접 입력이 빠짐) 이번에 걷어 냈다 - 편집 모드 경로로 다시 세울 것.

### 역추적 로그(PR #83)

- **`docker compose down -v` 금지.** `-v` 가 `travelhunter-logs` 볼륨을 DB 와 함께 지워 로그 이력이 사라진다. 운영·개발서버에서는 `down` 만 쓴다.
- Caddy 접근 로그는 파일로만 간다(Caddy 는 한 곳에만 쓸 수 있다). Dozzle·`docker logs caddy` 에는 기동·오류 줄만 보인다. 엣지 기록은 `scripts/trace.py` 로 본다.
- `RotatingFileHandler` 는 다중 프로세스 안전하지 않다. 지금은 uvicorn 워커 1개다. 워커를 늘리면 회전이 경합하므로 그때 핸들러를 바꿔야 한다.
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

- **권역 배정은 판단이 갈릴 수 있다.** 빠짐·중복만 테스트로 막았다(9개 시도 190개 단위가 정확히 분할).
  옮기려면 `backend/app/data/administrative_areas.py` 의 `ADMINISTRATIVE_GROUPS_BY_SIDO` 한 곳만 고치면 되고,
  옮기다 빠뜨리면 테스트가 잡는다.

- **해소됨(2026-09-05).** dgtour 슬러그 근본 수정은 #52 로 병합됐다. 로컬에만 있던 가지 8개는
  모두 push 돼 원격에 사본이 생겼고 #53~#56 으로 올라가 있다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
