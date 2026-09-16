# 일정 편집 모드 v1 + 배치 삭제 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 타임라인 상단 `편집` 토글로 모든 Day 를 세로로 적층해 전체 일정을 조망하고, 체크박스로 여러 장소를 골라 한 번의 API 호출로 삭제한다.

**Architecture:** 백엔드에 배치 삭제 엔드포인트 하나를 추가한다(한 트랜잭션, 리비전 1회 증가, 영향받은 Day 재정렬). 프런트는 `isEditMode` 상태 하나로 Day 탭 스트립과 DnD 타임라인 대신 `EditModeList`(Day 헤더 + 체크박스 카드) 를 렌더하고, 하단 고정 바에서 선택 수와 `삭제` 를 제공한다. 편집 모드에서는 드래그·카드 탭을 끈다(v1). 기존 `ConfirmDialog` 로 확인한다.

**Tech Stack:** FastAPI + SQLAlchemy(pytest, FakeDb 더블), React/Vite(vitest + testing-library), CSS(`app.css`).

**Spec:** `docs/superpowers/specs/2026-09-16-itinerary-card-management-design.md` §브랜치 ②

## Global Constraints

- 브랜치 `feature/itinerary-edit-mode`, 워크트리 `.superpowers/worktrees/itinerary-edit-mode`, base = `feature/itinerary-place-sheet@b1fb6a8` (①이 먼저 머지되어야 한다 — PR base 는 ① 또는 ① 머지 후 develop).
- **커밋은 테스트 통과 후 사용자 승인 뒤에만.** 각 Task 끝은 보고이지 커밋이 아니다. 푸시·PR 은 Codex.
- 파일은 Edit 도구로 부분 수정. 파일 전체 재작성·Python/Node/PowerShell 로 쓰기 금지(줄끝). 스테이징 전 `git diff --stat` == `git diff --ignore-space-at-eol --stat`.
- 백엔드 테스트: 워크트리에는 venv 가 없다. `cd <worktree>/backend` 에서 메인 리포 venv 로 실행: `C:/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest tests/<file> -q` (기준선: `tests/test_trip_db_service.py tests/test_trip_db_routes.py` 141 passed). 로컬/개발/운영 DB 에 마이그레이션·쿼리 금지 — 스키마 변경 없음.
- 프런트 테스트: `cd frontend && npx vitest run <file>`; 루트 `npm test` 금지. 타입: `npx tsc --noEmit -p tsconfig.json`.
- API 변경은 `docs/mvp-api-contract.md` 와 `.agent/evals/api-contract-golden.json` 을 같은 Task 에서 갱신한다(AGENTS.md 규칙). DTO camelCase, 경로 `/api` 접두.
- **엔드포인트 결정(스펙과 다름):** 스펙의 `DELETE /trips/{id}/places` + body 대신 **`POST /api/trips/{trip_id}/places/batch-delete`**. 이유: `apiClient.delete` 는 body 를 받지 않고(`client.ts:142`), 기존 배치 추가도 `POST …/places/batch` 다. DELETE+body 는 프록시/클라이언트에서 버려질 수 있다.
- 4174 는 사용자 포트. 5173 은 다른 워크트리가 점유 중 — 수동 확인은 5176(① 과 같은 서버를 이 워크트리로 재기동).
- 편집 모드 하단 바는 `.recommendation-preview-action-bar` 와 같은 고정 배치 규칙을 따른다: 모바일 `bottom: calc(72px + safe-area)`, `@media (min-width: 768px)` 에서 `bottom:0`(탭바 없음). 두 뷰포트 모두 확인.

## 파일 구조

| 파일 | 변경 |
|---|---|
| `backend/app/schemas/trip.py` | `DeleteTripPlacesRequest` |
| `backend/app/services/trips.py` | `delete_trip_places` |
| `backend/app/api/routes/trips.py` | `POST /{trip_id}/places/batch-delete` |
| `backend/tests/test_trip_db_service.py`, `backend/tests/test_trip_db_routes.py` | 서비스·라우트 테스트 |
| `docs/mvp-api-contract.md`, `.agent/evals/api-contract-golden.json` | 계약 |
| `frontend/src/api/dataApi.ts`, `backendApi.ts`, `backendApi.test.ts` | `deleteTripPlaces` |
| `frontend/src/pages/itinerary/ItineraryDetailPage.tsx` | `isEditMode`, `EditModeList`, `EditModeBar`, 배치 삭제 흐름 |
| `frontend/src/styles/app.css` | `.edit-mode-*` |
| `frontend/src/app/__tests__/trip-edit-mode.test.tsx` | 신규 |

---

### Task 1: 백엔드 배치 삭제 (서비스 + 라우트 + 스키마 + 계약)

**Files:**
- Modify: `backend/app/schemas/trip.py` (L191 `CreateTripPlacesRequest` 아래)
- Modify: `backend/app/services/trips.py` (`delete_trip_place` ~L1346 아래)
- Modify: `backend/app/api/routes/trips.py` (`delete_trip_place` ~L258 아래)
- Modify: `docs/mvp-api-contract.md` (L1171 `### DELETE /trips/{trip_id}/places/{place_id}` 섹션 뒤), `.agent/evals/api-contract-golden.json` (`endpoints` 배열, 기존 DELETE places 항목 뒤)
- Test: `backend/tests/test_trip_db_service.py` (L2021 `test_delete_trip_place_removes_existing_place` 뒤), `backend/tests/test_trip_db_routes.py` (L798 배치 라우트 테스트들 뒤)

