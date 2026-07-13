# Trips Detail Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign `/trips/:tripId` so trip detail becomes the single place for policy context, manual place add, editable recommended-itinerary preview, map, and saved itinerary list.

**Architecture:** Keep the frontend behind `AppDataApi`. Split the current large detail-page responsibilities into small trip-detail UI/state helpers while preserving the existing trip place add/update/move/delete APIs. Add one backend-backed Kakao place search boundary for arbitrary place search; keep recommended-itinerary generation on the existing recommendation endpoint and save accepted previews through existing single-place mutation calls.

**Tech Stack:** React 18, React Router, TypeScript, Vite, Vitest/Testing Library, FastAPI, SQLAlchemy repositories/services, Kakao Local REST through existing backend service, Playwright/Build Web Apps frontend validation.

## Global Constraints

- Do not implement before this plan is accepted.
- Frontend pages/components must access app data through `frontend/src/api/AppDataApi` and related API boundary files.
- API DTO fields stay `camelCase`; database and SQL fields stay `snake_case`.
- Trip routes use numeric string `Trip.id`; do not add public trip slugs.
- `/ai-results` functionality is absorbed into `/trips/:tripId`; `/ai-results?tripId=...` redirects/replaces to trip detail.
- 추천 생성 알고리즘 고도화 is out of scope.
- 추천 일정 저장 UX is one click, but implementation uses existing single-place APIs sequentially.
- 장소명 direct input is removed from the add-place flow; selected Kakao/recommended candidate provides the label.
- Preserve UTF-8 Korean text; use `apply_patch` or UTF-8-aware writes.
- If an API shape changes, update `docs/mvp-api-contract.md`, frontend types/client, backend schemas/routes/services, tests, and `.agent/evals/api-contract-golden.json` together.

---

## File Structure

- Modify `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`: orchestrate new detail layout, preview state, place-add workspace state, save sequence, viewer permission feedback.
- Modify `frontend/src/pages/itinerary/AiResultsPage.tsx`: replace full page with redirect/compatibility bridge to `/trips/:tripId?mode=recommend`.
- Modify `frontend/src/api/types.ts`: add `PlaceSearchCandidate` if backend search endpoint is added.
- Modify `frontend/src/api/dataApi.ts`: add `searchTripPlaces(tripId, options)` method to `AppDataApi` interface and request types.
- Modify `frontend/src/api/backendApi.ts`: call new backend search endpoint through `apiClient`.
- Modify `backend/app/schemas/trip.py`: add `PlaceSearchCandidate` response schema.
- Modify `backend/app/api/routes/trips.py`: add thin route `GET /trips/{trip_id}/place-search`.
- Modify `backend/app/services/trips.py`: authorize trip access and call Kakao Local search provider.
- Modify `docs/mvp-api-contract.md`: document place search endpoint and `/ai-results` compatibility behavior.
- Modify `docs/implemented-feature-spec.md`: after implementation, update screen behavior.
- Modify `.agent/evals/api-contract-golden.json`: add new endpoint contract only if backend search API is implemented.
- Tests: `frontend/src/app/__tests__/trip-detail.test.tsx`, `frontend/src/app/__tests__/place-edit.test.tsx`, `frontend/src/app/__tests__/ai-results.test.tsx`, backend trip route/service tests under `backend/tests/`.
- Update `CHECKLIST.md` with validation evidence and remaining risks after implementation.

---

### Task 1: Lock `/ai-results` Compatibility Redirect

**Files:**
- Modify: `frontend/src/pages/itinerary/AiResultsPage.tsx`
- Test: `frontend/src/app/__tests__/ai-results.test.tsx`

**Interfaces:**
- Consumes: React Router `useSearchParams`, `Navigate` or `useNavigate`.
- Produces: `/ai-results?tripId=55` routes users to `/trips/55?mode=recommend` and shows no standalone AI candidate workspace.

- [ ] **Step 1: Write failing route compatibility test**

Add a test to `frontend/src/app/__tests__/ai-results.test.tsx`:

```tsx
it("redirects ai-results into the integrated trip detail recommendation entry", async () => {
  renderAppRoute("/ai-results?tripId=55");

  await waitFor(() => {
    expect(window.location.pathname).toBe("/trips/55");
  });
  expect(window.location.search).toContain("mode=recommend");
});
```

- [ ] **Step 2: Run the focused failing test**

Run:

```bash
cd frontend
npm test -- src/app/__tests__/ai-results.test.tsx
```

Expected: FAIL because `/ai-results` still renders the standalone AI results page.

- [ ] **Step 3: Replace page body with redirect bridge**

In `frontend/src/pages/itinerary/AiResultsPage.tsx`, reduce the exported component to a compatibility redirect. Keep imports minimal.

```tsx
import { Navigate, useSearchParams } from "react-router-dom";

export function AiResultsPage() {
  const [searchParams] = useSearchParams();
  const tripId = searchParams.get("tripId");
  const destination = tripId ? `/trips/${encodeURIComponent(tripId)}?mode=recommend` : "/trips";
  return <Navigate to={destination} replace />;
}
```

- [ ] **Step 4: Run the focused test again**

Run:

```bash
cd frontend
npm test -- src/app/__tests__/ai-results.test.tsx
```

Expected: PASS for redirect behavior. Existing standalone AI page tests should be deleted or rewritten as trip-detail tests in later tasks.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/itinerary/AiResultsPage.tsx frontend/src/app/__tests__/ai-results.test.tsx
git commit -m "Route recommendation entry back to trip detail

Constraint: /ai-results is now a compatibility entry for the integrated trip-detail recommendation flow.
Confidence: medium
Scope-risk: narrow
Tested: cd frontend && npm test -- src/app/__tests__/ai-results.test.tsx
Not-tested: Full trip-detail integrated recommendation UI pending later tasks"
```

---

### Task 2: Reshape Trip Detail Layout Without Changing Data Mutations

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Modify: `frontend/src/styles/app.css`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Consumes: existing `Trip.days`, `linkedPolicies`, `recommendedPolicies`, `currentUserRole`.
- Produces: new visual order: policies, two CTAs, Day tabs, map, then saved itinerary list only when saved places exist.

- [ ] **Step 1: Write failing layout test for empty trip**

Add a fixture/test in `trip-detail.test.tsx` that returns a trip with `days: { 1: [], 2: [], 3: [] }`.

```tsx
it("shows empty trip detail with policy actions, day tabs, map, and no itinerary list", async () => {
  mockAppDataApi.getTrip.mockResolvedValueOnce({
    ...baseTrip,
    id: "101",
    title: "제주 3일 여행",
    days: { 1: [], 2: [], 3: [] },
    linkedPolicies: [],
    recommendedPolicies: [recommendedPolicy],
    currentUserRole: "owner",
  });

  renderAppRoute("/trips/101");

  expect(await screen.findByText("제주 3일 여행")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /장소 추가/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /추천 일정만들기/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Day 1/ })).toBeInTheDocument();
  expect(screen.getByText("아직 표시할 장소가 없어요")).toBeInTheDocument();
  expect(screen.queryByText("Day 1 일정")).not.toBeInTheDocument();
  expect(screen.queryByRole("tablist", { name: /일정 표시 방식/ })).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the focused failing test**

```bash
cd frontend
npm test -- src/app/__tests__/trip-detail.test.tsx
```

Expected: FAIL because list/map tabs still exist and action buttons are inside list mode.

- [ ] **Step 3: Move action row and remove `ListMapToggle` rendering**

In `ItineraryDetailPage.tsx`:

- Remove `TripDetailViewMode`, `viewMode`, `selectViewMode`, and `ListMapToggle`.
- Keep `selectedMapPlaceId` and Day query handling.
- Render `PrototypeTripMap` immediately after Day tabs.
- Render timeline/list only when `dayPlaces.length > 0`.
- Move the two CTA buttons above Day tabs.

Use this render structure:

```tsx
<section className="trip-primary-actions" aria-label="일정 편집 작업">
  <button className="prototype-trip-action-button prototype-trip-action-add" type="button" onClick={openAddPlace}>
    + 장소 추가
  </button>
  <button className="prototype-trip-action-button prototype-trip-action-ai" type="button" onClick={openRecommendationPreview}>
    ✨ 추천 일정만들기
  </button>
</section>

<div className="day-tabs">{dayNumbers.map(/* existing DroppableDayTab */)}</div>

<PrototypeTripMap
  dayNumber={visibleDay}
  onSelectPlace={selectMapPlace}
  onShowPlaceDetail={(place) => setPlaceDetail({ dayNumber: visibleDay, place })}
  places={dayPlaces}
  selectedPlaceId={selectedMapPlaceId}
/>

{dayPlaces.length > 0 && (
  <TripDayTimeline /* existing SortableContext content */ />
)}
```

- [ ] **Step 4: Keep viewer buttons visible but guarded**

Change `openAddPlace` and new `openRecommendationPreview` to show a toast instead of hiding buttons:

```tsx
const showEditPermissionRequired = () => {
  setNotice("편집 권한이 필요해요. 이 일정은 보기 권한으로 참여 중이라 장소 추가나 추천 일정 저장을 할 수 없어요.");
  window.setTimeout(() => setNotice(null), 2200);
};
```

- [ ] **Step 5: Add CSS for action row and empty map placement**

In `frontend/src/styles/app.css`, add focused classes:

```css
.trip-primary-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin: 14px 0 16px;
}

.trip-primary-actions .prototype-trip-action-button {
  min-height: 48px;
  justify-content: center;
}

@media (max-width: 380px) {
  .trip-primary-actions {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: Run focused test**

```bash
cd frontend
npm test -- src/app/__tests__/trip-detail.test.tsx
```

Expected: PASS for the empty-detail layout assertions.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/itinerary/ItineraryDetailPage.tsx frontend/src/styles/app.css frontend/src/app/__tests__/trip-detail.test.tsx
git commit -m "Make trip detail map-first itinerary layout

Constraint: Trip detail must remove list/map tabs and keep AppDataApi data boundaries.
Rejected: Keeping /ai-results-style separate navigation | User approved detail-integrated flow.
Confidence: medium
Scope-risk: moderate
Tested: cd frontend && npm test -- src/app/__tests__/trip-detail.test.tsx
Not-tested: Rendered responsive QA pending Build Web Apps validation"
```

---

### Task 3: Add Editable Recommended-Itinerary Preview State

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Consumes: `appDataApi.listRecommendations(tripId)` and existing `Recommendation` DTO.
- Produces: local unsaved preview places grouped by Day, with `저장 전 미리보기`, editable time/memo/day/delete, save/cancel controls.

- [ ] **Step 1: Define local preview types near existing draft types**

```tsx
type PreviewPlace = TripPlaceRequest & {
  previewId: string;
  dayNumber: number;
};

type RecommendationPreviewState = {
  status: "idle" | "loading" | "ready" | "saving";
  places: PreviewPlace[];
  error: string;
};
```

- [ ] **Step 2: Write failing preview generation test**

```tsx
it("shows editable unsaved recommendation preview without saving immediately", async () => {
  mockAppDataApi.getTrip.mockResolvedValueOnce({ ...baseTrip, id: "102", days: { 1: [], 2: [] } });
  mockAppDataApi.listRecommendations.mockResolvedValueOnce([
    { title: "성산일출봉", label: "⛰️", meta: "제주 서귀포시", reason: "추천", suggestedDay: 1 },
  ]);

  renderAppRoute("/trips/102");
  await userEvent.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));

  expect(await screen.findByText("저장 전 미리보기")).toBeInTheDocument();
  expect(screen.getByText("성산일출봉")).toBeInTheDocument();
  expect(mockAppDataApi.addTripPlace).not.toHaveBeenCalled();
});
```

- [ ] **Step 3: Implement preview creation**

