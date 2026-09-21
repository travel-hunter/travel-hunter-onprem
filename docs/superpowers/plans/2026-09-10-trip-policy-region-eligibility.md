# Trip Policy Region Eligibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent a trip from newly linking a localized policy outside its selected travel area, while preserving valid same-area and truly nationwide policy links.

**Architecture:** Make the backend the single authority for policy-to-trip geographic eligibility. Reuse the existing travel-area locality matcher that powers recommendations, but adapt one policy (including stay-discount alias slugs) into the same candidate shape before a link is created. Apply that guard both to the existing-trip attach route and the policy preselection path used while creating a trip; the frontend must only display the server’s rejection reason rather than maintain a second, lossy location-matching implementation.

**Tech Stack:** FastAPI, SQLAlchemy/PostgreSQL, Pydantic API contract, React/TypeScript, Vitest, pytest.

**Spec:** `docs/mvp-api-contract.md` — `POST /trips/{trip_id}/policies/{policy_slug}`, trip `recommendedPolicies`, and trip creation with `policySlug`.

## Global Constraints

- Keep API DTO names camelCase and database names snake_case.
- Keep `/api/trips/{trip_id}/policies/{policy_slug}` as the only attach API; no new endpoint or schema migration is needed.
- The backend is authoritative: UI code must not infer a policy city from display title or duplicate travel-area matching rules.
- A localized policy is attachable only when its normalized locality matches the trip’s selected `travelAreaId`; a `whole:` area may accept localized policies within that same `sido`.
- A truly nationwide policy (`region == "전국"` and no explicit locality in its candidate terms) remains attachable. A policy that says `전국` but explicitly names another municipality is still localized and must match that municipality.
- A legacy trip without a resolvable `travelAreaId` may attach only a truly nationwide policy; it must be edited to choose a travel area before adding a localized policy. This is fail-closed because a broad text region cannot safely distinguish distant municipalities.
- Preserve existing behavior: the same already-linked policy is idempotent, different policy categories may coexist when each is geographically eligible, and only `stay_discount` keeps its existing one-per-trip source-category limit.
- Do not delete, hide, or migrate existing `trip_policies`; this change governs new links only.
- Do not modify crawler, policy-collection, policy-photo, database schema, or unrelated worktree files.
- Do not update `CHECKLIST.md` until this branch is ready to merge.
- Tests must cover the rejection before implementation, and changed Korean files must remain UTF-8-clean with no `U+FFFD`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `backend/app/services/trips.py` | Converts a resolved policy to geographic candidate data, decides attach eligibility, validates both link-creation paths, and retains recommendation behavior. |
| `backend/tests/test_trip_db_service.py` | Locks geographic attach behavior with SQLite-backed service tests, including aliases, legacy trips, and no partial creation. |
| `docs/mvp-api-contract.md` | Documents the new `409` response and its geographic eligibility semantics. |
| `frontend/src/pages/PolicyPages.tsx` | Maps the authoritative geographic rejection detail to actionable Korean copy while keeping the trip picker open for another choice. |
| `frontend/src/app/__tests__/policies.test.tsx` | Verifies the message mapping and failed picker flow. |

## Eligibility Contract

1. Resolve the requested slug before deciding eligibility. For a stay-discount alias, use `StayDiscountAliasArea.sido` and `.city`, not the canonical source row’s broad campaign region.
2. Build candidate locality terms with `Policy.city` first, falling back to the linked `ExternalSourceRecord.city` only when `Policy.city` is empty. This keeps materialized policy data usable without an additional lookup and supports future collectors.
3. For a trip whose `travelAreaId` resolves to a city or curated multi-city area, the policy’s explicit locality must intersect `TravelArea.included_cities` and, when both values exist, its `sido` must match.
4. For `whole:<sido>`, accept an explicitly localized policy only when its `sido` equals the trip’s `sido`. This matches the already documented recommendation exception for a whole-province trip.
5. For a policy with no explicit locality, allow only a truly nationwide candidate. Do not treat an unlocalized provincial policy as evidence that it applies to every city in that province.
6. Check an existing `TripPolicy` link before this guard so re-adding an old link remains a no-op even after the trip region has changed. For a new link, fail with `TripServiceError(409, "Policy does not match trip travel area")`; do not insert or commit anything.
7. Validate a preselected `policySlug` before `create_trip` writes the trip, member, days, invite, or link. A rejected request must leave no partial trip rows.

