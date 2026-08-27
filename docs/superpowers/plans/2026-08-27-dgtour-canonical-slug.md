# dgtour 정책 슬러그 정식화 구현 계획

> **작업자 안내:** 각 Task는 실패 테스트를 먼저 쓰고 빨간 것을 확인한 뒤 구현한다. 단계는 체크박스로 추적한다.

**목표:** dgtour 정책 슬러그에서 VisitKorea 페이지 등장 순번에 의존하는 `-숫자` 접미사를 없애고, 다시 들어오지 못하게 막는다.

**설계:** 슬러그 규칙은 이미 `canonical_policy_slug_for_city()`에 있다. 슬러그를 만드는 유일한 코드 경로(크롤러)를 그 규칙에 연결하고, 시드 JSON을 규칙에 맞게 정렬하고, 검증기가 규칙 위반을 잡게 한다. 백엔드 별칭 계층은 이미 양쪽 슬러그를 해석하므로 새로 만들 것이 없다.

**조사 문서:** `docs/superpowers/specs/2026-08-27-dgtour-slug-investigation.md`

**리뷰 반영:** 2026-08-27 Codex 검토 4건을 모두 반영해 개정했다. 개정 내역은 문서 끝 "개정 이력" 참조.

## 전역 제약

- **작업 브랜치는 최신 `origin/develop`에서 새로 딴다.** `feature/stabilize-policy-trip-tests`에 얹지 않는다 — 그 브랜치에는 프론트 테스트 안정화 변경이 이미 6커밋 들어 있고, 성격이 다른 두 변경을 한 PR에 섞으면 안 된다.
- **DB 조작은 이 계획에 포함하지 않는다.** 갈라진 링크 병합은 별도 작업이다.
- **기존 데이터가 있는 환경에서 `seed`를 실행하는 것은 링크 병합 또는 명시적 데이터 보존 판단 전까지 금지한다.** 로컬 검증용 실행만 허용하며, 그때도 Task 5의 안전 게이트를 반드시 먼저 통과한다.
- 개발서버(192.168.32.15) git/배포/DB 조작 금지. merge, 운영 승격 금지.
- push / PR 금지. 커밋까지만 한다.
- `backend/scripts/`의 다른 스크립트가 `from app...`를 이미 임포트한다 (`audit_policy_semantics.py`, `normalize_external_policies.py`). 크롤러도 같은 방식을 쓴다.

---

## 배경

### 순번은 어디서 오는가

`backend/scripts/crawl_dgtourcard.py:217`

```python
policy["slug"] = f"dgtour-{slugify(city)}-{entry['id']}"
```

`entry['id']`는 `func_go_detail` 호출의 두 번째 인자 — VisitKorea 페이지에서의 **등장 순번**이다. 시드 JSON의 슬러그가 밀양-1 … 고창-16으로 파일 순서와 정확히 일치하는 것이 그 증거다.

### 중요: 크롤러는 이 JSON의 현재 관리자가 아니다

**이 사실이 Task 1의 근거를 바꾼다.** `backend/app/data/dgtourcard_policies.json`은 크롤러 산출물이 아니다.

- 크롤러의 `_make_policy_dict()`(`:252`)는 13개 필드만 낸다. 시드 JSON에는 크롤러가 만들 수 없는 필드가 7개 있다 — `sourceCanonicalKey`, `sourceCategory`, `sourceName`, `sourceStatus`, `sourceUrl`, `status`, `structuredDetail`
- 크롤러는 `officialUrl`에 `tour50.do`(목록 페이지)를 넣는다. 시드 JSON은 `regnMain.do?mtpcDoCd=..&signguCd=..`(지역 상세)를 갖는다
- 크롤러의 지도 경로는 제목을 `영광 디지털관광주민증 혜택`으로 만든다. 시드 JSON은 `[영광] 디지털관광주민증 혜택`이다
- git 이력상 이 JSON은 크롤 실행이 아니라 손으로 쓴 커밋으로 갱신돼 왔다 (`f12efc2`, `8e773e8`)

**따라서 "시드만 고치면 다음 크롤이 되돌린다"는 근거는 약하다.** 지금 상태로 크롤을 돌리면 슬러그만 되돌아가는 게 아니라 위 7개 필드가 통째로 날아간다. 그래서 아무도 안 돌리는 것으로 보인다.

크롤러를 고치는 진짜 이유는 두 가지다.

