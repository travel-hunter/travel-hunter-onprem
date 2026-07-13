# Local UX Spec: Place Detail And Search

## Goal

Complete the local itinerary place experience so users can inspect places, search or discover alternatives, and add useful candidates to an itinerary with clear fallback behavior.

## User Experience Boundary

This spec covers:

- Trip detail place list and map mode
- Map bottom-sheet place detail action
- Place search/discovery UX
- Kakao Local candidate quality
- Built-in catalog fallback coverage
- `/ai-results` additional candidates and fallback behavior
- Recommendation basis messaging

Deployment, public map domain setup, CI/CD, and staging smoke are deferred.

## Current State

Implemented or partially implemented:

- Trip detail supports list/map views and place CRUD/move.
- Kakao Maps rendering is attempted when key, SDK, and coordinates are available.
- Fallback map/search UI exists when Kakao rendering cannot be used.
- Map bottom-sheet "detail view" opens a local detail dialog with day context, time, category, address, memo, coordinates, and a Kakao Maps link.
- The itinerary add-place sheet loads recommendation candidates through `AppDataApi.listRecommendations`, filters them locally, and can add a selected candidate while preserving address, coordinates, category, Kakao URL, provider, and external place id fields.
- `/ai-results` lists additional recommendation candidates, supports adding a candidate to a selected day, and uses `sourceType` plus source copy/badges to distinguish fresh candidates from saved recommendation-summary fallback.
- Kakao Local is used when enabled; built-in catalog fallback keeps local trip creation from producing an empty experience.
- Kakao Local candidate smoke is available through `backend/app/scripts/smoke_kakao_local_candidates.py` and passed for five representative areas with configured env.
- Catalog fallback now retries travel-area display names through the area's `sido` and included cities, so `부산 전체` can use the existing `부산` catalog entries.

Known gaps:

- Candidate quality depends on Kakao Local env, search results, and travel area term matching.
- Catalog fallback can be sparse for some regions.
- `/ai-results` can fall back to recommendation descriptions saved at trip creation rather than fresh candidates, but the fallback is now labeled as saved summary content.
- The recommendation basis UI describes product direction, but not every factor is implemented as quantitative ranking.

## Missing UX To Complete Locally

No immediate local UX gap is currently tracked for this spec.

Conditional local UX:

1. Catalog fallback should cover enough regions to avoid sparse or empty trip days when local demo/support targets expand beyond the currently smoked representative areas.
2. Recommendation basis copy should match the actual local ranking inputs whenever ranking or fallback behavior changes.

Future scope, not active local UX backlog:

- Route-time optimization and ratings/reviews should remain explicitly future scope unless implemented.

## Current Validation Evidence

- 2026-06-05 frontend typecheck: `cd frontend && npm run typecheck` passed.
- 2026-06-05 map detail unit coverage: `cd frontend && npm test -- --run src/App.test.tsx -t "opens an inspectable place detail dialog"` passed with 1 selected test.
- 2026-06-05 adjacent map coverage: `cd frontend && npm test -- --run src/App.test.tsx -t "toggles itinerary detail between list and map views|opens an inspectable place detail dialog|uses stored Kakao place URL"` passed with 3 selected tests.
- 2026-06-05 frontend baseline: `cd frontend && npm test` passed with 8 files and 155 tests after adding Place Search/Add coverage and stabilizing the MyPage profile editor test to wait for loaded profile option buttons.
- 2026-06-05 place search/add RED: `cd frontend && npm test -- --run src/App.test.tsx -t "searches recommendation candidates from the add-place sheet"` failed because the add-place sheet did not call `listRecommendations`.
- 2026-06-05 place search/add GREEN: `cd frontend && npm test -- --run src/App.test.tsx -t "searches recommendation candidates from the add-place sheet"` passed with 1 selected test.
- 2026-06-05 adjacent place edit coverage: `cd frontend && npm test -- --run src/App.test.tsx -t "adds, edits, and deletes places from the itinerary detail|searches recommendation candidates from the add-place sheet|restores and clears add-place drafts"` passed with 3 selected tests.
- 2026-06-05 Kakao Local candidate smoke: `cd backend && .venv/bin/python -m app.scripts.smoke_kakao_local_candidates --min-candidates 6` passed with 5 configured Kakao Local areas, each returning 11 candidates with address, coordinates, external ids, and Kakao place URLs.
- 2026-06-05 catalog fallback smoke: `cd backend && KAKAO_LOCAL_ENABLED=false KAKAO_LOCAL_REST_API_KEY= .venv/bin/python -m app.scripts.smoke_kakao_local_candidates --min-candidates 6` passed with 5 representative fallback areas.
- 2026-06-05 backend candidate tests: `cd backend && .venv/bin/python -m pytest -s tests/test_kakao_local_candidate_smoke.py tests/test_kakao_local.py tests/test_itinerary_recommendations.py` passed with 26 tests.
- 2026-06-09 `/ai-results` source communication: frontend typecheck passed; targeted Vitest passed with 1 file and 7 tests after Docker Desktop WSL integration became available; backend targeted recommendation source tests passed.

## Local Completion Criteria

- Clicking map bottom-sheet place detail opens an inspectable local detail UI. Completed locally on 2026-06-05.
- A user can search for a place and add it to a trip day. Completed locally on 2026-06-05 with recommendation candidates through the existing AppDataApi boundary.
- Local runtime with Kakao Local enabled returns usable candidates for representative regions. Completed locally on 2026-06-05 for 제주 전체, 부산 전체, 속초·고성·양양, 여수·순천, and 경주.
- Local runtime without Kakao Local still produces non-empty, clearly labeled fallback candidates for supported regions. Completed locally on 2026-06-05 for the same representative areas.
- `/ai-results` communicates when candidates are fallback-derived. Completed locally on 2026-06-09 with API `sourceType`, source notice copy, and candidate badges.
- Recommendation explanation does not overclaim unimplemented route-time, rating, or review scoring.

## Relevant Files And APIs

Frontend:

- `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- `frontend/src/pages/itinerary/AiResultsPage.tsx`
- `frontend/src/components/map/KakaoMapView.tsx`
- `frontend/src/lib/kakaoMap.ts`
- `frontend/src/api/appDataApi.ts`
- `frontend/src/api/backendApi.ts`
- `frontend/src/api/types.ts`

Backend:

- `backend/app/api/routes/trips.py`
- `backend/app/services/trips.py`
- `backend/app/services/itinerary_recommendations.py`
- `backend/app/services/kakao_local.py`
- `backend/app/data/itinerary_catalog.py`
- `backend/app/scripts/smoke_kakao_local_candidates.py`

Contracts and references:

- `docs/mvp-api-contract.md`
- `docs/screen-feature-status-screens.md`
- `docs/screen-feature-status-logic.md`

## Non-Goals

- Do not implement public deployment or CI/CD in this spec.
- Do not claim AI, ratings/reviews, or route-time optimization are complete until corresponding services and tests exist.
- Do not add new dependencies without a separate implementation plan.
