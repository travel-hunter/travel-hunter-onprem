# CHECKLIST

## Current Status

- Merge-ready: 공공데이터 장소 기반(`feature/public-places`, 카카오 운영정책 2단계). 화면 변화 없음.
  새 표 `public_places` · `public_place_sync_state`(Alembic `0048`, `trip_places` 출처 열 5개 nullable - 3단계부터 채움), TourAPI 주 1회 동기화
  (`PUBLIC_PLACES_SYNC_ENABLED` 기본 꺼짐) · 손 스크립트 2개(`sync_public_places_tourapi.py` · `load_public_places_sangga.py`), 맞춰 보기 API `POST /api/places/match`
  (계약 · 골든 · 프론트 타입 갱신), `debug_capture` 가 장소 경로를 늘 뺀다. 공용 로그 함수는 숨긴 예외 맥락과 `serviceKey=` 를 더는 남기지 않는다.
  env 3개 추가(`.env.example` · `compose.local.yaml`). 설계: `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`, 계획: `docs/superpowers/plans/2026-10-04-public-places-stage2.md`.
- 통합 검색(1단계)은 PR #89 로 develop 에 머지됐다(`bb8c841`).
- 보류: `feature/error-alerts`(에러 알림, 로그 작업 뒤로).

## Recent Validation

- PASS: backend `python -m pytest` 1249 passed · 24 skipped(`test_stay_discount_semantics_snapshot.py` 는 뺐다 - 소유자 전용 폴더 권한 검사가 Windows 에서 실패, 이 변경과 무관).
- PASS: `npx tsc --noEmit`, `npm run test:mojibake`, `npm run build`, `npm run test:e2e:containers` 13/13, `docker compose -f compose.yaml config`(출력은 버림).
- 부분 PASS: `npx vitest run` 48파일 523개 중 517개. 실패 6개는 모두 `mypage.test.tsx` 다(아래 알려진 흔들림).
- 부분 PASS: `alembic upgrade head --sql` 을 처음부터 돌리면 기존 데이터 마이그레이션 `0044` 에서 멈춘다(오프라인인데 DB 를 읽음 - develop 그대로).
  `0045_traffic_detail:head --sql`(0046 ~ 0048)은 통과.
- PASS: 로컬 실측(세 컨테이너를 이 브랜치로, DB 볼륨 유지). 앞서 덤프를 떠 `pg_restore -l` 목차 314 · SHA-256 `26ef4268…efcd4`(저장소 밖) 확인, 0047 → 0048,
  TourAPI 전체 동기화 received 47,656 · written 47,619 · success(약 35초, 호출 약 50회), 상가정보 `--only 세종` written 5,923 · partial(지우지 않음),
  상자 조회 `EXPLAIN` 은 `ix_public_places_lat_lng` Index Scan, 정책 · 일정 · 사용자 · 수집 기록 · 일정 장소 행 수 전후 같음(202 · 291 · 4 · 118 · 180).
  맞춰 보기: '오동도 등대'(관광명소) → match 60m, 같은 이름에 카페 분류 → 후보, '오동도' → 후보 2곳(TourAPI 에는 '오동도' 단독 항목이 없다).
  상가정보 20260630판 `--dry-run` 여행 업종 1,036,750건(food 717,632 · cafe 122,623 · leisure 105,158 · stay 80,483 · culture 10,854).
- PASS: 계획 코덱스 검토 2회를 반영했다(오류 알림만 보류). 최종 리뷰(새 리뷰어) Critical 1(TourAPI 키가 오류 로그에 남음) · Important 1(크게 줄어든 단위를
  손으로도 지울 수 없음)을 고치고 시험을 더했다(사용자 결정: `--accept-shrink`). 최종 커밋 재리뷰 Critical 1(넓힌 가리기 규칙이 하이픈이 긴
  요청 경로에서 제곱 시간 - 16KB 에 9.5초)과 같은 꼴의 기존 이메일 규칙을 고치고 시간 상한 시험을 더했다. Minor 중 운영에 닿는 것은 아래 위험으로.