**Interfaces:**
- Produces: `POST /api/trips/{trip_id}/places/batch-delete` body `{ "expectedRevision": number>=1, "placeIds": number[] (1~50) }` → `Trip`. 403 viewer, 404 any id missing (no revision bump), 409 stale revision, 422 empty list. 서비스 `delete_trip_places(db, user, trip_handle, place_ids: list[int], expected_revision: int) -> dict`.

- [ ] **Step 1: 서비스 실패 테스트** — `test_trip_db_service.py` L2040 부근에 추가. `make_trip()`(L65-113) 은 **Day 1 에 장소 하나(id=1)** 만 가진다. 여러 Day 에 걸친 삭제·재정렬을 검증하려면 테스트 안에서 장소를 더 붙인다. 아래 헬퍼를 테스트들 위에 한 번 정의한다(`TripPlace`·`TripDay`·`date`·`time` 은 파일 상단에 이미 import 됨):

```python
def _add_places_for_batch_delete(trip: Trip) -> None:
    day_one = trip.days[0]
    day_one.places.append(
        TripPlace(id=2, trip_day_id=1, place_name="Market", visit_time=time(11, 0), order_num=2, memo="Food")
    )
    day_one.places.append(
        TripPlace(id=3, trip_day_id=1, place_name="Museum", visit_time=time(14, 0), order_num=3, memo="Art")
    )
    day_two = TripDay(id=2, trip_id=7, day_number=2, date=date(2026, 6, 16))
    day_two.places = [
        TripPlace(id=4, trip_day_id=2, place_name="Cafe stop", visit_time=time(12, 0), order_num=1, memo="Dessert")
    ]
    trip.days.append(day_two)


def test_delete_trip_places_removes_many_and_reorders_each_day(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    _add_places_for_batch_delete(trip)
    day_one, day_two = trip.days
    deleted: list[TripPlace] = []
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )

    def delete_place_stub(_db, place):
        deleted.append(place)

    monkeypatch.setattr(trip_service.trip_repository, "delete_trip_place", delete_place_stub)

    payload = trip_service.delete_trip_places(fake_db, user, "7", [1, 3, 4], 1)

    assert sorted(place.id for place in deleted) == [1, 3, 4]   # 두 Day 에 걸쳐 삭제
    assert fake_db.commits == 1
    assert trip.revision == 2
    assert payload["revision"] == 2


def test_delete_trip_places_dedupes_ids_and_bumps_revision_once(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )
    monkeypatch.setattr(trip_service.trip_repository, "delete_trip_place", lambda _db, _place: None)
    bumps: list[int] = []
    monkeypatch.setattr(
        trip_service.trip_repository,
        "bump_trip_revision_if_current",
        lambda _db, *, trip_id, expected_revision: bumps.append(expected_revision) or True,
    )

    trip_service.delete_trip_places(fake_db, user, "7", [1, 1, 2], 1)

    assert bumps == [1]
    assert fake_db.commits == 1


def test_delete_trip_places_404_on_unknown_id_without_bump(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )
    bumped = []
    monkeypatch.setattr(
        trip_service.trip_repository,
        "bump_trip_revision_if_current",
        lambda *_a, **_k: bumped.append(True) or True,
    )

    with pytest.raises(trip_service.TripServiceError) as error:
        trip_service.delete_trip_places(fake_db, user, "7", [1, 999], 1)

    assert error.value.status_code == 404
    assert bumped == []
    assert fake_db.commits == 0
```

`TripServiceError` 의 상태 코드 속성명은 파일에서 확인해(`status_code` 또는 `status`) 맞춘다. `payload["revision"]` 은 `_refresh_trip_payload` 가 `get_accessible_trip_by_id` 스텁이 돌려준 같은 `trip` 을 직렬화하므로 `trip.revision`(bump 후 2) 이 나온다 — 첫 테스트는 `bump_trip_revision_if_current` 를 스텁하지 않아 `FakeDb.execute` 의 `rowcount=1` 로 성공한다.

- [ ] **Step 2: 실패 확인**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_trip_db_service.py -q -k delete_trip_places`
Expected: FAIL — `AttributeError: … has no attribute 'delete_trip_places'`

- [ ] **Step 3: 스키마 + 서비스**

`schemas/trip.py` L193 뒤:

```python
class DeleteTripPlacesRequest(BaseModel):
    expectedRevision: int = Field(ge=1)
    placeIds: list[int] = Field(min_length=1, max_length=50)
