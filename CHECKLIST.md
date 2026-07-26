# CHECKLIST

## Current status

- Active task/status: `/policies` 정책 카드 기간 메타에서 확인되지 않은 시작일을 “시작일 확인 필요”로 보충하지 않도록 로컬 수정 완료했다.
- Scope guard: public Policy DTO에 `startDate: string | null`을 추가해 backend가 안전하게 확정한 대표 시작일만 내려준다. 확인되지 않은 시작일은 `null`이며, frontend는 확정된 시작일/마감일만 표시한다.

## Recent validation

- PASS: `cd frontend && npm run typecheck && npx vitest run src/app/__tests__/policies.test.tsx src/app/__tests__/policy-detail.test.tsx` — typecheck passed, 35 tests passed.
- PASS: `cd frontend && npm run build` — Vite production build completed.
- PASS: `cd backend && ../.venv/bin/python -m pytest tests/test_policy_db_service.py tests/test_policy_normalization.py -q` — 88 passed, 1 warning.
- PASS: `docker compose -f compose.yaml build backend frontend && docker compose -f compose.yaml up -d backend frontend` — local backend/frontend rebuilt and restarted; backend healthy, frontend bound to 4173.
- PASS: local smoke `http://127.0.0.1:8000/api/health`, `http://127.0.0.1:4173/policies`, `http://127.0.0.1:8000/api/policies` — HTTP 200; policy API count 141; API payload contains no “시작일 확인 필요” string.

## Active risks

- `deadline`은 기존 호환 필드라서 마감일 자체가 없으면 배지에는 “마감일 확인 필요”가 남을 수 있다. 이번 수정 범위는 카드 메타의 “시작일 확인 필요” 제거다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
