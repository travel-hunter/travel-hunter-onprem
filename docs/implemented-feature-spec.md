# Travel Hunter 구현 기능명세서

> Status: active implementation/status inventory.
> Use this document as the implemented-feature and conditional-scope inventory. For the current execution queue, use `docs/next-work-plan.md`; `docs/specs/spec-index.md` is only the local UX spec index.

## 기준

- 실행 모드: DB-backed-only.
- Runtime mock mode는 제거됐다.
- 이 문서는 현재 구현된 사용자 동작과 API/DB 연결을 기능명세 관점으로 정리한다.
- 제품 요구사항은 `docs/requirements.md`, 다음 작업 실행 큐는 `docs/next-work-plan.md`, API wire shape는 `docs/mvp-api-contract.md`를 따른다.

## 인증과 계정

| 기능 | 사용자 동작 | 연결 |
|---|---|---|
| 회원가입 | `/signup`에서 email과 필수 2종 약관(이용약관, 개인정보처리방침)을 확인한 뒤 인증 메일을 요청한다. `보기` 버튼은 하단 sheet/modal로 전문을 보여주며, 필수 체크가 없으면 프론트 제출과 백엔드 요청이 모두 차단된다. `/signup/verify?token=...` 링크를 열면 이메일 인증 완료 상태에서 비밀번호 입력창이 나타나고, 비밀번호 제출 시 계정이 생성되어 자동 로그인 후 온보딩으로 이어진다. 미완료 인증 재요청은 기존 pending signup을 교체하며, 동의 여부·시각·약관 버전을 pending signup과 최종 user에 저장한다. | `POST /api/auth/email-check`, `POST /api/auth/signup`, `POST /api/auth/signup/verify`, `POST /api/auth/signup/complete`, `pending_signups`, `users`, refresh cookie |
| 닉네임 설정 | `/nickname-setup`에서 자동 생성된 임시 닉네임을 수정하거나 주사위 버튼으로 새 추천 닉네임을 받아 저장한다. 소셜 신규 사용자는 provider 기본 닉네임이 있어도 이 단계를 먼저 완료해야 `/profile-setup`으로 진행한다. | `GET /api/me/nickname-suggestion`, `PATCH /api/me/nickname`, `users.nickname`, `users.nickname_setup_completed` |
| 로그인 | `/`와 `/login`에서 프로토타입과 같은 모바일 앱형 로그인 화면을 보여주고 email/password로 로그인한다. 실패 시 사용자용 오류를 표시한다. | `POST /api/auth/login`, `auth_refresh_tokens` |
| 세션 유지/로그아웃 | refresh cookie로 access token을 갱신하고, 로그아웃 시 refresh token을 revoke한다. | `POST /api/auth/refresh`, `POST /api/auth/logout` |
| 비밀번호 변경 | `/mypage`의 계정 보안 영역에서 앱 비밀번호 보유 계정만 현재 비밀번호와 새 비밀번호를 입력해 변경한다. 성공 시 사용자의 기존 refresh token을 revoke한다. OAuth-only/passwordless 계정은 `User.hasPassword=false`로 내려와 비밀번호 변경 대신 안내 문구를 표시하며, 이번 phase에서는 앱 비밀번호 설정 flow를 제공하지 않는다. | `User.hasPassword`, `POST /api/auth/password/change`, `auth_refresh_tokens` |
| 비밀번호 재설정 | `/forgot-password` 요청 후 email link로 `/reset-password?token=...`에서 새 비밀번호를 설정한다. 존재하지 않는 이메일, passwordless/OAuth-only 계정, 탈퇴 계정은 모두 열거 방지 응답만 반환하고 token을 만들지 않는다. 기존 `password_reset_tokens` row는 회원 탈퇴 시 삭제하지 않지만, 탈퇴 또는 passwordless user에 연결된 token confirm은 무효로 처리한다. | `password_reset_tokens`, SMTP 설정 필요 |
| 회원 탈퇴/재가입 | `/mypage`의 회원 탈퇴 영역에서 비밀번호 계정은 현재 비밀번호, OAuth-only/passwordless 계정은 확인 문구 `탈퇴합니다`를 요구한다. 성공 시 계정을 soft withdrawal 상태로 전환해 `withdrawn_at`과 HMAC `withdrawn_email_hash`를 저장하고, 이메일은 `withdrawn-{id}-{timestamp}@withdrawn.local`, 닉네임은 `탈퇴한 사용자 #<id>`로 익명화한다. 비밀번호 hash, 소셜 연결, profile preference, refresh token은 제거·revoke하되 저장 정책/일정/초대 등 관계 row와 password reset 이력은 보존한다. 이후 bearer/refresh/OAuth 연결은 active user 조회로 fail-closed 처리되며, 원래 이메일은 신규 계정으로 재가입할 수 있다. | `POST /api/auth/withdraw`, `users.withdrawn_at`, `users.withdrawn_email_hash`, `social_accounts`, `auth_refresh_tokens` |
| Kakao/Google OAuth | 로그인 버튼에서 provider authorization flow를 시작하고 callback에서 세션을 복구한다. 기존 소셜 계정 또는 검증된 동일 이메일 계정은 바로 로그인/연결된다. 신규 소셜 계정은 callback에서 즉시 user를 만들지 않고 `/signup/social-agreement` 대기 화면으로 이동해 확인된 provider/email 정보를 작게 보여준 뒤 필수 2종 약관 동의를 받아 계정을 생성한다. callback 실패는 닫힌 error code로 사용자용 메시지를 표시한다. Kakao는 `account_email`만 요청하며, 기존 `kakao_{providerId}@oauth.local` 내부 이메일 계정은 verified Kakao email을 받는 다음 로그인 때 충돌이 없으면 실제 email로 자동 교체한다. dev 도메인에서는 Google/Kakao 브라우저 로그인이 검증됐다. | `GET/POST /api/auth/oauth/pending-signup`, `pending_social_signups`, `social_accounts`, provider env 필요 |

