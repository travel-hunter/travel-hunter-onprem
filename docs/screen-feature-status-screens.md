# 화면 기준 기능 개발 현황

> Status: reference.
> This document remains the screen-by-screen status ledger. For current local UX completion specs, use `docs/specs/spec-index.md` and the three `docs/specs/local-ux-*.md` documents.

이 문서는 Travel Hunter에서 사용자가 직접 보는 화면(route/page) 단위의 기능 개발 현황을 누적 기록한다. 각 화면은 "완료", "부분 완료", "코드 구현/환경 미설정", "미구현" 상태로 구분하고, 확인 근거와 현재 환경에서의 제약을 함께 남긴다.

## 새 섹션 추가 기준

- 새 route/page 또는 화면 단위 기능 상태를 보고할 때 이 문서에 추가한다.
- 사용자가 보는 버튼, 링크, form, list, card, tab, modal/sheet, loading/error/empty 상태를 중심으로 작성한다.
- 내부 추천 기준, 수집 pipeline, 외부 API fallback, 저장/선정 알고리즘 설명은 이 문서에 길게 쓰지 말고 `screen-feature-status-logic.md`에 분리한다.
- 화면과 내부 로직이 모두 관련되면 이 문서에는 화면에 보이는 결과와 API 연결 상태만 요약하고, 자세한 판단 기준은 로직 문서로 링크한다.

## 2026-05-29 - 로그인 페이지

### 화면 범위

- 경로: `/`, `/login`
- 관련 후속 경로: `/forgot-password`, `/reset-password`, `/signup`, `/oauth/callback`
- 확인 대상 기능: 로그인, 비밀번호 찾기, 회원가입, 카카오로 시작하기, 구글로 시작하기

### 기능별 개발 현황

