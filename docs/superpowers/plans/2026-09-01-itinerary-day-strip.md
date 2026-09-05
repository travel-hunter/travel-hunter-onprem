# Itinerary Day Strip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 30일짜리 일정에서 Day 선택이 화면을 뒤덮지 않게 하고, 드래그 중 의도치 않은 날짜 전환을 없앤다.

**Architecture:** Day 탭을 감싸기(wrap)에서 가로 한 줄 스트립으로 바꾸고, 보고 있는 날짜를 항상 중앙에 둔다. 날짜 전환은 탭 위를 지나가는 것으로 발동하지 않고, 화면 좌우 가장자리 이동영역에 머무는 것으로 발동한다. PC에서는 휠과 화살표 키가 같은 일을 한다. 탭에 직접 드롭해 옮기는 기존 기능은 그대로 둔다.

**Tech Stack:** React, TypeScript, dnd-kit, CSS, Vitest, Testing Library

**Spec:** 대화형 시안(`Day 스트립 실험대`)에서 사용자가 값을 직접 조절해 확정했다. 확정값은 아래 Global Constraints에 있다.

## Global Constraints

- 확정된 값. 상수로 노출하고 이 값을 그대로 쓴다.
  - 이동영역 폭 `80px`
  - 머무는 시간(첫 전환) `900ms`
  - 반복 간격 `620ms`
  - 바깥쪽 가속 `2.8배` (안쪽 경계 620ms → 맨 끝 221ms)
  - 휠 민감도 `100`
  - 집는 시간 `800ms` — **TouchSensor 에만.** `MouseSensor` 의 `distance: 8` 은 건드리지 않는다.
- 화면 디자인을 바꾸지 않는다. 알약 모양·색·크기·카드·타임라인·아이콘·레이아웃 그대로.
- 탭에 직접 드롭해서 옮기는 기능을 유지한다. 없애는 것은 **탭 위를 지나갈 때 화면이 바뀌는 것**뿐이다.
- 2026-08-26 `itinerary-drag-viewport-lock` 의 결과물을 되돌리지 않는다.
  `layoutShiftCompensation: false`, `autoScroll.canScroll` 상한, `overflow-anchor: none`,
  드래그 중 타임라인 `min-height` 잠금은 그대로 둔다.
- 백엔드·API·스키마·마이그레이션·Docker·정책 데이터를 건드리지 않는다.
- 지도 컴포넌트를 건드리지 않는다.
- 의존성을 추가하지 않는다.
- 변경 범위는 아래 File Structure 의 세 파일로 제한한다.
- `AGENTS.md` 의 UTF-8 규칙을 지킨다. 한글이 든 파일은 UTF-8 명시 도구로만 쓰고,
  마무리 전에 `git diff --check` 와 U+FFFD 검사를 돌린다.

## File Structure

- Modify `frontend/src/styles/app.css`: `.day-tabs` 를 한 줄 스트립으로. 스크롤바는 이미 감춰져 있다.
- Modify `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`:
  상수, 중앙 정렬 효과, 가장자리 이동영역, 휠·키보드, TouchSensor 지연.
- Modify `frontend/src/app/__tests__/trip-detail.test.tsx`: 회귀 테스트.

---

### Task 1: Day 탭을 가로 한 줄 스트립으로

**Files:**
- Modify: `frontend/src/styles/app.css` (`.prototype-trip-detail-screen .day-tabs`)
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Produces: `dayTabsRef` — 스트립 DOM 참조. Task 2 가 중앙 정렬에 쓴다.

- [x] **Step 1: 실패하는 테스트를 쓴다**

`.day-tabs` 가 `nowrap` 이고 가로 스크롤이 되는지 스타일시트에서 확인한다.

```ts
it("day tabs stay on one row and scroll horizontally", () => {
  const css = readAppCss();
  expect(css).toMatch(
    /\.prototype-trip-detail-screen \.day-tabs\s*\{[^}]*flex-wrap:\s*nowrap/s,
  );
  expect(css).toMatch(
    /\.prototype-trip-detail-screen \.day-tabs\s*\{[^}]*overflow-x:\s*auto/s,
  );
});
```