## 사용자와 마이페이지

| 기능 | 사용자 동작 | 연결 |
|---|---|---|
| 프로필 설정 | `/profile-setup`에서 관심 지역, 스타일, 예산을 저장한다. 저장 성공 시 온보딩이 완료된다. `나중에 설정`을 누르면 profile 값 저장 없이 skip 상태를 기록하고 온보딩만 완료한다. | `PATCH /api/me/profile`, `POST /api/me/profile/skip`, `users.onboarding_completed`, `users.profile_setup_skipped` |
| 프로필 편집 | `/mypage`의 편집 sheet에서 profile 값을 수정한다. | `PATCH /api/me/profile` |
| 저장 정책 | `/mypage`에서 저장한 정책을 확인하고 삭제한다. | `GET/DELETE /api/me/saved-policies` |
| 신청 정책 통계 | `/mypage`에서 내 일정에 연결된 정책 수를 확인한다. | `GET /api/me/applied-policies`, `trip_policies` |
| 계정 보안 | `/mypage`에서 `User.hasPassword`에 따라 비밀번호 변경 form 또는 OAuth-only/passwordless 안내를 표시하고, 같은 API boundary에서 회원 탈퇴 요청을 보낸다. | `frontend/src/api/AppDataApi`, `POST /api/auth/password/change`, `POST /api/auth/withdraw` |

## 정책