1. **슬러그를 만드는 유일한 코드 경로다.** 지금의 `-숫자`는 여기서 한 번 나왔고 그 뒤 손으로 유지됐다. 고쳐두지 않으면 다음에 누가 돌릴 때 같은 버그가 다시 나온다.
2. 값싸다 (한 줄 + 테스트).

**재발을 실제로 막는 것은 크롤러가 아니라 Task 4의 검증기다.** 크롤러 수정은 원인 제거, 검증기는 방어선이다.

### 크롤 실행 시 데이터 손실 위험 (기록)

이 계획은 크롤러를 실행하지 않는다. 다만 고쳐진 크롤러라도 지금 그대로 돌리면 위 7개 필드가 사라진다. **크롤러가 enrich 파이프라인과 어떻게 맞물려야 하는지는 이 계획의 범위 밖이며, 별도 논의가 필요하다.** 스크립트 docstring에 경고를 남기는 것으로 갈음한다 (Task 1 Step 3).

---

## 파일 구성

| 파일 | 역할 | 작업 |
|---|---|---|
| `backend/scripts/crawl_dgtourcard.py` | 슬러그를 만드는 유일한 코드 경로 | 수정 — 규칙 연결, 도시 단위 중복 제거 |
| `backend/tests/test_crawl_dgtourcard.py` | 크롤러 단위 테스트 | **신규** |
| `backend/app/data/dgtourcard_policies.json` | 시드 데이터 (손으로 관리됨) | 수정 — 16건 슬러그 정렬 |
| `backend/scripts/validate_policy_data.py` | 시드 검증기 = 재발 방어선 | 수정 — 슬러그 규칙 추가 |
| `backend/tests/test_policy_data_validation.py` | 검증기 테스트 | 수정 (`bc3afc8` + 추가) |
| `backend/tests/test_policy_source_audit.py` | 시딩 감사 테스트 | 수정 (`bc3afc8`) |
| `frontend/e2e-backend/backend-mode.spec.ts` | e2e 상수 | 수정 (`bc3afc8`) |

---

## Task 0: 브랜치와 기준선

- [ ] **Step 1: preflight**

```bash
git fetch origin
git -C <루트> branch --show-current      # develop 인지
git -C <루트> status --short             # clean 인지
git rev-list --left-right --count develop...origin/develop
```

뒤처졌으면 `git merge --ff-only origin/develop`. dirty하거나 다른 브랜치면 자동 갱신하지 않는다. `reset --hard`와 강제 checkout은 쓰지 않는다.

- [ ] **Step 2: 새 worktree**

```bash
git worktree add .superpowers/worktrees/dgtour-canonical-slug -b feature/dgtour-canonical-slug origin/develop
```

**`feature/stabilize-policy-trip-tests`에서 따지 않는다.**

- [ ] **Step 3: 백엔드 기준선**

```
cd backend
python -m pytest tests/ -q
```

실패 **테스트 이름 목록**을 기록한다. 건수만 기록하지 않는다.

---

## Task 1: 크롤러가 정식 슬러그를 만들게 한다

**파일**
- 수정: `backend/scripts/crawl_dgtourcard.py` (`:180`, `:217`, docstring)
- 신규: `backend/tests/test_crawl_dgtourcard.py`

**인터페이스**
- 사용: `app.services.digital_tourism_resident_card.canonical_policy_slug_for_city(city) -> str | None`
  참여도시면 `dgtour-{도시}`, 비참여면 `None`
- 산출: `parse_policies_from_html(html)`이 `-숫자` 없는 슬러그를 담은 dict 목록을 반환

### 중복 제거 방침 (결정 사항)

기존 `deduplicate()`(`:279`)는 슬러그가 겹치면 `-2`, `-3`을 붙인다. 순번 접미사를 없애면 같은 도시가 두 번 나올 때 이 함수가 **숫자 접미사를 다시 만들어낸다.**

**결정: 슬러그 단계가 아니라 항목 추출 단계에서 도시 기준으로 합친다.**

`extract_map_entries()`(`:180`)의 중복 키가 지금은 `f"{city}:{entry_id}"`다. 같은 도시가 다른 `entry_id`로 두 번 나오면 **두 항목**이 된다. 키를 `city`로 바꾸면 첫 항목만 남아 애초에 충돌이 생기지 않는다. 한 도시는 하나의 정책이라는 것이 이 데이터의 실제 의미이므로 이쪽이 옳다.

`deduplicate()`는 **건드리지 않는다.** 테이블 파서 경로(도시 개념이 없다)의 안전망으로 그대로 둔다.

