# dgtour 정책 슬러그 정식화 구현 계획

> **작업자 안내:** 각 Task는 실패 테스트를 먼저 쓰고 빨간 것을 확인한 뒤 구현한다. 단계는 체크박스로 추적한다.

**목표:** dgtour 정책 슬러그가 VisitKorea 페이지의 등장 순번에 의존하지 않게 만든다. 크롤러가 정식 슬러그를 만들고, 시드 데이터를 거기에 맞춘다.

**설계:** 슬러그 규칙은 이미 `canonical_policy_slug_for_city()`에 있다. 크롤러만 이걸 안 쓴다. 크롤러를 규칙에 연결하고, 시드 JSON을 규칙에 맞게 정렬하고, 검증기가 규칙 위반을 잡게 한다. 백엔드 별칭 계층은 이미 양쪽 슬러그를 해석하므로 새로 만들 것이 없다.

**조사 문서:** `docs/superpowers/specs/2026-08-27-dgtour-slug-investigation.md`

## 전역 제약

- **DB 조작은 이 계획에 포함하지 않는다.** 갈라진 링크 병합은 별도 작업이다 (아래 "이 계획이 하지 않는 것" 참조).
- 개발서버(192.168.32.15) git/배포/DB 조작 금지. merge, 운영 승격 금지.
- push / PR 금지. 커밋까지만 한다.
- `backend/scripts/`의 다른 스크립트가 `from app...`를 이미 임포트한다 (`audit_policy_semantics.py`, `normalize_external_policies.py`). 크롤러도 같은 방식을 쓴다.

---

## 배경 (조사 결과 요약)

`backend/scripts/crawl_dgtourcard.py:217`

```python
policy["slug"] = f"dgtour-{slugify(city)}-{entry['id']}"
```

`entry['id']`는 `func_go_detail` 호출의 두 번째 인자 — VisitKorea 페이지에서의 **등장 순번**이다. 페이지 순서가 바뀌면 모든 슬러그가 바뀌고, 슬러그는 찜·일정연결의 키이므로 사용자 링크가 끊긴다.

`feature/local-remediation-integration`의 `bc3afc8`이 시드 JSON의 active 5건을 정식 슬러그로 바꿨지만 **크롤러를 안 고쳐서** 다음 크롤이 되돌린다. 그래서 두 변경은 한 PR이어야 한다.

---

## 파일 구성

| 파일 | 역할 | 작업 |
|---|---|---|
| `backend/scripts/crawl_dgtourcard.py` | 크롤 → JSON 생성 | 수정 — 슬러그 규칙 연결 |
| `backend/tests/test_crawl_dgtourcard.py` | 크롤러 단위 테스트 | **신규** |
| `backend/app/data/dgtourcard_policies.json` | 시드 데이터 | 수정 — 16건 슬러그 정렬 |
| `backend/scripts/validate_policy_data.py` | 시드 검증기 | 수정 — 정식 슬러그 규칙 추가 |
| `backend/tests/test_policy_data_validation.py` | 검증기 테스트 | 수정 (`bc3afc8`이 가져옴 + 추가) |
| `backend/tests/test_policy_source_audit.py` | 시딩 감사 테스트 | 수정 (`bc3afc8`이 가져옴) |
| `frontend/e2e-backend/backend-mode.spec.ts` | e2e 상수 | 수정 (`bc3afc8`이 가져옴) |

---

## Task 1: 크롤러가 정식 슬러그를 만들게 한다

**파일**
- 수정: `backend/scripts/crawl_dgtourcard.py:217`
- 신규: `backend/tests/test_crawl_dgtourcard.py`

**인터페이스**
- 사용: `app.services.digital_tourism_resident_card.canonical_policy_slug_for_city(city) -> str | None`
  참여도시면 `dgtour-{도시}`, 비참여면 `None`
- 산출: `parse_policies_from_html(html)`이 순번 없는 슬러그를 담은 dict 목록을 반환

- [ ] **Step 1: 실패 테스트 작성**

`backend/tests/test_crawl_dgtourcard.py` 신규:

```python
from __future__ import annotations

from scripts.crawl_dgtourcard import parse_policies_from_html

# data-signgucd 앞 두 자리가 광역시도를 결정한다. 46=전남, 48=경남.
MAP_HTML = (
    """<a href="#" onclick="func_go_detail('영광', '8')" data-signgucd='46870'>영광</a>\n"""
    """<a href="#" onclick="func_go_detail('하동', '3')" data-signgucd='48850'>하동</a>"""
)


def test_parse_policies_from_html_uses_canonical_slugs_without_page_order() -> None:
    policies = parse_policies_from_html(MAP_HTML)

    slugs = [policy["slug"] for policy in policies]
    assert slugs == ["dgtour-영광", "dgtour-하동"]


def test_parse_policies_from_html_keeps_region_from_signgucd() -> None:
    policies = parse_policies_from_html(MAP_HTML)

    regions = {policy["slug"]: policy["region"] for policy in policies}
    assert regions == {"dgtour-영광": "전남", "dgtour-하동": "경남"}
```

