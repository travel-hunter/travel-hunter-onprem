# 섬 여행비 지원 신청 절차 안내 설계

## 배경

`2026 섬 방문의 해` 섬 여행비 지원(`island_visit`)은 신청서 한 장으로 끝나지 않는다. 공식 페이지(`https://www.visitisland.kr/promotion2`, 2026-09-14 확인) 기준 절차는 다음과 같다.

| 단계 | 공식 내용 |
|---|---|
| 01 신청 | 구글 폼 제출, **2차 마감 9월 21일 오후 6시**. 1팀(가족·친구·모임) 대표 1인 1회, 중복 신청 불가, 1차 선정자는 2차 제외 |
| 선정 | 추첨, 선정자에게 개별 문자 |
| 02 여행 | **10월 1일 ~ 11월 4일**, 대상 섬 리스트에 있는 "육지와 연결되지 않아 배로 들어가는 섬"에서 **1박 2일 이상**, 섬 내 등록 숙박업소(캠핑 가능), 결제 10만원 이상 |
| 03 서류 제출 | **여행 후 2주 이내** 서류 제출 구글 폼 + 만족도 조사. 선정 문자 수신자이면서 기간 내 여행자만 제출 가능 |
| 04 지급 | 서류 완비 후 영업일 10일 이내 계좌이체 10만원 |

필수 증빙: 신분증, 통장사본, 왕복 배편 승선권 또는 영수증, 실 결제 영수증(카드·현금영수증·송금 내역), OTA 이용 시 예약·결제 내역. 사진은 이름·주민등록번호·날짜·금액이 명확해야 한다.
지원 제외: 중복 신청, 중복 영수증, 허위 증빙, 간이영수증·계좌이체 내역만 제출, 타 숙박 할인·지원사업 중복, 육지와 연결된 섬, 승선권·영수증 미증빙, 비인가 업소 영수증, 법인카드.

현재 서비스는 이 정책을 카드 한 장(`structuredDetail` 비어 있음, `mapper_status = missing`)으로만 보여 주고, 사용자가 어디까지 진행했는지 기록할 곳이 없다(`TripPolicy`는 링크만, 진행 상태 필드 없음).

## 목표

1. **공개 안내**: 정책 상세에서 위 4단계, 기간·마감, 필요 서류, 제외 기준, 신청/서류 제출 폼 링크를 공식 수집값으로 보여 준다.
2. **내 일정 기준 진행 관리**: 섬 정책을 담은 일정에서 팀 단위로 "신청함 → 선정/미선정 → 여행 완료 → 서류 제출 → 지급 확인"을 체크하고, 서류 체크리스트와 **내 일정으로 계산한 조건 점검**(여행 기간·박수·대상 섬 포함·서류 마감 D-day)을 보여 준다.

## 결정 (추천 기본값 — 사용자 확인 필요 항목은 맨 아래)

- 진행 상태는 **일정(팀) 단위**다. 공식 규칙이 "1팀 대표 1인 1회"라 개인 단위로 두면 같은 일정 멤버끼리 중복 신청을 막지 못한다. 일정 편집 권한자가 갱신한다.
- **증빙 파일은 받지 않는다.** 신분증·통장사본을 서버에 올리는 순간 민감 개인정보 보관 책임이 생긴다. 서비스는 체크리스트와 공식 폼 링크까지만 제공한다.
- 절차 데이터는 **수집 + 관리자 검토**를 거친다. 폼 링크·기간·서류 목록은 회차마다 바뀌므로 코드에 고정하지 않는다. 절차가 바뀐 수집 후보는 자동 발행 게이트에서 항상 보류한다.
- 신청·제출은 **공식 구글 폼으로 연결만** 한다(대리 제출·자동 입력 없음).
- 알림(마감 푸시)은 이번 범위 밖이다. 알림 런타임이 제거된 상태이므로 앱 내 D-day 표시로 대신한다.

## 데이터

### 공개 절차 (정책 단위)

- `island_visit_parser`가 `raw_payload.procedure`에 추가 저장:
  - `rounds`: `[{key: "2", applyUntil: "2026-09-21T18:00", travelStart, travelEnd, applicationFormUrl, documentFormUrl}]` — 페이지에 1차·2차가 함께 있으므로 회차별로 파싱하고, 오늘 기준 **진행 중이거나 다음 회차**를 대표로 쓴다.
  - `documentDeadlineDaysAfterTrip: 14`, `minNights: 1`, `minPaymentKrw: 100000`
  - `requiredDocuments: [..]`, `exclusions: [..]`, `contacts: {email, phones}`
  - 폼 링크는 **HTML 주석 밖**에 있고 호스트가 `forms.gle` 또는 `docs.google.com/forms`일 때만 채택(페이지에 주석 처리된 옛 버튼이 남아 있음).
  - 필수 항목(현재 회차 신청 마감·여행 기간·서류 제출 기한) 중 하나라도 못 찾으면 `IslandVisitParserChangedError` → 기존대로 `parser_changed`.
