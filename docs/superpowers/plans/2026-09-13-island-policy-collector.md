# Island Travel Support Collector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collect the official Island Visit Year travel-support announcement into the administrator review queue without automatically changing public policy cards.

**Architecture:** A code-owned `island_visit` adapter fetches only `https://www.visitisland.kr/promotion2`, parses one campaign record from stable labelled fields, and records `parser_changed` when the expected fields disappear. It reuses the source catalog and candidate-review path; publication remains an explicit administrator action.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, httpx, BeautifulSoup parser utilities, pytest.

**Spec:** `docs/superpowers/plans/2026-09-13-admin-policy-source-review.md`

## Global Constraints

- No administrator-entered URL is fetched.
- Allow only the `visitisland.kr` official host and the fixed `/promotion2` path.
- Do not change existing public Policy text during collection.
- Government24, arbitrary municipality crawling, and KORAIL are out of scope.
- A missing/changed page is a source-health result, not an empty successful collection.

### Task 1: Define the Island Visit source parser

**Files:**
- Create: `backend/app/services/island_visit_parser.py`
- Create: `backend/tests/test_island_visit_parser.py`

**Produces:** `parse_island_visit_support(html, *, fetched_at, today) -> list[ExternalBenefitSource]` and constants `SOURCE_CATEGORY = "island_visit"`, `SOURCE_URL`.

- [ ] Write a fixture-based failing test with labelled application period, travel period, support amount, eligibility islands, and official URL. Assert one source, canonical key `2026-island-visit-support`, nationwide region, and active/scheduled/ended status derived from the travel period.
- [ ] Run `python -m pytest tests/test_island_visit_parser.py -q`; confirm the missing module failure.
- [ ] Parse labelled text only. Require an application period and support content; when either is absent raise `IslandVisitParserChangedError` rather than returning an empty list.
- [ ] Use one deterministic source record. Keep the island list in `raw_payload["eligibleIslands"]`; do not emit one public policy per island.
- [ ] Re-run the focused tests and add a changed-markup test that asserts `IslandVisitParserChangedError`.

### Task 2: Register the code-reviewed source and collection health

**Files:**
- Modify: `backend/app/repositories/policy_collection_sources.py`
- Modify: `backend/app/services/external_benefit_collection.py`
- Modify: `backend/tests/test_policy_source_catalog.py`
- Modify: `backend/tests/test_external_benefit_collection.py`

**Consumes:** the parser from Task 1 and the existing `PolicyCollectionSource` catalog.

- [ ] Write a failing catalog test asserting `island_visit` has adapter key `island_visit`, the fixed official URL, `review` publication mode, and no editable URL field.
- [ ] Add the fixed source definition to `BUILTIN_COLLECTION_SOURCES` and the source registry. It must use the Island parser and be required only while enabled.
- [ ] Write a failing collector test that disables `island_visit`, stubs HTTP, runs collection, and asserts the fixed URL is not fetched.
- [ ] Filter live collection by enabled catalog sources; on `IslandVisitParserChangedError`, record `parser_changed` with zero records and continue other sources.
- [ ] Run catalog and collection tests. Assert collection creates a pending candidate and does not call global policy normalization.

### Task 3: Complete the review gate before enabling the source in shared environments

**Files:**
- Modify: `backend/app/services/policy_candidate_review.py`
- Modify: `backend/app/api/routes/ops.py`
- Modify: `backend/app/schemas/ops.py`
- Modify: `backend/tests/test_policy_candidate_review.py`
- Modify: `backend/tests/test_ops_routes.py`

**Produces:** list, approve, reject, and source-enable endpoints guarded by `require_admin_user`.

- [ ] Write failing route tests for a non-admin 403, source patch accepting only `enabled`, and approving exactly one pending candidate.
- [ ] Implement approval as a single-record publication operation. It must link the approved candidate to the resulting Policy and never run global promotion.
- [ ] Implement rejection with a required note and audit record containing safe IDs only.
- [ ] Run route tests and a lifecycle test: collect fixture -> pending -> approve -> one Policy -> same fixture -> no duplicate -> changed fixture -> pending material change -> reject -> original Policy fields unchanged.

### Task 4: Verify and document

**Files:**
- Modify: `docs/policy-collection-to-screen-flow.md`
- Modify: `docs/mvp-api-contract.md`
- Modify: `docs/db-schema-current.md`
- Modify: `docs/db-schema-current.sql`

- [ ] Run backend focused tests, then `python -m pytest` and `alembic upgrade head --sql` in the isolated test container.
- [ ] Verify `git diff --check` and UTF-8 cleanliness.
- [ ] Document that enabling the source makes collection discover candidates only; an admin must approve each candidate before it appears publicly.

## Self-review

- The source is fixed and official; no arbitrary website can be added through the UI.
- Source outage and markup changes are visible as health states rather than silently treated as no results.
- One campaign candidate preserves its eligible-island list as evidence and avoids duplicating 163 near-identical cards.
- KORAIL and Government24 remain separate source-onboarding decisions.