- [ ] **Step 1: 실패 테스트 작성**

`backend/tests/test_crawl_dgtourcard.py` 신규:

```python
from __future__ import annotations

from scripts.crawl_dgtourcard import parse_policies_from_html

MAP_HTML = (
    """<a href="#" onclick="func_go_detail('영광', '8')" data-signgucd='46870'>영광</a>\n"""
    """<a href="#" onclick="func_go_detail('하동', '3')" data-signgucd='48850'>하동</a>"""
)

# 같은 도시가 서로 다른 entry_id 로 두 번 노출되는 경우
DUPLICATE_CITY_HTML = (
    """<a href="#" onclick="func_go_detail('영광', '8')" data-signgucd='46870'>영광</a>\n"""
    """<a href="#" onclick="func_go_detail('영광', '21')" data-signgucd='46870'>영광</a>"""
)


def test_parse_policies_from_html_uses_canonical_slugs_without_page_order() -> None:
    policies = parse_policies_from_html(MAP_HTML)

    slugs = [policy["slug"] for policy in policies]
    assert slugs == ["dgtour-영광", "dgtour-하동"]


def test_parse_policies_from_html_collapses_a_city_listed_twice() -> None:
    policies = parse_policies_from_html(DUPLICATE_CITY_HTML)

    slugs = [policy["slug"] for policy in policies]
    assert slugs == ["dgtour-영광"]


def test_parse_policies_from_html_maps_signgucd_prefix_to_a_province() -> None:
    """크롤러의 SIGNGU_PREFIX_PROVINCE 매핑이 도는지 확인한다.

    주의: 이 픽스처는 VisitKorea 실제 페이지에서 캡처한 것이 아니라
    _MAP_ENTRY_RE 와 SIGNGU_PREFIX_PROVINCE(:144)에 맞춰 구성한 최소 입력이다.
    46=전남, 48=경남은 크롤러가 가진 매핑이며, 실제 페이지의
    data-signgucd 가 같은 체계인지는 원본 HTML이 없어 확인되지 않았다.
    이 테스트는 크롤러 자신의 로직을 고정할 뿐 실제 페이지를 대표하지 않는다.
    """
    policies = parse_policies_from_html(MAP_HTML)

    regions = {policy["slug"]: policy["region"] for policy in policies}
    assert regions == {"dgtour-영광": "전남", "dgtour-하동": "경남"}
```

- [ ] **Step 2: 실패 확인**

```
cd backend
python -m pytest tests/test_crawl_dgtourcard.py -v
```

기대:

- `..._uses_canonical_slugs_without_page_order` FAIL
  `assert ['dgtour-영광-8', 'dgtour-하동-3'] == ['dgtour-영광', 'dgtour-하동']`
- `..._collapses_a_city_listed_twice` FAIL — 두 항목이 나온다
- `..._maps_signgucd_prefix_to_a_province` **PASS** (region은 안 바꾼다)

세 번째가 실패하면 픽스처가 잘못된 것이니 멈추고 확인한다.

- [ ] **Step 3: 구현**

임포트부에 추가 (`from typing import Any` 아래):

```python
from app.services.digital_tourism_resident_card import canonical_policy_slug_for_city
```

`:180`의 중복 키를 도시 기준으로:

```python
        key = city
```

`:217`의 슬러그 생성:

```python
            policy["slug"] = canonical_policy_slug_for_city(city) or f"dgtour-{slugify(city)}"
```

모듈 docstring(`:1`)에 경고를 추가한다:

```
주의: backend/app/data/dgtourcard_policies.json 은 현재 이 스크립트의 산출물이 아니라
손으로 관리되고 있다. sourceCanonicalKey / structuredDetail / status 등 이 스크립트가
만들지 못하는 필드가 들어 있으므로, 그대로 덮어쓰면 그 필드들이 사라진다.
--output 으로 다른 경로에 쓰고 차이를 확인한 뒤 반영할 것.
```

- [ ] **Step 4: 통과 확인**

```
cd backend
python -m pytest tests/test_crawl_dgtourcard.py -v
```

기대: 3 passed

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

`git apply --check`로 develop에 깨끗이 적용됨을 확인했다.

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

`test_seed_policies_replaces_unlinked_numbered_dgtour_seed_with_canonical_slug`는 `sqlite_db_session`(빈 DB)에서 돌아 통과한다. **이 테스트는 링크가 붙은 중복 행 상황을 덮지 않는다** — 그 경우 재시딩은 순번 행을 삭제하지 않고 hidden으로 돌린다. Task 5에서 다룬다.

