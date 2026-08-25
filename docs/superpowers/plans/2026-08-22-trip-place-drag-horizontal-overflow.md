# Trip Place Drag Horizontal Overflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the existing drag-to-reorder and cross-Day drop behavior while preventing a dragged itinerary place card from expanding the app container's horizontal or vertical scroll area.

**Architecture:** `@dnd-kit` must retain its original two-dimensional drag coordinates so `DroppableDayTab` can still detect a pointer placed over another Day tab. Only the `SortablePlaceItem` presentation transform will be projected onto the vertical axis: `y`, `scaleX`, and `scaleY` remain unchanged while rendered `x` is always zero. No API, database, or drag sensor contract changes are required.

**Tech Stack:** React 18, TypeScript, `@dnd-kit/core` 6.3.1, `@dnd-kit/sortable` 10.0.0, Playwright, Vitest.

**Spec:** User-reported itinerary-detail regression on 2026-08-22; `docs/mvp-api-contract.md` trip-place move contract (`PATCH /api/trips/{trip_id}/places/{place_id}/move`).

## Execution Record — 2026-08-22

The browser investigation refined the initial hypothesis: the document width remains 390px because the shell clips it, but a same-Day pointer drag applied `matrix(1, 0, 0, 1, 220, 0)` to `.timeline-item.dragging` and expanded `.app-container` from 390px to 594px. That is the user-visible right-side blank area and continued horizontal motion.

- [x] Added a real-pointer E2E regression using two Day 1 places at a 390px viewport. Before the code change it failed with horizontal translation `220`; after the code change it asserts translation `0` and equal app-container client/scroll widths.
- [x] Kept dnd-kit sensor and collision coordinates unchanged; only `SortablePlaceItem` renders a copied transform with `x: 0`. Day-tab collision and the persisted Day 2 pointer drop stay active.
- [x] Ran the focused container E2E after the fix: 1 passed.
- [x] Ran frontend typecheck, mojibake scan, production build, UTF-8 U+FFFD scan, and `git diff --check`.
- [x] Committed only `ItineraryDetailPage.tsx` and `backend-mode.spec.ts` locally as `0d837a0`; no push, PR, development-server, API, or database schema change.
- [x] Added the vertical regression after the user reported lower blank space: before the fix a `translateY(220px)` drag expanded app-container height from `1309` to `1325`. A dnd-kit modifier now caps only positive Y translation at the original content bottom, including the card's bottom margin. The focused horizontal and vertical E2E tests pass together (2 passed); the remaining 2px is browser scroll rounding and is bounded by regression assertion.

The preparatory steps below remain as design rationale. Where they mention document-width overflow or a 500px pointer move, this execution record is authoritative: the verified regression is the app-container width caused by a 220px same-Day pointer move.

## Global Constraints

- Preserve the existing mouse, touch, and keyboard reorder controls.
- Preserve dropping a card onto another Day tab; `DroppableDayTab` must continue to receive the original horizontal pointer/collision position.
- Do not add dependencies. Use the installed dnd-kit modifier interface only to cap positive vertical drag translation at the original content boundary.
- Keep frontend data access behind `AppDataApi`; do not change `TripPlaceMoveRequest`, route, service, or database behavior.
- Do not alter dates/deadline display behavior or any unrelated dirty root-worktree file.
- Use `apply_patch` for source and documentation. Validate changed Korean-bearing files as UTF-8 with no U+FFFD, then run `git diff --check`.
- Work in a fresh `feature/*` worktree based on the latest `origin/develop`; do not push, create a PR, merge, or modify the development server.

---

### Task 1: Lock the Pointer-Drag Regression With a Browser Test