```

`services/trips.py` `delete_trip_place` 바로 아래:

```python
def delete_trip_places(
    db: Session,
    user: User,
    trip_handle: str,
    place_ids: list[int],
    expected_revision: int,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    # 하나라도 없으면 리비전을 올리기 전에 404. 부분 삭제는 없다.
    unique_ids = list(dict.fromkeys(place_ids))
    places = [_find_trip_place(trip, place_id) for place_id in unique_ids]
    _bump_trip_revision_or_conflict(db, trip, expected_revision)
    for place in places:
        trip_repository.delete_trip_place(db, place)
    db.commit()
    return _refresh_trip_payload(db, trip.id, user)
```

재정렬은 하지 않는다 — 단건 `delete_trip_place` 도 하지 않으며 `order_num` 빈칸은 이미 현재 동작이다(FakeDb 더블로는 재정렬을 검증할 수도 없다). 계약 문서의 "삭제 후 영향받은 Day의 순서를 다시 매긴다" 문장은 넣지 않는다.

- [ ] **Step 4: 통과 확인** — 같은 명령, PASS. 기존 `test_delete_trip_place_removes_existing_place` 도 그대로 통과.

- [ ] **Step 5: 라우트 실패 테스트** — `test_trip_db_routes.py` L830 부근:

```python
def test_db_trip_place_batch_delete_route_returns_updated_trip(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    def delete_places(db, current_user, trip_id, place_ids, expected_revision):
        assert db is fake_db
        assert current_user is user
        assert trip_id == "7"
        assert place_ids == [3, 5]
        assert expected_revision == 4
        return trip_payload(trip_id)

    monkeypatch.setattr(trip_routes.trip_service, "delete_trip_places", delete_places)

    try:
        response = client.post(
            "/api/trips/7/places/batch-delete",
            json={"expectedRevision": 4, "placeIds": [3, 5]},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["id"] == "7"


def test_db_trip_place_batch_delete_route_rejects_empty_ids(monkeypatch) -> None:
    fake_db = object()
    install_db_route_dependencies(monkeypatch, fake_db, make_user())
    try:
        response = client.post(
            "/api/trips/7/places/batch-delete",
            json={"expectedRevision": 1, "placeIds": []},
        )
    finally:
        clear_overrides()
    assert response.status_code == 422
```

- [ ] **Step 6: 라우트**

`routes/trips.py` `delete_trip_place` 아래(import 에 `DeleteTripPlacesRequest` 추가):

```python
@router.post("/{trip_id}/places/batch-delete", response_model=Trip)
def delete_trip_places(
    trip_id: str,
    payload: DeleteTripPlacesRequest,
    db: Session | None = Depends(get_optional_db),
    current_user: User | None = Depends(get_current_user),
) -> Trip:
    try:
        trip = trip_service.delete_trip_places(
            _require_db(db),
            _require_user(current_user),
            trip_id,
            payload.placeIds,
            payload.expectedRevision,
        )
    except trip_service.TripServiceError as error:
        _raise_trip_error(error)
    return Trip(**trip)
```

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_trip_db_routes.py backend/tests/test_trip_db_service.py -q` → PASS.

- [ ] **Step 7: 계약 문서** — `docs/mvp-api-contract.md` L1171 섹션(`### DELETE /trips/{trip_id}/places/{place_id}`) 의 `---` 뒤에:

```markdown
### POST /trips/{trip_id}/places/batch-delete

여러 장소를 한 번에 삭제한다. owner/editor만 가능. 낙관적 리비전 검사 1회, 증가 1회. 하나라도 없는 id가 있으면 아무것도 삭제하지 않고 404.

**Request**
```json
{ "expectedRevision": 4, "placeIds": [3, 5] }
```

- `expectedRevision`: required, 현재 `Trip.revision`.
- `placeIds`: required, 1~50개. 중복은 한 번으로 취급.

**Response 200** → `Trip`

**Errors**
- 403: viewer는 삭제 불가
- 404: placeIds 중 하나라도 이 일정에 없음
- 409: revision 불일치
- 422: placeIds 비어 있음

---
```

`.agent/evals/api-contract-golden.json` `endpoints` 배열에서 기존 `"method": "DELETE", "path": "/api/trips/1/places/2?expectedRevision=1"` 항목 바로 뒤에 같은 키 구성으로 추가(`requiredFields`·`conflictBehavior`·`dbModeBehavior` 값은 그 항목을 그대로 복사, `request` 는 `{"expectedRevision": 1, "placeIds": [2, 3]}`, `path` 는 `/api/trips/1/places/batch-delete`, `method` `POST`). JSON 은 Edit 도구로 부분 삽입하고 `python -c "import json;json.load(open('.agent/evals/api-contract-golden.json',encoding='utf-8'))"` 로 검증. 골든 JSON 을 소비하는 테스트가 있으면(`grep -rn api-contract-golden backend/tests frontend/src`) 실행.

- [ ] **Step 8: 보고** — 테스트 결과, 계약 diff 요약.

---

### Task 2: 프런트 API 클라이언트

**Files:**
- Modify: `frontend/src/api/dataApi.ts` (L207 `TripPlacesBatchRequest` 아래 타입; L282 `deleteTripPlace` 아래 시그니처)
- Modify: `frontend/src/api/backendApi.ts` (L172 `deleteTripPlace` 아래)
- Test: `frontend/src/api/backendApi.test.ts` (L205 배치 테스트 뒤)

**Interfaces:**
- Produces: `TripPlacesDeleteRequest = { expectedRevision: number; placeIds: string[] }`; `appDataApi.deleteTripPlaces(tripId: string, request: TripPlacesDeleteRequest): Promise<Trip>`. 프런트 `ItineraryPlace.id` 는 string 이므로 전송 시 `Number(id)` 로 변환한다.

- [ ] **Step 1: 실패 테스트**

```ts
it("posts a batch delete with numeric place ids", async () => {
  const fetchSpy = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(tripResponse), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchSpy);

  await expect(
    backendApi.deleteTripPlaces("7", { expectedRevision: 4, placeIds: ["3", "5"] }),
  ).resolves.toMatchObject({ id: "7" });

  expect(fetchSpy).toHaveBeenCalledWith(
    `${apiConfig.baseUrl}/api/trips/7/places/batch-delete`,
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ expectedRevision: 4, placeIds: [3, 5] }),
    }),
  );
});
```

Run: `cd frontend && npx vitest run src/api/backendApi.test.ts -t "batch delete"` → FAIL (`deleteTripPlaces is not a function`).

- [ ] **Step 2: 구현**

`dataApi.ts`:
```ts
export type TripPlacesDeleteRequest = {
  expectedRevision: number;
  placeIds: string[];
};
// AppDataApi 인터페이스, deleteTripPlace 아래
deleteTripPlaces: (tripId: string, request: TripPlacesDeleteRequest) => Promise<Trip>;
```

`backendApi.ts` (`deleteTripPlace` 아래):
```ts
deleteTripPlaces: (tripId: string, request: TripPlacesDeleteRequest): Promise<Trip> =>
  apiClient.post<Trip>(`/api/trips/${tripId}/places/batch-delete`, {
    expectedRevision: request.expectedRevision,
    placeIds: request.placeIds.map(Number),
  }),
```

`dataApi.ts` 에 `backendApi` 외 다른 구현체(mock 등)가 `AppDataApi` 를 구현하면 `tsc` 가 알려준다 — 같은 시그니처로 추가.

- [ ] **Step 3: 통과 + 타입** — `npx vitest run src/api/backendApi.test.ts` PASS, `npx tsc --noEmit -p tsconfig.json` clean.

- [ ] **Step 4: 보고**

---

### Task 3: 편집 모드 UI — 토글, 전체 Day 적층, 체크박스, 하단 바

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx` — 상태(~L1798 부근), `trip-primary-actions` 섹션(L4056), Day 탭/타임라인 렌더(L4118-4245), 새 컴포넌트 `EditModeList`·`EditModeBar`(`SortablePlaceItem` 위)
- Modify: `frontend/src/styles/app.css` (`.recommendation-preview-action-bar` 블록 L11905 근처)
- Test: Create `frontend/src/app/__tests__/trip-edit-mode.test.tsx`

**Interfaces:**
- Produces: 상태 `isEditMode: boolean`, `selectedPlaceIds: Set<string>`; 버튼 접근성 이름 `편집`/`완료`; 적층 목록 `role="list"` `aria-label="전체 일정 편집 목록"`; 각 카드 체크박스 `aria-label={`${place.label} 선택`}`; 하단 바 `aria-label="편집 도구"` 안의 `N개 선택` 텍스트와 `삭제` 버튼(선택 0이면 disabled). Task 4 가 `삭제` 클릭 이후를 잇는다.
- Consumes: `dayNumbers`, `trip.days`, `formatDayDateLabel(trip.dates, day)`, `getPlaceEmoji`, `canEditTrip`, `isPreviewActive`.

- [ ] **Step 1: 실패 테스트** — 새 파일. 상단 import/`login`/`renderAppRoute`/`getPreviewTrip` 는 `place-edit.test.tsx` 의 것을 그대로 복사한다(같은 헬퍼 모듈에서 import).

```tsx
describe("Travel Hunter app — itinerary edit mode", () => {
  it("stacks every day with checkboxes and hides day tabs while editing", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "61",
      revision: 2,
      currentUserRole: "owner",
      days: {
        1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }],
        2: [{ id: "2", time: "12:00", label: "Cafe stop", meta: "Dessert" }],
        3: [],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/61?day=1");
      const user = userEvent.setup();

      await screen.findByText("Sunrise peak");
      expect(screen.queryByText("Cafe stop")).not.toBeInTheDocument(); // Day 1 만 보임

      await user.click(screen.getByRole("button", { name: "편집" }));

      const list = await screen.findByRole("list", { name: "전체 일정 편집 목록" });
      expect(within(list).getByText("Sunrise peak")).toBeInTheDocument();
      expect(within(list).getByText("Cafe stop")).toBeInTheDocument();
      expect(within(list).getAllByRole("heading", { level: 3 })).toHaveLength(3); // Day 1·2·3 헤더
      expect(screen.queryByLabelText("일정 날짜 선택")).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Sunrise peak 순서 이동" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Sunrise peak 상세 열기" })).not.toBeInTheDocument();

      const bar = screen.getByRole("region", { name: "편집 도구" });
      expect(within(bar).getByText("0개 선택")).toBeInTheDocument();
      expect(within(bar).getByRole("button", { name: "삭제" })).toBeDisabled();

      await user.click(screen.getByRole("checkbox", { name: "Sunrise peak 선택" }));
      await user.click(screen.getByRole("checkbox", { name: "Cafe stop 선택" }));
      expect(within(bar).getByText("2개 선택")).toBeInTheDocument();
      expect(within(bar).getByRole("button", { name: "삭제" })).toBeEnabled();

      expect(screen.queryByRole("button", { name: "편집" })).not.toBeInTheDocument(); // 진입 버튼은 편집 중 숨김
      await user.click(within(bar).getByRole("button", { name: "완료" }));
      expect(screen.queryByRole("list", { name: "전체 일정 편집 목록" })).not.toBeInTheDocument();
      expect(screen.getByLabelText("일정 날짜 선택")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "편집" })).toBeInTheDocument();
      expect(screen.getByText("Sunrise peak")).toBeInTheDocument(); // activeDay 복원
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("does not offer edit mode to viewers", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "62",
      currentUserRole: "viewer",
      days: { 1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/62");
      await screen.findByText("Sunrise peak");
      expect(screen.queryByRole("button", { name: "편집" })).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });
});
```

Run: `cd frontend && npx vitest run src/app/__tests__/trip-edit-mode.test.tsx` → FAIL (`편집` 버튼 없음).

- [ ] **Step 2: 상태 + 토글**

상태(`deleteCandidatePlace` 선언 근처):
```tsx
const [isEditMode, setIsEditMode] = useState(false);
const [selectedPlaceIds, setSelectedPlaceIds] = useState<Set<string>>(() => new Set());
const enterEditMode = () => {
  if (!canEditTrip || isPreviewActive || isSavingPlace || movingPlaceId) return;
  closePlaceEditor(); // 맨 setPlaceEditor(null) 은 moveError·대기 플래시 정리를 건너뛴다
  setSelectedPlaceIds(new Set());
  setIsEditMode(true);
};
const exitEditMode = () => {
  setIsEditMode(false);
  setSelectedPlaceIds(new Set());
};
const togglePlaceSelection = (placeId: string) =>
  setSelectedPlaceIds((current) => {
    const next = new Set(current);
    if (next.has(placeId)) next.delete(placeId);
    else next.add(placeId);
    return next;
  });