- PASS: `git diff --check`, 변경 · 새 파일 U+FFFD 0건 · 한자 0건.
- 알려진 흔들림: `mypage.test.tsx` 는 공용 로컬 백엔드 시험 계정에 시험이 만든 일정이 쌓여(10/3 약 250개) `GET /api/trips` 가 1.1~1.6초 걸리면
  waitFor 1초를 넘겨 실패한다(백엔드 로그 duration_ms). 이 변경과 무관 - 시험 데이터를 비우거나 `/api/trips` 를 빠르게 하는 일은 따로.

## Active Risks

### 공공데이터 장소 기반(`feature/public-places`)

- **TourAPI(data.go.kr) 키 교체 필요.** 2026-10-02 14:23 개발서버 사진 후보 수집이 TourAPI 오류를 만나 지금 쓰는 키를 백엔드 로그 파일과
  장기 보관본(`dev/backend-2026-10.log`)에 한 줄씩 남겼다(개수와 같은지만 셌다). 이 브랜치의 로그 수정 뒤로는 남지 않는다.
  키를 재발급해 개발서버 env · 로컬 `.env`(같은 키) · 운영 env(있다면)를 바꾼다(사용자). 남은 두 줄은 교체 뒤 쓸모없다 - 지우려면 서버 쓰기 승인.
- 서버 적재는 머지 뒤 승인받아 손으로 한다: 개발서버 TourAPI 첫 동기화, 상가정보 zip(336MB)을 서버로 옮겨 약 104만 행 적재(옮긴 파일 600, 끝나면 지움).
  운영은 최신 develop 배포 뒤 같은 순서. DB 가 수백 MB 커져 덤프 · 백업 · 로컬 동기화도 그만큼 커진다.
- 주 1회 동기화는 사용자가 서버 env 에 `PUBLIC_PLACES_SYNC_ENABLED=true` 를 넣어야 돈다. 켜면 운영자가 매주 동기화 다음 날 `public_place_sync_state` 를
  읽기 전용으로 본다(시각은 UTC, KST 는 +9시간). success 가 아니거나 `last_success_at` 이 8일을 넘으면 로그 `public_places_sync_failed` · `public_places_prune_limited` 를 본다.
  `kept=39:10000->7000` 처럼 끝까지 받았는데 줄어든 단위는 원인을 확인한 뒤 손 스크립트 `--accept-shrink 39`(상가정보는 `--accept-shrink 세종`)로 지운다. 알림은 없다(에러 알림 보류).
- 바로 담기 비율은 실측 63%보다 낮다(두 출처 같은 이름, 분류가 다르거나 모름, TourAPI 의 비슷한 이름은 후보). 3단계에서 실데이터로 다시 잰다.
  상가정보 '예술·스포츠'에는 헬스장 · 당구장 같은 동네 시설이 섞인다(3단계 추천 카드에서 거른다).
- 로컬 DB 는 0048 이라 개발서버 배포 전까지 로컬 정책 동기화 스크립트가 Alembic 불일치로 멈춘다.
- 최종 리뷰 Minor(다음으로): 손 실행이 자동 동기화와 겹치면 서로 쓴 행을 지울 수 있다(잠금 없음 - 04시 무렵 손으로 돌리지 말 것),
  관광명소 1km 조회가 200m 만 쓰는 상가정보까지 읽는다(전체 적재 뒤 밀집 지점 실측), 읽은 뒤 단계에서 실패하면 상태가 `running` 으로 남는다,
  시도를 못 가린 상가정보 행은 지우기 판정에서 빠진다(전체 적재 뒤 `sido` NULL 건수 확인), `totalCount` 폭주 상한이 없다,
  맞춰 보기 요청이 모르는 필드를 조용히 받는다. 재리뷰 Minor: TourAPI 실패 이유가 'request failed' 뿐이라 시간 초과인지 연결 오류인지 모른다,
  가리기가 `areaCode=` 같은 일반 값까지 가린다, 스크립트 인자 오류도 종료 코드 2(partial 과 같다), 상가정보 `--accept-shrink` 이름 오타를 알리지 않는다,
  한 건도 못 쓴 partial 은 `kept` 가 비어 까닭이 안 보인다.

### 로그 장기 보관(PR #84 + `logarchive` 컨테이너)

