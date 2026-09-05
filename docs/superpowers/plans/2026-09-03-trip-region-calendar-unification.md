# 일정 지역·기간 선택 통합 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 모든 광역시도의 행정 세부지역을 빠짐없이 선택하게 하고, 기존 일정의 세부지역 변경과 생성·편집 공통 달력 선택을 지원한다.

**Architecture:** 행정지역 정적 스냅샷과 기존 추천 여행권역을 `travel_area_catalog` 서비스에서 하나의 선택 카탈로그로 합성한다. 새 조회 API와 일정 생성·수정은 동일 resolver를 사용하며, 프론트는 `AppDataApi` 뒤의 공통 지역 선택기와 controlled 날짜 범위 선택기를 생성·직접 편집·상세 기간 편집에 재사용한다.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy/PostgreSQL, React, TypeScript, React Router, Pytest, Vitest/Testing Library

**Spec:** `docs/superpowers/specs/2026-09-03-trip-region-calendar-unification-design.md`

## Global Constraints

- 지역 기준은 17개 광역시도 아래 시·군 또는 자치구·군이다. 제주에는 제주시·서귀포시를 제공하고 세종은 `세종 전체`만 제공한다.
- 일반시의 비자치구는 별도 선택지로 만들지 않는다.
- 모든 광역시도에 명시적인 `전체` 선택지를 정확히 하나 제공한다.
- 기존 `TRAVEL_AREAS`는 추천 여행권역으로 유지하고 행정지역과 별도 그룹으로 표시한다.
- `travelAreaId`는 opaque string이다. `whole:`, `admin:`, 기존 curated ID, `policy-region:` ID를 모두 해석한다.
- 지역 변경은 제목, 기존 장소, Day, 연결 정책을 자동 변경하지 않는다.
- 생성·직접 편집·상세 기간 편집은 같은 달력과 정방향/역방향 정규화 규칙을 사용한다.
- DTO는 `camelCase`, DB 필드는 `snake_case`, 프론트 데이터 접근은 `AppDataApi` 경계 뒤에 둔다.
- DB 컬럼은 이미 있으므로 Alembic migration과 새 dependency를 추가하지 않는다.
- 현재 수정 중인 생성/상세 페이지, 테스트, CSS의 사용자 변경은 실행 직전에 diff를 읽고 보존한다.
- 사용자 지시에 따라 중간 커밋은 금지한다. 전체 자동 테스트·build·5173 수동 검증 후 최종 커밋 한 번만 만든다.

## File Structure

### Backend

- Create `backend/app/data/administrative_areas.py`: 행정지역 snapshot과 기준일.
- Create `backend/app/services/travel_area_catalog.py`: catalog 합성과 단일 resolver.
- Create `backend/app/schemas/travel_areas.py`: 선택 catalog 응답 DTO.
- Create `backend/app/api/routes/travel_areas.py`: 얇은 `GET /api/travel-areas` route.
- Modify `backend/app/api/router.py`: 새 router 등록.
- Modify `backend/app/schemas/trip.py`: Trip `region`, settings `travelAreaId`.
- Modify `backend/app/services/trips.py`: DTO mapping과 region/travel-area 동시 갱신.
- Modify `backend/app/services/itinerary_recommendations.py`: 단일 resolver 사용.
- Test `backend/tests/test_travel_area_catalog.py`, `test_travel_area_catalog_routes.py`, `test_trip_db_routes.py`, `test_itinerary_recommendations.py`.

### Frontend

- Create `frontend/src/components/trip/TripRegionSelector.tsx`: 17개 광역시도와 3개 세부지역 그룹.
- Create `frontend/src/components/trip/TripDateRangePicker.tsx`: controlled 날짜 범위 dialog.
- Create `frontend/src/utils/tripDateRange.ts`: 날짜 parse/format/day-count/month-grid/range 정규화.
- Modify `frontend/src/api/types.ts`, `dataApi.ts`, `backendApi.ts`: catalog와 settings 계약.
- Modify `ItineraryCreatePage.tsx`, `ItineraryEditPage.tsx`, `ItineraryDetailPage.tsx`: 공통 component 통합.
- Modify 관련 component/API/page tests와 `frontend/src/styles/app.css`.

### Contract and evidence

- Modify `docs/mvp-api-contract.md`, `docs/requirements.md`, `docs/implemented-feature-spec.md`, `.agent/evals/api-contract-golden.json`.
- Modify `CHECKLIST.md` only after implementation to retain current status, recent evidence, and active risks.

---

### Task 1: 행정지역 snapshot과 통합 resolver

**Files:**
- Create: `backend/app/data/administrative_areas.py`
- Create: `backend/app/services/travel_area_catalog.py`
- Modify: `backend/app/data/travel_areas.py`
- Test: `backend/tests/test_travel_area_catalog.py`
- Test: `backend/tests/test_travel_areas.py`

