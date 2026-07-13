# Travel Hunter 요구사항 정의서

## 문서 기준

- 문서 버전: 2.2
- 기준 브랜치: `develop`
- 기준 검증 기준: `9bdcb73` 및 현재 문서 작업트리
- 실행 모드: DB-backed-only
- 대상 독자: PM, 개발자, QA, 디자이너

이 문서는 Travel Hunter가 제품 관점에서 제공해야 하는 기능과 acceptance 기준을 정의한다. API wire shape는 `docs/mvp-api-contract.md`, 현재 구현/상태 인벤토리는 `docs/implemented-feature-spec.md`, 다음 작업 실행 큐는 `docs/next-work-plan.md`를 따른다.

## 1. 시스템 개요

Travel Hunter는 국내 여행자가 여행 혜택 정책을 찾고, 여행 일정을 만들고, 친구와 협업할 수 있게 하는 모바일 우선 웹 애플리케이션이다.

| 구분 | 요구사항 |
|---|---|
| 주요 사용자 | 국내 여행을 계획하는 개인 사용자 |
| 핵심 가치 | 정책 탐색, 일정 생성/편집, 정책 저장, 초대 협업 |
| 플랫폼 | React/Vite SPA + FastAPI/PostgreSQL backend |
| 데이터 모드 | 모든 사용자-facing 데이터는 backend/PostgreSQL 기준으로 동작 |
| 인증 방식 | 이메일/비밀번호, Kakao OAuth, Google OAuth |

## 2. 사용자 역할

| 역할 | 설명 | 주요 권한 |
|---|---|---|
| Guest | 로그인 전 사용자 | 로그인, 회원가입, 비밀번호 재설정, 초대 링크 진입 후 로그인 유도 |
| Member | 인증된 사용자 | 정책 탐색/저장, 일정 생성/편집, 초대 생성/수락, 프로필 설정 |
| Trip Owner | 일정을 생성한 사용자 | 일정 삭제, 장소 편집, 초대 권한 설정 |
| Trip Editor | editor 권한으로 초대 수락한 멤버 | 일정 장소 편집 |
| Trip Viewer | viewer 권한으로 초대 수락한 멤버 | 일정 열람 |

## 3. 기능 요구사항

### 3.1 인증 및 계정

| ID | 요구사항 | Acceptance |
|---|---|---|
| FR-AUTH-001 | 사용자는 email 중복 확인 후 이메일/비밀번호로 회원가입할 수 있다. | 이름은 받지 않고 성공 시 access token과 user를 받고 refresh token은 HttpOnly cookie로 설정된다. 중복 email은 실패한다. |
| FR-AUTH-001A | 신규 사용자는 가입 직후 닉네임을 설정할 수 있다. | 서버는 임시 닉네임을 자동 생성하고, 사용자는 `/nickname-setup`에서 직접 입력하거나 주사위 버튼으로 새 추천 닉네임을 받아 저장할 수 있다. |
| FR-AUTH-002 | 사용자는 이메일/비밀번호로 로그인할 수 있다. | 성공 시 `/home` 또는 안전한 `redirect` 경로로 이동한다. 실패 시 사용자용 오류 문구가 표시된다. |
| FR-AUTH-003 | 앱은 refresh/logout 세션 흐름을 제공한다. | refresh cookie로 access token을 재발급하고, logout은 refresh token을 revoke하고 로컬 세션을 제거한다. |
| FR-AUTH-004 | 보호 경로는 인증을 요구한다. | 비로그인 사용자가 보호 경로에 접근하면 `/login?redirect=...`로 이동하고 로그인 후 원래 경로로 복귀한다. |
| FR-AUTH-005 | 사용자는 비밀번호 재설정 이메일을 요청할 수 있다. | 계정 존재 여부를 노출하지 않고 요청 응답을 제공한다. 실제 email 발송은 SMTP 설정이 필요하다. |
| FR-AUTH-006 | 사용자는 reset token으로 새 비밀번호를 설정할 수 있다. | 유효 token이면 password hash가 갱신되고 기존 refresh token이 revoke된다. 만료/사용됨/invalid token은 실패한다. |
| FR-AUTH-007 | 사용자는 Kakao/Google OAuth로 로그인할 수 있다. | provider authorization code flow를 시작하고 callback에서 state를 검증한 뒤 social account를 연결/생성한다. 동일 이메일 자동 연결은 검증된 provider email에만 허용하며, Google은 `email_verified=true`가 필수이고 Kakao는 `account_email` scope의 verified email만 서비스 email로 사용한다. Kakao email이 없거나 미검증이면 내부 `oauth.local` email 계정을 만들 수 있고, 이후 verified Kakao email을 받으면 충돌이 없을 때 실제 email로 자동 교체한다. 실제 로그인은 provider env와 등록된 redirect URI가 필요하다. |

