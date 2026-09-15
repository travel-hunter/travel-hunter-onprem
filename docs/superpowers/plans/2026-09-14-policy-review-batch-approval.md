# Policy Review Batch Approval and Pagination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an administrator page through pending policy candidates 50 at a time and approve either selected candidates or all pending candidates without exposing unapproved source text.

**Architecture:** Extend the existing candidate listing contract with total, limit, and offset. Add one transactional batch-approval endpoint that reuses the existing candidate approval service and commits only after every requested candidate is validated and promoted. The React review page owns page and selection state; it requests one page at a time and never treats an unseen page as selected.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL, React, TypeScript, Vitest, pytest.

**Spec:** `docs/superpowers/plans/2026-09-13-admin-policy-source-review.md`

## Global Constraints

- Keep public policy cards unchanged until an administrator approves a candidate.
- Preserve the existing single-candidate approve and reject endpoints.
- API DTO fields are camelCase; database columns remain snake_case.
- No schema migration is needed.
- Page size is exactly 50; all-pending approval is explicit and confirmation-gated.
- A batch is atomic: validation or promotion failure rolls back every candidate in that request.
- Update the API contract and backend/frontend types with every API shape change.
- Do not update CHECKLIST.md until the branch is ready to merge.

---

### Task 1: Add paged candidate listing and transactional batch approval API

**Files:**
- Modify: `backend/app/services/policy_candidate_review.py`
- Modify: `backend/app/schemas/admin.py`
- Modify: `backend/app/api/routes/admin.py`
- Modify: `backend/tests/test_policy_candidate_review.py`
- Modify: `backend/tests/test_admin_routes.py`
- Modify: `docs/mvp-api-contract.md`

**Interfaces:**
- Consumes: `list_pending_candidates(db, limit)`, `approve_candidate(db, candidate, record, admin, note)`.
- Produces: `list_pending_candidates(db, limit, offset)`, `count_pending_candidates(db)`, `approve_pending_candidates(db, candidate_ids, approve_all, admin)`.
- Produces: `GET /api/admin/policy-review-candidates?limit=50&offset=0` returning `{items,total,limit,offset}`.
- Produces: `POST /api/admin/policy-review-candidates/approve-batch` accepting `{candidateIds?: string[], approveAll?: boolean, note?: string}` and returning `{approvedCount, approvedCandidateIds}`.

- [x] **Step 1: Write failing backend tests**

Add a service test that creates two pending candidates, calls:
```python
approved = approve_pending_candidates(
    db,
    candidate_ids=[str(first.id), str(second.id)],
    approve_all=False,
    admin=admin,
)
assert [candidate.id for candidate in approved] == [first.id, second.id]
assert all(candidate.review_status == "approved" for candidate in approved)
```

Add a route test that stubs a total of 71 pending candidates and asserts:
```python
response = client.get("/api/admin/policy-review-candidates?limit=50&offset=50")
assert response.json()["total"] == 71
assert response.json()["limit"] == 50
assert response.json()["offset"] == 50
```

Add a route test that posts `{"candidateIds":["7","8"],"approveAll":false}` and asserts the batch service receives those exact IDs. Add a second test posting `{"approveAll":true}` and asserts the service receives the all-pending mode.

- [x] **Step 2: Run backend tests to verify RED**

Run:
```powershell
docker run --rm -v "${PWD}/.superpowers/worktrees/admin-policy-source-review/backend:/backend:ro" -w /backend -e PYTHONPATH=/backend travel-hunter-policy-review-backend:local python -m pytest tests/test_policy_candidate_review.py tests/test_admin_routes.py -q
```

Expected: FAIL because batch approval functions, request/response schemas, route, total, and offset do not exist.

- [x] **Step 3: Implement the minimal repository-service and route behavior**

Implement:
```python
def list_pending_candidates(db: Session, *, limit: int, offset: int = 0) -> list[tuple[PolicyReviewCandidate, ExternalSourceRecord]]:
    return list(
        db.execute(
            select(PolicyReviewCandidate, ExternalSourceRecord)
            .join(ExternalSourceRecord, PolicyReviewCandidate.external_source_record_id == ExternalSourceRecord.id)
            .where(PolicyReviewCandidate.review_status == "pending")
            .order_by(PolicyReviewCandidate.created_at.asc(), PolicyReviewCandidate.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
    )
```