**Interfaces:**
- Consumes: 기존 `TravelArea`, `TRAVEL_AREAS`, `get_travel_area()`, `policy-region:` 규칙.
- Produces: `TravelAreaOption`, `TravelAreaCatalog`, `list_travel_area_catalog(sido)`, `resolve_travel_area(area_id)`.

- [x] **Step 1: 공유 파일의 현재 diff를 읽는다**

Run:

```powershell
git diff -- backend/app/data/travel_areas.py backend/app/services/trips.py backend/app/services/itinerary_recommendations.py backend/tests/test_travel_areas.py
```

Expected: 사용자 변경이 있으면 범위를 식별하고 이후 patch에서 그대로 보존한다.

- [x] **Step 2: catalog 불변조건에 대한 실패 test를 작성한다**

`backend/tests/test_travel_area_catalog.py`에 다음 핵심 계약을 작성한다.

```python
EXPECTED_SIDOS = (
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
)

def test_catalog_covers_all_sidos_with_one_whole_area():
    assert list_supported_sidos() == EXPECTED_SIDOS
    for sido in EXPECTED_SIDOS:
        catalog = list_travel_area_catalog(sido)
        assert catalog.whole_area.area_type == "whole"
        assert catalog.whole_area.sido == sido

def test_catalog_exposes_previously_missing_localities():
    assert {item.name for item in list_travel_area_catalog("경기").administrative_areas} >= {"수원시", "용인시", "연천군"}
    assert {item.name for item in list_travel_area_catalog("강원").administrative_areas} >= {"춘천시", "태백시", "양구군"}
    assert {item.name for item in list_travel_area_catalog("전남").administrative_areas} >= {"목포시", "강진군", "신안군"}

def test_jeju_separates_curated_and_administrative_areas():
    catalog = list_travel_area_catalog("제주")
    assert {item.id for item in catalog.recommended_areas} >= {"jeju-east", "jeju-west"}
    assert [item.name for item in catalog.administrative_areas] == ["제주시", "서귀포시"]

@pytest.mark.parametrize("area_id,name", [
    ("whole:%EC%A0%9C%EC%A3%BC", "제주 전체"),
    ("admin:%EC%A0%9C%EC%A3%BC:%EC%84%9C%EA%B7%80%ED%8F%AC%EC%8B%9C", "서귀포시"),
    ("jeju-west", "제주 서부"),
    ("policy-region:%EC%A0%84%EB%82%A8:%EA%B0%95%EC%A7%84", "강진"),
])
def test_resolver_supports_every_id_family(area_id, name):
    assert resolve_travel_area(area_id).name == name
```

모든 option ID의 중복이 없고 세종의 행정지역 배열이 비어 있는 test도 추가한다.

- [x] **Step 3: test가 기능 부재로 실패하는지 확인한다**

Run: `cd backend; python -m pytest tests/test_travel_area_catalog.py tests/test_travel_areas.py -q`

Expected: FAIL because `travel_area_catalog` and administrative snapshot do not exist.

- [x] **Step 4: UTF-8 snapshot을 구현한다**

`administrative_areas.py`의 공개 형태를 다음과 같이 고정한다.

```python
ADMINISTRATIVE_AREAS_SOURCE_AS_OF = "2026-09-03"

ADMINISTRATIVE_AREAS_BY_SIDO: dict[str, tuple[str, ...]] = {
    # 행정안전부 행정표준코드관리시스템의 시·군·자치구를 가나다순으로 기록한다.
}
```

수량 검증 기준은 서울 25, 부산 16, 대구 9, 인천 10, 광주 5, 대전 5, 울산 5, 세종 0, 경기 31, 강원 18, 충북 11, 충남 15, 전북 14, 전남 22, 경북 22, 경남 18, 제주 2이다. 제주 행정시를 제품 선택 단위로 포함하고 일반시의 구는 제외한다.

- [x] **Step 5: catalog와 resolver를 최소 구현한다**

```python
AreaType = Literal["whole", "recommended", "administrative", "policy"]

@dataclass(frozen=True)
class TravelAreaOption:
    id: str
    name: str
    sido: str
    area_type: AreaType
    included_cities: tuple[str, ...]

@dataclass(frozen=True)
class TravelAreaCatalog:
    sido: str
    source_as_of: str
    whole_area: TravelAreaOption
    recommended_areas: tuple[TravelAreaOption, ...]
    administrative_areas: tuple[TravelAreaOption, ...]

def make_whole_area_id(sido: str) -> str:
    return f"whole:{quote(sido.strip(), safe='')}"

def make_administrative_area_id(sido: str, locality: str) -> str:
    return f"admin:{quote(sido.strip(), safe='')}:{quote(locality.strip(), safe='')}"
```

