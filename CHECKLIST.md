# CHECKLIST

## Current status

- Active task/status: 모바일 로그인 화면에서 카톡 인앱 브라우저, iOS Safari, 작은 Android 화면 높이에서 하단 소셜 로그인 버튼이 잘리고 스크롤되지 않던 문제를 수정했다.
- Scope guard: 인증 API/OAuth 시작 경로/로그인 폼 동작은 유지하고, public 로그인 shell의 viewport 높이와 overflow CSS만 조정했다.

## Recent validation

- PASS: `cd frontend && npx playwright test e2e-backend/backend-mode.spec.ts -g "login page remains scrollable" --config=playwright.backend.config.ts` — 390x560 모바일 viewport에서 문서 스크롤과 구글 로그인 버튼 접근 확인.
- PASS: Docker frontend rebuild/restart 후 `http://127.0.0.1:4173/login` Playwright smoke — 390x560 viewport에서 `documentScrollHeight=693`, `scrollY=133`, 구글 버튼 visible.
- PASS: `cd frontend && npx vitest run src/app/__tests__/auth.test.tsx` — 10 tests passed.
- PASS: `cd frontend && npm run build` — typecheck and Vite production build passed.
- PASS: `cd frontend && npm run test:mojibake` — no mojibake-like frontend text found.
- BLOCKED: `cd frontend && npm test` — test wrapper fails before frontend vitest because current Python 3.14 environment cannot run `python -m alembic` (`No module named alembic.__main__`). Direct vitest then shows 2 existing unrelated failures in policy document/trip creation expectations.

## Active risks

- 실제 iPhone Safari/카톡 인앱 브라우저는 로컬 Playwright가 완전히 동일하게 에뮬레이션하지 못하므로, 배포 전 실기기에서 `/login` 하단 구글 버튼까지 스크롤되는지 한 번 확인해야 한다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
