# Home Weekly Policy Card Readability A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/home`의 “이번 주 혜택” 정책 카드 A안을 실제 화면에 반영해 모바일에서 제목, 혜택, 기간, 조건이 더 빠르게 읽히게 만든다.

**Architecture:** 기존 `PrototypePolicyCard` 컴포넌트는 유지하고 카드 내부 정보 계층만 조정한다. 데이터 로직은 새로 만들지 않고 기존 `formatPolicyDeadlineTag`, `formatPolicyPeriodSummary`, `getPolicyCardSummary`, `getPolicyCardCondition` 흐름을 재사용한다. CSS는 기존 `.prototype-home-policy-*` 클래스 안에서 개선해 영향 범위를 `/home` 이번 주 혜택 카드로 제한한다.

**Tech Stack:** React, TypeScript, Vite, CSS, Vitest, Testing Library.

## Global Constraints

- 실제 앱 파일 수정은 사용자 승인 후 시작한다.
- 프론트엔드 데이터 접근은 기존 `AppDataApi` 경계를 유지한다.
- API DTO, 백엔드, DB 스키마는 변경하지 않는다.
- `/policies` 카드 로직과 충돌하지 않는다.
- 모바일 폭 360, 390, 430px에서 텍스트가 잘리거나 가로 스크롤이 생기지 않아야 한다.
- 기존 테스트 의도인 “디지털 관광주민증은 마감일 확인 필요로 보이지 않음”을 유지한다.

---

## 반영 방향 요약

### 현재 문제

현재 `/home` 이번 주 혜택 카드는 다음 정보가 비슷한 시각 무게로 들어간다.

- 아이콘
- 카테고리
- 제목
- 요약
- 기간 배지
- 조건 배지
- 금액/혜택명
- 마감 배지

이 때문에 모바일에서 첫눈에 읽어야 하는 `정책명`과 `실제 혜택`이 아래 정보들과 경쟁한다.

### A안 목표

카드 안의 정보 우선순위를 다음 순서로 고정한다.

1. 정책 타입과 상태: `관광 할인`, `상시 발급`
2. 정책 제목
3. 한 줄 요약
4. 핵심 혜택: `지역 제휴 혜택`, `최대 20만원 환급`
5. 보조 조건: `제휴처별 운영기간 확인`, `조건: ...`
6. 하단 CTA 느낌의 보조 텍스트: `상세 보기`, `바로 확인`

---

## File Structure

**Modify after approval:**

- `frontend/src/pages/HomePage.tsx`
  - `PrototypePolicyCard` 마크업을 A안 구조로 정리한다.
  - 기존 데이터 헬퍼는 유지한다.
  - 새 데이터 필드는 만들지 않는다.

- `frontend/src/styles/app.css`
  - `.prototype-home-policy-card` 내부 레이아웃을 A안 구조에 맞게 조정한다.
  - 제목, 요약, 혜택 배지, 보조 배지의 시각 계층을 분리한다.
  - 모바일 기준 줄바꿈, 클램프, 오버플로를 명확히 제한한다.

- `frontend/src/app/__tests__/home.test.tsx`
  - 현재 테스트가 CSS 구조에 과도하게 의존하지 않는지 확인한다.
  - 필요한 경우 A안에서 새로 생기는 CTA/혜택 텍스트를 검증한다.

**No backend files. No API contract changes.**

---

## 반영 예시

### Before: 현재 구조

```tsx
<Link className="prototype-home-policy-card" to={`/policies/${policy.slug}`}>
  <div className="prototype-home-policy-card-head">
    <div className="prototype-home-policy-label" aria-hidden="true">
      {getHomePolicyIcon(policy)}
    </div>
    <em className="prototype-home-policy-category">{policy.category}</em>
  </div>
  <div className="prototype-home-policy-card-copy">
    <strong>{policy.title}</strong>
    <p className="prototype-home-policy-summary">
      {getPolicyCardSummary(policy)}
    </p>
  </div>
  <div className="prototype-home-policy-card-meta">
    {scheduleLabel && (
      <span className="prototype-home-policy-schedule">
        {scheduleLabel}
      </span>
    )}
    <span className="prototype-home-policy-condition">
      조건: {getPolicyCardCondition(policy)}
    </span>
  </div>
  <small>
    <span>{policy.amount}</span>
    <span>{deadlineBadge}</span>
  </small>
</Link>
```

