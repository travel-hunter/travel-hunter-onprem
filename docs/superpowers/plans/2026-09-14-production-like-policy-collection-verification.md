# Production-like Policy Collection Verification Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate policy collection against a disposable copy of the current local development database, proving that collection does not alter public policy-card content before explicit candidate approval.

**Architecture:** The existing local development PostgreSQL database remains read-only throughout. A verified custom-format dump is restored into the `policy-source-review` Compose volume, then migration 0038 is applied only there. Policy identifiers, slugs, and display-field hashes are captured before and after collection; only source evidence, source health, and review candidates may change.

**Tech Stack:** PostgreSQL 16, Docker Compose, pg_dump/pg_restore, Alembic, FastAPI, pytest.

**Spec:** docs/mvp-api-contract.md, docs/superpowers/plans/2026-09-13-admin-policy-source-review.md

## Global constraints

- Never modify the primary local development database.
- Store dump and comparison artifacts outside the repository with restricted permissions.
- Do not print database URLs, passwords, tokens, or policy-card text.
- Stop if source and clone policy counts or display hashes differ before collection.
- Do not approve a candidate during the baseline-preservation run.

---

### Task 1: Fix source-catalog initialization race

**Files:**
- Modify: backend/app/repositories/policy_collection_sources.py
- Modify: backend/tests/test_policy_source_catalog.py

**Interfaces:**
- `ensure_builtin_collection_sources(db)` must be idempotent when two request sessions initialize the same empty catalog.
- `list_collection_sources(db)` must not return a 500 response after a concurrent first request.

- [ ] **Step 1: Add a regression test using two independent PostgreSQL sessions.**

The test calls `ensure_builtin_collection_sources` from both sessions before either request completes, then commits both in the same order that produced the duplicate-key error. It asserts exactly one row for every builtin source key.

- [ ] **Step 2: Run the new test and confirm the current duplicate-key failure.**

Run: `python -m pytest tests/test_policy_source_catalog.py -q`

- [ ] **Step 3: Replace ORM bulk insertion with PostgreSQL-safe conflict handling.**

Use the repository's existing dialect-safe insert pattern or an explicit per-key lookup protected by a unique-conflict retry. Preserve immutable adapter and URL fields; only create missing rows.

- [ ] **Step 4: Re-run the focused test and the full backend suite.**

Run: `python -m pytest tests/test_policy_source_catalog.py -q`
Run: `python -m pytest -q`

### Task 2: Prepare a verified disposable clone

**Files:**
- Create outside repository: temporary `.dump` and checksum artifacts only.

- [ ] **Step 1: Capture primary DB counts and policy display hashes.**

Record only aggregate counts and SHA-256/MD5 digests of `id`, `slug`, title, benefit, date, status, visibility, and source fields. Do not print policy text.

- [ ] **Step 2: Create and verify a custom-format backup.**

Run `pg_dump -Fc` inside the primary DB container, save outside the repository, check nonzero size, run `pg_restore --list`, and record SHA-256.

- [ ] **Step 3: Recreate only the `policy-source-review` database volume and restore the dump.**

Stop the isolated project, remove only its named volume, start its DB, and restore schema plus data with `pg_restore --clean --if-exists --no-owner --no-privileges`. Never stop or recreate the primary project.

- [ ] **Step 4: Compare clone baseline with primary baseline.**

The policy count and ordered display hash must match exactly. If not, stop and report before starting backend/frontend.

### Task 3: Run the exact collection lifecycle

**Files:**
- No source-code changes.

- [ ] **Step 1: Apply migration 0038 only to the clone and start 5174/8002.**

Run `alembic upgrade head` in the isolated backend. Confirm health on 8002 and frontend response on 5174.

- [ ] **Step 2: Enable the code-reviewed island source and run the existing admin collection endpoint once.**

Use the normal admin flow. Do not enable arbitrary URLs and do not approve any candidate.

- [ ] **Step 3: Verify the collection boundary.**

Compare policy display hashes to the pre-run baseline. Assert:
- public policy count unchanged;
- public policy display hash unchanged;
- external evidence and pending-candidate counts may increase;
- source health records the real parser outcome.

- [ ] **Step 4: Browser verification.**

At `http://127.0.0.1:5174/admin/policy-review`, verify source state and candidate entries. At `/policies`, verify cards match the copied development data.

### Task 4: Record the validation result

**Files:**
- Modify only at merge-ready state: CHECKLIST.md

- [ ] **Step 1: Record current validation evidence and active risk only.**

Include aggregate counts, hash comparison result, source outcome class, and whether candidate approval was intentionally skipped. Do not include any secrets or raw policy text.
