# 장소 카드 하단 시트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 장소 카드를 탭하면 상세·편집·Day 이동·삭제를 한 하단 시트에서 처리하고, 카드 하단의 수정·삭제 버튼을 없애며, Day 이동 후 목적지 카드를 눈에 띄게 한다.

**Architecture:** 기존 `PlaceEditorSheet`(edit 모드)를 유일한 장소 시트로 확장한다. `PlaceDetailDialog` 의 상세 블록을 시트로 옮기고 컴포넌트를 삭제한다. Day 칩 선택은 저장과 분리해 즉시 `PATCH /places/{id}/move` 를 호출한다. 이동 성공 시 `recentlyMovedPlaceId` 로 목적지 카드에 플래시 클래스를 붙이고 스크롤한다. 백엔드·API 계약 변경 없음.

**Tech Stack:** React 18 + Vite, dnd-kit(`@dnd-kit/core`, `@dnd-kit/sortable`), vitest + testing-library, CSS(`frontend/src/styles/app.css`).

**Spec:** `docs/superpowers/specs/2026-09-16-itinerary-card-management-design.md` §브랜치 ①

## Global Constraints

- 브랜치 `feature/itinerary-place-sheet`, 워크트리 `.superpowers/worktrees/itinerary-place-sheet`, base `develop@7456708`.
- 커밋은 **테스트 통과 후 사용자 승인**을 받은 뒤에만 만든다. 각 Task 의 마지막 단계는 "승인 요청" 이지 커밋이 아니다. 푸시·PR 은 Codex.
- 파일 편집은 Edit 도구로 부분 수정한다. 파일 전체를 다시 쓰지 않는다(줄끝 CRLF 혼입 방지). 스테이징 전 `git diff --stat` 과 `git diff -w --stat` 이 같아야 한다.
- 프런트 테스트: `cd frontend && npx vitest run <파일>` (루트 `npm test` 는 compose DB 를 띄우므로 워크트리에서 쓰지 않는다). 전체 게이트: `npx vitest run` + `npm run test:mojibake`.
- 4174 포트는 사용자 것. 수동 확인은 5173.
- 백엔드·`docs/mvp-api-contract.md`·골든 JSON 은 건드리지 않는다(API 변경 없음).
- 접근성: `<article>` 에 `role="button"` 을 붙이지 않는다(카드 안 컨트롤이 접근성 트리에서 사라짐 — `ItineraryDetailPage.tsx:5010-5013` 주석). 키보드 진입은 별도 sr-only 버튼으로.

## 파일 구조

| 파일 | 역할 | 변경 |
|---|---|---|
| `frontend/src/pages/itinerary/ItineraryDetailPage.tsx` | 페이지·카드·시트 전부 | `SortablePlaceItem` 카드 탭, `PlaceEditorSheet` 상세/삭제/즉시 Day 이동/readOnly, `PlaceDetailDialog` 삭제, `movePlaceTo` 플래시 상태 |
| `frontend/src/styles/app.css` | 스타일 | `.just-moved` 플래시, `.place-sheet-detail`, `.place-detail-dialog/-backdrop` 제거 |
| `frontend/src/app/__tests__/place-edit.test.tsx` | 편집 흐름 테스트 | 카드 탭 진입, Day 칩 즉시 이동, 저장 시 move 미호출, 플래시 |
| `frontend/src/app/__tests__/trip-detail.test.tsx` | 상세 페이지 테스트 | 지도 → 상세 경로 갱신(:2283-2308), 시트 안 삭제 |

---

### Task 0: 워크트리 부트스트랩 + 기준선

워크트리에는 `frontend/node_modules` 도 `frontend/.env` 도 없다(확인됨). 첫 RED 가 "모듈 없음" 이 되지 않게 먼저 맞춘다.

- [ ] **Step 1: node_modules 링크, .env 복사** (값은 출력하지 않는다)

```powershell
# 워크트리 frontend 디렉터리에서
New-Item -ItemType SymbolicLink -Path node_modules -Target ..\..\..\..\frontend\node_modules
Copy-Item ..\..\..\..\frontend\.env .env
```

- [ ] **Step 2: 기준선 실행**

Run: `npx vitest run src/app/__tests__/place-edit.test.tsx src/app/__tests__/trip-detail.test.tsx`
Expected: 전부 PASS (편집 전). 실패하면 여기서 멈추고 보고한다 — 이 브랜치의 문제가 아니다.

---

