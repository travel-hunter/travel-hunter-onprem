# 장소 검색 한 칸 정리(지역 먼저 15곳 · 더 보기 · 덜 친 말 대신 찾기) Implementation Plan (2판)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 일정 '장소 추가'와 홈 검색에서 검색창 밑 서브창 없이 아래 결과 칸 하나에 장소를 보이고, 일정이면 그 지역 주변 장소를 위에 · 나머지를 '다른 지역' 아래로 15곳씩(더 보기로 45곳까지) 보이며, 덜 친 말('스타벅')도 우리 공공데이터 완성어로 대신 찾아 장소를 보인다. 홈 장소 카드 지도는 크게 한다.

**Architecture:** 서버가 순서를 정한다. 일정 검색은 카카오 반경 20km 쪽들 → 전국 쪽들을 이은 목록의 page 번째 15곳을 주고 줄마다 `nearby`(20km 안인지)를 단다. 친 말로 0곳이면 `place_suggest.suggest_place_names` 상위 3개 말로 카카오를 대신 불러 모으고 줄마다 `viaWord` 를 단다. 홈 `/places/search` 도 0곳이면 같은 방식(지역 없음). 화면은 받은 순서대로 그리고 '다른 지역' 구분 줄 · '‘말’ 검색 결과' 안내 · '더 보기'만 더한다. 완성 검색어 서브창 · `place-suggest` API 는 걷는다.

**Tech Stack:** FastAPI · SQLAlchemy 2 · PostgreSQL(pg_trgm GIN, Alembic 0051 그대로) · React 18 · Vite · Vitest · Playwright

**Spec:** 이 문서 0절(사용자 결정 2026-10-12 · 실측). 앞 계획 `docs/superpowers/plans/2026-10-12-place-search-suggestions.md` 의 0.3 순위 규칙 · 0051 색인은 그대로 쓴다.

## 0. 설계

### 0.1 사용자 결정(2026-10-12, 그대로)

| 항목 | 결정 |
|---|---|
| 의도 | "위쪽 검색란에는 현재 일정에서 검색한 상태라면 주변지역을 위주로 띄우고 나머지를 밑으로 후순위로 내려서 검색창을 정립" - 하나 · 한정된 장소만 보이려는 게 아님 |
| 서브창 | 검색창 바로 밑 서브창 없이 아래 장소 검색 란 하나에서 |
| 결과 수 | 지역 먼저 15곳 + 더 보기(카카오 상한 45곳) |
| 덜 친 말 | 완성어 여러 개(상위 3개)로 모아 보이기 - 체인은 '스타벅스 전남' 한 줄이 아니라 가게들이 그대로 |
| 홈 검색 | 지역 치우침 없이 전국(지금 순서) + 덜 친 말 대신 찾기 같이 |
| 홈 지도 | 홈에서 고른 장소의 카드 지도를 더 크게 |
| 도 전체 일정 | 20km 원 한계는 지금대로(앞 결정 유지) |
| 진행 | 이 계획을 자체 검토 뒤 승인받고 구현, 커밋은 시험 통과 뒤, 푸시 · PR 은 브라우저 확인 뒤 |

### 0.2 실측(2026-10-12, 로컬 4173 · 카카오 실호출 · 개수만)

- 카카오는 덜 친 말을 예전 방식(좌표 없음)에서도 못 찾는다: `스타벅` · `메타세쿼` · `순천만습` 모두 좌표 없음 / 중심만 / 20km 0곳, `스타벅스` 는 15곳. 지금 바뀐 탓이 아니다.
- 카카오 쪽(page): `스타벅스@서울` · `카페@담양` 은 반경 20km · 전국 모두 1~3쪽이 15곳씩 새 장소, 4쪽은 새 장소 0(같은 줄 되풀이) → 한 검색어 45곳 상한.
- `스타벅스@전남 전체`: 20km 0곳(도 중앙값 둘레에 매장 없음), 전국 쪽 15곳씩 - 앞 실측에서 전국 쪽 6줄은 모두 전남이었다.
- 덜 친 말 → 완성어 상위 3개 → 카카오(20km / 전국): `스타벅@전남` 완성어 1개(0/15), `스타@서울` 3개(15/15 · 15/15 · 4/4), `메타세쿼@담양` 3개(0/1 · 5/5 · 0/1), `순천만습@전남` 3개(0/15 · 0/1 · 0/0), `초당순@강릉` 3개(2/5 · 15/15 · 2/5).
- 지역 없음 완성어에 상가정보까지 넣으면(전국): 2자 `스타` 1.2초 · `카페` 2.0~3.7초 · `롯데` 0.5~1.8초 · `순두` 0.03~0.2초, 3자 `스타벅` 8ms(후보 2,151) · `메타세쿼` 11~19ms → **지역 없음은 3자 이상만 상가정보를 본다.**

### 0.3 일정 장소 검색 `GET /api/trips/{trip_id}/place-search?query=&page=`

- `page`: 1~3(기본 1, 밖이면 422). 한 쪽 15곳.
- 목록: 일정 지역 중심이 있으면 [반경 20km 1쪽 → 2쪽 → 3쪽(15곳 미만이면 거기서 끝)] 뒤에 [반경 없는 전국 1쪽 → 2쪽 → 3쪽]을 잇고 카카오 장소 id 로 겹침을 뺀다. 그 목록의 `(page-1)*15 ~ page*15`. 서버는 상태를 두지 않아 page 쪽은 앞 쪽들을 다시 부른다.
  - 카카오 호출 수: 1쪽 1~2번, 2쪽 최대 5번, 3쪽 최대 6번(전국 쪽이 반경 쪽과 많이 겹치면 최대).
  - 반경 쪽 예외는 밖으로(서비스가 `[]` + 경고 `trip_place_search_failed`), 전국 쪽 예외는 모은 줄만 남기고 경고 `trip_place_search_wider_failed`(지금과 같음). 2 · 3쪽에서 반경 쪽이 실패해도 빈 배열 - 화면은 '여기까지예요'로 끝낸다(0.6).
  - 중심이 없으면(지역 없음 · 그 지역 공공데이터 없음) 좌표 없이 `search_keyword(query, size=15)` 한 번(2쪽부터 `page` 를 싣는다).
- 줄마다 `nearby`: 중심이 있으면 카카오가 준 거리(`distance_meters`)가 20,000m 이하면 `true`, 아니면 `false`. 중심이 없으면 `null`.
- 덜 친 말: **1쪽에서 친 말로 0곳일 때만**, `place_suggest.suggest_place_names(db, query, scope)` 상위 3개 말마다 위 목록의 1쪽(말마다 카카오 1~2번)을 받아, 20km 안 줄을 말 순서대로 먼저 · 그다음 나머지로 모아 15곳에서 끊는다. 줄마다 `viaWord`(찾은 말). 이 경우 2쪽은 없다(화면이 '더 보기'를 안 보인다).
  - 완성어 범위는 일정 지역(지역 안 먼저, 지역 안 체인은 '상표 + 지역'). 지역이 없으면 전국 - 2자는 TourAPI 이름만, 3자 이상은 가게 이름도(0.5).
  - 카카오 호출은 친 말 1~2번 + 대신 찾기 최대 6번 = **최대 8번**(0곳일 때만).
  - 완성어 읽기는 놓았던 세션을 다시 잡는다(SQLAlchemy 2 Session 은 close 뒤 다시 쓰면 새 연결 - `close_resets_only=True`) → 읽고 바로 놓는다. 완성어 읽기가 어떤 예외로 실패해도 경고 1줄(`trip_place_search_suggest_failed`)과 빈 말 목록 - 덤 기능이 검색을 500 으로 만들지 않는다.
- 응답 모양: **배열 그대로**(`PlaceSearchCandidate[]`), 줄에 `nearby`(bool|null) · `viaWord`(string|null)만 더한다. 미리보기(0.1 승인 화면)는 `{places, next, usedWords}` 객체였지만, 배열을 지키면 `searchTripPlaces` 를 쓰는 프론트 시험 줄(35줄)과 다른 호출자를 안 바꾸고, '더 보기'는 `받은 줄 수 == page × 15 && page < 3` 로, 안내 줄은 줄의 `viaWord` 로 같은 것을 낸다(Ruling - 사용자 검토 때 알린다).
- `GET /trips/{trip_id}/place-suggest` · `suggest_places_for_trip` 은 지운다(완성어는 서버 안에서만 쓴다).

### 0.4 홈 검색 `GET /api/places/search`

- 지금처럼 카카오 키워드 15곳(좌표 없음, 정확도순) + 동 · 읍 · 면 주소 검색.
- 키워드 · 주소 결과가 모두 0곳이고, **키워드 호출이 예외 없이 끝났고**, DB 세션이 있으면: `suggest_place_names(db, query=, scope=None)` 상위 3개 → 말마다 `search_keyword(word, size=15)` → 겹침 빼고 15곳까지, 줄마다 `viaWord`. 완성어 읽기 뒤 세션을 바로 닫는다. 카카오 장애일 때는 대신 찾기를 건너뛴다(시간 초과 5초 × 3번이 더 붙지 않게).
- `PlaceSearchItem` 에 `viaWord`(string|null) 추가 - 다른 호출자(정책 탭 위치로 찾기 · 지도에서 찾기 · `usePlaceById`)도 같은 결과를 받는다(덜 친 말로도 찾게 되는 쪽이라 해가 없다).

### 0.5 지역 없음 완성어(저장소)

- `suggest_candidates(scope=None)`: 2자는 지금처럼 전국 TourAPI 만, **3자 이상은 TourAPI + 상가정보(예술·스포츠 · 유흥 이름 제외)** - 지역 안 갈래와 같은 거름. 순위(`rank_suggestions`)는 그대로라 지역 없는 체인은 상표만(`스타벅스`) 남는다.
- 계약 문서에 이미 적은 "지역이 없으면 전국 관광지류(TourAPI) 이름만"은 틀렸다(코드는 TourAPI 분류를 가리지 않는다) - 이번에 그 절과 함께 지운다.

### 0.6 화면

- 일정 시트: 서브창(`PlaceSuggestions`) · 훅(`usePlaceSuggestions`) · 감싸개 `.place-search-box` · Esc · 알림 줄 · CSS 를 걷는다(c35d5d1 이전 짜임으로).
- 결과 칸(`.place-search-area`, 높이 220px 고정 · 칸 자체가 스크롤): 받은 줄 전부(6곳 자르기 삭제).
  - 첫 `nearby === false` 줄 앞에 `다른 지역` 구분 줄(`p.place-search-group`, 줄의 listitem 안 단추 위). 그 줄이 맨 위(20km 안 0곳)면 윗선 없이(`is-top`).
  - 줄에 `viaWord` 가 있으면 목록 위에 `‘{첫 말}’ 검색 결과` / 둘 이상이면 `‘{첫 말}’ 외 {N-1}개 검색 결과`(`p.place-search-via`, 대기 중이면 목록처럼 흐림, 화면 읽기에는 숨기고 그 글을 상태 줄 'N곳' 앞에 붙인다).
  - 목록 끝 `더 보기` 단추(`button.place-search-more`): `줄 수 == page × 15 && page < 3 && viaWord 줄 없음 && 끝나지 않음`. 누르면 같은 말의 다음 쪽을 뒤에 붙인다(id 로 겹침 뺌). 부르는 동안 `불러오는 중…` + `aria-disabled`(초점 유지, 거듭 누름 무시). 붙인 뒤 초점은 새로 붙은 첫 줄로. 새 줄이 0개면 단추 자리에 `여기까지예요`(`p.place-search-end`, 초점 받음).
  - 더 보기 실패: 단추 위 `p.place-search-status.error role="alert"` `더 불러오지 못했어요. 잠시 후 다시 시도해 주세요.`(받은 줄 · 상태 줄은 그대로, 전용 상태 `placeSearchMoreError`). 다시 누르거나 말을 바꾸면 지운다.
  - 말이 바뀜 · 후보 고름 · 창 열기/닫기에서 더 보기 상태(불러오는 중 · 오류 · 끝)를 모두 비운다 - 늦게 온 쪽은 버린다.
