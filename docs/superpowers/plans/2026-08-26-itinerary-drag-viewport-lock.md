# 드래그 중 화면 안정화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 장소 카드를 끌고 날짜를 바꿀 때 화면이 위아래로 출렁이지 않게 하고, 위쪽 자동 스크롤이 Day 탭을 밀어내지 않게 한다.

**Architecture:** 화면을 움직이는 주체가 넷이다 — 브라우저의 스크롤 앵커링, dnd-kit의 레이아웃 시프트 보정, 문서 축소로 인한 스크롤 클램프, dnd-kit의 위쪽 자동 스크롤. 앞의 둘은 "알아서 보정해주는" 기능이라 끄고, 셋째는 문서가 줄지 않게 막고, 넷째는 상한을 둔다.

**Tech Stack:** React 19, TypeScript, dnd-kit core 6.3.1 / sortable 10.0.0, Vite, Vitest

**Spec:** `docs/superpowers/plans/2026-08-25-itinerary-cross-day-drag.md` 의 **B-4** 에서 출발했으나, 실기기 확인 결과 원인이 하나가 아니라 넷임이 드러나 전면 재작성했다.

## Global Constraints

- 순수 프론트엔드 변경. API 계약 / 백엔드 / DB 변경 없음.
- 브랜치 `feature/itinerary-drag-viewport-lock`, base `develop` (`12173ab`).
- 기준선: 전체 스위트 `274 passed / 7 failed`. 실패 7건(`mypage` 5, `policies` 2)은 develop에서도 실패하는 기존 문제다. **이 수가 늘면 회귀다.**
- 검증은 한 파일만 돌리지 않고 `npx vitest run` 전체를 돌린다.
- push / PR / merge 금지. 이미 있는 커밋 `da894fd` 를 `--amend` 로 흡수한다.
- 로컬 브라우저 확인은 사용자가 4173에서 수행한다.

---

## 문제

### 증상 1 — 날짜를 옮길 때 화면이 출렁인다 (가끔)

드래그 중 Day 탭으로 옮기면 화면이 위아래로 튄다. 매번이 아니라 가끔이다.

배포 누락이 아니다. 개발서버 번들에 이번 변경 문자열이 모두 있고 CSS 해시도 로컬과 같다. **날짜별 장소 개수 차이** 라는 데이터 조건에 걸리느냐의 문제다.

### 증상 2 — 위로 끌면 Day 탭이 밀려 내려간다

Day 탭이 화면 위쪽에 있을 때 카드를 위로 끌면 일정이 자동으로 위로 스크롤되면서, 그 위에 있던 헤더와 버튼 줄이 나타나고 **Day 탭 박스가 화면 아래로 밀린다.** 겨냥하던 대상이 움직여 정확한 삽입이 어렵다.

---

## 원인 넷

`.app-container`가 `position: absolute; inset: 0; height: 100%; overflow-y: auto` 인 실제 스크롤러다(`app.css:151`). 창이 아니라 이 요소가 스크롤한다.

### 원인 A — 브라우저 스크롤 앵커링

`overflow-anchor`가 어디에도 설정돼 있지 않아 **브라우저 기본값이 활성**이다.

스크롤 앵커링은 화면 위쪽 콘텐츠가 바뀔 때 "보이는 것이 안 움직이도록" 브라우저가 `scrollTop`을 자동 보정하는 기능이다. 날짜를 바꾸면 타임라인 카드가 통째로 교체되어 브라우저가 잡고 있던 앵커 요소가 사라진다. 그러면 브라우저가 자기 판단으로 스크롤을 움직인다.

**명세에 동작이 고정돼 있지 않은 휴리스틱**이다. 어떤 요소가 앵커로 잡히느냐에 따라 결과가 달라져 "가끔 발생"으로 나타난다.

### 원인 B — dnd-kit `layoutShiftCompensation`

`DndContext`에 `autoScroll` 옵션을 주지 않아 기본값이 쓰인다. `AutoScrollOptions.layoutShiftCompensation` 의 기본값은 **`true`** 다 (`node_modules/@dnd-kit/core/dist/hooks/utilities/useAutoScroller.d.ts`).

이 기능은 드래그 중 끌고 있는 요소의 최초 사각형이 레이아웃 변화로 밀렸을 때 그만큼 **스크롤을 조정해 보정**한다. 그런데 날짜 전환은 타임라인 전체를 갈아치우는 거대한 레이아웃 변화다. 다른 날짜로 옮기는 경우 원본 카드가 언마운트되고 유령이 마운트되기까지 한다. dnd-kit이 큰 시프트를 감지해 스크롤을 크게 움직일 수 있다.

원인 A와 B는 **둘 다 "알아서 보정해주는" 기능**이고, 우리는 이미 어디를 보여줄지 직접 관리하고 있다. 둘이 동시에 개입하면 서로 상쇄되거나 증폭돼 예측이 불가능해진다.