`MAP_HTML`은 실제 파서로 돌려 검증한 최소 입력이다. 수정 전에는 `dgtour-영광-8` / `dgtour-하동-3`을 낸다.

- [ ] **Step 2: 실패 확인**

```
cd backend
python -m pytest tests/test_crawl_dgtourcard.py -v
```

기대: `test_parse_policies_from_html_uses_canonical_slugs_without_page_order` FAIL

```
AssertionError: assert ['dgtour-영광-8', 'dgtour-하동-3'] == ['dgtour-영광', 'dgtour-하동']
```

두 번째 테스트는 이 시점에 통과해야 한다 (region은 안 바꾼다). 통과하지 않으면 픽스처가 잘못된 것이니 멈추고 확인한다.

- [ ] **Step 3: 구현**

`crawl_dgtourcard.py` 임포트부에 추가 (`from typing import Any` 아래):

```python
from app.services.digital_tourism_resident_card import canonical_policy_slug_for_city
```

`:217` 한 줄을 교체:

```python
            policy["slug"] = canonical_policy_slug_for_city(city) or f"dgtour-{slugify(city)}"
```

비참여 도시는 `canonical_policy_slug_for_city`가 `None`을 주므로 순번 없는 폴백을 쓴다. 도시명이 겹치면 기존 `deduplicate()`(`:278`)가 `-2`, `-3`을 붙여 처리한다 — **그 함수는 건드리지 않는다.**

- [ ] **Step 4: 통과 확인**

```
cd backend
python -m pytest tests/test_crawl_dgtourcard.py -v
```

기대: 2 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/scripts/crawl_dgtourcard.py backend/tests/test_crawl_dgtourcard.py
git commit -m "Derive dgtour crawl slugs from the canonical city rule"
```

---

## Task 2: `bc3afc8` 반영 (active 5건 + 테스트 + e2e 상수)

**파일**
- 수정: `backend/app/data/dgtourcard_policies.json` (하동·영광·합천·해남·완도)
- 수정: `backend/tests/test_policy_data_validation.py`
- 수정: `backend/tests/test_policy_source_audit.py`
- 수정: `frontend/e2e-backend/backend-mode.spec.ts`

`git apply --check`로 develop에 깨끗이 적용됨을 이미 확인했다.

- [ ] **Step 1: cherry-pick**

```bash
git cherry-pick bc3afc8
```

충돌이 나면 멈추고 보고한다. Task 1이 JSON을 안 건드리므로 충돌은 없어야 한다.

- [ ] **Step 2: 가져온 테스트 실행**

```
cd backend
python -m pytest tests/test_policy_data_validation.py tests/test_policy_source_audit.py -v
```

기대: 전부 통과.

`test_seed_policies_replaces_unlinked_numbered_dgtour_seed_with_canonical_slug`는 `sqlite_db_session`(빈 DB)에서 돌아 통과한다. **이 테스트는 링크가 붙은 중복 행 상황을 덮지 않는다** — 그 경우 재시딩은 순번 행을 삭제하지 않고 hidden으로 돌린다. 아래 "사용자 확인 요청 전 반드시 알릴 것"에서 다룬다.

---

## Task 3: 나머지 11건도 정렬한다

`bc3afc8`은 active 5건만 바꾼다. Task 1을 적용한 크롤러가 만들 결과와 JSON을 완전히 일치시켜, 나중에 hidden 정책을 active로 올려도 순번이 되살아나지 않게 한다.

**파일**
- 수정: `backend/app/data/dgtourcard_policies.json`
- 수정: `backend/tests/test_policy_data_validation.py`

대상 (현재 → 목표):

```
dgtour-밀양-1  -> dgtour-밀양      dgtour-평창-2  -> dgtour-평창
dgtour-거창-4  -> dgtour-거창      dgtour-영월-5  -> dgtour-영월
dgtour-제천-6  -> dgtour-제천      dgtour-강진-7  -> dgtour-강진
dgtour-남해-11 -> dgtour-남해      dgtour-영암-12 -> dgtour-영암
dgtour-고흥-13 -> dgtour-고흥      dgtour-횡성-14 -> dgtour-횡성
dgtour-고창-16 -> dgtour-고창
```

강진·남해·영암·횡성은 비참여 도시라 `canonical_policy_slug_for_city`가 `None`을 준다. Task 1의 폴백(`dgtour-{slugify(city)}`)이 같은 값을 내므로 결과는 동일하다.

**이 11건은 DB에서 링크가 0건이다** (조사에서 확인). 재시딩 시 `_cleanup_legacy_dgtour_policies`가 옛 순번 행을 그냥 삭제한다 — 사용자 데이터 손실 없음.

- [ ] **Step 1: 실패 테스트 작성**

`backend/tests/test_policy_data_validation.py`에 추가:

```python
def test_seed_dgtour_slugs_never_carry_a_page_order_suffix() -> None:
    policies = json.loads(
        (Path(__file__).parents[1] / "app" / "data" / "dgtourcard_policies.json").read_text(
            encoding="utf-8"
        )
    )

    numbered = [
        str(policy["slug"])
        for policy in policies
        if str(policy["slug"]).rsplit("-", 1)[-1].isdigit()
    ]

    assert numbered == []