### Task 1: 카드 탭으로 편집 시트 열기 + 카드 하단 버튼 제거

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx:4998-5199` (`SortablePlaceItem` 렌더)
- Test: `frontend/src/app/__tests__/place-edit.test.tsx`

**Interfaces:**
- Consumes: `SortablePlaceItem` props `onEdit(place)`, `onDelete(place)`, `disabled`, `isDragging`(useSortable).
- Produces: 카드에 접근성 이름 `` `${place.label} 상세 열기` `` 인 sr-only 버튼. 이후 Task 의 테스트는 이 이름으로 시트를 연다. `onDelete` prop 은 이 Task 에서 제거된다(Task 3 에서 시트로 옮김).

- [ ] **Step 1: 실패 테스트 작성** — `place-edit.test.tsx` 의 `"edits places from the itinerary detail"` (L84) 에서 진입 방식을 바꾼다.

```tsx
// L112 교체
await user.click(screen.getByRole("button", { name: "Sunrise peak 상세 열기" }));
// 카드 하단 버튼이 사라졌는지도 같은 테스트에서 확인
expect(document.querySelector(".place-actions")).toBeNull();
```

- [ ] **Step 2: 실패 확인**

Run: `cd frontend && npx vitest run src/app/__tests__/place-edit.test.tsx -t "edits places"`
Expected: FAIL — `Unable to find role="button" and name "Sunrise peak 상세 열기"`

- [ ] **Step 3: 카드 구현** — `SortablePlaceItem` 에서:

(a) 드래그 직후 click 이 새는 것을 막는 ref (dnd-kit 은 drag 후 click 을 항상 억제하지는 않는다):

```tsx
// useSortable 호출 바로 아래
const wasDraggedRef = useRef(false);
useEffect(() => {
  if (isDragging) {
    wasDraggedRef.current = true;
    return;
  }
  const timer = window.setTimeout(() => {
    wasDraggedRef.current = false;
  }, 0);
  return () => window.clearTimeout(timer);
}, [isDragging]);
const canOpenSheet = Boolean(place.id) && !isRecommendationPreviewPlace && !isPreviewMode && !disabled;
const openSheet = () => {
  if (!canOpenSheet || wasDraggedRef.current) return;
  onEdit(place);
};
```

(b) `<article>` (L5014) 에 `onClick={openSheet}` 추가.

(c) 드래그 핸들 sr-only 버튼(L5023-5036) 바로 앞에 키보드 진입 버튼 추가:

```tsx
{canOpenSheet && (
  <button
    className="sr-only"
    type="button"
    aria-label={`${place.label} 상세 열기`}
    onClick={(event) => {
      event.stopPropagation();
      openSheet();
    }}
  />
)}
```

(d) `시간 확인` 버튼(L5078-5087)의 `onClick` 에 `event.stopPropagation()` 추가 — 시트가 두 번 열리는 것을 막는다:

```tsx
onClick={(event) => {
  event.stopPropagation();
  onEdit(place);
}}
```

(e) L5148-5195 의 `canEditTrip ? (<div className="place-actions">…</div>) : null` 분기에서 `isPreviewMode` 가 아닐 때의 `수정`·`삭제` 버튼을 제거한다. 결과:

```tsx
) : canEditTrip && isPreviewMode ? (
  <div className="place-actions">
    <details className="preview-time-edit" …>  {/* 기존 그대로 */}
    </details>
  </div>
) : null}
```

(f) `onDelete` prop 을 `SortablePlaceItem` 의 props/타입에서 제거하고, 호출부 L4149 `onDelete={requestDeletePlace}` 를 지운다. `requestDeletePlace` 자체는 Task 3 에서 다시 쓰므로 남긴다.

- [ ] **Step 4: 통과 확인**

Run: `cd frontend && npx vitest run src/app/__tests__/place-edit.test.tsx`
Expected: PASS. `"renders viewer trips as read-only"` (L327) 가 `.place-actions` 부재를 다른 방식으로 단언하고 있으면 그 단언만 새 구조에 맞춘다.

- [ ] **Step 5: 타입 검사** — `cd frontend && npx tsc --noEmit -p tsconfig.json`. `onDelete` 잔여 참조가 있으면 여기서 잡힌다.

- [ ] **Step 6: 승인 요청** — 변경 요약과 테스트 결과를 보고하고 커밋 승인을 기다린다.

---

### Task 2: 시트에 상세 블록 통합, `PlaceDetailDialog` 삭제, 보기 권한용 readOnly

**Files:**
- Modify: `ItineraryDetailPage.tsx:5461-5798` (`PlaceEditorSheet`), `:4662-4735` (삭제), `:4296-4302` (렌더 제거), `:3983-3986` (지도 진입), `:2972-2998` (`openEditPlace`)
- Modify: `frontend/src/styles/app.css:8025-8034`
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx:2283-2308`

**Interfaces:**
- Produces: `PlaceEditorSheet` 새 props `place: ItineraryPlace | null`(edit 모드에서 상세 표시용), `readOnly: boolean`. 새 헬퍼 `openPlaceSheet(place: ItineraryPlace)` — 편집 가능하면 `openEditPlace`, 아니면 readOnly 로 연다.
- Consumes: Task 1 의 `${label} 상세 열기` 버튼.

- [ ] **Step 1: 실패 테스트** — `trip-detail.test.tsx` L2283-2308 을 시트 기준으로 바꾼다.

```tsx
await screen.findByRole("dialog", { name: "성산 일출봉 지도 상세" });
await user.click(screen.getByRole("button", { name: "상세 보기" }));

const sheet = await screen.findByRole("dialog", { name: "장소 수정" });
expect(within(sheet).getByText("제주 서귀포시 성산읍 성산리 1")).toBeInTheDocument();
expect(within(sheet).getByText("33.458, 126.942")).toBeInTheDocument();
expect(within(sheet).getByText("관광명소")).toBeInTheDocument();
expect(within(sheet).getByRole("link", { name: "카카오맵에서 보기" })).toHaveAttribute(
  "href",
  "https://place.map.kakao.com/123",
);
expect(within(sheet).getByDisplayValue("성산 일출봉")).toBeInTheDocument();

await user.click(within(sheet).getByRole("button", { name: "닫기" }));
expect(screen.queryByRole("dialog", { name: "장소 수정" })).not.toBeInTheDocument();
```

