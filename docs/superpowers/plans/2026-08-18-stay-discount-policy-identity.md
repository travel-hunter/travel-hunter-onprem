# Stay Discount Policy Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store each public stay-discount area policy as its own `policies` row so saving, trip linking, detail pages, and linked-policy display use the same DB identity as ordinary policies.

**Architecture:** Replace the current virtual alias projection with real area policy rows whose slugs are `stay-discount-{sidoSlug}-{citySlug}`. Keep the source `external_source_records` row as evidence, but allow multiple `policies` rows to reference one source record. Hide the old canonical `travelmonth-{externalSourceRecordId}` stay-discount policy from public lists after area rows are created, and migrate confident existing canonical trip links to the matching area policy row.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL JSONB, React, TypeScript, Vite, Vitest, pytest.

**Spec:** `docs/mvp-api-contract.md`, `docs/db-schema-current.md`, `docs/implemented-feature-spec.md`, `docs/requirements.md`

## Global Constraints

- User-facing frontend data access must stay behind `frontend/src/api/AppDataApi` / `appDataApi`.
- API DTO fields stay `camelCase`; database and SQL fields stay `snake_case`.
- Trip routes use numeric string `tripId`; do not add `trips.slug`.
- Policy detail routes use `policySlug` / `policies.slug`.
- Backend routes stay thin; service behavior belongs in `app/services`, DB queries in `app/repositories`.
- Schema changes must use Alembic; do not use SQLAlchemy `create_all()`.
- `trip_policies` and `user_saved_policies` must keep ordinary `policy_id` foreign keys to `policies.id`.
- Do not reintroduce runtime mock mode.
- Keep Korean files UTF-8 clean and run `git diff --check` before completion.
- Update `CHECKLIST.md` because this changes DB behavior and validation evidence.

---

## File Structure

- Modify `backend/app/models/tables.py`: remove the one-policy-per-source uniqueness from `Policy.external_source_record_id`.
- Create Alembic migration `backend/alembic/versions/0024_stay_discount_area_policy_identity.py`: replace unique `ix_policies_external_source_record_id` with a non-unique index.
- Modify `backend/app/services/stay_discount_aliases.py`: split canonical-vs-area helpers and provide area row field helpers.
- Modify `backend/app/services/policy_normalization.py`: upsert real stay-discount area policies from `raw_payload.eligibleAreas`, hide the canonical source policy, and leave local-half-trip behavior unchanged.
- Modify `backend/app/services/policies.py`: stop projecting stay-discount aliases in `list_policies`; use ordinary `policy_to_api()` for area rows.
- Modify `backend/app/services/trips.py`: stop resolving stay-discount alias slugs to canonical policy ids when an area policy row exists; linked policies should return the actual row slug.
- Create `backend/app/scripts/migrate_stay_discount_area_policy_links.py`: create missing area rows for current source records and move confident canonical trip links to area rows.
- Modify backend tests: `backend/tests/test_db_schema.py`, `backend/tests/test_policy_normalization.py`, `backend/tests/test_policy_db_service.py`, `backend/tests/test_trip_db_service.py`, `backend/tests/test_trip_db_routes.py`.
- Modify frontend tests only where assumptions about duplicate route-state/API policy display need to change: `frontend/src/app/__tests__/trip-detail.test.tsx`, `frontend/src/app/__tests__/policies.test.tsx`.
- Modify docs and evals: `docs/mvp-api-contract.md`, `docs/db-schema-current.md`, `docs/db-schema-current.sql`, `docs/implemented-feature-spec.md`, `.agent/evals/api-contract-golden.json`, `CHECKLIST.md`.

---

### Task 1: Allow Multiple Public Policies Per External Source Record

**Files:**
- Modify: `backend/app/models/tables.py:210-215`
- Create: `backend/alembic/versions/0024_stay_discount_area_policy_identity.py`
- Modify: `backend/tests/test_db_schema.py`
- Modify: `backend/tests/fixtures/final_alembic_head_timestamp_columns.sql`

**Interfaces:**
- Consumes: existing `policies.external_source_record_id`.
- Produces: non-unique index `ix_policies_external_source_record_id` so many area policies can point to the same `external_source_records.id`.

- [ ] **Step 1: Write the failing schema test**

In `backend/tests/test_db_schema.py`, add this assertion near the existing policy index checks:

```python
def test_policies_external_source_record_id_index_is_not_unique(db: Session) -> None:
    rows = db.execute(
        text(
            """
            SELECT i.relname AS index_name, ix.indisunique AS is_unique
            FROM pg_class t
            JOIN pg_index ix ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            WHERE t.relname = 'policies'
              AND i.relname = 'ix_policies_external_source_record_id'
            """
        )
    ).mappings().all()

    assert rows == [{"index_name": "ix_policies_external_source_record_id", "is_unique": False}]
```

