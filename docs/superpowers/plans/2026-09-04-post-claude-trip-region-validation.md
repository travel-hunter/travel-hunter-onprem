# Post-Claude Trip Region Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:verification-before-completion and superpowers:requesting-code-review to validate this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate Claude's completed trip region/date work, separate unrelated dirty files, and reach a tested commit-ready state without losing existing workspace changes.

**Architecture:** Treat the current checkout as the source of truth because the user is testing on the shared 5173 environment. Do not add new feature work until the existing diff is reviewed, tested, and either committed or explicitly marked blocked.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy/PostgreSQL, React, TypeScript, Vite, Vitest/Testing Library, Pytest, Docker Compose

**Spec:** `docs/superpowers/specs/2026-09-03-trip-region-calendar-unification-design.md`

## Global Constraints

- Work in the current checkout only; do not create a separate worktree because 5173 is the active shared test surface.
- Do not commit until automated tests, build checks, diff hygiene, and 5173 smoke checks have been read and recorded.
- Do not revert unrelated dirty files. Preserve `frontend/src/app/__tests__/mypage.test.tsx`, `frontend/src/app/__tests__/policies.test.tsx`, `docs/2026-09-04-working-tree-attribution.md`, and any other file unless the diff proves it belongs to this feature.
- Keep API DTO fields camelCase and DB fields snake_case.
- Keep frontend page data access behind `AppDataApi`.
- Keep backend route modules thin; route logic belongs in services/schemas.
- Update `CHECKLIST.md` only with current status, recent validation evidence, and active risks.
- Before final completion, run UTF-8 and diff hygiene checks. Korean-bearing files must not contain U+FFFD replacement characters.

---

### Task 1: Establish Current Diff Ownership

**Files:**
- Read: `git status --short`
- Read: `docs/2026-09-04-codex-handoff.md`
- Read: `docs/2026-09-04-working-tree-attribution.md`
- Read: `docs/superpowers/plans/2026-09-03-trip-region-calendar-unification.md`
- Read: `docs/superpowers/specs/2026-09-03-trip-region-calendar-unification-design.md`

**Interfaces:**
- Consumes: Current dirty working tree.
- Produces: A reviewed intended-feature file list for later staging.

- [ ] **Step 1: Capture the current dirty state**

Run:

```powershell
git status --short
git diff --name-only
git diff --cached --name-only
```

Expected: `git diff --cached --name-only` is empty. If it is not empty, stop and inspect the staged paths before any test or commit.

- [ ] **Step 2: Classify modified files**

Use this intended feature list as the initial allowlist:

```text
backend/app/api/router.py
backend/app/api/routes/travel_areas.py
backend/app/data/administrative_areas.py
backend/app/data/travel_areas.py
backend/app/schemas/travel_areas.py
backend/app/schemas/trip.py
backend/app/services/itinerary_recommendations.py
backend/app/services/travel_area_catalog.py
backend/app/services/trips.py
backend/tests/test_travel_area_catalog.py
backend/tests/test_travel_area_catalog_routes.py
backend/tests/test_travel_areas.py
backend/tests/test_trip_db_routes.py
frontend/src/api/backendApi.test.ts
frontend/src/api/backendApi.ts
frontend/src/api/dataApi.ts
frontend/src/api/types.ts
frontend/src/app/__tests__/trip-create.test.tsx
frontend/src/app/__tests__/trip-detail.test.tsx
frontend/src/app/__tests__/trip-edit.test.tsx
frontend/src/components/trip/TripDateRangePicker.test.tsx
frontend/src/components/trip/TripDateRangePicker.tsx
frontend/src/components/trip/TripRegionSelector.test.tsx
frontend/src/components/trip/TripRegionSelector.tsx
frontend/src/pages/itinerary/ItineraryCreatePage.tsx
frontend/src/pages/itinerary/ItineraryDetailPage.tsx
frontend/src/pages/itinerary/ItineraryEditPage.tsx
frontend/src/styles/app.css
frontend/src/test/fixtures.ts
frontend/src/utils/tripDateRange.test.ts
frontend/src/utils/tripDateRange.ts
docs/mvp-api-contract.md
docs/requirements.md
docs/implemented-feature-spec.md
.agent/evals/api-contract-golden.json
docs/superpowers/specs/2026-09-03-trip-region-calendar-unification-design.md
docs/superpowers/plans/2026-09-03-trip-region-calendar-unification.md
CHECKLIST.md
```