---

## Task 3: 나머지 11건도 정렬한다

`bc3afc8`은 active 5건만 바꾼다. 나머지도 맞춰, 나중에 hidden 정책을 active로 올려도 순번이 되살아나지 않게 한다.

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

> **주의:** "이 11건은 링크가 0건"이라는 확인은 **현재 로컬 DB 한 곳에서만** 한 것이다. 개발·운영 DB에서도 참인지는 확인되지 않았다. 그 환경에서 시딩하는 것은 이 계획의 범위 밖이며, 실행 전 같은 확인을 반드시 다시 해야 한다.

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

`json`과 `Path`는 이 파일이 이미 임포트하고 있다 (`:57` 부근 기존 테스트가 같은 방식으로 읽는다). 없으면 추가한다.

- [ ] **Step 2: 실패 확인**

```
cd backend
python -m pytest tests/test_policy_data_validation.py::test_seed_dgtour_slugs_never_carry_a_page_order_suffix -v
```

기대: FAIL — `numbered`에 11건이 남아 있다.

- [ ] **Step 3: JSON 수정**

위 표대로 11건의 `"slug"` 값에서 `-숫자`를 뗀다. **`slug` 필드만 바꾼다.** `sourceCanonicalKey`, `status`, `officialUrl`은 그대로 둔다.

- [ ] **Step 4: 통과 확인**

```
cd backend
python -m pytest tests/test_policy_data_validation.py tests/test_policy_source_audit.py -v
```

기대: 전부 통과. 중복 슬러그가 생기지 않았는지는 기존 검증기(`중복 slug`)가 잡는다.

- [ ] **Step 5: 커밋**

```bash
git add backend/app/data/dgtourcard_policies.json backend/tests/test_policy_data_validation.py
git commit -m "Drop page-order suffixes from the remaining dgtour seed slugs"
```

---

## Task 4: 검증기가 규칙을 강제한다 — 실질적 방어선

`validate_policy_data.py`는 지금 빈 슬러그와 중복만 본다. 크롤러를 고쳐도 이 JSON은 손으로 관리되므로 **재발을 실제로 막는 것은 이 검증기다.**

**파일**
- 수정: `backend/scripts/validate_policy_data.py`
- 수정: `backend/tests/test_policy_data_validation.py`

### 실제 인터페이스

```python
def validate_policy_data(path: Path = DEFAULT_POLICY_DATA_PATH) -> list[str]
```

`backend/scripts/validate_policy_data.py:62`. **리스트를 받는 `validate_policies()`는 존재하지 않는다.** 임시 JSON 파일을 만들어 경로로 넘긴다.

### 검사 범위 (결정 사항)

두 규칙을 넣는다. 첫 번째가 핵심이다.

1. **모든** `digital_tourism_resident_card` 슬러그는 `-숫자`로 끝나면 안 된다 — status·참여 여부 무관
2. active + 참여도시면 슬러그가 `canonical_policy_slug_for_city()` 값과 정확히 같아야 한다

1번이 hidden 정책과 비참여 도시까지 덮으므로, Task 3의 정렬이 나중에 되돌아가는 것을 막는다.

- [ ] **Step 1: 실패 테스트 작성**

```python
def test_validate_policy_data_rejects_a_page_order_suffix_on_any_dgtour_slug(
    tmp_path,
) -> None:
    from scripts.validate_policy_data import validate_policy_data

    source = (
        Path(__file__).parents[1] / "app" / "data" / "dgtourcard_policies.json"
    ).read_text(encoding="utf-8")
    policies = json.loads(source)

    hidden = next(
        policy
        for policy in policies
        if str(policy.get("status")) == "hidden"
        and str(policy["slug"]).startswith("dgtour-")
    )
    hidden["slug"] = f"{hidden['slug']}-99"

    target = tmp_path / "policies.json"
    target.write_text(json.dumps(policies, ensure_ascii=False), encoding="utf-8")

    errors = validate_policy_data(target)

    assert any("-99" in error for error in errors)
```

실제 시드 파일을 복사해 한 항목만 망가뜨린다. 그래서 필수 필드 누락 같은 **다른 이유로** 실패하지 않는다. hidden 항목을 고르므로 규칙 1번(범위 확대)을 정면으로 검사한다.

- [ ] **Step 2: 실패 확인**

```
cd backend
python -m pytest tests/test_policy_data_validation.py::test_validate_policy_data_rejects_a_page_order_suffix_on_any_dgtour_slug -v
```

