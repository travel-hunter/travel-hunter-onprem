# Policy-specific Region Photos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task-by-task.

**Goal:** Assign a stable, relevant TourAPI photo to each policy while retaining existing region-level photos as a safe fallback.

**Architecture:** Add a `policy_photos` table keyed by `policy_id`; a policy-photo repository stores one current assignment per policy. The existing photo resolver loads policy assignments and region photos once per request, selecting policy photo first and region/city fallback second. A separate backfill script gathers and ranks TourAPI candidates without changing policy collection.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, TourAPI, pytest, React/Vitest.

**Spec:** `docs/superpowers/specs/2026-09-07-policy-specific-photos-design.md`

## Global Constraints

- Keep the existing `PolicyPhoto` DTO fields and nullable `photo` API contract.
- Keep `region_photos` as the fallback source; do not alter policy, trip, or user links.
- TourAPI requests remain opt-in through `TOUR_API_ENABLED` and must never log `TOUR_API_SERVICE_KEY`.
- Validate only against the isolated `travel-hunter-region-photos` Compose project.

---

### Task 1: Persist one photo assignment per policy

**Files:**
- Create: `backend/alembic/versions/0037_policy_photos.py`
- Create: `backend/app/repositories/policy_photos.py`
- Modify: `backend/app/models/tables.py`, `backend/app/models/__init__.py`
- Test: `backend/tests/test_policy_photos_repository.py`

- [ ] Write tests proving an upsert keeps one row per policy and updates its image, score, reason, and timestamp.
- [ ] Run the new repository tests and confirm they fail because the model/repository do not exist.
- [ ] Add `PolicyPhotoAssignment` and the migration table with a unique `policy_id`, provider metadata, image fields, score, assignment reason, status, and timestamps.
- [ ] Add repository functions to list active assignments and upsert an assignment by policy id.
- [ ] Re-run repository tests and `alembic upgrade head --sql`.

### Task 2: Prefer policy assignments in policy API payloads

**Files:**
- Modify: `backend/app/services/region_photos.py`, `backend/app/services/policies.py`
- Modify: `backend/tests/test_region_photos_service.py`, `backend/tests/test_policies_photo_payload.py`
- Modify: `docs/mvp-api-contract.md`

- [ ] Write failing tests for policy-photo priority, region fallback, and a `null` photo when neither source exists.
- [ ] Run those tests and confirm they fail against the region-only resolver.
- [ ] Build one per-request resolver index containing active policy assignments plus active region photos; resolve by policy id before `(region, city)`.
- [ ] Pass the policy id where a persisted policy is rendered; keep external-record-only payloads on region fallback.
- [ ] Update the contract explanation without changing DTO field names.
- [ ] Re-run the targeted API and resolver tests.

### Task 3: Backfill deterministic policy-specific candidates

**Files:**
- Create: `backend/scripts/backfill_policy_photos.py`
- Create: `backend/tests/test_backfill_policy_photos.py`
- Modify: `docs/policy-collection-to-screen-flow.md`

- [ ] Write failing tests for city-address priority, keyword priority, duplicate URL avoidance, region fallback, and idempotent skip behavior.
- [ ] Run the new script tests and confirm they fail before implementation.
- [ ] Implement pure candidate scoring: exact municipality address first, policy-title keyword match second, same-sido image candidate third; discard candidates without an image.
- [ ] Implement the opt-in script: list active policies, skip current active assignments unless `--refresh-older-than-days` is supplied, and continue after per-policy failures without printing request URLs.
- [ ] Use the region-level resolver result as the fallback only when no policy-specific candidate survives ranking.
- [ ] Re-run the script tests and backend photo test suite.

### Task 4: Verify presentation and isolated runtime

**Files:**
- Test: `frontend/src/components/policyListCard.test.tsx`

- [ ] Run the new card-media test, policy-photo frontend tests, typecheck, and production build.
- [ ] Rebuild the isolated backend image, migrate only the isolated DB to 0037, then run `backfill_policy_photos.py --dry-run --limit 3` with output key masking.
- [ ] Start the feature Vite server on 5173 and confirm the policy card uses an image when the API returns `photo`, otherwise the icon fallback.
- [ ] Run `git diff --check` and UTF-8 replacement-character checks before commit.
