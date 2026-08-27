# dgtour 정식 슬러그 계약 완성 계획

> **작업자 안내:** 각 Task는 실패 테스트를 먼저 쓰고 빨간 것을 확인한 뒤 구현한다. 단계는 체크박스로 추적한다.

**목표:** 이미 결정된 "정식 도시 슬러그 = 저장 정체성, 순번 슬러그 = 호환 별칭" 계약을 시드·크롤러·검증기까지 확장한다.

**조사 문서:** `docs/superpowers/specs/2026-08-27-dgtour-slug-investigation.md`

**개정:** 2026-08-27. 최초 판(`c64179d`)과 1차 개정(`5d46d03`)은 방향이 미정이라고 봤으나 **틀렸다.** 자세한 정정은 문서 끝 "개정 이력" 참조.

---

## 결정된 계약 (재확인, 새로 정하는 것 아님)

`b26aa9b` (2026-07-26):

```
Use stable dgtour city slugs for digital tourism resident-card policies while
preserving legacy URL aliases for old dgtour-numbered and travelmonth-derived links.

Constraint: public policy links must not expose stale numbered digital tourism slugs.
Rejected: removing legacy URLs outright | existing saved links and shared detail URLs
          still need compatibility.
Directive: after deploy, run the external collection job so existing dev DB rows are
           promoted to canonical dgtour city slugs.
```

```
저장/API 정본:  dgtour-하동
호환 별칭:      dgtour-하동-3   (조회는 되지만 노출하지 않는다)
```

**이 계획은 방향을 정하지 않는다. 아직 계약을 안 지키는 세 곳을 계약에 맞춘다.**

| 구성요소 | 계약 준수 여부 |
|---|---|
| 정규화 파이프라인 (`policy_normalization.py`) | ✅ 정식 슬러그 생성·개명 |
| 별칭 해석기 (`digital_tourism_policy_aliases.py`) | ✅ 순번 슬러그도 해석 |
| `frozen_legacy_dgtour_slugs()` | ✅ 과도기 보호 장치 — **유지한다** |
| 시드 JSON | ❌ 순번 슬러그 |
| 크롤러 | ❌ 순번 슬러그 생성 |
| 시드 검증기 | ❌ 규칙 없음 |

지금 `/api/policies`가 `dgtour-영광-8`을 내보내는 것은 위 Constraint 위반이다. 프론트 테스트 4건이 `dgtour-영광`을 기대한 것은 처음부터 옳았고, 그 실패는 진짜 버그 신고다.

### `frozen_legacy_dgtour_slugs()`는 지우지 않는다

1차 개정판은 "시드를 정식으로 바꾸면 이 집합이 아무 행과도 안 맞아 가드가 무력화된다"고 적었다. **틀렸다.** 기존 DB(로컬·개발서버)에는 링크가 붙은 순번 행이 그대로 남아 있고, 이 집합은 그 행들을 다른 정규화·삭제 처리로부터 보호한다. 시드가 정식 슬러그를 쓰게 되어도 **보호 대상은 계속 존재한다.**

## 전역 제약

- **작업 브랜치는 최신 `origin/develop`에서 새로 딴다.** `feature/stabilize-policy-trip-tests`에 얹지 않는다.
- **기존 데이터가 있는 환경에서 `seed` 실행은 백업과 링크 병합 판단 전까지 금지한다.** 로컬 검증용 실행만 허용하며 Task 5의 안전 게이트를 먼저 통과한다.
- **중복 행 병합은 이 계획에 없다.** 별도 데이터 마이그레이션으로 설계한다.
- 개발서버(192.168.32.15) git/배포/DB 조작 금지. merge, 운영 승격 금지.
- push / PR 금지. 커밋까지만 한다.
- `backend/scripts/`의 다른 스크립트가 `from app...`를 이미 임포트한다 (`audit_policy_semantics.py`, `normalize_external_policies.py`). 크롤러도 같은 방식을 쓴다.

---

## 알아둘 것: 시드 JSON은 크롤러 산출물이 아니다