- [ ] **Step 2: Run the schema test and verify it fails**

Run:

```bash
cd backend
python -m pytest tests/test_db_schema.py::test_policies_external_source_record_id_index_is_not_unique -q
```

Expected: FAIL because the current index is unique.

- [ ] **Step 3: Update the SQLAlchemy model**

In `backend/app/models/tables.py`, change:

```python
external_source_record_id: Mapped[int | None] = mapped_column(
    BigInteger,
    ForeignKey("external_source_records.id", ondelete="SET NULL"),
    index=True,
)
```

Remove `unique=True`.

- [ ] **Step 4: Add the Alembic migration**

Create `backend/alembic/versions/0024_stay_discount_area_policy_identity.py`:

```python
"""allow stay discount area policies per source record

Revision ID: 0024_stay_discount_area_policy_identity
Revises: 0023_policy_structured_detail
Create Date: 2026-08-18 00:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "0024_stay_discount_area_policy_identity"
down_revision = "0023_policy_structured_detail"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_policies_external_source_record_id", table_name="policies")
    op.create_index(
        "ix_policies_external_source_record_id",
        "policies",
        ["external_source_record_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_policies_external_source_record_id", table_name="policies")
    op.create_index(
        "ix_policies_external_source_record_id",
        "policies",
        ["external_source_record_id"],
        unique=True,
    )
```

- [ ] **Step 5: Run schema verification**

Run:

```bash
cd backend
alembic upgrade head --sql > /tmp/travel-hunter-alembic-head.sql
python -m pytest tests/test_db_schema.py::test_policies_external_source_record_id_index_is_not_unique -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/tables.py backend/alembic/versions/0024_stay_discount_area_policy_identity.py backend/tests/test_db_schema.py backend/tests/fixtures/final_alembic_head_timestamp_columns.sql
git commit -m "Allow source records to back area policies"
```

Use Lore trailers in the real commit message.

---

### Task 2: Normalize Stay-Discount Areas Into Real Policy Rows

**Files:**
- Modify: `backend/app/services/stay_discount_aliases.py`
- Modify: `backend/app/services/policy_normalization.py`
- Modify: `backend/tests/test_policy_normalization.py`

**Interfaces:**
- Produces: `stay_discount_aliases.is_stay_discount_area_policy(policy: PolicyModel) -> bool`.
- Produces: `stay_discount_aliases.area_source_canonical_key(record_key: str | None, alias_slug: str) -> str`.
- Produces: `policy_normalization.promote_external_benefits_to_policies(db)` creating active area `Policy` rows for stay-discount records.

- [ ] **Step 1: Write the failing normalization test**

In `backend/tests/test_policy_normalization.py`, replace `test_promotes_active_fresh_stay_discount_as_lodging_policy` with:

```python
def test_promotes_active_fresh_stay_discount_as_area_policy_rows(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                source_name="대한민국 숙박세일 페스타",
                source_url="https://korean.visitkorea.or.kr/travelmonth/benefits/stay.do",
                collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/stay.do",
                source_category="stay_discount",
                canonical_key="stay-discount",
                external_id="stay-discount",
                title="2026 대한민국 숙박세일 페스타 숙박 할인",
                region="비수도권·인구감소지역",
                benefit_text="숙박상품 2/3/5/7만원 할인권",
                benefit_value_text="2/3/5/7만원 할인권",
                extracted_amount_krw=70000,
                raw_payload={
                    "eligibleAreas": [
                        {"sido": "전남", "cities": ["강진군", "순천시"]},
                    ],
                    "eligibleAreaCount": 2,
                },
            )
        ],
    )

    from app.repositories.policies import get_policy_by_slug_any_status
    from app.services.policy_normalization import promote_external_benefits_to_policies

    promote_external_benefits_to_policies(db)

    canonical = get_policy_by_slug_any_status(db, f"travelmonth-{rows[0].id}")
    gangjin = get_policy_by_slug_any_status(db, "stay-discount-jeonnam-gangjin")
    suncheon = get_policy_by_slug_any_status(db, "stay-discount-jeonnam-suncheon")

    assert canonical is not None
    assert canonical.status == "hidden"
    assert gangjin is not None
    assert gangjin.status == "active"
    assert gangjin.external_source_record_id == rows[0].id
    assert gangjin.slug == "stay-discount-jeonnam-gangjin"
    assert gangjin.title == "[강진] 2026 대한민국 숙박세일 페스타 숙박 할인"
    assert gangjin.region == "전남"
    assert gangjin.policy_type == "숙박"
    assert gangjin.benefit_amount == 70000
    assert gangjin.source_canonical_key == "stay-discount:stay-discount-jeonnam-gangjin"
    assert suncheon is not None
    assert suncheon.status == "active"
```