- [x] **Step 2: 테스트가 실패하는지 확인한다**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx -t "one row"`
Expected: FAIL — 현재는 `flex-wrap: wrap` 이고 `overflow-x: visible` 이다.

- [x] **Step 3: CSS 를 고친다**

```css
.prototype-trip-detail-screen .day-tabs {
  display: flex;
  flex-wrap: nowrap;
  gap: 6px;
  margin-bottom: 16px;
  overflow-x: auto;
  padding: 6px 16px 8px;
  scrollbar-width: none;
  /* 첫날·마지막날도 가운데에 설 수 있도록 좌우 여백은 JS 가 넣는다 */
}
```

`margin-bottom` 은 22px 에서 16px 로 줄인다. 한 줄이 되어 아래 여백이 상대적으로 커 보인다.

- [x] **Step 4: 스트립 참조를 단다**

`ItineraryDetailPage.tsx` 의 `day-tabs` div 에 ref 를 붙인다.

```tsx
const dayTabsRef = useRef<HTMLDivElement | null>(null);
...
<div
  aria-label="일정 날짜 선택"
  className="day-tabs"
  data-itinerary-day-tabs
  ref={dayTabsRef}
>
```

- [x] **Step 5: 테스트가 통과하는지 확인한다**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx -t "one row"`
Expected: PASS

- [x] **Step 6: 커밋**

```bash
git add frontend/src/styles/app.css frontend/src/pages/itinerary/ItineraryDetailPage.tsx frontend/src/app/__tests__/trip-detail.test.tsx
git commit -m "feat(itinerary): day 탭을 가로 한 줄 스트립으로"
```

---

### Task 2: 보고 있는 날짜를 항상 가운데로

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Consumes: `dayTabsRef` (Task 1)
- Produces: `centerActiveDayTab()` — 활성 탭을 중앙으로. Task 3·4 가 날짜 전환 후 호출한다.

- [x] **Step 1: 실패하는 테스트를 쓴다**

```ts
it("centers the active day tab and pads both ends", () => {
  // 첫날 선택 시 좌측 여백이 생겨 Day 1 이 중앙에 올 수 있어야 한다
  const strip = screen.getByLabelText("일정 날짜 선택");
  expect(strip.style.paddingLeft).not.toBe("");
  expect(strip.style.paddingRight).not.toBe("");
});
```

- [x] **Step 2: 테스트가 실패하는지 확인한다**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx -t "centers the active"`
Expected: FAIL — 여백이 비어 있다.

- [x] **Step 3: 순수 함수로 계산부를 뺀다**

테스트하기 쉽도록 DOM 접근과 계산을 나눈다.

```ts
/** 첫날·마지막날도 가운데에 설 수 있도록 양 끝에 줄 여백 */
export function resolveDayStripPadding(
  containerWidth: number,
  firstWidth: number,
  lastWidth: number,
): { left: number; right: number } {
  return {
    left: Math.max(0, (containerWidth - firstWidth) / 2),
    right: Math.max(0, (containerWidth - lastWidth) / 2),
  };
}

/** 활성 탭을 중앙에 놓는 scrollLeft */
export function resolveDayStripScrollLeft({
  tabOffsetLeft,
  tabWidth,
  containerWidth,
  scrollWidth,
}: {
  tabOffsetLeft: number;
  tabWidth: number;
  containerWidth: number;
  scrollWidth: number;
}): number {
  const target = tabOffsetLeft - (containerWidth - tabWidth) / 2;
  return Math.max(0, Math.min(target, Math.max(0, scrollWidth - containerWidth)));
}
```

- [x] **Step 4: 효과를 붙인다**

`visibleDay` 가 바뀌거나 `dayNumbers` 가 바뀌면 여백을 다시 계산하고 활성 탭을 중앙으로 보낸다.
드래그 중에는 `behavior: "auto"` 로, 평소에는 `"smooth"` 로 움직인다. 드래그 중 부드러운 스크롤은
포인터 판정과 어긋난다.

```tsx
useEffect(() => {
  const strip = dayTabsRef.current;
  if (!strip) return;
  const first = strip.firstElementChild as HTMLElement | null;
  const last = strip.lastElementChild as HTMLElement | null;
  if (!first || !last) return;
  const pad = resolveDayStripPadding(strip.clientWidth, first.offsetWidth, last.offsetWidth);
  strip.style.paddingLeft = `${pad.left}px`;
  strip.style.paddingRight = `${pad.right}px`;

  const active = strip.querySelector<HTMLElement>(`[data-day-drop-id="${dayDropId(visibleDay)}"]`);
  if (!active) return;
  strip.scrollTo({
    left: resolveDayStripScrollLeft({
      tabOffsetLeft: active.offsetLeft,
      tabWidth: active.offsetWidth,
      containerWidth: strip.clientWidth,
      scrollWidth: strip.scrollWidth,
    }),
    behavior: draggingPlaceId ? "auto" : "smooth",
  });
}, [visibleDay, dayNumbers.length, draggingPlaceId]);
```

- [x] **Step 5: 순수 함수 단위 테스트를 더한다**

```ts
it("resolveDayStripScrollLeft clamps at both ends", () => {
  expect(
    resolveDayStripScrollLeft({ tabOffsetLeft: 0, tabWidth: 60, containerWidth: 390, scrollWidth: 2000 }),
  ).toBe(0);
  expect(
    resolveDayStripScrollLeft({ tabOffsetLeft: 1980, tabWidth: 60, containerWidth: 390, scrollWidth: 2000 }),
  ).toBe(1610);
});
```

- [x] **Step 6: 테스트가 통과하는지 확인한다**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx -t "day strip"`
Expected: PASS