- 크롤러 `_make_policy_dict()`(`:252`)는 13개 필드만 낸다. 시드 JSON에는 크롤러가 못 만드는 필드가 7개 있다 — `sourceCanonicalKey`, `sourceCategory`, `sourceName`, `sourceStatus`, `sourceUrl`, `status`, `structuredDetail`
- 크롤러는 `officialUrl`에 `tour50.do`(목록)를 넣는데 시드 JSON은 `regnMain.do`(지역 상세)를 갖는다
- git 이력상 이 JSON은 크롤 실행이 아니라 손으로 쓴 커밋으로 갱신돼 왔다 (`f12efc2`, `8e773e8`)

**그래서 크롤 실행은 이 계획에 없다.** 크롤러를 고치는 이유는 슬러그를 만드는 유일한 코드 경로라 원인을 제거하기 위함이고, 재발을 실제로 막는 것은 Task 4의 검증기다. 크롤러를 지금 그대로 돌리면 위 7개 필드가 날아가므로 docstring에 경고를 남긴다.

---

## Task 0: 브랜치와 기준선

- [ ] **Step 1: preflight**

```bash
git fetch origin
# 루트가 develop 이고 clean 인지 확인
git rev-list --left-right --count develop...origin/develop
```

뒤처졌으면 `git merge --ff-only origin/develop`. dirty하거나 다른 브랜치면 자동 갱신하지 않는다. `reset --hard`와 강제 checkout은 쓰지 않는다.

- [ ] **Step 2: 새 worktree**

```bash
git worktree add .superpowers/worktrees/dgtour-canonical-slug -b feature/dgtour-canonical-slug origin/develop
```

- [ ] **Step 3: 백엔드 기준선**

```
cd backend
python -m pytest tests/ -q
```

실패 **테스트 이름 목록**을 기록한다. 건수만 기록하지 않는다.

---

## Task 1: 크롤러를 정식 슬러그 규칙에 연결

**파일**
- 수정: `backend/scripts/crawl_dgtourcard.py` (`:180`, `:217`, docstring)
- 신규: `backend/tests/test_crawl_dgtourcard.py`

**인터페이스**
- 사용: `app.services.digital_tourism_resident_card.canonical_policy_slug_for_city(city) -> str | None`
- 산출: `parse_policies_from_html(html)`이 `-숫자` 없는 슬러그를 담은 dict 목록을 반환

### 중복 제거 방침 (결정 사항)

기존 `deduplicate()`(`:279`)는 슬러그가 겹치면 `-2`, `-3`을 붙인다. 순번을 없애면 같은 도시가 두 번 나올 때 이 함수가 **숫자 접미사를 다시 만든다.**

**결정: 슬러그 단계가 아니라 항목 추출 단계에서 도시 기준으로 합친다.** `extract_map_entries()`(`:180`)의 중복 키가 지금은 `f"{city}:{entry_id}"`라, 같은 도시가 다른 `entry_id`로 두 번 나오면 두 항목이 된다. 키를 `city`로 바꾸면 애초에 충돌이 안 생긴다. 한 도시는 하나의 정책이라는 것이 이 데이터의 실제 의미다.

`deduplicate()`는 **건드리지 않는다.** 도시 개념이 없는 테이블 파서 경로의 안전망으로 그대로 둔다.

- [ ] **Step 1: 실패 테스트 작성**

`backend/tests/test_crawl_dgtourcard.py` 신규:

```python
from __future__ import annotations

from scripts.crawl_dgtourcard import parse_policies_from_html

MAP_HTML = (
    """<a href="#" onclick="func_go_detail('영광', '8')" data-signgucd='46870'>영광</a>\n"""
    """<a href="#" onclick="func_go_detail('하동', '3')" data-signgucd='48850'>하동</a>"""
)

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
    """크롤러의 SIGNGU_PREFIX_PROVINCE(:144) 매핑이 도는지 확인한다.

    주의: 이 픽스처는 VisitKorea 실제 페이지에서 캡처한 것이 아니라
    _MAP_ENTRY_RE 와 그 매핑에 맞춰 구성한 최소 입력이다. 실제 페이지의
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

임포트부 (`from typing import Any` 아래):

```python
from app.services.digital_tourism_resident_card import canonical_policy_slug_for_city
```

`:180` 중복 키:

```python
        key = city