- [ ] **Step 2: Run the normalization test and verify it fails**

Run:

```bash
cd backend
python -m pytest tests/test_policy_normalization.py::test_promotes_active_fresh_stay_discount_as_area_policy_rows -q
```

Expected: FAIL because only the canonical `travelmonth-*` policy is created today.

- [ ] **Step 3: Add area identity helpers**

In `backend/app/services/stay_discount_aliases.py`, change canonical detection and add helpers:

```python
def is_stay_discount_area_slug(slug: str | None) -> bool:
    return bool(slug and slug.startswith(f"{ALIAS_PREFIX}-"))


def is_stay_discount_area_policy(policy: PolicyModel) -> bool:
    return (policy.source_category or "") == SOURCE_CATEGORY and is_stay_discount_area_slug(policy.slug)


def is_stay_discount_canonical_policy(policy: PolicyModel) -> bool:
    return (
        (policy.source_category or "") == SOURCE_CATEGORY
        and policy.external_source_record_id is not None
        and not is_stay_discount_area_slug(policy.slug)
    )


def area_source_canonical_key(record_key: str | None, alias_slug: str) -> str:
    base_key = (record_key or SOURCE_CATEGORY).strip() or SOURCE_CATEGORY
    return f"{base_key}:{alias_slug}"
```

- [ ] **Step 4: Add area policy assignment in normalization**

In `backend/app/services/policy_normalization.py`, add helper functions near `_assign_policy_from_external_record`:

```python
def _get_policy_by_slug(db: Session, slug: str) -> Policy | None:
    return db.scalar(select(Policy).where(Policy.slug == slug))


def _assign_stay_discount_area_policy(
    policy: Policy,
    record: ExternalSourceRecord,
    alias_area: stay_discount_aliases.StayDiscountAliasArea,
) -> Policy:
    benefit_value = extract_benefit_value(record.benefit_text or "", title=record.title)
    benefit_detail = record.benefit_value_text or benefit_value.value_text or record.benefit_text
    policy.status = "active"
    policy.slug = alias_area.slug
    policy.title = stay_discount_aliases.alias_title(record.title, alias_area)
    policy.organization = record.organizer_text or record.source_name
    policy.policy_type = "숙박"
    policy.description = record.raw_detail_text or record.benefit_text
    policy.benefit_amount = record.extracted_amount_krw or benefit_value.amount_krw
    policy.benefit_detail = benefit_detail
    policy.target_condition = _target_condition_for_record(record)
    policy.region = alias_area.sido
    policy.start_date = record.start_date
    policy.end_date = record.end_date
    policy.official_url = record.detail_url or record.collected_page_url
    policy.apply_url = None
    policy.policy_comment = record.benefit_text[:300] if record.benefit_text else None
    policy.policy_period = None
    policy.source_type = record.source_type
    policy.source_name = record.source_name
    policy.source_category = record.source_category
    policy.external_source_record_id = record.id
    policy.source_url = record.detail_url or record.collected_page_url or record.source_url
    policy.source_canonical_key = stay_discount_aliases.area_source_canonical_key(record.canonical_key, alias_area.slug)
    policy.normalized_at = record.last_fetched_at
    policy.last_verified_at = record.last_verified_at
    policy.verification_status = record.freshness_status
    policy.structured_detail = _build_structured_detail_for_record(policy, record)
    return policy
```

Import `stay_discount_aliases` at the top of `policy_normalization.py`.

- [ ] **Step 5: Branch stay-discount promotion**

In `promote_external_benefits_to_policies`, before the generic `_get_policy_for_external_record` path, add:

```python
        if record.source_category == stay_discount_aliases.SOURCE_CATEGORY:
            canonical = _get_policy_for_external_record(db, record)
            if canonical is None:
                canonical = Policy()
                db.add(canonical)
            _assign_policy_from_external_record(canonical, record)
            canonical.status = "hidden"
            for alias_area in stay_discount_aliases.alias_areas_for_record(record):
                area_policy = _get_policy_by_slug(db, alias_area.slug)
                if area_policy is None:
                    area_policy = Policy()
                    db.add(area_policy)
                _assign_stay_discount_area_policy(area_policy, record, alias_area)
                promoted_count += 1
            promoted_categories.add(record.source_category)
            continue
```