그리고 보기 권한 테스트를 하나 추가한다(같은 describe, 위 테스트 바로 아래):

```tsx
it("opens a read-only place sheet for viewers", async () => {
  const trip: Trip = {
    ...getPreviewTrip(),
    id: "56",
    currentUserRole: "viewer",
    days: { 1: [{ id: "1", time: "09:00", label: "성산 일출봉", meta: "메모", address: "제주 성산읍" }] },
  };
  const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
  try {
    await login();
    cleanup();
    renderAppRoute("/trips/56?day=1");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "성산 일출봉 상세 열기" }));
    const sheet = await screen.findByRole("dialog", { name: "장소 상세" });
    expect(within(sheet).getByText("제주 성산읍")).toBeInTheDocument();
    expect(within(sheet).queryByRole("button", { name: "저장하기" })).not.toBeInTheDocument();
    expect(within(sheet).queryByRole("button", { name: "삭제" })).not.toBeInTheDocument();
    expect(within(sheet).getByDisplayValue("성산 일출봉")).toBeDisabled();
  } finally {
    getTripSpy.mockRestore();
  }
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx -t "장소 상세|read-only place sheet|detail dialog"`
Expected: FAIL (시트에 주소 없음 / "장소 상세" 다이얼로그 없음).

- [ ] **Step 3: `PlaceEditorSheet` 확장**

(a) props 추가: `place?: ItineraryPlace | null; readOnly?: boolean;` — **선택 prop 에 기본값** (`place = null`, `readOnly = false`). `trip-detail.test.tsx:82` 가 `PlaceEditorSheet` 를 직접 렌더하므로 필수로 만들면 그 테스트가 타입 에러로 깨진다. Task 3 의 `onDelete?`, Task 4 의 `isMovingDay?` 도 같은 이유로 선택.

(b) 헤더(L5556-5563): 제목·설명을 readOnly 에 따라 바꾼다.

```tsx
<h2 id="place-editor-title">
  {mode === "add" ? "장소 추가" : readOnly ? "장소 상세" : "장소 수정"}
</h2>
<p className="meta">
  {mode === "add"
    ? "장소를 검색해 선택한 뒤 목록에 담아 저장하세요."
    : readOnly
      ? "보기 권한이라 내용을 바꿀 수 없어요."
      : "날짜를 고르면 바로 옮겨지고, 나머지는 저장하기로 반영돼요."}
</p>
```

(c) edit 모드 블록(L5704) 맨 앞, Day 칩 위에 상세 블록을 넣는다. `PlaceDetailDialog` L4672-4681 의 계산을 그대로 옮긴다.

```tsx
{mode === "edit" && place && (
  <PlaceSheetDetail place={place} />
)}
```

새 함수 컴포넌트(파일 안, `PlaceEditorSheet` 위):

```tsx
function PlaceSheetDetail({ place }: { place: ItineraryPlace }) {
  const addressText = place.address || "주소 정보 없음";
  const categoryText = place.category || place.categoryCode || "장소";
  const coordinateText =
    Number.isFinite(place.latitude) && Number.isFinite(place.longitude)
      ? `${place.latitude}, ${place.longitude}`
      : "좌표 정보 없음";
  const kakaoPlaceUrl =
    place.placeUrl ||
    `https://map.kakao.com/link/search/${encodeURIComponent(place.address || place.label)}`;
  return (
    <div className="place-sheet-detail">
      <div className="place-detail-summary" aria-label="장소 요약">
        <span>{categoryText}</span>
        {place.time && <span>{place.time}</span>}
      </div>
      <div className="place-detail-fields">
        <section>
          <strong>주소</strong>
          <p>{addressText}</p>
        </section>
        <section>
          <strong>좌표</strong>
          <p>{coordinateText}</p>
        </section>
      </div>
      <a className="btn sm line" href={kakaoPlaceUrl} rel="noreferrer" target="_blank">
        카카오맵에서 보기
      </a>
    </div>
  );
}
```

메모 섹션은 넣지 않는다 — 시트의 메모 textarea 가 같은 값을 보여준다.

(d) readOnly 일 때: Day 칩 블록(L5706) 은 `!readOnly && dayOptions.length > 1`, `PlaceTimePicker` 는 `disabled={isSaving || readOnly}`, 장소명 input 과 메모 textarea 에 `disabled={readOnly}`, `sheet-actions` 전체(L5786-5794) 는 `!readOnly &&` 로 감싼다.

- [ ] **Step 4: 페이지 쪽 배선**

(a) `openEditPlace`(L2972) 의 `!canEditTrip` 분기를 에러 대신 readOnly 열기로 바꾼다:

```tsx
const openEditPlace = (place: ItineraryPlace) => {
  const draft =
    canEditTrip && trip && place.id
      ? readDraft<TripPlaceEditDraft>(tripPlaceEditDraftKey(trip.id, place.id))
      : null;
  // 이하 기존 그대로 (cancelPendingPlaceSearch … setPlaceError(""))
};
```

즉 첫 `if (!canEditTrip) { setPlaceError(...); return; }` 블록을 삭제한다. 보기 권한은 시트가 `readOnly` 로 막는다.

(b) 렌더(L4262-4295) 에 `place={placeEditor.mode === "edit" ? placeEditor.place : null}` 와 `readOnly={!canEditTrip}` 를 넘긴다.

(c) 지도 진입 L3983-3986:

```tsx
onShowPlaceDetail={(place) => {
  setNotice(null);
  openEditPlace(place);
}}
```

(d) `placeDetail` state(L1759 부근 `useState<{ dayNumber: number; place: ItineraryPlace } | null>`)와 L4296-4302 렌더, `PlaceDetailDialog` 함수(L4662-4735) 를 삭제한다. `PlaceMapBottomSheet` 의 `onShowPlaceDetail` prop 은 그대로다.

(e) `SortablePlaceItem` 의 `canOpenSheet`(Task 1) 에서 `canEditTrip` 조건이 없는지 확인 — 보기 권한도 탭으로 열 수 있어야 한다. `<article>` 의 포인터 리스너 spread 는 `canEditTrip` 조건이 있어 드래그는 여전히 막힌다.

- [ ] **Step 5: CSS** — `app.css:8025-8034` 의 `.place-detail-backdrop`, `.place-detail-dialog` 를 지우고 아래를 추가한다. `.place-detail-summary`, `.place-detail-fields` 는 유지.

```css
.place-sheet-detail {
  display: grid;
  gap: 10px;
  padding-bottom: 4px;
  border-bottom: 1px solid #ececf2;
}
```

- [ ] **Step 6: 통과 확인**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx src/app/__tests__/place-edit.test.tsx`
Expected: PASS. `npx tsc --noEmit -p tsconfig.json` 도 통과(`placeDetail`·`PlaceDetailDialog` 잔여 참조 없음).

