# Admin-Reviewed Policy Source Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Detect new policies from approved official sources automatically, then let an administrator review and publish each new or materially changed policy without allowing arbitrary URL crawling.

**Architecture:** Code owns source adapters and their allowed official hostnames. The database owns whether each registered source is enabled and how its detected records are handled. Collection writes source evidence and candidate-review state first; only an explicit approval creates or updates a public Policy. The existing policy text remains stable until an administrator approves a replacement.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, React, TypeScript, AppDataApi, pytest, Vitest.

**Spec:** docs/mvp-api-contract.md, docs/implemented-feature-spec.md, docs/db-schema-current.md, docs/policy-collection-to-screen-flow.md.

## Global Constraints

- No administrator-entered URL may be fetched by the collector.
- A source adapter, its official hostname allowlist, parser, fixtures, and tests are code-reviewed before it can appear in the catalog.
- Source collection never directly changes a public Policy record.
- A new candidate needs administrator approval before public publication in the first release.
- A material source change never overwrites current policy-card display text automatically.
- Existing public policies and external-source records must be migrated without losing links, saved policies, trip attachments, or raw evidence.
- All new admin endpoints require require_admin_user.
- API DTO fields use camelCase; DB columns use snake_case.
- Government24 and arbitrary municipality crawling are out of scope.
- Existing scheduler configuration remains the timing authority; this plan does not add a second scheduler.

---

## User flow

~~~text
Code-reviewed source adapter registered
  -> admin enables source
  -> scheduled or manual collection fetches official source
  -> external evidence is upserted
  -> candidate is classified: new / changed / unchanged / unavailable
  -> admin sees candidate and source health
  -> approve creates or updates public policy
  -> reject preserves evidence but keeps it non-public
  -> expired policy follows existing visibility rule
~~~

The administrator can enable, disable, collect, review, approve, reject, and inspect a known source. The administrator cannot create a fetch target, replace a parser, or change an official hostname.

## File map

- Create: backend/alembic/versions/0038_policy_source_catalog.py
- Modify: backend/app/models/tables.py
- Modify: backend/app/models/__init__.py
- Create: backend/app/repositories/policy_collection_sources.py
- Create: backend/app/repositories/policy_review_candidates.py
- Create: backend/app/services/policy_source_catalog.py
- Create: backend/app/services/policy_candidate_review.py
- Modify: backend/app/services/external_benefit_collection.py
- Modify: backend/app/services/policy_normalization.py
- Modify: backend/app/services/external_collection_scheduler.py
- Modify: backend/app/api/routes/ops.py
- Modify: backend/app/schemas/ops.py
- Modify: backend/app/schemas/external_sources.py
- Modify: backend/app/api/routes/admin.py and backend/app/services/admin.py only for audit-log integration if existing ops audit cannot be reused
- Modify: frontend/src/api/dataApi.ts
- Modify: frontend/src/api/backendApi.ts
- Modify: frontend/src/api/types.ts
- Modify: frontend/src/pages/admin/AdminPages.tsx
- Modify: frontend/src/pages/admin/AdminPages.test.tsx
- Modify: frontend/src/app/App.tsx only if a separate review page is needed
- Modify: frontend/src/styles/app.css only for new admin review UI styles
- Create: backend/tests/test_policy_source_catalog.py
- Create: backend/tests/test_policy_candidate_review.py
- Modify: backend/tests/test_external_benefit_collection.py
- Modify: backend/tests/test_ops_routes.py
- Modify: backend/tests/test_policy_normalization.py
- Modify: backend/tests/test_external_collection_scheduler.py
- Modify: docs/policy-collection-to-screen-flow.md
- Modify: docs/mvp-api-contract.md
- Modify: docs/db-schema-current.md and docs/db-schema-current.sql

## Task 1: Add persisted state for approved source adapters

**Files:**
- Create: backend/alembic/versions/0038_policy_source_catalog.py
- Modify: backend/app/models/tables.py
- Modify: backend/app/models/__init__.py
- Create: backend/app/repositories/policy_collection_sources.py
- Test: backend/tests/test_policy_source_catalog.py

**Interfaces:**
- Produces model PolicyCollectionSource with key, adapter_key, official_url, source_category, display_name, enabled, publication_mode, expected_min_records, last_outcome, last_collected_at, last_successful_at, and last_error.
- Produces repository functions list_collection_sources, get_collection_source_by_key, update_collection_source_enabled, and record_collection_source_run.

- [ ] **Step 1: Write migration and repository tests first.**

~~~python
def test_builtin_source_rows_are_unique_and_disabled_only_when_configured(db):
    rows = list_collection_sources(db)
    assert {row.key for row in rows} >= {"local_half_trip", "digital_tourism_resident_card"}
    assert len({row.key for row in rows}) == len(rows)

