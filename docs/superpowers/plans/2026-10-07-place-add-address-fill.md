# 장소 담기 3단계 추가 계획 - 주소 채움(방식1 · 시안 v64) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 카카오로 찾은 장소가 우리 공공데이터 장소 목록에 없을 때, 그 자리의 **건물 · 땅 지번(국토교통부 공공데이터)** 으로 주소와 위치를 채우고 이름은 **사용자가 친 검색어**로 채워, 사용자는 [담기]만 누르게 한다. 지도에서 찍은 자리도 그 자리의 건물 · 땅 **ID 로만** 담는다(찍은 좌표는 저장하지 않는다). 직접 적기는 최후의 방법으로 남긴다.

**Architecture:** 서버 PostgreSQL 에 PostGIS 를 켜고 `geo` 스키마에 건물(GIS건물통합정보) · 땅(연속지적도, 농지 · 임야 제외) 도형을 둔다. 장소 검색의 미리 맞춤(v62)이 같은 DB 질의 묶음에서 6곳을 한꺼번에 '건물 → 없으면 땅(땅 중심 30m 안)'으로 찾아 응답에 `fill` 로 싣는다. 저장은 지번 참조 `geoRef{kind, id, pin}` 만 받고 주소 · 좌표는 서버가 자기 표에서 채운다 - `customPlace` 는 더 이상 위도 · 경도를 받지 않는다. 위치 찍기 지도에는 '지도에서 찾기'가 붙고, 찍은 자리는 `POST /api/places/locate` 로 실시간 비교한 뒤 버린다. 표는 월 1회 적재 도구가 manifest 검사를 거쳐 새 표에 넣고 바꿔치기한다.

**Tech Stack:** FastAPI · SQLAlchemy 2.0.54 · Alembic · PostgreSQL 16 + PostGIS 3.5(`postgis/postgis:16-3.5-alpine`) · psycopg 3 · httpx 0.28 · 적재 도구만 pyogrio · shapely · pyproj · React · TypeScript · Vite · Vitest · Playwright.

**Spec:**
- 설계 문서 `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`(이 계획 과제 13 이 2절 · 3절을 고친다)
- 3단계 계획 `docs/superpowers/plans/2026-10-05-place-add-flow-stage3.md`(이 계획은 그 위에 얹는다 - 같은 브랜치 `feature/place-add-flow`, 커밋하지 않은 상태에서 이어 간다)
- 시안 v64(아티팩트, 2026-10-08) - 결과 줄 갈래 · 나만의 장소 칸 · 지도에서 찾기 · 넓은 땅 주소만 · 지번 없음 이름만
- 이 문서의 '0. 설계 요약'(사용자 결정 · 실측 · 정책 근거) · '0.6 코덱스 검토 1차 반영'

---

## 0. 설계 요약

### 0.1 사용자 결정(2026-10-06 ~ 10-08)

| 결정 | 내용 |
|---|---|
| 방식1 | 맞는 공공 장소가 없으면 건물 · 땅 지번으로 주소와 핀을 채우고 이름은 사용자가 친 검색어. 카카오 이름 · 주소로 채우지 않는다 |
| 기준 | 자동 처리 비율이 80% 이하면 쓸 수 없다 |
| 갈래 순서 | 바로 담기 → 비슷한 곳 → **주소 채움** → **위치 찍기** → 직접 적기(최후). 직접 적기도 이름은 검색어로 미리, 이름만으로도 담긴다 |
| 지도에서 찾기 | 위치 찍기 지도 안에서 장소 이름 · 주소로 지도를 옮기고 찍을 수 있어야 한다 |
| 땅 거리 기준 | 땅 중심이 고른 자리에서 **30m** 안일 때만 핀까지 채운다 |
| 땅 거르기 | 농지 · 임야(지목 전 · 답 · 과 · 목 · 임)는 적재하지 않는다 |
| 저장 구조 | DB 안 별도 영역(PostGIS, `geo` 스키마). 백업 · 로컬 복사에서 빼고, 월 1회 새 표 → 바꿔치기 |
| 배지 문구 | '주소 채움' · '위치 찍기' |
| **찍은 좌표(10/8)** | 지도에서 찍은 좌표는 **어떤 경우에도 저장하지 않는다**(데브톡 151842). 찍은 자리는 그 자리의 건물 · 땅 ID 로만 담는다 |
| **넓은 땅(10/8)** | 찍은 자리가 땅 안이지만 땅 중심이 30m 밖이면 **주소만 담고 핀은 없음** |
| 지번 없음 | 찍은 자리에 건물 · 땅이 없으면(바다 · 공유수면) **이름만** |
| 커밋 | 이 브랜치는 커밋 없이 이어 간다(테스트 · 사용자 승인 뒤 한꺼번에) |
| 배포 | 운영은 AWS 예정. 온프레미스(개발서버)는 로컬 PC 라 디스크는 넉넉하고 DB 공간은 늘려 쓴다 |

### 0.2 실측(로컬, 여행 검색어 42개 · 카카오 실시간 결과 248줄)

| 갈래 | 줄 | 비율 |
|---|---|---|
| 바로 담기 | 60 | 24% |
| 비슷한 곳 | 84 | 34% |
| 주소 채움 - 건물 | 43 | 17% |
| 주소 채움 - 땅(30m) | 33 | 13% |
| **자동 합계** | **220** | **89%**(검색 첫 줄 98%) |
| 위치 찍기 | 28 | 11% |

- 위치 찍기 28줄을 그 자리에서 그대로 찍으면: 넓은 땅 26줄은 주소만(핀 없음), 지번 없음 2줄은 이름만.
- 농지 · 임야를 빼고 적재하면 자동 217/248(88%), 첫 줄 98% 그대로. 땅 표 크기는 49% 로.
- 건물 중심은 실제 자리에서 10m 안 77% · 30m 안 91% · 50m 안 98%.
- 전국 크기: 건물 1,439만 개(경기 3개 파일 고유 ID 227만, 파일끼리 겹침 수십 건 - 포털 소개의 666만은 옛 숫자), 땅 3,987만 필지(도형 11.6GB). 줄당 크기(색인 포함) 건물 270B · 땅 356B. 추산: **농지 · 임야 빼면 약 11~12GB(색인 약 1.5GB)**.
- 질의 속도(PostGIS 16-3.5, 부산 건물 47만 · 땅 71만, 6곳 묶음 질의 1번): 메모리에 있을 때 중앙 2.0ms · p95 2.6ms. 캐시를 비우고 메모리 192MB 로 묶으면 중앙 34~65ms · p95 70~280ms. DB 재시작 뒤 첫 질의 1.2~2.4s.
- 카카오 연결 재사용: 연결 시간 28ms → 7ms(지금은 검색마다 새로 연결).
- 채운 지번의 정확도(10/8, 같은 검색어 42개 다시 - 카카오 결과의 지번 주소와 메모리에서만 견주고 버림): `match` 가 아닌 190줄(비슷한 곳 줄 포함) 중 채움이 붙은 142줄 - 건물 91 · 땅 51.
  법정동 · 본번 일치 **135줄(95%)**, 부번까지 일치 129줄(91%), 법정동만 같음 7줄(건물 1 · 땅 6), **법정동부터 다름 0줄**. 나머지 48줄은 채움 없음 42 · 농지 · 임야라 적재 안 함 6.
- 적재 품질(10/8, 전국 속성만 읽음 - 값은 출력하지 않음): 건물 14,392,125줄 - 고유번호 잘못 0 · 식별자 빈 줄 1 · 같은 식별자 0.60% · 식별자 길이 최대 28자.
  땅 39,874,703줄 - 고유번호 잘못 0 · 같은 고유번호 0 · 농지 · 임야 20,467,836줄 빼고 19,406,867줄 · 지목 못 읽음 4,526줄(0.023%) · 지목이 정식 이름인 줄 약 2,300(그중 임야 · 과수원 · 목장용지 등 농지 · 임야 약 180 - `JIMOK_NAMES` 로 부호로 바꿔 거른다) · 지목 낱말 최대 4자.

### 0.3 정책 근거(카카오 데브톡 운영자 답변, 원문 다시 확인함)

- **151842(2026-09-27 답)** - 질문 1 "사용자가 지도를 움직여 직접 지정한 지점의 좌표를 저장해도 되는지" → "**지정 좌표의 DB 저장 및 활용은 불가합니다.**" 질문 3 "검색 결과를 저장하지 않고 지도 이동에만 쓰는 것" → "이슈 없습니다." 질문 4 "검색 결과를 고른 뒤 핀을 움직이지 않고 그대로 저장" → "로컬API 의 호출 결과값을 저장하는 구조라면 허용되지 않습니다."
- 151916-4 지도에서 고른 자리 → 좌표는 버리고 가장 가까운 우리 장소 ID 저장은 가능 → 찍은 자리는 건물 · 땅 참조(`geoRef`)로만 담는다.
- 151505-1 "DB저장 없이 실시간 비교 후 즉시 폐기하는 구조라면 허용" → 카카오 좌표 · 찍은 좌표로 건물 · 땅을 찾고 버린다.
- 151505-3 · 5 장소 ID · URL 영구 저장 허용 → `kakaoPlaceId` 와 '카카오맵에서 보기'만 남긴다.
- 151505-4c "사용자가 직접 입력한 텍스트라면 저장 사용 가능" → 이름은 사용자가 친 검색어(고칠 수 있음).
- 151505 추가 질문: 검색 결과 이름을 참고 표시 · placeholder 로 쓰는 것은 우회 → 카카오 이름은 이름 칸 어디에도 나오지 않는다.
- 151916-5 공공데이터 좌표로 카카오 지도에 마커 - 이슈 없음.
- 건물 · 땅 데이터 이용 조건: GIS건물통합정보 공공누리 1유형(출처 표시) · 연속지적도형정보 CC BY. 화면에 '국토교통부 공공데이터' 출처를 표시한다.
- 브이월드 API 는 쓰지 않는다(카카오 좌표 외부 전송 · 약관 19조 저장 사전승낙 · 건물 레이어에 지번 없음).

### 0.4 흐름

```
입력 → 350ms 기다림 → GET /api/trips/{id}/place-search (요청 1번)
  ① 카카오 키워드 검색 6곳                      연결 재사용(과제 7)
  ② DB: 공공 장소 맞추기(TourAPI · 상가, v62)
  ③ DB: 6곳 중 match 가 아닌 줄을 한꺼번에 건물 → 땅(30m) 찾기 → publicMatch.fill(SAVEPOINT 안, 실패하면 null)   (과제 3 · 4)
  ④ 응답 후 카카오 좌표는 버린다(저장 · 로그 없음)
화면: 줄 표시 바로 담기 · 비슷한 곳 N · 주소 채움 · 위치 찍기 → 누르면 추가 요청 없이 그 칸이 열림
  주소 채움: 이름 = 친 검색어, 주소 · 핀 = fill(공공데이터) → [담기] → customPlace { name, geoRef{kind, id, pin: true} }
  위치 찍기: 지도가 그 결과 자리에서 열림(보여 주기만 - 151842-3) → '지도에서 찾기'로 옮길 수 있음 → '이 위치로'
            → POST /api/places/locate(찍은 자리 - 비교에만 쓰고 버림) → 규칙 0.5 → customPlace { name, geoRef? }
  직접 적기(최후): 이름 = 검색 칸 글, 위치는 선택(같은 지도 · 같은 규칙)
저장: 서버가 geoRef 로 geo 표를 읽어 주소 · (pin 이면) 좌표를 채운다. customPlace 에 위도 · 경도를 보내면 422
```

### 0.5 찍은 자리를 담는 규칙(위치 찍기 · 위치 고치기 · 직접 적기의 지도)

찍은 자리 P 는 `POST /api/places/locate` 비교에만 쓰고 저장 · 로그하지 않는다. 화면도 P 를 바구니 · 저장 요청 · 브라우저 저장소에 두지 않는다.

| 경우 | 담는 주소 | 담는 좌표 | 화면 |
|---|---|---|---|
| P 가 건물 안, 또는 땅 안이고 땅 중심이 P 에서 30m 안(`nearCenter`) | 그 지번 | 그 건물 · 땅의 중심(공공데이터) | 주소 · 위치 + 작은 지도 |
| P 가 땅 안이지만 땅 중심이 30m 밖 | 그 지번 | 없음 | '이 땅은 넓어서 핀 없이 주소만 담겨요' |
| P 를 품은 건물 · 땅이 없음 | 없음 | 없음 | '이 자리는 지번이 없어 위치 없이 이름만 담겨요' |
| 지번을 묻지 못함(네트워크 · 서버) | - | - | 지도에 남아 '지번을 확인하지 못했어요. 다시 찍거나 취소하고 이름만 담아 주세요.' |

서버는 `geoRef.pin` 이 true 일 때만 좌표를 저장한다(좌표는 늘 우리 표의 중심이다 - 화면이 pin 을 잘못 보내도 카카오 · 찍은 좌표가 저장되는 길은 없다).

### 0.6 코덱스 검토 1차(2026-10-08) 반영

| 지적 | 반영 |
|---|---|
| HIGH 10m 이동 좌표 저장은 151842 위반 | 0.5 로 바꿈. 찍은 좌표는 저장하지 않는다. 3단계의 `customPlace.latitude/longitude` 도 없앤다(과제 6 · 9 ~ 12) |
| HIGH 서버가 원시 좌표를 받음 | `CustomPlaceInput` 은 `name` · `geoRef` 만(위도 · 경도 422) - 과제 6 |
| HIGH geo 표에 안정 키 없음 · 중복 파일 | 표마다 `id bigint identity PK` + `feature_key`(건물 A1 · 땅 PNU). `geoRef` 는 `id`(한 판 안에서 고유 - 판이 바뀌면 404). manifest 가 같은 파일 두 번 · 중복률을 막는다 - 과제 1 · 2 · 8 |
| HIGH 첫 적재에 80% 검사가 안 걸림 | manifest: 기대 시도 코드 집합 · 데이터셋마다 기준일 하나 · 시도마다 파일 이름 겹침 없음 · 행 수 범위 · 중복률 - 하나라도 어긋나면 바꾸지 않는다 - 과제 2 · 8 |
| HIGH CRS 를 확인하지 않음 | 파일마다 `pyproj.CRS` 를 읽어 5186 이면 그대로, 5174 면 5186 으로 변환, 그 밖은 멈춤. 작은 SHP 를 실제 PostGIS 에 넣어 좌표를 보는 통합 시험 - 과제 8 |
| HIGH 저장 경로 예외 격리 없음 | `get_by_ref` 를 SAVEPOINT 안에서. DB 오류는 503 `Address lookup is unavailable`(revision 그대로) - 과제 6 |
| MEDIUM 카카오 오류가 URL · 검색어를 로그에 남길 수 있음 | `str(exc)` · `exc_info=True` 를 빼고 예외 이름만 - 과제 7 |
| MEDIUM ST_Contains 는 경계 위 점을 놓침 | `ST_Covers` - 과제 3 |
| MEDIUM 적재 잠금 · 트랜잭션 | advisory lock(동시 적재 막기) · 표마다 커밋 · 바꿔치기만 짧은 트랜잭션 + `lock_timeout` · 실패하면 원래 표 그대로 - 과제 8 |
| MEDIUM AWS 저장 계산에 WAL · 임시 공간 없음 | 과제 14 에서 적재 중 최대 디스크 · WAL 을 재고, 그 1.5 배를 배포 게이트로 - 과제 14 · 15 |
| MEDIUM RDS 의 CREATE EXTENSION 권한 | 0050 은 확장이 있으면 건너뛰고, 없을 때만 만든다(권한 없으면 분명한 오류). RDS 는 프로비저닝 때 마스터가 먼저 설치 - 과제 1 · 15 |
| MEDIUM `_release_session` 뒤 세션 재사용이 설정에 기댐 | `sessionmaker(close_resets_only=True)` 를 명시 + 시험 - 과제 7 |
| MEDIUM 지번 묻는 중 지도를 다시 움직이면 늦은 답이 적용됨 | 요청 번호 + 답이 왔을 때 지도 가운데가 요청한 자리와 같을 때만 적용 - 과제 11 |
| MEDIUM 시험 도우미 이름이 실제와 다름 | `jsonResponse` · `vi.stubEnv` · `installAppKakaoSdkMock`(`dragMapTo` · `emitMapClick`) · `kakaoCandidate` · `mockSearch` · `openAddSheet` · `searchAndPick` 로 고침 - 과제 9 ~ 12 |
| MEDIUM 게이트가 정확성 · 운영 성능을 못 보여 줌 | 과제 14 에 정확도(카카오 지번과 채운 지번을 메모리에서 견준 일치율, 건수만) · 재시작 직후 · 동시 10요청 · `EXPLAIN (ANALYZE, BUFFERS)` 를 더함 |
| LOW 검색어로 채운 이름을 카카오 값이 덮지 않는 회귀 시험 | 과제 10 · 12 시험 |
| LOW 같은 geoRef 두 번 · 배치 중 404 | 같은 지번 두 번은 허용(한 건물의 다른 가게). 404 면 판이 바뀐 것이라 바구니의 geoRef 항목을 모두 이름만으로 바꾸고 알린다 - 과제 12 |
| LOW 지도에서 찾기 키보드 · 초점 | 결과 목록 · 경고 role · 고른 뒤 지도로 초점 · 확정 뒤 담기 단추로 초점 시험 - 과제 11 |

### 0.7 코덱스 재검토 2차(2026-10-08) 반영

| 지적 | 반영 |
|---|---|
| HIGH advisory lock 이 commit 뒤 다른 풀 연결로 바뀔 수 있음 | 적재 전체가 연결 하나(`get_engine().raw_connection()`)를 쥔다. `exclusive_load` 가 시작 · 끝의 `pg_backend_pid()` 가 같은지, `pg_advisory_unlock` 이 true 인지 확인하고 아니면 종료 코드 7. PostGIS 시험이 commit 뒤에도 같은 pid · 잠금 1개 · 두 번째 적재 `LoadBusy` 를 본다 - 과제 8 |
| HIGH `--force` 가 구조 검사까지 넘김 | `--force` 를 없앴다. 파일 이름 · 시도 · 기준일 · 같은 파일 · 같은 내용 · 좌표계 · 중복률 · 식별자 빈 줄 · 지목 못 읽음 · 법정동 빠짐은 넘길 수 없다. 행 수 범위만 `--accept-row-count-change` 로 받아들인다(`row_count_problems` 를 따로 뗐다) - 과제 2 · 8 |
| HIGH 정확도가 보고뿐 | 과제 14 Step 4 에 게이트를 둔다: 주소 채움 줄의 법정동 · 본번 일치율 하한과 동부터 다른 줄(오탐) 상한. 같은 248줄 실측값을 근거로 정했다(0.2) |
| MEDIUM `geoRef.pin` 을 화면이 정함 - 서명 토큰 제안 | **반영하지 않음.** 저장되는 좌표는 어느 경우에도 우리 geo 표의 중심이라 정책 · 보안 영향이 없고, 조작한 요청이 바꿀 수 있는 것은 자기 일정의 핀 정확도뿐이다(일정은 소유자 · 편집자만 고친다). 서명 · 만료 · 키 관리를 더하는 비용이 얻는 것보다 크다. 남는 위험 5 에 적었다 |
| MEDIUM `except Exception` 이 프로그래밍 오류를 503 으로 숨김 | 저장 경로는 `SQLAlchemyError` 만 503. SQLite 에 geo 표가 없는 실제 실패로 503 · 뒤이은 `SELECT 1` 성공 · revision 그대로를 보고, `ValueError` 는 그대로 올라오는지 본다. SQLite 는 실패 뒤에도 트랜잭션을 막지 않으므로 같은 일을 PostGIS 시험(`DROP SCHEMA geo` 를 트랜잭션 안에서 한 뒤 503 · locate 빈 답 · `SELECT 1`)으로도 본다 - 과제 6. 같은 원칙으로 `/api/places/locate` 도 DB 오류만 빈 답 - 과제 5. 검색 쪽 `with_fill` 만 넓게 잡는 그대로(덧붙이는 정보가 검색을 깨면 안 된다) |
| MEDIUM 건물 A1 이 비면 `"None"` 이 식별자가 됨 | `is_feature_key` 가 빈 값 · 공백 · `None` · `"None"` · `nan` 을 거르고, 걸린 줄은 넣지 않고 세어 0.1% 를 넘으면 멈춘다 - 과제 2 · 8 |
| MEDIUM `(2).shp` 가 나눈 조각인지 중복인지 이름으로 모름 | 모든 .shp 의 내용 sha256 을 견줘 같은 것이 둘이면 멈춘다(zip 안 파일도) - 과제 2 · 8 |
| MEDIUM 5174 변환을 실행하지 않음 | PostGIS 시험이 5174 로 쓴 작은 SHP 를 넣고 위도 · 경도를 직접 단언한다(10m 안) - 과제 8 |
| MEDIUM `new ApiError(404, …)` 가 실제 생성자와 다름 | `new ApiError("Address reference not found", { status: 404, statusText: "Not Found", detail: "Address reference not found" })` - 과제 12 |
| MEDIUM 공용 `Button` 은 ref 를 받지 않음 | 담기는 일반 `<button className="btn primary" ref={submitRef}>`(Button 과 같은 클래스)로 확정 - 과제 10 |
| MEDIUM `placeEdit.test.ts:130` 이 고칠 목록에 없음 | 과제 9 Step 1 목록에 더함 |
| MEDIUM 재시작 직후 · 동시 요청에 합격 기준 없음 | 과제 14 Step 5 에 기준을 둔다: 재시작 직후 첫 검색 3초 이하 · 처음 50번 p95 500ms 이하, 동시 10요청 p95 600ms 이하 |
| MEDIUM 백업을 되살릴 수 있는지 · 보호 표 건수 | `pg_restore -l` 로 목록을 읽고 `policies` · `external_source_records` · `users` · `trips` · `trip_places` · `public_places` 건수를 앞뒤로 적어 견준다 - 과제 1 Step 1 · Step 8 |
| LOW 지목을 못 읽은 땅을 그대로 넣음 | 넣되 세고 1% 를 넘으면 멈춘다 - 과제 2 · 8 |

### 0.8 자체 교차 검토(2026-10-08, 에이전트 다섯 갈래 + 반박 검증) 반영

코덱스 3차를 기다리지 않고(사용자 '계속 진행') 백엔드 · 적재 · 화면 · 정책과 비밀값 · 계획 일관성 다섯 갈래로 실제 코드와 대조했다. 지적 62개 중 반박 검증을 통과한 55개(같은 지적을 합치면 37개)를 모두 고쳤다.
과제 2 · 3 · 8 의 코드와 시험은 계획서에서 그대로 꺼내 일회용 PostGIS 에서 돌려 22개 모두 통과했다(나머지 과제의 시험은 각 갈래가 임시 사본에서 확인).

| 묶음 | 고친 것 |
|---|---|
| HIGH 저장소 `add_trip_place` 가 `geo_kind` · `geo_pnu` 를 받지 않음 - 모든 담기가 TypeError | 과제 6 에 `backend/app/repositories/trips.py` 단계와 진짜 저장소 시험 |
| HIGH(검증 MEDIUM) 운영 Jenkins 도 마이그레이션이 db 이미지 교체 앞 | 과제 1 Step 7 끝 설명, 과제 15 Step 6 '운영 승격 전 게이트'(사용자가 방법 선택, 보호 브랜치는 건드리지 않음) |
| MEDIUM 직접 적기가 350ms 늦은 검색어를 읽음 | 과제 12: 시트가 지금 검색 칸 글을 `matchPanel(typedQuery)` 로 넘긴다. 대기 끝의 맞춰 보기 초기화가 막 연 칸을 닫던 것도 고친다 |
| MEDIUM 계획이 깨는데 목록에 없던 기존 시험 | `test_public_places.py:594 · 612`, `trip-detail.test.tsx:3454`, `e2e-backend/backend-mode.spec.ts:384`, `trip-place-basket` 다섯 곳, `CustomPlaceForm.test` 넷, `usePlaceMatch.test` · `PlaceMatchPanel.test` · `publicPlaceText.test` · `placeBasket.test` 의 줄 - 과제 4 · 9 · 10 · 12 |
| MEDIUM 그대로는 통과할 수 없던 시험 | TestClient 는 500 응답을 받는다(미들웨어), `uvicorn.error` 로그는 caplog 에 핸들러를 붙여야 보인다, 같은 파일의 `FakeDb` 가 가져온 것을 가린다(`SavepointDb`), `get_session_factory()` 는 DATABASE_URL 이 있어야 한다, `role="alert"` 없음 → `findByText`, Mock 의 `getCenter()` 타입 오류 - 과제 4 ~ 7 · 11 · 12 |
| MEDIUM 지도 물음이 idle 로 물러지면 '이 위치로' 가 영영 꺼짐 | 과제 11: idle 이 물음 번호를 올릴 때 `asking` 도 푼다, `emitMapIdle` 시험 |
| MEDIUM 찍기를 닫은 뒤 초점 | 담기 단추가 켜져 있을 때만 그리로, 아니면 지도 다시 열기 단추 · 이름 칸 - 과제 10 |
| MEDIUM '아니요' 단추 문구 | 시안 v64 대로 추가 창만 '아니요, 다른 곳이에요'(`PlaceMatchChoices.noneLabel`), 예전 행 확인은 그대로 - 과제 10 · 12 |
| MEDIUM 적재 도구 | `run()` 은 이름 검사가 먼저(엉뚱한 목록이면 파일 · DB 를 건드리지 않음), `run()` 종료 코드 시험(DB 없이 2 · 3, PostGIS 에서 3 → 8 → 0 → 다음 달 0), 땅의 잘못된 고유번호도 센다, Git Bash 경로 변환, 시험 DB 기동 대기, `BACKUP_DIR` 이 비면 멈춤 - 과제 1 · 8 · 13 · 14 |
| MEDIUM 품질 상수가 실측 없이 정해짐 | 전국 속성 실측(0.2)으로 고침: 건물 같은 식별자 0.60% → 기준 2%, 땅 0% → 1%. 지목이 정식 이름('임야' · '과수원' 등 약 2,300줄)인 땅을 약식 부호로 바꿔 농지 · 임야 거르기에서 새지 않게 했다 - 과제 2 |
| LOW | 카카오 주소 첫 낱말을 남기던 `place_search.py:34` 로그, 이름 규칙 시험, 경계 위 점 시험(5186 에서 바로 만든 건물 변), 미리보기 배지 `fill` 클래스, Review Focus 1 · 5 의 시험을 실제 요청 · 화면으로 - 과제 3 · 6 · 7 · 10 · 12 |

반박 검증에서 떨어진 7개(최적화 제안 · 이미 계획이 다룬 것)는 반영하지 않았다.

### 0.9 개발서버 구조 - 지금(2026-10-08 실측)과 이 계획 뒤

지금(develop `4612926`, Alembic `0048_public_places`, public 표 32개, 컨테이너 frontend · backend · logarchive · caddy · cloudflared · db · jenkins):
```
브라우저 ─HTTPS→ Cloudflare ─터널→ caddy:80 ─/api→ backend:8000 ─→ db(postgres:16-alpine)
                                           └─나머지→ frontend:4173
backend ─실시간만→ Kakao Local(검색 · 주변)      jenkins(dev 에이전트): build → run --rm backend alembic → up -d --wait
```
이 계획 뒤(예정 - 굵은 것이 새것):
```
브라우저(결과 배지 · 담기 칸 · **지도에서 찾기**) ─→ caddy ─/api→ backend
  backend: place-search · /places/match 에 **fill**, **POST /places/locate**, 담기는 customPlace{name, **geoRef**} → geo 를 id 로 다시 읽음
  backend ─→ db(**postgis/postgis:16-3.5-alpine**): public.trip_places(+**geo_kind · geo_pnu**), **geo.building · geo.parcel · geo.legal_dong · geo.load_run**
  카카오 값 · 찍은 좌표: 비교만 하고 버림(151842 · 151916-4)
**th-geo-loader**(월 1회 일회성): 저장소 밖 폴더의 브이월드 SHP/ZIP → 검사 → geo.*_next COPY → 한 트랜잭션 바꿔치기
jenkins: **up -d db** → run --rm backend alembic(0050) → up -d --wait     (운영 Jenkins 는 과제 15 Step 6 게이트)
```
같은 내용의 Archify 맵(개발서버 아키텍처 · 요청 경로 · 공공 장소 · 주소 채움 예정 구조 · 주소 채움 담기 흐름)은 로컬 도구 `.archify-local` 의 `system-map:dev` 로 다시 만든다(저장소 밖 도구).

---

## Global Constraints

- 카카오 로컬 값(장소명 · 주소 · 좌표 · 전화 · 분류)과 **지도에서 찍은 좌표**는 저장 · 로그 · 외부 전송하지 않는다. 맞춰 보는 동안 서버 메모리에서만 쓰고 버린다. 로그에는 예외 이름만(`str(exc)` · `exc_info` 금지).
- 일정에 저장하는 주소 · 좌표는 공공데이터(public_places 또는 geo 표) 값뿐이다. 이름은 공공데이터 이름이거나 사용자가 쓴 글(검색어로 미리 채운 것 포함)이다.
- `customPlace` 는 `name` 과 선택 `geoRef{kind, id, pin}` 만 받는다. 위도 · 경도 · 주소는 받지 않는다(422).
- 이름 칸을 카카오 장소 이름(검색 결과 · 지도에서 찾기 결과)으로 채우거나 placeholder · 참고 문구로 보이지 않는다.
- 땅 거리 기준 `PARCEL_GATE_M = 30`, 적재 제외 지목 `{"전", "답", "과", "목", "임"}`, 기대 시도 코드 `{"11","12","26","27","28","30","31","36","41","43","44","47","48","50","51","52"}`(2026-07 부터 전남 · 광주 통합 코드 12).
- 출처 표시 문구 `국토교통부 공공데이터`(자세히: GIS건물통합정보 · 연속지적도).
- API 필드는 camelCase, DB 는 snake_case. 새 요청 모델은 모두 `extra="forbid"`.
- 스키마는 Alembic 으로만 만든다(`create_all` 금지). geo 표의 데이터는 적재 도구가 넣는다.
- 비밀값은 커밋 · 출력하지 않는다. 적재 도구는 앱 설정(`DATABASE_URL`)을 쓰고 연결 문자열을 출력하지 않는다.
- 한국어 파일은 UTF-8 그대로, `git diff --check` 깨끗, U+FFFD · 엉뚱한 한자 없음.
- 커밋하지 않는다(사용자 결정). 각 과제 끝의 '변경 확인'은 `git diff --stat` · `git status --short` 다.

## Review Focus

1. **옛 화면 · 조작한 요청이 `customPlace` 에 위도 · 경도를 보냄**: 422 이고 아무것도 쓰지 않으며 revision 그대로다(과제 6 시험 `refuses raw coordinates in a custom place` - 단건 · 묶음 요청을 실제로 보내 422 · 저장 없음 · revision 1 을 본다).
2. **geo 표가 비었거나 없음**(적재 전 · 로컬 SQLite 시험 · 마이그레이션 직후): 검색 · 맞춰 보기 · 위치 묻기는 500 없이 `fill` null, 저장(geoRef)은 503 이고 revision 그대로(과제 4 · 5 · 6 시험).
3. **월 갱신 바꿔치기 뒤 저장**: 화면이 쥔 `geoRef.id` 는 새 판에 없다 - 404, 화면은 바구니의 geoRef 항목을 모두 이름만으로 바꾸고 '주소 정보가 바뀌어 위치를 뺐어요'를 알린다(과제 6 · 12 시험).
4. **같은 파일이 두 번 들어온 적재**(압축 푼 폴더 이름이 다르거나 zip 과 폴더가 둘 다, `(2).shp` 가 같은 내용): 파일 이름 겹침 · 내용 지문 · 중복률로 막고 바꾸지 않으며, 어떤 옵션으로도 넘기지 못한다(과제 2 시험 `manifest refuses … a duplicated region file` · `a part file with the same content …`, 과제 8 의 `run`).
5. **긴 검색어 · 빈 검색어 · 지도에서 찾기로 고른 장소 이름**: 100자 넘는 검색어는 100자로 잘라 채우고, 빈 검색어면 이름 칸은 비고 담기 단추가 꺼지며, 지도에서 찾기로 옮겨도 이름 칸은 그대로다(과제 10 · 11 시험).

---

## 파일 지도

| 파일 | 하는 일 | 과제 |
|---|---|---|
| `compose.local.yaml` · `deploy/jenkins/dev/Jenkinsfile` | db 이미지 `postgis/postgis:16-3.5-alpine` · 마이그레이션 앞에 db 맞추기 | 1 |
| `backend/alembic/versions/0050_geo_reference.py` | postgis 확장(있으면 건너뜀) · geo 스키마 · 표(id PK · feature_key) · 색인 · trip_places.geo_kind/geo_pnu | 1 |
| `backend/app/models/tables.py` | TripPlace.geo_kind · geo_pnu + CHECK | 1 |
| `backend/app/services/geo_reference.py`(새) | 순수 규칙: 지번 주소 · 지목 · 기준 상수 · 바꿔치기 SQL · 구조 검사(manifest · 내용 지문 · 품질) · 행 수 검사 | 2 |
| `backend/app/repositories/geo.py`(새) | 6곳 묶음 찾기(ST_Covers) · id 로 읽기 | 3 |
| `backend/app/repositories/trips.py` | `add_trip_place` 가 geo_kind · geo_pnu 를 받아 저장(명시 키워드 인자라 안 더하면 모든 담기가 `TypeError`) | 6 |
| `backend/app/services/address_fill.py`(새) | fill 만들기(30m) · 위치 묻기 · SAVEPOINT · 실패 격리 | 4 · 5 |
| `backend/app/schemas/places.py` | AddressFill(id 포함) · PlaceMatchResponse.fill · LocateRequest/Response | 4 · 5 |
| `backend/app/services/trips.py` | `_prematch` 에 fill, customPlace.geoRef 저장(SAVEPOINT · 503 · 404), payload geoKind, 카카오 오류 로그 | 4 · 6 · 7 |
| `backend/app/api/routes/places.py` | `/match` 에 fill, `POST /locate` | 4 · 5 |
| `backend/app/schemas/trip.py` | GeoRef · CustomPlaceInput(name · geoRef 만) · ItineraryPlace.geoKind | 6 |
| `backend/app/services/trip_public_places.py` | custom/public 열에 주소 · geo 열 | 6 |
| `backend/app/services/kakao_local.py` · `place_search.py` · `backend/app/main.py` · `backend/app/db/session.py` | 공유 HTTP 연결 · 종료 시 닫기 · 오류 로그에 값 없음 · `close_resets_only=True` | 7 |
| `backend/scripts/geo_load.py`(새) · `backend/requirements-geo.txt`(새) · `backend/Dockerfile` | 월 적재 도구 · 의존성 · `geo-loader` 단계 | 8 |
| `frontend/src/api/{types,backendApi,dataApi}.ts` | AddressFill · fill · locatePlace · GeoRef · CustomPlaceInput(name · geoRef) · geoKind | 9 |
| `frontend/src/components/itinerary/placeAdd/{usePlaceMatch,placeBasket,publicPlaceText}.ts` | 갈래 · 시작값 · 바구니 · 배지 | 9 · 10 |
| `frontend/src/components/itinerary/placeAdd/{CustomPlaceForm,MapPointPicker,PlaceMatchChoices,PlaceMatchPanel}.tsx` · `LegacyPlaceConfirm.tsx` | 채운 칸 · 주소만 · 이름만 · 지도에서 찾기 · 0.5 규칙 · '아니요' 단추 문구(추가 창은 '다른 곳이에요') | 10 · 11 |
| `frontend/src/pages/itinerary/ItineraryDetailPage.tsx` | 친 검색어 넘기기 · 바구니 · 미리보기 문구 · 상세 출처 · 404/503 문구 | 12 |
| `frontend/src/styles/app.css` | 시안 v64 새 부품 CSS | 10 · 11 |
| 문서 · 계약 · 골든 · 운영 | 13 |
| 로컬 적재 · 실측 게이트 | 14 |
| 개발서버(머지 뒤, 단계마다 승인) · AWS 메모 | 15 |

---

## 과제 1: PostGIS 이미지 · 배포 순서 · 0050 마이그레이션 · TripPlace geo 열

**Files:**
- Modify: `compose.local.yaml:3`(db 이미지), `deploy/jenkins/dev/Jenkinsfile`('Run DB Migration' 단계)
- Create: `backend/alembic/versions/0050_geo_reference.py`
- Modify: `backend/app/models/tables.py`(TripPlace)
- Test: `backend/tests/test_db_schema.py`