`list_supported_sidos() -> tuple[str, ...]`는 snapshot key를 제품의 17개 고정 순서로 반환한다. `list_travel_area_catalog(sido: str) -> TravelAreaCatalog`는 지원 여부를 검사한 뒤 whole option 하나, 같은 sido의 기존 curated option, snapshot의 행정 option을 합성한다. `resolve_travel_area(area_id: str | None) -> TravelArea | None`는 새 ID를 decode한 뒤 snapshot membership을 확인하고, curated와 `policy-region:`은 기존 `get_travel_area()`에 위임한다. 기존 recommendation ranking은 `TRAVEL_AREAS`만 사용하므로 결과 순위를 바꾸지 않는다.

- [x] **Step 6: targeted backend test를 통과시킨다**

Run: `cd backend; python -m pytest tests/test_travel_area_catalog.py tests/test_travel_areas.py -q`

Expected: PASS; 기존 curated ID와 정책 동적 ID test도 유지된다.

---

### Task 2: 전체 선택 catalog API

**Files:**
- Create: `backend/app/schemas/travel_areas.py`
- Create: `backend/app/api/routes/travel_areas.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_travel_area_catalog_routes.py`

**Interfaces:**
- Consumes: Task 1의 `list_travel_area_catalog(sido)`.
- Produces: `GET /api/travel-areas?sido=<광역시도>`.

- [x] **Step 1: 정상·오류 route test를 작성한다**

```python
def test_lists_grouped_jeju_catalog(client):
    response = client.get("/api/travel-areas?sido=제주")
    assert response.status_code == 200
    payload = response.json()
    assert payload["wholeArea"]["areaType"] == "whole"
    assert {item["travelAreaId"] for item in payload["recommendedAreas"]} >= {"jeju-east", "jeju-west"}
    assert [item["travelAreaName"] for item in payload["administrativeAreas"]] == ["제주시", "서귀포시"]

def test_rejects_unsupported_sido(client):
    response = client.get("/api/travel-areas?sido=없는지역")
    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported travel area sido"
```

`sido` 누락 422도 별도 test로 고정한다.

- [x] **Step 2: 404 실패를 확인한다**

Run: `cd backend; python -m pytest tests/test_travel_area_catalog_routes.py -q`

Expected: FAIL with 404.

- [x] **Step 3: camelCase DTO와 얇은 route를 구현한다**

```python
class TravelAreaOptionResponse(BaseModel):
    travelAreaId: str
    travelAreaName: str
    sido: str
    areaType: Literal["whole", "recommended", "administrative"]
    includedCities: list[str]

class TravelAreaCatalogResponse(BaseModel):
    sido: str
    sourceAsOf: str
    wholeArea: TravelAreaOptionResponse
    recommendedAreas: list[TravelAreaOptionResponse]
    administrativeAreas: list[TravelAreaOptionResponse]
```

route는 service 반환값을 DTO로 바꾸고 `ValueError`만 400으로 변환한다. `api/router.py`에 새 router를 한 번 등록한다.

- [x] **Step 4: route test를 통과시킨다**

Run: `cd backend; python -m pytest tests/test_travel_area_catalog_routes.py -q`

Expected: PASS with grouped response and exact 400/422 behavior.

---

### Task 3: Trip region 응답과 지역 수정

**Files:**
- Modify: `backend/app/schemas/trip.py`
- Modify: `backend/app/services/trips.py`
- Modify: `backend/app/services/itinerary_recommendations.py`
- Test: `backend/tests/test_trip_db_routes.py`
- Test: `backend/tests/test_itinerary_recommendations.py`

**Interfaces:**
- Consumes: Task 1의 `resolve_travel_area()`.
- Produces: `Trip.region`, `UpdateTripSettingsRequest.travelAreaId`, 원자적 region/ID 갱신.

- [x] **Step 1: 실제 DB route 실패 test를 작성한다**

```python
def test_updates_region_without_replacing_trip_content(client, auth_headers, seeded_trip):
    before = client.get(f"/api/trips/{seeded_trip.id}", headers=auth_headers).json()
    response = client.patch(
        f"/api/trips/{seeded_trip.id}/settings",
        headers=auth_headers,
        json={"expectedRevision": before["revision"], "travelAreaId": "jeju-west"},
    )
    assert response.status_code == 200
    after = response.json()
    assert after["travelAreaId"] == "jeju-west"
    assert after["region"] == "제주 서부"
    assert after["title"] == before["title"]
    assert after["days"] == before["days"]
    assert after["linkedPolicies"] == before["linkedPolicies"]

def test_rejects_unknown_area_without_mutation(client, auth_headers, seeded_trip):
    response = client.patch(
        f"/api/trips/{seeded_trip.id}/settings",
        headers=auth_headers,
        json={"expectedRevision": seeded_trip.revision, "travelAreaId": "missing"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Travel area not found"
```

