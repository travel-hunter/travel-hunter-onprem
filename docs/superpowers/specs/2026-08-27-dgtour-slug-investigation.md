# 조사: dgtour 정책 슬러그 `-8` 접미사

**계기:** 프론트 스위트 잔여 실패 6건 중 4건이 `dgtour-영광` vs `dgtour-영광-8` 불일치.

**결론:** 테스트가 낡은 것이 아니라 **데이터와 크롤러가 어긋난 것**이다. 문제는 둘로 분리된다.

---

## 문제 1 — 슬러그가 불안정하다 (모든 환경)

`backend/scripts/crawl_dgtourcard.py:217`

```python
policy["slug"] = f"dgtour-{slugify(city)}-{entry['id']}"
```

`entry['id']`는 VisitKorea 페이지의 `func_go_detail('영광', '8')` 두 번째 인자, 즉 **그 페이지에서의 등장 순번**이다 (`_MAP_ENTRY_RE`, `:165`). 실제로 시드 파일은 밀양-1 … 고창-16으로 파일 순서 그대로다.

즉 **VisitKorea가 지도 항목 순서를 바꾸면 모든 슬러그가 바뀐다.** 슬러그는 사용자 저장/일정 연결의 키이므로 그때 링크가 전부 끊긴다.

정식 규칙은 이미 코드에 있다 — `canonical_policy_slug_for_city()` (`digital_tourism_resident_card.py:379`)는 `dgtour-{도시}`를 반환한다. 크롤러만 이걸 안 쓴다.

같은 정규식이 `data-signgucd`(5자리 코드)도 이미 뽑고 있다. 순번 대신 쓸 안정 식별자가 손에 있는데 안 쓰는 상태다.

> **정정 (2026-08-27):** 이 문단은 처음에 영광의 코드를 `12830`이라고 적었다. 그 값은 `officialUrl`의 `signguCd=12830` 쿼리 파라미터, 즉 VisitKorea 자체 코드이지 페이지 마크업의 `data-signgucd`가 아니다. 크롤러의 `SIGNGU_PREFIX_PROVINCE`(`:144`)는 앞 두 자리로 광역시도를 정하는데 `12`는 매핑에 없다. **실제 페이지의 `data-signgucd`가 어떤 체계인지는 원본 HTML이 없어 확인되지 않았다.** 아래 "추가 확인"에서 보듯 시드 JSON도 크롤러 산출물이 아니므로 JSON의 `region` 값은 이에 대한 증거가 되지 못한다.

### 참고: 백엔드는 이미 양쪽을 받아준다

`digital_tourism_policy_aliases.resolve_digital_tourism_alias_slug()`가 `city_from_policy_slug()`로 숫자 접미사를 떼고 도시 기준으로 정책을 찾는다. 조회/저장/일정연결 5곳에 연결돼 있다 (`services/policies.py:255,263,302,411`, `services/trips.py:731`).

**그래서 `-8`이어도 앱은 동작한다.** 하지만 `/api/policies`가 내보내는 `slug` 필드는 날것 그대로라 프론트는 `dgtour-영광-8`을 받아 그대로 쓴다. 테스트 4건이 여기서 깨진다.

## 문제 2 — 같은 도시가 두 행으로 갈라져 있다 (이 로컬 DB)

```
id 8    dgtour-영광     status=hidden   생성 08-18   external_source_record_id=37
id 156  dgtour-영광-8   status=active   생성 08-21   external_source 연결 없음
```

`source_canonical_key`가 `digital-tourism-resident-card:전남:영광`으로 **동일**하다. 하동도 같다.

원인: 08-18 크롤로 정식 슬러그 행이 먼저 생겼고, 08-21 재시딩 때 시드 JSON이 순번 슬러그를 들고 와서 **다른 행으로 추가**됐다. `_cleanup_legacy_dgtour_policies` (`db/seed.py:140`)는 시드 목록에 없는 행을 지우려 하지만, 링크가 있으면 지우지 않고 `hidden`으로 돌린다. 그래서 옛 행이 남았다.

### 사용자 영향 — 실제로 화면에서 사라진다

`list_saved_policies` / `list_applied_policies` / `list_applied_policy_links` 세 조회가 모두 `status == active`로 거른다 (`repositories/policies.py:62,84,101`).

