# CHECKLIST

## Current status

- Active task/status: 디지털관광주민증 정책 URL/slug canonical 정리, 52개 상세 지원내용 promotion 안정화, 정책 상세 핵심 혜택 카드 색상 수정 및 로컬 preview 재기동 검증을 완료했다.
- Scope guard: DB schema/API DTO shape는 변경하지 않았다. 디지털관광주민증 공개 slug는 지역별 `dgtour-{지역}` canonical로 통일하고, 기존 `dgtour-{city}-{n}` 및 과거 `travelmonth-*` URL은 같은 지역 canonical 정책으로 호환 해석한다. 전체 제휴처 원문은 `external_source_records.raw_payload.partnerBenefits`에 보존하고, public `structuredDetail.supportContent`에는 요약 + 대표 혜택만 투영한다. 핵심 혜택 카드 색상 변경은 정책 상세 화면에만 스코프를 제한했다.

## Recent validation

- PASS: `cd backend && ../.venv/bin/python -m pytest` — 632 passed, 17 skipped, 1 warning.
- PASS: `cd backend && ../.venv/bin/python -m alembic upgrade head --sql >/tmp/alembic-dgtour-canonical-url.sql`.
- PASS: `cd frontend && npm run typecheck`.
- PASS: `cd frontend && PYTHON=../.venv/bin/python npm test -- --run src/app/__tests__/policy-detail.test.tsx src/app/__tests__/policies.test.tsx` — 33 passed.
- PASS: `cd frontend && npm run build` — typecheck + Vite build, generated `dist/assets/index-CT1HfSAV.css` and JS bundle.
- PASS: `docker compose -f compose.yaml build backend && docker compose -f compose.yaml up -d backend`.
- PASS: `docker compose -f compose.yaml exec -T backend python -m app.scripts.collect_travelmonth_once --timeout 20` — outcome success, `digital_tourism_resident_card` parsed/upserted 52.
- PASS: compose PostgreSQL audit — active digital tourism policies 52, canonical `dgtour-*` 52, active legacy `travelmonth-*` 0, active numbered `dgtour-*-[0-9]` 0, `supportContent` min 6/max 9.
- PASS: API audit saved to `tmp/dgtour-canonical-url-detail-audit.json` — old URLs `travelmonth-95`, `dgtour-하동-3`, `dgtour-영광-8`, `dgtour-완도-15` resolve to canonical `dgtour-{지역}` with rich detail.
- PASS: `docker compose -f compose.yaml build frontend && docker compose -f compose.yaml up -d frontend` — `http://127.0.0.1:4173` now serves `index-CT1HfSAV.css` including `.policy-benefit-group--core`.
- PASS: Playwright computed style check on `http://127.0.0.1:4173/policies/dgtour-%ED%95%98%EB%8F%99` — core benefit card background `rgb(255, 253, 247)`, border `rgb(241, 211, 138)`.
- PASS: `docker compose -f compose.yaml config >/tmp/compose-dgtour-canonical-url.yaml`.
- PASS: `git diff --check` and UTF-8 scan — no whitespace errors, no `U+FFFD`.

## Active risks

- VisitKorea 참여지역/제휴처 혜택 API 응답은 변동 가능성이 있다. 현재 수집 결과는 2026-07-25 기준이며, 배포 환경에서는 새 코드 배포 후 수집 작업 재실행이 필요하다.
- VisitKorea API가 같은 `mbrbId`를 여러 페이지에 반복 반환하는 지역이 있어 저장 시 `mbrbId` 기준으로 중복 제거한다.
- Full frontend `npm test` needs `PYTHON` pointed at the repo venv or an equivalent backend Python environment with Alembic installed.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
