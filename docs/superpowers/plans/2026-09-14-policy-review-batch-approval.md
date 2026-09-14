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

- [ ] **Step 1: Write failing backend tests**

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

- [ ] **Step 2: Run backend tests to verify RED**

Run:
```powershell
docker run --rm -v "${PWD}/.superpowers/worktrees/admin-policy-source-review/backend:/backend:ro" -w /backend -e PYTHONPATH=/backend travel-hunter-policy-review-backend:local python -m pytest tests/test_policy_candidate_review.py tests/test_admin_routes.py -q
```

Expected: FAIL because batch approval functions, request/response schemas, route, total, and offset do not exist.

- [ ] **Step 3: Implement the minimal repository-service and route behavior**

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

- [ ] **Step 4: Update contract and tests to GREEN**

Document query parameters, paged response, request validation, atomic rollback, and the two batch modes in `docs/mvp-api-contract.md`.

Run the Task 1 command again.

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

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

- [ ] **Step 1: Write failing frontend tests**

Add a test with 71 candidates and a list response:
```ts
{ items: [candidate51], total: 71, limit: 50, offset: 50 }
```
Render the review page after moving forward and assert it displays b��y��y� 7;�u���t`, enables `5�Q�����������́���������A�����I�٥��������ѕ̡쁱������������͕���������()�����ѕ�Ёѡ�Ё�����́�����������є����������������͕����)�����)�����С��э���ɽٕM�䤹ѽ!�ٕ	��������]�Ѡ��(���������ѕ%���l��������є�ĉt�(�����ɽٕ��聙��͔�)���)���()�����ѕ�Ёѡ�Ё�����́��u���n�ן�w�Ћ�u���n�ן�w�ူ���Չ́�ݥ���ܹ�����ɵ���́��Ք��������͕����)�����)�����С��э���ɽٕM�䤹ѽ!�ٕ	��������]�Ѡ��(���������ѕ%���mt�(�����ɽٕ�����Ք�)���)���((��l�t���Mѕ����Iո��ɽ�ѕ���ѕ�ЁѼ�ٕɥ��I��()Iո�)�����ݕ�͡���)�����������ݕ�̽ݽɭ�ɕ�̽������������ͽ�ɍ��ɕ٥�ܽ�ɽ�ѕ��)����٥ѕ�Ё�ո��Ɍ�����̽����������A���̹ѕ�й���)���()����ѕ��%0������͔��������х��ф��������ѥ������������̰�������э��A$���ѡ��́�����Ё���и((��l�t���Mѕ����%�������Ёѡ����������A$���չ���䁅���U$��()U͔�)�����)����ЁIY%]}A}M%i�����)����Ёm���͕а�͕�=��͕�t���͕Mхє����)����Ёmѽх���͕�Q�х�t���͕Mхє����)����Ёm͕���ѕ�������ѕ%�̰�͕�M����ѕ�������ѕ%��t���͕Mхє�M�����ɥ�������܁M�Р���)���()1�����������ѕ́ݥѠ��쁱�����IY%]}A}M%i�����͕Ё��쁍���ȁ͕���ѥ���ݡ���ѡ�������������̸�������ɕ�е�����͕���е�����͕���ѥ���ѽ�������ɕ٥��̽���Ё����ɽ�̰���������ן�w���y��yЮ�ן�w����y��yр����ѽ����ͅ������ѥ��́ݡ������ɕ�Օ�Ё�́��������и�	���ɔ�͕���ѕ���������ɽم���������ݥ���ܹ�����ɵ��ݥѠ�ѡ���ᅍЁ�������є���չЁ�����хє�ѡ�Ё���ɽم���Չ��͡�́�����䁍�ɑ̸�=���Ս���́ɕ�����ѡ��ͅ�������쁥��ѡ�������������́����䁅�������͕Ѐ������ɕ�����ѡ���ɕ������������((��l�t���Mѕ����Iո��ɽ�ѕ���ѕ�ЁѼ�ٕɥ��I8��()Iո�)�����ݕ�͡���)�����������ݕ�̽ݽɭ�ɕ�̽������������ͽ�ɍ��ɕ٥�ܽ�ɽ�ѕ��)����٥ѕ�Ё�ո��Ɍ�����̽����������A���̹ѕ�й���)�����ո����������)�����ո��ե��)���()����ѕ��AML�((��l�t���Mѕ��������ЁQ�ͬ�Ȩ�()�����ݕ�͡���)��Ё�����ɽ�ѕ����Ɍ���������̹�́�ɽ�ѕ����Ɍ�������х����́�ɽ�ѕ����Ɍ����������������́�ɽ�ѕ����Ɍ�����̽����������A���̹�����ɽ�ѕ����Ɍ�����̽����������A���̹ѕ�й���)��Ё�����Ѐ���������������є�������э�����ɽٔ�������ɕ٥��̈)���((����Q�ͬ���Y�ɥ��A$�ͅ���䁅���ѡ�����Ё�ͽ��ѕ���͕ȁ����((������訨(��5�����聁���̽�������ݕ�̽����̼���ش���е������ɕ٥�ܵ��э�����ɽم���������ɬ�����ٕɥ�����хͭ́������є�((��%�ѕə����訨(�����յ���Q�ͬ�āA$�����Q�ͬ�ȁU$�(��Aɽ�Ս���م����ѥ����٥������ѡ�Ё����Չ������ɐ��́������������ɔ�������ɽم��ɕ�Օ�и((��l�t���Mѕ����Iո�����͕���ձ���х���ɕ�ɕ�ͥ���ѕ��̨�()Iո�)�����ݕ�͡���)�����ȁ�ո���ɴ��؀���A]����������ݕ�̽ݽɭ�ɕ�̽������������ͽ�ɍ��ɕ٥�ܽ�������轉�������ɼ���܀������������AeQ!=9AQ �����������Ʌٕ���չѕȵ������ɕ٥�ܵ�������鱽������ѡ��������ѕ�Ёѕ��̽ѕ��}������}�������ѕ}ɕ٥�ܹ��ѕ��̽ѕ��}�����}ɽ�ѕ̹��ѕ��̽ѕ��}��ѕɹ��}�������}������ѥ�����ѕ��̽ѕ��}������}ͽ�ɍ�}��х������ѕ��̽ѕ��}��}͍������䀵�)�����������ݕ�̽ݽɭ�ɕ�̽������������ͽ�ɍ��ɕ٥�ܽ�ɽ�ѕ��)����٥ѕ�Ё�ո��Ɍ�����̽����������A���̹ѕ�й���)���()����ѕ��AML�((��l�t���Mѕ����I��ե�������ѡ���ͽ��ѕ�����Ё�х����()Iո�)�����ݕ�͡���)�����ȁ�����͔����ɽ���е�����������ͽ�ɍ��ɕ٥�܀����ص��������؀�����������ݕ�̽ݽɭ�ɕ�̽������������ͽ�ɍ��ɕ٥�ܽ�����͔�兵����������Q5@�������ɕ٥�ܴ���й�ٕ�ɥ���兵�����������ե������������ɽ�ѕ��)���()����Ё�ո�ѡ�́������Ёѡ��ɽ�Ё��Ʌٕ���չѕȵ���ɕ�������͔��ɽ���и((��l�t���Mѕ����	ɽ�͕ȁ͵����ѕ�Ш�()M���������������������輼��ܸ���������р������ɴ������ā��̀����ȁ��ݕȁ�������ѕ̰����Ё���������͕́ѡ���ͱ�����������є��͕���ѥ��������������є�������́����ѡ�Ё��ɐ���ѕȁ�����ɵ�ѥ������������������ѡ���������ɽم�������ɵ�ѥ�������́���A$�ɕ�Օ�и((��l�t���Mѕ����������хѥ�������̨�()Iո�)�����ݕ�͡���)��Ё������������)ɜ�����qq������������ɽ�ѕ�������)���()����ѕ�聹���������ɽ�́�������ɕ��������Ё���Ʌ�ѕ�̸((��l�t���Mѕ��������ЁQ�ͬ�́���յ��хѥ����хє�����ݡ���ɕ��䨨()����Ё�����䁁!-1%MP�����չѥ��ѡ��������є������ɔ��Ʌ�����́ɕ��䁙�ȁ��ɝ���%��ѡ���������������́�ɔ�����ѕ��������Ё����ѡ������������ݥѠ�ѡ�������������ɔ������и