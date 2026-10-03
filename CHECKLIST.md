# CHECKLIST

## Current Status

- Merge-ready: 홈 · 정책 탭 통합 검색(`feature/unified-search`, 시안 v57 · v58). 홈 검색창이 그 자리에서 지역 · 혜택 · 장소를 찾고
  장소 카드(근처 혜택 · 일정에 담기 · 카카오맵 · 이 근처)로 잇는다. 정책 탭 '위치로 찾기'는 아는 장소를 그 시군 혜택 · 지도 핀 · 가까운 시군으로 잇는다.
  검색 규칙(띄어쓰기 무시 · 별칭 · 초성 · 지역 + 혜택)은 `components/map/searchText.ts` 한 곳. 계획: `docs/superpowers/plans/2026-10-03-unified-search.md`.
- Scope: 새 API `GET /api/places/search` · `GET /api/places/nearby`(카카오 로컬, 로그인 필요 - 계약 · 골든 갱신), frontend, 문서. DB · env 변경 없음(기존 `KAKAO_LOCAL_*`).
- 보류: `feature/error-alerts`(에러 알림, 로그 작업 뒤로).

## Recent Validation

- PASS: backend `python -m pytest` 1200 passed · 24 skipped(`test_stay_discount_semantics_snapshot.py` 는 뺐다 - 소유자 전용 폴더 권한 검사가 Windows 에서 실패, 이 변경과 무관).
- PASS: `npm run typecheck`, `npm run test:mojibake`, `npm run build`, `npm run test:e2e:containers` 13/13.
- 부분 PASS: `npx vitest run` 47파일 513개 중 507개. 실패 6개는 모두 `mypage.test.tsx` 다(아래 알려진 흔들림, 단독 실행도 같은 6개).
- PASS: 4173 headless 실측(390) - 'constructor' · '__proto__'(정책 탭 · 홈)는 결과 없음 안내만, 결과 없을 때 Enter 는 칸 · 주소 · 초점 그대로,
  '여수' Enter → '여수 1건' + 초점 빠짐 → 다시 누르면 열림, `place=__proto__` → '모든 지역 105건', 홈 `lv=2` 바로 열기의 ‹ → 검색 결과,
  '일정에 담기' → 기존 일정 고르기 → 그 일정의 장소 추가 창(바구니에 오동도 · 날짜 칩 3개, 저장은 누르지 않음), 홈 검색창 Enter → 결과 · 주소 그대로 · 초점 빠짐.
  페이지 오류 0 · 가로 넘침 없음, 백엔드 로그 5xx 0 · 비밀 문자열 0.
- PASS: 코드 리뷰(BASE `27b8457`, HEAD `828aae7`) - HIGH 1건(검색어 'constructor' · '__proto__'가 별칭 표에서 Object 를 꺼내 정책 탭 · 홈 검색이 멈춤),
  MEDIUM 4건(카카오 설정 오류가 500, 카카오를 부르는 동안 DB 세션을 쥠, 결과 없을 때 Enter 가 추천 칩을 누름, 다른 날에 담아도 보던 날에 머묾),
  LOW 4건(뒤로 뒤 주소에 근처가 남음, 주소로 바로 연 이어 본 카드의 ‹ 가 무반응, 홈 건수 기준 주석, 문서 상태)을 고치고 시험을 더했다.
  같은 종류의 기존 결함 두 가지도 함께 고쳤다: 주소 `place=__proto__`(develop 부터), Enter 로 고른 뒤 초점이 칸에 남아 다시 눌러도 안 열림.
  검토 밖에서 더한 것: 홈 검색창 Enter(검색 키)는 결과를 그대로 두고 휴대폰 키보드만 내린다.
- PASS: `git diff --check`, 변경 파일 U+FFFD 0건.
- 알려진 흔들림: `mypage.test.tsx` 는 공용 로컬 백엔드 시험 계정에 시험이 만든 일정이 쌓여(10/3 약 250개) `GET /api/trips` 가 1.1~1.6초 걸리면
  waitFor 1초를 넘겨 실패한다(백엔드 로그 duration_ms). 이 변경과 무관 - 시험 데이터를 비우거나 `/api/trips` 를 빠르게 하는 일은 따로.

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

### 통합 검색(`feature/unified-search`)

- 장소 결과는 카카오에 달려 있다. 꺼져 있거나 실패하면 빈 목록이라 화면에서는 '결과 없음'과 구분되지 않는다(설정 오류는 경고 로그 `place_search_kakao_misconfigured`).
- `/api/places/*` 에 호출 제한이 없다(로그인한 사용자 누구나). 프론트는 300ms 디바운스 · 화면 안 캐시뿐이라 카카오 일일 한도를 나눠 쓴다.
- '이 근처'는 인기순이 아니라 가까운 순이다(카카오가 별점 · 리뷰를 주지 않는다). 장소 정보는 이름 · 분류 · 주소 · 좌표뿐 - 결정은 카카오맵 링크로.
- 가까운 시군 거리는 시군 대표점 사이 직선 근사(약 45km 안)다.
- 일정 고르기 창은 기기 뒤로가기로 닫히지 않는다(홈을 떠난다). 새 일정을 만들어 담은 뒤의 뒤로는 만들기 화면으로 간다.
- 이어 본 장소 카드(`lv=2`)를 주소로 바로 열면 '‹ 앞 장소'는 앞 장소가 아니라 검색 결과로 간다 - 앞 장소 정보가 주소에 없다.

### 필터 · 글 검색을 지도 안에서(PR #88)

- 새로 고친 직후 '관심 정책만'이 걸려 있으면 관심 정책 목록이 오기 전 잠깐 0건이 보인다(목록을 못 받으면 0건에 머문다 - 조건 줄 ✕ 로 푼다).
- 조건은 탭(sessionStorage)에 남아 다른 탭에서 정책 탭으로 돌아와도 걸려 있다. 로그아웃하면 지운다.
- 휴대폰 반반 화면에서 지역을 고르면(지도 누르기와 같이) 같은 층이라 기록을 덮어쓴다 - 기기 뒤로가기는 정책 탭을 떠난다(예전부터의 층 규칙).
- 예전 목록 CSS(`.policy-list-card` · `.policy-list-photo-credit` · `.prototype-policy-result-row` 등)는 남아 있다 - 죽은 CSS 정리는 따로.

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
