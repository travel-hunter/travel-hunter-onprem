# 친구 초대와 일정 상세 수정 작업흐름 명세

> Status: active local UX workflow spec.
> Scope: 현재 구현된 링크 기반 친구 초대와 일정 상세 편집 흐름을 현실적인 사용자 작업 순서로 설명하고, 가까운 다음 개선 후보인 email 초대 발송 흐름을 별도 future-ready 범위로 정의한다.
> Authority: API wire shape는 `docs/mvp-api-contract.md`, 구현 상태 요약은 `docs/implemented-feature-spec.md`, 릴리즈 우선순위는 `docs/next-work-plan.md`를 따른다.

## 1. 목적

이 문서는 개발자와 QA가 친구 초대 및 일정 상세 수정 기능을 같은 방식으로 이해하고 smoke test할 수 있도록, 사용자가 실제로 누르는 버튼과 그 뒤의 인증/권한/API 흐름을 구체적으로 고정한다.

핵심 질문은 다음이다.

- 초대한 사람은 어디서 어떤 권한을 선택하고 어떤 링크를 공유하는가?
- 초대받은 사람은 링크를 열었을 때 로그인/가입 상태에 따라 어떤 화면을 거치는가?
- 초대 수락 후 viewer/editor 권한이 일정 상세 수정 가능 여부에 어떻게 반영되는가?
- 가까운 다음 개선인 email 초대 발송은 기존 링크 초대 흐름 위에 어떤 UI/API/예외 상태로 붙어야 하는가?

## 2. 범위

### 2.1 현재 구현 범위

- 일정 owner/editor가 `/friend-invite?tripId={tripId}`에서 viewer/editor 권한을 선택한다.
- owner/editor가 초대 링크를 활성화하고 복사/공유한다.
- 초대 URL은 공개 수락 경로 `/invites/{token}/accept`를 사용한다.
- 초대 수신자는 링크로 진입한다.
- 비로그인 수신자는 로그인 또는 회원가입 후 원래 초대 링크로 돌아와 수락한다.
- 로그인 수신자는 바로 초대 수락을 시도한다.
- 수락 성공 시 `trip_members.role`에 viewer/editor 권한이 반영되고 일정 상세로 이동한다.
- owner/editor는 일정 상세에서 장소 추가/수정/삭제/이동이 가능하다.
- viewer는 일정 상세를 볼 수 있지만 장소 편집은 할 수 없다.

### 2.2 가까운 다음 개선 범위

- SMTP/Brevo readiness 이후 친구 초대 email 발송을 링크 초대의 보조 전송 수단으로 추가한다.
- email 초대는 새 권한 모델이 아니라 기존 `trip_invites` 토큰/role/public accept URL을 전달하는 전송 채널이다.
- email 발송 실패는 초대 링크 생성 자체를 취소하지 않는다. 사용자는 링크 복사로 fallback할 수 있어야 한다.

### 2.3 명시적 제외 범위

다음은 이 명세의 첫 구현/검증 범위와 현재 제품 범위에서 제외한다.

- SMS 초대 발송.
- Kakao 메시지 초대 발송.
- 초대받은 사람의 권한 재승급/강등 UI.
- 로그인 전 일정 제목/여행 지역/초대한 사람 이름 등 일정 미리보기 노출.
- 운영 관리자 초대 관리 화면.

## 3. 역할과 권한

| 역할 | 진입 조건 | 가능한 행동 | 제한 |
| --- | --- | --- | --- |
| Guest | 로그인하지 않은 사용자 | 초대 링크 진입, 로그인/회원가입으로 이동, 비밀번호 재설정/OAuth 시작 | 초대 수락 API 호출, 일정 상세 조회, 장소 편집 불가 |
| Member | 로그인한 일반 사용자 | 본인 일정 생성, 초대 링크 수락, 참여한 일정 열람 | 참여하지 않은 일정 상세 접근 불가 |
| Trip Owner | 일정을 생성한 사용자 | 초대 링크 생성/role 설정, 일정 삭제, 장소 추가/수정/삭제/이동, 정책 연결/해제 | 본 명세에서는 owner 권한 양도 없음 |
| Trip Editor | editor 초대를 수락한 멤버 | 일정 상세 열람, 장소 추가/수정/삭제/이동, 정책 연결/해제 | 초대 링크 생성/role 설정, 일정 삭제 불가 |
| Trip Viewer | viewer 초대를 수락한 멤버 | 일정 상세 열람 | 장소 추가/수정/삭제/이동, 정책 연결/해제 불가 |

