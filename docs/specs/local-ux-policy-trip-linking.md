# Local UX Spec: Policy To Trip Linking

## Goal

Complete the local experience where a user discovers a travel support policy, understands whether it can be used, saves it, and links it to a trip without hitting unexplained disabled states.

## User Experience Boundary

This spec covers:

- Policy list and detail discovery
- Official/apply link clarity
- Saved policy behavior
- Policy-to-trip linking
- Raw/external collected policy action constraints
- MyPage and trip detail reflection after linking

Deployment, CI/CD, and staging provider smoke are deferred.

## Current State

Implemented or partially implemented:

- Policy list and detail pages use DB-backed API data.
- Saved policy actions exist for normalized active policies.
- Policy detail can link a normalized policy to an existing trip.
- A new trip can be created with policy context.
- Trip detail shows linked policies and allows owner/editor removal.
- External collected benefits are promoted into `policies` when normalized.
- Raw fallback details can expose `actionStatus="infoOnly"` so save/link controls are blocked with product-language guidance instead of a half-enabled action state.
- Policy details without `applyUrl` or `officialUrl` show an explicit unavailable-link explanation and an accessible disabled CTA.
- Policy-to-trip linking success feedback names the selected policy and trip, and the success path can route to the trip detail with linked policy context.
- MyPage saved/applied policy summaries stay consistent after policy detail save/unsave, MyPage saved-policy removal, policy-to-trip linking, and trip-detail unlinking.
- A normalized policy passes local backend-mode e2e smoke across save, unsave, link, trip-detail display, unlink, and MyPage refresh.

Remaining local follow-up:

- The policy list uses client-side filtering; large policy volume may require server search/pagination.

## Missing UX To Complete Locally

No immediate local UX gap is currently tracked for this spec.

Conditional follow-up:

1. Policy list filtering should be prepared for server search/pagination when local datasets grow beyond client filtering comfort. Track this as conditional local UX, not as the current immediate sequence.

## Local Completion Criteria

- A normalized policy can be saved, unsaved, linked to a trip, and removed from a trip in local runtime.
- A raw fallback policy cannot produce a confusing half-enabled action state.
- A policy without official/apply URL has clear user-facing messaging and does not look like a broken CTA.
- After linking a policy, `/trips/{tripId}` shows the linked policy without requiring a manual refresh.
- MyPage saved/applied policy summaries stay consistent after save/link/delete actions.

## Current Validation Evidence

- 2026-06-05: `cd frontend && npm run typecheck` passed.
- 2026-06-05: `cd frontend && npm test` passed with 8 files and 153 tests after starting compose PostgreSQL, applying Alembic migrations, seeding data, and running FastAPI backend-mode tests.
- 2026-06-05: `cd frontend && npm run test:e2e -- -g "normalized policy save, unsave, trip link, and unlink"` passed with 1 Playwright backend-mode test.

## Relevant Files And APIs

Frontend:

- `frontend/src/pages/PolicyPages.tsx`
- `frontend/src/pages/MyPage.tsx`
- `frontend/src/pages/itinerary/ItineraryCreatePage.tsx`
- `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- `frontend/src/components/cards.tsx`
- `frontend/src/utils/policyCapabilities.ts`
- `frontend/src/api/appDataApi.ts`
- `frontend/src/api/backendApi.ts`

Backend:

- `backend/app/api/routes/policies.py`
- `backend/app/api/routes/trips.py`
- `backend/app/services/policies.py`
- `backend/app/services/trips.py`
- `backend/app/services/policy_normalization.py`
- `backend/app/repositories/policies.py`
- `backend/app/repositories/external_sources.py`

Contracts and references:

- `docs/mvp-api-contract.md`
- `docs/screen-feature-status-screens.md`
- `docs/screen-feature-status-logic.md`
- `docs/db-schema-current.md`

## Non-Goals

- Do not add public trip slugs.
- Do not reintroduce runtime mock mode.
- Do not treat deployment/staging smoke as part of local completion.