```

`:217` 슬러그 생성:

```python
            policy["slug"] = canonical_policy_slug_for_city(city) or f"dgtour-{slugify(city)}"
```

모듈 docstring(`:1`)에 경고 추가:

```
주의: backend/app/data/dgtourcard_policies.json 은 현재 이 스크립트의 산출물이 아니라
손으로 관리되고 있다. sourceCanonicalKey / structuredDetail / status 등 이 스크립트가
만들지 못하는 필드가 들어 있으므로, 그대로 덮어쓰면 그 필드들이 사라진다.
--output 으로 다른 경로에 쓰고 차이를 확인한 뒤 반영할 것.
```

- [ ] **Step 4: 통과 확인** — `python -m pytest tests/test_crawl_dgtourcard.py -v` → 3 passed

- [ ] **Step 5: 커밋**

```bash
git add backend/scripts/crawl_dgtourcard.py backend/tests/test_crawl_dgtourcard.py
git commit -m "Derive dgtour crawl slugs from the canonical city rule"
```

---

## Task 2: `bc3afc8` 반영 (active 5건 + 테스트 + e2e 상수)

`git apply --check`로 develop에 깨끗이 적용됨을 확인했다.

- [ ] **Step 1:** `git cherry-pick bc3afc8`

충돌이 나면 멈추고 보고한다. Task 1이 JSON을 안 건드리므로 충돌은 없어야 한다.

- [ ] **Step 2: 가져온 테스트 실행**

```
cd backend
python -m pytest tests/test_policy_data_validation.py tests/test_policy_source_audit.py -v
```

기대: 전부 통과.

`test_seed_policies_replaces_unlinked_numbered_dgtour_seed_with_canonical_slug`는 `sqlite_db_session`(빈 DB)에서 돌아 통과한다. **링크가 붙은 중복 행 상황은 덮지 않는다.** Task 3-A와 Task 5에서 다룬다.

---

## Task 3: 나머지 11건 정렬

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

강진·남해·영암·횡성은 비참여 도시라 `canonical_policy_slug_for_city`가 `None`을 준다. Task 1의 폴백이 같은 값을 내므로 결과는 동일하다.

> **주의:** "이 11건은 링크가 0건"이라는 확인은 **현재 로컬 DB 한 곳에서만** 한 것이다. 개발·운영 DB에서도 참인지는 확인되지 않았다. 그 환경 시딩은 범위 밖이며, 실행 전 같은 확인을 반드시 다시 해야 한다.

- [ ] **Step 1: 실패 테스트 작성**

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

- [ ] **Step 2: 실패 확인** — `numbered`에 11건이 남아 있어야 한다

- [ ] **Step 3: JSON 수정** — 위 표대로 `"slug"` 필드만 바꾼다. `sourceCanonicalKey`, `status`, `officialUrl`은 그대로

- [ ] **Step 3-B: 시드 JSON을 슬러그로 인덱싱하는 기존 테스트 수정 (확인된 파손)**

`backend/tests/test_policy_data_validation.py:85` `test_seed_dgtour_non_participating_regions_are_hidden`이
시드 JSON을 읽어 `by_slug["dgtour-강진-7"]` 식으로 접근한다. Step 3이 그 4건을 개명하므로 **KeyError로 깨진다.**

```python
    for slug in ("dgtour-강진", "dgtour-남해", "dgtour-영암", "dgtour-횡성"):
        assert by_slug[slug]["status"] == "hidden"