```

`trip` 이 바뀌어(삭제·새로고침) 사라진 id 가 선택에 남지 않도록:
```tsx
useEffect(() => {
  if (!trip) return;
  const live = new Set(Object.values(trip.days).flat().map((place) => place.id).filter(Boolean) as string[]);
  setSelectedPlaceIds((current) => {
    const next = new Set([...current].filter((id) => live.has(id)));
    return next.size === current.size ? current : next;
  });
}, [trip]);
```

`trip-primary-actions` 섹션(L4056) 안, `+ 장소 추가` 버튼 앞에 편집 진입 버튼(편집 가능 + 미리보기 아님 + 편집 모드 아님일 때만 — 편집 모드에서는 이 섹션 전체를 숨기고 종료는 하단 바의 `완료` 하나만 둔다. 같은 이름의 버튼이 둘이면 접근성 이름이 겹친다):
```tsx
{!isEditMode && (
  <section className="trip-primary-actions" aria-label="일정 편집 작업" data-itinerary-actions>
    {canEditTrip && !isPreviewActive && (
      <button
        className="prototype-trip-action-button prototype-trip-action-edit"
        type="button"
        onClick={enterEditMode}
      >
        편집
      </button>
    )}
    {/* 기존 + 장소 추가 / 추천 일정만들기 그대로 */}
  </section>
)}
```
`.trip-primary-actions` 는 2열 grid 라 버튼이 3개가 되면 한 줄이 깨진다 — 편집 버튼에 `grid-column: 1 / -1` (기존 `.prototype-trip-action-date` 규칙과 같은 방식) 을 준다.

- [ ] **Step 3: 적층 목록 컴포넌트** — `SortablePlaceItem` 위에:

```tsx
function EditModeList({
  dayNumbers,
  onToggle,
  selectedPlaceIds,
  trip,
}: {
  dayNumbers: number[];
  onToggle: (placeId: string) => void;
  selectedPlaceIds: Set<string>;
  trip: Trip;
}) {
  return (
    <div className="edit-mode-list" role="list" aria-label="전체 일정 편집 목록">
      {dayNumbers.map((day) => {
        const places = trip.days[day] ?? [];
        return (
          <section className="edit-mode-day" key={day} role="listitem">
            <h3>
              Day {day} <em>{formatDayDateLabel(trip.dates, day)}</em>
              <span>{places.length > 0 ? `${places.length}곳` : "비어 있음"}</span>
            </h3>
            {places.map((place) => {
              const checked = Boolean(place.id) && selectedPlaceIds.has(place.id!);
              return (
                /* <label> 은 phrasing content 만 허용해 h4/div 를 감쌀 수 없다.
                   행 전체 클릭은 div 가, 접근성 이름은 체크박스가 맡는다. */
                <div
                  className={checked ? "place-detail edit-mode-place selected" : "place-detail edit-mode-place"}
                  key={place.id ?? `${place.time}-${place.label}`}
                  onClick={() => place.id && onToggle(place.id)}
                >
                  <input
                    aria-label={`${place.label} 선택`}
                    checked={checked}
                    disabled={!place.id}
                    onChange={() => place.id && onToggle(place.id)}
                    onClick={(event) => event.stopPropagation()}
                    type="checkbox"
                  />
                  <div className="place-copy">
                    <div className="place-prototype-meta">
                      {place.time && <span>{place.time}</span>}
                      <em aria-hidden="true">{getPlaceEmoji(place)}</em>
                    </div>
                    <h4>{place.label}</h4>
                    <div className="meta">{place.meta}</div>
                  </div>
                </div>
              );
            })}
          </section>
        );
      })}
    </div>
  );
}