### 3.2 사용자 프로필과 설정

| ID | 요구사항 | Acceptance |
|---|---|---|
| FR-USER-001 | 신규 사용자는 관심 지역, 여행 스타일, 예산을 설정할 수 있다. | `/profile-setup` 완료 시 profile 값이 backend에 저장되고 이후 화면에서 반영된다. |
| FR-USER-002 | 사용자는 마이페이지에서 프로필을 편집할 수 있다. | 편집 sheet에서 지역/스타일/예산을 저장하고 성공 후 요약 카드가 갱신된다. |

### 3.3 정책 탐색과 저장

| ID | 요구사항 | Acceptance |
|---|---|---|
| FR-POLICY-001 | 사용자는 정책 목록을 조회할 수 있다. | 정책 카드에는 제목, 기관, 지역, 카테고리, 혜택 요약이 표시된다. |
| FR-POLICY-002 | 사용자는 정책을 검색/필터링할 수 있다. | 검색어, 지역, 카테고리는 client-side AND 조건으로 적용된다. |
| FR-POLICY-003 | 사용자는 정책 상세를 볼 수 있다. | 상세에는 혜택, 조건, 필요 서류, 공식/신청 URL CTA가 표시된다. |
| FR-POLICY-004 | 사용자는 정책을 저장하고 삭제할 수 있다. | 저장 상태는 `user_saved_policies`에 유지되고 새로고침 후에도 반영된다. |
| FR-POLICY-005 | 사용자는 정책 링크를 복사할 수 있다. | 공유 동작은 현재 URL clipboard 복사와 toast 피드백으로 제공된다. |
| FR-POLICY-006 | 사용자는 정책을 특정 일정에 담을 수 있다. | 일정 선택 sheet에서 일정을 고르면 `trip_policies`에 연결되고 일정 상세에서 반영된다. |
| FR-POLICY-007 | 사용자는 홈에서 정책 기반 지역/목적지 추천을 볼 수 있다. | 추천 API는 공식 외부 수집 레코드를 정책 수, 마감 임박, 명시 금액, 취향 보정 순으로 정렬하고 사용자 프로필 지역은 최종 tie-breaker로만 사용한다. |

### 3.4 일정 관리

| ID | 요구사항 | Acceptance |
|---|---|---|
| FR-TRIP-001 | 사용자는 일정 목록을 조회할 수 있다. | 접근 가능한 일정만 표시된다. |
| FR-TRIP-002 | 사용자는 지역, 스타일, 기간을 선택해 일정을 생성할 수 있다. | 생성 결과는 numeric string `Trip.id`를 반환하고 상세 화면 제목은 `{지역} {일수}일 여행` 형식을 따른다. |
| FR-TRIP-003 | 사용자는 일정 상세를 볼 수 있다. | `trip.days` 기준으로 day tab과 장소 타임라인을 동적으로 표시한다. |
| FR-TRIP-004 | owner는 일정을 삭제할 수 있다. | 삭제 후 목록에서 제거되고 연결 데이터는 cascade 또는 서비스 규칙에 따라 정리된다. |
| FR-TRIP-005 | owner/editor는 장소를 추가/수정/삭제할 수 있다. | 장소 변경은 `trip_places`에 저장되고 새로고침 후에도 유지된다. viewer는 편집할 수 없다. |
| FR-TRIP-006 | 일정 상세/편집 handle은 numeric string `Trip.id`만 지원한다. | DB mode 응답의 canonical `Trip.id`는 numeric string이며 non-numeric handle은 not found로 처리된다. |