```

`json`과 `Path`는 이 파일이 이미 임포트하고 있다 (`:57` 부근의 기존 테스트가 같은 방식으로 읽는다). 없으면 추가한다.

- [ ] **Step 2: 실패 확인**

```
cd backend
python -m pytest tests/test_policy_data_validation.py::test_seed_dgtour_slugs_never_carry_a_page_order_suffix -v
```

기대: FAIL — `numbered`에 11건이 남아 있다.

- [ ] **Step 3: JSON 수정**

위 표대로 11건의 `"slug"` 값에서 `-숫자` 접미사를 뗀다. **`slug` 필드만 바꾼다.** `sourceCanonicalKey`, `status`, `officialUrl`은 그대로 둔다.

- [ ] **Step 4: 통과 확인**

```
cd backend
python -m pytest tests/test_policy_data_validation.py tests/test_policy_source_audit.py -v
```

기대: 전부 통과. 중복 슬러그가 생기지 않았는지는 기존 검증기(`중복 slug` 검사)가 잡는다.

- [ ] **Step 5: 커밋**

```bash
git add backend/app/data/dgtourcard_policies.json backend/tests/test_policy_data_validation.py
git commit -m "Drop page-order suffixes from the remaining dgtour seed slugs"
```

---

## Task 4: 검증기가 규칙을 강제한다

`validate_policy_data.py`는 지금 빈 슬러그와 중복만 본다. 규칙 위반이 다시 들어와도 못 잡는다.

**파일**
- 수정: `backend/scripts/validate_policy_data.py`
- 수정: `backend/tests/test_policy_data_validation.py`

- [ ] **Step 1: 실패 테스트 작성**

먼저 `validate_policy_data.py:74` 부근을 읽고 검증 함수의 **실제 이름과 시그니처, 필수 필드**를 확인한다. 아래 테스트는 그에 맞춰 조정한다.

```python
def test_validate_policies_rejects_a_page_order_suffix_on_an_active_dgtour_slug() -> None:
    from scripts.validate_policy_data import validate_policies

    errors = validate_policies(
        [
            {
                "slug": "dgtour-영광-8",
                "title": "[영광] 디지털관광주민증 혜택",
                "sourceCategory": "digital_tourism_resident_card",
                "sourceCanonicalKey": "digital-tourism-resident-card:전남:영광",
                "status": "active",
            }
        ]
    )

    assert any("dgtour-영광" in error for error in errors)
```

- [ ] **Step 2: 실패 확인**

```
cd backend
python -m pytest tests/test_policy_data_validation.py::test_validate_policies_rejects_a_page_order_suffix_on_an_active_dgtour_slug -v
```

기대: FAIL — 슬러그 규칙 오류가 하나도 안 나온다.

**실패 메시지를 반드시 눈으로 확인한다.** 필수 필드가 빠져 *다른 이유로* 실패하면 테스트가 규칙을 검사하지 못하는 것이므로, 그 경우 픽스처에 필드를 채워 넣고 다시 확인한다.

- [ ] **Step 3: 구현**

`validate_policy_data.py`의 항목 루프(`:84` 부근, `seen_slugs` 검사 직후)에 추가:

```python
        if (
            str(policy.get("sourceCategory") or "") == "digital_tourism_resident_card"
            and str(policy.get("status") or "active") == "active"
        ):
            city = official.city_from_policy_slug(slug)
            canonical_slug = official.canonical_policy_slug_for_city(city)
            if canonical_slug and slug != canonical_slug:
                errors.append(
                    f"{slug} must use the canonical dgtour slug {canonical_slug}."
                )