function EditModeBar({
  isDeleting,
  onDelete,
  onDone,
  selectedCount,
}: {
  isDeleting: boolean;
  onDelete: () => void;
  onDone: () => void;
  selectedCount: number;
}) {
  return (
    <aside className="edit-mode-bar" aria-label="편집 도구" role="region">
      <span className="edit-mode-count">{selectedCount}개 선택</span>
      <Button variant="danger" disabled={selectedCount === 0 || isDeleting} onClick={onDelete}>
        {isDeleting ? "삭제 중" : "삭제"}
      </Button>
      <Button disabled={isDeleting} onClick={onDone}>
        완료
      </Button>
    </aside>
  );
}
```

`Button`(`frontend/src/components/ui.tsx`, `variant: "primary" | … | "danger"`) 은 이 페이지에 이미 import 되어 있다(`PlaceEditorSheet` 의 `<Button full …>`).

- [ ] **Step 4: 렌더 분기** — Day 탭 `<div className="day-tabs" …>`(L4118) 부터 `<DragOverlay>` 끝(L4259 부근)까지를 `isEditMode` 로 감싼다. 편집 모드에서는 대신 `EditModeList` 를 렌더한다. 가장 작은 변경:

```tsx
{isEditMode && trip ? (
  <EditModeList
    dayNumbers={dayNumbers}
    onToggle={togglePlaceSelection}
    selectedPlaceIds={selectedPlaceIds}
    trip={trip}
  />
) : (
  <>
    {/* 기존 day-tabs … DragOverlay 블록 그대로 */}
  </>
)}
```

`DndContext` 는 바깥에 그대로 둔다(편집 모드에서는 `SortableContext` 가 렌더되지 않으니 드래그 대상이 없다). 하단 바는 `recommendation-preview-action-bar` 가 렌더되는 자리(L4261 `isPreviewActive && <aside …>`) 옆에:
```tsx
{isEditMode && (
  <EditModeBar
    isDeleting={isDeletingSelected}
    onDelete={requestDeleteSelected}
    onDone={exitEditMode}
    selectedCount={selectedPlaceIds.size}
  />
)}
```
Task 4 전까지는 `const isDeletingSelected = false; const requestDeleteSelected = () => {};` 로 둔다 (Task 4 가 교체).

`+ 장소 추가` 의 `openAddPlace` 와 지도의 `onShowPlaceDetail` 은 편집 모드에서 호출되지 않도록 각각 `if (isEditMode) return;` 을 첫 줄에 둔다.

- [ ] **Step 5: CSS** — `.recommendation-preview-action-bar` 블록(L11905) 뒤:

```css
.edit-mode-list {
  display: grid;
  gap: 14px;
  padding: 0 16px 96px; /* 하단 바가 마지막 카드를 가리지 않게 */
}

