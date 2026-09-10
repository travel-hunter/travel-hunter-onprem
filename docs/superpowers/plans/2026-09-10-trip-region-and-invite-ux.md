# 일정 생성 지역 선택 단순화 + 초대 시트 전환

> 작성: 2026-09-10. 기준 커밋 `b78722d` (develop).
> 워크트리 3개 / 커밋 4개. 커밋은 사용자 확인 후.

## Context

새 일정 생성 화면에서 세 가지 문제가 보고됐다.

1. **모바일에서 시도 버튼 글자가 세로로 떨어진다.** `.trip-region-selector__sido-grid` 가
   `repeat(auto-fit, minmax(56px, 1fr))` 이고 버튼 좌우 padding 이 10px 이라, 360px 화면에서
   칸 하나가 약 59px, 글자 공간은 약 39px 이다. 여기에 이모지(인라인, 상속 16px)와 굵은 2글자가
   같이 들어가 넘치고, 한글은 음절 사이에서 끊기므로 "서 / 울" 처럼 세로로 보인다.
   `.trip-region-selector*` 규칙에는 `@media` 오버라이드도 `word-break` 도 없다 (`app.css:12202-12351`).
2. **세부 지역이 과하다.** 전체 / 추천 여행권역 / 시·군·구 세 그룹인데, 시·군·구는 경기 31개처럼
   길고 접기 UI까지 필요하다. 대부분의 사용자는 "○○ 전체" 면 충분하다.
3. **친구 초대가 별도 페이지로 이탈시킨다.** 일정 상세에서 `+ 친구 초대` 를 누르면
   `/friend-invite?tripId=` 로 화면이 통째로 바뀐다. 링크 하나 복사하자고 일정에서 나갔다 돌아와야 한다.

원하는 결과: 시도 버튼이 한 줄로 읽히고, 세부 지역은 전체가 기본값이며 추천 권역만 대안으로 남고,
초대는 일정 화면 위에 시트로 떠서 링크를 바로 복사할 수 있다.

## 결정된 사항 (사용자 확인)

- 시·군·구 제거는 **생성·편집 두 화면 모두**. 같은 `TripRegionSelector` 이므로 한 곳만 고친다.
- 시도를 누르면 **즉시 "○○ 전체" 가 선택**된다. 세부 지역을 안 건드려도 다음 단계로 갈 수 있다.
- 초대는 **기존 초대 페이지 내용을 그대로 재사용**해 일정 화면에서 시트로 띄운다.
  `/friend-invite` 라우트는 남긴다.
- 워크트리 2개 / 커밋 3개.
- 확인은 **5173** 에서 한다. 4174 는 사용자가 쓰는 중이라 건드리지 않는다.

## 범위 밖

- API 계약, 백엔드, `.agent/evals` 는 건드리지 않는다. `administrativeAreas` 는 응답에 그대로 두고
  화면에서만 안 그린다. 그래야 기존에 `admin:` id 로 저장된 일정의 복원이 계속 동작한다.
- `tripRegionEmoji`(일정 카드·상세 헤더 이모지), `preferenceDisplay.regionIcons`(프로필 관심 지역)는
  다른 기능이므로 유지한다. 이모지 제거는 **일정 생성 시도 버튼에 한정**한다.

---

## 워크트리 A — `feature/trip-region-selector-simplify`

경로: `.superpowers/worktrees/trip-region-selector-simplify`

### 커밋 1: 시도 버튼 이모지 제거

| 파일 | 변경 |
|---|---|
| `frontend/src/data/displayConfig.ts:183-208` | `TripCreatePrimaryRegion` 에서 `emoji` 필드와 17개 리터럴의 이모지 삭제 |
| `frontend/src/components/trip/TripRegionSelector.tsx:39` | prop 타입에서 `emoji?` 삭제 |
| `frontend/src/components/trip/TripRegionSelector.tsx:364` | `{sido.emoji && <span aria-hidden>…</span>}` 삭제 |
| `frontend/src/pages/itinerary/ItineraryCreatePage.tsx:577` | "이모지·순서" 주석을 "순서"로 정정 |
| `frontend/src/styles/app.css:12225` | `.trip-region-selector__sido` 에 `word-break: keep-all` 추가 |