Expected: Any dirty file outside the allowlist is marked "do not stage" unless a diff review proves it is part of the feature.

- [ ] **Step 3: Inspect high-risk shared files**

Run:

```powershell
git diff -- frontend/src/pages/itinerary/ItineraryDetailPage.tsx frontend/src/styles/app.css frontend/src/app/__tests__/mypage.test.tsx frontend/src/app/__tests__/policies.test.tsx frontend/src/test/fixtures.ts
```

Expected: `ItineraryDetailPage.tsx` and `app.css` preserve prior title/edit-button/day-strip behavior while adding region/date work. `mypage.test.tsx` and `policies.test.tsx` are not staged for this feature unless the diff is directly required by the final passing test state.

---

### Task 2: Backend Contract Validation

**Files:**
- Review: `backend/app/api/routes/travel_areas.py`
- Review: `backend/app/services/travel_area_catalog.py`
- Review: `backend/app/data/travel_areas.py`
- Review: `backend/app/services/trips.py`
- Review: `backend/app/schemas/trip.py`
- Test: `backend/tests/test_travel_area_catalog.py`
- Test: `backend/tests/test_travel_area_catalog_routes.py`
- Test: `backend/tests/test_travel_areas.py`
- Test: `backend/tests/test_trip_db_routes.py`

**Interfaces:**
- Consumes: `GET /api/travel-areas?sido=<sido>`, `PATCH /api/trips/{tripId}/settings`.
- Produces: Evidence that region catalog and trip settings behave correctly.