현재 로컬 DB:

| 슬러그 | status | 일정 연결 | 찜 | 화면 |
|---|---|---|---|---|
| `dgtour-영광` | hidden | 1 (trip 1) | 1 (user 1) | **안 보임** |
| `dgtour-영광-8` | active | 0 | 1 (user 1) | 보임 |
| `dgtour-하동` | hidden | 1 (trip 1) | 0 | **안 보임** |
| `dgtour-하동-3` | active | 2 (trip 1, 243) | 0 | 보임 |

사용자가 08-21 이전에 담아둔 영광/하동 정책은 마이페이지에서 이미 사라진 상태다.

---

## 기존 커밋 `bc3afc8`의 위치

`feature/local-remediation-integration`의 `bc3afc8` "Align dgtour seed data with canonical slugs"는 시드 JSON에서 **active 5건**(하동·영광·합천·해남·완도)의 순번을 떼어 정식 슬러그로 바꾼다. 검증 테스트 2개와 e2e 상수도 함께 고친다.

이전 세션에서 "N개 중 5개만 처리 — 의도 불명"이라 판단했는데 **틀렸다.** 정확히 노출 대상인 active 5건만 고친 것이고, 나머지는 hidden이라 사용자에게 안 보인다. 의도는 명확하다.

**다만 이것만으로는 부족하다:**

1. **크롤러를 안 고친다.** `crawl_dgtourcard.py:217`이 그대로라 다음 크롤 실행이 순번 슬러그를 다시 만들어 낸다. 시드 JSON만 손으로 되돌린 셈이다.
2. **갈라진 링크를 합치지 않는다.** 이 커밋 적용 후 재시딩하면 극성만 뒤집힌다 — `dgtour-영광`이 active로 돌아오고, 찜이 붙은 `dgtour-영광-8`이 hidden이 된다. 08-27에 저장한 찜이 이번엔 사라진다.
3. **커밋이 추가한 테스트는 통과하지만 이 상황을 덮지 못한다.** `test_seed_policies_replaces_unlinked_numbered_dgtour_seed_with_canonical_slug`는 `sqlite_db_session` 픽스처, 즉 **빈 DB**에서 돈다. 거기서는 정식 슬러그만 생기므로 `dgtour-영광-8 not in slugs`가 자명하게 참이다. 문제는 링크가 붙은 중복 행 시나리오를 **모델링하지 않는다**는 것이다 — 그 경우 재시딩은 순번 행을 삭제하지 않고 hidden으로 돌린다. 이름의 `unlinked`가 적용 범위를 드러낸다.
4. **hidden인 참여도시 7곳**(밀양·평창·거창·영월·제천·고흥·고창)은 순번 슬러그를 유지한다. 나중에 active로 올리면 같은 문제가 재발한다.

### 병합 시 주의 — 단순 UPDATE는 실패한다

링크가 겹친다.

```
user_saved_policies:  user 1 이 dgtour-영광 과 dgtour-영광-8 을 둘 다 찜
trip_policies:        trip 1 이 dgtour-하동 과 dgtour-하동-3 에 둘 다 연결
```

`UPDATE ... SET policy_id = <정식행>` 을 그대로 돌리면 `(user_id, policy_id)` / `(trip_id, policy_id)` 유일 제약에 걸린다. **중복 제거를 먼저 하고 옮겨야 한다.**

---

## 권고 순서

1. **크롤러 수정** — `crawl_dgtourcard.py:217`이 `canonical_policy_slug_for_city()`를 쓰도록. 정식 슬러그가 없는 비참여 도시만 접미사 폴백. 근본 원인이고 이걸 안 고치면 나머지가 다음 크롤에 되돌아간다.
2. **`bc3afc8` 적용** — 시드 JSON 정렬. 1번과 같은 PR이어야 한다.
3. **데이터 병합** — 중복 제거 후 링크를 정식 행으로 옮기고 순번 행 삭제. 기존 사용자 데이터가 걸려 있으므로 별도 작업으로 분리하고 되돌릴 수 있게 한다.
4. **검증기 보강** — `validate_policy_data.py`는 현재 빈 슬러그와 중복만 본다. active + 참여도시면 정식 슬러그여야 한다는 규칙을 추가한다.

