# Policy Expiration Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hide expired policies from every user-facing policy path immediately after their canonical deadline ends in KST, while preserving rows and preparing collection normalization to persist hidden state later.

**Architecture:** Define one pure KST-aware policy visibility rule and apply it both to SQL repository predicates and object-level service checks. Apply the same date predicate to external-source promotion/deactivation selection so future automatic collection cleans persisted state, while request-time filtering remains the always-on safety net.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2, PostgreSQL/SQLite test fixtures, pytest.

**Spec:** `docs/superpowers/specs/2026-09-09-policy-expiration-visibility-design.md`

## Implementation Status

Implemented on `feature/policy-expiration-visibility`. The KST boundary, public
repository filters, detail/save/remove/attachment alias guards, recommendations,
travel-area recommendations, collection promotion/deactivation, and existing
trip-linked policy responses all use the same expiration rule. An isolated
FastAPI route test confirms an expired row is absent from list/detail responses
while remaining in the database. Existing trip links also remain stored but are
excluded from `linkedPolicies` and `expectedSaving` after their deadline.

Verification on 2026-09-09: focused policy/recommendation suites and the new
trip-link regression passed. The full backend suite passed 784 tests with 18
skips. `git diff --check` passed and no U+FFFD replacement character was found
in changed Korean-bearing files. `CHECKLIST.md` remains unchanged because its
current production-cutover record belongs to a separate operational task; this
branch's verification evidence is retained here and in the PR.

## Global Constraints

- Do not delete policy, saved-policy, or trip-policy rows.
- Do not change database schema or public DTO fields.
- Use the KST calendar date; the deadline date remains visible until that day ends.
- Policies with no canonical `end_date` remain visible.
- Admin/history queries remain status-based and can show expired rows.
- Automatic collection settings and server environment values are outside scope.
- Follow TDD: each behavior test must fail for the expected reason before production code changes.

---

### Task 1: Define the KST-aware object visibility contract

**Files:**
- Modify: `backend/app/models/policy_status.py`
- Modify: `backend/app/services/policy_semantics.py`
- Test: `backend/tests/test_policy_semantics.py`

**Interfaces:**
- Produces: `policy_visibility_date(now: datetime | None = None) -> date`
- Produces: `is_public_policy_on_date(status: str | None, end_date: date | None, *, today: date | None = None) -> bool`
- Produces: `is_public_policy(policy: Any, *, today: date | None = None) -> bool`

- [ ] **Step 1: Write failing boundary tests**

```python
def test_public_policy_visibility_uses_status_and_canonical_end_date() -> None:
    today = date(2026, 9, 9)
    assert is_public_policy(SimpleNamespace(status="active", end_date=date(2026, 9, 8)), today=today) is False
    assert is_public_policy(SimpleNamespace(status="active", end_date=today), today=today) is True
    assert is_public_policy(SimpleNamespace(status="active", end_date=None), today=today) is True
    assert is_public_policy(SimpleNamespace(status="hidden", end_date=date(2026, 9, 10)), today=today) is False

def test_policy_visibility_date_uses_kst_calendar_boundary() -> None:
    instant = datetime(2026, 9, 8, 15, 0, tzinfo=timezone.utc)
    assert policy_visibility_date(instant) == date(2026, 9, 9)
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m pytest tests/test_policy_semantics.py -q`

Expected: FAIL because the date-aware functions/signature do not exist.

- [ ] **Step 3: Implement the pure visibility rule**

```python
KST = ZoneInfo("Asia/Seoul")

def policy_visibility_date(now: datetime | None = None) -> date:
    instant = now or datetime.now(KST)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=KST)
    return instant.astimezone(KST).date()

def is_public_policy_on_date(status, end_date, *, today=None):
    effective_today = today or policy_visibility_date()
    return is_public_policy_status(status) and (
        end_date is None or end_date >= effective_today
    )
```

Update `policy_semantics.is_public_policy` to delegate to this function using
`policy.status` and `policy.end_date`.

- [ ] **Step 4: Run the tests and verify GREEN**

Run: `python -m pytest tests/test_policy_semantics.py -q`

Expected: PASS.

### Task 2: Enforce expiration in policy repository queries

**Files:**
- Modify: `backend/app/repositories/policies.py`
- Test: `backend/tests/test_trip_db_service.py`

**Interfaces:**
- Replaces internal `_active_policy_clause()` with `_public_policy_clause(today: date | None = None)`.
- Existing public repository function signatures remain compatible.

- [ ] **Step 1: Add expired rows to repository visibility fixtures**

Add active policies ending yesterday, today, and with no deadline. Link the
expired row to both `UserSavedPolicy` and `TripPolicy`. Assert that every public
repository list excludes yesterday, includes today/no-deadline, and that
`get_policy_by_slug_any_status` can still retrieve the preserved expired row.

- [ ] **Step 2: Run repository tests and verify RED**

Run: `python -m pytest tests/test_trip_db_service.py -k "policy_repository" -q`

Expected: FAIL because the active expired row is returned.

- [ ] **Step 3: Add the SQL deadline predicate**