### 3.5 AI 추천

| ID | 요구사항 | Acceptance |
|---|---|---|
| FR-AI-001 | 사용자는 일정 기준 추천 결과를 조회할 수 있다. | 추천 목록은 현재 저장된 recommendation 데이터를 기반으로 표시된다. |
| FR-AI-002 | 사용자는 추천 항목을 일정에 추가할 수 있다. | 추천 항목은 기존 place 추가 API를 재사용해 `trip_places`에 저장된다. |
| FR-AI-003 | 사용자는 추천 기준 설명을 확인할 수 있다. | 추천 기준 아이콘은 설명 sheet를 열고 닫을 수 있다. |

### 3.6 초대와 협업

| ID | 요구사항 | Acceptance |
|---|---|---|
| FR-INVITE-001 | 사용자는 일정 초대 링크를 만들 수 있다. | 초대 token과 URL이 생성되고 복사 가능한 형태로 표시된다. |
| FR-INVITE-002 | 사용자는 초대 권한을 viewer/editor 중 선택할 수 있다. | 선택한 role은 `trip_invites.role`에 저장되고 수락 시 `trip_members.role`에 반영된다. |
| FR-INVITE-003 | 초대 수신자는 링크로 초대를 수락할 수 있다. | 비로그인 사용자는 로그인 후 원래 초대 URL로 복귀하고, 수락 시 일정 멤버로 추가된다. |
| FR-INVITE-004 | 초대 링크는 외부 발송이 아닌 링크 활성화/공유 중심으로 표현한다. | UI는 실제 email/SMS/Kakao 발송처럼 오해되지 않는 문구를 사용한다. |

### 3.7 마감 알림

마감 알림 연락처, 사용자별 알림 설정, OTP 인증, 발송 scheduler/dispatch/webhook runtime은 현재 제품 범위에서 제거됐다. `notification_deliveries`는 과거 발송 이력/운영 기록을 확인하기 위한 inert history로만 유지하며, 새 알림 발송 row를 생성하지 않는다.

## 4. 비기능 요구사항

| 구분 | 요구사항 |
|---|---|
| 보안 | secret/env 값은 repo에 커밋하지 않는다. 비밀번호, refresh token, reset token, provider id 등 보안 필드는 response에 노출하지 않는다. |
| 데이터 | DB schema는 Alembic migration으로만 관리하고 `create_all()`은 사용하지 않는다. |
| API | DTO는 `camelCase`, DB column은 `snake_case`를 유지한다. |
| 접근성 | 주요 버튼/입력은 키보드 접근 가능해야 하며 모바일 touch target은 44px 이상을 목표로 한다. |
| 배포 | local compose와 Cloudflare Tunnel 중심 배포 방식을 문서화한다. |
| 검증 | 기능 변경 시 backend pytest, frontend typecheck/Vitest, 필요한 migration offline SQL을 실행한다. |
| Release grading | Weekend Public v1/Release Candidate 판정은 OAuth 2종, 정책 수집/정규화/노출, 공개 도메인 배포, 핵심 앱 flow, 최소 로그 가시성의 pass/fail 증거를 기준으로 한다. |

## 5. 데이터 요구사항

주요 persistence 대상은 다음과 같다.

| 영역 | 주요 테이블 |
|---|---|
| 인증 | `users`, `auth_refresh_tokens`, `password_reset_tokens`, `social_accounts` |
| 정책 | `policies`, `policy_documents`, `user_saved_policies` |
| 일정 | `trips`, `trip_days`, `trip_places`, `trip_members`, `trip_policies`, `trip_invites` |
| 추천 | `recommendations` |
| 알림 이력 | `notification_deliveries` (inert history only) |

