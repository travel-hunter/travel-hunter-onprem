# 정책 수집 후보 자동 발행 게이트 — 구현 계획

> Spec: `docs/superpowers/specs/2026-09-14-policy-auto-publish-design.md`. 각 Task는 RED → GREEN → 커밋. Claude가 커밋하고 push/PR/merge는 Codex가 한다.

## Global Constraints

- 기본 모드는 `review`; 기존 수동 승인·반려·일괄 승인 동작은 변하지 않는다.
- `eligible_island_*`와 `stay_discount`는 자동 발행 대상이 아니다.
- DTO는 camelCase, DB 컬럼은 snake_case. `docs/mvp-api-contract.md`, `docs/db-schema-current.md`, `.agent/evals/api-contract-golden.json`(해당 시)을 함께 갱신한다.
- `CHECKLIST.md`는 머지 직전에만 갱신한다.

---

### Task 1: 스키마 — `review_reason`, `last_parsed_count`

**Files:** Modify `backend/app/models/tables.py`, `backend/tests/test_db_schema.py`; Create `backend/alembic/versions/0041_policy_auto_publish.py`.

- [x] Step 1: `test_db_schema.py`에 두 컬럼 존재 단언 추가 → RED.
- [x] Step 2: 모델 컬럼 추가, 0041(`down_revision = "0040_eligible_island_catalog"`, 컬럼 2개 add/drop) 작성 → GREEN, `alembic upgrade 0040:head --sql` 확인.
- [x] Step 3: 커밋 `feat: add review reason and parsed count columns`.

### Task 2: 게이트 서비스와 수집 배선

**Files:** Modify `backend/app/services/policy_candidate_review.py`, `backend/app/services/external_benefit_collection.py`, `backend/app/repositories/policy_collection_sources.py`; Create `backend/tests/test_policy_auto_publish.py`.

**Interfaces:** `auto_publish_gate(db, *, candidate, record, source, source_result) -> str` (반환값은 `auto` 또는 보류 사유), `approve_candidate(..., admin: User | None)`, `record_collection_source_run(..., parsed_count)`.

- [x] Step 1: 스펙 테스트 기준 1~7을 sqlite 픽스처(`autoflush=False`)로 작성 → RED.
- [x] Step 2: 게이트 구현. `_queue_review_candidates`가 `source_results`를 받아 카테고리별 `SourceCollectionResult`와 소스 행을 조회해 게이트를 호출한다. 자동 승인 감사 로그는 `policy_review.auto_approve`, `admin_user_id`는 마지막 기준선 승인자.
- [x] Step 3: 전체 pytest → GREEN. 커밋 `feat: auto-publish reviewed-baseline policy updates`.

### Task 3: 관리자 API·화면·문서

**Files:** Modify `backend/app/schemas/admin.py`, `backend/app/api/routes/admin.py`, `backend/tests/test_admin_routes.py`, `frontend/src/api/types.ts`, `frontend/src/api/backendApi.ts`, `frontend/src/api/dataApi.ts`, `frontend/src/pages/admin/AdminPages.tsx`, `frontend/src/pages/admin/AdminPages.test.tsx`, `docs/mvp-api-contract.md`, `docs/db-schema-current.md`, `docs/policy-collection-to-screen-flow.md`.

- [x] Step 1: 라우트 테스트(모드 변경 409 `baseline_required`, `reviewReason` 노출) + 프론트 테스트(모드 토글, 사유 배지) → RED.
- [x] Step 2: `AdminCollectionSourceUpdateRequest`에 `publicationMode`/`expectedMinRecords` 선택 필드, 소스 DTO에 `expectedMinRecords`/`lastParsedCount`/`autoApprovedLast24h`, 후보 DTO에 `reviewReason`. 화면 토글·배지. 문서 3종 갱신.
- [x] Step 3: 전체 검증(pytest, vitest, typecheck, build, mojibake, `git diff --check`) → 커밋 `feat: manage auto-publish mode from the admin review page`.

### Task 4: 격리 스택 검증

- [x] 5174 스택 재빌드 → 0041 왕복 → `docs/db-schema-current.sql` 재생성 → 한 소스를 `auto`로 켜고 수집 실행 → 갱신 후보만 자동 승인되고 새 정책은 `pending`인지, 감사 로그가 남는지 확인 → 모드 원복.
