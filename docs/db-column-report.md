# Travel Hunter DB 컬럼 설명 보고서

- 작성일: 2026-07-11
- 최근 갱신: 2026-07-12 (`policies` first-pass semantic hardening 반영)
- 기준 schema: `docs/db-schema-current.sql`
- 보조 기준: `docs/db-schema-current.md`, `docs/db-erd.md`, `backend/app/models/tables.py`
- 기준 Alembic head: `0025_prune_contact_notify`
- 범위: 현재 PostgreSQL schema의 20개 테이블과 모든 컬럼

## 1. 요약 판단

현재 schema는 **20개 테이블, 213개 컬럼**으로 구성되어 있다. 테이블 수 20개 자체는 MVP가 인증, 정책 수집, 여행 일정, 알림 이력, 운영 감사까지 포함한다는 점을 고려하면 과도하다고 단정하기 어렵다. 다만 컬럼 수가 큰 테이블에는 서로 다른 책임이 섞여 있어 장기적으로는 정리 여지가 있다.

컬럼 수 상위 테이블은 다음과 같다.

| 순위 | 테이블 | 컬럼 수 | 1차 판단 |
|---:|---|---:|---|
| 1 | `external_source_records` | 37 | 원문 보존과 추출 후보가 함께 있어 큼. 분리/보관 정책 검토 가치가 가장 높음. |
| 2 | `policies` | 30 | 서비스 노출 정책 정보와 출처/운영 메타데이터가 함께 있어 큼. 현재는 핵심 테이블로 수용 가능. |
| 3 | `users` | 19 | 인증, 프로필, 온보딩, 약관 동의가 한 테이블에 있음. |
| 4 | `notification_deliveries` | 15 | 도메인 기능상 현재 규모는 수용 가능. |
| 5 | `trip_places` | 14 | 도메인 기능상 현재 규모는 수용 가능. |

### 전체 테이블 수에 대한 평가

- **테이블 수 20개는 구조적으로는 납득 가능**하다. 사용자 인증, 임시 가입, 정책, 수집 원문, 여행 일정, 초대, 알림 이력, 감사 로그가 각각 다른 생명주기를 가지기 때문이다.
- **정리 우선순위는 테이블 삭제가 아니라 큰 테이블의 책임 분리와 보관 정책**이다. 특히 `external_source_records`는 원문·추출값·품질정보가 함께 있어 가장 먼저 정리 기준을 세울 만하다.
- `alembic_version`은 업무 테이블이 아니라 migration 메타데이터다. 사람이 보는 “서비스 테이블” 수를 셀 때는 별도 표기하는 것이 좋다.

## 2. 테이블 그룹 지도

### 인증/사용자

- `users`: 서비스 사용자의 로그인 식별자, 기본 프로필, 온보딩 상태, 약관 동의 이력, 권한을 보관하는 중심 테이블이다.
- `auth_refresh_tokens`: 로그인 세션을 연장하기 위한 refresh token의 해시와 만료/폐기 상태를 저장한다.
- `social_accounts`: 구글·카카오 같은 외부 OAuth 계정과 내부 사용자 계정을 연결한다.
- `password_reset_tokens`: 비밀번호 재설정 링크/코드의 토큰 해시와 사용 여부를 추적한다.
- `pending_signups`: 이메일 회원가입 과정에서 아직 최종 사용자로 확정되지 않은 가입 요청과 약관 동의 정보를 임시 보관한다.
- `pending_social_signups`: 소셜 로그인 후 추가 가입 절차가 필요한 사용자의 provider 정보와 임시 토큰을 보관한다.
- `admin_audit_logs`: 관리자성 변경 작업의 대상, 요약, 변경 전후 JSON을 남기는 감사 로그 테이블이다.

### 정책/수집

- `policies`: 사용자에게 노출되는 여행 지원 정책의 정규화된 본문, 신청/공식 링크, 수집 출처, 운영 상태를 저장하는 핵심 정책 테이블이다.
- `policy_documents`: 정책 신청에 필요한 제출 서류 목록을 정책별로 저장한다.
- `user_saved_policies`: 사용자가 관심 정책을 저장한 관계를 표현하는 즐겨찾기/스크랩 테이블이다.
- `external_source_records`: 외부 정책 수집기가 가져온 원문, 추출값, 품질 점수, freshness 상태를 저장하는 수집 원문/근거 저장소다.

### 여행 일정

- `trips`: 사용자가 생성한 여행 계획의 기본 정보와 소유자, 기간, 지역, 편집 revision을 저장한다.
- `trip_days`: 여행 일정의 날짜별 단위를 저장한다.
- `trip_places`: 각 여행 날짜에 방문할 장소, 좌표, 외부 장소 식별자, 방문 순서와 메모를 저장한다.
- `trip_members`: 여행 계획에 참여한 사용자와 역할을 저장한다.
- `trip_policies`: 여행 계획에 첨부한 지원 정책 관계를 저장한다.
- `trip_invites`: 여행 계획 초대 링크 토큰, 생성자, 역할, 만료/수락 상태를 저장한다.
- `recommendations`: 사용자/여행 조건을 기반으로 생성한 추천 요청과 결과 JSON을 보관한다.

### 알림/운영 메타데이터

- `notification_deliveries`: 과거 정책 마감 알림 발송 이력을 사용자·정책 단위로 보존한다. 현재 runtime은 제거되어 inert history로만 사용한다.
- `alembic_version`: Alembic이 현재 DB에 적용된 migration revision을 추적하는 메타데이터 테이블이다.

## 3. 테이블별 컬럼 상세

### 3.1. `users`