**Interfaces:**
- Produces: 확장 `postgis`(있으면 건너뜀), 스키마 `geo`, 시퀀스 `geo.feature_id_seq`(판이 바뀌어도 id 를 다시 쓰지 않는다),
  표 `geo.building(id bigint PK DEFAULT nextval('geo.feature_id_seq'), feature_key varchar(40), pnu varchar(19), la, lo, rx, ry double precision, geom geometry(Geometry,5186))`,
  `geo.parcel(… 같은 열 + jimok varchar(4))`, `geo.legal_dong(code varchar(10) PK, name varchar(100))`, `geo.load_run`.
  색인 이름 `building_pkey` · `building_geom_gix` · `building_pnu_ix` · `parcel_pkey` · `parcel_geom_gix` · `parcel_pnu_ix`.
  `trip_places.geo_kind varchar(10)`(CHECK building · parcel) · `trip_places.geo_pnu varchar(19)`. ORM `TripPlace.geo_kind` · `TripPlace.geo_pnu`.

- [ ] **Step 1: 로컬 DB 덤프(되돌릴 자리) · 되살릴 수 있는지 · 보호 표 건수**

`BACKUP_DIR` 은 저장소 밖 백업 폴더(700)다 - 같은 셸 블록 안에서 정한다(비어 있으면 첫 줄에서 멈춘다).
```bash
DUMP="${BACKUP_DIR:?저장소 밖 백업 폴더를 BACKUP_DIR 로 먼저 정한다}/local-before-geo-20261008.dump"
MSYS_NO_PATHCONV=1 docker exec travel-hunter-onprem-db-1 sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/before-geo.dump' \
  && docker cp travel-hunter-onprem-db-1:/tmp/before-geo.dump "$DUMP" && chmod 600 "$DUMP" \
  && MSYS_NO_PATHCONV=1 docker exec travel-hunter-onprem-db-1 sh -c 'pg_restore -l /tmp/before-geo.dump | grep -c "TABLE DATA"' \
  && MSYS_NO_PATHCONV=1 docker exec travel-hunter-onprem-db-1 rm -f /tmp/before-geo.dump
MSYS_NO_PATHCONV=1 docker exec travel-hunter-onprem-db-1 test -e /tmp/before-geo.dump && echo LEFT-BEHIND || echo CLEANED
sha256sum "$DUMP" | cut -c1-16
MSYS_NO_PATHCONV=1 docker exec travel-hunter-onprem-db-1 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F " " -c "
  select (select count(*) from policies), (select count(*) from external_source_records), (select count(*) from users),
         (select count(*) from trips), (select count(*) from trip_places), (select count(*) from public_places)"'
```
Expected: `pg_restore -l` 이 덤프 목록을 읽고 TABLE DATA 줄 수(0 보다 큼)를 낸다 - 못 읽으면 멈춘다. 컨테이너 임시 파일은 `CLEANED`, 지문 16자만 출력.
보호 표 여섯의 건수를 적어 둔다(값은 출력하지 않는다). Step 8 뒤 같은 질의로 견준다.

- [ ] **Step 2: 실패하는 시험 쓰기** - `backend/tests/test_db_schema.py`

지금의 `test_alembic_0049_follows_0048_and_is_the_only_head` 는 head 가 0049 라고 단언하므로 0049 의 앞 버전만 보게 고치고, `render_0049` 를 아래 `render_migration` 으로 넓혀 0049 시험도 이것을 쓰게 한 뒤 0050 시험 셋을 더한다.

```python
def test_alembic_0049_follows_0048() -> None:
    backend = Path(__file__).parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_revision("0049_trip_place_public_category").down_revision == "0048_public_places"


def test_alembic_0050_follows_0049_and_is_the_only_head() -> None:
    backend = Path(__file__).parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0050_geo_reference"]
    assert script.get_revision("0050_geo_reference").down_revision == "0049_trip_place_public_category"


def render_migration(filename: str, direction: str) -> str:
    """마이그레이션의 upgrade · downgrade 가 내는 Postgres SQL - 오프라인이라 DB 에 닿지 않는다."""

    path = Path(__file__).parents[1] / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(f"migration_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    buffer = io.StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buffer})
    with Operations.context(context):
        getattr(module, direction)()
    return buffer.getvalue()


def render_0049(direction: str) -> str:
    return render_migration("0049_trip_place_public_category.py", direction)


def test_alembic_0050_creates_postgis_geo_tables_with_stable_ids_and_trip_place_geo_columns() -> None:
    up = render_migration("0050_geo_reference.py", "upgrade")
    down = render_migration("0050_geo_reference.py", "downgrade")
    # 확장은 없을 때만 만든다 - RDS 처럼 미리 설치된 곳에서는 권한 없이 지나간다
    assert "pg_extension WHERE extname = 'postgis'" in up and "CREATE EXTENSION postgis" in up
    assert up.index("CREATE EXTENSION postgis") < up.index("CREATE SCHEMA IF NOT EXISTS geo") < up.index("CREATE SEQUENCE geo.feature_id_seq")
    for table in ("geo.building", "geo.parcel", "geo.legal_dong", "geo.load_run"):
        assert f"CREATE TABLE {table}" in up
    # 판이 바뀌어도 id 를 다시 쓰지 않는다 - 옛 화면의 geoRef 가 다른 건물을 가리키지 않게(코덱스 HIGH)
    assert up.count("DEFAULT nextval('geo.feature_id_seq')") == 2 and "feature_key varchar(40) NOT NULL" in up
    assert "geometry(Geometry, 5186)" in up and "USING gist (geom)" in up and "jimok varchar(4)" in up
    assert "ADD COLUMN geo_kind VARCHAR(10)" in up and "ADD COLUMN geo_pnu VARCHAR(19)" in up and "ck_trip_places_geo_kind" in up
    # 되돌리기는 geo 스키마와 열만 지운다 - postgis 확장은 남긴다
    assert "DROP SCHEMA IF EXISTS geo CASCADE" in down and "DROP EXTENSION" not in down
    assert "DROP COLUMN geo_pnu" in down and "DROP COLUMN geo_kind" in down


def test_trip_place_geo_columns_are_registered() -> None:
    places = Base.metadata.tables["trip_places"]
    assert places.c.geo_kind.type.length == 10 and places.c.geo_kind.nullable
    assert places.c.geo_pnu.type.length == 19 and places.c.geo_pnu.nullable
    assert "ck_trip_places_geo_kind" in {constraint.name for constraint in places.constraints if constraint.name}
```
(기존 `render_0049` 함수 본문은 위 한 줄짜리로 바꾼다 - 0049 시험은 그대로 돈다.)

- [ ] **Step 3: 실패 확인** - Run: `cd backend && python -m pytest tests/test_db_schema.py -q` → Expected: FAIL(`0050_geo_reference.py` 없음 · `geo_kind` 없음).

- [ ] **Step 4: 마이그레이션 쓰기** - `backend/alembic/versions/0050_geo_reference.py`

```python
"""geo reference tables (building · parcel jibun) for address fill + trip_places geo provenance

Revision ID: 0050_geo_reference
Revises: 0049_trip_place_public_category
Create Date: 2026-10-08

방식1 '주소 채움'(계획 docs/superpowers/plans/2026-10-07-place-add-address-fill.md)이 쓴다.
- postgis 확장 · geo 스키마: 국토교통부 GIS건물통합정보(건물) · 연속지적도(땅, 농지 · 임야 제외)의 도형과 고유번호(PNU).
  데이터는 적재 도구(backend/scripts/geo_load.py)가 월 1회 새 표(*_next)에 넣고 바꿔치기한다. 이 마이그레이션은 빈 표만 만든다.
  앱 데이터와 다른 스키마라 백업 · 로컬 복사에서 뺄 수 있다(원본 파일에서 다시 넣을 수 있다).
- id 는 두 표가 함께 쓰는 시퀀스에서 받는다 - 판을 바꿔도 같은 id 가 다른 건물 · 땅을 가리키지 않는다(옛 geoRef 는 404).
- 확장은 없을 때만 만든다. AWS RDS 는 프로비저닝 때 마스터 사용자(rds_superuser)가 먼저 설치한다 - 그러면 여기서는 건너뛴다.
- trip_places.geo_kind · geo_pnu: 나만의 장소의 주소 · 좌표를 건물 · 땅 지번에서 채웠을 때 그 출처. nullable.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0050_geo_reference"
down_revision: str | None = "0049_trip_place_public_category"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SHAPE_COLUMNS = (
    "id bigint PRIMARY KEY DEFAULT nextval('geo.feature_id_seq'), feature_key varchar(40) NOT NULL, pnu varchar(19) NOT NULL, "
    "la double precision NOT NULL, lo double precision NOT NULL, rx double precision NOT NULL, ry double precision NOT NULL, "
    "geom geometry(Geometry, 5186) NOT NULL"
)


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis') THEN CREATE EXTENSION postgis; END IF; END $$"
    )
    op.execute("CREATE SCHEMA IF NOT EXISTS geo")
    op.execute("CREATE SEQUENCE geo.feature_id_seq")
    op.execute(f"CREATE TABLE geo.building ({SHAPE_COLUMNS})")
    op.execute(f"CREATE TABLE geo.parcel ({SHAPE_COLUMNS}, jimok varchar(4))")
    for table in ("building", "parcel"):
        op.execute(f"CREATE INDEX {table}_geom_gix ON geo.{table} USING gist (geom)")
        op.execute(f"CREATE INDEX {table}_pnu_ix ON geo.{table} (pnu)")
    op.execute("CREATE TABLE geo.legal_dong (code varchar(10) PRIMARY KEY, name varchar(100) NOT NULL)")
    op.execute(
        "CREATE TABLE geo.load_run (id bigserial PRIMARY KEY, finished_at timestamptz NOT NULL DEFAULT now(), "
        "building_rows bigint NOT NULL, parcel_rows bigint NOT NULL, building_base_date varchar(8), parcel_base_date varchar(8))"
    )
    op.add_column("trip_places", sa.Column("geo_kind", sa.String(length=10), nullable=True))
    op.add_column("trip_places", sa.Column("geo_pnu", sa.String(length=19), nullable=True))
    op.create_check_constraint("ck_trip_places_geo_kind", "trip_places", "geo_kind IS NULL OR geo_kind IN ('building', 'parcel')")


def downgrade() -> None:
    op.drop_constraint("ck_trip_places_geo_kind", "trip_places", type_="check")
    op.drop_column("trip_places", "geo_pnu")
    op.drop_column("trip_places", "geo_kind")
    op.execute("DROP SCHEMA IF EXISTS geo CASCADE")
```

- [ ] **Step 5: 모델에 열 더하기** - `backend/app/models/tables.py` TripPlace

`__table_args__` 끝에:
```python
        CheckConstraint(
            "geo_kind IS NULL OR geo_kind IN ('building', 'parcel')",
            name="ck_trip_places_geo_kind",
        ),
```
`user_label` 아래에:
```python
    # 나만의 장소의 주소 · 좌표를 건물 · 땅 지번(국토교통부 공공데이터, geo 스키마)에서 채웠을 때 그 출처(0050). 나머지 행은 비어 있다
    geo_kind: Mapped[str | None] = mapped_column(String(10))
    geo_pnu: Mapped[str | None] = mapped_column(String(19))
```

- [ ] **Step 6: 시험 통과 확인** - Run: `cd backend && python -m pytest tests/test_db_schema.py -q && alembic upgrade head --sql > /dev/null && echo SQL-OK` → Expected: PASS, `SQL-OK`.

- [ ] **Step 7: 개발서버 배포 순서 고치기** - `deploy/jenkins/dev/Jenkinsfile`

지금 'Run DB Migration' 단계는 `docker compose run --rm backend python -m alembic upgrade head` 이고, `up -d` 는 그 다음 'Deploy' 단계다. `run` 은 이미 떠 있는 db 를 다시 만들지 않으므로, db 이미지를 바꾼 첫 배포에서 0050 이 옛 이미지(postgis 없음)에 돌아 실패한다. 마이그레이션 앞에 db 를 compose 정의대로 맞춘다(이미지 · 설정이 같으면 아무 일도 없다).

```groovy
        stage('Run DB Migration') {
            steps {
                sh '''
                    echo "===== DB Migration 실행 ====="

                    cd ${PROJECT_DIR}

                    # db 를 compose 정의(이미지 포함)대로 먼저 맞춘다 - 이미지가 바뀐 배포에서도 마이그레이션이 새 db 에 돈다
                    docker compose \
                      -p ${COMPOSE_PROJECT_NAME} \
                      --env-file ${ENV_FILE} \
                      -f ${COMPOSE_FILE} \
                      up -d --no-deps --wait --wait-timeout 120 db

                    docker compose \
                      -p ${COMPOSE_PROJECT_NAME} \
                      --env-file ${ENV_FILE} \
                      -f ${COMPOSE_FILE} \
                      run --rm backend \
                      python -m alembic upgrade head
                '''
            }
        }
```
(운영 Jenkins 는 보호 브랜치 `ci/prod-jenkins` 의 `deploy/jenkins/prod/Jenkinsfile` 이고 순서가 같다 - 'Run DB Migration'(`run --rm backend`)이 'Deploy Production'(`up -d`) 앞이다. 운영 `compose.yaml` 은 `compose.local.yaml` 을 include 해 같은 db 이미지 줄을 쓴다.
그래서 이 변경이 main 에 올라가면 운영 배포는 0050 을 옛 postgres 컨테이너에 돌려 `CREATE EXTENSION postgis` 에서 멈춘다(마이그레이션 트랜잭션은 되돌려지고 앱은 그대로 - 안전하게 멈춘다).
보호 브랜치는 이 계획에서 고치지 않는다. 과제 15 Step 6 '운영 승격 전 게이트'에서 사용자가 방법을 정한다. AWS 는 RDS 라 이미지 바꾸기가 없다.)

- [ ] **Step 8: 로컬 db 이미지를 PostGIS 로 바꾸고 마이그레이션 적용**

`compose.local.yaml` 3번째 줄 `image: postgres:16-alpine` → `image: postgis/postgis:16-3.5-alpine`(같은 PostgreSQL 16 · alpine 이라 데이터 볼륨을 그대로 읽는다).
3단계 때 컨테이너를 다시 만든 명령과 같은 프로젝트 이름 · env 파일로 `db` 만 다시 만들고, backend 이미지를 이 워크트리로 다시 빌드해 `alembic upgrade head` 를 돌린다.

```bash
docker compose --env-file <3단계와 같은 env> -p travel-hunter-onprem -f compose.local.yaml config > /dev/null && echo CONFIG-OK
docker compose --env-file <같은 env> -p travel-hunter-onprem -f compose.local.yaml up -d --no-deps --wait db
docker compose --env-file <같은 env> -p travel-hunter-onprem -f compose.local.yaml build backend
docker compose --env-file <같은 env> -p travel-hunter-onprem -f compose.local.yaml up -d --no-deps backend
MSYS_NO_PATHCONV=1 docker exec travel-hunter-onprem-backend-1 sh -c 'alembic upgrade head'
MSYS_NO_PATHCONV=1 docker exec travel-hunter-onprem-db-1 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "select postgis_lib_version(), (select version_num from alembic_version), (select count(*) from geo.building), (select count(*) from geo.parcel)"'
```
Expected: `3.5.x|0050_geo_reference|0|0`. Step 1 에 적은 행 수가 그대로다.

- [ ] **Step 9: 변경 확인(커밋하지 않음)** - Step 1 의 보호 표 여섯 건수 질의를 다시 돌려 앞의 값과 같은지 본다(다르면 멈추고 덤프로 되돌릴지 사용자에게 묻는다). - `git diff --stat -- compose.local.yaml deploy/jenkins/dev/Jenkinsfile backend/alembic backend/app/models backend/tests/test_db_schema.py`

---

## 과제 2: 지번 규칙 · 적재 검사(순수 함수) - `geo_reference.py`

**Files:**
- Create: `backend/app/services/geo_reference.py`
- Test: `backend/tests/test_geo_reference.py`

**Interfaces:**
- Produces: `PARCEL_GATE_M = 30`, `EXCLUDED_JIMOK`, `EXPECTED_REGION_CODES`, `ROW_BOUNDS`, `MAX_DUP_RATIO`, `MAX_MISSING_KEY_RATIO = 0.001`, `MAX_UNKNOWN_JIMOK_RATIO = 0.01`, `GEO_SOURCE_NOTICE`, `GeoKind = Literal["building", "parcel"]`, `TABLES`,
  `is_pnu(value) -> bool`, `is_feature_key(value) -> bool`, `jibun_address(dong_name: str, pnu: str) -> str`, `JIMOK_CODES`, `JIMOK_NAMES`, `jimok_of(label) -> str | None`(약식 부호 한 글자 또는 None), `keep_parcel(jimok) -> bool`,
  `@dataclass(frozen=True) GeoHit(kind: GeoKind, id: int, pnu: str, address: str, latitude: float, longitude: float, distance_m: float)`,
  `within_gate(hit) -> bool`, `fill_item(hit) -> dict`, `swap_statements(table) -> list[str]`,
  `@dataclass(frozen=True) SourceFile(path: str, name: str, code: str, base_date: str)`, `parse_source(path: str) -> SourceFile | None`,
  **구조 검사(넘길 수 없음)** `manifest_problems(files: list[str]) -> list[str]`, `content_duplicate_problems(digests: dict[str, str]) -> list[str]`, `quality_problems(table, rows, distinct_keys, missing_keys, unknown_jimok) -> list[str]`,
  **행 수 검사(`--accept-row-count-change` 로만 넘김)** `row_count_problems(table: str, rows: int) -> list[str]`.

- [ ] **Step 1: 실패하는 시험 쓰기** - `backend/tests/test_geo_reference.py`

```python
import pytest

from app.services.geo_reference import (
    EXCLUDED_JIMOK, EXPECTED_REGION_CODES, PARCEL_GATE_M, GeoHit, content_duplicate_problems, fill_item, is_feature_key, is_pnu,
    jibun_address, jimok_of, keep_parcel, manifest_problems, parse_source, quality_problems, row_count_problems, swap_statements, within_gate,
)


def test_a_jibun_address_is_the_legal_dong_name_and_the_lot_number_from_the_pnu() -> None:
    # PNU 19자리 = 법정동코드 10 · 산 여부 1(1 일반, 2 산) · 본번 4 · 부번 4. 세종 실데이터 한 줄(A4 '세종특별자치시  부강면 문곡리', A5 '302-2')
    assert jibun_address("세종특별자치시  부강면 문곡리", "3611033025103020002") == "세종특별자치시 부강면 문곡리 302-2"
    assert jibun_address("세종특별자치시 반곡동", "3611010100109300000") == "세종특별자치시 반곡동 930"
    assert jibun_address("경기도 양평군 양평읍 백안리", "4183025026200120001") == "경기도 양평군 양평읍 백안리 산12-1"
    assert jibun_address("", "3611033025103020002") == "302-2"   # 법정동 이름이 빠진 경우(적재 검사가 막지만) 결과를 버리지 않는다


def test_a_malformed_pnu_or_feature_key_is_refused() -> None:
    assert is_pnu("3611033025103020002") and not is_pnu("361103302510302000") and not is_pnu(None) and not is_pnu("36110330251030200x2")
    with pytest.raises(ValueError):
        jibun_address("세종특별자치시 반곡동", "123")
    # 빈 값 · None · 'None' 문자열(str(None)) · 공백은 식별자가 아니다(코덱스 재검토 MEDIUM)
    assert is_feature_key("0000235425653372309500000000") and is_feature_key("1114010300100310000")
    assert not any(is_feature_key(v) for v in (None, "", "   ", "None", "nan"))


def test_the_land_category_is_the_hangul_at_the_end_of_the_lot_label() -> None:
    assert (jimok_of("203-24전"), jimok_of("930 공"), jimok_of("산12-1임"), jimok_of(""), jimok_of(None)) == ("전", "공", "임", None, None)
    # 정식 이름은 약식 부호로(전국 약 2,300줄), 겹친 글자 · 부호가 아닌 글자 · 깨진 글자는 못 읽음 - 열(varchar(4))을 넘는 값이 나오지 않는다
    assert (jimok_of("12임야"), jimok_of("5과수원"), jimok_of("3목장용지"), jimok_of("7도로"), jimok_of("9잡종지")) == ("임", "과", "목", "도", "잡")
    assert (jimok_of("4답답"), jimok_of("8가"), jimok_of("빈값"), jimok_of("1주유소용지아님")) == (None, None, None, None)


def test_farmland_and_forest_are_not_loaded_but_unknown_categories_are_kept_and_counted() -> None:
    assert EXCLUDED_JIMOK == frozenset({"전", "답", "과", "목", "임"})
    assert not keep_parcel("답") and keep_parcel("대") and keep_parcel("차") and keep_parcel(None)
    assert not keep_parcel(jimok_of("12임야")) and not keep_parcel(jimok_of("5과수원"))   # 정식 이름으로 적힌 농지 · 임야도 거른다


def test_a_building_always_fills_but_a_parcel_only_within_thirty_meters() -> None:
    building = GeoHit("building", 7, "3611033025103020002", "세종 302-2", 36.5, 127.3, 120.0)
    near = GeoHit("parcel", 8, "3611033025103020002", "세종 302-2", 36.5, 127.3, float(PARCEL_GATE_M))
    far = GeoHit("parcel", 9, "3611033025103020002", "세종 302-2", 36.5, 127.3, PARCEL_GATE_M + 0.5)
    assert within_gate(building) and within_gate(near) and not within_gate(far)
    assert fill_item(near) == {"kind": "parcel", "id": 8, "pnu": "3611033025103020002", "address": "세종 302-2", "latitude": 36.5, "longitude": 127.3, "distanceMeters": 30}


def test_the_monthly_swap_renames_next_tables_and_all_their_indexes_and_drops_the_old_ones() -> None:
    sql = swap_statements("parcel")
    assert sql[:4] == [
        "ALTER TABLE geo.parcel RENAME TO parcel_old",
        "ALTER INDEX geo.parcel_pkey RENAME TO parcel_old_pkey",
        "ALTER INDEX geo.parcel_geom_gix RENAME TO parcel_old_geom_gix",
        "ALTER INDEX geo.parcel_pnu_ix RENAME TO parcel_old_pnu_ix",
    ]
    assert sql[4:] == [
        "ALTER TABLE geo.parcel_next RENAME TO parcel",
        "ALTER INDEX geo.parcel_next_pkey RENAME TO parcel_pkey",
        "ALTER INDEX geo.parcel_next_geom_gix RENAME TO parcel_geom_gix",
        "ALTER INDEX geo.parcel_next_pnu_ix RENAME TO parcel_pnu_ix",
        "DROP TABLE geo.parcel_old",
    ]
    with pytest.raises(ValueError):
        swap_statements("users; drop table trips")


def full_set(dataset: str, date: str) -> list[str]:
    return [f"/data/{dataset}/AL_{dataset}_{code}_{date}/AL_{dataset}_{code}_{date}.shp" for code in sorted(EXPECTED_REGION_CODES)]


def test_a_complete_single_date_set_with_part_files_passes_the_manifest() -> None:
    files = full_set("D010", "20260909") + ["/data/D010/AL_D010_41_20260909/AL_D010_41_20260909(2).shp"]
    assert parse_source(files[-1]).code == "41" and parse_source(files[-1]).name == "AL_D010_41_20260909(2).shp"
    assert manifest_problems(files) == []


def test_manifest_refuses_a_missing_region_two_dates_and_a_duplicated_region_file() -> None:
    files = full_set("D002", "20260908")
    assert manifest_problems(files[1:]) == [f"missing region codes: {sorted(EXPECTED_REGION_CODES)[0]}"]
    assert "more than one base date: 20260808, 20260908" in manifest_problems(files[:-1] + [files[-1].replace("20260908", "20260808")])
    duplicated = files + ["/data/D002/other-folder/AL_D002_11_20260908.shp"]   # 같은 파일이 다른 폴더에 한 번 더
    assert "duplicated file: AL_D002_11_20260908.shp" in manifest_problems(duplicated)
    assert manifest_problems(files + ["/data/D002/readme.shp"]) == ["unknown file name: readme.shp"]


def test_a_part_file_with_the_same_content_as_another_is_a_duplicate_download() -> None:
    # '(2).shp'가 진짜 나눈 조각인지 같은 파일을 두 번 받은 것인지는 이름으로 모른다 - 내용 지문이 같으면 멈춘다(코덱스 재검토 MEDIUM)
    assert content_duplicate_problems({"AL_D010_41_20260909.shp": "aa", "AL_D010_41_20260909(2).shp": "bb"}) == []
    assert content_duplicate_problems({"AL_D010_41_20260909.shp": "aa", "AL_D010_41_20260909(2).shp": "aa"}) == [
        "same content: AL_D010_41_20260909(2).shp, AL_D010_41_20260909.shp"
    ]


def test_quality_checks_count_duplicates_missing_keys_and_unknown_land_categories() -> None:
    assert quality_problems("building", 14_392_124, 14_305_380, missing_keys=1, unknown_jimok=0) == []   # 2026-09 판 전국 실측 그대로
    assert quality_problems("parcel", 19_406_867, 19_406_867, missing_keys=0, unknown_jimok=4_526) == []
    assert quality_problems("building", 14_392_125, 14_000_000, missing_keys=0, unknown_jimok=0) == ["building: duplicate feature keys 2.7% > 2.0%"]
    assert quality_problems("parcel", 19_500_000, 18_000_000, missing_keys=0, unknown_jimok=0) == ["parcel: duplicate feature keys 7.7% > 1.0%"]
    assert quality_problems("building", 14_000_000, 14_000_000, missing_keys=20_000, unknown_jimok=0) == ["building: rows without a feature key 0.14% > 0.10%"]
    assert quality_problems("parcel", 19_500_000, 19_500_000, missing_keys=0, unknown_jimok=300_000) == ["parcel: unknown land category 1.54% > 1.00%"]


def test_row_count_bounds_are_a_separate_check_that_alone_can_be_accepted() -> None:
    assert row_count_problems("building", 14_392_125) == []
    assert row_count_problems("building", 9_000_000) == ["building: 9000000 rows is outside 12000000..17000000"]
```

- [ ] **Step 2: 실패 확인** - `cd backend && python -m pytest tests/test_geo_reference.py -q` → FAIL(모듈 없음).

- [ ] **Step 3: 구현** - `backend/app/services/geo_reference.py`

```python
"""건물 · 땅 지번(국토교통부 GIS건물통합정보 · 연속지적도) - 방식1 '주소 채움'의 공공데이터 규칙(순수 함수).

카카오 좌표 · 지도에서 찍은 좌표는 맞춰 보는 동안만 쓰고 버린다(데브톡 151505-1 · 151842). 일정에 담는 주소 · 좌표는 이 표의 값뿐이다.
계획: docs/superpowers/plans/2026-10-07-place-add-address-fill.md 0절.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

GeoKind = Literal["building", "parcel"]
TABLES = ("building", "parcel")
PARCEL_GATE_M = 30   # 땅 중심이 고른 자리에서 이만큼 안일 때만 핀까지 채운다(2026-10-07 사용자 결정, 248줄 실측 89%)
EXCLUDED_JIMOK = frozenset({"전", "답", "과", "목", "임"})   # 적재하지 않는 지목 - 농지 · 임야(10/7 결정, 땅 크기 49%, 자동 88%)
# 브이월드 전체데이터의 시도 코드(2026-09 판). 전남 · 광주는 2026-07 부터 통합 코드 12, 강원 51 · 전북 52. 바뀌면 여기와 운영 문서를 함께 고친다
EXPECTED_REGION_CODES = frozenset({"11", "12", "26", "27", "28", "30", "31", "36", "41", "43", "44", "47", "48", "50", "51", "52"})
# 판마다 행 수 범위(2026-09 판 전국 실측: 건물 14,392,125 · 땅 농지 · 임야 뺀 19,406,867 - 둘 다 약 ±15% 안)
ROW_BOUNDS = {"building": (12_000_000, 17_000_000), "parcel": (16_000_000, 23_000_000)}
MAX_DUP_RATIO = {"building": 0.02, "parcel": 0.01}   # 같은 feature_key 비율(전국 실측 건물 0.60% - 한 건물 여러 도형, 땅 0%)
MAX_MISSING_KEY_RATIO = 0.001   # 고유번호가 19자리 숫자가 아니거나 식별자(건물 A1)가 빈 줄 - 넣지 않고 센다(전국 실측 건물 1줄 · 땅 0줄)
MAX_UNKNOWN_JIMOK_RATIO = 0.01   # 지목을 읽지 못한 땅 - 넣되 센다(전국 실측 0.023%). 넘으면 농지 · 임야 거르기를 믿을 수 없다
# 지목 약식 부호 28개와 정식 이름 - 땅 지번 칸은 대개 약식('203-24전')이지만 약 2,300줄은 정식 이름('12임야' · '5과수원')이다(전국 실측).
# 정식 이름도 부호로 바꿔야 농지 · 임야 거르기를 빠져나가지 않는다. 둘 다 아니면(겹친 글자 · 깨진 글자) 못 읽음으로 센다
JIMOK_CODES = frozenset("전답과목임광염대장학차주창도철제천구유양수공체원종사묘잡")
JIMOK_NAMES = {
    "과수원": "과", "과수": "과", "목장용지": "목", "목장용": "목", "목장": "목", "임야": "임", "광천지": "광", "염전": "염", "대지": "대",
    "공장용지": "장", "공장용": "장", "학교용지": "학", "주차장": "차", "주유소용지": "주", "창고용지": "창", "창고용": "창", "도로": "도",
    "철도용지": "철", "제방": "제", "하천": "천", "구거": "구", "유지": "유", "양어장": "양", "수도용지": "수", "수도용": "수", "공원": "공",
    "체육용지": "체", "유원지": "원", "종교용지": "종", "사적지": "사", "묘지": "묘", "잡종지": "잡",
}
GEO_SOURCE_NOTICE = "국토교통부 공공데이터"   # 화면 출처 표시(GIS건물통합정보 공공누리 1유형 · 연속지적도 CC BY)
_PNU = re.compile(r"^\d{19}$")
_JIMOK = re.compile(r"([가-힣]+)\s*$")
_SOURCE = re.compile(r"^AL_D0(?:10|02)_(\d{2})_(\d{8})(?:\(\d+\))?\.shp$", re.IGNORECASE)
_NOT_A_KEY = frozenset({"", "none", "nan", "null"})


def is_pnu(value: object) -> bool:
    return isinstance(value, str) and bool(_PNU.match(value))


def is_feature_key(value: object) -> bool:
    return isinstance(value, str) and value.strip().lower() not in _NOT_A_KEY


def jibun_address(dong_name: str, pnu: str) -> str:
    """법정동 이름 + 고유번호 → 지번 주소. PNU 19자리 = 법정동코드 10 · 산 여부 1(1 일반, 2 산) · 본번 4 · 부번 4."""

    if not is_pnu(pnu):
        raise ValueError("pnu must be 19 digits")
    main, sub = int(pnu[11:15]), int(pnu[15:19])
    lot = ("산" if pnu[10] == "2" else "") + (f"{main}-{sub}" if sub else str(main))
    # 법정동 이름이 없으면(적재 검사가 막지만) 번지만 - 결과를 버려 위치 찍기로 떨어뜨리지 않는다
    return " ".join(part for part in (" ".join(dong_name.split()), lot) if part)


def jimok_of(label: str | None) -> str | None:
    """연속지적도 지번 칸('203-24전', '930 공', '12임야')의 끝 한글이 지목이다 - 약식 부호 한 글자로 돌려준다. 모르는 낱말은 None(못 읽음)."""

    match = _JIMOK.search(label or "")
    if match is None:
        return None
    word = match.group(1)
    return word if word in JIMOK_CODES else JIMOK_NAMES.get(word)


def keep_parcel(jimok: str | None) -> bool:
    return jimok not in EXCLUDED_JIMOK


@dataclass(frozen=True)
class GeoHit:
    """고른 자리를 품은 건물 · 땅 하나. id 는 이 판의 행 번호(판이 바뀌면 사라진다), 주소와 대표점은 공공데이터 값,
    distance_m 은 고른 자리에서 대표점(도형 중심, 밖이면 도형 위 한 점)까지."""

    kind: GeoKind
    id: int
    pnu: str
    address: str
    latitude: float
    longitude: float
    distance_m: float


def within_gate(hit: GeoHit) -> bool:
    return hit.kind == "building" or hit.distance_m <= PARCEL_GATE_M


def fill_item(hit: GeoHit) -> dict[str, object]:
    return {
        "kind": hit.kind,
        "id": hit.id,
        "pnu": hit.pnu,
        "address": hit.address,
        "latitude": hit.latitude,
        "longitude": hit.longitude,
        "distanceMeters": round(hit.distance_m),
    }


def swap_statements(table: str) -> list[str]:
    """월 갱신 - 새 표(*_next)와 그 색인을 한 트랜잭션 안에서 이름 바꿔치기한다. 읽는 쪽은 옛 표나 새 표 하나만 본다."""

    if table not in TABLES:
        raise ValueError(f"unknown geo table: {table}")
    indexes = ("pkey", "geom_gix", "pnu_ix")
    return (
        [f"ALTER TABLE geo.{table} RENAME TO {table}_old"]
        + [f"ALTER INDEX geo.{table}_{index} RENAME TO {table}_old_{index}" for index in indexes]
        + [f"ALTER TABLE geo.{table}_next RENAME TO {table}"]
        + [f"ALTER INDEX geo.{table}_next_{index} RENAME TO {table}_{index}" for index in indexes]
        + [f"DROP TABLE geo.{table}_old"]
    )


@dataclass(frozen=True)
class SourceFile:
    path: str
    name: str
    code: str
    base_date: str


def parse_source(path: str) -> SourceFile | None:
    name = PurePosixPath(path.replace("\\", "/")).name
    match = _SOURCE.match(name)
    return SourceFile(path, name, match.group(1), match.group(2)) if match else None


def manifest_problems(files: list[str]) -> list[str]:
    """한 데이터셋(건물 또는 땅)의 파일 목록 구조 검사 - 하나라도 있으면 적재하지 않는다(넘길 수 없다, 첫 적재에도 걸린다)."""

    problems: list[str] = []
    parsed = []
    for path in files:
        source = parse_source(path)
        if source is None:
            problems.append(f"unknown file name: {PurePosixPath(path.replace(chr(92), '/')).name}")
        else:
            parsed.append(source)
    codes = {source.code for source in parsed}
    if missing := sorted(EXPECTED_REGION_CODES - codes):
        problems.append(f"missing region codes: {', '.join(missing)}")
    if unexpected := sorted(codes - EXPECTED_REGION_CODES):
        problems.append(f"unexpected region codes: {', '.join(unexpected)}")
    if len(dates := sorted({source.base_date for source in parsed})) > 1:
        problems.append(f"more than one base date: {', '.join(dates)}")
    seen: set[str] = set()
    for source in parsed:
        if source.name.lower() in seen:
            problems.append(f"duplicated file: {source.name}")
        seen.add(source.name.lower())
    return problems


def content_duplicate_problems(digests: dict[str, str]) -> list[str]:
    """파일 이름 → .shp 내용 지문(sha256). 지문이 같은 파일이 둘 이상이면 같은 파일을 두 번 받은 것이다(넘길 수 없다)."""

    by_digest: dict[str, list[str]] = {}
    for name, digest in digests.items():
        by_digest.setdefault(digest, []).append(name)
    return [f"same content: {', '.join(sorted(names))}" for names in by_digest.values() if len(names) > 1]


def quality_problems(table: str, rows: int, distinct_keys: int, *, missing_keys: int, unknown_jimok: int) -> list[str]:
    """적재한 줄의 품질 검사(넘길 수 없다): 같은 식별자 비율 · 식별자 빈 줄 비율 · 지목을 못 읽은 땅 비율."""

    problems: list[str] = []
    dup = 1 - distinct_keys / rows if rows else 0.0
    if dup > MAX_DUP_RATIO[table]:
        problems.append(f"{table}: duplicate feature keys {dup * 100:.1f}% > {MAX_DUP_RATIO[table] * 100:.1f}%")
    read = rows + missing_keys
    if read and missing_keys / read > MAX_MISSING_KEY_RATIO:
        problems.append(f"{table}: rows without a feature key {missing_keys / read * 100:.2f}% > {MAX_MISSING_KEY_RATIO * 100:.2f}%")
    if rows and unknown_jimok / rows > MAX_UNKNOWN_JIMOK_RATIO:
        problems.append(f"{table}: unknown land category {unknown_jimok / rows * 100:.2f}% > {MAX_UNKNOWN_JIMOK_RATIO * 100:.2f}%")
    return problems


def row_count_problems(table: str, rows: int) -> list[str]:
    """행 수 범위 - 판이 실제로 커지거나 줄었을 수 있어 이것만 --accept-row-count-change 로 받아들일 수 있다."""

    low, high = ROW_BOUNDS[table]
    return [] if low <= rows <= high else [f"{table}: {rows} rows is outside {low}..{high}"]
```