- [ ] **Step 7: 승인 요청**

---

### Task 3: 시트 안 삭제 버튼

**Files:**
- Modify: `ItineraryDetailPage.tsx` `PlaceEditorSheet` 하단, `confirmDeletePlace:3621-3649`, 렌더 L4262
- Test: `frontend/src/app/__tests__/place-edit.test.tsx`

**Interfaces:**
- Produces: `PlaceEditorSheet` prop `onDelete: () => void`. 삭제 성공 시 시트가 닫힌다.
- Consumes: 기존 `requestDeletePlace`, `ConfirmDialog`(L4336).

- [ ] **Step 1: 실패 테스트** — `place-edit.test.tsx` 에 추가:

```tsx
it("deletes a place from the sheet", async () => {
  const trip: Trip = {
    ...getPreviewTrip(),
    id: "57",
    revision: 3,
    currentUserRole: "owner",
    days: { 1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }] },
  };
  const afterDelete: Trip = { ...trip, revision: 4, days: { 1: [] } };
  const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
  const deleteSpy = vi.spyOn(appDataApi, "deleteTripPlace").mockResolvedValue(afterDelete);
  try {
    await login();
    cleanup();
    renderAppRoute("/trips/57");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Sunrise peak 상세 열기" }));
    const sheet = await screen.findByRole("dialog", { name: "장소 수정" });
    await user.click(within(sheet).getByRole("button", { name: "삭제" }));
    const confirm = await screen.findByRole("dialog", { name: "장소를 삭제할까요?" });
    await user.click(within(confirm).getByRole("button", { name: "삭제" }));
    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith("57", "1", 3));
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "장소 수정" })).not.toBeInTheDocument(),
    );
    expect(document.body).not.toHaveTextContent("Sunrise peak");
  } finally {
    getTripSpy.mockRestore();
    deleteSpy.mockRestore();
  }
});
```

`ConfirmDialog`(`ui.tsx:215-217`) 는 `aria-labelledby` 가 `<h2>{title}</h2>` 를 가리키므로 위 `"장소를 삭제할까요?"` 이름이 그대로 맞는다(확인됨).

- [ ] **Step 2: 실패 확인**

Run: `cd frontend && npx vitest run src/app/__tests__/place-edit.test.tsx -t "deletes a place from the sheet"`
Expected: FAIL — 시트 안에 "삭제" 버튼 없음.

- [ ] **Step 3: 구현**

(a) `PlaceEditorSheet` props 에 `onDelete?: () => void` 추가(직접 렌더하는 테스트 때문에 선택). `sheet-actions`(L5786) 를 다음으로 교체:

```tsx
{!readOnly && (
  <div className="sheet-actions place-sheet-actions">
    {mode === "edit" && (
      <button className="btn line" type="button" disabled={isSaving} onClick={onDelete}>
        삭제
      </button>
    )}
    <Button full disabled={isSaving} onClick={onSubmit}>
      {isSaving ? "저장 중입니다" : hasPlaceBasket ? `${placeBasket.length}개 저장하기` : "저장하기"}
    </Button>
  </div>
)}
```

(b) 렌더 L4262 에 `onDelete={() => placeEditor.mode === "edit" && requestDeletePlace(placeEditor.place)}`.

(c) `confirmDeletePlace` 성공 분기(L3633 뒤)에 `setPlaceEditor(null);` 추가 — 삭제된 장소의 시트가 남아 있으면 안 된다.

(d) CSS:

```css
.place-sheet-actions {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px;
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd frontend && npx vitest run src/app/__tests__/place-edit.test.tsx`
Expected: PASS.

- [ ] **Step 5: 승인 요청**

---

### Task 4: Day 칩 선택 = 즉시 이동, 저장은 PATCH 단독

**Files:**
- Modify: `ItineraryDetailPage.tsx` `submitPlaceEditor:3207-3321`, 렌더 L4273-4277 `onDayChange`, `PlaceEditorSheet` Day 칩 `disabled`
- Test: `frontend/src/app/__tests__/place-edit.test.tsx`

**Interfaces:**
- Produces: 페이지 헬퍼 `movePlaceFromSheet(nextDay: number): Promise<void>`. `PlaceEditorSheet` prop `isMovingDay: boolean`.
- Consumes: 기존 `movePlaceTo(place, dayNumber, position)`(L3333), `resolveTimeSortedPosition`, `findTripPlaceById`.

- [ ] **Step 1: 실패 테스트** — `place-edit.test.tsx` 에 추가:

```tsx
it("moves the place immediately when a day chip is chosen and saves fields without a move", async () => {
  const trip: Trip = {
    ...getPreviewTrip(),
    id: "58",
    revision: 5,
    currentUserRole: "owner",
    days: {
      1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }],
      2: [{ id: "2", time: "08:00", label: "Early market", meta: "Food" }],
    },
  };
  const movedTrip: Trip = {
    ...trip,
    revision: 6,
    days: { 1: [], 2: [trip.days[2][0], trip.days[1][0]] },
  };
  const savedTrip: Trip = {
    ...movedTrip,
    revision: 7,
    days: { 1: [], 2: [trip.days[2][0], { ...trip.days[1][0], label: "Renamed peak" }] },
  };
  const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
  const moveSpy = vi.spyOn(appDataApi, "moveTripPlace").mockResolvedValue(movedTrip);
  const updateSpy = vi.spyOn(appDataApi, "updateTripPlace").mockResolvedValue(savedTrip);
  try {
    await login();
    cleanup();
    renderAppRoute("/trips/58?day=1");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Sunrise peak 상세 열기" }));
    const sheet = await screen.findByRole("dialog", { name: "장소 수정" });

    await user.click(within(sheet).getByRole("radio", { name: /Day 2/ }));
    await waitFor(() =>
      expect(moveSpy).toHaveBeenCalledWith("58", "1", {
        dayNumber: 2,
        position: 2, // 09:00 은 08:00 뒤
        expectedRevision: 5,
      }),
    );
    // 시트는 열린 채, Day 2 가 선택됨 — setTrip/setPlaceEditor 는 spy 해결 뒤에 반영되므로 waitFor
    await waitFor(() =>
      expect(within(sheet).getByRole("radio", { name: /Day 2/ })).toHaveAttribute("aria-checked", "true"),
    );
    // 시트가 덮고 있는 동안은 플래시하지 않는다 (Task 5 에서 닫을 때로 미룬다)
    expect(document.querySelector(".timeline-slot.just-moved")).toBeNull();

    await user.clear(document.querySelector('input[name="place-label"]') as HTMLInputElement);
    await user.type(document.querySelector('input[name="place-label"]') as HTMLInputElement, "Renamed peak");
    await user.click(within(sheet).getByRole("button", { name: "저장하기" }));

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith("58", "1", expect.objectContaining({ label: "Renamed peak", expectedRevision: 6 })),
    );
    expect(moveSpy).toHaveBeenCalledTimes(1); // 저장은 move 를 다시 부르지 않는다
    await waitFor(() => expect(document.body).toHaveTextContent("Renamed peak"));
    // 저장으로 시트가 닫히면 미뤄둔 플래시가 목적지 카드에 붙는다 (Task 5 구현 전에는 이 두 줄을 주석 처리)
    await waitFor(() => {
      const moved = document.querySelector(".timeline-slot.just-moved");
      expect(moved).toHaveTextContent("Renamed peak");
    });
  } finally {
    getTripSpy.mockRestore();
    moveSpy.mockRestore();
    updateSpy.mockRestore();
  }
});

it("reports a failed day move from the sheet instead of swallowing it", async () => {
  const trip: Trip = {
    ...getPreviewTrip(),
    id: "59",
    revision: 1,
    currentUserRole: "owner",
    days: { 1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }], 2: [] },
  };
  const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
  const moveSpy = vi.spyOn(appDataApi, "moveTripPlace").mockRejectedValue(new Error("network"));
  try {
    await login();
    cleanup();
    renderAppRoute("/trips/59?day=1");
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Sunrise peak 상세 열기" }));
    const sheet = await screen.findByRole("dialog", { name: "장소 수정" });
    await user.click(within(sheet).getByRole("radio", { name: /Day 2/ }));
    expect(await within(sheet).findByText("장소 순서를 변경하지 못했어요. 잠시 후 다시 시도해 주세요.")).toBeInTheDocument();
    expect(within(sheet).getByRole("radio", { name: /Day 1/ })).toHaveAttribute("aria-checked", "true");
  } finally {
    getTripSpy.mockRestore();
    moveSpy.mockRestore();
  }
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd frontend && npx vitest run src/app/__tests__/place-edit.test.tsx -t "day chip|failed day move"`
Expected: FAIL — 칩 클릭 시 `moveTripPlace` 미호출(현재는 저장 때 호출).