- [x] **Step 7: 커밋**

```bash
git commit -am "feat(itinerary): 보고 있는 day 를 스트립 가운데로 정렬"
```

---

### Task 3: 탭 호버 자동 전환을 가장자리 이동영역으로 교체

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Consumes: `centerActiveDayTab()` (Task 2), `placeDragPointerRef`
- Produces: `resolveDayEdgeZone()`, `resolveDayEdgeInterval()` — 순수 함수. Task 5 테스트가 쓴다.

- [x] **Step 1: 실패하는 테스트를 쓴다**

지나가는 것으로는 안 바뀌고, 머무는 것으로만 바뀌어야 한다.

```ts
it("does not switch day when the pointer merely crosses the tab row", () => {
  // 탭 위 통과는 전환을 예약하지 않는다
  expect(
    resolveDayEdgeZone({ pointerX: 200, left: 0, right: 390, edgeWidth: 80 }),
  ).toBe(0);
});

it("arms the edge zone only inside the edge band", () => {
  expect(resolveDayEdgeZone({ pointerX: 40, left: 0, right: 390, edgeWidth: 80 })).toBe(-1);
  expect(resolveDayEdgeZone({ pointerX: 360, left: 0, right: 390, edgeWidth: 80 })).toBe(1);
});

it("accelerates toward the outer edge", () => {
  // 안쪽 경계 620ms, 맨 끝 620/2.8
  expect(resolveDayEdgeInterval(0)).toBe(620);
  expect(Math.round(resolveDayEdgeInterval(1))).toBe(221);
});
```

- [x] **Step 2: 테스트가 실패하는지 확인한다**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx -t "edge"`
Expected: FAIL — 함수가 없다.

- [x] **Step 3: 상수와 순수 함수를 넣는다**

`DAY_SWITCH_DELAY_MS` 를 지우고 아래로 대체한다.

```ts
/** 화면 좌우 끝에서 이만큼이 날짜 넘김 구역 */
export const DAY_EDGE_WIDTH_PX = 80;
/** 이동영역에 들어간 뒤 첫 전환까지. 스쳐 지나가는 것과 머무는 것을 가른다 */
export const DAY_EDGE_FIRST_DELAY_MS = 900;
/** 계속 대고 있을 때 다음 날짜까지 */
export const DAY_EDGE_REPEAT_MS = 620;
/** 맨 끝에서는 반복 간격을 이 값으로 나눈다 */
export const DAY_EDGE_ACCEL = 2.8;

/** -1 왼쪽 · 0 없음 · 1 오른쪽 */
export function resolveDayEdgeZone({
  pointerX, left, right, edgeWidth = DAY_EDGE_WIDTH_PX,
}: { pointerX: number | null; left: number; right: number; edgeWidth?: number }): -1 | 0 | 1 {
  if (pointerX == null) return 0;
  if (pointerX >= left && pointerX < left + edgeWidth) return -1;
  if (pointerX <= right && pointerX > right - edgeWidth) return 1;
  return 0;
}