권한 원칙:

- `owner`와 `editor`는 일정 상세에서 편집 컨트롤을 사용할 수 있다.
- `viewer`는 편집 컨트롤을 보지 않거나 읽기 전용 안내를 본다. viewer가 API를 직접 호출해도 서버는 403으로 막아야 한다.
- 이미 더 높은 권한을 가진 멤버가 더 낮은 권한의 초대 링크를 다시 눌러도 기존 권한을 낮추지 않는다.

## 4. 현재 구현: 링크 기반 친구 초대 흐름

### 4.1 초대 화면으로 이동

1. owner/editor가 로그인한다.
2. owner/editor가 `/trips` 또는 홈/마이페이지의 일정 진입점에서 본인 일정을 연다.
3. owner/editor가 일정 상세 `/trips/{tripId}`에서 친구 초대 CTA를 누른다.
   - 예시 버튼 문구: `친구 초대`, `같이 일정 보기`, `초대 링크 만들기`.
4. 프론트엔드는 `/friend-invite?tripId={tripId}`로 이동한다.
5. 화면 진입 시 프론트엔드는 `AppDataApi`를 통해 현재 초대 상태를 조회한다.
   - API: `GET /api/trips/{tripId}/invite`
   - 성공 조건: 로그인 사용자이며 해당 일정의 owner/editor member.
   - 실패 조건:
     - 미로그인: 로그인 화면으로 이동.
     - owner/editor 아님: 권한 없음 안내.
     - 일정 없음 또는 접근 불가: not found/접근 불가 안내.

### 4.2 초대 권한을 선택한다

1. 초대 화면은 권한 선택 UI를 보여준다.
2. 기본 권장값은 `editor`이다. 단, 화면 copy는 권한 차이를 명확히 설명한다.

권한 선택 copy 예시:

- `함께 편집 가능`: 초대받은 사람이 장소를 추가, 수정, 삭제, 이동할 수 있다.
- `보기만 가능`: 초대받은 사람이 일정은 볼 수 있지만 장소를 편집할 수 없다.

주의 copy:

- `초대 링크를 받은 사람은 로그인 또는 회원가입 후 일정에 참여할 수 있어요.`
- `링크를 아는 사람이 접근할 수 있으니 신뢰하는 사람에게만 공유하세요.`
- `현재는 링크 공유 방식이며 email/SMS/Kakao 발송은 지원하지 않아요.`

### 4.3 초대 링크를 활성화한다

1. owner/editor가 `/friend-invite?tripId={tripId}`에 진입하면 프론트엔드는 권한별 링크 상태를 조회한다.
   - API: `GET /api/trips/{tripId}/invite`
   - Response: `{ "tripId": "...", "viewer": InviteState, "editor": InviteState }`
2. 화면은 `보기만 가능`과 `함께 편집` 링크 카드를 분리해 보여준다. 두 카드의 URL/token은 달라야 한다.
3. owner/editor가 특정 카드에서 `링크 만들기` 또는 `링크 준비` 버튼을 누르면 프론트엔드는 해당 role을 전송한다.
   - API: `POST /api/trips/{tripId}/invite`
   - Request: `{ "role": "viewer" }` 또는 `{ "role": "editor" }`
4. 백엔드는 다음을 수행한다.
   - 요청자가 owner/editor인지 확인한다.
   - role이 `viewer` 또는 `editor`인지 검증한다.
   - 같은 role의 active invite가 있으면 그 token을 그대로 반환한다.
   - 다른 role의 active invite는 절대 role을 갱신하거나 token을 재사용하지 않는다.
   - 같은 role의 active invite가 없으면 `trip_invites`에 새 token과 role을 저장한다.
   - `TRAVEL_HUNTER_PUBLIC_BASE_URL` 기준 `inviteUrl`을 만든다.
