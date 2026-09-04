# 일정 화면 후속 조정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `2026-09-01-itinerary-day-strip` 이후 사용자 요청으로 붙은 일정 화면 조정과, 실제 DB 상태에 휘둘리던 프론트 테스트를 정리한다.

**Architecture:** 새 구조를 만들지 않는다. day 스트립은 기존 한 줄 스트립 위에 마우스 끌기와 표시 정보를 더하고, 장소 카드·수정 시트는 기존 dnd-kit 흐름과 편집 폼 안에서 바꾼다. 테스트는 `appDataApi` 경계에 목을 세워 실제 백엔드에서 떼어낸다.

**Tech Stack:** React, TypeScript, dnd-kit, Vitest/Testing Library, CSS

**Spec:** 없음. 화면을 보며 받은 요청을 그때그때 반영한 작업이라 선행 설계 문서가 없다. 이 문서가 그 기록을 대신한다.

> **이 문서는 작업 뒤에 썼다.** 계획 없이 진행된 변경이 커밋에 섞이는 것을 막기 위해,
> 실제로 한 일을 계획서 형식으로 되짚어 남긴다. 모든 단계는 이미 완료 상태다.
> 근거가 되는 커밋은 `6e5b4ee`, `ec41c2e` 다.

## Global Constraints

- 커밋 전 게이트: `npm run typecheck`, `npx vitest run`, `npm run build`, `npm run test:mojibake`, `git diff --check` 전부 통과.
- 화면 문구는 한글로 통일한다. 브라우저가 그리는 네이티브 위젯은 예외다.
- 실기기·브라우저 확인은 운영자 몫이다. 자동 테스트로 대신하지 않는다.
- `frontend/src/test/fixtures.ts` 의 `examplePolicySlug` 는 바꾸지 않는다. 미병합 `feature/dgtour-canonical-slug` 가 정한 정식 계약이다.
- push / PR / merge 는 하지 않는다.

## File Structure

- Modify `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`: 스트립 끌기, 스트립 버튼, 장소 수정 시트, 시간순 재배치, 헤더 마크업.
- Modify `frontend/src/pages/itinerary/ItineraryCreatePage.tsx`: 날짜 선택 문구.
- Modify `frontend/src/styles/app.css`: 스트립·카드·칩·헤더 스타일.
- Modify `frontend/src/app/__tests__/trip-detail.test.tsx`, `trip-create.test.tsx`: 위 변경의 회귀 테스트.
- Modify `frontend/src/app/__tests__/mypage.test.tsx`, `policies.test.tsx`: 실제 DB 의존 제거.

---

### Task 1: 카드 전체를 잡을 수 있게 한다

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Modify: `frontend/src/styles/app.css`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Consumes: `useSortable` 의 `attributes` / `listeners`.
- Produces: 카드 전체가 드래그 손잡이. 키보드 경로는 `sr-only` 버튼이 유지한다.

- [x] **Step 1: 손잡이 칸을 없애고 카드에 포인터 리스너를 붙인다**

`listeners` 에서 `onKeyDown` 을 빼고 나머지만 `<article>` 에 편다.

```ts
const { onKeyDown: _sortableKeyDown, ...cardPointerListeners } =
  sortableListeners as Record<string, unknown>;
```

`attributes` 는 카드에 붙이지 않는다. 거기 실린 `role="button"` 이 자식 요소를
접근성 트리에서 지워 카드 안의 버튼들이 사라진다. `attributes` 와 `onKeyDown` 은
`sr-only` 버튼에 남겨 키보드 드래그를 유지한다.

- [x] **Step 2: 그리드 열을 다시 맞춘다**

손잡이 칸이 사라져 2열이 된다. `.place-copy`, `.place-actions`, `.place-moving-badge`,
미리보기 변형, 그리고 520px 이하 미디어 블록의 `grid-column` 을 전부 한 칸씩 당긴다.
`padding-top: 34px` 은 손잡이 자리였으므로 없앤다.

- [x] **Step 3: 게이트 실행**

Run: `cd frontend; npx vitest run src/app/__tests__/trip-detail.test.tsx`
Expected: PASS.

---

### Task 2: 시간을 고치면 시간순으로 자리를 옮긴다

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Produces: `resolveTimeSortedPosition({ places, movingPlaceId, nextTime }): number`

- [x] **Step 1: 실패 테스트를 쓴다**

```ts
expect(resolveTimeSortedPosition({ places, movingPlaceId: "b", nextTime: "09:30" })).toBe(2);
// 시간이 빈 장소는 맨 위에 쌓는다.
expect(resolveTimeSortedPosition({ places, movingPlaceId: "b", nextTime: "" })).toBe(1);
```

- [x] **Step 2: 구현한다**

시간이 없으면 앞쪽의 무시간 장소 뒤에 붙이고, 시간이 있으면 자기보다 늦은 첫 장소 앞에 둔다.
손으로 순서를 옮겨 생긴 시간 역전은 건드리지 않는다 — 지금처럼 경고 문구만 붙인다.
**저장된 장소에만 적용한다.**

