# 정책 상세 상단 CTA 및 표시 정리 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute task-by-task.

**Goal:** 정책 상세에서 신청과 일정 담기 행동을 사용자가 지원 내용을 읽기 전에 찾을 수 있게 하고, 하단 고정 바와 화면 전체 폭 점유를 없앤다. 수집된 정책 텍스트와 API 데이터는 변경하지 않는다.

**Architecture:** `PolicyPages.tsx`의 기존 CTA 판정과 일정 담기 동작은 유지한다. CTA 그룹의 렌더 위치만 제목 블록 뒤·지원 내용 섹션 앞의 본문 흐름으로 옮긴다. CSS는 뷰포트 고정 바 대신 본문 폭 안에서 줄바꿈 가능한 액션 행을 제공한다.

## 확정 요구

- 위치: 정책 제목·주관기관 정보 바로 아래, **지원 내용** 바로 위.
- 표시: 신청 폼/공식 안내 버튼과 `내 일정에 담기`를 모두 표시한다.
- 크기: 앱 본문 가로폭을 넘지 않는다. 좁은 화면에서는 버튼이 줄바꿈되어도 잘리거나 가로 스크롤이 생기지 않는다.
- 제거: 하단 고정 CTA, 하단 내비게이션 회피용 추가 여백, 뷰포트 전체 폭 CTA 스타일.
- 유지: 신청 가능 여부 판정, 비활성 사유 안내, 외부 링크·일정 담기 동작, 수집된 카드/상세 텍스트.
- 함께 유지하는 표시 원칙: 기간은 정보 행이므로 점·체크 표시를 붙이지 않고, 자격/완료 목록만 체크 표시를 쓴다. 상단 금액과 동일한 `최대 N원 혜택` 행만 화면에서 중복 제거한다.

## 범위

- Modify: `frontend/src/pages/PolicyPages.tsx`
- Modify: `frontend/src/styles/app.css`
- Modify: `frontend/src/app/__tests__/policy-detail.test.tsx`
- No API, backend, DB, crawler, normalization, or collected-text changes.
- Do not update `CHECKLIST.md` until this branch is merge-ready.

## Task 1 — 행동 계약을 테스트로 고정

1. 신청 가능한 섬 정책 fixture로 기간 뒤·지원 내용 앞 액션 영역을 찾는다.
2. 이 영역에 `신청 폼 열기`와 `내 일정에 담기`가 모두 있고 올바른 링크/버튼 동작을 유지함을 검증한다.
3. 기존 하단 `.sticky-cta`가 렌더되지 않음을 검증한다.
4. 신청 불가 정책에서도 비활성 버튼과 연결된 도움말이 같은 상단 영역에 남음을 검증한다.
5. 기존 중복 금액·기간 마커 회귀 검증은 유지한다.

## Task 2 — CTA를 본문 상단 액션 행으로 이동

1. `PolicyPages.tsx`에서 기존 CTA 판정과 버튼 JSX를 재사용해 기간 섹션 직후·지원 내용 직전에 렌더한다.
2. 도움말은 액션 행의 위 또는 아래에, 해당 비활성 제어와 `aria-describedby`로 연결한 채 둔다.
3. 화면 마지막의 `.sticky-cta` 렌더를 제거한다.
4. CSS에 `.policy-detail-actions`를 만들고 `display:flex; flex-wrap:wrap`으로 구성한다. 각 버튼은 터치 가능한 최소 높이를 유지하되, 본문 폭 안에서만 성장하도록 한다.
5. `.detail-body`의 고정 CTA 전용 하단 여백을 일반 상세 여백으로 되돌린다.

## Task 3 — 검증

1. `cd frontend && npx vitest run src/app/__tests__/policy-detail.test.tsx`
2. `npm run typecheck`, `npm run build`, `npm run test:mojibake`, `git diff --check`.
3. 로그인한 5173에서 신청 가능한 정책 상세를 360px, 390px, 430px, 데스크톱 폭으로 확인한다.
4. 확인 항목: 첫 화면 스크롤 없이 버튼이 보임, 지원 내용보다 위임, 모든 버튼이 보임, 좁은 폭 줄바꿈·가로 스크롤 없음, 신청 불가 안내 유지, 하단에 중복 CTA 없음.

## 완료 조건

- 수집 데이터·API 계약·카드 텍스트에 변경이 없다.
- 신청과 일정 담기 제어가 지원 내용 바로 위에 함께 있다.
- 작은 화면에서 액션이 잘리지 않고 전체 화면 폭 고정 바가 없다.
- 테스트와 정적 검증 결과가 새로 기록된다.