### Task 1: Establish the authoritative attach-eligibility helper

**Files:**
- Modify: `backend/app/services/trips.py:247-308, 421-483`
- Test: `backend/tests/test_trip_db_service.py`

**Interfaces:**
- Consumes: `Trip.travel_area_id`, `Policy.region`, `Policy.city`, `StayDiscountAliasArea`, `_candidate_matches_trip_locality(candidate, trip)`.
- Produces: `_policy_attachment_candidate(policy: Policy, alias_area: stay_discount_aliases.StayDiscountAliasArea | None) -> dict[str, object]` and `_policy_is_attachable_to_trip(policy: Policy, trip: Trip, alias_area: stay_discount_aliases.StayDiscountAliasArea | None) -> bool`.
- Error detail used by later tasks: `"Policy does not match trip travel area"`.

- [ ] **Step 1: Write failing helper-level service tests for the full eligibility matrix**

Add these tests near the existing recommendation and `add_policy_to_trip` tests. Use a real `Trip` with `travel_area_id="gangwon-sokcho-goseong-yangyang"`, `region="속초·고성·양양"`, and active policies with explicit `city` values.

```python
def test_policy_is_attachable_to_trip_requires_an_included_city() -> None:
    trip = make_trip()
    trip.travel_area_id = "gangwon-sokcho-goseong-yangyang"
    trip.region = "속초·고성·양양"
    assert trip_service._policy_is_attachable_to_trip(
        Policy(id=1, slug="goseong", title="[고성] 숙박 할인", region="강원", city="고성"),
        trip,
        None,
    ) is True
    assert trip_service._policy_is_attachable_to_trip(
        Policy(id=2, slug="samcheok", title="[삼척] 숙박 할인", region="강원", city="삼척"),
        trip,
        None,
    ) is False


def test_policy_is_attachable_to_trip_allows_only_unscoped_nationwide_policy() -> None:
    trip = make_trip()
    trip.travel_area_id = "gangwon-sokcho-goseong-yangyang"
    trip.region = "속초·고성·양양"
    assert trip_service._policy_is_attachable_to_trip(
        Policy(id=3, slug="nationwide", title="전국 교통 할인", region="전국"), trip, None
    ) is True
    assert trip_service._policy_is_attachable_to_trip(
        Policy(id=4, slug="named-jeju", title="제주 여행 할인", region="전국"), trip, None
    ) is False
```

Add a `whole:강원` assertion for a `city="삼척", region="강원"` policy and a legacy (`travel_area_id=None`) assertion that rejects the same localized policy but accepts `nationwide`.

- [ ] **Step 2: Run the new helper tests and confirm they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_trip_db_service.py -k "attachable_to_trip" -q
```

Expected: FAIL because `_policy_is_attachable_to_trip` does not exist.

- [ ] **Step 3: Implement candidate conversion and the attach predicate**

In `backend/app/services/trips.py`, retain `_policy_to_trip_policy_candidate` for recommendation data but make its locality source prefer the materialized policy city:

```python
city = policy.city or (external_record.city if external_record is not None else None)
```

Add the two interfaces declared above. The candidate factory must call `_stay_alias_to_trip_policy_candidate(policy, alias_area)` for aliases and `_policy_to_trip_policy_candidate(policy)` otherwise. Implement the predicate with these exact branches:

```python
def _policy_is_attachable_to_trip(policy: Policy, trip: Trip, alias_area: StayDiscountAliasArea | None) -> bool:
    candidate = _policy_attachment_candidate(policy, alias_area)
    has_locality = _candidate_has_explicit_locality(candidate)
    is_nationwide = not _candidate_sido(candidate) and _normalized_text(candidate.get("region")) == _normalized_text(NATIONWIDE_REGION)
    if not has_locality:
        return is_nationwide
    if not trip.travel_area_id:
        return False
    return _candidate_matches_trip_locality(candidate, trip)