### After: A안 구조

```tsx
<Link className="prototype-home-policy-card" to={`/policies/${policy.slug}`}>
  <div className="prototype-home-policy-visual" aria-hidden="true">
    {getHomePolicyIcon(policy)}
  </div>

  <div className="prototype-home-policy-content">
    <div className="prototype-home-policy-kicker-row">
      <em className="prototype-home-policy-category">{policy.category}</em>
      <span className="prototype-home-policy-deadline">{deadlineBadge}</span>
    </div>

    <strong>{policy.title}</strong>

    <p className="prototype-home-policy-summary">
      {getPolicyCardSummary(policy)}
    </p>

    <span className="prototype-home-policy-benefit">{policy.amount}</span>
  </div>

  <div className="prototype-home-policy-card-meta">
    {scheduleLabel && (
      <span className="prototype-home-policy-schedule">
        {scheduleLabel}
      </span>
    )}
    <span className="prototype-home-policy-condition">
      조건: {getPolicyCardCondition(policy)}
    </span>
  </div>

  <small>
    <span>상세 보기</span>
    <span>바로 확인</span>
  </small>
</Link>
```

### 예상 화면 문구 예시

디지털 관광주민증 카드:

```text
[관광 할인] [상시 발급]
[하동] 디지털관광주민증 혜택
제휴처 방문 시 할인과 무료 혜택을 받을 수 있어요.
지역 제휴 혜택
[상시 발급 · 제휴처별 운영기간 확인] [조건: 디지털 관광주민증 발급]
상세 보기                         바로 확인
```

반값여행 카드:

```text
[관광 지원] [D-25]
[강진] 대한민국 반값여행 지원
강진 여행 후 공식 기준을 충족하면 여행 비용 일부를 환급받을 수 있어요.
최대 20만원 환급
[2026.8.31 마감] [조건: 사전 신청 관광객]
상세 보기                         바로 확인
```

---

## Task 1: Home Card Markup Regression

**Files:**
- Modify: `frontend/src/app/__tests__/home.test.tsx`

**Interfaces:**
- Consumes: rendered `/home` route with mocked `Policy[]`.
- Produces: regression coverage that A안 still shows digital tourism cards without `마감일 확인 필요` and exposes benefit text clearly.

- [ ] **Step 1: Add or adjust a failing structure-oriented test**

Add assertions to the existing digital tourism home-card test so it checks that the card exposes the main benefit text and readable CTA text.

```ts
expect(document.body).toHaveTextContent("지역 제휴 혜택");
expect(document.body).toHaveTextContent("상세 보기");
expect(document.body).toHaveTextContent("바로 확인");
expect(document.body).not.toHaveTextContent("마감일 확인 필요");
```

- [ ] **Step 2: Run the targeted test before implementation**

Run:

```bash
cd frontend
npx vitest run src/app/__tests__/home.test.tsx -t "shows digital resident policies as always-issued on the home hero and weekly cards"
```

Expected before implementation: existing assertions pass, new CTA assertions fail if `상세 보기` / `바로 확인` are not rendered yet.

---

## Task 2: Apply A안 Markup in HomePage

**Files:**
- Modify: `frontend/src/pages/HomePage.tsx`

**Interfaces:**
- Consumes: `Policy`, `formatPolicyDeadlineTag(policy)`, `formatPolicyPeriodSummary(policy)`, `getPolicyCardSummary(policy)`, `getPolicyCardCondition(policy)`.
- Produces: same `/policies/{policy.slug}` link target with clearer internal card hierarchy.

