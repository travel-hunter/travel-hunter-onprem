# Policy Card Source Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 수집원별 원문에서 검증된 카드 문구를 추출하고, 불확실한 신규·변경 정책은 관리자 승인까지 공개를 보류한다.

**Architecture:** 기존 수집원별 파서와 후보 승인 서비스를 확장한다. 원문과 카드 추출 결과를 분리하고 공통 순수 함수로 품질 판정·표시를 일치시킨다. 기존 승인 Policy는 유지하며 새 추출 결과만 검토 후 승격한다.

**Tech Stack:** Python/FastAPI, SQLAlchemy/PostgreSQL, 기존 HTMLParser, pytest, React/TypeScript/Vitest. 신규 패키지 없음.

**Spec:** `docs/superpowers/specs/2026-09-21-policy-card-source-quality-design.md`

## Global Constraints

- 수집 원문과 공식 URL을 보존하고, 카드 표시를 위해 원문을 덮어쓰지 않는다.
- 신규 의존성과 LLM 호출을 추가하지 않는다.
- 정책 id/slug와 사용자 찜·일정 링크를 변경하지 않는다.
- 공개 Policy DTO 필드는 유지하고, 관리자 후보 DTO만 확장한다.
- DB 스키마 변경 없이 기존 raw_payload·review_reason·benefit_detail을 활용한다.
- 운영·개발 DB의 재수집·일괄 갱신은 구현 검증과 분리하여 별도 실행한다.
- 검토 대기 중에는 마지막 승인 내용을 유지하고 기존 마감 처리를 적용한다.
- 비밀값을 출력하거나 커밋하지 않는다.

## Review Focus

- 포인트를 원으로 오인하거나 1인/왕복/최대 한도를 섞지 않는다 — Task 1, 2의 단위·조건 fixture.
- HTML 홍보 블록을 실제 혜택으로 중복 등록하지 않고 마지막 footer도 제외한다 — Task 2.
- 요약만 변경되거나 A→B→A로 돌아와도 새 검토를 거치며 기존 id를 보존한다 — Task 3.
- 수집·개별/배치 승인이 겹쳐도 오래된 후보가 공개되지 않는다 — Task 3, 6의 PostgreSQL 검증.
- NULL 기간의 상시 정책과 파싱 실패를 구분하고 대기 중 마감도 적용한다 — Task 1, 4, 6.

---

## 실행 위치와 범위

작성 기준 HEAD `5eb23ec`. 문서 작성만 수행하며 현재 루트의 unrelated untracked 파일은 건드리지 않는다. 실행 시 using-git-worktrees 절차로 최신 origin/develop 기반 `feature/policy-card-source-quality` 작업 트리를 만든다. 원격 변화가 있으면 아래 함수/테스트 경로를 재확인한다. 프로젝트 규칙에 따라 Native/`executing-plans` 진행을 권장한다.

이번 작업은 하나의 수집→검토→공개 경계를 완성하는 변경이다. 크롤링 소스 확대, AI 요약, 관리자 후보 편집기, 카드 레이아웃 변경, 데이터 병합 마이그레이션은 포함하지 않는다. 예전 카드 문구 계획은 참고자료이며 이 계획과 겹치는 작업을 따로 중복 구현하지 않는다.

## 파일 구조와 책임

| 파일 | 책임 |
|---|---|
| `backend/app/services/policy_card_quality.py` (신규) | 카드 추출 결과 타입·검증·안전 표시 순수 함수 |
| `backend/app/services/travelmonth_traffic_parser.py` | 교통 DOM 경계·반복 블록·단위·기간 추출 |
| `backend/app/services/travelmonth_parser.py` | 지역 목록/modal 경계와 공통 결과 연결 |
| `backend/app/services/travelmonth_stay_parser.py` | 기존 숙박 조건별 추출 결과 연결 |
| `backend/app/services/dgtourcard_parser.py` | 반값여행 기존 추출 결과 연결 |
| `backend/app/services/digital_tourism_resident_card.py` | 관광주민증 기존 프로그램 문구 연결 |
| `backend/app/services/island_visit_parser.py` | 신청 가이드 유지하며 결과 연결 |
| `backend/app/services/policy_periods.py` | 예약·이용 기간 라벨의 기존 증거 모델 재사용 |
| `backend/app/services/policy_candidate_review.py` | 변경 감지, 품질 보류, 승인 경쟁 보호 |
| `backend/app/services/policy_normalization.py` | 승인 시 검증된 summary 저장 |
| `backend/app/services/policies.py` | 공개/외부 fallback 경로의 승인 경계 |
| `backend/app/services/admin.py`, `backend/app/api/routes/admin.py` | 미리보기 서비스와 얇은 DTO 변환 |
| `backend/app/schemas/admin.py`, `frontend/src/api/types.ts` | 관리자 preview 계약 |
| `frontend/src/pages/admin/AdminPages.tsx` | 원문·표시예정·보류사유 출력 |