### 원인 C — 문서 축소로 인한 스크롤 클램프

날짜를 바꾸면 문서 높이가 변한다. 새 높이가 현재 스크롤 위치보다 짧아지면 브라우저가 `scrollTop`을 강제로 줄인다. 이는 레이아웃 동작이라 JS로 막을 수 없다.

`da894fd`에서 타임라인 높이를 인라인 `min-height`로 고정해 이걸 막으려 했으나 **고정값을 드래그 시작 시점 높이로 잡은 것이 잘못**이었다.

```
Day2(장소 1개)에서 시작   타임라인 520px  -> 고정값 520px
  아래로 Day1(장소 8개)로 이동
타임라인 900px로 성장     (min-height 520이라 성장은 허용)
  아래로 다시 Day2로 이동
타임라인 max(200, 520) = 520px  -> 문서가 900에서 520으로 축소 -> 클램프 -> 출렁
```

**장소가 적은 날짜에서 드래그를 시작하면 고정이 무용지물이다.** 고정값은 시작 높이가 아니라 **드래그 중 관측한 최대 높이**여야 한다.

### 원인 D — 위쪽 자동 스크롤에 상한이 없다

dnd-kit 자동 스크롤은 포인터가 스크롤 컨테이너의 위/아래 가장자리 근처에 오면 그 방향으로 스크롤한다. Day 탭은 타임라인보다 **위에** 있으므로, 탭을 겨냥해 카드를 위로 끌면 자동 스크롤이 발동한다. 위에 있던 헤더와 버튼 줄이 나타나면서 Day 탭이 아래로 밀린다.

아래쪽 자동 스크롤은 화면 밖 장소에 닿기 위해 필요하지만, **위쪽은 Day 탭을 겨냥하는 것을 방해하기만 한다.** 위로 보는 것은 휠이나 모바일 스크롤로 자연스럽게 된다.

---

## 결정 사항 (승인 완료)

| 원인 | 조치 |
|---|---|
| A 스크롤 앵커링 | `.app-container`에 `overflow-anchor: none` |
| B 레이아웃 시프트 보정 | `autoScroll.layoutShiftCompensation: false` |
| C 문서 축소 | 고정값을 **드래그 중 최대 높이**로 갱신 |
| D 위쪽 자동 스크롤 | `autoScroll.canScroll`로 상한. Day 탭이 이미 보이면 위로 더 안 올라간다 |

D의 규칙을 정확히 적는다. 포인터가 컨테이너 위쪽 임계 영역에 있을 때,

- Day 탭 줄이 **이미 화면 안에 완전히 보이면** 위로 스크롤하지 않는다
- Day 탭 줄이 **화면 위로 벗어나 있으면** 보일 때까지는 스크롤한다

두 번째 조건이 필요한 이유는, 아래로 한참 스크롤한 상태에서 카드를 집으면 Day 탭이 화면 밖이기 때문이다. 그때 위로 못 가면 다른 날짜로 옮길 방법이 없다. 특히 모바일은 드래그 중 손가락이 하나뿐이라 휠 대안이 없다.

---

## File Structure

| 파일 | 책임 | 변경 |
|---|---|---|
| `frontend/src/pages/itinerary/ItineraryDetailPage.tsx` | 순수 함수 3개, autoScroll 설정, 높이 고정 갱신 | Modify |
| `frontend/src/styles/app.css` | `overflow-anchor`, 높이 해제 트랜지션 | Modify |
| `frontend/src/app/__tests__/trip-detail.test.tsx` | 순수 함수 단위 테스트, 소스·CSS 핀 | Modify |

`.timeline`의 기존 `min-height: clamp(...)` 값은 바꾸지 않는다. 드래그 중에만 인라인 값이 덮는다.

---

## Task 1: 자동 보정 끄기 (원인 A·B)

가장 먼저 한다. 원인 C·D의 효과를 관측하려면 "알아서 움직이는" 요소부터 제거해야 한다.

**Files:**
- Modify: `frontend/src/styles/app.css` — `.app-container` (`:151`)
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx` — `<DndContext>` 의 `measuring` prop 옆
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Consumes: 없음
- Produces: 없음 (설정 전용)

- [ ] **Step 1: 실패 테스트 작성**

`it("keeps the itinerary drag target and spacing affordance styles present", ...)` 안, `align-content: start` 단언 바로 뒤에 CSS 핀을 넣는다. `.app-container` 규칙이 `overflow-anchor: none` 을 갖는지 확인하는 정규식이다.

`it("installs a non-passive window wheel bridge for desktop gutters", ...)` 안, `MeasuringStrategy.Always` 단언 뒤에 소스 핀을 넣는다.

```tsx
    // dnd-kit도 레이아웃 변화를 감지해 스크롤을 보정한다. 날짜 전환은 거대한
    // 레이아웃 변화라 이 보정이 화면을 크게 움직인다. 우리가 직접 관리한다.
    expect(source).toContain("layoutShiftCompensation: false");