프론트 테스트 4건은 1+2로 해소된다. 3번은 사용자 데이터 복구용이다.

## 남은 2건 (미조사)

`mypage.test.tsx :: saves a policy from the policy detail header action`
`mypage.test.tsx :: shows saved policies on my page and removes them`

`expected undefined to be truthy` — 위 슬러그 문제와 원인이 다르다. 별도 조사 필요.


---

## 추가 확인 (2026-08-27, Codex 검토 중)

**시드 JSON은 크롤러 산출물이 아니다.**

- 크롤러의 `_make_policy_dict()`(`crawl_dgtourcard.py:252`)는 13개 필드만 낸다. 시드 JSON에는 크롤러가 만들 수 없는 필드가 7개 있다 — `sourceCanonicalKey`, `sourceCategory`, `sourceName`, `sourceStatus`, `sourceUrl`, `status`, `structuredDetail`
- 크롤러는 `officialUrl`에 `tour50.do`(목록)를 넣는데 시드 JSON은 `regnMain.do`(지역 상세)를 갖는다
- 크롤러 지도 경로의 제목은 `영광 디지털관광주민증 혜택`, 시드 JSON은 `[영광] 디지털관광주민증 혜택`
- git 이력상 이 JSON은 크롤 실행이 아니라 손으로 쓴 커밋으로 갱신돼 왔다 (`f12efc2`, `8e773e8`)

`-숫자` 접미사가 1..16으로 파일 순서와 일치하는 것은 여전히 크롤러 기원임을 가리킨다. 한 번 크롤로 나온 뒤 손으로 살이 붙은 것으로 보인다.

**두 가지 결과가 따라온다.**

1. "시드만 고치면 다음 크롤이 되돌린다"는 근거는 약하다. 지금 크롤을 돌리면 슬러그만이 아니라 위 7개 필드가 통째로 날아가므로, 아무도 그대로 돌리지 않는 것으로 보인다. 크롤러를 고치는 이유는 **슬러그를 만드는 유일한 코드 경로이기 때문**이고, 재발을 실제로 막는 것은 시드 검증기다.
2. 크롤러와 enrich 파이프라인이 어떻게 맞물려야 하는지는 미결이다. 별도 논의가 필요하다.

---

## 미결 항목 조사 (2026-08-27) — 구현 중단 사유

"크롤러와 enrich 파이프라인의 관계"를 파고든 결과, **순번 슬러그는 사고가 아니라 배포된 마이그레이션이 의도적으로 채택한 안정 식별자**임이 드러났다. 이 계획은 그 결정을 뒤집는 것이므로 구현 전에 판단이 필요하다.

### 정책 생산자는 둘이다

| 경로 | 진입점 | 슬러그 규칙 |
|---|---|---|
| 시드 | `app/db/seed.py:seed_policies` ← `dgtourcard_policies.json` | 순번 (`dgtour-영광-8`) |
| 정규화 | `scripts/normalize_external_policies.py` → `promote_external_benefits_to_policies` | 정식 (`dgtour-영광`) |

`external_source_records` → 정책 승격 파이프라인이 따로 있다. 로컬 DB의 두 행이 정확히 이 둘이다 — id 8은 `external_source_record_id=37`(정규화 산출), id 156은 그것이 `NULL`(시드 산출). **크롤러가 두 번 돈 게 아니라, 생산자 둘이 서로 다른 규칙으로 같은 도시를 만든 것이다.**

### 마이그레이션 0031이 순번 슬러그를 안정 식별자로 고정했다

`backend/alembic/versions/0031_digital_tourism_resident_card_identity.py` (2026-07-24) docstring:

> This is an idempotent data migration. It corrects existing dgtour seed rows and conservative VisitKorea digital-tourism external records in place **so saved policies and trip attachments keep their stable policy ids/slugs.**

그리고 16개 순번 슬러그를 `known_dgtour(slug, ...)` VALUES로 하드코딩해 `k.slug = p.slug`로 조인한다. 즉 **사용자 첨부를 지키려고 일부러 순번 슬러그를 정체성으로 삼았다.**