기대: FAIL — `-99` 오류가 하나도 안 나온다.

**실패 메시지를 눈으로 확인한다.** 다른 이유로 실패하면 테스트가 규칙을 검사하지 못하는 것이다.

- [ ] **Step 3: 구현**

`validate_policy_data.py`의 항목 루프(`:84` 부근, `seen_slugs` 검사 직후)에 추가:

```python
        if str(policy.get("sourceCategory") or "") == "digital_tourism_resident_card":
            if slug.rsplit("-", 1)[-1].isdigit():
                errors.append(
                    f"{slug} must not end with a page-order suffix."
                )
            if str(policy.get("status") or "active") == "active":
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

**전체 백엔드 스위트를 돌린다.** Task 0의 실패 이름 목록과 대조한다.

- [ ] **Step 5: 커밋**

```bash
git add backend/scripts/validate_policy_data.py backend/tests/test_policy_data_validation.py
git commit -m "Enforce canonical dgtour slugs in the seed data validator"
```

---

## Task 5: 로컬 검증 — DB 안전 게이트 먼저

프론트 실패 4건은 **로컬 백엔드 DB 상태에 의존한다.** 재시딩 전에는 그대로 실패한다. 그런데 재시딩은 기존 사용자 링크의 노출을 바꾼다. **백업 없이 돌리지 않는다.**

- [ ] **Step 1: 백업**

```bash
docker exec travel-hunter-onprem-db-1 sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > <스크래치>/travel-hunter-before-dgtour-seed.dump
pg_restore -l <스크래치>/travel-hunter-before-dgtour-seed.dump | head
sha256sum <스크래치>/travel-hunter-before-dgtour-seed.dump
```

`pg_restore -l`이 목록을 못 읽으면 **덤프가 깨진 것이므로 멈춘다.** SHA-256은 기록해 둔다.

- [ ] **Step 2: 행 수 기록 (전)**

```sql
SELECT 'policies' AS t, count(*) FROM policies
UNION ALL SELECT 'trip_policies', count(*) FROM trip_policies
UNION ALL SELECT 'user_saved_policies', count(*) FROM user_saved_policies;
```

dgtour 정책별 링크 수도 함께 기록한다 (조사 문서의 표와 같은 질의).

- [ ] **Step 3: 컨테이너 재빌드 + 시딩**

```bash
docker build -t travel-hunter-onprem-backend <worktree>/backend
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml up -d --no-build backend
docker exec travel-hunter-onprem-backend-1 python -m app.db.seed
```

시딩은 기동 시 자동으로 돌지 않는다 (`app/db/seed.py:295`의 `main()`이 진입점).

- [ ] **Step 4: 행 수 비교 (후) — 중단 기준**

Step 2와 같은 질의를 다시 돌린다.

**`trip_policies` 또는 `user_saved_policies` 행 수가 30% 이상 변하면 즉시 멈추고 백업에서 복원한 뒤 보고한다.** 이 작업은 링크 행을 지우지 않는다 — 정책 행의 `status`만 바뀐다. 링크 수가 줄었다면 예상 밖의 일이 벌어진 것이다.

`policies` 행 수는 줄어드는 것이 정상이다 (링크 없는 순번 행 11건 삭제).

- [ ] **Step 5: 실제로 반영됐는지 확인**

```bash
curl -s "http://127.0.0.1:8000/api/policies?limit=300" \
  | python -c "import json,sys; print(sorted(p['slug'] for p in json.load(sys.stdin) if p['slug'].startswith('dgtour-')))"
