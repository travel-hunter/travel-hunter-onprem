# 장소 검색 일정 지역 먼저 · 완성 검색어 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 장소 추가 시트에서 (1) 카카오 장소 검색 결과가 일정 지역 안의 장소를 먼저 보이고, (2) 단어를 덜 쳐도(`메타세쿼`) 일정 지역 안의 공공데이터 이름으로 완성 검색어를 보여 주어 누르면 그 말로 검색한다.

**Architecture:**
- 검색 결과: 일정 지역 중심 좌표(우리 공공데이터 중앙값 - 이미 있는 `trip_public_places.area_center`)를 카카오 키워드 검색에 `x` · `y` · `radius=20000` 으로 넘긴다. 1차가 성공했는데 6줄이 안 차면 같은 좌표를 반경 없이(정확도순, 지역 쪽으로 기운 전국) 한 번 더 불러 뒤를 채운다. 응답 모양은 그대로다.
- 완성 검색어: 새 API `GET /api/trips/{trip_id}/place-suggest?query=` → `string[]`(최대 6). 저장소는 **단순한 색인 질의로 후보 이름을 묶어 모으고**(지역 안 · 지역 밖 관광지), **순위는 파이썬 순수 함수**가 매긴다(SQLite 단위 시험 가능, 플래너에 기대지 않는다). 순위 규칙은 2026-10-12 실데이터 비교(후보 4개 · 검색어 20개 · 3관점 심사)에서 이긴 '최종안'이고, 0.3 은 그 SQL 의 조건을 빠짐없이 옮긴 명세다.
- 일정 지역: 접근 확인(`has_trip_access`) 뒤 새 가벼운 조회 `trip_repository.get_trip_travel_area_id` 로 지역 id 만 읽는다(일정 전체 그래프를 읽지 않는다 - 기존 시험이 금지).
- DB: `pg_trgm` GIN 색인(Alembic `0051`)으로 `ILIKE '%q%'` 를 빠르게 한다.
- 화면: 검색 칸 바로 아래에 카카오맵처럼 겹쳐 뜨는 완성 검색어 목록. 요청은 새 훅 `usePlaceSuggestions`(페이지)가 맡고 시트에는 값 · 콜백만 선택 props 로 내린다.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 · Alembic · PostgreSQL 16(`pg_trgm` contrib, 신뢰 확장) · httpx · React 18 · Vitest

**Spec:** 이 문서 '0. 설계 요약'. 순위 규칙 근거(실행한 SQL · 결과표)는 저장소 밖 작업 폴더에 있고, 결과표는 0.4 에 옮겼다.

---

## 0. 설계 요약

### 0.1 사용자 결정(2026-10-12)

| 결정 | 내용 |
|---|---|
| 완성 검색어 | 이번 PR(`feature/place-add-flow`)에 넣는다 |
| 지역 먼저 | 서울 일정에서 찾으면 서울 장소가 맨 위. 편의 기능이다(장소 자체는 지금도 결과에 보인다) |
| 검색 결과 | **지역 먼저, 모자라면 전국** - 반경 20km 를 먼저, 6줄이 안 차면 지역 쪽으로 기운 전국 검색으로 채운다 |
| 완성어 규칙 | **최종안**(아래 0.3) - 세 심사(사용자 · 지역 · 잡음) 모두 1위 |

계획 검토에서 정한 것(Ruling): 여러 시군 일정의 체인 줄은 최종안 SQL 대로 **시군마다 따로**(`스타벅스 강릉` / `스타벅스 동해`) - 한 줄로 합치면 그 말로 카카오를 불렀을 때 다른 시군 지점이 안 나오고, 상호에 시군 이름이 든 상표(`이디야삼척`)에 다른 시군 꼬리가 붙는다.

### 0.2 실측(2026-10-12, 로컬 DB · 카카오 실호출, 개수만 셈)

- 카카오 키워드 검색은 단어 단위: `메타세쿼` · `메타세쿼이` 0줄, `메타세쿼이아` 15줄. 완성 검색어는 공개 API 에 없다(카카오맵 앱 전용 - 앱 내부 주소 호출은 약관 위반).
- 지역 반영(15줄 중 지역 안 줄 수):

| 검색어@일정 지역 | 지금 | 중심 좌표만 | 반경 20km |
|---|---|---|---|
| 스타벅스@서울 | 6 | 15 | 15 |
| 남산@경주 | 0 | 0 | 15 |
| 해수욕장@강릉 | 3 | 6 | 15 |
| 메타세쿼이아@담양 | 5 | 8 | 10/11 |
| 순두부@강릉 | 3 | 15 | 15 |

- 체인 줄 말로 카카오를 부르면 그 지역 지점이 온다: `스타벅스 강릉` 12/13, `이디야커피 제주` 15/15, `호텔야자 부산` 4/4.
- 색인(검토 실측, 일회용 PG 에 108만 행 복사): GIN `name gin_trgm_ops` 77MB, 만드는 데 약 7초. 2자 어절 앞(`스타%`, `% 스타%`)도 색인을 탄다. 부호만 있는 입력(`--`, `()`)은 색인을 못 타 약 220ms. 색인 없이 서울 시도 `ILIKE '%q%'` 한 번 약 290ms.
- 로컬 DB: 시도는 모두 2자(+ NULL 14행, TourAPI), 1자 시군 0행, 광역시 구는 `중구` · `해운대` 꼴.

### 0.3 완성 검색어 규칙(최종안 - SQL 조건을 그대로 옮김)

표기: `q` = 앞뒤 공백을 자른 검색어, `ql` = `q.lower()`. 문자열 비교 · '시작' · '포함'은 모두 대소문자를 무시한다(`.lower()` 끼리). 정렬의 '가나다'는 **파이썬 기본 `str` 비교(코드 포인트)** 다 - `locale` · ICU 정렬은 쓰지 않는다(0.4 가 이 순서로 만들어졌다).

**① 입력**
- 2자 미만이거나 글자 · 숫자(`re.search(r"\w", q)`)가 없으면 빈 목록(DB 를 부르지 않는다). 80자 초과 422.
- LIKE 특수문자 `\` · `%` · `_` 는 이스케이프(`ESCAPE '\'`).

**② 후보 행(저장소)** - 각 행에 `tier`(0 = 지역 안 · 1 = 지역 밖)를 붙인다.
- tier 0, 지역 있음: 일정 지역(시도 + 고른 시군 - `trip_public_places.area_scope`) 안의 TourAPI 전부 + 상가정보 중 `category <> 'leisure'`.
- tier 0, 지역 없음: 전국 TourAPI 전부.
- tier 1(지역 있을 때만): 지역 밖 TourAPI 중 `category in ('sight', 'culture', 'leisure')`.
- 모두 `name ILIKE '%q%'`.
- 거르개: 상가정보 중 이름에 `노래` · `단란` · `유흥` · `룸살롱` · `가라오케` · `나이트클럽` 이 든 행 제외.
- 2자 규칙: `len(q) >= 3` 이거나, (tier 0 이고 TourAPI) 이거나, 이름이 `q` 로 시작하거나 `" " + q` 를 품은 행만 남긴다.
- 묶기: `(tier, name, source, category, sido, city)` 로 묶어 `count`. 상한 `SUGGEST_CANDIDATE_LIMIT = 4000` - tier → 이름 길이 → 이름 순으로 자른다(걸리면 경고 `place_suggest_candidates_capped count=<n>`).