```

- [ ] **Step 2: 빨간 것 확인**

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "affordance styles"
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "wheel bridge"
```

기대: 둘 다 FAIL.

- [ ] **Step 3: CSS 적용**

`.app-container` 규칙의 `overflow-x: hidden;` 바로 뒤:

```css
  overflow-x: hidden;
  /* 브라우저가 콘텐츠 변화에 맞춰 scrollTop을 임의로 보정하지 않게 한다.
     날짜 전환처럼 위쪽 콘텐츠가 통째로 바뀔 때 화면이 튀는 원인이다. */
  overflow-anchor: none;
```

- [ ] **Step 4: DndContext 설정**

`<DndContext>`의 `measuring` prop 바로 뒤:

```tsx
        autoScroll={{ layoutShiftCompensation: false }}
```

- [ ] **Step 5: 초록 확인** — Step 2와 같은 명령. 기대: 둘 다 PASS.

---

## Task 2: 높이 고정을 최대값으로 (원인 C)

`da894fd`에 이미 들어간 `resolveTimelineHeightLock`은 그대로 쓰고 **갱신 규칙**을 더한다.

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Consumes: `resolveTimelineHeightLock(timelineHeight: number | null): string | null`
- Produces:
  ```ts
  export function resolveRaisedTimelineHeightLock(
    currentLock: string | null,
    timelineHeight: number | null,
  ): string | null
  ```
  기존 고정값과 현재 높이 중 **큰 쪽**. 줄어드는 방향으로는 절대 바뀌지 않는다.

- [ ] **Step 1: 실패 테스트 작성**

import 블록에 `resolveRaisedTimelineHeightLock` 추가. `it("refuses to pin an unusable timeline height", ...)` 바로 뒤:

```tsx
  it("raises the timeline pin but never lowers it during one drag", () => {
    // 장소가 적은 날짜에서 시작해 많은 날짜를 거쳐 다시 짧은 날짜로 가면
    // 문서가 줄어 스크롤이 클램프된다. 고정값은 관측한 최대 높이여야 한다.
    expect(resolveRaisedTimelineHeightLock("520px", 900)).toBe("900px");
    expect(resolveRaisedTimelineHeightLock("900px", 200)).toBe("900px");
    expect(resolveRaisedTimelineHeightLock("900px", 900)).toBe("900px");
  });

  it("starts the timeline pin from nothing and survives unusable input", () => {
    expect(resolveRaisedTimelineHeightLock(null, 640)).toBe("640px");
    expect(resolveRaisedTimelineHeightLock("640px", null)).toBe("640px");
    expect(resolveRaisedTimelineHeightLock("640px", 0)).toBe("640px");
    expect(resolveRaisedTimelineHeightLock(null, null)).toBeNull();
    expect(resolveRaisedTimelineHeightLock("", 640)).toBe("640px");
    expect(resolveRaisedTimelineHeightLock("auto", 640)).toBe("640px");
  });
```

- [ ] **Step 2: 빨간 것 확인**

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "timeline pin"
```

기대: FAIL, `resolveRaisedTimelineHeightLock is not a function`.

- [ ] **Step 3: 순수 함수 구현**

`resolveTimelineHeightLock` 바로 뒤:

```ts
/**
 * 드래그 한 번 동안 고정값은 절대 내려가지 않는다. 장소가 적은 날짜에서
 * 시작해 많은 날짜를 거쳐 돌아오면 문서가 줄어 스크롤이 클램프되기 때문이다.
 * 시작 시점 높이가 아니라 관측한 최대 높이를 유지한다.
 */
export function resolveRaisedTimelineHeightLock(
  currentLock: string | null,
  timelineHeight: number | null,
): string | null {
  const nextLock = resolveTimelineHeightLock(timelineHeight);
  if (!nextLock) return currentLock || null;
  const currentPx = Number.parseFloat(currentLock ?? "");
  if (!Number.isFinite(currentPx)) return nextLock;
  return Number.parseFloat(nextLock) > currentPx ? nextLock : currentLock;
}
```

- [ ] **Step 4: 초록 확인** — Step 2와 같은 명령. 기대: PASS (2).

- [ ] **Step 5: 갱신 지점 소스 핀**

`wheel bridge` 테스트의 `layoutShiftCompensation` 단언 뒤:

```tsx
    // 날짜가 바뀌어 타임라인이 커지면 고정값도 따라 올라가야 한다.
    expect(source).toContain("resolveRaisedTimelineHeightLock");