- 홈: 장소 목록 제목 아래 같은 안내 줄(`p.home-places-via`). 안내 줄이 있으면 혜택 낱말로 장소를 접지 않는다. 카드 지도 높이 168px → 260px(768px 이상 360px).

### 0.7 범위 밖

- 지역 없는 일정의 '주변' 표시(중심 없음 → `nearby` null, 구분 줄 없음).
- 도 전체 일정 20km 원 한계 · 카카오 `rect`(사용자 결정: 지금대로).
- 화살표로 줄 고르기, 무한 스크롤(단추만). 2 · 3쪽 실패를 오류로 구별하기(빈 배열 → '여기까지예요').
- 15줄 · 구분 줄 · 더 보기의 폭별(360~1440) 모양은 e2e 가짜가 빈 배열이라 자동으로 안 본다 - 사용자 브라우저 확인 목록에 넣는다.

### 0.8 계획 검토 반영(1판 → 2판, 자체 교차 검토 2갈래)

| 지적 | 반영 |
|---|---|
| 기존 시험 11건이 깨지는데 고치라는 말이 없음(가짜 카카오 `page` 못 받음 8 · `size == 6` · 홈 세션 시험 · 홈 응답 전체 비교 · 기능 명세 place-suggest 시험) | 좌표 없는 경로는 2쪽부터만 `page` 를 실어 가짜 8곳을 그대로 둔다. 나머지는 과제 2 · 4 · 5 에 줄마다 적었다 |
| 홈 시험 조각이 실제 도우미(`place(name, address, *, pid=)`)와 다름, `pytest` import 없음 | 과제 4 시험을 실제 도우미로 다시 적었다 |
| 과제 5 확인이 과제 6 에 기댐(`backendApi.ts`), `GOLDEN_PATHS` 없음 | 프론트 단정은 과제 6 으로, 길 목록은 `GOLDEN["endpoints"]` 로 |
| 홈 키워드 호출이 실패해도 대신 찾기 → 장애 때 20초 | 키워드 예외면 건너뛴다 + 시험 |
| 카카오 호출 수가 최선의 경우 | 2쪽 최대 5번 · 3쪽 최대 6번 |
| 완성어 읽기 예외가 검색을 500 으로 | `except Exception` → 경고 + 빈 말, 세션 순서 시험 |
| 문서의 '6곳' 남은 곳 · 덜 친 말 지역 없음 범위 · golden 선택 필드 | 과제 5 에 정확한 바꿀 글을 적었다 |
| 더 보기 오류가 재시도 성공 뒤에도 남고 공용 오류라 'N곳'이 사라짐 · 오류 줄에 role 없음 | 전용 상태 + role="alert" + 시작 · 말 변경 · 고름 · 열기에서 비움 |
| 더 보기 '불러오는 중'이 새 말 아래 갇힘 | finally 는 세션 · 요청이 같을 때만, 비움 지점에서 함께 리셋 |
| 홈 360px 규칙이 뒤의 260px 에 짐 | 새 `@media` 블록을 `.home-place-map-fallback` 규칙 바로 뒤에 |
| 시험 코드가 typecheck 를 깸(`label` 없음 · 중복 import) · `renderHome` 없음 | `label: "📍"` · import 없이 · 홈은 실제 시험 패턴 |
| 걷을 목록에 `setSuggestionsOpen(true)` · `typedQuery` 빠짐 | 목록과 grep 에 더함 |
| 더 보기 초점 · 끝 표시, 안내 줄 흐림 · 화면 읽기, 맨 위 구분 줄 선 | 0.6 · 과제 6 에 반영 |
| 홈 안내 줄 자리 · 여백 · 접힘 문구 | 과제 7 에 못 박음 |

## Global Constraints

- 카카오 값(이름 · 주소 · 좌표 · 분류 · 전화 · 거리)은 저장 · 로그 · URL 금지 - 줄 표시와 이번 응답에만 쓴다. 로그에는 오류 종류와 개수만(검색어 · 완성어 · 좌표 금지).
- 비밀값 출력 금지(.env · DB 비번 · 토큰). `.env` · `.localdev` 는 열지 않는다.
- 한 쪽 15곳(`PLACE_SEARCH_PAGE_SIZE = 15`), 쪽 수 3(`PLACE_SEARCH_MAX_PAGES = 3`), 반경 20,000m(`PLACE_SEARCH_RADIUS_METERS`), 대신 찾는 말 3개(`PLACE_SUGGEST_FALLBACK_WORDS = 3`, 홈은 `FALLBACK_WORDS = 3`).
- 한글 파일은 UTF-8 · 원래 줄 끝(CRLF 파일은 CRLF) 유지, U+FFFD 0, `git diff --check` 깨끗. 파이썬으로 파일을 다시 쓰지 말 것(CRLF 섞임) - 편집 도구나 Node `fs` 로.
- API DTO 는 camelCase. 계약 문서 · golden · 프론트 타입 · 시험을 함께 고친다.
- 백엔드 시험: `C:/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider <파일>` (backend 폴더). 전체는 `--ignore=tests/test_stay_discount_semantics_snapshot.py`.
- 커밋은 과제마다 하지 않는다 - 컨트롤러가 끝에 한 번.

## Review Focus

1. 덜 친 말에서 완성어가 0개(예: `zz`) - 결과 칸은 '검색 결과가 없어요', 카카오 대신 찾기 호출 0번(과제 3 시험).
2. '더 보기'를 누른 사이 검색어를 바꿈 - 늦게 온 다음 쪽이 새 말 결과에 붙지 않고, 새 말의 단추가 '불러오는 중'에 갇히지 않는다(과제 6 시험).
3. 중심 있는 일정에서 반경 쪽이 정확히 15 × 3 = 45곳 - 4쪽을 부르지 않고 전국 쪽도 부르지 않는다(과제 2 시험).
4. 대신 찾기에서 말 하나만 카카오 실패 - 나머지 말 결과는 나오고 경고 1줄(검색어 없음)(과제 3 · 4 시험).
5. 홈에서 DB 세션이 없거나 카카오가 실패 - 대신 찾기 없이 빈 목록, 500 아님 · 지연 없음(과제 4 시험).

---

### Task 1: 지역 없음 완성어에 3자 이상이면 상가정보도

**Files:**
- Modify: `backend/app/repositories/public_places.py` (`suggest_candidates`, 약 233-273)
- Test: `backend/tests/test_public_places.py` (`test_suggest_without_an_area_is_nationwide_tourapi_only_at_tier_zero` 근처)

**Interfaces:**
- Produces: `suggest_candidates(db, query=, scope=None)` 가 3자 이상이면 상가정보 행(분류 `leisure` 아님, 이름에 `_NIGHTLIFE` 낱말 없음)도 tier 0 으로 준다. 2자는 지금 그대로.

- [ ] **Step 1: 실패하는 시험**

`test_suggest_without_an_area_is_nationwide_tourapi_only_at_tier_zero` 바로 뒤에 더한다.

```python
def test_suggest_without_an_area_adds_shops_from_three_characters(db: Session) -> None:
    # 지역 없는 검색(홈 · 지역 없는 일정)도 덜 친 체인 이름('스타벅')을 상표로 이어 준다. 2자는 전국 상가를 훑으면 1~4초라 TourAPI 만(10/12 실측)
    seed(
        db,
        sug_row("sangga", "C1", "스타벅스 강남점", category="cafe", sido="서울", city="강남"),
        sug_row("sangga", "C2", "스타벅스 해운대점", category="cafe", sido="부산", city="해운대"),
        sug_row("sangga", "L1", "스타벅스 볼링장", category="leisure", sido="서울", city="강남"),   # 예술·스포츠는 뺀다
        sug_row("sangga", "N1", "스타벅노래방", category="food", sido="서울", city="강남"),   # 유흥 이름은 뺀다
        sug_row("tourapi", "T1", "스타벅스 리저브 전망대", sido="부산", city="중구"),
    )
    assert found(suggest_candidates(db, query="스타벅", scope=None)) == {
        ("스타벅스 강남점", 0), ("스타벅스 해운대점", 0), ("스타벅스 리저브 전망대", 0),
    }
    assert found(suggest_candidates(db, query="스타", scope=None)) == {("스타벅스 리저브 전망대", 0)}   # 2자는 TourAPI 만
```

- [ ] **Step 2: 실패 확인**

Run: `... tests/test_public_places.py -k "adds_shops_from_three"`
Expected: FAIL - 첫 단정에서 상가 두 줄이 없다.

- [ ] **Step 3: 구현**

`suggest_candidates` 의 `if scope is None:` 앞에서 유흥 거름을 함께 쓰도록 옮긴다.

```python
    nightlife = and_(PublicPlace.source == "sangga", or_(*(PublicPlace.name.contains(word, autoescape=True) for word in _NIGHTLIFE)))
    # TourAPI 전부 + 상가정보 중 예술·스포츠가 아닌 것(유흥 이름 제외) - 지역 안 갈래와 지역 없음 3자 이상이 같이 쓴다
    places_and_shops = (or_(PublicPlace.source == "tourapi", PublicPlace.category != "leisure"), not_(nightlife))

    if scope is None:
        # 지역 없음: 전국. 2자는 TourAPI 만 - 전국 상가 108만 행을 2자로 훑으면 1~4초다(10/12 실측: 스타 1.2초 · 카페 2~3.7초).
        # 3자 이상은 상가도 본다('스타벅' 8ms) - 덜 친 체인 이름을 상표('스타벅스')로 이어 대신 찾기에 쓴다
        branches = [branch(0, PublicPlace.source == "tourapi") if short else branch(0, *places_and_shops)]
    else:
        sido, cities = scope
        inside = branch(0, *places_and_shops)
```

`else` 안의 옛 `nightlife = ...` · `inside = branch(0, or_(...), not_(nightlife))` 두 줄은 지운다. 독스트링의 `- 지역 없음: 전국 TourAPI(tier 0).` 을 `- 지역 없음: 전국(tier 0) - 2자는 TourAPI 만, 3자 이상은 지역 안 갈래와 같은 거름(상가정보 포함).` 로 고친다.

- [ ] **Step 4: 통과 확인**

Run: `... tests/test_public_places.py tests/test_place_suggest.py`
Expected: 모두 PASS(기존 `..._tourapi_only_at_tier_zero` 는 2자라 그대로 통과).

- [ ] **Step 5: 로컬 DB 실측(PostgreSQL)**

backend 컨테이너 안에서(앱 세션 팩토리, 출력은 개수 · 시간만, 스크립트는 `/tmp` 에 두고 끝나면 지운다 - Git Bash 는 `MSYS_NO_PATHCONV=1`, `PYTHONPATH=/app`) 지역 없음 3자 입력 10개(`스타벅` `메타세쿼` `순두부` `해수욕` `케이블` `이디야` `롯데리` `카페베` `편의점` `한옥마`)를 각 5번 `suggest_place_names(db, query=q, scope=None)` 로 재고 p95 와, `suggest_candidates` 결과가 상한 4000 에 닿은 입력 수를 보고서에 적는다.
Expected: p95 < 100ms. 넘거나 상한에 닿으면 멈추지 말고 그 입력 · 시간을 보고서에 적는다(컨트롤러 판정).

---

### Task 2: 일정 검색 15곳씩 · 쪽 · `nearby`

**Files:**
- Modify: `backend/app/services/trips.py` (`search_places_for_trip`, `_search_near`, 상수 `PLACE_SEARCH_SIZE` 자리)
- Modify: `backend/app/schemas/trip.py` (`PlaceSearchCandidate`)
- Modify: `backend/app/api/routes/trips.py` (`search_trip_places`)
- Test: `backend/tests/test_trip_db_service.py`, `backend/tests/test_trip_db_routes.py`

**Interfaces:**
- Produces: `search_places_for_trip(db, user, *, trip_handle: str, query: str, page: int = 1) -> list[dict]`, 줄 딕트에 `"nearby": bool | None`, `"viaWord": None`(과제 3 이 채운다). `_search_near(provider, query, center, page=1) -> list[KakaoLocalPlace]`. `_nearby(place, center) -> bool | None`. 상수 `PLACE_SEARCH_PAGE_SIZE = 15`, `PLACE_SEARCH_MAX_PAGES = 3`, `PLACE_SEARCH_RADIUS_METERS = 20000`.
- Route: `GET /api/trips/{trip_id}/place-search?query=&page=` (`page: int = Query(default=1, ge=1, le=3)`).