```

**이것이 시드 JSON 변경으로 깨지는 유일한 기존 테스트다.** 순번 슬러그를 참조하는 나머지 25곳은 확인 결과 영향이 없다:

- `test_travel_areas.py:165`, `test_source_provenance_migration_postgres.py` — 테스트가 **자기 픽스처로** 그 슬러그의 행을 직접 만든다. 시드와 무관하다
- `test_digital_tourism_resident_card.py:37` — `city_from_policy_slug("dgtour-하동-3") == "하동"`. 별칭 해석 함수를 검사하며 **이 함수는 유지한다**
- `test_policy_semantics_audit.py` — `legacy-dgtour-밀양-1`은 `source_canonical_key` 문자열이고 슬러그가 아니다

그래도 Step 4에서 **전체 스위트로 확인한다.** 위 분류는 정적 판독이며 실행 결과가 우선한다.

- [ ] **Step 4: 통과 확인**

```
cd backend
python -m pytest tests/test_policy_data_validation.py tests/test_policy_source_audit.py -v
```

- [ ] **Step 5: 커밋**

```bash
git add backend/app/data/dgtourcard_policies.json backend/tests/test_policy_data_validation.py
git commit -m "Drop page-order suffixes from the remaining dgtour seed slugs"
```

### 확인된 사실: 기존에 공유된 URL은 계속 열린다

실행 중인 로컬 백엔드에서 양방향을 실측했다.

```
요청 /api/policies/dgtour-영광    -> 응답 slug: dgtour-영광-8   (정식 행은 지금 hidden)
요청 /api/policies/dgtour-영광-8  -> 응답 slug: dgtour-영광-8
```

별칭 해석기가 슬러그가 아니라 **도시 → `source_canonical_key` → active 정책** 순으로 찾기 때문에, 어느 쪽 주소로 와도 그 시점의 활성 정책이 돌아온다. 변경 후에는 둘 다 `slug: dgtour-영광`을 반환한다. **이미 공유된 `-8` 주소는 깨지지 않는다.**

---

## Task 3-A: 정식 시드 행이 숨겨지지 않는지 회귀 테스트

시드가 정식 슬러그를 쓰게 되면 그 행은 `frozen_legacy_dgtour_slugs()`에 없고 `external_source_record_id`도 `NULL`이다. `_hide_legacy_dgtour_seed_policies()`(`policy_normalization.py:541`)의 보호 조건은

```
slug in frozen  또는  (source_category == dgtour AND external_source_record_id IS NOT NULL AND 참여도시)
```

이므로 **둘 다 통과하지 못해 hidden 처리될 가능성이 있다.** 이 함수는 `promoted_categories`에 `local_half_trip`이 있을 때만 도는 조건부 경로라 실제 발동 여부는 확인이 필요하다.

**추측으로 코드를 고치지 않는다. 테스트로 먼저 확인한다.**

- [ ] **Step 1: 확인 테스트 작성**

`backend/tests/test_policy_normalization.py`에 추가. 정식 슬러그 시드 행(외부 레코드 없음)을 만들고, `local_half_trip` 레코드가 포함된 승격을 돌린 뒤 `status`를 본다.

```python
def test_promotion_keeps_canonical_dgtour_seed_policies_visible(db: Session) -> None:
    seed = Policy(
        slug="dgtour-영광",
        title="[영광] 디지털관광주민증 혜택",
        status="active",
        source_category="digital_tourism_resident_card",
        source_canonical_key="digital-tourism-resident-card:전남:영광",
    )
    db.add(seed)
    db.flush()

    # local_half_trip 레코드를 포함해 _hide_legacy_dgtour_seed_policies 경로를 태운다.
    # 레코드 구성은 같은 파일의 기존 local_half_trip 테스트를 그대로 따른다.
    ...

    promote_external_benefits_to_policies(db)

    assert seed.status == "active"