whole/admin/curated/policy ID 생성·수정 parametrized test와 viewer 403, stale revision 409 회귀 test를 추가한다.

- [x] **Step 2: 새 필드 부재로 실패하는지 확인한다**

Run: `cd backend; python -m pytest tests/test_trip_db_routes.py -k "travel_area or region" -q`

Expected: FAIL because settings ignores `travelAreaId` and response omits `region`.

- [x] **Step 3: schema와 response mapping을 구현한다**

```python
class Trip(BaseModel):
    # existing fields remain
    travelAreaId: str | None = None
    region: str

class UpdateTripSettingsRequest(BaseModel):
    expectedRevision: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=100)
    travelAreaId: str | None = Field(default=None, max_length=120)
    startDate: date | None = None
    endDate: date | None = None
    overflowPlaceStrategy: TripDateOverflowStrategy = "moveToLastDay"
```

`trip_to_api()`에 `"region": trip.region`을 추가한다.

- [x] **Step 4: resolver 검증과 DB 동시 갱신을 구현한다**

```python
if payload.travelAreaId is not None:
    travel_area = resolve_travel_area(payload.travelAreaId)
    if travel_area is None:
        raise TripServiceError(400, "Travel area not found")
    trip.travel_area_id = travel_area.id
    trip.region = travel_area.name
```

ID 검증은 revision bump 전에 수행해 실패 요청이 revision도 바꾸지 않게 한다. 유효한 변경은 기존 단일 `db.commit()`에서 제목·지역·기간과 함께 저장한다. 생성과 itinerary recommendation의 resolver import도 교체한다.

- [x] **Step 5: backend 일정 test를 통과시킨다**

Run: `cd backend; python -m pytest tests/test_trip_db_routes.py tests/test_itinerary_recommendations.py -q`

Expected: PASS; 장소·정책·권한·revision 동작이 유지된다.

---

### Task 4: AppDataApi 계약과 공통 지역 선택기

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/dataApi.ts`
- Modify: `frontend/src/api/backendApi.ts`
- Modify: `frontend/src/api/backendApi.test.ts`
- Create: `frontend/src/components/trip/TripRegionSelector.tsx`
- Create: `frontend/src/components/trip/TripRegionSelector.test.tsx`
- Modify: `frontend/src/styles/app.css`

**Interfaces:**
- Consumes: Task 2 catalog API, Task 3 Trip/settings DTO.
- Produces: `TravelAreaCatalog`, `getTravelAreaCatalog(sido)`, controlled `TripRegionSelector`.

- [x] **Step 1: API serialization 실패 test를 작성한다**

```ts
it("requests one complete sido catalog", async () => {
  mockFetch.mockResolvedValue(jsonResponse(catalogFixture));
  await backendApi.getTravelAreaCatalog("제주");
  expect(mockFetch).toHaveBeenCalledWith(
    expect.stringContaining("/api/travel-areas?sido=%EC%A0%9C%EC%A3%BC"),
    expect.any(Object),
  );
});

it("serializes travelAreaId in trip settings", async () => {
  await backendApi.updateTripSettings("7", { expectedRevision: 4, travelAreaId: "jeju-west" });
  expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({
    expectedRevision: 4,
    travelAreaId: "jeju-west",
  });
});
```

- [x] **Step 2: API test가 method 부재로 실패하는지 확인한다**

Run: `cd frontend; npm test -- src/api/backendApi.test.ts`

Expected: FAIL because new method/types are missing.

- [x] **Step 3: API type과 method를 구현한다**

```ts
export type TravelAreaOption = {
  travelAreaId: string;
  travelAreaName: string;
  sido: string;
  areaType: "whole" | "recommended" | "administrative";
  includedCities: string[];
};