`word-break: keep-all` 은 이 저장소가 이미 쓰는 관용구다 (`app.css:1679, 1727, 1783, 2315`).
이모지만 빼도 2글자가 들어가지만, 폰트나 글자 크기가 바뀌면 다시 음절 단위로 깨지므로 함께 막는다.

**검증**: `trip-create.test.tsx` 에 시도 버튼의 `textContent` 가 라벨과 정확히 같은지
(이모지가 섞이지 않는지) 확인하는 단언을 추가한다. 기존 테스트는 접근 가능한 이름으로만
단언하고 이모지는 `aria-hidden` 이라 이름에 안 들어가므로, 이 단언이 없으면 회귀를 못 잡는다.

### 커밋 2: 세부 지역을 전체 + 추천 권역으로 좁히고 전체를 기본값으로

| 파일 | 변경 |
|---|---|
| `frontend/src/components/trip/TripRegionSelector.tsx` | `CollapsibleAreaGroup` 컴포넌트, `administrativeGroups` 계산, 시·군·구 렌더 블록 2개(`:402-425`) 삭제 |
| 같은 파일 | 카탈로그 도착 시 선택이 없고 복원 대상도 없으면 `wholeArea` 를 자동 선택 |
| 같은 파일 | 복원된 값이 `administrative` 이면 "현재 선택" 으로 계속 보여준다 |
| `frontend/src/styles/app.css:12311-12351` | `.trip-region-selector__region*` 규칙 삭제 (접기 UI 전용, 다른 사용처 없음) |
| `docs/requirements.md:79` | FR-TRIP-007 개정 |
| `docs/implemented-feature-spec.md:54` | 세 그룹 → 두 그룹으로 정정 |

`resolveRestoredArea`(`:45-64`)는 그대로 둔다. 여전히 `administrativeAreas` 를 뒤져야
`admin:` id 로 저장된 일정이 되살아난다. 그리지 않는 것과 찾지 않는 것은 다르다.

**자동 선택 순서 주의**: 복원(`restoreAreaId`/`restoreAreaName`)이 자동 선택보다 먼저다.
편집 화면에서 저장된 지역이 "전체" 로 덮이면 조용한 데이터 손상이다.

**자동 선택은 `onChange` 가 아니라 `onRestore` 로 흘린다.** 기본값은 사용자의 선택이 아니다.
컴포넌트에 이미 그 통로가 있고(`:35-37` 주석이 이유를 적어 뒀다), `onChange` 로 보내면 두 곳이 깨진다.
생성 화면은 URL 에 `travelAreaId=whole:…` 을 쓰는데 그 id 는 되돌려 읽을 수 없고(아래 선행 결함),
편집 화면은 `regionTouched` 가 켜져 저장 때 원래 지역을 "○○ 전체" 로 갈아치운다.
생성 화면에는 `onRestore={(option) => applyTravelArea(recommendationFromOption(option))}` 를
추가한다 — `syncUrl` 없이.

**구현 중 드러난 것: 카탈로그 id 를 추천 목록과 대조하면 안 된다.**
`ItineraryCreatePage` 의 추천 조회 효과는 "선택한 지역이 추천 응답에 없으면 선택을 지운다"는
분기를 갖고 있다. 그런데 추천 API 는 구조상 `whole:` / `admin:` id 를 절대 돌려주지 않으므로,
카탈로그에서 자동 선택된 `whole:` 은 추천이 도착할 때마다 지워진다. 실측으로 확인했다 —
"제주 전체" 가 잠깐 눌렸다가 풀리고 `다음` 이 잠겼다. `isCatalogTravelAreaId()` 가드를
그 분기 하나에 넣어 막는다.

**`docs/requirements.md:79` 는 명시적 요구사항이다** — "17개 광역시도 아래의 행정 시·군·구를
빠짐없이 세부 지역으로 선택할 수 있다". 화면에서 빼면 이 문장이 거짓이 되므로 같은 커밋에서 고친다.

**검증**: `TripRegionSelector.test.tsx` 의 시·군·구/접기 테스트 4건을 교체한다.
- 시도 선택 직후 `"○○ 전체"` 가 `aria-pressed="true"` 인지
- `group` 이름 `"시·군·구"` 가 없는지
- `restoreAreaId` 가 `admin:` 일 때 그 이름이 화면에 남는지 (회귀 방지의 핵심)
- 기존 `:87` 의 버튼 개수 단언은 그룹이 줄어 수가 바뀌므로 같이 고친다

---