`app/services/legacy_dgtour_reconciliation.py`의 `frozen_legacy_dgtour_slugs()`가 같은 16개를 담고 있고, `policy_normalization.py`의 3곳(`:250`, `:456`, `:542`)이 이를 참조해 그 행들을 보호한다. `_hide_legacy_dgtour_seed_policies`는 이름과 달리 동결 슬러그를 `continue`로 **건너뛴다**.

### 그런데 같은 파일이 정식 슬러그로 이름을 바꾼다

`policy_normalization.py:271`

```python
if record.source_category == DIGITAL_TOURISM_SOURCE_CATEGORY:
    policy.slug = _policy_slug_for_external_record(record)   # -> 정식 슬러그
```

`:250`의 동결 가드는 `record.source_category != DIGITAL_TOURISM`일 때만 조기 반환하므로, dgtour 레코드에는 걸리지 않고 `:271`에 도달한다.

`test_policy_normalization.py`가 이 결과를 단언한다 — `:1810`, `:1869`, `:2153`, `:2234`에서 `dgtour-영광`, `dgtour-하동`, `dgtour-가평`.

### 결론: 코드베이스가 마이그레이션 중이고 두 축이 서로 어긋나 있다

| | 순번 슬러그 편 | 정식 슬러그 편 |
|---|---|---|
| 근거 | 마이그레이션 0031 docstring + 16건 하드코딩, `frozen_legacy_dgtour_slugs()`, 파이프라인 가드 3곳, 시드 JSON, 테스트 26곳 | `canonical_policy_slug_for_city()`, `_policy_slug_for_external_record()`, `policy_normalization.py:271`, 별칭 해석기, 정규화 테스트 4건, 커밋 `bc3afc8` |

**어느 쪽이 목표인지 코드만으로는 결론이 안 난다.** 별칭 해석기가 양쪽을 다 받아주기 때문에 앱은 어느 쪽이든 동작하고, 그래서 이 어긋남이 오래 눈에 안 띈 것으로 보인다.

### 계획대로 진행할 때 예상되는 회귀 (검증 필요)

`bc3afc8` + Task 3으로 시드를 정식 슬러그로 바꾸면:

1. `frozen_legacy_dgtour_slugs()`의 16개가 **아무 행과도 안 맞게 된다.** 가드 3곳이 조용히 무력화된다
2. 마이그레이션 0031의 `k.slug = p.slug` 조인이 어긋난다. 새 DB에서 재생하면 dgtour 행을 못 찾는다
3. `_hide_legacy_dgtour_seed_policies`가 정식 슬러그 시드 행을 **hidden 처리할 수 있다** — 그 행은 `external_source_record_id`가 `NULL`이라 보호 조건(`source_category == dgtour AND external_source_record_id IS NOT NULL AND 참여도시`)을 통과하지 못한다. 현재 로컬 DB의 id 8은 external record가 붙어 있어 보호되지만, **빈 DB에 시드만 넣은 상태에서는 보호되지 않는다.** `promoted_categories`에 `local_half_trip`이 있을 때만 도는 조건부 경로이므로 실제 발동 여부는 확인이 필요하다
4. Task 4가 넣으려던 "`-숫자` 금지" 규칙은 0031이 하드코딩한 픽스처와 정면으로 충돌한다

### 필요한 결정

**정식 슬러그를 저장 정체성으로 삼을 것인가, 아니면 순번 슬러그를 유지하고 정식 슬러그는 별칭으로만 둘 것인가.**

- **정식으로 통일한다면** — 0031을 잇는 새 마이그레이션으로 기존 행을 개명하고 링크를 옮기며, `frozen_legacy_dgtour_slugs()`를 제거하고 가드 3곳을 재검토하고, 테스트 26곳을 갱신해야 한다. 이번 계획보다 훨씬 큰 작업이다
- **순번을 유지한다면** — `bc3afc8`은 적용하면 안 된다. 대신 `/api/policies` 응답에서 슬러그를 정식형으로 **노출만** 하거나, 프론트 테스트 4건의 기대값을 실제 값으로 고친다. 훨씬 작다

이 판단 전에는 Task 1(크롤러)만 단독으로도 안전하지 않다. 크롤러를 정식 슬러그로 바꾸면 그것이 만든 JSON이 곧 시드가 되어 같은 충돌을 일으키기 때문이다.