```

- [ ] **Step 6: 빨간 것 확인** — 기대: FAIL.

- [ ] **Step 7: 갱신 함수와 효과 추가**

`unlockPlaceDragViewportScroll` 바로 뒤:

```ts
  /**
   * 날짜가 바뀌면 타임라인 높이가 달라진다. 커졌으면 고정값을 올려서,
   * 나중에 짧은 날짜로 돌아갔을 때 문서가 줄지 않게 한다.
   */
  const raiseTimelineHeightLock = useCallback(() => {
    if (!placeDragScrollLockRef.current) return;
    const timelineElement = document.querySelector<HTMLElement>(
      "[data-itinerary-timeline]",
    );
    if (!timelineElement) return;
    const raised = resolveRaisedTimelineHeightLock(
      timelineElement.style.minHeight || null,
      timelineElement.getBoundingClientRect().height,
    );
    if (raised) timelineElement.style.minHeight = raised;
  }, []);
```

`restrictPlaceDragToContent` 정의 **앞**에:

```ts
  useEffect(() => {
    if (!draggingPlaceId) return;
    raiseTimelineHeightLock();
  }, [draggingPlaceId, visibleDay, raiseTimelineHeightLock]);
```

`visibleDay`가 바뀔 때마다, 즉 날짜가 전환되어 새 타임라인이 커밋된 직후에 돈다.

- [ ] **Step 8: 초록 확인** — 기대: PASS.

---

## Task 3: 위쪽 자동 스크롤 상한 (원인 D)

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Consumes: 없음
- Produces:
  ```ts
  export const PLACE_DRAG_AUTO_SCROLL_THRESHOLD = 0.2;
  export function shouldAllowPlaceDragAutoScroll(args: {
    pointerY: number | null;
    containerRect: Pick<DOMRect, "top" | "bottom"> | null;
    dayTabsRect: Pick<DOMRect, "top" | "bottom"> | null;
    thresholdRatio: number;
  }): boolean
  ```

- [ ] **Step 1: 실패 테스트 작성**

import 블록에 `PLACE_DRAG_AUTO_SCROLL_THRESHOLD`, `shouldAllowPlaceDragAutoScroll` 추가. `raises the timeline pin` 테스트 바로 앞:

```tsx
  it("stops scrolling further up once the Day tabs are fully visible", () => {
    // Day 탭은 타임라인 위에 있다. 탭을 겨냥해 위로 끌면 자동 스크롤이 돌고,
    // 위에 있던 헤더와 버튼 줄이 나타나며 탭이 아래로 밀려 겨냥이 어긋난다.
    expect(
      shouldAllowPlaceDragAutoScroll({
        pointerY: 60,
        containerRect: { top: 0, bottom: 900 },
        dayTabsRect: { top: 300, bottom: 340 },
        thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
      }),
    ).toBe(false);
  });

  it("still scrolls up while the Day tabs are off screen", () => {
    // 아래로 한참 내려간 상태에서 카드를 집으면 Day 탭이 화면 밖이다.
    // 그때까지 막으면 다른 날짜로 옮길 방법이 없다. 모바일은 휠도 없다.
    expect(
      shouldAllowPlaceDragAutoScroll({
        pointerY: 60,
        containerRect: { top: 0, bottom: 900 },
        dayTabsRect: { top: -220, bottom: -180 },
        thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
      }),
    ).toBe(true);
  });

  it("never blocks downward place drag auto scroll", () => {
    // 아래쪽 자동 스크롤은 화면 밖 장소에 닿기 위해 필요하다.
    expect(
      shouldAllowPlaceDragAutoScroll({
        pointerY: 860,
        containerRect: { top: 0, bottom: 900 },
        dayTabsRect: { top: 300, bottom: 340 },
        thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
      }),
    ).toBe(true);
    expect(
      shouldAllowPlaceDragAutoScroll({
        pointerY: 450,
        containerRect: { top: 0, bottom: 900 },
        dayTabsRect: { top: 300, bottom: 340 },
        thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
      }),
    ).toBe(true);
  });

  it("does not interfere with auto scroll when it cannot measure", () => {
    expect(
      shouldAllowPlaceDragAutoScroll({
        pointerY: null,
        containerRect: { top: 0, bottom: 900 },
        dayTabsRect: { top: 300, bottom: 340 },
        thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
      }),
    ).toBe(true);
    expect(
      shouldAllowPlaceDragAutoScroll({
        pointerY: 60,
        containerRect: null,
        dayTabsRect: { top: 300, bottom: 340 },
        thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
      }),
    ).toBe(true);
    expect(
      shouldAllowPlaceDragAutoScroll({
        pointerY: 60,
        containerRect: { top: 0, bottom: 900 },
        dayTabsRect: null,
        thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
      }),
    ).toBe(true);
  });
```

- [ ] **Step 2: 빨간 것 확인**

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "auto scroll"
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "Day tabs are fully visible"
```

기대: FAIL, `shouldAllowPlaceDragAutoScroll is not a function`.

- [ ] **Step 3: 순수 함수 구현**

`resolveRaisedTimelineHeightLock` 바로 뒤:

```ts
/** dnd-kit 자동 스크롤이 발동하는 가장자리 폭. 컨테이너 높이 대비 비율이다. */
export const PLACE_DRAG_AUTO_SCROLL_THRESHOLD = 0.2;

/**
 * 위쪽 자동 스크롤의 상한. Day 탭은 타임라인보다 위에 있어서, 탭을 겨냥해
 * 카드를 위로 끌면 자동 스크롤이 헤더와 버튼 줄을 불러와 탭을 아래로 밀어낸다.
 * 겨냥하던 대상이 움직이므로 삽입이 어려워진다.
 *
 * 탭이 이미 다 보이면 위로 더 갈 이유가 없으므로 막는다. 탭이 화면 밖이면
 * 보일 때까지는 허용한다 — 아래로 한참 내려간 상태에서 집었을 때 다른 날짜로
 * 옮길 길이 막히면 안 되고, 모바일은 드래그 중 휠 대안도 없다.
 *
 * 아래쪽 자동 스크롤은 건드리지 않는다. 화면 밖 장소에 닿으려면 필요하다.
 */
export function shouldAllowPlaceDragAutoScroll({
  pointerY,
  containerRect,
  dayTabsRect,
  thresholdRatio,
}: {
  pointerY: number | null;
  containerRect: Pick<DOMRect, "top" | "bottom"> | null;
  dayTabsRect: Pick<DOMRect, "top" | "bottom"> | null;
  thresholdRatio: number;
}): boolean {
  if (pointerY == null || !containerRect) return true;
  if (!dayTabsRect) return true;
  const containerHeight = containerRect.bottom - containerRect.top;
  if (containerHeight <= 0) return true;
  const isPointerInTopBand =
    pointerY <= containerRect.top + containerHeight * thresholdRatio;
  if (!isPointerInTopBand) return true;
  const areDayTabsFullyVisible =
    dayTabsRect.top >= containerRect.top &&
    dayTabsRect.bottom <= containerRect.bottom;
  return !areDayTabsFullyVisible;
}
```

- [ ] **Step 4: 초록 확인** — Step 2와 같은 명령. 기대: 모두 PASS.

- [ ] **Step 5: autoScroll 설정 소스 핀**

`wheel bridge` 테스트의 `resolveRaisedTimelineHeightLock` 단언 뒤:

```tsx
    // 위쪽 자동 스크롤 상한. threshold를 명시해야 판정 함수와 기준이 같아진다.
    expect(source).toContain("shouldAllowPlaceDragAutoScroll");
    expect(source).toContain("canScroll:");
    expect(source).toContain("PLACE_DRAG_AUTO_SCROLL_THRESHOLD");
```

- [ ] **Step 6: 빨간 것 확인** — 기대: FAIL.

- [ ] **Step 7: autoScroll 설정 완성**

`raiseTimelineHeightLock` 바로 뒤:

```ts
  const canPlaceDragAutoScroll = useCallback((element: Element): boolean => {
    const dayTabsElement = document.querySelector<HTMLElement>(
      "[data-itinerary-day-tabs]",
    );
    return shouldAllowPlaceDragAutoScroll({
      pointerY: placeDragPointerRef.current?.y ?? null,
      containerRect: element.getBoundingClientRect(),
      dayTabsRect: dayTabsElement?.getBoundingClientRect() ?? null,
      thresholdRatio: PLACE_DRAG_AUTO_SCROLL_THRESHOLD,
    });
  }, []);
```

Task 1의 `autoScroll` prop을 교체:

```tsx
        /* dnd-kit의 레이아웃 시프트 보정은 끄고(날짜 전환이 거대한 변화라
           보정량이 커진다), 위쪽 자동 스크롤에는 상한을 둔다. threshold를
           명시해야 shouldAllowPlaceDragAutoScroll과 기준이 일치한다. */
        autoScroll={{
          layoutShiftCompensation: false,
          canScroll: canPlaceDragAutoScroll,
          threshold: { x: 0, y: PLACE_DRAG_AUTO_SCROLL_THRESHOLD },
        }}
```

`x: 0`으로 가로 자동 스크롤도 끈다. 타임라인은 세로 목록이라 필요 없다.

- [ ] **Step 8: 초록 확인** — 기대: PASS.

---

## Task 4: 전체 검증과 커밋

- [ ] **Step 1: 전체 검증**

```bash
cd frontend
npx vitest run
npm.cmd run typecheck
npm.cmd run build
npm.cmd run test:mojibake
```

기대: `da894fd` 시점 276 + Task 2의 2개 + Task 3의 4개 = **282 passed / 7 failed**. Task 1은 기존 테스트에 단언만 더하므로 개수를 늘리지 않는다. **중요한 것은 FAIL이 7을 넘지 않는 것이다.**

- [ ] **Step 2: 커밋에 흡수**

`da894fd`는 아직 push 전이다. 이 저장소는 PR을 squash가 아니라 머지 커밋으로 합쳐 브랜치 중간 커밋이 히스토리에 남으므로, 새 커밋을 쌓지 말고 `--amend`로 흡수한다. 커밋 메시지는 네 원인을 모두 설명하도록 다시 쓴다.

