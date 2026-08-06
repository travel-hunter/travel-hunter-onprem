# CHECKLIST

## Current status

- Active task/status: 디지털관광주민증 정책 상세 지원내용에서 인기 혜택의 업체명, 혜택 설명, 장소 소개를 각각 분리해 표시하고, 본문 폰트 크기를 모바일 가독성 기준으로 재조정했다.
- Scope guard: DB 스키마는 변경하지 않고, 기존 `partnerBenefits` 원본 payload를 유지하면서 `structuredDetail.supportContent[*].url`에 공식 제휴처 상세 URL을 포함하도록 API 계약을 갱신했다.

## Recent validation

- PASS: `docker compose -f compose.yaml run --rm -v "$PWD/backend/app:/app/app:ro" -v "$PWD/backend/tests:/app/tests:ro" backend python -m pytest tests/test_digital_tourism_resident_card.py tests/test_policy_semantic_mapping.py tests/test_policy_normalization.py -q` — 96 passed, 1 existing StarletteDeprecationWarning.
- PASS: `cd frontend && npx vitest run src/app/__tests__/policy-detail.test.tsx -t "renders structured detail sections when the policy provides structuredDetail"` — title/description split regression passed.
- PASS: `docker compose -f compose.yaml run --rm -v "$PWD/backend/app:/app/app:ro" -v "$PWD/backend/tests:/app/tests:ro" backend python -m pytest tests/test_digital_tourism_resident_card.py tests/test_policy_semantic_mapping.py tests/test_policy_normalization.py tests/test_policy_db_service.py -q` — 142 passed, 1 existing StarletteDeprecationWarning.
- PASS: `cd frontend && npx vitest run src/app/__tests__/policy-detail.test.tsx` — 21 passed.
- PASS: `cd frontend && npm run typecheck` and `cd frontend && npm run build`.
- PASS: `docker compose -f compose.yaml build backend && docker compose -f compose.yaml up -d backend && docker compose -f compose.yaml run --rm backend python scripts/normalize_external_policies.py` — `promoted_or_repaired=55`.
- PASS: `docker compose -f compose.yaml build frontend && docker compose -f compose.yaml up -d frontend` — local `http://127.0.0.1:4173` rebuilt.
- PASS: `http://127.0.0.1:8000/api/policies/dgtour-%ED%95%A9%EC%B2%9C` — 대표 혜택이 `🍽️ 로우풀`, `🏨 합천휴테마파크`처럼 이모지만 남고 카테고리명은 제거됨.
- PASS: Playwright authenticated smoke at `http://127.0.0.1:4173/policies/dgtour-%ED%95%A9%EC%B2%9C` — 로우풀 title/benefit/place split verified, benefit weight 700, place weight 550; screenshot `/tmp/dgtour-hapcheon-benefit-bold-place-normal.png`.

## Active risks

- 공식 VisitKorea API는 합천 `all` 목록에서 페이지 경계 중복 항목을 포함해 `totCnt=18`을 내려주지만, 고유 `memberId` 기준 실제 표시 대상은 17곳이다. 현재 구현은 중복을 제거한 고유 업체 수를 표시한다.
- 개발서버 반영 후 기존 persisted structured detail 갱신을 위해 외부 수집 또는 `scripts/normalize_external_policies.py` 실행이 필요하다.

## Cleanup Policy

- Keep this file slim: current status, latest validation evidence, active remaining risks only.
- Do not append long historical logs; replace stale validation detail as new gates run.
- Before claiming completion, run `git diff --check`; for Korean-bearing changes, also verify UTF-8 has no U+FFFD replacement characters.