```

Use the module’s existing `stay_discount_aliases.StayDiscountAliasArea` type annotation rather than adding a new dependency or data model. Do not change `_recommended_policies` scoring or its limit in this task.

- [ ] **Step 4: Run the helper tests and existing recommendation tests**

Run:

```powershell
cd backend
python -m pytest tests/test_trip_db_service.py -k "attachable_to_trip or recommendations" -q
```

Expected: PASS. In particular, existing multi-city recommendation tests retain their current result ordering.

- [ ] **Step 5: Commit the helper and its tests**

```powershell
git add backend/app/services/trips.py backend/tests/test_trip_db_service.py
git commit -m "feat: define trip policy region eligibility"
```

### Task 2: Guard both policy-link creation paths without partial writes

**Files:**
- Modify: `backend/app/services/trips.py:1010-1072, 1075-1105`
- Test: `backend/tests/test_trip_db_service.py`

**Interfaces:**
- Consumes: `_policy_is_attachable_to_trip(policy, trip, alias_area) -> bool` from Task 1.
- Produces: `TripServiceError(409, "Policy does not match trip travel area")` for a new mismatched link; no changed API response body on success.

- [ ] **Step 1: Write failing attach-route tests for unrelated and duplicate regional policies**

Create a trip in `gangwon-sokcho-goseong-yangyang`, then persist one matching `city="고성"` policy and one non-matching `city="삼척"` policy. Assert the first link succeeds, the second link raises the exact `409`, and only the matching row exists.

```python
with pytest.raises(trip_service.TripServiceError) as error:
    trip_service.add_policy_to_trip(sqlite_db_session, user, str(trip.id), "samcheok-policy")

assert error.value.status_code == 409
assert error.value.detail == "Policy does not match trip travel area"
assert [link.policy_id for link in sqlite_db_session.query(TripPolicy).all()] == [goseong.id]
```

Add a separate test proving a stay-discount alias for `삼척` is rejected for the same trip even though its canonical campaign policy is broad. Keep the existing same-slug idempotency test unchanged.

- [ ] **Step 2: Write a failing preselected-policy creation test**

Build `CreateTripRequest` with `travelAreaId="policy-region:%EC%A0%84%EB%82%A8:%EC%98%81%EA%B4%91"` and a stored policy with `region="강원", city="삼척"`. Assert `create_trip` raises the exact `409`; after `db.expire_all()`, assert no trip with that title and no `TripPolicy` row were committed.

```python
with pytest.raises(trip_service.TripServiceError, match="Policy does not match trip travel area"):
    trip_service.create_trip(sqlite_db_session, user, request)

sqlite_db_session.expire_all()
assert sqlite_db_session.query(Trip).filter_by(title="영광 여행").count() == 0
assert sqlite_db_session.query(TripPolicy).count() == 0
```

- [ ] **Step 3: Run the route-path tests and confirm they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_trip_db_service.py -k "different_city or preselected_policy" -q
```

Expected: FAIL because both paths currently call `add_trip_policy` without an eligibility check.

- [ ] **Step 4: Implement the guard before mutation**

For `create_trip`, resolve `payload["policySlug"]` and call `_policy_is_attachable_to_trip` against a transient `Trip(region=region, travel_area_id=travel_area_id)` **before** calling `trip_repository.create_trip`, `add_trip_member`, `add_trip_day`, `_ensure_invite`, or `add_trip_policy`. Preserve the current `404 "Policy not found"` behavior and store the resolved `policy`/`alias_area` for the later successful insert.

For `add_policy_to_trip`, retain this ordering:

```python
trip_repository.lock_trip_row(db, trip_id=trip.id)
existing = trip_repository.get_trip_policy(db, trip_id=trip.id, policy_id=policy.id)
if existing is not None:
    return {"tripId": str(trip.id), "policyId": policy_slug, "added": True}
if not _policy_is_attachable_to_trip(policy, trip, alias_area):
    raise TripServiceError(409, "Policy does not match trip travel area")
# keep the existing stay_discount source-category conflict check and insert below it
```