5. 프론트엔드는 role 카드별 `inviteUrl`을 화면에 표시한다.
   - URL 형태: `https://<domain>/invites/{token}/accept`
6. owner/editor는 각 role 카드의 `링크 복사` 또는 OS 공유 기능을 사용해 외부 메신저에 직접 붙여넣는다.

성공 상태 copy 예시:

- `초대 링크가 준비됐어요.`
- `이 링크를 받은 사람은 로그인 또는 회원가입 후 일정에 참여합니다.`
- `선택된 권한: 함께 편집 가능` 또는 `선택된 권한: 보기만 가능`.

실패 상태:

| 실패 | 사용자 안내 | 회복 행동 |
| --- | --- | --- |
| 401 미로그인 | `로그인이 필요해요.` | 로그인 후 원래 초대 화면으로 복귀 |
| 403 owner/editor 아님 | `초대 링크는 일정 owner/editor 멤버만 만들 수 있어요.` | 일정 상세로 돌아가기 |
| 404 일정 없음 | `일정을 찾을 수 없어요.` | 일정 목록으로 이동 |
| 네트워크 오류 | `초대 링크를 만들지 못했어요. 잠시 후 다시 시도해 주세요.` | 재시도 버튼 제공 |

### 4.4 다른 권한 링크를 만든다

1. owner/editor가 같은 초대 화면에서 반대 role 카드의 링크를 만든다.
2. 프론트엔드는 `POST /api/trips/{tripId}/invite`로 해당 role을 전송한다.
3. 백엔드는 기존에 공유된 다른 role 링크를 변경하지 않고, 요청 role의 active invite만 반환하거나 새 token을 발급한다.
4. 이후 새로 수락하는 사용자는 본인이 연 token에 고정된 role을 받는다.
5. 이미 수락해 `trip_members`에 들어간 사용자의 기존 role은 이 동작만으로 자동 변경하지 않는다.

## 5. 현재 구현: 초대받은 사람의 수락 흐름

### 5.1 비로그인 사용자가 링크를 연다

1. 초대받은 사람이 메신저 등에서 `https://<domain>/invites/{token}/accept` 링크를 누른다.
2. 프론트엔드는 `/invites/{token}/accept` 화면을 연다.
3. 현재 세션이 없으면 일정 상세 내용은 보여주지 않는다.
4. 화면은 보안상 최소 안내만 표시한다.

비로그인 초대 화면 copy 기준:

- `트래블헌터 일정 초대입니다.`
- `로그인 또는 회원가입 후 초대를 수락할 수 있습니다.`
- `초대가 만료됐거나 사용할 수 없다면 초대한 사람에게 새 링크를 요청하세요.`

이 화면에서 보여주지 않는 것:

- 일정 제목.
- 여행 지역.
- 여행 날짜.
- 초대한 사람 이름.
- 기존 참여자 목록.
- 장소 목록.
- 연결된 정책.

5. 화면은 두 가지 주요 CTA를 제공한다.
   - `로그인하고 초대 수락하기`
   - `회원가입하고 초대 수락하기`
6. 사용자가 로그인 CTA를 누르면 `/login?redirect=/invites/{token}/accept`로 이동한다.
7. 사용자가 회원가입 CTA를 누르면 `/signup?redirect=/invites/{token}/accept`로 이동한다.

### 5.2 기존 계정으로 로그인 후 수락

1. 사용자가 `/login?redirect=/invites/{token}/accept`에서 email/password 또는 OAuth로 로그인한다.
2. 로그인 성공 후 프론트엔드는 redirect 값을 보존해 `/invites/{token}/accept`로 돌아간다.
3. 이제 인증된 상태이므로 프론트엔드는 초대 수락 API를 호출한다.
   - API: `POST /api/invites/{token}/accept`