Add `openRecommendationPreview`:

```tsx
const openRecommendationPreview = async () => {
  if (!trip) return;
  if (!canEditTrip) {
    showEditPermissionRequired();
    return;
  }
  setRecommendationPreview({ status: "loading", places: [], error: "" });
  try {
    const recommendations = await appDataApi.listRecommendations(trip.id);
    const nextPlaces = recommendations.map((item, index): PreviewPlace => ({
      ...recommendationPlacePayload(item, item.meta.match(/\b\d{2}:\d{2}\b/)?.[0] ?? defaultPlaceTime),
      previewId: item.id ?? item.externalPlaceId ?? `${item.title}:${index}`,
      dayNumber: dayNumbers.includes(item.suggestedDay ?? 1) ? item.suggestedDay ?? 1 : visibleDay,
    }));
    setRecommendationPreview({ status: "ready", places: nextPlaces, error: "" });
  } catch {
    setRecommendationPreview({ status: "idle", places: [], error: "추천 일정을 불러오지 못했어요. 잠시 후 다시 시도해 주세요." });
  }
};
```

- [ ] **Step 4: Render preview instead of saved places when ready**

Derive visible map/list places:

```tsx
const isPreviewActive = recommendationPreview.status === "ready" || recommendationPreview.status === "saving";
const previewDayPlaces = recommendationPreview.places.filter((place) => place.dayNumber === visibleDay);
const displayedPlaces = isPreviewActive ? previewDayPlaces : dayPlaces;
```

Render `저장 전 미리보기` banner before map when `isPreviewActive` is true.

- [ ] **Step 5: Add preview edit/delete handlers**

```tsx
const updatePreviewPlace = (previewId: string, patch: Partial<PreviewPlace>) => {
  setRecommendationPreview((current) => ({
    ...current,
    places: current.places.map((place) => place.previewId === previewId ? { ...place, ...patch } : place),
  }));
};

const deletePreviewPlace = (previewId: string) => {
  setRecommendationPreview((current) => ({
    ...current,
    places: current.places.filter((place) => place.previewId !== previewId),
  }));
};
```

- [ ] **Step 6: Run focused tests**

```bash
cd frontend
npm test -- src/app/__tests__/trip-detail.test.tsx
```

Expected: PASS for preview generation and no immediate save.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/itinerary/ItineraryDetailPage.tsx frontend/src/app/__tests__/trip-detail.test.tsx
git commit -m "Add editable recommendation preview state