**③ 행마다 계산**
- `attr` = TourAPI 이고 `category in ('sight', 'culture', 'leisure')`(관광지).
- `t`(보일 말) = 이름에서 `\s*(\[[^\]]*\]|\([^)]*\))` 를 모두 지우고 앞뒤 공백을 자른 말. 그 말이 비거나 `q` 를 품지 않으면 원래 이름.
- `core` = `t` 앞에 붙은 그 행 자신의 시도 · 시군 이름을 **되풀이해** 뗀 말: 정규식 `^((<sido>|<city>)\s*)+`(시군이 없으면 `^((<sido>)\s*)+`, 이름은 `re.escape`). **시도가 없으면(NULL) 떼지 않고 `core = t`**. 뗀 뒤 비면 `t`. 예: `담양 메타세쿼이아길` → `메타세쿼이아길`, `전주한옥마을` → `한옥마을`, `전북 전주 한옥마을` → `한옥마을`, `해운대해수욕장`(부산 해운대) → `해수욕장`(최종안 그대로 - #6 이 이 동작에 기댄다).
- `label` = tier 0 이고 지역이 있으면 그 행의 시군(범위에 시군이 있을 때) 또는 그 행의 시도(시도 전체일 때). 그 밖은 없음.

**④ 줄(line0)** - `(tier, label, t)` 로 묶는다. 줄의 `core` = 최소값, `attr` = 하나라도, `tour` = TourAPI 행이 하나라도, `n` = count 합, `lvl` = 최소값. 행의 lvl: `t` 나 `core` 가 `q` 로 시작하면 1, `t` 가 `" " + q` 를 품으면 2, 아니면 3.

**⑤ 지역 밖 · 지역 없음 core 합치기** - tier 1 이거나 지역 없음일 때, 같은 tier 에서 `core.lower()` 가 같은 줄이 2개 이상이면 그 줄들의 말을 `core` 로 바꾼다(`곡성 · 담양 메타세쿼이아길` → `메타세쿼이아길`). 나머지는 `t` 그대로.

**⑥ 열쇠 어절(kw)** - 말의 첫 어절이 `q` 로 시작하면 그 어절, 아니면 `core` 의 첫 어절(공백 기준 `split(" ")[0]`).

**⑦ 지역 안 관광지 core 모음(acore)** = tier 0 · attr 줄의 `core.lower()` 집합.

**⑧ 어절 줄(par)** - tier 0 · attr 줄 가운데 kw 가 `q` 로 시작하고 `kw.lower() != ql` 이고 `kw.lower()` 가 acore 에 없는 줄을 `kw.lower()` 로 묶어, **줄이 2개 이상**인 묶음마다 줄 하나를 더한다: 말 = 그 묶음 kw 의 최소값, tier 0, lvl 1, **attr = 참(관광지 줄)**, tour = 거짓, chain = 거짓, n = 0, kw = 그 어절. 무게는 ⑪의 관광지 무게(대표성).

**⑨ 체인 줄** - '접을 수 있는' 줄: tier 0 · attr 아님 · 말이 `q` 로 시작 · 말의 첫 어절 w1 에 대해 `w1.lower() != ql` · `w1.lower()` 가 acore 에도 어절 줄 열쇠에도 없음.
- 상표 수: `(label, w1.lower())` 마다 접을 수 있는 줄 수.
- 붙여 쓴 상표 모으기: 같은 label 에서 상표 x 가 다른 상표 y 로 시작하고(`len(x) > len(y)`), y 의 줄 수가 2 이상이고 x 보다 많으면 x 를 y 로 모은다(후보가 여럿이면 줄 수 큰 것 → 짧은 것).
- 같은 `(label, 모은 상표)` 의 접을 수 있는 줄이 2개 이상이면 체인: 말 = 그 줄들 w1 의 최소값 + (label 이 있으면 `" " + label`), core = 그 w1, kw = 그 w1. 1개뿐이면 접지 않는다(원래 줄).
- label 이 시군이므로 여러 시군 일정에서는 시군마다 따로 생긴다(Ruling).

**⑩ 합치기(agg)** - 입력과 똑같은 말(`text.lower() == ql`)은 뺀다. `(tier, 말)` 로 묶는다: core · kw = 최소값, lvl = 최소값, attr = 하나라도, tour = (TourAPI 이고 체인 아닌 줄) 하나라도, chain = 하나라도, n = 합. 같은 말(`lower`)이 tier 0 · 1 에 다 있으면 tier 0 만 남긴다.

**⑪ 무게(w)**
- attr 이고 tier 0: 대표성 = 지역 안(tier 0) 후보 **행**들 가운데 `name.lower()` 가 그 줄 `core.lower()` 를 품은 것의 count 합. (그런 행이 없으면 n)
- attr 이고 tier 1: n.
- attr 아니고 tour: `max(n, 어절수)`. 어절수 = core 의 첫 어절 `wc = core.split(" ")[0].lower()` 에 대해 - `wc` 가 `ql` 로 시작하고 `wc != ql` 일 때만 - 지역 안 후보 행 이름을 `lower().split(" ")` 로 나눈 낱말 가운데 `wc` 와 **똑같은** 낱말 수(행 count 를 곱해 합). 조건이 안 맞으면 0.
- 그 밖: n(체인은 지점 줄 수 합).

**⑫ 등급(rl)** - tier 0 · attr 이고 `len(q) >= 3` 이면 1, 아니면 lvl.

**⑬ 순서와 2줄 제한** - 같은 `kw.lower()`(어절 줄 · 체인 줄도 자기 kw 로 같은 칸에 든다) 안에서 `(tier, rl, not attr, -w, len(말), 말)` 순으로 번호를 매겨 3번째부터는 뒤로 민다. 최종 순서 = `(번호 > 2, tier, rl, not attr, -w, len(말), 말)`, 앞 6줄.

**카카오 정책**: 완성 검색어는 우리 공공데이터 이름(체인 줄은 우리 상표 + 우리 지역 이름)이다. 카카오 값은 읽지도 저장하지도 않는다. 누르면 그 말을 사용자가 친 말처럼 카카오 검색어로 보낸다. 검색 결과 쪽에 넘기는 좌표도 우리 공공데이터로 계산한 일정 지역 중심이다.

### 0.4 최종안 실측 결과(받아들임 기준 - 로컬 DB, 2026-10-12)

`*` 는 지역 밖에서 채운 줄. 지역은 '시도/시군' 하나짜리 범위로 잰 값이다(받아들임 스크립트도 같은 범위를 직접 넘긴다).

| # | 검색어 · 지역 | 결과(순서대로) |
|---|---|---|
| 1 | 메타세쿼 · 전남/담양 | 담양 메타세쿼이아길 / 곡성 메타세쿼이아길* / 김제 메타세쿼이아길* / 덕산 메타세쿼이아길* / 두왕 메타세쿼이아길* / 부귀 메타세쿼이아길* |
| 2 | 메타세쿼 · 서울 | 하늘공원 메타세쿼이아 숲길 / 메타세쿼이아길* / 김제 메타세쿼이아길* / 덕산 메타세쿼이아길* / 두왕 메타세쿼이아길* / 부귀 메타세쿼이아길* |
| 3 | 스타 · 서울 | 스타벅스 서울 / 스타필드 코엑스몰 / 스타동 서울 / 스타일 / 스타호프 / 스타하우스 서울 |
| 4 | 스타 · 강원/강릉 | 스타벅스 강릉 / 스타먹소고기무한 강릉 / 스타먹돈고기무한리필강릉내곡점 / 스타빌* / 스타CC* / 스타웨이하동* |
| 5 | 경복 · 서울 | 경복궁 / 경복궁 건청궁 / 경복궁엔타스 서울 / 경복궁삼계탕 서울 / 경복식당 / 경복궁떡집 |
| 6 | 해운 · 부산 | 해운대 / 해운대해수욕장 / 해운대 동백섬 / 해운대문화회관 / 해운대수목원 / 해운대온천센터 |
| 7 | 성산 · 제주 | 성산일출봉 / 성산포성당 / 성산포유람선 / 제주 성산항 / 성산포JC공원 / 성산세화해안도로 |
| 8 | 오동 · 전남/여수 | 오동도 / 오동도 등대 / 오동도-여자만자전거길 / 오동도펜션 / 오동동 / 오동도2 |
| 9 | 카페 · 강원/강릉 | 카페기와 / 카페정화 / 카페카모메 / 카페베네안목점 / 카페뤼미에르 강릉 / 카페뜰 |
| 10 | 한옥 · 전북/전주 | 전북 전주 한옥마을 / 전주한옥레일바이크 / 전주한옥마을역사관 / 전주한옥마을 도서관 / 한옥미담 / 한옥혜윰 |
| 11 | 불국 · 경북/경주 | 경주 불국사 / 불국사밀면 / 불국정떡갈비 / 불국사한옥동오당 / 불국빵 / 불국시 |
| 12 | 남산 · 서울 | 남산서울타워 / 남산공원 / 남산국치길 / 남산인권숲 / 남산 팔각정 / 남산예장공원 |
| 13 | 남산 · 경북/경주 | 경주 남산 / 남산 화강암 / 경주 남산동 동·서 삼층석탑 / 남산옥 / 남산루 / 남산서가 |
| 14 | 호텔 · 부산 | 호텔야자 부산 / 호텔콤마 / 호텔마레 / 호텔오즈 / 호텔쿼츠 / 호텔25시 |
| 15 | 순두부 · 강원/강릉 | 초당순두부마을 / 순두부젤라또 강릉 / 순두부짬뽕초당애 / 강릉순두부장칼국수 / 짬뽕 순두부 초당애 / 토담순두부 |
| 16 | 케이블 · 전남/여수 | 여수 해상케이블카 / 케이블카펜션 / 보니또여수해상케이블카돌산점 / 케이블카* / 사천케이블카 자연휴양림* / 케이블카파크랜드오토캠핑장* |
| 17 | 이디야 · 제주 | 이디야커피 제주 / 이디야삼도점 / 이디야제주삼화점 / 이디야제주외도점 / 이디야제주한림점 / 이디야서귀포 홈플러스점 |
| 18 | 감천 · 부산 | 부산 감천문화마을 / 감천사 / 감천문화마을 어린왕자 전시관 / 감천당 / 감천상회 / 감천집밥 |
| 19 | 메타세쿼 · 지역 없음 | 메타세쿼이아길 / 회덕메타세쿼이아길 / 김제 메타세쿼이아길 / 덕산 메타세쿼이아길 / 두왕 메타세쿼이아길 / 부귀 메타세쿼이아길 |
| 20 | 롯데 · 서울 | 롯데월드 / 롯데월드 어드벤처 / 롯데뮤지엄 / 롯데콘서트홀 / 롯데월드타워 서울스카이 / 롯데월드타워&롯데월드몰 |

받아들임: 파이썬 구현을 로컬 DB 에 돌려 **20개 모두 위 표와 같아야 한다**(로컬 DB 는 동기화로 행이 바뀔 수 있다 - 다르면 같은 범위로 `final.sql` 을 다시 돌려 표를 새로 뽑고, 그 표와 같아야 한다. 경우마다 진행 기록에 남긴다). 규칙 단위 시험(과제 2 Step 1)이 받아들임으로 못 잡는 어긋남을 고정한다.

### 0.5 검색 결과 지역 먼저(카카오)

- 순서: 접근 확인 → 카카오 클라이언트 만들기(꺼짐이면 `[]`, 설정 오류면 503 - **지금처럼 DB 를 더 읽지 않고**) → `get_trip_travel_area_id` → `area_center` → `_release_session` → 카카오.
- `center["latitude"]` · `center["longitude"]` 가 둘 다 있으면: 1차 `search_keyword(query, x=lng, y=lat, radius=20000, size=6)`. **1차가 예외 없이** 6줄 미만이면 2차 `search_keyword(query, x=lng, y=lat, size=6)`(반경 없음) - 1차에 없는 장소(카카오 장소 id 기준)만 뒤에 붙여 6줄까지.
- 1차가 예외면 2차를 부르지 않고 지금처럼 `[]` + 경고 1줄(오류 종류만). 2차가 예외면 1차 결과만(경고 1줄).
- 좌표가 없으면(지역 없음 · 공공데이터 행 없음 - `area_center` 는 값이 `None` 인 dict 를 돌려준다) **좌표 인자를 아예 넘기지 않고** 지금처럼 1번.
- 응답 모양 · 맞춰 보기(`_prematch`) · 그 뒤 처리는 그대로. 로그에 좌표 · 검색어를 남기지 않는다.

### 0.6 화면(장소 추가 시트)

- 짜임: 검색 칸 `label.field` 를 새 `div.place-search-box`(`position: relative`)로 감싸고, 완성 검색어 목록은 label 의 **형제**로 둔다(`MapPointPicker` 의 `.map-point-picker-search` 와 같은 짜임). 목록은 `position: absolute; top: 100%; left: 0; right: 0; z-index: 3`, 불투명 흰 배경 · 그림자, `max-height: 250px; overflow-y: auto`. 결과 칸(220px)과 그 아래 '직접 적기' 입구 위로 잠깐 겹쳐도 된다(목록이 닫히면 그대로 보인다).
- 검색 칸에 `autoComplete="off"`(브라우저 입력 기록 목록이 겹치지 않게).
- 열림 상태 = 감싸개 안에 초점이 있음: 감싸개 `onFocus` 로 열고, `onBlur` 에서 `relatedTarget` 이 감싸개 안이면 열어 두고 밖이면 닫는다. 목록 줄 단추와 목록에 `onMouseDown={e => e.preventDefault()}` - 눌러도 초점이 검색 칸에 남아 blur 가 생기지 않는다(Safari 처럼 단추가 초점을 받지 않는 브라우저도). Tab 으로 줄에 가면 감싸개 안이라 열려 있고, 마지막 줄에서 Tab 으로 나가면 닫힌다.
- 보이는 조건: 추가 모드 · 맞춰 보기 중 아님(`isMatching`) · 열림 · 목록이 있음 · `inputSearchQuery.trim()` 이 2자 이상 · `inputSearchQuery.trim() === suggestionQuery`(그 목록을 받은 질의 - 디바운스 대기 중엔 옛 목록을 숨긴다) · 입력이 목록의 말 하나와 똑같지 않음.
- 줄 = 단추. 받은 질의와 맞는 부분을 굵게(이름 맨 앞이나 공백 뒤의 첫 일치, 없으면 첫 부분 일치, 그것도 없으면 굵게 없음).
- 요청: 시트의 디바운스 콜백(`updateInputSearchQuery` 의 타이머 안)에서 `onSearchChange(query)` 와 함께 `onRequestSuggestions?.(query)`. **줄 누름 경로는 완성 검색어를 요청하지 않는다**(고른 말로 목록이 다시 뜨지 않게).
- 줄을 누르면: `onSearchInput?.()`(맞춰 보기 놓기 · 요청 번호 올리기) → 디바운스 타이머를 지우고 **ref 를 `null` 로** → `setInputSearchQuery(말)` → `onSearchChange(말)` 곧바로 → `onClearSuggestions?.()`(진행 중 요청 끊고 비움) → 초점은 검색 칸에 그대로.
- 닫히는 때: 줄 누름, 검색 칸에서 `Escape`(검색 칸 `onKeyDown`), 감싸개 밖으로 초점, 입력 2자 미만.
- 훅: 요청 번호 + `AbortController`(기존 `placeSearchRequestRef` 관례), 늦은 응답 버림, `clear()` 와 언마운트 때 끊음, 실패하면 목록만 비움(오류 문구 없음), `query` 는 trim 한 값.
- 홈 · 정책 탭 통합 검색은 범위 밖.

### 0.7 범위 밖 · 남는 위험

- 홈 · 정책 탭 통합 검색의 지역 먼저 · 완성 검색어.
- 키보드 위 · 아래 화살표로 줄 옮기기(Tab 으로 옮길 수 있다).
- 인기도 신호가 없어 같은 순위끼리는 짧은 말 순서다(남산골한옥마을 · 남산케이블카는 6줄 밖).
- 이름 패턴으로 거르는 유흥 잡음은 완전하지 않다(근본은 적재 때 상가 소분류 저장).
- core 떼기는 광역시 구 이름도 뗀다(`해운대해수욕장` → `해수욕장`) - 최종안 그대로이고 #6 이 기댄다.
- 분류 잡음(TourAPI sight 의 한복 대여점).
- 카카오 호출: 1차가 6줄 미만이면 검색마다 2번(디바운스 350ms 마다). 1차 실패 때는 2차를 부르지 않는다.
- 앱에 속도 제한 · `statement_timeout` 이 없다 - 완성 검색어는 상한 4000 · 2자 규칙으로 막는다.

---

## Global Constraints

- API DTO 는 camelCase(완성 검색어 응답은 문자열 배열). DB · SQL 은 snake_case.
- 라우트는 얇게: 스키마 `app/schemas`, 동작 `app/services`, 질의 `app/repositories`.
- API 모양이 바뀌면 `docs/mvp-api-contract.md` · `.agent/evals/api-contract-golden.json` · 프론트 타입 · 백엔드 시험을 함께 바꾼다.
- 스키마 변경은 Alembic 만. 모델(`app/models/tables.py`)에도 같은 색인을 선언한다(시험이 메타데이터를 읽는다).
- 검색어 · 완성 검색어 · 좌표를 로그에 남기지 않는다(`QUERY_ALLOWLIST` 에 `query` 없음, `debug_capture` 는 경로에 `place` 가 든 요청을 늘 뺀다 - 새 경로 `place-suggest` 도 해당).
- 로그 시험은 쓰는 로거의 `handlers` 를 `[caplog.handler]` 로 바꾼다(`trips.py` 로거는 `uvicorn.error` · propagate 꺼짐 - 기존 `test_trip_db_service.py:250` 관례). 경고 줄이 실제로 찍혔는지를 함께 단정한다(공허한 시험 금지).
- 카카오 값은 저장 · 로그 · 외부 전송하지 않는다. 카카오에 보내는 것은 사용자가 친 말 · 고른 완성 검색어 · 우리 공공데이터 좌표뿐.
- 장소 검색 · 완성 검색어는 일정 전체 그래프(`_resolve_required_trip`)를 읽지 않는다.
- 모든 파일 UTF-8, 한국어 깨짐 없음. Windows 에서 파이썬으로 파일을 다시 쓰지 않는다(CRLF).
- 비밀값을 출력하지 않는다. 로컬 DB 접속은 `docker exec <db> sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" …'`.
- 진행 기록(Ruling · 실측 숫자)은 `.superpowers/sdd/2026-10-12-place-search-suggestions/progress.md`.

## Review Focus

1. `%` · `_` · `\` 가 든 입력(`50%`) - 맞는 이름만, 부호만(`--`) 입력은 빈 목록이고 DB 를 부르지 않는다.
2. 빠르게 치기 · 늦은 응답 - 앞 질의 응답이 뒤 목록을 덮지 않는다(시험은 디바운스를 넘겨 두 요청이 실제로 나가게 쓴다).
3. 줄을 누른 뒤 - 대기 중이던 예전 검색이 새 검색을 덮지 않고, 고른 말로 완성 검색어를 요청하지 않으며, 목록이 다시 뜨지 않는다.
4. 카카오 2차 호출 - 1차 6줄이면 1번, 1차 예외면 1번, 겹침 제거, 좌표 없으면 좌표 인자 없음.
5. 0.3 의 SQL 조건 - 받아들임 20개가 지나지 않는 길(여러 시군 체인, 시도 NULL, 2줄 제한 칸에 든 어절 줄)을 단위 시험이 고정한다.

---

### Task 1: Alembic 0051 · 모델 색인 · head 시험

**Files:**
- Create: `backend/alembic/versions/0051_public_place_name_trgm.py`
- Modify: `backend/app/models/tables.py`(`PublicPlace.__table_args__`), `backend/tests/test_db_schema.py`, `docs/db-schema-current.md`(0051 문단), `docs/db-schema-current.sql`

- [ ] **Step 1: 실패하는 시험** - `test_db_schema.py`:
  - 기존 `test_alembic_0050_follows_0049_and_is_the_only_head`(head 를 `["0050_geo_reference"]` 로 못 박음)를 0051 이 0050 을 잇고 유일한 head 라는 시험으로 바꾼다(이름도).
  - 모델 메타데이터에 `ix_public_places_name_trgm`(`dialect_options["postgresql"]["using"] == "gin"`, ops `gin_trgm_ops`)이 있다.
  - 0049 렌더 시험과 같은 모양으로 순서까지 단언한다. upgrade: `up.index("CREATE EXTENSION IF NOT EXISTS pg_trgm") < up.index("COMMIT") < up.index("DROP INDEX CONCURRENTLY IF EXISTS ix_public_places_name_trgm") < up.index("CREATE INDEX CONCURRENTLY ix_public_places_name_trgm ON public_places USING gin (name gin_trgm_ops)") < up.index("BEGIN")`. downgrade: `COMMIT < DROP INDEX CONCURRENTLY IF EXISTS ix_public_places_name_trgm < BEGIN`, `DROP EXTENSION` 없음.
- [ ] **Step 2: 실패 확인** - `python -m pytest tests/test_db_schema.py -q` → 새 시험 실패.
- [ ] **Step 3: 모델** - `Index("ix_public_places_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"})`. SQLite `create_all` 은 방언 옵션을 무시한다.
- [ ] **Step 4: 마이그레이션**

```python
"""public_places 이름 trigram 색인 - 장소 검색 완성 검색어(ILIKE '%q%')

Revision ID: 0051_public_place_name_trgm
Revises: 0050_geo_reference
Create Date: 2026-10-12

- pg_trgm 은 신뢰 확장(PG13+) - DB 소유자가 만들 수 있다. AWS RDS 도 지원한다.
- 108만 행에서 약 77MB, 만드는 데 약 7초(2026-10-12 실측). CONCURRENTLY 라 적재 · 동기화 쓰기를 막지 않는다(0049 관례).
"""
from collections.abc import Sequence

