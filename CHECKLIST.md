# CHECKLIST

## Current status

- Active task/status: 일정 상세 장소 카드에서 방문 시간이 이전 장소보다 이른 경우 `시간 확인` 경고와 수정 진입점을 표시하도록 구현했다.
- Scope guard: frontend-only display change; API DTO, backend schema, trip move 동작은 변경하지 않았다.

## Recent validation

- PASS: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx` — 33 passed.
- PASS: `cd frontend && npm run typecheck`.
- PASS: `cd frontend && npm run build`.
- PASS: UTF-8/U+FFFD check for changed files.
- PASS: `git diff --check`.
- BLOCKED: `cd frontend && npm test`는 `python3.14: No module named alembic.__main__` 로컬 backend-test wrapper 환경 문제로 Vitest 진입 전 중단된다. 동일 변경 범위는 직접 Vitest/typecheck/build로 검증했다.

## Active risks

- 경고는 같은 Day 안의 표시 순서와 `HH:mm` 시간만 기준으로 계산한다. 이동 시간, 체류 시간, 영업시간까지 자동 판단하지 않는다.
- 로컬 브라우저에서 실제 카드 밀도와 모바일 줄바꿈 최종 육안 확인이 필요하다.
- `npm test` wrapper의 로컬 Alembic/Python 3.14 문제는 별도 환경 정리가 필요하다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