---

## 정정 (2026-08-27, Codex 재검토) — 방향은 이미 결정돼 있었다

바로 위 "결정이 필요합니다" 절의 결론은 **틀렸다.** 커밋 이력을 놓쳤다.

### `b26aa9b` (2026-07-26) — 0031 이틀 뒤

```
Keep digital tourism details canonical and evidence-rich

Use stable dgtour city slugs for digital tourism resident-card policies while
preserving legacy URL aliases for old dgtour-numbered and travelmonth-derived links.

Constraint: ... public policy links must not expose stale numbered digital tourism slugs.
Rejected: removing legacy URLs outright | existing saved links and shared detail URLs
          still need compatibility.
Directive: after deploy, run the external collection job so existing dev DB rows are
           promoted to canonical dgtour city slugs.
```

**계약은 명확하다.**

```
저장/API 정본:  dgtour-하동
호환 별칭:      dgtour-하동-3   (조회는 되지만 노출하지 않는다)
```

`test_policy_normalization.py:2168`의 테스트 이름이 그대로 계약을 말한다 — `test_promoting_legacy_numbered_dgtour_slug_renames_to_city_slug_and_keeps_alias`.

### 앞선 오독 정정

| 내가 쓴 것 | 실제 |
|---|---|
| "0031이 순번 슬러그를 영구 정본으로 선언" | 0031은 **당시 행을 제자리 교정**하는 idempotent 마이그레이션이다. 하드코딩된 16개는 그 행을 **찾기 위한 매핑**이지 정본 선언이 아니다. SQL은 slug를 순번형으로 바꾸거나 고정하지 않는다 |
| "새 DB 재생 시 0031이 행을 못 찾는다" | 새 DB는 보통 Alembic 후 seed가 돌아 0031 시점에 정책 행이 아예 없다. 정식 행이 있어도 `WHERE p.slug LIKE 'dgtour-%'`에는 걸린다 — `known_dgtour` 값만 NULL이 될 뿐이다 |
| "두 축이 어긋나 방향 미정" | 어긋난 것은 **시드 JSON 하나**다. 파이프라인·테스트·별칭 해석기는 전부 정식 슬러그 편이다 |
| "`frozen_legacy_dgtour_slugs()`가 순번이 정본이라는 증거" | 이름 그대로 **과도기 보호 장치**다. 링크가 붙은 옛 행을 다른 정규화·삭제 처리로부터 지킨다. dgtour 레코드 자체를 정규화할 때는 가드를 통과해 정식 슬러그로 바꾸도록 **의도돼 있다** |

**따라서 지금 `/api/policies`가 `dgtour-영광-8`을 내보내는 것은 `b26aa9b`가 명시한 제약을 정면으로 위반하는 상태다.** 프론트 테스트 4건이 `dgtour-영광`을 기대한 것은 처음부터 옳았고, 그 실패는 진짜 버그 신고였다.

### 그래도 유효한 경고 (조사에서 확인한 것)

방향은 정해졌지만 **원래 계획을 그대로 실행하면 안 된다**는 결론은 유지된다.

- 정식 행과 순번 행이 이미 **동시에 존재**한다 (영광·하동)
- 찜·일정 연결이 **양쪽에 나뉘어** 있다
- `UPDATE ... SET policy_id` 단순 실행은 유일 제약과 충돌한다
- 정식 시드 행에 외부 레코드가 없으면 `_hide_legacy_dgtour_seed_policies()`가 숨길 가능성이 있다 — 회귀 테스트 필요
- `bc3afc8`만 적용해서는 링크 보존이 해결되지 않는다
- 기존 데이터가 있는 DB는 백업과 링크 병합 없이 seed하면 안 된다

### 남은 일은 방향 재결정이 아니라 완성

`b26aa9b`의 directive는 "외부 수집 작업을 돌려 기존 행을 정식 슬러그로 승격하라"였다. 그 승격 경로는 이미 구현돼 있다 (`external_benefit_collection` → `promote_external_benefits_to_policies`). 미완인 것은 **시드·크롤러·검증기가 아직 순번 규칙에 남아 있다는 점**과 **이미 갈라진 중복 행 병합**이다.