- **존재 목적:** 서비스 사용자의 로그인 식별자, 기본 프로필, 온보딩 상태, 약관 동의 이력, 권한을 보관하는 중심 테이블이다.
- **주요 관계:** 다수의 인증 토큰, 소셜 계정, 저장 정책, 여행 소유/멤버십, 추천, 알림 이력과 연결된다.
- **컬럼 수:** 19개
- **정리 판단:** 핵심 테이블이다. 개인정보 최소수집 pass 이후 관심 지역은 `preferred_regions`만 유지한다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 내부 사용자 기본키다. 다른 테이블이 사용자를 참조할 때 기준이 된다. |
| `email` | `character varying(255)` | 필수 | `-` | 로그인 식별자이자 연락 가능한 이메일이다. 중복 가입 방지 기준이 된다. |
| `password_hash` | `character varying(255)` | 선택 | `-` | 비밀번호 로그인 사용자의 해시값이다. 소셜 전용 계정은 비어 있을 수 있다. |
| `nickname` | `character varying(50)` | 필수 | `-` | 서비스 화면에 표시할 사용자 이름이다. |
| `preferred_regions` | `character varying(255)` | 선택 | `-` | 복수 선호 여행 지역을 문자열로 저장한다. 배열/별도 테이블이 아니므로 검색·정렬에는 한계가 있다. |
| `onboarding_completed` | `boolean` | 필수 | `false` | 초기 온보딩 절차 완료 여부다. 첫 진입 UX 분기에 사용된다. |
| `created_at` | `timestamp without time zone` | 필수 | `now()` | 사용자 row 생성 시각이다. |
| `updated_at` | `timestamp without time zone` | 필수 | `now()` | 사용자 프로필 또는 상태가 마지막으로 변경된 시각이다. |
| `travel_style` | `character varying(50)` | 선택 | `-` | 선호 여행 방식이다. 추천 또는 개인화 필터에 사용할 수 있다. |
| `travel_budget` | `character varying(50)` | 선택 | `-` | 선호 예산대다. 추천/필터에 사용할 수 있지만 현재 활용도가 낮으면 정리 후보가 될 수 있다. |
| `role` | `character varying(20)` | 필수 | `'user'::character varying` | 사용자 권한이다. 일반 사용자와 관리자 기능 분기에 사용된다. |
| `nickname_setup_completed` | `boolean` | 필수 | `true` | 닉네임 설정 플로우 완료 여부다. 소셜 가입 후 추가 설정 여부를 판단한다. |
| `profile_setup_skipped` | `boolean` | 필수 | `false` | 프로필 설정을 사용자가 건너뛰었는지 나타낸다. 온보딩 재노출 판단에 사용된다. |
| `terms_accepted` | `boolean` | 필수 | `false` | 서비스 이용약관 동의 여부다. |
| `terms_accepted_at` | `timestamp without time zone` | 선택 | `-` | 서비스 이용약관 동의 시각이다. |
| `terms_version` | `character varying(32)` | 선택 | `-` | 동의한 서비스 이용약관 버전이다. 약관 개정 시 재동의 판단에 필요하다. |
| `privacy_accepted` | `boolean` | 필수 | `false` | 개인정보 처리방침 동의 여부다. |
| `privacy_accepted_at` | `timestamp without time zone` | 선택 | `-` | 개인정보 처리방침 동의 시각이다. |
| `privacy_version` | `character varying(32)` | 선택 | `-` | 동의한 개인정보 처리방침 버전이다. |

**읽는 방법:** `users`에는 로그인 식별자, 선호 지역/여행 프로필, 온보딩, 약관 동의가 함께 있다. 개인정보 최소수집 pass 이후 단일 사용자 지역과 연락처/실명성 프로필 컬럼은 제거됐고, 복수 관심 지역은 `preferred_regions`로만 보관한다.

### 3.2. `auth_refresh_tokens`

- **존재 목적:** 로그인 세션을 연장하기 위한 refresh token의 해시와 만료/폐기 상태를 저장한다.
- **주요 관계:** `user_id`로 `users.id`에 속한다.
- **컬럼 수:** 6개
- **정리 판단:** 보안 세션 운영에 필요하다. 원문 토큰이 아니라 해시만 저장하는 방향은 적절하다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | refresh token row 기본키다. |
| `user_id` | `bigint` | 필수 | `-` | 토큰 소유 사용자 id다. |
| `refresh_token_hash` | `character varying(255)` | 필수 | `-` | refresh token 원문 대신 저장하는 해시값이다. |
| `created_at` | `timestamp without time zone` | 필수 | `now()` | 토큰 발급 시각이다. |
| `expires_at` | `timestamp without time zone` | 필수 | `-` | 토큰 만료 시각이다. |
| `revoked_at` | `timestamp without time zone` | 선택 | `-` | 로그아웃/강제폐기 등으로 토큰이 무효화된 시각이다. |

### 3.3. `social_accounts`

- **존재 목적:** 구글·카카오 같은 외부 OAuth 계정과 내부 사용자 계정을 연결한다.
- **주요 관계:** `user_id`로 `users.id`에 속하며, provider/provider_id 조합으로 외부 계정을 식별한다.
- **컬럼 수:** 6개
- **정리 판단:** 소셜 로그인을 유지하는 한 필요하다. provider별 unique 제약과 내부 사용자 FK가 중요하다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 소셜 계정 연결 row 기본키다. |
| `user_id` | `bigint` | 필수 | `-` | 연결된 내부 사용자 id다. |
| `provider` | `character varying(20)` | 필수 | `-` | google, kakao 등 외부 인증 제공자 이름이다. |
| `provider_id` | `character varying(255)` | 필수 | `-` | provider가 제공하는 고유 subject/id다. |
| `provider_nickname` | `character varying(100)` | 선택 | `-` | provider에서 받은 표시 이름이다. |
| `created_at` | `timestamp without time zone` | 필수 | `now()` | 소셜 계정 연결 생성 시각이다. |