`policy_semantics.py`의 기존 일반 formatter를 전역 변경하지 않는다. 기존 승인 내용이 배포만으로 변하지 않게 승인 저장 단계에서 신규 결과를 반영한다. UI 카드 컴포넌트는 공개 amount를 그대로 사용한다.

### Task 1: 카드 품질 결과의 순수 함수 계약

**Files:** Create `backend/app/services/policy_card_quality.py`, `backend/tests/test_policy_card_quality.py`.

**Interfaces:** Produces `CardCopyResult`, `evaluate_card_copy(*, summary: str | None, evidence: str, issues: tuple[str, ...] = ()) -> CardCopyResult`, `card_copy_for_record(record: ExternalSourceRecord) -> CardCopyResult`. Consumers는 Task 2~5. `cardCopy` 없는 레코드는 benefit_value_text만 후보로 삼고 benefit_text 전체를 summary로 쓰지 않는다.

- [ ] **Step 1: 다음 실패 테스트를 추가한다.**

```python
import pytest
from app.services.policy_card_quality import evaluate_card_copy

@pytest.mark.parametrize('summary,code', [
    (None, 'benefit_missing'),
    ('할인혜택 보러가기', 'benefit_navigation_text'),
    ('Copyright 한국관광공사', 'benefit_site_chrome'),
    ('지원내용 및 금액', 'benefit_not_summary'),
    ('가' * 41, 'benefit_not_summary'),
])
def test_unsafe_summary_is_held(summary, code):
    result = evaluate_card_copy(summary=summary, evidence='공식 본문')
    assert code in result.issues
    assert result.display_text == '혜택 상세 확인'

@pytest.mark.parametrize('summary', ['최대 3만 포인트', '무료 입장', '가맹점별 할인'])
def test_non_cash_and_non_numeric_benefits_survive(summary):
    result = evaluate_card_copy(summary=summary, evidence=summary)
    assert result.display_text == summary
    assert not result.issues

def test_period_warning_does_not_erase_valid_benefit():
    result = evaluate_card_copy(summary='최대 50% 할인', evidence='원문',
                                issues=('period_ambiguous',))
    assert result.display_text == '최대 50% 할인'
    assert result.issues == ('period_ambiguous',)
```

- [ ] **Step 2:** `cd backend; python -m pytest tests/test_policy_card_quality.py -q` → 신규 모듈 미존재 실패 확인.
- [ ] **Step 3: 아래 결과 계약으로 구현한다.**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CardCopyResult:
    summary: str | None
    evidence: str
    issues: tuple[str, ...]

    @property
    def display_text(self) -> str:
        return self.summary or '혜택 상세 확인'

    def to_payload(self) -> dict[str, object]:
        return {'version': 1, 'summary': self.summary,
                'evidence': self.evidence, 'issues': list(self.issues)}