- [ ] **Step 4: 통과 확인** - `cd backend && python -m pytest tests/test_geo_reference.py -q` → PASS(11).

- [ ] **Step 5: 변경 확인.**

---

## 과제 3: geo 조회 저장소 - `repositories/geo.py`

**Files:**
- Create: `backend/app/repositories/geo.py`
- Test: `backend/tests/test_geo_repository.py`(가짜 세션), `backend/tests/test_geo_repository_postgis.py`(PostGIS 있을 때만)

**Interfaces:**
- Consumes: `GeoHit` · `jibun_address` · `TABLES`(과제 2)
- Produces: `locate(db, points: Sequence[tuple[float, float]]) -> list[GeoHit | None]`((위도, 경도), 같은 순서), `get_by_ref(db, kind: GeoKind, feature_id: int) -> GeoHit | None`(distance_m = 0)

- [ ] **Step 1: 실패하는 시험 쓰기** - `backend/tests/test_geo_repository.py`

```python
from app.repositories import geo as geo_repository
from app.services.geo_reference import GeoHit


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class FakeSession:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        return FakeResult(self.rows)


def test_locate_sends_every_point_in_one_covers_query_and_keeps_the_order() -> None:
    # 줄: (순번 1부터, 종류, id, PNU, 대표점 위도, 경도, 거리 m, 법정동 이름) - 2번 점은 아무 도형에도 없다, 3번은 법정동 이름이 없다
    session = FakeSession([
        (1, "building", 501, "3611033025103020002", 36.51, 127.31, 4.2, "세종특별자치시 부강면 문곡리"),
        (3, "parcel", 902, "3611010100109300000", 36.49, 127.29, 12.0, None),
    ])
    hits = geo_repository.locate(session, [(36.5, 127.3), (36.6, 127.4), (36.4, 127.2)])
    assert hits == [
        GeoHit("building", 501, "3611033025103020002", "세종특별자치시 부강면 문곡리 302-2", 36.51, 127.31, 4.2),
        None,
        GeoHit("parcel", 902, "3611010100109300000", "930", 36.49, 127.29, 12.0),
    ]
    (sql, params), = session.calls
    assert params == {"ys": [36.5, 36.6, 36.4], "xs": [127.3, 127.4, 127.2]}
    # 경계 위 점도 품는다(ST_Covers), 법정동이 없어도 결과를 버리지 않는다(LEFT JOIN)
    assert "st_covers" in sql.lower() and "st_contains" not in sql.lower() and "left join geo.legal_dong" in sql.lower()


def test_locate_with_no_points_does_not_touch_the_db() -> None:
    session = FakeSession([])
    assert geo_repository.locate(session, []) == [] and session.calls == []


def test_get_by_ref_reads_one_row_by_kind_and_id() -> None:
    session = FakeSession([(501, "3611033025103020002", 36.51, 127.31, "세종특별자치시 부강면 문곡리")])
    hit = geo_repository.get_by_ref(session, "building", 501)
    assert hit == GeoHit("building", 501, "3611033025103020002", "세종특별자치시 부강면 문곡리 302-2", 36.51, 127.31, 0.0)
    assert "geo.building" in session.calls[0][0] and session.calls[0][1] == {"id": 501}
    assert geo_repository.get_by_ref(FakeSession([]), "parcel", 777) is None
```

`backend/tests/test_geo_repository_postgis.py` - 실제 PostGIS(빈 시험 DB)에서만 돈다:

```python
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.repositories import geo as geo_repository

pytestmark = pytest.mark.skipif(os.getenv("RUN_POSTGIS_TESTS") != "1", reason="set RUN_POSTGIS_TESTS=1 and POSTGIS_TEST_DATABASE_URL")

# 0050 과 같은 모양(마이그레이션은 앱 코드를 들여오지 않으므로 여기 다시 적는다)
SHAPE = ("id bigint PRIMARY KEY DEFAULT nextval('geo.feature_id_seq'), feature_key varchar(40) NOT NULL, pnu varchar(19) NOT NULL, "
         "la double precision NOT NULL, lo double precision NOT NULL, rx double precision NOT NULL, ry double precision NOT NULL, geom geometry(Geometry, 5186) NOT NULL")
DDL = [
    "CREATE EXTENSION IF NOT EXISTS postgis", "DROP SCHEMA IF EXISTS geo CASCADE", "CREATE SCHEMA geo", "CREATE SEQUENCE geo.feature_id_seq",
    f"CREATE TABLE geo.building ({SHAPE})", f"CREATE TABLE geo.parcel ({SHAPE}, jimok varchar(4))",
    "CREATE TABLE geo.legal_dong (code varchar(10) PRIMARY KEY, name varchar(100) NOT NULL)",
]
CENTER = "st_transform(st_setsrid(st_makepoint(126.9780, 37.5665), 4326), 5186)"
EDGE = (37.5665, 126.9790)   # (위도, 경도) 시청 동쪽 약 90m, 400m 땅 안 - 아래 둘째 건물 B2 의 북쪽 변 위에 놓는 점


@pytest.fixture
def db():
    engine = create_engine(os.environ["POSTGIS_TEST_DATABASE_URL"])
    with Session(engine) as session:
        for statement in DDL:
            session.execute(text(statement))
        # 서울시청 둘레 TM(EPSG:5186) 정사각형: 건물 20m, 그 건물을 품는 땅 400m
        session.execute(text(f"INSERT INTO geo.building (feature_key, pnu, la, lo, rx, ry, geom) SELECT 'B1', '1114010300100310000', 37.5665, 126.9780, st_x(p), st_y(p), st_expand(p, 10) FROM (SELECT {CENTER} p) c"))
        session.execute(text(f"INSERT INTO geo.parcel (feature_key, pnu, la, lo, rx, ry, geom, jimok) SELECT '1114010300100310000', '1114010300100310000', 37.5665, 126.9780, st_x(p), st_y(p), st_expand(p, 200), '대' FROM (SELECT {CENTER} p) c"))
        # 경계 시험용 둘째 건물 B2: 시험 점(EDGE)을 locate 와 같은 식(4326 점 → st_transform 5186)으로 옮긴 점 e 가 북쪽 변 위에 정확히 놓이게 짠다.
        # 위도만 뽑아 경도를 리터럴로 다시 넣고 왕복 변환하면 y 가 부동소수 오차만큼 변에서 벗어난다 - 같은 입력은 같은 double 이다
        session.execute(
            text("INSERT INTO geo.building (feature_key, pnu, la, lo, rx, ry, geom) SELECT 'B2', '1114010300100310000', :lat, :lng, st_x(e), st_y(e) - 10, st_makeenvelope(st_x(e) - 10, st_y(e) - 20, st_x(e) + 10, st_y(e), 5186) FROM (SELECT st_transform(st_setsrid(st_makepoint(:lng, :lat), 4326), 5186) e) c"),
            {"lat": EDGE[0], "lng": EDGE[1]},
        )
        session.execute(text("INSERT INTO geo.legal_dong VALUES ('1114010300', '서울특별시 중구 태평로1가')"))
        session.commit()
        yield session
        session.execute(text("DROP SCHEMA geo CASCADE"))
        session.commit()


def test_inside_on_the_edge_far_inside_the_parcel_and_at_sea(db) -> None:
    inside, edge, parcel_far, sea = geo_repository.locate(db, [(37.5665, 126.9780), EDGE, (37.5675, 126.9780), (37.0, 125.0)])
    assert (inside.kind, inside.address) == ("building", "서울특별시 중구 태평로1가 31")
    assert edge.kind == "building" and abs(edge.distance_m - 10) < 0.001   # ST_Covers: 변 위의 점도 그 건물(ST_Contains 였다면 400m 땅이 나온다). 대표점은 변에서 10m 남쪽
    assert parcel_far.kind == "parcel" and 100 < parcel_far.distance_m < 120   # 약 111m 북쪽 - 30m 밖이라 주소만
    assert sea is None
    assert geo_repository.get_by_ref(db, "building", inside.id).address == inside.address
    assert geo_repository.get_by_ref(db, "parcel", inside.id) is None   # 같은 id 라도 종류가 다르면 없다
```

- [ ] **Step 2: 실패 확인** - `cd backend && python -m pytest tests/test_geo_repository.py -q` → FAIL(모듈 없음). PostGIS 시험은 건너뜀.

- [ ] **Step 3: 구현** - `backend/app/repositories/geo.py`

```python
"""geo 스키마(건물 · 땅 지번) 읽기 - PostGIS 공간 색인. 받은 좌표(카카오 좌표 · 찍은 좌표)는 질의에만 쓰고 저장 · 로그하지 않는다."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.geo_reference import TABLES, GeoHit, GeoKind, jibun_address

# 6곳을 질의 한 번에: 건물이 품으면(경계 포함) 건물, 아니면 땅. 거리는 대표점까지(30m 판정은 부르는 쪽). 겹치면 id 가 작은 것 하나
LOCATE_SQL = text("""
WITH p AS (
  SELECT i, st_transform(st_setsrid(st_makepoint(x, y), 4326), 5186) AS pt
  FROM unnest(CAST(:xs AS float8[]), CAST(:ys AS float8[])) WITH ORDINALITY AS t(x, y, i)
), b AS (
  SELECT DISTINCT ON (p.i) p.i, 'building' AS kind, g.id, g.pnu, g.la, g.lo, sqrt(power(g.rx - st_x(p.pt), 2) + power(g.ry - st_y(p.pt), 2)) AS d
  FROM p JOIN geo.building g ON st_covers(g.geom, p.pt) ORDER BY p.i, g.id
), q AS (
  SELECT DISTINCT ON (p.i) p.i, 'parcel' AS kind, g.id, g.pnu, g.la, g.lo, sqrt(power(g.rx - st_x(p.pt), 2) + power(g.ry - st_y(p.pt), 2)) AS d
  FROM p JOIN geo.parcel g ON st_covers(g.geom, p.pt)
  WHERE NOT EXISTS (SELECT 1 FROM b WHERE b.i = p.i) ORDER BY p.i, g.id
), hit AS (SELECT * FROM b UNION ALL SELECT * FROM q)
SELECT hit.i, hit.kind, hit.id, hit.pnu, hit.la, hit.lo, hit.d, d.name
FROM hit LEFT JOIN geo.legal_dong d ON d.code = substr(hit.pnu, 1, 10)
ORDER BY hit.i
""")


def _table(kind: GeoKind) -> str:
    if kind not in TABLES:
        raise ValueError(f"unknown geo kind: {kind}")
    return f"geo.{kind}"


def locate(db: Session, points: Sequence[tuple[float, float]]) -> list[GeoHit | None]:
    """(위도, 경도) 마다 품은 건물 · 땅. 없으면 None. 순서는 points 그대로."""

    if not points:
        return []
    rows = db.execute(LOCATE_SQL, {"ys": [lat for lat, _ in points], "xs": [lng for _, lng in points]}).all()
    hits: list[GeoHit | None] = [None] * len(points)
    for index, kind, feature_id, pnu, la, lo, distance, dong_name in rows:
        hits[index - 1] = GeoHit(kind, int(feature_id), pnu, jibun_address(dong_name or "", pnu), float(la), float(lo), float(distance))
    return hits


def get_by_ref(db: Session, kind: GeoKind, feature_id: int) -> GeoHit | None:
    """담을 때 - 화면이 보낸 참조(종류 · id)로 주소와 대표점을 다시 읽는다. 판이 바뀌어 사라졌으면 None."""

    row = db.execute(
        text(f"SELECT g.id, g.pnu, g.la, g.lo, d.name FROM {_table(kind)} g LEFT JOIN geo.legal_dong d ON d.code = substr(g.pnu, 1, 10) WHERE g.id = :id"),
        {"id": feature_id},
    ).first()
    if row is None:
        return None
    found_id, pnu, la, lo, dong_name = row
    return GeoHit(kind, int(found_id), pnu, jibun_address(dong_name or "", pnu), float(la), float(lo), 0.0)
```

- [ ] **Step 4: 통과 확인** - `cd backend && python -m pytest tests/test_geo_repository.py -q` → PASS(3). PostGIS 시험은 과제 14 Step 6.

- [ ] **Step 5: 변경 확인.**

---

## 과제 4: 맞춰 보기 응답에 `fill` 싣기 - 검색 미리 맞춤 · `/api/places/match`

**Files:**
- Modify: `backend/app/schemas/places.py`, `backend/app/services/trips.py:1776-1791`(`_prematch`), `backend/app/api/routes/places.py`(`match_place`)
- Create: `backend/app/services/address_fill.py`
- Test: `backend/tests/test_address_fill.py`, `backend/tests/test_trip_db_service.py`(기존 둘 기대값 · 새 둘), `backend/tests/test_public_places.py`(기존 둘 기대값 · 새 하나)

**Interfaces:**
- Consumes: `geo_repository.locate`(과제 3), `within_gate` · `fill_item`(과제 2), `public_place_service.PlaceMatchInput`
- Produces: `AddressFill { kind, id, pnu, address, latitude, longitude, distanceMeters }`, `PlaceMatchResponse.fill: AddressFill | None = None`,
  `address_fill.with_fill(db, rows, answers) -> list[dict | None]`(match 가 아닌 줄에 fill, 나머지 None, SAVEPOINT 안, 실패하면 모두 None)

- [ ] **Step 1: 실패하는 시험 쓰기** - `backend/tests/test_address_fill.py`

```python
import logging
from contextlib import nullcontext

from app.services import address_fill
from app.services.geo_reference import GeoHit
from app.services.public_places import PlaceMatchInput


class FakeDb:
    """SAVEPOINT 만 흉내 낸다 - 조회는 monkeypatch 한 geo_repository.locate 가 한다. _release_session 이 부르는 close() 도 있다."""

    def begin_nested(self):
        return nullcontext()

    def close(self):
        pass


ROWS = [PlaceMatchInput("오동도", 34.7447, 127.7678, "AT4"), None, PlaceMatchInput("비밀선착장", 34.7448, 127.7679, None), PlaceMatchInput("주차장", 34.70, 127.70, "PK6")]


def answers():
    return [{"result": "match", "places": []}, None, {"result": "none", "places": []}, {"result": "candidates", "places": []}]


def test_only_rows_without_a_match_are_located_in_one_call_and_parcels_need_thirty_meters(monkeypatch) -> None:
    calls = []

    def fake_locate(db, points):
        calls.append(list(points))
        return [GeoHit("parcel", 11, "1213010200100010006", "여수시 수정동 1-6", 34.7447, 127.7677, 2.0),
                GeoHit("parcel", 12, "1213010200100010007", "여수시 수정동 1-7", 34.7001, 127.7001, 31.0)]

    monkeypatch.setattr(address_fill.geo_repository, "locate", fake_locate)
    out = address_fill.with_fill(FakeDb(), ROWS, answers())
    assert calls == [[(34.7448, 127.7679), (34.70, 127.70)]]
    assert out[0]["fill"] is None and out[1] is None
    assert out[2]["fill"] == {"kind": "parcel", "id": 11, "pnu": "1213010200100010006", "address": "여수시 수정동 1-6", "latitude": 34.7447, "longitude": 127.7677, "distanceMeters": 2}
    assert out[3]["fill"] is None   # 땅 중심이 31m - 주소 채움 아님(위치 찍기)


def test_a_failed_lookup_leaves_every_fill_empty_and_logs_only_the_error_name(monkeypatch, caplog) -> None:
    def broken(db, points):
        raise RuntimeError("relation geo.building does not exist")

    monkeypatch.setattr(address_fill.geo_repository, "locate", broken)
    monkeypatch.setattr(address_fill.logger, "handlers", [caplog.handler])
    caplog.set_level(logging.WARNING)
    out = address_fill.with_fill(FakeDb(), ROWS, answers())
    assert [answer and answer["fill"] for answer in out] == [None, None, None, None]
    assert "place_fill_failed" in caplog.text and "RuntimeError" in caplog.text
    for value in ("비밀선착장", "34.7448", "127.7679", "geo.building"):
        assert value not in caplog.text


def test_a_db_without_savepoints_counts_as_a_failed_lookup(monkeypatch) -> None:
    monkeypatch.setattr(address_fill.geo_repository, "locate", lambda db, points: [GeoHit("building", 1, "1213010200100010006", "x", 1.0, 2.0, 0.0)])
    out = address_fill.with_fill(object(), ROWS, answers())   # 가짜 db object() 에는 begin_nested 가 없다
    assert [answer and answer["fill"] for answer in out] == [None, None, None, None]


def test_all_matches_do_not_touch_the_db(monkeypatch) -> None:
    monkeypatch.setattr(address_fill.geo_repository, "locate", lambda db, points: (_ for _ in ()).throw(AssertionError("called")))
    out = address_fill.with_fill(FakeDb(), [ROWS[0]], [{"result": "match", "places": []}])
    assert out == [{"result": "match", "places": [], "fill": None}]
```

`backend/tests/test_trip_db_service.py` - 맞춰 본 답 dict 를 통째로 견주는 기존 단언 둘을 고친다(`fill` 이 늘 붙는다. 가짜 db `object()` 는 SAVEPOINT 가 없어 조회 실패로 처리되고 fill 은 null).

```python
# test_search_places_for_trip_maps_kakao_candidates (159줄 근처)
    assert candidates[0]["publicMatch"] == {"result": "none", "places": [], "fill": None}
# test_search_places_for_trip_sends_every_row_to_one_batch_match (196줄 근처)
    assert [row["publicMatch"] for row in rows] == [{"result": "match", "places": [], "fill": None}, None]
```
(`publicMatch` 를 키로만 읽는 `test_public_places.py:545` · `test_trip_db_routes.py:1097` 은 그대로 통과한다. 프론트 시험의 publicMatch 는 `fill` 이 선택 필드라 그대로 둔다.)

`backend/tests/test_public_places.py` - `/api/places/match` 의 응답 JSON 을 통째로 견주는 기존 단언 둘도 고친다(라우트가 `PlaceMatchResponse` 로 내보내므로 `"fill": null` 이 늘 붙는다). `match` 줄은 조회하지 않고, `none` 줄은 SQLite 에서 PostGIS 질의가 실패하는데 SAVEPOINT 안에서 흡수되므로 둘 다 fill 은 null 이다.

```python
# test_match_route_needs_login_and_answers_in_camel_case (594줄 근처) - 마지막 줄의 닫는 부분만 바뀐다
        "photoUrl": "https://tong.visitkorea.or.kr/a.jpg", "photoLicense": "Type3", "distanceMeters": 0,
    }], "fill": None}
# test_match_never_writes_or_logs_the_values_it_received (612줄 근처)
    assert response.json() == {"result": "none", "places": [], "fill": None}
```

`/match` 가 `fill` 을 싣는 새 시험 하나를 `test_match_never_writes_or_logs_the_values_it_received` 앞에 더한다(파일 위쪽 import 에 `from app.services import address_fill` 와 `from app.services.geo_reference import GeoHit`). PostGIS 질의는 SQLite 에서 돌 수 없어 `locate` 를 바꿔 끼운다:

```python
def test_match_route_adds_the_address_fill_when_nothing_matches(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    # 홈에서 넘어온 장소도 검색 결과와 같은 갈래 - match 가 아니면 건물 · 땅 지번이 fill 로 실린다(조회는 SAVEPOINT 안에서 돈다)
    monkeypatch.setattr(address_fill.geo_repository, "locate",
                        lambda session, points: [GeoHit("building", 31, "1213010200100010006", "여수시 수정동 1-6", 34.7447, 127.7677, 3.0)])
    app.dependency_overrides[get_optional_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: USER
    try:
        response = TestClient(app).post("/api/places/match", json={"name": "오동도 선착장", "latitude": 34.7448, "longitude": 127.7679})
    finally:
        app.dependency_overrides.pop(get_optional_db, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert response.json() == {"result": "none", "places": [], "fill": {
        "kind": "building", "id": 31, "pnu": "1213010200100010006", "address": "여수시 수정동 1-6",
        "latitude": 34.7447, "longitude": 127.7677, "distanceMeters": 3,
    }}
```

`backend/tests/test_trip_db_service.py` 새 시험 둘(파일 위쪽 import 에 `from app.services.geo_reference import GeoHit` 와 `from tests.test_address_fill import FakeDb as SavepointDb` - 이 파일 794줄에 `begin_nested` · `close` 가 없는 모듈 수준 `class FakeDb` 가 따로 있어, 같은 이름으로 가져오면 그 class 문이 가져온 것을 가려 버린다. 그래서 별칭으로 가져온다):

```python
def test_search_places_for_trip_adds_a_fill_to_rows_without_a_match(monkeypatch) -> None:
    class FakeSearchProvider:
        def search_keyword(self, *, query: str, size: int = 10):
            return [kakao_place("1", "오동도", 34.7447, 127.7678), kakao_place("2", "오동도 선착장", 34.7448, 127.7679)]

    monkeypatch.setattr(trip_service.trip_repository, "has_trip_access", lambda db, trip_id, user_id: True, raising=False)
    monkeypatch.setattr(trip_service, "build_kakao_local_client", lambda: FakeSearchProvider())
    monkeypatch.setattr(trip_service.public_place_service, "match_places", lambda db, rows: [{"result": "match", "places": []}, {"result": "none", "places": []}])
    monkeypatch.setattr(trip_service.address_fill.geo_repository, "locate",
                        lambda db, points: [GeoHit("building", 31, "1213010200100010006", "여수시 수정동 1-6", 34.7447, 127.7677, 3.0)])

    rows = trip_service.search_places_for_trip(SavepointDb(), make_user(), trip_handle="7", query="오동도")

    assert rows[0]["publicMatch"]["fill"] is None
    assert (rows[1]["publicMatch"]["fill"]["id"], rows[1]["publicMatch"]["fill"]["address"]) == (31, "여수시 수정동 1-6")


def test_search_places_for_trip_still_answers_when_the_geo_lookup_fails(monkeypatch) -> None:
    class FakeSearchProvider:
        def search_keyword(self, *, query: str, size: int = 10):
            return [kakao_place("2", "오동도 선착장", 34.7448, 127.7679)]

    def broken(db, points):
        raise RuntimeError("no postgis")

    monkeypatch.setattr(trip_service.trip_repository, "has_trip_access", lambda db, trip_id, user_id: True, raising=False)
    monkeypatch.setattr(trip_service, "build_kakao_local_client", lambda: FakeSearchProvider())
    monkeypatch.setattr(trip_service.public_place_service, "match_places", lambda db, rows: [{"result": "none", "places": []}])
    monkeypatch.setattr(trip_service.address_fill.geo_repository, "locate", broken)

    rows = trip_service.search_places_for_trip(SavepointDb(), make_user(), trip_handle="7", query="오동도")

    assert rows[0]["publicMatch"] == {"result": "none", "places": [], "fill": None}
```

- [ ] **Step 2: 실패 확인** - `cd backend && python -m pytest tests/test_address_fill.py tests/test_trip_db_service.py tests/test_public_places.py -q -k "fill or batch_match or maps_kakao or geo or match_route or never_writes"` → FAIL.

- [ ] **Step 3: 스키마** - `backend/app/schemas/places.py`

```python
GeoKind = Literal["building", "parcel"]


class AddressFill(BaseModel):
    """주소 채움(방식1) - 고른 자리를 품은 건물, 또는 땅의 지번 주소와 중심. 국토교통부 공공데이터 값이다(카카오 값 아님).
    id 는 이 판의 행 번호 - 담을 때 kind · id 만 customPlace.geoRef 로 보낸다(판이 바뀌면 404). 주소 · 좌표는 서버가 다시 읽는다."""

    kind: GeoKind
    id: int
    pnu: str
    address: str
    latitude: float
    longitude: float
    distanceMeters: int
```
`PlaceMatchResponse` 에:
```python
    # 방식1: match 가 아니면 그 자리의 건물, 또는 중심이 30m 안인 땅의 지번(없으면 null) - 화면의 '주소 채움'
    fill: AddressFill | None = None
```

- [ ] **Step 4: 서비스** - `backend/app/services/address_fill.py`

```python
"""주소 채움(방식1) - 맞춰 본 줄 가운데 우리 장소 목록과 바로 맞지 않는 줄에 건물 · 땅 지번을 붙인다.
받은 좌표(카카오 좌표 · 찍은 좌표)는 질의에만 쓰고 버린다(데브톡 151505-1 · 151842). 실패해도 검색은 보인다 - fill 이 비고 화면은 위치 찍기로 간다.
조회는 SAVEPOINT 안에서 한다 - Postgres 는 실패한 문장 뒤 같은 트랜잭션의 다음 질의를 모두 막는다."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories import geo as geo_repository
from app.services.geo_reference import fill_item, within_gate
from app.services.public_places import PlaceMatchInput

logger = logging.getLogger(__name__)


def with_fill(db: Session, rows: Sequence[PlaceMatchInput | None], answers: list[dict[str, object] | None]) -> list[dict[str, object] | None]:
    for answer in answers:
        if answer is not None:
            answer["fill"] = None
    wanted = [i for i, (row, answer) in enumerate(zip(rows, answers)) if row is not None and answer is not None and answer["result"] != "match"]
    if not wanted:
        return answers
    try:
        with db.begin_nested():
            hits = geo_repository.locate(db, [(rows[i].latitude, rows[i].longitude) for i in wanted])
    except Exception as error:   # ponytail: 검색에 덧붙이는 정보라 무엇이 터져도 검색은 살린다(저장 · locate 는 SQLAlchemyError 만 잡는다)
        logger.warning("place_fill_failed error=%s", type(error).__name__)
        return answers
    for i, hit in zip(wanted, hits):
        answers[i]["fill"] = fill_item(hit) if hit is not None and within_gate(hit) else None
    return answers
```

- [ ] **Step 5: 미리 맞춤 · 맞춰 보기에 끼우기**

`backend/app/services/trips.py` 위 import 에 `from app.services import address_fill` 를 더하고 `_prematch` 의 `try` 를:
```python
    try:
        answers = public_place_service.match_places(db, rows)
    except Exception as error:
        logger.warning("trip_place_search_prematch_failed error=%s", type(error).__name__)   # 검색어 · 장소 값은 싣지 않는다
        return [None] * len(places)
    return address_fill.with_fill(db, rows, answers)   # 방식1: match 가 아닌 줄에 건물 · 땅 지번(같은 세션, 질의 1번)
```

`backend/app/api/routes/places.py` `match_place` 의 `return` 을:
```python
    answer = public_places.match_place_response(
        db, name=request.name, latitude=request.latitude, longitude=request.longitude, category_code=request.categoryCode,
    )
    row = public_places.PlaceMatchInput(request.name, request.latitude, request.longitude, request.categoryCode)
    (answer,) = address_fill.with_fill(db, [row], [answer])   # 홈에서 넘어온 장소도 검색 결과와 같은 갈래
    return PlaceMatchResponse(**answer)
```
(import: `from app.services import address_fill, place_search, public_places`)

- [ ] **Step 6: 통과 확인** - `cd backend && python -m pytest tests/test_address_fill.py tests/test_trip_db_service.py tests/test_public_places.py tests/test_trip_db_routes.py -q` → PASS.

- [ ] **Step 7: 변경 확인.**

---

## 과제 5: `POST /api/places/locate` - 찍은 자리의 지번(실시간 비교, 저장 없음)

**Files:**
- Modify: `backend/app/schemas/places.py`, `backend/app/services/address_fill.py`, `backend/app/api/routes/places.py`
- Test: `backend/tests/test_places_locate_routes.py`, `backend/tests/test_debug_capture.py`

**Interfaces:**
- Produces: `LocateRequest { latitude, longitude }`(extra forbid, 33~39 · 124~132), `LocateResponse { fill: AddressFill | null, nearCenter: bool }`(fill 은 30m 와 상관없이 품은 건물 · 땅, nearCenter = 건물이거나 땅 중심 30m 안), `address_fill.locate(db, latitude, longitude) -> dict`

- [ ] **Step 1: 실패하는 시험 쓰기** - `backend/tests/test_places_locate_routes.py`

```python
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.db.session import get_optional_db
from app.main import app
from app.models import User
from app.services import address_fill
from app.services.geo_reference import GeoHit
from tests.test_address_fill import FakeDb


def client_as(user):
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_optional_db] = lambda: FakeDb()
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_locate_needs_login() -> None:
    assert client_as(None).post("/api/places/locate", json={"latitude": 34.74, "longitude": 127.76}).status_code == 401


def test_locate_returns_the_parcel_and_says_whether_its_center_is_close(monkeypatch) -> None:
    monkeypatch.setattr(address_fill.geo_repository, "locate",
                        lambda db, points: [GeoHit("parcel", 77, "4215011500100010000", "강릉시 견소동 1", 37.77, 128.95, 85.0)])
    body = client_as(User(id=1, nickname="t", email="t@example.com")).post("/api/places/locate", json={"latitude": 37.7712, "longitude": 128.9480}).json()
    assert body == {"fill": {"kind": "parcel", "id": 77, "pnu": "4215011500100010000", "address": "강릉시 견소동 1", "latitude": 37.77, "longitude": 128.95, "distanceMeters": 85}, "nearCenter": False}


def test_locate_without_any_shape_or_with_a_broken_lookup_is_an_empty_answer(monkeypatch) -> None:
    client = client_as(User(id=1, nickname="t", email="t@example.com"))
    monkeypatch.setattr(address_fill.geo_repository, "locate", lambda db, points: [None])
    assert client.post("/api/places/locate", json={"latitude": 37.0, "longitude": 125.0}).json() == {"fill": None, "nearCenter": False}
    monkeypatch.setattr(address_fill.geo_repository, "locate", lambda db, points: (_ for _ in ()).throw(OperationalError("SELECT", {}, Exception("down"))))
    assert client.post("/api/places/locate", json={"latitude": 37.0, "longitude": 125.0}).json() == {"fill": None, "nearCenter": False}


def test_a_programming_error_in_locate_is_not_hidden_as_an_empty_answer(monkeypatch) -> None:
    # DB 실패만 '지번 없음'과 같은 빈 답이다. 코드 결함은 500 으로 올라가 화면이 '지번을 확인하지 못했어요'를 보인다(코덱스 재검토 MEDIUM 과 같은 원칙).
    # 예외 자체는 TestClient 에 닿지 않는다 - RequestContextMiddleware(core/request_context.py)가 잡아 로그를 남기고 500 JSON 을 직접 보낸다(다시 올리지 않는다). 그래서 pytest.raises 가 아니라 응답을 본다
    monkeypatch.setattr(address_fill.geo_repository, "locate", lambda db, points: (_ for _ in ()).throw(ValueError("bad row")))
    response = client_as(User(id=1, nickname="t", email="t@example.com")).post("/api/places/locate", json={"latitude": 37.0, "longitude": 125.0})
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal Server Error"
    assert "fill" not in response.json()   # 빈 답({"fill": null, "nearCenter": false})으로 숨기지 않았다


def test_locate_refuses_points_outside_korea_and_unknown_fields() -> None:
    client = client_as(User(id=1, nickname="t", email="t@example.com"))
    assert client.post("/api/places/locate", json={"latitude": 40.0, "longitude": 127.0}).status_code == 422
    assert client.post("/api/places/locate", json={"latitude": 37.0, "longitude": 127.0, "name": "카카오 이름"}).status_code == 422
```
화면은 `fill` 이 null 이면 '이름만', `nearCenter` 가 false 이면 '주소만'으로 담는다(0.5). DB 실패(`SQLAlchemyError`)도 null 이다 - '지번 없음'과 같게 둔다(지번을 지어내지 않는다). 그 밖의 오류는 500 이고 화면은 요청 실패(네트워크 · 5xx)로 알린다.
(시험 파일 import 에 `from sqlalchemy.exc import OperationalError` 를 더한다.)

`backend/tests/test_debug_capture.py` - 이미 있는 '장소 경로는 늘 뺀다' 시험의 경로 목록에 `"POST /api/places/locate"` 를 더한다(marker `place` 로 빠지는지 확인).

- [ ] **Step 2: 실패 확인** - `cd backend && python -m pytest tests/test_places_locate_routes.py -q` → FAIL(404 Not Found).

- [ ] **Step 3: 스키마 · 서비스 · 경로**

`backend/app/schemas/places.py`(`from pydantic import BaseModel, ConfigDict, Field`):
```python
class LocateRequest(BaseModel):
    """위치 찍기 - 지도에서 찍은 자리. 서버는 건물 · 땅을 찾는 데만 쓰고 저장 · 로그하지 않는다(데브톡 151842 · 151916-4)."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=33.0, le=39.0)
    longitude: float = Field(ge=124.0, le=132.0)


class LocateResponse(BaseModel):
    """fill = 찍은 자리를 품은 건물 · 땅(30m 와 상관없이). nearCenter = 건물이거나 땅 중심이 30m 안 - 화면이 핀까지 담는다(아니면 주소만)."""

    fill: AddressFill | None = None
    nearCenter: bool = False
```

`backend/app/services/address_fill.py`:
```python
def locate(db: Session, latitude: float, longitude: float) -> dict[str, object]:
    try:
        with db.begin_nested():
            (hit,) = geo_repository.locate(db, [(latitude, longitude)])
    except SQLAlchemyError as error:   # geo 표가 없거나 DB 가 실패 - 지번 없음과 같게. 코드 결함은 올린다
        logger.warning("place_locate_failed error=%s", type(error).__name__)
        return {"fill": None, "nearCenter": False}
    if hit is None:
        return {"fill": None, "nearCenter": False}
    return {"fill": fill_item(hit), "nearCenter": within_gate(hit)}
```

`backend/app/api/routes/places.py`:
```python
@router.post("/locate", response_model=LocateResponse)
def locate_place(
    request: LocateRequest,
    current_user: User | None = Depends(get_current_user),
    db: Session | None = Depends(get_optional_db),
) -> LocateResponse:
    """위치 찍기(방식1) - 찍은 자리를 품은 건물 · 땅의 지번. 받은 좌표는 질의에만 쓴다(debug_capture 도 place 경로는 늘 뺀다)."""

    if current_user is None or db is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return LocateResponse(**address_fill.locate(db, request.latitude, request.longitude))
```

- [ ] **Step 4: 통과 확인** - `cd backend && python -m pytest tests/test_places_locate_routes.py tests/test_debug_capture.py -q` → PASS.

- [ ] **Step 5: 변경 확인.**

---

## 과제 6: 저장 - `customPlace` 는 `name` · `geoRef` 만 · 일정 payload `geoKind`

**Files:**
- Modify: `backend/app/schemas/trip.py`, `backend/app/services/trip_public_places.py`, `backend/app/repositories/trips.py:105-149`(`add_trip_place`), `backend/app/services/trips.py:1420-1442 · 898-918`
- Test: `backend/tests/test_trip_public_places.py`, `backend/tests/test_trip_db_service.py`, `backend/tests/test_geo_repository_postgis.py`(과제 3 파일에 하나 더)

**Interfaces:**
- Consumes: `geo_repository.get_by_ref`(과제 3)
- Produces: `GeoRef { kind: "building" | "parcel", id: int ≥ 1, pin: bool }`(extra forbid), `CustomPlaceInput { name, geoRef?: GeoRef }`(위도 · 경도 · 주소 422),
  `custom_place_columns(name, *, address=None, latitude=None, longitude=None, geo_kind=None, geo_pnu=None)`, `trip_repository.add_trip_place(..., geo_kind=None, geo_pnu=None)`,
  `ItineraryPlace.geoKind: GeoKind | None`,
  오류 `404 "Address reference not found"`, `503 "Address lookup is unavailable"`(둘 다 revision 을 올리기 전)

