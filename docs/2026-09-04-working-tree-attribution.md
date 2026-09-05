# 작업 트리 귀속 정리 — 2026-09-04

두 세션(Claude, Codex)이 같은 체크아웃에서 작업했고, "테스트 확인 전까지 커밋 금지" 규칙 때문에
결과물이 커밋 없이 한 트리에 쌓였다. **커밋은 아직 하지 않는다.** 이 문서는 나중에 커밋할 때
무엇이 누구 것인지 가르기 위한 대조표다.

기준: `HEAD = d0f77a8`, 브랜치 `feature/itinerary-day-strip`.

---

## 1. 파일별 귀속

두 파일이 겹친다 — `app.css` 와 `ItineraryDetailPage.tsx`. 나머지는 전부 한쪽 소유다.

| 파일 | 소유 | 내용 |
|---|---|---|
| `frontend/src/pages/itinerary/ItineraryDetailPage.tsx` | **혼재** | Claude: day 스트립 끌기·버튼 교체·시간순 재배치·수정 시트 날짜 선택 / Codex: 히어로 헤더 한 헝크. 아래 2절 참조 |
| `frontend/src/pages/itinerary/ItineraryCreatePage.tsx` | Claude | 날짜 선택 영역 영문 2곳 한글화 |
| `frontend/src/app/__tests__/trip-detail.test.tsx` | Claude | 위 변경의 테스트 |
| `frontend/src/app/__tests__/trip-create.test.tsx` | Claude | 한글 표기 회귀 테스트 |
| `frontend/src/app/__tests__/mypage.test.tsx` | Claude | 실 DB 의존 제거(정책 슬러그) |
| `frontend/src/app/__tests__/policies.test.tsx` | Claude | 같음 |
| `frontend/src/styles/app.css` | **혼재** | 아래 2절 참조 |
| `CHECKLIST.md` | Codex | 헤더 작업 기록 + 실패 6건 메모 |
| `backend/app/api/router.py` | Codex | travel-areas 라우터 등록 |
| `backend/app/data/travel_areas.py` | Codex | 카탈로그 합성용 확장 |
| `backend/tests/test_travel_areas.py` | Codex | 위 테스트 |
| `backend/app/data/administrative_areas.py` (신규) | Codex | 행정구역 스냅샷 |
| `backend/app/services/travel_area_catalog.py` (신규) | Codex | 카탈로그·resolver |
| `backend/app/schemas/travel_areas.py` (신규) | Codex | 응답 DTO |
| `backend/app/api/routes/travel_areas.py` (신규) | Codex | `GET /api/travel-areas` |
| `backend/tests/test_travel_area_catalog.py` (신규) | Codex | Task 1 테스트 |
| `backend/tests/test_travel_area_catalog_routes.py` (신규) | Codex | Task 2 테스트 |
| `docs/superpowers/specs/2026-09-03-...-design.md` (신규) | Codex | 설계 |
| `docs/superpowers/plans/2026-09-03-...md` (신규) | Codex | 구현 계획 |
| `docs/deployment-cicd/2026-09-02-expired-policy-investigation.md` (신규) | 이전 작업 | 09-02자, 이번 두 작업과 무관 |
| `.superpowers/sdd/...` | Codex | `.gitignore`로 추적 제외. 커밋 대상 아님 |

---

## 2. 겹치는 두 파일의 경계

두 파일 모두 구간이 멀리 떨어져 있어 헝크가 섞이지 않는다. `git add -p` 로 고를 수 있다.

### `ItineraryDetailPage.tsx`

Codex 몫은 **헝크 하나뿐**이다.

```
@@ -3513,23 +3749,23 @@     Codex   히어로 헤더
그 외 모든 헝크                Claude
```

내용: 히어로의 이름 없는 `<div>` 를 `<div className="prototype-trip-hero-copy">` 로 바꾸고,
`편집` Link 를 그 안에서 꺼내 히어로 직속 자식으로 옮긴다(CSS 의 `position: absolute` 우하단 고정과 짝).

`TopBar` 와 뒤로가기 버튼 JSX 는 안 바뀌었다 — 위치 이동은 CSS 로만 처리됐다.

