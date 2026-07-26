# CHECKLIST

## Current status

- Active task/status: 대한민국 반값여행(`local_half_trip`) public 게시글 4개 중 강진/영광은 공식 상세 DOM 자동 추출을 개선하고, 합천/완도는 공식 페이지 기반 수동 보정 데이터를 병행해 로컬 API에 반영 완료했다.
- Scope guard: DB schema/API DTO shape는 변경하지 않았다. `structuredDetail`의 기존 5개 섹션(`supportContent`, `periods`, `applicationTarget`, `requiredDocuments`, `notes`) 안에서 데이터 품질만 보강했다.

## Recent validation

- PASS: `cd backend && ../.venv/bin/python -m pytest tests/test_dgtourcard_parser.py tests/test_policy_semantic_mapping.py tests/test_external_benefit_collection.py tests/test_policy_normalization.py -q` — 99 passed, 1 warning.
- PASS: `cd backend && ../.venv/bin/python -m pytest` — 641 passed, 17 skipped, 1 warning.
- PASS: `cd backend && ../.venv/bin/alembic upgrade head --sql >/tmp/alembic-halftrip.sql` — SQL generation completed.
- PASS: `docker compose -f compose.yaml build backend && docker compose -f compose.yaml up -d backend` — local backend image rebuilt and restarted.
- PASS: `docker compose -f compose.yaml exec -T backend python -m app.scripts.collect_travelmonth_once --timeout 25` — outcome success, parsed 81, `local_half_trip` parsed/upserted 12; optional `traffic_benefit` remains 404/source_unavailable.
- PASS: local API audit for `travelmonth-23`, `travelmonth-24`, `travelmonth-25`, `travelmonth-31` — all return populated support/application target/period/document/note sections; 합천/완도 no longer use generic 신청대상/서류 fallback. 화면 노출 문구에서 `KTO`, `수집 원문`, `공식 메인 기준` 같은 내부 출처 표현을 제거했다.
- PASS: `cd frontend && npm run typecheck && npx vitest run src/app/__tests__/policy-detail.test.tsx` — typecheck passed, 21 passed.

## Active risks

- 합천/완도는 공식 페이지 DOM이 표준 필드 구조가 아니므로 수동 보정 manifest에 의존한다. 공식 사이트 문구가 바뀌면 manifest 재검토가 필요하다.
- 강진 공식 `지원내용`은 원문 행 수가 많아 핵심 혜택 카드가 길어질 수 있다. 프론트 표시 밀도는 별도 UX 조정 대상으로 남겨둔다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