- [ ] **Step 1: Replace the internal markup of `PrototypePolicyCard`**

Use this structure:

```tsx
function PrototypePolicyCard({ policy }: { policy: Policy }) {
  const scheduleLabel = getHomePolicyScheduleLabel(policy);
  const deadlineBadge = getHomePolicyDeadlineBadge(policy);

  return (
    <Link
      className="prototype-home-policy-card"
      draggable={false}
      to={`/policies/${policy.slug}`}
    >
      <div className="prototype-home-policy-visual" aria-hidden="true">
        {getHomePolicyIcon(policy)}
      </div>

      <div className="prototype-home-policy-content">
        <div className="prototype-home-policy-kicker-row">
          <em className="prototype-home-policy-category">{policy.category}</em>
          <span className="prototype-home-policy-deadline">
            {deadlineBadge}
          </span>
        </div>

        <strong>{policy.title}</strong>

        <p className="prototype-home-policy-summary">
          {getPolicyCardSummary(policy)}
        </p>

        <span className="prototype-home-policy-benefit">
          {policy.amount}
        </span>
      </div>

      <div className="prototype-home-policy-card-meta">
        {scheduleLabel && (
          <span className="prototype-home-policy-schedule">
            {scheduleLabel}
          </span>
        )}
        <span className="prototype-home-policy-condition">
          조건: {getPolicyCardCondition(policy)}
        </span>
      </div>

      <small>
        <span>상세 보기</span>
        <span>바로 확인</span>
      </small>
    </Link>
  );
}
```

- [ ] **Step 2: Keep route and data logic unchanged**

Do not change:

```tsx
to={`/policies/${policy.slug}`}
```

Do not add new API calls or direct seed imports.

---

## Task 3: Apply A안 CSS

**Files:**
- Modify: `frontend/src/styles/app.css`

**Interfaces:**
- Consumes: class names from Task 2.
- Produces: readable mobile-first card layout.

- [ ] **Step 1: Replace the current home policy card CSS block**

Replace only the `.prototype-home-policy-*` block for weekly policy cards. Keep unrelated home AI/card CSS untouched.

Core CSS direction:

```css
.prototype-home-policy-card {
  display: grid;
  grid-template-columns: 46px minmax(0, 1fr);
  align-items: start;
  gap: 12px;
  min-width: 0;
  overflow: hidden;
  border: 1px solid rgba(36, 90, 115, 0.08);
  border-radius: 24px;
  padding: 16px;
  color: inherit;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 12px 30px rgba(28, 28, 46, 0.075);
}

.prototype-home-policy-visual {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  background: linear-gradient(135deg, #fff1f1 0%, #e9f7fb 100%);
  font-size: 23px;
  line-height: 1;
}

.prototype-home-policy-content {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.prototype-home-policy-kicker-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.prototype-home-policy-category,
.prototype-home-policy-deadline,
.prototype-home-policy-schedule,
.prototype-home-policy-condition {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  min-height: 26px;
  border-radius: 9999px;
  padding: 5px 9px;
  font-size: 11px;
  font-style: normal;
  font-weight: 900;
  line-height: 1.3;
  white-space: nowrap;
}

.prototype-home-policy-category {
  color: #245a73;
  background: #e9f7fb;
}

.prototype-home-policy-deadline {
  color: #166534;
  background: #eaf8ee;
}

.prototype-home-policy-card strong {
  overflow: hidden;
  overflow-wrap: anywhere;
  color: #1a1a2e;
  font-size: 16px;
  font-weight: 900;
  line-height: 1.34;
  letter-spacing: -0.025em;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.prototype-home-policy-summary {
  margin: 0;
  overflow: hidden;
  color: #5f6475;
  font-size: 13px;
  line-height: 1.48;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.prototype-home-policy-benefit {
  width: fit-content;
  max-width: 100%;
  overflow: hidden;
  border-radius: 14px;
  padding: 8px 10px;
  color: #c2410c;
  background: #fff1e8;
  font-size: 15px;
  font-weight: 950;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prototype-home-policy-card-meta {
  grid-column: 2;
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  min-width: 0;
}

.prototype-home-policy-schedule {
  color: #475569;
  background: #f1f5f9;
}

.prototype-home-policy-condition {
  color: #8a6100;
  background: #fff6e2;
}

.prototype-home-policy-card small {
  grid-column: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border-top: 1px solid #ececf1;
  padding-top: 10px;
  color: #667085;
  font-size: 12px;
  font-weight: 850;
  line-height: 1.35;
}

.prototype-home-policy-card small span:last-child {
  flex: 0 0 auto;
  color: #0f766e;
  font-weight: 950;
}
```