```

`...` 부분은 같은 파일에서 `local_half_trip`을 쓰는 기존 테스트의 픽스처 구성을 그대로 재사용한다. **새로 지어내지 않는다.**

- [ ] **Step 2: 실행해 실제 동작을 본다**

```
cd backend
python -m pytest tests/test_policy_normalization.py::test_promotion_keeps_canonical_dgtour_seed_policies_visible -v
```

- **PASS면** 회귀가 없다는 뜻이다. 테스트를 그대로 남겨 보호막으로 쓰고 Task 4로 넘어간다
- **FAIL이면** 실제 회귀다. `_hide_legacy_dgtour_seed_policies`의 보호 조건에 "참여도시의 정식 슬러그"를 추가해야 한다. **그 수정은 별도 커밋으로 하고, 왜 필요한지 커밋 메시지에 적는다**

- [ ] **Step 3: 커밋**

```bash
git add backend/tests/test_policy_normalization.py
git commit -m "Cover canonical dgtour seed policies against legacy hiding"
```

---

## Task 4: 검증기가 규칙을 강제한다 — 실질적 방어선

시드 JSON이 손으로 관리되므로 **재발을 실제로 막는 것은 이 검증기다.**

### 실제 인터페이스

```python
def validate_policy_data(path: Path = DEFAULT_POLICY_DATA_PATH) -> list[str]
```

`backend/scripts/validate_policy_data.py:62`. **리스트를 받는 `validate_policies()`는 존재하지 않는다.** 임시 JSON 파일을 만들어 경로로 넘긴다.

### 검사 범위 (결정 사항)

1. **모든** `digital_tourism_resident_card` 슬러그는 `-숫자`로 끝나면 안 된다 — status·참여 여부 무관
2. active + 참여도시면 슬러그가 `canonical_policy_slug_for_city()` 값과 정확히 같아야 한다

1번이 hidden·비참여까지 덮어 Task 3의 정렬이 되돌아가는 것을 막는다.

> 이 규칙은 **시드 JSON에만** 적용된다. 마이그레이션 0031이 하드코딩한 순번 슬러그나 `frozen_legacy_dgtour_slugs()`는 별칭·보호 목적의 과거 데이터이므로 대상이 아니다.

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

실제 시드 파일을 복사해 한 항목만 망가뜨린다. 필수 필드 누락 같은 **다른 이유로** 실패하지 않는다. hidden 항목을 고르므로 규칙 1번을 정면으로 검사한다.

- [ ] **Step 2: 실패 확인**

기대: FAIL — `-99` 오류가 안 나온다. **실패 메시지를 눈으로 확인한다.** 다른 이유로 실패하면 테스트가 규칙을 검사하지 못하는 것이다.

- [ ] **Step 3: 구현**

`validate_policy_data.py`의 항목 루프(`:84` 부근, `seen_slugs` 검사 직후):

```python
        if str(policy.get("sourceCategory") or "") == "digital_tourism_resident_card":
            if slug.rsplit("-", 1)[-1].isdigit():
                errors.append(f"{slug} must not end with a page-order suffix.")
            if str(policy.get("status") or "active") == "active":
                city = official.city_from_policy_slug(slug)
                canonical_slug = official.canonical_policy_slug_for_city(city)
                if canonical_slug and slug != canonical_slug:
                    errors.append(
                        f"{slug} must use the canonical dgtour slug {canonical_slug}."
                    )
```

`official`은 `digital_tourism_resident_card` 모듈을 가리키는 이름이다. 임포트가 없으면 추가하되 `test_policy_data_validation.py`의 임포트 이름에 맞춘다.

- [ ] **Step 4: 통과 확인**

```
cd backend
python -m pytest tests/ -q
```

**전체 백엔드 스위트.** Task 0의 실패 이름 목록과 대조한다.

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

`pg_restore -l`이 목록을 못 읽으면 **덤프가 깨진 것이므로 멈춘다.** SHA-256은 기록한다.

- [ ] **Step 2: 행 수 기록 (전)**

```sql
SELECT 'policies' AS t, count(*) FROM policies
UNION ALL SELECT 'trip_policies', count(*) FROM trip_policies
UNION ALL SELECT 'user_saved_policies', count(*) FROM user_saved_policies;
```

dgtour 정책별 링크 수도 함께 기록한다 (조사 문서의 표와 같은 질의).

- [ ] **Step 3: 재빌드 + 시딩**

```bash
docker build -t travel-hunter-onprem-backend <worktree>/backend
docker compose --env-file .env -p travel-hunter-onprem -f compose.local.yaml up -d --no-build backend
docker exec travel-hunter-onprem-backend-1 python -m app.db.seed
```

시딩은 기동 시 자동으로 돌지 않는다 (`app/db/seed.py:295`의 `main()`이 진입점).

- [ ] **Step 4: 행 수 비교 (후) — 중단 기준**

**`trip_policies` 또는 `user_saved_policies` 행 수가 30% 이상 변하면 즉시 멈추고 백업에서 복원한 뒤 보고한다.** 이 작업은 링크 행을 지우지 않는다 — 정책 행의 `status`만 바뀐다. 링크 수가 줄었다면 예상 밖의 일이다.

`policies` 행 수는 줄어드는 것이 정상이다 (링크 없는 순번 행 11건 삭제).

- [ ] **Step 5: 반영 확인**

```bash
curl -s "http://127.0.0.1:8000/api/policies?limit=300" \
  | python -c "import json,sys; print(sorted(p['slug'] for p in json.load(sys.stdin) if p['slug'].startswith('dgtour-')))"
