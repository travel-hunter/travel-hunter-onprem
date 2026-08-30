# Trip Place Time Order Warning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 일정 상세페이지에서 장소 순서와 방문 시간이 어긋난 장소에 노란 경고 아이콘과 시간 수정 진입점을 표시한다.

**Architecture:** 장소 이동 API와 DB 구조는 유지한다. 프론트에서 Day별 표시 목록을 순회해 “현재 카드의 시간이 직전 시간보다 이른지”를 파생 상태로 계산하고, 저장된 장소 카드에만 경고 UI를 표시한다. 사용자가 경고를 누르면 기존 장소 수정 플로우를 열어 방문 시간을 직접 고치게 한다.

**Tech Stack:** React, TypeScript, React Testing Library, Vitest, existing `AppDataApi`, existing `PlaceTimePicker` and place edit flow.

## Global Constraints

- 구현은 `frontend/` 변경으로 한정한다. API, DB, Alembic 마이그레이션은 변경하지 않는다.
- 프론트 데이터 접근은 기존 `AppDataApi` 경계를 유지한다.
- 같은 Day 안에서만 시간 순서 경고를 계산한다.
- 시간이 없는 장소는 경고 대상에서 제외한다.
- 같은 시간은 경고하지 않는다.
- 추천 미리보기 장소는 별도 편집 흐름이 있으므로 1차 구현에서는 저장된 장소 카드만 경고 대상으로 한다.
- 자동으로 시간을 바꾸거나 장소 간 시간을 교환하지 않는다.
- 경고 문구는 사용자 책임 전가처럼 보이지 않게 “시간 확인”과 “방문 시간을 확인해 주세요.” 톤으로 작성한다.

---

## File Structure

- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
  - Day별 시간 역순 경고 계산 함수 추가
  - `PlaceTimelineItem`에 경고 여부와 수정 핸들러 전달
  - 경고 버튼 클릭 시 기존 장소 수정 모달을 열도록 연결
- Modify: `frontend/src/styles/app.css`
  - 시간 경고 아이콘, 배지, 보조 문구 스타일 추가
  - 모바일에서도 카드 레이아웃이 깨지지 않게 inline-flex 기반으로 처리
- Modify: `frontend/src/app/__tests__/trip-detail.test.tsx`
  - 시간 역순 경고 표시 테스트 추가
  - 경고 버튼 클릭 시 장소 수정 UI가 열리는 테스트 추가
- Modify: `CHECKLIST.md`
  - 구현 후 검증 결과와 남은 리스크만 짧게 갱신

---

### Task 1: 시간 역순 감지 테스트 추가

**Files:**
- Modify: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Consumes: existing `Trip`, `appDataApi.getTrip`, `renderAppRoute`, `login`
- Produces: 경고 UI의 접근성 이름 계약
  - Button accessible name: `${place.label} 방문 시간 확인`
  - Visible short label: `시간 확인`

- [x] **Step 1: Write the failing test**

Add this test near the existing reorder tests:

```tsx
it("marks saved places whose visit time is earlier than the previous place", async () => {
  const trip: Trip = {
    ...getPreviewTrip(),
    id: "130",
    revision: 3,
    title: "시간 확인 여행",
    days: {
      1: [
        { id: "time-a", time: "11:00", label: "늦은 장소", meta: "오전" },
        { id: "time-b", time: "10:00", label: "이른 장소", meta: "오전" },
        { id: "time-c", time: "10:00", label: "같은 시간 장소", meta: "오전" },
      ],
      2: [{ id: "time-d", time: "09:00", label: "다른 Day 장소", meta: "오전" }],
    },
    currentUserRole: "owner",
  };
  const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

  try {
    await login();
    cleanup();
    renderAppRoute("/trips/130?day=1");

    expect(await screen.findByText("시간 확인 여행")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "이른 장소 방문 시간 확인" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "늦은 장소 방문 시간 확인" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "같은 시간 장소 방문 시간 확인" }),
    ).not.toBeInTheDocument();
  } finally {
    getTripSpy.mockRestore();
  }
});
```

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "marks saved places whose visit time is earlier than the previous place"
```

Expected: FAIL because the warning button does not exist yet.

---

### Task 2: 시간 역순 파생 상태 구현

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`

