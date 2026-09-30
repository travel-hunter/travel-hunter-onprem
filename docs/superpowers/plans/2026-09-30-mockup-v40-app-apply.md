# 시안 v40(홈·정책·일정) 앱 반영 계획

시안: https://claude.ai/artifact/BAPGExyD8otfWpH6aqxVZF (v40). 소스 보존: `D:\travel-hunter-review\2026-09-29-service-audit\policy-tab-mock\`.
목표: 시안을 실제 React 앱에 옮기고, 로컬 4173(빌드본)에서 사용자가 화면별로 테스트한다.

## 원칙

- **프론트엔드만 고친다.** API 모양·DB·백엔드는 그대로 둔다(계약·스키마·evals 변경 없음).
  - "어울리는 정책"·목록의 "추천 혜택 N건"은 **서버가 이미 주는 `trip.recommendedPolicies`(담기 규칙과 같은 판별, 최대 3건)** 를 그대로 쓴다(2026-09-30 사용자 결정). 처음 계획한 '화면에서 세기'는 서버 권역 판별을 프론트에 다시 짜야 해서 버렸다. 0건이면 표시하지 않는다.
  - 백엔드 규칙(지역이 다르면 담기 거부 409, 숙박 할인 일정당 1건)은 이미 develop 에 있어 자동으로 지켜진다. 화면은 그 결과를 미리 보여 주기만 한다.
- **라우트는 그대로.** `/home`, `/policies`, `/policies/:policyId`, `/trips`, `/trips/:id`, 만들기 경로. 새 페이지를 옆에 만들지 않고 기존 컴포넌트를 고친다.
- **층 방식 뒤로가기는 URL 검색 파라미터로.** 지역·시군·시트 높이·묶음을 `useSearchParams` 로 쌓으면 브라우저·기기 뒤로가 그대로 한 층씩 내려간다. 시안의 `history.state.th` 방식은 아티팩트용 우회라 옮기지 않는다.
- **색은 청록 하나.** 시안의 '고급스러운' 전환은 비교용이라 앱에 넣지 않는다.
- **시안에 없는 로딩·빈 상태·오류 화면은 앱 것을 그대로 둔다.**
- **두 폭에서 확인한다.** 390px(탭바 있음), 768px 이상(탭바 없음, 스크롤은 `.app-container`).
- **일정 상세 지도는 앱의 카카오 지도 그대로.** 시안의 대신 그린 지도는 옮기지 않는다.
- 파일 수정은 Edit/Write 로만 한다(파이썬 재작성은 CRLF 를 만든다). 한글 UTF-8 확인.

## 단계 (화면 하나 = 브랜치 하나 = PR 하나)

| 단계 | 브랜치 | 바꾸는 것 | 주요 파일 | 깨질 시험 |
|---|---|---|---|---|
| 1 일정 | `feature/trip-tab-redesign` | 목록: 상태 칩(D-n·여행 중·다녀옴), ⋯ 메뉴(편집·삭제), "쓸 수 있는 혜택 N건", 날짜순 한 목록. 상세: 44px 뒤로, "기간 바꾸기" → **이미 있는** 여행기간 수정 창, 연결된 정책·어울리는 정책 짧게(가로 5장 + 정책 탭에서 모두 보기), "N명 참여 중". 만들기: 앱 2단계 유지, 2단계 문구 정리, 만드는 동안 탭바 가림 | `ItineraryListPage.tsx`, `ItineraryDetailPage.tsx`(머리·기간 버튼·정책 두 절**만**), `ItineraryCreatePage.tsx`, `AppLayout.tsx`, 새 `utils/tripBenefits.ts`(+시험) | e2e 제목 "여행 정보를 한 번에 확인해요" |
| 2 홈 | `feature/home-redesign` | 팝업 → 닫는 배너, 마감이 가까운 혜택 사업별 가로 카드, 미니 지도 + 지역 사진 카드, 전국 공통·일정 만들기 한 줄 카드 | `HomePage.tsx`, `regionPhotos.ts`(재사용) | e2e "추천 홈 보기", "즐겨찾기 정책" 영역 확인 |
| 3 정책 상세 | `feature/policy-detail-redesign` | 머리 지역 사진, 혜택 문구 정리(시안 `benefit_text.py` 규칙을 TS 로 옮김: 첫 문장·틀 문구 제거·제휴처 줄마다 링크·기간·대상·서류), 주 버튼 "내 일정에 담기" 하나, 담기 창에 지역 불일치·숙박 1건 표시 | `PolicyPages.tsx`(상세만), 새 `utils/policyDetailText.ts`(+시험), `tripPolicyApplication.tsx` | e2e "혜택 안내 보기" |
| 4 정책 탭 | `feature/policy-map-redesign` | 시트 세 자리, 사업별 묶기 기본 + 고정 줄, 혜택 형태 그림 8개, 도 떠오름·시군 점 74곳, 지역 요약 카드 사진 배경, 돋보기(검색+지역 목록), 교통 칩 규칙, 층 뒤로. 크면 4a(목록·카드·묶기)·4b(지도·시트)로 나눈다 | `PolicyPages.tsx`(목록), `PolicyMapSheet.tsx`, `PolicyRegionMap.tsx`, `regionMapEngine.ts`, `policy-map.css`, 새 `sigunPoints.ts`(시군청 좌표 74곳, 생성 방법 주석) | `PolicyMapSheet.test.tsx`, `PolicyRegionMap.test.tsx`, e2e "정책 검색"·"필터 열기" |

순서 이유: 일정이 가장 작고 다른 화면과 떨어져 있다. 정책 탭이 가장 크고, 홈·일정 링크의 도착지다. 정책 탭이 바뀌기 전까지 홈·일정 링크는 지금 있는 `/policies?region=` 화면으로 간다(이미 동작함).

## 로컬 실행(4173)

- develop 이 최신이고 추적 파일이 깨끗하므로 **루트에서 브랜치**를 만든다. compose 빌드 문맥이 루트라 워크트리보다 4173 연결이 단순하다.
- 단계마다: `docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml build frontend` → `up -d --no-deps frontend` → 번들에 새 클래스명이 들어갔는지 `curl` 로 확인 → 사용자에게 하드 리로드(Ctrl+Shift+R) 안내.
- 백엔드는 안 바뀌므로 다시 굽지 않는다. 로컬 DB 정책은 지금 것 그대로(개발서버 복사본).

## 검증(단계마다)

`npm run typecheck`, `npm test`, `npm run build`, `npm run test:e2e`(바뀐 문구 반영). 두 폭 캡처는 agent-browser 로 한 번. 그 뒤 사용자 테스트 체크리스트를 넘긴다. 커밋은 시험 통과 + 사용자 승인 뒤, 푸시·PR 은 지시가 있을 때만. `CHECKLIST.md` 는 머지 직전에만.

## 하지 않는 것

로그인·마이 시안, 디자인 토큰 정리, 백엔드 `recommendedPolicies` 수정, 수집 문제 3건(마감 지난 정책·숙박세일 섞임·교통 1.5만), 수달 헌터, 오류 알림.

## 남은 위험

- `ItineraryDetailPage.tsx` 가 6191줄이다. 1단계는 위에 적은 네 곳만 건드린다.
- 4단계는 지도 엔진(`regionMapEngine.ts`)을 다시 짜는 일이라 가장 크다. 기존 시험을 먼저 읽고 유지할 동작을 적은 뒤 시작한다.
- 여행 권역 카탈로그는 시도마다 따로 부른다. 일정 목록에 시도가 여럿이면 호출이 그만큼 는다(8개 일정 기준 몇 번).
