# Travel Hunter MVP API 계약 v0.3

## 기준

- 기준일: 2026-05-20
- 기준 브랜치: `develop`
- Base URL: `http://localhost:8000/api` (local dev), `https://<domain>/api` (staging/production)
- 인증: Access Token을 `Authorization: Bearer <token>` 헤더로 전달한다.
- Refresh Token: HttpOnly cookie (`refresh_token`)로 관리한다.
- 모든 요청/응답의 Content-Type은 `application/json`이다.
- 이 문서는 실제 route 코드(`backend/app/api/routes/`)와 schema 코드(`backend/app/schemas/`)에서 직접 추출했다.

---

## 공통 에러 형식

```json
{ "detail": "<에러 메시지>" }
```

| 상태 코드 | 의미 |
|-----------|------|
| 400 | 요청 형식 오류 또는 비즈니스 규칙 위반 |
| 401 | 인증 필요 또는 토큰 만료/무효 |
| 403 | 권한 없음 (예: viewer가 편집 시도) |
| 404 | 리소스 없음 |
| 409 | 충돌 (이메일/닉네임 중복 등) |
| 422 | Pydantic validation 실패 |
| 500 | DB 연결 실패 등 서버 오류 |

---

## 시스템

### GET /health

DB 연결 상태 포함 서버 헬스 확인. 인증 불필요.

**Response 200**
```json
{
  "status": "ok",
  "service": "travel-hunter",
  "environment": "local",
  "database": "connected"
}
```

---

## 인증 (`/api/auth`)

## Ops

### GET /ops/external-collection

공식 외부 혜택 수집 scheduler 운영 확인용 상태를 반환한다. 기존 `/health`와 `/api/health` 응답 계약은 변경하지 않는다. 관리자 Bearer 인증이 필요하다.

**Response 200**
```json
{
  "schedulerEnabled": false,
  "runAt": "03:00",
  "pollSeconds": 60,
  "minParsedCount": 1,
  "lastAttemptedRunDate": null,
  "lastSuccessfulRunDate": null,
  "lastParsedCount": null,
  "lastOutcome": null,
  "lastError": null
}
```

`lastOutcome`은 현재 backend process의 in-memory scheduler snapshot이며, 값은 `success`, `partial_success`, `below_threshold`, `error`, 또는 `null`이다. process 재시작 후에는 마지막 실행 상태가 `null`로 돌아간다.

---

### POST /ops/external-collection/run

공식 외부 혜택 수집을 관리자 수동 실행으로 1회 수행한다. configured source를 live fetch하고 parser 결과를 `external_source_records`에 upsert한 뒤, public 대상인 `local_half_trip` 신청접수중/준비중 레코드와 active/fresh `stay_discount` 레코드만 `policies`로 승격한다. `regional_benefit`은 `vacation-benefit.do` 요약/legacy source evidence로 보존하되 대한민국 반값여행(`local_half_trip`)과 동일 정책으로 판단해 public 정책/추천/상세 fallback에서는 제외한다. `traffic_benefit`은 제거/404 가능성이 있는 optional legacy source로 취급한다. 관리자 Bearer 인증이 필요하다.

**Response 200**
```json
{
  "sourceName": "official external benefits",
  "sourceCategory": "multiple",
  "parsedCount": 58,
  "createdOrUpdatedCount": 58,
  "outcome": "success",
  "sources": [
    {
      "sourceCategory": "local_half_trip",
      "parsedCount": 42,
      "createdOrUpdatedCount": 42,
      "outcome": "success",
      "error": null
    }
  ]
}
```

`outcome`은 전체 실행 결과이며 `success`, `partial_success`, `error` 중 하나다. per-source `outcome`은 여기에 `source_unavailable`을 추가로 사용할 수 있으며, source HTTP 404/410은 `source_unavailable`로 기록한다. 필수 공식 source fetch/parser가 실패해도 다른 source가 성공하면 `partial_success`와 per-source `error`를 반환한다. optional legacy `traffic_benefit`의 404/410은 전체 실행을 실패로 강등하지 않는다. 응답에는 API key, bearer token, SMTP credential 같은 secret을 포함하지 않는다.

---

### GET /ops/external-collection/quality

외부 공식 혜택 수집 품질 리포트를 반환한다. 현재 DB의 `external_source_records`를 집계하며 live network fetch는 실행하지 않는다.
관리자 Bearer 인증이 필요하다.

**Query params**

| name | type | description |
|------|------|-------------|
| style | string, optional | 추천 preview에 전달할 취향 보정 값 |
| region | string, optional | 추천 preview에 전달할 최종 tie-breaker 지역 |
| sourceCategory | string, optional | `local_half_trip`, `stay_discount`, legacy `regional_benefit`/`traffic_benefit` 같은 외부 수집 source category 필터 |
| limit | number, optional | 추천 preview 개수. 기본 3, 1~10 |

**Response 200**
```json
{
  "sourceName": "여행가는 달",
  "sourceCategory": "local_half_trip",
  "totalRecords": 58,
  "freshRecords": 58,
  "activeRecords": 58,
  "regionalRecords": 42,
  "nationwideRecords": 16,
  "recordsWithAmount": 21,
  "recordsWithStyles": 37,
  "latestFetchedAt": "2026-05-21T00:00:00",
  "latestVerifiedAt": "2026-05-21T00:00:00",
  "regions": [],
  "recommendationPreview": []
}
```

`regions`는 지역별 저장 품질 집계이며 `recommendationPreview`는 기존 `GET /recommendations/regions`와 같은 ranking service를 사용한다.

---

## Auth (`/api/auth`)

### POST /auth/email-check

회원가입 전 이메일 중복 확인.

**Request**
```json
{ "email": "user@example.com" }
```

**Response 200**
```json
{ "available": true }
```

- `available`은 active user 기준이다. 탈퇴 완료 사용자는 `users.email`을 `withdrawn-{id}-{timestamp}@withdrawn.local`로 익명화하고 `withdrawn_at`으로 비활성 처리하므로, 원래 이메일은 재가입에 사용할 수 있다.

---

### POST /auth/signup

이메일 인증 요청. 성공 시 계정은 아직 생성하지 않고 인증 메일을 발송한다. 같은 이메일의 미완료 pending signup은 새 요청으로 교체한다. 신규 계정 생성 시점의 필수 약관 2종 동의를 함께 검증·저장한다. 탈퇴 사용자는 active user 조회에서 제외되며 원래 이메일이 `withdrawn-...@withdrawn.local`로 바뀌므로, 같은 이메일로 신규 가입할 수 있다.

**Request**
```json
{
  "email": "user@example.com",
  "agreements": {
    "termsAccepted": true,
    "privacyAccepted": true,
    "termsVersion": "2026-06-26",
    "privacyVersion": "2026-06-26"
  }
}
```

**Response 200**
```json
{
  "verificationRequired": true,
  "email": "user@example.com"
}
```

**Errors**
- 400: 필수 약관 미동의 또는 현재 약관 버전 불일치
- 409: 이미 가입 완료된 이메일
- 503: 인증 메일 발송 실패. 이 경우 pending signup은 저장하지 않는다.

---

### POST /auth/signup/verify

회원가입 인증 링크의 token을 검증한다. 성공 시 계정은 아직 생성하지 않고 비밀번호 설정 가능 상태를 반환한다.

**Request**
```json
{ "token": "<verification-token>" }
```

**Response 200**
```json
{
  "verified": true,
  "email": "user@example.com"
}
```

**Errors**
- 400: 인증 token 없음, 만료, 이미 사용됨, 또는 pending signup의 필수 약관 메타데이터가 유효하지 않음
- 409: 이미 가입 완료된 이메일

---

### POST /auth/signup/complete

검증된 회원가입 token과 비밀번호로 계정을 생성한다. 성공 시 access token을 반환하며 refresh token은 cookie에 set.