### 3.4. `password_reset_tokens`

- **존재 목적:** 비밀번호 재설정 링크/코드의 토큰 해시와 사용 여부를 추적한다.
- **주요 관계:** `user_id`로 `users.id`에 속한다.
- **컬럼 수:** 6개
- **정리 판단:** 비밀번호 로그인 기능이 있는 한 필요하다. 만료/사용 처리와 주기적 정리 정책이 필요하다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 비밀번호 재설정 토큰 row 기본키다. |
| `user_id` | `bigint` | 필수 | `-` | 재설정을 요청한 사용자 id다. |
| `token_hash` | `character varying(255)` | 필수 | `-` | 재설정 토큰 원문 대신 저장하는 해시값이다. |
| `created_at` | `timestamp without time zone` | 필수 | `now()` | 토큰 발급 시각이다. |
| `expires_at` | `timestamp without time zone` | 필수 | `-` | 토큰 만료 시각이다. |
| `used_at` | `timestamp without time zone` | 선택 | `-` | 토큰이 실제로 사용된 시각이다. NULL이면 미사용이다. |

### 3.5. `pending_signups`

- **존재 목적:** 이메일 회원가입 과정에서 아직 최종 사용자로 확정되지 않은 가입 요청과 약관 동의 정보를 임시 보관한다.
- **주요 관계:** 아직 `users` row가 생성되기 전 단계라 직접 FK가 없다.
- **컬럼 수:** 11개
- **정리 판단:** 이메일 인증 또는 가입 완료 전 약관 동의 증적이 필요하다면 필요하다. 오래된 pending row 정리 배치가 있으면 좋다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 가입 대기 row 기본키다. |
| `email` | `character varying(255)` | 필수 | `-` | 가입하려는 이메일이다. |
| `token_hash` | `character varying(255)` | 필수 | `-` | 가입 확인 토큰의 해시값이다. |
| `created_at` | `timestamp without time zone` | 필수 | `now()` | 가입 대기 생성 시각이다. |
| `expires_at` | `timestamp without time zone` | 필수 | `-` | 가입 확인 토큰 만료 시각이다. |
| `terms_accepted` | `boolean` | 필수 | `false` | 가입 단계에서 이용약관에 동의했는지 여부다. |
| `terms_accepted_at` | `timestamp without time zone` | 선택 | `-` | 이용약관 동의 시각이다. |
| `terms_version` | `character varying(32)` | 선택 | `-` | 동의한 이용약관 버전이다. |
| `privacy_accepted` | `boolean` | 필수 | `false` | 개인정보 처리방침 동의 여부다. |
| `privacy_accepted_at` | `timestamp without time zone` | 선택 | `-` | 개인정보 처리방침 동의 시각이다. |
| `privacy_version` | `character varying(32)` | 선택 | `-` | 동의한 개인정보 처리방침 버전이다. |

### 3.6. `pending_social_signups`

- **존재 목적:** 소셜 로그인 후 추가 가입 절차가 필요한 사용자의 provider 정보와 임시 토큰을 보관한다.
- **주요 관계:** 아직 `users` row가 생성되기 전 단계라 직접 FK가 없다.
- **컬럼 수:** 10개
- **정리 판단:** 소셜 로그인 후 추가 약관/프로필 절차가 존재하는 한 필요하다. 만료된 토큰 청소가 필요하다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 소셜 가입 대기 row 기본키다. |
| `token_hash` | `character varying(255)` | 필수 | `-` | 가입 완료 단계로 이어지는 임시 토큰 해시다. |
| `provider` | `character varying(20)` | 필수 | `-` | 소셜 인증 제공자 이름이다. |
| `provider_id` | `character varying(255)` | 필수 | `-` | provider의 사용자 고유 id다. |
| `email` | `character varying(255)` | 필수 | `-` | provider에서 받은 이메일이다. |
| `email_verified` | `boolean` | 필수 | `false` | provider가 이메일 검증을 보장했는지 여부다. |
| `nickname` | `character varying(100)` | 선택 | `-` | provider에서 받은 닉네임 또는 초기 닉네임 후보값이다. |
| `redirect_path` | `character varying(500)` | 필수 | `'/home'::character varying` | 가입 완료 후 이동할 내부 경로다. |
| `created_at` | `timestamp without time zone` | 필수 | `now()` | 소셜 가입 대기 생성 시각이다. |
| `expires_at` | `timestamp without time zone` | 필수 | `-` | 소셜 가입 대기 토큰 만료 시각이다. |

### 3.9. `admin_audit_logs`

- **존재 목적:** 관리자성 변경 작업의 대상, 요약, 변경 전후 JSON을 남기는 감사 로그 테이블이다.
- **주요 관계:** `admin_user_id`로 관리자 사용자(`users.id`)를 참조한다.
- **컬럼 수:** 9개
- **정리 판단:** 관리자 기능과 정책 운영 변경의 추적 가능성을 위해 중요하다. 개인정보가 before/after JSON에 과도하게 남지 않도록 주의한다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 감사 로그 row 기본키다. |
| `admin_user_id` | `bigint` | 필수 | `-` | 작업을 수행한 관리자 사용자 id다. |
| `action` | `character varying(80)` | 필수 | `-` | 수행한 작업 코드다. 예: create/update/delete/verify 등. |
| `target_type` | `character varying(40)` | 필수 | `-` | 작업 대상 종류다. 예: policy, user, source_record 등. |
| `target_id` | `character varying(120)` | 필수 | `-` | 작업 대상의 식별자다. 숫자 id 또는 외부 id를 문자열로 저장한다. |
| `summary` | `character varying(300)` | 선택 | `-` | 작업 요약 설명이다. |
| `before_json` | `jsonb` | 선택 | `-` | 변경 전 주요 값 JSON이다. |
| `after_json` | `jsonb` | 선택 | `-` | 변경 후 주요 값 JSON이다. |
| `created_at` | `timestamp without time zone` | 필수 | `now()` | 감사 로그 생성 시각이다. |

