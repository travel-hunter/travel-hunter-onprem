# Desktop Global Wheel Scroll Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On desktop, allow vertical page scrolling even when the mouse wheel starts over the left or right gutter outside the centered app shell.

**Architecture:** The current `.app-container` is the real vertical scroll container while the desktop gutters sit outside it. Wheel events that begin in those gutters do not reach the app container, so the page can feel stuck unless the pointer is over the app UI. Add a small window-level wheel forwarder while itinerary/detail app screens are mounted: if the event target is outside `.app-container`, forward the vertical delta to `.app-container.scrollTop`. Preserve native scrolling inside the app, map interaction, and drag scroll-lock behavior.

**Tech Stack:** React, TypeScript, DOM `WheelEvent`, Vitest, Testing Library, Vite.

**Spec:** User clarification on 2026-08-25: desktop-only improvement; goal is page-level vertical scrolling from side gutters; Kakao map behavior is out of scope.

## Global Constraints

- Do not modify Kakao map components, map props, map zoom behavior, or map pointer handling.
- Do not change API contracts, backend code, Docker files, Slack hook files, or policy data.
- Preserve existing drag scroll-lock behavior: when `.app-container` has `itinerary-place-drag-scroll-locked`, wheel forwarding must not move it.
- Add no dependencies.
- Keep the implementation small and reversible.
- Validate changed Korean-bearing files as UTF-8 with no U+FFFD, then run `git diff --check`.

---

### Task 1: Add a Focused Wheel-Forwarding Utility

**Files:**
- Modify: `frontend/src/components/AppLayout.tsx`
- Test: `frontend/src/components/AppLayout.test.tsx` or nearest existing layout test file

**Interfaces:**
- Consumes: a mounted `.app-container` element.
- Produces: a desktop wheel handler that forwards vertical wheel deltas from outside the app container to that container.

- [ ] **Step 1: Write a failing test for gutter wheel forwarding**

  Create a test that renders the app layout with a scrollable `.app-container`, dispatches a `WheelEvent` on `window` or `document.body` from outside the app container, and asserts the app container's `scrollTop` increases by the wheel delta.

  ```ts
  it("forwards desktop gutter wheel events to the app container", () => {
    render(<AppLayout>content</AppLayout>);
    const container = document.querySelector(".app-container") as HTMLElement;
    Object.defineProperty(container, "scrollHeight", { configurable: true, value: 2000 });
    Object.defineProperty(container, "clientHeight", { configurable: true, value: 800 });

    window.dispatchEvent(new WheelEvent("wheel", { deltaY: 120, bubbles: true }));

    expect(container.scrollTop).toBe(120);
  });
  ```

- [ ] **Step 2: Add the minimal wheel forwarder**

  In `AppLayout`, add an effect that listens for `wheel` events on `window`. If the event target is inside `.app-container`, do nothing. If the app container has `itinerary-place-drag-scroll-locked`, do nothing. Otherwise add `event.deltaY` to `appContainer.scrollTop`.

  ```ts
  useEffect(() => {
    const handleWheel = (event: WheelEvent) => {
      const appContainer = document.querySelector<HTMLElement>(".app-container");
      if (!appContainer) return;
      if (appContainer.classList.contains("itinerary-place-drag-scroll-locked")) return;
      if (event.target instanceof Node && appContainer.contains(event.target)) return;
      if (event.deltaY === 0) return;

      appContainer.scrollTop += event.deltaY;
    };

    window.addEventListener("wheel", handleWheel, { passive: true });
    return () => window.removeEventListener("wheel", handleWheel);
  }, []);
  ```

- [ ] **Step 3: Run the focused test**

  ```powershell
  npm.cmd run test -- AppLayout
  ```

  Expected: PASS for the new gutter wheel forwarding behavior.

### Task 2: Protect Excluded Interaction Paths

**Files:**
- Modify: `frontend/src/components/AppLayout.tsx`
- Test: `frontend/src/components/AppLayout.test.tsx` or nearest existing layout test file

**Interfaces:**
- Consumes: event target containment and app-container CSS classes.
- Produces: tests proving internal app scrolling and drag scroll-lock are not hijacked.

- [ ] **Step 1: Add a test that does not forward internal wheel events**

  Dispatch a wheel event from a child element inside `.app-container` and assert `scrollTop` is unchanged by the forwarder.

- [ ] **Step 2: Add a test that respects drag scroll-lock**

  Add `itinerary-place-drag-scroll-locked` to `.app-container`, dispatch a gutter wheel event, and assert `scrollTop` is unchanged.

- [ ] **Step 3: Run the focused test file**

  ```powershell
  npm.cmd run test -- AppLayout
  ```

  Expected: all wheel-forwarding tests pass.

### Task 3: Browser Smoke and Final Validation

**Files:**
- Modify: `frontend/src/components/AppLayout.tsx`
- Test: `frontend/e2e-backend/backend-mode.spec.ts` only if an existing browser smoke location already covers layout scrolling

**Interfaces:**
- Consumes: the layout-level wheel forwarder from Tasks 1 and 2.
- Produces: reproducible validation that desktop gutter wheel input scrolls the app without changing map behavior.

- [ ] **Step 1: Manually verify in browser**

  Open an itinerary detail page at desktop width. Move the pointer to the left or right gutter outside the centered app UI and use the mouse wheel.

  Expected: the app scrolls vertically. Map-specific wheel behavior remains unchanged because map targets inside the app container are not forwarded.

- [ ] **Step 2: Run static checks**

  ```powershell
  cd frontend
  npm.cmd run typecheck
  npm.cmd run test:mojibake
  npm.cmd run build
  cd ..
  git diff --check
  ```

  Expected: all commands pass.

- [ ] **Step 3: Commit only the wheel-scroll change**

  ```powershell
  git add frontend/src/components/AppLayout.tsx frontend/src/components/AppLayout.test.tsx
  git diff --cached --name-only
  git diff --cached --check
  git commit -m "Enable desktop gutter wheel scrolling"
  ```

  Expected staged list includes only the layout implementation and its focused test.

## Self-Review

- **Spec coverage:** The plan addresses desktop side-gutter wheel scrolling without changing map behavior.
- **Preserved behavior:** Internal app scrolling, map wheel input, and itinerary drag scroll-lock remain guarded.
- **No new dependency:** The implementation uses DOM wheel events and existing React lifecycle hooks.
- **Scope:** The plan excludes backend, API, Docker, policy data, and deployment changes.