- [ ] **Step 1: 기존 시험 고치기(3단계가 찍은 좌표를 저장하던 것)** - 데브톡 151842 로 `customPlace` 의 위도 · 경도가 없어진다.
  - `backend/tests/test_trip_public_places.py`
    - `test_custom_place_name_and_point_rules` → 지운다. 이름 규칙(앞뒤 공백 제거 · 100자 허용 · 빈 값 · 공백뿐 · 101자 거부)은 Step 2 의 `test_custom_place_takes_only_a_name_and_an_optional_geo_reference` 가 그대로 옮겨 받는다.
    - `test_custom_add_keeps_the_typed_name_and_only_a_point_the_user_picked`(208줄 근처) → 위도 · 경도를 빼고 이름과 카카오 링크만 남는지 본다(이름 · `address` None · 좌표 None · 카카오 링크 그대로).
    - `test_batch_add_mixes_public_and_custom_places_in_one_revision`(237줄의 customPlace) → `{"customPlace": {"name": "직접 적은 곳"}}` 로, 좌표 단언은 None 으로.
    - `test_a_custom_place_replaces_a_legacy_row_with_the_picked_point`(446줄) → `test_a_custom_place_replaces_a_legacy_row_with_a_geo_reference`(아래 `use_geo` 로 geoRef, 주소 · 중심이 공공데이터 값).
    - `test_renaming_a_custom_row_changes_its_name_itself`(497줄) → 요청에서 위도 · 경도를 빼면 좌표가 None 이라 508줄 `float(row.latitude)` 이 `TypeError` 가 된다. 이름만 바꿔도 주소 · 좌표 · 출처가 그대로인지가 이 시험의 뜻이므로, geoRef(pin true)로 담고 이름을 바꾼 뒤에도 GEO 중심 · 주소 · 출처가 남는지 보게 통째로 바꾼다(`use_geo` · `GEO` 는 Step 2 에서 파일 끝에 정의한다).
      ```python
      def test_renaming_a_custom_row_changes_its_name_itself(db: Session, monkeypatch) -> None:
          owner, _ = seed_trip(db)
          use_geo(monkeypatch)
          trip_service.add_place_to_trip_day(
              db, owner, "7", 1,
              CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "내 장소", "geoRef": {"kind": "parcel", "id": 4401, "pin": True}}),
          )
          (placed,) = saved_places(db)

          shown = patch(db, owner, placed.id, 2, label="새 이름")["days"][1][0]

          (row,) = saved_places(db)
          assert (row.place_name, row.user_label, row.place_origin) == ("새 이름", None, "custom")   # 나만의 장소는 이름 자체가 사용자 이름이다
          assert (row.address, row.geo_kind, row.geo_pnu) == (GEO.address, "parcel", GEO.pnu)   # 이름만 바뀐다 - 주소 · 출처는 그대로
          assert (float(row.latitude), float(row.longitude)) == (GEO.latitude, GEO.longitude)   # 좌표도 GEO 중심 그대로
          assert shown["label"] == "새 이름"
      ```
  - `backend/tests/test_trip_db_service.py:1910` 의 `customPlace={"name": "Cafe stop", "latitude": 38.1, "longitude": 128.6}` → `customPlace={"name": "Cafe stop"}`, 그 시험의 좌표 단언은 None 으로.

- [ ] **Step 2: 실패하는 새 시험 쓰기** - `backend/tests/test_trip_public_places.py` 끝에(같은 파일의 `seed_trip` · `saved_places` · `revision_of` · `public_place` · `TOUR_REF` 를 쓴다. `text` 는 `from sqlalchemy import text` 를 import 줄에 더한다)

```python
from app.services.geo_reference import GeoHit

GEO = GeoHit("parcel", 4401, "1213010200100010006", "전남광주통합특별시 여수시 수정동 1-6", 34.744764, 127.767783, 0.0)


def use_geo(monkeypatch, *, found=True, error: Exception | None = None) -> list[tuple]:
    calls: list[tuple] = []

    def get_by_ref(db, kind, feature_id):
        calls.append((kind, feature_id))
        if error is not None:
            raise error
        return GEO if found else None

    monkeypatch.setattr(trip_service.geo_repository, "get_by_ref", get_by_ref)
    return calls


def test_a_geo_reference_with_a_pin_fills_the_address_and_the_public_center(db: Session, monkeypatch) -> None:
    owner, _ = seed_trip(db)
    calls = use_geo(monkeypatch)
    payload = trip_service.add_place_to_trip_day(
        db, owner, "7", 1,
        CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "오동도", "geoRef": {"kind": "parcel", "id": 4401, "pin": True}}, kakaoPlaceId="777"),
    )
    (row,) = saved_places(db)
    assert calls == [("parcel", 4401)]
    assert (row.place_name, row.place_origin, row.address, row.geo_kind, row.geo_pnu) == ("오동도", "custom", GEO.address, "parcel", GEO.pnu)
    assert (float(row.latitude), float(row.longitude)) == (GEO.latitude, GEO.longitude)
    assert payload["days"][1][0]["geoKind"] == "parcel" and payload["days"][1][0]["meta"] == GEO.address


def test_a_geo_reference_without_a_pin_keeps_only_the_address(db: Session, monkeypatch) -> None:
    owner, _ = seed_trip(db)
    use_geo(monkeypatch)
    trip_service.add_place_to_trip_day(
        db, owner, "7", 1,
        CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "넓은 공원", "geoRef": {"kind": "parcel", "id": 4401, "pin": False}}),
    )
    (row,) = saved_places(db)
    assert (row.address, row.latitude, row.longitude, row.geo_kind) == (GEO.address, None, None, "parcel")


def test_custom_place_takes_only_a_name_and_an_optional_geo_reference() -> None:
    # 옛 test_custom_place_name_and_point_rules 의 이름 규칙을 옮겨 왔다(좌표 규칙은 아래 거부 시험이 대신한다)
    assert CustomPlaceInput(name="  내 장소  ").name == "내 장소"   # 앞뒤 공백은 뺀다
    assert CustomPlaceInput(name="가" * 100).name == "가" * 100
    for bad_name in ("", "   ", "가" * 101):
        with pytest.raises(ValidationError):
            CustomPlaceInput(name=bad_name)
    assert CustomPlaceInput(name="내 장소").geoRef is None
    ref = CustomPlaceInput(name="오동도", geoRef={"kind": "building", "id": 7, "pin": False}).geoRef
    assert (ref.kind, ref.id, ref.pin) == ("building", 7, False)


def test_refuses_raw_coordinates_in_a_custom_place(db: Session, api: Callable[[User], TestClient]) -> None:
    # 데브톡 151842: 지도에서 찍은 좌표는 저장 · 활용 불가 - 서버가 받지 않는다(코덱스 HIGH)
    for bad in ({"name": "a", "latitude": 34.7, "longitude": 127.7}, {"name": "a", "address": "카카오 주소"},
                {"name": "a", "geoRef": {"kind": "parcel", "id": 1, "pin": True, "latitude": 34.7}},
                {"name": "a", "geoRef": {"kind": "road", "id": 1, "pin": True}}, {"name": "a", "geoRef": {"kind": "parcel", "id": 0, "pin": True}}):
        with pytest.raises(ValidationError):
            CustomPlaceInput(**bad)

    # 요청으로도 막힌다 - 조작한 요청이 좌표를 실어 보내면 422, 앞에 정상 장소가 있어도 아무것도 쓰지 않고 revision 도 그대로
    owner, _ = seed_trip(db)
    client = api(owner)
    pinned = {"name": "찍은 곳", "latitude": 34.7, "longitude": 127.7}
    single = client.post("/api/trips/7/days/1/places", json={"expectedRevision": 1, "customPlace": pinned})
    batch = client.post(
        "/api/trips/7/days/1/places/batch",
        json={"expectedRevision": 1, "places": [{"customPlace": {"name": "이름만"}}, {"customPlace": pinned}]},
    )
    for response in (single, batch):
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert {error["type"] for error in errors} == {"extra_forbidden"}
        assert sorted(error["loc"][-1] for error in errors) == ["latitude", "longitude"]
    assert saved_places(db) == [] and revision_of(db) == 1


def test_a_geo_reference_gone_after_the_monthly_refresh_is_404_and_writes_nothing(db: Session, monkeypatch) -> None:
    owner, _ = seed_trip(db)
    use_geo(monkeypatch, found=False)
    with pytest.raises(trip_service.TripServiceError) as missing:
        trip_service.add_places_to_trip_day(
            db, owner, "7", 1,
            CreateTripPlacesRequest(expectedRevision=1, places=[{"customPlace": {"name": "a"}}, {"customPlace": {"name": "오동도", "geoRef": {"kind": "parcel", "id": 4401, "pin": True}}}]),
        )
    assert (missing.value.status_code, missing.value.detail) == (404, "Address reference not found")
    assert saved_places(db) == [] and revision_of(db) == 1


def test_a_missing_geo_table_is_503_writes_nothing_and_leaves_the_session_usable(db: Session, monkeypatch, caplog) -> None:
    # 실제 실패: 이 SQLite 시험 DB 에는 geo 표가 없다(적재 전 · 마이그레이션 직후와 같다). 가짜를 쓰지 않는다(코덱스 재검토 MEDIUM)
    owner, _ = seed_trip(db)
    monkeypatch.setattr(trip_service.logger, "handlers", [caplog.handler])   # uvicorn.error 로그는 앱이 따로 모아 두고 위로 안 올린다(propagate 끔) - 이 시험 동안만 caplog 로
    caplog.set_level(logging.WARNING)
    with pytest.raises(trip_service.TripServiceError) as unavailable:
        trip_service.add_place_to_trip_day(
            db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "오동도", "geoRef": {"kind": "parcel", "id": 4401, "pin": True}}),
        )
    assert (unavailable.value.status_code, unavailable.value.detail) == (503, "Address lookup is unavailable")
    assert db.execute(text("SELECT 1")).scalar() == 1   # SAVEPOINT 로 되돌려 세션이 살아 있다
    assert saved_places(db) == [] and revision_of(db) == 1
    assert "geo.parcel" not in caplog.text and "trip_place_geo_ref_failed error=OperationalError" in caplog.text


def test_a_programming_error_in_the_geo_lookup_is_not_hidden_as_503(db: Session, monkeypatch) -> None:
    owner, _ = seed_trip(db)
    use_geo(monkeypatch, error=ValueError("pnu must be 19 digits"))
    with pytest.raises(ValueError):
        trip_service.add_place_to_trip_day(
            db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "오동도", "geoRef": {"kind": "parcel", "id": 4401, "pin": True}}),
        )


def test_switching_a_geo_custom_place_to_a_public_place_clears_the_geo_columns(db: Session, monkeypatch) -> None:
    owner, _ = seed_trip(db)
    use_geo(monkeypatch)
    db.add(public_place())
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "오동도", "geoRef": {"kind": "parcel", "id": 4401, "pin": True}}))
    (row,) = saved_places(db)
    trip_service.update_trip_place(db, owner, "7", row.id, UpdateTripPlaceRequest(expectedRevision=2, publicPlace=TOUR_REF))
    db.refresh(row)
    assert (row.place_origin, row.geo_kind, row.geo_pnu) == ("public", None, None)
```

`backend/tests/test_trip_db_service.py` 의 `test_repository_add_trip_place_accepts_kakao_metadata`(2377줄) 바로 뒤에 - 서비스 시험의 `add_trip_place` 스텁은 `**kwargs` 라 인자 이름이 틀려도 못 잡는다. 진짜 저장소를 부른다:
```python
def test_repository_add_trip_place_stores_the_geo_reference_and_defaults_it_to_none(sqlite_db_session) -> None:
    user = UserModel(email="owner-geo@example.com", password_hash="hashed", nickname="Owner", onboarding_completed=True)
    sqlite_db_session.add(user)
    sqlite_db_session.flush()
    repository = trip_service.trip_repository
    trip = repository.create_trip(
        sqlite_db_session, owner_id=user.id, title="여수", start_date=date(2026, 10, 10), end_date=date(2026, 10, 10),
        status="draft", region="여수", travel_area_id=None, participant_count=1, description=None,
    )
    trip_day = repository.add_trip_day(sqlite_db_session, trip_id=trip.id, day_number=1, date_value=date(2026, 10, 10))

    geo = repository.add_trip_place(
        sqlite_db_session, trip_day_id=trip_day.id, place_name="오동도", visit_time=None, order_num=1, memo=None,
        place_origin="custom", geo_kind="parcel", geo_pnu="1213010200100010006",
    )
    plain = repository.add_trip_place(
        sqlite_db_session, trip_day_id=trip_day.id, place_name="이름만", visit_time=None, order_num=2, memo=None, place_origin="custom",
    )
    sqlite_db_session.commit()

    assert (geo.geo_kind, geo.geo_pnu) == ("parcel", "1213010200100010006")
    assert (plain.geo_kind, plain.geo_pnu) == (None, None)
```

`backend/tests/test_geo_repository_postgis.py` 끝에(과제 3 의 `db` 픽스처) - SQLite 는 실패한 문장 뒤에도 트랜잭션을 막지 않아 위 SQLite 시험으로는 SAVEPOINT 가 하는 일을 볼 수 없다. Postgres 에서 본다:
```python
def test_a_failed_geo_lookup_on_postgres_rolls_back_only_to_the_savepoint(db) -> None:
    # Postgres 는 실패한 문장 뒤 같은 트랜잭션의 질의를 모두 막는다(InFailedSqlTransaction). SAVEPOINT 가 저장 · locate 의 요청을 살리는지 본다
    from app.schemas.trip import GeoRef
    from app.services import address_fill
    from app.services import trips as trip_service

    db.execute(text("DROP SCHEMA geo CASCADE"))   # 이 트랜잭션 안에서만 - 아래 rollback 이 되돌린다
    with pytest.raises(trip_service.TripServiceError) as unavailable:
        trip_service._geo_ref_hit(db, GeoRef(kind="parcel", id=1, pin=True))
    assert unavailable.value.status_code == 503
    assert address_fill.locate(db, 37.5665, 126.9780) == {"fill": None, "nearCenter": False}
    assert db.execute(text("SELECT 1")).scalar() == 1   # 바깥 트랜잭션이 아직 쓸 수 있다
    db.rollback()
```

- [ ] **Step 3: 실패 확인** - `cd backend && python -m pytest tests/test_trip_public_places.py tests/test_trip_db_service.py -q` → FAIL(`geoRef` 는 모르는 필드 422 · 위도 · 경도는 아직 받음 · `geo_repository` 없음 · 저장소 `add_trip_place` 가 `geo_kind` 를 모름). Postgres 시험은 과제 14 Step 6 에서 돈다.

- [ ] **Step 4: 스키마** - `backend/app/schemas/trip.py`

```python
from app.schemas.places import GeoKind, PlaceMatchResponse, PublicPlaceCategory, PublicPlaceItem


class GeoRef(BaseModel):
    """주소 채움 참조 - 건물 · 땅의 종류와 이 판의 id, 핀까지 담을지(pin). 주소 · 좌표는 서버가 geo 표에서 다시 읽는다.
    pin 이 false 면(넓은 땅) 주소만 담는다. 어느 쪽이든 저장되는 좌표는 우리 표의 중심뿐이다."""

    model_config = ConfigDict(extra="forbid")

    kind: GeoKind
    id: int = Field(ge=1)
    pin: bool


class CustomPlaceInput(BaseModel):
    """나만의 장소 - 사용자가 쓴 이름과 (선택) 주소 채움 참조. 위도 · 경도 · 주소는 받지 않는다(422) -
    지도에서 찍은 좌표는 저장 · 활용 불가(데브톡 151842)라, 찍은 자리는 화면이 geoRef 로 바꿔 보낸다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    geoRef: GeoRef | None = None
```
(`validate_point` 를 지운다.) `ItineraryPlace` 의 `needsConfirmation` 위에 `geoKind: GeoKind | None = None`.

- [ ] **Step 5: 열 값** - `backend/app/services/trip_public_places.py`

`public_place_columns` 반환 dict 에 `"geo_kind": None, "geo_pnu": None,` 을 더하고 `custom_place_columns` 를:
```python
def custom_place_columns(
    name: str, *, address: str | None = None, latitude: float | None = None, longitude: float | None = None,
    geo_kind: str | None = None, geo_pnu: str | None = None,
) -> dict[str, object]:
    """나만의 장소 → trip_places 열. 사용자가 쓴 이름, 주소 채움이면 건물 · 땅 지번(공공데이터)과 그 출처, 좌표는 그 중심(pin 일 때)뿐."""

    return {
        "place_name": name,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
        "category_group_code": None,
        "category_group_name": None,
        "place_origin": "custom",
        "public_source": None,
        "public_source_id": None,
        "public_category": None,
        "photo_url": None,
        "photo_license": None,
        "user_label": None,
        "geo_kind": geo_kind,
        "geo_pnu": geo_pnu,
    }
```
부르는 곳 둘(`_value_columns` 의 custom · `update_trip_place` 의 예전 행 이름 바꾸기 `custom_place_columns(label, None, None)` → `custom_place_columns(label)`)을 같이 고친다.

- [ ] **Step 6: 저장 경로** - `backend/app/repositories/trips.py` · `backend/app/services/trips.py`

저장소 먼저. `add_trip_place`(105줄)는 명시 키워드 인자만 받는다(`**kwargs` 없음). 서비스가 열 dict 를 `**columns` 로 펼치므로(`services/trips.py` 1473 · 1493줄) 여기를 안 고치면 Step 5 의 `geo_kind` · `geo_pnu` 때문에 공공 · 나만의 장소, 단건 · 묶음 가릴 것 없이 모든 담기가 `TypeError: add_trip_place() got an unexpected keyword argument 'geo_kind'` 로 무너진다. `backend/app/repositories/trips.py` 의 인자 목록 끝(`user_label: str | None = None,` 다음 줄)에:
```python
    geo_kind: str | None = None,
    geo_pnu: str | None = None,
```
`TripPlace(` 호출 끝(`user_label=user_label,` 다음 줄)에:
```python
        geo_kind=geo_kind,
        geo_pnu=geo_pnu,
```
(고치기 경로 `update_trip_place` 는 `setattr` 이라 손대지 않는다.)

서비스. `backend/app/services/trips.py` 의 import 에 `from app.repositories import geo as geo_repository`. `PUBLIC_PLACE_NOT_FOUND` 아래:
```python
GEO_REF_NOT_FOUND = "Address reference not found"
GEO_LOOKUP_UNAVAILABLE = "Address lookup is unavailable"


def _geo_ref_hit(db: Session, ref) -> GeoHit:
    """담을 때 지번 참조를 다시 읽는다 - SAVEPOINT 안에서(실패가 이 요청의 트랜잭션을 막지 않게). revision 을 올리기 전에 부른다."""

    try:
        with db.begin_nested():
            hit = geo_repository.get_by_ref(db, ref.kind, ref.id)
    except SQLAlchemyError as error:   # geo 표가 없거나 DB 가 실패 - 값은 싣지 않는다. 그 밖의 오류(코드 결함)는 숨기지 않고 올린다
        logger.warning("trip_place_geo_ref_failed error=%s", type(error).__name__)
        raise TripServiceError(503, GEO_LOOKUP_UNAVAILABLE) from None
    if hit is None:
        raise TripServiceError(404, GEO_REF_NOT_FOUND)   # 월 갱신으로 바뀐 판 - 화면이 다시 찾게 한다
    return hit
```
(`from app.services.geo_reference import GeoHit` 와 `from sqlalchemy.exc import SQLAlchemyError` 를 import 에 더한다 - `trips.py` 에는 `SQLAlchemyError` 가 아직 없다. `from sqlalchemy.orm import Session` 위에 둔다)
`_value_columns` 의 custom 갈래:
```python
    if custom is not None:
        if custom.geoRef is None:
            return trip_public_places.custom_place_columns(custom.name)
        hit = _geo_ref_hit(db, custom.geoRef)
        point = {"latitude": hit.latitude, "longitude": hit.longitude} if custom.geoRef.pin else {}
        return trip_public_places.custom_place_columns(custom.name, address=hit.address, geo_kind=hit.kind, geo_pnu=hit.pnu, **point)
```
일정 payload(`"needsConfirmation": …` 위)에 `"geoKind": place.geo_kind,`.

- [ ] **Step 7: 통과 확인** - `cd backend && python -m pytest tests/test_trip_public_places.py tests/test_trip_db_service.py tests/test_trip_db_routes.py tests/test_trip_auth_edge_cases.py -q` → PASS(기존 시험 포함).

- [ ] **Step 8: 변경 확인.**

---

## 과제 7: 카카오 연결 재사용 · 카카오 오류 로그에 값 없음 · 세션 재사용 명시

**Files:**
- Modify: `backend/app/services/kakao_local.py:131-140 · 193 · 224`, `backend/app/services/trips.py:1747`, `backend/app/services/place_search.py:34 · 111 · 115 · 144`, `backend/app/main.py:37-46`, `backend/app/db/session.py:25-26`
- Test: `backend/tests/test_kakao_local.py`, `backend/tests/test_place_search.py`, `backend/tests/test_trip_db_service.py`, `backend/tests/test_db_session.py`(새)

**Interfaces:**
- Produces: `kakao_local.shared_http_get(url, **kwargs) -> httpx.Response`, `kakao_local.close_shared_http() -> None`, `KakaoLocalClient(http_get=…)` 기본값 `shared_http_get`. 카카오 HTTP 오류는 `KakaoLocalConfigurationError("Kakao local request failed: <예외 이름>")`.

- [ ] **Step 1: 실패하는 시험 쓰기**

`backend/tests/test_kakao_local.py`:
```python
KEYED = type("Settings", (), {"kakao_local_enabled": True, "kakao_local_rest_api_key": "test", "kakao_local_timeout_seconds": 5})()


def test_the_default_client_reuses_one_http_connection_pool() -> None:
    # 실측(10/7): 새 연결 28ms → 재사용 7ms. 검색마다 TLS 를 다시 맺지 않는다
    client = kakao_local.KakaoLocalClient(settings_obj=KEYED)
    assert client._http_get is kakao_local.shared_http_get
    kakao_local.close_shared_http()
    kakao_local.close_shared_http()   # 두 번 닫아도 괜찮다


def test_a_kakao_http_error_does_not_carry_the_url_query_or_coordinates() -> None:
    request = httpx.Request("GET", "https://dapi.kakao.com/v2/local/search/keyword.json?query=%EB%B9%84%EB%B0%80&x=127.7&y=34.7")

    def failing_get(url, **kwargs):
        raise httpx.HTTPStatusError("400 Bad Request for url " + str(request.url), request=request, response=httpx.Response(400, request=request))

    client = kakao_local.KakaoLocalClient(settings_obj=KEYED, http_get=failing_get)
    with pytest.raises(kakao_local.KakaoLocalConfigurationError) as raised:
        client.search_keyword(query="비밀")
    assert str(raised.value) == "Kakao local request failed: HTTPStatusError"
```

(`test_kakao_local.py` 위쪽 import 에 `import pytest` 와 `from app.services import kakao_local` 를 더한다.)

`backend/tests/test_trip_db_service.py`(카카오 실패 로그):
```python
def test_search_places_for_trip_logs_only_the_error_name_when_kakao_fails(monkeypatch, caplog) -> None:
    class FailingProvider:
        def search_keyword(self, *, query: str, size: int = 10):
            raise RuntimeError("GET https://dapi.kakao.com/...?query=비밀검색어 failed")

    monkeypatch.setattr(trip_service.trip_repository, "has_trip_access", lambda db, trip_id, user_id: True, raising=False)
    monkeypatch.setattr(trip_service, "build_kakao_local_client", lambda: FailingProvider())
    monkeypatch.setattr(trip_service.logger, "handlers", [caplog.handler])
    caplog.set_level(logging.WARNING)
    assert trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="비밀검색어") == []
    assert "trip_place_search_failed" in caplog.text and "RuntimeError" in caplog.text
    assert "비밀검색어" not in caplog.text and "dapi.kakao.com" not in caplog.text and "Traceback" not in caplog.text
```
`backend/tests/test_place_search.py`:
```python
def test_failed_kakao_calls_log_only_the_error_name(monkeypatch, caplog) -> None:
    class Leaky:
        def search_address(self, *, query, size):
            raise RuntimeError(f"GET https://dapi.kakao.com/v2/local/search/address.json?query={query}")

        def search_keyword(self, *, query, size):
            raise RuntimeError(f"GET https://dapi.kakao.com/v2/local/search/keyword.json?query={query}")

        def search_category(self, **kwargs):
            raise RuntimeError(f"GET https://dapi.kakao.com/v2/local/search/category.json?x={kwargs['x']}&y={kwargs['y']}")

    monkeypatch.setattr(place_search.logger, "handlers", [caplog.handler])
    caplog.set_level(logging.WARNING)
    assert place_search.search_places("비밀동", Leaky()) == []
    assert place_search.nearby_places(latitude=34.7447, longitude=127.7678, category="FD6", provider=Leaky()) == []
    for name in ("place_search_area_failed", "place_search_keyword_failed", "place_search_nearby_failed"):
        assert name in caplog.text
    for leaked in ("비밀동", "dapi.kakao.com", "34.7447", "127.7678", "Traceback"):
        assert leaked not in caplog.text


def test_an_unknown_region_is_logged_without_the_kakao_address(caplog) -> None:
    # 카카오 주소의 첫 낱말도 카카오 값이다(Global Constraints) - 운영 JSON 로거가 `token=` 값을 가려 주지만 그 우연에 기대지 않는다
    caplog.set_level(logging.INFO)
    place_search.search_places("어딘가", FakeKakao(places=[place("어딘가", "대구경북통합특별시 안동시 1")]))
    assert "place_search_unknown_region" in caplog.text   # 지역을 못 읽었다는 사실은 남기고
    assert "대구경북통합특별시" not in caplog.text and "안동시" not in caplog.text   # 카카오 주소 낱말은 남기지 않는다
```
(위쪽 `from datetime import datetime` 앞에 `import logging` 을 더한다 - 지금 파일에는 없다.)

`backend/tests/test_db_session.py`(새):
```python
from dataclasses import replace

from app.db import session as session_module


def test_a_closed_session_stays_usable_for_the_search_prematch(monkeypatch) -> None:
    # _release_session 으로 놓은 세션을 미리 맞춤 · 주소 채움이 다시 쓴다 - SQLAlchemy 기본값에 기대지 않고 명시한다(코덱스 MEDIUM)
    # 진짜 get_session_factory() 는 DATABASE_URL 이 있어야 돈다(없으면 RuntimeError) - Settings 는 frozen 이라 replace 로 연결을 맺지 않는
    # sqlite 주소를 끼워 환경과 무관하게 하고, lru_cache 는 앞뒤로 비워 다른 시험에 이 팩토리가 남지 않게 한다
    monkeypatch.setattr(session_module, "settings", replace(session_module.settings, database_url="sqlite://"))
    session_module.get_engine.cache_clear()
    session_module.get_session_factory.cache_clear()
    try:
        assert session_module.get_session_factory().kw["close_resets_only"] is True
    finally:
        session_module.get_session_factory.cache_clear()
        session_module.get_engine.cache_clear()
```

- [ ] **Step 2: 실패 확인** - `cd backend && python -m pytest tests/test_kakao_local.py tests/test_place_search.py tests/test_trip_db_service.py tests/test_db_session.py -q -k "reuses or url or error_name or closed_session or logs or unknown_region"` → FAIL(`test_db_session.py` 는 `KeyError: 'close_resets_only'` 로, 미인식 지역 시험은 로그에 `대구경북통합특별시` 가 있어서).

- [ ] **Step 3: 구현**

`backend/app/services/kakao_local.py`:
```python
import threading

_shared_lock = threading.Lock()
_shared_client: httpx.Client | None = None


def shared_http_get(url: str, **kwargs) -> httpx.Response:
    """카카오 로컬 호출이 함께 쓰는 연결 풀(keep-alive) - 검색마다 TCP · TLS 를 새로 맺지 않는다. httpx.Client 는 스레드 간에 같이 써도 된다."""

    global _shared_client
    if _shared_client is None:
        with _shared_lock:
            if _shared_client is None:
                _shared_client = httpx.Client()
    return _shared_client.get(url, **kwargs)


def close_shared_http() -> None:
    global _shared_client
    with _shared_lock:
        client, _shared_client = _shared_client, None
    if client is not None:
        client.close()
```
`KakaoLocalClient.__init__` 의 `http_get: callable = httpx.get` → `shared_http_get`. 두 곳의 `raise KakaoLocalConfigurationError(str(exc))` → `raise KakaoLocalConfigurationError(f"Kakao local request failed: {type(exc).__name__}") from None`(예외 문자열에는 요청 URL · 검색어 · 좌표가 들어 있다).
`backend/app/services/trips.py:1747` `logger.warning("trip_place_search_failed trip=%s", trip_handle, exc_info=True)` → `logger.warning("trip_place_search_failed trip=%s error=%s", trip_handle, type(error).__name__)`(`except Exception as error:`).
`backend/app/services/place_search.py` - 카카오 값이나 오류 문자열을 로그에 싣는 네 곳(34 · 111 · 115 · 144줄)을 고친다:
```python
# 34줄 resolve_region - 미인식 지역의 첫 낱말은 카카오 주소 값이다. 값 없이 사실만 남긴다
        logger.info("place_search_unknown_region")
# 110-111줄 search_places(구역 검색)
        except Exception as error:   # noqa: BLE001 - 장소 검색이 안 돼도 키워드 결과는 쓴다
            logger.warning("place_search_area_failed error=%s", type(error).__name__)
# 114-115줄 search_places(키워드 검색)
    except Exception as error:   # noqa: BLE001
        logger.warning("place_search_keyword_failed error=%s", type(error).__name__)
# 143-144줄 nearby_places
    except Exception as error:  # noqa: BLE001 - 이 근처가 안 돼도 카드의 나머지는 쓴다
        logger.warning("place_search_nearby_failed error=%s", type(error).__name__)
```
`backend/app/main.py` `lifespan` 의 `finally` 끝에 `close_shared_http()`(`from app.services.kakao_local import close_shared_http`).
`backend/app/db/session.py`: `return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False, close_resets_only=True)`.

- [ ] **Step 4: 통과 확인** - `cd backend && python -m pytest tests/test_kakao_local.py tests/test_place_search.py tests/test_kakao_local_candidate_smoke.py tests/test_trip_db_service.py tests/test_db_session.py -q` → PASS.

- [ ] **Step 5: 변경 확인.**

---

## 과제 8: 월 적재 도구 `geo_load.py` · `geo-loader` 이미지 단계

**Files:**
- Create: `backend/scripts/geo_load.py`, `backend/requirements-geo.txt`
- Modify: `backend/Dockerfile`(`final` 앞에 `geo-loader` 단계)
- Test: `backend/tests/test_geo_load_files.py`(런타임 의존성만), `backend/tests/test_geo_load_postgis.py`(PostGIS + 적재 의존성 있을 때만)

**Interfaces:**
- Consumes: `is_pnu` · `is_feature_key` · `jimok_of` · `keep_parcel` · `swap_statements` · `manifest_problems` · `content_duplicate_problems` · `quality_problems` · `row_count_problems`(과제 2)
- Produces: CLI `python scripts/geo_load.py --buildings DIR --parcels DIR [--accept-row-count-change]`. **구조 검사(파일 이름 · 시도 · 기준일 · 같은 파일 · 같은 내용 · 좌표계 · 중복률 · 고유번호나 식별자가 없거나 잘못된 줄 · 지목 못 읽음 · 법정동 빠짐)는 어떤 옵션으로도 넘기지 못한다.** 이름 검사가 먼저다 - 엉뚱한 파일 목록이면 파일을 열지도, DB 에 붙지도 않는다. `--accept-row-count-change` 는 행 수 범위만 받아들인다(코덱스 재검토 HIGH).
  함수 `discover(root: Path) -> list[str]`, `base_date(paths) -> str | None`, `file_digest(path) -> str`, `source_crs_problem(path) -> str | None`,
  `exclusive_load(connect)`(연결 하나를 적재 끝까지 쥐고 advisory lock 을 건다 - `LoadBusy` · `LockLost`), `load(cur, table, paths, dongs, prefixes) -> tuple[int, int, int, int]`(넣은 줄 · 고유번호나 식별자가 없거나 잘못돼 뺀 줄 · 지목 못 읽은 줄 · 도형이 없거나 비어서 뺀 줄),
  `run(buildings, parcels, *, connect, accept_row_count_change) -> int`. 종료 코드: 0 바꿈, 2 파일 없음, 3 구조 · 품질 검사, 4 법정동 빠짐, 5 다른 적재가 도는 중, 6 바꿔치기 잠금 실패, 7 잠금을 잃음, 8 행 수 범위(받아들이지 않음).

- [ ] **Step 1: 실패하는 시험 쓰기**

`backend/tests/test_geo_load_files.py`:
```python
import zipfile
from pathlib import Path

from scripts.geo_load import base_date, discover, file_digest, run


def test_extracted_folders_win_over_their_zip_and_lone_zips_are_read_inside(tmp_path: Path) -> None:
    (tmp_path / "AL_D010_11_20260909").mkdir()
    for name in ("AL_D010_11_20260909.shp", "AL_D010_11_20260909(2).shp"):
        (tmp_path / "AL_D010_11_20260909" / name).write_bytes(name.encode())
    for code in ("11", "26"):
        with zipfile.ZipFile(tmp_path / f"AL_D010_{code}_20260909.zip", "w") as zf:
            zf.writestr(f"AL_D010_{code}_20260909.shp", code.encode())
    found = discover(tmp_path)
    assert [Path(p).name for p in found if not p.startswith("/vsizip/")] == ["AL_D010_11_20260909(2).shp", "AL_D010_11_20260909.shp"]
    assert [p for p in found if p.startswith("/vsizip/")] == [f"/vsizip/{(tmp_path / 'AL_D010_26_20260909.zip').as_posix()}/AL_D010_26_20260909.shp"]


def test_the_digest_reads_the_shp_bytes_from_a_folder_or_inside_a_zip(tmp_path: Path) -> None:
    (tmp_path / "a.shp").write_bytes(b"same")
    with zipfile.ZipFile(tmp_path / "b.zip", "w") as zf:
        zf.writestr("b.shp", b"same")
    assert file_digest(str(tmp_path / "a.shp")) == file_digest(f"/vsizip/{(tmp_path / 'b.zip').as_posix()}/b.shp")


def test_the_base_date_is_the_latest_date_in_the_file_names() -> None:
    assert base_date(["/x/AL_D002_11_20260908.shp", "/vsizip//x/AL_D002_26_20260810.zip/AL_D002_26_20260810.shp"]) == "20260908"
    assert base_date(["/x/readme.shp"]) is None


def test_run_refuses_a_bad_file_set_before_connecting_even_with_the_row_count_option(tmp_path: Path) -> None:
    def no_db():
        raise AssertionError("connected")

    buildings, parcels = tmp_path / "buildings", tmp_path / "parcels"
    buildings.mkdir()
    parcels.mkdir()
    assert run(buildings, parcels, connect=no_db, accept_row_count_change=True) == 2   # 파일 없음
    (buildings / "AL_D010_11_20260909.shp").write_bytes(b"x")
    (parcels / "AL_D002_11_20260908.shp").write_bytes(b"x")
    # 시도 15개가 빠진 판 - 이름 검사가 먼저라 파일을 열거나 DB 에 붙지 않고, 행 수 옵션으로도 넘기지 못한다
    assert run(buildings, parcels, connect=no_db, accept_row_count_change=True) == 3
```

