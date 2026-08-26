# 숙박세일 정책 단일 연결과 추천 미리보기 편집 정리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 숙박세일 페스타 정책은 일정당 하나만 연결되게 하고, 추천 미리보기의 시간 수정창은 한 번에 하나만 열리게 하고, `완료` 버튼 문구를 실제 동작에 맞춘다.

**Architecture:** 서로 독립적인 세 항목이다. ②는 백엔드 서비스 계층에서 막고, ③은 비제어 `<details>` 두 곳을 부모가 소유한 상태로 바꾸고, ④는 문구 한 줄이다. ③과 ④는 같은 컴포넌트 트리라 함께 다룬다.

**Tech Stack:** React 19, TypeScript, Vitest / FastAPI, SQLAlchemy, pytest

**Spec:** 없음. 사용자가 제시한 개발 항목 조사 결과에서 출발했고, 아래 "현재 동작"은 이 계획을 쓰며 코드와 DB로 직접 확인했다.

## Global Constraints

- 브랜치 `feature/trip-policy-limit-and-preview-editing`, base `develop` (`b885fd0`, PR #45 머지본).
- 프론트 기준선: 전체 스위트 `284 passed / 7 failed`. 실패 7건(`mypage` 5, `policies` 2)은 develop에서도 실패하는 기존 문제다. **이 수가 늘면 회귀다.**
- 백엔드 기준선은 Task 1 시작 전에 실측해 기록한다.
- 검증은 한 파일만 돌리지 않고 프론트 `npx vitest run` 전체, 백엔드 `pytest` 전체를 돌린다.
- push / PR / merge 금지. 커밋까지만 한다.
- 로컬 브라우저 확인은 사용자가 4173에서 수행한다.

---

## 현재 동작 (확인 완료)

### ② 숙박세일 정책이 여러 개 연결된다

`add_policy_to_trip`(`backend/app/services/trips.py:1063`)이 막는 것은 **완전히 같은 정책의 재연결**뿐이다.

```python
existing = trip_repository.get_trip_policy(db, trip_id=trip.id, policy_id=policy.id)
if existing is None:
    trip_repository.add_trip_policy(db, trip_id=trip.id, policy_id=policy.id)
    db.commit()
```

`get_trip_policy`는 `trip_id`와 `policy_id`가 모두 같은 행만 찾는다(`repositories/trips.py:149`). `TripPolicy` 테이블의 유니크 제약도 `(trip_id, policy_id)`다(`models/tables.py:428`).

그런데 숙박세일 정책은 **DB에 86개의 별도 행**으로 들어 있다.

```
source_category = 'stay_discount'  →  86건
  67  travelmonth-65                   2026 대한민국 숙박세일 페스타 숙박 할인
  68  stay-discount-gangwon-goseong    [고성] 2026 대한민국 숙박세일 페스타 숙박 할인
  69  stay-discount-gangwon-samcheok   [삼척] ...
  ... 지역별로 85건
```

각 지역이 서로 다른 `policy.id`이므로 중복 검사를 통과한다. `[고성]`과 `[강진]`을 모두 연결할 수 있다.

### ③ 시간 수정창이 여러 개 열린다

`SortablePlaceItem` 안에 비제어 `<details className="preview-time-edit">` 가 **두 곳**에 있다.

- `frontend/src/pages/itinerary/ItineraryDetailPage.tsx:4503` — 추천 후보 카드
- `frontend/src/pages/itinerary/ItineraryDetailPage.tsx:4530` — 미리보기 모드의 기존 카드

`<details>` 는 자기 열림 상태를 스스로 들고 있고 서로를 모른다. 카드마다 독립이라 여러 개가 동시에 열린다.

### ④ 버튼 문구가 동작과 다르다

`ItineraryDetailPage.tsx:3659` 의 `완료` 버튼은 `commitRecommendationPreview({ saveAllCandidates: false })` 를 부른다. **동작은 이미 선택 저장**이고 문구만 남아 있다. 바로 옆에 `전체 저장` 버튼이 있어 대비가 필요하다.

---

## 결정 사항 (승인 완료)

| 항목 | 결정 |
|---|---|
| ② | **거부하고 안내.** 백엔드가 409로 막고 프론트가 메시지를 보여준다 |
| ③ | **아코디언.** 새로 열면 기존 것이 닫힌다 |
| ④ | 문구를 **`선택 저장`** 으로. 저장 중에는 `저장 중` |

②를 프론트에서만 막지 않는 이유는, API를 직접 부르면 여전히 들어가기 때문이다. 백엔드가 진짜 경계다. 프론트 사전 차단은 이번에 넣지 않는다 — 백엔드 거부와 안내 메시지로 충분하고, 두 곳에 규칙을 두면 어긋날 여지가 생긴다.

---

## File Structure

| 파일 | 책임 | 변경 |
|---|---|---|
| `backend/app/services/trips.py` | 숙박세일 단일 연결 규칙 | Modify (Task 1) |
| `backend/tests/test_trip_db_service.py` | 규칙 테스트 | Modify (Task 1) |
| `frontend/src/pages/itinerary/ItineraryDetailPage.tsx` | 시간 편집창 상태, 버튼 문구 | Modify (Task 2·3) |
| `frontend/src/app/__tests__/trip-detail.test.tsx` | 순수 함수·소스 핀 | Modify (Task 2·3) |

`stay_discount_aliases.SOURCE_CATEGORY`("stay_discount")를 판별 기준으로 재사용한다. 새 상수를 만들지 않는다.

---

## Task 1: 숙박세일 정책은 일정당 하나만 (②)

**Files:**
- Modify: `backend/app/services/trips.py` — `add_policy_to_trip` (`:1063`)
- Test: `backend/tests/test_trip_db_service.py`

**Interfaces:**
- Consumes: `stay_discount_aliases.SOURCE_CATEGORY`, `trip.policies` (TripPolicy 목록)
- Produces: `TripServiceError(409, "Trip already has a stay discount policy")`

- [ ] **Step 1: 백엔드 기준선 실측**

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q
```

통과/실패 수를 적어둔다. **이 수가 늘면 회귀다.**

- [ ] **Step 2: 실패 테스트 작성**

`backend/tests/test_trip_db_service.py` 의 `test_add_policy_to_trip_rejects_hidden_policy_slug_in_db_path` 바로 뒤에 넣는다. 같은 파일의 기존 패턴(`sqlite_db_session` 픽스처, `make_user`, 모델 직접 생성)을 그대로 따른다.

```python
def test_add_policy_to_trip_rejects_a_second_stay_discount_area(sqlite_db_session) -> None:
    # 숙박세일 페스타는 지역마다 별도 정책 행이라 policy_id 중복 검사를 통과한다.
    # 일정 하나에는 지역 하나만 붙어야 한다.
    user = make_user(80, "Stay Discount User")
    goseong = Policy(
        id=810,
        slug="stay-discount-gangwon-goseong",
        title="[고성] 2026 대한민국 숙박세일 페스타 숙박 할인",
        benefit_detail="최대 7만원",
        region="강원",
        status="active",
        source_category="stay_discount",
    )
    samcheok = Policy(
        id=811,
        slug="stay-discount-gangwon-samcheok",
        title="[삼척] 2026 대한민국 숙박세일 페스타 숙박 할인",
        benefit_detail="최대 7만원",
        region="강원",
        status="active",
        source_category="stay_discount",
    )
    trip = Trip(
        id=812,
        owner_id=user.id,
        title="Stay discount trip",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        region="강원",
        status="draft",
    )
    sqlite_db_session.add_all([user, goseong, samcheok, trip])
    sqlite_db_session.commit()

    trip_service.add_policy_to_trip(
        sqlite_db_session, user, str(trip.id), "stay-discount-gangwon-goseong"
    )
    assert sqlite_db_session.query(TripPolicy).count() == 1

    with pytest.raises(trip_service.TripServiceError) as error:
        trip_service.add_policy_to_trip(
            sqlite_db_session, user, str(trip.id), "stay-discount-gangwon-samcheok"
        )

    assert error.value.status_code == 409
    assert error.value.detail == "Trip already has a stay discount policy"
    assert sqlite_db_session.query(TripPolicy).count() == 1


def test_add_policy_to_trip_allows_re_adding_the_same_stay_discount_area(
    sqlite_db_session,
) -> None:
    # 같은 지역을 다시 누르는 것은 오류가 아니다. 기존처럼 조용히 넘어간다.
    user = make_user(81, "Same Area User")
    goseong = Policy(
        id=820,
        slug="stay-discount-gangwon-goseong",
        title="[고성] 2026 대한민국 숙박세일 페스타 숙박 할인",
        benefit_detail="최대 7만원",
        region="강원",
        status="active",
        source_category="stay_discount",
    )
    trip = Trip(
        id=821,
        owner_id=user.id,
        title="Same area trip",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        region="강원",
        status="draft",
    )
    sqlite_db_session.add_all([user, goseong, trip])
    sqlite_db_session.commit()

    trip_service.add_policy_to_trip(
        sqlite_db_session, user, str(trip.id), "stay-discount-gangwon-goseong"
    )
    trip_service.add_policy_to_trip(
        sqlite_db_session, user, str(trip.id), "stay-discount-gangwon-goseong"
    )

    assert sqlite_db_session.query(TripPolicy).count() == 1


def test_add_policy_to_trip_allows_a_non_stay_discount_policy_alongside(
    sqlite_db_session,
) -> None:
    # 규칙은 숙박세일에만 걸린다. 다른 종류는 여러 개 붙을 수 있어야 한다.
    user = make_user(82, "Mixed Policy User")
    goseong = Policy(
        id=830,
        slug="stay-discount-gangwon-goseong",
        title="[고성] 2026 대한민국 숙박세일 페스타 숙박 할인",
        benefit_detail="최대 7만원",
        region="강원",
        status="active",
        source_category="stay_discount",
    )
    other = Policy(
        id=831,
        slug="local-half-trip-gangwon",
        title="강원 반값여행",
        benefit_detail="최대 20만원 환급",
        region="강원",
        status="active",
        source_category="local_half_trip",
    )
    trip = Trip(
        id=832,
        owner_id=user.id,
        title="Mixed policy trip",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        region="강원",
        status="draft",
    )
    sqlite_db_session.add_all([user, goseong, other, trip])
    sqlite_db_session.commit()

    trip_service.add_policy_to_trip(
        sqlite_db_session, user, str(trip.id), "stay-discount-gangwon-goseong"
    )
    trip_service.add_policy_to_trip(
        sqlite_db_session, user, str(trip.id), "local-half-trip-gangwon"
    )

    assert sqlite_db_session.query(TripPolicy).count() == 2
```

- [ ] **Step 3: 빨간 것 확인**

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/test_trip_db_service.py -k "stay_discount_area or stay_discount_alongside" -q
```

기대: 첫 번째 테스트가 FAIL (`DID NOT RAISE` 또는 `count() == 2`). 나머지 둘은 현재도 통과한다 — 회귀 방지용이다.

**빨간 것을 눈으로 확인하지 않고 다음 단계로 넘어가지 않는다.**

- [ ] **Step 4: 규칙 구현**

`add_policy_to_trip` 의 중복 검사 바로 뒤에 넣는다.

```python
    existing = trip_repository.get_trip_policy(db, trip_id=trip.id, policy_id=policy.id)
    if existing is None:
        # 숙박세일 페스타는 지역마다 정책 행이 따로 있어 policy_id 검사를 통과한다.
        # 일정 하나에는 지역 하나만 붙는다.
        if (policy.source_category or "") == stay_discount_aliases.SOURCE_CATEGORY:
            for link in trip.policies:
                linked = link.policy
                if linked is None:
                    continue
                if (linked.source_category or "") == stay_discount_aliases.SOURCE_CATEGORY:
                    raise TripServiceError(
                        409, "Trip already has a stay discount policy"
                    )
        trip_repository.add_trip_policy(db, trip_id=trip.id, policy_id=policy.id)
        db.commit()
```

같은 지역을 다시 누르면 `existing` 이 있어 이 블록에 들어오지 않는다. 기존처럼 조용히 성공한다.

`trip.policies` 관계 이름과 `link.policy` 접근이 실제 모델과 맞는지 `backend/app/models/tables.py` 의 `Trip` / `TripPolicy` 정의로 확인한 뒤 쓴다. 다르면 `db.query(TripPolicy).join(Policy)` 로 조회하는 방식으로 바꾼다.

- [ ] **Step 5: 초록 확인**

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/test_trip_db_service.py -k "stay_discount" -q
```

기대: 전부 PASS.

- [ ] **Step 6: 프론트 안내 문구 확인**

프론트가 409를 어떻게 보여주는지 확인한다.

```bash
cd frontend
grep -rn "addPolicyToTrip" src/ --include=*.tsx --include=*.ts | grep -v test
```

호출부의 `catch` 가 서버 메시지를 그대로 노출하는지, 고정 문구로 덮는지 본다. 고정 문구라면 **409일 때만** 한글 안내를 보여주도록 분기를 넣는다.

> 숙박세일 페스타 정책은 일정당 하나만 연결할 수 있어요. 기존 정책을 먼저 해제해 주세요.

분기를 넣는다면 그 자리에도 실패 테스트를 먼저 쓴다.

---

## Task 2: 시간 수정창은 한 번에 하나만 (③)

`<details>` 는 자기 열림 상태를 스스로 들고 있다. 아코디언으로 만들려면 **부모가 열린 카드를 하나 기억**해야 한다.

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
  - `ItineraryDetailPage` 에 열린 카드 상태 추가
  - `SortablePlaceItem` 에 prop 두 개 추가, `<details>` 두 곳을 제어형으로
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

**Interfaces:**
- Produces:
  ```ts
  export function resolveNextOpenTimeEditorId(
    currentOpenId: string | null,
    toggledId: string,
    willOpen: boolean,
  ): string | null
  ```
  아코디언 규칙. 열면 그 id만 남고, 닫으면 `null`.

- [ ] **Step 1: 실패 테스트 작성**

import 블록에 `resolveNextOpenTimeEditorId` 를 추가하고, `it("pins the timeline height so a day switch cannot shrink the document", ...)` 바로 앞에 넣는다.

```tsx
  it("keeps only one preview time editor open at a time", () => {
    // <details>는 서로를 모른다. 부모가 열린 카드 하나를 기억해야 아코디언이 된다.
    expect(resolveNextOpenTimeEditorId(null, "place:a", true)).toBe("place:a");
    expect(resolveNextOpenTimeEditorId("place:a", "place:b", true)).toBe(
      "place:b",
    );
  });

  it("closes the preview time editor when the open one is toggled shut", () => {
    expect(resolveNextOpenTimeEditorId("place:a", "place:a", false)).toBeNull();
    // 이미 닫힌 다른 카드를 닫는 신호가 와도 열린 것을 건드리지 않는다.
    expect(resolveNextOpenTimeEditorId("place:a", "place:b", false)).toBe(
      "place:a",
    );
  });
```

- [ ] **Step 2: 빨간 것 확인**

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "preview time editor"
```

기대: FAIL, `resolveNextOpenTimeEditorId is not a function`.

- [ ] **Step 3: 순수 함수 구현**

`displayedPlaceWarningKey`(`:1352`) 바로 앞에 넣는다.

```ts
/**
 * 추천 미리보기의 시간 수정창은 한 번에 하나만 열린다. `<details>`는 자기
 * 열림 상태를 스스로 들고 서로를 모르므로, 부모가 열린 카드 하나를 기억한다.
 *
 * 닫는 신호는 그 카드가 실제로 열려 있을 때만 반영한다. 그렇지 않으면
 * 브라우저가 다른 카드에 보내는 닫힘 신호가 열린 창을 꺼버린다.
 */
export function resolveNextOpenTimeEditorId(
  currentOpenId: string | null,
  toggledId: string,
  willOpen: boolean,
): string | null {
  if (willOpen) return toggledId;
  return currentOpenId === toggledId ? null : currentOpenId;
}
```

- [ ] **Step 4: 초록 확인**

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "preview time editor"
```

기대: PASS (2).

- [ ] **Step 5: 소스 핀 작성**

`it("installs a non-passive window wheel bridge for desktop gutters", ...)` 안에 넣는다. 함수 정의가 아니라 **호출부**를 본다.

```tsx
    // 시간 수정창 아코디언은 부모가 열린 카드를 하나 들고 있어야 성립한다.
    expect(source).toContain("resolveNextOpenTimeEditorId(");
    expect(source).toContain("openTimeEditorId");
```

기대: 먼저 FAIL.

- [ ] **Step 6: 부모 상태와 prop 배선**

`ItineraryDetailPage` 안, `draggingPlaceId` 상태 근처에 넣는다.

```ts
  const [openTimeEditorId, setOpenTimeEditorId] = useState<string | null>(null);
```

미리보기가 끝나면 남지 않게 정리한다. `commitRecommendationPreview` 와 `cancelRecommendationPreview` 가 미리보기를 닫는 지점에서 `setOpenTimeEditorId(null)` 을 부른다.

`SortablePlaceItem` 호출부에 prop 두 개를 넘긴다. 카드 식별자는 이미 있는 `displayedPlaceWarningKey(place)` 를 쓴다 — `place.id ?? place.previewTimelineId` 라 미리보기 카드와 기존 카드 모두 값이 있다.

```tsx
                  openTimeEditorId={openTimeEditorId}
                  onToggleTimeEditor={(cardId, willOpen) =>
                    setOpenTimeEditorId((current) =>
                      resolveNextOpenTimeEditorId(current, cardId, willOpen),
                    )
                  }
```

`SortablePlaceItem` 의 prop 목록과 타입에 추가한다.

```ts
  openTimeEditorId: string | null;
  onToggleTimeEditor: (cardId: string, willOpen: boolean) => void;
```

- [ ] **Step 7: `<details>` 두 곳을 제어형으로**

`:4503` 과 `:4530` 두 곳을 같은 모양으로 바꾼다. 카드 식별자를 못 구하면(둘 다 null) 기존처럼 비제어로 둔다 — 아코디언이 안 될 뿐 열리지 않는 것보다 낫다.

```tsx
            <details
              className="preview-time-edit"
              aria-label={`${place.label} 시간 수정`}
              open={timeEditorCardId ? openTimeEditorId === timeEditorCardId : undefined}
              onToggle={(event) => {
                if (!timeEditorCardId) return;
                onToggleTimeEditor(
                  timeEditorCardId,
                  (event.currentTarget as HTMLDetailsElement).open,
                );
              }}
            >
```

컴포넌트 본문 위쪽에서 한 번 계산한다.

```ts
  const timeEditorCardId = displayedPlaceWarningKey(place);
```

- [ ] **Step 8: 초록 확인**

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "wheel bridge"
```

기대: PASS.

---

## Task 3: `완료` 문구를 `선택 저장` 으로 (④)

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx` (`:3659`)
- Test: `frontend/src/app/__tests__/trip-detail.test.tsx`

- [ ] **Step 1: 실패 테스트 작성**

`wheel bridge` 테스트에 넣는다.

```tsx
    // 동작은 이미 선택 저장인데 문구만 완료로 남아 있었다.
    expect(source).toContain('"저장 중" : "선택 저장"');
    expect(source).not.toMatch(/>\s*완료\s*</);
```

- [ ] **Step 2: 빨간 것 확인**

```bash
cd frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx -t "wheel bridge"
```

기대: FAIL.

- [ ] **Step 3: 문구 변경**

`:3651~3660` 의 버튼을 바꾼다. 옆의 `전체 저장` 버튼이 저장 중에 `저장 중` 으로 바뀌므로 같은 형태로 맞춘다.

```tsx
          <button
            className="btn sm line"
            type="button"
            disabled={recommendationPreview.status === "saving"}
            onClick={() =>
              void commitRecommendationPreview({ saveAllCandidates: false })
            }
          >
            {recommendationPreview.status === "saving" ? "저장 중" : "선택 저장"}
          </button>
```

- [ ] **Step 4: 초록 확인** — Step 2와 같은 명령. 기대: PASS.

`완료` 라는 문구를 쓰는 다른 테스트가 있으면 함께 갱신한다.

```bash
cd frontend
grep -rn '완료' src/app/__tests__/*.tsx | head
```

---

## Task 4: 전체 검증과 커밋

- [ ] **Step 1: 백엔드 전체**

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q
```

기대: Task 1 Step 1에서 적어둔 기준선 + 신규 3개. **실패 수가 늘면 회귀다.**

- [ ] **Step 2: 프론트 전체**

```bash
cd frontend
npx vitest run
npm.cmd run typecheck
npm.cmd run build
npm.cmd run test:mojibake
```

기대: `288 passed / 7 failed` (기준선 284 + Task 2의 2개 + Task 3·1의 핀은 기존 테스트에 단언만 추가). **정확한 수는 실측으로 확정하고, 중요한 것은 FAIL이 7을 넘지 않는 것이다.**

- [ ] **Step 3: 커밋**

`git status --short` 로 의도한 파일만 바뀌었는지 확인한 뒤 stage 한다. `dist`, `.env`, `node_modules`, `.venv` 는 stage 하지 않는다.

```bash
git add backend/app/services/trips.py \
        backend/tests/test_trip_db_service.py \
        frontend/src/pages/itinerary/ItineraryDetailPage.tsx \
        frontend/src/app/__tests__/trip-detail.test.tsx \
        docs/superpowers/plans/2026-08-26-trip-policy-limit-and-preview-editing.md
git diff --check
git commit
```

커밋 메시지는 세 항목을 각각 설명한다. 백엔드와 프론트가 한 커밋에 섞이지만, 세 항목 모두 "추천/정책 연결 다듬기"라는 하나의 요청에서 나왔고 서로 참조하지 않으므로 나눌 실익이 적다. 코덱스가 원하면 그때 쪼갠다.

---

## 브라우저 확인 (사용자, 4173)

### ② 숙박세일

1. 일정에 숙박세일 정책 하나를 연결한다
2. **다른 지역** 숙박세일을 연결하려 하면 거부되고 안내가 뜨는가
3. **같은 지역**을 다시 누르면 오류 없이 조용히 넘어가는가
4. 숙박세일이 아닌 정책(반값여행, 디지털관광주민증 등)은 **여러 개 연결되는가**
5. 기존 숙박세일을 해제한 뒤에는 다른 지역이 연결되는가

### ③ 시간 수정창

6. 추천 미리보기에서 카드 A의 `수정`을 열고 카드 B의 `수정`을 누르면 **A가 닫히는가**
7. 열려 있는 카드의 `수정`을 다시 누르면 닫히는가
8. 미리보기를 취소하거나 저장한 뒤 다시 열었을 때 **열린 창이 남아 있지 않은가**
9. 시간을 실제로 바꿔 저장했을 때 반영되는가

### ④ 버튼

10. 버튼 문구가 `선택 저장` 인가
11. 저장 중에 `저장 중` 으로 바뀌는가
12. 옆의 `전체 저장` 과 동작이 여전히 구분되는가 (선택한 것만 / 전부)

---

## 열린 위험

**Task 1의 `trip.policies` 관계 접근** — 모델 정의를 확인하고 쓰기로 했으나, 지연 로딩 설정에 따라 `link.policy` 가 추가 쿼리를 부를 수 있다. 정책 수가 적어 성능 문제는 아니지만, 관계가 없으면 명시적 조인으로 바꿔야 한다. Step 4에서 확인한다.

**Task 2의 `onToggle` 이벤트** — React의 `onToggle` 은 브라우저가 `<details>` 를 여닫을 때마다 발생한다. 제어형으로 만들면 `open` prop 변경 → 브라우저 토글 → `onToggle` → 상태 변경의 순환이 생길 수 있다. 순수 함수가 "닫는 신호는 그 카드가 실제로 열려 있을 때만 반영"하도록 만든 것이 그 방어다. 브라우저에서 6·7번을 반복해 확인한다.

**`완료` 문구를 쓰는 다른 곳** — Task 3 Step 4에서 테스트를 훑지만, 화면의 다른 `완료` 버튼(날짜 편집 시트 등)까지 바꾸지 않도록 주의한다. 바꾸는 것은 추천 미리보기 액션 바의 버튼 하나뿐이다.

## 되돌리기

한 커밋이므로 `git revert` 로 되돌린다. 백엔드는 조건 추가, 프론트는 상태 추가와 문구 변경뿐이라 스키마나 API 계약 변경이 없다.

---

## 구현 결과 (as-built)

### 전임자 계획과의 관계 — 충돌 없음

구현 전에 `2026-08-18-stay-discount-policy-identity.md`(전임자 `hoyoung94` 작성)를 확인했다. Task 4 제목이 "Make Trip Linking Return One Area Policy Card" 라 방향이 반대인가 싶었으나, 그것은 **연결 하나당 카드 하나를 반환**하라는 뜻이다.

> Produces: `Trip.linkedPolicies[]` contains exactly one item for the attached area policy slug.

문서 전체에 "일정당 숙박세일 하나만"에 대한 결정은 없다. "하나만 / 중복 / 여러 개 / 제한" 어느 표현도 나오지 않고 Remaining Risks에도 없다. 전임자는 지역 정책을 **일반 정책과 동일한 실제 행**으로 만드는 데 집중했고 개수 제한은 범위 밖이었다. 이번 규칙은 그 위에 얹는 것이지 되돌리는 것이 아니다.

### 기준선 (실측)

```
백엔드   669 passed / 1 failed / 22 skipped
         실패 1건은 test_stay_discount_semantics_snapshot.py 의 기존 문제
프론트   284 passed / 7 failed
```

### Task 1 — 계획에서 바뀐 점 둘

**`trip.policies` 관계 접근이 통하지 않았다.** 관계 자체는 존재하지만(`Trip.policies` → `TripPolicy.policy`), 같은 세션에서 방금 커밋한 링크가 컬렉션에 반영되지 않아 두 번째 호출에서 빈 목록을 봤다. 첫 구현은 `DID NOT RAISE` 로 계속 실패했다.

계획에 적어둔 대비책대로 명시적 조회로 바꿨다. 서비스에서 직접 쿼리하지 않고 저장소 계층에 함수를 하나 추가해 기존 구조를 따랐다.

```python
# backend/app/repositories/trips.py
def has_trip_policy_in_source_category(
    db: Session, *, trip_id: int, source_category: str
) -> bool:
```

**`FakeDb` 테스트 더블을 보강해야 했다.** `test_add_policy_to_trip_uses_stay_discount_area_policy` 가 쓰는 더블에 `scalar` 가 없어 `AttributeError` 로 깨졌다. 그 테스트의 관심사(지역 정책 id 사용)와 무관하므로 `scalar` 가 `None` 을 돌려주도록 더했다 — "아직 붙은 것이 없다"로 두어 원래 보던 경로가 그대로 흐른다.

**프론트 안내 문구는 좋은 자리가 이미 있었다.** `PolicyPages.tsx` 의 `policyTripErrorMessage` 가 서버 메시지별로 한글 안내를 매핑하고 있어 분기 한 줄만 더했다. 테스트를 위해 `export` 로 바꿨다.

### Task 2 — 계획대로

`resolveNextOpenTimeEditorId` 추가, `openTimeEditorId` 상태 추가, `<details>` 두 곳 제어형 전환. 미리보기가 닫히는 두 지점(commit 성공, cancel)에서 `setOpenTimeEditorId(null)` 로 정리한다.

카드 식별자는 계획대로 기존 `displayedPlaceWarningKey(place)` 를 재사용했다.

### Task 3 — 계획대로

`완료` → `{recommendationPreview.status === "saving" ? "저장 중" : "선택 저장"}`.

바꾸기 전에 `완료` 를 쓰는 다른 곳을 확인했다. `FriendInvitePage` 의 "함께 편집 링크 준비 완료", `ItineraryCreatePage` 의 "선택 완료" 는 다른 문자열이고, 이 문구에 의존하는 테스트도 없다. 바꾼 것은 추천 미리보기 액션 바의 버튼 하나뿐이다.

### 최종 검증

```
백엔드   672 passed / 1 failed / 22 skipped   (기준선 669 + 신규 3, 실패 동일)
프론트   (Task 4에서 실측)
```

### Task 3에서 낸 회귀 (수정 완료)

`완료` → `선택 저장` 으로 바꾼 뒤 전체 스위트가 `FAIL 12` 로 나왔다. 기준선 7에서 5개 늘었다.

원인은 확인 방식이었다. 바꾸기 전에 `grep -rn '완료' src/app/__tests__/*.tsx | head -5` 로 훑고 "이 문구에 의존하는 테스트 없음"이라고 판단했는데, `head -5` 에 `auth`·`home` 만 걸리고 `trip-detail` 이 잘렸다. 실제로는 **7곳이 `getByRole("button", { name: "완료" })` 로 버튼을 찾고 있었다.**

계획서 Task 3 Step 4에 "다른 테스트가 있으면 함께 갱신한다"고 적어두고도 확인을 대충 했다. 선택자 7곳을 `"선택 저장"` 으로 갱신해 해소했다.

**교훈:** 문자열을 바꾸기 전 사용처 조사에 `head` 를 쓰지 않는다. 개수를 세거나 전부 출력한다.

### 로컬 런타임 연결

구현 후 사용자가 "여전히 숙박세일이 여러 개 담긴다"고 보고했다. 코드 문제가 아니라 **실행 중인 백엔드 컨테이너가 develop 이미지**였다.

```
docker exec ... grep -c "Trip already has a stay discount policy"  →  0건
```

컨테이너는 빌드 시점 소스를 복사해 독립 실행되므로 worktree 수정이 반영되지 않는다. compose의 빌드 컨텍스트는 루트라 `compose build` 로도 worktree 코드가 들어가지 않는다. 이미지를 직접 굽고 교체했다.

```bash
docker build -t travel-hunter-onprem-backend <worktree>/backend
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml up -d --no-build backend
```

4173 preview도 이 브랜치로 재기동했다. 이후 사용자가 정상 동작을 확인했다.

### 최종 검증

```
백엔드   672 passed / 1 failed / 22 skipped   기준선 669 + 신규 3, 실패 동일
프론트   288 passed / 7 failed                기준선 284 + 신규 4, 실패 동일
typecheck / build / mojibake                  전부 통과
브라우저 (4173)                                사용자 확인 완료
```

실패는 백엔드 `test_stay_discount_semantics_snapshot.py` 1건, 프론트 `mypage` 5건 + `policies` 2건이다. 모두 develop에서도 실패하는 기존 문제다.

---

## Task 5: 동시 요청에서 규칙이 깨지는 문제 (리뷰 지적)

코덱스 리뷰에서 Important 1건이 나왔다. 타당한 지적이다.

### 문제

`add_policy_to_trip` 은 **확인 후 삽입(TOCTOU)** 구조다.

```python
if 숙박세일이고 has_trip_policy_in_source_category(...):   # 확인
    raise TripServiceError(409, ...)
trip_repository.add_trip_policy(...)                        # 삽입
db.commit()
```

서로 다른 숙박세일 정책을 동시에 요청하면 두 요청이 모두 "기존 없음"을 보고 각각 삽입할 수 있다. DB 제약도 `(trip_id, policy_id)` 뿐이라 서로 다른 정책 두 개를 막지 못한다.

### 왜 유니크 제약이 아니라 행 잠금인가

DB 제약으로 막는 편이 근본적이다. `trip_policies` 에 숙박세일일 때만 값이 들어가는 열을 두고 `(trip_id, 그 열)` 에 유니크를 걸면 경쟁 자체가 불가능해진다.

**그런데 지금 쓸 수 없다.** 이 규칙 이전에 만들어진 일정 중 이미 숙박세일이 여러 개 담긴 것이 있다. 유니크 제약을 추가하는 마이그레이션이 그 데이터에서 실패한다. 먼저 데이터 정리 마이그레이션이 필요한데 어느 지역을 남길지는 제품 결정이라 이번 범위 밖이다.

따라서 **행 잠금**으로 간다. 스키마 변경이 없고 기존 데이터를 건드리지 않는다.

### 테스트가 SQLite에서 무의미하다는 점

확인 결과 **SQLite는 `FOR UPDATE` 를 조용히 생략한다.** 오류도 내지 않는다.

```
compiled: SELECT trips.id, ... FROM trips WHERE trips.id = ?
```

기존 `sqlite_db_session` 픽스처로 두 세션 동시 요청 테스트를 쓰면 잠금이 걸리지 않아 둘 다 성공한다. 통과하지 않는 테스트를 남기거나, 더 나쁘게는 잠금이 동작한다고 착각하게 만든다.

저장소에 이미 **환경변수로 게이트되는 Postgres 테스트** 패턴이 있다(`test_source_provenance_migration_postgres.py`, `test_stay_discount_semantics_migration_postgres.py`).

```python
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_MIGRATION_TESTS") != "1",
    reason="...",
)
```

동시성 테스트는 이 패턴을 따른다. 기본 실행에서는 건너뛰고, 환경변수를 켜면 로컬 Postgres 컨테이너로 진짜 경쟁을 재현한다.

### 결정

| 항목 | 결정 |
|---|---|
| 잠금 | `SELECT ... FOR UPDATE` 로 Trip 기본 행만 잠근다 |
| 위치 | 저장소 계층에 전용 함수. 접근 권한 조회는 eager-load가 섞여 있어 그 경로로 잠그지 않는다 |
| 재확인 | 잠금 획득 후 동일 정책 존재와 숙박세일 존재를 **다시** 본다 |
| 테스트 | Postgres 게이트 동시성 테스트 + SQLite에서도 도는 구조 테스트 |

### 작업

**Files:**
- Modify: `backend/app/repositories/trips.py` — 잠금 함수 추가
- Modify: `backend/app/services/trips.py` — `add_policy_to_trip` 순서 조정
- Create: `backend/tests/test_trip_policy_concurrency_postgres.py`
- Modify: `backend/tests/test_trip_db_service.py` — 잠금 호출 구조 테스트

**Interfaces:**
- Produces:
  ```python
  def lock_trip_row(db: Session, *, trip_id: int) -> None
  ```
  Trip 기본 행만 `FOR UPDATE` 로 잠근다. 관계를 함께 읽지 않는다.

- [ ] **Step 1: 동시성 회귀 테스트 작성 (Postgres 게이트)**

`backend/tests/test_trip_policy_concurrency_postgres.py` 를 새로 만든다. 두 개의 독립 세션에서 같은 일정에 서로 다른 숙박세일 정책을 연결하고, 한 건만 성공하고 다른 한 건은 409가 되는지 본다.

- [ ] **Step 2: 빨간 것 확인**

```bash
cd backend
set RUN_POSTGRES_CONCURRENCY_TESTS=1
.venv/Scripts/python.exe -m pytest tests/test_trip_policy_concurrency_postgres.py -q
```

기대: FAIL — 잠금이 없어 두 건 모두 삽입된다.

- [ ] **Step 3: 잠금 함수 추가**

```python
def lock_trip_row(db: Session, *, trip_id: int) -> None:
    """Trip 기본 행만 FOR UPDATE 로 잠근다.

    접근 권한 조회는 eager-load 가 섞여 있어 잠금 대상으로 쓰기에 위험하다.
    관계를 건드리지 않는 최소 조회로 잠근다. SQLite 는 FOR UPDATE 를 조용히
    생략하므로 단위 테스트에서는 no-op 이다.
    """
    db.execute(select(Trip.id).where(Trip.id == trip_id).with_for_update())
```

- [ ] **Step 4: 서비스에서 잠금 후 재확인**

`add_policy_to_trip` 에서 정책을 찾은 직후, 존재 확인 **전에** 잠근다.

```python
    trip_repository.lock_trip_row(db, trip_id=trip.id)
    existing = trip_repository.get_trip_policy(db, trip_id=trip.id, policy_id=policy.id)
```

잠금 이후의 확인은 이미 재확인이다. 잠금을 얻을 때까지 다른 트랜잭션은 커밋을 마치지 못하므로, 뒤에 온 요청은 앞의 결과를 본다.

- [ ] **Step 5: 초록 확인**

Step 2와 같은 명령. 기대: 한 건 성공, 한 건 409.

- [ ] **Step 6: 구조 테스트 추가**

Postgres 게이트가 꺼진 기본 실행에서도 잠금이 호출되는지 확인한다. `test_trip_db_service.py` 에 `FakeDb` 를 쓰는 테스트를 더해, `add_policy_to_trip` 이 `lock_trip_row` 를 부르는지 본다.

- [ ] **Step 7: 전체 검증 후 `--amend`**

```bash
cd backend && .venv/Scripts/python.exe -m pytest -q
cd ../frontend && npx vitest run && npm.cmd run typecheck && npm.cmd run build && npm.cmd run test:mojibake
```

기존 커밋 `02fb83d` 에 `--amend` 로 흡수하고 새 SHA를 전달한다. push 하지 않는다.

### Task 5 구현 결과

경쟁 조건이 **실제로 재현됐다.** 잠금 없이 두 세션을 동시에 돌리면 둘 다 성공한다.

```
{'first': 'added', 'second': 'added'}
```

`lock_trip_row` 추가 후 한 건만 성공하고 다른 한 건은 409가 된다.

**검증 구성**

| 테스트 | 실행 조건 | 검증 대상 |
|---|---|---|
| `test_trip_policy_concurrency_postgres.py` | `RUN_POSTGRES_CONCURRENCY_TESTS=1` | 진짜 경쟁. 두 스레드가 `threading.Barrier` 로 같은 지점에서 출발 |
| `test_add_policy_to_trip_locks_the_trip_row_before_checking` | 항상 | 잠금이 확인보다 **먼저** 불리는지. SQLite 라 잠금 자체는 no-op 이므로 순서만 고정 |

기본 실행에서 Postgres 테스트는 skip 된다(`673 passed / 1 failed / 23 skipped`). 로컬 db 컨테이너가 떠 있을 때 환경변수로 켜서 확인했다.

**최종 검증**

```
백엔드   673 passed / 1 failed / 23 skipped   (Task 4 시점 672 + 구조 테스트 1)
백엔드   동시성 테스트 1 passed               (RUN_POSTGRES_CONCURRENCY_TESTS=1)
프론트   288 passed / 7 failed                (변동 없음)
typecheck / build / mojibake                  전부 통과
```

프론트를 한 번 `285 / 10` 으로 본 적이 있는데, 그 실행 도중 내가 백엔드 컨테이너를 재빌드·재시작해 라우트 테스트가 8000 에 닿지 못한 탓이었다. 백엔드가 안정된 뒤 다시 돌려 `288 / 7` 로 복귀했다. **검증 실행 중에는 런타임을 건드리지 않는다.**
