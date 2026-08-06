# CHECKLIST

## Current status

- Active task/status: 2026 대한민국 숙박세일 페스타 공식 기간 변경분을 수집, 최신 스냅샷 선택, 정책 alias 상세 표시에 반영했다.
- Scope guard: DB schema와 API shape는 변경하지 않고 기존 `stay_discount` canonical 정책과 alias projection 계약을 유지했다.

## Recent validation

- PASS: RED 확인 — parser provenance 테스트와 missing-logical-key 최신 snapshot selector 테스트가 각각 의도대로 실패했고, semantic mapper 최신 기간 테스트는 기존 mapper가 이미 처리해 통과했다.
- PASS: `docker compose -f compose.yaml run --rm --no-deps -v "$PWD/backend/app:/app/app:ro" -v "$PWD/backend/tests:/app/tests:ro" backend python -m pytest tests/test_travelmonth_stay_parser.py::test_parse_ktostay_latest_august_period_includes_campaign_provenance tests/test_policy_normalization.py::test_stay_selector_prefers_newer_missing_logical_key_snapshot tests/test_policy_semantic_mapping.py::test_stay_mapper_maps_latest_august_periods_to_structured_detail -q` — 3 passed, 1 existing StarletteDeprecationWarning.
- PASS: `docker compose -f compose.yaml run --rm --no-deps -v "$PWD/backend/app:/app/app:ro" -v "$PWD/backend/tests:/app/tests:ro" backend python -m pytest tests/test_travelmonth_stay_parser.py tests/test_policy_semantic_mapping.py tests/test_policy_normalization.py -q` — 90 passed, 1 existing StarletteDeprecationWarning.
- PASS: `docker compose -f compose.yaml run --rm --no-deps -v "$PWD/backend/app:/app/app:ro" -v "$PWD/backend/tests:/app/tests:ro" backend python -m pytest tests/test_policy_db_service.py tests/test_external_source_repository.py tests/test_region_recommendations.py tests/test_travel_areas.py -q` — 86 passed.
- BLOCKED: full backend pytest with correct frontend/alembic/backend binds has 1 unrelated existing failure in `tests/test_local_half_trip_five_semantics_migration.py::test_frozen_migration_semantics_equal_runtime_mapper_for_scoped_records`; failure is half-trip frozen migration Korean copy mismatch, not `stay_discount` behavior.
- PASS: `docker compose -f compose.yaml build backend && docker compose -f compose.yaml up -d backend` — local backend image rebuilt and restarted.
- PASS: live external collection service — `stay_discount` parsed 1, created/updated 1; latest row `id=139` now has `logical_key=stay-discount:2026-summer`, `canonical_key_version=snapshot-v1`, `end_date=2026-08-17`.
- PASS: `docker exec -w /app travel-hunter-onprem-backend-1 python scripts/normalize_external_policies.py` — `promoted_or_repaired=55`.
- PASS: Local API alias detail check — `stay-discount-gangwon-goseong`, `stay-discount-jeonnam-gangjin`, `stay-discount-gyeongnam-hapcheon` all return `startDate=2026-06-11`, `deadline=2026-08-17`, period end dates `['2026-08-17', '2026-08-17']`.

## Active risks

- 공식 페이지 DOM이 다시 바뀌면 live parser fixture 보강이 필요할 수 있다.
- 전체 backend suite의 기존 half-trip frozen migration snapshot 불일치는 별도 정리가 필요하다.
- 개발서버 반영 후 최신 이미지에서 외부 수집 1회와 `scripts/normalize_external_policies.py` 실행이 필요하다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
