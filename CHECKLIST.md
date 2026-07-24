# CHECKLIST

## Current status

- Active task/status: 디지털관광주민증 정책 수집/표출을 VisitKorea 공식 참여지역 52개 allowlist 기준으로 정리했다.
- Scope guard: backend source materializer, promotion/deactivation gates, seed URLs/status, Alembic data migrations, tests, API contract/docs/eval만 변경했다. Frontend runtime code는 변경하지 않았다.

## Recent validation

- PASS: `cd backend && ../.venv/bin/python -m pytest` — 617 passed, 17 skipped, 1 warning.
- PASS: `cd backend && ../.venv/bin/python -m alembic upgrade head --sql >/tmp/alembic-dgtour.sql` — SQL generated through `0033_dgtour_scope`.
- PASS: `cd frontend && npm run typecheck`.
- PASS: `cd frontend && PYTHON=../.venv/bin/python npm test -- --run src/app/__tests__/policy-detail.test.tsx src/app/__tests__/policies.test.tsx` — 32 passed.
- PASS: API smoke with test DB/env on `127.0.0.1:8002`: `dgtour-강진-7` -> 404, `dgtour-하동-3` -> 200 + `https://korean.visitkorea.or.kr/dgtourcard/`, `dgtour-해남-10` -> 200 + VisitKorea regional dgtourcard URL.
- PASS: local digital materializer run against compose DB: `success 52 52`; `/api/policies` returned 52 `디지털관광주민증` policies.
- PASS: `cd backend && ../.venv/bin/python -m pytest tests/test_policy_normalization.py tests/test_digital_tourism_resident_card.py tests/test_external_benefit_collection.py tests/test_external_source_repository.py tests/test_dgtourcard_parser.py tests/test_policy_data_validation.py tests/test_digital_tourism_identity_migration.py` — 73 passed, 1 warning.
- BLOCKED/ENV: `cd frontend && npm test -- --run ...` without `PYTHON=../.venv/bin/python` still resolves system Python 3.14 and fails before Vitest with `No module named alembic.__main__`.

## Active risks

- VisitKorea 참여지역은 변동 가능성이 있다. 현재 allowlist는 `https://korean.visitkorea.or.kr/dgtourcard/` 기준 2026-07-24 확인 목록이며, 변경 시 data allowlist와 tests를 갱신해야 한다.
- Full frontend `npm test` needs `PYTHON` pointed at the repo venv or an equivalent backend Python environment with Alembic installed.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