```bash
git add frontend/src/pages/itinerary/ItineraryDetailPage.tsx \
        frontend/src/styles/app.css \
        frontend/src/app/__tests__/trip-detail.test.tsx \
        docs/superpowers/plans/2026-08-26-itinerary-drag-viewport-lock.md
git diff --check
git status --short
git commit --amend
```

---

## 브라우저 확인 (사용자, 4173)

**재현 조건을 먼저 만든다.** 장소 개수가 크게 차이 나는 날짜 두 개가 필요하다. 예를 들어 Day1에 8개 이상, Day2에 1개.

### 증상 1 — 출렁임

1. **장소 많은 날짜에서 적은 날짜로** 카드를 끌 때 드래그 중 화면이 안 움직이는가
2. **장소 적은 날짜에서 시작** 해 많은 날짜를 거쳐 다시 짧은 날짜로 갈 때도 안 움직이는가 — Task 2가 고친 지점
3. Day 탭을 여러 번 왔다갔다 해도 안 움직이는가 (가끔 발생이라 반복이 필요하다)

### 증상 2 — 위쪽 자동 스크롤

4. Day 탭이 화면에 보이는 상태에서 카드를 위로 끌 때 **Day 탭이 제자리에 있는가**
5. 아래로 한참 스크롤해 Day 탭이 안 보이는 상태에서 카드를 집고 위로 끌면, **탭이 보일 때까지는 올라가고 거기서 멈추는가**
6. 아래쪽 자동 스크롤은 여전히 되는가

### 회귀

7. 드래그가 아닐 때 타임라인 높이가 예전과 같은가 (인라인 값이 남으면 빈 날짜가 과도하게 길어진다)
8. 드롭 직후 뚝 끊기지 않고 부드럽게 줄어드는가
9. Escape 취소 후에도 해제되는가
10. 드래그 중 휠이 되는가
11. 같은 날짜 재정렬, 빈 날짜로 이동, 왼쪽 번호 배지 고정

---

## 이번에 넣지 않는 것

**`restrictPlaceDragToContent`가 `scrollTop`을 매 프레임 읽는다.**

```js
const contentBottom =
  appContainer.getBoundingClientRect().top +
  appContainer.scrollHeight -
  appContainer.scrollTop;
y = Math.min(transform.y, contentBottom - bounds.activeBottomWithMargin)
```

`bounds.activeBottomWithMargin`은 드래그 시작 시점에 한 번 잰 뷰포트 좌표인데 `scrollTop`은 자동 스크롤 중 계속 변한다. 클램프 상한이 매 프레임 좁아져 **오버레이가 포인터를 못 따라가고 위로 밀릴 수 있다.**

아직 사용자가 보고한 증상이 아니다. 화면 출렁임과는 다른 증상(오버레이 지연)이므로 이번에 같이 건드리면 무엇이 들었는지 가릴 수 없다. 위 넷을 확인한 뒤 별건으로 다룬다.

---

## 알려진 부작용

`.timeline`의 `min-height`가 `clamp(360px, calc(100dvh - 480px), 520px)`라 **창 세로 크기를 바꾸면** 220ms 트랜지션이 돈다. 드래그와 무관한 상황이지만 리사이즈 중 높이가 살짝 늦게 따라온다. 실사용에 지장 없다고 판단해 그대로 둔다. 거슬리면 트랜지션을 드래그 중에만 거는 React 상태 방식으로 바꿔야 한다.

## 되돌리기

한 커밋이므로 `git revert` 로 되돌린다. CSS 두 줄과 dnd-kit 설정, 인라인 스타일만 걸고 푸는 변경이라 다른 화면에 영향이 없다.

---

## Task 5: 위쪽 상한 기준을 장소추가 버튼 줄로 (실기기 확인 후 수정)

Task 3 적용 후 사용자 확인 결과 **고정 자체는 잘 된다.** 다만 멈추는 위치가 아쉽다.

지금은 Day 탭 줄이 다 보이면 멈춘다. 그러면 Day 탭이 화면 맨 위 가장자리에 딱 붙은 상태가 되어 겨냥하기가 빡빡하다. 그 위에 있는 **장소추가 / 추천 일정만들기 버튼 줄까지 보이는 위치**가 자연스럽다.

### 변경

멈춤 기준 요소를 `[data-itinerary-day-tabs]` 에서 `[data-itinerary-actions]` 로 바꾼다. 버튼 줄은 Day 탭보다 위에 있으므로, 버튼 줄이 다 보일 때까지 올라가면 Day 탭은 그 아래에 여유를 두고 놓인다.

판정 함수의 논리는 그대로다. 무엇을 기준으로 삼느냐만 다르므로 매개변수 이름을 `dayTabsRect` 에서 `anchorRect` 로 바꿔 실제 역할과 맞춘다. "이 요소가 다 보이면 위로 더 안 간다"가 함수의 계약이다.