```

`official`은 `digital_tourism_resident_card` 모듈을 가리키는 이름이다. 이 파일에 임포트가 없으면 추가한다 — `test_policy_data_validation.py`가 이미 `official.canonical_policy_slug_for_city`를 쓰므로 **그쪽 임포트 이름에 맞춘다.**

- [ ] **Step 4: 통과 확인**

```
cd backend
python -m pytest tests/ -q
```

**전체 백엔드 스위트를 돌린다.** 일부만 돌리지 않는다 — 과거에 부분 실행 기준선 때문에 회귀를 놓친 적이 있다.

- [ ] **Step 5: 커밋**

```bash
git add backend/scripts/validate_policy_data.py backend/tests/test_policy_data_validation.py
git commit -m "Enforce canonical dgtour slugs in the seed data validator"
```

---

## 검증

### 백엔드

```
cd backend
python -m pytest tests/ -q
```

Task 1 시작 **전에** 기준선을 재고, 끝난 뒤 **실패 테스트 이름 목록**으로 비교한다. 건수만 비교하지 않는다.

### 로컬 런타임 연결

백엔드 코드와 시드 데이터가 바뀌므로 컨테이너를 다시 굽고 **시딩을 수동 실행**해야 한다. 시딩은 기동 시 자동으로 돌지 않는다 (`app/db/seed.py:295`의 `main()`이 진입점).

```bash
docker build -t travel-hunter-onprem-backend <worktree>/backend
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml up -d --no-build backend
docker exec travel-hunter-onprem-backend-1 python -m app.db.seed
```

들어갔는지 실제로 확인한다:

```bash
curl -s "http://127.0.0.1:8000/api/policies?limit=300" \
  | python -c "import json,sys; print(sorted(p['slug'] for p in json.load(sys.stdin) if p['slug'].startswith('dgtour-')))"
```

기대: `['dgtour-영광', 'dgtour-완도', 'dgtour-하동', 'dgtour-합천', 'dgtour-해남']` — 순번 없음.

### 프론트엔드

```
cd frontend
npx vitest run
```

현재 기준선 **289 passed / 6 failed**. 실패 4건이 슬러그 불일치이므로 **291 passed / 2 failed**를 기대한다.

주의 두 가지:

1. 이 4건은 **로컬 백엔드 DB 상태에 의존한다.** 재시딩 전에 돌리면 그대로 실패한다. 반드시 위 런타임 연결을 먼저 끝낸다.
2. **검증 실행 중에는 컨테이너를 건드리지 않는다.** 과거에 스위트 실행 중 백엔드를 재빌드해 실패가 부풀려진 적이 있다.

남는 2건은 `mypage.test.tsx`의 `expected undefined to be truthy` 2건으로, 원인이 다르고 이 계획의 범위 밖이다.

### 사용자 확인 요청 전 반드시 알릴 것

재시딩 후 **영광·하동의 노출 극성이 뒤집힌다.**

| 슬러그 | 지금 | 재시딩 후 |
|---|---|---|
| `dgtour-영광` (일정 1, 찜 1) | hidden — 안 보임 | **active — 다시 보임** |
| `dgtour-영광-8` (찜 1, 08-27 저장) | active — 보임 | **hidden — 안 보임** |
| `dgtour-하동` (일정 1) | hidden | **active** |
| `dgtour-하동-3` (일정 2) | active | **hidden** |

즉 08-27에 저장한 영광 찜과 하동 일정 연결 2건이 화면에서 사라진다. **데이터가 지워지는 것은 아니다** — 행은 남고 `status`만 hidden이 된다. 아래 병합 작업으로 되살릴 수 있다. 사용자에게 테스트를 요청하기 **전에** 이 사실을 전달한다.

---

## 이 계획이 하지 않는 것 — 후속 작업

**갈라진 링크 병합.** 영광·하동은 DB에 두 행으로 존재하고 사용자 링크가 양쪽에 흩어져 있다. 합치려면:

```
user_saved_policies:  user 1 이 dgtour-영광 과 dgtour-영광-8 을 둘 다 찜
trip_policies:        trip 1 이 dgtour-하동 과 dgtour-하동-3 에 둘 다 연결
```

겹침이 있으므로 `UPDATE ... SET policy_id = <정식행>`을 그대로 돌리면 `(user_id, policy_id)` / `(trip_id, policy_id)` 유일 제약에 걸린다. **중복 제거를 먼저 하고 옮겨야 한다.** 기존 사용자 데이터를 건드리므로 되돌릴 수 있는 별도 작업으로 분리한다.

**그 밖에 하지 않을 것**

- 크롤러 실행 (실제 VisitKorea 사이트 호출). JSON은 손으로 정렬한다
- `mypage.test.tsx` 잔여 2건 — 원인 미조사
- 프론트 테스트가 로컬 백엔드에 의존하는 구조 자체 — 별도 논의
- `deduplicate()` 재작성
- push / PR / merge