This preserves the PostgreSQL trip-row lock before all new-link checks and preserves old links when a trip’s travel area changes.

- [ ] **Step 5: Run focused backend tests**

Run:

```powershell
cd backend
python -m pytest tests/test_trip_db_service.py -k "add_policy_to_trip or preselected_policy or attachable_to_trip" -q
```

Expected: PASS, including the pre-existing stay-discount one-per-trip and lock-order tests.

- [ ] **Step 6: Commit the guarded service paths**

```powershell
git add backend/app/services/trips.py backend/tests/test_trip_db_service.py
git commit -m "fix: reject out-of-region trip policy links"
```

### Task 3: Document the API conflict and show an actionable picker error

**Files:**
- Modify: `docs/mvp-api-contract.md:1006-1022`
- Modify: `frontend/src/pages/PolicyPages.tsx:17-27, 985-998`
- Test: `frontend/src/app/__tests__/policies.test.tsx`

**Interfaces:**
- Consumes: backend error detail `"Policy does not match trip travel area"` from Task 2.
- Produces: Korean UI message `"선택한 일정의 여행 지역과 맞지 않아 연결할 수 없어요. 일정 지역을 변경하거나 다른 일정을 선택해 주세요."`.

- [ ] **Step 1: Write failing frontend message and picker-flow tests**

Extend the existing `policyTripErrorMessage` unit assertions:

```tsx
expect(policyTripErrorMessage(new Error("Policy does not match trip travel area"))).toBe(
  "선택한 일정의 여행 지역과 맞지 않아 연결할 수 없어요. 일정 지역을 변경하거나 다른 일정을 선택해 주세요.",
);
```

Add a policy-detail picker test where `listTrips` returns two trips and `addPolicyToTrip` rejects the first click with that error. Assert the error text is rendered and both `.trip-select-row` choices remain present, so the user can choose a different valid trip rather than reopening the policy page.

- [ ] **Step 2: Run the frontend tests and confirm they fail**

Run:

```powershell
cd frontend
npx vitest run src/app/__tests__/policies.test.tsx
```

Expected: FAIL because the new backend detail currently falls through to the generic retry message.

- [ ] **Step 3: Implement only error translation, not client-side geo matching**

Add this branch before the generic fallback in `policyTripErrorMessage`:

```ts
if (message.includes("Policy does not match trip travel area")) {
  return "선택한 일정의 여행 지역과 맞지 않아 연결할 수 없어요. 일정 지역을 변경하거나 다른 일정을 선택해 주세요.";
}
```

Keep `attachPolicyToTrip`’s existing `error` state and list rendering. Do not filter or disable rows in `TripSelectSheet`; `Policy` DTO intentionally does not expose a canonical city and backend validation must remain the only geographic authority.

In `docs/mvp-api-contract.md`, add this `409` bullet under the POST route errors:

```markdown
- 409: `Policy does not match trip travel area` — 지역 정책의 시·군·구가 일정의 `travelAreaId`와 일치하지 않음. `전국`이며 별도 지역명이 없는 정책만 예외로 연결 가능.
```

- [ ] **Step 4: Run frontend and API-boundary verification**

Run:

```powershell
cd frontend
npx vitest run src/app/__tests__/policies.test.tsx
npm run typecheck
```

Expected: PASS. No frontend API type changes are required because the success response and DTOs are unchanged.

- [ ] **Step 5: Commit the contract and UI feedback**

```powershell
git add docs/mvp-api-contract.md frontend/src/pages/PolicyPages.tsx frontend/src/app/__tests__/policies.test.tsx
git commit -m "docs: explain trip policy region conflicts"
```

### Task 4: Run regression and release-readiness verification

**Files:**
- Modify: none unless a regression is found.
- Test: `backend/tests/test_trip_db_service.py`, `frontend/src/app/__tests__/policies.test.tsx`, existing full test suites.

**Interfaces:**
- Consumes: all implementation from Tasks 1-3.
- Produces: verification evidence for the branch; `CHECKLIST.md` remains untouched until the branch is ready to merge.

