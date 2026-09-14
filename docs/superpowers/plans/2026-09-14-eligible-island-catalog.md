# Eligible Island Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 공식 섬 방문의 해 공지 Excel의 대상 섬을 관리자 승인 카탈로그로 관리하고, 승인된 정확 일치 장소에만 기존 섬 여행비 지원 정책을 추천한다.

**Architecture:** 기존 `island_visit` 정책 수집과 `PolicyReviewCandidate`는 그대로 둔다. 별도 카탈로그·스냅샷·스냅샷 항목·승인 목록을 만들고, 공지 첨부의 SHA-256 집합 지문이 바뀔 때만 pending 스냅샷을 만든다. 관리자 승인 시 카탈로그 행 잠금과 한 트랜잭션으로 승인 목록을 교체한다.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, httpx, `openpyxl>=3.1,<4.0`, React/Vite, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-09-14-eligible-island-catalog-design.md`

## Global Constraints

- `island_visit` 정책 카드의 기존 수집 텍스트, 제목, 혜택 문구를 변경하지 않는다.
- DB 필드는 `snake_case`, API DTO 필드는 `camelCase`를 쓴다.
- 정책 검토 후보와 대상 섬 카탈로그 후보는 API·화면·DB 테이블을 분리한다.
- 이름 일치는 Unicode NFC와 공백 축소 후의 완전 일치만 허용한다. 별칭, 접미어 제거, 부분 일치, 시도 단위 추론을 금지한다.
- 승인되지 않은 스냅샷은 공개 정책 응답과 일정 추천에 영향을 주지 않는다.
- 수집 실패, 열 누락, 빈 결과, 30% 초과 감소는 현재 승인 카탈로그를 보존한다.
- 실제 첨부 파일, 환경 변수, 토큰, DB URL은 테스트·커밋·로그에 넣지 않는다.
- 이 계획은 `0039_external_source_status_text` 다음 migration을 전제로 한다. 병합으로 head가 달라지면 Alembic head를 확인한 뒤 `down_revision`만 해당 head로 조정한다.

## File Structure

| File | Responsibility |
| --- | --- |
| `backend/app/models/tables.py` | 카탈로그·스냅샷·항목·승인 대상지 모델 |
| `backend/alembic/versions/0040_eligible_island_catalog.py` | 4개 테이블, 제약조건, 초기 카탈로그 |
| `backend/app/repositories/eligible_islands.py` | 승인 목록 조회와 카탈로그 행 잠금 |
| `backend/app/services/eligible_island_notice.py` | 공지 탐색, 첨부 다운로드, Excel 파싱 |
| `backend/app/services/eligible_island_catalog.py` | 지문, diff, 안전 게이트, 승인 교체 |
| `backend/app/api/routes/admin.py` | 관리자 카탈로그 API |
| `backend/app/services/policies.py`, `trips.py` | 정책 상세 파생 정보와 정확 일치 추천 |
| `frontend/src/pages/admin/AdminPages.tsx` | 분리된 대상 섬 갱신 검토 |

---

### Task 1: 승인형 카탈로그 스키마와 저장소

**Files:**
- Modify: `backend/requirements.txt`, `backend/app/models/tables.py`, `backend/app/models/__init__.py`, `backend/tests/test_db_schema.py`
- Create: `backend/alembic/versions/0040_eligible_island_catalog.py`, `backend/app/repositories/eligible_islands.py`, `backend/tests/test_eligible_island_repository.py`

**Interfaces:** Produces `EligibleIslandCatalog`, `EligibleIslandCatalogSnapshot`, `EligibleIslandSnapshotEntry`, `EligibleIsland`, `lock_catalog_row(db, *, catalog_key)`, and `list_approved_entries(db, *, catalog_key)`.

- [x] **Step 1: Write failing uniqueness tests.**

~~~python
def test_same_name_is_retained_when_jurisdiction_differs(db):
    snapshot = create_snapshot(db, catalog_key="island_visit_2026")
    add_snapshot_entry(db, snapshot=snapshot, name="가거도", jurisdiction="전남 신안군")
    add_snapshot_entry(db, snapshot=snapshot, name="가거도", jurisdiction="경남 통영시")
    db.commit()
    assert snapshot.entry_count == 2

def test_same_name_and_jurisdiction_is_rejected(db):
    snapshot = create_snapshot(db, catalog_key="island_visit_2026")
    add_snapshot_entry(db, snapshot=snapshot, name="가거도", jurisdiction="전남 신안군")
    add_snapshot_entry(db, snapshot=snapshot, name="가거도", jurisdiction="전남 신안군")
    with pytest.raises(IntegrityError):
        db.commit()
~~~

- [x] **Step 2: Run `cd backend && python -m pytest tests/test_eligible_island_repository.py tests/test_db_schema.py -q`; confirm it fails because the models are absent.**

- [x] **Step 3: Implement minimal schema and migration.** Add only `openpyxl>=3.1,<4.0`. Create catalog, snapshot, snapshot entry, and approved entry tables. Use unique `(snapshot_id, normalized_name, jurisdiction_name)` and `(catalog_id, normalized_name, jurisdiction_name)`, a snapshot status check for `pending|approved|rejected|superseded`, and a code-owned `island_visit_2026` row. Insert no island entries.

~~~python
def lock_catalog_row(db: Session, *, catalog_key: str) -> EligibleIslandCatalog:
    catalog = db.scalar(select(EligibleIslandCatalog).where(EligibleIslandCatalog.key == catalog_key).with_for_update())
    if catalog is None:
        raise EligibleIslandCatalogError("catalog_not_found")
    return catalog
~~~

- [x] **Step 4: Rerun focused tests and `cd backend && alembic upgrade head --sql`.** Expected: PASS; SQL creates only the four catalog tables.

- [x] **Step 5: Commit.**

~~~bash
git add backend/requirements.txt backend/app/models backend/app/repositories/eligible_islands.py backend/alembic/versions/0040_eligible_island_catalog.py backend/tests/test_eligible_island_repository.py backend/tests/test_db_schema.py
git commit -m "feat: add eligible island catalog schema"
~~~

### Task 2: 공식 공지 첨부 Excel 파서와 변경 감지

**Files:**
- Create: `backend/app/services/eligible_island_notice.py`, `backend/tests/test_eligible_island_notice.py`
- Modify: `backend/app/services/external_benefit_collection.py`, `backend/tests/test_external_benefit_collection.py`

**Interfaces:** Produces `ParsedIsland`, `SourceDocument`, `parse_eligible_island_xlsx(payload, *, filename)`, and `fetch_eligible_island_notice_snapshot`. Raises `EligibleIslandNoticeError` with `download_failed` or `parser_changed`.

- [x] **Step 1: Write failing in-memory Excel tests.**

~~~python
def test_parse_xlsx_requires_island_and_jurisdiction_columns():
    payload = make_xlsx_bytes(headers=["섬명", "시군구"], rows=[["가거도", "전남 신안군"]])
    assert parse_eligible_island_xlsx(payload, filename="eligible.xlsx").entries == [ParsedIsland("가거도", "가거도", "전남 신안군")]

def test_parse_xlsx_rejects_missing_jurisdiction_column():
    payload = make_xlsx_bytes(headers=["섬명"], rows=[["가거도"]])
    with pytest.raises(EligibleIslandNoticeError, match="parser_changed"):
        parse_eligible_island_xlsx(payload, filename="eligible.xlsx")
~~~

- [x] **Step 2: Run `cd backend && python -m pytest tests/test_eligible_island_notice.py -q`; confirm module-missing failure.**

- [x] **Step 3: Implement strict parsing.** Accept only same-host `.xlsx` attachment URLs and ZIP workbook bytes. Allow only explicit known aliases for island name and jurisdiction headers. Normalize with NFC plus whitespace collapse. Reject HTML, invalid or encrypted workbooks, unknown headers, blank names, and zero entries.

~~~python
def normalize_island_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())

def source_fingerprint(documents: list[SourceDocument]) -> str:
    body = "\n".join(sorted(f"{item.url}|{item.sha256}" for item in documents))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
~~~

- [x] **Step 4: Add tests for same fingerprint skip, download failure preservation, empty parse, and same-name same-jurisdiction dedupe.** Same aggregate fingerprint must not parse a workbook or write a snapshot.

- [x] **Step 5: Add `collect_eligible_island_catalog(db, *, fetched_at)` beside policy collection.** Existing `collect_external_benefits_from_live_sources` keeps producing one `island_visit` policy candidate with unchanged text and raw payload.

- [x] **Step 6: Run `cd backend && python -m pytest tests/test_eligible_island_notice.py tests/test_external_benefit_collection.py -q`; expected PASS. Commit `feat: detect official eligible island notice changes`.**

### Task 3: diff, safety gates, and atomic approval

**Files:**
- Create: `backend/app/services/eligible_island_catalog.py`, `backend/tests/test_eligible_island_catalog.py`
- Modify: `backend/app/repositories/eligible_islands.py`

**Interfaces:** Produces `stage_snapshot`, `approve_snapshot`, `reject_snapshot`, and `get_snapshot_diff`.

- [x] **Step 1: Write failing diff and large-shrink tests.**

~~~python
def test_stage_snapshot_records_added_and_removed_counts(db):
    approve_fixture_snapshot(db, [("가거도", "전남 신안군"), ("홍도", "전남 신안군")])
    candidate = stage_fixture_snapshot(db, [("가거도", "전남 신안군"), ("흑산도", "전남 신안군")])
    assert (candidate.added_count, candidate.removed_count, candidate.changed_count) == (1, 1, 0)

def test_large_shrink_preserves_approved_catalog(db):
    approve_fixture_snapshot(db, make_entries(100))
    result = stage_fixture_snapshot(db, make_entries(69))
    assert result.outcome == "suspicious_shrink"
    assert approved_names(db) == set(make_names(100))
~~~

- [x] **Step 2: Run `cd backend && python -m pytest tests/test_eligible_island_catalog.py -q`; confirm failure.**

- [x] **Step 3: Implement staging.** Diff keys are exactly `(normalized_name, jurisdiction_name)`. A nonempty, nonidentical, non-suspicious result becomes one pending snapshot. Mark older pending snapshots superseded. A removal ratio above 30% creates no candidate and preserves the approved list.

- [x] **Step 4: Implement approval with one locked transaction.**

~~~python
def approve_snapshot(db: Session, *, catalog_key: str, snapshot_id: int, admin: User):
    catalog = lock_catalog_row(db, catalog_key=catalog_key)
    snapshot = get_pending_snapshot_for_update(db, snapshot_id=snapshot_id, catalog_id=catalog.id)
    delete_approved_entries(db, catalog_id=catalog.id)
    copy_snapshot_entries_to_approved(db, snapshot=snapshot, catalog_id=catalog.id)
    catalog.approved_snapshot_id = snapshot.id
    snapshot.review_status = "approved"
    write_catalog_audit_log(db, catalog=catalog, snapshot=snapshot, admin=admin)
    return snapshot
~~~

Reject non-pending and superseded IDs. Do not mutate `policies`, `trip_policies`, or `PolicyReviewCandidate`.

- [x] **Step 5: Add lifecycle tests for rejection preservation, unapproved invisibility, atomic replacement, concurrent/stale approval rejection, and cross-jurisdiction duplicate retention.**

- [x] **Step 6: Run `cd backend && python -m pytest tests/test_eligible_island_catalog.py tests/test_eligible_island_repository.py -q`; expected PASS. Commit `feat: approve eligible island catalog updates`.**

### Task 4: 별도 관리자 검토 API

**Files:**
- Modify: `backend/app/schemas/admin.py`, `backend/app/api/routes/admin.py`, `backend/app/services/admin.py`, `backend/tests/test_admin_routes.py`, `docs/mvp-api-contract.md`

**Interfaces:** Produces admin-only collect, list, detail, approve, and reject routes below `/api/admin/eligible-island-catalogs/island_visit_2026`. The list accepts `limit` and `offset`; detail exposes paginated added, removed, and unchanged entries.

- [x] **Step 1: Write failing authorization and DTO isolation tests.**

~~~python
def test_non_admin_cannot_collect_or_approve_catalog(client, user_headers):
    assert client.post(COLLECT_URL, headers=user_headers).status_code == 403

def test_snapshot_item_has_catalog_diff_not_policy_review_fields(client, admin_headers):
    item = client.get(SNAPSHOT_LIST_URL, headers=admin_headers).json()["items"][0]
    assert {"addedCount", "removedCount", "sourceNoticeUrl", "attachmentFiles"} <= set(item)
    assert "externalSourceRecordId" not in item
~~~

- [x] **Step 2: Run `cd backend && python -m pytest tests/test_admin_routes.py -q`; confirm failure.**

- [x] **Step 3: Add `AdminEligibleIslandSnapshotItem`, `AdminEligibleIslandSnapshotDetail`, `AdminEligibleIslandSnapshotListResponse`, and `AdminEligibleIslandRejectRequest`.** Routes use `require_admin_user`, delegate to Task 3, return typed 400/404/409 errors, and never expose file bytes or stack traces.

- [x] **Step 4: Test rejected/superseded approval as 409, blank rejection note as 422, parser failure as health outcome, and zero calls to policy normalization. Update the API contract to state the path is independent of `/api/admin/policy-review-candidates`.**

- [x] **Step 5: Run `cd backend && python -m pytest tests/test_admin_routes.py tests/test_eligible_island_catalog.py -q`; expected PASS. Commit `feat: expose eligible island catalog review API`.**

### Task 5: 공개 정책 상세와 정확 일치 일정 추천

**Files:**
- Modify: `backend/app/schemas/policy.py`, `backend/app/services/policies.py`, `backend/app/services/trips.py`, `backend/tests/test_policy_service.py`, `backend/tests/test_trip_db_service.py`
- Modify: `frontend/src/api/types.ts`, `frontend/src/api/backendApi.ts`, `frontend/src/api/dataApi.ts`, `frontend/src/pages/PolicyPages.tsx`, `frontend/src/app/__tests__/policy-detail.test.tsx`

**Interfaces:** Produces optional `Policy.eligibleIslandCount` and `Policy.eligibleIslandsOfficialUrl`; island recommendation filtering reads approved entries only.

- [ ] **Step 1: Write failing policy-text preservation and exact-match tests.**

~~~python
def test_island_policy_exposes_approved_count_without_changing_text(db):
    policy = approved_island_policy(db, title="2026 섬 여행비 지원", benefit_text="최대 10만원")
    approve_fixture_snapshot(db, [("가거도", "전남 신안군")])
    payload = policy_to_api(policy, db=db)
    assert payload["eligibleIslandCount"] == 1
    assert payload["title"] == "2026 섬 여행비 지원"
    assert payload["amount"] == "최대 10만원"

def test_island_recommendation_requires_exact_normalized_place_name(db):
    approve_fixture_snapshot(db, [("가거도", "전남 신안군")])
    assert recommended_slugs_for_places(db, [" 가거도 "]) == {"2026-island-visit-support"}
    assert recommended_slugs_for_places(db, ["가거도 선착장"]) == set()
~~~

- [ ] **Step 2: Run `cd backend && python -m pytest tests/test_policy_service.py tests/test_trip_db_service.py -q`; confirm failure.**

- [ ] **Step 3: Implement narrow fields and predicate.** Populate fields only for `source_category == "island_visit"`, reading only approved catalog count and official URL. Apply the exact place predicate before `_trip_policy_candidate_score`; retain all existing scoring, locality filtering, and ordering. An empty approved catalog excludes only island policy.

~~~python
def _matches_approved_island(place_name: str, approved_names: set[str]) -> bool:
    return normalize_island_name(place_name) in approved_names
~~~

- [ ] **Step 4: Add optional frontend fields and detail UI.** Render `대상 섬 N곳` and `대상 섬 공식 안내` only when count is positive and URL is nonempty. Do not display the entire list or alter card title, summary, amount, or layout.

- [ ] **Step 5: Run `cd frontend && npx vitest run src/app/__tests__/policy-detail.test.tsx`; expected PASS, including an ordinary-policy no-section assertion. Commit `feat: recommend island support for approved exact matches`.**

### Task 6: 관리자 화면, 문서, 격리 실행 검증

**Files:**
- Modify: `frontend/src/pages/admin/AdminPages.tsx`, `frontend/src/pages/admin/AdminPages.test.tsx`, `frontend/src/styles/app.css`
- Modify: `docs/policy-collection-to-screen-flow.md`, `docs/db-schema-current.md`, `docs/db-schema-current.sql`
- Modify: `CHECKLIST.md` only when the branch is merge-ready

**Interfaces:** Consumes Task 4 catalog APIs and Task 5 policy fields.

- [ ] **Step 1: Write a failing separate-review UI test.**

~~~tsx
it("shows catalog changes separately from policy review candidates", async () => {
  vi.spyOn(appDataApi, "listAdminEligibleIslandSnapshots").mockResolvedValue(snapshotResponse);
  render(<AdminPolicyReviewPage />);
  expect(await screen.findByRole("heading", { name: "대상 섬 목록 갱신" })).toBeVisible();
  expect(screen.getByText("추가 3 · 삭제 1")).toBeVisible();
});
~~~

- [ ] **Step 2: Run `cd frontend && npx vitest run src/pages/admin/AdminPages.test.tsx`; confirm failure.**

- [ ] **Step 3: Keep `검토 대기 정책` unchanged and add `대상 섬 목록 갱신`.** Show counts, source links, warnings, and details. Approval requires browser confirmation that includes add/remove counts. Rejection requires a note. Do not add per-island approval.

- [ ] **Step 4: Document official-only source access, SHA no-change behavior, parser/empty/shrink safeguards, approval requirement, and first-run procedure: DB backup, collection, official total/region-file comparison, approval. Generate schema references from migration output.**

- [ ] **Step 5: Run final verification.**

~~~bash
cd backend
python -m pytest
alembic upgrade head --sql

cd ../frontend
npm run typecheck
npx vitest run
npm run build
npm run test:mojibake

cd ..
git diff --check
~~~

Expected: all changed targeted/full suites pass; migration SQL contains only catalog schema; changed Korean files contain no U+FFFD.

- [ ] **Step 6: Smoke test in an isolated Compose project and DB.** Collect fixture or official attachment, verify a pending snapshot, verify public policy unchanged, approve, verify exact `가거도` recommends the policy, verify `가거도 선착장` does not. Update `CHECKLIST.md` only after all gates pass.

- [ ] **Step 7: Commit merge-ready work.**

~~~bash
git add frontend/src/pages/admin/AdminPages.tsx frontend/src/pages/admin/AdminPages.test.tsx frontend/src/styles/app.css docs/policy-collection-to-screen-flow.md docs/db-schema-current.md docs/db-schema-current.sql CHECKLIST.md
git commit -m "feat: review eligible island catalog updates"
~~~

## Plan Self-Review

- Tasks 1-3 cover isolated data, fingerprinting, diff, approval, and safety; Task 4 covers separate admin API; Task 5 covers policy-detail and exact-match behavior; Task 6 covers UI, documentation, and runtime gates.
- Task 5 locks existing island policy text in tests.
- The plan excludes arbitrary sources, fuzzy matching, public full-island lists, and approval bypass.
- Interfaces are sequentially consistent: Task 1 models support Task 2 parsing and Task 3 lifecycle; Task 4 exposes Task 3; Task 5 reads Task 3 approved rows; Task 6 consumes Task 4 and Task 5.