4. 백엔드는 다음을 수행한다.
   - token 존재 여부와 만료 여부를 확인한다.
   - 로그인 사용자를 확인한다.
   - 사용자가 이미 일정 owner/member인지 확인한다.
   - 신규 멤버라면 `trip_members`에 초대 role을 저장한다.
   - 이미 멤버라면 중복 에러로 막지 않고 기존 멤버십을 유지한다.
5. 성공 시 화면은 수락 완료 상태를 보여주고 일정 상세로 이동할 수 있게 한다.

성공 copy 예시:

- `초대를 수락했어요.`
- `이제 일정 상세를 확인할 수 있습니다.`
- CTA: `일정 보러 가기` → `/trips/{tripId}`

### 5.3 신규 가입 후 수락

1. 사용자가 `/signup?redirect=/invites/{token}/accept`에서 email/password 가입을 시작한다.
2. 사용자는 email 중복 확인을 한다.
3. 가입이 성공하면 인증 세션이 생성된다.
4. 닉네임 설정 또는 프로필 설정이 필수인 경우에도 redirect 목적지는 유지되어야 한다.
   - 예: 가입 → 닉네임 설정 → 프로필 설정 → `/invites/{token}/accept` 복귀.
5. `/invites/{token}/accept`로 돌아오면 인증된 상태에서 수락 API를 호출한다.
6. 수락 성공 후 `/trips/{tripId}`로 이동한다.
7. 수락된 role이 `editor`이면 일정 상세에서 장소 편집 CTA가 보인다.
8. 수락된 role이 `viewer`이면 일정 상세는 읽기 전용이다.

가입 경로에서 중요한 UX 조건:

- 사용자가 가입 중 뒤로 가거나 새로고침해도 redirect가 사라지지 않아야 한다.
- email 중복 확인 실패는 초대 실패와 구분해서 보여준다.
- 가입 완료 후 초대 token이 만료됐으면 “가입은 완료됐지만 초대 링크는 사용할 수 없어요”라고 분리 안내한다.

### 5.4 이미 로그인한 사용자가 링크를 연다

1. 로그인한 사용자가 `/invites/{token}/accept`에 직접 진입한다.
2. 프론트엔드는 바로 `POST /api/invites/{token}/accept`를 호출한다.
3. 성공하면 `초대를 수락했어요` 안내 후 `/trips/{tripId}`로 이동한다.
4. 이미 같은 일정의 멤버라면 중복 수락 에러로 막지 않는다.
   - 안내: `이미 참여 중인 일정입니다.`
   - CTA: `일정 보러 가기`.
5. 이미 멤버의 기존 role은 낮추지 않는다.
   - 예: 이미 editor인 사용자가 viewer 초대 링크를 다시 눌러도 editor 유지.
   - 예: 이미 owner인 사용자가 초대 링크를 눌러도 owner 유지.

### 5.5 초대 수락 실패와 예외

| 상황 | API/상태 | 사용자 안내 | 다음 행동 |
| --- | --- | --- | --- |
| token 없음 | 404 | `초대 링크를 찾을 수 없어요.` | 새 링크 요청 안내 |
| token 만료 | 404 또는 만료 error | `초대 링크가 만료됐어요.` | 초대한 사람에게 새 링크 요청 |
| 미로그인 상태에서 수락 API 직접 호출 | 401 | `로그인 후 초대를 수락할 수 있어요.` | 로그인/가입 CTA |
| 서버 오류 | 500 | `초대를 수락하지 못했어요. 잠시 후 다시 시도해 주세요.` | 재시도 |
| 네트워크 오류 | client error | `연결이 불안정해요. 다시 시도해 주세요.` | 재시도 |
| 일정이 삭제됨 | 404 | `초대된 일정을 찾을 수 없어요.` | 새 초대 요청 불가 안내 |

## 6. 현재 구현: 일정 상세 수정 흐름

### 6.1 일정 상세 진입