/** 안쪽 경계 0 → 맨 끝 1 */
export function resolveDayEdgeDepth({
  pointerX, left, right, zone, edgeWidth = DAY_EDGE_WIDTH_PX,
}: { pointerX: number; left: number; right: number; zone: -1 | 1; edgeWidth?: number }): number {
  const raw = zone < 0
    ? (left + edgeWidth - pointerX) / edgeWidth
    : (pointerX - (right - edgeWidth)) / edgeWidth;
  return Math.max(0, Math.min(1, raw));
}

export function resolveDayEdgeInterval(depth: number): number {
  return DAY_EDGE_REPEAT_MS / (1 + (DAY_EDGE_ACCEL - 1) * Math.max(0, Math.min(1, depth)));
}
```

- [x] **Step 4: 탭 호버 전환을 걷어낸다**

`handlePlaceDragOver` 안에서 `shouldScheduleDaySwitch` 로 `setActiveDay` 를 예약하던 블록을 지운다.
`setDragOverDay` 로 탭을 강조하는 것과 `crossDayDragPreview` 는 남긴다 — 탭에 드롭해서 옮기는 길이
살아 있어야 하기 때문이다.

- [x] **Step 5: 가장자리 이동영역을 타이머로 돌린다**

포인터가 멈춰 있어도 진행해야 하므로 `pointermove` 가 아니라 `setInterval` 로 돈다.
`moveDrag` 안에서 처리하면 손가락을 흔들어야만 날짜가 넘어간다.

```tsx
useEffect(() => {
  if (!draggingPlaceId) return;
  const container = document.querySelector<HTMLElement>(".app-container");
  if (!container) return;
  let nextAt = 0;
  let zone: -1 | 0 | 1 = 0;
  const id = window.setInterval(() => {
    const pointer = placeDragPointerRef.current;
    const rect = container.getBoundingClientRect();
    const next = resolveDayEdgeZone({ pointerX: pointer?.x ?? null, left: rect.left, right: rect.right });
    if (next === 0) { zone = 0; nextAt = 0; return; }
    if (next !== zone) { zone = next; nextAt = Date.now() + DAY_EDGE_FIRST_DELAY_MS; return; }
    if (Date.now() < nextAt) return;
    const depth = resolveDayEdgeDepth({
      pointerX: pointer!.x, left: rect.left, right: rect.right, zone: next,
    });
    setActiveDay((current) => {
      const target = Math.min(Math.max(current + next, 1), dayNumbers.length);
      if (target !== current) updateDetailSearchParams({ day: target, place: null });
      return target;
    });
    nextAt = Date.now() + resolveDayEdgeInterval(depth);
  }, 50);
  return () => window.clearInterval(id);
}, [draggingPlaceId, dayNumbers.length]);
```

- [x] **Step 6: 테스트가 통과하는지 확인한다**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx -t "edge"`
Expected: PASS

- [x] **Step 7: 기존 날짜 드래그 회귀 테스트를 돌린다**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx`
Expected: PASS. 탭 드롭으로 옮기는 기존 테스트가 깨지면 Step 4 에서 너무 많이 걷어낸 것이다.

- [x] **Step 8: 커밋**

```bash
git commit -am "feat(itinerary): 탭 호버 자동 전환을 가장자리 이동영역으로 교체"
```

---

### Task 4: 드래그 중 휠과 화살표 키

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Consumes: `draggingPlaceId`, `setActiveDay`
- Produces: `DAY_WHEEL_THRESHOLD` 상수

- [x] **Step 1: 실패하는 테스트를 쓴다**

```ts
it("changes day by wheel while dragging", () => {
  // 누적이 임계값을 넘으면 하루 넘어간다
  expect(resolveWheelSteps(0, 100)).toEqual({ steps: 1, rest: 0 });
  expect(resolveWheelSteps(60, 60)).toEqual({ steps: 1, rest: 20 });
  expect(resolveWheelSteps(0, -250)).toEqual({ steps: -2, rest: -50 });
});
```

- [x] **Step 2: 테스트가 실패하는지 확인한다**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx -t "wheel"`
Expected: FAIL

- [x] **Step 3: 순수 함수와 상수를 넣는다**