`backend/tests/test_geo_load_postgis.py` - 실제 PostGIS 에서(코덱스 HIGH · 재검토 HIGH):
```python
import os

import pytest

pytestmark = pytest.mark.skipif(os.getenv("RUN_POSTGIS_TESTS") != "1", reason="set RUN_POSTGIS_TESTS=1 and POSTGIS_TEST_DATABASE_URL")
pyogrio = pytest.importorskip("pyogrio")
shapely = pytest.importorskip("shapely")
psycopg = pytest.importorskip("psycopg")

from app.services.geo_reference import EXPECTED_REGION_CODES  # noqa: E402
from scripts.geo_load import LoadBusy, exclusive_load, load, run, source_crs_problem  # noqa: E402

URL = os.environ.get("POSTGIS_TEST_DATABASE_URL", "").replace("postgresql+psycopg://", "postgresql://")
LAT, LNG = 37.5665, 126.9780


def connect():
    return psycopg.connect(URL)


def write_square(path, crs: str) -> None:
    import numpy as np
    from pyproj import Transformer

    x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(LNG, LAT)
    square = shapely.box(x - 10, y - 10, x + 10, y + 10)
    pyogrio.raw.write(str(path), geometry=np.array([shapely.to_wkb(square)], dtype=object),
                      field_data=[np.array(["0000000000000000000000000001"], dtype=object), np.array(["1114010300100310000"], dtype=object),
                                  np.array(["1114010300"], dtype=object), np.array(["서울특별시 중구 태평로1가"], dtype=object)],
                      fields=["A1", "A2", "A3", "A4"], geometry_type="Polygon", crs=crs, driver="ESRI Shapefile", encoding="cp949")


@pytest.fixture
def cur():
    with psycopg.connect(URL, autocommit=True) as conn, conn.cursor() as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS postgis; DROP SCHEMA IF EXISTS geo CASCADE; CREATE SCHEMA geo; CREATE SEQUENCE geo.feature_id_seq;")
        c.execute("CREATE TABLE geo.building_next (id bigint PRIMARY KEY DEFAULT nextval('geo.feature_id_seq'), feature_key varchar(40) NOT NULL, pnu varchar(19) NOT NULL, "
                  "la double precision NOT NULL, lo double precision NOT NULL, rx double precision NOT NULL, ry double precision NOT NULL, geom geometry(Geometry, 5186) NOT NULL)")
        yield c
        c.execute("DROP SCHEMA geo CASCADE")


def test_5186_and_5174_shapefiles_land_where_their_lat_lng_says_and_a_wrong_crs_is_refused(tmp_path, cur) -> None:
    tm, bessel, web = tmp_path / "AL_D010_11_20260909.shp", tmp_path / "AL_D010_26_20260909.shp", tmp_path / "AL_D010_27_20260909.shp"
    write_square(tm, "EPSG:5186")
    write_square(bessel, "EPSG:5174")   # 2023-08 이전 판의 좌표계 - 5186 으로 바꿔 넣는다
    write_square(web, "EPSG:3857")
    assert source_crs_problem(str(tm)) is None and source_crs_problem(str(bessel)) is None and "EPSG:3857" in source_crs_problem(str(web))
    dongs, prefixes = {}, set()
    assert load(cur, "building", [str(tm), str(bessel)], dongs, prefixes) == (2, 0, 0)
    cur.execute("SELECT st_srid(geom), la, lo, st_y(st_transform(st_centroid(geom), 4326)), st_x(st_transform(st_centroid(geom), 4326)) FROM geo.building_next ORDER BY id")
    for srid, la, lo, glat, glng in cur.fetchall():
        assert srid == 5186
        for value, expected in ((la, LAT), (lo, LNG), (glat, LAT), (glng, LNG)):
            assert abs(value - expected) < 1e-4   # 약 10m 안
    assert dongs == {"1114010300": "서울특별시 중구 태평로1가"} and prefixes == {"1114010300"}


def test_the_load_lock_stays_on_one_connection_across_commits_and_blocks_a_second_loader() -> None:
    with exclusive_load(connect) as (raw, pid):
        c = raw.cursor()
        c.execute("SELECT 1")
        raw.commit()
        c = raw.cursor()
        c.execute("SELECT pg_backend_pid(), count(*) FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid()")
        assert c.fetchone() == (pid, 1)   # commit 을 넘어 같은 연결 · 같은 잠금
        with pytest.raises(LoadBusy):
            with exclusive_load(connect):
                pass
    with exclusive_load(connect):   # 끝나면 풀렸다(unlock 이 true 였다)
        pass


SHAPE = ("id bigint PRIMARY KEY DEFAULT nextval('geo.feature_id_seq'), feature_key varchar(40) NOT NULL, pnu varchar(19) NOT NULL, "
         "la double precision NOT NULL, lo double precision NOT NULL, rx double precision NOT NULL, ry double precision NOT NULL, geom geometry(Geometry, 5186) NOT NULL")
SCHEMA_0050 = [   # 0050 의 geo 부분과 같은 모양
    "CREATE EXTENSION IF NOT EXISTS postgis", "DROP SCHEMA IF EXISTS geo CASCADE", "CREATE SCHEMA geo", "CREATE SEQUENCE geo.feature_id_seq",
    f"CREATE TABLE geo.building ({SHAPE})", f"CREATE TABLE geo.parcel ({SHAPE}, jimok varchar(4))",
    "CREATE INDEX building_geom_gix ON geo.building USING gist (geom)", "CREATE INDEX building_pnu_ix ON geo.building (pnu)",
    "CREATE INDEX parcel_geom_gix ON geo.parcel USING gist (geom)", "CREATE INDEX parcel_pnu_ix ON geo.parcel (pnu)",
    "CREATE TABLE geo.legal_dong (code varchar(10) PRIMARY KEY, name varchar(100) NOT NULL)",
    "CREATE TABLE geo.load_run (id bigserial PRIMARY KEY, finished_at timestamptz NOT NULL DEFAULT now(), building_rows bigint NOT NULL, "
    "parcel_rows bigint NOT NULL, building_base_date varchar(8), parcel_base_date varchar(8))",
]


@pytest.fixture
def geo_schema():
    with psycopg.connect(URL, autocommit=True) as conn, conn.cursor() as c:
        for statement in SCHEMA_0050:
            c.execute(statement)
        yield c
        c.execute("DROP SCHEMA geo CASCADE")


def write_shapes(path, points, fields: dict[str, list]) -> None:
    import numpy as np
    from pyproj import Transformer

    to_tm = Transformer.from_crs("EPSG:4326", "EPSG:5186", always_xy=True)
    boxes = [shapely.to_wkb(shapely.box(x - 8, y - 8, x + 8, y + 8)) for x, y in (to_tm.transform(lng, lat) for lat, lng in points)]
    path.parent.mkdir(parents=True, exist_ok=True)
    pyogrio.raw.write(str(path), geometry=np.array(boxes, dtype=object), field_data=[np.array(v, dtype=object) for v in fields.values()],
                      fields=list(fields), geometry_type="Polygon", crs="EPSG:5186", driver="ESRI Shapefile", encoding="cp949")


def write_month(root, building_date: str, parcel_date: str, *, blank_key_in: str | None = None) -> None:
    """시도 16개 - 건물 한 동씩, 땅은 대지 하나 · 논 하나(논은 적재에서 빠진다)."""

    for n, code in enumerate(sorted(EXPECTED_REGION_CODES)):
        lat, lng, dong = 35.0 + n * 0.01, 127.0, f"{code}11010100"
        pnu = f"{dong}1{n + 1:04d}0000"
        key = None if code == blank_key_in else f"B{building_date}{code}"
        write_shapes(root / "buildings" / f"AL_D010_{code}_{building_date}" / f"AL_D010_{code}_{building_date}.shp", [(lat, lng)],
                     {"A1": [key], "A2": [pnu], "A3": [dong], "A4": ["시험시 시험동"]})
        write_shapes(root / "parcels" / f"AL_D002_{code}_{parcel_date}" / f"AL_D002_{code}_{parcel_date}.shp", [(lat, lng), (lat + 0.001, lng)],
                     {"A1": [pnu, pnu[:-4] + "0001"], "A2": [dong, dong], "A3": ["시험시 시험동"] * 2, "A5": [f"{n + 1}대", f"{n + 1}-1답"]})


def test_run_checks_loads_swaps_and_never_reuses_ids(tmp_path, geo_schema) -> None:
    def go(root, accept: bool) -> int:
        return run(root / "buildings", root / "parcels", connect=connect, accept_row_count_change=accept)

    def state() -> tuple:
        geo_schema.execute("SELECT (SELECT count(*) FROM geo.building), (SELECT count(*) FROM geo.parcel), (SELECT count(*) FROM geo.legal_dong), "
                           "(SELECT count(*) FROM geo.load_run), (SELECT min(id) FROM geo.building), "
                           "(SELECT count(*) FROM pg_tables WHERE schemaname = 'geo' AND tablename LIKE '%_next'), "
                           "(SELECT count(*) FROM pg_locks WHERE locktype = 'advisory')")
        return geo_schema.fetchone()

    write_month(tmp_path / "bad", "20260909", "20260908", blank_key_in="11")
    assert go(tmp_path / "bad", True) == 3   # 식별자 빈 줄 1/16 - 품질 검사는 행 수 옵션으로 넘기지 못한다
    write_month(tmp_path / "m1", "20260909", "20260908")
    assert go(tmp_path / "m1", False) == 8   # 시험 판은 16줄이라 행 수 범위 밖
    assert state()[:4] == (0, 0, 0, 0)   # 바꾸지 않았다
    assert go(tmp_path / "m1", True) == 0
    first = state()
    assert first[:4] == (16, 16, 16, 1) and first[5:] == (0, 0)   # 논은 빠졌다 · _next 없음 · 잠금 풀림
    write_month(tmp_path / "m2", "20261009", "20261008")
    assert go(tmp_path / "m2", True) == 0
    second = state()
    assert second[:4] == (16, 16, 16, 2) and second[4] > first[4]   # 새 판은 새 id - 옛 geoRef 는 404 가 된다
    geo_schema.execute("SELECT indexname FROM pg_indexes WHERE schemaname = 'geo' ORDER BY 1")
    assert [row[0] for row in geo_schema.fetchall()] == [
        "building_geom_gix", "building_pkey", "building_pnu_ix", "legal_dong_pkey", "load_run_pkey", "parcel_geom_gix", "parcel_pkey", "parcel_pnu_ix",
    ]
    geo_schema.execute("SELECT building_base_date, parcel_base_date, jimok FROM geo.load_run, (SELECT DISTINCT jimok FROM geo.parcel) j ORDER BY geo.load_run.id")
    assert geo_schema.fetchall() == [("20260909", "20260908", "대"), ("20261009", "20261008", "대")]
```

- [ ] **Step 2: 실패 확인** - `cd backend && python -m pytest tests/test_geo_load_files.py -q` → FAIL(모듈 없음).
  (DB 없는 `run` 시험은 이름 검사를 좌표계 · 지문보다 먼저 해야 통과한다 - 순서가 바뀌면 가짜 .shp 를 pyogrio 가 열다 터진다.)

- [ ] **Step 3: 구현** - `backend/requirements-geo.txt`

```
# 적재 도구(scripts/geo_load.py) 전용 - 앱 런타임 이미지에는 넣지 않는다(Dockerfile geo-loader 단계)
pyogrio==0.13.0
shapely==2.1.2
pyproj==3.8.0
numpy==2.5.3
```

`backend/Dockerfile` - `FROM runtime AS final` 바로 위에:
```dockerfile
# 월 1회 건물 · 땅 적재 도구(방식1). compose 는 마지막 단계(final)만 빌드한다 - 이 단계는 --target geo-loader 로만 만든다
FROM runtime AS geo-loader

COPY requirements-geo.txt ./
RUN pip install --no-cache-dir -r requirements-geo.txt
```

`backend/scripts/geo_load.py`:
```python
"""건물 · 땅 지번 월 적재(방식1) - 브이월드 전체데이터(시도별 SHP/ZIP)를 검사하고, geo.*_next 에 넣고, 한 트랜잭션에서 바꿔치기한다.

받는 법: 브이월드 'GIS건물통합정보'(AL_D010) · '연속지적도형정보'(AL_D002) 의 구분 '전체데이터' 최신 기준일, 시도 전부(로그인 필요 - 사람이 받는다).
실행: docker build --target geo-loader -t th-geo-loader backend
      docker run --rm --network <compose 네트워크> --env-file <backend 와 같은 env 파일> -v <받은 폴더>:/data:ro th-geo-loader \
        python scripts/geo_load.py --buildings /data/buildings --parcels /data/parcels
      (Windows 의 Git Bash 에서는 앞에 MSYS_NO_PATHCONV=1 - 안 붙이면 /data/... 가 Windows 경로로 바뀐다)
DB 는 앱 설정(DATABASE_URL)의 엔진에서 연결 하나를 빌려 끝까지 쥔다(advisory lock 이 그 연결에 붙는다). 출력은 건수 · 시간뿐이다.
구조 검사는 넘기지 못한다. 행 수 범위만 --accept-row-count-change 로 받아들인다. 서버에서 돌리는 것은 실행할 때마다 승인받는다.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.services.geo_reference import (  # noqa: E402
    content_duplicate_problems, is_feature_key, is_pnu, jimok_of, keep_parcel, manifest_problems, quality_problems,
    row_count_problems, swap_statements,
)

CHUNK = 200_000
DATE = re.compile(r"_(\d{8})")
LOCK_KEY = 7_201_008   # pg_try_advisory_lock - 적재 도구 하나만 돈다
SWAP_LOCK_TIMEOUT = "5s"
SWAP_TRIES = 3
# 원본 칸 - 건물 A1 식별번호 · A2 고유번호 · A3 법정동코드 · A4 법정동명, 땅 A1 고유번호 · A2 법정동코드 · A3 법정동명 · A5 지번+지목(10/7 실파일 확인)
COLUMNS = {"building": {"key": "A1", "pnu": "A2", "code": "A3", "name": "A4", "jimok": None},
           "parcel": {"key": "A1", "pnu": "A1", "code": "A2", "name": "A3", "jimok": "A5"}}


class LoadBusy(Exception):
    """다른 적재가 같은 잠금을 쥐고 있다."""


class LockLost(Exception):
    """적재가 끝났을 때 연결이 바뀌었거나 잠금을 풀지 못했다."""


def discover(root: Path) -> list[str]:
    """압축을 푼 폴더의 .shp, 그리고 푼 폴더가 없는 zip 안의 .shp."""

    shp = sorted(str(p) for p in root.rglob("*.shp"))
    extracted = {Path(p).parent.name for p in shp}
    zipped = [
        f"/vsizip/{zip_path.as_posix()}/{name}"
        for zip_path in sorted(root.rglob("*.zip")) if zip_path.stem not in extracted
        for name in zipfile.ZipFile(zip_path).namelist() if name.lower().endswith(".shp")
    ]
    return shp + zipped


def base_date(paths: list[str]) -> str | None:
    dates = [m.group(1) for p in paths for m in [DATE.search(Path(p).name)] if m]
    return max(dates) if dates else None


def file_digest(path: str) -> str:
    """.shp 내용의 sha256 - '(2).shp'가 나눈 조각인지 같은 파일을 두 번 받은 것인지 내용으로 가린다."""

    digest = hashlib.sha256()
    if path.startswith("/vsizip/"):
        zip_path, member = path[len("/vsizip/"):].split(".zip/", 1)
        with zipfile.ZipFile(zip_path + ".zip") as zf, zf.open(member) as stream:
            for block in iter(lambda: stream.read(1 << 20), b""):
                digest.update(block)
    else:
        with open(path, "rb") as stream:
            for block in iter(lambda: stream.read(1 << 20), b""):
                digest.update(block)
    return digest.hexdigest()


def source_crs_problem(path: str) -> str | None:
    """좌표계 확인 - EPSG:5186 이면 그대로, 5174(2023-08 이전 판)는 load 가 5186 으로 바꾼다, 그 밖 · 없음은 멈춘다."""

    import pyogrio
    from pyproj import CRS

    raw = pyogrio.read_info(path).get("crs")
    if not raw:
        return f"{Path(path).name}: no CRS"
    epsg = CRS.from_user_input(raw).to_epsg()
    return None if epsg in (5186, 5174) else f"{Path(path).name}: unexpected CRS EPSG:{epsg}"


@contextmanager
def exclusive_load(connect: Callable[[], object]) -> Iterator[tuple[object, int]]:
    """연결 하나를 빌려 적재 끝까지 쥐고 advisory lock 을 건다. 잠금은 연결(세션)에 붙으므로 commit 을 여러 번 해도 같은 연결이어야 한다
    (풀에서 다시 빌리면 다른 연결이 될 수 있다 - 코덱스 재검토 HIGH). 끝날 때 같은 연결인지, 잠금이 풀렸는지 확인한다."""

    raw = connect()
    try:
        cur = raw.cursor()
        cur.execute("SELECT pg_backend_pid(), pg_try_advisory_lock(%s)", (LOCK_KEY,))
        pid, locked = cur.fetchone()
        raw.commit()
        if not locked:
            raise LoadBusy()
        try:
            yield raw, pid
        finally:
            raw.rollback()   # 끝나지 않은 트랜잭션이 있으면 놓는다(바꿔치기는 이미 commit 됐거나 되돌려졌다)
            cur = raw.cursor()
            cur.execute("SELECT pg_backend_pid(), pg_advisory_unlock(%s)", (LOCK_KEY,))
            now_pid, unlocked = cur.fetchone()
            raw.commit()
            if now_pid != pid or not unlocked:
                raise LockLost()
    finally:
        raw.close()


def load(cur, table: str, paths: list[str], dongs: dict[str, str], prefixes: set[str]) -> tuple[int, int, int, int]:
    """파일들을 geo.{table}_next 에 COPY 한다. 돌려주는 값: (넣은 줄, 고유번호나 식별자가 없거나 잘못된 줄 - 넣지 않음, 지목을 못 읽은 땅 - 넣음, 도형이 없거나 비어서 뺀 줄 - 넣지 않음)."""

    import numpy as np
    import pyogrio
    import shapely
    from pyproj import CRS, Transformer

    cols = COLUMNS[table]
    wanted = list(dict.fromkeys(c for c in (cols["key"], cols["pnu"], cols["code"], cols["name"], cols["jimok"]) if c))
    to_ll = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)
    rows = missing_keys = unknown_jimok = skipped_geometry = 0
    for path in paths:
        info = pyogrio.read_info(path)
        source = CRS.from_user_input(info["crs"])
        to_tm = None if source.to_epsg() == 5186 else Transformer.from_crs(source, "EPSG:5186", always_xy=True)
        total, skip = info["features"], 0
        while skip < total:
            meta, _, wkb, fd = pyogrio.raw.read(path, columns=wanted, skip_features=skip, max_features=CHUNK, encoding="cp949")
            skip += CHUNK
            field = dict(zip(meta["fields"], fd))
            pnu_raw = [(v or "").strip() if isinstance(v, str) else "" for v in field[cols["pnu"]]]
            key_raw = [v.strip() if isinstance(v, str) else "" for v in field[cols["key"]]]
            # 고유번호가 19자리 숫자가 아니거나 식별자가 빈 줄은 넣지 않고 센다(땅은 식별자가 곧 고유번호다)
            keep = np.array([is_pnu(p) and is_feature_key(k) for p, k in zip(pnu_raw, key_raw)], dtype=bool)
            missing_keys += int((~keep).sum())
            jimok_all = [jimok_of(v) for v in field[cols["jimok"]]] if cols["jimok"] else None
            if jimok_all is not None:
                keep &= np.array([keep_parcel(j) for j in jimok_all], dtype=bool)
            for code, name in zip(field[cols["code"]][keep], field[cols["name"]][keep]):
                if isinstance(code, str) and isinstance(name, str) and code.strip():
                    dongs.setdefault(code.strip(), " ".join(name.split()))
            g = shapely.from_wkb(wkb[keep])
            if to_tm is not None:
                g = shapely.transform(g, lambda xy: np.column_stack(to_tm.transform(xy[:, 0], xy[:, 1])))
            bad = ~shapely.is_valid(g)
            if bad.any():
                g[bad] = shapely.buffer(g[bad], 0)
            c = shapely.centroid(g)
            rep = np.where(shapely.contains(g, c), c, shapely.point_on_surface(g))
            rx, ry = shapely.get_x(rep), shapely.get_y(rep)
            lo, la = to_ll.transform(rx, ry)
            hexes = shapely.to_wkb(shapely.set_srid(g, 5186), hex=True, include_srid=True)
            pnus = [v for v, k in zip(pnu_raw, keep) if k]
            keys = [v for v, k in zip(key_raw, keep) if k]
            jimoks = [j for j, k in zip(jimok_all, keep) if k] if jimok_all is not None else None
            if jimoks is not None:
                unknown_jimok += sum(1 for j in jimoks if j is None)
            prefixes.update(pnu[:10] for pnu in pnus)
            names = "feature_key, pnu, la, lo, rx, ry, geom" + (", jimok" if jimoks is not None else "")
            with cur.copy(f"COPY geo.{table}_next ({names}) FROM STDIN") as copy:
                for k in range(len(pnus)):
                    if hexes[k] is not None and not shapely.is_empty(g[k]):
                        row = (keys[k], pnus[k], float(la[k]), float(lo[k]), float(rx[k]), float(ry[k]), hexes[k])
                        copy.write_row(row + ((jimoks[k],) if jimoks is not None else ()))
                        rows += 1
                    else:
                        skipped_geometry += 1
    return rows, missing_keys, unknown_jimok, skipped_geometry


def _swap(raw, counts: dict[str, int], dongs: dict[str, str], files: dict[str, list[str]]) -> bool:
    """바꿔치기만 짧은 트랜잭션. 잠금을 못 얻으면 되돌려 원래 표를 그대로 두고 다시 해 본다."""

    for attempt in range(1, SWAP_TRIES + 1):
        cur = raw.cursor()
        try:
            cur.execute(f"SET LOCAL lock_timeout = '{SWAP_LOCK_TIMEOUT}'")
            for table in ("building", "parcel"):
                for statement in swap_statements(table):
                    cur.execute(statement)
            cur.execute("TRUNCATE geo.legal_dong")
            with cur.copy("COPY geo.legal_dong (code, name) FROM STDIN") as copy:
                for code, name in sorted(dongs.items()):
                    copy.write_row((code, name))
            cur.execute(
                "INSERT INTO geo.load_run (building_rows, parcel_rows, building_base_date, parcel_base_date) VALUES (%s, %s, %s, %s)",
                (counts["building"], counts["parcel"], base_date(files["building"]), base_date(files["parcel"])),
            )
            raw.commit()
            return True
        except Exception as error:   # 잠금 시간 초과 등 - 되돌리고 다시
            raw.rollback()
            print(f"바꿔치기 {attempt}번째 실패: {type(error).__name__}", file=sys.stderr)
            if attempt < SWAP_TRIES:
                time.sleep(10)
    return False


def run(buildings: Path, parcels: Path, *, connect: Callable[[], object], accept_row_count_change: bool) -> int:
    files = {"building": discover(buildings), "parcel": discover(parcels)}
    if not files["building"] or not files["parcel"]:
        print("건물 · 땅 파일이 둘 다 있어야 한다", file=sys.stderr)
        return 2
    structural = [f"{t}: {p}" for t in files for p in manifest_problems(files[t])]
    if not structural:   # 이름 검사가 먼저 - 엉뚱한 파일 목록이면 열어 보지도 않는다
        structural += [p for t in files for path in files[t] if (p := source_crs_problem(path))]
        # 이름이 같은 두 파일은 manifest 가 이미 'duplicated file' 로 잡는다 - 여기서는 이름이 다르고 내용이 같은 것을 잡는다
        structural += [f"{t}: {p}" for t in files for p in content_duplicate_problems({Path(path).name: file_digest(path) for path in files[t]})]
    if structural:
        print("\n".join(structural), file=sys.stderr)
        return 3
    started = time.perf_counter()
    dongs: dict[str, str] = {}
    prefixes: set[str] = set()   # 넣은 고유번호의 앞 10자리(법정동코드) - 모두 이름이 있어야 주소가 만들어진다
    counts: dict[str, int] = {}
    row_counts: list[str] = []
    try:
        with exclusive_load(connect) as (raw, _pid):
            for table in ("building", "parcel"):
                cur = raw.cursor()
                cur.execute(f"DROP TABLE IF EXISTS geo.{table}_next")
                cur.execute(f"CREATE TABLE geo.{table}_next (LIKE geo.{table} INCLUDING DEFAULTS INCLUDING CONSTRAINTS)")
                rows, missing_keys, unknown_jimok, skipped_geometry = load(cur, table, files[table], dongs, prefixes)
                counts[table] = rows
                cur.execute(f"ALTER TABLE geo.{table}_next ADD CONSTRAINT {table}_next_pkey PRIMARY KEY (id)")
                cur.execute(f"CREATE INDEX {table}_next_geom_gix ON geo.{table}_next USING gist (geom)")
                cur.execute(f"CREATE INDEX {table}_next_pnu_ix ON geo.{table}_next (pnu)")
                cur.execute(f"ANALYZE geo.{table}_next")
                cur.execute(f"SELECT count(DISTINCT feature_key) FROM geo.{table}_next")
                distinct = cur.fetchone()[0]
                raw.commit()   # 표마다 확정 - 같은 연결이라 잠금은 그대로다. 바꿔치기 앞까지 실패해도 지금 표는 그대로다
                structural += quality_problems(table, rows, distinct, missing_keys=missing_keys, unknown_jimok=unknown_jimok)
                row_counts += row_count_problems(table, rows)
                print(f"{table}: 새 {rows:,}줄 · 고유 {distinct:,} · 식별자 빈 줄 {missing_keys:,} · 지목 못 읽음 {unknown_jimok:,} · {time.perf_counter() - started:.0f}s", flush=True)
            if missing := prefixes - dongs.keys():
                print(f"법정동 이름이 없는 법정동코드 {len(missing):,}개", file=sys.stderr)
                return 4
            if structural:
                print("\n".join(structural), file=sys.stderr)
                return 3
            if row_counts and not accept_row_count_change:
                print("\n".join(row_counts) + "\n판이 정말 커지거나 줄었으면 --accept-row-count-change", file=sys.stderr)
                return 8
            if not _swap(raw, counts, dongs, files):
                return 6
    except LoadBusy:
        print("다른 적재가 돌고 있다", file=sys.stderr)
        return 5
    except LockLost:
        print("적재 연결이 바뀌었거나 잠금을 풀지 못했다 - pg_locks 를 확인할 것", file=sys.stderr)
        return 7
    print(f"바꿔치기 끝 · 법정동 {len(dongs):,} · {time.perf_counter() - started:.0f}s", flush=True)
    return 0


def main() -> int:
    from app.db.session import get_engine

    parser = argparse.ArgumentParser()
    parser.add_argument("--buildings", type=Path, required=True)
    parser.add_argument("--parcels", type=Path, required=True)
    parser.add_argument("--accept-row-count-change", action="store_true", help="행 수 범위만 받아들인다 - 구조 검사는 넘기지 못한다")
    args = parser.parse_args()
    # 엔진 풀에서 DBAPI 연결 하나를 빌려 끝까지 쓴다(raw_connection) - commit 사이에 다른 연결로 바뀌지 않는다
    return run(args.buildings, args.parcels, connect=get_engine().raw_connection, accept_row_count_change=args.accept_row_count_change)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 통과 확인** - `cd backend && python -m pytest tests/test_geo_load_files.py tests/test_geo_reference.py -q` → PASS(파일 4 · 규칙 시험 전부). PostGIS 시험 3개(5186 · 5174 · 3857, 잠금, `run` 3 → 8 → 0 → 다음 달 0)는 과제 14 Step 6.

- [ ] **Step 5: 변경 확인.**

---

## 과제 9: 프론트 API 경계 · 바구니

**Files:**
- Modify: `frontend/src/api/types.ts`, `frontend/src/api/backendApi.ts`, `frontend/src/api/dataApi.ts`, `frontend/src/components/itinerary/placeAdd/placeBasket.ts`
- Test: `frontend/src/api/backendApi.test.ts`, `frontend/src/components/itinerary/placeAdd/placeBasket.test.ts`

**Interfaces:**
- Produces(types.ts):
```ts
/** 건물 · 땅 지번의 종류(국토교통부 GIS건물통합정보 · 연속지적도) */
export type GeoKind = "building" | "parcel";
/** 주소 채움 - 고른 자리를 품은 건물 · 땅의 지번 주소와 중심. 공공데이터 값이다(카카오 값 아님). id 는 이 판의 행 번호 */
export type AddressFill = { kind: GeoKind; id: number; pnu: string; address: string; latitude: number; longitude: number; distanceMeters: number };
/** 담을 때 보내는 지번 참조 - pin 이 false 면 주소만(넓은 땅). 주소 · 좌표는 서버가 다시 읽는다 */
export type GeoRef = { kind: GeoKind; id: number; pin: boolean };
/** POST /places/locate - 찍은 자리를 품은 건물 · 땅. nearCenter = 건물이거나 땅 중심이 30m 안(핀까지) */
export type LocateResult = { fill: AddressFill | null; nearCenter: boolean };
/** 나만의 장소 - 사용자가 쓴 이름과 (선택) 지번 참조뿐. 위도 · 경도 · 주소는 보내지 않는다(데브톡 151842 - 서버 422) */
export type CustomPlaceInput = { name: string; geoRef?: GeoRef };
```
  `PlaceMatchResult.fill?: AddressFill | null`, `ItineraryPlace.geoKind?: GeoKind | null`, `AppDataApi.locatePlace(latitude: number, longitude: number): Promise<LocateResult>`.
- Produces(placeBasket.ts): custom 칸 `{ basketId; kind: "custom"; name; address: string | null; geoRef: GeoRef | null; latitude: number | null; longitude: number | null; kakaoPlaceId }`(위도 · 경도는 미리보기 지도용 - pin 인 지번의 공공데이터 중심뿐, 저장 요청에는 넣지 않는다),
  `customBasketItem(input: { name; address?; geoRef?; latitude?; longitude? }, kakaoPlaceId)`.

- [ ] **Step 1: 기존 시험 고치기** - `CustomPlaceInput` 에서 위도 · 경도가 빠진다(타입 검사가 모두 짚어 준다).
  - `backendApi.test.ts:216` `{ customPlace: { name: "할머니 댁", latitude: 35.1, longitude: 129.03 } }` → `{ customPlace: { name: "할머니 댁", geoRef: { kind: "building", id: 501, pin: true } } }`(본문 단언도 같이).
  - `backendApi.test.ts:332 · 341` `customPlace: { name: "다시 적은 이름", latitude: 35.1, longitude: 129.03 }` → `customPlace: { name: "다시 적은 이름" }`.
  - `placeBasket.test.ts`: 새 `customBasketItem` 은 `geoRef.pin` 이 아니면 위도 · 경도를 버리고, 보조 글은 `item.address ?? "위치 없이 이름만"` 이라 `"지도에서 찍은 위치"` 문구는 코드에서 사라진다. 셋을 고친다(78-83줄 `drops half a point …` 는 그대로 통과한다).
    - 41-51줄 `fills publicPlace and customPlace with exactly the fields …`: 44줄 `customBasketItem({ name: "숙소 앞 편의점", latitude: 35.1, longitude: 129.03 }, "123456")` → `customBasketItem({ name: "숙소 앞 편의점", geoRef: { kind: "building", id: 501, pin: true } }, "123456")`, 50줄 기대 키 `["latitude", "longitude", "name"]` → `["geoRef", "name"]`.
    - 62-76줄 `sends a custom place as the typed name and the picked point only` → 아래로 통째로 바꾼다(저장 본문은 Step 2 의 새 시험이 본다).
      ```ts
        it("trims the name and keeps the public center of a pinned jibun for the preview map", () => {
          const item = customBasketItem(
            { name: "  숙소 앞 편의점  ", address: "부산광역시 해운대구 중동 1391-66", geoRef: { kind: "building", id: 501, pin: true }, latitude: 35.160131, longitude: 129.161383 },
            "123456",
          );

          expect(item).toMatchObject({ kind: "custom", name: "숙소 앞 편의점", latitude: 35.160131, longitude: 129.161383, kakaoPlaceId: "123456" });
        });
      ```
    - 92-106줄 `titles each row …`: 94줄 `pinned` → `customBasketItem({ name: "내 쉼터", address: "부산광역시 해운대구 중동 1391-66", geoRef: { kind: "building", id: 501, pin: true }, latitude: 35.160131, longitude: 129.161383 }, null)`, 104줄 기대 `"지도에서 찍은 위치"` → `"부산광역시 해운대구 중동 1391-66"`.
  - `frontend/src/components/itinerary/placeEdit.test.ts:130` `const customPlace = { name: "내가 아는 식당", latitude: 35.2, longitude: 129.1 };` → `const customPlace = { name: "내가 아는 식당", geoRef: { kind: "building" as const, id: 501, pin: true } };`(이어지는 `toEqual` 은 그대로 - 받은 값을 그대로 싣는지 본다).

- [ ] **Step 2: 실패하는 시험 쓰기**

`backendApi.test.ts`(300줄의 `jsonResponse` 를 쓰는 describe 안):
```ts
  it("asks the server which building or parcel holds a picked point", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse({ fill: null, nearCenter: false }));
    vi.stubGlobal("fetch", fetchSpy);

    await expect(backendApi.locatePlace(37.7712, 128.948)).resolves.toEqual({ fill: null, nearCenter: false });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/places/locate`,
      expect.objectContaining({ method: "POST", body: JSON.stringify({ latitude: 37.7712, longitude: 128.948 }) }),
    );
  });
```

`placeBasket.test.ts`:
```ts
it("sends only the name and the geo reference of an address-filled custom place", () => {
  const item = customBasketItem(
    { name: "오동도", address: "전남광주통합특별시 여수시 수정동 1-6", geoRef: { kind: "parcel", id: 4401, pin: true }, latitude: 34.744764, longitude: 127.767783 },
    "777",
  );
  expect(basketItemPayload(item)).toEqual({ customPlace: { name: "오동도", geoRef: { kind: "parcel", id: 4401, pin: true } }, kakaoPlaceId: "777" });
  expect(basketItemDetail(item)).toBe("전남광주통합특별시 여수시 수정동 1-6");
});

it("keeps a wide parcel's address without a point and a plain custom place as a name only", () => {
  const wide = customBasketItem({ name: "넓은 공원", address: "강릉시 견소동 1", geoRef: { kind: "parcel", id: 77, pin: false } }, null);
  expect(basketItemPayload(wide)).toEqual({ customPlace: { name: "넓은 공원", geoRef: { kind: "parcel", id: 77, pin: false } } });
  expect(wide).toMatchObject({ latitude: null, longitude: null });   // wide 는 유니온(public 갈래에는 latitude 가 없다)이라 .latitude 로 바로 읽으면 타입 오류다
  expect(basketItemDetail(wide)).toBe("강릉시 견소동 1");
  const plain = customBasketItem({ name: "친구네 펜션" }, null);
  expect(basketItemPayload(plain)).toEqual({ customPlace: { name: "친구네 펜션" } });
  expect(basketItemDetail(plain)).toBe("위치 없이 이름만");
});
```

- [ ] **Step 3: 실패 확인** - `cd frontend && npx vitest run src/api/backendApi.test.ts src/components/itinerary/placeAdd/placeBasket.test.ts` → FAIL.

- [ ] **Step 4: 구현**

`backendApi.ts`(`matchPlace` 아래):
```ts
  locatePlace: (latitude: number, longitude: number): Promise<LocateResult> =>
    apiClient.post<LocateResult>("/api/places/locate", { latitude, longitude }),
```
`dataApi.ts` 인터페이스에 `locatePlace: (latitude: number, longitude: number) => Promise<LocateResult>;`.

`placeBasket.ts`:
```ts
  | {
      basketId: string;
      kind: "custom";
      name: string;
      /** 주소 채움이면 건물 · 땅 지번 주소(공공데이터) - 보여 주기용. 저장은 geoRef 로 서버가 다시 읽는다 */
      address: string | null;
      geoRef: GeoRef | null;
      /** 미리보기 지도용 - pin 인 지번의 공공데이터 중심뿐(찍은 좌표 · 카카오 좌표는 여기에 오지 않는다) */
      latitude: number | null;
      longitude: number | null;
      kakaoPlaceId: string | null;
    };

export function customBasketItem(
  input: { name: string; address?: string | null; geoRef?: GeoRef | null; latitude?: number | null; longitude?: number | null },
  kakaoPlaceId: string | null,
): PlaceBasketItem {
  const point =
    input.geoRef?.pin && typeof input.latitude === "number" && typeof input.longitude === "number"
      ? { latitude: input.latitude, longitude: input.longitude }
      : { latitude: null, longitude: null };
  return { basketId: nextBasketId(), kind: "custom", name: input.name.trim(), address: input.address ?? null, geoRef: input.geoRef ?? null, ...point, kakaoPlaceId };
}
```
`basketItemPayload` 의 custom 줄: `return { customPlace: { name: item.name, ...(item.geoRef ? { geoRef: item.geoRef } : {}) }, ...kakao };`
`basketItemDetail` 의 custom 줄: `return item.address ?? "위치 없이 이름만";`

- [ ] **Step 5: 통과 확인** - 같은 명령 → PASS. `cd frontend && npm run typecheck` 가 짚는 다른 `customPlace` 위도 · 경도 사용처(과제 10 ~ 12 의 파일)는 그 과제에서 고친다 - 이 단계에서는 이 두 시험 파일만 통과하면 된다.

- [ ] **Step 6: 변경 확인.**

---

## 과제 10: 갈래 · 나만의 장소 칸 - `usePlaceMatch` · `publicPlaceText` · `CustomPlaceForm` · `PlaceMatchPanel` · `LegacyPlaceConfirm`

**Files:**
- Modify: `frontend/src/components/itinerary/placeAdd/{usePlaceMatch.ts,publicPlaceText.ts,CustomPlaceForm.tsx,PlaceMatchChoices.tsx,PlaceMatchPanel.tsx}`, `frontend/src/components/itinerary/LegacyPlaceConfirm.tsx`, `frontend/src/styles/app.css`
- Test: `frontend/src/components/itinerary/placeAdd/{usePlaceMatch.test.ts,publicPlaceText.test.ts,CustomPlaceForm.test.tsx,PlaceMatchPanel.test.tsx}`, `frontend/src/components/itinerary/LegacyPlaceConfirm.test.tsx`