```

기대: `['dgtour-영광', 'dgtour-완도', 'dgtour-하동', 'dgtour-합천', 'dgtour-해남']` — 순번 없음.

- [ ] **Step 6: 프론트 스위트**

```
cd frontend
npx vitest run
```

기준선 **289 passed / 6 failed** → **291 passed / 2 failed** 기대. 실패 **이름 목록**으로 대조한다.

**실행 중에는 컨테이너를 건드리지 않는다** — 과거에 스위트 실행 중 백엔드를 재빌드해 실패가 부풀려진 적이 있다.

남는 2건은 `mypage.test.tsx`의 `expected undefined to be truthy` 2건으로, 원인이 다르고 범위 밖이다.

### 사용자 확인 요청 전 반드시 알릴 것

재시딩 후 **영광·하동의 노출 극성이 뒤집힌다.**

| 슬러그 | 지금 | 재시딩 후 |
|---|---|---|
| `dgtour-영광` (일정 1, 찜 1) | hidden — 안 보임 | **active — 다시 보임** |
| `dgtour-영광-8` (찜 1, 08-27 저장) | active — 보임 | **hidden — 안 보임** |
| `dgtour-하동` (일정 1) | hidden | **active** |
| `dgtour-하동-3` (일정 2) | active | **hidden** |

08-27에 저장한 영광 찜과 하동 일정 연결 2건이 화면에서 사라진다. **데이터가 지워지는 것은 아니다** — 행은 남고 `status`만 hidden이 된다. 후속 병합 작업으로 되살릴 수 있고, Step 1의 백업으로도 되돌릴 수 있다. 사용자에게 테스트를 요청하기 **전에** 이 사실을 전달한다.

---

## 이 계획이 하지 않는 것 — 후속 작업

**갈라진 링크 병합.** 영광·하동은 DB에 두 행으로 존재하고 사용자 링크가 양쪽에 흩어져 있다.

```
user_saved_policies:  user 1 이 dgtour-영광 과 dgtour-영광-8 을 둘 다 찜
trip_policies:        trip 1 이 dgtour-하동 과 dgtour-하동-3 에 둘 다 연결
```

겹침이 있으므로 `UPDATE ... SET policy_id = <정식행>`을 그대로 돌리면 `(user_id, policy_id)` / `(trip_id, policy_id)` 유일 제약에 걸린다. **중복 제거를 먼저 하고 옮겨야 한다.** 기존 사용자 데이터를 건드리므로 되돌릴 수 있는 별도 작업으로 분리한다. 향후 DB 유니크 제약 추가도 그 작업에서 함께 판단한다.

**그 밖에 하지 않을 것**

- 크롤러 실행 (실제 VisitKorea 사이트 호출 + 위 7개 필드 손실 위험)
- 크롤러와 enrich 파이프라인의 관계 정리 — 별도 논의
- `mypage.test.tsx` 잔여 2건 — 원인 미조사
- 프론트 테스트가 로컬 백엔드에 의존하는 구조 — 별도 논의
- `deduplicate()` 재작성
- 개발·운영 DB 시딩
- push / PR / merge

---

## 개정 이력

**2026-08-27 — Codex 검토 반영**

| 지적 | 확인 결과 | 반영 |
|---|---|---|
| 재시딩 전 DB 안전 게이트 부재 | 타당 | Task 5로 분리. 백업·`pg_restore -l` 검증·SHA-256·행 수 전후 비교·30% 중단 기준 추가. 전역 제약에 "기존 데이터 환경 seed 금지" 명시 |
| "11건 링크 0건"은 로컬 DB에만 해당 | 타당 | Task 3에 경고 추가 |
| `deduplicate()`가 숫자를 다시 만든다 | 타당 | 결정 명시 — `extract_map_entries`의 키를 도시 기준으로 바꿔 원천에서 합침. `deduplicate()`는 테이블 경로 안전망으로 유지. 중복 도시 테스트 추가 |
| 검증기 범위가 좁다 (active + 참여도시만) | 타당 | 규칙 1번(모든 dgtour 슬러그에 `-숫자` 금지)을 추가해 hidden·비참여까지 덮음 |
| `validate_policies()`는 존재하지 않음 | 타당 — 실제는 `validate_policy_data(path: Path) -> list[str]` (`:62`) | 임시 JSON 파일 기반 테스트로 교체 |
| 픽스처 `data-signgucd`가 조사 문서와 불일치 | 타당 | region 테스트에 "실제 페이지를 대표하지 않음" 명시. 슬러그 테스트가 핵심이고 그쪽은 코드에 의존하지 않음 |
| dgtour 구현은 별도 브랜치여야 함 | 타당 | Task 0 추가. 최신 `origin/develop`에서 새 worktree |

**추가 발견 (검토 중 확인)**

시드 JSON은 크롤러 산출물이 **아니다.** 크롤러가 만들 수 없는 필드 7개를 갖고 있고 `officialUrl` 경로도 다르며, git 이력상 손으로 관리돼 왔다. 따라서 "시드만 고치면 다음 크롤이 되돌린다"는 원래 근거는 약하다. Task 1의 근거를 "슬러그를 만드는 유일한 코드 경로이므로 원인을 제거한다"로 바꾸고, 재발 방어의 무게를 Task 4 검증기로 옮겼다. 크롤 실행 시 필드 손실 위험도 기록했다.