## 워크트리 B — `feature/trip-invite-sheet`

경로: `.superpowers/worktrees/trip-invite-sheet`

### 커밋 3: 일정 화면에서 초대 시트로 띄우기

| 파일 | 변경 |
|---|---|
| `frontend/src/pages/itinerary/FriendInvitePanel.tsx` (신규) | `FriendInvitePage` 본문(상태 + API 4개 + 카드 JSX)을 `{ tripId }` 를 받는 컴포넌트로 추출 |
| `frontend/src/pages/itinerary/FriendInvitePage.tsx` | `TopBar` + `<FriendInvitePanel />` 로 축소 |
| `frontend/src/pages/itinerary/ItineraryDetailPage.tsx:3815` | `<Link>` → 시트를 여는 `<button>` |
| 같은 파일 | `.sheet-backdrop` + `.trip-select-sheet` + `.sheet-head` 로 시트 마운트 |
| `frontend/src/app/__tests__/trip-detail.test.tsx:1421,1462,1483` | `role="link"` → `role="button"` |

**CSS 는 추가하지 않는다.** 이미 같은 껍데기를 `PlaceEditorSheet`(`ItineraryDetailPage.tsx:5510`)와
`TripDateEditorSheet`(`:4314`)가 쓴다. `.sheet-backdrop`(`app.css:4499`)이 하단 정렬 백드롭,
`.trip-select-sheet`(`:4508`)이 상단 라운드 + `max-height: min(86dvh,720px)` 스크롤 + safe-area
padding 을 이미 준다. 새 클래스를 만들면 같은 것이 셋이 된다.

추출한 패널은 `tripId` 를 prop 으로 받고 내부에서 `getTrip`/`getInviteState` 를 부른다.
일정 상세가 이미 trip 을 갖고 있지만, 페이지와 시트가 같은 코드를 쓰게 하는 편이
분기를 만드는 것보다 싸다. 요청은 시트를 열 때만 나간다.

**시트는 열자마자 링크가 보인다.** 목적이 링크를 넘기는 것이므로 "편집 링크 만들기" 를 한 번 더
누르게 하지 않는다. 패널에 `autoPrepareLink` prop 을 두고 시트에서만 켠다 — 전용 페이지는
그냥 둘러볼 수도 있어 기존 동작을 유지한다. 자동 준비는 조용히(`silent`) 돌아 안내 토스트를 띄우지 않고,
ref 로 한 번만 실행한다. 같은 김에 `prepareInviteLink` 에 실패 처리를 넣는다 — 지금은 실패하면
unhandled rejection 이고 화면에 아무 말도 안 나온다(수동 클릭 경로도 마찬가지였다).

**검증**: `trip-detail.test.tsx` 에 시트 테스트 1건 추가 — `+ 친구 초대` 를 누르면
`role="dialog"` 가 뜨고 그 안에 초대 링크 영역이 보이는지. viewer 에게 버튼이 없는
기존 테스트는 role 만 바꿔 유지한다.

---

---

## 워크트리 C — `feature/api-401-refresh-retry`

경로: `.superpowers/worktrees/api-401-refresh-retry`

### 커밋 4: 액세스 토큰이 만료된 뒤 첫 요청을 살려낸다

**증상** (사용자 보고): 사이트를 방치한 뒤 일정 탭에 들어가면 일정이 안 뜨고,
새로고침을 두 번 해야 돌아온다.

**추적한 경로** — 재현으로 확인했다(액세스 토큰만 무효화, 리프레시 쿠키는 유지):

1. `SessionProvider` 가 localStorage 에서 `currentUser` 를 **동기적으로** 복원한다(`session.tsx:92-96`).
2. 그래서 `ProtectedRoute` 의 `isSessionBootstrapping && !currentUser` 가 거짓이 되어
   **낡은 토큰인 채로 화면이 바로 렌더된다**(`App.tsx:81`).
3. 페이지 로더(`useAsyncResource`, deps `[]`)가 세션 검증과 **동시에** 돌아 401 을 맞는다.
   `client.ts` 의 `request()` 에는 401 재시도가 **아예 없었다**.
4. 그 사이 `verifyStoredSession` 이 새 토큰을 저장하므로 **다음** 새로고침에서만 성공한다.

측정: 1회차 새로고침 → 일정 카드 0 + "불러오지 못했어요", 2회차 → 61건 정상. 보고와 일치한다.