### 3.10. `policies`

- **존재 목적:** 사용자에게 노출되는 여행 지원 정책의 정규화된 본문, 신청/공식 링크, 수집 출처, 운영 상태를 저장하는 핵심 정책 테이블이다.
- **주요 관계:** `external_source_record_id`로 수집 원문(`external_source_records.id`)과 연결될 수 있고, 저장/여행첨부/알림/서류 테이블의 중심이 된다.
- **컬럼 수:** 30개
- **정리 판단:** 서비스의 핵심 업무 테이블이다. 컬럼 수는 많지만 정책 상세·출처·운영상태가 섞인 결과이므로 단기적으로는 수용 가능하다. 2026-07 first pass에서는 컬럼 drop/rename 없이 helper로 의미를 중앙화했다. 장기적으로는 structured detail, 운영 메타데이터, 링크 모델 분리를 검토할 수 있다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 정책 기본키다. |
| `slug` | `character varying(160)` | 선택 | `-` | 정책 상세 페이지와 API에서 쓰는 공개 경로 식별자다. |
| `title` | `character varying(200)` | 필수 | `-` | 사용자에게 표시할 정책명이다. |
| `organization` | `character varying(100)` | 선택 | `-` | 정책 주관 기관명이다. |
| `policy_type` | `character varying(30)` | 선택 | `-` | 정책 유형 분류다. 예: 숙박, 교통, 할인, 지원금 등. |
| `description` | `text` | 선택 | `-` | 정책 개요 설명이다. |
| `benefit_amount` | `integer` | 선택 | `-` | 금액형 혜택을 정수 원 단위로 정규화한 값이다. 화면 표시에서는 `benefit_detail`이 먼저 쓰이고, 이 값은 detail이 없을 때의 표시 fallback이나 절약액 집계용 숫자로 남는다. |
| `benefit_detail` | `text` | 선택 | `-` | 혜택 조건·금액·방식의 상세 설명이다. DTO `amount`의 주 표시값이며, `benefit_amount`보다 우선한다. |
| `target_condition` | `text` | 선택 | `-` | 신청 대상 또는 자격 조건 설명이다. DB 필드명은 유지하며, DTO `requirements` fallback 배열은 helper에서 줄 분리/정제한다. |
| `region` | `character varying(50)` | 필수 | `-` | 정책 적용 지역이다. |
| `start_date` | `date` | 선택 | `-` | 신청 또는 사용 가능 시작일이다. |
| `end_date` | `date` | 선택 | `-` | 신청 또는 사용 가능 종료일이다. |
| `official_url` | `character varying(500)` | 선택 | `-` | 정책 공식 안내 페이지 URL이다. DTO `officialUrl`로 내려가며 안내 CTA에 사용된다. |
| `policy_comment` | `character varying(300)` | 선택 | `-` | 운영자가 사용자에게 보여줄 보충 코멘트다. |
| `policy_period` | `character varying(100)` | 선택 | `-` | 원문에 표현된 기간 문구다. 날짜로 완전히 정규화하기 어려운 경우 보존한다. |
| `created_at` | `timestamp without time zone` | 필수 | `now()` | 정책 row 생성 시각이다. |
| `apply_url` | `character varying(500)` | 선택 | `-` | 신청 페이지 또는 신청 안내 URL이다. DTO `applyUrl`로 내려가며, 값이 있으면 `officialUrl`보다 CTA 우선순위가 높다. |
| `source_type` | `character varying(50)` | 선택 | `-` | 정책 출처 유형이다. API `sourceType`은 이 값을 그대로 노출하지 않고 `internal` 또는 `external`로 정규화한다. `external_source_record_id`가 있으면 `external`, 비어 있고 source type도 비어 있으면 `internal`, 지원하지 않는 비어 있지 않은 값은 `external`로 본다. |
| `source_name` | `character varying(100)` | 선택 | `-` | 정책을 가져온 출처/provider 이름이다. |
| `source_category` | `character varying(80)` | 선택 | `-` | 출처 내부 분류다. |
| `external_source_record_id` | `bigint` | 선택 | `-` | 원본 수집 기록 `external_source_records.id` 참조값이다. |
| `source_url` | `character varying(500)` | 선택 | `-` | 수집 또는 근거가 된 원문 URL이다. |
| `source_canonical_key` | `character varying(160)` | 선택 | `-` | 외부 원천에서 중복 판별에 쓰는 canonical key다. 현재는 legacy mixed format을 허용하고, DB aggregate audit에서 key family별 count를 진단한다. |
| `normalized_at` | `timestamp without time zone` | 선택 | `-` | 수집 원문에서 정책 row로 정규화된 시각이다. |
| `last_verified_at` | `timestamp without time zone` | 선택 | `-` | 정책 정보가 마지막으로 확인된 시각이다. |
| `verification_status` | `character varying(30)` | 선택 | `-` | 정책 검증 상태다. 예: verified, needs_review 등. |
| `status` | `character varying(20)` | 필수 | `'active'::character varying` | 서비스 내 노출/운영 상태다. 현재 허용 값은 `active`와 `hidden`이며, public 목록/상세/저장/일정 연결 경로는 active-only 기준을 쓴다. boolean/visibility 컬럼 전환은 phase-2 검토 옵션이다. |
| `admin_override_enabled` | `boolean` | 필수 | `false` | 관리자 수동 수정이 수집 동기화보다 우선해야 하는지 여부다. |
| `updated_at` | `timestamp without time zone` | 필수 | `now()` | 정책 row 마지막 변경 시각이다. |
| `structured_detail` | `jsonb` | 선택 | `-` | 정책 상세 내용을 구조화해 저장한 JSON이다. 혜택·대상·절차 등 확장 정보를 담는다. |