1. 사용자가 `/trips/{tripId}`로 이동한다.
2. 프론트엔드는 `GET /api/trips/{tripId}`를 호출한다.
3. 백엔드는 접근 권한을 확인한다.
   - owner/member만 접근 가능.
   - 비멤버 또는 존재하지 않는 일정은 404 또는 접근 불가로 처리한다.
4. 응답에는 `currentUserRole`과 `revision`이 포함된다.
   - 허용 값: `owner`, `editor`, `viewer`.
5. 프론트엔드는 `currentUserRole`에 따라 화면을 분기하고, 장소 변경 요청에는 마지막으로 본 `revision`을 `expectedRevision`으로 보낸다.

### 6.2 owner/editor의 장소 추가

1. owner/editor가 일정 상세에서 `장소 추가` 버튼을 누른다.
2. 장소 추가 sheet가 열린다.
3. 사용자는 day, 시간, 장소명, 메모를 입력한다.
4. 장소 검색 후보가 필요한 경우 추천 후보 검색을 실행한다.
   - 후보는 `AppDataApi`를 통해 조회한다.
   - Kakao Local 후보가 있으면 외부 장소 메타데이터를 보존한다.
   - fallback catalog 후보도 표시할 수 있다.
5. 사용자가 후보를 선택하면 장소명, 주소, 좌표, 카테고리, Kakao place URL 같은 메타데이터가 form에 채워진다.
6. 사용자가 `추가`, `일정에 추가`, 또는 `저장` 버튼을 누른다.
7. 프론트엔드는 `POST /api/trips/{tripId}/days/{dayNumber}/places`를 호출하며 body에 `expectedRevision`을 포함한다.
8. 백엔드는 owner/editor 권한을 확인하고 같은 transaction에서 `trips.revision`을 atomic compare-and-increment한 뒤 `trip_places`에 저장한다.
9. 성공 시 sheet를 닫고 일정 상세 timeline을 갱신한다.

장소 추가 draft:

- 시간, 장소명, 메모, dayNumber draft는 24시간 localStorage에 저장된다.
- 저장 성공 또는 sheet 닫기 시 삭제된다.
- 유효 draft가 있으면 복원 안내와 폐기 버튼을 제공한다.

### 6.3 owner/editor의 장소 수정

1. owner/editor가 timeline의 기존 장소 카드에서 `수정` 또는 장소 상세 dialog의 `수정` 버튼을 누른다.
2. 장소 수정 sheet가 열린다.
3. 사용자는 시간, 장소명, 메모 등을 변경한다.
4. 사용자가 `저장` 버튼을 누른다.
5. 프론트엔드는 `PATCH /api/trips/{tripId}/places/{placeId}`를 호출하며 body에 `expectedRevision`을 포함한다.
6. 백엔드는 owner/editor 권한, place 소속, `trips.revision` 일치를 확인한다.
7. 성공 시 sheet를 닫고 timeline을 갱신한다.

장소 수정 draft:

- 수정 draft는 `placeId` 기준으로 24시간 localStorage에 저장된다.
- 저장 성공, sheet 닫기, 장소 삭제 시 삭제된다.

### 6.4 owner/editor의 장소 삭제

1. owner/editor가 장소 카드 또는 수정 sheet에서 `삭제`를 누른다.
2. 화면은 삭제 확인을 요구한다.
   - 예: `이 장소를 일정에서 삭제할까요?`
3. 사용자가 확인하면 `DELETE /api/trips/{tripId}/places/{placeId}?expectedRevision={revision}`를 호출한다.
4. 백엔드는 owner/editor 권한과 `trips.revision` 일치를 확인한다.
5. 성공 시 timeline에서 장소가 사라진다.
6. 삭제된 장소의 수정 draft가 있으면 제거한다.

### 6.5 owner/editor의 장소 이동

1. owner/editor가 장소 카드의 이동 handle을 잡는다.
2. 같은 Day 안에서 순서를 바꾸거나 다른 Day drop target으로 이동한다.
3. 이동 중 UI는 drag 상태와 drop 가능 영역을 표시한다.
4. drop하면 프론트엔드는 `PATCH /api/trips/{tripId}/places/{placeId}/move`를 호출하며 body에 `expectedRevision`을 포함한다.
5. 백엔드는 owner/editor 권한, place 존재, 대상 day 존재, `trips.revision` 일치를 확인한다.
6. 성공 시 timeline 순서를 갱신한다.
7. 실패하면 원래 순서로 되돌리고 오류 안내를 보여준다.