| 기능 | 사용자 동작 | 연결 |
|---|---|---|
| 정책 목록/상세 | `/policies`에서 DB 정책과 대한민국 반값여행 신청접수중/준비중 및 active/fresh 숙박세일 페스타 혜택을 함께 보고 `/policies/:slug`에서 상세를 확인한다. `local_half_trip` 수집 혜택은 `sourceType="external"`과 `travelmonth-{externalSourceRecordId}` slug로 노출하고 제목은 `[합천] 대한민국 반값여행 지원`처럼 지자체명을 대괄호 접두어로 표시한다. 기존 `dgtour-{city}-{n}` seed는 공식 디지털 관광주민증 지역 혜택으로 분리해 `[지역명] 디지털 관광주민증 혜택` 형식으로 유지한다. 이 seed는 `docs/디지털관광주민증.xlsx`의 지원내용/신청기간/확인 필요 사항/필요 서류를 정책 본문으로 쓰고, KTO 공식 운영 지자체 목록에 없는 지역이나 혜택 안내가 비어 있는 기존 dgtour 정책은 행을 삭제하지 않고 `hidden`으로 내려 public 목록/상세에서 제외한다. 반값여행 레거시 URL만 같은 지자체의 최신 `travelmonth-*` 정책으로 리다이렉트해 구버전 반값여행 상세 화면 재노출을 막는다. 숙박세일 페스타는 canonical 정책 1건을 내부 저장/중복 방지 기준으로 두고 목록/검색/추천에는 비수도권 인구감소지역 85개 지자체별 `stay-discount-{sidoSlug}-{citySlug}` alias로 노출하되 제목은 `[고성] ...`처럼 시/군 접두어를 붙이고 목록 메타 `region`은 광역자치단체만 표시한다. 상세 표시용 `summary`/`requirements`는 원문 반복 대신 결제 금액별 2만/3만/5만/7만원 할인 조건과 발급·입실 기간으로 정리한다. alias 상세/저장/삭제/일정 연결 응답은 요청 alias를 echo하지만 DB 저장과 연결은 canonical `policies.id`로 처리한다. 사용자 화면에는 구현 구분 라벨을 표시하지 않고 공식 혜택으로 표현한다. raw 수집 레코드는 normalization 전까지 저장/일정 연결 action을 neutral 안내와 함께 임시 제한한다. | `GET /api/policies`, `GET /api/policies/{policySlug}` |
| 검색/필터 | 검색어, 지역, 카테고리를 client-side AND 조건으로 적용한다. 카테고리는 `교통`, `숙박`, `여행상품`, `지역할인`, `이벤트`, `기타` 혜택 유형이며 `travelStyles`와 분리한다. | frontend filtering |
| 정책 탐색 바로가기 | `/policies` 상단에서 매칭 높은 정책, 마감 임박 정책, 유형별 모아보기를 먼저 보여주고 `/home`에서도 마감 임박/추천 혜택 영역을 분리해 보여준다. 홈 `이번 주 인기 정책`은 정리된 카드 톤으로 보여주며, 홈 `이번 주 혜택`은 가로 스크롤 없이 추천도 높은 정책을 우선 배치하고 남은 슬롯은 마감 임박순으로 채운 상위 3개를 세로 카드 목록으로 표시한다. 카드에는 아이콘/카테고리, 정책명, 요약 1줄, 신청 마감/D-day, 신청 조건 칩 1개, 금액/마감 핵심 1줄을 보여준다. 공식/신청 버튼과 상세 조건 전체 문장은 카드 안에 표시하지 않는다. 홈 인기 국내 여행지 rail은 제거되어 해당 섹션 전용 지역 추천 API 호출/계산을 하지 않는다. AI 추천 맞춤 일정 카드는 관심 지역(`preferredRegions`)이 있을 때만 `GET /api/recommendations/regions`를 `AppDataApi` 경유로 호출해 지역 기반 새 일정 CTA(`/trips/new?region=...`)를 보여주고, 관심 지역이 없으면 기존 일정 목록의 첫 일정을 노출하지 않는 일반 새 일정 CTA(`/trips/new`)로 연결한다. | `GET /api/recommendations/regions`, frontend grouping |
| 조건 확인 요약/FAQ | 정책 상세에서 내 관심 지역과 정책 지역, 핵심 신청 조건, 필요 서류를 요약하고 정적 FAQ accordion을 제공한다. 확정 자격 판정은 하지 않는다. | `Policy.requirements`, `Policy.documents`, `Policy.region` |
| 저장/삭제 | 내부 `policies` 레코드는 정책 상세에서 저장하고 마이페이지에서 삭제한다. raw 수집 레코드는 normalization 전까지 저장 action을 임시 제한한다. | `user_saved_policies` |
| 공식/신청 URL | `applyUrl`은 `신청하러 가기`, `officialUrl`은 `혜택 안내 보기`, 둘 다 없으면 `신청 링크 준비 중`으로 구분한다. | `policies.apply_url`, `policies.official_url` |
| 공유 | Web Share API, clipboard, legacy copy 순서로 현재 정책 URL을 공유한다. | frontend utility |
| 일정 담기 | 내부 `policies` 레코드는 정책 상세 sheet에서 일정을 선택해 정책을 담는다. raw 수집 레코드는 normalization 전까지 일정 연결 action을 임시 제한한다. | `POST /api/trips/{tripId}/policies/{policySlug}` |
| 혜택 패키지 요약 | 정책 상세에서 대표 지원, 교통 혜택 후보, 지역 할인 후보를 한 화면에 묶어 보여준다. 확정 자격 판정이 아니라 공식 확인 전 안내 UI로 제공한다. | frontend display |