Constraint: Recommendation itinerary must remain unsaved until explicit confirmation.
Rejected: Immediate persistence | User selected preview-first save.
Confidence: medium
Scope-risk: moderate
Tested: cd frontend && npm test -- src/app/__tests__/trip-detail.test.tsx
Not-tested: Replacement save sequence pending next task"
```

---

### Task 4: Save Preview Through Existing Single-Place APIs

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Consumes: preview places from Task 3, `appDataApi.addTripPlace`, existing `appDataApi.deleteTripPlace` if replacing saved places.
- Produces: `saveRecommendationPreview()` that asks for replacement when saved places exist, then sequentially deletes old places and adds preview places.

- [ ] **Step 1: Write failing save test for empty trip**

```tsx
it("saves recommendation preview with one user action through existing add place API", async () => {
  mockAppDataApi.getTrip.mockResolvedValueOnce({ ...baseTrip, id: "103", revision: 4, days: { 1: [] } });
  mockAppDataApi.listRecommendations.mockResolvedValueOnce([
    { title: "성산일출봉", label: "⛰️", meta: "제주 서귀포시", reason: "추천", suggestedDay: 1 },
  ]);
  mockAppDataApi.addTripPlace.mockResolvedValueOnce({
    ...baseTrip,
    id: "103",
    revision: 5,
    days: { 1: [{ id: "p1", time: "09:00", label: "성산일출봉", meta: "제주 서귀포시" }] },
  });

  renderAppRoute("/trips/103");
  await userEvent.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
  await userEvent.click(await screen.findByRole("button", { name: /이 일정으로 저장/ }));

  await waitFor(() => expect(mockAppDataApi.addTripPlace).toHaveBeenCalledTimes(1));
  expect(screen.queryByText("저장 전 미리보기")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Add replacement confirm state**

```tsx
const [replacePreviewConfirmOpen, setReplacePreviewConfirmOpen] = useState(false);
const hasSavedPlaces = Object.values(trip?.days ?? {}).some((places) => places.length > 0);
```

- [ ] **Step 3: Implement explicit save gate**

```tsx
const requestSaveRecommendationPreview = () => {
  if (hasSavedPlaces) {
    setReplacePreviewConfirmOpen(true);
    return;
  }
  void saveRecommendationPreview({ replaceExisting: false });
};
```

- [ ] **Step 4: Implement sequential save**

```tsx
const saveRecommendationPreview = async ({ replaceExisting }: { replaceExisting: boolean }) => {
  if (!trip || recommendationPreview.places.length === 0) return;
  setRecommendationPreview((current) => ({ ...current, status: "saving", error: "" }));
  try {
    let currentTrip = trip;
    if (replaceExisting) {
      for (const place of Object.values(currentTrip.days).flat()) {
        if (place.id) currentTrip = await appDataApi.deleteTripPlace(currentTrip.id, place.id, currentTrip.revision);
      }
    }
    for (const previewPlace of recommendationPreview.places) {
      const { dayNumber, previewId: _previewId, ...placePayload } = previewPlace;
      currentTrip = await appDataApi.addTripPlace(currentTrip.id, dayNumber, {
        ...placePayload,
        expectedRevision: currentTrip.revision,
      });
    }
    setTrip(currentTrip);
    setRecommendationPreview({ status: "idle", places: [], error: "" });
    setNotice("추천 일정을 저장했어요.");
  } catch (error) {
    if (isTripConflict(error)) await refreshTripAfterConflict((message) => setRecommendationPreview((current) => ({ ...current, error: message })));
    else setRecommendationPreview((current) => ({ ...current, status: "ready", error: "추천 일정을 저장하지 못했어요. 잠시 후 다시 시도해 주세요." }));
  }
};
```

- [ ] **Step 5: Render replacement confirmation**

Use existing `ConfirmDialog` with title `기존 장소를 대체할까요?`, confirm `대체하고 저장`, cancel `취소`.

- [ ] **Step 6: Run focused tests**

```bash
cd frontend
npm test -- src/app/__tests__/trip-detail.test.tsx
```

Expected: PASS for save and replacement tests.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/itinerary/ItineraryDetailPage.tsx frontend/src/app/__tests__/trip-detail.test.tsx
git commit -m "Persist recommendation previews through existing place APIs

Constraint: User gets one save action while implementation reuses existing single-place mutations.
Rejected: New bulk-save endpoint | User chose sequential existing API calls.
Confidence: medium
Scope-risk: moderate
Tested: cd frontend && npm test -- src/app/__tests__/trip-detail.test.tsx
Not-tested: Browser rendered save flow pending frontend QA"
```

---

### Task 5: Add Backend Kakao Place Search Boundary

**Files:**
- Modify: `backend/app/schemas/trip.py`
- Modify: `backend/app/api/routes/trips.py`
- Modify: `backend/app/services/trips.py`
- Test: `backend/tests/test_trips.py` or nearest existing trip route test file
- Modify: `docs/mvp-api-contract.md`
- Modify: `.agent/evals/api-contract-golden.json`

**Interfaces:**
- Consumes: existing `KakaoLocalClient` / `build_kakao_local_search_provider` and trip authorization.
- Produces: `GET /api/trips/{tripId}/place-search?query=성산일출봉` returning `PlaceSearchCandidate[]` with Kakao metadata.

- [ ] **Step 1: Write failing backend API test**

Add a test using dependency-injected/fake Kakao provider:

```python
def test_search_trip_places_returns_kakao_candidates(client, auth_headers, seeded_trip, monkeypatch):
    class FakeSearchProvider:
        def search_keyword(self, query, *, x=None, y=None, radius=None, size=10):
            return [
                KakaoLocalPlace(
                    external_place_id="kakao-1",
                    name="성산일출봉",
                    category_name="관광명소",
                    category_group_code="AT4",
                    category_group_name="관광명소",
                    phone="064-000-0000",
                    address="제주 서귀포시 성산읍",
                    road_address="제주 서귀포시 성산읍 일출로",
                    longitude=126.9425,
                    latitude=33.4581,
                    place_url="https://place.map.kakao.com/kakao-1",
                )
            ]

    monkeypatch.setattr("app.services.trips.build_kakao_local_search_provider", lambda: FakeSearchProvider())

    response = client.get(f"/api/trips/{seeded_trip.id}/place-search?query=성산일출봉", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()[0]["title"] == "성산일출봉"
    assert response.json()[0]["sourceProvider"] == "kakao"
    assert response.json()[0]["externalPlaceId"] == "kakao-1"
```

- [ ] **Step 2: Run failing backend test**

```bash
cd backend
python -m pytest tests/test_trips.py -k place_search -vv
```

Expected: FAIL because endpoint/schema do not exist.

- [ ] **Step 3: Add schema**

In `backend/app/schemas/trip.py`:

```python
class PlaceSearchCandidate(BaseModel):
    id: str | None = None
    label: str = "📍"
    title: str
    meta: str
    categoryCode: str | None = None
    categoryName: str | None = None
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    placeUrl: str | None = None
    sourceProvider: str | None = "kakao"
    externalPlaceId: str | None = None
```

- [ ] **Step 4: Add service function**

In `backend/app/services/trips.py` add `search_places_for_trip(db, user, trip_id, query)` that:

1. Loads accessible trip with existing helper.
2. Raises not found/forbidden consistently with trip routes.
3. Calls Kakao provider if configured.
4. Maps Kakao results to camelCase dicts.
5. Returns `[]` for blank query or unavailable provider.

- [ ] **Step 5: Add thin route**

In `backend/app/api/routes/trips.py`:

```python
@router.get("/{trip_id}/place-search", response_model=list[PlaceSearchCandidate])
def search_trip_places(
    trip_id: str,
    query: str = Query(min_length=1, max_length=80),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PlaceSearchCandidate]:
    return [PlaceSearchCandidate(**item) for item in trip_service.search_places_for_trip(db, current_user, trip_id=trip_id, query=query)]
```

- [ ] **Step 6: Update contract/eval**

Document:

```md
### GET /trips/{trip_id}/place-search
Authenticated owner/editor/viewer can search Kakao-registered places for selection; saving still uses POST /trips/{trip_id}/days/{day_number}/places.
```

Add a golden entry for response fields in `.agent/evals/api-contract-golden.json`.

- [ ] **Step 7: Run backend test**

```bash
cd backend
python -m pytest tests/test_trips.py -k place_search -vv
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/trip.py backend/app/api/routes/trips.py backend/app/services/trips.py backend/tests/test_trips.py docs/mvp-api-contract.md .agent/evals/api-contract-golden.json
git commit -m "Expose trip-scoped Kakao place search

Constraint: Place search must stay behind FastAPI/AppDataApi boundaries and preserve Kakao metadata for existing place-add API.
Rejected: Direct page-level seed/mock search | Runtime mock mode is removed and frontend must use AppDataApi.
Confidence: medium
Scope-risk: moderate
Tested: cd backend && python -m pytest tests/test_trips.py -k place_search -vv
Not-tested: Real Kakao Local credentials smoke"
```

---

### Task 6: Replace Add-Place Sheet With Integrated Place Workspace

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/dataApi.ts`
- Modify: `frontend/src/api/backendApi.ts`
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Modify: `frontend/src/styles/app.css`
- Test: `frontend/src/app/__tests__/place-edit.test.tsx`

**Interfaces:**
- Consumes: `appDataApi.searchTripPlaces(tripId, { query })`, `appDataApi.listRecommendations(tripId)`, `appDataApi.addTripPlace`.
- Produces: full-screen/sheet workspace with Day selector, search, map, candidate rail, selected place summary, time picker, memo, and save button.

- [ ] **Step 1: Add frontend API types and interface**

In `types.ts`:

```ts
export type PlaceSearchCandidate = Recommendation;
```

In `dataApi.ts`:

```ts
export type PlaceSearchOptions = { query: string };
searchTripPlaces: (tripId: string, options: PlaceSearchOptions) => Promise<PlaceSearchCandidate[]>;
```

In `backendApi.ts`:

```ts
searchTripPlaces: (tripId, options) => apiClient.get<PlaceSearchCandidate[]>(`/api/trips/${tripId}/place-search${queryString(options)}`),
```

- [ ] **Step 2: Write failing place workspace test**

```tsx
it("adds a selected Kakao place with time and memo without manual place-name input", async () => {
  mockAppDataApi.getTrip.mockResolvedValueOnce({ ...baseTrip, id: "104", revision: 2, days: { 1: [] } });
  mockAppDataApi.listRecommendations.mockResolvedValueOnce([]);
  mockAppDataApi.searchTripPlaces.mockResolvedValueOnce([
    { title: "성산일출봉", label: "📍", meta: "제주 서귀포시", reason: "검색", address: "제주 서귀포시", sourceProvider: "kakao", externalPlaceId: "kakao-1" },
  ]);
  mockAppDataApi.addTripPlace.mockResolvedValueOnce({
    ...baseTrip,
    id: "104",
    revision: 3,
    days: { 1: [{ id: "p1", time: "09:00", label: "성산일출봉", meta: "일출 보기" }] },
  });

  renderAppRoute("/trips/104");
  await userEvent.click(await screen.findByRole("button", { name: /장소 추가/ }));
  expect(screen.queryByLabelText("장소명")).not.toBeInTheDocument();

  await userEvent.type(screen.getByRole("searchbox", { name: /카카오맵 장소 검색/ }), "성산일출봉");
  await userEvent.click(await screen.findByRole("button", { name: /성산일출봉 선택/ }));
  await userEvent.type(screen.getByLabelText("메모"), "일출 보기");
  await userEvent.click(screen.getByRole("button", { name: /일정에 저장/ }));

  await waitFor(() => expect(mockAppDataApi.addTripPlace).toHaveBeenCalledWith("104", 1, expect.objectContaining({ label: "성산일출봉", meta: "일출 보기", expectedRevision: 2 })));
});
```

- [ ] **Step 3: Convert `PlaceEditorSheet` add mode to `PlaceAddWorkspace`**

Create a focused component inside the same file first:

```tsx
function PlaceAddWorkspace(props: {
  dayNumbers: number[];
  selectedDay: number;
  candidates: Recommendation[];
  selectedCandidate: Recommendation | null;
  searchQuery: string;
  form: Pick<TripPlaceRequest, "time" | "meta">;
  onSelectDay: (day: number) => void;
  onSearchChange: (query: string) => void;
  onSelectCandidate: (candidate: Recommendation) => void;
  onChangeForm: (form: Pick<TripPlaceRequest, "time" | "meta">) => void;
  onSubmit: () => void;
  onClose: () => void;
}) { /* render approved wireframe */ }
```

- [ ] **Step 4: Remove manual label editing in add mode**

`submitPlaceEditor` for add mode must validate selected candidate instead of `placeForm.label` free text.

- [ ] **Step 5: Run focused place tests**

```bash
cd frontend
npm test -- src/app/__tests__/place-edit.test.tsx
```

Expected: PASS for selected-place save and no manual label input.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/dataApi.ts frontend/src/api/backendApi.ts frontend/src/pages/itinerary/ItineraryDetailPage.tsx frontend/src/styles/app.css frontend/src/app/__tests__/place-edit.test.tsx
git commit -m "Integrate Kakao place selection into trip add-place flow

Constraint: Users choose a Kakao/recommended place and only enter visit time plus memo.
Rejected: Manual place-name input | User explicitly removed direct place-name entry.
Confidence: medium
Scope-risk: moderate
Tested: cd frontend && npm test -- src/app/__tests__/place-edit.test.tsx
Not-tested: Browser rendered workspace pending frontend QA"
```

---

### Task 7: Documentation, Evals, Checklist, and Full Regression

**Files:**
- Modify: `docs/implemented-feature-spec.md`
- Modify: `docs/mvp-api-contract.md`
- Modify: `.agent/evals/api-contract-golden.json`
- Modify: `CHECKLIST.md`

**Interfaces:**
- Consumes: completed frontend/backend behavior.
- Produces: updated source-of-truth docs and validation record.

- [ ] **Step 1: Run targeted frontend tests**

```bash
cd frontend
npm test -- src/app/__tests__/trip-detail.test.tsx src/app/__tests__/place-edit.test.tsx src/app/__tests__/ai-results.test.tsx
```

Expected: PASS.

- [ ] **Step 2: Run backend targeted tests**

```bash
cd backend
python -m pytest tests/test_trips.py -k "place_search or recommendations or trip_places" -vv
```

Expected: PASS.

- [ ] **Step 3: Run full fast lane**

```bash
cd frontend
npm run typecheck
npm test
npm run build
cd ../backend
python -m pytest
cd ..
docker compose -f compose.yaml config
```

Expected: all PASS.

- [ ] **Step 4: Run rendered frontend QA with Build Web Apps skill after Codex restart**

Use the command provided below in the user handoff. The target flow is:

```text
/trips/{seededTripId} -> empty/saved trip detail -> 추천 일정만들기 preview -> edit/save state -> 장소 추가 workspace -> select/search place -> save controls
```

Expected: QA report covers page identity, blank-page check, framework overlay, console health, screenshot evidence, interaction proof, mobile and desktop viewports.

- [ ] **Step 5: Update docs and checklist**

Update `docs/implemented-feature-spec.md` with the implemented behavior. Update `CHECKLIST.md` with latest validation commands and active risks only.

- [ ] **Step 6: UTF-8 and diff hygiene**

```bash
git diff --check
python3 - <<'PY'
from pathlib import Path
for path in [Path('docs/implemented-feature-spec.md'), Path('docs/mvp-api-contract.md'), Path('CHECKLIST.md')]:
    text = path.read_text(encoding='utf-8')
    assert '\ufffd' not in text, f'U+FFFD found in {path}'
print('utf8-ok')
PY
```

Expected: `git diff --check` has no output and script prints `utf8-ok`.

- [ ] **Step 7: Commit**

```bash
git add docs/implemented-feature-spec.md docs/mvp-api-contract.md .agent/evals/api-contract-golden.json CHECKLIST.md
git commit -m "Document integrated trip detail itinerary flow

Constraint: API and feature source-of-truth docs must match the implemented contract.
Confidence: medium
Scope-risk: narrow
Tested: frontend typecheck/test/build, backend pytest, compose config, git diff --check, UTF-8 check
Not-tested: Production Kakao credential smoke unless runtime credentials are available"
```

---

## Plan Self-Review

- Spec coverage: Covers layout order, `/ai-results` absorption, unsaved editable preview, replacement confirm, sequential save, place add workspace, Kakao place search boundary, viewer CTA feedback, docs/evals/checklist, and rendered QA.
- Placeholder scan: No `TBD`, `TODO`, or open-ended implementation placeholders are present.
- Type consistency: `PreviewPlace`, `RecommendationPreviewState`, and `PlaceSearchCandidate` are introduced before use; API method names are consistent across frontend interface and backend client.
- Scope risk: The largest risk is keeping `ItineraryDetailPage.tsx` manageable. If the file becomes hard to review during execution, split local components into `frontend/src/pages/itinerary/tripDetail/` after Task 2 while preserving the same interfaces.
