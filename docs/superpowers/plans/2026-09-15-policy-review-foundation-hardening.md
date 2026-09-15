# Policy Review Foundation Hardening Implementation Plan

Goal: Make policy-source review and eligible-island catalog behavior safe under concurrent admin actions while keeping public policy reads database-write-free.

Architecture: Migration 0040 owns the initial island catalog row. Public summary reads only query it; admin collection/approval can explicitly bootstrap legacy or test databases. Candidate creation serializes on the external-source row, and approve/reject serializes on the candidate row. A ? B ? A creates a fresh pending candidate.

## Constraints

- Do not mutate development or production DBs during verification.
- Public policy/list/recommendation paths must issue no INSERT, UPDATE, DELETE, or row-locking statement.
- Keep admin authorization unchanged.
- Amend unmerged migrations 0038 and 0040 rather than adding a competing 0041.

## Task 1: Public read / bootstrap boundary

Files: backend/app/repositories/eligible_islands.py, backend/app/api/routes/admin.py, backend/tests/test_eligible_island_policy_fields.py

- [ ] Keep get_catalog and list_approved_entries SELECT-only.
- [ ] Make bootstrap_builtin_catalogs callable only from explicit admin write paths and test fixtures.
- [ ] Add an empty-schema summary regression test that asserts no DML.
- [ ] Run the policy-field test module.

## Task 2: Migration-owned catalog seed

Files: backend/alembic/versions/0040_eligible_island_catalog.py and eligible-island test fixtures

- [ ] Insert island_visit_2026 during migration 0040.
- [ ] Have Base.metadata.create_all test fixtures create the same row explicitly.
- [ ] Verify offline Alembic SQL and catalog tests.

## Task 3: Race-safe candidate lifecycle

Files: migration 0038, models/tables.py, policy_candidate_review.py, admin.py, test_policy_candidate_review.py

- [ ] Remove historical fingerprint uniqueness while 0038 is unmerged.
- [ ] Lock the external source row; reuse only the newest matching fingerprint.
- [ ] Lock candidate rows and re-check pending before approve/reject; sort batch IDs before locking.
- [ ] Cover A ? B ? A and compiled PostgreSQL FOR UPDATE.

## Task 4: Final PR gate

- [ ] Run all targeted backend tests, offline Alembic SQL, frontend typecheck, focused Vitest, build, mojibake, UTF-8 scan, and git diff --check.
- [ ] Re-review final diff and present one PR preview plus one matching Slack-hook text before push.