- [ ] **Step 3: 페이지 헬퍼**

`movePlaceTo` 바로 아래에 추가:

```tsx
/* 시트의 Day 칩은 저장과 분리해 그 자리에서 옮긴다. 저장에 묶어 두면
   move 실패를 조용히 삼키게 되고(이전 :3294), 사용자는 옮겨진 줄 안다. */
const movePlaceFromSheet = async (nextDay: number) => {
  if (!trip || !placeEditor || placeEditor.mode !== "edit") return;
  const place = placeEditor.place;
  if (!place.id || nextDay === placeEditor.dayNumber) return;
  // 저장된 시간(place.time)으로 자리를 정한다. 아직 저장 안 한 폼의 시간을 쓰면
  // 저장 시 재정렬과 기준이 둘이 된다.
  const position = resolveTimeSortedPosition({
    places: trip.days[nextDay] ?? [],
    movingPlaceId: place.id,
    nextTime: place.time ?? "",
  });
  await movePlaceTo(place, nextDay, position);
};
```

`resolveTimeSortedPosition`(L1518) 은 1-based 이고 `movingPlaceId` 가 목록에 없으면 그냥 전부를 `others` 로 쓴다 — 테스트의 `position: 2`(08:00 뒤) 는 이 규칙에 맞는다.

`movePlaceTo` 성공 분기(L3365 `setTrip(nextTrip)` 뒤)에 시트의 Day 를 따라가게 한다:

```tsx
setPlaceEditor((current) =>
  current && current.mode === "edit" && current.place.id === place.id
    ? { ...current, dayNumber }
    : current,
);
```

실패 시 `setMoveError(...)` 는 기존 그대로다. 시트가 이 오류를 보여주도록 렌더 L4266 을 `error={placeError || moveError}` 로 바꾼다. `moveError` 를 시트가 닫힐 때 지우도록 `closePlaceEditor` 에 `setMoveError("")` 추가.

409 충돌(`isTripConflict`) 분기에서는 `refreshTripAfterConflict(setMoveError)` 가 trip 을 다시 받는데 `placeEditor.place` 는 옛 객체로 남는다. 이 분기에 `setPlaceEditor(null)` 을 추가해 시트를 닫고, 타임라인의 기존 인라인 `moveError` 표시가 충돌 메시지를 보여주게 둔다.

시트 부제(Task 2 (b))의 "날짜를 고르면 바로 옮겨지고…" 문구가 이 즉시 이동을 설명한다 — 성공 토스트는 백드롭 뒤에 떠서 안 보이므로 칩의 선택 상태와 Day 장소 수가 확인 수단이다.

- [ ] **Step 4: `submitPlaceEditor` 정리** — L3261-3300 블록을 다음으로 교체. Day 변경 분기는 사라지고, 시간 변경 시 같은 Day 안 재정렬만 남기되 실패를 알린다.

```tsx
/* 시간을 고쳤으면 같은 Day 안에서 알맞은 자리로 옮긴다. Day 는 시트의 칩이
   이미 옮겼다. 손으로 끌어 생긴 역전은 건드리지 않는다 — "시간 확인" 경고가 맡는다. */
const editedPlaceId = placeEditor.place.id;
let resortFailed = false;
if (placeEditor.mode === "edit" && editedPlaceId) {
  const located = findTripPlaceById(nextTrip, editedPlaceId);
  const timeChanged = (placeEditor.place.time ?? "") !== time;
  if (located && timeChanged) {
    const position = resolveTimeSortedPosition({
      places: nextTrip.days[located.dayNumber] ?? [],
      movingPlaceId: editedPlaceId,
      nextTime: time,
    });
    if (position !== located.index + 1) {
      try {
        nextTrip = await appDataApi.moveTripPlace(nextTrip.id, editedPlaceId, {
          dayNumber: located.dayNumber,
          position,
          expectedRevision: nextTrip.revision,
        });
      } catch {
        resortFailed = true; // 수정은 저장됐다. 되돌리면 방금 한 수정이 사라진다.
      }
    }
  }
}
```

그리고 성공 토스트(L3308)를:

```tsx
setNotice(resortFailed ? "장소 정보는 저장했지만 순서를 맞추지 못했어요." : "장소 정보를 수정했어요.");
```

`setActiveDay(targetDay)`/`updateDetailSearchParams` 호출은 이 블록에서 사라진다(Day 이동이 여기서 일어나지 않으므로).

- [ ] **Step 5: 시트 배선** — 렌더 L4273-4277 의 `onDayChange` 를 `onDayChange={(nextDay) => void movePlaceFromSheet(nextDay)}` 로. `PlaceEditorSheet` 에 `isMovingDay: boolean` prop 을 추가하고 Day 칩 `disabled={isSaving || isMovingDay}`; 렌더에서 `isMovingDay={Boolean(movingPlaceId)}`.

- [ ] **Step 6: 통과 확인**

