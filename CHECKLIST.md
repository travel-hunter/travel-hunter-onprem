# CHECKLIST

## Current Status

- Active task/status: `develop` 이 두 건을 받았다. **#51** 일정의 지역·기간 선택 통합 — 전국 행정 시·군·구 카탈로그를 권역으로 접어 보여주고, 기존 일정의 세부 지역을 바꿔 저장하며, 생성·직접 편집·상세 기간 수정이 같은 달력을 쓴다. day 스트립도 함께 다듬었다. **#52** 디지털관광주민증 정책 슬러그를 canonical city 기준으로 고정.
- Scope guard: `backend/app/{data,services,schemas,api}`, `backend/tests`, `frontend/src/{api,components/trip,pages/itinerary,utils,styles,app/__tests__,test}`, `frontend/scripts`, `docs`, `.agent/evals`. 정책 수집·크롤러·알림·배포 설정은 건드리지 않았다.
- 두 PR 이 합쳐진 상태는 각 PR 에서 따로 검증되지 않아 2026-09-05 에 별도로 돌렸다. 결과는 아래 Recent Validation 이다.
- 열려 있는 draft PR: #53 backend-mode e2e·dev Jenkins 테스트 단계, #54 운영 DB 이전 기록, #55 로컬 런타임 문서, #56 드래그 가로 오버플로. **#53·#54 는 `CHECKLIST.md` 충돌이 있었고 2026-09-05 에 `origin/develop` 을 병합해 풀었다.**

## Recent Validation

- PASS: `cd frontend && npm run typecheck`
- PASS: `cd frontend && npx vitest run` — **348 passed / 0 failed** (28 files) / #51+#52 병합 후 재실행
- PASS: `cd frontend && npm run build`
- PASS: `cd frontend && npm run test:mojibake` — 이번에 제어문자 검사를 추가했고 탐침 파일로 실제 검출을 확인했다
- PASS: `cd backend && python -m pytest` — **708 passed / 1 failed / 23 skipped** / #52 가 더한 테스트 포함
- PASS: `docker compose -f compose.yaml config`, `docker compose -f compose.local.yaml config` (출력은 버림 — 환경변수가 펼쳐진다)
- PASS: `git diff --check`
- PASS: `GET /api/travel-areas` 실응답 확인 — 경기 31개가 북부 10 / 서부 8 / 남부 8 / 동부 5 로 갈리고 연천군이 포함된다. 세종은 하위 없이 "세종 전체"만 나온다.

백엔드 실패 1건은 `test_stay_discount_semantics_snapshot.py::test_restricted_atomic_artifact_and_sidecar_round_trip` 이다.
Windows 임시 디렉터리 권한에 걸리는 **간헐적 환경 이슈**로 통과할 때도 있다. 2026-08-27 기록에도 같은 이름으로 남아 있고 이 브랜치가 만든 것이 아니다.

## Active Risks

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

## 참고 문서

- `docs/2026-09-05-commit-handoff.md` — 커밋·push 인계
- `docs/2026-09-04-codex-handoff.md` — 세션 밖에서 바뀐 설정과 기준선
- `docs/superpowers/plans/2026-09-03-trip-region-calendar-unification.md` — 지역·달력 통합 (Task 1~8)
- `docs/superpowers/plans/2026-09-04-itinerary-day-strip-followups.md` — 일정 화면 후속 조정 (Task 1~10)
- `docs/superpowers/plans/2026-09-01-itinerary-day-strip.md` — day 스트립 1차