- [x] **Step 3: 게이트 실행** — PASS.

---

### Task 3: day 스트립을 마우스로 밀 수 있게 한다

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Modify: `frontend/src/styles/app.css`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Produces: `useDragScroll(externalRef?)` — `{ ref, onPointerDown, onClickCapture }`

- [x] **Step 1: 훅을 만든다**

`setPointerCapture` 는 쓰지 않는다. 캡처가 걸리면 뒤따르는 `click` 이 눌린 버튼이 아니라
캡처한 컨테이너로 가서 **날짜를 눌러도 선택이 안 된다.** 대신 `window` 에
`pointermove` / `pointerup` / `pointercancel` 을 걸어 줄 밖으로 나가도 끝을 놓치지 않는다.

- [x] **Step 2: 손가락은 제외한다**

```ts
if (event.pointerType === "touch") return;
```

모바일은 브라우저 기본 가로 스크롤이 이미 잘 돈다. 여기서 가로채면 관성까지 뺏는다.

- [x] **Step 3: 끌고 난 클릭을 먹는다**

6px 넘게 밀었으면 `onClickCapture` 에서 그 클릭 하나를 막는다. 안 그러면 밀다 멈춘
자리의 날짜가 선택된다. 밖에서 손을 떼면 `click` 이 아예 안 오므로, 다음
`pointerdown` 에서 플래그를 먼저 지운다.

- [x] **Step 4: 장소 수정 시트의 날짜 줄에도 같은 훅을 적용한다**

- [x] **Step 5: 게이트 실행** — PASS.

---

### Task 4: 스트립 버튼에 날짜와 장소 수를 함께 보여준다

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Modify: `frontend/src/styles/app.css`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Consumes: `trip.days[day]?.length`
- Produces: `DroppableDayTab` 에 `count: number` 추가

- [x] **Step 1: 알약을 카드형으로 바꾼다**

`min-width: 74px`, `min-height: 62px`, 3줄(Day N / 날짜 / N곳). 장소 수정 시트의
날짜 칩과 같은 값이다 — 같은 것을 고르는 자리이므로 같은 모양이어야 한다.

- [x] **Step 2: 드롭 대상 폭을 평소 폭과 같게 맞춘다**

```css
.prototype-trip-detail-screen .day-tab.drop-target { min-width: 74px; }
```

커지면 드래그를 시작하는 순간 30개 탭이 한꺼번에 밀려 가운데 정렬이 어긋난다.
테스트가 이 불변조건을 지킨다.

- [x] **Step 3: 드래그가 올라온 날짜 표시를 링으로 바꾼다**

바탕을 진하게 채우면 날짜와 장소 수 글자가 같은 붉은색이라 묻힌다.
`box-shadow` 링으로 알린다.

- [x] **Step 4: 게이트 실행** — PASS.

---

### Task 5: 장소 수정에서 날짜를 고를 수 있게 한다

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Modify: `frontend/src/styles/app.css`

- [x] **Step 1: 네이티브 select 를 칩 줄로 바꾼다**

네이티브 `<option>` 높이는 운영체제가 정해 손댈 수 없다. 칩 줄로 두면 칸을
넉넉히 잡고 그 날 장소 수까지 함께 보여줄 수 있다.

- [x] **Step 2: 선택된 날짜가 보이게 스크롤한다**

35일 일정에서 Day 30 을 열면 줄 밖에 있다.

- [x] **Step 3: 게이트 실행** — PASS.

---

### Task 6: 일정 만들기의 날짜 선택 문구를 한글로 바꾼다

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryCreatePage.tsx`
- Test: `frontend/src/app/__tests__/trip-create.test.tsx`

- [x] **Step 1: 영어 두 곳을 고친다**

```
Select a start and end date for the trip.  ->  출발일과 도착일을 고릅니다.
Done                                       ->  완료
```

- [x] **Step 2: 회귀 테스트를 넣는다**

달력을 열고 `완료` 버튼을 확인한 뒤, 달력 안에 세 글자 이상 영어 낱말이 없는지 본다.

```ts
expect(calendar.textContent ?? "").not.toMatch(/[A-Za-z]{3,}/);
```

- [x] **Step 3: 게이트 실행** — PASS.

---

### Task 7: 상세 헤더의 제목을 뒤로가기 버튼 옆으로 옮긴다

**Files:**
- Modify: `frontend/src/styles/app.css`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

- [x] **Step 1: 히어로 여백을 다시 잡는다**

```
padding: 54px 88px 16px 20px  ->  16px 88px 18px 72px
min-height: 156px             ->  120px
```

`.top-bar` 는 히어로 **밖에서** 절대 배치된다(`app.css:7069`). 버튼의 `left` 와
히어로의 `padding-left` 가 같은 기준점이 아니라, 버튼 폭만 더해 계산하면
글자가 버튼에 깔린다. 계산 대신 넉넉히 띄운다.

- [x] **Step 2: 회귀 테스트를 넣는다**

왼쪽 여백이 버튼 오른쪽 끝(34px)보다 작아지면 글이 깔린다. 그 하한을 지킨다.

- [x] **Step 3: 게이트 실행** — PASS.

---

### Task 8: 마이페이지·정책 테스트를 실제 DB에서 떼어낸다

**Files:**
- Modify: `frontend/src/app/__tests__/mypage.test.tsx`
- Modify: `frontend/src/app/__tests__/policies.test.tsx`

**Interfaces:**
- Produces: `installExamplePolicyApi({ saved })` — 인메모리 찜 저장소 위의 `appDataApi` 목 묶음

- [x] **Step 1: 원인을 가른다**

`appDataApi` 는 `backendApi` 이고 `client.ts` 는 `http://127.0.0.1:8000` 을 친다.
목이 아니라 실제 백엔드다. 2026-09-03 14:34 정책 수집이 돌며 `dgtour-영광` 이
hidden 이 되고 `dgtour-영광-8` 이 active 가 되자 6건이 깨졌다.

