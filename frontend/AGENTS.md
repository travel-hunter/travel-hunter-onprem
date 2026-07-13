# Frontend Agent Rules

## Scope

These rules apply inside `frontend/`. The app is a React, TypeScript, Vite, and React Router frontend for the Travel Hunter MVP.

## Architecture

- Keep route composition under the app entry/provider structure.
- Keep pages focused on rendering and user flow.
- Access data only through `src/api` boundaries, especially `AppDataApi`.
- Do not import seed data directly into pages or reusable UI components.
- The frontend always calls the FastAPI backend. Do not reintroduce a runtime data-source selector or mock API client.

## UI Rules

- Preserve the production app experience. Do not reintroduce prototype wrappers, phone status bars, or explanatory prototype copy.
- Public routes include `/`, `/login`, and `/signup`.
- Protected routes must redirect anonymous users to `/login`.
- Authenticated smoke routes include `/home`, `/policies`, `/policies/{seededPolicySlug}`, `/trips`, `/trips/new`, `/trips/{seededTripId}`, `/ai-results?tripId={seededTripId}`, `/friend-invite?tripId={seededTripId}`, and `/mypage`; substitute a currently seeded policy slug and trip id.
- Check responsive behavior at 360, 390, 430, 1024, and 1440 px widths when UI layout changes.
- Avoid horizontal overflow, blank root rendering, and text clipping.

## API And Types

- API DTO fields are `camelCase`.
- When API response shape changes, update `src/api/types.ts`, API clients, tests, `docs/mvp-api-contract.md`, and `.agent/evals/api-contract-golden.json`.
- Policy detail uses `policySlug`; trip detail uses `tripId`.

## Validation

Run relevant checks after frontend changes:

```bash
npm run typecheck
npm test
npm run test:e2e
npm run build
```

If a check cannot run, record the exact command and blocker in the handoff or `CHECKLIST.md`.