- [ ] **Step 6: Run normalization tests**

Run:

```bash
cd backend
python -m pytest tests/test_policy_normalization.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/stay_discount_aliases.py backend/app/services/policy_normalization.py backend/tests/test_policy_normalization.py
git commit -m "Promote stay discount areas as policies"
```

Use Lore trailers in the real commit message.

---

### Task 3: Make Policy APIs Use Area Rows Instead Of Virtual Aliases

**Files:**
- Modify: `backend/app/services/policies.py`
- Modify: `backend/tests/test_policy_db_service.py`
- Modify: `.agent/evals/api-contract-golden.json`

**Interfaces:**
- Consumes: `policy_repository.list_policies(db)` returning active area policy rows.
- Produces: `list_policies()` returns each active stay-discount area row once; it does not synthesize extra alias DTOs.
- Produces: `save_policy("stay-discount-jeonnam-gangjin")` stores that row's `policy_id`.

- [ ] **Step 1: Update failing list/detail/save tests**

In `backend/tests/test_policy_db_service.py`, replace virtual alias tests with DB-row tests:

```python
def test_stay_discount_list_uses_area_policy_rows_without_virtual_projection(monkeypatch) -> None:
    fake_db = object()
    canonical = make_stay_policy()
    canonical.status = "hidden"
    area_policy = make_stay_policy()
    area_policy.id = 188
    area_policy.slug = "stay-discount-jeonnam-gangjin"
    area_policy.title = "[강진] 2026 대한민국 숙박세일 페스타 숙박 할인"
    area_policy.region = "전남"

    monkeypatch.setattr(policy_service.policy_repository, "list_policies", lambda db: [area_policy] if db is fake_db else [])

    payload = policy_service.list_policies(fake_db)

    assert [item["slug"] for item in payload] == ["stay-discount-jeonnam-gangjin"]
    assert payload[0]["title"] == "[강진] 2026 대한민국 숙박세일 페스타 숙박 할인"
    assert payload[0]["region"] == "전남"
```

Add save test:

```python
def test_stay_discount_area_save_uses_area_policy_id(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    area_policy = make_stay_policy()
    area_policy.id = 188
    area_policy.slug = "stay-discount-jeonnam-gangjin"

    monkeypatch.setattr(policy_service.policy_repository, "get_policy_by_slug", lambda db, slug: area_policy if db is fake_db and slug == area_policy.slug else None)
    monkeypatch.setattr(policy_service.policy_repository, "get_saved_policy", lambda db, *, user_id, policy_id: None)
    captured: dict[str, object] = {}
    monkeypatch.setattr(policy_service.policy_repository, "add_saved_policy", lambda db, *, user_id, policy_id: captured.update({"user_id": user_id, "policy_id": policy_id}))

    payload = policy_service.save_policy("stay-discount-jeonnam-gangjin", fake_db, user)

    assert payload == {"policyId": "stay-discount-jeonnam-gangjin", "saved": True}
    assert captured == {"user_id": user.id, "policy_id": 188}
```

- [ ] **Step 2: Run the policy service tests and verify they fail**

Run:

```bash
cd backend
python -m pytest tests/test_policy_db_service.py -k "stay_discount" -q
```

Expected: failures around virtual projection and canonical save behavior.

- [ ] **Step 3: Remove virtual projection from policy list**

In `backend/app/services/policies.py`, replace `list_policies` with:

```python
def list_policies(db: Session | None = None) -> list[dict[str, object]]:
    if db is None:
        raise RuntimeError("DB session is required.")
    return [policy_to_api(policy) for policy in policy_repository.list_policies(db)]
```

- [ ] **Step 4: Prefer concrete policy rows for detail/save/remove**

In `get_policy`, look up the actual policy row first:

```python
policy = policy_repository.get_policy_by_slug_any_status(db, policy_slug)
if policy is not None:
    if not is_public_policy(policy):
        return None
    return policy_to_api(policy)
```

Keep `resolve_stay_discount_alias_slug` only after this block as a temporary read-only fallback for pre-migration environments.

In `save_policy` and `remove_saved_policy`, remove canonical alias resolution and use:

```python
policy = policy_repository.get_policy_by_slug(db, policy_slug)
```

Return `None` if no active row exists.

- [ ] **Step 5: Run policy tests**

Run:

```bash
cd backend
python -m pytest tests/test_policy_db_service.py tests/test_policy_normalization.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/policies.py backend/tests/test_policy_db_service.py .agent/evals/api-contract-golden.json
git commit -m "Use concrete stay discount policy rows"
```

Use Lore trailers in the real commit message.

---