```

`evaluate_card_copy`는 공백 정리, 40자 제한, 버튼문구/항목명 완전 일치, script·저작권·기관 footer 패턴 검사를 수행한다. 혜택 관련 문제이면 summary=None, 기간 문제만 있으면 summary 유지. 이 함수는 금액을 추론하지 않는다. payload version/type 오류는 안전하게 summary=None과 benefit_not_summary로 처리한다. `card_copy_for_record`도 payload를 그대로 신뢰하지 않고 이 검사를 통과시킨다. evidence에 실제 원문을 유지하며 로그에는 출력하지 않는다.

- [ ] **Step 4:** 동일 pytest → PASS. malformed payload와 여러 문제의 순서/중복 제거도 단위 테스트한다.
- [ ] **Step 5:** 두 신규 파일만 stage, `git commit -m "feat: define safe policy card copy evaluation"`.

### Task 2: 수집원 경계와 교통 의미 추출 교정

**Files:** Modify 위 파일 구조의 6개 수집원 파서와 `policy_periods.py`. Create `backend/tests/fixtures/traffic_card_quality.html`; Modify `backend/tests/test_travelmonth_traffic_parser.py`, `backend/tests/test_travelmonth_parser.py`, `backend/tests/test_travelmonth_stay_parser.py`, `backend/tests/test_dgtourcard_parser.py`, `backend/tests/test_island_visit_parser.py`; Create `backend/tests/test_policy_card_source_adapters.py`.

**Interfaces:** Consumes Task 1 `evaluate_card_copy`. Produces 각 ExternalBenefitSource의 `raw_payload['cardCopy'] = CardCopyResult.to_payload()`. 기존 기간 증거 `PeriodEvidence.to_payload()`와 evidence_from_payload 계약을 그대로 사용한다. 모든 수집원은 동일 결과 형식을 반환하고 추출 방식은 수집원별로 유지한다.

- [ ] **Step 1: 공식 교통 HTML을 파일로 저장하고 재현 범위를 만든다.** 공개 페이지의 철도·항공·자동차·렌터카 본문 및 반복 홍보/푸터 경계를 보존한다. 쿠키·개인정보는 저장하지 않는다. 소스 URL·확인일을 fixture 주석에 기록한다. 재현 fixture는 아래 항공 블록을 포함한다.

```html
<section><h3>국내 항공권 할인</h3>
<h4>네이버 항공권 국내선 포인트</h4>
<p>항공권 구매 이용 시 인당 1만 포인트 지급</p>
<ul><li>왕복 기준 최대 4만 포인트 지급</li></ul>
<dl><dt>예약 기간</dt><dd>2026.09.15 ~ 2026.11.30</dd>
<dt>탑승 및 이용 기간</dt><dd>2026.10.01 ~ 2026.11.30</dd></dl>
<a href="https://travel.naver.com/">할인혜택 보러가기</a></section>
<footer><p>Copyright 한국관광공사</p></footer>
```

- [ ] **Step 2: 실제 parse_traffic_benefits를 호출하는 테스트 추가.**

```python
from pathlib import Path
from datetime import UTC, datetime, date
from app.services.travelmonth_traffic_parser import parse_traffic_benefits

def test_air_summary_uses_qualified_maximum_and_excludes_footer():
    html = (Path(__file__).parent / 'fixtures/traffic_card_quality.html').read_text(encoding='utf-8')
    rows = parse_traffic_benefits(html,
        collected_page_url='https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do',
        fetched_at=datetime(2026, 9, 21, tzinfo=UTC), today=date(2026, 9, 21))
    air = next(row for row in rows if '네이버' in row.title)
    copy = air.raw_payload['cardCopy']
    assert '4만 포인트' in copy['summary']
    assert '왕복' in copy['summary']
    assert 'Copyright' not in air.benefit_text
    assert air.start_date == date(2026, 9, 15)
    assert air.end_date == date(2026, 11, 30)
    assert all(row.benefit_text != '할인혜택 보러가기' for row in rows)
