# Frontend Test Helpers

This directory owns shared test support only. Keep production code and API
runtime behavior out of this layer.

## Helper Boundaries

- `fixtures.ts` owns typed test data factories and constants shared by multiple
  test files.
- `renderAppRoute.tsx` owns full-app route rendering helpers. Use
  `renderAppRoute` only for route or app-shell integration tests because it
  renders `App` inside `AppProviders`.
- `kakaoMock.ts` owns Kakao Maps SDK test doubles and browser globals.
- Keep component-only tests self-contained unless they genuinely need shared
  typed fixtures.

## Route Test Organization

The former monolithic `App.test.tsx` has been split by route ownership into
`src/app/__tests__/`. Add new route/app-shell tests to the file that matches
the feature under test:

- `auth.test.tsx` — app-shell bootstrap, login, session, protected routes.
- `trip-create.test.tsx` — `/trips/new`, travel-area recommendations, itinerary
  generation, selected dates.
- `trip-detail.test.tsx` — `/trips/:tripId`, day/view/place params, map
  candidates, linked/recommended policies.
- `place-edit.test.tsx` — place add/edit/delete, drafts, drag ordering,
  viewer read-only.
- `ai-results.test.tsx` — `/ai-results?tripId=...`, candidate selection, map-first
  behavior.
- `trips-list.test.tsx` — `/trips`, deletion, confirmation control visibility.
- `policies.test.tsx` — `/policies`, filters/tabs, policy-trip picker.
- `policy-detail.test.tsx` — `/policies/:policySlug`, official/apply links,
  section formatting, info-only states.
- `home.test.tsx` — home rails and region-recommendation fallbacks.
- `mypage.test.tsx` — `/mypage`, saved/applied policies, profile, and settings menu.
- `invite-oauth.test.tsx` — profile setup, invites, password reset, OAuth
  callback/start, sharing.

These files drive a shared, stateful dev backend, so vitest runs test files
serially (`fileParallelism: false` in `vite.config.ts`).