from alembic import op


revision: str = "0051_public_place_name_trgm"
down_revision: str | None = "0050_geo_reference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    with op.get_context().autocommit_block():
        # 앞선 시도가 실패해 남긴 INVALID 색인 - 지워야 다시 돌리기가 풀린다
        op.drop_index("ix_public_places_name_trgm", table_name="public_places", postgresql_concurrently=True, if_exists=True)
        op.create_index(
            "ix_public_places_name_trgm", "public_places", ["name"],
            postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}, postgresql_concurrently=True,
        )


def downgrade() -> None:
    # 확장은 남긴다 - 다른 객체가 쓸 수 있다
    with op.get_context().autocommit_block():
        op.drop_index("ix_public_places_name_trgm", table_name="public_places", postgresql_concurrently=True, if_exists=True)
```

- [ ] **Step 5: 확인** - 시험 통과. `alembic upgrade 0050_geo_reference:head --sql` 출력 확인. 로컬 DB `alembic upgrade head`(보호 표 행 수 전후 같음, 색인 크기 기록), `alembic downgrade -1` → `upgrade head` 왕복 한 번.
- [ ] **Step 6: 문서** - `db-schema-current.md` 에 '장소 검색 완성 검색어(0051)' 문단, `.sql` 에 확장 · 색인 줄(0050 처럼 손으로 쓴 요약 모양).

### Task 2: 완성 검색어 후보 질의 · 순위 함수 · 서비스

**Files:**
- Create: `backend/app/services/place_suggest.py`(순위 순수 함수 · 서비스), `backend/tests/test_place_suggest.py`
- Modify: `backend/app/repositories/public_places.py`(`suggest_candidates`), `backend/tests/test_public_places.py`(저장소 시험)

**Interfaces:**
- Produces:
  - `SuggestCandidate`(dataclass, frozen): `name: str, source: str, category: str, sido: str | None, city: str | None, tier: int, count: int`
  - `public_place_repository.suggest_candidates(db, *, query: str, scope: tuple[str, tuple[str, ...] | None] | None, limit: int = SUGGEST_CANDIDATE_LIMIT) -> list[SuggestCandidate]`
  - `place_suggest.rank_suggestions(query: str, candidates: Sequence[SuggestCandidate], *, scope, limit: int = 6) -> list[str]`
  - `place_suggest.suggest_place_names(db, *, query: str, scope) -> list[str]`

- [ ] **Step 1: 실패하는 시험(순위 함수 - 순수, DB 없음)** `test_place_suggest.py`. 0.3 의 번호마다:
  - ② 지역 안이 지역 밖보다 먼저, 지역 밖은 관광지만 채움(후보는 저장소가 거르지만 순위 함수는 tier 를 믿는다).
  - ③ 꼬리표: `경주 불국사 [유네스코 세계유산]` → `경주 불국사`. core: `담양 메타세쿼이아길`(전남, 담양) → `메타세쿼이아길`, `전주한옥마을`(전북, 전주) → `한옥마을`, **`전북 전주 한옥마을`(전북, 전주) → `한옥마을`(되풀이 떼기)**, **`김제 메타세쿼이아길`(sido `None`, city `죽산면`) → 떼지 않음**(지역 밖 · 지역 없음에서 다른 `… 메타세쿼이아길` 과 합쳐지지 않는다).
  - ⑤ 지역 없음: `곡성 메타세쿼이아길` · `담양 메타세쿼이아길` → `메타세쿼이아길` 한 줄.
  - ⑧ 어절 줄: 지역 안 관광지 `오동도 등대` · `오동도 유람선터미널`(q=오동) → `오동도` 줄이 더해지고 **`오동도` 가 `오동도 등대` 보다 위**. `경주 남산` 관광지(core `남산`)가 있으면 q=남산 에서 `남산` 어절 줄 없음(입력과 같은 말이기도 하다). kw 가 q 로 시작하지 않으면(q=케이블, `여수 해상케이블카` · `통영 해상케이블카` → kw `해상케이블카`) 어절 줄 없음.
  - ⑨ 체인: 지역 안 상가 `스타벅스 강남역점` · `스타벅스 홍대점`, 범위 (서울, None) → `스타벅스 서울`. 범위 (강원, (강릉, 동해, 삼척)), `스타벅스 강릉점`(강릉) · `스타벅스 교동점`(강릉) · `스타벅스 동해점`(동해) · `스타벅스 천곡점`(동해) → `스타벅스 강릉` · `스타벅스 동해` 두 줄. 지역 없음 → `스타벅스`. 1곳뿐이면 묶지 않음. 상표가 관광지 core(`경복궁`)와 같으면 묶지 않음. 붙여 쓴 상표: `롯데리아용인`(1줄) · `롯데리아 강남점` · `롯데리아 홍대점` → `롯데리아 서울` 한 줄에 셋 다.
  - ⑪ 무게: q=스타, TourAPI 비관광지(shopping) `스타필드 코엑스몰` 1행 + 지역 안 행 이름에 `스타필드` 낱말이 3번 → 무게 3 으로 `스타일` (상가 2행)보다 위. q=호텔, TourAPI 비관광지 `호텔 농심` 은 첫 어절이 q 와 같아 무게 = 행 수(1).
  - ⑫ 등급: q=케이블(3자), 지역 안 관광지 `여수 해상케이블카` 가 상가 `케이블카펜션` 보다 위. q=한옥(2자), 지역 안 관광지 `남원 광한루 한옥` 은 등급 2.
  - ⑬ 2줄 제한: q=롯데, 관광지 `롯데월드 A`(2행) · `롯데월드 B` · `롯데월드 C` · `롯데월드 D` + 관광지 `롯데뮤지엄` → 정확히 `[롯데월드, 롯데월드 A, 롯데뮤지엄, 롯데월드 B, 롯데월드 C, 롯데월드 D]`(어절 줄 `롯데월드` 도 그 칸의 한 줄). 동률이면 코드 포인트 순(`남산 팔각정` < `남산예장공원`).
  - ⑩ 입력과 똑같은 줄 빠짐, 최대 6줄, 같은 말 한 줄(tier 0 우선).
- [ ] **Step 2: 실패 확인**
- [ ] **Step 3: 순위 함수 구현** - 0.3 ③~⑬ 을 그대로 옮긴다. 정규식은 모듈 상수. 대표성 · 어절수는 후보 목록 안에서 센다.
- [ ] **Step 4: 실패하는 시험(저장소 - SQLite 픽스처 `db` · `seed` · `place_row`)** `test_public_places.py`:
  - 지역 안: sido/city 범위, 상가 `leisure` 와 유흥 이름 패턴 제외, TourAPI 는 `leisure` 도 남음, tier 0.
  - 지역 밖: TourAPI `sight` · `culture` · `leisure` 만, tier 1.
  - 지역 없음(`scope=None`): 전국 TourAPI 만, tier 0.
  - 이스케이프: `50%` 는 `50%할인` 만(`500원` 아님), `a_` 는 `a_b` 만(`ab` 아님), `\` 도.
  - 2자: 상가 `블라스타` 는 `스타` 에 안 맞고, 지역 안 TourAPI `전주한옥마을` 은 `한옥` 에 맞는다.
  - 같은 (tier, 이름, 출처, 분류, 시도, 시군)은 한 행으로 묶여 `count` 를 갖는다.
  - 대소문자 무시(`cu` → `CU 강남점`). 붙여 친 말(`담양메타`)은 `담양 메타세쿼이아길` 에 안 맞는다.
  - `limit` 을 넘으면 tier → 길이 → 이름 순으로 잘린다.
- [ ] **Step 5: 저장소 구현** - 갈래 select 들(지역 있음: tier 0 · tier 1, 지역 없음: tier 0 하나)을 `union_all(...).subquery()` 로 묶고, **바깥 select 한 곳에서** `GROUP BY tier, name, source, category, sido, city` · `count()` · `ORDER BY tier, length(name), name` · `LIMIT` 을 건다(갈래마다 ORDER BY · LIMIT 을 달지 않는다 - SQLite 가 거부한다. `tier` 를 GROUP BY 에서 빼면 PostgreSQL 이 거부한다). 범위 조건은 `_in_area` 를 쓴다. 이스케이프 `ilike(..., escape="\\")`. 유흥 패턴은 `or_(*(PublicPlace.name.contains(w, autoescape=True) for w in _NIGHTLIFE))` 의 부정. 2자 규칙은 0.3 ② 그대로. 상한에 걸리면(받은 행 수 == limit) 경고 `place_suggest_candidates_capped count=<n>`.
- [ ] **Step 6: 실패하는 시험(서비스)** `test_place_suggest.py`:
  - `--` · `a` · `  ` 는 `[]` 이고 저장소를 부르지 않는다(spy).
  - 저장소가 표식 글자(`비밀검색어`)가 든 `OperationalError` 를 던지면 `[]`, 경고 줄 `place_suggest_failed error=OperationalError` 가 **찍혔고** 표식은 없다.
  - 상한 경고에도 검색어가 없다(경고가 찍혔는지 함께 단정).
- [ ] **Step 7: 서비스 구현** - `suggest_place_names`: 0.3 ① → 저장소 → 순위 함수. `SQLAlchemyError` → `[]` + 경고(오류 종류만).
- [ ] **Step 8: 실데이터 받아들임(로컬 DB, 수동 - 저장소 밖 스크래치 스크립트)** - 0.4 의 20개를 같은 범위로 서비스에 돌려 표와 **20개 모두 같은지** 비교(다르면 0.4 의 절차). 시간: 후보 질의 + 순위를 경우마다 5번 재 p95 를 2자 · 3자 이상으로 나눠 기록하고, 최악 입력 `카페`@경기 전체 · `김밥`@서울 · `치킨`@경기 · `가 나`@서울 도 잰다(상한에 걸리는지 기록). 목표 3자 이상 50ms · 2자 80ms - 넘으면 Ruling(상한을 줄이거나 2자는 지역 안만).
- [ ] **Step 9: 시험 통과**

### Task 3: 일정 지역 조회 · 완성 검색어 API

**Files:**
- Modify: `backend/app/repositories/trips.py`(`get_trip_travel_area_id`), `backend/app/services/trips.py`(`suggest_places_for_trip`, 지역 범위 도우미), `backend/app/api/routes/trips.py`(`GET /{trip_id}/place-suggest`)
- Test: `backend/tests/test_trip_db_service.py`(서비스), `backend/tests/test_trip_db_routes.py`(라우트 - 기존 `place-search` 라우트 시험 자리 · 같은 픽스처), `backend/tests/test_public_places.py`(저장소 함수 - SQLite)

**Interfaces:**
- Produces: `trip_repository.get_trip_travel_area_id(db, trip_id: int) -> str | None`(`select(Trip.travel_area_id).where(Trip.id == trip_id)` - 접근 확인은 호출 전에 `has_trip_access` 로), `trips._trip_area(db, trip_id: int) -> TravelArea | None`(= `get_travel_area(get_trip_travel_area_id(...))`), `GET /api/trips/{trip_id}/place-suggest?query=` → `list[str]`

- [ ] **Step 1: 실패하는 시험** - 저장소: 지역 있는 일정 → id, 없는 일정 → `None`. 서비스: 접근 없음 · 숫자 아닌 id → 404(`place-search` 와 같은 `TripServiceError`), 지역 있는 일정이면 `suggest_place_names` 가 `area_scope(area)` 로, 지역 없는 일정이면 `scope=None` 으로 불린다(가짜), `_resolve_required_trip` 을 부르면 실패(기존 `reject_graph_load` 관례). 라우트: 비로그인 401, `query` 81자 422, 빈 `query` 422(`place-search` 와 같은 `min_length=1`), 로그인 200 · `list[str]`.
- [ ] **Step 2: 구현** - 서비스는 `has_trip_access` 로 확인한 뒤 `_trip_area` → `area_scope` → `suggest_place_names`(세션은 놓지 않는다 - DB 가 필요하다). 라우트는 `place-search` 와 같은 모양.
- [ ] **Step 3: 시험 통과**

### Task 4: 카카오 검색 결과 지역 먼저

**Files:**
- Modify: `backend/app/services/kakao_local.py`(`search_keyword` 에 `x` · `y` · `radius` 선택 인자 - 프로토콜과 구현 둘 다), `backend/app/services/trips.py`(`search_places_for_trip`)
- Test: `backend/tests/test_kakao_local.py`, `backend/tests/test_trip_db_service.py`
- **기존 시험 손질**: 장소 검색 시험 가운데 카카오 클라이언트가 만들어지는(꺼짐 · 503 이 아닌) 시험은 이제 `get_trip_travel_area_id` 를 부른다 - db 자리에 `object()` · `SpyDb` · `SavepointDb` 를 넘기므로 `monkeypatch.setattr(trip_repository, "get_trip_travel_area_id", lambda *a: None)` 를 더한다(지역 없음 → 지금처럼 1번). 대상: `test_trip_db_service.py` 의 장소 검색 시험(검토 시점 줄 116 · 179 · 201 · 218 · 236 · 263 · 280 · 287 · 3796 부근), `test_trip_db_routes.py` 의 503 · 장소 검색 라우트 시험(1101 부근), `test_public_places.py` 의 장소 검색 시험(522 · 543 부근). 구현 뒤 `grep -n "search_places_for_trip\|place-search" backend/tests` 로 빠진 곳이 없는지 확인한다. 기존 가짜 제공자의 `search_keyword(self, *, query, size=10)` 는 좌표가 없으면 그대로 맞는다(좌표 인자를 안 넘기므로).

- [ ] **Step 1: 실패하는 시험(클라이언트)** - `search_keyword(query=…, x=127.0, y=37.5, radius=20000)` 가 요청 파라미터에 `x` · `y` · `radius` 를 넣는다. 좌표 없이 부르면 파라미터에 없다(지금과 같다). `radius` 만 주거나 `x` 만 주면 `ValueError`.
- [ ] **Step 2: 클라이언트 구현** - 선택 인자 `x: float | None = None, y: float | None = None, radius: int | None = None`.
- [ ] **Step 3: 실패하는 시험(서비스)** - 가짜 제공자(좌표 인자를 받는 새 가짜)와 `get_trip_travel_area_id` · `area_center` 가짜로:
  - 지역 있는 일정: 1차 호출이 `x=lng` · `y=lat` · `radius=20000` · `size=6`. 1차 6줄이면 호출 1번.
  - 1차 4줄이면 2차가 `x` · `y`(반경 없음)로 불리고, 2차의 1차와 같은 id 는 빠지고 6줄까지. 순서는 1차 먼저.
  - 1차 예외 → 호출 1번, `[]`, 경고 1줄(오류 종류만, 검색어 · 좌표 없음 - 경고가 찍혔는지도 단정). 2차 예외 → 1차 4줄 + 경고 1줄.
  - `area_center` 가 **값이 `None` 인 dict** 를 주면 좌표 인자 없이 1번, 경고 없음.
  - 지역 없는 일정(`get_trip_travel_area_id` → `None`)이면 좌표 인자 없이 1번.
  - 카카오가 꺼져 있으면(`build_kakao_local_client` → `None`) `get_trip_travel_area_id` 를 부르지 않는다. 설정 오류(503)도 마찬가지.
  - `area_center` 는 `_release_session` 앞에서 한 번만.
- [ ] **Step 4: 서비스 구현** - 0.5 순서 그대로. 작은 도우미 `_search_near(provider, query, center) -> list[KakaoLocalPlace]`(예외는 1차만 밖으로 올린다 - 바깥의 기존 `except` 가 `[]` + 경고). `_prematch` 이하는 그대로.
- [ ] **Step 5: 시험 통과 · 실호출 확인(수동)** - 0.2 표의 5개를 로컬 API 로 불러 지역 안 줄 수가 '반경 20km' 쪽과 같은지(개수만, 응답을 파일로 남기지 않는다).

### Task 5: 계약 · 프론트 API 경계

**Files:**
- Modify: `docs/mvp-api-contract.md`(`GET /trips/{trip_id}/place-suggest` 절 - `place-search` 절 바로 뒤. `POST /places/match` 와 `GET /trips/{trip_id}/recommendations` 사이에는 두지 않는다 - 기존 문서 시험의 `section()` 이 그 구간을 잘라 쓴다. `place-search` 절에 지역 먼저 동작 한 단락), `.agent/evals/api-contract-golden.json`, `backend/tests/test_places_contract_docs.py`(새 경로가 golden · 계약 · 앱에 있다 - 기존 `test_the_new_routes_are_in_the_golden_the_contract_and_the_app` 모양), `docs/implemented-feature-spec.md`(엔드포인트 칸), `frontend/src/api/dataApi.ts` · `backendApi.ts` · `backendApi.test.ts`

- [ ] **Step 1: 실패하는 시험** - `backendApi.test.ts`: `suggestTripPlaceNames("479", "메타세쿼", { signal })` 가 `GET /api/trips/479/place-suggest?query=%EB%A9%94…` 를 부르고 `string[]` 을 돌려준다. 계약 문서 시험이 새 경로를 요구한다.
- [ ] **Step 2: 구현** - `AppDataApi.suggestTripPlaceNames: (tripId: string, query: string, control?: ApiRequestControl) => Promise<string[]>`. backendApi 는 `searchTripPlaces` 와 같은 모양.
- [ ] **Step 3: 계약 문서 · golden** - 로그인 · 404 · 2자 · `\w` · 80자 422 · 최대 6 · 지역 먼저 · 체인 줄은 '상표 + 지역 이름'(시군마다) · 이름만 내는 이유 · 로그에 남기지 않음 · DB 오류 시 빈 목록. golden 은 `query` · `dbModeBehavior` · 응답 종류 키. `place-search` 절: 일정 지역 반경 20km 먼저, 1차가 6줄 미만이면 지역 쪽으로 기운 전국으로 채움, 1차 실패 시 빈 목록 - 응답 모양 같음.
- [ ] **Step 4: 시험 통과**

### Task 6: 시트 완성 검색어 목록

**Files:**
- Create: `frontend/src/components/itinerary/placeAdd/usePlaceSuggestions.ts` · `.test.ts`, `frontend/src/components/itinerary/placeAdd/PlaceSuggestions.tsx` · `.test.tsx`
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`, `frontend/src/styles/app.css`, `frontend/src/app/__tests__/trip-place-basket.test.tsx`, 시트를 열고 장소 검색 칸에 2자 이상 치는 다른 시험(`home.test.tsx` · `trip-detail.test.tsx` 등 - 구현 뒤 `grep -rn "장소 검색" frontend/src/app/__tests__` 로 확인)의 공용 준비, `frontend/e2e-backend/backend-mode.spec.ts`(완성 검색어에 기대지 않는지 확인)