### 6.6 stale 저장 충돌 처리

1. 두 세션이 같은 일정 상세를 열면 둘 다 같은 `Trip.revision`을 가진다.
2. 먼저 저장한 사용자 요청은 `expectedRevision`이 현재 revision과 일치하므로 성공하고, 백엔드는 `trips.revision`을 1 증가시킨다.
3. 나중에 저장한 사용자 요청은 stale `expectedRevision`이므로 409 `Trip has changed. Refresh before saving.`을 받는다.
4. 프론트엔드는 최신 일정을 다시 조회하고 다음 안내를 보여준다.
   - `다른 사용자가 먼저 일정을 수정했어요. 최신 내용을 확인한 뒤 다시 저장해 주세요.`
5. 장소 추가/수정 sheet의 draft는 성공 전까지 삭제하지 않으므로 사용자는 최신 일정을 확인한 뒤 다시 저장할 수 있다.
6. 이 처리는 장소 추가, 장소 수정, 장소 이동, 장소 삭제에 적용된다. 일정 상태 변경과 정책 연결/해제는 후속 범위다.

### 6.7 viewer의 일정 상세

1. viewer가 `/trips/{tripId}`에 진입한다.
2. 일정 상세, day tab, timeline, 장소 상세 dialog는 볼 수 있다.
3. 다음 편집 컨트롤은 보이지 않거나 비활성화된다.
   - `장소 추가`.
   - 장소 `수정`.
   - 장소 `삭제`.
   - drag handle.
   - 정책 연결/해제.
4. viewer가 API를 직접 호출해도 백엔드는 403을 반환한다.
5. 화면 copy는 필요할 때만 짧게 노출한다.
   - 예: `보기 권한으로 참여 중이라 일정 편집은 할 수 없어요.`

## 7. 권한별 UI/API 매트릭스

| 행동 | Guest | Member 비참여자 | Viewer | Editor | Owner |
| --- | --- | --- | --- | --- | --- |
| 초대 링크 열기 | 가능 | 가능 | 가능 | 가능 | 가능 |
| 초대 수락 | 로그인/가입 필요 | 가능 | 이미 참여 안내 | 이미 참여 안내 | 이미 참여 안내 |
| 일정 상세 조회 | 불가 | 불가 | 가능 | 가능 | 가능 |
| 장소 추가 | 불가 | 불가 | 불가 | 가능 | 가능 |
| 장소 수정 | 불가 | 불가 | 불가 | 가능 | 가능 |
| 장소 삭제 | 불가 | 불가 | 불가 | 가능 | 가능 |
| 장소 이동 | 불가 | 불가 | 불가 | 가능 | 가능 |
| 초대 링크 생성/role 설정 | 불가 | 불가 | 불가 | 가능 | 가능 |
| 일정 삭제 | 불가 | 불가 | 불가 | 불가 | 가능 |

## 8. 가까운 다음 개선: email 초대 발송 흐름

### 8.1 설계 원칙

- email 초대는 링크 초대의 전송 방식이다.
- email 초대는 새로운 수락 URL을 만들지 않는다.
- email 본문은 `/invites/{token}/accept` 링크를 담는다.
- email 발송 실패는 링크 생성 실패와 분리한다.
- SMTP/Brevo 설정이 없거나 발송 실패 시 email 입력 UI는 유지하되 링크 복사 fallback을 안내한다.
- SMS/Kakao 발송은 포함하지 않는다.

### 8.2 owner/editor의 email 초대 작업흐름

1. owner/editor가 `/friend-invite?tripId={tripId}`에 진입한다.
2. owner/editor가 권한을 선택한다.
   - `함께 편집 가능(editor)` 또는 `보기만 가능(viewer)`.