- [ ] **Step 1: Run backend trip-policy regression tests**

```powershell
cd backend
python -m pytest tests/test_trip_db_service.py -q
```

Expected: PASS. If the known repository-wide baseline failure appears only in a full suite, record it separately; do not classify it as a geographic-link regression.

- [ ] **Step 2: Run frontend policy and trip creation tests**

```powershell
cd frontend
npx vitest run src/app/__tests__/policies.test.tsx src/app/__tests__/trip-create.test.tsx
```

Expected: PASS. This guards the policy-detail attach sheet and the `policySlug` new-trip flow.

- [ ] **Step 3: Run project checks required for this cross-layer behavior change**

```powershell
cd frontend
npm run typecheck
npm run build

cd ../backend
python -m pytest
alembic upgrade head --sql

cd ..
git diff --check
```

Expected: typecheck, build, Alembic SQL rendering, and diff check PASS; full pytest result recorded exactly with any pre-existing baseline failure identified.

- [ ] **Step 4: Verify UTF-8 and intended scope**

```powershell
git diff --check
rg -n "\x{FFFD}" backend/app/services/trips.py backend/tests/test_trip_db_service.py frontend/src/pages/PolicyPages.tsx frontend/src/app/__tests__/policies.test.tsx docs/mvp-api-contract.md
git diff --stat origin/develop...HEAD
git status --short
```

Expected: no `U+FFFD`, no whitespace errors, and only the five planned files are part of the feature diff. Preserve the root’s pre-existing untracked handoff and prior search-latency documents.

- [ ] **Step 5: Commit any regression-only adjustment, then prepare the branch for review**

```powershell
git add <only-files-changed-by-the-regression-fix>
git commit -m "test: cover trip policy region eligibility regression"
```

If no regression adjustment is needed, do not create an empty commit. At branch-readiness time only, update `CHECKLIST.md` with concise current validation and active risks, then validate it with `git diff --check -- CHECKLIST.md`.

## Self-Review

**Spec coverage:**

- Unrelated/far policies: Tasks 1 and 2 use city/sido-aware server validation before every new policy link.
- Multiple regional policies: Task 2 proves a valid local policy followed by a different-city policy leaves one link only; it does not over-restrict different eligible policy categories.
- Existing trip attach and new-trip preselection: Task 2 covers both paths.
- User feedback: Task 3 maps the exact server conflict and preserves alternative trip choices.
- API contract and regression proof: Tasks 3 and 4 cover documentation, targeted tests, full checks, and UTF-8/scope validation.

**Placeholder scan:** The plan has no deferred implementation markers or unspecified error/testing steps. The one literal `<only-files-changed-by-the-regression-fix>` is a Git staging safety instruction, not an implementation dependency; it intentionally prevents staging unrelated worktree files.

**Type consistency:** All tasks use the same `Policy`, `Trip`, `StayDiscountAliasArea`, `_policy_attachment_candidate`, `_policy_is_attachable_to_trip`, and `TripServiceError(409, "Policy does not match trip travel area")` names.

## 2026-09-21 재개 — develop 리베이스와 실데이터 검증에서 나온 보강

9/15 에 멈춘 브랜치를 `origin/develop`(5eb23ec) 위로 리베이스했다(충돌 없음, e325af4 → 53a3002).
개발서버 복사본 정책 108건을 카탈로그 여행 지역 273곳에 전부 대입해 판정 함수를 검증했다.

- 전국 12건 전부 허용. `[시군]` 정책 96건은 제 시군 일정에 못 붙는 경우 0건.
- **오탐 1 — "디지털관광주민증" 안의 "광주".** `_candidate_local_terms` 가 제목을 공백 없이 이어 붙인 뒤
  지명을 부분 문자열로 찾는다. 경기 `광주시` 일정에 `[연천]`·`[가평]` 디지털관광주민증이 붙었다.
  develop 에 원래 있던 버그지만 추천에서는 점수에 섞이는 정도였고, 여기서는 허용/거부를 가른다.
  → 제목을 낱말로 쪼개 **낱말 머리에서만** 지명을 찾는다("광주 비엔날레", "여수에서" 는 그대로 잡힌다).