**Request**
```json
{
  "token": "<verification-token>",
  "password": "password123"
}
```

- `password`: 최소 8자

**Response 200** → `AuthResponse`
```json
{
  "accessToken": "<jwt>",
  "user": { ...User }
}
```

**Errors**
- 400: 인증 token 없음, 만료, 또는 이미 사용됨
- 409: 이미 가입 완료된 이메일
- 409: 인증 전 같은 이메일 계정이 이미 생성됨


---

### GET /auth/oauth/pending-signup

신규 소셜 로그인 callback에서 아직 계정을 만들지 않고 발급한 pending social signup token의 화면 표시용 정보와 서버에 저장된 안전한 완료 후 이동 경로를 조회한다. 기존 소셜 계정은 이 흐름을 타지 않고 바로 로그인된다.

**Query**
```text
token=<pending-social-signup-token>
```

**Response 200**
```json
{
  "provider": "google",
  "email": "user@example.com",
  "nickname": "홍길동",
  "expiresAt": "2026-06-26T06:30:00",
  "redirectPath": "/home"
}
```

**Errors**
- 400: pending social signup token 없음 또는 만료

---

### POST /auth/oauth/pending-signup/complete

신규 소셜 계정 생성 대기 상태에서 필수 약관 2종 동의를 검증한 뒤 실제 `users`와 `social_accounts`를 생성하고 로그인한다.

**Request**
```json
{
  "token": "<pending-social-signup-token>",
  "agreements": {
    "termsAccepted": true,
    "privacyAccepted": true,
    "termsVersion": "2026-06-26",
    "privacyVersion": "2026-06-26"
  }
}
```

**Response 200** → `AuthResponse`, refresh cookie set

**Errors**
- 400: pending social signup token 없음/만료, 필수 약관 미동의 또는 현재 약관 버전 불일치

---

### POST /auth/login

이메일/비밀번호 로그인.

**Request**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response 200** → `AuthResponse`

**Errors**
- 401: 이메일 없음 또는 비밀번호 불일치

---

### POST /auth/refresh

Cookie의 refresh token으로 access token 갱신.

**Request**: body 없음. Cookie `refresh_token` 필요.

**Response 200** → `AuthResponse`

**Errors**
- 401: refresh token 없음, 만료, revoke됨, 또는 token의 사용자가 탈퇴 처리됨. 탈퇴 사용자의 refresh token은 fail-closed로 revoke 후 거절한다.

---

### POST /auth/logout

현재 refresh token을 revoke하고 cookie 삭제.

**Request**: body 없음. Cookie `refresh_token` 필요.

**Response 200**
```json
{ "loggedOut": true }
```

---

### POST /auth/password/change

현재 로그인한 비밀번호 계정의 앱 비밀번호를 변경하고 해당 사용자의 기존 refresh token을 모두 revoke한다. OAuth-only/passwordless 계정은 이번 phase에서 앱 비밀번호를 새로 설정할 수 없으므로 안전하게 거절한다. 탈퇴 사용자는 bearer auth 단계에서 active user가 아니므로 401로 거절된다.

**Request**
```json
{
  "currentPassword": "old-password123",
  "newPassword": "new-password123"
}
```

- `currentPassword`: 최소 1자
- `newPassword`: 최소 8자
- 추가 필드는 허용하지 않는다.

**Response 200**
```json
{ "changed": true }
```

**Errors**
- 400: passwordless 계정이거나 요청 조합이 잘못됨
- 401: 인증 없음 또는 현재 비밀번호 불일치

---

### POST /auth/withdraw

현재 로그인한 계정을 탈퇴 처리한다. 서버는 사용자를 soft-disable/anonymize하고, 소셜 연결과 refresh token을 정리하며, route 응답에서 refresh cookie를 삭제한다. `password_reset_tokens` 이력은 보존하지만, 탈퇴 사용자는 active user가 아니므로 기존 재설정 token confirm은 fail-closed로 거절된다.

**Password user request**
```json
{ "password": "password123" }
```

**OAuth-only/passwordless request**
```json
{ "confirmationPhrase": "탈퇴합니다" }
```

- 비밀번호 계정은 `password`만 허용한다.
- OAuth-only/passwordless 계정은 `confirmationPhrase`만 허용하며 값은 정확히 `"탈퇴합니다"`여야 한다.
- 누락/초과/잘못된 조합과 추가 필드는 거절한다.
- 탈퇴 처리 시 `users.withdrawn_at`을 저장하고, 원래 이메일은 HMAC/peppered `users.withdrawn_email_hash`로만 보관한다. 공개 `email`은 `withdrawn-{id}-{YYYYMMDDHHMMSS}@withdrawn.local`, `nickname`은 `탈퇴한 사용자 #<id>`로 바뀐다.
- `password_hash`, `social_accounts`, profile preference, onboarding/profile skip 상태는 제거·초기화한다. 저장 정책, 일정, 초대 등 user FK가 있는 관계 row는 보존한다.
- 탈퇴 후 bearer/refresh/OAuth 동일 provider-id 또는 동일 이메일 연결은 active user lookup만 사용해 실패한다. 같은 원래 이메일은 새 계정으로 재가입할 수 있으며, `withdrawn_email_hash`는 재가입 차단 키로 쓰지 않는다.

**Response 200**
```json
{ "withdrawn": true }
```

**Errors**
- 400: 계정 유형별 필수 확인값 누락, 초과, 또는 문구 불일치
- 401: 인증 없음 또는 비밀번호 불일치

---

### POST /auth/password-reset/request

비밀번호 재설정 이메일 발송 요청.

**Request**
```json
{ "email": "user@example.com" }
```

**Response 200**
```json
{ "requested": true }
```

> 이메일이 존재하지 않아도 동일한 응답을 반환한다 (열거 방지).
> Passwordless/OAuth-only 계정, 탈퇴 계정, 존재하지 않는 이메일은 모두 token 생성 없이 `{ "requested": true }`를 반환한다.

---

### POST /auth/password-reset/confirm

재설정 토큰으로 새 비밀번호 확정.

**Request**
```json
{
  "token": "<reset_token>",
  "newPassword": "newpassword123"
}
```

- `newPassword`: 최소 8자

**Response 200**
```json
{ "reset": true }
```

**Errors**
- 400: 토큰 만료 또는 무효. token의 user가 탈퇴했거나 passwordless 상태이면 기존 token도 무효로 취급한다.

---

### GET /auth/oauth/{provider}/start

OAuth 인증 시작. `provider`는 `kakao` 또는 `google`.

**Query params**: `redirect` (optional) — 인증 완료 후 돌아올 프론트엔드 경로.

**Response**: 302 → provider 인증 URL로 리디렉션. State cookie set.

**Errors**
- 404: 지원하지 않는 provider
- 503: provider client id/secret/redirect URI 미설정

---

### GET /auth/oauth/{provider}/callback

OAuth provider callback 처리.

**Query params**: `code`, `state`, `error` (provider cancellation/error)

**Success response**: 302 → 프론트엔드 `/oauth/callback?redirect={safePath}`로 리디렉션. Refresh token cookie set, OAuth state cookie clear.

**Failure response**: 302 → 프론트엔드 `/oauth/callback?error={code}&redirect={safePath}`로 리디렉션. Refresh token cookie는 설정하지 않고 OAuth state cookie는 clear한다. Provider `error_description` 원문은 프론트엔드에 전달하지 않는다.

Closed failure codes:

- `access_denied`: provider 동의 취소 또는 `error=access_denied`
- `invalid_state`: state 누락/불일치, code 누락, 사용할 수 없는 state cookie
- `provider_unavailable`: provider 설정 누락, token exchange 실패, provider-side non-cancellation error
- `profile_unavailable`: userinfo/profile fetch 실패 또는 durable provider id 누락
- `email_policy`: Google verified email 누락, 기타 verified-email 자동 연결 정책 위반