```

추가 fixture 변형: nested span 제목, li/table 안에만 혜택 존재, 마지막 footer, script/style, 같은 신청 URL에 반복 홍보, 서로 다른 신청 URL의 비슷한 제목. 실제 캠페인 단위로 중복 제거하며 제목만으로 합치지 않는다. 최대치가 대상/조건과 연결되지 않으면 benefit_unit_ambiguous로 보류한다. 100% 운임 상당 쿠폰은 무료 승차로 표현하지 않는다.

- [ ] **Step 3:** `python -m pytest tests/test_travelmonth_traffic_parser.py tests/test_policy_card_source_adapters.py -q` → 기존 파서가 footer/최대치/기간에서 실패하는지 확인.
- [ ] **Step 4: 파서 본문 경계와 결과 연결 구현.** DOM 조상 경계와 h3/h4 계층을 추적하고 p/li/dd/table을 해당 실제 혜택에만 연결한다. script/style/nav/footer는 표시 의미 추출에서 제외한다. 전체 원문 증거 저장은 유지한다. 페이지 구조를 인식하지 못하면 기존 수집 실패/이상 상태를 반환해 대량 소실을 정상 처리하지 않는다.

```python
# 수집원에서 의미 추출을 마친 직후 기존 raw_payload에 병합한다.
card_copy = evaluate_card_copy(summary=benefit_value_text,
                              evidence=benefit_text,
                              issues=tuple(extraction_issues))
raw_payload['cardCopy'] = card_copy.to_payload()
```

위 지역 변수 benefit_value_text/benefit_text는 각 파서의 기존 결과, extraction_issues는 파서가 초기화하는 list[str]이다. 교통은 금액·포인트·조건을 함께 추출한 summary를 사용한다. 숙박/반값/주민증/섬은 기존 확정 summary를 사용하고 의미를 일괄 변경하지 않는다. 기간 라벨 `예약 기간`, `발급 및 예약 기간`은 ISSUE로, `탑승 및 이용 기간`은 USAGE로 기존 증거 모델에 연결한다. 분류되지 않은 날짜나 충돌은 period_ambiguous로 남긴다. 단순 날짜 부재는 별도 문제로 만들지 않는다.

- [ ] **Step 5:** 각 기존 파서 pytest와 신규 adapter 테스트 PASS. 여섯 수집원 표본에 cardCopy 형식 존재, 섬 applicationGuide·서류 기한 불변 확인. 교통 title/기간/benefit을 바꾸면 기존 canonical_key가 변하므로 라이브 승격은 금지하고 Task 6에서 매칭 충돌을 보고한다.
- [ ] **Step 6:** Task 2의 명시 파일만 stage, `git commit -m "fix: extract source-scoped policy benefits and periods"`.

### Task 3: 후보 변경 감지와 자동 공개 품질 게이트

**Files:** Modify `backend/app/services/policy_candidate_review.py`; Test `backend/tests/test_policy_candidate_review.py`, `backend/tests/test_policy_auto_publish.py`, `backend/tests/test_policy_candidate_concurrency_postgres.py`.

**Interfaces:** Consumes `card_copy_for_record(record)`. Produces 추가 fingerprint 입력 `cardCopy`, `benefitValueText` 및 보류 reason `card_quality_review`. 기존 후보 상태·approveAll·감사로그 계약 유지.

- [ ] **Step 1: 기존 make_record fixture로 변경 감지 테스트 추가.**

```python
def test_summary_only_change_creates_pending_candidate(db):
    record = make_record()
    record.benefit_value_text = '최대 1만원 할인'
    db.add(record)
    db.flush()
    first = classify_candidate(db, record=record)
    record.benefit_value_text = '최대 2만원 할인'
    second = classify_candidate(db, record=record)
    assert first.id != second.id
    assert first.review_status == 'superseded'
    assert second.review_status == 'pending'
```

동일 결과 반복은 후보 1개, A→B→A는 새 후보, raw footer만 바뀌고 의미 결과 불변이면 불필요 후보 없음도 검사한다. 기존 evidence_fingerprint의 title/benefit/기간 등 입력을 제거하지 않는다.

- [ ] **Step 2:** `python -m pytest tests/test_policy_candidate_review.py tests/test_policy_auto_publish.py -q` → summary-only 테스트 실패 확인.
- [ ] **Step 3: 해시와 보류 이유를 연결한다.**

```python
# evidence_fingerprint의 payload 구성에 추가한다.
payload['benefitValueText'] = record.benefit_value_text
copy = card_copy_for_record(record)
payload['cardCopy'] = {'summary': copy.summary, 'issues': list(copy.issues)}
# _hold_reason에서 자동 승인 자격 평가보다 먼저 검사한다.
if card_copy_for_record(record).issues:
    return 'card_quality_review'