`[data-itinerary-actions]` 는 Day 존 계산(`resolveDayZoneRect`)에서 이미 쓰고 있는 랜드마크라 새로 붙일 속성이 없다.

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx` — `shouldAllowPlaceDragAutoScroll` 매개변수명, `canPlaceDragAutoScroll` 이 조회하는 요소
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

- [ ] **Step 1: 테스트를 새 이름·새 의미로 고쳐 빨간 것 확인**

Task 3의 네 테스트에서 `dayTabsRect` 를 `anchorRect` 로 바꾸고, 주석의 "Day 탭"을 "장소추가 버튼 줄"로 고친다. 함수가 아직 `dayTabsRect` 를 받으므로 `anchorRect` 는 무시되고 `dayTabsRect` 가 `undefined` 가 되어, "다 보이면 false" 를 기대하는 테스트가 실패한다.

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "fully visible"
```

기대: FAIL.

- [ ] **Step 2: 순수 함수 매개변수명 변경**

`shouldAllowPlaceDragAutoScroll` 의 `dayTabsRect` 를 `anchorRect` 로 바꾸고 주석을 새 기준에 맞게 고친다.

- [ ] **Step 3: 호출부 소스 핀**

```tsx
    expect(source).toContain("anchorRect: actionsElement");
```

기대: 먼저 FAIL.

- [ ] **Step 4: 호출부 변경**

`canPlaceDragAutoScroll` 이 `[data-itinerary-day-tabs]` 대신 `[data-itinerary-actions]` 를 조회하고 `anchorRect` 로 넘긴다.

- [ ] **Step 5: 전체 검증 후 커밋에 흡수**

### 브라우저 확인 추가

12. 카드를 위로 끌었을 때 **장소추가 버튼 줄까지 보이는 지점에서 멈추는가**
13. Day 탭이 화면 맨 위에 딱 붙지 않고 아래에 여유를 두고 놓이는가

---

## Task 6: 시트가 열린 채 휠을 굴리면 뒤 화면이 스크롤된다

장소 추가 서브창을 띄운 상태에서 마우스 휠을 굴리면 뒤에 있는 일정 화면까지 스크롤된다. 서브창만 스크롤돼야 한다.

드래그와 무관한 별개 증상이지만 원인 하나가 이번에 손댄 휠 브리지와 같은 함수라 함께 처리한다.

### 원인 둘

**원인 E — 휠 브리지가 대상을 가리지 않는다**

```ts
const handleWindowWheel = (event: WheelEvent) => {
  const appContainer = document.querySelector<HTMLElement>(".app-container");
  if (!appContainer) return;
  if (!shouldForwardWindowWheelToAppScroll(event, appContainer)) return;
  event.preventDefault();
  appContainer.scrollTop += event.deltaY;
};
```

이 브리지는 데스크톱에서 가운데 앱 열 **바깥 여백**에 마우스를 두고 휠을 굴려도 스크롤되게 하려고 만든 것이다. 그런데 **이벤트가 어디서 났는지 전혀 보지 않는다.**

휠 이벤트는 버블링되어 window까지 올라온다. 시트 위에서 굴려도 브리지가 잡고, `preventDefault()`로 **브라우저의 기본 스크롤을 취소한 뒤** `.app-container`를 직접 스크롤한다. 그래서 시트 대신 뒤 화면이 움직인다.

시트뿐 아니라 **앱 컨테이너 안쪽의 모든 중첩 스크롤 영역**이 같은 피해를 본다. `.trip-select-list`, `.prototype-filter-sheet`, `.prototype-account-dialog`, `.prototype-agreement-sheet-body` 등이 해당한다.

**원인 F — 시트에 스크롤 체이닝 차단이 없다**

`.trip-select-sheet`는 `max-height: min(86dvh, 720px); overflow-y: auto` 인데 `overscroll-behavior`가 없다(`app.css:4506`). 원인 E를 고쳐 네이티브 스크롤이 살아나도, 시트를 **끝까지 굴리면** 그 다음 휠이 부모로 넘어가 뒤 화면이 스크롤된다.

둘 다 고쳐야 증상이 사라진다.

### 결정

| 원인 | 조치 |
|---|---|
| E | 휠이 **앱 컨테이너보다 안쪽의 스크롤 가능한 요소**에서 났으면 브리지가 손대지 않는다 |
| F | 스크롤 가능한 시트·다이얼로그에 `overscroll-behavior: contain` |