Account linking policy:

- 기존 `social_accounts(provider, provider_id)` 연결이 있으면 provider email 변경 여부와 무관하게 해당 사용자를 우선 사용한다.
- 모든 기존 계정 조회는 active user 기준이다. `withdrawn_at`이 있는 탈퇴 사용자의 social account/provider id 또는 원래 email은 자동 연결 대상이 아니며, callback은 새 pending social signup 또는 닫힌 실패로 처리된다.
- 동일 이메일 자동 연결은 provider가 검증 이메일을 제공한 경우에만 허용한다.
- Google은 `email_verified=true`인 email이 필수다.
- Kakao는 `account_email` scope만 요청하고, `kakao_account.is_email_verified=true`이며 `is_email_valid`가 false가 아닌 email만 동일 이메일 연결과 서비스 이메일 표시/연락처 기준에 사용한다.
- Kakao email이 없거나 검증되지 않았으면 기존 이메일 계정에 연결하지 않고 `kakao_{providerId}@oauth.local` 내부 이메일로 새 계정을 만들 수 있다.
- 기존 Kakao social account의 email이 `kakao_{providerId}@oauth.local`인 상태에서 이후 verified Kakao email을 받으면, 같은 email을 가진 다른 user가 없을 때만 `users.email`을 실제 Kakao email로 자동 교체한다. 다른 user가 이미 소유한 email은 자동 병합하지 않는다.

---

## 사용자/프로필 (`/api/me`, `/api/profile-options`)

모든 엔드포인트는 `Authorization: Bearer <token>` 필요 (profile-options 제외).

---

### GET /me

현재 로그인 사용자 정보.

**Response 200** → `User`
```json
{
  "id": "uuid",
  "nickname": "여행자123",
  "email": "user@example.com",
  "role": "user",
  "hasPassword": true,
  "preferredRegions": ["부산", "강원"],
  "persona": "탐험가",
  "savedAmount": 0,
  "onboardingCompleted": false,
  "nicknameSetupCompleted": false,
  "socialAccounts": [],
  "createdAt": "2026-05-19T00:00:00",
  "updatedAt": "2026-05-19T00:00:00"
}
```

---

### GET /me/profile

프로필 (여행 지역/스타일/예산).

**Response 200**
```json
{
  "preferredRegions": ["부산", "강원"],
  "style": "휴식",
  "budget": "1인 40만원 이하"
}
```

- `preferredRegions`는 17개 광역시도 중 최대 3개를 담는다. 미설정 상태는 `null`이며 UI의 `미정` 표시는 저장/전송하지 않는다.
- 요청 body에 정의되지 않은 프로필 필드를 보내면 422를 반환한다.

---

### PATCH /me/profile

프로필 업데이트. 모든 필드 optional.

**Request**
```json
{
  "preferredRegions": ["제주", "부산", "강원"],
  "style": "가족",
  "budget": "1인 40만원 이하"
}
```

- 모든 필드는 생략 가능하다. 명시적으로 `null` 또는 빈 `preferredRegions` 배열을 보내면 해당 항목을 미설정 상태로 저장한다.
- `preferredRegions`는 중복을 제거하고 순서를 보존하며, 4개 이상 또는 17개 광역시도 외 값은 422를 반환한다.

**Response 200** → `Profile`

---

### POST /me/profile/skip

프로필 설정 단계를 건너뛰고 온보딩을 완료 처리한다.

**Response 200**
```json
{
  "skipped": true,
  "onboardingCompleted": true
}
```

---

### GET /me/nickname-suggestion

서버가 랜덤 닉네임 후보를 생성해 반환.

**Response 200**
```json
{ "nickname": "여행하는두더지" }
```

---

### PATCH /me/nickname

닉네임 변경.

**Request**
```json
{ "nickname": "새닉네임" }
```

- `nickname`: 2~20자, `[가-힣a-zA-Z0-9_ ]`만 허용. 앞뒤 공백은 저장 전 제거하고, 내부 띄어쓰기는 보존한다.

**Response 200** → `User`

- 성공 시 `nicknameSetupCompleted=true` 로 전환되어 다음 로그인부터는 `/nickname-setup` 이 아니라 `/profile-setup` 또는 완료 상태로 진행된다.

**Errors**
- 409: 닉네임 이미 사용 중

---

### Removed contact and notification settings API

사용자 연락처 저장, OTP 인증, 사용자별 마감 알림 설정 API는 이번 pass에서 제거됐다. 해당 route는 더 이상 API contract에 포함되지 않으며 legacy client 요청은 등록된 route 부재로 실패한다.

`notification_deliveries` 테이블은 과거 발송 이력/운영 기록을 보존하기 위한 inert history로만 남는다. 알림 scheduler, dispatch, retry, webhook runtime은 비활성화/제거됐고 이 pass 이후 새 발송 row를 생성하지 않는다.

---

### GET /me/saved-policies

저장한 정책 목록. 응답 형식은 `Policy[]` (아래 정책 섹션 참조).

---

### GET /me/applied-policies

일정에 담긴(신청 연결된) 정책 목록. 응답 형식은 `Policy[]`.

---

### GET /me/applied-policy-links

내 일정에 담긴 정책을 정책 기준으로 묶어서 반환한다. 기존 `GET /me/applied-policies`는 카운트 및 단순 정책 목록 호환용으로 유지하고, 이 엔드포인트는 "정책 -> 연결된 일정들" 화면에 사용한다.

**Response 200** - `AppliedPolicyLink[]`

```json
[
  {
    "policy": { "...": "Policy DTO" },
    "linkedTrips": [
      {
        "id": "55",
        "title": "부산 주말 여행",
        "region": "부산",
        "startDate": "2026-06-12",
        "endDate": "2026-06-13"
      }
    ]
  }
]
```

---
### POST /me/saved-policies/{policy_slug}

정책 저장.

**Response 200**
```json
{ "policyId": "uuid", "saved": true }
```

**Errors**
- 404: 정책 없음

---

### DELETE /me/saved-policies/{policy_slug}

정책 저장 해제.

**Response 200**
```json
{ "policyId": "uuid", "saved": false }
```

**Errors**
- 404: 정책 없음

---

### GET /profile-options

프로필 설정 선택지 목록. 인증 불필요.

**Response 200**
```json
{
  "regions": ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"],
  "travelStyles": ["휴식", "맛집", "체험", "자연", "사진"],
  "budgets": ["1인 30만원 이하", "1인 40만원 이하", "1인 60만원 이하", "상관없음"]
}
```

---

## 추천 (`/api/recommendations`)

### GET /recommendations/regions

여행가는 달 등 공식 외부 수집 레코드(`external_source_records`)를 기반으로 지역/목적지 추천 목록을 반환한다. 인증 불필요.

**Query params**

| 이름 | 타입 | 설명 |
|------|------|------|
| style | string, optional | `휴식`, `맛집`, `체험`, `자연`, `사진` 같은 장소 취향. 점수 보정에만 사용하며 정책 점수 우선순위를 뒤집지 않는다. |
| region | string, optional | 요청자가 명시한 단일 목적지/관심 지역 tie-breaker. `preferredRegions`가 있으면 그 값이 우선한다. |
| preferredRegions | string[], optional | 반복 query param(`?preferredRegions=부산&preferredRegions=강원`)으로 전달하는 관심 지역 최대 3개. 제공되면 legacy `region`보다 우선하며 선택 지역별 추천 다양성을 보장한다. |
| limit | number, optional | 반환 개수. 기본 3, 1~10. |

**Ranking**

