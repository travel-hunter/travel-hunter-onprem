# CHECKLIST

## Current status

- Active task/status: Trips recommendation preview action bar now matches the `main > section` width while keeping the visit-time editor above the fixed bottom bar.
- Scope guard: 변경 범위는 `/trips/:tripId` 추천 일정 미리보기 UI와 관련 frontend regression test로 제한한다.

## Recent validation

- PASS: RED 확인 — `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx --testNamePattern "recommendation preview|추천"` failed before implementation on missing `선택 저장`, local time save, and centered notice behavior.
- PASS: Browser RED 확인 — mocked Playwright smoke showed action bar width mismatch before this fix: 1024px viewport had section 760px vs action bar 1009px, and 1440px had section 820px vs action bar 1425px.
- PASS: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx` — 35 passed.
- PASS: `cd frontend && npm run typecheck`.
- PASS: `cd frontend && npm run build`.
- PASS: Mocked Playwright smoke at `http://127.0.0.1:4175/trips/124?day=1` for 360/390/430/1024/1440px showed action bar x/width matching `main > section`, 13px gap above the bottom action bar for the floating time editor, visible `저장` button, and no console/page issues. Screenshots saved outside repo: `/tmp/trips-actionbar-pr-390.png`, `/tmp/trips-actionbar-pr-1024.png`.
- PASS: `git diff --check -- frontend/src/pages/itinerary/ItineraryDetailPage.tsx frontend/src/styles/app.css frontend/src/app/__tests__/trip-detail.test.tsx CHECKLIST.md`.
- PASS: UTF-8/U+FFFD check for changed Korean-bearing files.

## Active risks

- No backend/API contract change is included.
- Browser plugin was not available in this session; rendered validation used regular Playwright.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