def test_admin_can_toggle_enabled_but_cannot_change_adapter_or_url(db):
    source = get_collection_source_by_key(db, key="island_visit")
    update_collection_source_enabled(db, source=source, enabled=False)
    assert source.enabled is False
    assert source.adapter_key == "island_visit"
~~~

- [ ] **Step 2: Run the focused test and confirm it fails before the model and migration exist.**

Run: cd backend; python -m pytest tests/test_policy_source_catalog.py -q

- [ ] **Step 3: Add the migration.**

Create policy_collection_sources with a unique key, immutable adapter_key, immutable official_url, source category, enabled flag, publication mode, collection health fields, timestamps, and a check constraint restricting publication mode to review or auto_after_reviewed_baseline.

Seed the existing code-reviewed sources as review mode. Do not seed a Government24 source.

- [ ] **Step 4: Implement model and repository functions.**

Repository update functions only mutate enabled state and health fields. They must not accept arbitrary URL, adapter, parser, or hostname fields.

- [ ] **Step 5: Run focused tests and Alembic SQL review.**

~~~text
cd backend
python -m pytest tests/test_policy_source_catalog.py -q
alembic upgrade head --sql
~~~

- [ ] **Step 6: Commit.**

~~~text
git add backend/alembic/versions/0038_policy_source_catalog.py backend/app/models backend/app/repositories/policy_collection_sources.py backend/tests/test_policy_source_catalog.py
git commit -m "feat: add approved policy collection source catalog"
~~~

## Task 2: Store candidate review state beside source evidence

**Files:**
- Modify: backend/alembic/versions/0038_policy_source_catalog.py
- Modify: backend/app/models/tables.py
- Create: backend/app/repositories/policy_review_candidates.py
- Create: backend/app/services/policy_candidate_review.py
- Test: backend/tests/test_policy_candidate_review.py

**Interfaces:**
- Produces PolicyReviewCandidate is versioned by evidence fingerprint for each ExternalSourceRecord, preserving prior review history when evidence changes.
- Candidate fields: review_status pending | approved | rejected | superseded, change_kind new | material_change, evidence_fingerprint, reviewed_by_user_id, reviewed_at, review_note, published_policy_id.
- Produces classify_candidate, list_candidates, approve_candidate, and reject_candidate.

- [ ] **Step 1: Write candidate lifecycle tests.**

~~~python
def test_new_external_record_becomes_pending_candidate(db):
    candidate = classify_candidate(db, record=source_record)
    assert candidate.review_status == "pending"
    assert candidate.change_kind == "new"

def test_same_evidence_does_not_create_a_second_candidate(db):
    first = classify_candidate(db, record=source_record)
    second = classify_candidate(db, record=source_record)
    assert first.id == second.id

def test_material_change_supersedes_prior_rejected_candidate(db):
    rejected = reject_candidate(db, candidate=old_candidate, admin=admin, note="missing period")
    changed = classify_candidate(db, record=changed_record)
    assert changed.review_status == "pending"
    assert rejected.review_status == "superseded"
~~~

- [ ] **Step 2: Run the focused test and confirm it fails.**

Run: cd backend; python -m pytest tests/test_policy_candidate_review.py -q

- [ ] **Step 3: Implement deterministic evidence fingerprints.**

Fingerprint only policy-facing source fields: title, organizer, eligibility/benefit text, start/end date, region/city, official/detail URL, and normalized status. Do not use fetch timestamp or HTML formatting so an unchanged source does not reappear as a new candidate.

- [ ] **Step 4: Implement review actions.**

Approval records reviewer identity/time and produces a single promotion request. Rejection requires a short note and preserves raw evidence. Approval/rejection writes an admin audit log with safe IDs and no raw payload.

- [ ] **Step 5: Run focused tests and commit.**

~~~text
git add backend/app/models/tables.py backend/app/repositories/policy_review_candidates.py backend/app/services/policy_candidate_review.py backend/tests/test_policy_candidate_review.py
git commit -m "feat: queue collected policy candidates for review"
~~~

## Task 3: Separate collection from publication

**Files:**
- Modify: backend/app/services/external_benefit_collection.py
- Modify: backend/app/services/policy_normalization.py
- Modify: backend/app/repositories/external_sources.py
- Modify: backend/app/services/external_collection_scheduler.py
- Test: backend/tests/test_external_benefit_collection.py
- Test: backend/tests/test_policy_normalization.py
- Test: backend/tests/test_external_collection_scheduler.py

**Interfaces:**
- Consumes enabled PolicyCollectionSource rows and code-owned SourceDefinition adapters.
- Produces external evidence, source health, and review candidates.
- Public policy writes occur only through approve_candidate.