- [ ] **Step 2: Remove obsolete selectors**

Remove CSS selectors that no longer match the markup:

```css
.prototype-home-policy-card-head
.prototype-home-policy-label
.prototype-home-policy-card-copy
.prototype-home-policy-card small span:first-child
```

Only remove them if the selectors are not used elsewhere.

---

## Task 4: Validate Locally

**Files:**
- Modify if needed: `CHECKLIST.md`

**Interfaces:**
- Produces: evidence that the visual/card behavior did not regress.

- [ ] **Step 1: Run targeted home test**

```bash
cd frontend
npx vitest run src/app/__tests__/home.test.tsx
```

Expected: PASS.

- [ ] **Step 2: Run related policies/home tests**

```bash
cd frontend
npx vitest run src/app/__tests__/home.test.tsx src/app/__tests__/policies.test.tsx
```

Expected: PASS.

- [ ] **Step 3: Run typecheck and build**

```bash
cd frontend
npm run typecheck
npm run build
```

Expected: PASS.

- [ ] **Step 4: Rebuild local frontend container**

```bash
docker compose -f compose.yaml build frontend
docker compose -f compose.yaml up -d frontend
curl -I --max-time 5 http://127.0.0.1:4173/home
```

Expected: `/home` returns `HTTP/1.1 200 OK`.

- [ ] **Step 5: Manual responsive check**

Open `http://127.0.0.1:4173/home` and check widths:

- 360px
- 390px
- 430px
- 1024px
- 1440px

Expected:

- No horizontal scroll.
- Card title is readable within two lines.
- Summary is readable within two lines.
- `지역 제휴 혜택` or amount badge is visible before period/condition chips.
- Digital tourism cards do not show `마감일 확인 필요`.

- [ ] **Step 6: UTF-8 and diff validation**

```bash
python3 - <<'PY'
from pathlib import Path
for path in [
    Path("frontend/src/pages/HomePage.tsx"),
    Path("frontend/src/styles/app.css"),
    Path("frontend/src/app/__tests__/home.test.tsx"),
    Path("CHECKLIST.md"),
]:
    text = path.read_text(encoding="utf-8")
    assert "\\ufffd" not in text.encode("unicode_escape").decode("ascii"), path
print("utf8-ok")
PY
git diff --check
```

Expected: `utf8-ok`, no diff check output.

---

## Approval Gate

사용자 승인 전에는 다음 파일을 수정하지 않는다.

- `frontend/src/pages/HomePage.tsx`
- `frontend/src/styles/app.css`
- `frontend/src/app/__tests__/home.test.tsx`
- `CHECKLIST.md`

승인 후에는 이 계획 순서대로 TDD에 가깝게 진행한다.

## Self-Review

- Spec coverage: A안 구조, 반영 예시, 테스트, 로컬 빌드, 모바일 검증 포함.
- Placeholder scan: `TBD`, `TODO`, `implement later` 없음.
- Type consistency: 기존 `Policy`, `scheduleLabel`, `deadlineBadge` 흐름 유지.
- Scope check: `/home` 이번 주 혜택 카드만 수정한다. 백엔드, 정책 수집, `/policies`는 범위 밖이다.