- 개발서버는 cron 으로 돌던 보관을 컨테이너로 넘기고 crontab 을 지워야 한다(#85 머지 후, 서버 쓰기라 승인 받아 진행 - 진행 여부 확인 필요).
- 보관본은 같은 PC 의 다른 디스크(D:)다. WSL·Docker 고장은 견디지만 PC 다운·D: 고장은 못 막는다. 다음 단계는 다른 기계(NAS)나 S3 로 한 번 더 복사.
- 개발 배포가 D: 에 의존한다. `/mnt/d` 가 없으면 `logarchive` 가 못 떠 `up --wait` 가 실패한다.
- `logarchive` 는 root 로 돈다(Caddy 접근 로그가 0600). 대신 네트워크 없음·특수 권한 없음·권한 상승 금지·읽기 전용으로 묶었다. 개발서버 D: 는 drvfs 라 소유자를 저장하지 않는다.
- 보관본(사용자 ID·IP 앞자리·경로)은 그 PC 에 로그인하는 누구나 읽을 수 있다. 보관 기간(12개월)과 열람 범위는 팀이 정한다.
- profile 로 꺼진 서비스는 `--remove-orphans` 로 안 지워진다. 끌 때는 `--profile logarchive rm -sf logarchive`.
- 5분 주기다. 볼륨 보관 한도(스트림당 200MB)를 넘길 만큼 멈춰 있으면 그 사이는 잃는다. `docker logs` 로 회차 기록을 본다.
- AWS 로 옮기면 빼 오는 곳이 CloudWatch 로 바뀐다(ASG·private subnet). 보관 형식은 그대로 둔다.

### 통합 검색(PR #89, 머지됨)

- 장소 결과는 카카오에 달려 있다. 꺼져 있거나 실패하면 빈 목록이라 화면에서는 '결과 없음'과 구분되지 않는다(설정 오류는 경고 로그 `place_search_kakao_misconfigured`).
- `/api/places/*` 에 호출 제한이 없다(로그인한 사용자 누구나). 프론트는 300ms 디바운스 · 화면 안 캐시뿐이라 카카오 일일 한도를 나눠 쓴다.
- '이 근처'는 인기순이 아니라 가까운 순이다(카카오가 별점 · 리뷰를 주지 않는다). 장소 정보는 이름 · 분류 · 주소 · 좌표뿐 - 결정은 카카오맵 링크로.
- 가까운 시군 거리는 시군 대표점 사이 직선 근사(약 45km 안)다.
- 주소로 연 장소 카드(새로 고침 · 휴대폰 탭 복원 · 받은 링크)는 같은 말로 다시 찾아 그린다. 다시 찾아도 없거나 카카오가 실패하면 홈은 검색 결과로
  (쌓인 기록이 있으면 되감는다), 정책 탭은 근처 표시를 지우고 시군만 남긴다. 이어 본 장소(`lv` 2 이상)는 같은 말 검색 결과에 없으면 대개 이렇게 돌아간다.
  받은 링크로 연 이어 본 카드가 그려져도 '‹ 앞 장소'는 앞 장소가 아니라 검색 결과로 간다(되감을 기록이 없다).
  같은 화면에서도 30분 · 200곳이 지난 뒤 앞의 이어 본 장소로 돌아가면 검색 결과로 간다 - 화면은 지금 그린 한 곳만 붙잡는다.
- 이 PR은 카카오 장소값 노출을 줄인 것이지 저장 문제의 해결이 아니다. 일정 안 장소 검색 · 추천 카드 · `?addPlace` 받기 · 편집 초안(localStorage)에 남아 있고, 설계 2~4단계에서 고친다.

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
- 롤백 자산: 안정화 기간의 끝은 운영을 최신 develop으로 맞추는 배포다. 그 배포를 확인한 뒤 옛 운영 DB(`travelhunter_before_20260830_1824`)와 `prod-before-20260830-1824.dump`를 지운다(승인 후). 개발 원본 덤프 `dev-full-20260830-1824.dump` 두 벌은 카카오 값과 정제 전 개발 데이터가 있어 2026-10-03에 지웠다. 두 서버의 덤프 파일은 600, 폴더는 700이다. 근거: `docs/superpowers/specs/2026-10-03-public-place-storage-design.md` '백업과 보존'.
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