- [ ] **Step 1: Run targeted backend tests**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_travel_area_catalog.py tests/test_travel_area_catalog_routes.py tests/test_travel_areas.py tests/test_trip_db_routes.py tests/test_itinerary_recommendations.py -q
```

Expected: PASS. Any failure in invalid `travelAreaId`, unknown `policy-region:`, or revision behavior blocks commit.

- [ ] **Step 2: Verify API behavior with route tests**

Confirm these assertions exist and pass:

```text
GET /api/travel-areas?sido=제주 returns sourceAsOf, wholeArea, recommendedAreas, administrativeAreas.
GET /api/travel-areas?sido=없는지역 returns 400 Unsupported travel area sido.
GET /api/travel-areas without sido returns 422.
PATCH trip settings with jeju-west updates travelAreaId and region without changing days/title/linkedPolicies.
PATCH trip settings with unknown area returns 400 and does not bump revision.
```

Expected: Each assertion is covered by an explicit test, not only by manual inspection.

- [ ] **Step 3: Run full backend suite**

Run:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

Expected: PASS. If failures are unrelated environment failures, capture exact failing test names and compare against `docs/2026-09-04-codex-handoff.md`; do not call the backend complete until the new failures are understood.

---

### Task 3: Frontend Contract and Component Validation

**Files:**
- Review: `frontend/src/api/types.ts`
- Review: `frontend/src/api/dataApi.ts`
- Review: `frontend/src/api/backendApi.ts`
- Review: `frontend/src/components/trip/TripRegionSelector.tsx`
- Review: `frontend/src/components/trip/TripDateRangePicker.tsx`
- Test: `frontend/src/api/backendApi.test.ts`
- Test: `frontend/src/components/trip/TripRegionSelector.test.tsx`
- Test: `frontend/src/components/trip/TripDateRangePicker.test.tsx`
- Test: `frontend/src/utils/tripDateRange.test.ts`

**Interfaces:**
- Consumes: Backend catalog DTO and Trip DTO.
- Produces: Evidence that frontend API boundary and reusable selectors work before page integration.

- [ ] **Step 1: Run component and API tests**

Run:

```powershell
cd frontend
npm.cmd test -- src/api/backendApi.test.ts src/components/trip/TripRegionSelector.test.tsx src/components/trip/TripDateRangePicker.test.tsx src/utils/tripDateRange.test.ts
```

Expected: PASS. If the test runner needs Docker socket access, rerun with the same command under approved escalation and record that escalation was only for the test harness.

- [ ] **Step 2: Run typecheck**

Run:

```powershell
cd frontend
npm.cmd run typecheck
```

Expected: PASS. Any `Trip.region`, `travelAreaId`, or `TravelAreaCatalog` mismatch blocks commit.

- [ ] **Step 3: Inspect accessibility and selection behavior**

Confirm in tests or code:

```text
TripRegionSelector has 17 sido choices.
Changing sido clears incompatible detail selection.
Jeju shows whole, recommended east/west, and administrative Jeju-si/Seogwipo-si.
Large regions expose administrative options beyond the former recommendation limit.
TripDateRangePicker uses a 42-cell month grid and normalizes reverse date selection.
```

Expected: Missing coverage is fixed before moving to page validation.

---

### Task 4: Page Workflow Validation

**Files:**
- Review: `frontend/src/pages/itinerary/ItineraryCreatePage.tsx`
- Review: `frontend/src/pages/itinerary/ItineraryEditPage.tsx`
- Review: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Test: `frontend/src/app/__tests__/trip-create.test.tsx`
- Test: `frontend/src/app/__tests__/trip-edit.test.tsx`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Consumes: Shared selector, shared date picker, `AppDataApi`.
- Produces: Evidence that create/edit/detail workflows satisfy the user request.

- [ ] **Step 1: Run itinerary page tests**

Run:

```powershell
cd frontend
npm.cmd test -- src/app/__tests__/trip-create.test.tsx src/app/__tests__/trip-edit.test.tsx src/app/__tests__/trip-detail.test.tsx
```

Expected: PASS. Required covered behaviors:

```text
Create requires explicit whole/detail area selection, not only a vague sido.
Create sends selected travelAreaId.
Edit can change Jeju east to Jeju west.
Edit does not overwrite title when region changes.
Edit uses the same date-range picker mechanism as create.
Detail period-edit sheet uses the shared date-range picker, not native date inputs.
Viewer/read-only and revision conflict behavior remain intact.
```

- [ ] **Step 2: Run full frontend suite**

Run:

```powershell
cd frontend
npm.cmd test
```

Expected: PASS. If `mypage.test.tsx` or `policies.test.tsx` fail, determine whether the failure is the known local DB slug state or a regression from this feature before staging any fixture changes.

- [ ] **Step 3: Build the frontend**

Run:

```powershell
cd frontend
npm.cmd run build
```

Expected: PASS.

---

### Task 5: Contract, Eval, and Hygiene Validation

**Files:**
- Review: `docs/mvp-api-contract.md`
- Review: `docs/requirements.md`
- Review: `docs/implemented-feature-spec.md`
- Review: `.agent/evals/api-contract-golden.json`
- Review: `CHECKLIST.md`

**Interfaces:**
- Consumes: Final API/UI behavior.
- Produces: Contract and status evidence suitable for commit.

- [ ] **Step 1: Verify contract updates**

Run:

```powershell
rg -n "travel-areas|travelAreaId|region" docs/mvp-api-contract.md docs/requirements.md docs/implemented-feature-spec.md .agent/evals/api-contract-golden.json
python -m json.tool .agent/evals/api-contract-golden.json
```

Expected: Contract documents mention `GET /api/travel-areas`, `Trip.region`, settings `travelAreaId`, invalid ID 400, and dynamic `policy-region:` behavior. JSON validation exits 0.

- [ ] **Step 2: Run diff hygiene**

Run:

```powershell
git diff --check
git diff --cached --check
```

Expected: PASS or no staged diff for the cached command.

- [ ] **Step 3: Scan changed text for replacement characters**

Run:

```powershell
rg -n "�" backend frontend docs .agent CHECKLIST.md
```

Expected: No results in changed files. PowerShell console mojibake does not count; only literal U+FFFD in file content blocks completion.

- [ ] **Step 4: Update CHECKLIST.md**

Replace stale entries with:

```text
Active task/status: trip region catalog/date picker work is implemented and under final validation.
Recent Validation: list exact commands with PASS/FAIL.
Active Risks: list only unresolved test, 5173, viewport, or deployment risks.
```

Expected: `CHECKLIST.md` stays slim and `git diff --check -- CHECKLIST.md` passes.

---

### Task 6: 5173 Smoke and Commit Gate

**Files:**
- Verify: Current running 5173 frontend/backend behavior.
- Stage: Only intended feature files from Task 1 allowlist.

**Interfaces:**
- Consumes: Completed code and tests.
- Produces: One final commit only if all gates pass.

- [ ] **Step 1: Verify 5173 is serving the changed app**

Run:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173 | Select-Object -ExpandProperty StatusCode
```