**Interfaces:**
- Consumes: `AddressFill` · `GeoRef`(과제 9), `MapPointPicker` 의 `start?: PickerStart | null` · `onPick(spot: PickedSpot | null)`(과제 11 - 이 과제는 그 모양에 맞춰 부른다)
- Produces:
```ts
export type CustomPlaceReason = "none" | "noCoords" | "failed" | "direct" | "building" | "parcel" | "pin";
/** 나만의 장소 칸을 여는 값 - 이름은 사용자가 친 검색어, fill 은 공공데이터 지번, openAt 은 위치 찍기를 열 자리(카카오 결과 자리 - 보여 주기만, 저장하지 않는다) */
export type CustomStart = { typedName: string; fill: AddressFill | null; openAt: MapPoint | null };
export type CustomPlaceSubmit = { name: string; address: string | null; geoRef: GeoRef | null; latitude: number | null; longitude: number | null };
PlaceMatchState custom: { status: "custom"; kakaoPlaceId; reason: CustomPlaceReason; pickId: number; start: CustomStart }
PlaceMatchState choose: { status: "choose"; kakaoPlaceId; candidates; fallback: CustomStart }
usePlaceMatch().pick(candidate: PlacePickInput, typedQuery?: string), .startDirect(typedQuery?: string), .chooseCustom()
publicMatchBadge: tone "ready" | "similar" | "fill" | "custom" - none 이면 fill 이 있으면 '주소 채움', 없으면 '위치 찍기'
PlaceMatchChoices props: { candidates; onChoose; onNone; noneLabel?: string }   // 기본 "아니요, 직접 적을게요"(예전 행 확인) - 장소 추가 창(PlaceMatchPanel)은 "아니요, 다른 곳이에요"(시안 v64)
```

- [ ] **Step 1: 기존 시험 고치기**
  - `CustomPlaceForm.test.tsx`(고친 코드는 이 목록 아래에 모았다): 새 `start` prop · 지도 단추 이름 · 초점 규칙이 바뀐다.
    - 1줄 import → `import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";`, 6줄 import → `import { CustomPlaceForm, type CustomPlaceReason, type CustomStart } from "./CustomPlaceForm";`. `renderForm`(14-19줄)은 아래 첫 코드로 바꾼다. `start` 기본값에 `CustomStart` 를 못 박는다 - 안 그러면 `fill` 이 `null` 로 좁혀져 `FILL` 을 넘기는 호출이 타입 오류가 된다. `FILL` · `EMPTY_START` 도 여기서 한 번만 둔다(Step 2 의 새 시험이 같이 쓴다).
    - 지도 단추 이름: 78줄(`queryByRole` - 없다는 단언이라 안 바꾸면 아무것도 못 잡는다) · 110 · 151줄의 `"지도에서 위치 찍기"` → `"지도에서 찾아 위치 찍기"`(89 · 129 · 168줄은 아래에서 통째로 바꾸거나 지우는 시험 안에 있다). 154줄 `getByRole("region", { name: "지도에서 위치 찍기" })` 는 `MapPointPicker` 구역의 `aria-label` 이라 그대로.
    - `explains why it opened`(32-47줄): 새 이유 셋(`building` · `parcel` · `pin`)이 더해져 `Record` 에 키가 모자라 타입 오류이고, 41-43줄이 `renderForm` 을 안 거쳐 `start` 없이 그려 `start.typedName` 에서 런타임 오류가 나며, `direct` 문구(`/찾는 곳의 이름을 직접 적어/`)도 새 소개와 다르다 → 아래 둘째 코드로 통째로 바꾼다.
    - `submits the trimmed name without a point when no point was picked`(57줄) · `submits with Enter and ignores a blank name`(71줄): 기대값을 각각 `{ name: "할머니 댁", address: null, geoRef: null, latitude: null, longitude: null }` · `{ name: "숙소", address: null, geoRef: null, latitude: null, longitude: null }` 로.
    - `lets the user pick a point on the map and submits it with the name`(81-100줄): 지운다 - Step 2 의 `fills the address and the public center from the jibun of the picked spot` 이 대신한다.
    - `lets the user pick the point with the keyboard alone and puts the focus back on cancel`(121-142줄): 아래 셋째 코드로 통째로 바꾼다(`locatePlace` 가짜 · 초점은 담기).
    - `puts the focus back on the open-map button when the map is cancelled`(144-158줄): 단추 이름만 바꾼다. 이름이 비어 있어 담기가 꺼져 있으므로 새 초점 규칙(Step 6)에서도 지도를 다시 여는 단추로 간다. 이름이 있을 때 담기로 가는 것은 Step 2 의 새 시험이 본다.
    - `lets the user clear a picked point before submitting`(160-176줄): `locatePlace` 를 가짜로 두지 않으면 '이 위치로'가 진짜 요청을 보내 '지우기'가 생기지 않고, 기대 본문도 옛 모양이다 → 아래 넷째 코드로 통째로 바꾼다.
    - `starts with an empty name field …`(22줄) · `hides its own cancel and add buttons …`(102줄) · `cancels`(178줄)는 그대로다(위 단추 이름만 바뀐다). `renderForm` 의 기본 `start` 가 빈 `typedName` 이므로 이름이 비고 담기가 꺼진 채 열린다. 이름이 카카오 값이 아니라 사용자가 친 글이라는 것은 Step 2 의 새 시험이 따로 본다.
  - `LegacyPlaceConfirm.test.tsx:64` `{ customPlace: { name: "내가 아는 식당", latitude: null, longitude: null } }` → `{ customPlace: { name: "내가 아는 식당" } }`. 58 · 72줄의 `"아니요, 직접 적을게요"` 는 그대로다 - 예전 행 확인은 `PlaceMatchChoices` 의 기본 문구를 쓴다. `PlaceMatchChoices.test.tsx:81` 도 기본 문구라 고치지 않는다. 페이지 통합 시험 `trip-place-basket.test.tsx:189` 의 같은 단추(장소 추가 창이므로 새 문구)는 과제 12 Step 1 이 고친다.
  - `usePlaceMatch.test.ts`: 새 상태는 custom 에 `start`, choose 에 `fallback` 이 필수이고, 지번 없는 줄의 `reason` 은 `"none"` 이 아니라 `"pin"` 이다(`settle` · `chooseCustom`). `kakaoPick()` 의 좌표가 `openAt` 이 되므로 파일 위쪽 `kakaoPick` 아래에 `const SPOT = { latitude: 34.744, longitude: 127.766 };` 을 두고 고친다.
    - 74줄 `toEqual({ status: "custom", kakaoPlaceId: "8193468", reason: "noCoords", pickId: expect.any(Number), start: { typedName: "", fill: null, openAt: null } })`.
    - 104-108줄 · 376줄 choose `toEqual` 에 `fallback: { typedName: "", fill: null, openAt: SPOT }` 을 더한다.
    - 146 · 158줄 `toEqual({ status: "custom", kakaoPlaceId: "8193468", reason: "pin", pickId: expect.any(Number), start: { typedName: "", fill: null, openAt: SPOT } })`. 200줄(`kakaoPlaceId: null`) · 258줄(`kakaoPlaceId: "2"`)도 같은 모양(`reason: "pin"` + 같은 `start`).
    - 188줄(`reason: "failed"`)에는 `start: { typedName: "", fill: null, openAt: null }` - 실패한 줄은 지도를 결과 자리에서 열지 않는다. 289줄(`startDirect()`)에도 같은 `start`.
    - 171 · 176 · 381 · 394줄 `toMatchObject` 의 `reason: "none"` → `reason: "pin"`.
  - `PlaceMatchPanel.test.tsx`: `import type { CustomStart } from "./CustomPlaceForm";` 와 `odongdo` 아래 `const EMPTY_START: CustomStart = { typedName: "", fill: null, openAt: null };` 을 더하고 고친다.
    - 55-59줄 choose 상태 객체에 `fallback: EMPTY_START,` (없으면 타입 오류). 62줄 `{ name: "아니요, 직접 적을게요" }` → `{ name: "아니요, 다른 곳이에요" }`(장소 추가 창의 새 문구).
    - 69줄 · 90줄 · 94줄 custom 상태 객체에 `start: EMPTY_START` (없으면 타입 오류이고 런타임에서 `start.typedName` 이 터진다). 76줄 기대값 → `{ name: "숙소", address: null, geoRef: null, latitude: null, longitude: null }`.
    - 99-141줄 harness 시험은 그대로 통과한다(`CustomPlaceSubmit` 은 `customBasketItem` 입력에 그대로 들어가고 140줄 본문도 같다).
  - `publicPlaceText.test.ts` 54줄 · 60줄: 기대값 `{ tone: "custom", text: "직접 적기" }` → `{ tone: "custom", text: "위치 찍기" }` (Step 4 의 `publicMatchBadge` 는 `fill` 이 없으면 '위치 찍기').

`CustomPlaceForm.test.tsx` 의 고친 코드. 첫째 - 상수 · `renderForm`(14-19줄 대신):
```tsx
const EMPTY_START: CustomStart = { typedName: "", fill: null, openAt: null };
const FILL = { kind: "parcel" as const, id: 4401, pnu: "1213010200100010006", address: "전남광주통합특별시 여수시 수정동 1-6", latitude: 34.744764, longitude: 127.767783, distanceMeters: 2 };

function renderForm(reason: CustomPlaceReason = "none", start: CustomStart = EMPTY_START) {
  const onSubmit = vi.fn();
  const onCancel = vi.fn();
  render(<CustomPlaceForm fallbackCenter={null} onCancel={onCancel} onSubmit={onSubmit} reason={reason} start={start} tripId="7" />);
  return { onSubmit, onCancel, form: screen.getByRole("form", { name: "나만의 장소" }) };
}
```
둘째 - `explains why it opened`(32-47줄 대신):
```tsx
  it("explains why it opened", () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const expected: Record<CustomPlaceReason, RegExp> = {
      none: /같은 곳을 찾지 못했어요/,
      noCoords: /위치 정보가 없어서/,
      failed: /맞춰 보지 못했어요/,
      direct: /이름을 적고, 지도에서 찾아/,
      building: /건물의 지번으로 주소와 위치를/,
      parcel: /땅의 지번으로 주소와 위치를/,
      pin: /주소를 바로 채우지 못했어요/,
    };
    for (const [reason, text] of Object.entries(expected)) {
      const { form } = renderForm(reason as CustomPlaceReason);
      expect(within(form).getByText(text)).toBeInTheDocument();
      cleanup();
    }
  });
```
셋째 - 키보드만으로 고르기(121-142줄 대신):
```tsx
  it("lets the user pick the spot with the keyboard alone and puts the focus on the add button", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const locate = vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: { ...FILL, kind: "building", distanceMeters: 3 }, nearCenter: true });
    const { form, onSubmit } = renderForm("direct", { typedName: "내 쉼터", fill: null, openAt: null });
    const user = userEvent.setup();

    await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
    // 지도가 열리면 지도에 초점이 있어 바로 방향키를 쓴다
    const map = await within(form).findByRole("application", { name: "위치 고르기 지도" });
    await waitFor(() => expect(map).toHaveFocus());
    await user.keyboard("{ArrowRight}");
    expect(kakao.mapInstances[0].map.panBy).toHaveBeenCalledWith(60, 0);
    kakao.dragMapTo(34.77, 127.67);
    await user.keyboard("{Enter}");

    expect(await within(form).findByText(FILL.address)).toBeInTheDocument();
    expect(locate).toHaveBeenCalledWith(34.77, 127.67);
    // 이름이 있어 담기가 켜져 있다 - 지도가 닫힌 뒤 초점은 담기로
    await waitFor(() => expect(within(form).getByRole("button", { name: "담기" })).toHaveFocus());
    await user.click(within(form).getByRole("button", { name: "담기" }));
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "내 쉼터", address: FILL.address, geoRef: { kind: "building", id: 4401, pin: true }, latitude: FILL.latitude, longitude: FILL.longitude });
  });
```
넷째 - 찍은 자리 지우기(160-176줄 대신):
```tsx
  it("lets the user clear a picked point before submitting", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: { ...FILL, kind: "building", distanceMeters: 3 }, nearCenter: true });
    const { form, onSubmit } = renderForm("direct", { typedName: "내 쉼터", fill: null, openAt: null });
    const user = userEvent.setup();

    await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    act(() => kakao.emitMapClick(34.75, 127.65));
    await user.click(within(form).getByRole("button", { name: "이 위치로" }));
    expect(await within(form).findByText(FILL.address)).toBeInTheDocument();
    await user.click(within(form).getByRole("button", { name: "지우기" }));
    await user.click(within(form).getByRole("button", { name: "담기" }));

    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "내 쉼터", address: null, geoRef: null, latitude: null, longitude: null });
  });
```

- [ ] **Step 2: 실패하는 새 시험 쓰기**

`publicPlaceText.test.ts`:
```ts
it("labels a row without a public match by whether its spot has a jibun", () => {
  const fill = { kind: "parcel" as const, id: 11, pnu: "1213010200100010006", address: "여수시 수정동 1-6", latitude: 34.74, longitude: 127.76, distanceMeters: 2 };
  expect(publicMatchBadge({ result: "none", places: [], fill })).toEqual({ tone: "fill", text: "주소 채움" });
  expect(publicMatchBadge({ result: "none", places: [], fill: null })).toEqual({ tone: "custom", text: "위치 찍기" });
  expect(publicMatchBadge({ result: "none", places: [] })).toEqual({ tone: "custom", text: "위치 찍기" });
});
```

`usePlaceMatch.test.ts`(기존 renderHook 방식):
```ts
const FILL = { kind: "building" as const, id: 501, pnu: "2635010600113910066", address: "부산광역시 해운대구 중동 1391-66", latitude: 35.160131, longitude: 129.161383, distanceMeters: 9 };
const ROW = { id: "kakao:123", title: "카카오 이름(쓰지 않음)", latitude: 35.1602, longitude: 129.1614, categoryCode: "PK6" };

it("opens an address-filled form named by the typed query when the row has a fill", () => {
  const { result } = renderHook(() => usePlaceMatch({ onMatched: vi.fn() }));
  act(() => { void result.current.pick({ ...ROW, publicMatch: { result: "none", places: [], fill: FILL } }, "해운대 공영주차장"); });
  expect(result.current.state).toMatchObject({ status: "custom", reason: "building", kakaoPlaceId: "123",
    start: { typedName: "해운대 공영주차장", fill: FILL, openAt: { latitude: 35.1602, longitude: 129.1614 } } });
  expect(JSON.stringify(result.current.state)).not.toContain("카카오 이름");
});

it("opens the pin picker at the result spot when there is no fill", () => {
  const { result } = renderHook(() => usePlaceMatch({ onMatched: vi.fn() }));
  act(() => { void result.current.pick({ ...ROW, publicMatch: { result: "none", places: [], fill: null } }, "안목해변"); });
  expect(result.current.state).toMatchObject({ status: "custom", reason: "pin", start: { typedName: "안목해변", fill: null, openAt: { latitude: 35.1602, longitude: 129.1614 } } });
});

it("falls from 'not this one' among candidates to the same fill", () => {
  const candidate = { source: "tourapi" as const, sourceId: "1", name: "오동도", latitude: 34.74, longitude: 127.76, category: "sight" as const, distanceMeters: 12 };
  const { result } = renderHook(() => usePlaceMatch({ onMatched: vi.fn() }));
  act(() => { void result.current.pick({ ...ROW, publicMatch: { result: "candidates", places: [candidate], fill: FILL } }, "오동도"); });
  act(() => result.current.chooseCustom());
  expect(result.current.state).toMatchObject({ status: "custom", reason: "building", start: { typedName: "오동도", fill: FILL } });
});

it("starts the last-resort form with the search box text", () => {
  const { result } = renderHook(() => usePlaceMatch({ onMatched: vi.fn() }));
  act(() => result.current.startDirect("친구네 펜션"));
  expect(result.current.state).toMatchObject({ status: "custom", reason: "direct", kakaoPlaceId: null, start: { typedName: "친구네 펜션", fill: null, openAt: null } });
});
```

`CustomPlaceForm.test.tsx`(`FILL` · `EMPTY_START` · `renderForm` · import 는 Step 1 에서 이미 위쪽에 두었다):
```tsx
it("prefills the typed query, shows the public jibun and submits its reference with a pin", async () => {
  vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
  const { form, onSubmit } = renderForm("parcel", { typedName: "오동도 선착장", fill: FILL, openAt: null });
  expect(within(form).getByLabelText("장소 이름")).toHaveValue("오동도 선착장");
  expect(within(form).getByText("내가 친 검색어로 채웠어요 · 고칠 수 있어요")).toBeInTheDocument();
  expect(within(form).getByText(FILL.address)).toBeInTheDocument();
  expect(within(form).getByText("땅 지번 · 국토교통부 공공데이터")).toBeInTheDocument();
  expect(within(form).getByRole("button", { name: "담기" })).toHaveFocus();   // 이름 · 주소가 이미 있다
  await userEvent.setup().click(within(form).getByRole("button", { name: "담기" }));
  expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "오동도 선착장", address: FILL.address, geoRef: { kind: "parcel", id: 4401, pin: true }, latitude: FILL.latitude, longitude: FILL.longitude });
});

it("cuts a long typed query to 100 characters and keeps the button off for an empty one", () => {
  vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
  const long = renderForm("direct", { typedName: "가".repeat(130), fill: null, openAt: null });
  expect((within(long.form).getByLabelText("장소 이름") as HTMLInputElement).value).toHaveLength(100);
  cleanup();
  const empty = renderForm("direct", { typedName: "", fill: null, openAt: null });
  expect(within(empty.form).getByRole("button", { name: "담기" })).toBeDisabled();
  expect(within(empty.form).queryByText("내가 친 검색어로 채웠어요 · 고칠 수 있어요")).not.toBeInTheDocument();
});

it("opens the picker right away at the result spot for a pin row and hides its own buttons", async () => {
  vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
  const kakao = installAppKakaoSdkMock();
  vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
  const { form } = renderForm("pin", { typedName: "안목해변", fill: null, openAt: { latitude: 37.7712, longitude: 128.948 } });
  await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
  expect(kakao.mapInstances[0].options).toMatchObject({ center: { lat: 37.7712, lng: 128.948 } });   // 결과 자리에서 연다(보여 주기만)
  expect(within(form).queryByRole("button", { name: "담기" })).not.toBeInTheDocument();   // 결정 26
});

it("fills the address and the public center from the jibun of the picked spot", async () => {
  vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
  const kakao = installAppKakaoSdkMock();
  vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
  const locate = vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: { ...FILL, kind: "building", distanceMeters: 3 }, nearCenter: true });
  const { form, onSubmit } = renderForm("direct", { typedName: "내 쉼터", fill: null, openAt: null });
  const user = userEvent.setup();
  await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
  await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
  act(() => kakao.emitMapClick(34.75, 127.65));
  await user.click(within(form).getByRole("button", { name: "이 위치로" }));
  expect(locate).toHaveBeenCalledWith(34.75, 127.65);
  expect(await within(form).findByText(FILL.address)).toBeInTheDocument();
  await user.click(within(form).getByRole("button", { name: "담기" }));
  // 찍은 좌표(34.75, 127.65)는 어디에도 없다 - 좌표는 공공데이터 중심
  expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "내 쉼터", address: FILL.address, geoRef: { kind: "building", id: 4401, pin: true }, latitude: FILL.latitude, longitude: FILL.longitude });
});

it("keeps only the address for a wide parcel and only the name where there is no jibun", async () => {
  vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
  const kakao = installAppKakaoSdkMock();
  vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
  const locate = vi.spyOn(appDataApi, "locatePlace").mockResolvedValueOnce({ fill: { ...FILL, distanceMeters: 85 }, nearCenter: false });
  const { form, onSubmit } = renderForm("direct", { typedName: "넓은 공원", fill: null, openAt: null });
  const user = userEvent.setup();
  await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
  await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
  await user.click(within(form).getByRole("button", { name: "이 위치로" }));
  expect(await within(form).findByText("이 땅은 넓어서 핀 없이 주소만 담겨요")).toBeInTheDocument();
  await user.click(within(form).getByRole("button", { name: "담기" }));
  expect(onSubmit).toHaveBeenLastCalledWith({ name: "넓은 공원", address: FILL.address, geoRef: { kind: "parcel", id: 4401, pin: false }, latitude: null, longitude: null });

  locate.mockResolvedValueOnce({ fill: null, nearCenter: false });
  await user.click(within(form).getByRole("button", { name: "다시 찍기" }));
  await user.click(await within(form).findByRole("button", { name: "이 위치로" }));
  expect(await within(form).findByText("이 자리는 지번이 없어 위치 없이 이름만 담겨요")).toBeInTheDocument();
  await user.click(within(form).getByRole("button", { name: "담기" }));
  expect(onSubmit).toHaveBeenLastCalledWith({ name: "넓은 공원", address: null, geoRef: null, latitude: null, longitude: null });
});

it("puts the focus on the add button when the map is cancelled with a name filled in", async () => {
  vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
  installAppKakaoSdkMock();
  vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
  const { form } = renderForm("direct", { typedName: "내 쉼터", fill: null, openAt: null });
  const user = userEvent.setup();

  await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
  await within(form).findByRole("application", { name: "위치 고르기 지도" });
  // 양식 자체의 취소와 지도의 취소가 둘 다 있다 - 지도 쪽을 누른다
  await user.click(within(within(form).getByRole("region", { name: "지도에서 위치 찍기" })).getByRole("button", { name: "취소" }));

  expect(within(form).queryByRole("application")).not.toBeInTheDocument();
  expect(within(form).getByRole("button", { name: "담기" })).toHaveFocus();   // 담기가 켜져 있으면 담기로
});

it("puts the focus on the fix-position button when a spot was picked but the name is still empty", async () => {
  vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
  const kakao = installAppKakaoSdkMock();
  vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
  vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: { ...FILL, kind: "building", distanceMeters: 3 }, nearCenter: true });
  const { form } = renderForm("direct");
  const user = userEvent.setup();

  await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
  await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
  act(() => kakao.emitMapClick(34.75, 127.65));
  await user.click(within(form).getByRole("button", { name: "이 위치로" }));

  expect(await within(form).findByText(FILL.address)).toBeInTheDocument();
  // 이름이 비어 담기가 꺼져 있다 - 꺼진 단추로 보내면 초점이 body 로 떨어지니 지도를 다시 여는 단추로
  expect(within(form).getByRole("button", { name: "담기" })).toBeDisabled();
  await waitFor(() => expect(within(form).getByRole("button", { name: "위치 고치기" })).toHaveFocus());
});

it("keeps the typed name when a place found in the map search only moves the map", async () => {
  vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
  const kakao = installAppKakaoSdkMock();
  vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
  vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([{ kind: "place", id: "kakao:1", name: "해운대 공영주차장", address: "부산 해운대구 중동", latitude: 35.1602, longitude: 129.1614 }]);
  const locate = vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: { ...FILL, kind: "building", distanceMeters: 3 }, nearCenter: true });
  const { form, onSubmit } = renderForm("direct", { typedName: "내 쉼터", fill: null, openAt: null });
  const user = userEvent.setup();

  await user.click(within(form).getByRole("button", { name: "지도에서 찾아 위치 찍기" }));
  await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
  await user.type(within(form).getByRole("textbox", { name: "지도에서 찾기" }), "해운대");
  await user.click(await within(form).findByRole("button", { name: /해운대 공영주차장/ }));

  expect(kakao.mapInstances[0].map.setCenter).toHaveBeenCalledWith(expect.objectContaining({ lat: 35.1602, lng: 129.1614 }));   // 지도만 옮겼다
  expect(within(form).getByLabelText("장소 이름")).toHaveValue("내 쉼터");   // 이름 칸은 그대로
  await user.click(within(form).getByRole("button", { name: "이 위치로" }));
  expect(locate).toHaveBeenCalledWith(35.1602, 129.1614);
  await user.click(await within(form).findByRole("button", { name: "담기" }));
  expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "내 쉼터", address: FILL.address, geoRef: { kind: "building", id: 4401, pin: true }, latitude: FILL.latitude, longitude: FILL.longitude });
  expect(JSON.stringify(onSubmit.mock.calls)).not.toContain("해운대 공영주차장");   // 카카오 이름은 어디에도 실리지 않는다
});
```
(위 세 시험의 `FILL` · `EMPTY_START` · `renderForm` 은 Step 1 의 것이다.)

- [ ] **Step 3: 실패 확인** - `cd frontend && npx vitest run src/components/itinerary` → FAIL.

- [ ] **Step 4: `publicPlaceText.ts`**

```ts
export type PublicMatchBadge = { tone: "ready" | "similar" | "fill" | "custom"; text: string };

export function publicMatchBadge(match: PlaceMatchResult | null | undefined): PublicMatchBadge | null {
  if (!match) return null;
  if (match.result === "match" && match.places.length > 0) return { tone: "ready", text: "바로 담기" };
  if (match.result === "candidates" && match.places.length > 0)
    return { tone: "similar", text: `비슷한 곳 ${Math.min(match.places.length, 3)}` };
  // 시안 v64: 우리 목록에 없으면 그 자리의 건물 · 가까운 땅 지번이 있는지로 가른다
  return match.fill ? { tone: "fill", text: "주소 채움" } : { tone: "custom", text: "위치 찍기" };
}
```

- [ ] **Step 5: `usePlaceMatch.ts`**

파일 위쪽 import 에 `import type { CustomPlaceReason, CustomStart } from "./CustomPlaceForm";` 와 `import type { MapPoint } from "./MapPointPicker";` 를 더한다(타입만 가져오므로 순환 import 가 되지 않는다).

```ts
export type PlaceMatchState =
  | { status: "idle" }
  | { status: "matching" }
  | { status: "choose"; kakaoPlaceId: string | null; candidates: PublicPlaceItem[]; fallback: CustomStart }
  | { status: "custom"; kakaoPlaceId: string | null; reason: CustomPlaceReason; pickId: number; start: CustomStart };

const pointOf = (candidate: PlacePickInput): MapPoint | null =>
  typeof candidate.latitude === "number" && typeof candidate.longitude === "number" && Number.isFinite(candidate.latitude) && Number.isFinite(candidate.longitude)
    ? { latitude: candidate.latitude, longitude: candidate.longitude }
    : null;

  /* 맞춰 본 답을 상태로 옮긴다. 시안 v64: 없으면 지번(fill)으로 주소 채움, 지번도 없으면 그 자리에서 위치 찍기 */
  const settle = useCallback(
    (answer: PlaceMatchResult, kakaoPlaceId: string | null, turn: number, typedName: string, openAt: MapPoint | null) => {
      const [first] = answer.places;
      const start: CustomStart = { typedName, fill: answer.fill ?? null, openAt };
      if (answer.result === "match" && first) {
        commit(IDLE);
        onMatchedRef.current(publicBasketItem(first, kakaoPlaceId));
      } else if (answer.result === "candidates" && answer.places.length > 0) {
        commit({ status: "choose", kakaoPlaceId, candidates: answer.places.slice(0, 3), fallback: start });
      } else {
        commit({ status: "custom", kakaoPlaceId, reason: start.fill ? start.fill.kind : "pin", pickId: turn, start });
      }
    },
    [commit],
  );
```
`pick(candidate, typedQuery = "")`: `const typedName = typedQuery.trim(); const openAt = pointOf(candidate);` - `publicMatch` 가 있으면 `settle(candidate.publicMatch, kakaoPlaceId, turn, typedName, openAt)`, 좌표가 없으면 `commit({ status: "custom", kakaoPlaceId, reason: "noCoords", pickId: turn, start: { typedName, fill: null, openAt: null } })`, 맞춰 보기 실패면 `reason: "failed"` 에 같은 `start`(실패한 줄은 지도를 결과 자리에서 열지 않는다), 답이 오면 `settle(answer, kakaoPlaceId, turn, typedName, openAt)`.
`chooseCustom()`: choose 상태에서 `commit({ status: "custom", kakaoPlaceId: current.kakaoPlaceId, reason: current.fallback.fill ? current.fallback.fill.kind : "pin", pickId: ++turnRef.current, start: current.fallback })`.
`startDirect(typedQuery = "")`: `commit({ status: "custom", kakaoPlaceId: null, reason: "direct", pickId: ++turnRef.current, start: { typedName: typedQuery.trim(), fill: null, openAt: null } })`.
파일 머리 주석: '카카오 이름 · 주소는 상태에 두지 않는다 - 이름은 사용자가 친 검색어(typedName)뿐, openAt 은 지도를 여는 데만 쓰고 저장하지 않는다(151842-3)'.

- [ ] **Step 6: `CustomPlaceForm.tsx`**

```tsx
import { useEffect, useRef, useState, type FormEvent } from "react";
import type { AddressFill, GeoKind, GeoRef } from "../../../api";
import { hasKakaoMapKey } from "../../../lib/kakaoMap";
import { KakaoMapView } from "../../map/KakaoMapView";
import { Button } from "../../ui";
import { MapPointPicker, type MapPoint, type PickedSpot, type PickerStart } from "./MapPointPicker";

export type CustomPlaceReason = "none" | "noCoords" | "failed" | "direct" | "building" | "parcel" | "pin";
export type CustomStart = { typedName: string; fill: AddressFill | null; openAt: MapPoint | null };
export type CustomPlaceSubmit = { name: string; address: string | null; geoRef: GeoRef | null; latitude: number | null; longitude: number | null };

const INTRO: Record<CustomPlaceReason, string> = {
  none: "우리 장소 목록에서 같은 곳을 찾지 못했어요. 이름을 직접 적어 담을 수 있어요.",
  noCoords: "이 장소는 위치 정보가 없어서 우리 장소 목록과 맞춰 보지 못했어요. 이름을 직접 적어 담을 수 있어요.",
  failed: "장소를 맞춰 보지 못했어요. 이름을 직접 적어 담을 수 있어요.",
  // 시안 v64
  direct: "찾는 곳의 이름을 적고, 지도에서 찾아 위치를 찍어 담을 수 있어요(위치는 선택).",
  building: "우리 장소 목록에는 없어서, 이 자리 건물의 지번으로 주소와 위치를 채웠어요. 이름만 확인하고 담으세요.",
  parcel: "우리 장소 목록에는 없어서, 이 자리 땅의 지번으로 주소와 위치를 채웠어요. 이름만 확인하고 담으세요.",
  pin: "이 자리는 주소를 바로 채우지 못했어요. 지도에서 찾거나 옮겨서 정확한 자리를 찍어 주세요. 찍은 자리의 건물 · 땅 지번으로 담겨요.",
};
const SOURCE: Record<GeoKind, string> = { building: "건물 지번", parcel: "땅 지번" };
const fromFill = (fill: AddressFill): PickedSpot => ({
  address: fill.address, geoRef: { kind: fill.kind, id: fill.id, pin: true }, latitude: fill.latitude, longitude: fill.longitude,
});

/* 나만의 장소 - 이름은 사용자가 쓴 글(시안 v64: 사용자가 친 검색어로 미리 - 카카오 이름이 아니다), 주소 · 위치는 건물 · 땅 지번(공공데이터)뿐.
   찍은 좌표는 받지도 보내지도 않는다(데브톡 151842). 이 부품은 카카오 이름을 받는 props 가 아예 없다 */
export function CustomPlaceForm({ reason, start, tripId, fallbackCenter, onSubmit, onCancel }: {
  reason: CustomPlaceReason;
  start: CustomStart;
  tripId: string;
  fallbackCenter: MapPoint | null;
  onSubmit: (input: CustomPlaceSubmit) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(() => start.typedName.slice(0, 100));
  // undefined = 아직 안 찍음, null = 찍었지만 지번 없음(이름만), PickedSpot = 지번(주소 · pin 이면 중심)
  const [spot, setSpot] = useState<PickedSpot | null | undefined>(() => (start.fill ? fromFill(start.fill) : undefined));
  const [pickerStart, setPickerStart] = useState<PickerStart | null>(() =>
    reason === "pin" && start.openAt ? { center: start.openAt, origin: "kakao" } : null,
  );
  const [picking, setPicking] = useState(() => reason === "pin" && start.openAt !== null && hasKakaoMapKey());
  const nameRef = useRef<HTMLInputElement | null>(null);
  const submitRef = useRef<HTMLButtonElement | null>(null);
  const reopenRef = useRef<HTMLButtonElement | null>(null);   // 지도를 다시 여는 단추(위치 고치기 · 다시 찍기 · 지도에서 찾아 위치 찍기 - 화면에는 하나만 있다)
  const wasPicking = useRef(picking);
  const trimmed = name.trim();

  useEffect(() => {
    // 주소가 채워져 열리면 담기 단추로(이름 · 주소가 이미 있다), 아니면 이름 칸으로. 위치 찍기로 바로 열리면 지도가 초점을 가져간다
    if (picking) return;
    if (start.fill && start.typedName) submitRef.current?.focus();
    else nameRef.current?.focus();
  }, []);

  useEffect(() => {
    // 고르기 · 취소로 지도가 닫힌 뒤 초점이 사라지지 않게: 담기가 켜져 있으면 담기로, 꺼져 있으면(이름이 비었다) 지도를 다시 여는 단추로, 그것도 없으면 이름 칸으로.
    // 꺼진 단추에는 focus() 가 먹지 않아 초점이 body 로 떨어진다
    if (wasPicking.current && !picking) {
      const add = submitRef.current;
      (add && !add.disabled ? add : (reopenRef.current ?? nameRef.current))?.focus();
    }
    wasPicking.current = picking;
  }, [picking]);

  const openPicker = (next: PickerStart | null) => {
    setPickerStart(next);
    setPicking(true);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!trimmed || picking) return;   // 결정 26: 찍는 동안에는 담지 않는다
    onSubmit({ name: trimmed, address: spot?.address ?? null, geoRef: spot?.geoRef ?? null, latitude: spot?.latitude ?? null, longitude: spot?.longitude ?? null });
  };

  return (
    <form aria-label="나만의 장소" className="custom-place-form" onSubmit={submit}>
      <p className="custom-place-intro">{INTRO[reason]}</p>
      <label className="field">
        장소 이름
        <input maxLength={100} name="custom-place-name" onChange={(event) => setName(event.target.value)}
          placeholder="예: 할머니 댁, 숙소 앞 편의점" ref={nameRef} value={name} />
      </label>
      {start.typedName && <p className="cpf-hint">내가 친 검색어로 채웠어요 · 고칠 수 있어요</p>}
      {picking ? (
        <MapPointPicker fallbackCenter={fallbackCenter} start={pickerStart} tripId={tripId}
          onCancel={() => setPicking(false)} onPick={(next) => { setSpot(next); setPicking(false); }} />
      ) : spot ? (
        <div className={`custom-place-fill${spot.geoRef?.pin ? "" : " nopin"}`}>
          {spot.geoRef?.pin && spot.latitude !== null && spot.longitude !== null && hasKakaoMapKey() && (
            <KakaoMapView ariaLabel="채운 자리" fallback={null} markers={[{ id: "fill", label: trimmed || "선택한 위치", latitude: spot.latitude, longitude: spot.longitude }]}
              onSelectMarker={() => undefined} selectedMarkerId="fill" />
          )}
          <div className="cpf-fill-body">
            <strong>{spot.geoRef?.pin ? "주소 · 위치" : "주소"}</strong>
            <p>{spot.address}</p>
            <small>{spot.geoRef ? `${SOURCE[spot.geoRef.kind]} · 국토교통부 공공데이터` : "국토교통부 공공데이터"}</small>
            {!spot.geoRef?.pin && <small className="cpf-nopin">이 땅은 넓어서 핀 없이 주소만 담겨요</small>}
          </div>
          <span className="cpf-pair">
            {hasKakaoMapKey() && (
              <button className="btn sm ghost" ref={reopenRef} type="button"
                onClick={() => openPicker(spot.latitude !== null && spot.longitude !== null ? { center: { latitude: spot.latitude, longitude: spot.longitude }, origin: "public" } : null)}>
                {spot.geoRef?.pin ? "위치 고치기" : "다시 찍기"}
              </button>
            )}
            <button className="btn sm ghost" onClick={() => setSpot(undefined)} type="button">지우기</button>
          </span>
        </div>
      ) : spot === null ? (
        <div className="custom-place-point">
          <span>이 자리는 지번이 없어 위치 없이 이름만 담겨요</span>
          <button className="btn sm ghost" onClick={() => openPicker(null)} ref={reopenRef} type="button">다시 찍기</button>
        </div>
      ) : (
        hasKakaoMapKey() && (
          <button className="btn sm line" onClick={() => openPicker(null)} ref={reopenRef} type="button">지도에서 찾아 위치 찍기</button>
        )
      )}
      {!picking && (
        <div className="custom-place-actions">
          <Button onClick={onCancel} variant="line">취소</Button>
          {/* 공용 Button 은 ref 를 넘기지 않는다 - 같은 클래스의 일반 button 으로 초점을 옮긴다 */}
          <button className="btn primary" disabled={!trimmed} ref={submitRef} type="submit">담기</button>
        </div>
      )}
    </form>
  );
}
```
(`KakaoMapView` 의 `fallback` · `onSelectMarker` 는 그 부품의 필수 props 이름에 맞춘다.)