```

해시 버전 변경으로 최초 재수집에 후보가 늘 수 있으므로 첫 적용은 수집원 review 모드로 수행한다. classify_candidate의 기존 record→candidate 잠금 순서를 유지한다. approve_candidate도 동일 순서로 레코드와 후보를 잠그고 최신 fingerprint와 일치하는 pending 후보만 승인한다. 기존 approved 해시를 DB에서 일괄 다시 쓰지 않는다.

- [ ] **Step 4:** 통합 테스트에서 기존 정책 승인→불량 변경 수집→auto_publish_gate 호출 후 pending, published Policy 내용 불변을 검증한다. 개별/선택/전체 승인과 수집 경쟁은 실제 PostgreSQL 테스트에 추가한다. 기존 ValueError→409 라우트 매핑을 확인한다.
- [ ] **Step 5:** 표적 pytest PASS 후 명시 파일 stage, `git commit -m "fix: hold uncertain policy copy for review"`.

### Task 4: 승인 내용과 공개 API 표시의 일치

**Files:** Modify `backend/app/services/policy_normalization.py`, `backend/app/services/policies.py`; Test `backend/tests/test_policy_normalization.py`, `backend/tests/test_policy_candidate_review.py`, `backend/tests/test_policy_semantics.py`, `backend/tests/test_admin_routes.py`.

**Interfaces:** Consumes CardCopyResult.display_text. Produces 승인된 Policy.benefit_detail. 공개 DTO의 amount:string 및 기존 id/slug 유지.

- [ ] **Step 1: 수동 승인도 오염 원문을 게시하지 않는 테스트 추가.**

```python
def test_manual_approval_publishes_safe_fallback(db):
    record = make_record()
    record.benefit_value_text = '할인혜택 보러가기'
    admin = User(id=10, email='admin@example.com', nickname='admin', role='admin')
    db.add_all([record, admin])
    db.flush()
    candidate = classify_candidate(db, record=record)
    approved = approve_candidate(db, candidate=candidate, record=record, admin=admin)
    policy = db.get(Policy, approved.published_policy_id)
    assert policy.benefit_detail == '혜택 상세 확인'
    assert record.benefit_value_text == '할인혜택 보러가기'
```

선택/전체 승인에도 같은 기대값 추가. 기존 Policy 승인 후 ExternalSourceRecord만 바꾼 경우 공개 목록/상세/홈/일정 연결 DTO에서 승인 amount가 유지되는 통합 테스트를 추가한다. 현재 섬 신청 정책의 마감 후 서류기한 예외도 기존 테스트로 유지한다.

- [ ] **Step 2:** 위 표적 pytest → 원문 fallback 때문에 실패 확인.
- [ ] **Step 3: 일반 및 숙박 alias 승인 투영을 변경한다.**

```python
benefit_detail = card_copy_for_record(record).display_text
```

Policy.description과 ExternalSourceRecord 원문은 그대로 유지한다. 기존 admin_override_enabled 우선 경로를 유지한다. public fallback의 `record.benefit_value_text or record.benefit_text`도 같은 함수로 대체하되 기존 fallback 허용 수집원/상태 범위를 확대하지 않는다. 일반 공개 Policy는 최신 원문을 읽어 재정규화하지 않는다. 포인트 summary가 원 금액으로 재변환되지 않는지 확인한다.

- [ ] **Step 4:** 표적 tests PASS, 현재 정상 숙박·주민증·반값·섬 amount 및 id/slug 불변 확인.
- [ ] **Step 5:** 명시 파일 stage, `git commit -m "fix: publish only reviewed safe policy card text"`.

### Task 5: 관리자 원문·카드 미리보기 계약과 UI

**Files:** Modify `backend/app/schemas/admin.py`, `backend/app/services/admin.py`, `backend/app/api/routes/admin.py`, `frontend/src/api/types.ts`, `frontend/src/pages/admin/AdminPages.tsx`, `docs/mvp-api-contract.md`, `.agent/evals/api-contract-golden.json`; Test `backend/tests/test_admin_routes.py`, `frontend/src/pages/admin/AdminPages.test.tsx`.

**Interfaces:** Produces AdminPolicyReviewCandidateItem의 `cardPreview: {amount:string, evidence:string, issues:string[]}`. 기존 benefitText/reviewReason 유지. 서비스에 `build_candidate_card_preview(record: ExternalSourceRecord) -> dict[str, object]` 추가. 관리자 전용이며 공개 DTO에 원문 추가 없음.

- [ ] **Step 1: DTO/서비스 단위 테스트 추가.**

```python
from types import SimpleNamespace
from app.services.admin import build_candidate_card_preview

