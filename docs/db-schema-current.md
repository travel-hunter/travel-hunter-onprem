# Travel Hunter Current DB Schema

## 기준

- 기준일: 2026-07-12
- 기준 Alembic head: `0026_user_withdrawal_fields`
- PostgreSQL: 16.14 (`postgres:16-alpine` fresh container)
- SQL snapshot: `docs/db-schema-current.sql`
- ERD/관계 시각화: `docs/db-erd.md`
- 생성 방식: 이전 schema-only snapshot에 Alembic head `0026_user_withdrawal_fields`의 offline SQL diff를 반영했다. Fresh DB pg_dump 재생성은 별도 검증으로 다시 수행할 수 있다. Schema 변경은 Alembic 기준으로 추적하고, 관계/핵심 컬럼 요약은 `docs/db-erd.md`가 제공한다.

이 문서는 현재 앱이 사용하는 PostgreSQL schema의 기준 문서다. 초기 SQL 기준본 이후 Alembic migration `0002`~`0026`이 적용된 현재 구조를 설명한다. 테이블 관계, 핵심 컬럼, 제약/index, 문서 drift는 `docs/db-erd.md`를 함께 본다.

## 테이블 그룹

Auth/User:

- `users`
- `auth_refresh_tokens`
- `social_accounts`
- `password_reset_tokens`
- `pending_signups`
- `pending_social_signups`

`social_accounts.provider_id`는 Google OIDC `sub` 등 긴 provider subject를 보관할 수 있도록 `varchar(255)`로 유지한다.

Policy:

- `policies`
- `policy_documents`
- `user_saved_policies`

External collection:

- `external_source_records`

Trip:

- `trips`
- `trip_days`
- `trip_places`
- `trip_members`
- `trip_policies`
- `trip_invites`
- `recommendations`

Notification:

- `notification_deliveries`

Migration metadata:

- `alembic_version`

## v0.3 이후 추가된 구조

추가 테이블:

- `user_saved_policies`
- `notification_deliveries`
- `password_reset_tokens`
- `pending_signups`
- `pending_social_signups`
- `admin_audit_logs`
- `external_source_records`
- `alembic_version`

추가 컬럼:

- `users.travel_style`
- `users.travel_budget`
- `users.nickname_setup_completed`
- `users.profile_setup_skipped`
- `users.terms_accepted` / `users.terms_accepted_at` / `users.terms_version`
- `users.privacy_accepted` / `users.privacy_accepted_at` / `users.privacy_version`
- `users.withdrawn_at` / `users.withdrawn_email_hash`
- `pending_signups.terms_accepted` / `pending_signups.privacy_accepted` 계열 약관 동의 컬럼
- `policies.apply_url`
- `policies.structured_detail`
- `trip_invites.role`
  - 초대 token에 고정되는 권한(`viewer`/`editor`)이다. 같은 일정에서 role별 active invite가 공존할 수 있으며, 다른 role 링크 생성은 기존 token의 role을 변경하지 않는다.
- `trips.status`
- `trips.revision`



## 2026-06-30 ERD/current-code 기준

`docs/db-erd.md`는 SQLAlchemy metadata(`backend/app/models/tables.py`)와 Alembic head `0026_user_withdrawal_fields`를 기준으로 맞춰야 하는 현재 코드 기준 ERD다. 이 ERD는 테이블 관계, 핵심 컬럼, PK/FK/unique/index 요약, `docs/db-schema-current.sql`과의 drift를 함께 기록한다.

이전에 확인됐고 이번 SQL snapshot 재생성으로 해소된 주요 drift:

- 기존 `docs/db-schema-current.sql`은 문서상 `0019_email_first_signup` 기준으로 남아 있었으나, 2026-06-30에 Alembic head `0023_policy_structured_detail` 기준으로 재생성했고 2026-07-11에 `0025_prune_contact_notify` diff를 반영했다.
- `0020_oauth_onboarding_state_flags`: `users.nickname_setup_completed`, `users.profile_setup_skipped` 추가.
- `0021_legacy_social_nickname`: social 계정 onboarding 상태 backfill이며 schema object 추가는 없다.
- `0022_signup_terms_agreements`: `users`와 `pending_signups`의 terms/privacy 동의 컬럼 추가, `pending_social_signups` 테이블 추가.
- `0023_policy_structured_detail`: `policies.structured_detail` JSONB 컬럼 추가. 기존 정책 row는 현재 정책 필드에서 느슨한 사용자 상세 섹션 JSON으로 backfill하되, 조건 섹션은 코드의 조건 정제 규칙과 drift가 생기지 않도록 비워 두고 화면에서 기존 조건 fallback을 사용한다.
- `0024_local_kst_time_shift`: guarded local KST timestamp data shift migration.
- `0025_prune_contact_notify`: contact/OTP/notification settings surface를 제거하면서 `users`의 personal/contact columns와 관련 설정/OTP 테이블을 drop했다. `users.preferred_regions`는 유지한다.
- `0026_user_withdrawal_fields`: soft withdrawal/anonymization 상태 추적을 위해 `users.withdrawn_at`과 HMAC/peppered fingerprint 저장용 `users.withdrawn_email_hash` 및 조회 index를 추가했다. `password_reset_tokens`는 유지한다.

