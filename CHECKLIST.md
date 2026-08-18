# CHECKLIST

## Current status

- Active task/status: Trips recommendation preview controls updated for `선택 저장`, single time editor, local time save, centered candidate-save notice, and full-width bottom action bar.
- Scope guard: 변경 범위는 `/trips/:tripId` 추천 일정 미리보기 UI와 관련 frontend regression test로 제한한다.

## Recent validation

- PASS: RED 확인 — `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx --testNamePattern "recommendation preview|추천"` failed before implementation on missing `선택 저장`, local time save, and centered notice behavior.
- PASS: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx` — 34 passed.
- PASS: `cd frontend && npm run typecheck`.
- PASS: `cd frontend && npm run build`.
- PASS: `git diff --check -- frontend/src/pages/itinerary/ItineraryDetailPage.tsx frontend/src/styles/app.css frontend/src/app/__tests__/trip-detail.test.tsx CHECKLIST.md`.
- PASS: UTF-8/U+FFFD check for changed Korean-bearing files.

## Active risks

- No backend/API contract change is included.
- Browser visual smoke was not run in this PR worktree; behavior is covered by targeted React tests and build/typecheck.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