3. owner/editor가 초대 받을 사람의 email 주소를 입력한다.
4. owner/editor가 `email로 초대 보내기` 버튼을 누른다.
5. 프론트엔드는 email 발송 API를 호출한다.
   - API: `POST /api/trips/{tripId}/invite/email`
   - Request 예시: `{ "email": "friend@example.com", "role": "editor" }`
6. 백엔드는 선택 role 전용 링크 확인/생성과 email 발송을 같은 service 흐름에서 처리한다.
7. 백엔드는 다음을 수행한다.
   - 요청자가 owner/editor인지 확인한다.
   - email 형식을 검증한다.
   - 선택한 role의 초대 token과 role을 확인한다.
   - public invite URL을 포함한 email을 발송한다.
   - 발송 결과를 audit/log로 남긴다. secret 또는 SMTP credential은 로그에 남기지 않는다.
8. 성공 시 화면은 발송 완료를 보여준다.

성공 copy 예시:

- `초대 email을 보냈어요.`
- `상대방은 email의 링크를 눌러 로그인 또는 회원가입 후 일정에 참여합니다.`
- `문제가 있으면 아래 링크를 직접 복사해 보내도 됩니다.`

### 8.3 Email 수신자의 흐름

1. 수신자가 email을 연다.
2. email 본문은 최소 정보를 제공한다.
   - `트래블헌터 일정 초대가 도착했어요.`
   - `아래 버튼으로 로그인 또는 회원가입 후 초대를 수락하세요.`
   - CTA: `초대 수락하기`.
3. 수신자가 CTA를 누르면 `/invites/{token}/accept`로 이동한다.
4. 이후 흐름은 링크 초대와 동일하다.
   - 비로그인: 로그인/회원가입 후 원래 링크 복귀.
   - 로그인: 바로 수락.
   - 만료/오류: 새 초대 요청 안내.

Email 본문에서도 로그인 전 일정 상세 미리보기는 제공하지 않는다.

### 8.4 Email 발송 예외 상태

| 상황 | 사용자 안내 | 시스템 동작 | 회복 행동 |
| --- | --- | --- | --- |
| SMTP 미설정 | `email 발송 설정이 아직 없어요. 해당 권한 링크를 복사해 직접 보내 주세요.` | API는 200과 `deliveryStatus=notConfigured`를 반환하고 선택 role 링크는 유지 | 링크 복사 fallback |
| 잘못된 email 형식 | `email 주소를 확인해 주세요.` | API 호출 전 client 검증 또는 422 | 입력 수정 |
| SMTP provider 실패 | `email을 보내지 못했어요. 링크를 복사해 직접 보내세요.` | 초대 token은 유지, 실패 로그 기록 | 링크 복사/재시도 |
| rate limit | `잠시 후 다시 시도해 주세요.` | 과도한 발송 차단 | 시간 후 재시도 |
| owner/editor 권한 없음 | `초대 email은 일정 owner/editor 멤버만 보낼 수 있어요.` | 403 | 일정 상세로 이동 |
| token 만료/갱신 필요 | `초대 링크를 다시 만든 뒤 보내 주세요.` | 새 token 생성 유도 | 링크 재생성 |

### 8.5 Email 개선의 acceptance criteria

- SMTP 설정이 없는 환경에서도 현재 링크 초대는 계속 정상 동작한다.
- email 발송 실패가 초대 링크 생성 성공을 되돌리지 않는다.
- email 본문은 public accept URL만 사용한다.
- email 본문과 화면 copy는 실제 SMS/Kakao 발송이 되는 것처럼 표현하지 않는다.
- 수신자는 email 링크를 통해 기존 `/invites/{token}/accept` 수락 흐름을 그대로 탄다.
- 발송 로그에는 수신 email과 발송 상태는 남길 수 있으나 SMTP secret/token은 남기지 않는다.

## 9. Smoke test 시나리오

### 9.1 현재 링크 초대 smoke