Add `count_pending_candidates` using `select(func.count())`. Resolve every batch candidate before promotion, reject duplicate/non-pending/missing IDs with `ValueError`, then call the existing `approve_candidate` for each item. In the route, call `session.commit()` once after all approvals; on an exception call `session.rollback()` before returning an error.

Add Pydantic request/response DTOs, list response pagination fields, a maximum request size of 100 candidate IDs, and the `approve-batch` route before the parameterized `/{candidate_id}` routes.

- [x] **Step 4: Update contract and tests to GREEN**

Document query parameters, paged response, request validation, atomic rollback, and the two batch modes in `docs/mvp-api-contract.md`.

Run the Task 1 command again.

Expected: PASS.

- [x] **Step 5: Commit Task 1**

```powershell
git add backend/app/services/policy_candidate_review.py backend/app/schemas/admin.py backend/app/api/routes/admin.py backend/tests/test_policy_candidate_review.py backend/tests/test_admin_routes.py docs/mvp-api-contract.md
git commit -m "feat: page and batch-approve policy review candidates"
```

### Task 2: Add paged selection and all-pending approval controls to the admin review page

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/dataApi.ts`
- Modify: `frontend/src/api/backendApi.ts`
- Modify: `frontend/src/pages/admin/AdminPages.tsx`
- Modify: `frontend/src/pages/admin/AdminPages.test.tsx`

**Interfaces:**
- Consumes: `listAdminPolicyReviewCandidates({limit, offset})` and `approveAdminPolicyReviewCandidates({candidateIds, approveAll})`.
- Produces: a page-local `offset`, `total`, and `selectedCandidateIds` state; page size `50`.

- [x] **Step 1: Write failing frontend tests**

Add a test with 71 candidates and a list response:
```ts
{ items: [candidate51], total: 71, limit: 50, offset: 50 }
```

Render the review page after moving forward and assert it displays `Candidate 51` and `2 / 2`, enables `선택 승인` only after a checkbox is selected, calls `approveAdminPolicyReviewCandidates({ candidateIds, approveAll: false })` with exactly the selected ids, and calls `{ candidateIds: [], approveAll: true }` for `전체 승인` only after `window.confirm` returned true with a message that states the total (`71건`).

- [x] **Step 2: Run frontend tests to verify RED**

Run: `cd frontend && npx vitest run src/pages/admin/AdminPages.test.tsx`
Expected: FAIL because the review page has no checkboxes, batch buttons, or pagination.

- [x] **Step 3: Implement the minimal page state and controls**

In `AdminPolicyReviewPage`: `REVIEW_PAGE_SIZE = 50`, page-local `offset`/`total`/`selectedIds`; `load()` passes `{ limit, offset }` and clears the selection; a checkbox per candidate (`aria-label="<title> 선택"`); `선택 승인` (disabled with no selection) and `전체 승인` (disabled when `total === 0`), both gated by `window.confirm` whose text states the count; reuse the `admin-pagination` block (`이전` / `n / m` / `다음`). The single-candidate `반려` / `승인하고 공개` buttons are unchanged. A failed batch shows one error line saying nothing in that request was published (the API is atomic).

- [x] **Step 4: Run frontend tests to verify GREEN**

Run: `cd frontend && npx vitest run src/pages/admin/AdminPages.test.tsx && npm run typecheck && npm run build && npm run test:mojibake`
Expected: PASS.

- [x] **Step 5: Commit Task 2**

```bash
git add frontend/src/pages/admin/AdminPages.tsx frontend/src/pages/admin/AdminPages.test.tsx docs/superpowers/plans/2026-09-14-policy-review-batch-approval.md
git commit -m "feat: page and batch-approve policy review candidates in the admin UI"
```

## Verification

- Backend: `cd backend && python -m pytest -q` (batch route tests in `tests/test_admin_routes.py`, atomic rollback in `tests/test_policy_candidate_review.py`).
- Frontend: `cd frontend && npx vitest run && npm run typecheck && npm run build && npm run test:mojibake`.
- Isolated stack (`policy-source-review`, 5174/8002): approve a selected subset, confirm only those candidates become `approved`, then move to page 2 and confirm the remaining pending count. Do not update `CHECKLIST.md` until merge-ready.

> 2026-09-14: lines after Task 2 Step 1 of this file were byte-corrupted in the original commit (1789d2e); this tail was rewritten from the implemented behavior.