```ts
/** 굴림량이 이만큼 쌓여야 하루. 마우스 휠 한 칸이 보통 100 안팎이다 */
export const DAY_WHEEL_THRESHOLD = 100;

export function resolveWheelSteps(
  carried: number,
  delta: number,
  threshold: number = DAY_WHEEL_THRESHOLD,
): { steps: number; rest: number } {
  const total = carried + delta;
  const steps = Math.trunc(total / threshold);
  return { steps, rest: total - steps * threshold };
}
```

- [x] **Step 4: 리스너를 붙인다**

드래그 중에만 산다. 드래그 중에는 이미 `itinerary-place-drag-scroll-locked` 로 페이지 스크롤이
잠겨 있어 휠이 놀고 있다.

```tsx
useEffect(() => {
  if (!draggingPlaceId) return;
  let carried = 0;
  const shift = (step: number) => {
    setActiveDay((current) => {
      const target = Math.min(Math.max(current + step, 1), dayNumbers.length);
      if (target !== current) updateDetailSearchParams({ day: target, place: null });
      return target;
    });
  };
  const onWheel = (event: WheelEvent) => {
    event.preventDefault();
    const delta = Math.abs(event.deltaY) >= Math.abs(event.deltaX) ? event.deltaY : event.deltaX;
    const { steps, rest } = resolveWheelSteps(carried, delta);
    carried = rest;
    if (steps) shift(steps);
  };
  const onKey = (event: KeyboardEvent) => {
    if (event.key === "ArrowLeft") { event.preventDefault(); shift(-1); }
    else if (event.key === "ArrowRight") { event.preventDefault(); shift(1); }
    else if (event.key === "Home") { event.preventDefault(); shift(-dayNumbers.length); }
    else if (event.key === "End") { event.preventDefault(); shift(dayNumbers.length); }
  };
  window.addEventListener("wheel", onWheel, { passive: false });
  window.addEventListener("keydown", onKey);
  return () => {
    window.removeEventListener("wheel", onWheel);
    window.removeEventListener("keydown", onKey);
  };
}, [draggingPlaceId, dayNumbers.length]);
```

- [x] **Step 5: 테스트가 통과하는지 확인한다**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx -t "wheel"`
Expected: PASS

- [x] **Step 6: 커밋**

```bash
git commit -am "feat(itinerary): 드래그 중 휠과 화살표 키로 날짜 전환"
```

---

### Task 5: 터치 집는 시간을 800ms 로

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

- [x] **Step 1: 실패하는 테스트를 쓴다**

```ts
it("uses a long touch hold and leaves the mouse sensor alone", () => {
  expect(PLACE_DRAG_TOUCH_DELAY_MS).toBe(800);
  expect(PLACE_DRAG_TOUCH_TOLERANCE_PX).toBe(8);
  expect(PLACE_DRAG_MOUSE_DISTANCE_PX).toBe(8);
});
```

- [x] **Step 2: 테스트가 실패하는지 확인한다**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx -t "touch hold"`
Expected: FAIL — 상수가 없다.

- [x] **Step 3: 상수를 뽑고 센서에 건다**

```ts
/** 목록 스크롤과 카드 집기를 가르는 값. 짧으면 스크롤하려다 카드가 집힌다 */
export const PLACE_DRAG_TOUCH_DELAY_MS = 800;
export const PLACE_DRAG_TOUCH_TOLERANCE_PX = 8;
/** 마우스는 홀드가 아니라 거리 기준이다. 여기에 지연을 걸면 안 된다 */
export const PLACE_DRAG_MOUSE_DISTANCE_PX = 8;
```

```tsx
const dragSensors = useSensors(
  useSensor(MouseSensor, {
    activationConstraint: { distance: PLACE_DRAG_MOUSE_DISTANCE_PX },
  }),
  useSensor(TouchSensor, {
    activationConstraint: {
      delay: PLACE_DRAG_TOUCH_DELAY_MS,
      tolerance: PLACE_DRAG_TOUCH_TOLERANCE_PX,
    },
  }),
  useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
);
```

- [x] **Step 4: 테스트가 통과하는지 확인한다**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx -t "touch hold"`
Expected: PASS

- [x] **Step 5: 커밋**

```bash
git commit -am "feat(itinerary): 터치 집는 시간을 800ms 로"
```

---

### Task 6: 전체 게이트와 개발서버 확인

**Files:**
- Modify: `CHECKLIST.md`

- [x] **Step 1: 프런트 게이트**

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx
npm run typecheck
npm run test:mojibake
npm run build
```

