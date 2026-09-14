# 정책 수집 후보 자동 발행 게이트 설계

## 배경

수집(`collect_external_benefits_*`)은 원문 근거를 `external_source_records`에 저장하고, 발행 전 검토 후보(`policy_review_candidates`, `pending`)를 만든다. 현재는 모든 후보를 관리자가 승인해야 공개 정책 카드가 된다. `policy_collection_sources.publication_mode`에 `review | auto_after_reviewed_baseline` 값이 이미 정의돼 있지만 읽는 코드가 없고, `expected_min_records`도 쓰이지 않는다.

이 설계는 그 두 컬럼을 실제로 사용해 **정상적인 갱신은 자동 발행하고, 사람이 봐야 할 후보만 `pending`에 남긴다.**

## 결정 (2026-09-14 확정)

1. 자동 발행은 **이미 발행된 정책의 갱신(`change_kind = material_change`)만** 대상이다. 완전히 새 정책(`new`)은 항상 사람이 본다.
2. 자동 허용 변경 필드는 **금액·기간·상태·공식 URL**(`benefitText`, `startDate`, `endDate`, `status`, `officialUrl`)로 한정한다. `title`, `region`, `city`가 발행본과 달라지면 사람이 본다.
3. `expected_min_records`의 초기값은 소스별 실측 정상 건수의 **절반**으로 잡고, 관리자 API로 조정 가능하게 한다.
4. 기본 모드는 모든 소스 `review`. 소스별로 기준선(사람 승인 1건 이상)이 생긴 뒤 관리자가 켠다.

## 범위

포함:
- 수집 직후 후보마다 게이트를 평가해 자동 승인 또는 `pending` + 사유(`review_reason`) 기록
- 소스 단위 이상 감지(파서 실패, 최소 건수 미달, 30% 초과 급감)와 그 회차 후보 전체 보류
- 관리자 API: 소스 `publicationMode`/`expectedMinRecords` 변경, 후보 DTO에 `reviewReason`
- 관리자 화면: 소스 카드 모드 토글, 후보 사유 배지
- 자동 승인의 감사 로그(`policy_review.auto_approve`)

제외:
- 대상 섬 카탈로그(`eligible_island_*`) — 스펙상 승인 없이는 변경 없음, 계속 수동
- `stay_discount` — alias 정책 수십 건을 갱신하는 특수 경로. 코드상 자동 대상에서 제외(모드를 켜도 `pending`)
- 자동 반려. 게이트는 승인하거나 보류만 한다.

## 데이터 모델

- `policy_review_candidates.review_reason` String(40) nullable — `pending`인 이유. 값: `source_mode_review` | `first_baseline` | `new_policy` | `identity_changed` | `source_anomaly` | `would_publish_hidden` | `low_confidence` | `stay_discount_manual`. 자동 승인된 후보는 `review_reason = 'auto'`, `reviewed_by_user_id NULL`, `review_note = 'auto'`.
- `policy_collection_sources.last_parsed_count` Integer nullable — 마지막 **성공** 수집의 파싱 건수. 급감 판정의 기준선.
- 새 상태값·새 테이블 없음. 마이그레이션 `0041_policy_auto_publish`는 컬럼 2개만 추가하고 행을 넣지 않는다.

## 게이트 규칙

`auto_publish_gate(db, *, candidate, record, source, source_result)`는 후보 생성 직후 호출되며, 아래를 **순서대로** 검사해 첫 실패 사유를 `review_reason`에 쓴다. 전부 통과하면 `approve_candidate(... admin=None, note="auto")`로 즉시 발행한다.