- `structuredDetail`에 새 섹션 `applicationSteps`를 추가한다(다른 정책도 관리자 편집으로 쓸 수 있는 일반 섹션). 항목 키는 기존 허용 키(`title/label/description/url/startDate/endDate/type`)만 사용하고, `type`은 `apply | selection | travel | documents | payout`.
- `island_visit` 전용 mapper를 `policy_semantic_mapping._MAPPERS`에 추가해 `supportContent`(10만원, 조건), `periods`(신청 마감·여행 기간·서류 제출 기한), `applicationTarget`(1팀 1인, 대상 섬 1박 2일 이상, 등록 숙박업소, 결제 10만원 이상), `requiredDocuments`, `notes`(제외 기준·사진 요건·문의처), `applicationSteps`를 채운다. 신청 폼 링크는 `applyUrl`로 승격해 기존 "신청하러 가기" CTA가 동작하게 한다.
- `evidence_fingerprint`에 `procedure` 해시를 포함해 폼 링크·기간·서류가 바뀌면 새 검토 후보가 생기게 하고, 자동 발행 게이트에 `procedure_changed` 보류 사유를 추가한다.

### 진행 상태 (일정 단위, 마이그레이션 `0042_trip_policy_application`)

`trip_policies`에 컬럼 추가(행 추가 없음):

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `application_status` | String(24) nullable, CHECK | `not_started` · `applied` · `selected` · `not_selected` · `traveled` · `documents_submitted` · `paid` |
| `application_checklist` | JSON(B) nullable | `{ "<documentKey>": true }` — 체크 여부만, 파일·번호 없음 |
| `application_updated_at` | DateTime nullable | |
| `application_updated_by_user_id` | BigInteger FK users SET NULL | |

상태 전이는 서버에서 검증한다: `not_started → applied → (selected | not_selected)`, `selected → traveled → documents_submitted → paid`, 한 단계 되돌리기 허용. `not_selected`는 종료.

### 계산 점검 (저장하지 않음)

`linkedPolicies[]`의 섬 정책 항목에 `application` 객체를 붙인다.

- `inTravelWindow`: 일정 `start_date`~`end_date`가 대표 회차 여행 기간 안인가
- `meetsMinNights`: `end_date > start_date`
- `eligibleIslandMatched`: 일정 장소 중 승인된 대상 섬과 정확 일치하는 곳이 있는가(기존 `_matches_approved_island` 재사용)
- `applyDeadline`: 대표 회차 신청 마감, `documentsDueDate`: `end_date + 14일`
- `status`, `checklist`, `requiredDocuments`(키·라벨)

## API

- `GET /api/policies/{slug}`: `structuredDetail.applicationSteps` 추가(island_visit은 채워짐, 나머지는 빈 배열).
- `GET /api/trips/{id}`: `linkedPolicies[]`에 `deadline`(기존 누락)과 섬 정책일 때 `application` 추가.
- `PATCH /api/trips/{id}/policies/{slug}/application` (편집자): `{ status?, checklist? }`. 허용되지 않은 전이는 409, 섬 정책이 아니면 404, 알 수 없는 서류 키는 422. 일정 행을 잠가 동시 수정 직렬화.
- `GET /api/me/applied-policy-links`: `linkedTrips[]`에 `applicationStatus` 추가.

## 화면

- **정책 상세**: `신청 절차` 섹션(4단계 스텝, 단계별 기간과 마감 D-day), `신청 폼 열기`/`서류 제출 폼 열기` 버튼(서류 폼 옆에 "선정 문자를 받은 분만 제출 가능" 경고), 기존 필요서류·비고 섹션은 수집값으로 채워짐.
- **일정 상세 > 연결된 정책**: 섬 정책 카드에 `신청 진행` 패널 — 현재 단계 스텝퍼와 다음 행동 버튼, 조건 점검 4줄(✓/⚠), 서류 체크리스트, `서류 제출 D-n`.
- **신청한 정책 목록**: 일정별 진행 상태 배지.
- 증빙 업로드 UI는 만들지 않는다. "사진은 이름·주민번호·날짜·금액이 보이게" 안내 문구만 둔다.

## 제외

증빙 파일 업로드·보관, 구글 폼 대리 제출, 선정 문자 연동, 푸시/이메일 알림, 섬 정책 외 다른 정책의 진행 관리(데이터 구조는 일반화하되 UI는 섬 정책만).

## 위험

- 공식 페이지가 1차·2차·주석 블록이 섞인 비정형 HTML이다 → 회차 단위 파싱 + 필수 항목 누락 시 `parser_changed`, 절차 변경은 항상 사람 검토.
- 폼 링크가 회차마다 바뀐다 → 지문에 포함, 관리자가 승인해야 공개.
- 일정 멤버 여러 명이 상태를 바꿀 수 있다 → 편집자만, 마지막 수정자·시각 표시.

## 테스트 기준

1. 2026-09-14에 저장한 공식 페이지 픽스처에서 2차 신청 마감·여행 기간·서류 기한 14일·서류 5종·제외 기준·폼 2개(주석 속 옛 링크 제외)를 파싱한다.
2. 필수 항목이 빠진 페이지는 `parser_changed`.
3. island_visit 정책 상세에 `applicationSteps` 5개와 `applyUrl`이 나오고, 다른 정책은 빈 배열·기존 CTA 그대로.
4. 폼 링크만 바뀐 수집은 새 후보 + `procedure_changed` 보류.
5. 진행 상태 전이 규칙, 편집자 권한, 알 수 없는 서류 키 422, 비섬 정책 404.
6. 조건 점검: 기간 밖 일정 ⚠, 당일치기 ⚠, 대상 섬 없는 일정 ⚠, 서류 마감 = 종료일+14.
7. 화면: 정책 상세 스텝·폼 버튼, 일정 상세 진행 패널 버튼·체크리스트 저장, 목록 배지.