1. 신청 가능한 지역 혜택 수
2. 마감 임박 혜택 수
3. 명시 금액 혜택 가치
4. 취향 일치 수는 동점권 보조 점수로만 사용
5. 단일 프로필 지역 일치는 마지막 tie-breaker로만 사용
6. `preferredRegions`가 2~3개이면 선택 순서대로 각 지역 후보를 먼저 1개씩 확보한 뒤 남은 슬롯을 점수순으로 채운다. 1개이면 해당 지역을 점수 보정한다.

전국 혜택은 지역 후보가 `limit`보다 부족할 때만 fallback으로 포함한다.

**Response 200** — `RegionRecommendation[]`
```json
[
  {
    "region": "부산",
    "title": "부산이 지금 좋아요",
    "reason": "신청 가능한 지역 혜택 4개 · 마감 임박 2개 · 명시 혜택 최대 100,000원을 기준으로 추천합니다.",
    "policyCount": 4,
    "endingSoonCount": 2,
    "estimatedValueKrw": 100000,
    "score": 86,
    "styleMatchedCount": 1
  }
]
```

---

## 정책 (`/api/policies`)

### GET /policies

전체 정책 목록. 인증 불필요. DB `policies` 레코드만 `Policy` DTO로 반환한다. TravelMonth, 대한민국 반값여행 등 공식 외부 수집 레코드(`external_source_records`)는 수집/검증 원문 근거로 보존하고, `local_half_trip` 신청접수중/준비중 항목과 active/fresh `stay_discount` 항목만 collection normalization service가 `policies`로 승격한다. `regional_benefit`은 대한민국 반값여행과 같은 정책의 legacy 요약 source로 보고 public 정책 승격/추천/상세 fallback에서 제외하며, 기존 승격 정책은 `hidden`으로 내린다. `traffic_benefit`은 legacy/optional 수집 근거로 보존될 수 있지만 public 정책 승격 대상에서는 제외한다. `local_half_trip` 같은 지역별 외부 정책은 기존 호환 slug `travelmonth-{externalSourceRecordId}`를 사용한다. `stay_discount`는 공식 `https://ktostay.visitkorea.or.kr/`의 비수도권 인구감소지역 85개 지자체를 `raw_payload.eligibleAreas`에 저장하고, 목록/검색/지역 추천에서는 canonical `travelmonth-{externalSourceRecordId}` 1건을 숨긴 뒤 `stay-discount-{sidoSlug}-{citySlug}` 지역 alias 85건으로 투영한다. alias DTO는 제목을 `[고성] 2026 대한민국 숙박세일 페스타 숙박 할인`처럼 시/군 단위 접두어로 표시하고, `region`은 정책 목록 메타/필터가 반값여행 카드와 맞도록 광역자치단체(`강원`, `경남` 등)만 담는다. 숙박세일 상세/alias 응답의 `summary`, `amount`, `requirements`는 원문 반복 문구 대신 2만/3만/5만/7만원 할인 조건과 발급·입실 기간을 항목화한 정리본으로 반환한다. 저장/일정 연결 가능 상태이므로 `actionStatus`를 생략하거나 `null`로 둔다. 대한민국 반값여행 계열(`local_half_trip`)은 공식 페이지의 지역별 상태가 `신청접수중` 또는 `준비중`인 항목을 public 정책으로 노출하고, 제목은 `[합천] 대한민국 반값여행 지원`처럼 지자체명을 대괄호 접두어로 표시한다. 공식 디지털 관광주민증 seed 정책은 `docs/디지털관광주민증.xlsx`의 `지원내용`, `신청기간`, `확인 필요 사항`, `필요 서류` 값을 그대로 정책 본문으로 사용하고, KTO 공식 운영 지자체 목록(`https://korean.visitkorea.or.kr/dgtourcard/biz/main/main.do`)에 있는 지역만 `digital_tourism_card` 성격의 `dgtour-{city}-{n}` 별도 정책으로 유지한다. 제목은 `[지역명] 디지털 관광주민증 혜택` 형식으로 표시하고, 같은 지자체 반값여행 정책과 제목/요약/공식 URL을 섞지 않는다. `[강진]`처럼 지역 상세 페이지가 비었거나 공식 운영 지자체 목록에 없는 기존 dgtour 정책은 삭제하지 않고 `policies.status = "hidden"`으로 내려 public 목록/상세/저장 가능 대상에서 제외한다. `준비중` 항목은 원천 `freshness_status`가 `unknown`이어도 정책 목록/상세에 표시하며, 마감/unknown 상태 또는 stale 항목은 기존 연결 보호를 위해 `policies.status = "hidden"`으로 내려 사용자 목록에서 제외한다.

**Response 200** → `Policy[]`
```json
[
  {
    "id": "uuid",
    "slug": "dgtourcard-2026",
    "label": "🎫",
    "tag": "지역할인",
    "title": "디지털관광주민증",
    "org": "한국관광공사",
    "region": "전국",
    "deadline": "2026-12-31",
    "amount": "최대 30만원",
    "summary": "여행지 할인 혜택 제공",
    "match": 85,
    "category": "지역할인",
    "requirements": ["만 19세 이상", "국내 거주자"],
    "documents": ["신분증"],
    "structuredDetail": {
      "benefits": [{ "title": "혜택", "description": "최대 30만원", "amount": "최대 30만원" }],
      "conditions": [{ "title": "조건", "description": "만 19세 이상" }],
      "periods": [{ "title": "신청 기간", "description": "2026-01-01 ~ 2026-12-31", "startDate": "2026-01-01", "endDate": "2026-12-31" }],
      "links": [{ "label": "공식 안내", "url": "https://example.com/official" }],
      "documents": [{ "title": "필요 서류", "description": "신분증" }],
      "notices": []
    },
    "officialUrl": "https://example.com/official",
    "applyUrl": "https://example.com/apply",
    "sourceType": "internal",
    "actionStatus": null
  }
]
```

`category` 허용 값: `"교통" | "숙박" | "여행상품" | "지역할인" | "이벤트" | "기타"`
`sourceType` 허용 값은 `"internal" | "external"`이며 API 호환과 내부 진단을 위해 유지한다. 사용자 화면은 `internal/external` 같은 구현 구분 문구를 노출하지 않는다. 사용자에게 노출되는 모든 정책은 정규화된 `policies` 레코드이므로 저장/일정 연결 동작을 동일하게 지원한다.

`PolicyStructuredDetail` v1 섹션은 아래 여섯 배열만 표준으로 사용한다. 각 item은 화면 표시용 `title`/`label`, `description`/`value`, `amount`, `url`, `startDate`, `endDate` 같은 문자열 필드를 느슨하게 담을 수 있다. 빈 배열은 허용하며 frontend는 빈 섹션을 숨긴다. 외부 수집 정책 상세에서 `structuredDetail`은 primary screen-ready contract다. frontend는 비어 있지 않은 `structuredDetail` 섹션을 그대로 우선 렌더링하고, 해당 섹션이 비어 있거나 누락된 경우에만 `summary`/`requirements`/`documents`/기간 값으로 section-by-section fallback을 수행한다. `requirements`는 legacy/simple fallback 재료이며, `structuredDetail`이 제공한 섹션 항목을 다시 신청 대상/혜택 조건/필요 서류/확인 사항으로 의미 추론하거나 재분류하지 않는다.

```json
{
  "benefits": [],
  "conditions": [],
  "periods": [],
  "links": [],
  "documents": [],
  "notices": []
}
```