**Interfaces:**
- `usePlaceSuggestions(tripId: string | undefined) -> { suggestions: string[]; query: string; request(query: string): void; clear(): void }` - `query` 는 그 목록을 받은 trim 질의. 요청 번호 + `AbortController`, 늦은 응답 버림, `clear` 는 진행 중 요청을 끊고 비운다, 언마운트 때 끊는다, 2자 미만은 요청하지 않고 비운다.
- 시트 새 선택 props: `suggestions?: string[]`, `suggestionQuery?: string`, `onRequestSuggestions?: (query: string) => void`, `onClearSuggestions?: () => void`. 페이지가 훅의 값 · 함수를 넘긴다. 시트 단독 렌더 시험(`trip-detail.test.tsx`)은 넘기지 않아도 돈다.
- `PlaceSuggestions({ query, suggestions, onPick })` - `<ul aria-label="완성 검색어">` 안의 단추들, 굵게 규칙은 0.6, 단추 · 목록에 `onMouseDown` preventDefault.

- [ ] **Step 1: 실패하는 시험(훅)** - `request("메타")` 응답을 늦게 풀고 그 사이 `request("메타세쿼")` 가 먼저 풀리면 `suggestions` 는 `메타세쿼` 것. `clear()` 뒤 도착한 응답 무시. 실패하면 `[]`. 2자 미만은 요청하지 않는다. `request(" 메타세쿼 ")` 의 `query` 는 `메타세쿼`.
- [ ] **Step 2: 훅 구현**
- [ ] **Step 3: 실패하는 시험(부품)** - 굵게: `query="스타"`, `["아스타 스타벅스", "스타벅스 서울"]` → 첫 줄은 두 번째 어절의 `스타` 가 굵음, 둘째 줄은 맨 앞. 누르면 `onPick`. `fireEvent.mouseDown(줄)` 의 반환값이 `false`(기본 동작 막힘). 빈 배열이면 아무것도 안 그린다.
- [ ] **Step 4: 부품 구현 · CSS · 짜임** - 0.6 짜임(`.place-search-box` 감싸개, 목록은 label 형제, z-index 3, 불투명 배경, max-height 250px), 검색 칸 `autoComplete="off"`, 줄 높이 40px 이상 · 글자 14px · 굵게는 강조색 · `text-overflow: ellipsis`.
- [ ] **Step 5: 실패하는 시험(시트)** `trip-place-basket.test.tsx`(공용 준비 `openAddSheet` 등에서 `suggestTripPlaceNames` 를 기본 `[]` 로 스파이 - 진짜 백엔드 · 로컬 DB 에 요청이 나가지 않게):
  - (진짜 타이머 · `user.click`) `메타세쿼` 를 치고 디바운스를 넘기면 목록이 뜬다. 줄을 누르면 검색 칸 값이 그 말, `searchTripPlaces` 의 마지막 호출이 그 말(`toHaveBeenLastCalledWith`), 목록 닫힘, 검색 칸 `toHaveFocus`. 350ms 를 더 넘겨도 `suggestTripPlaceNames` 가 고른 말로 불리지 않는다.
  - (가짜 타이머 - `trip-detail.test.tsx` 의 관례: 시트를 연 뒤 `vi.useFakeTimers`, `fireEvent`, `advanceTimersByTimeAsync`) `메타` 입력 → 디바운스 넘김(요청 나감) → `메타세쿼` 입력 → 디바운스 넘김 → `메타세쿼` 응답 먼저, `메타` 응답 나중 → 목록은 `메타세쿼` 것.
  - (가짜 타이머) 대기 중이던 예전 검색: `메타세쿼` 입력 → 목록 뜸 → `메타세쿼이` → 350ms 안에 다시 `메타세쿼` → 줄 누름 → 350ms 넘김 → `searchTripPlaces` 의 마지막 호출이 고른 말이고 그 뒤 `메타세쿼` 로 다시 불리지 않았다. 이어서 검색 결과를 하나 고르면 검색 칸이 빈다(타이머 ref 를 `null` 로 돌렸는지).
  - Tab 으로 첫 줄에 가도 목록이 남고, 마지막 줄에서 Tab 으로 나가면 닫힌다. 검색 칸에서 `Escape` 로 닫힌다.
  - 완성 검색어 실패 → 장소 검색 결과는 보이고 오류 문구 없음.
  - 맞춰 보기 중(나만의 장소 칸) · 입력 2자 미만 · 디바운스 대기 중에는 목록이 없다.
  - 끝에 공백이 있는 입력(`메타세쿼 `)에도 목록이 뜬다.