- **잠재 위험 — 시군 단서 없는 시도 단위 정책은 어떤 일정에도 못 붙는다.** 지금은 0건이지만
  섬·지자체 수집원을 늘리면 나온다. → 단서가 없고 시도만 있으면 **일정의 시도가 같을 때** 허용.
- **같이 고쳐야 하는 것 — 붙이기 판정이 `Policy.city` 를 안 본다.** 후보를 만들 때 시군을
  `ExternalSourceRecord.city` 에서만 가져오는데 붙이기 경로는 그 기록을 넘기지 않는다.
  활성 정책 113건 중 69건이 `city` 를 갖고 있다. 시도 규칙만 넣으면 "제목에 지명이 없고 city 만 있는
  정책"이 같은 시도 아무 일정에나 붙는다(기존 테스트 `Samcheok local benefit` 이 정확히 그 모양이고,
  지금은 '단서 없음 → 거부'라는 엉뚱한 이유로 통과하고 있다). → 외부 기록이 없으면 `policy.city` 를 쓴다.
- **제주** — `제주시` 는 정규화하면 시도명과 같아 "제주 전체" 일정으로 판정되고 `[서귀포]` 정책이 붙는다.
  사용자 결정(2026-09-21): 제주는 하나의 생활권으로 보고 **그대로 둔다.**
  비대칭은 남는다 - `서귀포시` 일정에는 제주시 정책이 안 붙는다. 실해가 없어 손대지 않는다.
- 운영 영향: `travel_area_id` 없는 일정(로컬 15건 중 3건)은 지역 정책을 못 붙인다. 안내 문구가
  "일정 지역을 변경"하도록 이끈다. 이미 연결된 정책은 소급해서 끊지 않는다.

## 2026-09-21 추가 — 일정 지역을 바꿀 때 안 맞는 정책을 확인받고 뺀다

**왜.** 붙일 때만 검사하면 규칙이 반쪽이다. 속초 일정에 `[고성]` 정책을 붙인 뒤 지역을 제주로 바꾸면
강원 정책이 제주 일정에 남는다. 계약(`mvp-api-contract.md`)이 "지역을 바꿔도 연결된 정책은 그대로"라고
못박고 있어서다.

**사용자 결정(2026-09-21):** 조용한 자동 삭제가 아니라 **확인 후 제거**, 같은 브랜치에서.
자동 삭제를 안 하는 이유 - 연결 행(`trip_policies`)에 사용자가 직접 기록한 신청 진행 상태
(`application_status`·체크리스트)가 같이 있어, 지역을 잘못 눌렀다 되돌리기만 해도 복구 없이 사라진다.

**설계 - 같은 요청에 이미 있는 `overflowPlaceStrategy` 선례를 그대로 따른다.**

- `PATCH /api/trips/{id}/settings` 에 `mismatchedPolicyStrategy: "reject" | "remove"`(기본 `reject`).
- 지역이 **실제로 바뀔 때만** 본다(같은 id 를 다시 보내거나 제목·날짜만 고치면 검사하지 않는다 -
  옛 연결 때문에 제목 수정이 막히면 안 된다).
- 새 지역과 안 맞는 연결이 있는데 `reject` 면 **409**, `detail` 은 객체:
  `{ code: "trip_policies_outside_travel_area", message, policies: [{ slug, title, hasApplicationProgress }] }`.
  판정은 리비전을 올리기 **전에** 한다 - 거부된 요청은 `revision` 을 안 건드린다는 기존 계약을 지킨다.
- `remove` 면 지역 변경과 연결 삭제를 **한 트랜잭션**으로. 맞는 정책과 전국 정책은 남는다.
- 판정 함수는 `_policy_is_attachable_to_trip` 그대로(붙일 때와 뺄 때의 기준이 같아야 한다).
- `TripServiceError.detail` 을 문자열뿐 아니라 객체도 받게 한다. 프런트 `ApiError` 는 이미 `detail: unknown` 을 들고 있다.
- 프런트: 지역을 바꾸는 곳은 `ItineraryEditPage` 하나다. 409 + 위 code 면 폼 안에 확인 상자를 띄운다 -
  빠질 정책 이름, 신청 기록이 있으면 "진행 기록도 함께 지워져요". `정책 빼고 저장` / `취소`.