## 일정

| 기능 | 사용자 동작 | 연결 |
|---|---|---|
| 일정 목록/생성 | `/trips`에서 목록을 보고 `/trips/new`에서 지역, 제목, 기간, 스타일로 일정을 만든다. `/trips` 카드의 참여 정보는 생성 시 계획 인원이 아니라 실제 owner/member 표시 이름(`Trip.people`) 기준으로 아바타 최대 3개, `n명 참여 중`, 닉네임 축약 문구를 보여준다. `/trips/new`는 여행 인원을 묻지 않으며 생성 payload에도 `participantCount`를 보내지 않는다. `/home`의 추천 지역 링크가 넘긴 `/trips/new?region=...` 값은 새 일정 생성 지역으로 유지된다. 여행 지역 1단계는 17개 광역시도 버튼(`서울`, `부산`, `대구`, `인천`, `광주`, `대전`, `울산`, `세종`, `경기`, `강원`, `충북`, `충남`, `전북`, `전남`, `경북`, `경남`, `제주`)을 모두 제공해야 하며, backend travel-area 추천도 동일 17개 catalog를 broad fallback으로 지원한다. 정책 상세에서 `policySlug`만 들고 새 일정으로 진입하면 정책 제목의 `[지역명]`과 광역 `region`을 기준으로 세부 지역을 자동 조회·선택하며, 정적 여행권역에 없는 정책 지자체는 `policy-region:{sido}:{city}` 동적 단일 지역 카드로 표시해 선택된 `travelAreaId`를 일정 생성 payload에 포함한다. 생성 성공 직후 상세의 Day bucket은 비어 있으며, 장소/추천 저장은 수동 장소 추가 또는 상세의 추천 미리보기 저장 액션에서만 발생한다. | `GET /api/recommendations/travel-areas`, `GET/POST /api/trips` |
| 일정 확정 저장 | `/trips` 카드에서 draft 일정을 확정 선택 후 저장해 DB 상태를 `confirmed`로 바꾼다. | `trips.status`, `PATCH /api/trips/{tripId}/status` |
| 생성 draft autosave | `/trips/new`의 지역, 스타일, 기간, policySlug draft를 24시간 localStorage에 저장한다. 생성 성공 시 삭제한다. | `frontend/src/utils/draftStorage.ts` |
| 상세/삭제 | `/trips/:id`에서 상세를 보고 owner는 목록에서 일정을 삭제한다. 일정 상세는 정책 맥락, 장소 추가/추천 일정 만들기 CTA, Day 탭, 지도, 저장된 일정 리스트 순서의 map-first 화면이다. `/ai-results?tripId=...`는 `/trips/{tripId}?mode=recommend`로 대체 이동하는 호환 진입점이다. 추천 정책 카드는 `recommendedPolicies`를 사용해 정규화된 정책과 TravelMonth/반값여행/숙박세일 혜택 상세 페이지로 연결하며 지역, 날짜 겹침, 카테고리, 스타일 텍스트만으로 deterministic ranking한다. | `GET/DELETE /api/trips/{tripId}`, `Trip.recommendedPolicies` |
| 장소 추가/수정/삭제/이동 | owner/editor는 Kakao-backed 장소 검색 후보를 선택해 장소를 추가하고, 저장된 장소를 수정/삭제하며 드래그앤드롭으로 같은 Day 순서 변경 또는 다른 Day 이동을 수행한다. 장소명 직접 입력은 추가 flow에서 제거되며 선택 후보가 label/주소/좌표/Kakao URL을 제공한다. 각 장소 변경은 `Trip.revision`/`expectedRevision` optimistic conflict 처리를 거치며 stale 저장은 409 후 최신 일정을 다시 불러오고 draft를 유지한다. viewer는 상세 CTA를 볼 수 있지만 저장 시도는 권한 안내로 막힌다. | `GET /api/trips/{tripId}/place-search`, trip_places CRUD/move endpoints, `trips.revision` |
| 장소 추가 draft autosave | 장소 추가 sheet의 시간, 선택된 장소 후보, 메모, dayNumber draft를 24시간 localStorage에 저장한다. 저장 성공 또는 닫기 시 삭제한다. | `frontend/src/utils/draftStorage.ts` |
| 장소 수정 draft autosave | 장소 수정 sheet의 시간, 장소명, 메모 draft를 `placeId` 기준으로 24시간 localStorage에 저장한다. 저장 성공, 닫기, 장소 삭제 시 삭제한다. | `frontend/src/utils/draftStorage.ts` |
| Draft 복원 안내/폐기 | `/trips/new`와 장소 sheet에서 유효 draft를 불러오면 안내를 표시하고 사용자가 임시 저장 내용을 버릴 수 있다. | frontend localStorage UX |
| 정책 연결 | 정규화된 정책 상세에서 선택한 정책을 일정에 연결한다. `travelmonth-{id}` TravelMonth 혜택은 새 일정 생성 참고 컨텍스트로만 쓰고 normalization 전 `trip_policies` 연결 요청에는 보내지 않는다. | `trip_policies`, frontend policy context |