**Interfaces:**
- Produces:
  - `function placeTimeMinutes(time: string | undefined): number | null`
  - `function timeOrderWarningPlaceIds(places: DisplayedPlace[]): Set<string>`
  - `PlaceTimelineItem` prop: `hasTimeOrderWarning: boolean`

- [x] **Step 1: Add pure helper functions**

Add near existing timeline helper functions:

```tsx
function placeTimeMinutes(time: string | undefined): number | null {
  if (!time) return null;
  const match = /^(\d{2}):(\d{2})$/.exec(time);
  if (!match) return null;
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (!Number.isInteger(hour) || !Number.isInteger(minute)) return null;
  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return null;
  return hour * 60 + minute;
}

function displayedPlaceWarningKey(place: DisplayedPlace): string | null {
  return place.id ?? place.previewTimelineId ?? null;
}

function timeOrderWarningPlaceIds(places: DisplayedPlace[]): Set<string> {
  const warningIds = new Set<string>();
  let previousMinutes: number | null = null;

  for (const place of places) {
    const currentMinutes = placeTimeMinutes(place.time);
    const key = displayedPlaceWarningKey(place);
    if (currentMinutes !== null && previousMinutes !== null && currentMinutes < previousMinutes && key) {
      warningIds.add(key);
    }
    if (currentMinutes !== null) {
      previousMinutes = currentMinutes;
    }
  }

  return warningIds;
}
```

- [x] **Step 2: Pass warning state into timeline items**

Inside the Day timeline render block, compute once per displayed list:

```tsx
const timeWarningPlaceIds = timeOrderWarningPlaceIds(displayedPlaces);
```

Then pass:

```tsx
hasTimeOrderWarning={Boolean(displayedPlaceWarningKey(place) && timeWarningPlaceIds.has(displayedPlaceWarningKey(place)!))}
```

- [x] **Step 3: Run failing test again**