- [ ] **Step 1: 실패하는 시험 - 서비스**

`backend/tests/test_trip_db_service.py` 위에 `from dataclasses import replace` 를 더하고, `near_places` 를 거리를 받게 바꾸고 도우미를 더한다.

```python
def near_places(*ids: str, distance: int | None = 1000) -> list[KakaoLocalPlace]:
    return [replace(kakao_place(external_id, f"장소{external_id}", None, None), distance_meters=distance) for external_id in ids]


def ids(start: int, stop: int) -> list[str]:
    return [str(number) for number in range(start, stop)]
```

새 시험:

```python
def test_search_places_for_trip_asks_the_trips_area_first_and_stops_when_fifteen_rows_come(monkeypatch) -> None:
    provider = NearKakao(near_places(*ids(1, 16)))
    center_calls = install_near_search(monkeypatch, provider, center=NEAR_CENTER)
    db = object()

    rows = trip_service.search_places_for_trip(db, make_user(), trip_handle="7", query="스타벅스")

    assert provider.calls == [{"query": "스타벅스", "x": 127.7456, "y": 34.7123, "radius": 20000, "size": 15, "page": 1}]
    assert near_ids(rows) == ids(1, 16)
    assert [row["nearby"] for row in rows] == [True] * 15
    assert [(received_db, area.id) for received_db, area in center_calls] == [(db, "jeonnam-yeosu-suncheon")]


def test_search_places_for_trip_fills_up_from_the_wider_search_and_marks_far_rows(monkeypatch) -> None:
    provider = NearKakao(near_places("1", "2", "3", "4"), near_places("9", "3", "8", "1", distance=45000))
    install_near_search(monkeypatch, provider, center=NEAR_CENTER)

    rows = trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="스타벅스")

    assert provider.calls == [
        {"query": "스타벅스", "x": 127.7456, "y": 34.7123, "radius": 20000, "size": 15, "page": 1},
        {"query": "스타벅스", "x": 127.7456, "y": 34.7123, "size": 15, "page": 1},   # 반경 없음 - 전국 1쪽
    ]
    assert near_ids(rows) == ["1", "2", "3", "4", "9", "8"]   # 지역 안 줄 먼저, 겹침(3 · 1)은 한 번
    assert [row["nearby"] for row in rows] == [True, True, True, True, False, False]


def test_search_places_for_trip_second_page_continues_the_joined_list(monkeypatch) -> None:
    # 반경 쪽 1쪽 15곳 · 2쪽 4곳에서 끝 → 전국 1쪽에서 채운다. 2쪽 = 이은 목록의 16~30번째
    provider = NearKakao(near_places(*ids(1, 16)), near_places(*ids(16, 20)), near_places(*ids(30, 45), distance=90000))
    install_near_search(monkeypatch, provider, center=NEAR_CENTER)

    rows = trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="카페", page=2)

    assert [call["page"] for call in provider.calls] == [1, 2, 1]
    assert ["radius" in call for call in provider.calls] == [True, True, False]
    assert near_ids(rows) == ids(16, 20) + ids(30, 41)
    assert [row["nearby"] for row in rows] == [True] * 4 + [False] * 11


def test_search_places_for_trip_stops_at_three_kakao_pages_of_the_area(monkeypatch) -> None:
    # 반경 쪽이 15 × 3 = 45곳이면 3쪽은 반경 쪽만으로 찬다 - 4쪽 · 전국 쪽을 부르지 않는다
    provider = NearKakao(near_places(*ids(1, 16)), near_places(*ids(16, 31)), near_places(*ids(31, 46)))
    install_near_search(monkeypatch, provider, center=NEAR_CENTER)

    rows = trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="카페", page=3)

    assert [call["page"] for call in provider.calls] == [1, 2, 3]
    assert all("radius" in call for call in provider.calls)
    assert near_ids(rows) == ids(31, 46)


def test_search_places_for_trip_without_a_center_pages_one_plain_search_and_marks_nothing(monkeypatch) -> None:
    provider = NearKakao(near_places(*ids(16, 31), distance=None))
    install_near_search(monkeypatch, provider, area_id=None, center={"latitude": None, "longitude": None})

    rows = trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="카페", page=2)

    assert provider.calls == [{"query": "카페", "size": 15, "page": 2}]
    assert [row["nearby"] for row in rows] == [None] * 15
```

기존 시험 고치기(이 과제에서 함께):
- `..._stops_when_six_rows_come` · `..._fills_up_from_the_wider_search_after_the_area_rows` 는 위 두 시험으로 바꾼다.
- 나머지 `NearKakao` 지역 먼저 시험(겹침만 · 1차 실패 · 2차 실패 · 좌표 없음 등)은 기대 호출의 `"size": 6` → `"size": 15` 와 `"page": 1` 추가만(좌표 없는 호출은 `page` 없이 `"size": 15`).
- `test_search_places_for_trip_maps_kakao_candidates`(약 :116)의 `assert size == 6` → `assert size == 15`.
- 좌표 없는 경로는 1쪽에 `page` 를 싣지 않으므로 `search_keyword(self, *, query, size=10)` 꼴 가짜(약 :185 · :205 · :223 · :245 · :300 · :4028, `test_public_places.py` 약 :529)는 그대로 둔다.

- [ ] **Step 2: 실패하는 시험 - 라우트**

`backend/tests/test_trip_db_routes.py` 에 더한다.

```python
@pytest.mark.parametrize("page", ["0", "4", "x"])
def test_db_trip_place_search_route_rejects_a_page_outside_one_to_three(monkeypatch, page) -> None:
    install_db_route_dependencies(monkeypatch, object(), make_user())
    monkeypatch.setattr(trip_routes.trip_service, "search_places_for_trip", lambda *args, **kwargs: pytest.fail("must not reach the service"))
    try:
        response = client.get("/api/trips/7/place-search", params={"query": "카페", "page": page})
    finally:
        clear_overrides()
    assert response.status_code == 422


def test_db_trip_place_search_route_passes_the_page_and_returns_the_row_marks(monkeypatch) -> None:
    install_db_route_dependencies(monkeypatch, object(), make_user())
    seen: dict[str, object] = {}

    def fake(db, user, *, trip_handle, query, page):
        seen.update(page=page)
        return [{"title": "카페 하나", "meta": "카페", "nearby": False, "viaWord": None}]

    monkeypatch.setattr(trip_routes.trip_service, "search_places_for_trip", fake)
    try:
        response = client.get("/api/trips/7/place-search", params={"query": "카페", "page": "2"})
    finally:
        clear_overrides()
    assert response.status_code == 200
    assert seen == {"page": 2}
    assert response.json()[0]["nearby"] is False and response.json()[0]["viaWord"] is None
```

기존 라우트 시험의 가짜 `search_places_for_trip` 이 `page` 키워드를 받지 않으면(`lambda db, user, *, trip_handle, query: ...` 꼴) `page=1` 을 받도록 고친다.

- [ ] **Step 3: 실패 확인**

Run: `... tests/test_trip_db_service.py tests/test_trip_db_routes.py`
Expected: 새 시험 FAIL(`size` 6 · `page` 키 없음 · `nearby` KeyError · 422 아님).

- [ ] **Step 4: 구현 - 서비스**

`trips.py` 의 상수를 바꾼다.

```python
PLACE_SEARCH_PAGE_SIZE = 15   # 카카오 한 쪽 최대 - 담기 창은 쪽마다 15곳, '더 보기'로 다음 쪽
PLACE_SEARCH_MAX_PAGES = 3   # 카카오는 한 검색어에 45곳까지만 준다(4쪽부터 같은 줄이 되풀이 - 10/12 실측)
PLACE_SEARCH_RADIUS_METERS = 20000   # 일정 지역 중심에서 먼저 보는 반경(카카오 상한)
```

`_search_near` 를 바꾸고 `_nearby` 를 더한다.

```python
def _search_near(provider: KakaoLocalSearchProvider, query: str, center: dict[str, float | None], page: int = 1) -> list[KakaoLocalPlace]:
    """지역 먼저, 모자라면 전국: 반경 20km 쪽들을 먼저 다 잇고 그 뒤에 반경 없는 전국 쪽들을 잇는다(카카오 장소 id 로 겹침을 뺀다).
    그 목록의 page 번째 15곳. 서버가 상태를 두지 않아 page 쪽은 앞 쪽들을 다시 부른다 - 카카오 호출은 1쪽 1~2번, 2쪽 최대 5번, 3쪽 최대 6번.
    중심이 없으면(지역 없음 · 공공데이터 행 없음) 좌표 없이 그 쪽 한 번(2쪽부터 page 를 싣는다). 반경 쪽 예외는 밖으로 올린다(호출한 쪽이 `[]` + 경고) -
    전국 쪽 예외는 모은 줄만 남기고 경고 1줄. 경고에는 오류 종류만 싣는다(검색어 · 좌표 금지)."""

    size = PLACE_SEARCH_PAGE_SIZE
    start, want = (page - 1) * size, page * size
    latitude, longitude = center.get("latitude"), center.get("longitude")
    if latitude is None or longitude is None:
        return provider.search_keyword(query=query, size=size, **({"page": page} if page > 1 else {}))
    rows: list[KakaoLocalPlace] = []
    seen: set[str] = set()

    def take(**stream: int) -> None:
        for kakao_page in range(1, PLACE_SEARCH_MAX_PAGES + 1):
            if len(rows) >= want:
                return
            got = provider.search_keyword(query=query, x=longitude, y=latitude, size=size, page=kakao_page, **stream)
            for place in got:
                if place.external_place_id not in seen:
                    seen.add(place.external_place_id)
                    rows.append(place)
            if len(got) < size:
                return

    take(radius=PLACE_SEARCH_RADIUS_METERS)
    if len(rows) < want:
        try:
            take()
        except Exception as error:
            logger.warning("trip_place_search_wider_failed error=%s", type(error).__name__)
    return rows[start:want]


def _nearby(place: KakaoLocalPlace, center: dict[str, float | None]) -> bool | None:
    """일정 지역 중심에서 20km 안인지 - 화면의 '다른 지역' 구분 줄용(보여 주기만, 저장 · 로그 금지). 중심이 없으면 None."""

    if center.get("latitude") is None or center.get("longitude") is None:
        return None
    return place.distance_meters is not None and place.distance_meters <= PLACE_SEARCH_RADIUS_METERS
```

`search_places_for_trip` 은 `page: int = 1` 키워드를 받아 `_search_near(provider, trimmed_query, center, page)` 로 넘기고, 줄 딕트의 `"publicMatch": public_match,` 뒤에 `"nearby": _nearby(place, center), "viaWord": None,` 을 더한다.

- [ ] **Step 5: 구현 - 스키마 · 라우트**

`schemas/trip.py` `PlaceSearchCandidate` 끝에:

```python
    # 일정 지역 중심에서 20km 안이면 true, 밖이면 false, 일정에 지역 중심이 없으면 null - 화면이 '다른 지역' 구분 줄을 긋는다
    nearby: bool | None = None
    # 친 말로 카카오가 0곳이라 우리 공공데이터 완성어로 대신 찾은 줄이면 그 말(카카오 값 아님), 아니면 null
    viaWord: str | None = None
```

`routes/trips.py` `search_trip_places` 에 `page: int = Query(default=1, ge=1, le=3),` 를 `query` 뒤에 더하고 서비스에 `page=page` 로 넘긴다.

- [ ] **Step 6: 통과 확인**

Run: `... tests/test_trip_db_service.py tests/test_trip_db_routes.py tests/test_kakao_local.py tests/test_public_places.py` 를 함께, 그리고 `tests/test_trip_db_service.py` 를 따로 한 번.
Expected: 둘 다 PASS.

---

### Task 3: 일정 검색 덜 친 말 대신 찾기 · `place-suggest` 걷기