Run: `cd frontend && npx vitest run src/app/__tests__/place-edit.test.tsx src/app/__tests__/trip-detail.test.tsx`
Expected: PASS. 기존 테스트 중 "저장 시 Day 가 바뀐다" 를 전제한 것이 있으면(`updateTripPlace` 뒤 `moveTripPlace` 를 기대) 새 흐름(칩 클릭 시 move)으로 고친다 — 전제가 바뀐 것이지 회귀가 아니다.

- [ ] **Step 7: 승인 요청**

---

### Task 5: 이동 후 목적지 카드 플래시 + 스크롤

**Files:**
- Modify: `ItineraryDetailPage.tsx` state(L1787 부근), `movePlaceTo`, `submitPlaceEditor` 재정렬 성공 지점, `SortablePlaceItem` props/렌더, 호출부 L4129 부근
- Modify: `frontend/src/styles/app.css` (`.place-moving-badge` 근처 L3605)
- Test: `frontend/src/app/__tests__/place-edit.test.tsx:366` 기존 이동 테스트

**Interfaces:**
- Produces: state `recentlyMovedPlaceId: string | null`, `SortablePlaceItem` prop `isRecentlyMoved: boolean`, 클래스 `timeline-slot.just-moved`.
- Consumes: Task 4 의 이동 경로.

- [ ] **Step 1: 실패 테스트** — `place-edit.test.tsx` L443-457 (`resolveFirstMove(movedUpTrip)` 뒤) 에 단언 추가:

```tsx
await waitFor(() => {
  const moved = document.querySelector(".timeline-slot.just-moved");
  expect(moved).not.toBeNull();
  expect(moved).toHaveTextContent("Cafe stop");
});
```

jsdom 에는 `scrollIntoView` 가 없고 `src/test/setup.ts` 도 폴리필하지 않는다(확인됨). 파일 상단 `beforeEach` 근처에 한 번:

```tsx
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? vi.fn();
```

- [ ] **Step 2: 실패 확인**

Run: `cd frontend && npx vitest run src/app/__tests__/place-edit.test.tsx -t "moves places with drag handles"`
Expected: FAIL — `.just-moved` 없음.

- [ ] **Step 3: 구현**

(a) state:

```tsx
const [recentlyMovedPlaceId, setRecentlyMovedPlaceId] = useState<string | null>(null);
const recentlyMovedTimerRef = useRef<number | null>(null);
const flashMovedPlace = (placeId: string) => {
  if (recentlyMovedTimerRef.current !== null) window.clearTimeout(recentlyMovedTimerRef.current);
  setRecentlyMovedPlaceId(placeId);
  recentlyMovedTimerRef.current = window.setTimeout(() => {
    setRecentlyMovedPlaceId(null);
    recentlyMovedTimerRef.current = null;
  }, PLACE_MOVED_FLASH_MS);
};
useEffect(
  () => () => {
    if (recentlyMovedTimerRef.current !== null) window.clearTimeout(recentlyMovedTimerRef.current);
  },
  [],
);
```

상수(L514-517 근처): `const PLACE_MOVED_FLASH_MS = 1600;`

(b) **시트가 덮고 있으면 플래시를 닫을 때로 미룬다.** 시트는 `max-height: min(86dvh, 720px)` 라 폰에서는 목적지 카드가 백드롭 뒤에 있다. 지금 플래시하면 타이머가 시트 뒤에서 끝나 사용자는 아무것도 못 본다.

```tsx
const pendingMovedFlashRef = useRef<string | null>(null);
const flashOrDefer = (placeId: string) => {
  const sheetCoversTimeline =
    placeEditor?.mode === "edit" && placeEditor.place.id === placeId;
  if (sheetCoversTimeline) pendingMovedFlashRef.current = placeId;
  else flashMovedPlace(placeId);
};
const releasePendingFlash = () => {
  const pending = pendingMovedFlashRef.current;
  pendingMovedFlashRef.current = null;
  if (pending) flashMovedPlace(pending);
};
```

- `movePlaceTo` 성공 분기 `setTrip(nextTrip)` 뒤: `flashOrDefer(place.id)`. (드래그·키보드 이동은 시트가 없으니 즉시 플래시된다.)
- `submitPlaceEditor` 재정렬 성공(try 안 `nextTrip = await …` 뒤): `pendingMovedFlashRef.current = editedPlaceId` (저장은 시트를 닫으므로 항상 미룬다).
- 시트가 닫히는 세 지점 — `closePlaceEditor`, `submitPlaceEditor` 의 `setPlaceEditor(null)` 뒤, `confirmDeletePlace` 의 `setPlaceEditor(null)` 뒤 — 에서 `releasePendingFlash()`. 삭제 경로는 pending 이 있어도 카드가 없어 아무 일도 안 일어난다(`isRecentlyMoved` 매칭 실패).
- Task 4 테스트의 주석 처리해 둔 두 단언(`just-moved` 없음 / 저장 후 `just-moved`)을 여기서 살린다.

(c) `SortablePlaceItem` prop `isRecentlyMoved: boolean`; className 배열에 `isRecentlyMoved ? "just-moved" : ""`; 스크롤:

```tsx
const slotRef = useRef<HTMLDivElement | null>(null);
useEffect(() => {
  if (isRecentlyMoved)
    slotRef.current?.scrollIntoView?.({ block: "center", behavior: "smooth" });
}, [isRecentlyMoved]);
```