**읽는 방법:** `policies`는 서비스 노출 기준 테이블이다. `external_source_records`에서 온 내용이 정규화되어 들어오며, `admin_override_enabled`가 켜진 정책은 수집 동기화보다 관리자 판단을 우선해야 한다. 2026-07 first pass는 DB schema/API DTO를 바꾸지 않고 `backend/app/services/policy_semantics.py`와 `backend/app/models/policy_status.py`로 혜택 표시, 조건 fallback, link DTO, sourceType 정규화, 공개 상태 의미를 중앙화했다. 현재 schema reference와 SQL snapshot은 그대로 유효하다.

정책 semantics 집계 진단:

```bash
cd backend
.venv/bin/python scripts/audit_policy_semantics.py --json
```

이 명령은 DB를 read-only aggregate 방식으로 읽어 `status`, `benefit_amount`, `apply_url`, source metadata 조합, `source_canonical_key` family를 집계한다. 기존 `backend/scripts/audit_policy_sources.py --json path/to/policies.json`은 별도 JSON 파일을 입력으로 받는 URL/source 품질 auditor이며, DB aggregate 진단과 역할이 다르다.

### 3.11. `policy_documents`

- **존재 목적:** 정책 신청에 필요한 제출 서류 목록을 정책별로 저장한다.
- **주요 관계:** `policy_id`로 `policies.id`에 속한다.
- **컬럼 수:** 5개
- **정리 판단:** 작고 명확한 종속 테이블이다. 유지가 적절하다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 제출서류 row 기본키다. |
| `policy_id` | `bigint` | 필수 | `-` | 해당 서류가 속한 정책 id다. |
| `document_name` | `character varying(100)` | 필수 | `-` | 서류 이름이다. |
| `description` | `character varying(255)` | 선택 | `-` | 서류 설명 또는 제출 조건이다. |
| `is_required` | `boolean` | 필수 | `true` | 필수 제출 여부다. |

### 3.12. `user_saved_policies`

- **존재 목적:** 사용자가 관심 정책을 저장한 관계를 표현하는 즐겨찾기/스크랩 테이블이다.
- **주요 관계:** `user_id`, `policy_id`로 사용자와 정책을 연결한다.
- **컬럼 수:** 4개
- **정리 판단:** 사용자-정책 다대다 관계라 별도 테이블이 적절하다. 컬럼은 최소 구성이다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 저장 정책 row 기본키다. |
| `user_id` | `bigint` | 필수 | `-` | 정책을 저장한 사용자 id다. |
| `policy_id` | `bigint` | 필수 | `-` | 저장된 정책 id다. |
| `saved_at` | `timestamp without time zone` | 필수 | `now()` | 사용자가 정책을 저장한 시각이다. |

### 3.13. `external_source_records`