**Files:**
- Modify: `backend/app/services/trips.py` (`search_places_for_trip`, 새 `_search_by_suggestions`, `suggest_places_for_trip` 삭제)
- Modify: `backend/app/api/routes/trips.py` (`suggest_trip_places` 삭제)
- Test: `backend/tests/test_trip_db_service.py`, `backend/tests/test_trip_db_routes.py`, `backend/tests/test_public_places.py`

**Interfaces:**
- Consumes: `_search_near`, `_nearby`, `PLACE_SEARCH_PAGE_SIZE`(과제 2), `place_suggest.suggest_place_names(db, *, query, scope) -> list[str]`, `trip_public_places.area_scope(area)`.
- Produces: 1쪽에서 친 말로 0곳이면 줄마다 `viaWord` 가 채워진 최대 15곳. 상수 `PLACE_SUGGEST_FALLBACK_WORDS = 3`.

- [ ] **Step 1: 실패하는 시험**

`test_trip_db_service.py` 에 말마다 다른 답을 주는 가짜와 시험을 더한다.

```python
class WordKakao:
    """검색어마다 정해 둔 답(없으면 빈 목록)을 주는 가짜 카카오 - 예외면 던진다. calls 에 (검색어, 반경 여부)를 쌓는다."""

    def __init__(self, answers: dict[str, object]) -> None:
        self.answers = answers
        self.calls: list[tuple[str, bool]] = []

    def search_keyword(self, **kwargs):
        self.calls.append((kwargs["query"], "radius" in kwargs))
        answer = self.answers.get(kwargs["query"], [])
        if isinstance(answer, Exception):
            raise answer
        return answer


def install_suggestions(monkeypatch, words, seen: list[object] | None = None) -> None:
    """완성어 가짜. words 가 예외면 던진다."""

    def fake(db, *, query, scope):
        if seen is not None:
            seen.append((query, scope))
        if isinstance(words, Exception):
            raise words
        return words

    monkeypatch.setattr(trip_service.place_suggest, "suggest_place_names", fake)


def test_search_places_for_trip_searches_the_top_three_completed_words_when_the_typed_word_finds_nothing(monkeypatch) -> None:
    provider = WordKakao({
        "스타벅스 전남": near_places("a1", "a2", distance=45000),
        "스타벅스 리저브": near_places("b1", distance=3000) + near_places("a1", distance=45000),
        "스타벅스커피": near_places("c1", distance=8000),
    })
    install_near_search(monkeypatch, provider, center=NEAR_CENTER)
    asked: list[object] = []
    install_suggestions(monkeypatch, ["스타벅스 전남", "스타벅스 리저브", "스타벅스커피", "스타벅스 넷째"], asked)

    rows = trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="스타벅")

    assert asked == [("스타벅", ("전남", ("여수", "순천")))]   # 일정 지역 범위로 완성어를 묻는다
    assert near_ids(rows) == ["b1", "c1", "a1", "a2"]   # 20km 안 줄을 말 순서대로 먼저, 그다음 나머지 - 겹침(a1)은 처음 찾은 말로 한 번
    assert [row["viaWord"] for row in rows] == ["스타벅스 리저브", "스타벅스커피", "스타벅스 전남", "스타벅스 전남"]
    assert [row["nearby"] for row in rows] == [True, True, False, False]
    assert {query for query, _ in provider.calls} == {"스타벅", "스타벅스 전남", "스타벅스 리저브", "스타벅스커피"}   # 넷째 말은 안 부른다


def test_search_places_for_trip_does_not_search_completed_words_when_the_typed_word_finds_places(monkeypatch) -> None:
    provider = WordKakao({"남산": near_places("1")})
    install_near_search(monkeypatch, provider, center=NEAR_CENTER)
    install_suggestions(monkeypatch, ["남산서울타워"])

    rows = trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="남산")

    assert near_ids(rows) == ["1"] and rows[0]["viaWord"] is None
    assert {query for query, _ in provider.calls} == {"남산"}


def test_search_places_for_trip_has_no_completed_word_search_on_later_pages(monkeypatch) -> None:
    provider = WordKakao({})
    install_near_search(monkeypatch, provider, center=NEAR_CENTER)
    install_suggestions(monkeypatch, ["스타벅스 전남"])

    assert trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="스타벅", page=2) == []
    assert {query for query, _ in provider.calls} == {"스타벅"}


def test_search_places_for_trip_with_no_completed_words_answers_empty_without_more_kakao_calls(monkeypatch) -> None:
    provider = WordKakao({})
    install_near_search(monkeypatch, provider, center=NEAR_CENTER)
    install_suggestions(monkeypatch, [])

    assert trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="zz") == []
    assert {query for query, _ in provider.calls} == {"zz"}


def test_search_places_for_trip_answers_empty_when_reading_completed_words_fails(monkeypatch, caplog) -> None:
    provider = WordKakao({})
    install_near_search(monkeypatch, provider, center=NEAR_CENTER)
    install_suggestions(monkeypatch, AttributeError("boom"))
    monkeypatch.setattr(trip_service.logger, "handlers", [caplog.handler])
    monkeypatch.setattr(trip_service.logger, "propagate", False)
    caplog.set_level(logging.WARNING)

    assert trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="스타벅") == []
    assert [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING] == ["trip_place_search_suggest_failed error=AttributeError"]


def test_search_places_for_trip_skips_a_completed_word_whose_kakao_call_fails(monkeypatch, caplog) -> None:
    provider = WordKakao({"스타벅스 전남": RuntimeError("GET https://dapi.kakao.com/...?query=스타벅스 전남 failed"), "스타벅스커피": near_places("c1")})
    install_near_search(monkeypatch, provider, center=NEAR_CENTER)
    install_suggestions(monkeypatch, ["스타벅스 전남", "스타벅스커피"])
    monkeypatch.setattr(trip_service.logger, "handlers", [caplog.handler])
    monkeypatch.setattr(trip_service.logger, "propagate", False)
    caplog.set_level(logging.WARNING)

    rows = trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="스타벅")

    assert near_ids(rows) == ["c1"]
    assert [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING] == ["trip_place_search_suggestion_failed error=RuntimeError"]
    assert "스타벅" not in caplog.text and "dapi.kakao.com" not in caplog.text


def test_search_places_for_trip_cuts_the_completed_word_rows_at_fifteen(monkeypatch) -> None:
    provider = WordKakao({"가나다": near_places(*ids(1, 16)), "가나다라": near_places(*ids(100, 115))})
    install_near_search(monkeypatch, provider, center=NEAR_CENTER)
    install_suggestions(monkeypatch, ["가나다", "가나다라"])

    rows = trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="가나")

    assert near_ids(rows) == ids(1, 16)


def test_search_places_for_trip_releases_the_session_around_reading_completed_words(monkeypatch) -> None:
    events: list[str] = []

    class SpyDb:
        def close(self) -> None:
            events.append("close")

    class Kakao(WordKakao):
        def search_keyword(self, **kwargs):
            events.append(f"kakao {kwargs['query']}")
            return super().search_keyword(**kwargs)

    provider = Kakao({"스타벅스 전남": near_places("a1")})
    install_near_search(monkeypatch, provider, center=NEAR_CENTER)

    def fake(db, *, query, scope):
        events.append("suggest")
        return ["스타벅스 전남"]

    monkeypatch.setattr(trip_service.place_suggest, "suggest_place_names", fake)

    trip_service.search_places_for_trip(SpyDb(), make_user(), trip_handle="7", query="스타벅")

    # 카카오를 부르기 전마다 세션을 놓는다: 접근 확인 뒤 → (친 말 카카오) → 완성어 읽기 → 다시 놓음 → (완성어 카카오)
    assert events[:2] == ["close", "kakao 스타벅"]
    assert events[events.index("suggest") + 1] == "close"
    assert events.index("suggest") < events.index("kakao 스타벅스 전남")
```

`install_near_search` 는 `area_scope` 를 가짜로 하지 않는다 - 진짜 `trip_public_places.area_scope(get_travel_area("jeonnam-yeosu-suncheon"))` 가 `("전남", ("여수", "순천"))` 이다(카탈로그 값이 다르면 그 값으로 단정을 맞춘다).

지울 시험: `test_trip_db_service.py` · `test_trip_db_routes.py` · `test_public_places.py` 에서 `suggest_places_for_trip` · `/place-suggest` 를 쓰는 시험 전부(`grep -n "suggest_places_for_trip\|place-suggest" backend/tests` 로 찾는다). `test_public_places.py` 의 진짜 `Session` 잇기 시험(`suggest_places_for_trip(db, USER, trip_handle="7", query="오동")`)은 아래로 바꾼다(진짜 DB 완성어 → 가짜 카카오).

```python
def test_trip_place_search_falls_back_to_completed_words_from_the_real_public_rows(db: Session, monkeypatch) -> None:
    seed(
        db,
        place_row("tourapi", "T1", "오동공원", sido="서울", category="sight"),
        place_row("tourapi", "T2", "오동도 등대", sido="전남", category="sight"),
    )
    db.add(Trip(id=7, owner_id=USER.id, title="여수 여행", start_date=date(2026, 10, 1), end_date=date(2026, 10, 2), travel_area_id="jeonnam-yeosu-suncheon"))
    db.commit()
    asked: list[str] = []

    class Kakao:
        def search_keyword(self, **kwargs):
            asked.append(kwargs["query"])
            if kwargs["query"] == "오동":
                return []
            return [KakaoLocalPlace(external_place_id="k1", name="오동도", category_name=None, category_group_code=None, category_group_name=None,
                                    phone=None, address=None, latitude=34.74, longitude=127.76, place_url=None, distance_meters=500)]

    monkeypatch.setattr(trip_service, "build_kakao_local_client", lambda: Kakao())
    monkeypatch.setattr(trip_service.public_place_service, "match_places", lambda db, rows: [None for _ in rows])

    rows = trip_service.search_places_for_trip(db, USER, trip_handle="7", query="오동")

    assert asked[0] == "오동" and "오동도 등대" in asked   # 친 말 → 완성어(지역 안 '오동도 등대' 가 먼저)
    assert rows[0]["viaWord"] == "오동도 등대"
```

- [ ] **Step 2: 실패 확인**

Run: `... tests/test_trip_db_service.py -k "completed_word or completed_words"`
Expected: FAIL(대신 찾기 없음 - 빈 목록).

- [ ] **Step 3: 구현**

`trips.py`:

```python
PLACE_SUGGEST_FALLBACK_WORDS = 3   # 친 말로 0곳일 때 대신 찾는 완성어 수 - 말마다 카카오 1~2번(최대 6번 더)


def _search_by_suggestions(
    db: Session,
    provider: KakaoLocalSearchProvider,
    query: str,
    center: dict[str, float | None],
    scope: tuple[str, tuple[str, ...] | None] | None,
) -> tuple[list[KakaoLocalPlace], dict[str, str]]:
    """덜 친 말('스타벅')은 카카오 키워드 검색이 못 찾는다(낱말 단위 - 10/12 실측 0곳). 우리 공공데이터 완성어 상위 3개로 대신 찾는다.
    20km 안 줄을 말 순서대로 먼저, 그다음 나머지(카카오 장소 id 로 겹침을 뺀다), 15곳에서 끊는다. 돌려주는 사전은 장소 id → 찾은 말.
    완성어는 놓았던 세션을 다시 잡아 읽고 바로 놓는다 - 읽기가 어떤 예외로 실패해도 경고 1줄과 빈 결과(덤 기능이 검색을 500 으로 만들지 않게).
    말 하나의 카카오 실패는 경고 1줄만 남기고 다음 말로 간다. 경고에는 오류 종류만(검색어 · 완성어 · 좌표 금지)."""

    try:
        words = place_suggest.suggest_place_names(db, query=query, scope=scope)[:PLACE_SUGGEST_FALLBACK_WORDS]
    except Exception as error:
        logger.warning("trip_place_search_suggest_failed error=%s", type(error).__name__)
        words = []
    finally:
        _release_session(db)
    near: list[KakaoLocalPlace] = []
    other: list[KakaoLocalPlace] = []
    via: dict[str, str] = {}
    for word in words:
        try:
            found = _search_near(provider, word, center)
        except Exception as error:
            logger.warning("trip_place_search_suggestion_failed error=%s", type(error).__name__)
            continue
        for place in found:
            if place.external_place_id in via:
                continue
            via[place.external_place_id] = word
            (near if _nearby(place, center) else other).append(place)
    places = (near + other)[:PLACE_SEARCH_PAGE_SIZE]
    return places, {place.external_place_id: via[place.external_place_id] for place in places}
```

