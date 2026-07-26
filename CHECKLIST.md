# CHECKLIST

## Current status

- Active task/status: `/policies` 결과 행에서 실제 동작하지 않는 `마감 임박순` 고정 표시를 제거했다.
- Scope guard: 정책 검색/필터/목록 정렬 로직과 API/DB 계약은 변경하지 않고, 오해를 만드는 CSS pseudo-content만 제거했다.

## Recent validation

- PASS: `cd frontend && npm run typecheck` — TypeScript check passed.
- PASS: `cd frontend && npx vitest run src/app/__tests__/policies.test.tsx` — 14 tests passed.
- PASS: `cd frontend && npm run build` — production build completed.
- PASS: UTF-8 replacement scan for changed Korean-bearing files — no U+FFFD found.
- PASS: `git diff --check` — no whitespace errors.

## Active risks

- 로컬 preview 컨테이너 재기동은 아직 수행하지 않았다. 현재 변경은 CSS pseudo-content 제거라 production build 기준으로 반영 가능하다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