| 파일 | 변경 |
|---|---|
| `frontend/src/api/client.ts` | `setApiTokenRefresher()` / `refreshApiAccessToken()` 추가. 401 이면 토큰을 다시 받아 **요청당 한 번** 재시도 |
| 같은 파일 | `/api/auth/*` 는 재발급 대상에서 제외 (`/api/auth/refresh` 는 자기 자신을 부르고, 로그인 401 은 비밀번호가 틀린 것이다). `/api/me` 는 포함 — 낡은 토큰으로 부르는 첫 요청이라 오히려 필요하다 |
| `frontend/src/app/session.tsx` | 재발급 함수를 client 에 등록하고, 부트스트랩도 같은 통로를 쓰게 한다 |
| 같은 파일 | `getCurrentUser()` 성공 후 저장할 토큰을 `readStoredAuth()` 에서 다시 읽는다 — client 가 조용히 재발급했으면 `stored.accessToken` 을 되쓰는 순간 새 토큰을 덮어쓴다 |

**단일 실행(single-flight)이 핵심이다.** 백엔드 `auth_service.refresh` 는 기존 리프레시 토큰을
**revoke 하고 새로 발급한다**(`backend/app/services/auth.py:239`). 화면 하나가 뜰 때
`listTrips` / `getCurrentUser` / `listSavedPolicies` / `readRemoteProfile` 이 동시에 401 을 맞으므로,
묶지 않으면 재발급이 4번 나가고 2~4번째는 이미 폐기된 쿠키를 보내 401 → **멀쩡한 세션이 끊긴다.**
그래서 묶음은 client 한 곳에 두고 세션도 그 함수를 쓴다. 두 곳에 두면 각자 한 번씩 흘러 의미가 없다.

**검증**: `frontend/src/api/client.test.ts` (신규) 6건 — 401 후 새 토큰으로 재시도,
재시도도 401 이면 원래 오류를 올리고 한 번만 재시도, 재발급 실패 시 재시도 안 함,
`/api/auth/*` 는 건너뜀, **동시 401 세 건이 재발급을 한 번만 호출**, 그리고 묶음이 끝나면 풀림.
중복 제거를 빼면 다섯 번째가 실패하는 것까지 확인했다.

브라우저 실측(수정 후): 1회차 새로고침에 61건 정상 · 새로고침 없이 일정 탭 클릭도 정상 ·
리프레시 쿠키까지 폐기한 진짜 만료 세션은 `/login?redirect=/trips` 로 보내고 로컬 인증도 지운다(무한 재시도 없음).

**남긴 것**: `session.tsx` 의 `completeOAuthSession` 은 여전히 `appDataApi.refreshSession()` 을
직접 부른다. 같은 회전 위험을 갖지만 실패 시 예외를 던지는 계약이라 바꾸면 OAuth 오류 처리가 달라진다.
보고된 증상과 무관해서 그대로 뒀다.

---

## 발견된 선행 결함 (이번 범위 밖, 별도 처리 권고)

**1. `whole:` / `admin:` id 는 URL 로 왕복하지 못한다.**
사용자가 "○○ 전체" 를 직접 눌러 URL 에 `travelAreaId=whole:…` 이 남은 뒤 새로고침하면
"요청한 세부 지역을 찾을 수 없습니다" 가 뜬다. 그 id 를 추천 API(`listTravelAreaRecommendations`)로
조회하는데 그쪽은 카탈로그 계열 id 를 내지 않고, 게다가 `travelAreaId` 가 있으면
`travelAreaChoiceSido` 가 `null` 로 시작해(`ItineraryCreatePage.tsx:141`) 카탈로그조차 안 불러온다.
develop 에서 그대로 재현된다. 고치려면 `:141` 과 추천 조회 효과를 같이 손봐야 하므로 별도 커밋이다.
이번 변경은 기본값을 URL 에 쓰지 않으므로 이 구멍을 넓히지는 않는다.

**2.** `frontend/e2e-backend/backend-mode.spec.ts:163` 이 `"보기만 가능 링크 준비 완료"` 버튼을
기대하는데, `invite-oauth.test.tsx:116` 은 `"보기만 가능"` 이 **없어야** 한다고 단언한다.
초대 role 이 `editor` 하나로 좁혀질 때 e2e 만 안 따라간 흔적이다. 이번 변경과 무관한 기존 실패이고,
고치려면 e2e 를 `"함께 편집 링크 준비 완료"` 로 바꾸면 된다.