`search_places_for_trip` 의 중심 읽기를 지역과 함께 읽도록 바꾸고 0곳일 때 대신 찾는다.

```python
    # 일정 지역 중심(공공데이터 좌표)으로 지역 안 결과를 먼저 받는다 - DB 는 여기까지만 읽는다(완성어 대신 찾기는 0곳일 때 다시 잡는다)
    area = _trip_area(db, int(trip_handle))
    center = trip_public_places.area_center(db, area)
    _release_session(db)   # 접근 확인 · 지역 중심이 끝났다 - 카카오를 기다리는 동안 DB 연결을 쥐지 않는다
    try:
        places = _search_near(provider, trimmed_query, center, page)
    except Exception as error:
        logger.warning("trip_place_search_failed trip=%s error=%s", trip_handle, type(error).__name__)
        return []
    via: dict[str, str] = {}
    if not places and page == 1:
        places, via = _search_by_suggestions(db, provider, trimmed_query, center, trip_public_places.area_scope(area))
    matches = _prematch(db, places)
```

줄 딕트의 `"viaWord": None` 을 `"viaWord": via.get(place.external_place_id)` 로 바꾼다. `suggest_places_for_trip` 함수와 `routes/trips.py` 의 `suggest_trip_places` 라우트를 지운다(`place_suggest` import 는 `_search_by_suggestions` 가 쓴다).

- [ ] **Step 4: 통과 확인**

Run: `... tests/test_trip_db_service.py tests/test_trip_db_routes.py tests/test_public_places.py tests/test_place_suggest.py`
Expected: PASS. `grep -rn "suggest_places_for_trip\|place-suggest\|suggest_trip_places" backend/app backend/tests` 가 0줄(계약 문서 시험은 과제 5).

---

### Task 4: 홈 검색 덜 친 말 대신 찾기

**Files:**
- Modify: `backend/app/services/place_search.py` (`search_places`, 새 `_search_by_suggestions`)
- Modify: `backend/app/api/routes/places.py` (`search_places` 라우트가 `db` 를 넘김)
- Modify: `backend/app/schemas/places.py` (`PlaceSearchItem.viaWord`)
- Test: `backend/tests/test_place_search.py`

**Interfaces:**
- Consumes: `place_suggest.suggest_place_names(db, *, query, scope)` - 홈은 `scope=None` 을 명시해 부른다(과제 1 이 3자 이상 상가를 더함).
- Produces: `search_places(query, provider=None, db=None) -> list[dict]`, 대신 찾은 줄에 `"viaWord": str`. 상수 `FALLBACK_WORDS = 3`.

- [ ] **Step 1: 실패하는 시험**

`backend/tests/test_place_search.py` 위 import 에 `import logging` · `import pytest` 가 없으면 더하고, 파일의 `place(name, address, *, pid=...)` 도우미로 시험을 더한다.

```python
class WordKakao:
    def __init__(self, answers: dict[str, object]) -> None:
        self.answers, self.calls = answers, []

    def search_keyword(self, **kwargs):
        self.calls.append(kwargs["query"])
        answer = self.answers.get(kwargs["query"], [])
        if isinstance(answer, Exception):
            raise answer
        return answer

    def search_address(self, **kwargs):
        return []


class ClosingDb:
    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


def test_home_search_falls_back_to_completed_words_when_kakao_finds_nothing(monkeypatch) -> None:
    provider = WordKakao({
        "스타벅스": [place("스타벅스 강남점", "서울 강남구 역삼동 1", pid="k1"), place("스타벅스 역삼점", "서울 강남구 역삼동 2", pid="k2")],
        "스타벅스 리저브": [place("스타벅스 역삼점", "서울 강남구 역삼동 2", pid="k2"), place("스타벅스 리저브 청담", "서울 강남구 청담동 3", pid="k3")],
    })
    db = ClosingDb()

    def words(db, *, query, scope):
        assert scope is None   # 홈은 지역이 없다
        return ["스타벅스", "스타벅스 리저브", "셋째", "넷째"]

    monkeypatch.setattr(place_search, "suggest_place_names", words)

    items = place_search.search_places("스타벅", provider=provider, db=db)

    assert [item["id"] for item in items] == ["kakao:k1", "kakao:k2", "kakao:k3"]
    assert [item["viaWord"] for item in items] == ["스타벅스", "스타벅스", "스타벅스 리저브"]
    assert provider.calls == ["스타벅", "스타벅스", "스타벅스 리저브", "셋째"]   # 넷째 말은 안 부른다
    assert db.closed == 1   # 완성어를 읽고 바로 놓는다


def test_home_search_keeps_kakao_rows_without_a_via_word_when_the_typed_word_finds_places(monkeypatch) -> None:
    provider = WordKakao({"남산": [place("남산타워", "서울 용산구 용산동2가 1", pid="k1")]})
    monkeypatch.setattr(place_search, "suggest_place_names", lambda *args, **kwargs: pytest.fail("must not ask completed words"))

    items = place_search.search_places("남산", provider=provider, db=ClosingDb())

    assert [item["id"] for item in items] == ["kakao:k1"] and "viaWord" not in items[0]


def test_home_search_without_a_db_session_answers_empty_instead_of_falling_back(monkeypatch) -> None:
    monkeypatch.setattr(place_search, "suggest_place_names", lambda *args, **kwargs: pytest.fail("no db, no completed words"))
    assert place_search.search_places("스타벅", provider=WordKakao({}), db=None) == []


def test_home_search_does_not_fall_back_when_the_kakao_keyword_call_failed(monkeypatch) -> None:
    # 카카오 장애일 때 대신 찾기까지 부르면 시간 초과(5초)가 세 번 더 붙는다
    provider = WordKakao({"스타벅": RuntimeError("timeout")})
    monkeypatch.setattr(place_search, "suggest_place_names", lambda *args, **kwargs: pytest.fail("kakao is down - no fallback"))

    assert place_search.search_places("스타벅", provider=provider, db=ClosingDb()) == []
    assert provider.calls == ["스타벅"]


def test_home_search_skips_a_completed_word_whose_kakao_call_fails(monkeypatch, caplog) -> None:
    provider = WordKakao({
        "스타벅스": RuntimeError("GET https://dapi.kakao.com/...?query=스타벅스 failed"),
        "스타벅스 리저브": [place("스타벅스 리저브 청담", "서울 강남구 청담동 3", pid="k3")],
    })
    monkeypatch.setattr(place_search, "suggest_place_names", lambda db, *, query, scope: ["스타벅스", "스타벅스 리저브"])
    caplog.set_level(logging.WARNING)

    items = place_search.search_places("스타벅", provider=provider, db=ClosingDb())

    assert [item["id"] for item in items] == ["kakao:k3"]
    assert "place_search_suggestion_failed error=RuntimeError" in caplog.text and "dapi.kakao.com" not in caplog.text
```

기존 시험 고치기(이 과제에서 함께):
- `test_places_route_needs_login_and_returns_camel_case_items`(약 :171-175)의 기대 딕트에 `"viaWord": None` 을 넣는다.
- `test_place_routes_release_the_db_session_before_calling_kakao`(약 :248): `monkeypatch.setattr(place_search, "suggest_place_names", lambda *args, **kwargs: [])` 를 더하고, 기대 `events` 를 `["db closed", "kakao", "db closed", "db closed", "kakao"]` 로 바꾼다(검색: 로그인 확인 뒤 닫음 → 친 말 카카오 → 대신 찾기 완성어 읽고 닫음, 근처: 닫음 → 카카오).

- [ ] **Step 2: 실패 확인**

Run: `... tests/test_place_search.py`
Expected: FAIL(`db` 인자 없음 · 대신 찾기 없음).

- [ ] **Step 3: 구현**

`place_search.py`:

```python
from app.services.place_suggest import suggest_place_names

FALLBACK_WORDS = 3   # 친 말로 0곳일 때 대신 찾는 완성어 수(말마다 카카오 1번)


def _search_by_suggestions(db, client: KakaoLocalSearchProvider, query: str) -> list[dict[str, object]]:
    """덜 친 말('스타벅')은 카카오 키워드 검색이 못 찾는다(10/12 실측 0곳) - 우리 공공데이터 완성어(전국, 3자 이상이면 가게 이름도)
    상위 3개로 대신 찾아 15곳까지 모은다. 줄마다 viaWord 로 찾은 말을 단다. 완성어 읽기 뒤 세션을 바로 놓는다(카카오를 기다리는 동안 쥐지 않게).
    완성어 읽기가 실패하면 경고 1줄과 빈 목록 - 덤 기능이 검색을 500 으로 만들지 않는다."""

    try:
        words = suggest_place_names(db, query=query, scope=None)[:FALLBACK_WORDS]
    except Exception as error:   # noqa: BLE001
        logger.warning("place_search_suggest_failed error=%s", type(error).__name__)
        words = []
    finally:
        db.close()
    items: list[dict[str, object]] = []
    seen: set[object] = set()
    for word in words:
        try:
            found = client.search_keyword(query=word, size=KEYWORD_SIZE)
        except Exception as error:   # noqa: BLE001 - 말 하나가 실패해도 다음 말로
            logger.warning("place_search_suggestion_failed error=%s", type(error).__name__)
            continue
        for place in found:
            item = _place_item(place)
            if item["id"] not in seen:
                seen.add(item["id"])
                items.append({**item, "viaWord": word})
    return items[:KEYWORD_SIZE]
```

`search_places` 서명을 `search_places(query: str, provider: KakaoLocalSearchProvider | None = None, db=None)` 로 바꾸고, 키워드 호출의 `try` 에 실패 표시를 단 뒤 `return items` 앞에서 대신 찾는다.

```python
    keyword_failed = False
    try:
        items += [_place_item(place) for place in client.search_keyword(query=q, size=KEYWORD_SIZE)]
    except Exception as error:   # noqa: BLE001
        logger.warning("place_search_keyword_failed error=%s", type(error).__name__)
        keyword_failed = True
    if not items and not keyword_failed and db is not None:
        items = _search_by_suggestions(db, client, q)
    return items
```

`schemas/places.py` `PlaceSearchItem` 의 `distanceMeters` 뒤에:

```python
    # 친 말로 카카오가 0곳이라 우리 공공데이터 완성어로 대신 찾은 줄이면 그 말(카카오 값 아님), 아니면 null
    viaWord: str | None = None
```

`routes/places.py` `search_places` 는 `place_search.search_places(query, db=db)` 로 부른다(`_signed_in` 이 닫은 세션은 완성어를 읽을 때 새 연결을 잡는다 - SQLAlchemy 2).

- [ ] **Step 4: 통과 확인**

Run: `... tests/test_place_search.py`
Expected: PASS.

---

### Task 5: 계약 문서 · golden · 기능 명세

**Files:**
- Modify: `docs/mvp-api-contract.md` (place-search 절 약 1309-1363, place-suggest 절 약 1365-1388 삭제, places/search 절 약 1390-1433, 모델 표 `PlaceSearchCandidate` 약 1844-1860)
- Modify: `.agent/evals/api-contract-golden.json` (`/api/trips/1/place-search`, `/api/trips/1/place-suggest` 삭제, `/api/places/search`)
- Modify: `docs/implemented-feature-spec.md` (장소 담기 행)
- Test: `backend/tests/test_places_contract_docs.py`

**Interfaces:**
- Consumes: 과제 2 · 3 · 4 의 동작(page 1~3 · 15곳 · nearby · viaWord · 대신 찾기 · place-suggest 없음).

- [ ] **Step 1: 시험을 먼저 고친다**

`test_places_contract_docs.py`:
- `test_the_search_docs_describe_the_prematch_on_each_row`(약 :74-80)의 `"6곳"` · `"6 places"` 단정을 `"15곳"` · `"15 places"` 로.
- 기존 `test_the_search_docs_describe_the_area_first_search_and_its_fallback`(6곳 미만 · 2차 · 응답 모양은 같다 등 옛 문구)은 아래 새 시험으로 대신하고 지운다.
- `SUGGEST_HEADING` 상수와 place-suggest 를 보는 시험(`test_the_suggest_route_is_in_the_golden_the_contract_and_the_app`, `test_the_suggest_docs_state_...`, `test_the_feature_spec_lists_the_suggest_endpoint`)을 지운다.
- 아래를 더한다.

