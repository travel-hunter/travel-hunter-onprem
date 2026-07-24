# CHECKLIST

## Current Status

- Active task/status: `/mypage` account section Option A design refresh implemented on `feature/mypage-account-design-refresh` targeting `origin/develop`.
- Scope guard: account card CSS, stable design-hook regression coverage, current validation evidence, and the G005 final review/commit/push/PR delivery gate.
- G005 supersedes G004 as the active delivery gate; merge/production promotion, modal/sheet behavior, API/backend changes, and broader MyPage redesign remain out of scope.

## Latest Validation Evidence

- Password management and withdrawal remain expanded semantic regions using `.prototype-account-section`, section-head/icon hooks, and the existing danger modifier before the settings menu.
- AI slop cleanup pass tightened account CSS selector scope to `/mypage` and reduced duplicate design-hook assertions without changing behavior.
- Frontend typecheck passed after cleanup: `cd frontend && npm run typecheck`.
- Account design and behavior tests passed after cleanup (4 passed, 17 skipped): `cd frontend && npx vitest run src/app/__tests__/mypage.test.tsx -t "account actions|password users change password|OAuth-only account guidance|password confirmation for password user withdrawal"`.
- Production build passed after cleanup: `cd frontend && npm run build`.
- Diff/UTF-8 hygiene passed after cleanup: `git diff --check -- frontend/src/styles/app.css frontend/src/app/__tests__/mypage.test.tsx CHECKLIST.md`; UTF-8/U+FFFD/Hanja scan for scoped files.
- Frontend mojibake precheck passed as part of `cd frontend && npm test -- mypage`.

## Remaining Risks

- `npm test -- mypage` and full `npm test` are blocked before Vitest by the local Python 3.14 Alembic environment: `No module named alembic.__main__; 'alembic' is a package and cannot be directly executed`.
- Direct full-file Vitest ran 21 tests with 16 passing and 5 pre-existing live-data-dependent failures outside the account sections.
- Browser viewport smoke was not run.
- G005 supersedes G004 as the active delivery gate; merge/production promotion remains out of scope.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
