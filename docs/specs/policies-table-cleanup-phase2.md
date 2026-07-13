# Policies Table Cleanup Phase 2 Notes

## Purpose

This note records future schema cleanup options for `policies` after the 2026-07 compatibility-preserving semantic hardening pass.

The first pass did **not** drop or rename columns and did **not** change the public `Policy` DTO. It centralized current semantics in helpers and added aggregate diagnostics so a later migration can be evidence-based.

## Current First-Pass Baseline

- DB columns stay unchanged: `benefit_amount`, `benefit_detail`, `target_condition`, `official_url`, `apply_url`, `source_type`, `source_name`, `source_category`, `source_canonical_key`, and `status` remain in place.
- Public `Policy` DTO stays unchanged: `amount`, `requirements`, `officialUrl`, `applyUrl`, `sourceType`, and `structuredDetail` retain their existing names and meanings.
- `benefit_detail` display wins over `benefit_amount` fallback. `benefit_amount` remains numeric fallback/aggregate input.
- `target_condition` remains the DB field. DTO `requirements` are helper-normalized fallback items.
- `applyUrl` and `officialUrl` remain separate. Frontend CTA priority remains `applyUrl` first, then `officialUrl`.
- API `sourceType` normalizes to `internal|external`; source metadata and canonical keys remain diagnostic/traceability fields.
- `status` remains the `active|hidden` enum. Boolean visibility or richer lifecycle modeling is only a phase-2 option.

## Required Diagnostics Before Migration

Run the DB aggregate audit on the target environment before choosing any schema change:

```bash
cd backend
.venv/bin/python scripts/audit_policy_semantics.py --json
```

Use this for aggregate counts only: status counts, amount nullability, apply URL nullability, source metadata combinations, and source canonical key family distribution.

Keep the existing URL/source auditor separate:

```bash
cd backend
.venv/bin/python scripts/audit_policy_sources.py --json path/to/policies.json
```

That command audits a JSON file input and should not be treated as the DB aggregate semantics source of truth.

## Phase-2 Decision Options

### 1. Amount/detail consolidation

Question: should `benefit_amount` and `benefit_detail` remain split, be renamed, or move into a structured benefit model?

Options:

- Keep both fields and document `benefit_detail` as display text, `benefit_amount` as numeric fallback/analytics.
- Rename in DB after a compatibility migration, for example display text vs numeric amount.
- Move display-rich benefit sections into `structured_detail.benefits` or a future `policy_benefits` table while keeping DTO `amount` compatible.

Decision evidence:

- Count rows where `benefit_amount` is null/non-null.
- Count rows where `benefit_detail` duplicates formatted numeric amount.
- Check frontend and trip savings logic that still depends on numeric `benefit_amount`.

### 2. `target_condition` rename

Question: should `target_condition` be renamed to a clearer policy eligibility/requirements field?

Options:

- Keep the DB field and continue helper-normalized `requirements` fallback.
- Add a new field, backfill from `target_condition`, and dual-read during migration.
- Move richer conditions into `structured_detail.conditions` and retain `target_condition` as legacy fallback.

Decision evidence:

- Count rows with non-empty `target_condition`.
- Compare rows with `structured_detail.conditions` present.
- Verify frontend fallback only uses DTO `requirements` when structured conditions are absent.

### 3. Link model and `apply_url` decision

Question: should `official_url` and `apply_url` stay as two columns, or move to a link table/JSON model?

Options:

- Keep two columns: `official_url` for 안내, `apply_url` for 신청.
- Add link metadata to `structured_detail.links` while preserving DTO fields.
- Introduce a policy links table if multiple official/apply/notice URLs become common.

Decision evidence:

- Count `apply_url` null/non-null.
- Audit source URLs for root/portal links with `audit_policy_sources.py`.
- Confirm CTA priority remains unchanged in frontend tests.

### 4. `source_canonical_key` versioning

Question: should canonical keys be versioned or normalized to one stable format?

Options:

- Keep legacy mixed keys and diagnose families only.
- Add `source_canonical_key_version` or prefix version into the key value.
- Split canonical identity into source family, source item id, parser version, and hash columns.

Decision evidence:

- Use `sourceCanonicalKeyFamilies` from `audit_policy_semantics.py`.
- Identify duplicate collisions and cross-source key format drift.
- Preserve `external_source_records` upsert semantics before changing `policies` key format.

### 5. Status enum vs boolean visibility

Question: should `status active|hidden` remain, become a boolean visibility field, or expand into richer lifecycle states?

Options:

- Keep `active|hidden` enum and centralized constants.
- Add `is_public`/`visibility` while retaining `status` during compatibility migration.
- Expand lifecycle states only if operations need more than public visibility, for example `draft`, `archived`, or `needs_review`.

Decision evidence:

- Confirm all public paths use active-only semantics.
- Count current `status` distribution.
- Decide whether hidden means one concept or several operational states.

## Migration Guardrails

- Do not change public `Policy` DTO shape without updating `docs/mvp-api-contract.md`, frontend types, backend schemas/routes/services, tests, and `.agent/evals` together.
- Keep DB fields `snake_case` and API DTO fields `camelCase`.
- Use Alembic for every schema change. Do not use SQLAlchemy `create_all()` for app schema.
- Preserve `policies.slug`, saved policy relations, trip policy relations, and stay-discount alias behavior.
- Run targeted backend policy/trip tests and repository hygiene checks before migration approval.