- [ ] **Step 1: Write non-publication collection tests.**

~~~python
def test_collection_creates_pending_candidate_not_public_policy(db, monkeypatch):
    result = collect_external_benefits_from_live_sources(db)
    assert result.sources[0].pending_candidate_count == 1
    assert db.query(Policy).count() == 0

def test_disabled_source_is_not_fetched(db, monkeypatch):
    set_source_enabled(db, key="island_visit", enabled=False)
    collect_external_benefits_from_live_sources(db)
    fetch.assert_not_called()
~~~

- [ ] **Step 2: Confirm tests fail under current immediate normalization behavior.**

Run: cd backend; python -m pytest tests/test_external_benefit_collection.py tests/test_policy_normalization.py -q

- [ ] **Step 3: Refactor orchestration.**

For every enabled catalog source, call only its matching code-owned adapter. Upsert evidence, classify candidate, and update source health. Do not call global policy_normalization during normal collection.

Existing sources are migrated with an approved baseline candidate linked to their current Policy; their existing policy text and associations remain unchanged.

- [ ] **Step 4: Implement approval-only promotion.**

approve_candidate may create a new Policy from approved evidence or prepare a proposed update. It never overwrites existing public display fields without explicit approval. Existing expiration and hidden-policy behavior remain unchanged.

- [ ] **Step 5: Keep scheduler behavior bounded.**

Scheduler calls the same collection path for enabled sources. It records inactive, parser_changed, and error outcomes per source; a failed optional source does not prevent other sources from producing candidates.

- [ ] **Step 6: Run targeted tests and commit.**

~~~text
cd backend
python -m pytest tests/test_external_benefit_collection.py tests/test_policy_normalization.py tests/test_external_collection_scheduler.py -q
git add backend/app/services backend/app/repositories/external_sources.py backend/tests/test_external_benefit_collection.py backend/tests/test_policy_normalization.py backend/tests/test_external_collection_scheduler.py
git commit -m "refactor: separate policy collection from publication"
~~~

## Task 4: Add source-catalog and candidate-review admin APIs

**Files:**
- Modify: backend/app/api/routes/ops.py
- Modify: backend/app/schemas/ops.py
- Test: backend/tests/test_ops_routes.py
- Modify: docs/mvp-api-contract.md

**Interfaces:**
- GET /api/ops/external-collection/sources returns catalog state and source health.
- PATCH /api/ops/external-collection/sources/{sourceKey} accepts only enabled.
- POST /api/ops/external-collection/run collects enabled sources and returns evidence/candidate counts.
- GET /api/ops/external-collection/candidates returns paginated pending, approved, rejected, or superseded candidates.
- POST /api/ops/external-collection/candidates/{candidateId}/approve publishes only that candidate.
- POST /api/ops/external-collection/candidates/{candidateId}/reject requires reviewNote.

- [ ] **Step 1: Write authorization and request-shape tests.**

~~~python
def test_non_admin_cannot_list_or_review_candidates(client, user_token):
    response = client.get("/api/ops/external-collection/candidates", headers=user_token)
    assert response.status_code == 403

def test_admin_can_approve_one_pending_candidate(client, admin_token):
    response = client.post(f"/api/ops/external-collection/candidates/{candidate_id}/approve", headers=admin_token)
    assert response.status_code == 200
    assert response.json()["reviewStatus"] == "approved"

def test_source_patch_rejects_url_or_adapter_fields(client, admin_token):
    response = client.patch("/api/ops/external-collection/sources/island_visit", json={"officialUrl": "https://invalid.example"}, headers=admin_token)
    assert response.status_code == 422
~~~

- [ ] **Step 2: Run the focused test and confirm it fails.**

Run: cd backend; python -m pytest tests/test_ops_routes.py -q

- [ ] **Step 3: Implement thin routes and strict DTOs.**

The source patch DTO has only enabled. Candidate list returns safe summary fields plus source URL, before/after field summary, status, and review metadata. It never returns raw HTML or sensitive configuration.

- [ ] **Step 4: Update API contract and run route tests.**

- [ ] **Step 5: Commit.**

~~~text
git add backend/app/api/routes/ops.py backend/app/schemas/ops.py backend/tests/test_ops_routes.py docs/mvp-api-contract.md
git commit -m "feat: expose admin policy source review APIs"
~~~

## Task 5: Add the administrator source and candidate screens

**Files:**
- Modify: frontend/src/api/dataApi.ts
- Modify: frontend/src/api/backendApi.ts
- Modify: frontend/src/api/types.ts
- Modify: frontend/src/pages/admin/AdminPages.tsx
- Modify: frontend/src/pages/admin/AdminPages.test.tsx
- Modify: frontend/src/app/App.tsx only if route extraction makes the screen clearer
- Modify: frontend/src/styles/app.css only for dedicated review controls

