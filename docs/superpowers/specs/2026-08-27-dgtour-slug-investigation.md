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

같은 정규식이 `data-signgucd`(5자리 행정구역 코드, 영광=12830)도 이미 뽑고 있다. 순번 대신 쓸 안정 식별자가 이미 손에 있는데 안 쓰는 상태다.

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