E를 "시트일 때만" 이 아니라 "중첩 스크롤러 일반"으로 잡는다. 특정 클래스를 나열하면 새 모달이 생길 때마다 같은 버그가 재발한다.

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx` — 순수 함수 추가, `handleWindowWheel`
- Modify: `frontend/src/styles/app.css` — 시트 4곳
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Produces:
  ```ts
  export function isWheelInsideNestedScroller(
    path: { canScrollY: boolean; isAppContainer: boolean }[],
  ): boolean
  ```
  `event.target`에서 위로 올라가며 만든 경로. 앱 컨테이너에 닿기 전에 세로 스크롤 가능한 요소를 만나면 참.

- [ ] **Step 1: 실패 테스트 작성**

```tsx
  it("leaves the wheel alone inside a nested scroller such as an open sheet", () => {
    // 휠은 window까지 버블링된다. 브리지가 대상을 안 가리면 시트 위에서 굴려도
    // preventDefault로 기본 스크롤을 죽이고 뒤 화면을 스크롤한다.
    expect(
      isWheelInsideNestedScroller([
        { canScrollY: false, isAppContainer: false },
        { canScrollY: true, isAppContainer: false },
        { canScrollY: true, isAppContainer: true },
      ]),
    ).toBe(true);
  });

  it("still bridges the wheel from the desktop gutter", () => {
    // 앱 컨테이너에 닿기 전 스크롤러가 없으면 브리지가 원래 하던 일을 한다.
    expect(
      isWheelInsideNestedScroller([
        { canScrollY: false, isAppContainer: false },
        { canScrollY: true, isAppContainer: true },
      ]),
    ).toBe(false);
    expect(isWheelInsideNestedScroller([])).toBe(false);
  });
```

- [ ] **Step 2: 빨간 것 확인**

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "nested scroller"
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "desktop gutter"
```

기대: FAIL, `isWheelInsideNestedScroller is not a function`.

- [ ] **Step 3: 순수 함수 구현**

`shouldForwardWindowWheelToAppScroll` 바로 뒤에 넣는다.

```ts
/**
 * 휠이 앱 컨테이너보다 안쪽의 스크롤 가능한 요소에서 났는지 본다.
 * 휠은 window까지 버블링되므로, 대상을 가리지 않으면 시트 위에서 굴려도
 * 브리지가 기본 스크롤을 취소하고 뒤 화면을 스크롤한다.
 *
 * 특정 모달 클래스를 나열하지 않는다. 새 모달이 생길 때마다 재발한다.
 */
export function isWheelInsideNestedScroller(
  path: { canScrollY: boolean; isAppContainer: boolean }[],
): boolean {
  for (const node of path) {
    if (node.isAppContainer) return false;
    if (node.canScrollY) return true;
  }
  return false;
}
```

- [ ] **Step 4: 초록 확인** — Step 2와 같은 명령. 기대: PASS.

- [ ] **Step 5: 호출부 소스 핀**

`wheel bridge` 테스트에:

```tsx
    // 시트 등 중첩 스크롤러 위에서는 브리지가 손대지 않는다.
    expect(source).toContain("isWheelInsideNestedScroller(");
```

기대: 먼저 FAIL.

- [ ] **Step 6: `handleWindowWheel` 에 연결**

```ts
    const handleWindowWheel = (event: WheelEvent) => {
      const appContainer = document.querySelector<HTMLElement>(".app-container");
      if (!appContainer) return;
      const path: { canScrollY: boolean; isAppContainer: boolean }[] = [];
      let node =
        event.target instanceof Element ? event.target : null;
      while (node) {
        path.push({
          canScrollY: node.scrollHeight > node.clientHeight,
          isAppContainer: node === appContainer,
        });
        if (node === appContainer) break;
        node = node.parentElement;
      }
      if (isWheelInsideNestedScroller(path)) return;
      if (!shouldForwardWindowWheelToAppScroll(event, appContainer)) return;

      event.preventDefault();
      appContainer.scrollTop += event.deltaY;
    };
```

- [ ] **Step 7: 초록 확인** — 기대: PASS.

- [ ] **Step 8: CSS 핀 작성 후 적용**

```tsx
    // 시트를 끝까지 굴리면 그 다음 휠이 부모로 넘어가 뒤 화면이 스크롤된다.
    expect(css).toMatch(
      /\.trip-select-sheet\s*\{[^}]*overscroll-behavior:\s*contain/s,
    );
```

빨간 것을 확인한 뒤, `overflow-y: auto` 를 가진 시트·다이얼로그에 `overscroll-behavior: contain` 을 넣는다.

- `.trip-select-sheet` (`:4506`)
- `.trip-select-list` (`:4576` 부근)
- `.prototype-filter-sheet` (`:5260` 부근)
- `.prototype-account-dialog` (`:9148` 부근)
- `.prototype-agreement-sheet-body` (`:1152` 부근)

- [ ] **Step 9: 전체 검증 후 커밋에 흡수**

### 브라우저 확인 추가

17. 장소 추가 서브창을 띄우고 휠을 굴렸을 때 **서브창만** 스크롤되는가
18. 서브창을 **끝까지** 굴려도 뒤 화면이 안 움직이는가
19. 서브창을 닫은 뒤 데스크톱 여백에서 휠을 굴리면 **여전히 화면이 스크롤되는가** (브리지 본래 기능 회귀 확인)
20. 검색 결과 목록처럼 시트 안의 중첩 목록에서도 그 목록만 스크롤되는가
