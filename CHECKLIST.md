# CHECKLIST

## Current status

- Active task/status: 디지털관광주민증 52개 참여지역의 VisitKorea 지역별 상세 URL을 모두 반영했다.
- Scope guard: backend 디지털관광주민증 source data/materializer/semantic mapper/normalization/seed/Alembic/tests/API contract만 변경했다. Frontend runtime code는 변경하지 않았다.

## Recent validation

- PASS: `cd backend && ../.venv/bin/python -m pytest` — 624 passed, 17 skipped, 1 warning.
- PASS: `cd backend && ../.venv/bin/python -m alembic upgrade head --sql >/tmp/alembic-dgtour-detail-url.sql` — SQL generated through `0034_dgtour_detail_urls` with 52 regional URL values.
- PASS: local compose DB migration rewrite: `alembic downgrade 0033_dgtour_scope && alembic upgrade head` — reapplied `0034_dgtour_detail_urls` after the 52-region URL update.
- PASS: local seed + materializer: `Travel Hunter development seed data applied`; `app.scripts.collect_travelmonth_once --timeout 15` produced 52 `digital_tourism_resident_card` records and promoted active policies.
- PASS: DB audit on `127.0.0.1:55432`: 52 active digital tourism policies, 52 external digital records, 0 generic URLs, 0 non-regional URLs, 0 forbidden half-trip rows.
- PASS: API audit on `127.0.0.1:8000`, saved to `tmp/dgtour-52-api-link-audit.json` and `.csv`: 52/52 list policies, 52/52 detail 200, 52/52 regional VisitKorea `regnMain.do` URLs, 0 generic URLs, 0 forbidden half-trip rows.
- PASS: `cd frontend && npm run typecheck`.
- PASS: `cd frontend && PYTHON=../.venv/bin/python npm test -- --run src/app/__tests__/policy-detail.test.tsx src/app/__tests__/policies.test.tsx` — 32 passed.
- PASS: `cd frontend && npm run build`.
- PASS: logged-in Playwright UI audit on `127.0.0.1:4173`, saved to `tmp/dgtour-52-ui-link-audit.json`: 52/52 CTA found, 52/52 API `officialUrl` equals frontend `혜택 안내 보기` href, 52/52 regional URL, 0 generic URL, 0 forbidden half-trip rows.

## Active risks

- VisitKorea 참여지역/지역별 URL은 변동 가능성이 있다. 현재 지역 URL 매핑은 2026-07-25 렌더링된 VisitKorea 디지털관광주민증 메인 지도 DOM의 `fnRegnMain(mtpcDoCd, signguCd)` 값을 근거로 한다.
- Full frontend `npm test` needs `PYTHON` pointed at the repo venv or an equivalent backend Python environment with Alembic installed.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