- [ ] **Step 7: `PlaceMatchChoices.tsx` · `PlaceMatchPanel.tsx` · `LegacyPlaceConfirm.tsx`**

PlaceMatchChoices(시안 v64: 장소 추가 창의 '아니요' 는 '다른 곳이에요', 예전 행 확인은 그대로 '직접 적을게요' - 그래서 단추 문구를 prop 으로 받는다):
```tsx
export function PlaceMatchChoices({
  candidates,
  onChoose,
  onNone,
  noneLabel = "아니요, 직접 적을게요",
}: {
  candidates: PublicPlaceItem[];
  onChoose: (place: PublicPlaceItem) => void;
  onNone: () => void;
  /** '맞는 곳이 없다' 단추 문구 - 장소 추가 창(PlaceMatchPanel)은 '아니요, 다른 곳이에요', 예전 행 확인(LegacyPlaceConfirm)은 기본값 */
  noneLabel?: string;
}) {
```
맨 아래 단추의 글 `아니요, 직접 적을게요` 를 `{noneLabel}` 로 바꾼다(그 문구는 기본값으로만 남는다).

PlaceMatchPanel: `PlaceMatchChoices` 에 `noneLabel="아니요, 다른 곳이에요"` 를 넘기고, `CustomPlaceForm` 에 `start={state.start}` 를 넘기고, `onSubmitCustom: (input: CustomPlaceSubmit) => void`.
LegacyPlaceConfirm: `PlaceMatchChoices` 는 건드리지 않는다(기본 문구), `CustomPlaceForm` 에는 `start={{ typedName: "", fill: null, openAt: null }}`(예전 이름은 카카오 값이라 채우지 않는다), `onSubmit={(input) => onReplace({ customPlace: { name: input.name, ...(input.geoRef ? { geoRef: input.geoRef } : {}) } })}`.

- [ ] **Step 8: CSS** - `frontend/src/styles/app.css`(시안 v64 의 `.tps` 규칙을 앱 이름으로)

```css
/* 시안 v64 주소 채움 · 지도에서 찾기 */
.place-search-result-state.fill, .place-preview-state.fill { background: #e8f1fb; color: #1f5f99; }
.cpf-hint { margin: -4px 0 0; color: var(--gray-500); font-size: 11px; font-weight: 700; }
.custom-place-fill { display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: 10px; align-items: start; padding: 10px; border: 1px solid var(--primary-100); border-radius: var(--radius-sm); background: #fff; }
.custom-place-fill.nopin, .custom-place-fill:not(:has(.kakao-map-view)) { grid-template-columns: minmax(0, 1fr); }
.custom-place-fill .kakao-map-view { height: 76px; border-radius: 8px; overflow: hidden; }
.cpf-fill-body { display: grid; gap: 2px; min-width: 0; }
.cpf-fill-body strong { color: var(--gray-600); font-size: 11px; font-weight: 800; }
.cpf-fill-body p { margin: 0; font-size: 14px; font-weight: 800; overflow-wrap: anywhere; }
.cpf-fill-body small { color: var(--gray-500); font-size: 11px; font-weight: 700; }
.cpf-nopin { color: var(--primary-600); font-weight: 800; }
.custom-place-fill .cpf-pair { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: 8px; }
```

- [ ] **Step 9: 통과 확인** - `cd frontend && npx vitest run src/components/itinerary` → PASS(과제 11 의 MapPointPicker 를 아직 고치지 않았으면 이 과제와 함께 고친다 - 두 과제는 같은 묶음으로 돌린다). `npm run typecheck` 의 0 은 여기서 나오지 않는다: `ItineraryDetailPage.tsx` 의 `SEARCH_HELP`(`Record<PublicMatchBadge["tone"], string>` 에 `fill` 키가 없다)와 `addCustomPlace`(`CustomPlaceInput` 을 받는데 `onSubmitCustom` 은 `CustomPlaceSubmit` 을 준다) 두 곳은 과제 12 Step 4 에서야 고쳐진다. 그래서 이 과제에서는 `cd frontend && npm run typecheck 2>&1 | grep "error TS" | grep "src/components/itinerary"` → 출력 없음만 본다. 0 은 과제 12 Step 5 에서 한 번에 확인한다.

- [ ] **Step 10: 변경 확인.**

---

## 과제 11: 위치 찍기 지도 - '지도에서 찾기' · 찍은 자리는 지번으로만(0.5)

**Files:**
- Modify: `frontend/src/components/itinerary/placeAdd/MapPointPicker.tsx`, `frontend/src/styles/app.css`
- Test: `frontend/src/components/itinerary/placeAdd/MapPointPicker.test.tsx`

**Interfaces:**
- Consumes: `appDataApi.searchPlaces`(있음 - `GET /api/places/search`, 지도만 옮긴다), `appDataApi.locatePlace`(과제 9)
- Produces:
```ts
export type PickerStart = { center: MapPoint; origin: "kakao" | "public" };
/** 찍은 자리를 담는 값 - 지번 주소와 참조, pin 이면 공공데이터 중심. 찍은 좌표는 들어 있지 않다 */
export type PickedSpot = { address: string; geoRef: GeoRef; latitude: number | null; longitude: number | null };
export function spotFromLocate(located: LocateResult): PickedSpot | null;   // null = 지번 없음(이름만)
MapPointPicker props: { tripId; fallbackCenter?; start?: PickerStart | null; onPick: (spot: PickedSpot | null) => void; onCancel }
```

- [ ] **Step 1: 기존 시험 고치기** - '이 위치로'가 이제 `locatePlace` 를 부르고 `onPick` 에 지번(또는 null)을 넘긴다.
  - `openPicker(area, fallbackCenter = null, start: PickerStart | null = null)` 로 넓혀 `render(<MapPointPicker … start={start} … />)` 하고, 기본 가짜 `const locate = vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: BUILDING, nearCenter: true })` 를 두고 `locate` 를 돌려준다(`BUILDING = { kind: "building" as const, id: 501, pnu: "2635010600113910066", address: "부산광역시 해운대구 중동 1391-66", latitude: 35.160131, longitude: 129.161383, distanceMeters: 9 }` - `kind` 에 `as const` 를 붙인다. 안 붙이면 `kind` 가 `string` 으로 넓어져 `locate` 의 `mockResolvedValue` 와 아래 `answer` 가 `GeoKind` 와 안 맞아 `npm run typecheck` 에서 걸린다).
  - 시험 파일 머리 import 를 `import { appDataApi, type ItineraryPlace, type LocateResult } from "../../../api";` 와 `import { KOREA_CENTER, MapPointPicker, firstPublicPlacePoint, pickerStart, spotFromLocate, type PickerStart } from "./MapPointPicker";` 로 바꾼다(`LocateResult` 는 아래 `answer` 타입에, `spotFromLocate` 는 새 시험에, `PickerStart` 는 `openPicker` 에 쓴다).
  - 좌표로 `onPick` 을 단언하던 넷(`opens on the trip area center … picks the point the crosshair ends on` · `moves the center to the clicked point instead of dropping a pin` · `is a labelled map the keyboard can use…` · `tells a screen reader where the center is…`)은 같은 좌표가 **`locate` 의 인자**인지(`expect(locate).toHaveBeenCalledWith(34.744312, 127.766399)` 처럼 소수 여섯 자리)와 `onPick` 이 `spotFromLocate` 결과(`{ address, geoRef: { kind: "building", id: 501, pin: true }, latitude: 35.160131, longitude: 129.161383 }`)인지로 바꾼다. 찍은 좌표가 `onPick` 에 실리지 않는 것이 이 시험의 요점이다.
  - `never starts from a Kakao point - area center, then the trip's own public place…` 는 `pickerStart()`(start prop 이 없을 때)의 시험이라 그대로 둔다. 이름만 `opens on the area center, then the trip's own public place, when no start is given` 으로.

- [ ] **Step 2: 실패하는 새 시험 쓰기**

```ts
const FAR = { kind: "parcel" as const, id: 77, pnu: "4215011500100010000", address: "강릉시 견소동 1", latitude: 37.77, longitude: 128.95, distanceMeters: 85 };

describe("spotFromLocate", () => {
  it("keeps the public center for a building or a near parcel, only the address for a wide parcel, nothing without a jibun", () => {
    expect(spotFromLocate({ fill: BUILDING, nearCenter: true })).toEqual({ address: BUILDING.address, geoRef: { kind: "building", id: 501, pin: true }, latitude: 35.160131, longitude: 129.161383 });
    expect(spotFromLocate({ fill: FAR, nearCenter: false })).toEqual({ address: "강릉시 견소동 1", geoRef: { kind: "parcel", id: 77, pin: false }, latitude: null, longitude: null });
    expect(spotFromLocate({ fill: null, nearCenter: false })).toBeNull();
  });
});

it("opens at the result spot when a start is given and still never hands out the picked coordinates", async () => {
  const { kakao, onPick, locate } = openPicker({ latitude: 34.76, longitude: 127.66 }, null, { center: { latitude: 37.7712, longitude: 128.948 }, origin: "kakao" });
  await waitFor(() => expect(kakao.mapInstances[0]?.options).toMatchObject({ center: { lat: 37.7712, lng: 128.948 }, level: 3 }));
  locate.mockResolvedValueOnce({ fill: null, nearCenter: false });
  await userEvent.setup().click(screen.getByRole("button", { name: "이 위치로" }));
  await waitFor(() => expect(onPick).toHaveBeenCalledExactlyOnceWith(null));   // 지번 없음 - 카카오 결과 좌표는 담지 않는다(151842-4)
});

it("moves the map to a place found in the map search without touching the name and asks for its jibun on pick", async () => {
  const { kakao, onPick, locate } = openPicker({ latitude: 34.76, longitude: 127.66 });
  vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([{ kind: "place", id: "kakao:1", name: "해운대 공영주차장", address: "부산 해운대구 중동", latitude: 35.1602, longitude: 129.1614 }]);
  const user = userEvent.setup();
  await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
  await user.type(screen.getByRole("textbox", { name: "지도에서 찾기" }), "해운대");
  const result = await screen.findByRole("button", { name: /해운대 공영주차장/ });
  expect(screen.getByRole("list", { name: "지도에서 찾기 결과" })).toContainElement(result);
  await user.click(result);
  expect(kakao.mapInstances[0].map.setCenter).toHaveBeenLastCalledWith(expect.objectContaining({ lat: 35.1602, lng: 129.1614 }));   // 지도만 옮겼다
  expect(screen.getByText(/‘해운대 공영주차장’ 자리로 옮겼어요/)).toBeInTheDocument();   // 상태 줄이 둘이라 role 로 고르지 않는다
  expect(screen.getByRole("application", { name: "위치 고르기 지도" })).toHaveFocus();   // 고른 뒤 지도로
  await user.click(screen.getByRole("button", { name: "이 위치로" }));
  expect(locate).toHaveBeenCalledWith(35.1602, 129.1614);
  expect(onPick).toHaveBeenCalledExactlyOnceWith({ address: BUILDING.address, geoRef: { kind: "building", id: 501, pin: true }, latitude: BUILDING.latitude, longitude: BUILDING.longitude });
});

it("ignores a late jibun answer when the map stopped after asking, lets the user pick again, and tells the user when asking failed", async () => {
  const { kakao, onPick, locate } = openPicker({ latitude: 34.76, longitude: 127.66 });
  let answer: (value: LocateResult) => void = () => undefined;
  locate.mockImplementationOnce(() => new Promise<LocateResult>((resolve) => { answer = resolve; }));
  const user = userEvent.setup();
  await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
  const confirm = screen.getByRole("button", { name: "이 위치로" });
  await waitFor(() => expect(confirm).toBeEnabled());
  await user.click(confirm);
  expect(confirm).toBeDisabled();   // 묻는 동안은 꺼 둔다
  kakao.dragMapTo(34.8, 127.7);   // 묻는 동안 지도를 옮기고
  act(() => kakao.emitMapIdle());   // 멈춘다 - 실제 지도는 끌기가 끝나면 idle 을 낸다. 물음을 무르고 '이 위치로'를 다시 켠다
  expect(confirm).toBeEnabled();
  await act(async () => answer({ fill: BUILDING, nearCenter: true }));
  expect(onPick).not.toHaveBeenCalled();   // 늦은 답은 버린다(코덱스 MEDIUM)
  expect(confirm).toBeEnabled();   // 버린 답이 단추를 다시 잠그지 않는다
  locate.mockRejectedValueOnce(new Error("network"));
  await user.click(confirm);
  expect(await screen.findByRole("alert")).toHaveTextContent("지번을 확인하지 못했어요. 다시 찍거나 취소하고 이름만 담아 주세요.");
  expect(onPick).not.toHaveBeenCalled();
});

it("also ignores a late jibun answer for a spot the map already left before it reported idle", async () => {
  const { kakao, onPick, locate } = openPicker({ latitude: 34.76, longitude: 127.66 });
  let answer: (value: LocateResult) => void = () => undefined;
  locate.mockImplementationOnce(() => new Promise<LocateResult>((resolve) => { answer = resolve; }));
  await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
  const confirm = screen.getByRole("button", { name: "이 위치로" });
  await waitFor(() => expect(confirm).toBeEnabled());
  await userEvent.setup().click(confirm);
  kakao.dragMapTo(34.8, 127.7);   // idle 은 아직 안 냈다 - 방향키로 옮긴 직후처럼
  await act(async () => answer({ fill: BUILDING, nearCenter: true }));
  expect(onPick).not.toHaveBeenCalled();   // 십자선 밑이 달라졌으니 버린다
  expect(confirm).toBeEnabled();   // 답이 왔으니 다시 누를 수 있다
});
```
(`installAppKakaoSdkMock()` 은 `mapInstances[i].map.setCenter`(부른 값 `{lat, lng, …}` - `toHaveBeenLastCalledWith(expect.objectContaining({ lat, lng }))` 로 본다. `map.getCenter` 는 `ReturnType<typeof vi.fn>` 타입이라 시험 코드에서 바로 부르면 타입 검사(TS2348)에 걸린다) · `dragMapTo(lat, lng)`(끌기 - 가운데만 옮기고 idle 은 내지 않는다) · `emitMapIdle()`(멈춤 - 실제 지도는 끌기가 끝나면 낸다) · `emitMapClick(lat, lng)` 를 준다 - 지금 시험들이 쓰는 그대로다.)

- [ ] **Step 3: 실패 확인** - `cd frontend && npx vitest run src/components/itinerary/placeAdd/MapPointPicker.test.tsx` → FAIL.

- [ ] **Step 4: 구현** - `MapPointPicker.tsx`

```ts
const CLOSE_LEVEL = 3;

/* 계획 0.5 - 찍은 자리는 그 자리를 품은 건물 · 땅의 지번으로만 담는다(데브톡 151842 · 151916-4). 찍은 좌표는 여기서 버린다:
   건물이거나 땅 중심이 가까우면 공공데이터 중심까지, 넓은 땅이면 주소만, 지번이 없으면 null(이름만) */
export function spotFromLocate(located: LocateResult): PickedSpot | null {
  const fill = located.fill;
  if (!fill) return null;
  const pin = located.nearCenter;
  return { address: fill.address, geoRef: { kind: fill.kind, id: fill.id, pin }, latitude: pin ? fill.latitude : null, longitude: pin ? fill.longitude : null };
}
```
맨 위 `../../../api` import 를 `import { appDataApi, useAsyncResource, type GeoRef, type ItineraryPlace, type LocateResult, type TripAreaCenter } from "../../../api";` 로 바꾼다.
컴포넌트 안:
- 시작: `start` 가 있으면 `{ center: start.center, level: CLOSE_LEVEL }`, 없으면 지금의 `pickerStart(area, fallbackCenter)`. 파일 머리의 '고른 카카오 장소의 좌표로는 열지 않는다' 주석은 '카카오 결과 자리 · 지도에서 찾기 결과 자리에서 열거나 옮길 수 있다 - 보여 주기만(151842-3). 담는 것은 spotFromLocate 가 정한 지번뿐'으로 바꾼다.
- 지도에서 찾기(시안 v64): 지도 위에 `<label className="field">지도에서 찾기<input …/></label>`, 300ms 뒤 `appDataApi.searchPlaces(q, { signal })`(앞 요청은 `AbortController` 로 끊는다), 좌표가 있는 결과 4개까지 `<ul className="mpp-results" aria-label="지도에서 찾기 결과">` 안 `<li><button className="mpp-result">이름 · 주소</button></li>`(보여 주기만 - 이름 칸은 건드리지 않는다). 누르면 `map.setCenter(new kakao.maps.LatLng(lat, lng)); map.setLevel(CLOSE_LEVEL); setMoved(name); setFailed(false)` 하고 검색 칸을 비우고 지도 칸에 초점을 둔다. Esc 는 결과를 닫는다.
  옮긴 뒤 한 줄: `<p className="mpp-moved" role="status">‘{name}’ 자리로 옮겼어요. 십자선을 정확한 자리에 맞추고 ‘이 위치로’를 누르세요.</p>`.
- 상태 셋을 `failed` 옆(`useEffect` 위)에 더한다. `askRef` 는 `useEffect` 안의 `readCenter` 도 쓰므로 `pickCenter` 가 아니라 여기 둔다:
```ts
  const [asking, setAsking] = useState(false);   // 지번을 묻는 동안 '이 위치로'를 끈다
  const [locateFailed, setLocateFailed] = useState(false);
  const askRef = useRef(0);   // 물음 번호 - 올리면 그 전 물음의 늦은 답은 버려진다. 올리는 쪽이 asking 도 맡는다(pickCenter 는 true, 지도가 멈추면 false)
```
- 지도가 멈추면 진행 중인 물음을 무르고 '이 위치로'를 다시 켠다. `useEffect` 안의 `readCenter` 를 아래로 바꾼다(`idle` 리스너와 처음 한 번 부르는 자리는 그대로):
```ts
        const readCenter = () => {
          if (disposed) return;
          askRef.current += 1;   // 묻는 중이던 물음의 늦은 답은 pickCenter 의 askRef 비교에서 버려진다
          setAsking(false);   // 여기서 안 풀면 무른 물음의 답이 asking 을 풀 길이 없어 '이 위치로'가 취소 전까지 꺼져 있다
          setCenterPoint(centerOf(map));
        };
```
- `pickCenter`(비동기, 늦은 답 버리기):
```ts
  const pickCenter = async () => {
    const map = mapRef.current;
    if (!map) return;
    const point = centerOf(map);
    if (!isInKorea(point)) return;
    const ask = ++askRef.current;
    setAsking(true);
    setLocateFailed(false);
    let located: LocateResult;
    try {
      located = await appDataApi.locatePlace(point.latitude, point.longitude);
    } catch {
      if (askRef.current === ask) { setAsking(false); setLocateFailed(true); }
      return;
    }
    if (askRef.current !== ask) return;   // 지도가 멈추며 이미 무른 물음이다 - asking 은 그때 풀었다
    setAsking(false);
    const now = mapRef.current ? centerOf(mapRef.current) : null;
    if (!now || now.latitude !== point.latitude || now.longitude !== point.longitude) return;   // 묻는 동안 지도가 움직였다 - 다시 고르게 둔다
    onPick(spotFromLocate(located));
  };
```
  실패 문구(시안 v64): `{locateFailed && <p className="form-error" role="alert">지번을 확인하지 못했어요. 다시 찍거나 취소하고 이름만 담아 주세요.</p>}`. '이 위치로' 는 `asking` 동안 꺼 둔다: `<button … disabled={!inside || asking} …>`. 지도가 멈출 때 물음을 무르고 `asking` 을 푸는 것은 위 `readCenter` 가 한다.

CSS(app.css):
```css
.map-point-picker-search { display: grid; gap: 6px; }
.mpp-results { display: grid; gap: 4px; margin: 0; padding: 0; list-style: none; }
.mpp-result { display: grid; gap: 2px; width: 100%; min-height: 44px; padding: 8px 10px; border: 1px solid var(--gray-200); border-radius: 8px; background: #fff; text-align: left; }
.mpp-result strong { font-size: 13px; }
.mpp-result small { color: var(--gray-500); font-size: 11px; }
.mpp-moved { margin: 0; color: var(--primary-600); font-size: 12px; font-weight: 800; }
```

- [ ] **Step 5: 통과 확인** - `cd frontend && npx vitest run src/components/itinerary` → PASS. `npm run typecheck` 는 아직 0 이 아니다 - 페이지 쪽 오류(`ItineraryDetailPage.tsx` 의 `SEARCH_HELP` 에 `fill` 키가 없고, `addCustomPlace` 가 새 `onSubmitCustom` 타입에 안 맞는다)는 과제 12 가 고치고, 0 은 과제 12 Step 5 에서 확인한다. 이 과제에서는 `npm run typecheck` 출력에 `placeAdd/MapPointPicker` 가 든 줄이 없는지만 본다.

- [ ] **Step 6: 변경 확인.**

---

## 과제 12: 일정 상세 연결 - 친 검색어 · 바구니 · 미리보기 문구 · 상세 출처 · 404/503 문구

**Files:**
- Modify: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`
- Test: `frontend/src/app/__tests__/trip-place-basket.test.tsx`, `frontend/src/app/__tests__/place-edit.test.tsx`, `frontend/src/app/__tests__/trip-legacy-place.test.tsx`, `frontend/src/app/__tests__/trip-detail.test.tsx`, `frontend/e2e-backend/backend-mode.spec.ts`

**Interfaces:**
- Consumes: `usePlaceMatch().pick(candidate, typedQuery)` · `.startDirect(typedQuery)`(과제 10), `CustomPlaceSubmit`, `customBasketItem`(과제 9)
- Produces: `PlaceEditorSheet` 의 `matchPanel?: (typedQuery: string) => ReactNode` - 시트가 검색 칸에 **지금 적힌 글**(350ms 대기 전 값)을 넘겨 준다. 페이지의 `placeSearchQuery` 는 대기 뒤에야 바뀌어서, 친 직후 누르는 '직접 적기'가 그것을 읽으면 이름이 빈다.

- [ ] **Step 1: 기존 시험 고치기** - `trip-place-basket.test.tsx`(시안 v64 문구 · 이름 미리 채움 · 찍은 좌표 없음). 나만의 장소 칸의 이름은 이제 검색 칸에 **친 글**(`searchAndPick` 의 검색어)로 열린다. `toHaveValue("")` 던 곳은 그 글로 바꾸고, 이름 칸에 `user.type` 하던 곳은 글이 이어 붙으니 앞에 `await user.clear(…)` 를 넣는다. 각 시험 이름 앞의 `:번호` 는 지금 파일의 줄 번호다.
  - `:178 lets the user say none of the candidates is right and write the place by hand, starting from an empty name` → 제목 끝을 `starting from the typed words` 로. `:189` 단추 이름 `"아니요, 직접 적을게요"` → `"아니요, 다른 곳이에요"`(과제 10 의 `noneLabel` - 추가 창에서만 이 문구). `:194` `expect(name).toHaveValue("")` → `toHaveValue("바다")` 로 바꾸고 바로 아래에 `expect(form).toHaveTextContent("주소를 바로 채우지 못했어요")`(후보에 fill 이 없어 '위치 찍기' 소개이고, 지도 키 스텁이 없어 지도는 안 열린다). `:199` `await user.type(name, "  우리가 가던 횟집  ");` 앞에 `await user.clear(name);`. 카카오 이름이 안 보이는 단언과 저장 본문 `{ name: "우리가 가던 횟집" }` 은 그대로.
  - `:217 opens the custom place form straight away when nothing matches` → 지번 없는 줄이라 '위치 찍기': `:226` `toHaveValue("")` → `toHaveValue("새로")`, `:227` `"같은 곳을 찾지 못했어요"` → `"주소를 바로 채우지 못했어요"`(지도 키가 없으면 칸이 `pin` 소개 문구로 열린다). `:228` 의 카카오 이름이 안 보이는 단언은 그대로.
  - `:231 asks for a name without calling match when the picked place has no coordinates` → `:240` 아래에 `expect(within(form).getByLabelText("장소 이름")).toHaveValue("좌표");` 를 더한다(지금은 이름 단언이 없다). `:244 falls back to the custom place form when matching fails` → `:256` `toHaveValue("")` → `toHaveValue("맞춰")`.
  - `:259 lets the user write a place by hand without searching, …` 는 그대로다 - 후보를 고르면 검색 칸이 비워져서 직접 적기가 빈 이름으로 열리고 `user.type` 이 이어 붙지 않는다.
  - `:350 starts the custom place form empty for each picked result, even when two results without coordinates come in a row` → 제목을 `starts the custom place form from the words typed for each picked result, even when two results without coordinates come in a row` 로. `:361` 위에 `expect(within(first).getByLabelText("장소 이름")).toHaveValue("첫째");`, `:365` `toHaveValue("")` → `toHaveValue("둘째")`(앞 줄에 적던 글이 남지 않고 이 줄을 고를 때의 검색어로 새로 채워진다), `:366` `user.type` 앞에 `await user.clear(within(second).getByLabelText("장소 이름"));`. 저장 본문 `{ name: "둘째에 적은 이름" }` 과 `not.toContain("첫째")` 는 그대로.
  - `:460 says the place search is unavailable on a 503, …` → 검색이 실패해도 칸의 글 `여수` 가 직접 적기의 이름으로 미리 찬다. `:481` 한 줄 `await user.type(within(form).getByLabelText("장소 이름"), "여수 밤바다 쉼터");` 을 `const name = within(form).getByLabelText("장소 이름");` · `expect(name).toHaveValue("여수");` · `await user.clear(name);` · `await user.type(name, "여수 밤바다 쉼터");` 네 줄로. 저장 본문 `{ customPlace: { name: "여수 밤바다 쉼터" } }` 은 그대로.
  - `:505 marks each row with its prematched path …` · `:535 opens the candidates or the own-place form right away …` → `:520` · `:551` 의 `"죽녹원 앞 노점 선택, 직접 적기"` → `"죽녹원 앞 노점 선택, 위치 찍기"`, `:553` `toHaveValue("")` → `toHaveValue("죽녹원 앞")`(그 줄을 고를 때 검색 칸에 있던 글. 앞 후보를 고르면 목록이 비워지므로 새 결과가 와야 단추가 생겨 대기와 겹치지 않는다).
  - `:292 saves a custom place with a point picked on the map that opened on the trip area, not on the Kakao place` → 아래 새 시험으로 `:292-323` 을 통째로 바꾼다. 지번 없는 줄은 지도 키가 있으면 `지도에서 위치 찍기` 단추 없이 지도가 처음부터 열리고(과제 10 의 `picking` 초기값), 카카오 결과 자리에서 열리며, 저장 본문에는 위도 · 경도 대신 지번 참조가 간다. 그래서 옛 시험의 단추 클릭 · `areaSpy` 호출 단언 · 가운데 `35.5/127.7` 단언 · 본문 `latitude`/`longitude` 가 모두 맞지 않는다. 이 시험이 쓰는 `BUILDING_FILL` 은 여기서 파일 머리에 한 번만 두고, Step 2 의 새 시험은 그것을 쓴다.
  - `trip-legacy-place.test.tsx:121` `customPlace: { name: "내가 아는 식당", latitude: null, longitude: null }` → `customPlace: { name: "내가 아는 식당" }`.
  - `trip-detail.test.tsx:3438 goes to the custom-place step with only the Kakao id when the handed-over place cannot be found again` → 홈에서 넘어온 친 말 `오동도` 가 이름으로 미리 찬다(`openAddPlace(…, handoff.query)`). `:3452` 주석의 `(빈 이름 칸)` → `(이름은 넘어온 친 말 오동도)`, `:3454` `toHaveValue("")` → `toHaveValue("오동도")`, `:3457` `await user.type(within(form).getByLabelText("장소 이름"), "오동도 앞 매점");` 앞에 `await user.clear(within(form).getByLabelText("장소 이름"));`. 저장 본문 `{ name: "오동도 앞 매점" }` · `kakaoPlaceId: "8193468"` 은 그대로.
  - `frontend/e2e-backend/backend-mode.spec.ts` 의 390폭 구간(`:374-384`, 검색어 `후보없는수동장소` 를 넣고 `검색 결과가 없어요` 를 본 뒤 직접 적기) → `:378` 주석의 `카카오 이름 없이 빈 채로 시작한다` 를 `검색 칸에 친 글(후보없는수동장소)이 이름으로 미리 찬다 - 카카오 이름은 아니다` 로, `:384` `await expect(customName).toHaveValue("");` → `await expect(customName).toHaveValue("후보없는수동장소");`. `:362` 의 폭 순회는 검색어 없이 누르므로 이름이 `""` 라 그대로.

`trip-place-basket.test.tsx` 파일 머리(`expectNoKakaoValues` 함수 아래)에 한 번만 더한다:

```tsx
const BUILDING_FILL = { kind: "building" as const, id: 501, pnu: "2635010600113910066", address: "부산광역시 해운대구 중동 1391-66", latitude: 35.160131, longitude: 129.161383, distanceMeters: 9 };
```

`:292-323` 의 새 시험:

```tsx
  it("saves the jibun of the spot picked on the map, never the picked coordinates", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    const trip = addTrip("99");
    mockSearch(kakaoCandidate("8008", "동네 쉼터", { latitude: 33.4584, longitude: 126.9425 }));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "none", places: [] });
    // 일정 지역 중심(옛 시험과 같은 값): 지도는 이 응답을 기다린 뒤 열리므로 지우지 않는다. 열리는 자리는 이 값(35.5, 127.7)이 아니라 카카오 결과 자리여야 한다
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 35.5, longitude: 127.7 });
    const locateSpy = vi.spyOn(appDataApi, "locatePlace").mockResolvedValue({ fill: BUILDING_FILL, nearCenter: true });
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "동네", "동네 쉼터");
    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    // 지번이 없는 줄(fill 없음)은 위치 찍기 - 단추를 누르지 않아도 지도가 열려 있고, 카카오 결과 자리(33.4584, 126.9425)에서 열린다(보여 주기만)
    expect(within(form).queryByRole("button", { name: "지도에서 찾아 위치 찍기" })).not.toBeInTheDocument();
    await waitFor(() =>
      expect(kakao.mapInstances[kakao.mapInstances.length - 1].options).toMatchObject({ center: { lat: 33.4584, lng: 126.9425 } }),
    );
    const name = within(form).getByLabelText("장소 이름");
    expect(name).toHaveValue("동네");   // 친 검색어 - 카카오 이름("동네 쉼터")이 아니다
    await user.clear(name);
    await user.type(name, "우리 쉼터");

    act(() => kakao.emitMapClick(35.51, 127.71));
    await user.click(within(form).getByRole("button", { name: "이 위치로" }));
    // 찍은 좌표는 우리 서버에 지번을 묻는 데만 쓰고, 고른 뒤에는 지번 주소만 보인다
    await waitFor(() => expect(locateSpy).toHaveBeenCalledWith(35.51, 127.71));
    expect(await within(form).findByText(BUILDING_FILL.address)).toBeInTheDocument();
    await user.click(within(form).getByRole("button", { name: "담기" }));
    await user.click(await within(dialog).findByRole("button", { name: "Day 1에 1개 저장하기" }));

    await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
    expect(addBatchSpy).toHaveBeenCalledWith("99", 1, {
      expectedRevision: 3,
      places: [{ customPlace: { name: "우리 쉼터", geoRef: { kind: "building", id: 501, pin: true } }, kakaoPlaceId: "8008" }],
    });
    // 찍은 좌표도 카카오 결과 좌표도 요청에 없다
    expect(JSON.stringify(addBatchSpy.mock.calls[0][2])).not.toMatch(/35\.51|127\.71|33\.4584|126\.9425/);
    expectNoKakaoValues(addBatchSpy.mock.calls[0][2]);
  });
```

- [ ] **Step 2: 실패하는 새 시험 쓰기** - `trip-place-basket.test.tsx`

```tsx
// BUILDING_FILL 은 Step 1 에서 파일 머리에 더한 것을 쓴다

it("fills a no-match row from its jibun, names it by the typed query and saves only the reference (시안 v64)", async () => {
  const trip = addTrip("120");
  mockSearch(kakaoCandidate("8601", "해운대 공영주차장", { categoryCode: "PK6", publicMatch: { result: "none", places: [], fill: BUILDING_FILL } }));
  const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
  const { user, dialog } = await openAddSheet(trip);

  fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "해운대 공영" } });
  await user.click(await within(dialog).findByRole("button", { name: "해운대 공영주차장 선택, 주소 채움" }));
  const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
  expect(within(form).getByLabelText("장소 이름")).toHaveValue("해운대 공영");   // 친 검색어 - 카카오 이름이 아니다
  expect(form).toHaveTextContent(BUILDING_FILL.address);
  await user.click(within(form).getByRole("button", { name: "담기" }));
  await user.click(await within(dialog).findByRole("button", { name: "Day 1에 1개 저장하기" }));

  await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
  expect(addBatchSpy).toHaveBeenCalledWith("120", 1, {
    expectedRevision: 3,
    places: [{ customPlace: { name: "해운대 공영", geoRef: { kind: "building", id: 501, pin: true } }, kakaoPlaceId: "8601" }],
  });
  expectNoKakaoValues(addBatchSpy.mock.calls[0][2]);
});

it("opens the last-resort form with the search text as the name even when pressed before the search fires, and keeps it open after the search runs", async () => {
  const trip = addTrip("121");
  const searchSpy = mockSearch();
  const { user, dialog } = await openAddSheet(trip);
  fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "친구네 펜션" } });
  // 350ms 대기 안에 누른다 - 아직 검색이 나가지 않았고 페이지의 검색어 상태는 비어 있다. 칸의 글을 넘겨야 이름이 찬다
  expect(searchSpy).not.toHaveBeenCalled();
  await user.click(within(dialog).getByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" }));
  const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
  expect(within(form).getByLabelText("장소 이름")).toHaveValue("친구네 펜션");
  // 대기가 끝나 검색이 나가도 열어 둔 칸을 닫지 않는다(칠 때 이미 맞춰 보던 것을 놓았다)
  await waitFor(() => expect(searchSpy).toHaveBeenCalledTimes(1));
  expect(within(dialog).getByRole("form", { name: "나만의 장소" })).toBeInTheDocument();
  expect(within(dialog).getByLabelText("장소 이름")).toHaveValue("친구네 펜션");
});

it("turns geo-filled basket rows into names only when their jibun disappeared in the monthly refresh", async () => {
  const trip = addTrip("122");
  mockSearch(kakaoCandidate("8602", "해운대 공영주차장", { categoryCode: "PK6", publicMatch: { result: "none", places: [], fill: BUILDING_FILL } }));
  const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces")
    .mockRejectedValueOnce(new ApiError("Address reference not found", { status: 404, statusText: "Not Found", detail: "Address reference not found" }))
    .mockResolvedValueOnce({ ...trip, revision: 4 });
  const { user, dialog } = await openAddSheet(trip);
  fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "해운대 공영" } });
  await user.click(await within(dialog).findByRole("button", { name: "해운대 공영주차장 선택, 주소 채움" }));
  await user.click(within(await within(dialog).findByRole("form", { name: "나만의 장소" })).getByRole("button", { name: "담기" }));
  await user.click(await within(dialog).findByRole("button", { name: "Day 1에 1개 저장하기" }));

  expect(await within(dialog).findByText("주소 정보가 바뀌어 위치를 뺐어요. 위치가 필요하면 다시 찾아 담아 주세요.")).toBeInTheDocument();   // 시트의 저장 오류 줄(form-error)에는 역할이 없다
  expect(dialog).toHaveTextContent("위치 없이 이름만");
  await user.click(within(dialog).getByRole("button", { name: "Day 1에 1개 저장하기" }));
  expect(addBatchSpy).toHaveBeenLastCalledWith("122", 1, { expectedRevision: 3, places: [{ customPlace: { name: "해운대 공영" }, kakaoPlaceId: "8602" }] });
});
```
(`ApiError` 는 `frontend/src/api/client.ts` 의 `(message, { status, statusText, detail })` - `place-edit.test.tsx:166` 과 같은 꼴. 이 시험 파일은 이미 `ApiError` 를 import 한다.)

`place-edit.test.tsx`(`renames a public place …` 시험 아래, 같은 `describe` 안):

```tsx
  it("shows the address and its public source line on a custom place that was filled from a jibun", async () => {
    const address = "전남광주통합특별시 여수시 수정동 1-6";
    const filledRow: ItineraryPlace = {
      id: "1",
      time: "09:00",
      label: "우리 쉼터",
      meta: address,
      address,
      latitude: 34.744764,
      longitude: 127.767783,
      placeOrigin: "custom",
      geoKind: "parcel",
    };
    const trip: Trip = { ...getPreviewTrip(), id: "84", revision: 3, currentUserRole: "owner", days: { 1: [filledRow] } };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/84");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: "우리 쉼터 상세 열기" }));
      const sheet = await screen.findByRole("dialog", { name: "장소 수정" });

      const fields = sheet.querySelector(".place-detail-fields") as HTMLElement;
      expect(fields).toHaveTextContent(address);
      expect(fields).toHaveTextContent("주소: 국토교통부 공공데이터(땅 지번)");
    } finally {
      getTripSpy.mockRestore();
    }
  });