현재 `docs/db-schema-current.sql`은 기존 schema-only snapshot에서 Alembic `0026_user_withdrawal_fields` diff를 반영한 schema reference다. 향후 migration이 추가되면 같은 절차로 다시 생성한다.

## `notification_deliveries`

`notification_deliveries`는 현재 과거 발송 이력/운영 기록을 보존하기 위한 inert history 테이블로만 남는다. 사용자 연락처, OTP 인증, 사용자별 알림 설정, scheduler/dispatch/webhook runtime은 제거됐으며 이 pass 이후 새 발송 row를 생성하지 않는다.

## `pending_signups`

`pending_signups`는 email-first 회원가입 인증 링크를 위한 단기 pending 상태 저장 테이블이다. 원문 토큰은 저장하지 않고 `token_hash`만 보관하며, 비밀번호는 인증 완료 단계에서만 수집한다.

주요 컬럼:

- `id`
- `email`
- `token_hash`
- `created_at`
- `expires_at`

## `users` withdrawal state

`users`는 soft withdrawal 상태를 직접 보관한다. 탈퇴 row는 삭제하지 않으며, user FK가 있는 저장 정책/일정/초대/이력 row를 유지한다.

탈퇴 관련 컬럼/index:

- `withdrawn_at`: 탈퇴 처리 시각. `NULL`이면 active user로 본다.
- `withdrawn_email_hash`: 원래 이메일을 `withdrawn-email:{normalizedEmail}` payload로 HMAC-SHA256 처리한 64자 fingerprint. 원문 이메일은 저장하지 않는다.
- `ix_users_withdrawn_email_hash`: 운영/감사 조회용 btree index.

탈퇴 처리 후 직접 식별자는 다음 값으로 바뀐다.

- `email`: `withdrawn-{id}-{YYYYMMDDHHMMSS}@withdrawn.local`
- `nickname`: `탈퇴한 사용자 #<id>`
- `password_hash`: `NULL`
- `preferred_regions`, `travel_style`, `travel_budget`: `NULL`
- `onboarding_completed`, `profile_setup_skipped`: `false`

`users.email` unique 제약은 유지한다. 탈퇴 시 이메일을 익명화하므로 원래 이메일은 새 active user 가입에 다시 사용할 수 있다. 서비스 조회는 `withdrawn_at IS NULL`과 동등한 active user repository path를 사용해야 한다.

## `password_reset_tokens`

`password_reset_tokens`는 비밀번호 재설정 token hash 이력을 저장한다. 원문 token은 저장하지 않고 `token_hash`만 unique/index로 보관한다.

주요 컬럼:

- `id`
- `user_id`
- `token_hash`
- `created_at`
- `expires_at`
- `used_at`

회원 탈퇴는 soft withdrawal이므로 `password_reset_tokens` row를 삭제하지 않는다. 단, 재설정 confirm은 연결된 user가 active이고 `password_hash`가 있는 경우에만 성공하므로 탈퇴 user 또는 passwordless/OAuth-only user의 기존 token은 fail-closed로 무효 처리된다.

## `external_source_records`

`external_source_records`는 공식 외부 출처에서 수집한 원문과 파생 레코드를 내부 정책/추천 입력으로 변환하기 전에 보존하는 수집 기준 테이블이다. 목록/상세 원문, 출처 메타데이터, 정규화된 지역/상태/혜택/선호도 필드, 신뢰도와 freshness 정보를 함께 저장해 후속 collector, normalizer, recommendation API가 같은 근거 데이터를 재사용할 수 있게 한다. `source_category`는 `regional_benefit`, `traffic_benefit`, `local_half_trip`처럼 출처/혜택 계열을 구분하며, 기존 TravelMonth 지역 수집 전용 값으로 제한하지 않는다.

주요 컬럼 그룹:

- `id`
- `source_name` / `source_type` / `source_url` / `source_category`
- `external_id` / `canonical_key`
- `detail_url` / `collected_page_url`
- `title` / `organizer_text` / `organizers`
- `region` / `city` / `is_nationwide`
- `status_text` / `status` / `start_date` / `end_date`
- `benefit_text` / `benefit_value_text` / `extracted_amount_krw` / `extracted_discount_percent` / `benefit_value_type`
- `tags` / `contact_text` / `inferred_travel_styles`
- `confidence` / `field_completeness`
- `raw_list_text` / `raw_detail_text` / `raw_payload`
- `last_fetched_at` / `last_verified_at` / `freshness_status`
- `created_at` / `updated_at`

## `policies` source tracking

`policies`는 사용자에게 노출되는 공식 혜택의 정규화 테이블이다. TravelMonth 등 외부 공식 수집 레코드는 원문 근거를 `external_source_records`에 보존한 뒤 active/fresh 항목을 `policies`로 승격한다. 승격된 정책은 저장, 일정 연결, 추천 카드, 상세 페이지에서 일반 정책과 같은 경로를 사용한다.