Run:

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "marks saved places whose visit time is earlier than the previous place"
```

Expected: still FAIL until UI renders the warning.

---

### Task 3: 경고 아이콘과 수정 진입점 UI 추가

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Modify: `frontend/src/styles/app.css`

**Interfaces:**
- Consumes:
  - `hasTimeOrderWarning: boolean`
  - existing `onEdit(place)`
- Produces:
  - clickable warning button beside the time
  - button opens existing place editor

- [x] **Step 1: Extend `PlaceTimelineItem` props**

Add prop:

```tsx
hasTimeOrderWarning: boolean;
```

Use it in the component parameter destructuring.

- [x] **Step 2: Render warning button beside saved place time**

Replace the saved-place meta time block:

```tsx
{place.time && <span>{place.time}</span>}
```

with:

```tsx
{place.time && (
  <span className="place-time-with-warning">
    <span>{place.time}</span>
    {hasTimeOrderWarning && canEditTrip && !isPreviewMode && (
      <button
        type="button"
        className="place-time-warning-button"
        aria-label={`${place.label} 방문 시간 확인`}
        title="앞 장소보다 이른 시간입니다. 방문 시간을 확인해 주세요."
        onClick={() => onEdit(place)}
      >
        <AlertTriangle size={13} aria-hidden="true" />
        <span>시간 확인</span>
      </button>
    )}
  </span>
)}
```

If `AlertTriangle` is not already imported from `lucide-react`, add it to the existing import list.

- [x] **Step 3: Add CSS**

Add near existing `.place-prototype-meta` styles:

```css
.place-time-with-warning {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.place-time-warning-button {
  border: 1px solid rgba(217, 119, 6, 0.28);
  background: #fff7ed;
  color: #b45309;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 7px;
  font-size: 11px;
  font-weight: 800;
  line-height: 1.2;
  cursor: pointer;
}

.place-time-warning-button:hover,
.place-time-warning-button:focus-visible {
  border-color: rgba(217, 119, 6, 0.55);
  background: #ffedd5;
  color: #92400e;
}
```

- [x] **Step 4: Run test to verify it passes**

Run:

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "marks saved places whose visit time is earlier than the previous place"
```

Expected: PASS.

---

### Task 4: 경고 클릭 시 기존 시간 수정 UI 진입 테스트

**Files:**
- Modify: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Consumes: warning button from Task 3
- Produces: verified behavior that warning is an edit entry point, not a passive icon

- [x] **Step 1: Write the failing or passing behavior test**

Add this test near Task 1 test:

```tsx
it("opens the existing place editor when the time warning is clicked", async () => {
  const trip: Trip = {
    ...getPreviewTrip(),
    id: "131",
    revision: 4,
    title: "시간 수정 진입 여행",
    days: {
      1: [
        { id: "edit-a", time: "12:00", label: "점심 장소", meta: "식사" },
        { id: "edit-b", time: "11:00", label: "오전 장소", meta: "관광" },
      ],
      2: [],
    },
    currentUserRole: "owner",
  };
  const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

  try {
    await login();
    cleanup();
    renderAppRoute("/trips/131?day=1");

    fireEvent.click(
      await screen.findByRole("button", { name: "오전 장소 방문 시간 확인" }),
    );

    expect(
      await screen.findByRole("heading", { name: /오전 장소/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("방문 시간")).toBeInTheDocument();
  } finally {
    getTripSpy.mockRestore();
  }
});
```

- [x] **Step 2: Run test**

Run:

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "opens the existing place editor when the time warning is clicked"
```

Expected: PASS if Task 3 correctly calls `onEdit(place)`. If the heading text differs, inspect the existing place editor markup and update the assertion to its actual accessible label.

---

### Task 5: Regression and build verification

**Files:**
- Modify: `CHECKLIST.md`

**Interfaces:**
- Consumes: Tasks 1-4
- Produces: verified local change set ready for rebuild or PR

- [x] **Step 1: Run targeted test file**

Run:

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx
```

Expected: PASS.

- [x] **Step 2: Run frontend typecheck**

Run:

```bash
cd frontend
npm run typecheck
```

Expected: PASS.

- [x] **Step 3: Run frontend build**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [x] **Step 4: Run UTF-8 and diff checks**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
paths = [
    Path("frontend/src/pages/itinerary/ItineraryDetailPage.tsx"),
    Path("frontend/src/styles/app.css"),
    Path("frontend/src/app/__tests__/trip-detail.test.tsx"),
    Path("CHECKLIST.md"),
]
for path in paths:
    text = path.read_text(encoding="utf-8")
    if "\ufffd" in text:
        raise SystemExit(f"U+FFFD found in {path}")
print("utf8-ok")
PY
git diff --check
```

Expected: `utf8-ok` and no `git diff --check` output.

- [x] **Step 5: Update `CHECKLIST.md`**

Replace the current status block with concise evidence:

```markdown
## Current Status

- 일정 상세 장소 카드에서 방문 시간이 이전 장소보다 이른 경우 `시간 확인` 경고와 수정 진입점을 표시하는 작업을 검증 중입니다.

## Recent Validation

- PASS: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx`
- PASS: `cd frontend && npm run typecheck`
- PASS: `cd frontend && npm run build`
- PASS: UTF-8/U+FFFD check for changed files
- PASS: `git diff --check`

## Active Risks

- 경고는 같은 Day 안의 표시 순서와 `HH:mm` 시간만 기준으로 계산합니다. 이동 시간, 체류 시간, 영업시간까지 자동 판단하지 않습니다.
```

---

## Self-Review

- Spec coverage: 아이콘 표시, 수정 진입점, 자동 시간 변경 금지, 같은 Day 기준 경고, 테스트와 빌드 검증을 모두 포함했다.
- Placeholder scan: 미정 상태나 열린 구현 지시 표현은 없다.
- Type consistency: `DisplayedPlace`, `PlaceTimelineItem`, `onEdit(place)`, `AppDataApi` 기존 경계를 유지한다.
- Scope check: API와 DB를 건드리지 않는 단일 프론트 UX 작업으로 분리되어 있다.