Expected: `200`.

- [ ] **Step 2: Manual 5173 checks**

Check in browser:

```text
Create trip: Gyeonggi administrative details include previously missing localities such as Yeoncheon.
Create trip: Jeju shows whole, east/west, Jeju-si, and Seogwipo-si as separate choices.
Edit trip: A Jeju east trip can be changed to Jeju west and saved.
Edit trip: Date change uses the same calendar interaction as create.
Detail period edit: Uses the same calendar interaction and preserves overflow/revision behavior.
Detail header: title is prominent and edit button remains at lower-right as requested earlier.
Responsive widths: 360, 390, 430, 1024, and 1440 have no horizontal overflow or clipped critical controls.
```

Expected: Every item passes or the exact failed item is fixed and retested.

- [ ] **Step 3: Stage only intended files**

Run after all validation passes:

```powershell
git add backend/app/api/router.py backend/app/api/routes/travel_areas.py backend/app/data/administrative_areas.py backend/app/data/travel_areas.py backend/app/schemas/travel_areas.py backend/app/schemas/trip.py backend/app/services/itinerary_recommendations.py backend/app/services/travel_area_catalog.py backend/app/services/trips.py backend/tests/test_travel_area_catalog.py backend/tests/test_travel_area_catalog_routes.py backend/tests/test_travel_areas.py backend/tests/test_trip_db_routes.py frontend/src/api/backendApi.test.ts frontend/src/api/backendApi.ts frontend/src/api/dataApi.ts frontend/src/api/types.ts frontend/src/app/__tests__/trip-create.test.tsx frontend/src/app/__tests__/trip-detail.test.tsx frontend/src/app/__tests__/trip-edit.test.tsx frontend/src/components/trip/TripDateRangePicker.test.tsx frontend/src/components/trip/TripDateRangePicker.tsx frontend/src/components/trip/TripRegionSelector.test.tsx frontend/src/components/trip/TripRegionSelector.tsx frontend/src/pages/itinerary/ItineraryCreatePage.tsx frontend/src/pages/itinerary/ItineraryDetailPage.tsx frontend/src/pages/itinerary/ItineraryEditPage.tsx frontend/src/styles/app.css frontend/src/test/fixtures.ts frontend/src/utils/tripDateRange.test.ts frontend/src/utils/tripDateRange.ts docs/mvp-api-contract.md docs/requirements.md docs/implemented-feature-spec.md .agent/evals/api-contract-golden.json docs/superpowers/specs/2026-09-03-trip-region-calendar-unification-design.md docs/superpowers/plans/2026-09-03-trip-region-calendar-unification.md docs/superpowers/plans/2026-09-04-post-claude-trip-region-validation.md CHECKLIST.md
```

Expected: `git status --short` shows only intended files staged. Unrelated files remain unstaged.

- [ ] **Step 4: Review staged diff and commit**

Run:

```powershell
git diff --cached --stat
git diff --cached --check
git commit -m "feat: unify trip region and date selection"
```

Expected: Commit succeeds only after Tasks 1-6 all pass. If any validation fails, do not commit.

## Self-Review

- Spec coverage: The plan validates regional catalog completeness, editable detailed region, create/edit/detail calendar unification, contract sync, 5173 smoke, and prior detail-header visibility.
- Placeholder scan: No TBD/TODO/fill-in steps are present.
- Type consistency: `TravelAreaCatalog`, `TravelAreaOption`, `travelAreaId`, `region`, and `/api/travel-areas` are used consistently with the implementation spec.