2026-07 first-pass cleanup은 schema 변경이 아니다. `benefit_amount`/`benefit_detail`, `target_condition`, `apply_url`/`official_url`, `source_type`, `source_canonical_key`, `status`의 의미를 helper와 문서로 정리했지만, `policies` 컬럼 drop/rename과 public `Policy` DTO 변경은 하지 않았다.

정책 상세 화면용 구조화 컬럼:

- `structured_detail`: `benefits`, `conditions`, `periods`, `links`, `documents`, `notices` 섹션을 담는 JSONB 정리본이다. raw 수집 JSON이 아니라 사용자 화면에서 바로 섹션 렌더링하기 위한 보조/장기 기준 데이터이며, 섹션이 없거나 비어 있으면 해당 섹션만 기존 `summary`/`requirements` fallback을 사용한다. public 링크는 `http://`/`https://`만 노출한다.

정규화 출처 추적 컬럼:

- `source_type`
- `source_name`
- `source_category`
- `external_source_record_id`
- `source_url`
- `source_canonical_key`
- `normalized_at`
- `last_verified_at`
- `verification_status`

`external_source_record_id`는 `external_source_records.id`를 참조하며, 원문 레코드 삭제 시 정책 row는 유지하고 참조만 `NULL`로 만든다.

API `sourceType`은 `source_type` 원문값을 그대로 노출하지 않고 `internal` 또는 `external`로 정규화한다. `external_source_record_id`가 있으면 `external`, source 정보가 비어 있으면 `internal`, 지원하지 않는 비어 있지 않은 source type은 `external`로 본다. `source_name`, `source_category`, `source_canonical_key`는 중복 판단과 운영 진단 metadata로 유지한다.

정책 semantics 집계 진단은 아래 DB-backed read-only command를 사용한다.

```bash
cd backend
.venv/bin/python scripts/audit_policy_semantics.py --json
```

기존 `backend/scripts/audit_policy_sources.py --json path/to/policies.json`는 파일 입력 기반 URL/source auditor로 남긴다.

## 운영 기준

- Schema 생성과 변경은 Alembic으로만 수행한다.
- 앱 schema 생성을 위해 SQLAlchemy `create_all()`을 사용하지 않는다.
- 현재 구조 공유와 검토는 Alembic head, `docs/db-erd.md`, 그리고 fresh DB에서 생성한 `docs/db-schema-current.sql`을 함께 기준으로 한다. 실제 배포 적용은 여전히 Alembic migration을 사용한다.
- API DTO는 `camelCase`, DB/SQLAlchemy field는 `snake_case`를 유지한다.
- `policies.slug`는 정책 상세 route key다.
- `trips.slug`는 만들지 않는다. 일정 route는 내부 trip id를 사용한다.

## 잔여 리스크

`alembic check`는 현재 index/unique constraint 이름 차이를 감지한다. 예시는 다음과 같다.

- `idx_policies_slug` vs SQLAlchemy metadata의 `ix_policies_slug`
- `idx_trip_invites_token` / `idx_trip_invites_trip_id` vs `ix_trip_invites_*`
- 일부 unique constraint와 unique index 표현 차이

이번 문서 작업은 schema 문서 최신화가 목적이므로 해당 drift를 수정하지 않는다. 필요하면 별도 migration/metadata 정리 작업으로 분리한다.

## 2026-05-27 trips.participant_count

`trips.participant_count` stores a legacy planned travel party size. It remains exposed as `participantCount` for backward compatibility, but the current `/trips/new` flow no longer asks for it and actual participation UI must use `trip_members`/`Trip.people` instead. Real owner/member participation is capped in invite acceptance logic, not by this column.


## 2026-06-11 trips.revision

`trips.revision` is an integer optimistic-lock version for itinerary place edits. It defaults to `1` and is incremented atomically when owner/editor users add, update, move, or delete trip places. The API exposes this field as `Trip.revision`, while place mutation requests send the last seen value as `expectedRevision`.

## Admin management additions

관리자 관리 기반 migration(`0015_admin_management_foundation`)은 일반 사용자와 관리자를 구분하기 위해 `users.role`을 추가한다. 허용 값은 `user`와 `admin`이며 기본값은 `user`다.

관리자 화면에서 public 정책 노출 상태를 제어할 수 있도록 `policies`에 다음 컬럼을 추가한다.

- `status`: `active` 또는 `hidden`, 기본값은 `active`
- `admin_override_enabled`: external normalized policy를 관리자가 수동 보정했는지 나타내며, 기본값은 `false`
- `updated_at`: 정책 수정 시각 추적용 timestamp

현재 `status`는 계속 `active|hidden` string enum이다. public 목록/상세/저장/일정 연결 경로는 active-only 규칙을 공유한다. boolean/visibility 컬럼 전환은 phase-2 schema cleanup 선택지이며, 이 schema snapshot에는 반영하지 않는다.

`admin_audit_logs`는 관리자 변경 이력을 남긴다. `before_json`과 `after_json`에는 sanitized JSON만 저장해야 하며 password hash, token, OTP, OAuth identifier 같은 secret/internal 값은 포함하지 않는다.