**Interfaces:**
- AppDataApi exposes listPolicyCollectionSources, setPolicyCollectionSourceEnabled, runExternalCollection, listPolicyReviewCandidates, approvePolicyReviewCandidate, and rejectPolicyReviewCandidate.
- Admin UI shows source health and candidate queue only to an authenticated admin.

- [ ] **Step 1: Write UI tests before implementation.**

~~~tsx
it("shows a pending candidate with official source and approve/reject actions", async () => {
  vi.spyOn(appDataApi, "listPolicyReviewCandidates").mockResolvedValue(pendingResponse);
  renderAppRoute("/admin/policy-collection");
  expect(await screen.findByText("Island travel support")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve" })).toBeEnabled();
});

it("does not offer an editable URL field for a source", async () => {
  renderAppRoute("/admin/policy-collection");
  expect(screen.queryByLabelText("Official URL")).not.toBeInTheDocument();
});
~~~

- [ ] **Step 2: Run the focused Vitest file and confirm it fails.**

Run: cd frontend; npx vitest run src/pages/admin/AdminPages.test.tsx

- [ ] **Step 3: Build the admin page.**

Use two sections:
1. Source catalog: display name, official hostname, enabled switch, last outcome/time, pending count, and a collect-now action.
2. Candidate queue: source, category, region, title, date/benefit summary, official link, new/change indicator, and approve/reject controls.

A rejected candidate stays inspectable. A changed public policy shows a field summary and requires an approval action; it does not silently replace the card.

- [ ] **Step 4: Register the protected admin route and navigation entry.**

Use the existing AdminRoute and AppDataApi boundary. Do not add direct fetch calls in page code.

- [ ] **Step 5: Run focused tests, typecheck, and build.**

~~~text
cd frontend
npx vitest run src/pages/admin/AdminPages.test.tsx
npm run typecheck
npm run build
~~~

- [ ] **Step 6: Commit.**

~~~text
git add frontend/src/api frontend/src/pages/admin frontend/src/app/App.tsx frontend/src/styles/app.css
git commit -m "feat: add admin policy source review screen"
~~~

## Task 6: Migrate safely and verify the first source lifecycle

**Files:**
- Modify: docs/policy-collection-to-screen-flow.md
- Modify: docs/db-schema-current.md
- Modify: docs/db-schema-current.sql
- Test: backend/tests/test_policy_source_catalog.py
- Test: backend/tests/test_policy_candidate_review.py

- [ ] **Step 1: Verify migration against a copy of the development database.**

Before running it against any shared DB, create a backup outside the repository, validate it, and record counts for policies, external_source_records, user_saved_policies, and trip_policies. Do not migrate a server DB in this task.

- [ ] **Step 2: Run migration upgrade/downgrade/upgrade in local test data.**

~~~text
cd backend
alembic upgrade head
alembic downgrade -1
alembic upgrade head
~~~

- [ ] **Step 3: Confirm baseline migration invariants.**

Every existing public external policy retains the same id, slug, saved-policy links, trip-policy links, and display-text hash. Existing evidence receives no new public policy unless a newly collected candidate is approved.

- [ ] **Step 4: Test a complete controlled lifecycle with island policy fixture.**

Enable source -> collect -> pending candidate appears -> approve -> exactly one public policy appears -> recollect unchanged evidence -> no duplicate candidate -> change fixture -> pending material-change candidate -> reject -> public card unchanged.

- [ ] **Step 5: Run release checks.**

~~~text
cd backend
python -m pytest
alembic upgrade head --sql

cd ../frontend
npx vitest run
npm run typecheck
npm run build
npm run test:mojibake
~~~

- [ ] **Step 6: Update operational documentation and CHECKLIST.md at merge-ready state only.**

Document the approved-source onboarding path, candidate approval workflow, source outage handling, and no-arbitrary-URL rule. Record only current validation and active risk; do not paste raw source responses.

- [ ] **Step 7: Commit documentation.**

~~~text
git add docs/policy-collection-to-screen-flow.md docs/db-schema-current.md docs/db-schema-current.sql CHECKLIST.md
git commit -m "docs: document policy source review operations"
~~~

## Plan self-review

- Every new policy can be detected automatically from an enabled code-reviewed source, but no arbitrary website becomes a crawler target.
- New and changed policies require review before public card publication in the initial release.
- Existing policy-card text is protected by baseline migration and approval-only updates.
- Source health differentiates inactive campaign, parser change, source error, and successful no-change collection.
- Government24, municipality-wide discovery, and a second scheduler are explicitly out of scope.