| 기능 | 개발 상태 | 확인 내용 |
| --- | --- | --- |
| 로그인 | 완료 | 이메일/비밀번호 입력 후 `/api/auth/login`을 호출한다. 성공 시 access token을 저장하고 refresh cookie를 발급받은 뒤 `/home`으로 이동한다. 현재 로컬 서버에서 `test.user@example.com / password123` 로그인 `200 OK`를 확인했다. |
| 비밀번호 찾기 | 부분 완료 | `/forgot-password` 요청 화면, `/reset-password` 재설정 화면, 백엔드 토큰 생성/검증/비밀번호 변경 API는 구현되어 있다. 다만 현재 Docker 로컬 환경은 SMTP 설정이 비어 있어 실제 가입 이메일 대상으로 재설정 메일 발송 요청 시 `503 Email delivery is not configured`가 발생한다. |
| 회원가입 | 완료 | `/signup` 화면에서 이메일 중복 확인 후 `/api/auth/signup`을 호출한다. 가입 성공 시 세션을 저장하고 닉네임 설정 화면으로 이동한다. |
| 카카오로 시작하기 | 코드 구현/환경 미설정 | 로그인 화면 버튼은 `/api/auth/oauth/kakao/start`로 연결되고, 백엔드 start/callback 로직도 구현되어 있다. 현재 compose 환경의 `KAKAO_CLIENT_ID`, `KAKAO_CLIENT_SECRET` 값이 비어 있어 실제 클릭 시 `503 OAuth provider is not configured`가 발생한다. |
| 구글로 시작하기 | 코드 구현/환경 미설정 | 로그인 화면 버튼은 `/api/auth/oauth/google/start`로 연결되고, 백엔드 start/callback 로직도 구현되어 있다. 현재 compose 환경의 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` 값이 비어 있어 실제 클릭 시 `503 OAuth provider is not configured`가 발생한다. |

### 보고용 요약

현재 로그인 화면은 일반 이메일 로그인과 회원가입 기능이 실제 백엔드/DB와 연결되어 개발 완료된 상태다. 비밀번호 찾기는 화면과 서버 로직은 구현되어 있으나, 실제 메일 발송을 위한 SMTP 설정이 없어 로컬/현재 환경에서는 발송 기능이 동작하지 않는다. 카카오/구글 소셜 로그인은 프론트 버튼과 백엔드 OAuth 처리 흐름은 구현되어 있지만, 각 provider의 클라이언트 키/시크릿이 설정되지 않아 현재 환경에서는 실제 로그인이 불가능하다.

### 확인 근거

- `frontend/src/pages/AuthPages.tsx`: 로그인, 회원가입, 비밀번호 재설정, OAuth callback 화면 구현
- `frontend/src/api/backendApi.ts`: auth/password reset/OAuth start API 연결
- `frontend/src/app/session.tsx`: 로그인, 회원가입, OAuth 완료 후 세션 저장 처리
- `backend/app/api/routes/auth.py`: login/signup/password reset/OAuth route 구현
- `backend/app/services/auth.py`: 로그인, 회원가입, refresh token, password reset 서비스 구현
- `backend/app/services/oauth.py`: Kakao/Google OAuth provider 설정, state 검증, token 교환, userinfo 조회, 사용자 생성/연결 로직 구현
- `backend/app/services/email.py`: SMTP 설정이 없으면 비밀번호 재설정 메일 발송 실패 처리
- `docs/mvp-api-contract.md`: auth/password reset/OAuth API 계약 문서화

### 2026-05-29 로컬 검증 결과

- `docker.exe compose -f compose.yaml config`: 통과
- frontend/backend Docker 이미지 `--no-cache` 재빌드: 통과
- DB Alembic head: `0016_kakao_place_metadata`
- seed 적용 후 정책 데이터: 68건
- `GET /api/health`: `200 OK`, database connected
- `POST /api/auth/login` with `test.user@example.com / password123`: `200 OK`
- `POST /api/auth/password-reset/request` with unknown email: `200 OK`, 계정 존재 여부 숨김 동작 확인
- `POST /api/auth/password-reset/request` with existing email: `503`, SMTP 미설정 확인
- `GET /api/auth/oauth/kakao/start?redirect=/home`: `503`, provider 설정 미완료 확인
- `GET /api/auth/oauth/google/start?redirect=/home`: `503`, provider 설정 미완료 확인

### 남은 작업/리스크

- 실제 비밀번호 찾기 메일 발송을 완료하려면 SMTP 환경변수 설정과 실제 메일 발송 smoke가 필요하다.
- 카카오/구글 소셜 로그인을 운영 기능으로 완료하려면 각 provider client id/secret, callback URL, 프론트 공개 URL 설정이 필요하다.
- 현재 로컬 실행은 WSL 내 `docker` 명령이 직접 잡히지 않아 Windows Docker CLI 경로인 `docker.exe`로 검증했다.

## 2026-05-29 - 홈 페이지

### 화면 범위

- 경로: `/home`
- 접근 조건: 로그인 필요. 비로그인 사용자는 `/login?redirect=/home`으로 이동한다.
- 확인 대상 기능: 상단 검색/마이페이지 진입, 정리된 인기 정책 카드, 세로형 최대 3개 이번 주 혜택 목록, AI 추천 맞춤 일정, 공통 상단/하단 내비게이션

### 화면에 보이는 버튼/링크별 개발 현황

| 화면 요소 | 개발 상태 | 연결/동작 | 확인 내용 |
| --- | --- | --- | --- |
| 상단 검색 pill `어디로 떠나세요?` | 완료 | `/policies` | 홈 안에서 직접 검색어를 입력하는 기능은 아니고, 정책 탐색 화면으로 이동하는 진입 버튼이다. |
| 상단 프로필 원형 버튼 | 완료 | `/mypage` | 사용자 닉네임 첫 글자를 아바타처럼 표시하고 마이페이지로 이동한다. 접근성 label은 `마이페이지`다. |
| 인사말 영역 | 완료 | 세션 사용자 정보 표시 | `currentUser.nickname`을 사용해 `안녕, {name}님` 문구를 보여준다. 사용자 정보가 없으면 `여행자` fallback을 쓴다. |
| `이번 주 인기 정책` 히어로 카드 | 완료 | `/policies/{policySlug}` | 정책 목록의 대표 정책을 깔끔한 카드 톤으로 보여주고 `자세히 보기 →` CTA로 정책 상세에 이동한다. 대표 정책 slug가 별도 지정되지 않으면 첫 번째 정책을 사용한다. |
| `이번 주 혜택` 섹션의 `더보기` | 완료 | `/policies` | 전체 정책 탐색 화면으로 이동한다. |
| `이번 주 혜택` 정책 카드들 | 완료 | `/policies/{policySlug}` | 마감일이 가까운 정책 상위 3개를 세로형 카드 목록으로 표시하고 각 카드 클릭 시 정책 상세로 이동한다. 카드는 아이콘/카테고리, 정책명, 요약 1줄, 신청 마감/D-day, 신청 조건 칩 1개, 금액/마감 핵심 1줄을 보여준다. 공식/신청 버튼과 상세 조건 전체 문장은 카드 안에 표시하지 않는다. |
| `인기 국내 여행지` 카드들 | 제거 | - | 홈 화면 단순화를 위해 섹션, 카드 공간, 해당 섹션 전용 지역 추천 API 호출/계산을 제거했다. 지역 기반 일정 CTA는 `AI 추천 맞춤 일정`에서 유지한다. |
| `AI 추천 맞춤 일정` 카드/캐러셀 | 완료 | `/trips/new?region={지역}` | 홈에서 AI 결과를 바로 호출하는 기능은 아니고, 추천 지역을 넣어 새 일정 생성 화면으로 이동하는 CTA다. 관심 지역이 1개 이상이면 이 영역은 관심 지역만 보여준다. 관심 지역 1개는 중앙 단일 카드, 2개 이상은 좌우 카드 끄트머리 노출 없이 한 번에 1개 카드만 보이는 이전/다음 순환 관심지역 카드 캐러셀로 표시한다. |
| 공통 상단 내비게이션 | 완료 | `/home`, `/policies`, `/trips`, `/mypage`, admin이면 `/admin` | 데스크톱 주요 메뉴로 표시된다. 현재 페이지인 홈 탭은 active 상태가 된다. |
| 공통 하단 탭 | 완료 | `/home`, `/policies`, `/trips`, `/mypage`, admin이면 `/admin` | 모바일/앱형 주요 메뉴로 표시된다. 현재 페이지인 홈 탭은 active 상태가 된다. |

### 데이터/API 연결 현황

| 데이터 | 개발 상태 | API/로직 |
| --- | --- | --- |
| 정책 목록 | 완료 | `appDataApi.listPolicies()` → `GET /api/policies` |
| 지역 추천 | 완료 | `appDataApi.listRegionRecommendations({ style, region, preferredRegions, limit: 3 })` → `GET /api/recommendations/regions` |
| 지역 추천 fallback | 완료 | 지역 추천 API 결과가 없으면 정책 목록에서 지역별 정책 수를 계산해 제주/부산/강원 등 fallback 카드 생성 |
| 로딩/오류 상태 | 완료 | 정책 목록 로딩 중 `혜택을 불러오는 중입니다`, 실패 시 `혜택을 불러오지 못했어요` 오류 상태 표시 |

### 보고용 요약

홈 화면은 로그인 후 사용자가 정책 탐색과 일정 생성으로 진입하는 대시보드 역할로 개발되어 있다. 상단 검색 pill은 실제 홈 내 검색 입력이 아니라 정책 목록 화면으로 이동하는 버튼이며, 마이페이지 버튼은 사용자 아바타 형태로 제공된다. 인기 정책/이번 주 혜택 정책 카드는 실제 정책 API 데이터를 사용해 정책 상세로 연결되고, 이번 주 혜택은 가로 스크롤 없이 마감 임박순 상위 3개 세로 카드로 요약 1줄, 신청 마감/D-day, 신청 조건 칩을 포함한 핵심 혜택 정보를 간단히 보여준다. 인기 국내 여행지 rail은 제거되었고, AI 추천 맞춤 일정 영역은 관심 지역이 있으면 관심 지역만 일정 생성 CTA로 보여주며, 2개 이상일 때는 좌우 카드 끄트머리 노출 없이 한 번에 1개만 보이는 순환형 카드 캐러셀로 제공된다. 공통 상단/하단 내비게이션도 홈 화면에서 동작한다.

### 확인 근거

- `frontend/src/pages/HomePage.tsx`: 홈 화면 구성, 정책/지역 추천 API 호출, 각 링크 연결
- `frontend/src/components/AiRecommendationCard.tsx`: AI 추천 맞춤 일정 카드 링크 UI
- `frontend/src/components/patterns.tsx`: 홈 섹션 헤더, rail 구성
- `frontend/src/components/AppLayout.tsx`: 공통 상단 내비게이션과 하단 탭
- `frontend/src/data/displayConfig.ts`: 대표 정책, 마감 임박 정책, 인기 여행지/fallback 계산
- `frontend/src/App.test.tsx`: 홈 rail, 정책 링크, 지역 추천, fallback 동작 테스트
- `backend/app/api/routes/recommendations.py`: 지역 추천 API route
- `backend/app/services/region_recommendations.py`: 지역 추천 ranking 로직
- `docs/mvp-api-contract.md`: `GET /recommendations/regions` API 계약 문서화

### 2026-05-29 로컬 검증 결과

- `docker.exe compose -f compose.yaml ps`: backend/db healthy, frontend running
- `GET /api/policies`: `200 OK`
- `GET /api/recommendations/regions?style=휴식&region=제주&limit=3`: `200 OK`
- `HEAD /home` on frontend preview server: `200 OK`

### 남은 작업/리스크

- 홈 상단 `어디로 떠나세요?`는 검색 입력이 아니라 정책 목록 이동 버튼이다. 발표 시 "홈 검색"으로 표현하면 실제 동작과 다르므로 "정책 탐색 진입"으로 설명하는 편이 정확하다.
- `AI 추천 맞춤 일정`은 홈에서 AI 추천 결과를 바로 생성하지 않는다. 현재는 추천 지역을 새 일정 생성 화면에 전달하는 진입 카드다.
- 지역 추천 API가 실패해도 화면은 정책 기반 fallback으로 계속 보이므로, 추천 API 실패가 사용자에게 별도 오류로 표시되지는 않는다.

## 2026-05-29 - 정책 목록 페이지

### 화면 범위

- 경로: `/policies`
- 접근 조건: 로그인 필요. 비로그인 사용자는 `/login?redirect=/policies`로 이동한다.
- 확인 대상 기능: 정책 카테고리 탭, 즐겨찾기 필터/저장, 검색, 지역/기간/금액 필터, 필터 초기화, 정책 카드 목록, 정책 상세 이동, 공통 상단/하단 내비게이션

### 화면에 보이는 버튼/기능별 개발 현황

| 화면 요소 | 개발 상태 | 연결/동작 | 확인 내용 |
| --- | --- | --- | --- |
| 카테고리 탭 `전체` | 완료 | query `category` 제거 | 모든 카테고리 정책을 표시한다. 목록 정렬 시 카테고리 다양화 로직이 적용된다. |
| 카테고리 탭 `교통`, `숙박`, `여행상품`, `지역할인`, `이벤트`, `기타` | 완료 | `/policies?category={카테고리}` 상태 | 선택한 카테고리만 표시하고 URL query로 복원된다. 테스트에서 `교통`, `여행상품`, `지역할인` 필터 동작을 확인한다. |
| `♥ 즐겨찾기` 버튼 | 완료 | `/policies?saved=1` 상태 | 현재 사용자가 저장한 정책만 표시한다. 저장된 개수가 있으면 버튼에 개수 표시가 붙는다. |
| 정책 카드의 하트 버튼 | 완료 | `POST /api/me/saved-policies/{policySlug}` 또는 `DELETE /api/me/saved-policies/{policySlug}` | 정책을 즐겨찾기에 저장/해제한다. 카드 링크 내부 버튼이지만 클릭 시 상세 이동을 막고 저장 동작만 수행한다. |
| 검색 입력 `정책명, 지역, 혜택으로 검색` | 완료 | 프론트 클라이언트 필터 | 정책 제목, 기관, 지역, 카테고리, 금액, 요약, 태그, 조건, 서류 텍스트를 대상으로 검색한다. |
| 지역 필터 `🌎 지역` | 완료 | 프론트 클라이언트 필터 | `전체`, `전국`, 프로필 관심 지역, 선택 지역, 정책 수가 많은 주요 지역을 우선 표시한다. 나머지는 `전체 지역 보기`로 확장한다. |
| `전체 지역 보기` / `전체 지역 닫기` | 완료 | 지역 필터 패널 확장/접기 | 주요 지역에 없는 지역까지 선택할 수 있게 전체 지역 목록을 보여준다. |
| 기간 필터 `🗓 기간` | 완료 | 프론트 클라이언트 필터 | `전체`, `7일 이내`, `30일 이내`, `3개월 이내` 기준으로 마감일을 필터링한다. |
| 금액 필터 `💰 금액` | 완료 | 프론트 클라이언트 필터 | `전체`, `금액 명시`, `10만원 이상`, `30만원 이상` 기준으로 혜택 금액 문자열을 필터링한다. |
| `초기화` 버튼 | 완료 | 모든 필터/검색/query 초기화 | 검색어, 지역, 기간, 금액, 카테고리, 즐겨찾기 필터를 모두 기본값으로 되돌린다. |
| 결과 개수 문구 | 완료 | `전체 N개 중 M개 표시` | API에서 받은 전체 정책 수와 필터 후 표시 정책 수를 보여준다. |
| 정책 카드 | 완료 | `/policies/{policySlug}` | 금액, D-day, 제목, 지역, 마감일, 혜택 유형 아이콘을 표시하고 클릭 시 정책 상세 화면으로 이동한다. |
| 로딩/오류/빈 상태 | 완료 | 상태별 UI | 정책 로딩 중 `정책을 불러오는 중입니다`, API 오류 시 홈으로 가기 액션, 필터 결과 없음 시 `전체 보기` 액션을 제공한다. |
| 공통 상단/하단 내비게이션 | 완료 | `/home`, `/policies`, `/trips`, `/mypage`, admin이면 `/admin` | 정책 탭 active 상태로 표시된다. |

### 데이터/API 연결 현황

| 데이터/동작 | 개발 상태 | API/로직 |
| --- | --- | --- |
| 정책 목록 조회 | 완료 | `appDataApi.listPolicies()` → `GET /api/policies` |
| 정책 상세 이동 | 완료 | 카드 링크 → `/policies/{policySlug}`, 상세 화면에서 `GET /api/policies/{policySlug}` 사용 |
| 즐겨찾기 저장 | 완료 | `appDataApi.savePolicy(policySlug)` → `POST /api/me/saved-policies/{policySlug}` |
| 즐겨찾기 해제 | 완료 | `appDataApi.removeSavedPolicy(policySlug)` → `DELETE /api/me/saved-policies/{policySlug}` |
| 즐겨찾기 필터 상태 | 완료 | 세션의 `savedSlugs`와 URL query `saved=1`을 함께 사용 |
| 목록 필터링 | 완료 | 서버 검색 API가 아니라, `GET /api/policies`로 받은 정책 배열을 프론트에서 검색/필터/정렬 |

### 보고용 요약

정책 목록 화면은 전체 정책을 DB-backed API에서 불러온 뒤 프론트에서 카테고리, 지역, 기간, 금액, 검색어, 즐겨찾기 조건으로 필터링하는 화면이다. 카테고리와 즐겨찾기는 URL query로 상태가 남고, 지역/기간/금액/검색은 화면 내부 상태로 동작한다. 각 정책 카드는 상세 화면으로 이동하며, 카드 오른쪽 하트 버튼으로 정책을 즐겨찾기에 저장하거나 해제할 수 있다. 현재 목록 검색은 서버 검색이 아니라 클라이언트 필터 방식이다.

### 확인 근거

- `frontend/src/pages/PolicyPages.tsx`: 정책 목록 화면, 카테고리/지역/기간/금액/검색/즐겨찾기 필터 구현
- `frontend/src/components/cards.tsx`: 정책 카드와 카드 하트 저장 버튼 구현
- `frontend/src/app/App.tsx`: `/policies` protected route 구성
- `frontend/src/api/backendApi.ts`: 정책 목록/상세/저장/해제 API 연결
- `frontend/src/App.test.tsx`: 카테고리 탭, 지역 필터, 전체 지역 보기, 검색, 결과 개수, 정렬, 즐겨찾기 저장/해제 테스트
- `backend/app/api/routes/policies.py`: `GET /policies`, `GET /policies/{policy_slug}`, saved policy route 구현
- `backend/app/repositories/policies.py`: active 정책만 목록 반환, 저장 정책 조회/추가/삭제 repository 구현
- `docs/mvp-api-contract.md`: `GET /policies`, `GET /policies/{policy_slug}` API 계약 문서화

### 2026-05-29 로컬 검증 결과

- `docker.exe compose -f compose.yaml ps`: backend/db healthy, frontend running
- `GET /api/policies`: `200 OK`, active 정책 57건 반환
- 첫 번째 active 정책 응답 확인: `travelmonth-1`, `남원시 여행가는 달 관광택시 50% 할인`, `전북`, `지역할인`
- `HEAD /policies` on frontend preview server: `200 OK`

### 남은 작업/리스크

- `/policies` 검색/필터는 현재 클라이언트 필터 방식이다. 정책 수가 크게 늘어나면 서버 검색/페이지네이션이 필요할 수 있다.
- 기간 필터는 브라우저 실행 시점의 현재 날짜 기준으로 `Date.now()`를 사용한다. 발표/시연 날짜에 따라 `7일 이내`, `30일 이내` 결과 수가 달라질 수 있다.
- 금액 필터는 `만원` 문자열과 `%` 포함 여부를 기준으로 파싱한다. `천원`, `무료`, `환급`처럼 다양한 금액 표현은 일부 필터에서 기대와 다르게 분류될 수 있다.
- 숨김 상태 정책은 API 목록에서 제외되므로 DB 전체 정책 수와 화면/API active 정책 수가 다를 수 있다.

## 2026-05-29 - 정책 상세 페이지

### 화면 범위

- 경로: `/policies/{policySlug}`
- 접근 조건: 로그인 필요. 비로그인 사용자는 `/login?redirect=/policies/{policySlug}`로 이동한다.
- 확인 대상 기능: 정책 상세 조회, 지원 내용/신청 기간/대상/서류 표시, 공식 안내/신청 링크, 관심 정책 저장/해제, 공유, 내 일정에 담기, 새 일정 생성 진입, 로딩/오류/빈 상태

### 화면에 보이는 버튼/기능별 개발 현황

| 화면 요소 | 개발 상태 | 연결/동작 | 확인 내용 |
| --- | --- | --- | --- |
| 뒤로 버튼 | 완료 | `navigate(-1)` | 정책 목록이나 이전 화면으로 돌아간다. |
| 저장 하트 버튼 | 완료 | `POST /api/me/saved-policies/{policySlug}` 또는 `DELETE /api/me/saved-policies/{policySlug}` | 현재 세션의 `savedSlugs`를 기준으로 저장 여부를 표시하고, 클릭 시 관심 정책 저장/해제를 수행한다. 성공/실패 결과는 토스트 문구로 안내한다. |
| 공유 버튼 | 완료 | Web Share API 또는 clipboard fallback | 현재 정책 상세 URL을 공유하거나 복사한다. 성공 시 `정책 링크를 공유했어요` 또는 `정책 링크를 복사했어요` 토스트를 표시한다. |
| 정책 제목/기관/지역/태그 | 완료 | `GET /api/policies/{policySlug}` 응답 표시 | 정책 제목, 주관 기관, 지역, 혜택 태그, D-day를 상세 상단에 표시한다. |
| 지원 내용 | 완료 | 응답의 `amount`, `summary`, benefit parsing 결과 표시 | 단순 금액만 반복하지 않고 핵심 혜택, 운영 기간, 이용 조건, 유의사항 등으로 나눠 보여준다. 긴 TravelMonth 요약도 화면에서 읽기 쉬운 그룹으로 분리한다. |
| 신청 기간 | 완료 | `deadline` 기반 표시 | 마감일과 D-day를 표시하고 `서둘러 신청하세요` 안내를 제공한다. |
| 신청 대상/혜택 적용 조건/확인 필요 사항 | 완료 | `requirements` 기반 분류 표시 | 요구사항 문구를 신청 대상, 결제/지역/한도 등 적용 조건, 공식 안내 확인 사항으로 나눠 보여준다. |
| 필요 서류 | 완료 | `documents` 배열 표시 | 각 필요 서류를 체크 리스트 형태로 표시한다. |
| `📅 내 일정에 담기` 버튼 | 완료 | `GET /api/trips` 후 일정 선택 sheet 표시 | 사용자의 일정 목록을 불러오고, 선택한 일정에 정책을 연결할 수 있는 sheet를 연다. 이미 세션에 담긴 정책이면 `일정에 담김` 문구로 표시된다. |
| 일정 선택 sheet | 완료 | `POST /api/trips/{tripId}/policies/{policySlug}` | 일정 목록 로딩, 일정 선택, 연결 중, 연결 성공, 오류 상태를 처리한다. 성공 후 `일정에서 보기` 버튼으로 선택 일정 상세에 이동한다. |
| 담을 일정이 없는 상태 | 완료 | `/trips/new?policySlug={policySlug}` | 일정이 없으면 새 일정 만들기 CTA를 제공하고, 생성 화면에 정책 slug를 전달한다. |
| `새 일정에 담기` 링크 | 완료 | `/trips/new?policySlug={policySlug}` | 기존 일정이 있어도 새 일정 생성 경로로 정책 slug를 전달할 수 있다. |
| `신청하러 가기` CTA | 완료 | `applyUrl` 외부 링크 | 직접 신청 URL이 있는 정책은 primary CTA로 새 탭 외부 링크를 제공한다. |
| `혜택 안내 보기` CTA | 완료 | `officialUrl` 외부 링크 | 직접 신청 URL이 없고 공식 안내 URL이 있으면 안내 링크를 secondary CTA로 제공한다. |
| `신청 링크 준비 중` 비활성 CTA | 완료 | 비활성 버튼 | `applyUrl`과 `officialUrl`이 모두 없으면 신청 링크 준비 중 상태를 보여준다. |
| 사용 불가 정책 controls 안내 | 부분 완료 | `canUsePolicyActions(policy)` 조건 | 화면에는 안내 문구와 비활성 버튼 처리가 구현되어 있다. 다만 상세 조회는 일부 migration gap raw fallback을 허용하므로, 저장/일정 담기는 정규화된 active `policies` 기준 정책에서만 안정적으로 동작한다. |
| 로딩/오류 상태 | 완료 | `useAsyncResource()` 상태 UI | 상세 로딩 중 `정책 상세를 불러오는 중입니다`, 오류/404 시 `정책 목록으로` 액션을 제공한다. |

### 데이터/API 연결 현황

| 데이터/동작 | 개발 상태 | API/로직 |
| --- | --- | --- |
| 정책 상세 조회 | 완료 | `appDataApi.getPolicy(policySlug)` → `GET /api/policies/{policySlug}` |
| 관심 정책 저장 | 완료 | `appDataApi.savePolicy(policySlug)` → `POST /api/me/saved-policies/{policySlug}` |
| 관심 정책 해제 | 완료 | `appDataApi.removeSavedPolicy(policySlug)` → `DELETE /api/me/saved-policies/{policySlug}` |
| 일정 목록 조회 | 완료 | `appDataApi.listTrips()` → `GET /api/trips` |
| 일정에 정책 연결 | 완료 | `appDataApi.addPolicyToTrip(trip.id, policy.slug)` → `POST /api/trips/{tripId}/policies/{policySlug}` |
| 새 일정 생성 연계 | 완료 | `/trips/new?policySlug={policySlug}` query 전달. 일정 생성 API는 `POST /api/trips` 요청의 `policySlug`를 지원한다. |
| 외부 신청/안내 링크 | 완료 | `applyUrl` 우선, 없으면 `officialUrl`, 둘 다 없으면 비활성 fallback |
| 공유 | 완료 | `shareLinkWithFallback()`으로 Web Share API 또는 clipboard 사용 |

### 보고용 요약

정책 상세 화면은 정책 목록에서 선택한 `policySlug`를 기준으로 DB-backed 정책 상세 API를 호출해 지원 내용, 신청 기간, 신청 대상/조건, 필요 서류를 보여주는 화면이다. 사용자는 상세 화면에서 정책을 관심 정책으로 저장하거나 해제할 수 있고, 정책 링크를 공유할 수 있으며, 기존 일정 또는 새 일정에 해당 정책을 연결할 수 있다. 신청 CTA는 직접 신청 링크(`applyUrl`)가 있으면 `신청하러 가기`, 직접 신청 링크가 없고 공식 안내 링크(`officialUrl`)가 있으면 `혜택 안내 보기`, 둘 다 없으면 `신청 링크 준비 중` 비활성 상태로 표시된다.

### 확인 근거

- `frontend/src/pages/PolicyPages.tsx`: 정책 상세 화면, 저장/공유/일정 담기 sheet, 신청/안내 CTA, 로딩/오류 상태 구현
- `frontend/src/api/backendApi.ts`: 정책 상세, 저장/해제, 일정 목록, 일정 정책 연결 API 연결
- `frontend/src/app/App.tsx`: `/policies/:policyId` protected route 구성
- `frontend/src/app/session.tsx`: 저장 정책 slug와 일정에 담긴 정책 slug 세션 상태 관리
- `frontend/src/App.test.tsx`: 정책 상세 섹션 순서, 공식 안내/직접 신청 CTA, 저장/일정 담기, 긴 혜택 요약 분리, raw/external 정책 표시 숨김 테스트
- `backend/app/api/routes/policies.py`: `GET /policies/{policy_slug}`, saved policy route 구현
- `backend/app/services/policies.py`: active 정책 상세 조회, raw external fallback, 저장/해제 서비스 구현
- `backend/app/services/trips.py`: `POST /trips/{tripId}/policies/{policySlug}` 정책-일정 연결 서비스 구현
- `docs/mvp-api-contract.md`: 정책 상세, saved policy, 일정 정책 연결 API 계약 문서화

### 2026-05-29 로컬 검증 결과

- 코드 근거 확인: `frontend/src/pages/PolicyPages.tsx`, `frontend/src/api/backendApi.ts`, `backend/app/api/routes/policies.py`, `backend/app/services/policies.py`, `backend/app/services/trips.py`, `docs/mvp-api-contract.md`
- 테스트 근거 확인: `frontend/src/App.test.tsx`에 정책 상세 CTA/저장/일정 담기/상세 섹션 관련 회귀 테스트가 존재한다.
- 이번 문서 작성 턴에서는 기능 코드를 변경하지 않았고, 실행 중인 브라우저에서 신규 수동 smoke는 추가 수행하지 않았다.

### 남은 작업/리스크

- 정책 상세 조회는 migration gap 동안 일부 raw `external_source_records` fallback을 허용하지만, 저장/일정 연결은 정규화된 active `policies` 기준이므로 raw fallback 정책은 controls 제약이 있을 수 있다.
- 공유 기능은 브라우저 Web Share API/clipboard 권한에 따라 동작 방식이 달라질 수 있다.
- 외부 신청/안내 CTA는 공식 URL 품질에 의존한다. 수집 원천의 상세 URL이 generic URL이면 사용자가 실제 신청 페이지를 추가로 찾아야 할 수 있다.
- 일정 담기는 사용자에게 편집 가능한 일정이 있어야 자연스럽게 완료된다. 일정이 없으면 새 일정 생성 경로로 이어진다.

## 2026-05-29 - 일정 상세 페이지

### 화면 범위

- 경로: `/trips/{tripId}`
- 접근 조건: 로그인 필요. 비로그인 사용자는 `/login?redirect=/trips/{tripId}`로 이동한다.
- 라우트 식별자: 공개 slug가 아니라 내부 numeric string trip id를 사용한다.
- 확인 대상 기능: 일정 상세 조회, 참여자/초대 진입, 연결 정책 표시/해제, 추천 정책 표시, Day 탭, 리스트/지도 전환, 장소 추가/수정/삭제/이동, 장소 작성 draft 복원/삭제, AI 추천 후보 진입, viewer 읽기 전용 처리, Kakao 지도/fallback 지도 표시, 로딩/오류 상태

### 화면에 보이는 버튼/기능별 개발 현황

| 화면 요소 | 개발 상태 | 연결/동작 | 확인 내용 |
| --- | --- | --- | --- |
| 상단 `일정 목록` 뒤로 버튼 | 완료 | `/trips` | 일정 목록 화면으로 이동한다. |
| 일정 히어로 | 완료 | `GET /api/trips/{tripId}` 응답 표시 | 일정 제목, 날짜, D-day, 지역 기반 이모지 아이콘을 표시한다. |
| 참여자 요약 | 완료 | `trip.people` 또는 fallback 표시 | 최대 3명의 아바타 이니셜과 참여 인원 수를 보여준다. |
| `+ 친구 초대` 링크 | 완료 | `/friend-invite?tripId={tripId}` | 현재 일정 id를 query로 전달해 친구 초대 화면으로 이동한다. |
| 연결된 정책 카드 | 완료 | `/policies/{policySlug}` | 일정에 연결된 정책을 표시하고 active 정책은 정책 상세로 이동한다. 숨김 정책은 링크 대신 숨김 처리 상태로 표시한다. |
| 연결 정책 삭제 버튼 | 완료 | `DELETE /api/trips/{tripId}/policies/{policySlug}` | owner/editor 권한에서 정책 연결을 해제한다. 삭제 중 상태와 실패 오류 문구를 처리한다. viewer는 삭제 버튼을 볼 수 없다. |
| 연결 정책 없음 상태 | 완료 | `/policies` | 연결 정책이 없으면 정책 목록으로 이동하는 banner를 표시한다. `expectedSaving` 값이 남아 있으면 정책 목록 확인 안내로 fallback한다. |
| 이 일정에 어울리는 정책 | 완료 | `trip.recommendedPolicies` 표시 | 추천 정책 카드가 있으면 정책 상세로 이동하고, 추천 정책이 없으면 정책 목록으로 이동하는 fallback 카드를 보여준다. |
| Day 탭 | 완료 | URL query `day`와 내부 상태 연동 | 일정의 day 번호와 날짜 라벨을 표시하고 선택한 day의 장소 목록/지도를 전환한다. 장소 drag 중에는 다른 day로 드롭 가능한 탭으로 동작한다. |
| 리스트/지도 전환 탭 | 완료 | URL query `view=list` / `view=map` | 일정 장소를 리스트 또는 지도 모드로 전환한다. 지도 모드 선택 시 `place` query로 선택 장소도 복원한다. |
| viewer 읽기 전용 안내 | 완료 | `currentUserRole === "viewer"` | viewer는 일정과 정책을 확인할 수 있지만 장소 추가/수정/삭제/이동, 정책 연결 삭제를 할 수 없다는 안내가 표시된다. |
| 장소 리스트 | 완료 | `trip.days[day]` 표시 | 방문 시간, 장소명, 메모, 장소 유형 이모지, 순번을 타임라인 형태로 표시한다. |
| 장소 빈 상태 | 완료 | day별 장소 배열이 비어 있을 때 표시 | 편집 가능 사용자는 장소 추가 안내, viewer는 등록된 장소 없음 안내를 본다. |
| `+ 장소 추가` 버튼 | 완료 | `POST /api/trips/{tripId}/days/{dayNumber}/places` | owner/editor만 볼 수 있다. 장소명은 필수이고 방문 시간은 비어 있거나 `HH:MM` 10분 단위여야 한다. 저장 성공 시 전체 Trip 응답으로 화면을 갱신한다. |
| 장소 수정 버튼 | 완료 | `PATCH /api/trips/{tripId}/places/{placeId}` | 기존 장소의 시간/장소명/메모를 sheet에서 수정한다. 저장 성공 시 전체 Trip 응답으로 화면을 갱신한다. |
| 장소 삭제 버튼 | 완료 | `DELETE /api/trips/{tripId}/places/{placeId}` | 삭제 확인 dialog를 거친 뒤 장소를 삭제한다. 실패 시 dialog 안에 오류를 표시한다. |
| 장소 순서 이동 핸들 | 완료 | `PATCH /api/trips/{tripId}/places/{placeId}/move` | drag handle과 키보드 조작으로 같은 day 내 순서 변경 또는 다른 day 이동을 지원한다. 이동 중 badge와 실패 토스트를 처리한다. |
| 장소 작성 draft | 완료 | localStorage `travel-hunter:draft:trip-place:{tripId}:...` | 장소 추가/수정 sheet 작성 중 값을 저장하고, 재진입 시 복원 안내를 표시한다. 저장/닫기/삭제 시 draft를 정리한다. |
| 방문 시간 picker | 완료 | 프론트 검증 후 장소 저장 API 호출 | 기본 `09:00`, 시간/10분 단위 증감, 시간 비우기 기능을 제공한다. 10분 단위가 아니면 저장하지 않고 오류를 표시한다. |
| `✨ 추천 후보 추가` 링크 | 완료 | `/ai-results?tripId={tripId}` | 현재 일정에 추가할 AI 추천 후보 화면으로 이동한다. |
| 지도 모드 | 완료 | `KakaoMapView` + fallback 지도 | 장소 좌표/주소/검색어를 marker로 전달해 Kakao 지도를 시도한다. 장소가 없으면 지도 빈 상태를 보여주고, SDK/좌표 제약이 있으면 SVG fallback 지도를 표시한다. |
| 지도 marker 선택 | 완료 | URL query `place={placeId}` | 선택한 장소의 bottom sheet를 표시하고 닫기/선택 해제를 지원한다. |
| 지도 bottom sheet `길찾기` | 완료 | Kakao Map 외부 링크 | `placeUrl`이 있으면 해당 URL, 없으면 Kakao 지도 검색 URL을 새 탭으로 연다. |
| 지도 bottom sheet `상세 보기` | 완료 | 로컬 장소 상세 dialog | 선택한 장소의 day context, 시간, 카테고리, 주소, 메모, 좌표, Kakao Maps 링크를 inspectable dialog로 표시한다. |
| 로딩/오류 상태 | 완료 | `useAsyncResource()` 상태 UI | 상세 로딩 중 `일정 상세를 불러오는 중입니다`, 오류/404 시 `일정 목록으로` 액션을 제공한다. |

### 데이터/API 연결 현황

| 데이터/동작 | 개발 상태 | API/로직 |
| --- | --- | --- |
| 일정 상세 조회 | 완료 | `appDataApi.getTrip(tripId)` → `GET /api/trips/{tripId}` |
| 연결 정책 해제 | 완료 | `appDataApi.removePolicyFromTrip(trip.id, policy.slug)` → `DELETE /api/trips/{tripId}/policies/{policySlug}` |
| 장소 추가 | 완료 | `appDataApi.addTripPlace(trip.id, dayNumber, { ...payload, expectedRevision: trip.revision })` → `POST /api/trips/{tripId}/days/{dayNumber}/places` |
| 장소 수정 | 완료 | `appDataApi.updateTripPlace(trip.id, place.id, { ...payload, expectedRevision: trip.revision })` → `PATCH /api/trips/{tripId}/places/{placeId}` |
| 장소 이동 | 완료 | `appDataApi.moveTripPlace(trip.id, place.id, { dayNumber, position, expectedRevision: trip.revision })` → `PATCH /api/trips/{tripId}/places/{placeId}/move` |
| 장소 삭제 | 완료 | `appDataApi.deleteTripPlace(trip.id, place.id, trip.revision)` → `DELETE /api/trips/{tripId}/places/{placeId}?expectedRevision=...` |
| 친구 초대 진입 | 완료 | `/friend-invite?tripId={tripId}` 화면 이동. 초대 상태 API는 친구 초대 화면에서 사용한다. |
| AI 추천 후보 진입 | 완료 | `/ai-results?tripId={tripId}` 화면 이동. 추천 후보 API는 AI 결과 화면에서 `GET /api/trips/{tripId}/recommendations`를 호출한다. |
| 지도 표시 | 완료 | 장소의 `latitude`, `longitude`, `address`, `placeUrl`, `externalPlaceId` 등 Kakao place metadata를 `KakaoMapView` marker로 전달한다. |
| URL 상태 복원 | 완료 | `day`, `view`, `place` query를 읽고 선택 day/표시 방식/선택 marker를 복원한다. |

### 보고용 요약

일정 상세 화면은 내부 trip id 기반 `/trips/{tripId}` route에서 현재 사용자가 접근 가능한 일정 하나를 조회해 일정 날짜, 참여자, 연결 정책, 추천 정책, Day별 장소를 관리하는 화면이다. owner/editor는 장소를 추가·수정·삭제·이동할 수 있고 정책 연결도 해제할 수 있으며, viewer는 읽기 전용 안내와 함께 일정/정책 확인만 가능하다. 장소는 리스트와 지도 두 방식으로 볼 수 있고, 지도는 Kakao Maps SDK를 우선 사용하되 좌표/SDK 제약이 있을 때 fallback SVG 지도를 유지한다. AI 추천 후보 추가와 친구 초대는 각각 별도 화면으로 현재 `tripId`를 전달하는 진입 링크로 구현되어 있다.

### 확인 근거

- `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`: 일정 상세 조회, 연결 정책, Day 탭, 리스트/지도 전환, 장소 CRUD/move, draft, viewer read-only, Kakao 지도/fallback, 지도 bottom sheet 장소 상세 dialog 구현
- `frontend/src/pages/ItineraryPages.tsx`: `ItineraryDetailPage` route export
- `frontend/src/app/App.tsx`: `/trips/:tripId` protected route 구성
- `frontend/src/api/backendApi.ts`: 일정 상세, 장소 추가/수정/이동/삭제, 정책 연결 해제 API 연결
- `frontend/src/components/map/KakaoMapView.tsx`: Kakao Map SDK marker 렌더링과 fallback 처리
- `frontend/src/utils/draftStorage.ts`: 장소 추가/수정 draft 저장/복원 유틸
- `frontend/src/App.test.tsx`: 일정 상세 렌더링, 장소 추가/수정/삭제/이동, viewer 읽기 전용, draft 복원/삭제, 지도/추천 후보 진입 관련 회귀 테스트
- `backend/app/api/routes/trips.py`: `GET /trips/{trip_id}`, 장소 CRUD/move, 정책 연결 해제 route 구현
- `backend/app/services/trips.py`: trip 접근 권한, owner/editor/viewer 권한, 장소/정책 연결 business logic 구현
- `docs/mvp-api-contract.md`: 일정 상세, 장소 CRUD/move, 정책 연결/해제, 추천 후보 API 계약 문서화

### 2026-05-29 로컬 검증 결과

- 코드 근거 확인: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`, `frontend/src/api/backendApi.ts`, `backend/app/api/routes/trips.py`, `backend/app/services/trips.py`, `docs/mvp-api-contract.md`
- 테스트 근거 확인: `frontend/src/App.test.tsx`에 `/trips/{tripId}` 상세 표시, viewer read-only, 장소 추가/수정/삭제/이동, draft, AI 추천 진입, 지도 장소 상세 dialog 관련 회귀 테스트가 존재한다.
- 이번 문서 작성 턴에서는 기능 코드를 변경하지 않았고, 실행 중인 브라우저/API 신규 smoke는 추가 수행하지 않았다.

### 남은 작업/리스크

- `tripId`는 내부 numeric string id 기준이다. 정책처럼 public slug를 쓰지 않으므로 보고/시연 자료에서도 `/trips/{id}`로 표현해야 한다.
- 지도 모드는 Kakao Maps JavaScript key, 도메인 등록, 장소 좌표/주소 품질에 영향을 받는다. 좌표가 없거나 SDK 로드가 실패하면 fallback 지도/검색 기반 표시가 사용된다.
- 지도 bottom sheet의 `상세 보기`는 로컬 장소 상세 dialog로 동작한다. 별도 full-page 장소 상세 화면은 현재 범위가 아니다.
- AI 추천 후보 생성/조회 품질은 `/ai-results` 및 `GET /api/trips/{tripId}/recommendations`의 별도 동작에 의존한다. 일정 상세 화면 자체는 추천 후보 화면으로 이동시키는 진입점이다.
- viewer 권한 사용자는 확인만 가능하며 장소 편집과 정책 연결 삭제는 제한된다.