```python
def test_place_suggest_is_gone_from_the_contract_the_golden_and_the_feature_spec() -> None:
    assert "place-suggest" not in CONTRACT
    assert all("place-suggest" not in item["path"] for item in GOLDEN["endpoints"])
    assert "place-suggest" not in (ROOT / "docs/implemented-feature-spec.md").read_text(encoding="utf-8")


def test_the_search_docs_describe_pages_marks_and_completed_word_search() -> None:
    search = section("### GET /trips/{trip_id}/place-search", "### GET /places/search")
    for needle in ("15곳", "page", "1~3", "45곳", "nearby", "다른 지역", "viaWord", "덜 친 말", "완성어 상위 3개", "최대 8번",
                   "반경 밖 장소는 결과에 들지 않", "이웃 지역", "3자 이상"):
        assert needle in search, needle
    assert "6곳" not in search
    home = section("### GET /places/search", "### GET /places/nearby")
    for needle in ("viaWord", "덜 친 말", "3자 이상"):
        assert needle in home, needle
    behavior = golden("GET", "/api/trips/1/place-search")["dbModeBehavior"]
    for needle in ("15 places", "page", "nearby", "viaWord", "completed words"):
        assert needle in behavior, needle
    assert "6 places" not in behavior
    assert "viaWord" in golden("GET", "/api/places/search")["dbModeBehavior"]
    assert golden("GET", "/api/places/search")["optionalArrayItemFields"]["viaWord"] == "string|null"
```

- [ ] **Step 2: 실패 확인**

Run: `... tests/test_places_contract_docs.py`
Expected: FAIL.

- [ ] **Step 3: 계약 문서**

place-search 절 머리 설명에서 `6곳` 이 든 문장(영어 `6 places (6곳)` 포함)을 아래 첫 단락으로 바꾸고, 기존 '지역 먼저' 단락을 아래 둘째 단락으로, 그 뒤에 셋째 단락을 더한다.

```markdown
결과는 쪽(`page`, 1~3, 기본 1)마다 15곳이다. 카카오가 한 검색어에 45곳까지만 주므로 3쪽이 끝이다(밖이면 422). 줄마다 `nearby` 와 `viaWord` 를 단다.

**지역 먼저**: 일정에 지역(`travelAreaId`)이 있으면 그 지역 공공데이터 장소의 중앙값(`GET /trips/{trip_id}/area-center` 와 같은 점)을 구해 카카오에 좌표와 함께 보낸다. 목록은 [그 점 반경 20km(`radius=20000`) 1~3쪽] 뒤에 [반경 없이 같은 좌표 쪽으로 기운 전국 1~3쪽]을 이은 것이고(카카오 장소 id 로 겹침을 뺀다) `page` 는 그 목록의 15곳씩이다. 반경 쪽에서 15곳이 차는 쪽에는 반경 밖 장소는 결과에 들지 않는다. 반경은 지역 경계가 아니라 중심점 둘레라 이웃 지역 장소가 섞일 수 있고, 도 전체처럼 20km 보다 넓은 지역은 반경 밖의 지역 안 장소가 전국 쪽에서 나온다. `nearby` 는 카카오가 준 거리로 20km 안이면 true, 밖이면 false, 중심을 구하지 못했으면(지역 없음 · 그 지역 공공데이터 없음) null 이다 - 이때는 좌표 없이 그 쪽을 한 번 부른다. 화면은 첫 false 줄 앞에 '다른 지역' 구분 줄을 긋는다. 서버는 상태를 두지 않아 2 · 3쪽은 앞 쪽들을 다시 부른다(카카오 호출: 1쪽 1~2번, 2쪽 최대 5번, 3쪽 최대 6번). 반경 쪽이 실패하면 빈 배열(2 · 3쪽도), 전국 쪽만 실패하면 모은 줄 그대로다.

**덜 친 말**: 카카오 키워드 검색은 낱말 단위라 덜 친 말(`스타벅`)로는 0곳이다. 1쪽에서 친 말로 0곳이면 우리 공공데이터(`public_places`) 이름으로 만든 완성어 상위 3개로 위 목록의 1쪽을 대신 찾아 20km 안 줄을 말 순서대로 먼저, 나머지를 뒤에 모아 15곳에서 끊는다. 완성어는 일정 지역 안 이름이 먼저고 지역 안 체인은 '상표 + 지역'이다. 지역이 없으면 전국이고, 2자는 TourAPI 이름만, 3자 이상이면 가게 이름도 보며 체인은 상표만이다. 줄마다 `viaWord` 에 찾은 말을 싣는다(대신 찾지 않은 줄은 null). 대신 찾은 결과는 2쪽이 없다. 카카오 호출은 친 말 1~2번에 대신 찾기 최대 6번, 모두 최대 8번이다. 완성어가 없거나 완성어 읽기가 실패하면 빈 배열이다. 말 하나의 카카오 실패는 건너뛴다. 카카오로 가는 말은 우리 공공데이터 이름과 사용자가 친 말뿐이고, 검색어 · 완성어 · 좌표는 로그에 남기지 않는다.
```

Query 목록에 `` - `page`: integer, 1-3(기본 1). 15곳씩. `` 을 더하고, 응답 예시 줄에 `"nearby": true, "viaWord": null` 을 더한다. `### GET /trips/{trip_id}/place-suggest` 절 전체를 지운다(그 안의 "지역이 없으면 전국 관광지류(TourAPI) 이름만" 문장도 함께 사라진다). places/search 절에 단락을 더한다.

```markdown
**덜 친 말**: 카카오 키워드 · 주소 검색이 모두 0곳이고 키워드 호출이 실패하지 않았으면 우리 공공데이터 이름으로 만든 완성어 상위 3개(전국 - 2자는 TourAPI 이름만, 3자 이상이면 가게 이름도, 체인은 상표만)로 키워드 검색을 대신 불러 15곳까지 모은다. 대신 찾은 줄은 `viaWord` 에 찾은 말을 싣고 그 밖의 줄은 null 이다. 완성어를 읽은 뒤 DB 세션을 바로 놓는다. 카카오가 실패했으면 대신 찾지 않는다(장애 때 기다림이 늘지 않게).
```

응답 필드 목록에 `viaWord` 를 더하고, 모델 표 `PlaceSearchCandidate` 에 `publicMatch`(빠져 있던 행 - 본문 설명과 같게) · `nearby`(boolean \| null) · `viaWord`(string \| null) 행을 더한다.

- [ ] **Step 4: golden**

- `/api/trips/1/place-search`: `query` 에 `page`(같은 항목의 기존 query 표기 꼴로 `"integer 1-3, default 1"`)를 더한다. `dbModeBehavior` 에서 `6 places` 가 든 문장을 "Returns 15 places per page (page 1-3; Kakao gives at most 45 places per word): the 20 km area pages first, then the nationwide pages, de-duplicated by Kakao place id. Each row has nearby (true within 20 km of the trip area center, false outside, null without a center) and viaWord. When the typed word finds nothing on page 1, the top 3 completed words from our public place names are searched instead (at most 8 Kakao calls) and those rows carry viaWord." 로 바꾼다. `requiredArrayItemFields` 에 `"nearby": "boolean|null"`, `"viaWord": "string|null"` 을 더한다(같은 항목의 기존 타입 문자열 꼴).
- `/api/trips/1/place-suggest` 항목을 지운다.
- `/api/places/search`: `optionalArrayItemFields` 에 `"viaWord": "string|null"` 을 더하고, `dbModeBehavior` 끝에 "When Kakao finds nothing and the keyword call did not fail, the top 3 completed words (nationwide; shop names from 3 characters) are searched instead and those rows carry viaWord." 를 더한다.

- [ ] **Step 5: 기능 명세**

`docs/implemented-feature-spec.md` 장소 담기 행:
- "일정 안 장소 검색은 카카오 결과 6곳을 보이고," → "일정 안 장소 검색은 카카오 결과를 15곳씩('더 보기'로 45곳까지) 보이고,"
- "검색 칸에 2자 이상 치면 ... 완성 검색어(최대 6줄)가 칸 아래에 뜨고, 줄을 누르면 그 말로 검색한다. 일정에 지역이 있으면 카카오 검색은 그 지역 중심 20km 안 장소를 먼저 보인다." → "일정에 지역이 있으면 그 지역 중심 20km 안 장소가 위, 나머지는 '다른 지역' 아래다. 덜 친 말('스타벅')은 우리 공공데이터 완성어로 대신 찾아 '‘말’ 검색 결과'로 보인다(홈 검색도 같다)."
- 엔드포인트 칸에서 `place-suggest` 를 지운다.
- 홈 검색 행이 있으면 "장소 카드 지도는 크게(260px · 넓은 화면 360px)" 를 더한다.

- [ ] **Step 6: 통과 확인**

Run: `... tests/test_places_contract_docs.py` · `node -e "JSON.parse(require('fs').readFileSync('.agent/evals/api-contract-golden.json','utf8'))"`(저장소 루트)
Expected: PASS · 오류 없음. golden 은 원래 줄 끝을 지킨다(`git diff --stat` 가 바꾼 줄 수만큼).

---

### Task 6: 일정 시트 - 서브창 걷기 · 결과 칸 15곳 · 다른 지역 · 더 보기

**Files:**
- Delete: `frontend/src/components/itinerary/placeAdd/PlaceSuggestions.tsx`, `PlaceSuggestions.test.tsx`, `usePlaceSuggestions.ts`, `usePlaceSuggestions.test.ts`
- Modify: `frontend/src/api/types.ts`, `frontend/src/api/dataApi.ts`, `frontend/src/api/backendApi.ts`, `frontend/src/api/backendApi.test.ts`
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Modify: `frontend/src/styles/app.css`
- Modify: `frontend/src/app/__tests__/trip-place-basket.test.tsx`, `frontend/src/app/__tests__/trip-detail.test.tsx`, `frontend/e2e-backend/backend-mode.spec.ts`

**Interfaces:**
- Consumes: 서버 `GET /api/trips/{id}/place-search?query=&page=` (배열, 줄에 `nearby` · `viaWord`).
- Produces: `TripPlaceSearchOptions = { query: string; page?: number }`, `PlaceSearchCandidate.nearby?: boolean | null`, `PlaceSearchCandidate.viaWord?: string | null`, `PlaceSearchItem.viaWord?: string | null`. `suggestTripPlaceNames` 없음.

- [ ] **Step 1: 서브창 걷기**

- 위 4 파일을 지운다.
- `backendApi.ts` · `dataApi.ts` 에서 `suggestTripPlaceNames` 를, `backendApi.test.ts` 에서 그 시험을 지운다.
- `ItineraryDetailPage.tsx` 에서 c35d5d1 이 더한 완성 검색어 조각을 모두 걷는다(`git show c35d5d1 -- frontend/src/pages/itinerary/ItineraryDetailPage.tsx` 로 대조): `PlaceSuggestions` · `usePlaceSuggestions` import, `const placeSuggestions = usePlaceSuggestions(...)`, 시트에 넘기는 `suggestions` · `suggestionQuery` · `onRequestSuggestions` · `onClearSuggestions` props 와 그 선언 · 주석, `suggestionsOpen` 상태와 `updateInputSearchQuery` 안의 `setSuggestionsOpen(true)`, 죽은 `const typedQuery`, `showSuggestions`, `pickSuggestion`, 디바운스 끝의 `onRequestSuggestions?.(...)`, `useEffect(() => onClearSuggestions, ...)`, `.place-search-box` 감싸개 div(안의 `label.field` 는 그 자리에 그대로 남긴다)와 그 onFocus · onBlur · onKeyDown, `완성 검색어 N개` 알림 span. `autoComplete="off"` 는 남긴다.
- `app.css` 의 `.place-search-box` · `.place-suggestions` · `.place-suggestion` 규칙(과 `:hover` · `:focus-visible` 변형)을 지운다.
- `trip-place-basket.test.tsx` 의 완성 검색어 `describe`(약 :830 부터 끝까지의 둘째 describe 전체)와 `suggestionList` · `suggestionLines` 도우미 · 기본 `suggestSpy`, `trip-detail.test.tsx` 의 `suggestTripPlaceNames` 기본 spy, `backend-mode.spec.ts` 의 `place-suggest` 가짜 라우트를 지운다.