`actionStatus`는 생략 또는 `null`이면 저장/일정 연결 가능 상태로 간주한다. migration gap 동안 상세 조회만 허용되는 raw fallback 정책은 `"infoOnly"`를 반환하며, 프론트엔드는 저장/일정 연결 action을 차단하고 공식 원문 확인 안내만 제공한다.
`external_source_records.source_category` 중 정책 승격 대상은 `local_half_trip`, `stay_discount`이다. `local_half_trip`은 신청접수중과 준비중을 모두 공개 승격 대상으로 본다. `stay_discount`는 하나의 canonical 정책으로 저장/중복 방지하고, public 목록과 추천 후보에서만 eligible area alias로 확장한다. `regional_benefit`과 `traffic_benefit`은 legacy source evidence로 남기며 목적지/지역 추천 점수와 public 정책 승격에서 제외한다. 일정 상세 정책 추천은 정규화된 공개 정책 및 `stay_discount` alias 후보에 대해 지역/일정 날짜/카테고리/여행 스타일 태그만 사용하는 deterministic scoring을 적용한다.
외부 수집 정책의 `category`는 `external_source_records`의 제목, 혜택 본문, 태그, 출처 URL, source category를 점수화한 deterministic classifier 결과다. 단순 source URL/source category 매핑이 아니며, 동점이면 `교통 > 숙박 > 여행상품 > 이벤트 > 지역할인 > 기타` 우선순위를 따른다.

---

### GET /policies/{policy_slug}

정책 상세. `policies.status != "active"`인 정책은 기존 행을 보존하더라도 public 상세에서 404로 처리한다. `travelmonth-{externalSourceRecordId}` slug는 정규화된 TravelMonth 정책 상세로 해석한다. 기존 `dgtour-{city}-{n}` 상세 slug가 같은 지자체의 승격된 `local_half_trip` 정책과 중복되면 `307`로 최신 `/api/policies/travelmonth-{externalSourceRecordId}`에 리다이렉트해 구버전 상세 내용이 다시 노출되지 않게 한다. 단, 활성 `dgtour-*` 정책이 `digital_tourism_card`처럼 반값여행이 아닌 별도 공식 디지털 관광주민증 정책으로 정리되어 있으면 redirect하지 않고 `[지역명] 디지털 관광주민증 혜택` 상세를 반환한다. `stay-discount-{sidoSlug}-{citySlug}` slug는 숙박세일 canonical 정책 상세로 해석하되 응답의 `id`, `slug`는 요청 alias를 echo하고, `title`은 `[고성] ...` 지역 접두어 형식, `region`은 광역자치단체 단위로 반환하며, `summary`/`requirements`는 중복 원문 대신 결제 금액별 할인 조건과 발급·입실 기간을 항목화한다. 저장, 삭제, 일정 연결은 내부적으로 canonical `policies.id`를 사용해 중복 저장/중복 연결을 방지하고, mutation 응답의 `policyId`는 요청 alias를 echo한다. migration gap 동안 상세 조회만 기존 raw `external_source_records` fallback을 사용할 수 있지만, 목록/추천/저장/일정 연결 경로는 정규화된 `policies` 기준이다. raw fallback은 active/fresh `local_half_trip`, `stay_discount`만 허용하며, `regional_benefit`, `traffic_benefit`, non-active/non-fresh source는 상세 404와 동일하게 처리한다. `local_half_trip`의 지역별 상세 URL이 확인된 경우 `officialUrl`은 generic `tour50.do`보다 해당 지역 안내/신청 페이지를 우선하며, 제목은 `[합천] 대한민국 반값여행 지원`처럼 지자체명을 대괄호 접두어로 표시한다.

**Response 200** → `Policy`

**Errors**
- 404: 정책 없음

---

## 일정 (`/api/trips`)

모든 엔드포인트는 인증 필요.

`trip_id` route parameter는 `trips.id`를 문자열화한 numeric string이며 `^[1-9][0-9]*$` 형식만 지원한다. non-numeric handle은 404로 처리한다.

---

### GET /trips

내 일정 목록 (owner 또는 member).

**Response 200** → `Trip[]`
```json
[
  {
    "id": "1",
    "title": "제주 3일 여행",
    "status": "draft",
    "revision": 1,
    "dates": "2026-07-12 ~ 2026-07-14",
    "people": ["나", "친구"],
    "participantCount": 2,
    "expectedSaving": "최대 15만원",
    "linkedPolicies": [
      {
        "slug": "dgtourcard-2026",
        "title": "디지털관광주민증",
        "amount": "최대 30만원",
        "region": "전국"
      }
    ],
    "recommendedPolicies": [
      {
        "slug": "travelmonth-58",
        "title": "부산 공식 캐시백",
        "amount": "카드 결제 5% 캐시백",
        "region": "부산"
      }
    ],
    "days": {
      "1": [
        { "id": "1", "time": "10:00", "label": "공항 도착", "meta": "제주 국제공항" }
      ]
    },
    "currentUserRole": "owner"
  }
]
```

`status` 허용 값: `"draft" | "confirmed"`
`revision`은 일정 상세 장소 add/update/move/delete optimistic conflict 처리용 정수 버전이다. 장소 변경 성공 시 1씩 증가하며, 클라이언트는 마지막으로 조회한 `revision`을 `expectedRevision`으로 보내야 한다. stale revision이면 409 `Trip has changed. Refresh before saving.`을 반환한다.

Frontend behavior: `/trips` does not expose trip confirmation controls or draft/confirmed status badges. `/trips/{tripId}` keeps owner/editor editing controls available regardless of persisted `draft` or `confirmed` status. Viewer users remain read-only by role.
Frontend behavior: `/trips` participant UI uses `people.length` and `people` names from real owner/member data. It must not use legacy `participantCount` as the displayed actual participation count.
`currentUserRole` 허용 값: `"owner" | "editor" | "viewer"`

---

### POST /trips

일정 생성. 모든 필드 optional. 생성 경로는 Trip, owner 멤버십, Day bucket, 선택 정책 연결만 만든다. 새 일정의 `days` 값은 요청 기간만큼의 빈 배열로 초기화되며, `POST /api/trips`는 추천 코스 생성, `trip_places` 저장, `trip_recommendations` 저장을 수행하지 않는다. 장소/추천 저장은 상세 화면의 수동 장소 추가 또는 명시적인 추천 미리보기 저장 액션에서만 발생한다.

**Request**
```json
{
  "title": "제주 여행",
  "region": "제주",
  "style": "자연",
  "description": "제주 자연 중심 여행",
  "policySlug": "dgtourcard-2026",
  "durationDays": 3,
  "startDate": "2026-07-12",
  "endDate": "2026-07-14"
}
```

- `durationDays`: 2~7 범위
- `participantCount`: optional legacy/back-compat field. 1~10. Planned travel party size only; it is stored separately from real member/invite list `people`. The current `/trips/new` frontend does not ask for or send this value.
- `startDate`/`endDate`: 함께 제공하거나 모두 생략. 기간은 2~7일.

**Response 200** → `Trip`. 새로 생성된 응답의 `days`는 예를 들어 3일 일정이면 `{"1": [], "2": [], "3": []}`처럼 빈 Day 배열만 포함한다. `recommendedPolicies`는 일정 지역에 맞는 정책 추천일 수 있지만, `days` 안의 장소와 `GET /trips/{trip_id}/recommendations`의 saved summary를 create 시점에 seed하지 않는다.

---

### GET /trips/{trip_id}

일정 상세. owner 또는 member만 접근 가능.

**Response 200** → `Trip`

**Errors**
- 404: 일정 없음 또는 접근 권한 없음

---

### DELETE /trips/{trip_id}

일정 삭제. owner만 가능.

**Response 200**
```json
{ "tripId": "1", "deleted": true }
```

**Errors**
- 403: owner가 아님
- 404: 일정 없음

---

### PATCH /trips/{trip_id}/status

일정 상태 변경. owner/editor만 가능.

**Request**
```json
{ "status": "confirmed" }
```

`status` 허용 값: `"draft" | "confirmed"`

**Response 200** → `Trip`

**Errors**
- 403: viewer는 변경 불가
- 404: 일정 없음

---

### POST /trips/{trip_id}/policies/{policy_slug}

일정에 정책 연결. owner/editor만 가능.

