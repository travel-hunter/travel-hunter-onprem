# CHECKLIST

## Current status

- Active task/status: `/home` 이번 주 혜택 정책 카드 하단 CTA를 단일 `상세 보기` 문구로 정리했고, 기존 `바로 확인` 문구는 제거했다.
- Scope guard: frontend-only display change; API DTO, backend schema, 정책 수집/정규화 동작은 변경하지 않았다.

## Recent validation

- PASS: `cd frontend && npx vitest run src/app/__tests__/home.test.tsx` — 14 passed.
- PASS: `cd frontend && npm run typecheck`.
- PASS: `cd frontend && npm run build`.
- PASS: `git diff --check`.
- PASS: UTF-8 check for changed source files — no U+FFFD replacement characters.
- BLOCKED: `cd frontend && npm test -- home.test.tsx --runInBand`는 `python3.14: No module named alembic.__main__` 로컬 backend-test wrapper 환경 문제로 테스트 진입 전 중단된다. 동일 변경 범위는 직접 Vitest로 검증했다.

## Active risks

- 실제 카드 하단 CTA 위치는 로컬 브라우저에서 최종 육안 확인이 필요하다.
- `npm test` wrapper의 로컬 Alembic/Python 3.14 문제는 별도 환경 정리가 필요하다. 관련 검증은 직접 Vitest/typecheck/build로 대체했다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