### `app.css`

줄 구간으로 깨끗하게 갈린다. 겹치는 헝크가 없다.

```
7071 ~ 7188    Codex   일정 상세 헤더
7504 이후      Claude  day 스트립, 카드 드래그, 수정 시트
```

7188 과 7504 사이에는 헝크가 없다.

**Codex 구간 (7071~7188)** — 뒤로가기 버튼 `top: 50px → 18px`, `transform` 제거,
히어로 `height: 100px → min-height: 156px`, 패딩 재배치, `.prototype-trip-hero-copy` 신설,
제목 `18px → 24px` + `overflow-wrap: anywhere`, 편집 버튼을 `position: absolute` 우하단 고정.

**Claude 구간 (7504~)** — `.itinerary-day-edge` 계열, `.drag-handle.sr-only`,
`.place-day-picker` / `.place-day-options` / `.place-day-chip`,
`.day-tabs` / `.day-tab` 계열, 타임라인 유령 카드와 그리드 열 재배치(8066~, 11792~).

---

## 3. 커밋할 때 쓸 묶음

세 덩어리로 나뉜다. 각각 별도 브랜치·커밋이 맞다.

### A. Claude — 일정 화면 UI

```
frontend/src/pages/itinerary/ItineraryCreatePage.tsx
frontend/src/app/__tests__/trip-detail.test.tsx
frontend/src/app/__tests__/trip-create.test.tsx
frontend/src/styles/app.css                              ← 7504 이후 헝크만
frontend/src/pages/itinerary/ItineraryDetailPage.tsx     ← 히어로 헝크(@@ -3513,23) 제외 전부
```

두 파일 다 `git add -p` 로 헝크를 골라야 한다.

### B. Claude — 테스트를 실 DB에서 분리

```
frontend/src/app/__tests__/mypage.test.tsx
frontend/src/app/__tests__/policies.test.tsx
```

A와 독립이다. 먼저 올려도 되고 따로 올려도 된다.

### C. Codex — 지역·달력 통합 (미완)

```
CHECKLIST.md
backend/app/api/router.py
backend/app/api/routes/travel_areas.py
backend/app/data/administrative_areas.py
backend/app/data/travel_areas.py
backend/app/schemas/travel_areas.py
backend/app/services/travel_area_catalog.py
backend/tests/test_travel_area_catalog.py
backend/tests/test_travel_area_catalog_routes.py
backend/tests/test_travel_areas.py
docs/superpowers/specs/2026-09-03-trip-region-calendar-unification-design.md
docs/superpowers/plans/2026-09-03-trip-region-calendar-unification.md
frontend/src/styles/app.css                              ← 7071~7188 헝크만
frontend/src/pages/itinerary/ItineraryDetailPage.tsx     ← 히어로 헝크(@@ -3513,23) 하나만
```

**C는 Task 8까지 가야 완성이다.** 지금은 Task 1~2까지만 되어 있다.

`app.css` 와 `ItineraryDetailPage.tsx` 가 A와 C 양쪽에 걸린다. 파일 단위 `git add` 로는 못 가른다.

```bash
git add -p frontend/src/styles/app.css
git add -p frontend/src/pages/itinerary/ItineraryDetailPage.tsx
```

두 파일 모두 구간이 멀리 떨어져 있어 헝크가 섞일 일은 없다.
`ItineraryDetailPage.tsx` 는 Codex 헝크가 하나라 오히려 고르기 쉽다.

---

## 4. 검증 상태

### A + B (Claude) — 전부 통과

| 항목 | 결과 |
|---|---|
| `npm run typecheck` | PASS |
| `npx vitest run` | **314 passed / 0 failed** (25파일) |
| `npm run build` | PASS |
| `npm run test:mojibake` | 없음 |
| `git diff --check` | 깨끗 |

실기기 확인은 미완이다. `CHECKLIST.md` Active Risks의 목록을 따른다.

### C (Codex) — Task 1~2만