**Response 200**
```json
{
  "tripId": "1",
  "policyId": "dgtour-밀양-1",
  "added": true
}
```

**Errors**
- 403: viewer는 추가 불가
- 404: 일정 또는 정책 없음

---

### DELETE /trips/{trip_id}/policies/{policy_slug}

일정에 연결된 정책을 해제. owner/editor만 가능.

**Response 200**
```json
{
  "tripId": "1",
  "policyId": "dgtour-밀양-1",
  "added": false
}
```

**Errors**
- 403: viewer는 해제 불가
- 404: 일정 또는 정책 없음

---

### POST /trips/{trip_id}/days/{day_number}/places

Kakao place candidate metadata can be preserved when adding a recommended place.

Optional request fields:
- `address`: string | null
- `latitude`: number | null
- `longitude`: number | null
- `category`: string | null
- `categoryCode`: string | null
- `placeUrl`: string | null
- `sourceProvider`: string | null
- `externalPlaceId`: string | null

일정 특정 day에 장소 추가. owner/editor만 가능.

**Request**
```json
{
  "expectedRevision": 1,
  "time": "10:30",
  "label": "함덕해수욕장",
  "meta": "제주시 조천읍"
}
```

- `expectedRevision`: 필수, 현재 `Trip.revision` 값. 불일치 시 409.
- `label`: 필수, 1~200자
- `time`: optional, `HH:MM` 형식 또는 빈 문자열
- `meta`: optional

**Response 200** → `Trip` (전체 일정 반환)

**Errors**
- 403: viewer는 추가 불가
- 404: 일정 없음 또는 day 없음
- 409: 다른 사용자가 먼저 장소를 변경해 revision 불일치

---

### PATCH /trips/{trip_id}/places/{place_id}

장소 정보 수정. owner/editor만 가능. 모든 필드 optional.

**Request**
```json
{
  "expectedRevision": 1,
  "time": "11:00",
  "label": "함덕해수욕장",
  "meta": "제주시 조천읍"
}
```

- `expectedRevision`: 필수, 현재 `Trip.revision` 값. 불일치 시 409.

**Response 200** → `Trip`

**Errors**
- 403: viewer는 수정 불가
- 404: 장소 없음
- 409: 다른 사용자가 먼저 장소를 변경해 revision 불일치

---

### PATCH /trips/{trip_id}/places/{place_id}/move

장소를 다른 day 또는 순서로 이동. owner/editor만 가능.

**Request**
```json
{
  "expectedRevision": 1,
  "dayNumber": 2,
  "position": 1
}
```

- `expectedRevision`: 필수, 현재 `Trip.revision` 값. 불일치 시 409.
- `dayNumber`: 1 이상
- `position`: 1 이상

**Response 200** → `Trip`

**Errors**
- 403: viewer는 이동 불가
- 404: 장소 또는 대상 day 없음
- 409: 다른 사용자가 먼저 장소를 변경해 revision 불일치

---

### DELETE /trips/{trip_id}/places/{place_id}

장소 삭제. owner/editor만 가능. `expectedRevision` query parameter가 필수이며 현재 `Trip.revision` 값과 일치해야 한다.

**Query**
- `expectedRevision`: number, 1 이상. 불일치 시 409.

**Response 200** → `Trip`

**Errors**
- 403: viewer는 삭제 불가
- 404: 장소 없음
- 409: 다른 사용자가 먼저 장소를 변경해 revision 불일치

---


---

### GET /trips/{trip_id}/place-search

Authenticated trip members (owner/editor/viewer) can search Kakao-registered places for selection in the trip detail add-place sheet. Saving a selected place still uses `POST /trips/{trip_id}/days/{day_number}/places` with `expectedRevision`; this endpoint does not mutate itinerary data.

**Query**
- `query`: string, 1-80 chars. Place name or address keyword.

**Response 200** → `PlaceSearchCandidate[]`
```json
[
  {
    "id": "kakao:12345",
    "label": "📍",
    "title": "성산일출봉",
    "meta": "관광명소 · 제주 서귀포시 성산읍",
    "categoryCode": "AT4",
    "categoryName": "관광명소",
    "phone": "064-000-0000",
    "address": "제주 서귀포시 성산읍",
    "latitude": 33.4581,
    "longitude": 126.9425,
    "placeUrl": "https://place.map.kakao.com/12345",
    "sourceProvider": "kakao",
    "externalPlaceId": "12345"
  }
]
```

**Errors**
- 401: 인증 필요
- 404: 일정 없음 또는 접근 권한 없음
- 422: `query` 누락/길이 위반

### GET /trips/{trip_id}/recommendations

Returns additional AI place candidates for the trip. The backend treats `(sourceProvider, externalPlaceId)` as the durable external identity, then applies a conservative same-provider `externalPlaceId` and normalized-title duplicate exclusion for existing MVP data. Kakao-backed candidates include official Kakao Local API map metadata when available; ratings/reviews are not exposed because the official API response does not provide those fields. When official Kakao data can supply enough non-duplicate places, the response targets at least 10 candidates with a useful mix of attractions, food, and stays; sparse categories are backfilled from other official candidates instead of creating synthetic places. New trip creation no longer seeds saved summaries. `sourceType="savedSummary"` is reserved for legacy rows or future explicit recommendation-persistence flows, not for fresh `POST /api/trips` results.

Additional `Recommendation` fields:
- `id`: string | null
- `categoryGroup`: `stay` | `food` | `attraction` | `other` | null
- `categoryCode`: string | null
- `categoryName`: string | null
- `phone`: string | null
- `address`: string | null
- `latitude`: number | null
- `longitude`: number | null
- `placeUrl`: string | null
- `suggestedDay`: number | null
- `aiReview`: string | null
- `sourceProvider`: string | null
- `externalPlaceId`: string | null
- `sourceType`: `freshCandidate` | `savedSummary` | null

AI 추천 장소 목록 조회.

**Response 200** → `Recommendation[]`
```json
[
  {
    "label": "🏖️",
    "title": "함덕해수욕장",
    "meta": "제주시 조천읍",
    "reason": "제주 북동부 대표 해수욕장으로 물이 맑습니다.",
    "categoryName": "관광명소 > 해수욕장",
    "phone": "064-000-0000",
    "sourceType": "freshCandidate"
  }
]
```

**Errors**
- 404: 일정 없음

---

### GET /trips/{trip_id}/invite

초대 링크 상태 조회. owner 또는 editor만 가능. viewer/editor 권한별 링크를 동시에 반환한다. 기존 active invite는 현재 저장된 role의 전용 링크로 보존되고, 반대 role 링크가 없으면 새 token을 만든다.

**Response 200** → `InviteLinksState`
```json
{
  "tripId": "1",
  "viewer": {
    "id": "uuid-viewer",
    "tripId": "1",
    "inviteToken": "<viewer-token>",
    "inviteUrl": "https://<domain>/invites/<viewer-token>/accept",
    "expiresAt": "2026-05-25T00:00:00",
    "createdAt": "2026-05-19T00:00:00",
    "acceptedAt": null,
    "invited": false,
    "copied": false,
    "role": "viewer",
    "alreadyMember": false
  },
  "editor": {
    "id": "uuid-editor",
    "tripId": "1",
    "inviteToken": "<editor-token>",
    "inviteUrl": "https://<domain>/invites/<editor-token>/accept",
    "expiresAt": "2026-05-25T00:00:00",
    "createdAt": "2026-05-19T00:00:00",
    "acceptedAt": null,
    "invited": false,
    "copied": false,
    "role": "editor",
    "alreadyMember": false
  }
}
```

**Errors**
- 404: 일정 없음

---

### POST /trips/{trip_id}/invite

선택한 role의 초대 링크 생성 또는 확인. owner 또는 editor만 가능. 같은 trip에서 viewer/editor 링크는 서로 다른 token이며, 다른 role의 기존 token/role을 덮어쓰지 않는다.