## AI 추천

| 기능 | 사용자 동작 | 연결 |
|---|---|---|
| 추천 조회 | `/trips/:tripId`에서 추천 일정 만들기를 눌러 저장 전 미리보기를 본다. 새 후보는 `sourceType="freshCandidate"`로 내려오며, `sourceType="savedSummary"`는 새 일정 생성이 아니라 legacy 데이터 또는 향후 명시적 추천 저장 계약에서만 쓰는 fallback이다. 미리보기는 명시적으로 `이 일정으로 저장`을 누르기 전까지 장소 API를 호출하지 않는다. | `GET /api/trips/{tripId}/recommendations` |
| 추천 항목 추가 | 추천 미리보기 저장은 사용자에게 한 번의 저장 액션으로 보이지만 내부적으로 기존 단일 장소 추가 API를 순차 호출한다. 저장된 장소가 이미 있으면 대체 확인 후 기존 장소 삭제와 추가를 순차 처리한다. | `GET /api/trips/{tripId}`, `POST /api/trips/{tripId}/days/{dayNumber}/places`, `DELETE /api/trips/{tripId}/places/{placeId}` |
| 추천 기준 설명 | 추천 기준 아이콘으로 설명 sheet를 연다. | frontend sheet |

## 초대와 협업

| 기능 | 사용자 동작 | 연결 |
|---|---|---|
| 초대 링크/email 생성 | `/friend-invite?tripId=...`에서 owner/editor가 viewer/editor 권한별 링크 카드를 확인하고, 각 권한 전용 링크를 복사하거나 email 초대를 보낸다. viewer/editor는 서로 다른 token/URL을 쓰며 이미 공유한 링크의 role은 다른 권한 링크 생성으로 바뀌지 않는다. 백엔드가 반환하는 `inviteUrl`은 `TRAVEL_HUNTER_PUBLIC_BASE_URL` 기준 `/invites/{token}/accept` 공개 수락 경로를 사용하며, email 본문에는 일정 상세를 담지 않는다. SMTP 미설정/실패 시 해당 권한 링크 복사 fallback을 안내한다. | `trip_invites.role`, `TRAVEL_HUNTER_PUBLIC_BASE_URL`, SMTP env |
| 초대 수락 | `/invites/:token/accept`로 진입해 로그인 후 초대를 수락한다. 비로그인 사용자는 로그인/가입 후 redirect로 원래 초대 링크에 복귀하고, 만료/오류 상태는 새 초대 링크 요청 안내를 표시한다. 새 참여자는 owner + 수락된 member 기준 실제 참여자 10명까지만 추가하며, 기존 참여자의 재수락은 멤버 중복 생성 없이 허용한다. | `trip_invites.accepted_at`, `trip_members` |
| 권한 적용 | owner/editor만 장소를 편집하고 viewer는 읽기 전용으로 본다. | trip service authorization |
| 상세 작업흐름 | 링크 기반 초대, 로그인/가입 후 수락, 중복 수락, 상세 일정 편집 권한, 장소 저장 충돌, email 초대와 예외 흐름은 별도 workflow spec을 따른다. | `docs/specs/invite-trip-edit-workflow.md` |