.edit-mode-day h3 {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 0 0 8px;
  font-size: 15px;
}

.edit-mode-day h3 em {
  font-style: normal;
  color: var(--gray-500);
  font-size: 12px;
}

.edit-mode-day h3 span {
  margin-left: auto;
  color: var(--gray-500);
  font-size: 12px;
}

.edit-mode-place {
  cursor: pointer;
  margin-bottom: 8px;
}

.edit-mode-place input[type="checkbox"] {
  width: 20px;
  height: 20px;
  margin-top: 2px;
  flex: 0 0 auto;
}

.edit-mode-place.selected {
  border-color: var(--primary-500);
  background: var(--primary-50);
}

.edit-mode-bar {
  position: fixed;
  left: 50%;
  bottom: calc(72px + env(safe-area-inset-bottom));
  z-index: 88;
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 8px;
  box-sizing: border-box;
  width: min(100vw - 24px, 560px);
  padding: 10px 12px;
  transform: translateX(-50%);
  border-radius: var(--radius-lg);
  background: #fff;
  border: 1px solid var(--gray-200);
  box-shadow: var(--shadow-md, 0 8px 24px rgba(0, 0, 0, 0.12));
}

.edit-mode-count {
  font-size: 14px;
  font-weight: 600;
}

@media (min-width: 768px) {
  .edit-mode-bar {
    bottom: 0;
    width: min(100vw, 760px);
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  }
}
```

브레이크포인트는 **768px** — `.recommendation-preview-action-bar` 의 `bottom: 0` 규칙이 `app.css:11957 @media (min-width: 768px)` 안에 있고 탭바도 768px 에서 사라진다.

토큰 이름(`--primary-500`, `--gray-500`, `--shadow-md`)은 확정이 아니다 — `frontend/src/styles/tokens.css` 와 `app.css` 상단 `:root` 에서 실제 이름을 찾아 바꾼다(`.place-detail` 이 쓰는 `var(--gray-200)`, `.place-sheet-detail` 근처의 `var(--primary-50)` 은 존재 확인됨). 없는 토큰은 인접 규칙이 쓰는 리터럴로 대체한다. `.recommendation-preview-action-bar` 의 `min-width:760px` 미디어 블록과 같은 구조여야 한다(탭바가 없는 데스크톱에서 바닥에 붙는다).

- [ ] **Step 6: 통과 + 회귀**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-edit-mode.test.tsx src/app/__tests__/place-edit.test.tsx src/app/__tests__/trip-detail.test.tsx src/app/__tests__/trips-list.test.tsx` → PASS. `npx tsc --noEmit -p tsconfig.json` clean.

- [ ] **Step 7: 보고**

---