자세한 API/DB 매핑은 `docs/mvp-api-contract.md`, `docs/db-schema-current.md`, `docs/db-schema-current.sql`을 기준으로 한다.

## 6. 조건부 기능 및 후속 범위

### 조건부 완료

| 기능 | 조건 |
|---|---|
| Password reset email | SMTP host/account/from address와 public base URL 필요 |
| Kakao OAuth | Kakao REST API key/client secret/redirect URI, Kakao Login ON, `account_email` 동의항목, public redirect URI 필요 |
| Google OAuth | Google OAuth client id/secret/redirect URI 필요 |
| Cloudflare Tunnel staging | domain, tunnel token, 실제 runtime env 필요 |

## 7. Weekend Public v1 release addendum

2026-06-14 주말 공개 v1 목표는 일반 MVP 기능 완료와 별도로 다음 release grade 규칙을 따른다.

| 등급 | 필수 조건 |
|---|---|
| Public v1 | Google OAuth, Kakao OAuth, SMTP 비밀번호 재설정, 공개 도메인 `travel-hunter.co.kr`, Cloudflare/Tunnel 또는 동등 public HTTPS route, 정책 수집/정규화/노출, 핵심 auth/profile/policy/trip/invite flow, Kakao Maps public-domain rendering, backend/proxy/tunnel 로그 확인이 모두 증거로 통과한다. |
| Release Candidate | Google OAuth, Kakao OAuth, 정책 수집/정규화/노출, public deployment, 핵심 flow, 최소 로그 가시성은 통과하고, invite email 발송처럼 SMTP 이후 단계 polish만 남는다. |
| Internal Beta | Google OAuth, Kakao OAuth, 정책 수집, 정책 정규화, 정책 공개 노출 중 하나라도 실패하면 RC/Public v1로 부르지 않는다. |
| No Release | 로그인, 데이터 안전성, trip/invite/policy core flow, migration, seed safety, 배포 안정성 중 하나라도 실패한다. |

추가 release 요구:

- 초대 링크는 공개 도메인의 `/invites/{token}/accept`로 열려야 한다. 비로그인 수신자는 로그인/가입 후 원래 초대 링크로 돌아와 수락하고, 로그인 사용자는 바로 수락한다. 만료/오류 링크는 재초대 요청 안내를 표시한다.
- 정책 수집은 seed/static 정책만으로 대체할 수 없다. 최소 한 개 이상의 수집 external record가 정규화되어 `/api/policies`와 `/api/policies/{policySlug}`에 노출되고, stale/hidden/raw-only record는 공개 정책으로 잘못 노출되지 않아야 한다.
- Kakao 장소 별점은 공식 API에서 제공되지 않으면 만들거나 추론하지 않는다. 별점은 v1 차단조건이 아니며, fallback 사용 시 UI는 live Kakao 후보처럼 주장하지 않는다.
- 공개 release 주장은 명령, smoke, 로그, owner 확인 등 증거와 함께 남겨야 하며 secret/env 값은 출력하거나 commit하지 않는다.

### 후속 범위

- 실제 AI 추천 엔진.
- 지도/장소 검색 API와 이동 시간 계산.
- 전화번호 OTP/연락처 알림 재도입은 현재 후속 범위가 아니며, 필요하면 새 제품/API 계약부터 작성한다.
- SMTP readiness 이후 친구 초대 email 발송, 그리고 email 외 SMS/Kakao 외부 발송.
- 운영 관리자 화면.
- 정책 수집 source 확대, full automation, 운영 관리자 수동 제어.
- 공개 사용자용 약관, 개인정보, 운영 모니터링, 백업 체계.

## 8. 문서 관리 규칙

- 요구사항이 바뀌면 이 문서를 먼저 갱신한다.
- API shape가 바뀌면 `docs/mvp-api-contract.md`, frontend type, backend schema/test를 함께 갱신한다.
- 구현 완료/조건부/미구현 상태가 바뀌면 `docs/implemented-feature-spec.md`와 필요한 계약 문서를 갱신한다.
- 다음 우선순위는 `docs/next-work-plan.md`에만 짧게 유지한다.