Run: `grep -rn "PlaceSuggestions\|usePlaceSuggestions\|suggestTripPlaceNames\|place-suggest\|place-search-box\|place-suggestion\|suggestionsOpen\|suggestionQuery" frontend/src frontend/e2e-backend`
Expected: 0줄.

- [ ] **Step 2: 실패하는 시험 - 결과 칸**

`trip-place-basket.test.tsx` 에 더한다(`PlaceSearchCandidate` 는 이 파일이 이미 import 한다 - 다시 import 하지 않는다. 파일의 `addTrip` · `openAddSheet` 도우미를 쓴다).

```tsx
const candidate = (id: string, extra: Partial<PlaceSearchCandidate> = {}): PlaceSearchCandidate => ({
  id: `kakao:${id}`, label: "📍", title: `장소${id}`, meta: "카페", externalPlaceId: id, sourceProvider: "kakao", publicMatch: null, ...extra,
});
const fifteen = (from: number, extra: Partial<PlaceSearchCandidate> = {}) =>
  Array.from({ length: 15 }, (_, index) => candidate(String(from + index), extra));

it("shows every row the server sends, marks where other regions begin, and loads the next 15 with 더 보기", async () => {
  const trip = addTrip("150");
  const searchSpy = vi.spyOn(appDataApi, "searchTripPlaces").mockImplementation(async (_tripId, options) =>
    options.page === 2
      ? fifteen(16, { nearby: false })
      : [...fifteen(1, { nearby: true }).slice(0, 10), ...fifteen(11, { nearby: false }).slice(0, 5)],
  );
  const { user, dialog } = await openAddSheet(trip);
  await user.type(within(dialog).getByLabelText("장소 검색"), "카페");

  const list = await within(dialog).findByRole("list", { name: "장소 검색 결과" });
  expect(within(list).getAllByRole("button", { name: /선택$/ })).toHaveLength(15);
  const marks = within(list).getAllByText("다른 지역");
  expect(marks).toHaveLength(1);
  expect(marks[0].closest('[role="listitem"]')).toHaveTextContent("장소11");   // 첫 '밖' 줄 위

  await user.click(within(dialog).getByRole("button", { name: "더 보기" }));
  await waitFor(() => expect(within(list).getAllByRole("button", { name: /선택$/ })).toHaveLength(30));
  expect(searchSpy).toHaveBeenLastCalledWith("150", { query: "카페", page: 2 });
  expect(within(list).getAllByText("다른 지역")).toHaveLength(1);   // 이어 붙인 '밖' 줄에는 다시 긋지 않는다
  expect(within(dialog).getByRole("button", { name: "장소16 선택" })).toHaveFocus();   // 새로 붙은 첫 줄로
});

it("says which completed word found the rows and offers no 더 보기 for them", async () => {
  const trip = addTrip("151");
  vi.spyOn(appDataApi, "searchTripPlaces").mockResolvedValue([
    ...fifteen(1, { nearby: true, viaWord: "스타벅스 전남" }).slice(0, 12),
    ...fifteen(20, { nearby: false, viaWord: "스타벅스 리저브" }).slice(0, 3),
  ]);
  const { user, dialog } = await openAddSheet(trip);
  await user.type(within(dialog).getByLabelText("장소 검색"), "스타벅");

  expect(await within(dialog).findByText("‘스타벅스 전남’ 외 1개 검색 결과")).toBeInTheDocument();
  expect(within(dialog).queryByRole("button", { name: "더 보기" })).not.toBeInTheDocument();
});

it("drops a late next page when the search word changed meanwhile and does not keep the new button loading", async () => {
  const trip = addTrip("152");
  let releaseMore: (rows: PlaceSearchCandidate[]) => void = () => undefined;
  vi.spyOn(appDataApi, "searchTripPlaces").mockImplementation((_tripId, options) =>
    options.page === 2
      ? new Promise((resolve) => { releaseMore = resolve; })
      : Promise.resolve(fifteen(options.query === "카페" ? 1 : 100, { nearby: true })),
  );
  const { user, dialog } = await openAddSheet(trip);
  const input = within(dialog).getByLabelText("장소 검색");
  await user.type(input, "카페");
  await within(dialog).findByRole("button", { name: "장소1 선택" });
  await user.click(within(dialog).getByRole("button", { name: "더 보기" }));

  await user.clear(input);
  await user.type(input, "빵집");
  await within(dialog).findByRole("button", { name: "장소100 선택" });
  expect(within(dialog).getByRole("button", { name: "더 보기" })).not.toHaveAttribute("aria-disabled", "true");
  await act(async () => releaseMore(fifteen(16, { nearby: false })));

  expect(within(dialog).queryByRole("button", { name: "장소16 선택" })).not.toBeInTheDocument();
});

it("shows a retryable error for a failed 더 보기 and clears it once the retry works", async () => {
  const trip = addTrip("153");
  let failNext = true;
  vi.spyOn(appDataApi, "searchTripPlaces").mockImplementation(async (_tripId, options) => {
    if (options.page !== 2) return fifteen(1, { nearby: true });
    if (failNext) {
      failNext = false;
      throw new Error("network");
    }
    return fifteen(16, { nearby: true });
  });
  const { user, dialog } = await openAddSheet(trip);
  await user.type(within(dialog).getByLabelText("장소 검색"), "카페");
  await within(dialog).findByRole("button", { name: "장소1 선택" });

  await user.click(within(dialog).getByRole("button", { name: "더 보기" }));
  expect(await within(dialog).findByRole("alert")).toHaveTextContent("더 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
  expect(within(dialog).getByRole("status")).toHaveTextContent("검색 결과 15곳");   // 상태 줄은 그대로

  await user.click(within(dialog).getByRole("button", { name: "더 보기" }));
  await within(dialog).findByRole("button", { name: "장소16 선택" });
  expect(within(dialog).queryByRole("alert")).not.toBeInTheDocument();
});

it("ends with 여기까지예요 when the next page brings nothing new", async () => {
  const trip = addTrip("154");
  vi.spyOn(appDataApi, "searchTripPlaces").mockImplementation(async (_tripId, options) =>
    options.page === 2 ? [] : fifteen(1, { nearby: true }),
  );
  const { user, dialog } = await openAddSheet(trip);
  await user.type(within(dialog).getByLabelText("장소 검색"), "카페");
  await within(dialog).findByRole("button", { name: "장소1 선택" });

  await user.click(within(dialog).getByRole("button", { name: "더 보기" }));

  expect(await within(dialog).findByText("여기까지예요")).toHaveFocus();
  expect(within(dialog).queryByRole("button", { name: "더 보기" })).not.toBeInTheDocument();
});
```

(결과 줄 단추 이름은 지금처럼 `"{title} 선택"`, 공공데이터 배지가 없으면 그대로다.)

`backendApi.test.ts` 의 기존 `searchTripPlaces` 시험 옆에 `page: 2` 가 `/api/trips/7/place-search?query=…&page=2` 로 가고 `page` 를 안 주면 붙지 않는다는 단정을 더한다.

- [ ] **Step 3: 실패 확인**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-place-basket.test.tsx src/api/backendApi.test.ts`
Expected: 새 시험 FAIL(6곳에서 잘림 · 구분 줄 · 더 보기 없음).

- [ ] **Step 4: 구현 - API · 타입**

`dataApi.ts`:

```ts
export type TripPlaceSearchOptions = {
  query: string;
  /** 1~3. 서버가 쪽마다 15곳 - '더 보기'가 다음 쪽 */
  page?: number;
};
```

`types.ts` `PlaceSearchCandidate` 끝에:

```ts
  /** 일정 지역 중심 20km 안이면 true, 밖이면 false, 중심이 없으면 null - '다른 지역' 구분 줄 */
  nearby?: boolean | null;
  /** 친 말로 0곳이라 우리 완성어로 대신 찾은 줄이면 그 말 */
  viaWord?: string | null;
```

`PlaceSearchItem` 끝에 `/** 친 말로 0곳이라 우리 완성어로 대신 찾은 줄이면 그 말 */ viaWord?: string | null;`. `backendApi.searchTripPlaces` 는 `queryString(options)` 가 `page` 를 함께 싣는다(바꿀 것 없음 - Step 2 시험이 확인).

- [ ] **Step 5: 구현 - 페이지 상태 · 더 보기**

`ItineraryDetailPage.tsx` 위 상수 자리(`PLACE_SEARCH_DEBOUNCE_MS` 옆):

```ts
const PLACE_SEARCH_PAGE_SIZE = 15;   // 서버가 쪽마다 주는 수
const PLACE_SEARCH_MAX_PAGES = 3;   // 카카오 상한 45곳
```

장소 검색 상태(`placeSearchCandidates` 선언) 옆:

```ts
  const [placeSearchPage, setPlaceSearchPage] = useState(1);
  const [isLoadingMorePlaces, setIsLoadingMorePlaces] = useState(false);
  const [placeSearchMoreError, setPlaceSearchMoreError] = useState("");
  const [placeSearchEnded, setPlaceSearchEnded] = useState(false);
  const [placeSearchFocusId, setPlaceSearchFocusId] = useState<string | null>(null);   // 더 보기 뒤 초점 줄(id) 또는 "end"

  /* 더 보기 상태를 비운다 - 말이 바뀜 · 후보 고름 · 창 열기에서. 늦게 오는 쪽은 요청 번호가 달라 버려진다 */
  const resetPlaceSearchMore = () => {
    setPlaceSearchPage(1);
    setIsLoadingMorePlaces(false);
    setPlaceSearchMoreError("");
    setPlaceSearchEnded(false);
    setPlaceSearchFocusId(null);
  };