## 검증 결과 (2026-09-10, 5173 + 실제 로컬 백엔드)

프론트 게이트는 두 워크트리 모두 통과했다 — `npm run typecheck`, `vitest run`
(지역 360건 / 초대 361건), `npm run build`, `git diff --check`, UTF-8 스캔.
`npm test` 래퍼는 워크트리에 루트 `.env` 가 없어 compose DB 기동 단계에서 멈춘다(코드 문제 아님).
모지바케 검사는 따로 돌려 통과했다.

브라우저 실측:

| 확인 | 결과 |
|---|---|
| 시도 버튼 높이 320 / 360 / 390 / 430 / 1024 / 1440px | 전부 38px 한 줄, 가로 넘침 없음 (`frontend/AGENTS.md` 가 요구하는 다섯 폭 전부 포함) |
| 이모지를 되돌렸을 때 (대조) | 50px 2줄 — 이모지가 원인임이 확인됨 |
| 깨끗한 `/trips/new` | `제주 전체` 자동 선택, `다음` 활성, URL 에 `travelAreaId` 없음 |
| 경기 (원래 시·군·구 31개) | 그룹은 `전체`/`추천 여행권역` 둘뿐, 권역 버튼 4개, 접기 UI 없음 |
| 그 상태에서 새로고침 | 선택 유지, 오류 없음 |
| 기존 `admin:제주:제주시` 일정(id 251) 편집 열기 | `제주시` 가 `현재 선택` 으로 눌린 채 보존됨 |
| 같은 일정을 지역 안 건드리고 저장 | revision 1→2, `travel_area_id`/`region` 그대로 — 덮이지 않음 |
| 일정 상세에서 `+ 친구 초대` (390px) | 시트가 바닥에 붙어 뜨고(하단 여백 0) 실제 초대 링크 표시, 경로는 `/trips/251` 유지 |
| 같은 시트 1024 / 1440px | 가운데 정렬 모달로 전환(위아래 118px 대칭) — 기존 시트와 같은 동작 |
| 닫기 버튼 / 배경 클릭 | 둘 다 닫히고 일정 화면을 떠나지 않음 |
| 초대 이력 **없는** 새 일정(252)에서 시트 열기 | 클릭 185ms 만에 링크 표시, 추가 탭 없음, 토스트 없음, 경로 `/trips/252` 유지 |
| 같은 시트를 닫았다 다시 열기 | `trip_invites` 는 여전히 1건 — 열 때마다 초대가 늘지 않음 |
| `/friend-invite?tripId=251` (기존 페이지) | 그대로 동작, 뒤로가기가 `/trips/251` 로 해석됨 |

## 미실행

```bash
cd frontend && npm run test:e2e
```

워크트리에 루트 `.env` 가 없어 `scripts/run-backend-e2e.cjs` 가 compose 를 띄우는 단계에서 멈춘다
(`required variable VITE_API_BASE_URL is missing a value`). 게다가 위 선행 결함 2번 때문에
지금 develop 에서도 이 스위트는 `:163` 에서 실패한다. 개발서버나 루트 `.env` 가 있는 체크아웃에서 돌려야 한다.

## 검증 절차

```bash
# 각 워크트리에서
cd frontend
npm run typecheck
npm test

# 화면 확인은 5173 (4174 는 사용자 작업 중이라 사용 금지)
npm run dev -- --port 5173 --strictPort
```

화면에서 볼 것:

1. **360 / 390 / 430px** — 시도 버튼 글자가 한 줄인지. 세로로 떨어지면 실패.
2. 시도를 누른 직후 **"○○ 전체" 가 눌린 상태**인지, 세부 지역을 안 건드리고 다음 단계로 가지는지.
3. 세부 지역에 **시·군·구 그룹이 없는지**, 추천 여행권역은 남았는지.
4. 시·군·구로 저장된 기존 일정을 **편집** 화면에서 열었을 때 그 지역명이 그대로 보이는지.
   저장 후 "○○ 전체" 로 바뀌면 실패다.
5. 일정 상세에서 `+ 친구 초대` → **시트가 아래에서 올라오고**, 링크 복사가 되고,
   배경을 누르면 닫히는지. 1024 / 1440px 에서도 시트가 바닥에 붙는지.