### Task 4: 선택 삭제 흐름 (확인 → 배치 API → 409 처리)

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx` — Task 3 의 스텁 교체, `ConfirmDialog`(L4397) 옆에 두 번째 `ConfirmDialog`
- Test: `frontend/src/app/__tests__/trip-edit-mode.test.tsx`

**Interfaces:**
- Consumes: Task 2 `appDataApi.deleteTripPlaces`, Task 3 상태, 기존 `refreshTripAfterConflict(setError)`, `isTripConflict`, `ConfirmDialog`.
- Produces: 확인 다이얼로그 제목 `선택한 장소 N개를 삭제할까요?`, 성공 토스트 `장소 N개를 일정에서 삭제했어요.`.

- [ ] **Step 1: 실패 테스트** — 파일에 추가:

```tsx
it("deletes the selected places with one batch call and stays in edit mode", async () => {
  const trip: Trip = {
    ...getPreviewTrip(),
    id: "63",
    revision: 5,
    currentUserRole: "owner",
    days: {
      1: [
        { id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" },
        { id: "2", time: "11:00", label: "Market", meta: "Food" },
      ],
      2: [{ id: "3", time: "12:00", label: "Cafe stop", meta: "Dessert" }],
    },
  };
  const afterDelete: Trip = {
    ...trip,
    revision: 6,
    days: { 1: [trip.days[1][1]], 2: [] },
  };
  const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
  const deleteSpy = vi.spyOn(appDataApi, "deleteTripPlaces").mockResolvedValue(afterDelete);
  const singleDeleteSpy = vi.spyOn(appDataApi, "deleteTripPlace").mockResolvedValue(trip);
  try {
    await login();
    cleanup();
    renderAppRoute("/trips/63?day=1");
    const user = userEvent.setup();
    await screen.findByText("Sunrise peak");
    await user.click(screen.getByRole("button", { name: "편집" }));
    await user.click(await screen.findByRole("checkbox", { name: "Sunrise peak 선택" }));
    await user.click(screen.getByRole("checkbox", { name: "Cafe stop 선택" }));

    const bar = screen.getByRole("region", { name: "편집 도구" });
    await user.click(within(bar).getByRole("button", { name: "삭제" }));
    const confirm = await screen.findByRole("dialog", { name: "선택한 장소 2개를 삭제할까요?" });
    await user.click(within(confirm).getByRole("button", { name: "삭제" }));

    await waitFor(() =>
      expect(deleteSpy).toHaveBeenCalledWith("63", { expectedRevision: 5, placeIds: ["1", "3"] }),
    );
    expect(deleteSpy).toHaveBeenCalledTimes(1);
    expect(singleDeleteSpy).not.toHaveBeenCalled();

    const list = await screen.findByRole("list", { name: "전체 일정 편집 목록" });
    await waitFor(() => expect(within(list).queryByText("Sunrise peak")).not.toBeInTheDocument());
    expect(within(list).queryByText("Cafe stop")).not.toBeInTheDocument();
    expect(within(list).getByText("Market")).toBeInTheDocument();
    expect(within(bar).getByText("0개 선택")).toBeInTheDocument();
    expect(screen.getByText("장소 2개를 일정에서 삭제했어요.")).toBeInTheDocument();
  } finally {
    getTripSpy.mockRestore();
    deleteSpy.mockRestore();
    singleDeleteSpy.mockRestore();
  }
});

it("refreshes the trip and keeps the selection when the batch delete conflicts", async () => {
  const trip: Trip = {
    ...getPreviewTrip(),
    id: "64",
    revision: 1,
    currentUserRole: "owner",
    days: { 1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }] },
  };
  const latest: Trip = { ...trip, revision: 2 };
  const getTripSpy = vi
    .spyOn(appDataApi, "getTrip")
    .mockResolvedValueOnce(trip)
    .mockResolvedValue(latest);
  const deleteSpy = vi
    .spyOn(appDataApi, "deleteTripPlaces")
    .mockRejectedValueOnce(new ApiError("conflict", { status: 409, statusText: "Conflict" }));
  try {
    await login();
    cleanup();
    renderAppRoute("/trips/64?day=1");
    const user = userEvent.setup();
    await screen.findByText("Sunrise peak");
    await user.click(screen.getByRole("button", { name: "편집" }));
    await user.click(await screen.findByRole("checkbox", { name: "Sunrise peak 선택" }));
    await user.click(within(screen.getByRole("region", { name: "편집 도구" })).getByRole("button", { name: "삭제" }));
    const confirm = await screen.findByRole("dialog", { name: "선택한 장소 1개를 삭제할까요?" });
    await user.click(within(confirm).getByRole("button", { name: "삭제" }));

    expect(await within(confirm).findByText(/다른 사용자가 먼저 일정을 수정/)).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Sunrise peak 선택" })).toBeChecked();
    expect(screen.getByRole("dialog", { name: "선택한 장소 1개를 삭제할까요?" })).toBeInTheDocument(); // 다이얼로그 유지, 재시도 가능
  } finally {
    getTripSpy.mockRestore();
    deleteSpy.mockRestore();
  }
});
```

`ApiError` import 경로와 생성자 시그니처는 `trip-detail.test.tsx` 의 409 테스트(`new ApiError("conflict", { status: 409, statusText: "Conflict" })`)에서 그대로 가져온다. 충돌 메시지 문구는 `refreshTripAfterConflict` 가 setter 에 넣는 문자열(`ItineraryDetailPage.tsx:2190-2198` 부근)로 확인해 정규식을 맞춘다.

Run: `npx vitest run src/app/__tests__/trip-edit-mode.test.tsx -t "batch"` → FAIL.

- [ ] **Step 2: 구현** — Task 3 의 스텁을 교체:

```tsx
const [isSelectedDeleteOpen, setIsSelectedDeleteOpen] = useState(false);
const [isDeletingSelected, setIsDeletingSelected] = useState(false);
const [selectedDeleteError, setSelectedDeleteError] = useState("");

const requestDeleteSelected = () => {
  if (selectedPlaceIds.size === 0 || isDeletingSelected) return;
  setSelectedDeleteError("");
  setIsSelectedDeleteOpen(true);
};