`ref={setNodeRef}` 는 유지하고 `ref={(node) => { setNodeRef(node); slotRef.current = node; }}` 로 합친다. 호출부 L4129 부근에 `isRecentlyMoved={Boolean(place.id) && place.id === recentlyMovedPlaceId}`.

(d) CSS (`.place-moving-badge` 위):

```css
.timeline-slot.just-moved .place-detail {
  animation: placeJustMoved 1.6s ease-out;
}

@keyframes placeJustMoved {
  0% {
    box-shadow: 0 0 0 3px rgba(255, 122, 89, 0.55);
    background: #fff4ef;
  }
  100% {
    box-shadow: 0 0 0 0 rgba(255, 122, 89, 0);
    background: inherit;
  }
}
```

색은 앱의 강조색 토큰이 있으면 그것으로 바꾼다(`app.css` 상단 `:root` 확인).

- [ ] **Step 4: 통과 확인**

Run: `cd frontend && npx vitest run src/app/__tests__/place-edit.test.tsx src/app/__tests__/trip-detail.test.tsx`
Expected: PASS.

- [ ] **Step 5: 승인 요청**

---

### Task 6: 전체 게이트 + 수동 확인 목록 + 인계

**Files:**
- Create: `docs/2026-09-16-codex-handoff-itinerary-place-sheet.md`

- [ ] **Step 1: 전체 테스트**

Run: `cd frontend && npx vitest run && npm run test:mojibake && npx tsc --noEmit -p tsconfig.json`
Expected: 전부 PASS.

- [ ] **Step 2: 줄끝·diff 검사**

Run: `git diff --stat && git diff -w --stat`
Expected: 두 stat 의 파일별 +/- 가 같다.

- [ ] **Step 3: 5173 수동 확인 (사용자 또는 agent-browser)** — 목록을 인계서에 넣는다:
  1. 모바일 폭(390px): 카드 탭 → 시트 열림, 길게 눌러 드래그 → 시트 안 열림.
  2. 데스크톱: 카드 클릭 → 시트; 8px 이상 끌기 → 드래그만.
  3. 시트에서 Day 칩 → 카드가 그 Day 로 이동, 화면이 따라가고 카드가 1.6초 플래시.
  4. 시트에서 장소명 수정 → 저장 → move 호출 없음(네트워크 탭).
  5. 시트 삭제 → 확인 → 카드 사라지고 시트 닫힘.
  6. 보기 권한 계정: 카드 탭 → "장소 상세" 읽기 전용, 저장·삭제 없음.
  7. 지도 뷰 → 핀 → 상세 보기 → 같은 시트.
  8. 카드에 수정·삭제 버튼 없음. 추천 미리보기 카드는 이전과 동일.
  9. **390px 에서 시트를 연 채 타임라인이 위에 조금이라도 보이는가.** 상세 블록+Day 칩+시간+장소명+메모+버튼이 뷰포트를 다 채우면 "하단 시트를 고른 이유(타임라인 유지)" 가 무너진다 — 그러면 인계서에 적고 상세 블록을 접이식(`<details>`)으로 바꿀지 사용자에게 묻는다.
  10. 시트에서 Day 이동 → 시트 닫기 → 그때 목적지 카드가 플래시되는가.

e2e(`frontend/e2e-backend/*.spec.ts`)는 카드의 수정·삭제 버튼을 누르지 않는다(grep 확인: `연결 삭제` 는 정책 쪽) — 이 브랜치로 깨지는 spec 없음. e2e 는 실행하지 않았다고 인계서에 적는다.

- [ ] **Step 4: 인계서 작성** — 브랜치, 커밋 목록, 테스트 결과, 수동 확인 결과, e2e 미실행 여부, Codex 가 할 일(푸시·PR)을 적는다. 값이 있는 `.env` 내용은 적지 않는다.

- [ ] **Step 5: 승인 요청** — 사용자가 커밋 승인을 주면 Task 별 커밋(또는 사용자가 원하면 한 커밋)으로 만든다. 메시지 예: `feat: open place cards in an editing sheet`, `feat: move places from the sheet and flash the destination`.

---

## Self-review

- 스펙 ① 항목 대조: 카드 탭(T1) ✔, 하단 버튼 제거(T1) ✔, 시트 통합·`PlaceDetailDialog` 삭제(T2) ✔, 지도 진입 동일 시트(T2) ✔, 키보드 진입(T1 sr-only 버튼) ✔, move 단독 호출·잠수 실패 제거(T4) ✔, 플래시+스크롤(T5) ✔, `?place=` 지우는 동작 유지 ✔, 테스트 갱신 ✔.
- 스펙 밖: 보기 권한 readOnly 시트는 스펙에 없지만 `PlaceDetailDialog` 삭제로 보기 권한자의 지도 상세가 사라지는 것을 막기 위한 최소 대응이다.
- 타입 일치: `onDelete`(카드에서 제거 → 시트에 추가), `readOnly`/`place`/`isMovingDay` props 는 T2·T3·T4 에서 동일 이름. `flashMovedPlace`/`recentlyMovedPlaceId`/`isRecentlyMoved` 는 T5 에서만.
- 알려진 미확인: dnd-kit 드래그 후 click 누수는 jsdom 으로 재현이 안 돼 T1 의 `wasDraggedRef` 는 수동 확인 3·2 번에 의존한다.