Expected: 전부 PASS

- [x] **Step 2: 전체 프런트 테스트**

Run: `cd frontend && npm test -- --run`
Expected: PASS. 한 파일만 돌리지 않는다 — 그 구멍으로 예전에 `place-edit` 파손을 놓친 적이 있다.

- [x] **Step 3: 인코딩과 공백**

```bash
git diff --check
```
그리고 변경된 파일에 U+FFFD 가 없는지 확인한다.

- [ ] **Step 4: 개발서버 반영은 PR 경로로 간다**

`develop` 에 머지되면 dev Jenkins 가 자동 배포한다. 직접 서버를 만지지 않는다.
푸시와 PR 은 Codex 가 한다.

- [x] **Step 5: 실기기 확인 목록을 남긴다**

`CHECKLIST.md` 에 아래를 미확인으로 적는다. 브라우저·실기기 확인은 운영자 몫이다.

```
[ ] 30일 일정에서 Day 줄이 한 줄로 보이고 보고 있는 날짜가 가운데에 온다
[ ] Day 1 과 Day 30 도 가운데에 선다
[ ] 카드를 들고 목록 위를 위아래로 움직여도 날짜가 안 바뀐다
[ ] 좌우 끝에 0.9초 들고 있으면 날짜가 넘어간다
[ ] 계속 대고 있으면 이어서 넘어가고, 바깥쪽일수록 빠르다
[ ] 카드를 왼쪽 아이콘 쪽에서 집어도 곧바로 날짜가 안 넘어간다
[ ] 손가락을 0.8초 미만으로 떼면 집히지 않고 목록이 스크롤된다
[ ] PC 에서 드래그 중 휠로 날짜가 바뀐다
[ ] PC 에서 ← → Home End 로 날짜가 바뀐다
[ ] 탭에 직접 드롭해서 옮기는 기존 동작이 그대로다
[ ] 드래그 중 화면이 위아래로 출렁이지 않는다
```

- [x] **Step 6: 커밋**

```bash
git add CHECKLIST.md
git commit -m "docs: day 스트립 실기기 확인 목록"
```

---

## Self-Review

**미해결로 남기는 것**

- 밀어서 스냅됐을 때 그 날짜를 자동 선택할지는 정하지 않았다. 지금은 가운데로 오기만 하고
  선택은 탭으로만 한다. 훑어보다 의도치 않게 날짜가 바뀌는 것을 피하기 위해서다.
- 스트립을 손으로 밀어 탐색하는 관성·스냅은 이번 범위에 넣지 않았다.
  `overflow-x: auto` 의 기본 터치 스크롤로 충분한지 실기기에서 먼저 본다.
- `resolveDayZoneRect` 는 탭 강조와 드롭 판정에 계속 쓰이므로 지우지 않는다.
  자동 전환 예약에서만 떼어낸다.

**확인이 필요한 값**

- 집는 시간 800ms 는 일반적인 길게 누르기(300~500ms)보다 길다. 목록 스크롤을 확실히 살리는
  대신 카드가 늦게 잡힌다. 실기기에서 답답하면 500ms 부터 다시 본다.

---

## 실행 결과 (2026-09-01, 기록은 2026-09-05)

커밋 `d0f77a8`. 계획대로 구현됐고 산출물이 코드에 남아 있다 —
`DAY_EDGE_WIDTH_PX` / `DAY_EDGE_FIRST_DELAY_MS` / `DAY_EDGE_REPEAT_MS` /
`DAY_EDGE_ACCEL` / `PLACE_DRAG_TOUCH_DELAY_MS`, `resolveDayEdgeZone`,
`resolveDayStripScrollLeft`, 휠·화살표 처리.

확정된 조작값: 이동영역 80px, 머무는 시간 900ms, 반복 간격 620ms,
바깥쪽 가속 2.8배, 휠 민감도 100, 터치 집는 시간 800ms.

**Task 6 Step 4 만 미완이다.** push / PR 은 이 세션의 권한 밖이라 개발서버에
아직 반영되지 않았다. 실기기 확인 목록은 `CHECKLIST.md` Active Risks 에 남겼다.

이 절은 작업 뒤에 붙였다. 체크박스가 전부 비어 있어 계획서만 보면 아무것도
안 한 것처럼 읽혔기 때문이다.