### Task 4: Make Trip Linking Return One Area Policy Card

**Files:**
- Modify: `backend/app/services/trips.py`
- Modify: `backend/tests/test_trip_db_service.py`
- Modify: `backend/tests/test_trip_db_routes.py`
- Modify: `frontend/src/app/__tests__/trip-detail.test.tsx`
- Modify: `frontend/src/app/__tests__/policies.test.tsx`

**Interfaces:**
- Consumes: stay-discount area rows created by Task 2.
- Produces: `trip_policies.policy_id` points to the area `policies.id`, not the canonical source policy id.
- Produces: `Trip.linkedPolicies[]` contains exactly one item for the attached area policy slug.

- [ ] **Step 1: Update failing backend trip tests**

In `backend/tests/test_trip_db_service.py`, replace canonical alias expectations:

```python
def test_add_policy_to_trip_uses_stay_discount_area_policy_id(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    area_policy = make_stay_policy()
    area_policy.id = 188
    area_policy.slug = "stay-discount-jeonnam-gangjin"
    area_policy.title = "[강진] 2026 대한민국 숙박세일 페스타 숙박 할인"
    area_policy.region = "전남"

    monkeypatch.setattr(trip_service.trip_repository, "get_accessible_trip_by_id", lambda *_args, **_kwargs: trip)
    monkeypatch.setattr(trip_service.policy_repository, "get_policy_by_slug", lambda db, slug: area_policy if db is fake_db and slug == area_policy.slug else None)
    monkeypatch.setattr(trip_service.trip_repository, "get_trip_policy", lambda db, *, trip_id, policy_id: None)
    captured: dict[str, object] = {}
    monkeypatch.setattr(trip_service.trip_repository, "add_trip_policy", lambda db, *, trip_id, policy_id: captured.update({"trip_id": trip_id, "policy_id": policy_id}))

    payload = trip_service.add_policy_to_trip(fake_db, user, "7", "stay-discount-jeonnam-gangjin")

    assert payload == {"tripId": "7", "policyId": "stay-discount-jeonnam-gangjin", "added": True}
    assert captured == {"trip_id": trip.id, "policy_id": 188}
```

Add linked-policy serialization test:

```python
def test_trip_to_api_returns_single_stay_discount_area_link() -> None:
    trip = make_trip()
    area_policy = make_stay_policy()
    area_policy.id = 188
    area_policy.slug = "stay-discount-jeonnam-gangjin"
    area_policy.title = "[강진] 2026 대한민국 숙박세일 페스타 숙박 할인"
    area_policy.region = "전남"
    trip.policies[0].policy = area_policy

    payload = trip_service.trip_to_api(trip, make_user(1))

    assert payload["linkedPolicies"] == [
        {
            "slug": "stay-discount-jeonnam-gangjin",
            "title": "[강진] 2026 대한민국 숙박세일 페스타 숙박 할인",
            "amount": "2/3/5/7만원 할인권",
            "region": "전남",
            "status": "active",
        }
    ]
```

- [ ] **Step 2: Run the trip tests and verify they fail**

Run:

```bash
cd backend
python -m pytest tests/test_trip_db_service.py -k "stay_discount or linked" -q
```

Expected: failures where alias slugs still resolve to canonical policy ids.

- [ ] **Step 3: Resolve request slugs by concrete policy row**

In `backend/app/services/trips.py`, change `_resolve_policy_for_request_slug`:

```python
def _resolve_policy_for_request_slug(
    db: Session,
    policy_slug: str,
) -> tuple[Policy | None, stay_discount_aliases.StayDiscountAliasArea | None]:
    policy = policy_repository.get_policy_by_slug(db, policy_slug)
    if policy is not None:
        return policy, None

    alias_resolution = stay_discount_aliases.resolve_stay_discount_alias_slug(db, policy_slug)
    if alias_resolution is not None:
        policy = alias_resolution.canonical_policy
        if not is_public_policy(policy):
            return None, None
        return policy, alias_resolution.alias_area
    return None, None
```

The fallback remains only to avoid breaking a half-migrated DB during rollout. After area rows exist, the first branch is always used.

- [ ] **Step 4: Simplify linked policy serialization**

Keep `_linked_policies` alias override support for `create_trip` fallback compatibility, but ensure ordinary area rows pass through untouched. No frontend-specific dedupe should be needed when the backend returns the actual area slug.

- [ ] **Step 5: Update frontend duplicate-display test**

In `frontend/src/app/__tests__/trip-detail.test.tsx`, add a regression test:

```tsx
it("does not duplicate a stay discount area policy after attaching and opening the trip", async () => {
  const trip: Trip = {
    ...getPreviewTrip(),
    id: "27",
    linkedPolicies: [
      {
        slug: "stay-discount-jeonnam-gangjin",
        title: "[강진] 2026 대한민국 숙박세일 페스타 숙박 할인",
        amount: "최대 7만원",
        region: "전남",
      },
    ],
    days: { 1: [] },
  };
  const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

  try {
    await login();
    cleanup();
    render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: "/trips/27",
            state: {
              linkedPolicy: {
                slug: "stay-discount-jeonnam-gangjin",
                title: "[강진] 2026 대한민국 숙박세일 페스타 숙박 할인",
                amount: "최대 7만원",
                region: "전남",
              },
            },
          },
        ]}
      >
        <AppProviders>
          <App />
        </AppProviders>
      </MemoryRouter>,
    );

    const linkedRegion = await screen.findByRole("region", { name: "연결된 정책" });
    expect(within(linkedRegion).getAllByText("[강진] 2026 대한민국 숙박세일 페스타 숙박 할인")).toHaveLength(1);
    expect(within(linkedRegion).queryByText("2026 대한민국 숙박세일 페스타 숙박 할인")).not.toBeInTheDocument();
  } finally {
    getTripSpy.mockRestore();
  }
});
```

- [ ] **Step 6: Run backend and frontend focused tests**

Run:

```bash
cd backend
python -m pytest tests/test_trip_db_service.py tests/test_trip_db_routes.py -q

cd ../frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx src/app/__tests__/policies.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/trips.py backend/tests/test_trip_db_service.py backend/tests/test_trip_db_routes.py frontend/src/app/__tests__/trip-detail.test.tsx frontend/src/app/__tests__/policies.test.tsx
git commit -m "Link trips to stay discount area policies"
```

Use Lore trailers in the real commit message.

---

### Task 5: Backfill Current DB Links And Document Rollout

**Files:**
- Create: `backend/app/scripts/migrate_stay_discount_area_policy_links.py`
- Modify: `docs/mvp-api-contract.md`
- Modify: `docs/db-schema-current.md`
- Modify: `docs/db-schema-current.sql`
- Modify: `docs/implemented-feature-spec.md`
- Modify: `CHECKLIST.md`

**Interfaces:**
- Consumes: real area policy rows from Task 2.
- Produces: JSON migration report with `createdAreaPolicyCount`, `migratedTripPolicyCount`, `ambiguousTripPolicyCount`, and `leftCanonicalSavedPolicyCount`.
- Produces: existing `trip_policies` rows that can be confidently matched to a trip locality are moved from canonical stay-discount `policy_id` to the matching area `policy_id`.

- [ ] **Step 1: Write script unit test for confident trip-link migration**

Add to `backend/tests/test_trip_db_service.py` or create `backend/tests/test_stay_discount_area_migration.py`:

```python
def test_migrate_stay_discount_trip_link_to_matching_area_policy(db: Session) -> None:
    from datetime import date, datetime

    from sqlalchemy import select

    from app.models import ExternalSourceRecord, Policy, Trip, TripPolicy, User
    from app.scripts import migrate_stay_discount_area_policy_links

    user = User(email="stay-migrate@example.com", nickname="여행자")
    db.add(user)
    db.flush()

    record = ExternalSourceRecord(
        source_name="대한민국 숙박세일 페스타",
        source_type="official_campaign",
        source_url="https://ktostay.visitkorea.or.kr/",
        source_category="stay_discount",
        external_id="stay-discount",
        canonical_key="stay-discount",
        detail_url="https://ktostay.visitkorea.or.kr/",
        collected_page_url="https://ktostay.visitkorea.or.kr/",
        title="2026 대한민국 숙박세일 페스타 숙박 할인",
        organizer_text="문화체육관광부, 한국관광공사",
        organizers=["문화체육관광부", "한국관광공사"],
        region="비수도권·인구감소지역",
        city=None,
        is_nationwide=False,
        status_text="진행중",
        status="active",
        start_date=date(2026, 6, 11),
        end_date=date(2026, 7, 31),
        benefit_text="2/3/5/7만원 할인권",
        benefit_value_text="2/3/5/7만원 할인권",
        extracted_amount_krw=70000,
        extracted_discount_percent=None,
        benefit_value_type="amount",
        tags=["숙박", "숙박세일"],
        contact_text=None,
        inferred_travel_styles=["휴식"],
        confidence=90,
        field_completeness=90,
        raw_list_text="숙박세일",
        raw_detail_text="숙박세일",
        raw_payload={
            "eligibleAreas": [{"sido": "전남", "cities": ["강진군"]}],
            "eligibleAreaCount": 1,
        },
        last_fetched_at=datetime(2026, 8, 18, 0, 0, 0),
        last_verified_at=datetime(2026, 8, 18, 0, 0, 0),
        freshness_status="fresh",
    )
    db.add(record)
    db.flush()

    canonical = Policy(
        slug=f"travelmonth-{record.id}",
        title="2026 대한민국 숙박세일 페스타 숙박 할인",
        organization="문화체육관광부, 한국관광공사",
        policy_type="숙박",
        description="숙박 할인",
        benefit_amount=70000,
        benefit_detail="2/3/5/7만원 할인권",
        target_condition="참여 온라인 여행사에서 발급",
        region="비수도권·인구감소지역",
        start_date=date(2026, 6, 11),
        end_date=date(2026, 7, 31),
        official_url="https://ktostay.visitkorea.or.kr/",
        policy_comment="숙박 할인",
        source_type="official_campaign",
        source_name="대한민국 숙박세일 페스타",
        source_category="stay_discount",
        external_source_record_id=record.id,
        source_url="https://ktostay.visitkorea.or.kr/",
        source_canonical_key="stay-discount",
        verification_status="fresh",
        status="active",
    )
    db.add(canonical)
    db.flush()

    trip = Trip(
        owner_id=user.id,
        title="강진 3일 여행",
        start_date=date(2026, 6, 15),
        end_date=date(2026, 6, 17),
        status="draft",
        region="강진",
        participant_count=1,
        description="강진 여행",
    )
    db.add(trip)
    db.flush()

    db.add(TripPolicy(trip_id=trip.id, policy_id=canonical.id))
    db.commit()

    report = migrate_stay_discount_area_policy_links.run(db)

    assert report["migratedTripPolicyCount"] == 1
    assert report["ambiguousTripPolicyCount"] == 0
    link = db.scalar(select(TripPolicy).where(TripPolicy.trip_id == trip.id))
    area_policy = db.scalar(select(Policy).where(Policy.slug == "stay-discount-jeonnam-gangjin"))
    assert area_policy is not None
    assert link is not None
    assert link.policy_id == area_policy.id
```

- [ ] **Step 2: Implement the migration script**

Create `backend/app/scripts/migrate_stay_discount_area_policy_links.py` with:

```python
from __future__ import annotations

import json
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Policy, TripPolicy, UserSavedPolicy
from app.repositories import external_sources
from app.services import stay_discount_aliases
from app.services.policy_normalization import promote_external_benefits_to_policies


def _normalized(value: str | None) -> str:
    return "".join(str(value or "").split()).replace("시", "").replace("군", "")


def _matching_area_policy(db: Session, trip_policy: TripPolicy) -> Policy | None:
    trip = trip_policy.trip
    canonical = trip_policy.policy
    if trip is None or canonical is None or canonical.external_source_record_id is None:
        return None
    record = external_sources.get_external_source_record_by_id(db, canonical.external_source_record_id)
    aliases = stay_discount_aliases.alias_areas_for_record(record)
    trip_text = _normalized(" ".join([trip.title or "", trip.region or "", trip.travel_area_id or ""]))
    matches = [
        alias
        for alias in aliases
        if _normalized(alias.city) in trip_text or _normalized(alias.sido + alias.city) in trip_text
    ]
    if len(matches) != 1:
        return None
    return db.scalar(select(Policy).where(Policy.slug == matches[0].slug, Policy.status == "active"))


def run(db: Session) -> dict[str, int]:
    promote_external_benefits_to_policies(db)
    migrated = 0
    ambiguous = 0
    canonical_links = db.scalars(
        select(TripPolicy)
        .join(TripPolicy.policy)
        .where(Policy.source_category == stay_discount_aliases.SOURCE_CATEGORY)
        .where(Policy.slug.like("travelmonth-%"))
    ).all()
    for link in canonical_links:
        area_policy = _matching_area_policy(db, link)
        if area_policy is None:
            ambiguous += 1
            continue
        existing = db.scalar(
            select(TripPolicy).where(
                TripPolicy.trip_id == link.trip_id,
                TripPolicy.policy_id == area_policy.id,
            )
        )
        if existing is not None:
            db.delete(link)
        else:
            link.policy_id = area_policy.id
        migrated += 1
    db.commit()
    left_saved = db.execute(
        select(func.count())
        .select_from(UserSavedPolicy)
        .join(Policy, Policy.id == UserSavedPolicy.policy_id)
        .where(Policy.source_category == stay_discount_aliases.SOURCE_CATEGORY)
        .where(Policy.slug.like("travelmonth-%"))
    ).scalar_one()
    return {
        "migratedTripPolicyCount": migrated,
        "ambiguousTripPolicyCount": ambiguous,
        "leftCanonicalSavedPolicyCount": left_saved,
    }


def main() -> None:
    with SessionLocal() as db:
        print(json.dumps(run(db), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run migration script locally against compose DB**

Run:

```bash
cd backend
python -m app.scripts.migrate_stay_discount_area_policy_links
```

Expected JSON keys:

```json
{
  "ambiguousTripPolicyCount": 0,
  "leftCanonicalSavedPolicyCount": 1,
  "migratedTripPolicyCount": 1
}
```

The exact counts can differ by local seed data. `ambiguousTripPolicyCount` must be reviewed before production rollout.

- [ ] **Step 4: Update docs**

Update `docs/mvp-api-contract.md` policy section:

```markdown
`stay_discount` source records are normalized into one active `policies` row per eligible municipality, using `stay-discount-{sidoSlug}-{citySlug}` slugs. The source-level `travelmonth-{externalSourceRecordId}` row is retained only as hidden canonical/source evidence and is not used for public save or trip-link mutations.
```

Update trip section:

```markdown
`linkedPolicies` returns the concrete `policies.slug` stored through `trip_policies.policy_id`; stay-discount area policies are not re-expanded or remapped at read time.
```

Update `docs/db-schema-current.md`:

```markdown
`policies.external_source_record_id` is a non-unique source-evidence reference. Multiple public policies may point at one `external_source_records` row when one official source contains multiple municipality-level benefits.
```

- [ ] **Step 5: Run full relevant verification**

Run:

```bash
cd backend
python -m pytest tests/test_db_schema.py tests/test_policy_normalization.py tests/test_policy_db_service.py tests/test_trip_db_service.py tests/test_trip_db_routes.py -q
alembic upgrade head --sql