| 항목 | 결과 |
|---|---|
| `pytest tests/test_travel_area_catalog.py tests/test_travel_area_catalog_routes.py tests/test_travel_areas.py` | **31 passed** |
| 전체 `pytest` | 682 passed / **6 failed** — 아래 5절 참조 |
| Task 3~8 | 미착수. 프런트 파일 없음 |

SDD 원장에 `Task 2: in progress`로 남아 있으나, 지적됐던 `sourceAsOf` 검증은
`test_travel_area_catalog_routes.py:15`에 이미 들어가 있다. **Task 2는 사실상 완료다.**

---

## 5. 백엔드 실패 6건 — 코드 결함 아님

```
682 passed, 6 failed
```

**5건은 포트가 원인이다.**

```
기대  http://127.0.0.1:5173/oauth/callback?...
실제  http://127.0.0.1:4173/oauth/callback?...
```

`.env:13` `TRAVEL_HUNTER_PUBLIC_BASE_URL`이 4173을 가리킨다.
`.env.example:8`에 이유가 적혀 있다 — 일반 로컬은 4173, Vite HMR 환경은 5173.
지금 프런트를 5173으로 띄워 쓰면서 `.env`는 4173인 채라 어긋났다.

- `test_auth_db_routes.py` 4건
- `test_trip_db_service.py::test_invite_to_api_computes_display_flags`

**나머지 1건** `test_stay_discount_semantics_snapshot.py::test_restricted_atomic_artifact_and_sidecar_round_trip`
은 2026-08-27 dgtour 계획서에도 같은 이름으로 환경 이슈(Windows 임시 디렉터리 권한)라고 기록돼 있다.

> 계획서 Task 8은 "backend 전체 통과"를 커밋 조건으로 건다.
> 이 6건을 그대로 두면 그 게이트가 열리지 않는다. `.env`를 5173으로 맞추든,
> 알려진 예외로 명시하든 **Task 8 전에 정해야 한다.**

---

## 6. 같이 알아야 할 것

### 정책 슬러그 문제는 이번이 처음이 아니다

프런트 6건이 깨졌던 원인은 로컬 DB의 `dgtour-영광`이 `hidden`으로 내려가고
`dgtour-영광-8`이 `active`가 된 것이다. 2026-09-03 14:34 정책 수집이 돌면서 바뀌었다.

**같은 문제를 2026-08-27에 이미 고쳤고, 그 수정이 병합되지 않았다.**

```
feature/dgtour-canonical-slug     develop 대비 8커밋 미병합
feature/stabilize-policy-trip-tests
```

전자는 크롤러가 `dgtour-{도시}-{페이지순번}`으로 슬러그를 만드는 근본 원인을 고친다
(`backend/scripts/crawl_dgtourcard.py:217`). 조사 문서는
`feature/dgtour-canonical-slug:docs/superpowers/specs/2026-08-27-dgtour-slug-investigation.md`.

이번에 B로 한 것은 **테스트를 DB에서 떼어낸 것**이지 원인 제거가 아니다.
픽스처의 `examplePolicySlug = "dgtour-영광"`은 일부러 그대로 뒀다 —
그 가지가 병합되면 DB도 이 값으로 돌아오기 때문이다.

### 동시 작업 규칙

이번에 한 트리를 둘이 같이 썼다. 커밋 금지 규칙 때문에 복구 지점이 없었고,
진단 목적의 `git checkout --`가 상대 작업을 덮을 뻔했다(확인 결과 유실 없음).

다음부터는 세션을 겹치지 않게 돌리고, 각자 자기 브랜치에 커밋해 경계를 만드는 편이 안전하다.
공유 자원은 파일만이 아니다 — DB, 컨테이너, 5173 서버, `.env`가 전부 하나다.

---

## 7. 열려 있는 결정

1. **Codex Task 3~8을 누가 이어갈지.** Task 3은 `backend/app/services/trips.py`를 건드려
   절반만 해두면 위험하다. Task 4~6은 `ItineraryDetailPage.tsx` / `app.css`에서 A와 정면으로 겹친다
2. **위 5절의 포트 처리**
3. **커밋 시점.** 지금은 미룬 상태다
