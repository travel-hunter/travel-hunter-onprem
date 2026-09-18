# 전국 정책 분리 — 지역 집계에서 빼고 홈에 '전국 혜택' 칸

## Context

전국 정책(현재 개발서버 활성 12건: 교통 11·섬 1)이 **17개 시도 전부에 합산**된다. 지도 건수, 시트의 지역 카드, 지역을 눌렀을 때 목록과 표시 알약까지 같은 12건이 매 지역에 반복돼 "이 지역에 정책이 몇 개인가"가 왜곡된다. 사용자 결정(2026-09-18):

- 전국 정책은 **홈에 '전국 혜택' 칸**으로 따로 보여준다.
- 지역 건수·지역 카드·지역 목록에서는 **완전히 뺀다**.

부수 효과: 전국 카드에 지역 사진을 붙이려던 `feature/policy-photo-nationwide-fix` 는 필요 없어진다(전국은 지역이 아니라 혜택 종류가 정체성 — 이모지 타일이 맞다).

## 바뀌는 곳 — 프런트 3곳 + 홈 1곳

전국을 지역에 섞는 코드는 정확히 세 군데다(조사 결과). 백엔드는 안 건드린다.

| # | 파일:줄 | 지금 | 바꿈 |
|---|---|---|---|
| 1 | `frontend/src/utils/policyPrograms.ts:30-49` `groupByRegion` | `items = [...own, ...nationwide]` — 모든 지역 카드에 전국 추가 | 전국을 빼고 `items = own`. `nationwide` 수집 코드 삭제. 정렬·`subLabel` 은 그대로 |
| 2 | `frontend/src/pages/PolicyPages.tsx:775-789` `regionCounts` | `total = own + nationwide` | `total = own`. `RegionCount { own, total }` 타입·엔진은 그대로(둘이 같아질 뿐) |
| 3 | `frontend/src/pages/PolicyPages.tsx:897-900` `mapRegionPolicies` | `region === mapRegion \|\| region === 전국` | `region === mapRegion` 만. 이걸 먹는 `pillGroups`·`selectedRegionTotal` 은 자동으로 전국이 빠진다 |
| 4 | `frontend/src/pages/HomePage.tsx:183-188` 아래 | 없음 | **큰 카드 하나**(`NationwideBenefitCard`, HomePage 로컬 컴포넌트) — 머리(✈️ 전국 혜택 · N건) + 안에 전국 정책이 **줄로 나열**. 전국 정책 0건이면 카드 자체를 안 그린다 |

**홈 카드 모양 (사용자 결정 2026-09-18: "전국혜택 카테고리 큰 카드 안에 정책들이 나열")**

```
┌─────────────────────────────────────┐
│ ✈️ 전국 혜택               12건      │  ← 머리: 이모지(displayConfig 전국 "✈️")·제목·건수
├─────────────────────────────────────┤
│ 🚌 내일로패스 할인      최대 2만원  D-14 │  ← 줄 1건 = Link → /policies/{slug}
│ 🚌 테마열차 할인        최대 50%   D-30 │     왼쪽 카테고리 이모지(getPolicyMoodIcon), 제목 1줄 말줄임,
│ 🛏 2026 섬 여행비 지원   최대 30만원 D-45 │     오른쪽 amount + 마감 태그(formatPolicyDeadlineTag)
│ 🚌 인구감소지역 자동차 …  최대 3만P  D-60 │
│ 🚌 자유여행상품 할인     최대 100%  상시 │
├─────────────────────────────────────┤
│           전체 12건 보기 →           │  ← Link → /policies?region=전국 (5건 이하면 이 줄 없음)
└─────────────────────────────────────┘
```

- 겉은 `SurfaceCard`(`components/cards.tsx` 가 이미 씀), 줄은 `<Link>` + 기존 헬퍼(`getPolicyMoodIcon`, `formatPolicyDeadlineTag`) 재사용. 새 컴포넌트는 HomePage 안 로컬 함수 하나, CSS 는 `app.css` 에 `.prototype-home-nationwide-*` 몇 규칙(카드 머리·줄·꼬리).
- 줄 수 상한 `NATIONWIDE_HOME_ROWS = 5`(상수 하나). 마감 임박 순 정렬은 기존 `compareDeadlineHomePolicies`(`data/displayConfig.ts`) 재사용.
- `nationwidePolicies = policies.filter(p => p.region === NATIONWIDE_REGION)` — `utils/policyPrograms.ts:7` 의 상수를 import 한다. `PolicyPages.tsx:55` 의 중복 상수 `nationwideRegion` 도 이 import 로 바꾼다(정리).
- 위치: **인사말 바로 아래 맨 위**(사용자 결정 2026-09-18). 히어로 카드는 없앤다.

## 홈 구성 변경 (같은 작업에 포함, 사용자 결정 2026-09-18)