cd ../frontend
npx vitest run src/app/__tests__/trip-detail.test.tsx src/app/__tests__/policies.test.tsx
npm run typecheck
npm run build

cd ..
git diff --check
node -e "const fs=require('fs'); const {execSync}=require('child_process'); const files=execSync('git diff --name-only',{encoding:'utf8'}).trim().split('\\n').filter(Boolean); for (const file of files) { if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) continue; const text=fs.readFileSync(file,'utf8'); if (text.includes('\\uFFFD')) { console.error('replacement char in '+file); process.exit(1); } } console.log('utf8 ok')"
```

Expected: all commands PASS.

- [ ] **Step 6: Update CHECKLIST.md**

Record only current status, validation evidence, and active risk:

```markdown
## Current Status

- Stay-discount municipality benefits now use concrete `policies` rows for public save/trip-link behavior.
- Canonical `travelmonth-*` stay-discount source rows are hidden evidence rows.

## Recent Validation

- `python -m pytest tests/test_db_schema.py tests/test_policy_normalization.py tests/test_policy_db_service.py tests/test_trip_db_service.py tests/test_trip_db_routes.py -q`
- `alembic upgrade head --sql`
- `npx vitest run src/app/__tests__/trip-detail.test.tsx src/app/__tests__/policies.test.tsx`
- `npm run typecheck`
- `npm run build`
- `git diff --check`
- UTF-8 replacement-character scan

## Remaining Risks

- Existing canonical stay-discount saved-policy rows do not contain enough locality information to infer the user's selected municipality; they remain hidden from public saved-policy lists until the user saves a concrete area policy again.
- Existing canonical trip links are migrated only when the trip title/region/travel-area data identifies exactly one eligible municipality.
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/scripts/migrate_stay_discount_area_policy_links.py docs/mvp-api-contract.md docs/db-schema-current.md docs/db-schema-current.sql docs/implemented-feature-spec.md CHECKLIST.md
git commit -m "Document stay discount area policy rollout"
```

Use Lore trailers in the real commit message.

---

## Self-Review

- Spec coverage: The plan covers schema identity, normalization, public policy APIs, trip linking/display, migration of existing confident trip links, docs, evals, and checklist updates.
- Placeholder scan: No placeholder markers or open-ended test instructions remain; each task names files, test commands, and expected behavior.
- Type consistency: `Policy.external_source_record_id`, `TripPolicy.policy_id`, `Policy.slug`, `source_canonical_key`, `LinkedTripPolicy.slug`, and stay-discount helper names are used consistently across tasks.
- Known limitation: historical canonical saved-policy rows cannot preserve the selected municipality because the current DB stores only canonical `policy_id`; this is recorded as a rollout risk rather than guessed during migration.