export type TravelAreaCatalog = {
  sido: string;
  sourceAsOf: string;
  wholeArea: TravelAreaOption;
  recommendedAreas: TravelAreaOption[];
  administrativeAreas: TravelAreaOption[];
};
```

`Trip`에 `travelAreaId: string | null`, `region: string`을 추가하고 settings request에 `travelAreaId?: string`을 추가한다. `AppDataApi.getTravelAreaCatalog()`와 URLSearchParams 기반 backend 구현을 추가한다.

- [x] **Step 4: selector의 그룹·완전성·오류 실패 test를 작성한다**

```tsx
render(<TripRegionSelector selectedSido="제주" value={jejuEast} onSidoChange={onSidoChange} onChange={onChange} />);
expect(await screen.findByRole("group", { name: "전체" })).toBeInTheDocument();
expect(screen.getByRole("group", { name: "추천 여행권역" })).toBeInTheDocument();
expect(screen.getByRole("group", { name: "시·군·구" })).toBeInTheDocument();
expect(screen.getByRole("button", { name: "제주 동부" })).toHaveAttribute("aria-pressed", "true");
```

경기 fixture에 21개 이상을 넣어 마지막 항목도 표시되는지, 오류 시 기존 선택과 retry가 유지되는지, sido 변경 시 이전 세부 선택을 남기지 않는지 검증한다.

- [x] **Step 5: selector test가 component 부재로 실패하는지 확인한다**

Run: `cd frontend; npm test -- src/components/trip/TripRegionSelector.test.tsx`

Expected: FAIL because component is missing.

- [x] **Step 6: controlled selector를 구현한다**

```ts
type TripRegionSelectorProps = {
  selectedSido: string | null;
  value: TravelAreaOption | null;
  onSidoChange: (sido: string) => void;
  onChange: (area: TravelAreaOption) => void;
  disabled?: boolean;
  error?: string;
};
```

17개 button은 `aria-pressed`를 쓴다. catalog를 `전체`, `추천 여행권역`, `시·군·구` 순서의 fieldset/legend로 렌더링한다. 빈 optional group만 숨기며 전체는 항상 보인다. loading 동안 기존 선택을 보존하고 오류·retry를 표시한다.

- [x] **Step 7: API/selector test와 typecheck를 통과시킨다**

Run: `cd frontend; npm test -- src/api/backendApi.test.ts src/components/trip/TripRegionSelector.test.tsx; npm run typecheck`

Expected: PASS; 모든 Trip fixture가 새 계약을 만족한다.

---

### Task 5: 공통 날짜 유틸과 달력

**Files:**
- Create: `frontend/src/utils/tripDateRange.ts`
- Create: `frontend/src/utils/tripDateRange.test.ts`
- Create: `frontend/src/components/trip/TripDateRangePicker.tsx`
- Create: `frontend/src/components/trip/TripDateRangePicker.test.tsx`
- Modify: `frontend/src/styles/app.css`

**Interfaces:**
- Consumes: 기존 `normalizeTripDateRange()` 의미와 생성 화면의 calendar behavior.
- Produces: `TripDateRangeValue`, 순수 date helpers, controlled `TripDateRangePicker`.

- [x] **Step 1: 순수 date helper 실패 test를 작성한다**

```ts
expect(parseTripDate("2026-09-10")?.getDate()).toBe(10);
expect(parseTripDate("2026-02-30")).toBeNull();
expect(normalizeSelectedRange("2026-09-12", "2026-09-10")).toEqual({ startDate: "2026-09-10", endDate: "2026-09-12" });
expect(buildCalendarDays(new Date(2026, 8, 1))).toHaveLength(42);
expect(tripDateDayCount("2026-09-10", "2026-09-12")).toBe(3);
```

- [x] **Step 2: helper 부재로 실패하는지 확인한다**

Run: `cd frontend; npm test -- src/utils/tripDateRange.test.ts`

Expected: FAIL because module is missing.

- [x] **Step 3: 날짜 유틸을 구현한다**

```ts
export type TripDateRangeValue = { startDate: string; endDate: string };
export function parseTripDate(value: string): Date | null;
export function formatTripDate(date: Date): string;
export function startOfTripMonth(value: string): Date;
export function addTripMonths(date: Date, months: number): Date;
export function formatTripCalendarMonth(date: Date): string;
export function buildCalendarDays(month: Date): Date[];
export function isTripDateInRange(value: string, startDate: string, endDate: string): boolean;
export function tripDateDayCount(startDate: string, endDate: string): number | null;
export function normalizeSelectedRange(startDate: string, endDate: string): TripDateRangeValue;
```

- [x] **Step 4: 달력 interaction 실패 test를 작성한다**

```tsx
const onChange = vi.fn();
render(<TripDateRangePicker value={{ startDate: "2026-09-10", endDate: "2026-09-12" }} onChange={onChange} />);
await user.click(screen.getByTestId("trip-date-range-trigger"));
await user.click(screen.getByRole("button", { name: "2026-09-15" }));
await user.click(screen.getByRole("button", { name: "2026-09-11" }));
expect(onChange).toHaveBeenLastCalledWith({ startDate: "2026-09-11", endDate: "2026-09-15" });
```

이전/다음 달, range class, 완료 닫기, disabled, error 연결도 별도 test로 작성한다.

- [x] **Step 5: controlled picker를 구현한다**

```ts
type TripDateRangePickerProps = {
  value: TripDateRangeValue;
  onChange: (value: TripDateRangeValue) => void;
  disabled?: boolean;
  error?: string;
};
```

내부 state는 open 여부, 표시 월, `start | end` 단계뿐이다. 두 번째 선택에서 `normalizeSelectedRange()` 후 한 번에 `onChange`한다. trigger에 범위/일수, dialog에 42칸 grid, 한국어 요일, 범위 강조, 월 이동, 완료를 제공한다.

- [x] **Step 6: date test를 통과시킨다**

Run: `cd frontend; npm test -- src/utils/tripDateRange.test.ts src/components/trip/TripDateRangePicker.test.tsx`

Expected: PASS; 정방향과 역방향 선택 결과가 같다.

---

### Task 6: 생성·직접 편집·상세 편집 통합

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryCreatePage.tsx`
- Modify: `frontend/src/pages/itinerary/ItineraryEditPage.tsx`
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Modify: `frontend/src/app/__tests__/trip-create.test.tsx`
- Modify: `frontend/src/app/__tests__/trip-edit.test.tsx`
- Modify: `frontend/src/app/__tests__/trip-detail.test.tsx`
- Modify: `frontend/src/styles/app.css`