```

기대: `['dgtour-영광', 'dgtour-완도', 'dgtour-하동', 'dgtour-합천', 'dgtour-해남']`

- [ ] **Step 6: 프론트 스위트**

```
cd frontend
npx vitest run
```

**이 브랜치(`feature/dgtour-canonical-slug`)에서 돌린다.** `feature/stabilize-policy-trip-tests`와 기준선이 다르니 섞지 않는다.

| 브랜치 | 기준선 | 슬러그 4건 해소 후 |
|---|---|---|
| `feature/dgtour-canonical-slug` (develop 기준) | 288 passed / 7 failed | **292 passed / 3 failed** |
| `feature/stabilize-policy-trip-tests` (참고) | 289 passed / 6 failed | 293 passed / 2 failed |

총 295건이다. 이 브랜치에는 policy-scope 목 수정(`04ed2d0`)이 없어 `keeps the trip-attached state scoped to the selected policy`가 계속 실패한다 — **회귀가 아니다.**

실패 **이름 목록**으로 대조한다. 건수만 보지 않는다.

**실행 중에는 컨테이너를 건드리지 않는다** — 과거에 스위트 실행 중 백엔드를 재빌드해 실패가 부풀려진 적이 있다.

남는 3건은 `mypage.test.tsx`의 `expected undefined to be truthy` 2건(원인이 다르고 범위 밖)과 위의 policy-scope 1건이다.

### 사용자 확인 요청 전 반드시 알릴 것

재시딩 후 **영광·하동의 노출 극성이 뒤집힌다.**

| 슬러그 | 지금 | 재시딩 후 |
|---|---|---|
| `dgtour-영광` (일정 1, 찜 1) | hidden — 안 보임 | **active — 다시 보임** |
| `dgtour-영광-8` (찜 1, 08-27 저장) | active — 보임 | **hidden — 안 보임** |
| `dgtour-하동` (일정 1) | hidden | **active** |
| `dgtour-하동-3` (일정 2) | active | **hidden** |

08-27에 저장한 영광 찜과 하동 일정 연결 2건이 화면에서 사라진다. **데이터가 지워지는 것은 아니다** — 행은 남고 `status`만 hidden이 된다. 후속 병합 작업으로 되살릴 수 있고 Step 1의 백업으로도 되돌릴 수 있다. 테스트를 요청하기 **전에** 전달한다.

---

## 후속 작업: 중복 행 병합 (별도 계획)

`b26aa9b`의 directive는 "외부 수집 작업을 돌려 기존 행을 정식 슬러그로 승격하라"였다. 승격 경로는 이미 구현돼 있다 (`external_benefit_collection` → `promote_external_benefits_to_policies`). 하지만 **이미 두 행으로 갈라진 영광·하동은 승격만으로 합쳐지지 않는다.**

```
user_saved_policies:  user 1 이 dgtour-영광 과 dgtour-영광-8 을 둘 다 찜
trip_policies:        trip 1 이 dgtour-하동 과 dgtour-하동-3 에 둘 다 연결
```

겹침이 있어 `UPDATE ... SET policy_id = <정식행>`을 그대로 돌리면 `(user_id, policy_id)` / `(trip_id, policy_id)` 유일 제약에 걸린다. **중복 제거를 먼저 하고 옮겨야 한다.**

별도 계획에서 다룰 것:

1. 정식 행 생존, 순번 행 폐기 원칙 확정
2. 찜·일정 연결 중복 제거 후 정식 행으로 이동
3. 순번 행 삭제 또는 hidden 유지 판단 (별칭 해석은 슬러그가 아니라 `source_canonical_key` 기반이므로 삭제해도 별칭은 동작하는지 확인 필요)
4. `frozen_legacy_dgtour_slugs()` 축소 또는 제거 시점 판단
5. 향후 `(source_category, source_canonical_key)` 유니크 제약 추가 검토
6. 백업·복원 검증을 포함한 실행 절차

**그 밖에 하지 않을 것**

- 크롤러 실행 (실제 사이트 호출 + 7개 필드 손실 위험)
- 크롤러와 enrich 파이프라인의 관계 정리 — 별도 논의
- `mypage.test.tsx` 잔여 2건 — 원인 미조사
- 프론트 테스트가 로컬 백엔드에 의존하는 구조 — 별도 논의
- 개발·운영 DB 시딩
- push / PR / merge

---

## 개정 이력

**2026-08-27 2차 개정 — 방향 오판 정정**

1차 개정판은 "순번 슬러그가 마이그레이션 0031이 채택한 안정 식별자이므로 방향이 미정"이라고 결론지었다. **틀렸다.** `b26aa9b`(0031 이틀 뒤, 2026-07-26)가 이미 "정식 도시 슬러그 = 저장 정체성, 순번 = 호환 별칭"을 명시했다.

| 1차 개정판의 오독 | 실제 |
|---|---|
| 0031이 순번 슬러그를 영구 정본으로 선언 | 0031은 당시 행을 제자리 교정하는 idempotent 마이그레이션. 하드코딩된 16개는 행을 **찾기 위한 매핑**이며 slug를 순번형으로 바꾸거나 고정하지 않는다 |
| 새 DB 재생 시 0031이 행을 못 찾는다 | 새 DB는 Alembic 후 seed가 돌아 0031 시점에 정책 행이 없다. 정식 행이 있어도 `LIKE 'dgtour-%'`에는 걸리고 `known_dgtour` 값만 NULL이 된다 |
| 두 축이 어긋나 방향 미정 | 어긋난 것은 시드 JSON·크롤러·검증기 셋뿐. 파이프라인·테스트·별칭 해석기는 전부 정식 편 |
| `frozen_legacy_dgtour_slugs()`가 순번 정본의 증거 | 과도기 보호 장치. **유지한다** — 기존 DB에 링크 붙은 순번 행이 남아 있어 보호 대상은 계속 존재한다 |
| 시드를 바꾸면 frozen 집합이 무력화된다 | 무력화되지 않는다. 보호 대상은 시드가 아니라 DB의 기존 행이다 |

**1차 개정(Codex 검토 반영)에서 유지되는 것**

DB 안전 게이트(Task 5), 도시 단위 중복 제거 결정(Task 1), 검증기 범위 확대와 실제 인터페이스(Task 4), 픽스처 한계 명시, 별도 브랜치(Task 0), "11건 링크 0건은 로컬 한정" 경고. 여기에 정식 시드 행 숨김 회귀 테스트(Task 3-A)를 추가했다.

---

## 실행 결과 (2026-08-27)

### 테스트

| 스위트 | 기준선 | 결과 |
|---|---|---|
| 백엔드 | 673 passed / 1 failed / 23 skipped | **680 passed / 1 failed / 23 skipped** |
| 프론트 | 288 passed / 7 failed (295건) | **294 passed / 1 failed** |

백엔드의 실패 1건은 기준선과 동일한 `test_restricted_atomic_artifact_and_sidecar_round_trip`이다. Windows에서 임시 디렉터리 권한이 `S_IMODE & 0o077` 검사를 통과하지 못해 나는 환경 이슈이며 이번 작업과 무관하다.

프론트는 **7건 중 6건이 해소**됐다. 예상은 4건(슬러그 불일치)이었는데, `mypage.test.tsx`의 `expected undefined to be truthy` 2건도 같이 사라졌다 — 이 두 건 역시 로컬 백엔드의 dgtour 데이터 상태에 의존하고 있었다.

남은 1건 `policies.test.tsx :: keeps the trip-attached state scoped to the selected policy`는 **회귀가 아니다.** 이 테스트에 목을 넣는 수정은 `feature/stabilize-policy-trip-tests`의 `04ed2d0`에 있고 이 브랜치에는 없다. 두 브랜치가 모두 머지되면 295/0이 될 것으로 예상된다 (합쳐서 실행해 확인하지는 않았다).

### API

```
목록     ['dgtour-영광','dgtour-완도','dgtour-하동','dgtour-합천','dgtour-해남']   순번 0건
옛 주소  /api/policies/dgtour-영광-8  ->  slug: dgtour-영광
        /api/policies/dgtour-하동-3  ->  slug: dgtour-하동
