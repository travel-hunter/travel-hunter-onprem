# Local UX Supporting Gap Scan

## Purpose

This supporting gap scan gives one scan-friendly view of remaining local UX and screen-facing work. It is not the execution-priority owner and must not be used as a second queue. Use `docs/next-work-plan.md` for current priority, `docs/implemented-feature-spec.md` for implemented/status inventory, and the active `local-ux-*.md` specs for domain detail.

## Source Priority

When documents conflict for UX completion status, use this order:

1. `docs/next-work-plan.md`
2. `docs/implemented-feature-spec.md`
3. Active local UX specs under `docs/specs/local-ux-*.md`
4. `docs/screen-feature-status-screens.md` and `docs/screen-feature-status-logic.md` as older reference ledgers and mismatch evidence

## Scope Boundary

Included here:

- Local user-facing UX and screen gaps that can be developed and validated without public DNS, Cloudflare, real SMTP sender-domain authentication, public OAuth redirect registration, staging infrastructure, or external-provider production smoke.
- Conditional local UX work that should stay visible but is not the current immediate sequence.

Excluded from the active local UX backlog:

- Cloudflare Tunnel staging, public HTTPS smoke, Brevo sender-domain authentication, real SMTP password reset delivery, public OAuth redirect smoke, and Jenkins/CI/CD automation.
- Source code, API, DB schema, dependency, or runtime changes unless a later execution plan explicitly expands scope.

## Mirrored Current Queue Item

No immediate local UX/screen gap is currently mirrored here. The previous `/ai-results` fallback-source communication item is complete: `GET /api/trips/{tripId}/recommendations` now exposes `sourceType`, and `/ai-results` shows source notice copy plus candidate badges for fresh candidates versus saved recommendation-summary fallback.

## Supporting Conditional Gap Scan

| Item | Condition | Source pointer | Current need | Done when |
| --- | --- | --- | --- | --- |
| Policy list server search/pagination readiness | Local policy volume makes client-side filtering uncomfortable. | `docs/next-work-plan.md`, `local-ux-policy-trip-linking.md` | Keep the follow-up visible without making it immediate while current policy volume remains manageable. | Server-backed search/pagination is planned and implemented only when policy volume justifies moving beyond client filtering. |
| Catalog fallback coverage expansion | Local demo or supported target regions become sparse beyond the representative smoked areas. | `local-ux-place-discovery.md`, `docs/next-work-plan.md` | Built-in catalog fallback should not create empty-feeling trip days for supported local demo areas. | Additional local fallback coverage is added and smoke-tested for the newly supported areas. |
| Recommendation basis copy alignment | Ranking implementation or fallback behavior drifts from the current explanation copy. | `local-ux-place-discovery.md`, `screen-feature-status-logic.md` | Recommendation explanations should describe actual local inputs and avoid route-time, rating, review, or full-AI overclaims. | The explanation copy matches implemented ranking/fallback inputs and leaves route-time/ratings/reviews as future scope. |

## Explicitly Deferred / Future Scope

These are not active local UX backlog items for the current pass:

- Route-time optimization.
- Ratings and reviews scoring.
- Real AI engine behavior beyond the current local recommendation/fallback logic.
- Password reset inbox delivery through real SMTP and sender-domain authentication.
- Kakao/Google full public-provider browser smoke using production/public redirect URIs.
- Phone contact/OTP smoke is not deferred; the contact/OTP surface has been removed and would require a new product/API contract to reintroduce.
- Cloudflare, public HTTPS, deployment, and CI/CD smoke.

## Reference Mismatches

| Area | Older reference says | Current source-of-truth interpretation | Follow-up |
| --- | --- | --- | --- |
| Map bottom-sheet place detail | `docs/screen-feature-status-screens.md` still describes the itinerary detail map bottom-sheet `상세 보기` as partial/toast-only. | `docs/specs/local-ux-place-discovery.md`, `docs/next-work-plan.md`, and current validation evidence treat the local inspectable detail dialog as complete. | Keep the older ledger as reference evidence; do not use it to reopen the completed map detail task unless newer code/tests contradict the active specs. |

## Verification Notes For Future Documentation Updates

For documentation-only updates that touch this supporting scan or active local UX specs:

- Run `git diff --check`.
- Scan changed docs for Unicode replacement characters (`U+FFFD`).
- Confirm changed files are documentation/planning/checklist files only unless a later explicit execution handoff expands scope.
- Update `CHECKLIST.md` with current validation evidence and active remaining risks.