**Interfaces:**
- Consumes: Tasks 4–5의 API, selector, date picker.
- Produces: 생성/settings payload와 세 화면의 동일한 날짜 선택 UX.

- [x] **Step 1: 현재 사용자 변경 diff를 다시 읽는다**

Run:

```powershell
git diff -- frontend/src/pages/itinerary/ItineraryCreatePage.tsx frontend/src/pages/itinerary/ItineraryDetailPage.tsx frontend/src/app/__tests__/trip-create.test.tsx frontend/src/app/__tests__/trip-detail.test.tsx frontend/src/styles/app.css
```

Expected: 제목 가시성·편집 button 위치를 포함한 최신 변경을 확인하고 보존한다.

- [x] **Step 2: create page 실패 test를 작성한다**

경기 catalog를 stub해 `연천군`까지 표시하고 선택 후 다음 payload를 검증한다.

```ts
expect(createTripSpy).toHaveBeenCalledWith(expect.objectContaining({
  region: "연천군",
  travelAreaId: "admin:%EA%B2%BD%EA%B8%B0:%EC%97%B0%EC%B2%9C%EA%B5%B0",
}));
```

광역시도만 고른 상태에서는 진행하지 않고 `전체 또는 세부 지역을 선택해 주세요`를 표시하는 test도 추가한다.

- [x] **Step 3: edit page 실패 test를 작성한다**

`travelAreaId: "jeju-east", region: "제주 동부"` trip을 불러 제주 서부로 변경하고 다음 settings payload를 단언한다.

```ts
expect(updateSettingsSpy).toHaveBeenCalledWith("91", expect.objectContaining({
  travelAreaId: "jeju-west",
  startDate: "2026-09-10",
  endDate: "2026-09-12",
}));
```

legacy `travelAreaId: null`은 exact region name, 그다음 해당 sido 전체로 화면 복원하되 저장 전 API를 호출하지 않는 test와 viewer read-only test를 추가한다.

- [x] **Step 4: 상세 기간 edit 실패 test를 작성한다**

`여행기간 수정`을 열었을 때 native `input[type=date]`가 없고 공통 `trip-date-range-trigger`가 있으며, 역순 선택이 정방향 settings payload로 저장되는지 검증한다. 기존 overflow strategy test는 유지한다.

- [x] **Step 5: 기존 UI에서 정확히 실패하는지 확인한다**

Run: `cd frontend; npm test -- src/app/__tests__/trip-create.test.tsx src/app/__tests__/trip-edit.test.tsx src/app/__tests__/trip-detail.test.tsx`

Expected: FAIL because create uses recommendation `limit=20`, edit has no region selector, and edit surfaces use native date inputs.

- [x] **Step 6: create page를 공통 component로 교체한다**

- `travelAreaId` query는 catalog에서 ID로 복원한다.
- `region`/`sido`만 있으면 광역시도를 열되 `전체` 또는 세부지역을 명시적으로 고르게 한다.
- `policy-region:`이 catalog에 없으면 기존 recommendation lookup의 동적 option을 병합해 호환한다.
- 직접 수정한 title은 지역 변경으로 덮어쓰지 않는다.
- inline calendar helper/state/markup은 삭제하고 `TripDateRangePicker`를 사용한다.

- [x] **Step 7: direct edit page를 통합한다**

catalog option의 sido와 `trip.travelAreaId`로 현재 선택을 복원한다. legacy fallback은 exact `trip.region`, `"<sido> 전체"`, whole option 순으로만 적용하고 저장 전 DB를 바꾸지 않는다. 선택 변경은 title을 건드리지 않으며 save payload에 `travelAreaId`를 포함한다. native date input은 공통 picker로 교체한다.