```

- [ ] **Step 3: 실패 확인** - `cd frontend && npx vitest run src/app/__tests__/trip-place-basket.test.tsx src/app/__tests__/place-edit.test.tsx src/app/__tests__/trip-legacy-place.test.tsx src/app/__tests__/trip-detail.test.tsx` → FAIL.

- [ ] **Step 4: 구현**

- `selectPlaceSearchCandidate`: 맨 앞에서 `const typedQuery = placeSearchQuery;`(검색 칸을 비우기 전) 를 쥐고, 끝을 `void placeMatch.pick(candidate, typedQuery);` 로. 후보 단추는 칸의 글과 검색어가 다른 동안(`isSearchPending`) 꺼져 있어서, 눌릴 때 `placeSearchQuery` 는 칸의 글과 같다(공백만 다를 수 있고 `pick` 이 `trim` 한다).
- 홈 넘김: `openAddPlace(initial?: PlacePickInput, typedQuery = "")` → `if (initial) void placeMatch.pick(initial, typedQuery);`, 부르는 곳은 `openAddPlace(…, handoff.query)`.
- 직접 적기는 **칸에 지금 적힌 글**을 쓴다. 페이지의 `placeSearchQuery` 는 시트의 `updateInputSearchQuery` 가 350ms(`PLACE_SEARCH_DEBOUNCE_MS`) 기다린 뒤에야 바뀌어서, 친 직후 입구를 누르면 `startDirect("")` 가 되어 이름이 빈다. 시트가 자기 `inputSearchQuery` 를 넘기게 한다(`ItineraryDetailPage.tsx`, 줄 번호는 지금 파일):
  - `PlaceEditorSheet` props 타입 `:5933-5934` 의 `matchPanel?: ReactNode;` → `matchPanel?: (typedQuery: string) => ReactNode;`, 위 주석 끝에 '칸에 지금 적힌 글을 받는다' 를 더한다.
  - 시트 본문 `:6162` 의 `{matchPanel}` → `{matchPanel?.(inputSearchQuery)}`.
  - 페이지 `:4585-4598` 의 `matchPanel` 을 함수로 바꾼다. `onStartDirect={placeMatch.startDirect}` 를 그대로 두면 클릭 이벤트가 `typedQuery` 로 들어가므로 반드시 감싼다(`startDirect` 가 `trim` 한다).
```tsx
          matchPanel={
            placeEditor.mode === "add"
              ? (typedQuery) => (
                  <PlaceMatchPanel
                    fallbackCenter={firstPublicPlacePoint(trip.days)}
                    onCancel={placeMatch.reset}
                    onChooseCandidate={placeMatch.chooseCandidate}
                    onChooseCustom={placeMatch.chooseCustom}
                    onStartDirect={() => placeMatch.startDirect(typedQuery)}
                    onSubmitCustom={addCustomPlace}
                    state={placeMatch.state}
                    tripId={trip.id}
                  />
                )
              : undefined
          }
```
  `trip-detail.test.tsx:131` 은 `PlaceEditorSheet` 를 `matchPanel` 없이 그리므로 고치지 않는다.
- 대기가 끝나 부르는 `updatePlaceSearchQuery`(`:3163`)의 `invalidatePlaceSearch();` 한 줄을 아래 두 줄로 바꾼다. 칠 때마다 `onSearchInput`(= `invalidatePlaceSearch`)이 맞춰 보던 것을 이미 놓았는데, 대기가 끝나 여기서 또 `placeMatch.reset()` 하면 친 직후 '직접 적기'로 연 칸이 350ms 뒤에 닫히고 적던 이름이 사라진다(Step 2 의 새 시험이 이것을 잡는다).
```ts
    // 맞춰 보던 것은 칠 때(onSearchInput)에 이미 놓았다 - 여기서는 앞 검색 요청만 무른다
    placeSearchRequestRef.current += 1;
    cancelPendingPlaceSearch();
```
- `addCustomPlace = (input: CustomPlaceSubmit) => { const current = placeMatch.state; if (current.status !== "custom") return; addToBasket(customBasketItem(input, current.kakaoPlaceId)); placeMatch.reset(); }`.
- 미리보기 문구(`SEARCH_HELP`):
```ts
  const SEARCH_HELP: Record<PublicMatchBadge["tone"], string> = {
    ready: "우리 장소 목록에 있는 곳이에요. 누르면 바로 담겨요.",
    similar: "비슷한 곳을 찾았어요. 누르면 맞는 곳을 고를 수 있어요.",
    // 시안 v64
    fill: "우리 장소 목록에는 없지만 이 자리의 지번으로 주소와 위치를 채울 수 있어요. 누르면 이름만 확인하고 담아요.",
    custom: "이 자리는 주소를 바로 채우지 못했어요. 누르면 지도에서 찾거나 찍어서 담아요.",
  };
```
- 지도 미리보기 배지 클래스(`PlacePreviewMapCard` 의 `stateClass`, `:5714-5715`): `place-preview-state${badge.tone === "ready" ? " ready" : badge.tone === "similar" ? " similar" : ""}` → `` `place-preview-state ${badge.tone}` ``(검색 결과 줄 `:6150` 과 같은 꼴이다. 새 CSS `.place-preview-state.fill` 이 붙어야 '주소 채움' 배지에 색이 입혀진다. `custom` 은 규칙이 없어 모양이 그대로다).
- 장소 상세(`PlaceSheetDetail`, `:5843`): `showAddress = Boolean(place.address) || !isOwn` 는 이미 주소가 있는 나만의 장소를 보이므로 조건은 그대로 둔다. 주소 칸의 `<p>{place.address || "주소 정보 없음"}</p>` 바로 아래에 한 줄만 더한다.
```tsx
            {place.geoKind && <small>{`주소: 국토교통부 공공데이터(${place.geoKind === "building" ? "건물 지번" : "땅 지번"})`}</small>}
```
- 저장 오류: `isMissingTripDay` 옆에
```ts
export function isMissingAddressReference(error: unknown): boolean {
  return isApiError(error) && error.status === 404 && error.detail === "Address reference not found";
}
export function isAddressLookupUnavailable(error: unknown): boolean {
  return isApiError(error) && error.status === 503 && error.detail === "Address lookup is unavailable";
}
```
  묶음 저장 실패에서 `isMissingAddressReference` 면 바구니의 `geoRef` 가 있는 custom 칸을 모두 `{ ...item, address: null, geoRef: null, latitude: null, longitude: null }` 로 바꾸고 `"주소 정보가 바뀌어 위치를 뺐어요. 위치가 필요하면 다시 찾아 담아 주세요."`(판이 바뀌면 모든 id 가 함께 사라진다). 이 문구는 `setPlaceError` 로 시트의 저장 오류 줄(`<p className="form-error">`, 역할 없음)에 뜬다. `isAddressLookupUnavailable` 이면 바구니는 그대로 `"지금 주소를 확인할 수 없어요. 잠시 뒤 다시 저장해 주세요."`. 단일 저장 · 수정(예전 행 확인)도 같은 두 문구.

- [ ] **Step 5: 통과 확인** - `cd frontend && npm run typecheck && npx vitest run src/app/__tests__ src/components/itinerary` → 0 · PASS(기존 mypage 6개 실패는 기준선 그대로인지 이름으로 확인). e2e 파일(`backend-mode.spec.ts`)은 타입 검사 대상이 아니라 과제 14 Step 7 의 `npm run test:e2e` 에서 돈다.

- [ ] **Step 6: 변경 확인.**

---

## 과제 13: 계약 · 골든 · 설계 문서 · 기능 명세 · 스키마 문서 · 운영 문서

**Files:**
- Modify: `docs/mvp-api-contract.md`, `.agent/evals/api-contract-golden.json`, `backend/tests/test_places_contract_docs.py`,
  `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`, `docs/implemented-feature-spec.md`, `docs/screen-feature-status-logic.md`,
  `docs/db-schema-current.md`, `docs/db-schema-current.sql`
- Create: `docs/geo-reference-monthly-load.md`

- [ ] **Step 1: 실패하는 시험 쓰기** - `backend/tests/test_places_contract_docs.py`(기존 publicMatch 시험 옆, 같은 파일의 경로 상수를 쓴다)

```python
def test_the_contract_documents_address_fill_locate_and_geo_reference_without_raw_coordinates() -> None:
    contract = CONTRACT   # 이 파일 위에서 docs/mvp-api-contract.md 를 읽어 둔 모듈 상수
    for needle in ("publicMatch.fill", "POST /api/places/locate", "nearCenter", "customPlace.geoRef", "Address reference not found",
                   "Address lookup is unavailable", "geoKind", "151842"):
        assert needle in contract, needle
    # 나만의 장소는 이름 · 지번 참조뿐 - 위도 · 경도를 받지 않는다는 문장이 계약에 있다
    assert "위도 · 경도 · 주소는 받지 않음" in contract
    assert "/api/places/locate" in json.dumps(GOLDEN, ensure_ascii=False)   # GOLDEN: 같은 파일의 골든 모듈 상수
```

- [ ] **Step 2: 실패 확인** - `cd backend && python -m pytest tests/test_places_contract_docs.py -q` → FAIL.

- [ ] **Step 3: 문서 쓰기**

1. `docs/mvp-api-contract.md`
   - 장소 검색(`GET /api/trips/{id}/place-search`)과 맞춰 보기(`POST /api/places/match`)의 `publicMatch` 에 `publicMatch.fill`(`AddressFill | null` - kind · id · pnu · address · latitude · longitude · distanceMeters, match 가 아니고 건물이거나 땅 중심 30m 안일 때만, 국토교통부 공공데이터 값, id 는 판마다 바뀜) 한 절.
   - 새 절 `POST /api/places/locate` - 요청 `{latitude, longitude}`(extra 422, 범위 밖 422), 응답 `{fill: AddressFill | null, nearCenter: boolean}`, 로그인 필요(401), 받은 좌표는 저장 · 로그하지 않음(데브톡 151842 · 151916-4).
   - 장소 담기 · 수정의 `customPlace` 를 `{name, geoRef?}` 로: `customPlace.geoRef` = `{kind, id, pin}`(extra 422) - 서버가 geo 표에서 주소와(pin 이면) 중심을 채움. **위도 · 경도 · 주소는 받지 않음(422)** - 지도에서 찍은 좌표는 저장 · 활용 불가(151842). 오류 `404 Address reference not found`, `503 Address lookup is unavailable`(둘 다 revision 그대로). 3단계 때 있던 `customPlace.latitude/longitude` 예시는 지운다.
   - `ItineraryPlace.geoKind`(`"building" | "parcel" | null`) - 주소 채움으로 담긴 나만의 장소의 지번 종류.
2. `.agent/evals/api-contract-golden.json` - v62 때 `publicMatch` 를 더한 방식 그대로 `publicMatch.fill: "object|null"`, `POST /api/places/locate` 응답 필드(`fill` · `nearCenter`), 담기 요청 `customPlace` 의 필드가 `name` · `geoRef` 뿐인 것, 일정 장소 `geoKind`.
3. 설계 문서 `2026-10-03-public-place-storage-design.md`
   - 2절 '위치 찍기': '고른 카카오 장소의 좌표로는 열지 않는다' → '카카오 결과 자리 · 지도에서 찾기 결과 자리에서 열거나 옮길 수 있다(보여 주기만 - 151842-3). **찍은 좌표는 저장하지 않는다**(151842-1 "지정 좌표의 DB 저장 및 활용은 불가합니다") - 찍은 자리를 품은 건물 · 땅의 지번 참조로만 담는다(151916-4): 가까우면 공공데이터 중심까지, 넓은 땅은 주소만, 지번이 없으면 이름만'.
   - 2절 '나만의 장소': '이름 칸은 비어 있다' → '이름은 사용자가 친 검색어로 미리 채운다(151505-4c). 카카오 이름은 어디에도 나오지 않는다(151505 추가 질문)'. '나만의 장소의 위치(사용자가 찍은 좌표)' 문장은 지운다.
   - 3절 '데이터 출처'에 건물(GIS건물통합정보, 공공누리 1유형) · 땅(연속지적도, CC BY, 농지 · 임야 제외) · 월 1회 갱신 · 출처 표시 · 브이월드 API 를 쓰지 않는 까닭.
   - 새 절 'geo 표': 스키마 `geo`, 공유 시퀀스 id(판이 바뀌면 옛 id 404), 30m · 지목 기준, manifest · 좌표계 검사, 바꿔치기, 백업 · 로컬 복사 제외, 크기(0.2 · 과제 14 실측).
4. `docs/implemented-feature-spec.md` '장소 담기(공공데이터 · 나만의 장소)' 줄 - 주소 채움 · 위치 찍기(지번으로만) · 지도에서 찾기 · 직접 적기(최후).
5. `docs/screen-feature-status-logic.md` 3-A · 3-B · 3-C - 결과 줄 배지 넷, 나만의 장소 칸의 이유(direct · building · parcel · pin · 기존 셋), 주소만 · 이름만 · 지번 묻기 실패 문구, 바구니 404 · 503 문구.
6. `docs/db-schema-current.md` · `.sql` - `geo` 스키마(시퀀스 · 네 표 · 색인), `trip_places.geo_kind` · `geo_pnu` · `ck_trip_places_geo_kind`.
7. `docs/geo-reference-monthly-load.md`(운영):
   - 받을 것: 브이월드 'GIS건물통합정보'(AL_D010) · '연속지적도형정보'(AL_D002), 구분 '전체데이터', 최신 기준일, 시도 16개 전부(`EXPECTED_REGION_CODES` - 전남 · 광주는 2026-07 부터 통합 코드 12). 500MB 넘는 파일은 '선택다운로드'. 로그인이 필요해 사람이 받는다. 새 판은 키 없는 카탈로그 API(`https://api.vworld.kr/ned/dtmk/getDatasetList.do?format=json&ds_nm=…`)로 알 수 있다. 시도 코드가 바뀌면 `EXPECTED_REGION_CODES` 를 고치는 PR 이 먼저다.
   - 검사(넘길 수 없음): 파일 이름 · 시도 코드 · 기준일 하나 · 같은 파일 두 번 · 같은 내용(sha256) · 좌표계(5186, 5174 는 변환) · 중복률 · 식별자 빈 줄 · 지목 못 읽음 · 법정동 빠짐 - 하나라도 어긋나면 바꾸지 않는다(종료 코드 3 · 4). 파일을 다시 받거나 고친 뒤 다시 돌린다.
   - 행 수 범위(종료 코드 8)만 판이 정말 커지거나 줄었음을 확인한 뒤 `--accept-row-count-change` 로 받아들이고, 다음 PR 에서 `ROW_BOUNDS` 를 고친다.
   - 잠금: 적재는 DB 연결 하나를 끝까지 쥐고 advisory lock 을 건다. 종료 코드 7 이면 `select pid from pg_locks where locktype = 'advisory'` 로 남은 잠금을 확인한다.
   - 돌리기: 과제 14 의 명령(로컬) · 과제 15 의 명령(개발서버 · AWS). 걸리는 시간 · 크기 · 최대 디스크 · WAL(과제 14 실측값).
     Windows 의 Git Bash 에서는 `docker run` 앞에 `MSYS_NO_PATHCONV=1` 을 붙인다(안 붙이면 `/data/...` 가 Windows 경로로 바뀌어 종료 코드 2). 리눅스 서버에는 필요 없다.
   - 품질 검사(같은 식별자 비율 · 고유번호 · 식별자가 없거나 잘못된 줄 · 지목 못 읽음)로 종료 코드 3 이 나면 파일 문제가 아니라 판의 성질이 바뀐 것일 수 있다 - 숫자를 들고 판단하고, 상수(`MAX_DUP_RATIO` 등)를 실측에 맞추는 PR(과제 2 시험 함께) 뒤에 다시 돌린다. 넘기는 옵션은 없다.
   - 운영 배포: db 이미지를 PostGIS 로 바꾼 첫 배포는 마이그레이션 앞에서 db 를 다시 만들어야 한다(과제 1 Step 7 · 과제 15 Step 6).
   - 확인: `select (select count(*) from geo.building), (select count(*) from geo.parcel), (select max(finished_at) from geo.load_run)`.
   - 백업: `pg_dump … --exclude-schema=geo`(원본 파일에서 다시 넣을 수 있다). 로컬 정책 복사 스크립트도 geo 를 건드리지 않는다.
   - 실패: 바꿔치기 앞에서 멈추면 지금 표는 그대로, `*_next` 는 다음 실행이 지운다. 바꿔치기는 잠금 5초 · 3번 시도 뒤 멈춘다(종료 코드 6). 다른 적재가 돌면 종료 코드 5.
   - 출처 표시: 화면의 '국토교통부 공공데이터'(GIS건물통합정보 공공누리 1유형 · 연속지적도 CC BY).

- [ ] **Step 4: 통과 확인** - `cd backend && python -m pytest tests/test_places_contract_docs.py -q` → PASS. `git diff --check` 깨끗, 바뀐 한국어 문서에 U+FFFD · 엉뚱한 한자 없음.

- [ ] **Step 5: 변경 확인.**

---

## 과제 14: 로컬 적재 · 실측 게이트 · 전체 검증

모두 로컬이다(개발서버 · 사용자 크롬은 건드리지 않는다). 출력은 건수 · 시간 · 크기뿐. 카카오 값은 메모리에서만 견주고 버린다.

- [ ] **Step 1: 빈 표 상태의 검색 시간(기준선)** - 적재 전에 42개 검색어를 세 번씩 `GET /api/trips/479/place-search` 로 불러 p50 · p95 를 적는다(scratchpad 스크립트, 결과는 숫자만).

- [ ] **Step 2: 디스크 확인** - Docker 데이터가 C: 에 있다(DISK-LAYOUT). 적재는 vhdx 를 약 12~15GB(+ 적재 중 임시 공간) 키우고 줄어들지 않는다. `Get-PSDrive C` 여유가 40GB 이상인지 보고, 모자라면 멈추고 사용자에게 묻는다.

- [ ] **Step 3: 적재 + 최대 디스크 · WAL 재기**

```bash
docker build --target geo-loader -t th-geo-loader backend
docker network ls --format '{{.Name}}' | grep travel-hunter-onprem
# 적재하는 동안 1분마다 DB 크기 · WAL 크기를 숫자만 적는다(scratchpad 의 작은 반복 스크립트, 끝나면 최댓값만 남긴다)
# Git Bash 는 /data/... 를 Windows 경로로 바꾼다 - MSYS_NO_PATHCONV=1 이 없으면 파일을 못 찾아 종료 코드 2
time MSYS_NO_PATHCONV=1 docker run --rm --network <위 네트워크> --env-file <3단계 backend 와 같은 env> -v "<받은 파일 폴더>:/data:ro" th-geo-loader \
  python scripts/geo_load.py --buildings /data/buildings --parcels /data/parcels
MSYS_NO_PATHCONV=1 docker exec travel-hunter-onprem-db-1 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "select count(*) from geo.building; select count(*) from geo.parcel; select count(*) from geo.legal_dong; select pg_size_pretty(pg_total_relation_size(\$\$geo.building\$\$)), pg_size_pretty(pg_total_relation_size(\$\$geo.parcel\$\$)); select building_base_date, parcel_base_date from geo.load_run order by id desc limit 1"'
```
Expected: 종료 코드 0, 건물 약 1,439만 줄, 땅 약 1,950만 줄(3,987만의 49%), 크기 합 약 11~12GB(추산 - 실측값을 적는다), 기준일 20260909 · 20260908. 걸린 시간, **적재 중 최대 DB 크기 · 최대 WAL** 을 적는다.
적재 도구가 도는 동안 한 번 `select count(*) from pg_locks where locktype = 'advisory'` 가 1 인지 본다(과제 8 의 advisory lock 이 commit 을 넘어 유지되는지).
`ROW_BOUNDS` 가 실측과 15% 넘게 다르면 그 값을 실측 ±15% 로 고친다(과제 2 시험도 함께). 적재 도구가 종료 코드 8(행 수 범위)로 멈췄다면 숫자를 확인한 뒤에만 `--accept-row-count-change` 로 다시 돌린다 - 구조 검사(3 · 4)로 멈췄다면 원인을 본다: 파일 이름 · 시도 · 기준일 · 같은 파일 · 좌표계 · 법정동이면 파일을 다시 받거나 고친다. 품질 상수(같은 식별자 비율 · 고유번호나 식별자가 없거나 잘못된 줄 · 지목 못 읽음)면 판의 성질이 바뀐 것일 수 있다 - 숫자를 들고 사용자에게 묻고, 상수를 고치는 변경(과제 2 시험 함께)을 승인받은 뒤 다시 돌린다. 넘기는 옵션은 없다.

- [ ] **Step 4: 자동 처리 비율 게이트(80%)와 정확도** - backend 를 다시 띄우고 248줄(검색어 42개, 일정 479)을 실제 API 로: `publicMatch.result` · `publicMatch.fill` 로 바로 담기 · 비슷한 곳 · 주소 채움 · 위치 찍기를 센다.
  정확도: 주소 채움 줄마다 **카카오 결과의 지번 주소(검색 응답의 `address`)와 채운 지번을 메모리에서만 견준다**(법정동 · 본번이 같은지, 부번까지 같은지) - 건수 · 비율만 출력하고 값은 버린다.
  Expected: 자동(바로 담기 + 비슷한 곳 + 주소 채움) **80% 초과**(예상 88%, 첫 줄 98%). 80% 이하면 멈추고 숫자를 들고 사용자에게 묻는다.
  정확도 게이트(`match` 가 아닌 줄 가운데 채움이 붙고 카카오 주소가 지번 꼴인 줄만 센다): **법정동 · 본번 일치 80% 이상 · 법정동부터 다른 줄 3% 이하**.
  근거는 0.2 의 실측(일치 95% · 다름 0/142). 실측보다 낮게 둔 것은 카카오 결과가 바뀌고 판 · 서버가 달라서다 - 이 게이트는 좌표계 · 법정동 코드 · 파일 뒤바뀜처럼 일치율이 0 쪽으로 무너지는 고장을 잡는다.
  미달이면 멈추고 갈래(건물 · 땅)별 숫자와 원인 후보(같은 필지의 다른 건물 · 경계 · 30m 기준)를 들고 사용자에게 묻는다.

- [ ] **Step 5: 속도 게이트**
  - 데워진 상태: Step 1 과 같은 방법으로 다시 잰다. 검색 p95 증가 **10ms 이하**. `POST /api/places/locate` 를 부산 공공데이터 장소 둘레 100점으로 불러 잰다 - 지오 부분은 끝에서 끝까지의 HTTP p95 가 아니라 **DB 시간(`EXPLAIN ANALYZE` 5ms 이하)과 적중 대 미적중의 차이**로 가린다. 로컬 Docker 호스트에서는 HTTP 왕복만으로 기준선이 약 16ms 라 20ms 는 지오 비용을 가리지 못한다(실측: locate p95 33ms · 미적중 31ms · DB 0.35ms).
  - 재시작 직후: db 컨테이너를 다시 띄우고 처음 50번의 검색 p50 · p95 · 첫 번째를 적는다. 기준: **첫 검색 3초 이하 · 처음 50번 p95 500ms 이하**(벤치마크의 재시작 직후 1.2~2.4초 · 차가운 p95 70~280ms 에 카카오 왕복을 더한 값).
  - 동시: 검색 10개를 동시에 5번 - 기준: **p95 600ms 이하**(데워진 상태).
  - 실행 계획: 6곳 묶음 `LOCATE_SQL` 하나를 `EXPLAIN (ANALYZE, BUFFERS)` 로 - 두 GiST 색인을 타는지(Index Scan / Bitmap), shared hit · read 수를 적는다.
  하나라도 기준을 넘거나 색인을 안 타면 멈추고 원인과 숫자를 들고 사용자에게 묻는다(배포 전 게이트).

- [ ] **Step 6: PostGIS 시험** - 빈 시험 DB 를 따로 띄워 과제 3 · 6 · 8 의 PostGIS 시험을 돌리고 지운다(적재 시험은 적재 의존성 + psycopg 가 있는 venv 에서 - 5186 · 5174 적재 위치, 3857 거부, commit 을 넘는 잠금 · 두 번째 적재 거절).
```bash
docker run -d --name th-geo-test --label purpose=geo-test -p 127.0.0.1:56433:5432 -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=geo postgis/postgis:16-3.5-alpine
# 초기화 중 임시 서버는 TCP 를 열지 않는다 - 127.0.0.1 로 받을 때까지 기다린다
until docker exec th-geo-test pg_isready -h 127.0.0.1 -U postgres -d geo -q; do sleep 1; done
export RUN_POSTGIS_TESTS=1 POSTGIS_TEST_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:56433/geo
(cd backend && python -m pytest tests/test_geo_repository_postgis.py -q)
(cd backend && <requirements-geo 를 깐 venv>/python -m pytest tests/test_geo_load_postgis.py -q)
unset RUN_POSTGIS_TESTS POSTGIS_TEST_DATABASE_URL
docker rm -f -v th-geo-test
```

- [ ] **Step 7: 전체 검증**

```bash
(cd backend && python -m pytest -q && alembic upgrade head --sql > /dev/null && echo SQL-OK)
(cd frontend && npm run typecheck && npm test && npm run build && npm run test:e2e)
git diff --check
```
Expected: 백엔드 전부 통과, 프론트 타입 0 · 시험은 mypage 기준선 6개 말고 통과 · 빌드 OK · e2e 통과(3단계 13개 + 이 계획에서 바뀐 흐름). 실패는 이름 · 출력 그대로 기록한다.

- [ ] **Step 8: 로컬 런타임 연결** - 4173(빌드본) · 5173(Vite) 을 이 워크트리로 다시 띄우고 확인 목록을 사용자에게 넘긴다(사용자가 브라우저로 확인 - 크롬에 붙지 않는다). 지도 키(`VITE_KAKAO_MAP_JS_KEY`)가 비어 있으면 위치 찍기 · 지도에서 찾기 · 작은 지도는 숨는다고 적는다.
  확인 목록: 결과 줄 배지 넷 · 주소 채움 [담기] 한 번 · 위치 찍기(그 자리에서 열림, 찍으면 지번 · 넓은 땅 주소만 · 지번 없으면 이름만) · 지도에서 찾기(이름 칸 그대로) · 비슷한 곳 '아니요, 다른 곳이에요' · 직접 적기(검색 칸 글이 이름) · 저장 뒤 타임라인 주소 · 상세 출처 줄 · 폭 390 · 1440.

---

## 과제 15: 개발서버(머지 뒤, 실행할 때마다 승인) · AWS 메모

개발서버 작업은 머지 뒤 하나씩 승인받고 돈다. 서버 env 파일은 사용자가 고친다(줄과 값 없는 확인 명령만 전한다). TourAPI 키 교체 대기 중이니 TourAPI 관련 서버 작업 전에는 한 번 묻는다.

- [ ] **Step 1: 개발서버 DB 덤프**(권한 600, 저장소 밖) - 이미지 바꾸기 전.
- [ ] **Step 2: 배포** - 과제 1 Step 7 의 Jenkinsfile 이 마이그레이션 앞에서 `up -d --no-deps --wait db` 로 db 컨테이너를 PostGIS 이미지로 다시 만든다(같은 볼륨, 몇 초 끊김). 그 뒤 `run --rm backend python -m alembic upgrade head` 가 0050 을 올린다. 확인: `postgis_lib_version()` · 버전 표 · 앱 표 행 수 그대로.
- [ ] **Step 3: 파일 올리기 · 적재** - 받은 zip(건물 약 2.4GB · 땅 약 6.6GB)을 서버의 저장소 밖 폴더로 옮기고, 서버 backend 와 같은 env 파일로 `th-geo-loader` 를 돌린다(과제 14 Step 3 과 같은 명령, 네트워크 · 경로만 서버 것 - 리눅스라 `MSYS_NO_PATHCONV` 는 빼도 된다). 확인 질의 · 걸린 시간 · 크기 · 최대 디스크를 적는다.
- [ ] **Step 4: 서버 실측** - 검색 p95 · locate p95 · 248줄 자동 비율(개발서버 시험 계정).
- [ ] **Step 5: 백업 제외** - 서버의 정기 백업이 `pg_dump` 를 쓰면 `--exclude-schema=geo` 한 줄을 사용자에게 전한다.
- [ ] **Step 6: 운영(온프레미스) 승격 전 게이트** - main 에 올리기 전에 끝낸다. 하나하나 사용자에게 묻고 승인받는다.
  - 왜: 운영 Jenkins(`ci/prod-jenkins` 의 `deploy/jenkins/prod/Jenkinsfile`)도 마이그레이션(`run --rm backend`)이 `up -d` 앞이라, 고치지 않으면 첫 승격 배포가 옛 postgres 컨테이너에서 `CREATE EXTENSION postgis` 로 멈춘다(과제 1 Step 7 끝).
  - 운영 db 덤프(권한 600, 저장소 밖) · `pg_restore -l` 로 목록 확인 · 보호 표 여섯 건수(과제 1 Step 1 의 질의)를 먼저 적는다.
  - 방법은 사용자가 고른다(권장 (가)):
    (가) 보호 브랜치 `ci/prod-jenkins` 의 'Run DB Migration' 앞에 과제 1 Step 7 과 같은 `up -d --no-deps --wait --wait-timeout 120 db` 를 넣는 변경 - 보호 브랜치라 사용자가 만들고 머지한다(Claude 는 문안만 준다).
    (나) 첫 승격 배포가 마이그레이션에서 안전하게 멈추면, 운영 서버의 체크아웃 폴더에서 승인받고 db 만 compose 정의대로 다시 만든 뒤(`docker compose -p prodtravelhunterapp --env-file <운영 env 파일> -f compose.yaml up -d --no-deps --wait --wait-timeout 120 db` - 값 출력 없음) 파이프라인을 다시 돌린다. db 가 몇 초 끊긴다.
  - 확인: `postgis_lib_version()` · `alembic_version` · 보호 표 여섯 건수가 덤프 때와 같은지.
  - 운영 적재는 그 뒤 따로(Step 3 과 같은 명령, 실행할 때마다 승인). 적재 전에는 `fill` 이 늘 null 이라 화면은 위치 찍기 · 이름만으로 떨어진다(기능이 꺼진 것과 같고 오류는 없다).

**AWS(운영 구축 때 - 이 계획에서는 문서만):**
- 프로비저닝: RDS PostgreSQL 16 을 만든 뒤 **마스터 사용자(rds_superuser)가 `CREATE EXTENSION postgis;`** 를 먼저 돌린다. 0050 은 확장이 있으면 건너뛴다(앱 사용자에게 확장 권한이 없어도 된다).
- 저장공간: (앱 1GB 미만 + geo 실측 크기) + 월 갱신 동안 새 표(같은 크기) + 적재 중 WAL · GiST 임시 공간(과제 14 Step 3 실측 최대치) → **실측 최대 사용량의 1.5 배 이상**을 처음 크기로, gp3 + 자동 확장 상한을 그 2 배로(RDS 는 늘린 공간을 줄일 수 없고, 바꾼 뒤 6시간은 다시 못 바꾼다). 지금 추산으로는 30GB 대.
- 메모리: 6곳 묶음 찾기가 늘 2ms 대이려면 geo 색인(약 1.5GB)과 자주 찾는 지역이 메모리에 있어야 한다 → **메모리 4GB 이상 인스턴스**부터, 버퍼 적중률(`pg_statio_user_indexes`)을 보고 조정.
- 재시작 직후 첫 질의(1~2초): 배포 · 재시작 뒤 `pg_prewarm` 으로 geo 색인을 올리거나 데우기 질의 한 번.
- 월 적재: 받은 파일을 S3 에 두고, 운영 네트워크 안의 일회성 컨테이너(`th-geo-loader`)가 내려받아 돌린다.

---

## 자체 점검(작성자)

- **설계 요약과 과제의 대응:** 갈래 순서(과제 4 · 10 · 12) · 이름은 검색어(10 · 12) · 지도에서 찾기(11) · 30m(2 · 4 · 5) · 지목 제외(2 · 8) · 찍은 좌표 저장 금지(5 · 6 · 9 · 10 · 11 · 13) · 넓은 땅 주소만 · 지번 없음 이름만(5 · 10 · 11) · DB 별도 영역 · 바꿔치기 · 넘길 수 없는 구조 검사 · 연결 하나에 붙은 적재 잠금 · CRS · 백업 제외(1 · 2 · 8 · 13 · 15) · 배지 문구(10) · 카카오 연결 재사용 · 오류 로그(7) · 출처 표시(10 · 12 · 13) · 80% · 정확도 · 재시작 직후 · 동시 요청 게이트(14).
- **코덱스 재검토 2차:** 0.7 표의 열네 줄 중 열세 줄을 해당 과제에 넣었다. 서명된 `geoRef.pin` 토큰 하나는 이유를 적고 반영하지 않았다.
- **자체 교차 검토(0.8):** 확인된 55개(37개)를 모두 고쳤다. 과제 2 · 3 · 8 은 계획서 코드 그대로 22개 시험(PostGIS 4)이 통과했다.
- **이름 · 모양 일치:** 서버 `AddressFill`(kind · id · pnu · address · latitude · longitude · distanceMeters) = 화면 `AddressFill`. `LocateResponse{fill, nearCenter}` = `LocateResult`. `GeoRef{kind, id, pin}` 양쪽 같음. 오류 문구 두 개(`Address reference not found` · `Address lookup is unavailable`)가 서버 상수 · 계약 · 화면 판별에서 같다.
- **Review Focus 다섯 줄**은 각각 과제 6(`refuses raw coordinates in a custom place`) · 4 · 5 · 6(503) · 6 · 12(404 → 이름만) · 2(`manifest refuses a duplicated region file`에 해당하는 `test_manifest_refuses_a_missing_region_two_dates_and_a_duplicated_region_file`) · 10 · 11(100자 · 빈 이름 · 지도에서 찾기 이름 그대로) 시험에 붙였다.
- **남는 위험:**
  1. 위치 찍기 28줄(248줄 중) 가운데 넓은 땅 26줄은 핀 없이 주소만 남는다(사용자 결정). 지도에서 그 장소가 보이지 않는다.
  2. 건물 1,439만 동 · 땅 1,950만 필지 적재는 로컬 C: 의 Docker 데이터를 영구히 키운다(vhdx 압축 불가 - DISK-LAYOUT).
  3. 캐시가 차가울 때 수십 ms(실측 34~65ms 중앙) - AWS 메모리 크기가 체감 속도를 정한다.
  4. `EXPECTED_REGION_CODES` 는 행정구역이 바뀌면 고쳐야 한다(적재가 멈추는 쪽으로 실패한다).
  5. `geoRef.pin` 은 화면이 정한다(서명 토큰은 0.7 에서 반영하지 않기로 함) - 조작한 요청이어도 저장되는 좌표는 우리 표의 중심뿐이라 정책 · 보안 문제는 없고, 그 일정의 넓은 땅에 핀이 먼 중심으로 찍히는 정확도 문제만 남는다.
  6. 적재 도구는 모든 .shp 의 내용 지문을 만든다 - 압축 안 파일까지 읽어 적재 시간이 몇 분 늘어난다(과제 14 Step 3 에 걸린 시간으로 적는다).
  7. 운영(온프레미스) 승격은 과제 15 Step 6 의 게이트가 끝나야 한다 - 그 전에 main 에 올리면 운영 배포가 마이그레이션에서 멈춘다(되돌려져 앱은 그대로).
  8. 과제 12 는 검색 대기 끝의 맞춰 보기 초기화를 요청만 무르게 바꾼다 - 막 연 나만의 장소 칸이 닫히지 않는 대신, 칸이 열린 채 검색 결과가 옆에 보이고 미리보기 지도는 숨은 채다.

## 실행

이 계획은 검토(코덱스 2차 · 자체 교차 검토 0.8)를 마친 뒤 실행 방법(과제마다 새 에이전트 + 검토 / 이 세션에서 직접 + 마지막에 전체 검토)을 사용자에게 묻는다. 3단계와 같은 브랜치 · 같은 실행 기록(scratchpad `stage3-exec/`)에 이어 적는다.