**Request** (optional)
```json
{ "role": "viewer" }
```

`role` 허용 값: `"viewer" | "editor"` (기본값: `"editor"`)

**Response 200** → `InviteState`

**Errors**
- 404: 일정 없음

---

### POST /trips/{trip_id}/invite/email

선택한 role의 전용 초대 링크를 생성/확인한 뒤 email로 전송. owner 또는 editor만 가능. email 본문에는 일정 상세를 포함하지 않고 “트래블헌터 일정 초대입니다 / 로그인 또는 회원가입 후 수락할 수 있습니다 / 초대가 만료됐으면 다시 요청하세요” 수준의 안전 안내와 초대 링크만 포함한다.

**Request**
```json
{
  "email": "friend@example.com",
  "role": "editor"
}
```

`role` 허용 값: `"viewer" | "editor"` (기본값: `"editor"`)

**Response 200**
```json
{
  "invite": {
    "id": "uuid",
    "tripId": "1",
    "inviteToken": "<token>",
    "inviteUrl": "https://<domain>/invites/<token>/accept",
    "expiresAt": "2026-05-25T00:00:00",
    "createdAt": "2026-05-19T00:00:00",
    "acceptedAt": null,
    "invited": true,
    "copied": false,
    "role": "editor",
    "alreadyMember": false
  },
  "deliveryStatus": "sent",
  "message": "Invite email sent."
}
```

`deliveryStatus` 허용 값:
- `"sent"`: SMTP 발송 성공
- `"notConfigured"`: SMTP 설정 없음. 초대 링크는 유효하므로 프론트는 링크 복사 fallback을 안내한다.
- `"failed"`: SMTP 발송 실패. 초대 링크는 유효하므로 프론트는 링크 복사 fallback을 안내한다.

**Errors**
- 403: owner/editor 아님
- 404: 일정 없음
- 422: email 또는 role 형식 오류

---

### POST /trips/{trip_id}/invites

`POST /trips/{trip_id}/invite`와 동일. 하위 호환용 alias.

---

## 초대 수락 (`/api/invites`)

### POST /invites/{invite_token}/accept

초대 링크로 일정에 참여. 인증 필요. 이미 참여 중인 사용자가 다시 수락하면 중복 멤버를 만들거나 기존 권한을 낮추지 않고 `alreadyMember: true`를 반환한다.
새 참여자 수락은 owner + accepted/authenticated members 기준 실제 참여자 10명까지 허용한다. 이미 참여 중인 사용자의 재수락은 10명 제한에 막히지 않는다.

**Response 200** → `InviteState`

**Errors**
- 404: 초대 토큰 없음 또는 만료
- 409: 실제 참여자 10명 초과 (`Trip participant limit reached`)

---

## 알림 runtime removed

알림 발송 runtime과 SOLAPI webhook route는 이번 pass에서 제거됐다. `notification_deliveries`는 과거 이력 확인용 inert history로만 유지하며, public/user API에는 연락처·OTP·알림 설정 route가 없다.

---

## 타입 참조

### User

| 필드 | 타입 | 설명 |
|------|------|------|
| id | string (UUID) | 사용자 ID |
| nickname | string | 닉네임 |
| email | string | 이메일 |
| role | string | 사용자 권한 (`user` 또는 `admin`) |
| hasPassword | boolean | 앱 비밀번호 보유 여부. OAuth-only/passwordless 계정은 `false` |
| preferredRegions | string[] \| null | 관심 지역 최대 3개. 미설정은 `null` |
| persona | string | 여행 유형 |
| savedAmount | number | 예상 절약 금액 |
| onboardingCompleted | boolean | 온보딩 완료 여부 |
| nicknameSetupCompleted | boolean | 닉네임 확인 단계 완료 여부 |
| socialAccounts | SocialAccount[] | 연결된 소셜 계정 |
| createdAt | string (ISO 8601) | 가입일 |
| updatedAt | string (ISO 8601) | 최종 수정일 |

### SocialAccount

| 필드 | 타입 | 설명 |
|------|------|------|
| provider | string | `"kakao"` 또는 `"google"` |
| providerNickname | string \| null | provider 닉네임 |
| connectedAt | string (ISO 8601) | 연결 일시 |

### Policy

| 필드 | 타입 | 설명 |
|------|------|------|
| id | string (UUID) | 정책 ID |
| slug | string | URL 식별자 |
| label | string | 이모지/아이콘 |
| tag | string | 표시 태그 |
| title | string | 정책명 |
| org | string | 주관 기관 |
| region | string | 적용 지역 |
| deadline | string | 마감일 |
| amount | string | 혜택 금액 표시 |
| summary | string | 요약 |
| match | number | 매칭 점수 (0~100) |
| category | string | `"교통" \| "숙박" \| "여행상품" \| "지역할인" \| "이벤트" \| "기타"` |
| requirements | string[] | 신청 조건 목록. `structuredDetail`이 없는 legacy/simple fallback 재료이며, 수집 정책 상세에서 `structuredDetail` 섹션이 비어 있지 않으면 frontend가 이 값을 다시 의미 추론해 같은 섹션을 재구성하지 않는다. |
| documents | string[] | 필요 서류 목록. `structuredDetail.documents`가 비어 있거나 없는 경우에만 문서 섹션 fallback으로 사용한다. |
| structuredDetail | PolicyStructuredDetail \| null | 사용자 정책 상세 화면용 구조화 JSON. 외부 수집 정책 상세의 primary screen-ready contract다. 섹션별로 비어 있지 않은 `benefits`, `conditions`, `periods`, `links`, `documents`, `notices`를 우선 렌더링하고, 해당 섹션이 비어 있거나 없는 경우에만 기존 `summary`/`requirements`/`documents`/기간 fallback을 사용한다. `links.url`은 `http://` 또는 `https://`만 public 화면에 노출한다. raw 수집 JSON이 아니다. |
| officialUrl | string \| null | 공식 안내 URL. 사용자 화면 CTA 라벨은 `혜택 안내 보기` |
| applyUrl | string \| null | 신청 URL |
| sourceType | string | `"internal"` \| `"external"`; 생략 시 internal로 간주 |
| actionStatus | string \| null | 생략/`null` 또는 `"infoOnly"`; `"infoOnly"`는 raw fallback 상세 전용이며 저장/일정 연결 불가 |

### Trip

| 필드 | 타입 | 설명 |
|------|------|------|
| id | string | 일정 ID |
| title | string | 일정 제목 |
| status | string | `"draft" \| "confirmed"` |
| revision | number | 장소 add/update/move/delete optimistic conflict 처리용 일정 버전. 변경 성공 시 1 증가 |
| dates | string | 날짜 표시 문자열 |
| people | string[] | 실제 참여자 닉네임 목록. owner와 수락된 member 표시 이름을 중복 제거해 제공한다. `/trips` 화면의 참여 인원 수 기준이다. |
| participantCount | number | Legacy planned travel party size, separate from real member/invite list `people`. 실제 참여자 수 표시 기준으로 사용하지 않는다. |
| expectedSaving | string | 예상 절약 금액 표시 |
| linkedPolicies | LinkedTripPolicy[] | 연결된 정책 목록 |
| recommendedPolicies | LinkedTripPolicy[] | 일정 지역에 맞춰 추천된 정규화 정책 및 공개 TravelMonth/반값여행/숙박세일 혜택 목록. 기본적으로 일정의 실제 시/군/구와 정책 지자체가 일치해야 하며, `서울 전체` 같은 광역 전체 여행만 해당 광역 내부 자치구 정책을 예외로 허용한다. 광역자치단체만 같은 정책은 추천하지 않는다. 숙박세일은 canonical 1건을 직접 추천하지 않고 `raw_payload.eligibleAreas`에서 파생한 지역 alias 후보만 추천한다. 이미 연결된 정규화 정책은 canonical id/slug 기준으로 제외하며 각 항목은 `/policies/{slug}` 상세로 이동 가능하다. 추천 순서는 지역, 일정 날짜 겹침, 정책 카테고리, 여행 스타일 텍스트/태그만 사용하며 AI/LLM 판단을 사용하지 않는다. |
| days | object | `{ [dayNumber]: ItineraryPlace[] }` |
| currentUserRole | string | `"owner" \| "editor" \| "viewer"` |