- **존재 목적:** 외부 정책 수집기가 가져온 원문, 추출값, 품질 점수, freshness 상태를 저장하는 수집 원문/근거 저장소다.
- **주요 관계:** 정규화 후 `policies.external_source_record_id`에서 참조될 수 있는 원천 기록이다.
- **컬럼 수:** 37개
- **정리 판단:** 가장 큰 테이블이지만 원문 근거·정규화 후보·품질 메타데이터를 한 번에 보존하기 위한 수집 staging/audit 성격이라 존재 이유가 강하다. 다만 UI/API가 직접 쓰지 않는 원문·추출 보조 컬럼은 보관 기간과 분리 저장 전략을 검토할 수 있다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 외부 수집 기록 기본키다. |
| `source_name` | `character varying(100)` | 필수 | `-` | 수집 provider 또는 출처 이름이다. |
| `source_type` | `character varying(50)` | 필수 | `-` | 출처 유형이다. 예: 공공 API, 웹 페이지, CSV 등. |
| `source_url` | `character varying(500)` | 필수 | `-` | 출처의 대표 URL이다. |
| `source_category` | `character varying(80)` | 필수 | `-` | 수집 대상의 카테고리다. 예: regional_benefit, stay_discount 등. |
| `external_id` | `character varying(160)` | 필수 | `-` | 외부 시스템에서 제공한 원본 id다. |
| `canonical_key` | `character varying(160)` | 필수 | `-` | 중복 수집을 판별하기 위해 내부에서 만든 표준 키다. |
| `detail_url` | `character varying(500)` | 선택 | `-` | 원문 상세 페이지 URL이다. |
| `collected_page_url` | `character varying(500)` | 필수 | `-` | 실제로 수집기가 접근한 목록/상세 페이지 URL이다. |
| `title` | `character varying(300)` | 필수 | `-` | 원문에서 추출한 정책명 후보값이다. |
| `organizer_text` | `character varying(300)` | 필수 | `-` | 원문에 적힌 주관기관 문자열이다. |
| `organizers` | `jsonb` | 필수 | `-` | 주관기관을 배열/객체 형태로 구조화한 JSON이다. |
| `region` | `character varying(50)` | 선택 | `-` | 원문에서 추출한 광역/지역명이다. |
| `city` | `character varying(80)` | 선택 | `-` | 원문에서 추출한 시군구 또는 세부 지역명이다. |
| `is_nationwide` | `boolean` | 필수 | `false` | 전국 대상 정책인지 여부다. |
| `status_text` | `character varying(50)` | 선택 | `-` | 원문에 적힌 상태 문구다. |
| `status` | `character varying(30)` | 필수 | `-` | 내부 표준 상태값이다. 예: active, inactive, unknown 등. |
| `start_date` | `date` | 선택 | `-` | 원문에서 해석한 시작일이다. |
| `end_date` | `date` | 선택 | `-` | 원문에서 해석한 종료일이다. |
| `benefit_text` | `text` | 필수 | `-` | 원문 혜택 설명 전체 또는 핵심 문구다. |
| `benefit_value_text` | `character varying(300)` | 선택 | `-` | 원문에 표현된 금액/할인율 문구다. |
| `extracted_amount_krw` | `integer` | 선택 | `-` | 혜택 금액을 원 단위 정수로 추출한 값이다. |
| `extracted_discount_percent` | `integer` | 선택 | `-` | 할인율을 퍼센트 정수로 추출한 값이다. |
| `benefit_value_type` | `character varying(30)` | 필수 | `-` | 혜택값의 종류다. 예: amount, discount, text, unknown 등. |
| `tags` | `jsonb` | 필수 | `-` | 원문 또는 추론 태그 JSON이다. |
| `contact_text` | `character varying(200)` | 선택 | `-` | 문의처 또는 연락처 문구다. |
| `inferred_travel_styles` | `jsonb` | 필수 | `-` | 원문으로부터 추론한 여행 스타일 태그 JSON이다. |
| `confidence` | `integer` | 필수 | `-` | 수집/정규화 결과에 대한 신뢰도 점수다. |
| `field_completeness` | `integer` | 필수 | `-` | 필수·권장 필드가 얼마나 채워졌는지 나타내는 완성도 점수다. |
| `raw_list_text` | `text` | 필수 | `-` | 목록 페이지에서 수집한 원문 텍스트다. |
| `raw_detail_text` | `text` | 필수 | `-` | 상세 페이지에서 수집한 원문 텍스트다. |
| `raw_payload` | `jsonb` | 필수 | `-` | 수집기가 받은 원본 응답 또는 중간 파싱 결과 전체 JSON이다. |
| `last_fetched_at` | `timestamp without time zone` | 필수 | `-` | 해당 원천을 마지막으로 가져온 시각이다. |
| `last_verified_at` | `timestamp without time zone` | 선택 | `-` | 원천 내용이 마지막으로 검증된 시각이다. |
| `freshness_status` | `character varying(30)` | 필수 | `-` | 원천 정보의 신선도 상태다. 예: fresh, stale, unavailable 등. |
| `created_at` | `timestamp without time zone` | 필수 | `now()` | 수집 기록 생성 시각이다. |
| `updated_at` | `timestamp without time zone` | 필수 | `now()` | 수집 기록 마지막 변경 시각이다. |

**읽는 방법:** 이 테이블은 사용자에게 바로 보여줄 최종 정책 테이블이 아니라, 수집기가 판단한 “근거 묶음”이다. `raw_*`와 `raw_payload`는 감사·재처리용, `extracted_*`와 `benefit_value_type`은 정규화 후보, `confidence`와 `field_completeness`는 품질 판단용이다.

### 3.14. `trips`

- **존재 목적:** 사용자가 생성한 여행 계획의 기본 정보와 소유자, 기간, 지역, 편집 revision을 저장한다.
- **주요 관계:** `owner_id`로 `users.id`를 참조하고 날짜/장소/멤버/첨부 정책/초대/추천의 중심이 된다.
- **컬럼 수:** 13개
- **정리 판단:** 여행 계획 핵심 테이블이다. 현재 규모는 적절하다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 여행 계획 기본키다. 라우트도 내부 id 기반 문자열을 사용한다. |
| `owner_id` | `bigint` | 필수 | `-` | 여행 계획을 생성한 소유자 사용자 id다. |
| `title` | `character varying(200)` | 필수 | `-` | 여행 계획 제목이다. |
| `start_date` | `date` | 필수 | `-` | 여행 시작일이다. |
| `end_date` | `date` | 필수 | `-` | 여행 종료일이다. |
| `region` | `character varying(100)` | 선택 | `-` | 여행 대표 지역명이다. |
| `description` | `text` | 선택 | `-` | 여행 설명 또는 메모다. |
| `created_at` | `timestamp without time zone` | 필수 | `now()` | 여행 계획 생성 시각이다. |
| `updated_at` | `timestamp without time zone` | 필수 | `now()` | 여행 계획 마지막 변경 시각이다. |
| `status` | `character varying(20)` | 필수 | `'draft'::character varying` | 여행 계획 상태다. 기본 draft다. |
| `travel_area_id` | `character varying(120)` | 선택 | `-` | 지도/지역 provider가 제공하는 여행 지역 id 또는 내부 지역 식별자다. |
| `participant_count` | `integer` | 필수 | `1` | 예상 또는 현재 참여 인원 수다. |
| `revision` | `integer` | 필수 | `1` | 동시 편집/변경 감지를 위한 버전 번호다. |

### 3.15. `trip_days`

- **존재 목적:** 여행 일정의 날짜별 단위를 저장한다.
- **주요 관계:** `trip_id`로 `trips.id`에 속한다.
- **컬럼 수:** 4개
- **정리 판단:** 반복되는 날짜 단위를 분리한 구조라 적절하다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 여행 날짜 row 기본키다. |
| `trip_id` | `bigint` | 필수 | `-` | 소속 여행 계획 id다. |
| `day_number` | `integer` | 필수 | `-` | 여행 n일차 번호다. |
| `date` | `date` | 필수 | `-` | 해당 일차의 실제 날짜다. |