지금 홈의 "인기"는 근거가 없다 — 히어로 "이번 주 인기 정책"은 코드에 박힌 slug 아니면 목록 첫 건(`data/displayConfig.ts:124-126`), "이번 주 혜택"은 `match ≥ 90` 우선인데 백엔드가 `match` 를 전부 90으로 내려(`services/policies.py:143`) 사실상 전체 통과 후 마감순이다.

새 순서:
1. 인사말
2. **전국 혜택 큰 카드** (위 설계)
3. **`내 관심 지역 혜택`** — `profile.preferredRegions`(`HomePage.tsx:86-91`, 이미 씀)에 속한 지역 정책을 마감순으로 3건. 관심 지역이 없거나 해당 정책이 0건이면 제목을 `마감 임박 혜택` 으로 바꾸고 전체 지역 정책 마감순 3건. 전국 정책은 이 목록에서 뺀다(위 카드에 있음). `더보기` → `/policies`.
4. AI 추천 맞춤 일정 (그대로)
5. 프로필 완료 모달 (그대로)

구현:
- `data/displayConfig.ts` `getHomeBenefitPolicies(policies, limit)` → `getHomeBenefitPolicies(policies, limit, preferredRegions)` 로 바꾸고 `match` 기준(`HOME_RECOMMENDED_POLICY_MATCH_THRESHOLD`, `compareRecommendedHomePolicies`)은 삭제. 반환에 `{ policies, title }` 또는 폴백 여부 플래그를 실어 제목을 정한다. `compareDeadlineHomePolicies` 재사용.
- `getFeaturedPolicy`·`featuredPolicySlug`·히어로 JSX(`HomePage.tsx:160-181`)·관련 CSS(`.prototype-home-hero*`) 삭제. 다른 사용처가 있으면 grep 으로 확인 후 정리.
- 히어로 삭제로 남는 사용처가 없어지는 `homePolicyIcons` 등은 손대지 않는다(범위 밖).
- "더보기" 링크는 목록 필터가 데이터에서 지역을 뽑으므로(`PolicyPages.tsx:770-773`) `?region=전국` 이 "기타" 그룹으로 이미 존재하고, 필터는 정확 일치(`:819`)라 전국만 보인다.
- 시트의 "정책별" 보기, 목록 "전체" 보기, 정책 상세, 일정 만들기 링크(`getPolicyTripRegionQuery`)는 변경 없음 — 전국 정책은 거기서 계속 보인다.

## 테스트

- `frontend/src/app/__tests__/policies.test.tsx:211-215` — "전국 정책은 어느 지역 타일을 열어도 같이 들어 있다" 를 **반대로**: 강원 타일에 전국 정책이 없다.
- 같은 파일 지도 선택 왕복 테스트 — 선택 지역 건수·알약에 전국이 안 섞이는 단언 추가(기존 픽스처에 전국 1건 있음, `:189`).
- `frontend/src/app/__tests__/home.test.tsx` — 전국 정책이 있으면 "전국 혜택" 카드에 건수와 정책 줄(상세 링크)이 보이고, 6건 이상이면 "전체 N건 보기" 가 `/policies?region=전국` 을 가리킨다; 전국 정책이 없으면 카드가 없다. 관심 지역이 있으면 "내 관심 지역 혜택" 제목과 그 지역 정책만; 없으면 "마감 임박 혜택" 제목과 마감순. 히어로("이번 주 인기 정책")가 없다. 기존 히어로·"이번 주 혜택" 단언은 제거·교체.
- `PolicyRegionMap.test.tsx:32-37` (own/total 분리, 엔진) — 변경 없음, 그대로 통과해야 한다.
- 백엔드 테스트 변경 없음.

## 문서

- `docs/implemented-feature-spec.md` — 정책 탭·홈 설명에 "전국 정책은 지역 집계에 포함하지 않고 홈 '전국 혜택' 칸에서 본다" 한 줄. (API 계약 변경 없음 → `mvp-api-contract.md`·`.agent/evals` 손대지 않음.)
- `docs/superpowers/plans/2026-09-17-policy-card-photo-gaps.md` "B 후속" 절 — "전국 카드는 설계상 사진 없음(이모지 타일), 분리 계획으로 대체" 로 정정.

## 정리(같이 처리)

- `feature/policy-photo-nationwide-fix` 브랜치·작업 폴더 삭제(커밋 없음). 개발서버 컨테이너에 임시로 넣은 스크립트는 다음 Jenkins 배포에서 사라지므로 손대지 않는다.
- PR #75 로 들어간 전국 백필 키(`(전국, "")`)는 결과를 못 내지만 무해하다. 로그의 `no_photo sido=전국` 한 줄이 거슬리면 후속에서 전국 키 생성을 다시 빼면 된다 — 이번 범위 밖.

## 검증

