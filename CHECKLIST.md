# CHECKLIST

## Current Status

- Active task/status: port only `b6e85f0` MyPage account settings changes onto current onprem `develop` via `agent/mypage-account-settings-dialogs`.
- Scope guard: `/mypage` password management and account withdrawal menu rows, modal/dialog UX, focused regression coverage, and PR delivery only.
- Out of scope: backend/API changes, broader MyPage redesign, merge/production promotion, and unrelated live-data route test failures.

## Latest Validation Evidence

- MyPage account controls now live in the settings menu as `비밀번호 관리` and `회원 탈퇴` rows and open independent dialogs; withdrawal keeps the second confirmation dialog.
- Frontend typecheck passed: `cd frontend && npm run typecheck`.
- Frontend mojibake scan passed: `cd frontend && npm run test:mojibake`.
- Account-focused MyPage Vitest passed: `cd frontend && npx vitest run src/app/__tests__/mypage.test.tsx -t "account|password|withdrawal|OAuth"` (5 passed, 17 skipped).
- Production build passed: `cd frontend && npm run build`.
- Diff and UTF-8 hygiene passed: `git diff --cached --check`, `git diff --cached --check -- CHECKLIST.md`, and UTF-8/U+FFFD scan for changed files.

## Remaining Risks

- `cd frontend && npm test -- --run src/app/__tests__/mypage.test.tsx` is blocked before Vitest because an existing local Docker container `travel-hunter-onprem-db-1` already binds `0.0.0.0:55432`.
- Full frontend/backend/e2e suites were not run for this frontend-only port; run them in an isolated environment before merge if required.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