## 알림

마감 알림 연락처, 사용자별 알림 설정, OTP 인증, scheduler/dispatch/retry/webhook runtime은 현재 구현 범위에서 제거됐다. `notification_deliveries`는 과거 발송 이력/운영 기록을 확인하기 위한 inert history로만 유지하며, 새 알림 발송 row를 생성하지 않는다.

## 플랫폼과 배포

| 기능 | 설명 |
|---|---|
| 공통 상태 UX | `/policies`, `/trips`, `/mypage`의 loading/empty/error 상태는 공통 상태 패널과 다음 행동 CTA를 사용한다. |
| 프로토타입 기반 앱 UX | 업로드 HTML 프로토타입의 모바일 앱형 흐름을 현재 React 화면에 반영했다. `/` 랜딩은 제거하고 프로토타입 로그인 첫 화면을 실제 auth flow와 연결했다. 홈 대표 혜택 hero, 정책 카드/태그, 정책 상세 혜택 패키지, 일정 상세 혜택 묶음, 공통 배경/카드 톤을 정리하되 실제 DB-backed 기능은 유지한다. |
| PWA manifest/meta | 앱 이름, theme color, Apple mobile meta, 192/512/maskable icon을 제공한다. Service worker는 아직 추가하지 않는다. |
| Production sourcemap | Vite production sourcemap은 명시적으로 비활성화되어 있다. |
| 로컬 개발 런타임 | Docker `db/backend`와 Vite dev server 기준 실행 절차를 문서화했다. |
| Cloudflare Tunnel 배포 | `docs/deployment-cicd/`에 GitHub, Docker, Jenkins 계획, release checklist 기준을 모았다. |
| 정책 수집 운영 상태/수동 실행 | 관리자 인증된 `/api/ops/external-collection`과 `/api/ops/external-collection/quality`가 scheduler 상태, 수집 품질 count, 추천 preview를 제공한다. public 수집 source는 대한민국 반값여행(`local_half_trip`)과 숙박세일 페스타(`stay_discount`)이며, 여행가는 달 지역/교통 혜택 source는 중복/legacy evidence로만 보존한다. `/api/ops/external-collection/run`은 관리자가 공식 source 수집을 1회 실행하고 per-source 성공/실패를 반환한다. 관리자 대시보드에서는 외부 정책 수집 상태와 수동 실행 버튼을 제공한다. RC gate는 `totalRecords >= minParsedCount`, `freshRecords > 0`, `activeRecords > 0`, 최신 수집/검증 timestamp 존재, 정규화 정책의 list/detail 노출, stale 숨김으로 검증한다. | `GET /api/ops/external-collection`, `POST /api/ops/external-collection/run`, `GET /api/ops/external-collection/quality`, `GET /api/admin/external-sources/summary` |

## 조건부 기능과 미구현 범위

- SMTP env와 public base URL이 있어야 password reset email smoke를 완료할 수 있다.
- dev 도메인 `dev.travel-hunter.co.kr`에서는 Kakao/Google provider secret과 public redirect URI 기반 브라우저 OAuth smoke가 완료됐다. 운영 도메인 `travel-hunter.co.kr`에서는 별도 provider redirect URI, runtime env, public smoke 증거가 필요하다.
- 회원 탈퇴는 soft withdrawal과 동일 이메일 재가입까지 구현돼 있지만, 운영 privacy/legal 문구와 hard-delete retention 정책은 별도 제품/법무 결정이 필요하다.
- 정책 수집/정규화/노출의 local code path와 release-gate test는 존재하지만, Public v1/RC 판정에는 public domain/runtime smoke 증거가 추가로 필요하다.
- 실제 AI 엔진, SMTP readiness 이후 친구 초대 email 발송, 운영 관리자 화면, 정책 수집 source 확대와 full automation은 후속 범위다.
- 지도/장소 검색의 로컬 기본 UX는 일정 상세 지도, 장소 상세 dialog, 장소 추가 sheet 후보 검색, Kakao Local 후보, catalog fallback 기준으로 구현되어 있다. Public map-domain 검증과 추천 품질 고도화는 별도 개선 범위다.
