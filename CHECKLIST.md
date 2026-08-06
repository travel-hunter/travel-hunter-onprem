# CHECKLIST

## Current status

- Active task/status: 대한민국 반값여행 지원 게시글의 지원내용 본문에서 원문 수집 기호 `:`, `ㆍ`, `·`가 혜택 문장 앞에 그대로 노출되는 문제를 백엔드 구조화 매핑 단계에서 정리했다.
- Scope guard: DB 스키마와 API shape는 변경하지 않고, `structuredDetail.supportContent[].description` 표시 문자열 정규화만 수정했다.

## Recent validation

- PASS: `docker compose -f compose.yaml run --rm --no-deps -v "$PWD/backend/app:/app/app:ro" -v "$PWD/backend/tests:/app/tests:ro" backend python -m pytest tests/test_policy_semantic_mapping.py::test_local_half_trip_strips_raw_bullet_prefixes_from_support_content -q` — 1 passed.
- PASS: `docker compose -f compose.yaml run --rm --no-deps -v "$PWD/backend/app:/app/app:ro" -v "$PWD/backend/tests:/app/tests:ro" backend python -m pytest tests/test_policy_semantic_mapping.py tests/test_policy_normalization.py::test_local_half_trip_builds_semantic_structured_detail_for_gangjin tests/test_policy_normalization.py::test_local_half_trip_structured_detail_uses_source_record_fields_without_duplicates -q` — 42 passed, 1 existing StarletteDeprecationWarning.
- PASS: `docker compose -f compose.yaml build backend && docker compose -f compose.yaml up -d backend` — local backend image rebuilt and restarted with `_display_description_text` present.
- PASS: `docker exec -w /app travel-hunter-onprem-backend-1 python scripts/normalize_external_policies.py` — `promoted_or_repaired=55`.
- PASS: Local API 전수 확인 `http://127.0.0.1:8000/api/policies` — 대한민국 반값여행 2건 중 선행 `:`, `ㆍ`, `·` 문제 0건.

## Active risks

- 개발서버 반영 후 기존 persisted `structured_detail` 갱신을 위해 새 이미지 배포 뒤 `scripts/normalize_external_policies.py` 실행이 필요하다.
- 프론트 CSS의 리스트 장식 `•`는 별도 표시 정책이다. 이번 수정은 데이터 원문 기호가 문장 안에 섞이는 문제만 해결한다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
