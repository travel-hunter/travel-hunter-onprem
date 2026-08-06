# CHECKLIST

## Current status

- Active task/status: `/home` 이번 주 혜택 정책 카드 A안 가독성 개선을 적용했고, 후속으로 카드 본문 요약 문단을 제거해 `제목 → 핵심 혜택 → 기간/조건` 흐름으로 압축했다.
- Scope guard: frontend-only display change; API DTO, backend schema, 정책 수집/정규화 동작은 변경하지 않았다.

## Recent validation

- PASS: `cd frontend && npx vitest run src/app/__tests__/home.test.tsx src/app/__tests__/policies.test.tsx` — 28 passed.
- PASS: `cd frontend && npm run typecheck`.
- PASS: `cd frontend && npm run build`.
- PASS: `docker compose -f compose.yaml build frontend`.
- PASS: `docker compose -f compose.yaml up -d frontend` 후 `curl -I --max-time 5 http://127.0.0.1:4173/home` — `HTTP/1.1 200 OK`.
- BLOCKED: `cd frontend && npm test`는 `python3.14: No module named alembic.__main__` 로컬 backend-test wrapper 환경 문제로 중단된다. 동일 변경 범위는 직접 Vitest로 검증했다.

## Active risks

- 실제 모바일 카드 텍스트 밀도는 로컬 브라우저 폭 360/390/430px에서 최종 육안 확인이 필요하다.
- `npm test` wrapper의 로컬 Alembic/Python 3.14 문제는 별도 환경 정리가 필요하다. 관련 검증은 직접 Vitest/typecheck/build로 대체했다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