```

`resetPlaceSearchMore()` 를 `invalidatePlaceSearch` 안(요청 번호를 올린 뒤), `loadPlaceSearchCandidates` 시작, `selectPlaceSearchCandidate` 시작, `openAddPlace` · `openEditPlace` 에서 상태를 처음으로 맞추는 자리에서 부른다.

`loadPlaceSearchCandidates` 아래에:

```ts
  /* '더 보기' - 같은 말의 다음 15곳을 뒤에 붙인다(겹치는 id 는 뺀다). 그새 말이 바뀌었거나 창이 닫혔으면 버린다.
     새 줄이 0개면 '여기까지예요'로 끝낸다(2 · 3쪽 카카오 실패도 서버는 빈 배열이라 같다) */
  const loadMorePlaceSearchCandidates = async () => {
    if (!trip || isLoadingMorePlaces) return;
    const sessionId = placeEditorSessionRef.current;
    const requestId = placeSearchRequestRef.current;
    const isCurrent = () => placeEditorSessionRef.current === sessionId && placeSearchRequestRef.current === requestId;
    const nextPage = placeSearchPage + 1;
    setIsLoadingMorePlaces(true);
    setPlaceSearchMoreError("");
    try {
      const more = await appDataApi.searchTripPlaces(trip.id, { query: placeSearchQuery.trim(), page: nextPage });
      if (!isCurrent()) return;
      const shown = new Set(placeSearchCandidates.map((candidate) => candidate.id));
      const fresh = more.filter((candidate) => !shown.has(candidate.id));
      setPlaceSearchCandidates((current) => [...current, ...fresh]);
      setPlaceSearchPage(nextPage);
      if (fresh.length === 0) setPlaceSearchEnded(true);
      setPlaceSearchFocusId(fresh[0]?.id ?? "end");
    } catch {
      if (isCurrent()) setPlaceSearchMoreError("더 불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      if (isCurrent()) setIsLoadingMorePlaces(false);
    }
  };
```

(`trip` · `placeSearchQuery` 는 이 컴포넌트의 실제 이름 - `loadPlaceSearchCandidates` 를 부르는 곳이 쓰는 일정 · 검색 말과 같은 값.)

`const placeSearchResults = placeSearchCandidates.slice(0, 6);` 과 그 위 주석을 아래로 바꾼다.

```ts
  // 서버가 준 순서 그대로 전부(지역 먼저 · 나머지는 '다른 지역' 아래) - 친 말로 다시 거르지 않는다(결정 22)
  const placeSearchResults = placeSearchCandidates;
  const canLoadMorePlaces =
    !placeSearchEnded &&
    placeSearchCandidates.length === placeSearchPage * PLACE_SEARCH_PAGE_SIZE &&
    placeSearchPage < PLACE_SEARCH_MAX_PAGES &&
    !placeSearchCandidates.some((candidate) => candidate.viaWord);
```

시트에 `canLoadMore={canLoadMorePlaces}`, `isLoadingMore={isLoadingMorePlaces}`, `loadMoreError={placeSearchMoreError}`, `searchEnded={placeSearchEnded}`, `focusResultId={placeSearchFocusId}`, `onFocusedResult={() => setPlaceSearchFocusId(null)}`, `onLoadMore={() => void loadMorePlaceSearchCandidates()}` 를 넘기고 시트 props 에 같은 이름(`canLoadMore?: boolean; isLoadingMore?: boolean; loadMoreError?: string; searchEnded?: boolean; focusResultId?: string | null; onFocusedResult?: () => void; onLoadMore?: () => void;`)을 선언한다.

- [ ] **Step 6: 구현 - 결과 칸 그리기**

시트 본문 위쪽 계산 자리(`searchStatus` 앞)에:

```ts
  const viaWords = [...new Set(searchCandidates.flatMap((candidate) => (candidate.viaWord ? [candidate.viaWord] : [])))];
  const viaLabel = viaWords.length > 0 ? `‘${viaWords[0]}’${viaWords.length > 1 ? ` 외 ${viaWords.length - 1}개` : ""} 검색 결과` : "";
  const firstOtherIndex = searchCandidates.findIndex((candidate) => candidate.nearby === false);
  const resultsAreaRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    // 더 보기 뒤 초점: 새로 붙은 첫 줄, 새 줄이 없으면 '여기까지예요' - 사라진 단추에서 초점이 body 로 떨어지지 않게
    if (!focusResultId) return;
    const area = resultsAreaRef.current;
    const target =
      focusResultId === "end"
        ? area?.querySelector<HTMLElement>(".place-search-end")
        : Array.from(area?.querySelectorAll<HTMLElement>("[data-result-id]") ?? []).find((element) => element.dataset.resultId === focusResultId);
    target?.focus();
    onFocusedResult?.();
  }, [focusResultId, onFocusedResult]);
```

`searchStatus` 의 `` `검색 결과 ${searchCandidates.length}곳` `` 을 `` `${viaLabel ? `${viaLabel} · ` : ""}검색 결과 ${searchCandidates.length}곳` `` 로 바꾼다(화면 읽기는 상태 줄로 대신 찾았다는 것을 듣는다).

`.place-search-area` div 에 `ref={resultsAreaRef}` 를 단다. 상태 · 오류 줄 뒤, 목록 앞에:

```tsx
                  {viaLabel && (
                    <p aria-hidden="true" className={isSearchPending ? "place-search-via is-stale" : "place-search-via"}>
                      {viaLabel}
                    </p>
                  )}
```

줄 단추에 `data-result-id={candidate.id ?? undefined}` 를 달고, listitem 안 단추 앞에:

```tsx
                            {index === firstOtherIndex && (
                              <p className={index === 0 ? "place-search-group is-top" : "place-search-group"}>다른 지역</p>
                            )}
```

목록 div 닫는 태그 뒤(같은 `.place-search-area` 안)에:

```tsx
                  {loadMoreError && (
                    <p className="place-search-status error" role="alert">{loadMoreError}</p>
                  )}
                  {canLoadMore && searchCandidates.length > 0 && (
                    <button
                      aria-disabled={isLoadingMore || isSearchPending ? "true" : undefined}
                      className="place-search-more"
                      type="button"
                      onClick={() => {
                        if (!isLoadingMore && !isSearchPending) onLoadMore?.();
                      }}
                    >
                      {isLoadingMore ? "불러오는 중…" : "더 보기"}
                    </button>
                  )}
                  {searchEnded && (
                    <p className="place-search-end" tabIndex={-1}>여기까지예요</p>
                  )}
```

(`useRef` · `useEffect` 는 이 파일이 이미 import 한다. `onFocusedResult` 는 부모가 넘기는 화살표라 렌더마다 바뀌어도 `focusResultId` 가 null 로 돌아가 효과가 한 번만 일한다.)

`app.css` 의 `.place-search-area` 규칙들 뒤에:

```css
.place-search-via,
.place-search-group,
.place-search-end {
  margin: 0;
  color: var(--gray-600);
  font-size: 12.5px;
  font-weight: 700;
}

.place-search-via.is-stale {
  opacity: 0.55;
}

.place-search-group {
  padding: 6px 2px 4px;
  border-top: 1px solid var(--gray-200);
}

.place-search-group.is-top {
  padding-top: 0;
  border-top: 0;
}

.place-search-more {
  min-height: 40px;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-sm);
  background: #fff;
  color: var(--ink);
  font-size: 14px;
  font-weight: 700;
}

.place-search-more[aria-disabled="true"] {
  color: var(--gray-500);
}

.place-search-end {
  padding: 6px 2px;
  text-align: center;
}
```

(`.place-search-results.is-stale` 의 흐림 값과 맞춘다 - 다르면 그 값을 쓴다.)

- [ ] **Step 7: e2e 가짜 응답**

`backend-mode.spec.ts` 의 `place-search` 가짜는 빈 배열 그대로 둔다(모양 같음). `place-suggest` 가짜가 Step 1 에서 지워졌는지 확인한다. 15줄 · 구분 줄 · 더 보기의 폭별 모양은 사용자 브라우저 확인 목록으로 넘긴다(0.7).

- [ ] **Step 8: 통과 확인**

Run: `cd frontend && npx vitest run src/app/__tests__/trip-place-basket.test.tsx src/app/__tests__/trip-detail.test.tsx src/api && npm run typecheck && npm run test:mojibake`
Expected: PASS · 오류 없음.

---

### Task 7: 홈 - 대신 찾은 안내 줄 · 카드 지도 크게

**Files:**
- Modify: `frontend/src/components/HomeSearch.tsx` (장소 목록 약 241-251, `loadingPlaces` 상태 약 :145)
- Modify: `frontend/src/styles/home.css` (약 745 · 786-790)
- Test: `frontend/src/app/__tests__/home.test.tsx`

**Interfaces:**
- Consumes: `PlaceSearchItem.viaWord`(과제 6 타입).

- [ ] **Step 1: 실패하는 시험**

`home.test.tsx` 의 "searches places from the home search bar, opens a place card ..." 시험(약 :831)의 준비(로그인 · `listPolicies` · `getProfile` spy · `cleanup` · `renderAppRoute("/home")` · `findByRole("searchbox", { name: "지역 · 혜택 · 장소 검색" })` · `user.click` · `user.type`)를 그대로 따라 새 시험을 쓴다.

```tsx
it("says which completed word found the home place rows and does not fold them behind benefit words", async () => {
  // 준비는 :831 시험과 같다(로그인 · 정책 · 프로필 spy · 홈 렌더)
  vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([
    { kind: "place", id: "kakao:1", name: "스타벅스 강남점", category: "음식점 > 카페", address: "서울 강남구 역삼동 1", latitude: 37.5, longitude: 127.0, viaWord: "스타벅스" },
    { kind: "place", id: "kakao:2", name: "스타벅스 리저브 청담", category: "음식점 > 카페", address: "서울 강남구 청담동 3", latitude: 37.5, longitude: 127.0, viaWord: "스타벅스 리저브" },
  ]);
  const search = await screen.findByRole("searchbox", { name: "지역 · 혜택 · 장소 검색" });
  await user.click(search);
  await user.type(search, "스타벅");

  expect(await screen.findByText("‘스타벅스’ 외 1개 검색 결과")).toBeInTheDocument();
  expect(screen.getByText("스타벅스 강남점")).toBeInTheDocument();
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd frontend && npx vitest run src/app/__tests__/home.test.tsx -t "completed word"`
Expected: FAIL.

- [ ] **Step 3: 구현**

`HomeSearch.tsx` 의 `loadingPlaces` 상태 선언(약 :145) 바로 아래에:

```ts
  // 친 말로 카카오가 0곳이라 서버가 우리 완성어로 대신 찾은 줄이면 그 말들(줄 순서)
  const placeViaWords = [...new Set((places ?? []).flatMap((item) => (item.viaWord ? [item.viaWord] : [])))];
```

장소 목록의 접힘 조건 `benefitWords && !placesOpen` 을 `benefitWords && !placesOpen && placeViaWords.length === 0` 으로 바꾸고(대신 찾은 줄은 '이름이 든 장소'가 아니라 접지 않는다), `<h3>장소<span className="src">카카오 지도</span></h3>` 바로 뒤에:

```tsx
                  {placeViaWords.length > 0 && (
                    <p className="home-places-via">
                      {`‘${placeViaWords[0]}’${placeViaWords.length > 1 ? ` 외 ${placeViaWords.length - 1}개` : ""} 검색 결과`}
                    </p>
                  )}
```

`home.css`: 기존 세 규칙의 168px 를 260px 로 바꾼다.

```css
.home-place-map .kakao-map-view { min-height: 260px; border: 1px solid var(--gray-200); border-radius: 16px; }
.home-place-map .kakao-map-canvas { min-height: 260px; }
.home-place-map-fallback {
  min-height: 260px;
```

그리고 `.home-place-map-fallback { ... }` 규칙 **바로 뒤에** 새 블록을 둔다(앞쪽 :580 의 768px 블록에 넣으면 뒤의 260px 가 이긴다).

```css
@media (min-width: 768px) {
  .home-place-map .kakao-map-view,
  .home-place-map .kakao-map-canvas,
  .home-place-map-fallback { min-height: 360px; }
}
```

`.home-places-more` 규칙 근처에 `.home-places-via { margin: 0 4px 6px; color: var(--gray-600); font-size: 12.5px; font-weight: 700; }` 를 더한다(장소 `h3` 의 좌우 4px 와 맞춤 - 실제 값이 다르면 그 값).

- [ ] **Step 4: 통과 확인**

Run: `cd frontend && npx vitest run src/app/__tests__/home.test.tsx && npm run typecheck`
Expected: PASS.

---

### Task 8: 마무리(컨트롤러)

- [ ] 전체 시험: backend `python -m pytest`(`--ignore=tests/test_stay_discount_semantics_snapshot.py`), `npx vitest run`(mypage 6건은 원래 실패), `npm run typecheck`, `npm run test:mojibake`, `npm run build`, 4173 backend · frontend 다시 빌드 뒤 `npm run test:e2e:containers`, `git diff --check`, U+FFFD 0.
- [ ] 실측(컨테이너 안, 개수 · 시간만): 일정 검색 1쪽 · 2쪽 · 3쪽 왕복 시간(`스타벅스@서울`), 덜 친 말 5개(`스타벅@전남 전체` `메타세쿼@담양` `순천만습@전남 전체` `초당순@강릉` `스타@서울`)의 줄 수 · `viaWord` 수 · 카카오 호출 수 · 왕복 시간, 홈 덜 친 말 3개(`스타벅` `메타세쿼` `순천만습`)의 줄 수.
- [ ] 브랜치 자체 검토(관점별) → 고침.
- [ ] `CHECKLIST.md`: 완성 검색어 서브창 · place-suggest 없앰, 15곳 · 더 보기 · 다른 지역, 덜 친 말 대신 찾기(카카오 최대 8번), 홈 대신 찾기 · 카드 지도 260/360px, 앞 커밋의 "사용자 결정 대기" 문구를 결정대로.
- [ ] 사용자 브라우저 확인 목록(15줄 · 구분 줄 · 더 보기 · 안내 줄을 360/390/430/1024/1440 에서, 홈 카드 지도 크기 포함) → 커밋(승인 범위). 푸시 · PR 은 브라우저 확인 뒤.