const confirmDeleteSelected = async () => {
  if (!trip || selectedPlaceIds.size === 0 || isDeletingSelected) return;
  // 화면 순서(Day → 순번)대로 보내 서버 로그와 사용자 인식이 같게 한다.
  const placeIds = Object.values(trip.days)
    .flat()
    .map((place) => place.id)
    .filter((id): id is string => Boolean(id) && selectedPlaceIds.has(id!));
  setIsDeletingSelected(true);
  setSelectedDeleteError("");
  try {
    const nextTrip = await appDataApi.deleteTripPlaces(trip.id, {
      expectedRevision: trip.revision,
      placeIds,
    });
    placeIds.forEach((id) => clearDraft(tripPlaceEditDraftKey(trip.id, id)));
    setTrip(nextTrip);
    setSelectedPlaceIds(new Set());
    setIsSelectedDeleteOpen(false);
    setNotice(`장소 ${placeIds.length}개를 일정에서 삭제했어요.`);
    window.setTimeout(() => setNotice(null), 1800);
  } catch (error) {
    if (isTripConflict(error)) {
      await refreshTripAfterConflict(setSelectedDeleteError);
    } else {
      setSelectedDeleteError("장소를 삭제하지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  } finally {
    setIsDeletingSelected(false);
  }
};
```

`refreshTripAfterConflict` 가 `setTrip` 을 하면 Task 3 의 정리 effect 가 사라진 id 만 선택에서 뺀다 — 남아 있는 카드의 선택은 유지된다(두 번째 테스트).

`ConfirmDialog`(L4397) 아래에:
```tsx
<ConfirmDialog
  open={isSelectedDeleteOpen}
  title={`선택한 장소 ${selectedPlaceIds.size}개를 삭제할까요?`}
  body="선택한 장소가 이 일정에서 한 번에 삭제됩니다."
  error={selectedDeleteError}
  confirmLabel="삭제"
  isSubmitting={isDeletingSelected}
  onCancel={() => !isDeletingSelected && setIsSelectedDeleteOpen(false)}
  onConfirm={() => void confirmDeleteSelected()}
/>
```

`exitEditMode` 에 `setIsSelectedDeleteOpen(false); setSelectedDeleteError("");` 추가.

- [ ] **Step 3: 통과 + 회귀** — `npx vitest run src/app/__tests__/trip-edit-mode.test.tsx src/app/__tests__/place-edit.test.tsx src/app/__tests__/trip-detail.test.tsx` PASS, `tsc` clean.

- [ ] **Step 4: 보고**

---

### Task 5: 전체 게이트 + 수동 확인 + 인계

**Files:**
- Create: `docs/2026-09-16-codex-handoff-itinerary-edit-mode.md`

- [ ] **Step 1: 게이트** — `cd backend && C:/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest tests -q -x` (sqlite 만), `cd frontend && npx vitest run && npm run test:mojibake && npx tsc --noEmit -p tsconfig.json`. 골든 JSON 소비 테스트가 있으면 포함.
- [ ] **Step 2: 줄끝** — `git diff --stat` == `git diff --ignore-space-at-eol --stat`.
- [ ] **Step 3: 수동 확인 목록(5176)**:
  1. 390px: `편집` → Day 탭 사라지고 Day 1·2·3 세로 적층, 하단 바가 탭바 위에 뜸, 마지막 카드가 바에 가려지지 않음.
  2. 데스크톱(≥760px): 하단 바가 바닥에 붙음(탭바 없음).
  3. 체크 2개 → `2개 선택` → 삭제 → 확인 → 네트워크에 `batch-delete` 1회, 카드 2장 사라짐, 편집 모드 유지.
  4. `완료` → 원래 Day 탭·타임라인 복귀, 이전 Day 유지.
  5. 편집 모드에서 카드 탭·드래그·`+ 장소 추가`·지도 상세 안 됨.
  6. 보기 권한: `편집` 버튼 없음.
  7. 추천 미리보기 중: `편집` 버튼 없음.
- [ ] **Step 4: 인계서** — 브랜치·base(①)·엔드포인트 결정 이유·테스트 결과·수동 확인·e2e 미실행·Codex 할 일(① 머지 후 ② PR).
- [ ] **Step 5: 승인 요청** — 커밋은 사용자 승인 뒤.

---

## Self-review

- 스펙 ② 대조: 배치 API(T1) ✔ — 경로만 POST 로 변경(Global Constraints 에 이유 기록); 계약·골든(T1) ✔; 백엔드 테스트 3종(T1) ✔ — "여러 Day 에 걸친 삭제" 는 첫 테스트가 Day 1 만 다루므로 T1 Step 1 의 Day 2 장소 추가 안내로 보강; `편집` 토글·전체 Day 적층·체크박스·카드 탭/드래그 비활성(T3) ✔; 하단 바 `N개 선택`/`삭제`/`완료`(T3) ✔; 확인 1회 → API 1회 → `setTrip`(T4) ✔; 409 → `refreshTripAfterConflict`(T4) ✔; 일반 모드 복귀 시 `activeDay` 복원 — `activeDay` 를 건드리지 않으므로 자동(T3 테스트가 검증) ✔.
- 타입 일치: `TripPlacesDeleteRequest.placeIds: string[]`(T2) ↔ T4 가 string 배열 전달 ✔; `deleteTripPlaces(tripId, request)` 시그니처 T2/T4 동일 ✔; `EditModeBar` props `isDeleting/onDelete/onDone/selectedCount` T3 정의 = T4 사용 ✔; 서비스 `delete_trip_places(db, user, trip_handle, place_ids, expected_revision)` T1 서비스 = T1 라우트 호출 순서 ✔.
- 미확인: `make_trip()` 더블에서 `place.trip_day` 역참조가 채워져 있는지(T1 Step 3 에 대안 명시); `Button variant="danger"` 클래스명(T3 Step 3 에 확인 지시); 토큰 이름(T3 Step 5).