### 3.16. `trip_places`

- **존재 목적:** 각 여행 날짜에 방문할 장소, 좌표, 외부 장소 식별자, 방문 순서와 메모를 저장한다.
- **주요 관계:** `trip_day_id`로 `trip_days.id`에 속한다.
- **컬럼 수:** 14개
- **정리 판단:** 장소 정보와 외부 provider 메타데이터가 함께 있어 컬럼이 비교적 많지만 일정 기능상 자연스럽다. 장소 확장성이 커지면 별도 place cache와 itinerary item 분리를 검토할 수 있다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 방문 장소 row 기본키다. |
| `trip_day_id` | `bigint` | 필수 | `-` | 소속 여행 날짜 id다. |
| `place_name` | `character varying(200)` | 필수 | `-` | 장소 이름이다. |
| `address` | `character varying(500)` | 선택 | `-` | 장소 주소다. |
| `latitude` | `numeric(10,7)` | 선택 | `-` | 위도 좌표다. |
| `longitude` | `numeric(10,7)` | 선택 | `-` | 경도 좌표다. |
| `visit_time` | `time without time zone` | 선택 | `-` | 방문 예정 시각이다. |
| `order_num` | `integer` | 선택 | `-` | 해당 날짜 안에서의 방문 순서다. |
| `memo` | `text` | 선택 | `-` | 장소별 사용자 메모다. |
| `source_provider` | `character varying(40)` | 선택 | `-` | 장소 정보를 가져온 provider 이름이다. 예: kakao 등. |
| `external_place_id` | `character varying(80)` | 선택 | `-` | provider가 제공한 장소 고유 id다. |
| `category_group_code` | `character varying(20)` | 선택 | `-` | provider 장소 카테고리 코드다. |
| `category_group_name` | `character varying(80)` | 선택 | `-` | provider 장소 카테고리 이름이다. |
| `place_url` | `character varying(500)` | 선택 | `-` | provider 장소 상세 URL이다. |

### 3.17. `trip_members`

- **존재 목적:** 여행 계획에 참여한 사용자와 역할을 저장한다.
- **주요 관계:** `trip_id`, `user_id`로 여행과 사용자를 연결한다.
- **컬럼 수:** 5개
- **정리 판단:** 여행 참여자 다대다 관계라 별도 테이블이 적절하다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 여행 멤버 row 기본키다. |
| `trip_id` | `bigint` | 필수 | `-` | 참여 중인 여행 계획 id다. |
| `user_id` | `bigint` | 필수 | `-` | 참여 사용자 id다. |
| `role` | `character varying(20)` | 필수 | `'editor'::character varying` | 여행 내 역할이다. 기본 editor다. |
| `joined_at` | `timestamp without time zone` | 필수 | `now()` | 여행에 참여한 시각이다. |

### 3.18. `trip_policies`

- **존재 목적:** 여행 계획에 첨부한 지원 정책 관계를 저장한다.
- **주요 관계:** `trip_id`, `policy_id`로 여행과 정책을 연결한다.
- **컬럼 수:** 4개
- **정리 판단:** 여행-정책 다대다 관계라 별도 테이블이 적절하다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 여행 첨부 정책 row 기본키다. |
| `trip_id` | `bigint` | 필수 | `-` | 정책을 첨부한 여행 계획 id다. |
| `policy_id` | `bigint` | 필수 | `-` | 첨부된 정책 id다. |
| `added_at` | `timestamp without time zone` | 필수 | `now()` | 정책을 여행에 첨부한 시각이다. |

### 3.19. `trip_invites`

- **존재 목적:** 여행 계획 초대 링크 토큰, 생성자, 역할, 만료/수락 상태를 저장한다.
- **주요 관계:** `trip_id`와 `created_by` 사용자로 연결된다.
- **컬럼 수:** 8개
- **정리 판단:** 초대 토큰과 만료/수락 상태가 있어 별도 테이블이 적절하다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 초대 row 기본키다. |
| `trip_id` | `bigint` | 필수 | `-` | 초대 대상 여행 계획 id다. |
| `invite_token` | `character varying(100)` | 필수 | `-` | 초대 링크에 쓰이는 토큰이다. |
| `created_by` | `bigint` | 필수 | `-` | 초대를 생성한 사용자 id다. |
| `accepted_at` | `timestamp without time zone` | 선택 | `-` | 초대가 수락된 시각이다. NULL이면 미수락이다. |
| `expires_at` | `timestamp without time zone` | 필수 | `-` | 초대 토큰 만료 시각이다. |
| `created_at` | `timestamp without time zone` | 필수 | `now()` | 초대 생성 시각이다. |
| `role` | `character varying(20)` | 필수 | `'editor'::character varying` | 초대 수락 시 부여할 여행 내 역할이다. |

### 3.20. `recommendations`

- **존재 목적:** 사용자/여행 조건을 기반으로 생성한 추천 요청과 결과 JSON을 보관한다.
- **주요 관계:** `user_id`로 사용자, 선택적으로 `trip_id`로 여행에 연결된다.
- **컬럼 수:** 6개
- **정리 판단:** 추천 결과 재사용·디버깅을 위한 로그/캐시 성격이다. 장기 보관 정책과 result JSON schema 관리가 필요하다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 추천 row 기본키다. |
| `user_id` | `bigint` | 필수 | `-` | 추천 요청 사용자 id다. |
| `trip_id` | `bigint` | 선택 | `-` | 추천이 특정 여행 계획에 연결될 때의 여행 id다. |
| `query` | `text` | 선택 | `-` | 추천 생성에 사용한 질의 또는 조건 텍스트다. |
| `result` | `jsonb` | 선택 | `-` | 추천 결과 JSON이다. |
| `created_at` | `timestamp without time zone` | 필수 | `now()` | 추천 생성 시각이다. |

