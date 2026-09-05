# CHECKLIST

## Current Status

- Active task/status: 개발서버 DB 스냅샷을 정제해 운영서버 DB로 1회 이전 완료(2026-08-30 KST). 운영 백엔드는 자기 Compose 네트워크의 `db:5432/travelhunter` 를 계속 사용한다.
- Scope guard: 이번 작업 범위는 개발 DB 전체 덤프 → 운영 임시 DB 복원 → 개발 전용 시드/세션 정제 → DB 이름 전환 → 스모크로 제한한다. 스키마 변경, 코드 변경, 수집 스케줄러 활성화, 관리자 지정은 포함하지 않는다.
- 2026-09-05 에 `origin/develop` 을 병합했다. 충돌은 `CHECKLIST.md` 하나뿐이고 코드 충돌은 없었다. draft PR #54 로 올라가 있다.

## Recent Validation

- PASS: 운영 전환 직전본 백업 `prod-before-20260830-1824.dump` (77KB, mode 600) — `pg_restore --list` TOC 208 entries 확인.
- PASS: 개발 원본 덤프 `dev-full-20260830-1824.dump` (402KB, mode 600) — TOC 208 entries, 전송 전후 SHA-256 일치.
- PASS: 개발 백엔드 정지 상태에서 덤프 생성(쓰기 동결) 후 작업 종료 시 재기동 및 healthy 확인.
- PASS: 운영 임시 DB `travelhunter_restore_20260830_1824` 로 `pg_restore --single-transaction --no-owner --no-privileges` 오류 0, 이후 `ANALYZE` 실행.
- PASS: 정제 드라이런과 적용 결과 일치 — 시드 3명, 시드 소유 여행 1건(day 3/place 9/member 3/policy 1 CASCADE), 추천 1건, kakao 소셜연결 2건, refresh 209 + pending_signups 2 + pending_social_signups 1 삭제.
- PASS: 정제 후 잔여 0 확인 — 시드 계정, kakao 소셜연결, refresh/reset/pending 토큰 전부 0.
- PASS: 외래키 고아 검사 12개 관계 전부 0.
- PASS: 시퀀스 검사 19개 전부 `MAX(id)` 이상.
- PASS: Alembic revision `0035_stay_policy_identity` — 개발/운영 동일.
- PASS: DB 이름 전환 — `travelhunter` → `travelhunter_before_20260830_1824`, 복원본 → `travelhunter`.
- PASS: 운영 백엔드 healthy, 내부 `/api/health` `database: connected`, `environment: production`.
- PASS: 공개 도메인 `https://prod.travel-hunter.co.kr/api/health` 200 및 DB connected.
- PASS: 공개 `GET /api/policies` 139건 응답(active 수와 일치) — 전남 28 / 경북 22 / 강원 20 / 경남 17 / 전북 16.
- PASS: 운영 DB 최종 건수 — policies 159(active 139/hidden 20), external_source_records 88, policy_documents 16, users 10, social_accounts 4(google), trips 21, trip_days 116, trip_places 252, trip_members 24, trip_policies 9, trip_invites 23, user_saved_policies 4, recommendations 0, auth_refresh_tokens 0.
- PASS: `EXTERNAL_COLLECTION_SCHEDULER_ENABLED=false` 유지 확인(개발/운영 모두).
- PASS: Google `provider_id` 가 개발/운영 앱에서 동일함을 실측 확인(동일 계정 지문 일치) — google 소셜연결 4건은 무손실 이전.
- 미실행: Kakao / Google 브라우저 로그인 스모크는 운영자 로컬에서 수행 예정.
- PASS: 운영 관리자 승격 — `hjiung792@gmail.com`(id 13) `role=admin`, 관리자 1명. `/api/ops/external-collection*` 는 미인증 시 401 반환 확인.
- PASS: 수집 리허설 — 운영서버의 격리 사본 DB 에 `collect_external_benefits_from_live_sources` 1회 실행(37.9초, outcome success, parsed 70 / upsert 70). policies 159→166, active 139→146, hidden 20 유지, external_source_records 88→97. 중복 생성 없음, 수동 큐레이션 보존, 운영서버 아웃바운드 정상 확인. 시험용 DB 는 삭제했다.

## Active Risks

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