1. `cd frontend && npm run typecheck && npm test && npm run build && npm run test:mojibake`, `git diff --check`
2. 4174(작업 폴더 vite, 로컬 백엔드 8000)에서:
   - 홈: 인사말 → "전국 혜택" 큰 카드(줄 클릭 → 상세, "전체 N건 보기" → `/policies?region=전국`) → "내 관심 지역 혜택"(관심 지역 없으면 "마감 임박 혜택") → AI 추천. 히어로 없음. 제목이 길어도 1줄 말줄임, 360px 에서 amount·마감 태그가 줄바꿈 없이 붙는지. 관심 지역을 바꿔(마이페이지) 목록이 따라오는지
   - 정책 탭 지도: 지역 건수가 지역 정책만(예: 개발서버 기준 대구는 `own 0`이라 흐림 유지), 지역 눌렀을 때 목록·알약에 전국 없음
   - 시트 "지역별": 각 지역 카드 건수에서 전국 12건이 빠짐, "정책별" 은 그대로
   - 360·390·430·1024·1440px 에서 홈 칸 가로 넘침 없음
   - 로컬 DB 에 전국 정책이 없으면(현재 0건) 홈 칸이 안 보이는 것이 정상 — 개발서버 머지 뒤 실제 확인
3. 커밋은 테스트 통과 + 사용자 확인 뒤. push·PR 은 지시 있을 때.

## 하지 않는 것

- 백엔드 `travel_areas.policyCount` 에 전국이 더해지는 것(여행 지역 추천) — 별건, 필요하면 다음 계획.
- 전국 정책 사진(지역·카테고리 사진) — 하지 않는다. 이모지 타일 유지.
- 홈 칸 전용 디자인·캐러셀 — 기존 세로 목록 재사용.

---

## 구현 결과 (2026-09-18)

브랜치 `feature/nationwide-home-card`, 8파일. 백엔드 변경 없음.

- `policyPrograms.ts` `groupByRegion`: 전국 합산 제거. `PolicyPages.tsx`: `regionCounts.total = own`, `mapRegionPolicies` 정확 일치, 중복 상수 `nationwideRegion` → `NATIONWIDE_REGION` import.
- `displayConfig.ts`: `getHomeBenefitPolicies(policies, limit, preferredRegions) → { title, policies }`, `getNationwideHomePolicies` 추가. `match` 기반 선별·`getFeaturedPolicy`·`featuredPolicySlug` 삭제.
- `HomePage.tsx`: 히어로 제거, `NationwideBenefitCard`(줄 5개 + "전체 N건 보기"), 목록 제목을 선별 규칙이 정함. 목록 aria-label `추천 혜택 정책 목록`.
- `app.css`: 히어로 CSS 블록 삭제(≈120줄), 전국 카드 스타일 추가.
- 테스트: `home.test.tsx` 히어로·"이번 주 혜택" 단언 교체, "추천 우선" 테스트를 "관심 지역 우선"·"폴백+긴 전국 목록 접기" 두 개로 교체. `policies.test.tsx` 강원 타일에 전국 없음 단언.
- 문서: `implemented-feature-spec.md` 홈 설명 갱신.

관문: typecheck·build·mojibake·`git diff --check` 통과, vitest **417/417**. 백엔드는 안 건드려 pytest 생략.
런타임: 4174 = 이 작업 폴더 vite(로컬 백엔드 8000). 로컬 DB 에 전국 정책이 0건이라 홈 전국 카드는 로컬에서 안 보이고, 관심 지역이 없는 계정은 "마감 임박 혜택" 이 보이는 것이 정상. 전국 카드·"내 관심 지역 혜택" 은 테스트로 검증했고 실제 화면은 머지 뒤 개발서버(전국 12건)에서 확인.
정리: `feature/policy-photo-nationwide-fix` 브랜치·작업 폴더는 커밋 뒤 삭제.

---

## 설계 변경 (2026-09-18 오후, 사용자 결정)

홈의 전국 카드는 **정책 줄을 담지 않는다.** 카드 한 장(제목·건수·나중에 넣을 그림 자리)만 두고,
누르면 `/policies?region=전국` 으로 이동해 정책 탭 목록(기존 카드·필터)에서 전국 정책을 본다.
홈 안 시트로 펼치는 안은 사용자가 배제. `NATIONWIDE_HOME_ROWS`·줄 마크업·"전체 N건 보기" 는 삭제.
카드는 `<Link>` 하나 — 접근성 이름 "전국 혜택 N건 보기". 그림·사진 자리는 `.prototype-home-nationwide-visual`
(지금은 ✈️ 이모지), 추후 이미지로 교체.
테스트: 카드가 링크이고 href·건수를 보이며 정책 줄이 없다는 것으로 교체.

기존 결함 메모: `home.test.tsx > uses the generic fallback AI trip card…` 는 변경 없는 develop 에서도 같은 로컬 DB 로 실패한다
(`listRegionRecommendations` 호출 기대). 로컬 DB 를 개발서버 복사본으로 바꾼 뒤 상태가 달라진 영향으로 보이며 이 브랜치와 무관. 별건.