들어오는 지점은 하나다. `getPolicy` 가 DB 행을 읽고, 그 `slug` 가 이후 모든 링크와
스파이 인자로 흘러간다. 상세 화면 자체는 정상이다 — 별칭 해석이 옛 주소도 받아준다
(`backend/app/services/policies.py:247`). 다만 응답의 `slug` 가 달라 링크가 달라진다.

- [x] **Step 2: `getPolicy` 만으로 되는 4건을 고친다**

- [x] **Step 3: 목이 없던 2건은 인메모리 가짜 저장소로 돌린다**

`getPolicy` / `listPolicies` / `listSavedPolicies` / `savePolicy` / `removeSavedPolicy` 를
하나의 `Set` 위에서 일관되게 굴린다. 저장하면 목록에 뜨고 해제하면 사라지는
흐름이 그대로 살아 검증이 비지 않는다.

`listPolicies` 까지 막아야 한다. 관심 필터가 **전체 목록을 저장 슬러그로 거르는**
방식이라(`PolicyPages.tsx:674`) 찜 상태만 가짜로 만들면 링크가 안 나온다.

- [x] **Step 4: 스파이 누수를 막는다**

`onTestFinished` 복원은 옆 테스트를 오염시켰다. describe 수준 `afterEach` 에
등록해 되돌린다. 개별 스파이는 `finally` 에서 복원한다.

- [x] **Step 5: 게이트 실행** — 두 파일 38 passed.

---

## 실행 결과 (2026-09-04)

| 항목 | 결과 |
|---|---|
| `npm run typecheck` | PASS |
| `npx vitest run` | **344 passed / 0 failed** (28 files) |
| `npm run build` | PASS |
| `npm run test:mojibake` | 없음 |
| `git diff --check` | 깨끗 |

커밋: `6e5b4ee`(Task 1~7), `ec41c2e`(Task 8).

Task 1~7 은 같은 파일에 지역·달력 통합 작업과 겹쳐 있어 파일 단위로 나눌 수 없었다.
`git add -p` 가 이 환경에서 대화형으로 돌지 않아 한 커밋에 담았고, 커밋 메시지에
네 갈래를 나눠 적었다.

## 남은 것

- [ ] **실기기·브라우저 확인.** 30일 일정으로 스트립 끌기, 날짜 클릭, 카드 드래그 중
      탭 폭 흔들림, 장소 수정 시트, 헤더 제목 줄바꿈을 눈으로 본다.
- [ ] **미해결 버그.** 카드를 잡고 좌우 이동영역으로 날짜를 옮긴 뒤 위로 올리면
      스크롤 고정이 듣지 않는다. 자동 스크롤 제동은 `autoScrollBrakedRef` 로
      한 번만 `autoScrollBrakeTick` 을 올려 dnd-kit 의 `canScroll` 정체성을 바꾸는
      구조다. 날짜 전환 시 그 상태가 어떻게 되는지가 다음 확인 지점이다.
      (`ItineraryDetailPage.tsx:2439` 의 타이머 effect 와 `:2149` 의 `canScroll`)

## 이 계획이 하지 않는 것

- 지역·달력 통합 — `2026-09-03-trip-region-calendar-unification.md` 소관이다.
- dgtour 슬러그의 근본 수정 — 크롤러가 페이지 순번을 붙이는 문제이고
  `feature/dgtour-canonical-slug` 에 미병합으로 남아 있다.
- 상세의 `여행기간 수정` 시트 진입점. `openDateEditor` 가 어디서도 호출되지 않아
  열 방법이 없다. HEAD 이전부터 그렇다. 진입점을 만들지 시트를 지울지는 제품 판단이다.