```

계약대로 정식 슬러그만 노출하고 기존 공유 링크는 계속 열린다.

### DB 안전 게이트

백업: `D:\backup\travel-hunter-before-dgtour-seed-20260827.dump`, SHA-256 `6d36ff34…3b6a9b`, `pg_restore -l` TOC 208항목 판독 확인.

| 테이블 | 시딩 전 | 시딩 후 |
|---|---|---|
| `policies` | 109 | 109 |
| `trip_policies` | 7 | **8** |
| `user_saved_policies` | 2 | 2 |

`trip_policies` +1은 **중단 기준에 걸려 조사했고 손상이 아님을 확인했다.**

trip 243이 시드 트립이다 (owner 1, `제주 3일 여행`, start_date 2026-06-15 — `get_or_create_trip`의 조건과 일치). `seed_dev_data`(`:285`)는 항상 **첫 번째 active 정책**을 시드 트립에 붙이는데, 그 첫 active가 `dgtour-하동-3`(링크 id 10, 08-25 시딩분)에서 `dgtour-하동`(링크 id 19)으로 바뀐 것뿐이다. 같은 도시이고 사용자 링크는 삭제·이동 0건이다.

`policies`가 109로 같은 것도 정상이다 — 링크 없는 순번 행 11건이 삭제되고 정식 행 11건이 생겨 상쇄됐다.

### 계획에 없던 수정 1건

`validate_policy_data.py`가 `app`을 임포트하게 되면서 **독립 실행(CLI)이 `ModuleNotFoundError`로 깨졌다.** `normalize_external_policies.py`와 같은 방식으로 `sys.path`를 세워 고쳤고, `backend/`와 다른 디렉터리 양쪽에서 실행해 확인했다.

### 예측이 맞은 것

- **Task 3-A의 회귀는 실재했다.** 테스트를 먼저 써서 정식 시드 행이 실제로 hidden 처리되는 것을 확인한 뒤 `_hide_legacy_dgtour_seed_policies`에 보호 조건을 추가했다. 추측으로 미리 고쳤다면 근거 없는 변경이 될 뻔했다
- **`test_seed_dgtour_non_participating_regions_are_hidden` 1건만 깨졌다.** 순번 슬러그를 참조하는 나머지 25곳은 예상대로 무영향이었다

### 4173 프리뷰

이 브랜치는 `frontend/src`를 **0줄** 바꾼다 (`frontend/e2e-backend/backend-mode.spec.ts`는 e2e 상수). 따라서 프론트 컨테이너는 재빌드가 필요 없고, 실행 중인 빌드 그대로 이 백엔드를 보면 된다.

### 후속 작업에 참고할 것

`backend/app/scripts/migrate_stay_discount_area_policy_links.py`가 이미 **중복 제거 후 링크 이동** 패턴을 구현하고 있다 (`_move_trip_links`, `trip_links_deleted_as_duplicates`). dgtour 중복 행 병합 계획은 이것을 본보기로 삼는다.