1. owner 또는 editor 계정으로 로그인한다.
2. 일정 하나를 생성하거나 seed 일정에 진입한다.
3. 일정 상세에서 `친구 초대`를 누른다.
4. 권한을 `함께 편집 가능`으로 선택한다.
5. 초대 링크를 생성한다.
6. 생성된 URL이 `/invites/{token}/accept` 형태인지 확인한다.
7. 시크릿 브라우저 또는 로그아웃 상태에서 링크를 연다.
8. 일정 상세 내용이 보이지 않고 로그인/회원가입 안내만 보이는지 확인한다.
9. 기존 계정으로 로그인한다.
10. 초대 수락 완료 안내가 보이는지 확인한다.
11. 일정 상세로 이동한다.
12. editor 권한이면 `장소 추가`와 장소 수정/삭제/이동이 가능한지 확인한다.
13. 같은 링크를 다시 열었을 때 “이미 참여 중” 안내 또는 일정 상세 이동이 되는지 확인한다.

### 9.2 Viewer 권한 smoke

1. owner 또는 editor가 같은 일정에서 role을 `보기만 가능`으로 선택해 링크를 생성한다.
2. 다른 계정 또는 신규 가입 계정으로 링크를 수락한다.
3. 일정 상세에 진입한다.
4. timeline과 장소 상세는 보이는지 확인한다.
5. `장소 추가`, `수정`, `삭제`, drag handle이 보이지 않거나 비활성인지 확인한다.
6. API 직접 호출 또는 UI 우회 시 서버가 403을 반환하는지 확인한다.

### 9.3 가입 후 초대 수락 smoke

1. 로그아웃 상태에서 초대 링크를 연다.
2. `회원가입하고 초대 수락하기`를 누른다.
3. email 중복 확인과 회원가입을 완료한다.
4. 필요한 닉네임/프로필 설정을 완료한다.
5. 원래 `/invites/{token}/accept`로 복귀하는지 확인한다.
6. 초대 수락 완료 후 일정 상세로 이동하는지 확인한다.
7. role에 맞는 편집 가능 여부를 확인한다.

### 9.4 일정 상세 편집 smoke

1. editor 또는 owner로 일정 상세에 진입한다.
2. 장소 추가 sheet를 연다.
3. 장소명/시간/메모를 입력하고 저장한다.
4. 새로고침 후 장소가 유지되는지 확인한다.
5. 장소를 수정하고 저장한다.
6. 장소를 같은 Day 안에서 이동한다.
7. 장소를 다른 Day로 이동한다.
8. 장소를 삭제한다.
9. viewer 계정으로 같은 일정에 진입해 위 편집 컨트롤이 차단되는지 확인한다.

### 9.5 Email 초대 smoke

1. SMTP/Brevo가 설정된 dev 또는 staging 환경을 준비한다. 로컬 SMTP 미설정 환경에서는 `deliveryStatus=notConfigured`와 링크 복사 fallback만 확인한다.
2. owner 또는 editor가 초대 화면에서 role과 email을 입력한다.
3. `email로 초대 보내기`를 누른다.
4. 발송 성공 안내와 링크 복사 fallback이 함께 보이는지 확인한다.
5. 수신 inbox에서 email을 확인한다.
6. email CTA가 `/invites/{token}/accept`로 이동하는지 확인한다.
7. 수신자가 로그인/가입 후 수락하는지 확인한다.
8. SMTP 실패 환경에서는 email 실패 안내가 나오고 링크 복사 초대는 계속 가능한지 확인한다.

## 10. 문서 동기화 규칙

이 흐름이 바뀌면 다음 문서를 함께 확인한다.

- `docs/requirements.md`: 역할, 초대, 일정 편집 요구사항.
- `docs/implemented-feature-spec.md`: 구현 상태 요약.
- `docs/mvp-api-contract.md`: invite/trip place API shape와 status code.
- `docs/next-work-plan.md`: release priority와 email 초대의 우선순위.
- `docs/deployment-cicd/09-release-checklist.md`: public smoke checklist.

API shape가 바뀌면 frontend types, backend schemas/routes/services/repositories, tests, `.agent/evals/api-contract-golden.json`을 함께 갱신해야 한다.