- 이미 잘못 붙어 있는 옛 연결은 일괄 삭제하지 않는다. 지역을 바꾸는 순간에만 정리된다.

## 2026-09-21 추가 — 연결된 정책 카드 다듬기 (사용자 확인 뒤 요청)

지역 변경 확인 기능을 5173 에서 확인한 뒤 나온 세 가지. 프런트만, 백엔드 변경 없음.

- **밋밋하다** — 옅은 민트 바탕이 아래 '어울리는 정책' 레일과 무게가 같았다. 흰 바탕 + 왼쪽 주색 띠 + 옅은 그림자로
  '이미 담은 것'임을 드러내고, 금액은 정책 목록 카드와 같은 알약으로 올린다. 섹션 머리에 `N건 · 예상 절약` 요약.
- **혜택 안내 보기 버튼** — 카드 전체가 링크였지만 눌러진다는 단서가 없었다. 카드 아랫줄에 버튼을 둔다(목적지는 같은 정책 상세).
  숨김 처리된 정책은 상세가 없으므로 버튼을 내지 않는다.
- **삭제가 너무 세다** (사용자 선택: A안) — 카드에서 제일 눈에 띄는 것이 제일 덜 쓰는 빨간 `삭제` 였다.
  오른쪽 위 `⋯` 메뉴 안의 "일정에서 빼기"로 옮긴다. 네이티브 `<details>` 라 새 의존성이 없고 키보드로 열린다.
  "삭제"는 정책 자체를 지우는 말로 읽혀 문구도 바꾼다. 접근성 이름(`… 연결 삭제`)과 클래스는 그대로 둬
  기존 테스트와 보조기기 사용자의 기억을 깨지 않는다. 뷰어에게는 메뉴가 없다(지금과 같다).

**5173 확인 뒤 두 가지 조정(같은 날).**
- `혜택 안내 보기` 는 앱 안 정책 상세가 아니라 **공식 사이트로 바로** 나간다(새 탭, `noopener noreferrer`).
  연결 정책 응답에 주소가 없어 `LinkedTripPolicy` 에 `officialUrl`·`applyUrl` 을 추가했다(계약·golden 동기화).
  문구 규칙은 정책 상세의 버튼과 같다 - `applyUrl` 이 있으면 "신청하러 가기"가 우선. 활성 113건 전부 `official_url` 이
  있고 `apply_url` 은 0건이라 지금은 전부 "혜택 안내 보기"다. 주소가 없는 정책만 상세로 보낸다. 카드 본문은 여전히 상세로 간다.
- `⋯` 메뉴 대신 **조용한 회색 ×**, 누르면 **확인 창**. 앱에 이미 있는 `ConfirmDialog`(장소 삭제가 쓰는 것)를 재사용했다.
  본문은 "연결만 풀려요, 정책은 정책 탭에 그대로" - '삭제'가 정책 자체를 지우는 말로 읽히는 것을 막는다.
  신청 진행 기록이 있으면 함께 지워진다고 알린다. 접근성 이름(`… 연결 삭제`)은 그대로.
- **"정책 상세 보기"로 떨어지던 버그(사용자 발견).** 정책 상세의 "일정에서 보기"로 넘어오면 방금 담은 정책 요약이
  라우터 state 로 먼저 오는데, `linkedTripPoliciesForDisplay` 가 그 요약을 서버 응답보다 **앞에** 넣어 같은 정책의
  서버 버전을 밀어냈다. 요약에는 공식 주소가 없어 버튼이 앱 안 상세로 갔다. → 서버 응답에 같은 slug 가 있으면 그쪽을 쓰고,
  state 요약에도 `officialUrl`·`applyUrl` 을 실어 서버 응답이 아직 낡았을 때도 사이트로 나가게 했다.