- [ ] **Step 6: 시트 연결 구현** - 0.6 의 요청 · 줄 누름 · 닫힘 순서 그대로.
- [ ] **Step 7: 기존 시험 보호** - 위 grep 으로 찾은 시험들의 공용 준비에 기본 스파이. e2e 는 완성 검색어 결과에 기대지 않는지 확인(기대면 그 단정을 고친다).
- [ ] **Step 8: 시험 통과**

### Task 7: 마무리

- [ ] 전체 시험: backend `python -m pytest`(Windows 권한 시험 1개 제외), `npx vitest run`, `npm run typecheck`, `npm run test:mojibake`, `vite build`, 4173 다시 빌드 · 백엔드 다시 빌드 · 로컬 DB `alembic upgrade head` 뒤 `npm run test:e2e:containers`, `git diff --check`, U+FFFD 0건.
- [ ] 실측: 0.4 의 20개 완성 검색어 API 왕복 p95, 0.2 의 5개 장소 검색 지역 안 줄 수.
- [ ] 브랜치 자체 검토(관점별 + 반박 검증) → 고침.
- [ ] `CHECKLIST.md`: 0051(`pg_trgm` · GIN 77MB) · 운영 승격 게이트는 0050 과 같이 물려받음 · 카카오 호출이 검색마다 최대 2번.
- [ ] 사용자 브라우저 확인 목록: 담양 일정 `메타세쿼`, 서울 일정 `스타` · `남산`, 강릉 일정 `순두부`, 부산 일정 `해운`, 지역 없는 일정, 360px 폭, 휴대폰 키보드가 올라온 상태에서 목록이 보이는지.
- [ ] 커밋(사용자 승인 뒤 - 이번 승인 범위에 포함).