### LinkedTripPolicy

| ?? | ?? | ?? |
|------|------|------|
| slug | string | ?? ?? URL ??? |
| title | string | ??? |
| amount | string | ?? ?? ?? |
| region | string | ?? ?? |
| status | `"active" | "hidden"` | ?? ?? ?? ??? ?? ??. ?? ??? `active`? ????, ?? ?? ??? hidden?? ??? `hidden`?? ????. |

### ItineraryPlace

| 필드 | 타입 | 설명 |
|------|------|------|
| id | string \| null | 장소 ID |
| time | string | 시간 (`HH:MM` 또는 `""`) |
| label | string | 장소명 |
| meta | string | 부가 정보 |
| address | string \| null | 장소 주소 |
| latitude | number \| null | 위도 |
| longitude | number \| null | 경도 |
| category | string \| null | 장소 카테고리 이름 |
| categoryCode | string \| null | 장소 카테고리 코드 |
| placeUrl | string \| null | 장소 상세 URL |
| sourceProvider | string \| null | 외부 장소 제공자 식별자 |
| externalPlaceId | string \| null | 외부 장소 ID |

`externalPlaceId` is scoped by `sourceProvider`; the durable external identity is the pair `(sourceProvider, externalPlaceId)`.

---

### PlaceSearchCandidate

| 필드 | 타입 | 설명 |
|------|------|------|
| id | string \| null | 클라이언트 표시용 후보 ID |
| label | string | 후보 표시 아이콘/라벨 |
| title | string | Kakao 장소명 |
| meta | string | 카테고리/주소 기반 요약 |
| categoryCode | string \| null | Kakao 카테고리 그룹 코드 |
| categoryName | string \| null | Kakao 카테고리 이름 |
| phone | string \| null | 장소 전화번호 |
| address | string \| null | 장소 주소 |
| latitude | number \| null | 위도 |
| longitude | number \| null | 경도 |
| placeUrl | string \| null | Kakao 장소 상세 URL |
| sourceProvider | string \| null | `kakao` |
| externalPlaceId | string \| null | Kakao 장소 ID |

---

## 2026-05-26 Travel-area itinerary contract addendum

This addendum defines the AI itinerary travel-area contract. It preserves the existing `GET /api/recommendations/regions` endpoint as the policy-backed region ranking API.

### GET /recommendations/travel-areas

Returns travel-area candidates for the AI itinerary creation wizard.

Query params:

| name | type | description |
|---|---|---|
| `sido` | string, optional | Return travel areas inside a specific province/metropolitan city, for example `강원`. |
| `query` | string, optional | Search by travel-area name, sido, included city, alias, tag, or style. |
| `mode` | `nationwide`, optional | Return nationwide recommendations. If no query params are provided, this is the default behavior. |
| `style` | string, optional | User preference used as a ranking boost. |
| `limit` | number, optional | Default 6, minimum 1, maximum 20. |

Request priority:

```text
query > sido > mode=nationwide > default nationwide
```

When `query` and `sido` are both provided, `sido` limits the search scope. The static v1 travel-area catalog provides at least one broad candidate for every 17개 광역시도 (`서울`, `부산`, `대구`, `인천`, `광주`, `대전`, `울산`, `세종`, `경기`, `강원`, `충북`, `충남`, `전북`, `전남`, `경북`, `경남`, `제주`). If the requested city is not covered by the static catalog but is present in collected regional policy records, or `sido + query` names a future policy locality, the backend can synthesize a single-city travel area. Its `travelAreaId` uses `policy-region:{urlencoded-sido}:{urlencoded-city}` and should be treated as an opaque id by clients.

Response 200:

```json
{
  "mode": "sido",
  "sido": "강원",
  "query": null,
  "emptyReason": null,
  "items": [
    {
      "travelAreaId": "gangwon-sokcho-goseong-yangyang",
      "travelAreaName": "속초·고성·양양",
      "sido": "강원",
      "includedCities": ["속초", "고성", "양양"],
      "summary": "바다와 설악산, 감성 카페를 함께 즐기는 동해 북부 권역",
      "tags": ["바다", "산", "카페", "2박3일"],
      "reason": "강원 지역 혜택과 속초·고성·양양 여행 동선이 잘 맞아요.",
      "policyCount": 5,
      "localPolicyCount": 4,
      "nationwidePolicyCount": 1,
      "endingSoonCount": 1,
      "estimatedValueKrw": 120000,
      "score": 86
    }
  ]
}
```

`emptyReason` values:

| value | meaning |
|---|---|
| `unsupported_sido` | The requested `sido` is outside the supported 17개 광역시도 catalog. |
| `no_match` | The search query does not match any travel area. |
| `null` | Normal response. |

### POST /trips travel-area extension

`POST /api/trips` accepts optional `travelAreaId` in addition to legacy `region`.

Request example:

```json
{
  "title": "속초·고성·양양 3일 여행",
  "region": "속초·고성·양양",
  "travelAreaId": "gangwon-sokcho-goseong-yangyang",
  "style": "바다",
  "startDate": "2026-06-15",
  "endDate": "2026-06-17"
}
```

Rules:

| input | behavior |
|---|---|
| `travelAreaId` present and valid | Resolve backend travel-area catalog, including dynamic `policy-region:{urlencoded-sido}:{urlencoded-city}` ids, store `trips.travel_area_id`, and use the travel-area display name as `trips.region`. |
| `travelAreaId` present and invalid | Return 400 with `Travel area not found`. |
| `travelAreaId` absent and `region` present | Preserve legacy region-only trip creation behavior. |

Trip response includes:

```json
{
  "travelAreaId": "gangwon-sokcho-goseong-yangyang",
  "participantCount": 3
}
```

Existing trips can return `travelAreaId: null`.

## Admin user profile fields

- `GET /api/admin/users/{userId}` and `PATCH /api/admin/users/{userId}` expose the legacy admin `preferredRegions` field as a comma-separated `string | null` for the current admin UI.
- On update, `preferredRegions` is normalized with the same 17개 광역시도 allowlist and max-3 rule as the public profile API. Blank input clears the field to `null`; invalid or 4+ regions return 422.
- The public profile API continues to expose the same stored value as `preferredRegions: string[] | null`.

## Admin external source summary

- `GET /api/admin/external-sources/summary`
- Auth: bearer token required, admin role required.
- Purpose: read-only dashboard summary for external policy collection health. This endpoint never starts a collection job and does not expose source-specific manual controls.
- Response:
  - `items[]`
  - `items[].sourceCategory`
  - `items[].label`
  - `items[].sourceName`
  - `items[].totalRecords`
  - `items[].activeRecords`
  - `items[].scheduledRecords`
  - `items[].endedRecords`
  - `items[].unknownRecords`
  - `items[].freshRecords`
  - `items[].promotedPolicyCount`
  - `items[].activePromotedPolicyCount`
  - `items[].latestFetchedAt`
  - `items[].latestVerifiedAt`
  - `totalRecords`
  - `activeRecords`
  - `freshRecords`
  - `promotedPolicyCount`
  - `latestFetchedAt`

Admin policy list items additionally expose `sourceCategory` and `sourceLabel` for minimal source identification in `/admin/policies`. Public policy DTOs are unchanged.
