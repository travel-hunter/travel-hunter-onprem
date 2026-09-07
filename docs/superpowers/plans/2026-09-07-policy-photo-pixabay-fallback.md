# Policy Photo City Matching and Pixabay Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each policy a city-relevant photo when possible, using Pixabay only after TourAPI has no city-relevant candidate.

**Architecture:** The backfill resolves a city from `policies.city` or a leading `[city]` title marker, caches TourAPI candidates per `(region, city)`, and persists only city-matching TourAPI candidates. A disabled-or-empty optional Pixabay provider supplies a separately attributed city-landscape fallback; otherwise the existing `region_photos` response fallback remains unchanged.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, httpx, pytest, TourAPI, Pixabay REST API.

**Spec:** `docs/superpowers/specs/2026-09-07-policy-specific-photos-design.md`

## Global Constraints

- Keep `PolicyPhoto` API fields unchanged: `imageUrl`, `thumbnailUrl`, `alt`, `attribution`.
- Never log, return, commit, or print either provider API key.
- TourAPI remains the preferred source; Pixabay only fills a missing city-specific candidate.
- Do not persist a broad region-level image as a policy-specific assignment.
- A missing Pixabay key must remain a no-op; existing regional and icon fallbacks continue working.

---

### Task 1: Optional Pixabay provider

**Files:**
- Create: `backend/app/services/pixabay.py`
- Modify: `backend/app/core/config.py`, `.env.example`, `backend/tests/test_pixabay_client.py`

**Interfaces:**
- Produces `PixabayImage`, `PixabayPhotoProvider`, and `build_pixabay_client(settings_obj) -> PixabayPhotoProvider | None`.
- `PixabayPhotoProvider.search_images(query: str, rows: int) -> list[PixabayImage]` returns normalized image metadata only.

- [ ] Write tests for disabled no-op, response parsing, required-key validation, and sanitized HTTP errors.
- [ ] Run the new tests and observe failure because the module does not exist.
- [ ] Add optional `PIXABAY_ENABLED`, `PIXABAY_API_KEY`, `PIXABAY_TIMEOUT_SECONDS` settings and a client that calls `https://pixabay.com/api/` with safe-search photo-only query parameters.
- [ ] Run the provider tests until they pass.

### Task 2: City-first assignment and provider fallback

**Files:**
- Modify: `backend/scripts/backfill_policy_photos.py`, `backend/tests/test_backfill_policy_photos.py`

**Interfaces:**
- `policy_city_hint(policy) -> str | None` uses normalized `policy.city`, then a leading `[city]` title marker.
- `run_backfill(..., fallback_provider: PixabayPhotoProvider | None = None, force: bool = False)` reuses city candidate caches and only calls fallback after no TourAPI city match.

- [ ] Write failing tests proving title city extraction, rejection of region-only TourAPI rows, one query per city cache key, fallback ordering, and `force=True` replacement.
- [ ] Run the target backfill tests and observe the expected failures.
- [ ] Implement city candidate caching, strict city matching, optional Pixabay lookup, source-specific attribution, and the `--force` CLI flag.
- [ ] Run target tests until they pass.

### Task 3: Isolated runtime proof

**Files:**
- Modify: no tracked runtime files
- Test: `backend/tests/test_pixabay_client.py`, `backend/tests/test_backfill_policy_photos.py`, full backend suite, frontend policy card test

- [ ] Rebuild only Compose project `travel-hunter-region-photos` and apply migration `0037` to its isolated DB.
- [ ] Run TourAPI-only full dry-run first; do not write all policies before reporting its city match/fallback counts.
- [ ] If a Pixabay key is configured locally, run a small isolated `--force --limit 3` proof and verify attribution through `/api/policies`; otherwise verify disabled-provider fallback tests.
- [ ] Run backend suite, frontend targeted test, typecheck, build, mojibake, UTF-8, and `git diff --check`.