def test_candidate_preview_matches_safe_public_amount():
    record = SimpleNamespace(raw_payload={}, benefit_value_text='할인혜택 보러가기',
                             benefit_text='공식 본문', raw_detail_text='공식 본문')
    preview = build_candidate_card_preview(record)
    assert preview['amount'] == '혜택 상세 확인'
    assert 'benefit_navigation_text' in preview['issues']
```

- [ ] **Step 2:** 해당 backend 테스트 → 함수 미정의 실패. UI는 기존 mock candidate에 cardPreview를 추가하고 `screen.getByText('혜택 상세 확인')`, `screen.getByText('버튼 문구가 포함되어 있어요')` 검증을 추가한다. 승인 API 실패 시 행/선택이 사라지지 않는 테스트와 50건 페이지 경계 테스트를 유지한다.
- [ ] **Step 3: 스키마와 얇은 route 변환 구현.**

```python
class AdminPolicyCardPreview(BaseModel):
    amount: str
    evidence: str
    issues: list[str] = Field(default_factory=list)

# AdminPolicyReviewCandidateItem에 추가
# cardPreview: AdminPolicyCardPreview

def build_candidate_card_preview(record):
    copy = card_copy_for_record(record)
    return {'amount': copy.display_text, 'evidence': copy.evidence,
            'issues': list(copy.issues)}