**Files:**
- Modify: `frontend/e2e-backend/backend-mode.spec.ts`
- Read: `frontend/playwright.container.config.ts`
- Read: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`

**Interfaces:**
- Consumes: `POST /api/trips`, `POST /api/trips/{trip_id}/days/{day}/places`, and the existing `PATCH /api/trips/{trip_id}/places/{place_id}/move` endpoint.
- Produces: a real-pointer regression test proving that rightward pointer travel does not cause horizontal document overflow and that a second-Day drop still persists the move.

- [ ] **Step 1: Add the failing two-Day drag test after `expectNoDocumentOverflow` in `frontend/e2e-backend/backend-mode.spec.ts`**

  Create a trip through `page.request` with two days, then add one place to Day 1. Use the existing `seedStoredAuth(page)` helper and its `accessToken` in `Authorization: Bearer` request headers. Use unique labels so parallel historic test data cannot be selected accidentally:

  ```ts
  test("place drag keeps the document width bounded and can still move to another Day", async ({ page }) => {
    const auth = await seedStoredAuth(page);
    const headers = { Authorization: `Bearer ${auth.accessToken}` };
    const placeLabel = `가로 드래그 회귀 ${Date.now()}`;
    const createResponse = await page.request.post(`${apiBaseUrl}/api/trips`, {
      headers,
      data: {
        title: `가로 드래그 회귀 일정 ${Date.now()}`,
        dates: "2026.09.01 - 09.02",
        region: "서울",
      },
    });
    expect(createResponse.ok()).toBeTruthy();
    const tripId = String((await createResponse.json()).id);

    const addResponse = await page.request.post(
      `${apiBaseUrl}/api/trips/${tripId}/days/1/places`,
      {
        headers,
        data: {
          expectedRevision: 1,
          time: "09:00",
          label: placeLabel,
          meta: "가로 드래그 회귀 검증",
        },
      },
    );
    expect(addResponse.ok()).toBeTruthy();

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/trips/${tripId}?day=1`);
    const handle = page.getByRole("button", { name: `${placeLabel} 순서 이동` });
    await expect(handle).toBeVisible();
  });
  ```

- [ ] **Step 2: Extend the test with a real pointer sequence that fails before the fix**

  Obtain the drag-handle bounding box, begin the drag, and move at least 500 CSS pixels to the right before releasing. While the mouse button remains down, assert the shared helper's width condition explicitly:

  ```ts
  const handleBox = await handle.boundingBox();
  expect(handleBox).not.toBeNull();
  const start = {
    x: (handleBox?.x ?? 0) + (handleBox?.width ?? 0) / 2,
    y: (handleBox?.y ?? 0) + (handleBox?.height ?? 0) / 2,
  };

  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(start.x + 12, start.y, { steps: 2 });
  await page.mouse.move(start.x + 500, start.y, { steps: 8 });
  await expectNoDocumentOverflow(page);
  ```

  Before implementation, record the measured `document.documentElement.scrollWidth - document.documentElement.clientWidth` and the `.timeline-item.dragging` computed transform in the failed assertion output. Do not weaken the test by adding a page-level `overflow-x: hidden` rule.

- [ ] **Step 3: Complete the same test with cross-Day pointer drop assertions**

  During the active drag, locate the enabled Day 2 target by its dynamic accessible name, move to its bounding-box centre, and release. Wait for the persisted result rather than using a timeout:

  ```ts
  const dayTwoTarget = page.getByRole("button", {
    name: /Day 2 .*에 .* 놓기/,
  });
  await expect(dayTwoTarget).toBeVisible();
  const dayTwoBox = await dayTwoTarget.boundingBox();
  expect(dayTwoBox).not.toBeNull();
  await page.mouse.move(
    (dayTwoBox?.x ?? 0) + (dayTwoBox?.width ?? 0) / 2,
    (dayTwoBox?.y ?? 0) + (dayTwoBox?.height ?? 0) / 2,
    { steps: 8 },
  );
  await page.mouse.up();

  await expect(page).toHaveURL(new RegExp(`/trips/${tripId}\\?day=2`));
  await expect(page.getByText(placeLabel)).toBeVisible();
  await expectNoDocumentOverflow(page);
  ```

- [ ] **Step 4: Run the new E2E test and capture RED**

  Run from `frontend`:

  ```powershell
  npx playwright test e2e-backend/backend-mode.spec.ts --grep "place drag keeps the document width bounded"
  ```

  Expected: FAIL on the in-drag `expectNoDocumentOverflow(page)` assertion, demonstrating the current positive horizontal transform produces document overflow. If the local app cannot be started by the configured Playwright server, record the exact server error and run the test through `npm.cmd run test:e2e:containers` after rebuilding only the frontend service.

### Task 2: Project Only the Card's Rendered Transform Onto the Vertical Axis

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx:3016-3030`
- Test: `frontend/e2e-backend/backend-mode.spec.ts`

**Interfaces:**
- Consumes: `useSortable(...).transform`, whose value includes `{ x, y, scaleX, scaleY }`.
- Produces: a style transform with `x: 0` while dnd-kit context and collision detection continue to receive the unmodified drag coordinate.

- [ ] **Step 1: Add the minimal local display transform in `SortablePlaceItem`**

  Replace the direct use of `transform` in the style object with a copied transform whose `x` is fixed to zero only when a transform exists:

  ```ts
  const displayTransform = transform ? { ...transform, x: 0 } : null;
  const style = {
    transform: CSS.Transform.toString(displayTransform),
    transition,
  };
  ```

  Do not add a `modifiers` prop to `DndContext`, and do not change `dragSensors`, `closestCenter`, `handlePlaceDragEnd`, `DroppableDayTab`, or `movePlaceTo`. Those code paths must keep the original pointer `x` for Day-tab collision detection.

- [ ] **Step 2: Run the focused E2E regression and verify GREEN**

  Run:

  ```powershell
  npx playwright test e2e-backend/backend-mode.spec.ts --grep "place drag keeps the document width bounded"
  ```

  Expected: PASS. It proves the dragged card cannot create document-width overflow while the pointer can still trigger the Day 2 droppable target and persist the move.

- [ ] **Step 3: Run affected component tests**

  Run:

  ```powershell
  node .\node_modules\vitest\vitest.mjs run src/app/__tests__/trip-detail.test.tsx
  ```

  Expected: PASS, including existing keyboard reordering and cross-Day move assertions.

### Task 3: Verify Responsive Runtime Behavior and Commit the Isolated Fix

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Modify: `frontend/e2e-backend/backend-mode.spec.ts`
- Update only if project state changes: `CHECKLIST.md`

**Interfaces:**
- Consumes: Task 1 browser regression and Task 2 presentation-only transform.
- Produces: a two-file, reviewable frontend fix with exact verification evidence.

- [ ] **Step 1: Run responsive drag verification at the supported mobile and desktop widths**

  In the browser test, loop the existing supported widths `360`, `390`, `430`, `1024`, and `1440`. For each viewport repeat the rightward drag, Day 2 drop, and `expectNoDocumentOverflow(page)` assertion. Create a fresh trip per viewport or use distinct trip IDs so revision updates cannot interfere.

  ```ts
  for (const width of [360, 390, 430, 1024, 1440]) {
    await page.setViewportSize({ width, height: width < 768 ? 844 : 900 });
    // Create a fresh two-day trip, add one Day 1 place, drag right, then drop on Day 2.
    // Assert the document has no horizontal overflow before and after mouseup.
  }
  ```

  Expected: every viewport remains horizontally bounded and the moved place appears on Day 2.

- [ ] **Step 2: Run frontend static and production checks**

  Run from `frontend`:

  ```powershell
  npm.cmd run typecheck
  npm.cmd run test:mojibake
  npm.cmd run build
  ```

  Expected: all commands pass. If the full E2E command still has its previously recorded unrelated official-URL baseline failure, report it separately and do not modify that assertion in this fix.

- [ ] **Step 3: Verify diff scope and UTF-8 before staging**

  Run from the fix worktree root:

  ```powershell
  node -e "const fs=require('fs'); for(const f of ['frontend/src/pages/itinerary/ItineraryDetailPage.tsx','frontend/e2e-backend/backend-mode.spec.ts']){const s=fs.readFileSync(f,'utf8');if(s.includes('\uFFFD'))throw new Error('U+FFFD '+f)} console.log('utf8-ok')"
  git diff --check
  git status --short
  ```

  Expected: `utf8-ok`, no whitespace errors, and only the two planned files are modified.

- [ ] **Step 4: Commit only the drag-overflow fix locally**

  ```powershell
  git add frontend/src/pages/itinerary/ItineraryDetailPage.tsx frontend/e2e-backend/backend-mode.spec.ts
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "Fix itinerary place drag horizontal overflow"
  ```

  Expected staged list:

  ```text
  frontend/src/pages/itinerary/ItineraryDetailPage.tsx
  frontend/e2e-backend/backend-mode.spec.ts
  ```

## Self-Review

- **Spec coverage:** Task 1 reproduces the user-visible rightward overflow; Task 2 removes only the rendered horizontal movement; Task 3 checks all supported widths and preserves API behavior.
- **Preserved behavior:** The dnd-kit collision coordinate is deliberately not modified, so Day-tab drops and keyboard reordering remain available.
- **No new dependency:** The plan uses the existing `useSortable` transform and existing Playwright overflow helper.
- **Scope:** The plan excludes recommendation behavior, policy crawling, date validation, batch place addition, and every development-server change.