- [x] **Step 8: detail 기간 sheet를 통합한다**

`TripDateEditorSheet`의 두 date input과 두 change callback을 `TripDateRangePicker`와 `onChangeDateRange(value)`로 교체한다. overflow 계산, revision conflict, save 후 active day 보정은 그대로 둔다.

- [x] **Step 9: 통합 test와 typecheck를 통과시킨다**

Run:

```powershell
cd frontend
npm test -- src/app/__tests__/trip-create.test.tsx src/app/__tests__/trip-edit.test.tsx src/app/__tests__/trip-detail.test.tsx
npm run typecheck
```

Expected: PASS; 지역 변경과 공통 달력이 제목, 장소, 정책, 권한, overflow를 깨지 않는다.

---

### Task 7: 계약 문서와 golden eval 동기화

**Files:**
- Modify: `docs/mvp-api-contract.md`
- Modify: `docs/requirements.md`
- Modify: `docs/implemented-feature-spec.md`
- Modify: `.agent/evals/api-contract-golden.json`

**Interfaces:**
- Consumes: Tasks 1–6의 최종 API/UI.
- Produces: 구현과 일치하는 프로젝트 소스 오브 트루스.

- [x] **Step 1: API contract를 갱신한다**

`GET /travel-areas` grouped response, `sourceAsOf`, 400/422, 네 ID family를 추가한다. Trip response `region`, PATCH settings optional `travelAreaId`, invalid ID 400, 기존 content 보존 규칙을 명시한다.

- [x] **Step 2: requirements와 implemented spec을 갱신한다**

일정 생성/편집 설명을 `17개 광역시도 → 전체/추천 여행권역/시·군·구`, 기존 일정 지역 변경, 생성·편집 공통 달력으로 교체한다.

- [x] **Step 3: golden JSON을 동기화하고 검증한다**

`.agent/evals/api-contract-golden.json`에 `/api/travel-areas`, Trip `region`, settings `travelAreaId` behavior를 추가한다.

Run: `python -m json.tool .agent/evals/api-contract-golden.json > $null`

Expected: exit code 0.

---

### Task 8: 전체 검증, 5173 확인, 체크리스트, 최종 커밋

**Files:**
- Modify: `CHECKLIST.md`
- Verify: all files above

**Interfaces:**
- Consumes: Tasks 1–7의 완성 기능.
- Produces: 자동/수동 검증 증거와 검증 후 단일 commit.

- [x] **Step 1: backend 전체 회귀를 실행한다**

Run: `cd backend; python -m pytest`

Expected: all backend tests PASS. DB schema가 바뀌지 않아 새 Alembic revision이 없다.

- [x] **Step 2: frontend 전체 회귀와 build를 실행한다**

Run:

```powershell
cd frontend
npm run typecheck
npm test
npm run build
```

Expected: all commands PASS.

- [x] **Step 3: compose contract를 확인한다**

Run: `cd ..; docker compose -f compose.yaml config`

Expected: exit code 0.

- [ ] **Step 4: 5173 개발서버에서 수동 검증한다**

1. 경기에서 수원시·용인시·연천군과 목록 끝까지 접근한다.
2. 제주에서 전체, 동부/서부, 제주시/서귀포시가 별도 그룹으로 보이는지 확인한다.
3. 제주 동부 일정을 생성하고 `/trips/{id}/edit`에서 제주 서부로 저장한다.
4. 생성, 직접 편집, 상세 기간 수정에서 같은 달력과 역순 정규화를 확인한다.
5. 기간 축소 overflow 처리와 viewer read-only를 확인한다.
6. 360×780, 390×844, 430×932, 1024×768, 1440×900에서 overflow, clipping, dialog 이탈이 없는지 확인한다.

- [x] **Step 5: CHECKLIST를 최신 증거로 교체한다**

이번 상태, 명령별 PASS/FAIL, viewport 결과, 행정지역 snapshot 갱신 risk만 남기고 과거 task chronology를 추가하지 않는다.

- [x] **Step 6: UTF-8과 diff 위생을 확인한다**

Run:

```powershell
git diff --check
rg -n "\x{FFFD}" backend/app/data/administrative_areas.py backend/app/services/travel_area_catalog.py frontend/src/components/trip docs/superpowers docs/mvp-api-contract.md docs/requirements.md docs/implemented-feature-spec.md CHECKLIST.md
git status --short
```

Expected: diff check PASS, replacement character 없음, 의도한 변경만 존재한다.

- [x] **Step 7: 모든 검증 후에만 commit한다**

하나라도 실패하면 commit하지 않고 수정 후 관련 검증부터 재실행한다. 모두 통과하면 의도한 파일만 명시적으로 stage하고 staged diff를 다시 검사한다.