```

스키마/TS/문서/golden을 같은 커밋에 변경한다. 원문 증거는 최대 2,000자까지만 DTO로 보내고 UI에 `원문 일부`를 표시하며 공식 URL로 전체 확인 가능하게 한다. DB 원문은 자르지 않는다. frontend 타입은 `cardPreview?: { amount: string; evidence: string; issues: string[] }`로 배포 전후 구버전 응답도 허용한다. 누락 시 기존 원문 표시와 공식 링크를 유지하고 검증 완료로 표시하지 않는다.

- [ ] **Step 4: 기존 후보 article에 미리보기 출력.**

```tsx
{candidate.cardPreview && (
  <section aria-label="카드 표시 예정">
    <strong>{candidate.cardPreview.amount}</strong>
    <details><summary>원문 일부</summary><p>{candidate.cardPreview.evidence}</p></details>
    <ul>{candidate.cardPreview.issues.map((issue) => (
      <li key={issue}>{CARD_QUALITY_LABEL[issue] ?? "원문 확인이 필요해요"}</li>
    ))}</ul>
  </section>
)}
```

CARD_QUALITY_LABEL은 Task 1의 6가지 사유를 한국어로 매핑한다. 각각 혜택 추출 실패, 요약 불명확, 버튼 문구 포함, 사이트 공통 문구 포함, 혜택 단위/조건 불명확, 기간 구분 불명확이다. 문자열은 React 텍스트로만 출력한다. 선택/전체 승인 확인 안내에 중립 문구 게시를 명시하고 approveAll의 기존 전체 pending 범위를 유지한다.

- [ ] **Step 5:** `python -m pytest tests/test_admin_routes.py -q`; frontend에서 `npx vitest run src/pages/admin/AdminPages.test.tsx` 및 `npm run typecheck` → PASS. API golden JSON parse 검사.
- [ ] **Step 6:** 명시 파일 stage, `git commit -m "feat: show policy copy evidence in admin review"`.

### Task 6: 격리 종단 검증과 데이터 적용 준비

**Files:** Modify `docs/policy-collection-to-screen-flow.md`, `docs/implemented-feature-spec.md`, 본 계획 검증 기록. CHECKLIST.md는 PR 준비 시점만 갱신한다.

**Interfaces:** Task 1~5의 수집→후보→승인→공개 경계 전체. 새로운 공개 API/DB 필드 없음.

- [x] **Step 1 현재 컨테이너 provenance·포트 소유자를 제한된 형식으로 확인한다.** 기존 서버를 임의 종료하지 않는다. 격리 DB·backend·frontend를 같은 worktree로 실행하고 자동 스케줄러는 끈다. 기본 `npm run test:e2e`는 공유 DB를 재생성할 수 있으므로 사용하지 않는다.
- [x] **Step 2 fixture 기반 전체 흐름 테스트를 실행한다.** 신규 불량 후보는 목록/상세/추천에 노출 0, 기존 승인 정책은 재수집 후 amount·id·slug·찜/일정 링크 불변, 수동 승인 후 preview와 공개 amount 동일, 마감 도달 시 기존 숨김 동작 유지. SQLite 결과를 PostgreSQL 경쟁 검증으로 대체하지 않는다.
- [x] **Step 3 PostgreSQL 경쟁 테스트를 전용 DB에서 실행한다.** `test_policy_candidate_concurrency_postgres.py`의 기존 환경변수 게이트와 URL 읽기 방식을 확인한 뒤 실행한다. 두 세션의 수집/승인·반려/전체승인 경쟁에서 오래된 후보 409 및 부분 커밋 없음 확인. DSN·토큰을 출력하지 않는다.
- [x] **Step 4 격리 스택에서 실제 공식 수집을 한 번 실행한다.** 모든 수집원 publication_mode=review 유지. 교통 11행과 신규 추출 결과를 공식 신청 URL/캠페인/제목/차수로 비교한다. canonical_key 변경·다대일 매칭·기존 찜/일정 링크 존재 여부를 보고한다. 애매한 매칭은 승인하지 않고 기존 데이터를 남긴다. 개발/운영 DB에 이 작업을 복사 실행하지 않는다.
- [ ] **Step 5: 사용자 테스트 경로 확인.**
  - 보류: 5173은 `policy-tab-bottom-tabs-hidden` worktree의 `node.exe`(PID 2392)가 사용 중이었다. 해당 프로세스를 종료하지 않았으며 이 세션에서 별도 시각 UI 테스트는 실행하지 않았다. 사용자 UI 확인 필요. 5173 사용 가능 여부와 worktree를 확인해 격리 backend로 연결한다. 관리자에서 원문/표시 예정/사유 확인 후 테스트 후보 승인, 홈/정책/상세에서 같은 문구를 확인한다. 5173이 다른 작업 소유이면 해당 프로세스를 종료하지 않고 충돌을 보고한다.
- [x] **Step 6 최종 게이트.**

```text
backend: python -m pytest
frontend: npm run typecheck
frontend: npx vitest run
frontend: npm run build
frontend: npm run test:mojibake
root: git diff --check
```

기존 스냅샷 실패를 무조건 기존 문제로 간주하지 않는다. 최신 develop 동일 조건 기준선과 대조해 새 실패가 없는지 증명한다. 전체 tests는 공유 데이터가 아닌 격리 DB로 실행한다. 변경 파일 UTF-8/U+FFFD 및 API 계약 동기화를 검증한다.

- [x] **Step 7 문서에 운영 적용 순서를 기록한다.** 배포→수집원 review 확인→백업/복원 가능성 확인→읽기 전용 기준선→수집→후보 비교→명시적 승인→링크 수/노출 비교. 기존 홍보 카드 정리와 ID 병합은 별도 작업으로 남긴다. 자동화 재활성화는 정상 표본 승인·검증 뒤 운영자가 결정한다.
- [x] **Step 8** 검증 증거와 한계를 계획에 기록하고 문서만 명시 stage, `git commit -m "docs: record policy card quality verification"`. 푸시/PR은 사용자 절차에 맞춰 본문 미리보기를 먼저 제공한다.


### Task 6 검증 결과 (2026-09-21)

- 격리 경계: 현재 루트 8000/4173 서비스와 혼합 출처 DB는 재사용하지 않았다. 별도 PostgreSQL 16 컨테이너 `policy-card-quality-verify-20260921`의 로컬 전용 포트 55433에 새 DB를 만들고, 스케줄러를 끈 테스트 API는 18000을 사용했다. 컨테이너/포트는 완료 뒤 정리한다.
- fixture/회귀: 기존 승인 정책 identity 스냅샷(id/slug/찜/일정 링크), 안전 문구 수동 승인, 카드 요약 변경 감지, 검토모드 pending, 만료 정책 public route 숨김 테스트가 전체 백엔드 스위트에서 통과했다. PostgreSQL 후보 승인·반려 경합 테스트 1건도 전용 DB에서 통과했다.
- 공식 live 수집: 빈 격리 DB에서 `traffic_benefit`만 활성화하고 전체 소스 `publication_mode=review`를 확인한 뒤 한 번 수집했다. 결과 `success`, parsed/upserted 11/11`, 후보 11건 모두 `pending`, 자동 승인 0, 동일 canonical key 중복 0`이다. 빈 DB에서 실행했으므로 이 수치는 개발 데이터와의 ID/링크 무변경 증거가 아니다. 기존 즐겨찾기·일정 링크, canonical key의 개발 DB 전후 대조도 이 환경에서는 불가능하다.
- 실제 페이지 증거로 발견한 교정: 공식 원문의 `왕복 기준, 최대 4만 포인트` 쉼표 표기, 정액 2만원, 1인당 상품권, 운임 비율 및 운임 상당 할인쿠폰을 구분하도록 교통 요약 파서를 보완했다. 조건과 떨어진 최대 포인트 3종은 `benefit_unit_ambiguous`로 보류된다. 가능한 캠페인 겹침(상세 항공권 혜택과 요약 홍보 블록, 인구감소지역 운전 보상 관련 제목들)은 별도 canonical key로 남아 있어 수동 대조/승인 전 병합하지 않는다.
- 최종 검증: backend `946 passed / 1 failed / 24 skipped`; 유일 실패는 기준선과 같은 Windows 임시 폴더 권한 검사(`test_restricted_atomic_artifact_and_sidecar_round_trip`). 앞선 전체 실행에서 섬 첨부 엑셀 해시 테스트가 한 번 간헐 실패했으나 단독 재실행 및 최종 전체 실행에서 통과했다. frontend 격리 Vitest `37 files / 420 passed`; `npm run typecheck`, `npm run build`, `npm run test:mojibake` 통과. Build는 기존 500KB chunk-size 경고를 출력했다.
- UI 한계: 5173은 `policy-tab-bottom-tabs-hidden` worktree에 속한 Node/Vite 프로세스가 점유하여 건드리지 않았다. 브라우저에서 이 worktree의 관리자 미리보기와 공개 카드 노출을 시각 확인하지 못했다. 사용자 검토를 위한 별도 preview가 필요하다.
- 운영 전 적용 순서: 배포 후 소스 모드를 review로 확인 → 백업/복원 가능성 확보 → 읽기 전용 정책·링크 기준선 저장 → 수집 → 후보별 제목/차수/공식 URL/기간/benefitCopy 대조 → 명시 승인 → 목록·상세·홈/추천·찜/일정 링크 수 비교. 수동 수집 전후의 기존 텍스트를 자동 치환하지 않는다. 자동 발행은 여러 정상 표본의 승인/노출을 확인한 뒤 운영자가 별도로 결정한다.

## 작성자 자체 검토

- [x] 설계의 신규 검토 대기·기존 승인 유지·마감 규칙을 Task 3/4/6에 연결했다.
- [x] 공통 계약 이름 CardCopyResult/cardCopy/cardPreview와 summary/display_text/amount의 매핑을 일치시켰다.
- [x] 단순 금액 정규식·단순 말줄임으로 의미를 바꾸지 않도록 Task 1/2에 조건 테스트를 배치했다.
- [x] 배치 승인·재수집 해시·기존 ID 변경 위험을 명시했다.
- [x] 원문 보존·관리자 전용 DTO·공개 DTO 유지·DB 무변경 범위를 명시했다.
- [x] 예전 중복 계획과 현재 계획의 우선순위를 정의했다.

구현 테스트 결과: 아직 실행하지 않았다. 이 문서는 구현 계획이며 위 체크된 자체 검토는 코드 검증을 의미하지 않는다.
