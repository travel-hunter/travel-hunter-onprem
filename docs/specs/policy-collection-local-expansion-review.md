# Policy Collection Local Expansion Review

> Status: active implementation-review handoff for the 2026-06-11 local expansion plan. This document records review boundaries, contract checks, and verification expectations for the team implementation lanes. It does not replace `docs/mvp-api-contract.md` as API authority or `CHECKLIST.md` as validation evidence.

## Source of Truth

- PRD: `.omx/plans/prd-policy-collection-local-expansion-20260611.md`
- Test spec: `.omx/plans/test-spec-policy-collection-local-expansion-20260611.md`
- Consensus gate: `.omx/plans/ralplan-consensus-policy-collection-local-expansion-20260611.json`

The approved option is to extend the existing `external_source_records -> policies -> Trip.recommendedPolicies` pipeline before introducing any new source-specific schema. If a schema gap is discovered, use Alembic only and document why `raw_payload` plus existing normalized fields were insufficient.

## Review Scope

The team implementation must cover these benefit families and connections:

| Area | Expected result | Boundary checks |
| --- | --- | --- |
| `stay_discount` / 숙박세일 페스타 | Official-like stay benefit HTML parses into active/fresh `ExternalBenefitSource` rows, promotes to public `policies`, classifies as `숙박`, and can appear in trip recommendations. | Add the source category in schema literals, collector parser/url dispatch, repository promotion/recommendation allowlists, classifier boosts, admin/ops quality filters, contract docs, and tests together. |
| `local_half_trip` / 대한민국 반값여행 | June/July application-status variants are classified as active/scheduled/ended without losing the travel-period text needed for recommendation date matching. | Preserve application period vs travel period in `raw_payload`; expose scheduled rows in the public policy list, but keep ended/stale rows hidden. |
| 여행가는 달 benefits | Modal-only and anchor+modal records merge into one stable canonical key with title, organizer, period, benefit, tags, detail URL, and confidence/freshness handling. | Prevent duplicate promotions and keep parser failures isolated to per-source `partial_success`. |
| Rule-based trip recommendation | Matching policies rank deterministically by region, trip-date intersection, category, and travel-style/tag signals only. | No AI/LLM calls or semantic judgment. Keep DTO stable unless API contract, frontend types, fixtures, and evals are updated in the same change. |

## Current Baseline Risks Found During Review

These are the integration points reviewers must re-check after implementation lanes land:

- `SourceCategory` now covers `regional_benefit`, optional legacy `traffic_benefit`, `local_half_trip`, and `stay_discount`; future source additions must stay synchronized across Pydantic schemas, contract docs, tests, and evals.
- `POLICY_PROMOTION_SOURCE_CATEGORIES`, `RECOMMENDATION_SOURCE_CATEGORIES`, and raw detail fallback allowlists must include any newly public `stay_discount` behavior consistently, or list/detail/recommendation paths will diverge.
- Category classification already has a URL marker for `benefits/stay.do`, but source-category scoring must explicitly boost `stay_discount -> 숙박` so records without a stay URL still classify correctly.
- Trip recommendation output currently uses the stable `LinkedTripPolicy` shape. If reasons or source metadata are added, update `docs/mvp-api-contract.md`, `frontend/src/api/types.ts`, frontend fixtures/tests, and `.agent/evals/api-contract-golden.json` together.
- Documentation must distinguish local deterministic validation from live official-site smoke. Live collection smoke requires approved admin bearer auth and must not log tokens.
- Admin/source-label and quality-report paths must be checked for new categories so `stay_discount` does not fall back to a generic operator label or category-mismatched recommendation preview.
- TravelMonth modal-only parsing and local-half-trip shorthand application statuses (`6월 중 예정`, `6.16 10시부터`) need explicit regression coverage because the existing parser baseline was anchor/full-date oriented.

## Required Verification Matrix

Run the narrowest commands that prove the changed implementation, then keep this matrix reflected in `CHECKLIST.md`.

| Claim | Minimum local evidence |
| --- | --- |
| Parser/source expansion works | Backend parser tests for stay discount, dgtourcard status variants, TravelMonth modal/detail merge; collection-service test with `stay_discount` source result. |
| Promotion/public exposure is safe | Policy normalization and external-source repository tests proving active/fresh and scheduled local_half_trip rows promote, ended/stale rows hide, and detail fallback matches public allowlists. |
| Recommendations are deterministic | Trip service tests proving matching region/date/category/style ranking, linked-policy exclusion, stale/ended exclusion, stable tie ordering, and no AI/LLM/external API call. |
| API/frontend contract remains aligned | API contract docs/evals JSON validation; frontend typecheck/build and trip/admin tests if DTOs, fixtures, or display change. |
| Hygiene | `git diff --check`, UTF-8 replacement-character scan for Korean-bearing docs, and Alembic SQL generation if schema changes. |

## Documentation Update Rules

- Update `docs/mvp-api-contract.md` whenever configured source categories, public policy fallback behavior, trip DTOs, or ops/admin response examples change.
- Update `.agent/evals/api-contract-golden.json` for endpoint-field or behavioral contract changes, then validate it with `python3 -m json.tool`.
- Update `docs/implemented-feature-spec.md` and `docs/screen-feature-status-logic.md` only after implementation evidence exists; avoid documenting planned behavior as complete.
- Update `docs/next-work-plan.md` when the release queue or remaining runtime smoke gates change.
- Keep `CHECKLIST.md` concise: current status, fresh command evidence, and remaining risks only.

## Coordination Notes

- Coordination protocol: coordinated - backend collector/parser/normalization, recommendation scoring, frontend/API contract, and docs/checklist boundaries must be checked before final integration.
- Shared files likely touched by multiple lanes: `docs/mvp-api-contract.md`, `.agent/evals/api-contract-golden.json`, `CHECKLIST.md`, `backend/app/services/trips.py`, and `backend/app/repositories/external_sources.py`. Merge these only after reviewing adjacent lane diffs.