```powershell
git add backend/app/data/administrative_areas.py backend/app/data/travel_areas.py backend/app/services/travel_area_catalog.py backend/app/schemas/travel_areas.py backend/app/api/routes/travel_areas.py backend/app/api/router.py backend/app/schemas/trip.py backend/app/services/trips.py backend/app/services/itinerary_recommendations.py backend/tests/test_travel_area_catalog.py backend/tests/test_travel_area_catalog_routes.py backend/tests/test_travel_areas.py backend/tests/test_trip_db_routes.py backend/tests/test_itinerary_recommendations.py frontend/src/api/types.ts frontend/src/api/dataApi.ts frontend/src/api/backendApi.ts frontend/src/api/backendApi.test.ts frontend/src/components/trip/TripRegionSelector.tsx frontend/src/components/trip/TripRegionSelector.test.tsx frontend/src/components/trip/TripDateRangePicker.tsx frontend/src/components/trip/TripDateRangePicker.test.tsx frontend/src/utils/tripDateRange.ts frontend/src/utils/tripDateRange.test.ts frontend/src/pages/itinerary/ItineraryCreatePage.tsx frontend/src/pages/itinerary/ItineraryEditPage.tsx frontend/src/pages/itinerary/ItineraryDetailPage.tsx frontend/src/app/__tests__/trip-create.test.tsx frontend/src/app/__tests__/trip-edit.test.tsx frontend/src/app/__tests__/trip-detail.test.tsx frontend/src/styles/app.css docs/mvp-api-contract.md docs/requirements.md docs/implemented-feature-spec.md .agent/evals/api-contract-golden.json docs/superpowers/specs/2026-09-03-trip-region-calendar-unification-design.md docs/superpowers/plans/2026-09-03-trip-region-calendar-unification.md CHECKLIST.md
git diff --cached --check
git commit -m "feat: unify trip region and date selection"
```

Expected: commit succeeds only after every automated and 5173 manual gate has passed.

---

## 실행 결과 (2026-09-03 ~ 09-05)

Task 1~3 은 Codex 세션이, Task 4~8 은 Claude 세션이 이어받아 마쳤다.
인수 시점과 그때 닫은 구멍은 `docs/2026-09-04-codex-handoff.md` 에 적혀 있다.

| Task | 커밋 | 비고 |
|---|---|---|
| 1~3 백엔드 카탈로그·resolver·Trip 계약 | `f31ae58` | |
| 4~5 API 계약·공용 선택기·공용 달력 | `388a2e4` | |
| 6 생성·직접 편집·상세 통합 | `6e5b4ee` | |
| 7 계약 문서·golden eval | `b8d51ce`, `1e03180` | |
| 8 전체 검증 | — | Step 4(수동 확인)만 미완 |

### 계획과 달라진 것

**Task 6 Step 6.** 생성 화면의 지역 흐름을 통째로 갈아끼우지 않았다. 질의 사전선택
로직(`travelAreaId` / `region` / `sido` / `policySlug`)은 그대로 두고 렌더링과 선택
목록만 바꿨다. 그 로직에 10건 가까운 테스트가 붙어 있어 함께 갈아엎으면 회귀를
가릴 위험이 컸다. 대신 선택기에 `sidoOptions`(이 화면의 이모지·순서)와
`extraAreas`(카탈로그에 없는 동적 권역 병합)를 더했다.

**Task 4 복원 규칙.** 복원을 `onChange` 로 흘리면 화면을 열기만 해도 "지역을 바꿨다"로
기록돼, 손대지 않은 일정의 `travel_area_id` 가 저장 때 갈아치워졌다. 통로를
`onRestore` 로 분리했다.

**Task 8 Step 7.** 커밋은 수동 검증 전에 했다. 사용자 지시다. 한 번이 아니라
논리 단위로 나눠 담았고, `git add -p` 가 이 환경에서 대화형으로 돌지 않아
`ItineraryDetailPage.tsx` / `app.css` 는 헝크 단위로 못 갈랐다.

**계획 밖에서 더한 것.** 시·군·구를 권역으로 접는 작업(`9815c30`, `3235fd6`)은
이 계획서에 없다. 목록이 너무 길다는 지적을 받고 뒤에 붙였고,
`docs/superpowers/plans/2026-09-04-itinerary-day-strip-followups.md` 의 Task 9 로 기록했다.

### 검증

frontend 348 passed / 0 failed (28 files), backend 701 passed / 1 failed,
typecheck / build / mojibake / compose config / `git diff --check` 전부 통과.
백엔드 실패 1건은 Windows 임시 디렉터리 권한에 걸리는 간헐적 환경 이슈다.

이 절은 작업 뒤에 붙였다. 체크박스가 전부 비어 있어 계획서만 보면 아무것도
안 한 것처럼 읽혔기 때문이다.