| 순서 | 조건 | 실패 사유 |
|---|---|---|
| 1 | `source.publication_mode == 'auto_after_reviewed_baseline'` | `source_mode_review` |
| 2 | `record.source_category != 'stay_discount'` | `stay_discount_manual` |
| 3 | 같은 소스 카테고리에서 사람이 승인한 후보(`approved` & `reviewed_by_user_id IS NOT NULL`)가 1건 이상 | `first_baseline` |
| 4 | 이번 회차 `source_result.outcome == 'success'` 이고 `parsed_count >= expected_min_records` 이고 (`last_parsed_count`가 있으면) `parsed_count >= 0.7 * last_parsed_count` | `source_anomaly` |
| 5 | `candidate.change_kind == 'material_change'` 이고 이 레코드로 발행된 정책(`published_policy_id`)이 존재 | `new_policy` |
| 6 | 발행본과 비교해 `title`/`region`/`city`가 같다 | `identity_changed` |
| 7 | `map_external_source_semantics(record).policy_status != 'hidden'` (ended 등은 자동 공개하지 않음) | `would_publish_hidden` |
| 8 | `record.confidence >= 70` 이고 `field_completeness >= 60` 이고 `benefit_text`가 비어 있지 않다 | `low_confidence` |

- 4번의 급감 비율 30%는 대상 섬 카탈로그와 같은 정수 연산(`(prev - now) * 100 > 30 * prev`)을 쓴다.
- 4번 실패 시 그 회차의 **모든** 후보가 `source_anomaly`로 보류된다(소스 단위 판단이므로).
- 자동 승인은 기존 `approve_candidate`를 그대로 쓴다. `admin=None`을 허용하도록 시그니처만 넓히고, 감사 로그는 `admin_user_id` 없이 남길 수 없으므로 `policy_review.auto_approve` 액션으로 `admin_user_id`는 시스템 사용자(없으면 로그 생략이 아니라 **감사 테이블에 NULL 허용 컬럼을 추가하지 않고** `after_json.actor = "system"`, `admin_user_id`는 마지막으로 기준선을 승인한 관리자 id)를 기록한다. 즉 "이 자동화를 켠 사람이 책임자"라는 의미다.
- 성공 수집 후 `record_collection_source_run`이 `last_parsed_count`를 갱신한다(실패 회차는 갱신하지 않음).

## API

- `PATCH /api/admin/policy-collection-sources/{sourceKey}`: 기존 `enabled` 외에 선택 필드 `publicationMode` (`review | auto_after_reviewed_baseline`), `expectedMinRecords` (0 이상 정수). 모드를 `auto`로 바꾸려면 기준선(규칙 3)이 있어야 하며 없으면 `409 baseline_required`.
- `GET /api/admin/policy-review-candidates` 항목에 `reviewReason: string | null` 추가.
- `GET /api/admin/policy-collection-sources` 항목에 `expectedMinRecords`, `lastParsedCount`, `autoApprovedLast24h` 추가.

## 화면

- 소스 카드: 모드 토글 버튼(`자동 발행 켜기` / `검토로 되돌리기`)과 `최근 24시간 자동 발행 N건`, `기준 건수 N`.
- 후보 카드: 사유 배지(한글 라벨: 첫 기준선 / 새 정책 / 제목·지역 변경 / 소스 이상 / 비공개 예정 / 신뢰도 낮음 / 숙박세일 수동).
- 기존 개별·일괄 승인 흐름은 그대로.

## 테스트 기준

1. 모드 `review`면 어떤 후보도 자동 승인되지 않는다.
2. 모드 `auto`라도 기준선이 없으면 `first_baseline`으로 보류된다.
3. 기준선이 있고 갱신(`material_change`)이며 금액만 바뀐 후보는 자동 승인되고, 감사 로그 `policy_review.auto_approve`가 남고, 공개 정책이 갱신된다.
4. 제목이 바뀐 갱신은 `identity_changed`, 새 정책은 `new_policy`로 보류된다.
5. 파서 실패·최소 건수 미달·30% 초과 급감 회차의 후보는 모두 `source_anomaly`로 보류된다.
6. `ended` 레코드는 `would_publish_hidden`으로 보류된다.
7. `stay_discount`는 모드와 무관하게 보류된다.
8. `PATCH publicationMode=auto`는 기준선이 없으면 409다.