```python
def _public_policy_clause(today: date | None = None):
    effective_today = today or policy_visibility_date()
    return and_(
        Policy.status == POLICY_STATUS_ACTIVE,
        or_(Policy.end_date.is_(None), Policy.end_date >= effective_today),
    )
```

Use it for public listing, public slug lookup, saved/applied lists, applied links,
and photo-backfill candidates. Do not change admin repository queries.

- [ ] **Step 4: Run repository tests and verify GREEN**

Run: `python -m pytest tests/test_trip_db_service.py -k "policy_repository" -q`

Expected: PASS.

### Task 3: Block expired detail, save, aliases, attachment, and recommendations

**Files:**
- Modify: `backend/app/services/policies.py`
- Modify: `backend/app/services/trips.py`
- Test: `backend/tests/test_policy_db_service.py`
- Test: `backend/tests/test_trip_db_service.py`

**Interfaces:**
- Consumes: date-aware `is_public_policy(policy, today=...)`.
- Preserves existing 404/not-found and trip policy error contracts.

- [ ] **Step 1: Write failing service tests**

Cover an active policy ending yesterday through direct detail lookup, a digital
alias, a stay-discount alias, save, trip attachment, and recommendation candidate
selection. Assert absence/rejection while an active policy ending today remains
available.

- [ ] **Step 2: Run focused service tests and verify RED**

Run: `python -m pytest tests/test_policy_db_service.py tests/test_trip_db_service.py -k "expired_policy" -q`

Expected: at least the object-level alias or action paths expose the expired row.

- [ ] **Step 3: Apply object-level guards**

After alias resolution, require `is_public_policy(policy)` before returning
details, saving, or attaching. Recommendation candidates continue to use the
repository's public list, so no frontend filtering is added.

- [ ] **Step 4: Run focused service tests and verify GREEN**

Run: `python -m pytest tests/test_policy_db_service.py tests/test_trip_db_service.py -k "expired_policy" -q`

Expected: PASS.

### Task 4: Connect the same rule to future collection normalization

**Files:**
- Modify: `backend/app/repositories/external_sources.py`
- Test: `backend/tests/test_external_source_repository.py`
- Test: `backend/tests/test_policy_normalization.py`

**Interfaces:**
- `_policy_public_condition(today: date | None = None)` includes the canonical source deadline.
- Expired sources enter `list_policy_deactivation_records`; non-expired sources remain promotion candidates.

- [ ] **Step 1: Write failing source lifecycle tests**

Create active/fresh source records ending yesterday, today, and with no deadline.
Assert yesterday is excluded from promotion and included in deactivation, while
today/no-deadline remain eligible. Assert normalization hides the materialized
policy without deleting its row.

- [ ] **Step 2: Run lifecycle tests and verify RED**

Run: `python -m pytest tests/test_external_source_repository.py tests/test_policy_normalization.py -k "expired" -q`

Expected: FAIL because status/freshness currently override the elapsed deadline.

- [ ] **Step 3: Add the external-source deadline predicate**

```python
def _policy_deadline_condition(today: date | None = None):
    effective_today = today or policy_visibility_date()
    return or_(
        ExternalSourceRecord.end_date.is_(None),
        ExternalSourceRecord.end_date >= effective_today,
    )
```

Combine it with `_policy_public_condition`, raw public-detail lookup, and regional
recommendation source selection. Keep collector scheduling configuration out of
this change.

- [ ] **Step 4: Run lifecycle tests and verify GREEN**

Run: `python -m pytest tests/test_external_source_repository.py tests/test_policy_normalization.py -k "expired" -q`

Expected: PASS.

### Task 5: Synchronize contract and run release-level verification

**Files:**
- Modify: `docs/mvp-api-contract.md`
- Modify when merge-ready: `CHECKLIST.md`

**Interfaces:**
- Documents the effective public rule without changing response DTOs.

- [ ] **Step 1: Update the API contract**

Document that public lists/details/actions require active status and a canonical
deadline that is absent or not before the current KST date. State that expired
rows and relationships remain stored but disappear from user endpoints.

- [ ] **Step 2: Run focused and full backend verification**

Run:

```bash
cd backend
python -m pytest tests/test_policy_semantics.py tests/test_policy_db_service.py tests/test_trip_db_service.py tests/test_external_source_repository.py tests/test_policy_normalization.py -q
python -m pytest
```

Expected: all new tests pass; any baseline failure must be identified by exact
test name and compared with `origin/develop`.

- [ ] **Step 3: Run static and encoding checks**

Run:

```bash
git diff --check
rg -n "\uFFFD|\?\?\?\?" backend docs/mvp-api-contract.md
```

Expected: no diff errors and no newly introduced encoding corruption.

- [ ] **Step 4: Verify the development-data effect without mutation**

Call the branch backend against a copied or isolated database and verify that
the known 87 policies ending 2026-08-31 disappear from public `/api/policies`
while row/link counts remain unchanged. Do not alter the shared development or
production database for this verification.

- [ ] **Step 5: Update CHECKLIST only when the branch is merge-ready**

Replace the existing active risk about 87 expired policies with current validation
evidence and retain the separate scheduler risk until automatic collection is
designed and enabled.