### 3.21. `notification_deliveries`

- **존재 목적:** 과거 정책 마감 알림 발송 예약, 시도, 성공/실패 결과를 사용자·정책 단위로 기록한다.
- **주요 관계:** `user_id`, `policy_id`로 발송 대상 사용자와 정책을 연결한다.
- **컬럼 수:** 15개
- **정리 판단:** 현재 알림 runtime은 제거됐으므로 새 row를 생성하지 않는 inert history로만 유지한다. 향후 알림 기능을 재설계할 때 보관 기간과 삭제 여부를 별도 결정한다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `id` | `bigint` | 필수 | `-` | 알림 이력 row 기본키다. |
| `user_id` | `bigint` | 필수 | `-` | 이력 대상 사용자 id다. |
| `policy_id` | `bigint` | 필수 | `-` | 이력 대상 정책 id다. |
| `channel` | `character varying(30)` | 필수 | `-` | 과거 발송 채널이다. |
| `lead_day` | `integer` | 필수 | `-` | 마감일 며칠 전에 알릴지 나타내는 값이다. |
| `target_deadline_date` | `date` | 필수 | `-` | 알림 기준이 되는 정책 마감일이다. |
| `status` | `character varying(20)` | 필수 | `'pending'::character varying` | 발송 상태다. 기본 pending이다. |
| `attempt_count` | `integer` | 필수 | `0` | 발송 시도 횟수다. |
| `provider_message_id` | `character varying(100)` | 선택 | `-` | 외부 발송 provider가 반환한 메시지 id다. |
| `error_message` | `text` | 선택 | `-` | 발송 실패 시 오류 메시지다. |
| `scheduled_at` | `timestamp without time zone` | 선택 | `-` | 발송 예약 시각이다. |
| `sent_at` | `timestamp without time zone` | 선택 | `-` | 발송 성공 시각이다. |
| `failed_at` | `timestamp without time zone` | 선택 | `-` | 최종 실패 시각이다. |
| `created_at` | `timestamp without time zone` | 필수 | `now()` | 알림 이력 row 생성 시각이다. |
| `updated_at` | `timestamp without time zone` | 필수 | `now()` | 알림 이력 row 마지막 변경 시각이다. |

### 3.22. `alembic_version`

- **존재 목적:** Alembic이 현재 DB에 적용된 migration revision을 추적하는 메타데이터 테이블이다.
- **주요 관계:** 업무 테이블과 FK 관계가 없다.
- **컬럼 수:** 1개
- **정리 판단:** 애플리케이션 업무 테이블은 아니지만 migration 운영에 필수다. 사람이 직접 수정하면 안 된다.

| 컬럼 | 타입 | 필수 여부 | 기본값 | 상세 설명 |
|---|---|---|---|---|
| `version_num` | `character varying(32)` | 필수 | `-` | 현재 DB에 적용된 Alembic migration revision 번호다. |

## 4. 정리 우선순위 제안

1. **`external_source_records` 정리 기준 수립**: 삭제보다 먼저 보관 기간, 원문 압축/아카이브, 재처리에 필요한 최소 필드를 정해야 한다. 원문 근거가 사라지면 정책 품질 검증과 재수집 디버깅이 어려워진다.
2. **`users` 프로필 컬럼 사용처 점검**: `travel_budget`, `preferred_regions`가 현재 추천/정책 자격/화면에서 실제로 쓰이는지 확인하고, 미사용이면 수집 중단 또는 별도 선택 프로필로 격리할 수 있다.
3. **`policies` 책임 분리 후보 검토**: 지금은 MVP상 단일 테이블 유지가 단순하지만, 운영 메타데이터와 상세 JSON이 계속 커지면 `policy_source_metadata`, `policy_structured_details` 같은 분리를 검토할 수 있다. 구체적인 phase-2 선택지는 `docs/specs/policies-table-cleanup-phase2.md`에 둔다.
4. **만료성 테이블 청소 정책**: `pending_signups`, `pending_social_signups`, `password_reset_tokens`, `trip_invites`는 만료 후 정리 배치 또는 운영 절차가 필요하다.
5. **로그/이력 테이블 보관 정책**: `admin_audit_logs`, `notification_deliveries`, `recommendations`는 운영 추적에 유용하지만 장기적으로 보관 기간과 개인정보 마스킹 기준이 필요하다.

## 5. 결론

현재 20개 테이블은 기능 단위로 나뉘어 있어 “테이블 수가 많아서 문제”라고 보기보다는, **큰 테이블의 책임과 보관 목적을 명확히 해야 하는 상태**에 가깝다. 정리의 1순위는 `external_source_records`, 2순위는 남은 선택 프로필 컬럼, 3순위는 `policies`의 운영/출처/상세 정보 분리 가능성이다.

---

### 부록: 컬럼 수 목록

| 테이블 | 컬럼 수 |
|---|---:|
| `admin_audit_logs` | 9 |
| `alembic_version` | 1 |
| `auth_refresh_tokens` | 6 |
| `external_source_records` | 37 |
| `notification_deliveries` | 15 |
| `password_reset_tokens` | 6 |
| `pending_signups` | 11 |
| `pending_social_signups` | 10 |
| `policies` | 30 |
| `policy_documents` | 5 |
| `recommendations` | 6 |
| `social_accounts` | 6 |
| `trip_days` | 4 |
| `trip_invites` | 8 |
| `trip_members` | 5 |
| `trip_places` | 14 |
| `trip_policies` | 4 |
| `trips` | 13 |
| `user_saved_policies` | 4 |
| `users` | 19 |
