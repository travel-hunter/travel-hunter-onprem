# 카카오 장소값 3단계 - 장소를 담는 흐름(공공데이터 장소 · 나만의 장소) 구현 계획

> **에이전트 작업자용:** 이 계획은 superpowers:subagent-driven-development(권장) 또는 superpowers:executing-plans로 과제별로 실행한다. 단계는 체크박스(`- [ ]`)로 추적한다.

**목표:** 일정에 장소를 담을 때 카카오 장소값(이름 · 주소 · 좌표 · 분류 · 전화)을 저장하지 않는다. 사용자가 고른 카카오 장소를 맞춰 보기(`POST /api/places/match`)로 공공데이터 장소와 견주어 **바로 담기 · '이 장소가 맞나요?' 후보 · 나만의 장소** 세 갈래로 담고, 카카오 장소 ID 와 링크만 남긴다. 추천 장소는 우리 장소 기반(`public_places`)에서 고르고, 홈 장소 카드의 '일정에 담기'를 되살린다. 예전에 저장된 카카오 행은 그대로 보이고, 고치려 하면 '확인 필요' 화면이 열린다.

**구조:** 서버는 장소 추가 요청에서 카카오 필드를 받지 않는다(`extra="forbid"` - 보내면 422). 공공데이터 장소는 참조(`source`, `sourceId`)만 받아 서버가 자기 표에서 값을 복사하고, 나만의 장소는 사용자가 쓴 이름과 찍은 좌표만 받는다. 카카오 장소 ID 로 서버가 `place_url` 을 만든다. 프론트의 담는 흐름은 새 폴더 `frontend/src/components/itinerary/placeAdd/`의 맞춰 보기 훅 · 바구니 모델 · 화면 조각으로 옮기고, 6천 줄짜리 `ItineraryDetailPage` 는 연결만 바꾼다. 추천은 `public_places` 를 일정 지역(시도 · 시군)으로 고른다.

**기술:** FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · React/TypeScript · vitest · Playwright · 카카오 지도 JS SDK(위치 찍기)

**설계:** `docs/superpowers/specs/2026-10-03-public-place-storage-design.md` 2절 '장소를 담는 흐름', 배포 순서 3. 2단계(`POST /api/places/match`, `public_places`)는 PR #90 이고, 이 PR 은 #90 이 develop 에 머지된 뒤 develop 기준으로 연다.

## 전체 제약

- 카카오 로컬 API 응답의 장소명 · 주소 · 좌표 · 전화 · 분류는 DB · 로그 · 주소(URL) · localStorage(편집 초안) 어디에도 남기지 않는다. 남기는 것은 카카오 장소 ID 와 그 ID 로 서버가 만든 `place_url`('카카오맵에서 보기')뿐이다.
- 카카오 값은 검색 결과 화면에 실시간으로 보이고, 맞춰 보기 요청에 실려 서버 메모리에서 견주고 버려진다(2단계). 공공 API 질의로 보내지 않는다.
- 나만의 장소 칸에는 카카오 이름을 미리 채우지도, 옆에 참고로 보여 주지도 않는다. 위치 찍기 지도는 일정 지역에서 시작하고, 고른 카카오 장소의 좌표로 열지 않는다.
- 예전 행(`source_provider` 가 `kakao` · `kakao_local` 이고 `place_origin` 이 비어 있는 행)은 그대로 읽어 보여 준다. 고치려 하면 '확인 필요' 화면이 열린다. 저장분 일괄 변환은 4단계다 - 이 PR 은 하지 않는다.
- 화면은 시안(v59)부터 만든다. 과제 1 의 시안을 사용자가 승인하기 전에는 화면 코드(과제 9 ~ 12)를 쓰지 않는다. 시안에서 구조가 바뀌면 해당 과제를 고쳐 다시 확인받는다.
- API 모양 변경은 `docs/mvp-api-contract.md` · `.agent/evals/api-contract-golden.json` · 프론트 타입 · 백엔드 스키마 · 시험을 함께 고친다.
- Alembic `0049` 는 열과 색인을 더하기만 한다.
- 공공데이터 사진은 공공누리 출처를 함께 보인다('사진: 한국관광공사', 제3유형은 변경 금지 표시). TourAPI 사진 주소(`http://tong.visitkorea.or.kr/`)는 https 로 바꿔 쓴다(2026-10-05 확인: 같은 이미지가 https 로 200).
- 비밀값은 출력하지 않는다. 로컬 DB 를 바꾸기 전에는 `.codex/skills/travel-hunter-workflow/SKILL.md` 4절(덤프 · `pg_restore -l` · SHA-256 · 행 수 비교)을 따른다. db · backend · frontend 세 컨테이너는 같은 워크트리에서 띄운다.
- 한글 파일은 UTF-8 로 유지한다(U+FFFD 0, `git diff --check`).
- 커밋은 과제마다 하지 않는다. 과제 13 에서 전체 검증 뒤 사용자 승인을 받아 한다. 푸시와 PR 은 따로 승인받는다. PR base 는 develop 이고 머지하지 않는다.

## 계획에서 정한 것

설계가 계획에 맡겼거나 글자만으로는 갈리는 것이다.

1. **담기 요청은 참조나 사용자 값만 받는다.** 항목은 `publicPlace {source, sourceId}` 또는 `customPlace {name, latitude?, longitude?}` 중 정확히 하나와 선택 `kakaoPlaceId`, `time`. 예전 카카오 필드(`label` · `meta` · `address` · `latitude` · `longitude` · `category` · `categoryCode` · `placeUrl` · `sourceProvider` · `externalPlaceId`)는 422 다. 안쪽 객체(`publicPlace` · `customPlace`)도 모르는 필드를 받으면 422 다(코덱스 검토 - 안쪽에 숨긴 카카오 필드가 조용히 무시되지 않게). 배포 때 이미 열려 있던 옛 화면은 저장 실패 때 서버 문구 대신 '장소 정보를 저장하지 못했어요'만 보여 새로 고칠 때까지 담기가 안 된다 - 배포 절차로 처리한다(사용이 적은 때 배포하고 시험하는 분들께 새로 고침을 알린다, 과제 13). 새 화면은 장소 저장이 요청 모양 때문에 422 로 실패하면(응답 `detail` 에 모르는 필드 `extra_forbidden` · 빠진 필드 `missing`) '새로 고침' 안내를 보여 다음 배포부터 대비한다(사용자 결정). 이름 길이 · 시간 형식 · 위치 범위 같은 값 오류의 422 는 새로 고쳐도 그대로라 일반 문구로 둔다(코덱스 재검토).
2. **`place_url` 은 서버가 카카오 ID 로 만든다**(`https://place.map.kakao.com/{id}`). 클라이언트가 보낸 주소는 받지 않는다 - 아무 주소나 저장되지 않게.
3. **공공데이터 참조는 revision 을 올리기 전에 모두 찾는다.** 하나라도 없으면 404 `"Public place not found"` 이고 아무것도 쓰지 않는다.
4. **메모(`memo`)는 사용자 메모만 담는다.** 새로 담을 때는 비운다. 예전 카카오 행의 메모('분류 · 주소' 문구)는 변환할 때 지운다. 응답의 `meta` 는 지금처럼 메모 → 주소 순이다.
5. **공공데이터 분류는 새 열 `trip_places.public_category`(0049)에 둔다.** 예전 `category_group_code` · `category_group_name` 은 예전 행에만 남는다(한 열에 두 뜻을 섞지 않는다).
6. **`needsConfirmation` 은 서버가 계산한다**(`place_origin` 이 비어 있고 `source_provider` 가 `kakao` · `kakao_local`). 손으로 적은 예전 행(`source_provider` 없음)은 사용자 입력이라 확인 대상이 아니다.
7. **예전 행의 이름을 고치면 나만의 장소로 바뀐다**(주소 · 좌표 · 분류 · 메모를 지움). 시간만 바꾸는 것은 변환 없이 허용한다 - 추천 일정 저장이 기존 장소의 시간을 바꾼다. **공공데이터 행의 이름을 고치면 사용자 이름 칸(`trip_places.user_label`, 0049)에 따로 담는다** - 공공데이터 이름 · 주소 · 사진 · 위치는 그대로이고 화면에는 고친 이름이 보인다. 한 칸에 사용자 입력과 공공데이터를 섞지 않는다(코덱스 검토 · 사용자 결정). 나만의 장소는 이름 칸을 그대로 고친다.
8. **'확인 필요' 후보는 서버가 예전 행에 저장된 이름 · 좌표로 메모리에서 맞춰 본다**(새 경로 `GET /api/trips/{trip_id}/places/{place_id}/public-candidates`). 이미 DB 에 있는 값을 새로 저장하거나 밖으로 보내지 않는다. 그 값은 4단계에서 지운다.
9. **'찾는 곳이 없어요 · 직접 적기' 입구를 둔다.** 카카오에 없는 곳이나 카카오가 꺼진 환경에서도 나만의 장소를 담을 수 있다(카카오 ID 없음).
10. **위치 찍기 지도의 처음 중심은 일정 지역 공공데이터 장소 위경도의 중앙값이다**(새 경로 `GET /api/trips/{trip_id}/area-center`). 저장소에 시군 중심 좌표 표가 없고, 공공데이터로 충분하다. 값이 없으면 대한민국 중심.
11. **추천은 `public_places` 에서 고른다.** 일정 지역(시도 전체 · 시군 · 세종은 시도만, 같은 시군 이름은 시도와 함께), 사진 있는 TourAPI 장소 먼저, 일정마다 고정된 섞음, 관광 3 · 음식 3 · 숙박 2 를 먼저 채우고 최대 18곳. 표가 비면 지금의 저장 요약으로. 카카오 추천 제공자는 이 경로에서 뺀다(클래스와 점검 스크립트 정리는 다음).
12. **편집 초안 판을 2 로 올리고 예전 판 키를 앱 시작 때 지운다 - 이 단계에서.** 설계는 4단계 일로 적었지만 초안 모양이 이 단계에서 바뀌어 예전 초안(카카오 이름이 든)을 읽을 수 없다. 설계 문서를 고친다(과제 13).
13. **`?addPlace` 에는 카카오 장소 ID 와 친 말만 싣는다**(1단계 원칙). 받는 쪽은 화면 메모리 또는 같은 말 재검색으로 장소를 꺼내 맞춰 보기를 돈다. 지금 남아 있는, 값을 싣는 넘김 형식은 없앤다. 홈에서 새 일정을 만들 때도 주소에 `sido` 를 싣지 않는다 - 서버가 가렸어도 카카오 주소에서 나온 값이다(코덱스 검토). 일정 만들기에서 사용자가 지역을 고른다.
14. **일정 안 장소 검색(`GET /api/trips/{trip_id}/place-search`)은 계약을 그대로 둔다.** 카카오를 일부러 껐으면 빈 목록, 켜 두고 설정이 틀리면 비밀값 없는 503 과 경고 로그로 드러낸다 - '결과 없음'으로 숨기지 않는다(코덱스 검토). 카카오를 부르는 동안 DB 세션을 쥐는 것도 함께 고친다.
15. **두 출처의 같은 이름은 계속 둘로 센다(설계대로).** 2026-10-05 로컬 전체 데이터(108만 행) 실측에서 같은 이름 쌍 10,825 중 9,524 가 50m 안이고 분류도 맞았고, 이 쌍 때문에 TourAPI 장소의 바로 담기가 99% → 74%(음식점 62% · 카페 57% · 숙박 39% 가 쌍을 가짐)로 떨어졌다. 그러나 이 수는 규칙에 맞는 비율이지 같은 곳이라는 증거가 아니다(코덱스 HIGH). 사람이 표본에 같은 곳인지 붙여 정확도를 확인한 뒤 다시 정한다(다음 작업, 사용자 결정). 지금은 후보 확인이고 후보는 TourAPI 가 먼저 나온다.
16. **맞춰 보기는 출처별 상자로 읽는다.** 관광명소 · 문화시설(1km)이면 TourAPI 는 1km 상자, 상가정보는 200m 상자. 같은 실측에서 명동 · 종로의 1km 상자가 약 6,300행(상가정보 약 5,700행은 읽고 버림)을 읽어 중앙값 약 70ms 였다(전에는 5ms).
17. **0049 의 색인은 쓰기를 막지 않게 만든다**(`CREATE INDEX CONCURRENTLY` - 108만 행에서 만드는 동안 `public_places` 쓰기를 막지 않는다, 코덱스 검토). 만들다 실패하면 INVALID 색인이 남으므로 마이그레이션이 만들기 전에 같은 이름의 색인을 지운다(`DROP INDEX CONCURRENTLY IF EXISTS`) - 배포를 다시 돌리면 스스로 풀린다(코덱스 재검토). 이 단계는 0049 가 버전 표에 오르기 전에만 돌아서, 지우는 것은 앞선 시도가 남긴 색인뿐이다. 로컬에서 걸리는 시간과 다시 돌리기를 본다(과제 13).
18. **위치 찍기는 키보드로도 된다.** 지도 가운데 고정 핀, 화살표 키로 지도 옮기기, `+` · `-` 로 확대 · 축소, Enter 또는 '이 위치로'로 고르기. 지도를 누르면 그 자리가 가운데로 온다(코덱스 검토). 지도가 멈출 때마다 가운데 위도 · 경도를 화면 읽기 프로그램에 알리고(`role="status"`), 가운데가 대한민국 밖이면 '이 위치로' · Enter 를 막고 그 사실을 보이고 알린다(코덱스 재검토).
19. **나만의 장소 칸은 결과를 고를 때마다 새로 연다** - 앞 장소에 적던 이름이 새로 고른 카카오 ID 에 붙지 않게(코덱스 검토).
20. **추천 · 지역 중심 질의 비용은 머지 전 실측이 필수다**(과제 13, 1초). 넘으면 미리 정한 대안 - 분류별 후보를 먼저 줄인 뒤 섞기, 중앙값은 DB 집계 - 으로 고친다(과제 5 에 적었다).

## 검토 초점

1. 모든 저장 경로(단일 · 묶음 담기, PATCH, 추천 일정 저장, 홈에서 넘긴 장소)에서 카카오 이름 · 주소 · 좌표 · 분류가 DB 행 · 요청 본문 · URL · localStorage 에 남지 않는지. 과제 3 · 8 · 9 · 10 · 11 · 12 가 시험한다.
2. 예전 행: 시간만 바꿀 때는 변환되지 않고, 이름을 고치거나 후보를 고르면 카카오 값이 지워지는지. 과제 4 · 10 이 시험한다.
3. 공공데이터 참조가 없을 때 revision 이 오르지 않는지(묶음에서 하나만 없어도). 과제 3 이 시험한다.
4. 맞춰 보기 분기: 좌표 없는 결과, 맞춰 보기 실패, 다른 결과를 빠르게 다시 골라 늦게 온 답이 섞이는 경우, 위치 없는 결과를 연달아 고를 때 앞 이름이 남는 경우, 후보에서 '아니요'. 과제 8 · 9 가 시험한다.
5. 추천 지역 필터: 시도 전체 · 시군 · 세종 · 같은 시군 이름(고성 · 중구 · 광주), 공공데이터 표가 빈 환경. 과제 5 가 시험한다.
6. 안쪽 객체에 숨긴 카카오 필드(422), 공공데이터 장소 이름 고치기(사용자 이름 칸 - 공공데이터 값은 그대로), 키보드만으로 위치 찍기(옮긴 뒤 가운데를 알림 · 대한민국 밖은 막음), 값 오류의 422 에는 '새로 고침'이 뜨지 않음. 과제 3 · 4 · 9 · 10 이 시험한다.

## 코덱스 검토 반영(2026-10-05)

결론 '고친 뒤 진행'(HIGH 6 · MEDIUM 4)을 모두 반영했다.
- HIGH: 두 출처 합치기 철회(결정 15) · 공공데이터 이름 고치기는 사용자 이름 칸으로(결정 7) · 안쪽 객체도 422(결정 1) · 새 일정 주소의 `sido` 뺌(결정 13) · 열려 있던 옛 화면은 배포 절차와 새 화면의 새로 고침 안내(결정 1) · 카카오 설정 오류는 503(결정 14).
- MEDIUM: 나만의 장소 칸을 고를 때마다 새로(결정 19) · 추천 · 지역 중심 실측을 머지 전 필수로, 넘으면 쓸 대안을 미리 적음(결정 20) · 색인은 쓰기를 막지 않게(결정 17) · 키보드로 위치 찍기(결정 18).
- 결정 16개 판단: 수용 2 · 3 · 4 · 5 · 8 · 9, 조건부 수용 6 · 10 · 11 · 12 · 16, 수정 필요 1 · 7 · 13 · 14 · 15 - 수정 필요 다섯은 위 반영으로 고쳤다. 과제 7 ~ 12 를 차례로 적용한 통합 검증(전체 시험 · e2e · 브라우저)은 과제 13 에서 한다는 지적에 동의한다 - 지금까지의 시험 통과는 부분별 확인이다.
- 같은 이유로 1단계(PR #89)의 정책 탭 주소 `near` 에 실리는 지역 · 시군도 카카오 주소에서 나온 값이다. 이 PR 에서는 고치지 않고 다음 작업으로 둔다(사용자 결정, CHECKLIST 에 남긴다).

**재검토(2026-10-05, 결론 '고친 뒤 진행' - HIGH 0 · MEDIUM 3 · LOW 2):** 지난 10건은 해결로 판정됐다(`user_label` 은 담기 · 이름 고치기 · 바꾸기 · 응답 `label` · 추천 거르기에서 일관된다). 새 지적은 이렇게 고쳤다.
- MEDIUM 모든 422 를 '화면이 오래됨'으로 봄 → 응답 `detail` 의 오류 종류가 모르는 필드(`extra_forbidden`) · 빠진 필드(`missing`)일 때만 새로 고침을 안내하고, 값 오류는 일반 문구다. 서버의 422 모양은 FastAPI 기본 그대로이고 과제 3 시험이 그 모양을 붙잡는다(결정 1, 과제 3 · 9 · 10).
- MEDIUM INVALID 색인이 남으면 다시 돌려도 실패 → 마이그레이션이 만들기 전에 같은 이름의 색인을 지워 다시 돌리기로 풀리고, 배포 뒤 `indisvalid` 를 읽어 확인한다(결정 17, 과제 2 · 13 · 머지 뒤 서버 작업).
- MEDIUM 키보드로 옮긴 뒤 어디인지 알 수 없음 → 지도가 멈출 때 가운데 위도 · 경도를 `role="status"` 로 알리고, 대한민국 밖이면 막고 알린다. `+` · `-` 확대 · 축소도 지금 넣고 시험한다(결정 18, 과제 9).
- LOW 되돌리기 문구 → '단추와 `publicName` 이 없다'로 좁히고, 같은 장소를 다시 보내면 공식 이름으로 돌아간다고 적었다(통합에서 정한 세부). LOW 다음 작업 둘(통합 검색 503 · 1단계 `near`)은 과제 13 의 CHECKLIST 활성 위험에 이미 있다.

## 시안 v60 ~ v62 반영(2026-10-06)

시안 v59 를 사용자 의견으로 v62 까지 다듬었다(같은 아티팩트 판 68, 원본은 저장소 밖). 과제 9 의 '시안 v59 대응표'에서 시안이 정하기로 한 것은 아래로 정했다. 과제 8b 와 과제 9 의 5 ~ 8단계가 만든다.

21. **화면은 개발서버 모양 그대로다(v60).** 장소 추가 · 수정 · 확인 창은 지금의 `PlaceEditorSheet` 마크업과 `app.css` 를 그대로 쓰고 새 부품만 더한다(지도 미리보기 카드 포함). 사용자 의견: "장소추가창 ui는 최대한 개발서버거를 사용".
22. **검색 중 창이 흔들리지 않는다(v61).** 원인(로컬 4173 실측): 칠 때마다 앞 결과를 새 검색어로 거르는 클라이언트 거르기(`placeSearchText`) 때문에 불러오는 동안 목록이 0 이 됐다가 결과가 오면 다시 늘었다. 그래서 아래의 바구니 · 지도 미리보기가 약 200px 씩 오르내렸다. 같은 거르기가 '담양 죽녹원' · '여수 카페'처럼 두 낱말 검색의 결과를 숨겼다. 고침: 거르기를 지우고 서버 순서대로 6곳을 보인다. 검색어가 있는 동안 결과 칸(`place-search-area`) 높이를 220px 로 고정하고, 상태 줄(불러오는 중 · 오류 · 결과 없음)을 그 안에 둔다. 불러오는 동안 앞 결과는 흐리게 남긴다(`is-stale`, `aria-busy`). 지도 미리보기는 지금처럼 결과가 올 때만 바뀐다.
23. **검색 결과 줄에 미리 맞춘 갈래를 붙인다(v62, 사용자 결정 10/6).** 사용자 지적: 고른 뒤에야 다시 고르기가 나와 어색하다. 일정 안 검색(`GET /api/trips/{trip_id}/place-search`)이 카카오 결과를 받은 뒤 같은 요청 안에서 6곳을 한꺼번에 맞춰 줄마다 `publicMatch` 를 싣는다. 모양은 `POST /api/places/match` 응답과 같고, 필드는 늘 있으며 값은 null 일 수 있다. 맞춰 보기는 출처마다 질의 한 번(줄마다의 상자를 OR 로 묶음, TourAPI · 상가정보 두 번)으로 후보를 읽고, 줄마다 메모리에서 `match_place` 와 같은 규칙으로 가린다(규칙 함수 하나를 같이 쓴다). 실패 범위를 나눈다: 좌표가 없는 줄은 null, 한 줄을 가리다 실패하면 그 줄만 null, DB 읽기가 실패하면 모든 줄이 null 이다(코덱스 검토). null 인 줄은 고른 뒤 예전처럼 맞춰 본다. 카카오 값은 지금처럼 서버 메모리에서 견주고 버린다. 카카오 검색은 10곳에서 6곳으로 줄인다(화면이 6곳만 보인다). 결정 14 의 '계약을 그대로 둔다'를 바꾼다 - 응답에 필드 하나를 더한다. 설계 문서 2절도 과제 8b 에서 고친다(코덱스 검토).
24. **줄 표시와 고른 뒤.** 주소 줄 오른쪽 끝에 '바로 담기'(초록) · '비슷한 곳 N'(주황) · '직접 적기'(회색)를 붙인다. 고르면 '맞춰 보는 중' 없이 그 갈래로 바로 간다. 바로 담기는 그 공공데이터 장소가 바구니에 들어가고 초점이 검색 칸으로 돌아온다. 비슷한 곳은 후보 칸이, 직접 적기는 나만의 장소 칸이 열린다. `publicMatch` 가 null 인 줄은 표시가 없고, 고르면 예전처럼 맞춰 본다. 버튼 이름은 `{이름} 선택, {표시}`(표시가 없으면 `{이름} 선택`). 새 검색을 기다리는 동안 흐리게 남은 앞 결과는 누를 수 없다(`disabled` - 앞 검색어의 장소가 잘못 담기지 않게, 코덱스 검토). 결과 목록은 `listitem` 으로 감싸고, 결과가 오면 화면 읽기 프로그램에 '검색 결과 N곳'을 알린다(초점은 검색 칸에 그대로 둔다 - 치는 중에 초점을 옮기지 않는다).
25. **지도 미리보기 표시.** 검색 결과 첫 곳을 보일 때 배지는 그 줄의 갈래와 같고(바로 담기는 `ready`, 비슷한 곳은 `similar`, 직접 적기는 기본), 도움말도 갈래마다 한 줄이다. 바구니에 담은 뒤에는 '저장 가능'이다(지금은 '확인 필요'에 머문다 - `addToBasket` 이 `saveEligibility` 를 `saveSelected` 로).
26. **v59 에서 정한 것.** 위치를 찍는 동안 나만의 장소 칸의 취소 · 담기를 숨긴다(지도의 취소 · 이 위치로와 둘씩 보이지 않게, 과제 9 의 `CustomPlaceForm` 그대로). 예전 행 확인 화면의 단서는 'Day N · N번째 장소 · 시각'이다(예전 이름은 보이지 않는다). 사진은 장소 수정 창과 추천 미리보기 · 후보 카드에만 두고, 바구니 줄과 타임라인 카드에는 두지 않는다.
27. **(사용자 결정 10/6) 같은 출처에 같은 곳이 두 줄이면 한 곳으로 센다.** 상가정보 안에 이름 · 주소가 같은 행이 있어(로컬 14,632행, 예: 송도해상케이블카 근처 이디야 두 줄) 후보에 같은 곳이 두 번 나왔다. 같은 줄의 기준은 출처 · 이름 열쇠(`name_key` - 소문자로 바꾸고 띄어쓰기 · 기호를 뺀 이름, 맞춰 보기와 같은 비교) · 주소(앞뒤 공백 뺀 원문) · 분류가 모두 같은 것이다. 분류가 다르면 묶지 않는다(코덱스 검토 - 가까운 줄의 분류로 바로 담기가 잘못 나지 않게). 가까운 줄 하나만 남긴다. 주소가 빈 줄은 묶지 않는다. 출처가 다른 같은 이름은 결정 15 대로 둘로 센다.
28. **(사용자 결정 10/6: 이번 PR 에서 빼고 다음 작업) 검색 결과 제목이 한 글자씩 꺾이는 문제.** 분류 칸이 카카오 분류 전체('음식점 > 카페 > 커피전문점 > …')를 줄이지 않고 보여 이름 칸이 좁아진다. 분류는 마지막 단계만 보이고 분류 칸을 줄어들게 하는 고침은 다음 작업이다(과제 13 의 CHECKLIST 활성 위험에 남긴다).

## 과제 순서와 의존

- 순서는 1 → 13 이다. 과제 2 ~ 8(서버 · 데이터 · 화면 없는 모듈)은 시안 승인 전에 해도 된다. 과제 9 ~ 12(화면)는 과제 1 의 시안 v59 승인 뒤에 한다.
- 과제 8b(미리 맞춤 · 같은 후보 하나로, 결정 23 · 27)는 과제 8 뒤, 과제 9 앞이다. 서버 · 계약 · 프론트 경계 · 훅만 바꾸고, 화면은 과제 9 의 5 ~ 8단계가 쓴다. 과제 2 ~ 8 은 이미 적용돼 있다(미커밋) - 8b 의 '찾을 글'은 그 결과 기준이다.
- 과제 3 부터 서버가 예전 요청 모양을 422 로 거절한다. 과제 9 가 끝나도 수정 저장(과제 10)과 추천 담기(과제 11) · 홈 넘김과 e2e 시드(과제 12)는 아직 예전 모양이라, 과제 12 까지 끝나기 전에는 그 길들을 손으로 시험하지 않는다(시험은 `appDataApi` 스파이로 가려져 통과한다). 커밋은 과제 13 에서 한 번에 하므로 중간 상태가 남지 않는다.
- 과제 10 ~ 12 의 '찾을 글'은 과제 9 까지 적용한 `ItineraryDetailPage.tsx` 기준이다. 실행 때 앞 과제 결과와 글자가 어긋나면 찾을 글의 뜻(어느 함수의 어느 줄을 무엇으로)을 따르고 실행 기록에 남긴다. 합칠 때 확인했다: 과제 10 ~ 12 가 기대는 이름 9개(`openAddPlace(` · `PlacePickInput` · `PlaceEditorForm` · `TripPlaceEditDraft` · `matchPanel` · `hidePreview` · `recommendationPlacePayload` · `tripPlaceMutationFromDisplayedPlace` · 시험 도우미 `publicPlaceFor`)는 모두 과제 9 의 바꿀 글에 있다 - 남을 수 있는 어긋남은 글자 모양뿐이다.

## 통합에서 정한 세부

각 부분의 '공통 사항' 절에 적힌 결정은 그대로 따른다. 부분들이 남긴 질문은 아래로 정했다.

**서버**
- `needsConfirmation` 은 예전 카카오 행만이다. 4단계가 `needs_review` 행을 만들 때 `is_legacy_kakao_place` 한 함수에 그 조건을 더한다.
- 추천 문구는 `"{지역} 일정에 추가로 검토할 만한 공공데이터 장소입니다."`, `aiReview` 는 null 이다(AI 가 하지 않은 일을 AI 리뷰라 쓰지 않는다).
- 저장 요약으로 넘어가는 조건은 구현대로 '고를 공공데이터 장소가 하나도 없으면'이다(지역에 수천 곳이 있어 '모두 담음'은 사실상 없다). 계약 문구도 이렇게 적는다.
- 추천에서 상가정보 예술·스포츠(동네 헬스장 · 당구장)는 빼고, 상가정보 도서관 · 사적지는 남긴다.
- `incheon-ganghwa` 지역 데이터(`included_cities` 에 시도 이름 '인천')는 이 PR 에서 고치지 않는다 - 강화 장소만 추천된다(위험에 적는다).
- 이미 담은 장소를 이름으로 거르는 추천 질의가 예전 카카오 행의 이름을 우리 DB 질의 매개변수로 쓴다. 앱 로그에는 남지 않고(`hide_parameters`), 4단계 변환 뒤 사라진다 - 받아들인다.
- 카카오 추천 제공자 클래스 · 점검 스크립트는 남기고, 쓰는 곳이 없어진 `trips.py` 비공개 함수 넷만 지운다.
- 공공데이터 장소에 붙인 사용자 이름을 지우는 단추와 응답의 `publicName` 은 두지 않는다. API 로는 같은 장소를 `publicPlace` 로 다시 보내면(`label` 없이) 사용자 이름이 비워져 공식 이름으로 돌아가지만(과제 4 의 바꾸기), 화면에는 그 입구가 없다. 필요해지면 '공식 이름으로' 단추가 이 요청을 보내게 한다 - `label: null` 같은 새 뜻은 만들지 않는다(코덱스 재검토).
- 일정 안 장소 검색은 카카오 설정 오류에 503 이지만, 홈 · 정책 탭 통합 검색(`/api/places/search`, 1단계)은 여전히 빈 목록이다. 맞추는 일은 1단계 `near` 와 함께 다음 작업으로 둔다.

**프론트**
- 서버가 `ItineraryPlace.memo`(사용자 메모)를 따로 내려 준다(과제 3). 수정 칸의 처음 값은 `memo` 이고, `meta` 로 짐작하는 길은 `memo` 가 없는 응답에만 쓴다.
- 공용 사진 부품 `PlacePhoto` 는 과제 9 가 만들고 과제 11 은 쓰기만 한다. `RecommendationSourceType` 의 `"public_place"` 와 `RecommendationCategoryGroup` 의 `"cafe"` 는 과제 7 이 더한다.
- `placeHandoff.ts` · 홈 넘김 시험 · e2e 시드 두 곳은 과제 12 가 맡는다. 과제 9 는 컴파일에 필요한 만큼(`tripPlaceFromSearchItem`)만 지운다.
- 홈에서 새 일정을 만들 때 주소에 `sido` 를 싣지 않는다(결정 13, 코덱스 검토). 넘김(`addPlace`)에는 카카오 장소 ID 와 친 말만 싣는다. 1단계 `near` 의 지역 · 시군도 같은 이유로 다음 작업에서 고친다.
- 예전 행 확인 화면은 수정 창 본문을 바꾸는 방식이고, 예전 이름 · 주소를 확인 화면에 보이거나 칸에 채우지 않는다(타임라인 카드에는 지금처럼 보인다). 어떤 행을 확인하는지 알리는 단서는 시안 v59 가 정한다.
- 저장 요약 추천(공공데이터 참조 없음)은 이름만 나만의 장소로 담는다(좌표 · 주소 · 분류는 옮기지 않는다).
- 지도 마커: 좌표 없는 나만의 장소 · 확인 필요 행은 이름으로 위치를 찾지 않는다. 예전 행은 지금 그대로다.
- 바뀐 게 없으면 수정 창은 요청 없이 닫는다. 초안 판 지우기는 `AppProviders` 의 효과에서 한다.
- 위치 찍기: 지도 가운데가 대한민국 범위(위도 33 ~ 39, 경도 124 ~ 132 - 서버의 `customPlace` 범위와 같다) 밖이면 '이 위치로' · Enter 를 막고 '대한민국 밖이에요. 대한민국 안으로 옮겨 주세요.'를 보이고 알린다. 지도가 멈출 때(`idle`)마다 가운데 위도 · 경도를 `role="status"` 한 줄로 알리고(화면에는 숨김), `+`(`=`) · `-` 로 한 단계씩 확대 · 축소한다 - 과제 9 의 `MapPointPicker` 코드와 시험에 들어 있다(코덱스 재검토). 화살표 한 번에 옮기는 거리(60px), 십자선 모양, 처음부터 '이 위치로'를 켤지, 알림 문구는 시안 v59 가 다듬는다.
- '새로 고침' 안내는 담기 창 묶음 저장과 수정 · 예전 행 바꾸기 저장이 요청 모양 오류(422 의 `extra_forbidden` · `missing`)로 거절될 때만 둔다. 값 오류의 422 와 그 밖의 실패는 일반 문구이고, 추천 일정 저장은 지금 문구 그대로다.

---

### Task 1: 시안 v59 - 담는 흐름 화면

**파일:** 저장소 밖 시안 원본(정책 탭 · 홈 · 일정 시안, 현재 v58)과 같은 아티팩트. 저장소 파일은 바꾸지 않는다.

**인터페이스:**
- 내놓는 것: 사용자가 승인한 v59 화면 - 과제 9 ~ 12 의 문구 · 배치 · 클래스 이름의 기준.

- [ ] **1단계: 그릴 화면** - v58 에 '일정' 탭 화면으로 더한다(모바일 위주, 색은 앱 청록 토큰).
  1. 일정 장소 추가 창: 카카오 검색 → 결과 고르기 → (a) 바로 담김(바구니에 공공데이터 이름 · 주소, 사진이 있으면 작은 사진과 출처) (b) '이 장소가 맞나요?' 후보 1 ~ 3곳(이름 · 주소 · 거리 · 사진) + '아니요, 직접 적을게요' (c) 나만의 장소: 빈 이름 칸 + '지도에서 위치 찍기(선택)' + 담기.
  2. 검색 결과 아래 '찾는 곳이 없어요 · 직접 적기' 입구.
  3. 위치 찍기 지도: 일정 지역 가운데서 열림, 가운데 고정 핀, 화살표 키 · 끌기로 지도 옮기기, `+` · `-` 확대 · 축소, 누른 곳이 가운데로, '이 위치로'(Enter) · '취소', 가운데가 대한민국 밖이면 '이 위치로'가 꺼지고 안내.
  4. 담은 장소 카드와 상세: 공공데이터(사진 + 출처, 주소, 핀, 카카오맵 링크, 이름을 고쳤으면 고친 이름), 나만의 장소(이름, 핀은 찍은 경우만, 카카오맵 링크), 예전 장소(지금 그대로).
  5. 예전 장소를 고치면 열리는 '확인 필요' 화면: '장소 이름을 다시 적어 주세요', 공공데이터 후보 1 ~ 3곳, 직접 적기와 위치 찍기, 카카오맵에서 보기, 시간 바꾸기.
  6. 추천 일정 미리보기 카드: 공공데이터 사진과 출처.
  7. 홈 장소 카드 '일정에 담기' → 일정 고르기(새 일정 만들기는 지역을 일정 만들기에서 고름) → 일정 화면의 같은 흐름.
  8. 저장이 요청 모양 오류(422)로 실패했을 때의 '화면이 오래됐을 수 있어요 · 새로 고침' 안내(담기 창 · 수정 창). 값 오류는 지금의 일반 문구다.
- [ ] **2단계: 만들기** - 시안 원본의 v58 템플릿에 화면을 더해 v59 를 만들고(원본 README 의 빌드 · 문자열 치환 방식), 스크립트 오류 없이 열리는지 한 번 확인한 뒤 같은 아티팩트에 다시 게시한다. 시안의 장소 예시는 공공데이터(TourAPI · 상가정보) 이름만 쓴다.
- [ ] **3단계: 승인받기** - 화면 8개를 보이고 바꿀 점을 받는다. 승인 전에는 과제 9 ~ 12 를 시작하지 않는다(과제 2 ~ 8 의 서버 · 데이터 과제는 먼저 해도 된다). 시안이 이 계획과 다른 구조(예: 후보를 창이 아니라 목록 안에 보임)를 고르면 해당 과제를 고쳐 다시 확인받는다.

---

## 백엔드 공통 사항 (과제 2 ~ 6)

- **저장하는 값:** 일정 장소 행의 이름 · 주소 · 좌표 · 분류 · 사진은 공공데이터 장소(`public_places`)의 값을 복사하거나(`place_origin='public'`) 사용자가 쓴 값이다(`'custom'` - 이름과 지도에서 찍은 좌표뿐). 카카오 장소는 장소 ID(`external_place_id`)와 서버가 만든 `place_url`(`https://place.map.kakao.com/{id}`), `source_provider='kakao'` 만 남긴다. 요청은 카카오 필드를 받지 않는다(`extra="forbid"` → 422) - 최상위만이 아니라 중첩 `publicPlace` · `customPlace` 도 같아서, 카카오 값이 그 안에 숨어 들어와도 조용히 버려지지 않고 422 다.
- **이름을 섞지 않는다:** 공공데이터 장소 행의 `place_name` 은 늘 공공데이터 이름이다. 사용자가 그 이름을 고치면 새 열 `user_label` 에 따로 담고(0049), 화면 이름(`ItineraryPlace.label`)은 `user_label` 이 있으면 그것, 없으면 `place_name` 이다. 나만의 장소는 이름 자체가 사용자가 쓴 값이라 `place_name` 을 바꾼다. 장소를 다른 것으로 바꾸면(`publicPlace` · `customPlace`) `user_label` 은 비워진다. 새 DTO 필드는 없다.
- **한 곳에서 정한다:** 담을 때(과제 3)와 고칠 때(과제 4)의 열 값은 새 `app/services/trip_public_places.py` 의 세 함수(`public_place_columns` · `custom_place_columns` · `kakao_link_columns`)가 정한다(`user_label` 도 두 함수가 `None` 으로 정한다). 라우트는 얇게 두고 서비스(`services/trips.py`)가 일하고 조회는 `repositories/public_places.py` 가 한다.
- **쓰기 전에 다 확인한다:** 공공데이터 참조 조회와 방문 시간 형식 검사는 `_bump_trip_revision_or_conflict` 보다 앞에서 끝낸다. 하나라도 틀리면 revision 도 행도 그대로다.
- **일정 안 장소 검색의 오류:** 카카오를 일부러 껐을 때(`KAKAO_LOCAL_ENABLED=false`)와 카카오 요청이 실패했을 때는 빈 목록, 켜 두었는데 설정이 틀렸을 때(예: REST 키 없음)는 503 `Place search is unavailable` 이다. 키 · 설정 값은 응답에도 로그에도 없다. 홈 검색(`GET /api/places/search`)은 이 계획이 건드리지 않아 설정 오류에도 빈 목록이다.
- **색인은 쓰기를 막지 않는다:** 0049 는 `public_places`(108만 행)의 색인을 `CREATE INDEX CONCURRENTLY` 로 만든다. 그래서 이 단계는 `autocommit_block` 으로 트랜잭션 밖에서 돌고, 열 · 제약보다 앞에 둔다. 실패하면 INVALID 색인 하나가 남는데, 같은 블록이 만들기 전에 `DROP INDEX CONCURRENTLY IF EXISTS` 로 그것을 지우므로 다시 돌리면 풀린다(`IF NOT EXISTS` 로 만들면 INVALID 색인을 그대로 두고 지나가므로 쓰지 않는다).
- **같은 곳의 쌍을 하나로 세지 않는다:** 같은 곳을 TourAPI 와 상가정보가 따로 담은 것처럼 보여도(이름이 같고 50m 안, 분류가 짝) 같은 곳이라는 증거는 아니라는 결정이다. 맞춰 보기(`match_place`)의 결과 규칙은 2단계 그대로 두 출처의 같은 이름을 둘로 센다 - 이 계획은 조회 상자(5-나)만 줄인다. 되살리지 않는다.
- **새 시험은 한 파일이다:** `backend/tests/test_trip_public_places.py`. 운영 세션처럼 `autoflush=False` 인 SQLite 이고, `TripPlace` 의 BigInteger 기본키는 SQLite 가 자동 증가시키지 않아 시험 동안만 Integer 로 바꾼다(기존 `sqlite_db_session` 과 같다). 과제 3 · 4 · 5가 이 파일에 이어 붙인다.
- **알려진 한계:** `alembic upgrade head --sql` 을 처음부터 돌리면 기존 데이터 마이그레이션 `0044` 에서 멈춘다(오프라인인데 DB 를 읽음 - develop 그대로, CHECKLIST 에 있다). 그래서 마이그레이션 검증은 범위 형식 `0048_public_places:0049_trip_place_public_category` 로 한다. `autocommit_block` 을 실제 Postgres 에서 돌려 본 것은 아니다(오프라인 SQL 과 렌더 시험까지).
- **한글 파일:** 문서 · 시험의 한글은 UTF-8 로 유지한다. 바꾼 diff 에 U+FFFD 가 없어야 하고 `git diff --check` 를 통과해야 한다. 한글이 든 파일은 PowerShell `Set-Content` 로 다시 쓰지 말고 편집 도구로 고친다.
- **커밋:** 과제마다 하지 않는다. 전체 검증(과제 6 끝) 뒤 사용자 승인을 받아 한다. 푸시와 PR 은 따로 승인받는다.

실행 명령은 모두 이 저장소 루트에서 `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider <파일>` 꼴이다(워크트리에는 `.venv` 가 없어 메인 저장소의 것을 쓴다).

---

### Task 2: 마이그레이션 0049와 모델 · 스키마 문서

**파일:**
- 고치기: `backend/app/models/tables.py`(`TripPlace` · `PublicPlace`)
- 만들기: `backend/alembic/versions/0049_trip_place_public_category.py`
- 고치기: `backend/tests/test_db_schema.py`, `docs/db-schema-current.md`, `docs/db-schema-current.sql`

**인터페이스:**
- 내놓는 것(뒤 과제가 쓴다):
  - `TripPlace.public_category` - `String(20)` nullable, CHECK `ck_trip_places_public_category`(NULL 또는 `sight` · `culture` · `leisure` · `stay` · `shopping` · `food` · `cafe`). 과제 3이 공공데이터 장소를 담을 때 `public_places.category` 를 복사한다.
  - `TripPlace.user_label` - `String(100)` nullable. 사용자가 공공데이터 장소(`place_origin='public'`)에 붙인 이름이다. 이름을 고쳐도 `place_name`(공공데이터 이름)은 그대로 두고 여기에 담는다 - 화면 이름은 `user_label` 이 있으면 그것, 없으면 `place_name`(과제 3 · 4).
  - 색인 `ix_public_places_sido_city`(`public_places` 의 `sido`, `city`) - 과제 5의 추천 · 지역 중심 조회가 일정 지역(시도 + 시군)으로 거를 때 쓴다. `CREATE INDEX CONCURRENTLY` 로 만들어 108만 행 위에서도 `public_places` 쓰기를 막지 않는다. 만들기 전에 같은 이름의 색인(앞선 시도가 실패해 남긴 INVALID 색인)을 지워 다시 돌리면 풀린다.
  - Alembic `0049_trip_place_public_category`(down `0048_public_places`, 31자 - 버전 표 한도 32자 안).

- [ ] **1단계: 실패하는 시험 쓰기** - `backend/tests/test_db_schema.py`

파일 위쪽 import 를 바꾼다(`alembic` 의 스크립트 디렉터리로 머리가 하나인지 보고, 마이그레이션이 내는 SQL 을 오프라인으로 렌더한다).

전:

```python
import ast
from pathlib import Path

import sqlalchemy as sa
import app.models  # noqa: F401
```

후:

```python
import ast
import importlib.util
import io
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

import app.models  # noqa: F401
```

파일 끝에 더한다(`_check_names` 는 2단계에서 이미 있다). 셋째 시험은 마이그레이션을 DB 없이 렌더해, 색인이 트랜잭션 밖(`COMMIT` 과 `BEGIN` 사이)에서 `CONCURRENTLY` 로 만들어지고 그 앞에서 같은 이름의 남은 색인을 지우는지(다시 돌리기) 본다.

```python
def test_trip_place_columns_and_area_index_are_registered() -> None:
    trip_places = Base.metadata.tables["trip_places"]
    assert trip_places.c["public_category"].nullable is True
    assert trip_places.c["public_category"].type.length == 20
    assert "ck_trip_places_public_category" in _check_names(trip_places)
    assert trip_places.c["user_label"].nullable is True
    assert trip_places.c["user_label"].type.length == 100
    places = Base.metadata.tables["public_places"]
    index_columns = {index.name: [column.name for column in index.columns] for index in places.indexes}
    assert index_columns["ix_public_places_sido_city"] == ["sido", "city"]


def test_alembic_0049_follows_0048_and_is_the_only_head() -> None:
    backend = Path(__file__).parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert script.get_heads() == ["0049_trip_place_public_category"]
    assert script.get_revision("0049_trip_place_public_category").down_revision == "0048_public_places"


def render_0049(direction: str) -> str:
    """0049 의 upgrade · downgrade 가 내는 Postgres SQL - 오프라인이라 DB 에 닿지 않는다."""

    path = Path(__file__).parents[1] / "alembic" / "versions" / "0049_trip_place_public_category.py"
    spec = importlib.util.spec_from_file_location("migration_0049", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    buffer = io.StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": buffer})
    with Operations.context(context):
        getattr(module, direction)()
    return buffer.getvalue()


def test_alembic_0049_builds_the_area_index_concurrently_outside_the_transaction() -> None:
    up, down = render_0049("upgrade"), render_0049("downgrade")
    leftover = "DROP INDEX CONCURRENTLY IF EXISTS ix_public_places_sido_city"
    index = "CREATE INDEX CONCURRENTLY ix_public_places_sido_city ON public_places (sido, city)"
    # 트랜잭션 밖에서 만든다 - public_places 쓰기를 막지 않는다. 앞선 시도가 남긴 INVALID 색인은 먼저 지워 다시 돌리기가 풀린다
    assert up.index("COMMIT") < up.index(leftover) < up.index(index) < up.index("BEGIN")
    assert "ADD COLUMN public_category VARCHAR(20)" in up and "ADD COLUMN user_label VARCHAR(100)" in up
    assert down.index("COMMIT") < down.index("DROP INDEX CONCURRENTLY IF EXISTS ix_public_places_sido_city") < down.index("BEGIN")
    assert "DROP COLUMN user_label" in down and "DROP COLUMN public_category" in down
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_db_schema.py`
기대: FAIL 3개(`3 failed, 10 passed`). `trip_places` 에 `public_category` 열이 없고(`KeyError`), 머리가 아직 `0048_public_places` 하나이고, 0049 파일이 없다.

- [ ] **3단계: 구현**

`backend/app/models/tables.py` 를 세 곳 고친다.

1. `TripPlace.__table_args__` - 기존 `ck_trip_places_place_origin` 제약 뒤에 제약 하나를 더한다.

전:

```python
            "place_origin IS NULL OR place_origin IN ('public', 'custom', 'needs_review')",
            name="ck_trip_places_place_origin",
        ),
    )
```

후:

```python
            "place_origin IS NULL OR place_origin IN ('public', 'custom', 'needs_review')",
            name="ck_trip_places_place_origin",
        ),
        CheckConstraint(
            "public_category IS NULL OR public_category IN "
            "('sight', 'culture', 'leisure', 'stay', 'shopping', 'food', 'cafe')",
            name="ck_trip_places_public_category",
        ),
    )
```

2. `TripPlace` - `photo_license` 줄 바로 뒤, `visit_time` 앞에 열 둘을 더한다.

전:

```python
    photo_url: Mapped[str | None] = mapped_column(String(500))
    photo_license: Mapped[str | None] = mapped_column(String(20))
    visit_time: Mapped[time | None] = mapped_column(Time)
```

후:

```python
    photo_url: Mapped[str | None] = mapped_column(String(500))
    photo_license: Mapped[str | None] = mapped_column(String(20))
    # 공공데이터 장소의 분류(0049) - public_places.category 를 담을 때 복사한다. 나만의 장소 · 예전 행은 비어 있다
    public_category: Mapped[str | None] = mapped_column(String(20))
    # 사용자가 붙인 이름(0049) - 공공데이터 장소(place_origin='public')의 이름을 고치면 place_name(공공데이터 이름)은 두고 여기에 담는다.
    # 화면 이름은 user_label 이 있으면 그것, 없으면 place_name. 나만의 장소는 이름 자체가 place_name 이라 비어 있다
    user_label: Mapped[str | None] = mapped_column(String(100))
    visit_time: Mapped[time | None] = mapped_column(Time)
```

3. `PublicPlace.__table_args__` - 색인 하나를 더한다.

전:

```python
        Index("ix_public_places_name_key", "name_key"),
    )
```

후:

```python
        Index("ix_public_places_name_key", "name_key"),
        # 추천 · 지역 중심 조회(0049) - 일정 지역(시도 + 시군)으로 고른다
        Index("ix_public_places_sido_city", "sido", "city"),
    )
```

`backend/alembic/versions/0049_trip_place_public_category.py` 를 만든다. 색인을 맨 앞에 두는 까닭은 파일 위쪽 설명에 있다 - `CONCURRENTLY` 는 트랜잭션 밖에서만 돌아서 `autocommit_block` 으로 감싸고, 그 단계가 실패해도 열 · 제약 · 버전 표는 건드리지 않은 채 INVALID 색인 하나만 남고, 다시 돌리면 같은 블록이 그것을 먼저 지운다.

```python
"""trip place public category + user label + public places area index (Kakao Local policy, stage 3)

Revision ID: 0049_trip_place_public_category
Revises: 0048_public_places
Create Date: 2026-10-05

3단계 담는 흐름(설계 docs/superpowers/specs/2026-10-03-public-place-storage-design.md)이 쓴다.
- trip_places.public_category: 공공데이터 장소를 담을 때 그 분류(public_places.category)를 복사한다. 일정 화면이 시간대와
  분류 표시에 쓴다. nullable - 나만의 장소와 예전 행은 비어 있다. 값은 public_places 와 같은 7개로 CHECK 한다.
- trip_places.user_label: 사용자가 붙인 이름. 공공데이터 장소(place_origin='public')의 이름을 고쳐도 place_name(공공데이터 이름)은
  그대로 두고 여기에 담는다. 화면 이름은 user_label 이 있으면 그것, 없으면 place_name. nullable - 나만의 장소와 예전 행은 비어 있다.
- ix_public_places_sido_city: 추천 · 지역 중심 조회가 일정 지역(시도 + 시군)으로 거른다. public_places 는 108만 행이라 CONCURRENTLY 로
  만들어 TourAPI 동기화 · 상가정보 적재(쓰기)를 막지 않는다.
열 둘과 색인만 더하므로 앞 버전 코드가 그대로 돈다. downgrade 는 셋 다 지운다.

CONCURRENTLY 는 트랜잭션 안에서 못 돌려서 autocommit_block 으로 감싼다(블록 앞까지 커밋된다). 그래서 색인을 맨 앞에 둔다 - 이 단계가
실패해도 열 · 제약 · 버전 표는 그대로이고 남는 것은 INVALID 색인 하나뿐이다. 블록은 만들기 전에 같은 이름의 색인을 지우므로
(DROP INDEX CONCURRENTLY IF EXISTS) 배포를 다시 돌리면 스스로 풀린다. 이 블록은 0049 가 버전 표에 오르기 전에만 돌아서 지우는 것은
앞선 시도가 남긴 색인뿐이다. IF NOT EXISTS 로 만들지 않는다 - INVALID 색인을 그대로 두고 지나간다.
열 · 제약은 그 뒤 한 트랜잭션이라 버전 표 갱신과 함께 되돌려진다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0049_trip_place_public_category"
down_revision: str | None = "0048_public_places"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        # 앞선 시도가 실패해 남긴 INVALID 색인 - 지워야 다시 돌리기가 풀린다(0049 가 오르기 전에만 도는 자리다)
        op.drop_index("ix_public_places_sido_city", table_name="public_places", postgresql_concurrently=True, if_exists=True)
        op.create_index("ix_public_places_sido_city", "public_places", ["sido", "city"], postgresql_concurrently=True)
    op.add_column("trip_places", sa.Column("public_category", sa.String(length=20), nullable=True))
    op.add_column("trip_places", sa.Column("user_label", sa.String(length=100), nullable=True))
    op.create_check_constraint(
        "ck_trip_places_public_category",
        "trip_places",
        "public_category IS NULL OR public_category IN ('sight', 'culture', 'leisure', 'stay', 'shopping', 'food', 'cafe')",
    )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index("ix_public_places_sido_city", table_name="public_places", postgresql_concurrently=True, if_exists=True)
    op.drop_constraint("ck_trip_places_public_category", "trip_places", type_="check")
    op.drop_column("trip_places", "user_label")
    op.drop_column("trip_places", "public_category")
```

`docs/db-schema-current.md` 의 `- trip_places 에 place_origin(...)` 으로 시작하는 줄(`공공데이터 장소 (2026-10-04, 0048_public_places)` 절의 마지막 줄) 바로 뒤, 다음 `수집 소스·검토 후보 테이블` 절 앞에 아래 절을 더한다.

```markdown
담는 흐름 (2026-10-05, `0049_trip_place_public_category`):

- `trip_places.public_category` String(20) nullable, CHECK `ck_trip_places_public_category`: `sight`/`culture`/`leisure`/`stay`/`shopping`/`food`/`cafe`(`public_places.category` 와 같은 7개) 또는 NULL. 공공데이터 장소를 담을 때 그 분류를 복사한다. 나만의 장소 · 예전 카카오 행은 NULL.
- `trip_places.user_label` String(100) nullable: 사용자가 붙인 이름. 공공데이터 장소(`place_origin='public'`)의 이름을 고쳐도 `place_name`(공공데이터 이름)은 그대로 두고 여기에 담는다 - 화면 이름은 `user_label` 이 있으면 그것, 없으면 `place_name`. 나만의 장소(`custom`)는 이름 자체가 `place_name` 이라 NULL 이고, 다른 장소로 바꾸면 NULL 로 돌아간다. 예전 카카오 행도 NULL.
- `public_places` 에 색인 `ix_public_places_sido_city`(시도, 시군)를 더했다 - 추천 · 지역 중심 조회가 일정 지역으로 거른다. `CREATE INDEX CONCURRENTLY` 라 `public_places` 쓰기를 막지 않는다(마이그레이션이 이 단계만 트랜잭션 밖에서 돈다).
- 3단계부터 `trip_places` 에는 카카오 장소명 · 주소 · 좌표 · 분류를 새로 쓰지 않는다. 공공데이터 장소(`place_origin='public'`)는 그 장소의 이름 · 주소 · 좌표 · 분류 · 사진을 복사하고 `public_source` · `public_source_id` 를 남기며, 나만의 장소(`place_origin='custom'`)는 사용자가 쓴 이름과 지도에서 찍은 좌표(없으면 NULL)만 둔다. 카카오 장소를 골랐으면 `source_provider='kakao'` · `external_place_id` · `place_url`(`https://place.map.kakao.com/{id}`, 서버가 만든다)만 남는다. `place_origin` 이 NULL 이고 `source_provider` 가 `kakao`/`kakao_local` 이면 예전 행이다(4단계에서 변환 - 화면은 '확인 필요'로 보인다).
```

`docs/db-schema-current.sql` 을 pg_dump 모양 그대로 고친다.

- `CREATE TABLE public.trip_places (` 블록의 마지막 열과 제약을 아래처럼 바꾼다(`photo_license` 뒤에 열 둘 - 열은 만든 차례대로, 제약은 이름순이라 `ck_trip_places_place_origin` 다음).

전:

```sql
    photo_license character varying(20),
    CONSTRAINT ck_trip_places_place_origin CHECK (((place_origin IS NULL) OR ((place_origin)::text = ANY ((ARRAY['public'::character varying, 'custom'::character varying, 'needs_review'::character varying])::text[]))))
);
```

후:

```sql
    photo_license character varying(20),
    public_category character varying(20),
    user_label character varying(100),
    CONSTRAINT ck_trip_places_place_origin CHECK (((place_origin IS NULL) OR ((place_origin)::text = ANY ((ARRAY['public'::character varying, 'custom'::character varying, 'needs_review'::character varying])::text[])))),
    CONSTRAINT ck_trip_places_public_category CHECK (((public_category IS NULL) OR ((public_category)::text = ANY ((ARRAY['sight'::character varying, 'culture'::character varying, 'leisure'::character varying, 'stay'::character varying, 'shopping'::character varying, 'food'::character varying, 'cafe'::character varying])::text[]))))
);
```

- `-- Name: ix_public_places_name_key; Type: INDEX;` 블록 바로 뒤(`ix_trip_places_external_place_id` 블록 앞)에 더한다.

```sql
--
-- Name: ix_public_places_sido_city; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_public_places_sido_city ON public.public_places USING btree (sido, city);
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_db_schema.py && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m alembic upgrade 0048_public_places:0049_trip_place_public_category --sql 2>/dev/null | grep -c "ADD COLUMN public_category\|ADD COLUMN user_label\|CREATE INDEX CONCURRENTLY ix_public_places_sido_city"`
기대: `13 passed`, 오프라인 SQL 에 열 둘의 추가와 `CREATE INDEX CONCURRENTLY` 가 나온다(`3`). 이어서 `git diff --check -- docs/db-schema-current.md docs/db-schema-current.sql` 가 비어 있다.

주의: 오프라인 SQL 과 위 렌더 시험은 `CONCURRENTLY` · `COMMIT`/`BEGIN` 의 모양까지만 본다. `autocommit_block` 을 실제 Postgres 에서 돌려 보는 것은 이 환경에서 못 했다 - 로컬 Postgres 에서 `upgrade` → `downgrade` → `upgrade` 를 한 번 돌려 본다(과제 13 의 로컬 측정과 같이 해도 된다). 색인 단계가 중간에 멎으면 INVALID 색인이 남는다 - 다시 돌리면 마이그레이션이 그것을 먼저 지우고 새로 만든다(과제 13 에서 실제 Postgres 로 확인한다). upgrade 의 `drop_index` 줄을 빼면 셋째 시험이 `ValueError: substring not found` 로 실패한다(확인했다).

---

### Task 3: 담기 - 요청 모양, 값 정하기, 응답 필드

**파일:**
- 고치기: `backend/app/schemas/trip.py`
- 고치기: `backend/app/services/public_places.py`(`secure_photo_url`), `backend/app/repositories/public_places.py`(`get_public_place`), `backend/app/repositories/trips.py`(`add_trip_place`)
- 만들기: `backend/app/services/trip_public_places.py`
- 고치기: `backend/app/services/trips.py`
- 만들기: `backend/tests/test_trip_public_places.py`
- 고치기: `backend/tests/test_trip_db_service.py`, `backend/tests/test_trip_db_routes.py`, `backend/tests/test_trip_auth_edge_cases.py`, `backend/tests/test_public_places.py`

**인터페이스:**
- 받는 것: 과제 2의 `TripPlace.public_category`, 2단계의 `PublicPlace` · `public_place_item` · `match_place`.
- 내놓는 것:
  - 스키마(`app/schemas/trip.py`): `PublicPlaceRef(source, sourceId)`, `CustomPlaceInput(name, latitude?, longitude?)`(둘 다 `extra="forbid"` - 안에 숨은 카카오 값도 422), `TripPlaceAddItem(time?, publicPlace?, customPlace?, kakaoPlaceId?)`(`extra="forbid"`, 둘 중 정확히 하나), `CreateTripPlaceRequest(TripPlaceAddItem) + expectedRevision`, `CreateTripPlacesRequest(expectedRevision, places: TripPlaceAddItem[1..50])`(`extra="forbid"`). 옛 `CreateTripPlaceItem` 은 없앤다. `ItineraryPlace` 에 `memo`(저장된 사용자 메모 그대로 - `meta` 는 지금처럼 메모가 있으면 메모, 없으면 주소) · `placeOrigin` · `publicSource` · `publicSourceId` · `publicCategory` · `photoUrl` · `photoLicense` · `needsConfirmation`. 응답의 `label` 은 `user_label`(사용자가 붙인 이름)이 있으면 그것, 없으면 `place_name` 이다 - 새 DTO 필드는 없다.
  - `secure_photo_url(url: str | None) -> str | None`(`services/public_places.py`) - `http://tong.visitkorea.or.kr/` 로 시작하면 https 로 바꾼다. `public_place_item` 의 `photoUrl` 에도 쓴다.
  - `get_public_place(db, source, source_id) -> PublicPlace | None`(`repositories/public_places.py`)
  - `add_trip_place(...)` 에 `place_origin` · `public_source` · `public_source_id` · `public_category` · `photo_url` · `photo_license` · `user_label`(모두 기본 `None`)
  - `services/trip_public_places.py`: `is_legacy_kakao_place(place) -> bool`, `public_place_columns(place) -> dict`, `custom_place_columns(name, latitude, longitude) -> dict`(둘 다 `user_label` 을 `None` 으로 정한다 - 과제 4에서 장소를 바꿀 때 예전 사용자 이름이 따라오지 않는다), `kakao_link_columns(kakao_place_id) -> dict`
  - `services/trips.py`: `PUBLIC_PLACE_NOT_FOUND`, `_value_columns(db, public_ref, custom, found) -> dict | None`(과제 4도 쓴다), `_new_place_columns(db, items) -> list[dict]`. 공개 함수 `add_place_to_trip_day` · `add_places_to_trip_day` 의 시그니처는 그대로다.

- [ ] **1단계: 실패하는 시험 쓰기**

`backend/tests/test_trip_public_places.py` 를 만든다. 공공데이터 장소 · 일정 · 사용자를 심는 도우미와 SQLite 세션(`db`), 로그인 도우미(`api`)를 이 파일에 둔다. 과제 4 · 5가 같은 파일에 이어 붙인다.

```python
"""3단계 담는 흐름(카카오 운영정책) - 일정 장소는 공공데이터 값과 사용자가 쓴 값만 저장한다.
DB 는 운영과 같은 autoflush=False 세션의 SQLite 다. TripPlace 의 BigInteger 기본키는 SQLite 가 자동 증가시키지 않아 시험 동안만 Integer 로 바꾼다."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import BigInteger, Integer, create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_optional_db
from app.main import app
from app.models import PublicPlace, Trip, TripDay, TripMember, TripPlace, User
from app.schemas.trip import CreateTripPlacesRequest, CreateTripPlaceRequest, CustomPlaceInput, PublicPlaceRef
from app.services import trips as trip_service
from app.services.public_places import name_key, public_place_item, secure_photo_url

SYNCED = datetime(2026, 10, 5, 3, 0)
ODONGDO_PHOTO = "http://tong.visitkorea.or.kr/cms/resource/a.jpg"
TOUR_REF = {"source": "tourapi", "sourceId": "126508"}


@pytest.fixture
def db() -> Iterator[Session]:
    # StaticPool · check_same_thread=False: TestClient 가 라우트를 다른 스레드에서 돌린다. autoflush 는 운영처럼 끈다
    swapped = [(c, c.type) for t in Base.metadata.tables.values() for c in t.c if c.primary_key and isinstance(c.type, BigInteger)]
    for column, _ in swapped:
        column.type = Integer()
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    try:
        Base.metadata.create_all(bind=engine)
        with sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)() as session:
            yield session
    finally:
        for column, original in swapped:
            column.type = original


@pytest.fixture
def api(db: Session) -> Iterator[Callable[[User], TestClient]]:
    client = TestClient(app)

    def login(user: User) -> TestClient:
        app.dependency_overrides[get_optional_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        return client

    yield login
    app.dependency_overrides.pop(get_optional_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def make_user(user_id: int, nickname: str) -> User:
    return User(id=user_id, email=f"user-{user_id}@travel.kr", nickname=nickname, onboarding_completed=True)


def seed_trip(db: Session, *, travel_area_id: str | None = None) -> tuple[User, Trip]:
    """일정 7번(이틀, 첫 사용자가 owner, revision 1) 하나."""

    owner = make_user(1, "Owner")
    trip = Trip(
        id=7, owner_id=1, title="여수 여행", status="confirmed", revision=1, start_date=date(2026, 10, 10),
        end_date=date(2026, 10, 11), region="여수", travel_area_id=travel_area_id, participant_count=1,
    )
    db.add_all([owner, trip, TripDay(id=1, trip_id=7, day_number=1, date=date(2026, 10, 10)),
                TripDay(id=2, trip_id=7, day_number=2, date=date(2026, 10, 11))])
    db.commit()
    return owner, trip


def seed_viewer(db: Session) -> User:
    viewer = make_user(2, "Viewer")
    db.add_all([viewer, TripMember(trip_id=7, user_id=2, role="viewer")])
    db.commit()
    return viewer


def public_place(source_id: str = "126508", *, source: str = "tourapi", name: str = "오동도", category: str = "sight",
                 sido: str = "전남", city: str = "여수", lat: float = 34.7443, lng: float = 127.7663,
                 photo: str | None = ODONGDO_PHOTO, address: str | None = "전남광주통합특별시 여수시 오동도로 222") -> PublicPlace:
    return PublicPlace(
        source=source, source_id=source_id, name=name, name_key=name_key(name), address=address, latitude=lat, longitude=lng,
        category=category, sido=sido, city=city, photo_url=photo, photo_license="Type3" if photo else None, synced_at=SYNCED,
    )


def saved_places(db: Session) -> list[TripPlace]:
    db.expire_all()
    return list(db.scalars(select(TripPlace).order_by(TripPlace.id)))


def revision_of(db: Session, trip_id: int = 7) -> int:
    db.expire_all()
    return db.scalar(select(Trip.revision).where(Trip.id == trip_id))


OLD_KAKAO_FIELDS = {
    "label": "카카오가게", "meta": "음식점 > 한식 · 전남 여수시", "address": "전남 여수시 수정동 1", "latitude": 34.7443,
    "longitude": 127.7663, "category": "음식점", "categoryCode": "FD6", "placeUrl": "https://place.map.kakao.com/1",
    "sourceProvider": "kakao", "externalPlaceId": "1",
}


@pytest.mark.parametrize("field", sorted(OLD_KAKAO_FIELDS))
def test_add_requests_reject_every_old_kakao_field(field: str) -> None:
    body = {"time": "10:00", "customPlace": {"name": "내 장소"}, field: OLD_KAKAO_FIELDS[field]}
    with pytest.raises(ValidationError) as single:
        CreateTripPlaceRequest(expectedRevision=1, **body)
    assert single.value.errors()[0]["type"] == "extra_forbidden"
    with pytest.raises(ValidationError):
        CreateTripPlacesRequest(expectedRevision=1, places=[body])


def test_an_add_request_needs_exactly_one_of_public_or_custom_place() -> None:
    with pytest.raises(ValidationError):
        CreateTripPlaceRequest(expectedRevision=1, time="10:00")
    with pytest.raises(ValidationError):
        CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF, customPlace={"name": "내 장소"})
    assert CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF).customPlace is None
    assert CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "내 장소"}).publicPlace is None


def test_custom_place_name_and_point_rules() -> None:
    assert CustomPlaceInput(name="  내 장소  ").name == "내 장소"   # 앞뒤 공백은 뺀다
    assert CustomPlaceInput(name="가" * 100).name == "가" * 100
    for bad_name in ("", "   ", "가" * 101):
        with pytest.raises(ValidationError):
            CustomPlaceInput(name=bad_name)
    assert CustomPlaceInput(name="내 장소", latitude=34.7, longitude=127.7).latitude == 34.7
    for bad_point in ({"latitude": 34.7}, {"longitude": 127.7}, {"latitude": 40.0, "longitude": 127.7}, {"latitude": 34.7, "longitude": 123.0}):
        with pytest.raises(ValidationError):
            CustomPlaceInput(name="내 장소", **bad_point)


def test_public_ref_and_kakao_place_id_shapes() -> None:
    assert PublicPlaceRef(source="sangga", sourceId="MA0101").sourceId == "MA0101"
    for bad_ref in ({"source": "kakao", "sourceId": "1"}, {"source": "tourapi", "sourceId": ""}, {"source": "tourapi", "sourceId": "9" * 41}):
        with pytest.raises(ValidationError):
            PublicPlaceRef(**bad_ref)
    assert CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF, kakaoPlaceId="1234567890").kakaoPlaceId == "1234567890"
    for bad_id in ("abc", "12a", "", "1" * 21, "12 34"):
        with pytest.raises(ValidationError):
            CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF, kakaoPlaceId=bad_id)


def test_secure_photo_url_upgrades_only_the_tour_api_host() -> None:
    assert secure_photo_url("http://tong.visitkorea.or.kr/cms/a.jpg") == "https://tong.visitkorea.or.kr/cms/a.jpg"
    assert secure_photo_url("https://tong.visitkorea.or.kr/cms/a.jpg") == "https://tong.visitkorea.or.kr/cms/a.jpg"
    assert secure_photo_url("http://example.com/a.jpg") == "http://example.com/a.jpg"
    assert secure_photo_url(None) is None
    assert public_place_item(public_place(), 0)["photoUrl"] == "https://tong.visitkorea.or.kr/cms/resource/a.jpg"


def test_public_add_saves_only_the_public_values_and_the_kakao_link(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()

    payload = trip_service.add_place_to_trip_day(
        db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, time="12:30", publicPlace=TOUR_REF, kakaoPlaceId="12345"),
    )

    (row,) = saved_places(db)
    assert (row.place_name, row.address, row.place_origin) == ("오동도", "전남광주통합특별시 여수시 오동도로 222", "public")
    assert (float(row.latitude), float(row.longitude)) == (34.7443, 127.7663)
    assert (row.public_source, row.public_source_id, row.public_category) == ("tourapi", "126508", "sight")
    assert (row.photo_url, row.photo_license) == ("https://tong.visitkorea.or.kr/cms/resource/a.jpg", "Type3")
    assert (row.memo, row.category_group_code, row.category_group_name, row.user_label) == (None, None, None, None)
    assert (row.source_provider, row.external_place_id, row.place_url) == ("kakao", "12345", "https://place.map.kakao.com/12345")
    assert row.visit_time.strftime("%H:%M") == "12:30"
    assert (row.order_num, revision_of(db)) == (1, 2)
    added = payload["days"][1][0]
    assert (added["label"], added["meta"], added["placeOrigin"], added["publicCategory"]) == ("오동도", row.address, "public", "sight")
    assert (added["publicSource"], added["publicSourceId"], added["photoLicense"], added["needsConfirmation"]) == ("tourapi", "126508", "Type3", False)
    assert added["placeUrl"] == "https://place.map.kakao.com/12345" and added["externalPlaceId"] == "12345"
    assert added["memo"] is None   # 새로 담은 행은 메모가 비어 있다(수정으로 채운다)


def test_a_public_add_without_a_kakao_id_keeps_no_kakao_link(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF))
    (row,) = saved_places(db)
    assert (row.source_provider, row.external_place_id, row.place_url) == (None, None, None)


def test_custom_add_keeps_the_typed_name_and_only_a_point_the_user_picked(db: Session) -> None:
    owner, _ = seed_trip(db)
    trip_service.add_place_to_trip_day(
        db, owner, "7", 1,
        CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": " 우리 아지트 ", "latitude": 34.75, "longitude": 127.75}, kakaoPlaceId="777"),
    )
    payload = trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=2, customPlace={"name": "이름만"}))

    pinned, unpinned = saved_places(db)
    assert (pinned.place_name, pinned.place_origin, pinned.address) == ("우리 아지트", "custom", None)
    assert (float(pinned.latitude), float(pinned.longitude)) == (34.75, 127.75)
    assert (pinned.public_source, pinned.public_source_id, pinned.public_category, pinned.photo_url, pinned.photo_license) == (None,) * 5
    assert (pinned.category_group_code, pinned.category_group_name, pinned.memo) == (None, None, None)
    assert (pinned.source_provider, pinned.external_place_id, pinned.place_url) == ("kakao", "777", "https://place.map.kakao.com/777")
    assert (unpinned.place_name, unpinned.latitude, unpinned.longitude, unpinned.place_url) == ("이름만", None, None, None)
    assert [place["label"] for place in payload["days"][1]] == ["우리 아지트", "이름만"]
    assert [place["latitude"] for place in payload["days"][1]] == [34.75, None]


def test_batch_add_mixes_public_and_custom_places_in_one_revision(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add_all([public_place(), public_place("MA01", source="sangga", name="카페마레 여수점", category="cafe", photo=None)])
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "먼저 담은 곳"}))

    payload = trip_service.add_places_to_trip_day(
        db, owner, "7", 1,
        CreateTripPlacesRequest(expectedRevision=2, places=[
            {"publicPlace": TOUR_REF, "kakaoPlaceId": "11"},
            {"customPlace": {"name": "직접 적은 곳", "latitude": 34.7, "longitude": 127.7}},
            {"publicPlace": {"source": "sangga", "sourceId": "MA01"}, "time": "15:00"},
            {"publicPlace": TOUR_REF},   # 같은 공공데이터 장소를 또 담아도 된다
        ]),
    )

    rows = saved_places(db)
    assert [row.place_name for row in rows] == ["먼저 담은 곳", "오동도", "직접 적은 곳", "카페마레 여수점", "오동도"]
    assert [row.order_num for row in rows] == [1, 2, 3, 4, 5]
    assert [row.place_origin for row in rows] == ["custom", "public", "custom", "public", "public"]
    assert [row.public_category for row in rows] == [None, "sight", None, "cafe", "sight"]
    assert [row.external_place_id for row in rows] == [None, "11", None, None, None]
    assert rows[3].visit_time.strftime("%H:%M") == "15:00" and rows[3].photo_url is None
    assert revision_of(db) == 3 and payload["revision"] == 3   # 묶음은 한 번만 올린다


def test_a_missing_public_place_is_404_and_writes_nothing(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()

    with pytest.raises(trip_service.TripServiceError) as single:
        trip_service.add_place_to_trip_day(
            db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, publicPlace={"source": "tourapi", "sourceId": "000"}),
        )
    with pytest.raises(trip_service.TripServiceError) as batch:
        trip_service.add_places_to_trip_day(
            db, owner, "7", 1,
            CreateTripPlacesRequest(expectedRevision=1, places=[{"publicPlace": TOUR_REF}, {"publicPlace": {"source": "sangga", "sourceId": "000"}}]),
        )

    assert (single.value.status_code, single.value.detail) == (404, "Public place not found")
    assert (batch.value.status_code, batch.value.detail) == (404, "Public place not found")
    assert saved_places(db) == [] and revision_of(db) == 1   # 앞의 장소가 있어도 하나도 쓰지 않고 revision 도 그대로


def test_stale_revision_and_viewer_are_refused_without_writes(db: Session) -> None:
    owner, _ = seed_trip(db)
    viewer = seed_viewer(db)
    db.add(public_place())
    db.commit()

    with pytest.raises(trip_service.TripServiceError) as stale:
        trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=9, publicPlace=TOUR_REF))
    with pytest.raises(trip_service.TripServiceError) as forbidden:
        trip_service.add_places_to_trip_day(
            db, viewer, "7", 1, CreateTripPlacesRequest(expectedRevision=1, places=[{"publicPlace": {"source": "tourapi", "sourceId": "000"}}]),
        )
    with pytest.raises(trip_service.TripServiceError) as no_day:
        trip_service.add_places_to_trip_day(db, owner, "7", 9, CreateTripPlacesRequest(expectedRevision=1, places=[{"publicPlace": TOUR_REF}]))

    assert stale.value.status_code == 409
    assert forbidden.value.status_code == 403   # 권한 확인이 공공데이터 조회보다 먼저다
    assert (no_day.value.status_code, no_day.value.detail) == (404, "Trip day not found")
    assert saved_places(db) == [] and revision_of(db) == 1


def test_add_routes_answer_with_the_new_fields_and_refuse_the_old_ones(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()
    client = api(owner)

    added = client.post("/api/trips/7/days/1/places", json={"expectedRevision": 1, "publicPlace": TOUR_REF, "kakaoPlaceId": "12345"})
    batch = client.post(
        "/api/trips/7/days/2/places/batch",
        json={"expectedRevision": 2, "places": [{"customPlace": {"name": "내 장소"}}, {"publicPlace": TOUR_REF}]},
    )
    old_single = client.post("/api/trips/7/days/1/places", json={"expectedRevision": 3, "label": "카카오가게", "sourceProvider": "kakao"})
    old_batch = client.post("/api/trips/7/days/1/places/batch", json={"expectedRevision": 3, "places": [{"label": "카카오가게"}]})
    missing = client.post("/api/trips/7/days/1/places", json={"expectedRevision": 3, "publicPlace": {"source": "tourapi", "sourceId": "000"}})

    assert added.status_code == 200 and batch.status_code == 200
    place = added.json()["days"]["1"][0]
    assert (place["label"], place["placeOrigin"], place["publicCategory"], place["photoLicense"]) == ("오동도", "public", "sight", "Type3")
    assert place["photoUrl"].startswith("https://") and place["needsConfirmation"] is False
    assert [item["placeOrigin"] for item in batch.json()["days"]["2"]] == ["custom", "public"]
    assert (old_single.status_code, old_batch.status_code) == (422, 422)
    # 화면은 이 오류 종류(모르는 필드)를 보고 '새로 고침'을 안내한다(과제 9 의 isStaleScreenError) - 422 모양이 바뀌면 여기서 걸린다
    for old in (old_single, old_batch):
        assert "extra_forbidden" in {error["type"] for error in old.json()["detail"]}
    assert (missing.status_code, missing.json()) == (404, {"detail": "Public place not found"})
    assert revision_of(db) == 3 and len(saved_places(db)) == 3


@pytest.mark.parametrize(("path", "body", "extra"), [
    ("/api/trips/7/days/1/places", {"expectedRevision": 1, "publicPlace": {**TOUR_REF, "name": "카카오가 준 이름"}}, "name"),
    ("/api/trips/7/days/1/places/batch",
     {"expectedRevision": 1, "places": [{"customPlace": {"name": "내 장소", "address": "카카오가 준 주소"}}]}, "address"),
])
def test_unknown_fields_inside_public_or_custom_place_are_refused_and_nothing_is_written(
    db: Session, api: Callable[[User], TestClient], path: str, body: dict[str, object], extra: str
) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()

    response = api(owner).post(path, json=body)

    assert response.status_code == 422
    assert [(error["type"], error["loc"][-1]) for error in response.json()["detail"]] == [("extra_forbidden", extra)]
    assert saved_places(db) == [] and revision_of(db) == 1   # 숨은 값을 조용히 버리고 담지 않는다


def test_itinerary_places_tell_new_rows_from_old_kakao_rows() -> None:
    owner = make_user(1, "Owner")
    trip = Trip(id=7, owner_id=1, title="t", status="confirmed", revision=1, start_date=date(2026, 10, 10), end_date=date(2026, 10, 10), participant_count=1)
    trip.owner, trip.members, trip.policies, trip.invites, trip.recommendations = owner, [], [], [], []
    day = TripDay(id=1, trip_id=7, day_number=1, date=date(2026, 10, 10))
    day.places = [
        TripPlace(id=1, trip_day_id=1, place_name="카카오 예전 행", order_num=1, source_provider="kakao", external_place_id="1",
                  memo="음식점 > 한식 · 전남 여수시"),
        TripPlace(id=2, trip_day_id=1, place_name="로컬 예전 행", order_num=2, source_provider="kakao_local", external_place_id="2"),
        TripPlace(id=3, trip_day_id=1, place_name="카탈로그 예전 행", order_num=3),
        TripPlace(id=4, trip_day_id=1, place_name="오동도", order_num=4, place_origin="public", public_source="tourapi", public_source_id="126508",
                  public_category="sight", photo_url="https://tong.visitkorea.or.kr/a.jpg", photo_license="Type3", source_provider="kakao", external_place_id="4"),
        TripPlace(id=5, trip_day_id=1, place_name="나만의 곳", order_num=5, place_origin="custom", source_provider="kakao", external_place_id="5",
                  memo="일몰 때 가기"),
        TripPlace(id=6, trip_day_id=1, place_name="오동도", order_num=6, place_origin="public", public_source="tourapi", public_source_id="126508",
                  public_category="sight", user_label="내가 부르는 이름"),
    ]
    trip.days = [day]

    places = trip_service.trip_to_api(trip, owner, recommended_policies=[])["days"][1]

    assert [place["needsConfirmation"] for place in places] == [True, True, False, False, False, False]   # 카카오 값을 가진 예전 행만
    assert [place["placeOrigin"] for place in places] == [None, None, None, "public", "custom", "public"]
    assert [place["label"] for place in places] == ["카카오 예전 행", "로컬 예전 행", "카탈로그 예전 행", "오동도", "나만의 곳", "내가 부르는 이름"]   # 사용자 이름이 있으면 그것
    assert (places[3]["publicSource"], places[3]["publicSourceId"], places[3]["publicCategory"]) == ("tourapi", "126508", "sight")
    assert (places[3]["photoUrl"], places[3]["photoLicense"]) == ("https://tong.visitkorea.or.kr/a.jpg", "Type3")
    assert places[0]["publicSource"] is None and places[0]["photoUrl"] is None
    assert [place["memo"] for place in places] == ["음식점 > 한식 · 전남 여수시", None, None, None, "일몰 때 가기", None]   # 저장된 메모 그대로
    assert (places[0]["meta"], places[4]["meta"]) == ("음식점 > 한식 · 전남 여수시", "일몰 때 가기")   # meta 는 메모가 있으면 메모
```

새 시험에는 `publicPlace` · `customPlace` 안에 숨은 모르는 필드(`publicPlace.name`, `customPlace.address`)가 422 로 막히고 아무것도 안 쓰는지, 그리고 응답의 `label` 이 `user_label` 을 따르는지도 들어 있다.

옛 시험 중 새 요청 모양과 맞지 않는 것을 고친다. 요청이 `label` · `meta` · 카카오 필드 대신 `customPlace` · `kakaoPlaceId` 를 쓰게 하고, 저장소에 넘어가는 값과 응답 단언을 새 모양으로 바꾼다. 아래 14개가 구현 전에 이미 실패하는 시험이다.

`backend/tests/test_trip_db_service.py`

- `test_add_place_to_trip_day_persists_place_and_returns_updated_trip` - 저장소 스텁이 `place_origin` 도 옮기게 하고,

전:

```python
        place.category_group_code = kwargs["category_group_code"]
        place.category_group_name = kwargs["category_group_name"]
        place.place_url = kwargs["place_url"]
        place.source_provider = kwargs["source_provider"]
        place.external_place_id = kwargs["external_place_id"]
        trip.days[0].places.append(place)
        return place

    monkeypatch.setattr(trip_service.trip_repository, "add_trip_place", add_place_stub)

    payload = trip_service.add_place_to_trip_day(
```

후:

```python
        place.category_group_code = kwargs["category_group_code"]
        place.category_group_name = kwargs["category_group_name"]
        place.place_url = kwargs["place_url"]
        place.source_provider = kwargs["source_provider"]
        place.external_place_id = kwargs["external_place_id"]
        place.place_origin = kwargs["place_origin"]
        trip.days[0].places.append(place)
        return place

    monkeypatch.setattr(trip_service.trip_repository, "add_trip_place", add_place_stub)

    payload = trip_service.add_place_to_trip_day(
```

  요청과 단언을 바꾼다.

전:

```python
        CreateTripPlaceRequest(
            expectedRevision=1,
            time="14:30",
            label="Cafe stop",
            meta="Dessert",
            address="Gangwon road 1",
            latitude=38.1,
            longitude=128.6,
            category="Food",
            categoryCode="FD6",
            placeUrl="http://place.map.kakao.com/food-1",
            sourceProvider="kakao_local",
            externalPlaceId="food-1",
        ),
    )

    assert captured["trip_day_id"] == 1
    assert captured["place_name"] == "Cafe stop"
    assert captured["visit_time"] == time(14, 30)
    assert captured["order_num"] == 2
    assert captured["address"] == "Gangwon road 1"
    assert captured["latitude"] == 38.1
    assert captured["longitude"] == 128.6
    assert captured["category_group_name"] == "Food"
    assert captured["category_group_code"] == "FD6"
    assert captured["place_url"] == "http://place.map.kakao.com/food-1"
    assert captured["source_provider"] == "kakao_local"
    assert captured["external_place_id"] == "food-1"
    added = payload["days"][1][-1]
    assert added["id"] == "2"
    assert added["time"] == "14:30"
    assert added["label"] == "Cafe stop"
    assert added["meta"] == "Dessert"
    assert added["address"] == "Gangwon road 1"
    assert added["categoryCode"] == "FD6"
    assert added["sourceProvider"] == "kakao_local"
    assert added["externalPlaceId"] == "food-1"
    assert fake_db.commits == 1
```

후:

```python
        CreateTripPlaceRequest(
            expectedRevision=1,
            time="14:30",
            customPlace={"name": "Cafe stop", "latitude": 38.1, "longitude": 128.6},
            kakaoPlaceId="12345",
        ),
    )

    assert captured["trip_day_id"] == 1
    assert captured["place_name"] == "Cafe stop"
    assert captured["visit_time"] == time(14, 30)
    assert captured["order_num"] == 2
    assert captured["address"] is None
    assert captured["latitude"] == 38.1
    assert captured["longitude"] == 128.6
    assert captured["category_group_name"] is None
    assert captured["category_group_code"] is None
    assert captured["place_origin"] == "custom"
    assert captured["place_url"] == "https://place.map.kakao.com/12345"
    assert captured["source_provider"] == "kakao"
    assert captured["external_place_id"] == "12345"
    added = payload["days"][1][-1]
    assert added["id"] == "2"
    assert added["time"] == "14:30"
    assert added["label"] == "Cafe stop"
    assert added["meta"] == ""
    assert added["address"] is None
    assert added["categoryCode"] is None
    assert added["placeOrigin"] == "custom"
    assert added["sourceProvider"] == "kakao"
    assert added["externalPlaceId"] == "12345"
    assert fake_db.commits == 1
```

- `test_add_places_to_trip_day_persists_batch_atomically` - 요청과 단언.

전:

```python
            places=[
                {
                    "time": "",
                    "label": "Cafe stop",
                    "meta": "Dessert",
                    "address": "Gangwon road 1",
                    "category": "Food",
                    "categoryCode": "FD6",
                    "placeUrl": "http://place.map.kakao.com/food-1",
                    "sourceProvider": "kakao",
                    "externalPlaceId": "food-1",
                },
                {"label": "Beach stop", "meta": "Sea"},
            ],
        ),
    )

    assert [item["place_name"] for item in added] == ["Cafe stop", "Beach stop"]
    assert [item["order_num"] for item in added] == [2, 3]
    assert added[0]["visit_time"] is None
    assert added[0]["category_group_code"] == "FD6"
    assert added[0]["source_provider"] == "kakao"
```

후:

```python
            places=[
                {"time": "", "customPlace": {"name": "Cafe stop"}, "kakaoPlaceId": "123"},
                {"customPlace": {"name": "Beach stop"}},
            ],
        ),
    )

    assert [item["place_name"] for item in added] == ["Cafe stop", "Beach stop"]
    assert [item["order_num"] for item in added] == [2, 3]
    assert added[0]["visit_time"] is None
    assert added[0]["source_provider"] == "kakao"
    assert added[1]["source_provider"] is None
```

- `test_add_places_to_trip_day_rejects_stale_revision_without_writes` 와 `test_add_places_to_trip_day_uses_specific_missing_day_error` - 한 줄씩.

  `CreateTripPlacesRequest(expectedRevision=99, places=[{"label": "Cafe stop"}]),` → `CreateTripPlacesRequest(expectedRevision=99, places=[{"customPlace": {"name": "Cafe stop"}}]),`

  `CreateTripPlacesRequest(expectedRevision=1, places=[{"label": "Cafe stop"}]),` → `CreateTripPlacesRequest(expectedRevision=1, places=[{"customPlace": {"name": "Cafe stop"}}]),`

- `test_trip_place_crud_returns_404_for_missing_day_or_place` 와 `test_viewer_member_cannot_edit_trip_places` - 한 줄씩.

  `CreateTripPlaceRequest(expectedRevision=1, time="12:00", label="Missing day", meta=""),` → `CreateTripPlaceRequest(expectedRevision=1, time="12:00", customPlace={"name": "Missing day"}),`

  `CreateTripPlaceRequest(expectedRevision=1, time="12:00", label="Viewer add", meta=""),` → `CreateTripPlaceRequest(expectedRevision=1, time="12:00", customPlace={"name": "Viewer add"}),`

`backend/tests/test_trip_db_routes.py` - 추가 요청 본문과 단언을 새 모양으로 바꾼다(고치기 전 → 후).

- `test_db_trip_place_crud_routes_return_updated_trip`: `json={"time": "10:00", "label": "Cafe", "meta": "Dessert", "expectedRevision": 1},` → `json={"time": "10:00", "customPlace": {"name": "Cafe"}, "expectedRevision": 1},` 그리고 `assert calls[0][1].label == "Cafe"` → `assert calls[0][1].customPlace.name == "Cafe"`
- `test_db_trip_place_batch_route_returns_updated_trip`: `assert [place.label for place in payload.places] == ["Cafe stop", "Beach stop"]` → `assert [place.customPlace.name for place in payload.places] == ["Cafe stop", "Beach stop"]` 그리고 아래 두 줄을

```python
                    {"label": "Cafe stop", "time": "", "sourceProvider": "kakao"},
                    {"label": "Beach stop"},
```

  이렇게.

```python
                    {"customPlace": {"name": "Cafe stop"}, "time": "", "kakaoPlaceId": "123"},
                    {"customPlace": {"name": "Beach stop"}},
```

- `test_db_trip_place_batch_route_maps_missing_day_error`: `json={"expectedRevision": 1, "places": [{"label": "Cafe stop"}]},` → `json={"expectedRevision": 1, "places": [{"customPlace": {"name": "Cafe stop"}}]},`
- `test_db_trip_place_routes_map_service_errors`: `add_response = client.post("/api/trips/7/days/99/places", json={"label": "Missing", "expectedRevision": 1})` → `add_response = client.post("/api/trips/7/days/99/places", json={"customPlace": {"name": "Missing"}, "expectedRevision": 1})`
- `test_db_trip_place_routes_map_viewer_permission_error`: `response = client.post("/api/trips/7/days/1/places", json={"label": "Read only", "expectedRevision": 1})` → `response = client.post("/api/trips/7/days/1/places", json={"customPlace": {"name": "Read only"}, "expectedRevision": 1})`

`backend/tests/test_trip_auth_edge_cases.py` - `test_viewer_cannot_add_place`: `payload=CreateTripPlaceRequest(expectedRevision=1, label="New Place"),` → `payload=CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "New Place"}),` / `test_nonmember_cannot_add_place`: `payload=CreateTripPlaceRequest(expectedRevision=1, label="Sneaky Place"),` → `payload=CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "Sneaky Place"}),`

`backend/tests/test_public_places.py` - `test_match_route_needs_login_and_answers_in_camel_case`: 맞춰 보기 응답의 사진 주소가 https 로 나간다(씨앗 행은 http 그대로 둔다). `"photoUrl": "http://tong.visitkorea.or.kr/a.jpg", "photoLicense": "Type3", "distanceMeters": 0,` → `"photoUrl": "https://tong.visitkorea.or.kr/a.jpg", "photoLicense": "Type3", "distanceMeters": 0,`

- [ ] **2단계: 실패하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_trip_public_places.py`
기대: 수집 오류 1개 - `ImportError: cannot import name 'CustomPlaceInput' from 'app.schemas.trip'`(새 스키마가 없다).

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_trip_db_service.py tests/test_trip_db_routes.py tests/test_trip_auth_edge_cases.py tests/test_public_places.py`
기대: FAIL 14개(`14 failed`) - 고친 옛 시험 중 `test_trip_db_service.py` 6개, `test_trip_db_routes.py` 5개, `test_trip_auth_edge_cases.py` 2개, `test_public_places.py` 1개. 요청에 `label` 이 없다는 검증 오류이거나(`ValidationError`), 사진 주소가 아직 http 다.

- [ ] **3단계: 구현**

`backend/app/schemas/trip.py` 를 고친다.

1. import - `ConfigDict` 를 더하고 공공데이터 분류 형식을 가져온다.

전:

```python
from pydantic import BaseModel, EmailStr, Field, model_validator
```

후:

```python
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.schemas.places import PublicPlaceCategory
```

2. 형식 이름 둘을 `InviteEmailDeliveryStatus` 다음에 더한다.

전:

```python
InviteEmailDeliveryStatus = Literal["sent", "notConfigured", "failed"]
```

후:

```python
InviteEmailDeliveryStatus = Literal["sent", "notConfigured", "failed"]
PlaceOrigin = Literal["public", "custom", "needs_review"]
PublicSource = Literal["tourapi", "sangga"]
```

3. `ItineraryPlace` 끝에 새 필드를 더한다(기존 필드는 예전 행을 보이려고 그대로 둔다).

전:

```python
    sourceProvider: str | None = None
    externalPlaceId: str | None = None


ApplicationStatus = Literal[
```

후:

```python
    sourceProvider: str | None = None
    externalPlaceId: str | None = None
    # 사용자가 쓴 메모(trip_places.memo 그대로) - meta 는 메모가 있으면 메모, 없으면 주소다. 새로 담은 행은 비어 있고 수정(PATCH memo)으로 채운다
    memo: str | None = None
    # 3단계(카카오 운영정책): 저장하는 값은 공공데이터 장소 또는 사용자가 쓴 값이다. placeOrigin 이 비어 있으면 예전 행
    placeOrigin: PlaceOrigin | None = None
    publicSource: PublicSource | None = None
    publicSourceId: str | None = None
    publicCategory: PublicPlaceCategory | None = None
    photoUrl: str | None = None
    photoLicense: str | None = None
    # 예전 카카오 행(placeOrigin 없음 + sourceProvider 가 kakao · kakao_local) - 편집하려면 이름을 다시 적어야 한다
    needsConfirmation: bool = False


ApplicationStatus = Literal[
```

4. `CreateTripPlaceRequest` · `CreateTripPlaceItem` · `CreateTripPlacesRequest` 세 클래스를 아래로 통째로 바꾼다.

전:

```python
class CreateTripPlaceRequest(BaseModel):
    expectedRevision: int = Field(ge=1)
    time: str | None = None
    label: str = Field(min_length=1, max_length=200)
    meta: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    category: str | None = None
    categoryCode: str | None = None
    placeUrl: str | None = None
    sourceProvider: str | None = None
    externalPlaceId: str | None = None


class CreateTripPlaceItem(BaseModel):
    time: str | None = None
    label: str = Field(min_length=1, max_length=200)
    meta: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    category: str | None = None
    categoryCode: str | None = None
    placeUrl: str | None = None
    sourceProvider: str | None = None
    externalPlaceId: str | None = None


class CreateTripPlacesRequest(BaseModel):
    expectedRevision: int = Field(ge=1)
    places: list[CreateTripPlaceItem] = Field(min_length=1, max_length=50)
```

후:

```python
class PublicPlaceRef(BaseModel):
    """공공데이터 장소 참조 - 서버가 자기 표(public_places)에서 값을 채운다. 클라이언트가 보낸 이름 · 주소 · 좌표는 받지 않는다(422) -
    중첩 모델도 extra="forbid" 라 카카오 값이 이 안에 숨어 들어와도 조용히 버려지지 않는다."""

    model_config = ConfigDict(extra="forbid")

    source: PublicSource
    sourceId: str = Field(min_length=1, max_length=40)


class CustomPlaceInput(BaseModel):
    """나만의 장소 - 사용자가 쓴 이름과 (선택) 지도에서 찍은 위치. 위도 · 경도는 둘 다 있거나 둘 다 없다. 그 밖의 필드(주소 등)는 받지 않는다(422)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    latitude: float | None = Field(default=None, ge=33.0, le=39.0)
    longitude: float | None = Field(default=None, ge=124.0, le=132.0)

    @model_validator(mode="after")
    def validate_point(self) -> "CustomPlaceInput":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self


class TripPlaceAddItem(BaseModel):
    """담을 장소 하나. 예전 카카오 필드(label · meta · address · 좌표 · 분류 · placeUrl · sourceProvider · externalPlaceId)는 받지 않는다(422).
    카카오 장소는 장소 ID(kakaoPlaceId)만 받고, place_url 은 서버가 만든다."""

    model_config = ConfigDict(extra="forbid")

    time: str | None = None
    publicPlace: PublicPlaceRef | None = None
    customPlace: CustomPlaceInput | None = None
    kakaoPlaceId: str | None = Field(default=None, pattern=r"^[0-9]{1,20}$")

    @model_validator(mode="after")
    def validate_exactly_one_place(self) -> "TripPlaceAddItem":
        if (self.publicPlace is None) == (self.customPlace is None):
            raise ValueError("Provide exactly one of publicPlace or customPlace")
        return self


class CreateTripPlaceRequest(TripPlaceAddItem):
    expectedRevision: int = Field(ge=1)


class CreateTripPlacesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expectedRevision: int = Field(ge=1)
    places: list[TripPlaceAddItem] = Field(min_length=1, max_length=50)
```

`backend/app/services/public_places.py` - `public_place_item` 앞에 `secure_photo_url` 을 더하고, `public_place_item` 이 쓰게 한다.

전:

```python
def public_place_item(place: PublicPlace, distance: float) -> dict[str, object]:
```

후:

```python
TOUR_API_PHOTO_HTTP_PREFIX = "http://tong.visitkorea.or.kr/"


def secure_photo_url(url: str | None) -> str | None:
    """TourAPI 사진 주소는 http 로 오지만 같은 이미지가 https 로도 열린다(2026-10-05 확인) - https 페이지에서 막히지 않게 바꾼다."""

    if url and url.startswith(TOUR_API_PHOTO_HTTP_PREFIX):
        return "https://" + url.removeprefix("http://")
    return url


def public_place_item(place: PublicPlace, distance: float) -> dict[str, object]:
```

그리고 `public_place_item` 안에서

전:

```python
        "photoUrl": place.photo_url,
        "photoLicense": place.photo_license,
        "distanceMeters": round(distance),
```

후:

```python
        "photoUrl": secure_photo_url(place.photo_url),
        "photoLicense": place.photo_license,
        "distanceMeters": round(distance),
```

`backend/app/repositories/public_places.py` - 파일 끝에 더한다(`Session` · `PublicPlace` 는 이미 가져와 있다).

```python
def get_public_place(db: Session, source: str, source_id: str) -> PublicPlace | None:
    """(출처, 출처 ID)로 한 곳 - 일정에 담을 때 서버가 이 값으로 장소 열을 채운다."""

    return db.get(PublicPlace, (source, source_id))
```

`backend/app/repositories/trips.py` - `add_trip_place` 에 출처 열 여섯 개와 `user_label` 을 더한다.

전:

```python
    category_group_name: str | None = None,
    place_url: str | None = None,
) -> TripPlace:
```

후:

```python
    category_group_name: str | None = None,
    place_url: str | None = None,
    place_origin: str | None = None,
    public_source: str | None = None,
    public_source_id: str | None = None,
    public_category: str | None = None,
    photo_url: str | None = None,
    photo_license: str | None = None,
    user_label: str | None = None,
) -> TripPlace:
```

그리고 `TripPlace(...)` 를 만드는 곳에서

전:

```python
        category_group_name=category_group_name,
        place_url=place_url,
    )
    db.add(place)
```

후:

```python
        category_group_name=category_group_name,
        place_url=place_url,
        place_origin=place_origin,
        public_source=public_source,
        public_source_id=public_source_id,
        public_category=public_category,
        photo_url=photo_url,
        photo_license=photo_license,
        user_label=user_label,
    )
    db.add(place)
```

`backend/app/services/trip_public_places.py` 를 만든다.

```python
"""일정 장소와 공공데이터 장소(카카오 운영정책 3단계) - 담을 때 저장하는 열 값과 예전 카카오 행 판별.

일정에 저장하는 값은 공공데이터 장소(public_places)의 값과 사용자가 직접 쓴 값뿐이다. 카카오 로컬 값(장소명 · 주소 · 좌표 · 전화 · 분류)은
저장하지 않고, 카카오 장소 ID 와 place_url 만 '카카오맵에서 보기' 링크로 남긴다.
설계: docs/superpowers/specs/2026-10-03-public-place-storage-design.md.
"""

from __future__ import annotations

from app.models import PublicPlace, TripPlace
from app.services.public_places import secure_photo_url

LEGACY_KAKAO_PROVIDERS = frozenset({"kakao", "kakao_local"})
KAKAO_PLACE_URL = "https://place.map.kakao.com/{kakao_place_id}"


def is_legacy_kakao_place(place: TripPlace) -> bool:
    """예전 카카오 행 - 출처 열(place_origin)이 비어 있고 카카오에서 온 행. 이름 · 주소 · 좌표가 카카오 값이라 4단계에서 변환한다."""

    return place.place_origin is None and place.source_provider in LEGACY_KAKAO_PROVIDERS


def public_place_columns(place: PublicPlace) -> dict[str, object]:
    """공공데이터 장소 → trip_places 열. 이름 · 주소 · 좌표 · 분류 · 사진을 복사하고 출처를 남긴다(외래키는 없다).
    사용자가 붙인 이름(user_label)은 비운다 - 장소를 바꿀 때 예전 이름이 따라오지 않게 값 열을 모두 이 함수가 정한다."""

    return {
        "place_name": place.name,
        "address": place.address,
        "latitude": place.latitude,
        "longitude": place.longitude,
        "category_group_code": None,
        "category_group_name": None,
        "place_origin": "public",
        "public_source": place.source,
        "public_source_id": place.source_id,
        "public_category": place.category,
        "photo_url": secure_photo_url(place.photo_url),
        "photo_license": place.photo_license,
        "user_label": None,
    }


def custom_place_columns(name: str, latitude: float | None, longitude: float | None) -> dict[str, object]:
    """나만의 장소 → trip_places 열. 사용자가 쓴 이름과 지도에서 찍은 위치(없으면 비움)만 둔다. 이름은 place_name 자체라 user_label 은 비운다."""

    return {
        "place_name": name,
        "address": None,
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
    }


def kakao_link_columns(kakao_place_id: str | None) -> dict[str, object]:
    """카카오 장소 ID → '카카오맵에서 보기' 링크 열. place_url 은 서버가 만든다(클라이언트가 보낸 주소는 받지 않는다)."""

    if not kakao_place_id:
        return {"source_provider": None, "external_place_id": None, "place_url": None}
    return {
        "source_provider": "kakao",
        "external_place_id": kakao_place_id,
        "place_url": KAKAO_PLACE_URL.format(kakao_place_id=kakao_place_id),
    }
```

`backend/app/services/trips.py` 를 고친다.

1. import 네 곳 - `PublicPlace`, 공공데이터 저장소, 새 스키마 이름, 새 서비스 모듈.

전:

```python
from app.models import ExternalSourceRecord, Policy, Trip, TripDay, TripInvite, TripPlace, TripPolicy, User
```

후:

```python
from app.models import ExternalSourceRecord, Policy, PublicPlace, Trip, TripDay, TripInvite, TripPlace, TripPolicy, User
```

전:

```python
from app.repositories import policies as policy_repository
from app.repositories import trips as trip_repository
```

후:

```python
from app.repositories import policies as policy_repository
from app.repositories import public_places as public_place_repository
from app.repositories import trips as trip_repository
```

전:

```python
    CreateTripRequest,
    MAX_TRIP_PARTICIPANTS,
    MoveTripPlaceRequest,
    SendInviteEmailRequest,
    UpdateTripSettingsRequest,
```

후:

```python
    CreateTripRequest,
    CustomPlaceInput,
    MAX_TRIP_PARTICIPANTS,
    MoveTripPlaceRequest,
    PublicPlaceRef,
    SendInviteEmailRequest,
    TripPlaceAddItem,
    UpdateTripSettingsRequest,
```

전:

```python
from app.services import itinerary_recommendations
```

후:

```python
from app.services import itinerary_recommendations
from app.services import trip_public_places
```

2. `trip_to_api` - 장소 dict 에 새 필드를 더하고, `label` 이 사용자가 붙인 이름을 따르게 한다.

전:

```python
                "sourceProvider": getattr(place, "source_provider", None),
                "externalPlaceId": getattr(place, "external_place_id", None),
            }
            for place in places
```

후:

```python
                "sourceProvider": getattr(place, "source_provider", None),
                "externalPlaceId": getattr(place, "external_place_id", None),
                "memo": place.memo,
                "placeOrigin": place.place_origin,
                "publicSource": place.public_source,
                "publicSourceId": place.public_source_id,
                "publicCategory": place.public_category,
                "photoUrl": place.photo_url,
                "photoLicense": place.photo_license,
                "needsConfirmation": trip_public_places.is_legacy_kakao_place(place),
            }
            for place in places
```

전:

```python
                "label": place.place_name,
```

후:

```python
                "label": place.user_label or place.place_name,   # 사용자가 붙인 이름이 있으면 그것(공공데이터 장소의 이름은 place_name 에 그대로 있다)
```

3. `add_place_to_trip_day` 와 `add_places_to_trip_day` 두 함수를 아래로 통째로 바꾼다(앞에 `PUBLIC_PLACE_NOT_FOUND` · `_value_columns` · `_new_place_columns` 가 들어간다). 옛 `Place label is required` 검사는 스키마(`min_length=1` + 공백 제거)가 맡는다.

전:

```python
def add_place_to_trip_day(
    db: Session,
    user: User,
    trip_handle: str,
    day_number: int,
    payload: CreateTripPlaceRequest,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    trip_day = _find_trip_day(trip, day_number)
    label = payload.label.strip()
    if not label:
        raise TripServiceError(422, "Place label is required")
    _bump_trip_revision_or_conflict(db, trip, payload.expectedRevision)

    next_order = max((place.order_num or 0 for place in trip_day.places), default=0) + 1
    trip_repository.add_trip_place(
        db,
        trip_day_id=trip_day.id,
        place_name=label,
        visit_time=_parse_optional_time(payload.time),
        order_num=next_order,
        memo=payload.meta.strip() if payload.meta is not None else None,
        address=payload.address.strip() if payload.address else None,
        latitude=payload.latitude,
        longitude=payload.longitude,
        category_group_code=payload.categoryCode,
        category_group_name=payload.category,
        place_url=payload.placeUrl,
        source_provider=payload.sourceProvider,
        external_place_id=payload.externalPlaceId,
    )
    db.commit()
    return _refresh_trip_payload(db, trip.id, user)


def add_places_to_trip_day(
    db: Session,
    user: User,
    trip_handle: str,
    day_number: int,
    payload: CreateTripPlacesRequest,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    trip_day = _find_trip_day_for_batch(trip, day_number)
    labels = [place.label.strip() for place in payload.places]
    if any(not label for label in labels):
        raise TripServiceError(422, "Place label is required")
    _bump_trip_revision_or_conflict(db, trip, payload.expectedRevision)

    next_order = max((place.order_num or 0 for place in trip_day.places), default=0) + 1
    for index, place in enumerate(payload.places):
        trip_repository.add_trip_place(
            db,
            trip_day_id=trip_day.id,
            place_name=labels[index],
            visit_time=_parse_optional_time(place.time),
            order_num=next_order + index,
            memo=place.meta.strip() if place.meta is not None else None,
            address=place.address.strip() if place.address else None,
            latitude=place.latitude,
            longitude=place.longitude,
            category_group_code=place.categoryCode,
            category_group_name=place.category,
            place_url=place.placeUrl,
            source_provider=place.sourceProvider,
            external_place_id=place.externalPlaceId,
        )

    db.commit()
    return _refresh_trip_payload(db, trip.id, user)
```

후:

```python
PUBLIC_PLACE_NOT_FOUND = "Public place not found"


def _value_columns(
    db: Session,
    public_ref: PublicPlaceRef | None,
    custom: CustomPlaceInput | None,
    found: dict[tuple[str, str], PublicPlace],
) -> dict[str, object] | None:
    """공공데이터 참조 또는 나만의 장소 → trip_places 열 값(둘 다 없으면 None). 참조는 서버 표에서 찾아 그 값을 복사한다 -
    없으면 404. revision 을 올리기 전에 부른다. found 는 같은 요청에서 이미 찾은 장소(묶음 추가에서 되풀이를 줄인다)."""

    if public_ref is not None:
        key = (public_ref.source, public_ref.sourceId)
        if key not in found:
            public_place = public_place_repository.get_public_place(db, *key)
            if public_place is None:
                raise TripServiceError(404, PUBLIC_PLACE_NOT_FOUND)
            found[key] = public_place
        return trip_public_places.public_place_columns(found[key])
    if custom is not None:
        return trip_public_places.custom_place_columns(custom.name, custom.latitude, custom.longitude)
    return None


def _new_place_columns(db: Session, items: list[TripPlaceAddItem]) -> list[dict[str, object]]:
    """담을 장소마다 trip_places 열 값을 만든다(trip_public_places). 공공데이터 참조는 revision 을 올리기 전에 모두 찾는다 -
    하나라도 없으면 404 로 멈춰 아무것도 쓰지 않고 revision 도 그대로다. 시간 형식 오류(422)도 여기서 먼저 걸린다."""

    found: dict[tuple[str, str], PublicPlace] = {}
    rows: list[dict[str, object]] = []
    for item in items:
        columns = _value_columns(db, item.publicPlace, item.customPlace, found)   # 스키마가 둘 중 정확히 하나를 보장한다
        columns.update(trip_public_places.kakao_link_columns(item.kakaoPlaceId))
        columns["visit_time"] = _parse_optional_time(item.time)
        rows.append(columns)
    return rows


def add_place_to_trip_day(
    db: Session,
    user: User,
    trip_handle: str,
    day_number: int,
    payload: CreateTripPlaceRequest,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    trip_day = _find_trip_day(trip, day_number)
    (columns,) = _new_place_columns(db, [payload])
    _bump_trip_revision_or_conflict(db, trip, payload.expectedRevision)

    next_order = max((place.order_num or 0 for place in trip_day.places), default=0) + 1
    trip_repository.add_trip_place(db, trip_day_id=trip_day.id, order_num=next_order, memo=None, **columns)
    db.commit()
    return _refresh_trip_payload(db, trip.id, user)


def add_places_to_trip_day(
    db: Session,
    user: User,
    trip_handle: str,
    day_number: int,
    payload: CreateTripPlacesRequest,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    trip_day = _find_trip_day_for_batch(trip, day_number)
    rows = _new_place_columns(db, payload.places)
    _bump_trip_revision_or_conflict(db, trip, payload.expectedRevision)

    next_order = max((place.order_num or 0 for place in trip_day.places), default=0) + 1
    for index, columns in enumerate(rows):
        trip_repository.add_trip_place(db, trip_day_id=trip_day.id, order_num=next_order + index, memo=None, **columns)

    db.commit()
    return _refresh_trip_payload(db, trip.id, user)
```

라우트(`api/routes/trips.py`)는 요청 클래스 이름이 그대로라 고치지 않는다.

- [ ] **4단계: 통과하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_trip_public_places.py tests/test_trip_db_service.py tests/test_trip_db_routes.py tests/test_trip_auth_edge_cases.py tests/test_public_places.py tests/test_db_schema.py tests/test_admin_service.py`
기대: 모두 PASS(`254 passed`). 새 시험 24개(옛 카카오 필드 10개 · 중첩 모르는 필드 2개 각각 포함)와 옛 시험 14개가 통과하고, `trip_to_api` 를 쓰는 `test_admin_service.py` 도 그대로 통과한다.

주의: 이 과제부터 현재 프론트(옛 요청 모양을 보낸다)는 장소 추가가 422 로 막힌다. 프론트 부분이 같은 PR 에 들어가야 한다.

---

### Task 4: 수정 - 예전 카카오 행 변환과 공공데이터 후보 경로

**파일:**
- 고치기: `backend/app/schemas/trip.py`(`UpdateTripPlaceRequest`, 새 `LegacyPlaceCandidatesResponse`)
- 고치기: `backend/app/services/trips.py`(`update_trip_place`, 새 `list_legacy_place_candidates`)
- 고치기: `backend/app/api/routes/trips.py`(새 경로)
- 고치기: `backend/tests/test_trip_public_places.py`, `backend/tests/test_trip_db_service.py`

**인터페이스:**
- 받는 것: 과제 3의 `_value_columns` · `is_legacy_kakao_place` · `custom_place_columns` · `PublicPlaceRef` · `CustomPlaceInput`(둘 다 `extra="forbid"`), 과제 2의 `TripPlace.user_label`, 2단계의 `match_place` · `public_place_item`.
- 내놓는 것:
  - `UpdateTripPlaceRequest(expectedRevision, time?, label?, memo?, publicPlace?, customPlace?)`(`extra="forbid"`) - `label` 1~100자(앞뒤 공백 뺀 뒤), `memo` 0~500자, `publicPlace` 와 `customPlace` 는 함께 올 수 없다(422). 옛 `meta` 는 받지 않는다(422). `publicPlace` · `customPlace` 안의 모르는 필드(`publicPlace.latitude`, `customPlace.address` 등)도 받지 않는다(422) - 과제 3 의 중첩 모델이 막는다.
  - 수정 규칙(`update_trip_place`, 시그니처 그대로):
    - `time` 은 모든 행에 적용한다. 예전 행의 `time` 만 바꾸는 요청은 변환하지 않는다.
    - `label` = 사용자가 쓴 이름. 담기는 자리는 행 종류에 따라 다르다. **공공데이터 장소 행**(`public`)은 `user_label` 에 따로 담고 `place_name` · 주소 · 좌표 · 분류 · 사진 · 출처는 공공데이터 값 그대로 둔다(한 열에 이름이 섞이지 않는다). **나만의 장소 행**(`custom`)은 `place_name` 자체를 바꾼다. **예전 카카오 행**은 아래처럼 `custom` 으로 바꾼다(`user_label` 은 비어 있다). 응답의 `label` 은 `user_label` 이 있으면 그것이다.
    - `memo` = 사용자 메모(빈 문자열 · `null` 은 지움 - 응답의 `ItineraryPlace.memo` 로 그대로 돌아온다). 새 방식 행(`public` · `custom`)은 이름을 고쳐도 출처 열 · 공공데이터 열을 그대로 둔다.
    - `publicPlace` / `customPlace` = 그 장소로 바꾸기. 공공데이터 값 또는 사용자 값으로 이름 · 주소 · 좌표 · 분류 · 사진 · 출처 열을 새로 채우고 `user_label` 은 비운다(`public_place_columns` · `custom_place_columns` 가 정한다). 같은 요청에 `label` 이 함께 오면 바뀐 행에 적용한다 - 공공데이터 장소로 바꾸면서 보낸 `label` 은 그 장소의 `user_label` 이 된다. 없는 공공데이터 장소는 revision 을 올리기 전에 404.
    - **예전 카카오 행**(`needsConfirmation`)은 `label` 만 와도 `custom` 으로 바꾼다(이름 = `label`, 주소 · 좌표 · 분류 · 메모를 지운다). `publicPlace` / `customPlace` 로 바꿀 때도 카카오 '분류 · 주소' 문구인 `memo` 를 지운다. 새 방식 행은 `memo` 를 지우지 않는다. 카카오 ID · `place_url` · `source_provider` 는 어느 경우에도 남긴다.
  - `list_legacy_place_candidates(db, user, trip_handle, place_id) -> list[dict]`(편집 권한) - 예전 카카오 행의 저장된 이름 · 좌표 · 분류로 `match_place` 를 서버 메모리에서 돌려 후보(바로 맞음 포함, 가까운 순 최대 3)를 `public_place_item` 모양으로 낸다. 예전 행이 아니거나 좌표가 없으면 빈 목록. 받은 값은 저장 · 로그하지 않는다.
  - `GET /api/trips/{trip_id}/places/{place_id}/public-candidates` → `LegacyPlaceCandidatesResponse{places: PublicPlaceItem[]}`. 403 viewer, 404 일정 · 장소 없음.

- [ ] **1단계: 실패하는 시험 쓰기**

`backend/tests/test_trip_public_places.py` - 위쪽 import 를 고친다(로그 · 시간 · Decimal · `func` · 수정 요청 클래스).

전:

```python
from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime
```

후:

```python
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from datetime import date, datetime, time
from decimal import Decimal
```

`from sqlalchemy import BigInteger, Integer, create_engine, select` → `from sqlalchemy import BigInteger, Integer, create_engine, func, select`

`from app.schemas.trip import CreateTripPlacesRequest, CreateTripPlaceRequest, CustomPlaceInput, PublicPlaceRef` → `from app.schemas.trip import CreateTripPlacesRequest, CreateTripPlaceRequest, CustomPlaceInput, PublicPlaceRef, UpdateTripPlaceRequest`

파일 끝에 시험을 더한다.

```python
LEGACY_ID = 10


def seed_legacy_place(db: Session, **overrides: object) -> TripPlace:
    """3단계 이전에 카카오 값으로 저장된 행(이름 · 주소 · 좌표 · 분류가 카카오 값, memo 는 '분류 · 주소' 문구)."""

    values: dict[str, object] = dict(
        id=LEGACY_ID, trip_day_id=1, place_name="카카오에서온가게이름", address="전남 여수시 수정동 1", latitude=Decimal("34.7443000"),
        longitude=Decimal("127.7663000"), source_provider="kakao", external_place_id="777", category_group_code="FD6",
        category_group_name="음식점", place_url="https://place.map.kakao.com/777", memo="음식점 > 한식 · 전남 여수시 수정동 1",
        visit_time=time(12, 0), order_num=1,
    )
    place = TripPlace(**{**values, **overrides})
    db.add(place)
    db.commit()
    return place


def row_values(place: TripPlace) -> dict[str, object]:
    return {column.name: getattr(place, column.name) for column in TripPlace.__table__.columns}


def patch(db: Session, user: User, place_id: int, revision: int, **fields: object) -> dict[str, object]:
    return trip_service.update_trip_place(db, user, "7", place_id, UpdateTripPlaceRequest(expectedRevision=revision, **fields))


def test_update_requests_check_name_memo_and_replacement_rules() -> None:
    assert UpdateTripPlaceRequest(expectedRevision=1, label="  새 이름  ").label == "새 이름"
    assert UpdateTripPlaceRequest(expectedRevision=1, label="가" * 100, memo="나" * 500).memo == "나" * 500
    for bad in ({"label": ""}, {"label": "   "}, {"label": "가" * 101}, {"memo": "나" * 501}, {"meta": "옛 필드"}, {"address": "주소"},
                {"publicPlace": TOUR_REF, "customPlace": {"name": "내 장소"}},
                {"publicPlace": {**TOUR_REF, "name": "카카오 이름"}}, {"customPlace": {"name": "내 장소", "address": "카카오 주소"}}):
        with pytest.raises(ValidationError):
            UpdateTripPlaceRequest(expectedRevision=1, **bad)
    assert UpdateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF).customPlace is None


def test_a_time_only_patch_leaves_a_legacy_row_untouched(db: Session) -> None:
    owner, _ = seed_trip(db)
    legacy = seed_legacy_place(db)
    before = row_values(legacy)

    payload = patch(db, owner, LEGACY_ID, 1, time="15:30")

    (row,) = saved_places(db)
    assert row.visit_time.strftime("%H:%M") == "15:30"
    assert {**row_values(row), "visit_time": before["visit_time"]} == before   # 시간만 바뀌고 카카오 값은 그대로(변환 없음)
    assert row.place_origin is None and revision_of(db) == 2
    shown = payload["days"][1][0]
    assert (shown["needsConfirmation"], shown["placeOrigin"], shown["label"]) == (True, None, "카카오에서온가게이름")
    assert shown["memo"] == before["memo"]   # 변환하지 않았으니 메모도 그대로


def test_a_new_name_turns_a_legacy_row_into_a_custom_place_and_drops_the_kakao_values(db: Session) -> None:
    owner, _ = seed_trip(db)
    seed_legacy_place(db)

    payload = patch(db, owner, LEGACY_ID, 1, label=" 우리 단골집 ")

    (row,) = saved_places(db)
    assert (row.place_name, row.place_origin) == ("우리 단골집", "custom")
    assert (row.address, row.latitude, row.longitude, row.memo) == (None, None, None, None)
    assert (row.category_group_code, row.category_group_name) == (None, None)
    assert (row.public_source, row.public_source_id, row.public_category, row.photo_url, row.photo_license, row.user_label) == (None,) * 6
    assert (row.source_provider, row.external_place_id, row.place_url) == ("kakao", "777", "https://place.map.kakao.com/777")   # 링크는 남긴다
    assert row.visit_time.strftime("%H:%M") == "12:00"
    shown = payload["days"][1][0]
    assert (shown["needsConfirmation"], shown["placeOrigin"], shown["meta"], shown["memo"]) == (False, "custom", "", None)


def test_a_custom_place_replaces_a_legacy_row_with_the_picked_point(db: Session) -> None:
    owner, _ = seed_trip(db)
    seed_legacy_place(db)

    patch(db, owner, LEGACY_ID, 1, customPlace={"name": "내가 찍은 곳", "latitude": 34.8, "longitude": 127.8}, time="18:00")
    (pinned,) = saved_places(db)
    assert (pinned.place_name, pinned.place_origin, pinned.address, pinned.memo) == ("내가 찍은 곳", "custom", None, None)
    assert (float(pinned.latitude), float(pinned.longitude)) == (34.8, 127.8)
    assert (pinned.category_group_code, pinned.category_group_name, pinned.external_place_id) == (None, None, "777")
    assert pinned.visit_time.strftime("%H:%M") == "18:00"

    patch(db, owner, LEGACY_ID, 2, customPlace={"name": "위치는 안 찍음"})
    (unpinned,) = saved_places(db)
    assert (unpinned.place_name, unpinned.latitude, unpinned.longitude) == ("위치는 안 찍음", None, None)


def test_a_public_place_replaces_a_legacy_row_with_the_public_values(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()
    seed_legacy_place(db)

    patch(db, owner, LEGACY_ID, 1, publicPlace=TOUR_REF)

    (row,) = saved_places(db)
    assert (row.place_name, row.address, row.place_origin) == ("오동도", "전남광주통합특별시 여수시 오동도로 222", "public")
    assert (float(row.latitude), float(row.longitude)) == (34.7443, 127.7663)
    assert (row.public_source, row.public_source_id, row.public_category) == ("tourapi", "126508", "sight")
    assert (row.photo_url, row.photo_license) == ("https://tong.visitkorea.or.kr/cms/resource/a.jpg", "Type3")
    assert (row.category_group_code, row.category_group_name, row.memo) == (None, None, None)   # 카카오 분류 · '분류 · 주소' 문구를 지운다
    assert (row.source_provider, row.external_place_id, row.place_url) == ("kakao", "777", "https://place.map.kakao.com/777")


def test_renaming_a_public_row_stores_the_users_name_apart_and_keeps_the_public_values(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()
    trip_service.add_place_to_trip_day(
        db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF, kakaoPlaceId="12345"),
    )
    (added,) = saved_places(db)
    before = row_values(added)

    shown = patch(db, owner, added.id, 2, label="  내가 부르는 이름  ")["days"][1][0]

    (row,) = saved_places(db)
    assert row.user_label == "내가 부르는 이름"
    assert {**row_values(row), "user_label": None} == before   # 사용자 이름 말고는 한 열도 안 바뀐다 - 공공데이터 이름 · 주소 · 좌표 · 사진 · 출처 · 카카오 링크 그대로
    assert (row.place_name, row.place_origin) == ("오동도", "public")   # 이름이 섞이지 않는다
    assert (shown["label"], shown["placeOrigin"], shown["publicSourceId"]) == ("내가 부르는 이름", "public", "126508")   # 화면 이름은 사용자 이름

    patch(db, owner, added.id, 3, label="또 다른 이름")
    assert saved_places(db)[0].user_label == "또 다른 이름"


def test_renaming_a_custom_row_changes_its_name_itself(db: Session) -> None:
    owner, _ = seed_trip(db)
    trip_service.add_place_to_trip_day(
        db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "내 장소", "latitude": 34.75, "longitude": 127.75}),
    )
    (placed,) = saved_places(db)

    shown = patch(db, owner, placed.id, 2, label="새 이름")["days"][1][0]

    (row,) = saved_places(db)
    assert (row.place_name, row.user_label, row.place_origin) == ("새 이름", None, "custom")   # 나만의 장소는 이름 자체가 사용자 이름이다
    assert (float(row.latitude), float(row.longitude)) == (34.75, 127.75)
    assert shown["label"] == "새 이름"


def test_replacing_a_row_drops_the_users_name_but_a_label_sent_along_still_applies(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add_all([public_place(), public_place("MA01", source="sangga", name="카페마레 여수점", category="cafe", photo=None)])
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF))
    (placed,) = saved_places(db)
    patch(db, owner, placed.id, 2, label="내가 부르는 이름")
    assert saved_places(db)[0].user_label == "내가 부르는 이름"

    patch(db, owner, placed.id, 3, publicPlace={"source": "sangga", "sourceId": "MA01"})   # 다른 장소로 바꾸면 예전 사용자 이름은 버린다
    row = saved_places(db)[0]
    assert (row.place_name, row.user_label) == ("카페마레 여수점", None)

    patch(db, owner, placed.id, 4, label="우리 카페")
    patch(db, owner, placed.id, 5, customPlace={"name": "내가 찍은 곳"})
    row = saved_places(db)[0]
    assert (row.place_name, row.place_origin, row.user_label) == ("내가 찍은 곳", "custom", None)

    shown = patch(db, owner, placed.id, 6, publicPlace=TOUR_REF, label="한꺼번에")["days"][1][0]   # label 이 함께 오면 바뀐 행에 적용한다
    row = saved_places(db)[0]
    assert (row.place_name, row.place_origin, row.user_label, shown["label"]) == ("오동도", "public", "한꺼번에", "한꺼번에")


def test_a_memo_is_the_users_own_text_and_an_empty_one_clears_it(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF))
    (added,) = saved_places(db)

    shown = patch(db, owner, added.id, 2, memo="  일몰 때 가기  ")["days"][1][0]
    assert (shown["memo"], shown["meta"]) == ("일몰 때 가기", "일몰 때 가기")   # 응답에 메모가 따로 오고, meta 는 메모가 있으면 메모
    (row,) = saved_places(db)
    assert (row.memo, row.place_origin, row.public_source_id, row.photo_license) == ("일몰 때 가기", "public", "126508", "Type3")   # 공공데이터 열은 그대로

    cleared = patch(db, owner, added.id, 3, memo="")["days"][1][0]
    assert saved_places(db)[0].memo is None
    assert (cleared["memo"], cleared["meta"]) == (None, "전남광주통합특별시 여수시 오동도로 222")   # 메모가 없으면 meta 는 주소
    patch(db, owner, added.id, 4, memo="다시 적음")
    patch(db, owner, added.id, 5, memo=None)
    assert saved_places(db)[0].memo is None


def test_switching_a_new_row_between_public_and_custom_keeps_the_users_memo(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "내 장소"}))
    placed = saved_places(db)[0]
    patch(db, owner, placed.id, 2, memo="내 메모")

    patch(db, owner, placed.id, 3, publicPlace=TOUR_REF)
    row = saved_places(db)[0]
    assert (row.place_name, row.place_origin, row.memo) == ("오동도", "public", "내 메모")   # 예전 카카오 행이 아니면 메모를 지우지 않는다

    patch(db, owner, placed.id, 4, customPlace={"name": "다시 내 장소"})
    row = saved_places(db)[0]
    assert (row.place_name, row.place_origin, row.memo) == ("다시 내 장소", "custom", "내 메모")
    assert (row.public_source, row.public_source_id, row.public_category, row.photo_url, row.address) == (None,) * 5


def test_a_missing_public_place_in_a_patch_is_404_and_changes_nothing(db: Session) -> None:
    owner, _ = seed_trip(db)
    legacy = seed_legacy_place(db)
    before = row_values(legacy)

    with pytest.raises(trip_service.TripServiceError) as error:
        patch(db, owner, LEGACY_ID, 1, publicPlace={"source": "tourapi", "sourceId": "000"}, time="15:00")

    assert (error.value.status_code, error.value.detail) == (404, "Public place not found")
    assert row_values(saved_places(db)[0]) == before and revision_of(db) == 1


def test_patch_routes_convert_legacy_rows_and_refuse_old_fields(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db)
    seed_legacy_place(db)
    client = api(owner)

    old_field = client.patch(f"/api/trips/7/places/{LEGACY_ID}", json={"expectedRevision": 1, "meta": "옛 메모"})
    renamed = client.patch(f"/api/trips/7/places/{LEGACY_ID}", json={"expectedRevision": 1, "label": "우리 단골집"})

    assert old_field.status_code == 422
    assert renamed.status_code == 200
    shown = renamed.json()["days"]["1"][0]
    assert (shown["label"], shown["placeOrigin"], shown["needsConfirmation"], shown["address"]) == ("우리 단골집", "custom", False, None)


@pytest.mark.parametrize(("replacement", "extra"), [
    ({"publicPlace": {**TOUR_REF, "latitude": 34.7443}}, "latitude"),
    ({"customPlace": {"name": "내 장소", "address": "카카오 주소"}}, "address"),
])
def test_unknown_fields_inside_public_or_custom_place_of_a_patch_are_refused_and_change_nothing(
    db: Session, api: Callable[[User], TestClient], replacement: dict[str, object], extra: str
) -> None:
    owner, _ = seed_trip(db)
    before = row_values(seed_legacy_place(db))

    response = api(owner).patch(f"/api/trips/7/places/{LEGACY_ID}", json={"expectedRevision": 1, **replacement})

    assert response.status_code == 422
    assert [(error["type"], error["loc"][-1]) for error in response.json()["detail"]] == [("extra_forbidden", extra)]
    assert row_values(saved_places(db)[0]) == before and revision_of(db) == 1


def seed_candidate_places(db: Session) -> None:
    db.add_all([
        public_place("T1", name="오동도횟집", category="food", photo=None, lat=34.7446, lng=127.7666),
        public_place("T2", source="sangga", name="오동도횟집바다", category="food", photo=None, lat=34.7447, lng=127.7667),
        public_place("T3", source="sangga", name="오동도횟집별관", category="food", photo=None, lat=34.7448, lng=127.7668),
        public_place("T4", source="sangga", name="오동도횟집본점", category="food", photo=None, lat=34.7449, lng=127.7669),
        public_place("FAR", name="오동도횟집먼곳", category="food", photo=None, lat=35.2, lng=128.2),
        public_place("OTHER", name="전혀 다른 가게", category="food", photo=None),
    ])
    db.commit()


def test_public_candidates_for_a_legacy_row_are_the_nearest_three_public_places(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db)
    seed_candidate_places(db)
    seed_legacy_place(db, place_name="오동도횟")   # 공공데이터 이름 네 곳에 들어 있다(포함) - 먼 곳 · 다른 이름은 후보가 아니다

    response = api(owner).get(f"/api/trips/7/places/{LEGACY_ID}/public-candidates")

    assert response.status_code == 200
    body = response.json()
    assert [place["sourceId"] for place in body["places"]] == ["T1", "T2", "T3"]   # 가까운 순 최대 3곳
    assert set(body["places"][0]) == {"source", "sourceId", "name", "address", "latitude", "longitude", "category", "sido", "city",
                                      "photoUrl", "photoLicense", "distanceMeters"}


def test_an_exact_name_is_returned_as_the_single_candidate(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place(name="오동도", category="sight"))
    db.commit()
    seed_legacy_place(db, place_name="오동도", category_group_code="AT4")

    response = api(owner).get(f"/api/trips/7/places/{LEGACY_ID}/public-candidates")

    assert [place["sourceId"] for place in response.json()["places"]] == ["126508"]


def test_public_candidates_are_empty_unless_the_row_is_a_legacy_row_with_a_point(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db)
    seed_candidate_places(db)
    seed_legacy_place(db, id=11, place_name="오동도횟집", place_origin="public")   # 새 방식 행
    seed_legacy_place(db, id=12, place_name="오동도횟집", place_origin="custom")
    seed_legacy_place(db, id=13, place_name="오동도횟집", latitude=None, longitude=None)   # 좌표 없는 예전 행
    seed_legacy_place(db, id=14, place_name="오동도횟집", source_provider=None, external_place_id=None)   # 카카오가 아닌 예전 행
    client = api(owner)

    for place_id in (11, 12, 13, 14):
        assert client.get(f"/api/trips/7/places/{place_id}/public-candidates").json() == {"places": []}


def test_public_candidates_need_an_editor_and_a_place_of_the_trip(db: Session, api: Callable[[User], TestClient]) -> None:
    seed_trip(db)
    viewer = seed_viewer(db)
    seed_legacy_place(db)

    assert api(viewer).get(f"/api/trips/7/places/{LEGACY_ID}/public-candidates").status_code == 403
    assert api(make_user(99, "Outsider")).get(f"/api/trips/7/places/{LEGACY_ID}/public-candidates").status_code == 404
    assert api(db.get(User, 1)).get("/api/trips/7/places/999/public-candidates").status_code == 404


def test_public_candidates_never_log_or_store_the_kakao_values(
    db: Session, api: Callable[[User], TestClient], caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _ = seed_trip(db)
    seed_candidate_places(db)
    legacy = seed_legacy_place(db, place_name="오동도횟집바다전망")
    before = row_values(legacy)
    monkeypatch.setattr(trip_service.logger, "handlers", [caplog.handler])   # uvicorn.error 로그도 이 시험에서 보이게(앱이 따로 모아 둔 것을 시험 동안만 caplog 로)
    caplog.set_level(logging.DEBUG)

    response = api(owner).get(f"/api/trips/7/places/{LEGACY_ID}/public-candidates")

    assert response.status_code == 200
    assert [place["sourceId"] for place in response.json()["places"]] == ["T1", "T2"]   # 이 이름을 품은 공공데이터 이름 두 곳
    for value in ("오동도횟집바다전망", "34.7443", "127.7663", "수정동", "place.map.kakao.com/777"):
        assert value not in caplog.text   # 로그에 남기지 않는다
    assert "오동도횟집바다전망" not in response.text   # 응답에도 카카오 값은 없다
    assert row_values(saved_places(db)[0]) == before and revision_of(db) == 1   # 읽기만 한다 - 행도 revision 도 그대로
    assert db.scalar(select(func.count()).select_from(PublicPlace)) == 6   # 공공데이터 표에 카카오 값을 더하지 않는다
```

`backend/tests/test_trip_db_service.py` - 옛 수정 시험의 `meta` 를 `memo` 로 바꾼다(`test_update_trip_place_changes_existing_place`. 응답의 `meta` 는 메모가 보이는 자리라 단언은 그대로다).

`UpdateTripPlaceRequest(expectedRevision=1, time="10:15", label="Updated peak", meta="New memo"),` → `UpdateTripPlaceRequest(expectedRevision=1, time="10:15", label="Updated peak", memo="New memo"),`

- [ ] **2단계: 실패하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_trip_public_places.py tests/test_trip_db_service.py`
기대: FAIL 18개(`18 failed`) - 새 시험 17개(수정 요청이 `publicPlace` · `customPlace` · `memo` 와 중첩 필드 거절을 모르고, 공공데이터 행의 `label` 이 아직 `place_name` 을 덮고, 후보 경로가 없어 404/405)와 옛 `test_update_trip_place_changes_existing_place`. 시간만 바꾸는 시험(`test_a_time_only_patch_leaves_a_legacy_row_untouched`)과 나만의 장소 이름 바꾸기 시험(`test_renaming_a_custom_row_changes_its_name_itself`)은 지금도 통과한다 - 변환하지 않는다 · 나만의 장소는 이름 자체를 바꾼다는 회귀 방지다.

- [ ] **3단계: 구현**

`backend/app/schemas/trip.py`

1. import 에 `PublicPlaceItem` 을 더한다.

전:

```python
from app.schemas.places import PublicPlaceCategory
```

후:

```python
from app.schemas.places import PublicPlaceCategory, PublicPlaceItem
```

2. `UpdateTripPlaceRequest` 를 바꾸고 바로 뒤에 `LegacyPlaceCandidatesResponse` 를 더한다.

전:

```python
class UpdateTripPlaceRequest(BaseModel):
    expectedRevision: int = Field(ge=1)
    time: str | None = None
    label: str | None = Field(default=None, min_length=1, max_length=200)
    meta: str | None = None
```

후:

```python
class UpdateTripPlaceRequest(BaseModel):
    """장소 수정 - 바뀐 필드만 보낸다. label(이름)과 memo(메모)는 사용자가 쓴 값이다. publicPlace · customPlace 는 그 장소로 바꾼다(함께 못 온다).
    예전 카카오 값(meta · address · 좌표 · 분류)은 받지 않는다(422)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expectedRevision: int = Field(ge=1)
    time: str | None = None
    label: str | None = Field(default=None, min_length=1, max_length=100)
    memo: str | None = Field(default=None, max_length=500)
    publicPlace: PublicPlaceRef | None = None
    customPlace: CustomPlaceInput | None = None

    @model_validator(mode="after")
    def validate_one_replacement(self) -> "UpdateTripPlaceRequest":
        if self.publicPlace is not None and self.customPlace is not None:
            raise ValueError("Provide only one of publicPlace or customPlace")
        return self


class LegacyPlaceCandidatesResponse(BaseModel):
    """예전 카카오 행과 겹치는 공공데이터 후보 - 가까운 순 최대 3곳(바로 맞는 곳 포함). 없으면 빈 목록."""

    places: list[PublicPlaceItem]
```

`backend/app/services/trips.py`

1. import - 공공데이터 서비스 모듈(맞춰 보기 · 응답 항목).

전:

```python
from app.services import itinerary_recommendations
from app.services import trip_public_places
```

후:

```python
from app.services import itinerary_recommendations
from app.services import public_places as public_place_service
from app.services import trip_public_places
```

2. `update_trip_place` 의 본문을 바꾸고, 바로 뒤에 `list_legacy_place_candidates` 를 더한다. 공공데이터 조회와 시간 형식 검사는 `_bump_trip_revision_or_conflict` 앞에서 끝낸다.

전:

```python
    place = _find_trip_place(trip, place_id)
    values = payload.model_dump(exclude_unset=True, exclude={"expectedRevision"})

    if "label" in values:
        label = (values["label"] or "").strip()
        if not label:
            raise TripServiceError(422, "Place label is required")
    _bump_trip_revision_or_conflict(db, trip, payload.expectedRevision)

    if "label" in values:
        place.place_name = label
    if "time" in values:
        place.visit_time = _parse_optional_time(values["time"])
    if "meta" in values:
        place.memo = values["meta"].strip() if values["meta"] is not None else None

    db.commit()
    return _refresh_trip_payload(db, trip.id, user)
```

후:

```python
    place = _find_trip_place(trip, place_id)
    values = payload.model_dump(exclude_unset=True, exclude={"expectedRevision"})

    label = None
    if "label" in values:
        label = (values["label"] or "").strip()
        if not label:
            raise TripServiceError(422, "Place label is required")
    visit_time = _parse_optional_time(values["time"]) if "time" in values else None
    replacement = _value_columns(db, payload.publicPlace, payload.customPlace, {})   # 없는 공공데이터 장소는 revision 전에 404
    _bump_trip_revision_or_conflict(db, trip, payload.expectedRevision)

    legacy = trip_public_places.is_legacy_kakao_place(place)
    if replacement is None and legacy and label is not None:
        # 예전 카카오 행은 이름만 고쳐도 나만의 장소로 바뀐다 - 카카오 이름 · 주소 · 좌표 · 분류를 남기지 않는다
        replacement = trip_public_places.custom_place_columns(label, None, None)
    if replacement is not None:
        for column, value in replacement.items():
            setattr(place, column, value)   # 사용자가 붙인 이름(user_label)도 이때 비워진다
        if legacy:
            place.memo = None   # 카카오 '분류 · 주소' 문구. 카카오 ID · place_url · source_provider 는 남긴다
    if label is not None:
        if place.place_origin == "public":
            place.user_label = label   # 공공데이터 장소는 이름을 따로 담는다 - place_name · 주소 · 좌표 · 사진 · 출처는 공공데이터 값 그대로
        else:
            place.place_name = label
    if "time" in values:
        place.visit_time = visit_time
    if "memo" in values:
        place.memo = (values["memo"] or "").strip() or None

    db.commit()
    return _refresh_trip_payload(db, trip.id, user)


def list_legacy_place_candidates(
    db: Session,
    user: User,
    trip_handle: str,
    place_id: int,
) -> list[dict[str, object]]:
    """예전 카카오 행과 겹치는 공공데이터 후보(가까운 순 최대 3곳, 바로 맞는 곳 포함). 저장된 이름 · 좌표 · 분류는 서버 메모리에서
    견주기만 하고 저장 · 로그에 남기지 않는다. 예전 행이 아니거나 이름 · 좌표가 없으면 빈 목록."""

    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    place = _find_trip_place(trip, place_id)
    if (
        not trip_public_places.is_legacy_kakao_place(place)
        or not place.place_name
        or place.latitude is None
        or place.longitude is None
    ):
        return []
    found = public_place_service.match_place(
        db,
        name=place.place_name,
        latitude=float(place.latitude),
        longitude=float(place.longitude),
        category_code=place.category_group_code,
    )
    return [public_place_service.public_place_item(candidate, distance) for candidate, distance in found.places]
```

`backend/app/api/routes/trips.py`

1. import 에 `LegacyPlaceCandidatesResponse` 를 더한다.

전:

```python
    InviteState,
    MoveTripPlaceRequest,
```

후:

```python
    InviteState,
    LegacyPlaceCandidatesResponse,
    MoveTripPlaceRequest,
```

2. 새 경로를 `GET /{trip_id}/recommendations` 바로 앞에 더한다. 라우트는 서비스를 부르고 오류를 옮기기만 한다.

전:

```python
@router.get("/{trip_id}/recommendations", response_model=list[Recommendation])
```

후:

```python
@router.get("/{trip_id}/places/{place_id}/public-candidates", response_model=LegacyPlaceCandidatesResponse)
def list_legacy_place_candidates(
    trip_id: str,
    place_id: int,
    db: Session | None = Depends(get_optional_db),
    current_user: User | None = Depends(get_current_user),
) -> LegacyPlaceCandidatesResponse:
    try:
        places = trip_service.list_legacy_place_candidates(
            _require_db(db),
            _require_user(current_user),
            trip_id,
            place_id,
        )
    except trip_service.TripServiceError as error:
        _raise_trip_error(error)
    return LegacyPlaceCandidatesResponse(places=places)


@router.get("/{trip_id}/recommendations", response_model=list[Recommendation])
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_trip_public_places.py tests/test_trip_db_service.py tests/test_trip_db_routes.py tests/test_trip_auth_edge_cases.py tests/test_public_places.py tests/test_db_schema.py tests/test_admin_service.py`
기대: 모두 PASS(`273 passed`). 구현을 일부러 틀리게 바꿔 보면 시험이 잡는지 한 번 본다 - `update_trip_place` 에서 `if legacy:` 메모 지우기를 빼면, `label` 변환 조건을 빼면, 공공데이터 행의 `label` 을 `place_name` 에 쓰게 하면, 장소를 바꿀 때 `user_label` 을 안 비우면, 공공데이터 조회를 리비전 올리기 뒤로 옮기면, 후보 서비스에서 예전 행 확인을 빼면, 중첩 모델의 `extra="forbid"` 를 빼면 각각 FAIL 이 나야 한다.

---

### Task 5: 추천 · 지역 중심 · 일정 안 검색 고치기, 맞춰 보기 다듬기

두 부분이다. **5-가**는 일정 API 쪽(추천을 공공데이터로 바꾸기, 지역 중심 경로, 일정 안 장소 검색의 500 고치기)이고, **5-나**는 2단계 `match_place` 의 보완 하나(출처별 조회 상자)이다. 부분마다 실패 확인 → 구현 → 통과 확인을 따로 돈다. 5-나는 5-가와 코드가 겹치지 않는다(같은 저장소 파일의 다른 함수만 고친다).

**파일:**
- 5-가 고치기: `backend/app/schemas/trip.py`, `backend/app/repositories/public_places.py`, `backend/app/services/trip_public_places.py`, `backend/app/services/trips.py`, `backend/app/api/routes/trips.py`, `backend/tests/test_trip_public_places.py`, `backend/tests/test_trip_db_service.py`, `backend/tests/test_trip_db_routes.py`
- 5-나 고치기: `backend/app/services/public_places.py`, `backend/app/repositories/public_places.py`, `backend/tests/test_public_places.py`

**인터페이스:**
- 5-가가 내놓는 것:
  - 스키마: `RecommendationSourceType` 에 `"public_place"` 추가, `Recommendation` 에 `publicSource` · `publicSourceId` · `publicCategory` · `photoUrl` · `photoLicense`, 새 `TripAreaCenter(latitude: float | None, longitude: float | None)`.
  - 저장소(`repositories/public_places.py`): `recommended_public_places(db, *, sido, cities, categories, shuffle_key, exclude_keys, exclude_names, limit) -> list[PublicPlace]`, `area_coordinates(db, *, sido, cities) -> list[tuple[float, float]]`.
  - `services/trip_public_places.py`: `area_scope(area) -> tuple[str, tuple[str, ...] | None] | None`, `existing_place_keys(trip)`, `recommendation_item(place, *, suggested_day, region)`, `recommend_public_places(db, *, trip, area, region) -> list[dict]`, `area_center(db, area) -> dict`, 상수 `PUBLIC_CATEGORY_LABELS` · `CATEGORY_GROUPS` · `RECOMMENDATION_LIMIT`(18) · `RECOMMENDATION_GROUPS`.
  - `services/trips.py`: `list_recommendations(db, user, trip_handle)`(시그니처 그대로 - 공공데이터 → 저장 요약), `get_trip_area_center(db, user, trip_handle) -> dict`, `search_places_for_trip` 고침(카카오를 켜 두었는데 설정이 틀리면 500 대신 503 `Place search is unavailable` - 일부러 끈 경우와 카카오 요청 실패는 지금처럼 빈 목록, 접근 확인 뒤 카카오를 부르기 전에 DB 세션을 놓음). 카카오 추천 경로(`_build_external_place_provider` · `_additional_recommendation_items` · `_existing_place_keys` · `_is_duplicate_candidate`)는 쓰는 곳이 없어 지운다. `KakaoItineraryPlaceProvider` 클래스와 점검 스크립트(`smoke_kakao_local_candidates.py` 등)는 그대로 둔다(다음 정리로).
  - `GET /api/trips/{trip_id}/area-center` → `TripAreaCenter`(보기 권한).
- 5-나가 내놓는 것: `public_places_in_box(db, *, south, north, west, east, source: str | None = None)`, `match_place` 의 출처별 상자(`_box`).

#### 5-가. 추천 · 지역 중심 · 일정 안 검색

- [ ] **1단계: 실패하는 시험 쓰기**

`backend/tests/test_trip_public_places.py` - 위쪽 import 와 `db` 도우미를 고친다(`md5()` 는 Postgres 내장이라 SQLite 에는 없다. 연결마다 같은 이름으로 등록해 같은 SQL 을 돌린다).

전:

```python
from __future__ import annotations

import logging
```

후:

```python
from __future__ import annotations

import hashlib
import logging
```

한 줄씩 바꾼다.

- `from sqlalchemy import BigInteger, Integer, create_engine, func, select` → `from sqlalchemy import BigInteger, Integer, create_engine, event, func, select`
- `from app.models import PublicPlace, Trip, TripDay, TripMember, TripPlace, User` → `from app.models import PublicPlace, Recommendation, Trip, TripDay, TripMember, TripPlace, User`

`app.api.dependencies` 와 `app.db.base` import 사이에 한 줄을 끼운다.

전:

```python
from app.api.dependencies import get_current_user
from app.db.base import Base
```

후:

```python
from app.api.dependencies import get_current_user
from app.data.travel_areas import get_travel_area, make_policy_region_area_id
from app.db.base import Base
```

`from app.services.public_places import name_key, ...` 줄 바로 뒤에 두 줄을 더한다.

```python
from app.services.travel_area_catalog import make_administrative_area_id, make_whole_area_id
from app.services.trip_public_places import area_scope
```

`db` 도우미 바로 앞(`@pytest.fixture` 앞)에 `register_md5` 를 더한다.

```python
def register_md5(dbapi_connection, _record) -> None:
    # 추천 순서는 Postgres 내장 md5() 로 정한다. SQLite 에는 없어서 연결마다 같은 이름으로 등록한다
    dbapi_connection.create_function("md5", 1, lambda value: hashlib.md5(str(value).encode()).hexdigest())
```

`db` 도우미에서 엔진을 만든 곳에 연결 이벤트를 건다.

전:

```python
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    try:
```

후:

```python
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", register_md5)
    try:
```

파일 끝에 시험을 더한다.

```python
YEOSU_AREA = "jeonnam-yeosu-suncheon"   # 전남 · 여수, 순천


def set_area(db: Session, area_id: str | None, trip_id: int = 7) -> None:
    db.get(Trip, trip_id).travel_area_id = area_id
    db.commit()


def recommended(db: Session, user: User, trip_handle: str = "7") -> list[dict[str, object]]:
    db.expire_all()   # 시험이 직접 심은 행도 보이게 - 요청마다 새 세션인 운영과 같다
    return trip_service.list_recommendations(db, user, trip_handle) or []


def recommended_ids(db: Session, user: User, trip_handle: str = "7") -> list[str]:
    return [str(item["publicSourceId"]) for item in recommended(db, user, trip_handle)]


AREA_ROWS = (
    ("Y1", "오동도", "전남", "여수"), ("S1", "순천만", "전남", "순천"), ("G1", "광양매화마을", "전남", "광양"),
    ("E1", "서울숲", "서울", "성동"), ("GW", "강원 고성 통일전망대", "강원", "고성"), ("GN", "경남 고성 공룡박물관", "경남", "고성"),
    ("SJ1", "세종호수공원", "세종", "한솔동"), ("SJ2", "조치원역", "세종", "조치원읍"),
    ("JJ1", "협재해변", "제주", "제주"), ("JJ2", "천지연폭포", "제주", "서귀포"),
)


@pytest.mark.parametrize(("area_id", "expected"), [
    (YEOSU_AREA, {"Y1", "S1"}),   # 시도 + 포함 시군
    (make_whole_area_id("전남"), {"Y1", "S1", "G1"}),   # whole: 은 시도 전체
    (make_administrative_area_id("전남", "여수시"), {"Y1"}),
    (make_administrative_area_id("강원", "고성군"), {"GW"}),   # 같은 시군 이름이 두 시도에 있어도 시도와 함께 건다
    (make_administrative_area_id("경남", "고성군"), {"GN"}),
    ("gyeongnam-tongyeong-geoje-goseong", {"GN"}),
    ("sejong-all", {"SJ1", "SJ2"}),   # 세종의 시군 자리는 읍 · 동 이름 - 시도만으로 고른다
    (make_whole_area_id("세종"), {"SJ1", "SJ2"}),
    (make_policy_region_area_id("세종", "세종"), {"SJ1", "SJ2"}),   # 정책에서 온 세종 지역도 시도만으로 고른다
    ("jeju-all", {"JJ1", "JJ2"}),   # 옛 *-all 은 시도 전체
    ("jeju-seogwipo", {"JJ2"}),
    ("not-an-area", set()),
    (None, set()),
])
def test_recommendations_follow_the_trip_area(db: Session, area_id: str | None, expected: set[str]) -> None:
    owner, _ = seed_trip(db, travel_area_id=area_id)
    db.add_all(public_place(source_id, name=name, sido=sido, city=city) for source_id, name, sido, city in AREA_ROWS)
    db.commit()

    assert set(recommended_ids(db, owner)) == expected


def test_area_scope_reads_whole_legacy_whole_sejong_and_city_areas() -> None:
    assert area_scope(get_travel_area(YEOSU_AREA)) == ("전남", ("여수", "순천"))
    assert area_scope(get_travel_area(make_whole_area_id("전남"))) == ("전남", None)
    assert area_scope(get_travel_area("jeju-all")) == ("제주", None)
    assert area_scope(get_travel_area("sejong-all")) == ("세종", None)
    assert area_scope(get_travel_area(make_administrative_area_id("제주", "제주시"))) == ("제주", ("제주",))   # 제주시 하나는 시도 전체가 아니다
    assert area_scope(None) is None


def test_photo_first_then_tourapi_without_photo_then_store_data(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add_all([
        public_place("STORE", source="sangga", name="가게식당", category="food", photo=None),
        public_place("NOPHOTO", name="사진없는식당", category="food", photo=None),
        public_place("PHOTO", name="사진있는식당", category="food"),
    ])
    db.commit()

    assert recommended_ids(db, owner) == ["PHOTO", "NOPHOTO", "STORE"]


def test_order_is_fixed_per_trip_and_follows_md5_of_the_source_id_and_trip_id(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add_all([
        Trip(id=8, owner_id=1, title="두 번째 여행", status="confirmed", revision=1, start_date=date(2026, 11, 1), end_date=date(2026, 11, 1),
             region="여수", travel_area_id=YEOSU_AREA, participant_count=1),
        TripDay(id=3, trip_id=8, day_number=1, date=date(2026, 11, 1)),
    ])
    ids = [f"A{n:02d}" for n in range(12)]
    db.add_all(public_place(source_id, name=f"명소{source_id}") for source_id in ids)
    db.commit()

    def expected(trip_id: int) -> list[str]:
        return sorted(ids, key=lambda source_id: hashlib.md5(f"{source_id}{trip_id}".encode()).hexdigest())

    first = recommended_ids(db, owner, "7")
    assert first == expected(7)
    assert recommended_ids(db, owner, "7") == first   # 다시 불러도 같다
    assert recommended_ids(db, owner, "8") == expected(8) != first   # 일정이 다르면 다르게 섞인다


def test_a_balanced_mix_comes_first_then_the_groups_take_turns(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add_all(
        [public_place(f"S{n:02d}", name=f"명소{n}", category="sight") for n in range(10)]
        + [public_place(f"F{n:02d}", name=f"식당{n}", category="food") for n in range(10)]
        + [public_place(f"H{n:02d}", name=f"숙소{n}", category="stay") for n in range(10)]
    )
    db.commit()

    groups = [str(item["categoryGroup"]) for item in recommended(db, owner)]

    assert groups[:8] == ["attraction"] * 3 + ["food"] * 3 + ["stay"] * 2   # 관광 3 · 음식 3 · 숙박 2 를 먼저
    assert groups[8:] == ["attraction", "food", "stay"] * 3 + ["attraction"]   # 남는 10자리는 세 묶음이 번갈아
    assert len(groups) == 18

    set_area(db, "jeju-seogwipo")
    db.add_all([public_place(f"X{n}", name=f"서귀포명소{n}", sido="제주", city="서귀포") for n in range(5)])
    db.commit()
    assert len(recommended(db, owner)) == 5   # 모자라면 있는 만큼만 - 가짜로 채우지 않는다


def test_places_already_in_the_trip_are_left_out_by_key_and_by_name(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add_all([
        public_place("126508", name="오동도"),   # 같은 공공데이터 장소를 이미 담았다
        public_place("MA01", source="sangga", name="카페 마레 여수점", category="cafe", photo=None),   # 같은 이름의 나만의 장소가 있다
        public_place("T9", name="순천만"),   # 같은 이름의 예전 카카오 행이 있다
        public_place("KEEP", name="향일암"),
    ])
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF))
    patch(db, owner, saved_places(db)[0].id, 2, label="내가 부르는 이름")   # 사용자 이름을 붙여도 같은 공공데이터 장소로 센다(공공데이터 이름 · 출처 열이 그대로다)
    sunk = db.get(PublicPlace, ("tourapi", "126508"))
    sunk.name, sunk.name_key = "오동도 해상공원", name_key("오동도 해상공원")   # 그 뒤 공공데이터 쪽 이름이 바뀌어 이름으로는 못 거르는 경우도 (출처, ID)로 거른다
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=3, customPlace={"name": "카페마레 여수점"}))
    seed_legacy_place(db, place_name="순천만")

    assert recommended_ids(db, owner) == ["KEEP"]


def test_store_arts_and_sports_are_left_out_but_libraries_and_historic_sites_stay(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add_all([
        public_place("GYM", source="sangga", name="동네헬스장", category="leisure", photo=None),
        public_place("LIB", source="sangga", name="여수도서관", category="culture", photo=None),
        public_place("RAFT", name="레포츠체험", category="leisure"),
    ])
    db.commit()

    assert sorted(recommended_ids(db, owner)) == ["LIB", "RAFT"]


def test_without_usable_public_places_the_saved_summary_is_used(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add(Recommendation(user_id=1, trip_id=7, query="trip_create", result=[
        {"label": "attraction", "title": "저장된 요약 장소", "meta": "Day 1", "reason": "일정 생성 시 저장된 추천 요약입니다."},
    ]))
    db.commit()

    empty_table = recommended(db, owner)   # 표가 비었다
    db.add(public_place())
    db.commit()
    with_places = recommended(db, owner)
    set_area(db, None)
    no_area = recommended(db, owner)   # 지역을 못 가린다

    assert [(item["title"], item["sourceType"]) for item in empty_table] == [("저장된 요약 장소", "savedSummary")]
    assert [(item["title"], item["sourceType"]) for item in with_places] == [("오동도", "public_place")]   # 공공데이터가 있으면 요약은 쓰지 않는다
    assert [(item["title"], item["sourceType"]) for item in no_area] == [("저장된 요약 장소", "savedSummary")]


def test_suggested_days_go_round_the_trip_days(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add_all(public_place(f"P{n}", name=f"명소{n}") for n in range(5))
    db.commit()

    assert [item["suggestedDay"] for item in recommended(db, owner)] == [1, 2, 1, 2, 1]


def test_a_public_recommendation_has_the_documented_shape(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add_all([public_place(), public_place("MA01", source="sangga", name="카페마레", category="cafe", photo=None, address=None)])
    db.commit()

    sight, cafe = recommended(db, owner)

    assert sight == {
        "id": "public:tourapi:126508", "label": "오동도", "title": "오동도", "meta": "관광지 · 전남광주통합특별시 여수시 오동도로 222",
        "reason": "여수 일정에 추가로 검토할 만한 공공데이터 장소입니다.", "categoryGroup": "attraction", "categoryCode": None,
        "categoryName": None, "phone": None, "address": "전남광주통합특별시 여수시 오동도로 222", "latitude": 34.7443, "longitude": 127.7663,
        "placeUrl": None, "suggestedDay": 1, "aiReview": None, "sourceProvider": None, "externalPlaceId": None, "sourceType": "public_place",
        "publicSource": "tourapi", "publicSourceId": "126508", "publicCategory": "sight",
        "photoUrl": "https://tong.visitkorea.or.kr/cms/resource/a.jpg", "photoLicense": "Type3",
    }
    assert (cafe["categoryGroup"], cafe["meta"], cafe["address"], cafe["photoUrl"], cafe["publicCategory"]) == ("cafe", "카페", None, None, "cafe")


def test_recommendation_route_answers_with_public_places_and_the_saved_summary(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add(Recommendation(user_id=1, trip_id=7, query="trip_create", result=[{"label": "a", "title": "저장 요약", "meta": "m", "reason": "r"}]))
    db.commit()
    client = api(owner)

    summary = client.get("/api/trips/7/recommendations")
    db.add_all([public_place(), public_place("MA01", source="sangga", name="카페마레", category="cafe", photo=None)])
    db.commit()
    public = client.get("/api/trips/7/recommendations")

    assert [item["sourceType"] for item in summary.json()] == ["savedSummary"]
    assert public.status_code == 200
    assert [(item["sourceType"], item["categoryGroup"], item["publicSource"]) for item in public.json()] == [
        ("public_place", "attraction", "tourapi"), ("public_place", "cafe", "sangga"),
    ]
    assert public.json()[0]["photoLicense"] == "Type3" and public.json()[0]["placeUrl"] is None


def test_area_center_is_the_median_of_the_area_places(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    viewer = seed_viewer(db)
    db.add_all([
        public_place("C1", name="가", lat=34.0, lng=127.0), public_place("C2", name="나", lat=35.0, lng=128.0),
        public_place("C3", name="다", lat=37.0, lng=131.0),   # 멀리 있는 하나가 평균(35.33)을 끌어도 중앙값은 그대로
        public_place("OUT", name="다른지역", sido="서울", city="성동", lat=37.5, lng=127.0),
        public_place("STORE", source="sangga", name="가게", category="food", photo=None, lat=36.9, lng=130.9),   # TourAPI 가 있으면 가게는 보지 않는다
    ])
    db.commit()

    assert api(owner).get("/api/trips/7/area-center").json() == {"latitude": 35.0, "longitude": 128.0}
    assert api(viewer).get("/api/trips/7/area-center").status_code == 200   # 보기 권한이면 된다
    assert api(make_user(99, "Outsider")).get("/api/trips/7/area-center").status_code == 404

    db.add(public_place("C4", name="라", lat=36.0, lng=129.0))
    db.commit()
    assert api(owner).get("/api/trips/7/area-center").json() == {"latitude": 35.5, "longitude": 128.5}   # 짝수 개면 가운데 둘의 평균


def test_area_center_falls_back_to_store_data_and_is_null_without_places(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    client = api(owner)
    assert client.get("/api/trips/7/area-center").json() == {"latitude": None, "longitude": None}   # 표가 비었다

    db.add_all([public_place("S1", source="sangga", name="가게1", category="food", photo=None, lat=34.7, lng=127.7),
                public_place("S2", source="sangga", name="가게2", category="food", photo=None, lat=34.9, lng=127.9)])
    db.commit()
    assert client.get("/api/trips/7/area-center").json() == pytest.approx({"latitude": 34.8, "longitude": 127.8})   # TourAPI 가 없으면 상가정보

    set_area(db, None)
    assert client.get("/api/trips/7/area-center").json() == {"latitude": None, "longitude": None}   # 지역을 못 가린다
```

`backend/tests/test_trip_db_service.py` - 옛 카카오 추천 시험을 걷어내고, 일정 안 검색 고치기 시험을 더한다.

1. import 두 곳.

전:

```python
from datetime import date, datetime, time, timedelta
from decimal import Decimal
```

후:

```python
import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal
```

`from app.services.kakao_local import KakaoLocalPlace` → `from app.services.kakao_local import KakaoLocalConfigurationError, KakaoLocalPlace`

2. `test_search_places_for_trip_maps_kakao_candidates` 의 마지막 단언 줄(`    assert candidates[0]["externalPlaceId"] == "kakao-1"`) 바로 뒤에 시험 셋을 더한다 - 켜 두고 설정이 틀리면 503(로그에 키 이름이 없다), 일부러 끄면 빈 목록, 카카오를 부르기 전에 DB 세션을 놓는다.

```python
def test_search_places_for_trip_answers_503_when_kakao_is_misconfigured(monkeypatch, caplog) -> None:
    def misconfigured():
        raise KakaoLocalConfigurationError("KAKAO_LOCAL_REST_API_KEY is required when KAKAO_LOCAL_ENABLED=true.")

    monkeypatch.setattr(trip_service.trip_repository, "has_trip_access", lambda db, trip_id, user_id: True, raising=False)
    monkeypatch.setattr(trip_service, "build_kakao_local_client", misconfigured)
    monkeypatch.setattr(trip_service.logger, "handlers", [caplog.handler])   # 앱이 uvicorn.error 로그를 따로 모아 둔 것을 시험 동안만 caplog 로
    caplog.set_level(logging.WARNING)

    with pytest.raises(trip_service.TripServiceError) as error:
        trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="성산일출봉")

    assert (error.value.status_code, error.value.detail) == (503, "Place search is unavailable")
    assert "trip_place_search_kakao_misconfigured" in caplog.text
    assert "KAKAO_LOCAL_REST_API_KEY" not in caplog.text   # 키 이름 · 설정 값은 로그에 남기지 않는다


def test_search_places_for_trip_answers_with_an_empty_list_when_kakao_is_switched_off(monkeypatch) -> None:
    monkeypatch.setattr(trip_service.trip_repository, "has_trip_access", lambda db, trip_id, user_id: True, raising=False)
    monkeypatch.setattr(trip_service, "build_kakao_local_client", lambda: None)   # KAKAO_LOCAL_ENABLED=false - 일부러 끈 것은 오류가 아니다

    assert trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="성산일출봉") == []


def test_search_places_for_trip_releases_the_db_session_before_calling_kakao(monkeypatch) -> None:
    events: list[str] = []

    class SpyDb:
        def close(self) -> None:
            events.append("db closed")

    class FakeSearchProvider:
        def search_keyword(self, *, query: str, size: int = 10):
            events.append("kakao called")
            return []

    monkeypatch.setattr(trip_service.trip_repository, "has_trip_access", lambda db, trip_id, user_id: True, raising=False)
    monkeypatch.setattr(trip_service, "build_kakao_local_client", lambda: FakeSearchProvider())

    assert trip_service.search_places_for_trip(SpyDb(), make_user(), trip_handle="7", query="성산일출봉") == []
    assert events == ["db closed", "kakao called"]
```

3. 아래를 지운다. 추천은 이제 카카오 검색이 아니라 공공데이터에서 고르므로 이 시험들이 지킬 대상이 없다(같은 뜻의 시험 - 이미 담은 장소 제외 · 18곳 · 번갈아 채우기 · 일정 날짜 돌려 주기 - 은 새 시험 파일에 다시 썼다).
   - `class FakeRecommendationProvider:` 부터 `test_list_recommendations_excludes_existing_trip_places` 끝까지(도우미 `_recommendation_candidate` 포함).
   - `test_list_recommendations_backfills_to_ten_after_duplicate_filtering`, `test_list_recommendations_filters_duplicates_before_final_ten_slice`, `test_list_recommendations_assigns_suggested_day_round_robin` 세 시험.
   - 남기는 `test_list_recommendations_marks_saved_summary_fallback` 에서는 카카오 제공자 스텁 한 줄을 지운다(이 시험의 일정은 지역이 없어 DB 를 읽지 않고 바로 저장 요약으로 간다).

전:

```python
    monkeypatch.setattr(trip_service, "_build_external_place_provider", lambda: None)
    monkeypatch.setattr(
        trip_service.trip_repository,
        "list_recommendations",
```

후:

```python
    monkeypatch.setattr(
        trip_service.trip_repository,
        "list_recommendations",
```

`backend/tests/test_trip_db_routes.py` - 일정 안 장소 검색이 카카오 설정 오류에 503 으로 답하는 시험을 더한다. import 줄 바로 뒤에 한 줄,

```python
from app.services.kakao_local import KakaoLocalConfigurationError
```

그리고 `test_db_trip_place_search_route_returns_candidates` 의 마지막 단언 줄(`    assert response.json()[0]["externalPlaceId"] == "kakao-1"`) 바로 뒤에 시험을 더한다 - 응답은 503 과 `{"detail": "Place search is unavailable"}` 뿐이고 키 이름이 없다.

```python
def test_db_trip_place_search_route_answers_503_when_kakao_is_misconfigured(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)
    monkeypatch.setattr(trip_service.trip_repository, "has_trip_access", lambda db, trip_id, user_id: True, raising=False)

    def misconfigured():
        raise KakaoLocalConfigurationError("KAKAO_LOCAL_REST_API_KEY is required when KAKAO_LOCAL_ENABLED=true.")

    monkeypatch.setattr(trip_service, "build_kakao_local_client", misconfigured)

    try:
        response = client.get("/api/trips/7/place-search?query=성산일출봉")
    finally:
        clear_overrides()

    assert response.status_code == 503
    assert response.json() == {"detail": "Place search is unavailable"}
    assert "KAKAO" not in response.text   # 키 이름 · 설정 값은 응답에 없다
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_trip_public_places.py`
기대: 수집 오류 1개 - `ImportError: cannot import name 'area_scope' from 'app.services.trip_public_places'`.

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_trip_db_service.py tests/test_trip_db_routes.py`
기대: FAIL 3개(`3 failed`) - 일정 안 검색 시험 셋(설정 오류 503 서비스 · 라우트, 세션 놓기). 설정 오류 시험은 카카오 설정 오류가 잡히지 않고 500 으로 나가는 현재 버그를 그대로 보여 준다. 일부러 끈 경우의 빈 목록 시험은 지금도 통과한다(회귀 방지).

- [ ] **3단계: 구현**

`backend/app/repositories/public_places.py`

1. import 에 쿼리 도구를 더한다.

전:

```python
from sqlalchemy import delete, func, select
```

후:

```python
from sqlalchemy import and_, case, delete, func, not_, select, tuple_
```

2. 파일 끝에 함수 셋을 더한다(`recommended_public_places` 는 한 지역의 한 묶음 후보를 DB 에서 순서대로 18곳까지 가져온다 - 이미 담은 장소와 상가정보 예술·스포츠는 SQL 에서 뺀다). 저장소는 서비스를 가져오지 않으므로 출처 이름은 글자 그대로 쓴다.

```python
def _in_area(statement, *, sido: str, cities: Collection[str] | None):
    """일정 지역(시도 + 시군)의 장소로 거른다. cities 가 None 이면 시도 전체 - 같은 시군 이름이 여러 시도에 있어 시도와 함께 건다(ix_public_places_sido_city)."""

    statement = statement.where(PublicPlace.sido == sido)
    return statement if cities is None else statement.where(PublicPlace.city.in_(sorted(cities)))


def recommended_public_places(
    db: Session,
    *,
    sido: str,
    cities: Collection[str] | None,
    categories: Collection[str],
    shuffle_key: str,
    exclude_keys: Collection[tuple[str, str]],
    exclude_names: Collection[str],
    limit: int,
) -> list[PublicPlace]:
    """추천 후보 - 일정 지역의 이 분류들 가운데 TourAPI 사진 있음 → TourAPI 사진 없음 → 상가정보 순이고, 같은 묶음 안은
    md5(출처 ID + shuffle_key) 순(일정마다 고정된 섞음 - md5 는 Postgres 내장이다). 이미 담은 장소((출처, 출처 ID)와 비교용 이름)와
    상가정보 예술·스포츠(동네 헬스장 · 당구장 같은 시설이 섞인다)는 뺀다. ponytail: 큰 지역은 DB 가 수만 행을 정렬해 18곳만 돌려준다 -
    느려지면 md5 로 섞기 전에 층 순서로 앞 N행만 남긴다."""

    tier = case(
        (and_(PublicPlace.source == "tourapi", PublicPlace.photo_url.is_not(None)), 0),
        (PublicPlace.source == "tourapi", 1),
        else_=2,
    )
    statement = _in_area(select(PublicPlace).where(PublicPlace.category.in_(sorted(categories))), sido=sido, cities=cities)
    statement = statement.where(not_(and_(PublicPlace.source == "sangga", PublicPlace.category == "leisure")))
    if exclude_keys:
        statement = statement.where(tuple_(PublicPlace.source, PublicPlace.source_id).not_in(sorted(exclude_keys)))
    if exclude_names:
        statement = statement.where(PublicPlace.name_key.not_in(sorted(exclude_names)))
    statement = statement.order_by(
        tier, func.md5(PublicPlace.source_id + shuffle_key), PublicPlace.source, PublicPlace.source_id
    ).limit(limit)
    return list(db.scalars(statement))


def area_coordinates(db: Session, *, sido: str, cities: Collection[str] | None) -> list[tuple[float, float]]:
    """일정 지역의 장소 좌표(위도, 경도). TourAPI 장소가 있으면 그 좌표만, 없으면 상가정보 좌표다 - 큰 지역에서 상가정보
    수십만 행을 읽지 않으려는 순서이고, 관광지 중심이 가게 밀집지보다 지도를 열 자리로 알맞다."""

    for source in ("tourapi", "sangga"):
        rows = db.execute(
            _in_area(select(PublicPlace.latitude, PublicPlace.longitude).where(PublicPlace.source == source), sido=sido, cities=cities)
        ).all()
        if rows:
            return [(latitude, longitude) for latitude, longitude in rows]
    return []
```

**미리 정해 둔 되돌림(코드가 아니다):** 추천 질의는 한 묶음의 지역 전체 행을 `md5(...)` 로 정렬해 18곳만 돌려주므로 `whole:경기` 같은 큰 시도에서 느릴 수 있고, 지역 중심은 좌표를 파이썬으로 가져와 중앙값을 낸다. 이 환경에서는 못 쟀다. 통합 계획 과제 13 의 로컬 Postgres 측정이 문턱을 넘으면 다음 둘로 되돌린다 - (1) 묶음마다 `md5` 로 섞기 전에 층(tier) 순서로 앞의 N행(예: 2,000)만 후보로 남긴 뒤 그 안에서 18곳을 고른다(서브쿼리에서 `ORDER BY tier LIMIT N`), (2) 지역 중심은 DB 집계(`percentile_cont(0.5) WITHIN GROUP (ORDER BY ...)`)로 구한다. 둘 다 Postgres 에서만 도는 문법이라 SQLite 시험으로는 못 덮는다 - 적용하게 되면 시험 방법도 그때 정한다. 측정이 문턱 안이면 이 계획의 코드를 그대로 쓴다.

`backend/app/schemas/trip.py`

전:

```python
RecommendationSourceType = Literal["freshCandidate", "savedSummary"]
```

후:

```python
RecommendationSourceType = Literal["freshCandidate", "savedSummary", "public_place"]
```

전:

```python
    sourceType: RecommendationSourceType | None = None


class PlaceSearchCandidate(BaseModel):
```

후:

```python
    sourceType: RecommendationSourceType | None = None
    # sourceType 이 public_place 인 추천(공공데이터 장소) - 담을 때 publicSource + publicSourceId 를 publicPlace 로 보낸다
    publicSource: PublicSource | None = None
    publicSourceId: str | None = None
    publicCategory: PublicPlaceCategory | None = None
    photoUrl: str | None = None
    photoLicense: str | None = None


class TripAreaCenter(BaseModel):
    """일정 지역의 공공데이터 장소 위경도 중앙값 - 위치 찍기 지도가 여기서 연다. 지역을 가리지 못하거나 장소가 없으면 둘 다 null."""

    latitude: float | None = None
    longitude: float | None = None


class PlaceSearchCandidate(BaseModel):
```

`backend/app/services/trip_public_places.py` - import 를 바꾸고 파일 끝에 추천 · 지역 중심 함수를 더한다.

전:

```python
from __future__ import annotations

from app.models import PublicPlace, TripPlace
from app.services.public_places import secure_photo_url
```

후:

```python
from __future__ import annotations

import statistics

from sqlalchemy.orm import Session

from app.data.travel_areas import WHOLE_AREA_ID_PREFIX, TravelArea
from app.models import PublicPlace, Trip, TripPlace
from app.repositories import public_places as public_place_repository
from app.services.public_places import name_key, secure_photo_url
from app.services.travel_area_catalog import _is_legacy_whole_area
```

파일 끝에 더한다.

```python
PUBLIC_CATEGORY_LABELS = {
    "sight": "관광지",
    "culture": "문화시설",
    "leisure": "레포츠",
    "stay": "숙박",
    "shopping": "쇼핑",
    "food": "음식점",
    "cafe": "카페",
}
# 추천 항목의 categoryGroup - 프론트가 시간대(오전 · 점심 · 카페 · 숙소)를 고르는 데 쓴다
CATEGORY_GROUPS = {
    "sight": "attraction",
    "culture": "attraction",
    "leisure": "attraction",
    "shopping": "attraction",
    "food": "food",
    "cafe": "cafe",
    "stay": "stay",
}
# 추천은 최대 18곳이다. 관광 3 · 음식 3 · 숙박 2 를 먼저 채우고, 남는 자리는 세 묶음을 번갈아 채운다
RECOMMENDATION_LIMIT = 18
RECOMMENDATION_GROUPS = (
    (("sight", "culture", "leisure", "shopping"), 3),
    (("food", "cafe"), 3),
    (("stay",), 2),
)
SEJONG = "세종"   # 세종은 시군 자리에 읍 · 면 · 동 이름이 들어 있어 시도만으로 고른다


def area_scope(area: TravelArea | None) -> tuple[str, tuple[str, ...] | None] | None:
    """일정 지역 → (시도, 시군 목록). 시군 목록이 None 이면 시도 전체다. 지역을 가리지 못하면 None.
    whole: · 옛 `*-all` · 세종은 시도만, 그 밖은 시도 + included_cities(같은 시군 이름이 여러 시도에 있으니 시도와 함께)."""

    if area is None:
        return None
    if area.id.startswith(WHOLE_AREA_ID_PREFIX) or _is_legacy_whole_area(area) or area.sido == SEJONG:
        return area.sido, None
    return area.sido, tuple(area.included_cities)


def existing_place_keys(trip: Trip) -> tuple[set[tuple[str, str]], set[str]]:
    """이미 담은 장소 - (공공데이터 출처, 출처 ID)와 비교용 이름. 이름은 예전 카카오 행의 것도 견주기만 한다(저장 · 로그 없음).
    사용자가 붙인 이름(user_label)은 보지 않는다 - 공공데이터 장소는 (출처, ID)로 걸러지고, 나만의 장소는 place_name 이 곧 사용자 이름이다."""

    keys: set[tuple[str, str]] = set()
    names: set[str] = set()
    for trip_day in trip.days:
        for place in trip_day.places:
            if place.public_source and place.public_source_id:
                keys.add((place.public_source, place.public_source_id))
            if key := name_key(place.place_name):
                names.add(key)
    return keys, names


def recommendation_item(place: PublicPlace, *, suggested_day: int, region: str) -> dict[str, object]:
    return {
        "id": f"public:{place.source}:{place.source_id}",
        "label": place.name,
        "title": place.name,
        "meta": " · ".join(part for part in (PUBLIC_CATEGORY_LABELS[place.category], place.address) if part),
        "reason": f"{region} 일정에 추가로 검토할 만한 공공데이터 장소입니다.",
        "categoryGroup": CATEGORY_GROUPS[place.category],
        "categoryCode": None,
        "categoryName": None,
        "phone": None,
        "address": place.address,
        "latitude": place.latitude,
        "longitude": place.longitude,
        "placeUrl": None,
        "suggestedDay": suggested_day,
        "aiReview": None,
        "sourceProvider": None,
        "externalPlaceId": None,
        "sourceType": "public_place",
        "publicSource": place.source,
        "publicSourceId": place.source_id,
        "publicCategory": place.category,
        "photoUrl": secure_photo_url(place.photo_url),
        "photoLicense": place.photo_license,
    }


def recommend_public_places(db: Session, *, trip: Trip, area: TravelArea | None, region: str) -> list[dict[str, object]]:
    """일정 지역의 공공데이터 장소로 추천 항목을 만든다(카카오 검색 없음). 지역을 못 가리거나 고를 장소가 없으면 빈 목록 -
    부르는 쪽이 저장 요약으로 넘어간다. 순서 · 섞음은 recommended_public_places 가 정한다(일정 번호가 섞음의 씨앗)."""

    scope = area_scope(area)
    if scope is None:
        return []
    sido, cities = scope
    keys, names = existing_place_keys(trip)
    pools = [
        public_place_repository.recommended_public_places(
            db, sido=sido, cities=cities, categories=categories, shuffle_key=str(trip.id),
            exclude_keys=keys, exclude_names=names, limit=RECOMMENDATION_LIMIT,
        )
        for categories, _target in RECOMMENDATION_GROUPS
    ]
    picked = [place for pool, (_categories, target) in zip(pools, RECOMMENDATION_GROUPS) for place in pool[:target]]
    leftovers = [pool[target:] for pool, (_categories, target) in zip(pools, RECOMMENDATION_GROUPS)]
    while len(picked) < RECOMMENDATION_LIMIT and any(leftovers):
        for rest in leftovers:
            if rest and len(picked) < RECOMMENDATION_LIMIT:
                picked.append(rest.pop(0))
    day_numbers = sorted(day.day_number for day in trip.days) or [1]
    return [
        recommendation_item(place, suggested_day=day_numbers[index % len(day_numbers)], region=region)
        for index, place in enumerate(picked)
    ]


def area_center(db: Session, area: TravelArea | None) -> dict[str, float | None]:
    """일정 지역 공공데이터 장소 위경도의 중앙값(평균이 아니라 - 먼 외딴 장소 하나가 지도 중심을 끌지 않게)."""

    scope = area_scope(area)
    points = public_place_repository.area_coordinates(db, sido=scope[0], cities=scope[1]) if scope else []
    if not points:
        return {"latitude": None, "longitude": None}
    return {
        "latitude": statistics.median(latitude for latitude, _longitude in points),
        "longitude": statistics.median(longitude for _latitude, longitude in points),
    }
```

`backend/app/services/trips.py`

1. import 에 `KakaoLocalConfigurationError` 를 더한다.

전:

```python
from app.services.kakao_local import KakaoLocalClient, build_kakao_local_client
```

후:

```python
from app.services.kakao_local import KakaoLocalClient, KakaoLocalConfigurationError, build_kakao_local_client
```

2. `_build_external_place_provider` 함수를 지운다(`KakaoItineraryPlaceProvider` 클래스는 남긴다).

```python
def _build_external_place_provider() -> KakaoItineraryPlaceProvider | None:
    if not settings.kakao_local_enabled:
        return None
    try:
        return KakaoItineraryPlaceProvider(KakaoLocalClient(settings_obj=settings))
    except Exception:
        logger.warning("kakao_local_provider_bootstrap_failed", exc_info=True)
        return None
```

3. `_flush` 바로 뒤에 `_release_session` 을 더한다. 시험의 `object()` 같은 가짜 DB 에는 `close` 가 없을 수 있어 `getattr` 로 거른다.

전:

```python
def _flush(db: Session) -> None:
    if hasattr(db, "flush"):
        db.flush()
```

후:

```python
def _flush(db: Session) -> None:
    if hasattr(db, "flush"):
        db.flush()


def _release_session(db: Session) -> None:
    """접근 확인이 끝난 세션을 놓는다 - 카카오를 기다리는 동안(최대 수 초) DB 연결을 쥐고 있으면 몰린 요청이 풀을 말린다(/api/places 와 같은 꼴)."""
    close = getattr(db, "close", None)
    if close is not None:
        close()
```

4. `def _existing_place_keys(trip: Trip)` 부터 `def _place_search_meta(` 앞까지(`_existing_place_keys` · `_is_duplicate_candidate` · `_additional_recommendation_items` · 옛 `list_recommendations`)를 아래 두 함수로 바꾼다.

```python
def list_recommendations(
    db: Session,
    user: User,
    trip_handle: str,
) -> list[dict[str, object]] | None:
    trip = _resolve_trip(db, trip_handle, user)
    if trip is None:
        return None

    # 카카오 검색 대신 공공데이터(public_places)에서 일정 지역으로 고른다. 지역을 못 가리거나 고를 장소가 없으면 저장 요약으로 넘어간다
    public_items = trip_public_places.recommend_public_places(
        db, trip=trip, area=get_travel_area(trip.travel_area_id), region=trip.region or trip.title
    )
    if public_items:
        return public_items

    items: list[dict[str, object]] = []
    for recommendation in trip_repository.list_recommendations(db, trip_id=trip.id, user_id=user.id):
        items.extend(_recommendation_items(recommendation.result))
    return items


def get_trip_area_center(db: Session, user: User, trip_handle: str) -> dict[str, float | None]:
    """일정 지역의 공공데이터 장소 위경도 중앙값 - 위치 찍기 지도가 여기서 연다. 보기 권한이면 된다."""

    trip = _resolve_required_trip(db, trip_handle, user)
    return trip_public_places.area_center(db, get_travel_area(trip.travel_area_id))
```

5. `search_places_for_trip` - 빈 검색어 확인 뒤를 고친다. 켜 두었는데 설정이 틀린 경우(`KakaoLocalConfigurationError`)만 503 이고, 일부러 끈 경우(`None`)와 카카오 요청 실패는 지금처럼 빈 목록이다. 503 의 `detail` 에도 로그에도 키 이름 · 설정 값을 넣지 않는다. 라우트는 그대로다(`_raise_trip_error` 가 서비스 오류의 상태 코드를 그대로 옮긴다).

전:

```python
    trimmed_query = query.strip()
    if not trimmed_query:
        return []
    provider = build_kakao_local_client()
    if provider is None:
        return []
```

후:

```python
    trimmed_query = query.strip()
    if not trimmed_query:
        return []
    _release_session(db)   # 접근 확인이 끝났다 - 카카오를 기다리는 동안 DB 연결을 쥐지 않는다
    try:
        provider = build_kakao_local_client()
    except KakaoLocalConfigurationError:
        # 켜 두었는데 설정이 틀렸다(키 없음 등) - 500 이 아니라 503. 일부러 끈 경우(None)의 빈 목록과 구별한다. 키 · 설정 값은 로그 · 응답에 남기지 않는다
        logger.warning("trip_place_search_kakao_misconfigured")
        raise TripServiceError(503, "Place search is unavailable") from None
    if provider is None:
        return []
```

`backend/app/api/routes/trips.py`

1. import 에 `TripAreaCenter` 를 더한다.

전:

```python
    Trip,
    TripPolicyResponse,
```

후:

```python
    Trip,
    TripAreaCenter,
    TripPolicyResponse,
```

2. 새 경로를 `GET /{trip_id}/place-search` 바로 앞에 더한다.

전:

```python
@router.get("/{trip_id}/place-search", response_model=list[PlaceSearchCandidate])
```

후:

```python
@router.get("/{trip_id}/area-center", response_model=TripAreaCenter)
def get_trip_area_center(
    trip_id: str,
    db: Session | None = Depends(get_optional_db),
    current_user: User | None = Depends(get_current_user),
) -> TripAreaCenter:
    try:
        center = trip_service.get_trip_area_center(_require_db(db), _require_user(current_user), trip_id)
    except trip_service.TripServiceError as error:
        _raise_trip_error(error)
    return TripAreaCenter(**center)


@router.get("/{trip_id}/place-search", response_model=list[PlaceSearchCandidate])
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_trip_public_places.py tests/test_trip_db_service.py tests/test_trip_db_routes.py tests/test_trip_auth_edge_cases.py tests/test_public_places.py tests/test_db_schema.py tests/test_admin_service.py`
기대: 모두 PASS(`298 passed`). 구현을 일부러 틀리게 바꿔 보면 시험이 잡는지도 한 번 본다 - 이미 담은 장소를 (출처, ID)로만/이름으로만 거르기, 사진 먼저 층 빼기, 상가정보 예술·스포츠 빼기를 빼기, 세종 시도만 규칙 빼기, 섞음에서 일정 번호 빼기, 평균으로 바꾸기, 세션 놓기 빼기, 카카오 설정 오류 잡기 빼기, 503 을 빈 목록으로 되돌리기 각각 FAIL 이 나야 한다.

#### 5-나. 맞춰 보기 다듬기(2단계 보완)

전체 적재 실측(2026-10-05, 1,084,369행)에서 나온 한 가지다. 명동 · 종로에서 관광명소(`AT4` · `CT1`)를 맞출 때 1km 상자가 줄 6,300개를 읽어(상가정보 약 5,700줄은 곧 버렸다) 중앙값이 5ms 에서 약 70ms 가 됐다. 1km 상자는 TourAPI 만, 상가정보는 200m 상자만 읽는다. 맞는 곳을 고르는 규칙(반경 · 이름 · 분류)은 2단계 그대로다 - 같은 곳을 TourAPI 와 상가정보가 따로 담은 쌍을 하나로 세는 규칙은 넣지 않는다(이름 · 거리 · 분류가 같다고 같은 곳이라는 증거가 되지는 않는다).

- [ ] **1단계: 실패하는 시험 쓰기** - `backend/tests/test_public_places.py`

import 에 지구 반경 상수를 더한다(상자 · 거리 시험이 같은 값을 쓰게).

전:

```python
from app.services.public_places import (
    WIDE_RADIUS_M,
```

후:

```python
from app.services.public_places import (
    METERS_PER_DEGREE,
    WIDE_RADIUS_M,
```

2단계에서 쓴 `test_the_same_name_in_both_sources_asks_instead_of_guessing` 을 포함해 기존 시험은 하나도 고치지 않는다. 파일 끝에 더한다.

```python
def north_of(latitude: float, meters: float) -> float:
    return latitude + meters / METERS_PER_DEGREE


def test_dense_area_matching_reads_only_a_200m_box_of_stores(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str | None, float, list[str]]] = []
    real = public_places.public_places_in_box

    def spy(session: Session, **kwargs):
        rows = real(session, **kwargs)
        calls.append((kwargs.get("source"), kwargs["north"] - kwargs["south"], [row.source_id for row in rows]))
        return rows

    monkeypatch.setattr(public_places, "public_places_in_box", spy)
    seed(db, place_row("sangga", "S300", "향일암", north_of(34.7443, 300), 127.7663, "leisure"),
         place_row("tourapi", "T900", "향일암", north_of(34.7443, 900), 127.7663, "sight"))

    found = match_place(db, name="향일암", latitude=34.7443, longitude=127.7663, category_code="AT4")

    assert found.result == "match" and [place.source_id for place, _ in found.places] == ["T900"]   # 900m 떨어진 TourAPI 장소는 맞는다
    assert [(source, ids) for source, _span, ids in calls] == [("tourapi", ["T900"]), ("sangga", [])]   # 가게 300m 는 읽지도 않았다
    assert calls[1][1] < calls[0][1] / 4   # 가게 상자(약 400m)는 TourAPI 상자(약 2km)보다 훨씬 좁다
    calls.clear()
    match_place(db, name="향일암", latitude=34.7443, longitude=127.7663, category_code="FD6")
    assert [source for source, _span, _ids in calls] == [None]   # 넓은 반경이 필요 없으면 200m 상자 한 번


def test_box_query_can_be_limited_to_one_source(db: Session) -> None:
    seed(db, place_row("tourapi", "T", "a"), place_row("sangga", "S", "b"))
    bounds = {"south": 34.74, "north": 34.75, "west": 127.76, "east": 127.77}
    assert {row.source_id for row in public_places_in_box(db, **bounds)} == {"T", "S"}
    assert [row.source_id for row in public_places_in_box(db, **bounds, source="sangga")] == ["S"]
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_public_places.py`
기대: FAIL 2개(`2 failed`) - 출처별 상자 시험(지금은 상자 하나)과 출처 한정 조회 시험(`source` 인자 없음).

- [ ] **3단계: 구현**

`backend/app/repositories/public_places.py` - `public_places_in_box` 에 선택 인자 `source` 를 더한다.

전:

```python
def public_places_in_box(db: Session, *, south: float, north: float, west: float, east: float) -> list[PublicPlace]:
    """위도 · 경도 상자 안의 장소(ix_public_places_lat_lng). 반경 거르기는 서비스가 한다."""

    return list(
        db.scalars(
            select(PublicPlace).where(
                PublicPlace.latitude.between(south, north),
                PublicPlace.longitude.between(west, east),
            )
        )
    )
```

후:

```python
def public_places_in_box(
    db: Session, *, south: float, north: float, west: float, east: float, source: str | None = None
) -> list[PublicPlace]:
    """위도 · 경도 상자 안의 장소(ix_public_places_lat_lng). source 를 주면 그 출처만 - 밀집 지역의 넓은 상자가 가게 줄을
    수천 개 읽지 않게 한다. 반경 거르기는 서비스가 한다."""

    statement = select(PublicPlace).where(
        PublicPlace.latitude.between(south, north),
        PublicPlace.longitude.between(west, east),
    )
    if source is not None:
        statement = statement.where(PublicPlace.source == source)
    return list(db.scalars(statement))
```

`backend/app/services/public_places.py` - 상자 계산을 `_box` 로 빼고, 반경에 따라 출처별로 조회한다.

1. `match_place` 바로 앞에 `_box` 를 더한다.

```python
def _box(latitude: float, longitude: float, radius_m: float) -> dict[str, float]:
    """반경(m)을 덮는 위경도 상자 - 거리 함수와 같은 지구 반경에 여유 1%, 상자 북쪽 끝의 좁은 경도까지 덮는다."""

    dlat = radius_m * BOX_MARGIN / METERS_PER_DEGREE
    dlng = dlat / math.cos(math.radians(latitude + dlat))
    return {"south": latitude - dlat, "north": latitude + dlat, "west": longitude - dlng, "east": longitude + dlng}
```

2. `match_place` 안에서 상자 계산과 조회를 바꾼다.

전:

```python
    tour_radius = WIDE_RADIUS_M if category_code in WIDE_KAKAO_CATEGORIES else NEAR_RADIUS_M
    dlat = max(tour_radius, NEAR_RADIUS_M) * BOX_MARGIN / METERS_PER_DEGREE
    dlng = dlat / math.cos(math.radians(latitude + dlat))   # 상자 북쪽 끝의 좁은 경도까지 덮는다
    near: list[tuple[PublicPlace, float]] = []
    for place in public_places_in_box(
        db, south=latitude - dlat, north=latitude + dlat, west=longitude - dlng, east=longitude + dlng
    ):
        distance = distance_m(latitude, longitude, place.latitude, place.longitude)
        if distance <= (tour_radius if place.source == TOURAPI else NEAR_RADIUS_M):
            near.append((place, distance))
```

후:

```python
    tour_radius = WIDE_RADIUS_M if category_code in WIDE_KAKAO_CATEGORIES else NEAR_RADIUS_M
    if tour_radius > NEAR_RADIUS_M:
        # 넓은 반경(1km)은 TourAPI 만 쓴다. 가게는 200m 상자만 읽는다 - 명동 · 종로에서는 1km 상자가 가게 수천 줄을 읽고 버렸다
        in_boxes = [
            *public_places_in_box(db, **_box(latitude, longitude, tour_radius), source=TOURAPI),
            *public_places_in_box(db, **_box(latitude, longitude, NEAR_RADIUS_M), source=SANGGA),
        ]
    else:
        in_boxes = public_places_in_box(db, **_box(latitude, longitude, NEAR_RADIUS_M))
    near: list[tuple[PublicPlace, float]] = []
    for place in in_boxes:
        distance = distance_m(latitude, longitude, place.latitude, place.longitude)
        if distance <= (tour_radius if place.source == TOURAPI else NEAR_RADIUS_M):
            near.append((place, distance))
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_trip_public_places.py tests/test_trip_db_service.py tests/test_trip_db_routes.py tests/test_trip_auth_edge_cases.py tests/test_public_places.py tests/test_db_schema.py tests/test_admin_service.py`
기대: 모두 PASS(`300 passed`). 2단계의 `test_the_same_name_in_both_sources_asks_instead_of_guessing`(후보 `S1` 다음 `1`), 상자 끝 시험(`test_places_just_inside_the_radius_are_not_lost_at_the_box_edge`)과 반경 시험은 그대로 통과한다. 구현을 일부러 틀리게 바꿔 보면 - 상자를 하나로 되돌리면 FAIL 이 나야 한다.

주의: 출처별 상자는 `POST /api/places/match` 와 과제 4의 후보 경로(`public-candidates`)에 같이 적용된다. 맞는 곳을 고르는 결과는 바뀌지 않는다(읽는 줄만 줄어든다).

---

### Task 6: API 계약 · 골든 · 기능 명세 · 설계 문서

**파일:**
- 만들기: `backend/tests/test_places_contract_docs.py`
- 고치기: `docs/mvp-api-contract.md`, `.agent/evals/api-contract-golden.json`, `docs/implemented-feature-spec.md`, `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`

**인터페이스:**
- 받는 것: 과제 3~5의 요청 · 응답 모양(중첩 요청의 422, 사용자 이름 `user_label`, 일정 안 검색의 503)과 5-나의 출처별 조회 상자.
- 내놓는 것: 계약의 장소 추가 · 묶음 · 수정 절, 새 경로 두 절(`public-candidates` · `area-center`), 일정 안 검색 · 추천 · 맞춰 보기 절의 갱신, `ItineraryPlace` 표의 새 필드 8개(`memo` 포함)와 `label` 행의 설명. 골든의 `days` 모양(세 항목)과 `places` 추가 · 묶음 · 수정 · 검색 · 맞춰 보기 · 추천 항목의 갱신, 새 경로 항목 둘. 기능 명세 한 행 갱신 + 한 행 추가, 설계 문서 문장 하나. 이 문서들이 코드와 어긋나지 않게 지키는 작은 시험 모음(`test_places_contract_docs.py`).
- 프론트 쪽 표(`frontend/src/api/types.ts` · `dataApi.ts` · `backendApi.ts`)는 프론트 부분이 맡는다. 같은 PR 에서 `docs/implemented-feature-spec.md` 의 '장소 추가/수정/삭제/이동'(61행) · '추천 항목 추가'(72행) 같은 화면 설명 행은 프론트 부분이 화면 흐름에 맞춰 고친다.

- [ ] **1단계: 실패하는 시험 쓰기** - `backend/tests/test_places_contract_docs.py`

계약 · 골든이 코드와 같은 모양을 말하는지 본다(카카오 값을 받지 않는다는 규칙이 문서에서 되살아나지 않게, 그리고 사용자 이름 · 중첩 422 · 검색 503 이 문서에 적혀 있는지). 경로는 FastAPI 의 OpenAPI 에서 읽는다(이 버전은 포함 라우터를 `app.routes` 에 펼치지 않는다).

```python
"""3단계 담는 흐름의 API 계약 · 골든이 코드와 같은 모양을 말하는지 - 카카오 값을 받지 않는다는 규칙이 문서에서 되살아나지 않게 한다."""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = json.loads((ROOT / ".agent/evals/api-contract-golden.json").read_text(encoding="utf-8"))
CONTRACT = (ROOT / "docs/mvp-api-contract.md").read_text(encoding="utf-8")
OLD_KAKAO_FIELDS = {"label", "meta", "address", "latitude", "longitude", "category", "categoryCode", "placeUrl", "sourceProvider", "externalPlaceId"}


def golden(method: str, path: str) -> dict:
    return next(item for item in GOLDEN["endpoints"] if (item["method"], item["path"]) == (method, path))


def section(start: str, end: str) -> str:
    return CONTRACT.split(start)[1].split(end)[0]


def test_golden_place_requests_use_public_or_custom_places_and_no_kakao_fields() -> None:
    requests = [golden("POST", "/api/trips/1/days/1/places")["request"], golden("POST", "/api/trips/1/days/1/places")["customPlaceRequestExample"]]
    requests += golden("POST", "/api/trips/1/days/1/places/batch")["request"]["places"]
    for request in requests:
        assert ("publicPlace" in request) != ("customPlace" in request)
        assert not OLD_KAKAO_FIELDS & set(request)
    update = golden("PATCH", "/api/trips/1/places/2")
    assert {"label", "memo"} <= set(update["request"]) and "meta" not in update["request"]
    assert all(("publicPlace" in item) != ("customPlace" in item) for item in update["replaceRequestExamples"])


def test_the_new_routes_are_in_the_golden_the_contract_and_the_app() -> None:
    served = {(method.upper(), served_path) for served_path, item in app.openapi()["paths"].items() for method in item}
    for golden_path, served_path in (
        ("/api/trips/1/places/2/public-candidates", "/api/trips/{trip_id}/places/{place_id}/public-candidates"),
        ("/api/trips/1/area-center", "/api/trips/{trip_id}/area-center"),
    ):
        golden("GET", golden_path)
        assert ("GET", served_path) in served
        assert f"### GET {served_path.removeprefix('/api')}" in CONTRACT


def test_the_contract_and_golden_describe_the_new_place_fields_and_recommendations() -> None:
    days = golden("GET", "/api/trips")["requiredArrayItemFields"]["days"]
    for field in ("memo", "placeOrigin", "publicSource", "publicSourceId", "publicCategory", "photoUrl", "photoLicense", "needsConfirmation"):
        assert f"| {field} |" in CONTRACT
        assert field in days
    recommendations = golden("GET", "/api/trips/1/recommendations")
    assert "public_place" in recommendations["optionalArrayItemFields"]["sourceType"]
    assert {"publicSource", "publicSourceId", "publicCategory", "photoUrl", "photoLicense"} <= set(recommendations["optionalArrayItemFields"])
    assert "cafe" in recommendations["categoryGroupValues"]
    assert "`public_place`" in CONTRACT


def test_the_place_docs_say_unknown_nested_fields_are_422_and_a_public_row_keeps_its_name_apart() -> None:
    for method, path in (("POST", "/api/trips/1/days/1/places"), ("POST", "/api/trips/1/days/1/places/batch"), ("PATCH", "/api/trips/1/places/2")):
        assert "unknown field" in golden(method, path)["dbModeBehavior"] and "inside publicPlace or customPlace" in golden(method, path)["dbModeBehavior"]
    update = section("### PATCH /trips/{trip_id}/places/{place_id}\n", "### PATCH /trips/{trip_id}/places/{place_id}/move")
    assert "`user_label`" in update and "안의 모르는 필드" in update
    assert "user_label" in golden("PATCH", "/api/trips/1/places/2")["dbModeBehavior"]
    assert "| label | string | 화면에 보이는 장소 이름." in CONTRACT


def test_the_search_docs_say_503_for_a_misconfigured_kakao_and_an_empty_list_for_an_off_one() -> None:
    search = section("### GET /trips/{trip_id}/place-search", "### GET /places/search")
    assert "- 503:" in search and "Place search is unavailable" in search
    behavior = golden("GET", "/api/trips/1/place-search")["dbModeBehavior"]
    assert "503" in behavior and "switched off" in behavior and "not a 500" not in behavior


def test_the_match_docs_describe_the_per_source_lookup_boxes() -> None:
    assert "1km 상자는 TourAPI 만" in section("### POST /places/match", "### GET /trips/{trip_id}/recommendations")
    assert "a 200 m box for store rows" in golden("POST", "/api/places/match")["dbModeBehavior"]
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_places_contract_docs.py`
기대: FAIL 6개(`6 failed`). 골든 요청이 아직 옛 카카오 필드이고, 새 경로 둘이 골든 · 계약에 없고, 새 필드가 표에 없고, 중첩 422 · 사용자 이름 · 검색 503 · 출처별 상자 설명이 없다.

- [ ] **3단계: 구현**

골든은 항목 번호로 찾지 말고 아래 앞뒤 글로 찾는다(새 항목을 끼우면 번호가 밀린다). 계약은 절 제목으로 찾는다.

**`docs/mvp-api-contract.md`**

1. `### POST /trips/{trip_id}/days/{day_number}/places` 절 전체(제목부터 다음 `### POST .../places/batch` 제목 앞까지, 끝의 `---` 포함)를 아래로 바꾼다.

````markdown
### POST /trips/{trip_id}/days/{day_number}/places

일정 특정 day에 장소 추가. owner/editor만 가능. 카카오 운영정책(설계 `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`)에 따라 일정에는 **공공데이터 장소의 값**(`public_places` - TourAPI, 소상공인 상가정보) 또는 **사용자가 직접 쓴 값**만 저장한다. 카카오 로컬 값(장소명 · 주소 · 좌표 · 전화번호 · 분류)은 받지도 저장하지도 않는다 - 예전 필드(`label` · `meta` · `address` · `latitude` · `longitude` · `category` · `categoryCode` · `placeUrl` · `sourceProvider` · `externalPlaceId`)를 보내면 422다. `publicPlace` · `customPlace` 안에도 아래에 적은 필드 밖의 값(`name` · `address` · 좌표 등)을 보내면 422다 - 카카오 값이 그 안에 숨어 들어와 조용히 버려지는 일이 없게 한다. 카카오에서 고른 장소는 장소 ID(`kakaoPlaceId`)만 받아 '카카오맵에서 보기' 링크로 남긴다. 고른 카카오 장소를 공공데이터와 맞춰 보는 것은 `POST /places/match` 다.

**Request** (공공데이터 장소)
```json
{
  "expectedRevision": 1,
  "time": "10:30",
  "publicPlace": { "source": "tourapi", "sourceId": "126508" },
  "kakaoPlaceId": "12345"
}
```

**Request** (나만의 장소)
```json
{
  "expectedRevision": 1,
  "time": "10:30",
  "customPlace": { "name": "우리 아지트", "latitude": 34.75, "longitude": 127.75 },
  "kakaoPlaceId": "12345"
}
```

- `expectedRevision`: 필수, 현재 `Trip.revision` 값. 불일치 시 409.
- `time`: optional, `HH:MM` 형식 또는 빈 문자열. 형식이 틀리면 422.
- `publicPlace` · `customPlace`: 둘 중 정확히 하나(아니면 422).
  - `publicPlace{source, sourceId}`: `source` 는 `tourapi` | `sangga`, `sourceId` 는 1~40자. 서버가 `public_places` 에서 찾아 그 이름 · 주소 · 좌표 · 분류 · 사진 · 사진 저작권 유형을 복사한다(`placeOrigin="public"`). 클라이언트가 보낸 값은 쓰지 않는다. 없는 장소면 404 `Public place not found` - 아무것도 쓰지 않고 `revision` 도 그대로다.
  - `customPlace{name, latitude?, longitude?}`: `name` 은 앞뒤 공백을 뺀 1~100자(빈 이름은 422). `latitude`(33~39) · `longitude`(124~132)는 둘 다 있거나 둘 다 없다(아니면 422) - 사용자가 지도에서 찍은 점이다(`placeOrigin="custom"`, 주소 · 분류는 비운다).
- `kakaoPlaceId`: optional, 숫자 1~20자리. 있으면 `sourceProvider="kakao"`, `externalPlaceId`, `placeUrl`(`https://place.map.kakao.com/{id}`, 서버가 만든다)을 남긴다. 없으면 셋 다 `null`. 클라이언트가 보낸 `placeUrl` 은 받지 않는다.

**Response 200** → `Trip` (전체 일정 반환)

**Errors**
- 403: viewer는 추가 불가
- 404: 일정 없음, day 없음, 또는 `Public place not found`
- 409: 다른 사용자가 먼저 장소를 변경해 revision 불일치
- 422: 예전 카카오 필드, `publicPlace`/`customPlace` 안의 모르는 필드, `publicPlace`/`customPlace` 가 둘 다 있거나 둘 다 없음, 이름 · 위치 · 시간 형식 오류

---
````

2. `### POST /trips/{trip_id}/days/{day_number}/places/batch` 절 전체(다음 `### PATCH /trips/{trip_id}/places/{place_id}` 제목 앞까지)를 바꾼다.

````markdown
### POST /trips/{trip_id}/days/{day_number}/places/batch

한 day 에 장소 여러 곳을 한 번에 담는다. 낙관적 리비전 검사 1회, 증가 1회. owner/editor만 가능. 각 항목은 단일 추가와 같은 모양(`time` · `publicPlace` | `customPlace` · `kakaoPlaceId`)이고 같은 규칙으로 저장한다. 프론트의 장소 추가 시트는 장소를 바구니에 담았다가 이 경로로 한 번에 저장한다.

**Request**
```json
{
  "expectedRevision": 1,
  "places": [
    { "publicPlace": { "source": "tourapi", "sourceId": "126508" }, "kakaoPlaceId": "12345" },
    { "customPlace": { "name": "우리 아지트", "latitude": 34.75, "longitude": 127.75 }, "time": "15:00" },
    { "publicPlace": { "source": "sangga", "sourceId": "MA0101202210A0094848" } }
  ]
}
```

- `expectedRevision`: 필수, 현재 `Trip.revision` 값.
- `places`: 필수, 1~50개. 각 항목은 위 네 필드만 받는다(예전 카카오 필드와 `publicPlace`/`customPlace` 안의 모르는 필드는 422).
- 공공데이터 참조를 모두 `revision` 을 올리기 전에 찾는다. 하나라도 없으면 404 `Public place not found` 이고 아무것도 쓰지 않는다.

**Response 200** → `Trip`

**Errors**
- 403: viewer cannot add
- 404: trip not found, `Trip day not found`, 또는 `Public place not found`
- 409: stale revision
- 422: 단일 추가와 같음, `places` 가 비었거나 50개 초과

---
````

3. `### PATCH /trips/{trip_id}/places/{place_id}` 절 전체(다음 `### PATCH .../move` 제목 앞까지)를 바꾼다.

````markdown
### PATCH /trips/{trip_id}/places/{place_id}

장소 정보 수정. owner/editor만 가능. 모든 필드 optional - 바뀐 필드만 보낸다. 예전 카카오 필드(`meta` 등)는 받지 않는다(422).

**Request**
```json
{
  "expectedRevision": 1,
  "time": "11:00",
  "label": "우리 단골집",
  "memo": "일몰 때 가기"
}
```

- `expectedRevision`: 필수, 현재 `Trip.revision` 값. 불일치 시 409.
- `time`: `HH:MM` 또는 빈 문자열(시간을 지움). 모든 행에 적용한다.
- `label`: 사용자가 쓴 이름, 앞뒤 공백을 뺀 1~100자. 담기는 자리는 행 종류에 따라 다르다.
  - **공공데이터 장소 행**(`placeOrigin="public"`): 사용자 이름을 따로 담는다(`trip_places.user_label`). 공공데이터 이름 · 주소 · 좌표 · 분류 · 사진 · 출처는 그대로 두고, 응답의 `label` 이 이 이름이 된다 - 공공데이터 이름과 사용자 이름이 한 열에 섞이지 않는다.
  - **나만의 장소 행**(`placeOrigin="custom"`): 장소 이름 자체가 바뀐다.
  - **예전 카카오 행**(`needsConfirmation=true`): `label` 만 보내도 나만의 장소(`placeOrigin="custom"`)로 바꾼다 - 이름은 `label`, 주소 · 좌표 · 분류 · 메모는 지운다. `time` 만 바꾸는 요청은 변환하지 않는다.
- `memo`: 사용자 메모, 0~500자(빈 문자열 · `null` 은 지움). 응답의 `ItineraryPlace.memo` 로 그대로 돌아온다. 예전 카카오 행이 아니면 `label` · 장소 바꾸기로 지우지 않는다.
- `publicPlace` | `customPlace`: 그 장소로 바꾼다(함께 보내면 422, 그 안의 모르는 필드도 422 - 예: `publicPlace.latitude`). 공공데이터 장소는 `POST` 와 같이 서버 표에서 값을 복사하고(없으면 404 `Public place not found`, `revision` 그대로), 나만의 장소는 사용자 값을 쓴다. 이름 · 주소 · 좌표 · 분류 · 사진 · 출처 열을 새 값으로 채우고 사용자 이름(`user_label`)은 비운다. 같은 요청에 `label` 이 함께 오면 바뀐 행에 적용한다(공공데이터 장소로 바꾸면서 보낸 `label` 은 그 장소의 사용자 이름이 된다). 예전 카카오 행이면 카카오 '분류 · 주소' 문구인 메모도 지운다.
- 카카오 장소 ID · `placeUrl` · `sourceProvider` 는 어느 경우에도 남긴다.

**Response 200** → `Trip`

**Errors**
- 403: viewer는 수정 불가
- 404: 장소 없음, 또는 `Public place not found`
- 409: 다른 사용자가 먼저 장소를 변경해 revision 불일치
- 422: 예전 필드, `publicPlace`/`customPlace` 안의 모르는 필드, `label`/`memo` 길이 위반, `publicPlace` 와 `customPlace` 동시 전송

---
````

4. `### GET /trips/{trip_id}/place-search` 제목 바로 앞에 새 절 둘을 더한다.

````markdown
### GET /trips/{trip_id}/places/{place_id}/public-candidates

예전 카카오 행(`needsConfirmation=true`)과 겹치는 공공데이터 후보. owner/editor만 가능. 서버가 행에 저장돼 있는 이름 · 좌표 · 카카오 분류로 `POST /places/match` 와 같은 맞춰 보기를 서버 메모리에서 돌려 후보(바로 맞는 곳 포함, 가까운 순 최대 3곳)를 낸다. 저장된 값은 비교에만 쓰고 응답 · 로그 · DB 에 남기지 않는다(응답에는 공공데이터 값만 있다). 예전 행이 아니거나 좌표가 없으면 빈 목록이다. 읽기만 하며 `revision` 을 올리지 않는다. 후보를 고르면 `PATCH /trips/{trip_id}/places/{place_id}` 에 `publicPlace` 로 보낸다.

**Response 200** → `LegacyPlaceCandidatesResponse`
```json
{
  "places": [
    {
      "source": "tourapi",
      "sourceId": "126508",
      "name": "오동도",
      "address": "전남광주통합특별시 여수시 오동도로 222",
      "latitude": 34.7443,
      "longitude": 127.7663,
      "category": "sight",
      "sido": "전남",
      "city": "여수",
      "photoUrl": "https://tong.visitkorea.or.kr/cms/resource/23/3074123_image2_1.jpg",
      "photoLicense": "Type3",
      "distanceMeters": 55
    }
  ]
}
```
- `places` 항목은 `POST /places/match` 의 `PublicPlaceItem` 과 같다.

**Errors**
- 403: viewer
- 404: 일정 없음 · 접근 권한 없음 · 장소 없음

---

### GET /trips/{trip_id}/area-center

일정 지역(`travelAreaId`)의 공공데이터 장소 위경도 중앙값. owner/editor/viewer 모두 볼 수 있다. 장소 직접 적기의 '지도에서 위치 찍기'가 이 점에서 지도를 연다(카카오 좌표로 열지 않는다). 지역은 `whole:`(시도 전체) · 옛 `*-all` · 세종은 시도 단위로, 그 밖은 시도 + 포함 시군으로 가린다(같은 시군 이름이 여러 시도에 있어 시도와 함께). TourAPI 장소가 있으면 그 좌표의 중앙값이고, 없으면 상가정보 좌표의 중앙값이다. 지역을 가리지 못하거나 공공데이터 장소가 없으면 둘 다 `null` 이다(오류 아님).

**Response 200** → `TripAreaCenter`
```json
{ "latitude": 34.7459, "longitude": 127.7371 }
```
- `latitude`, `longitude`: number | null (둘 다 있거나 둘 다 null)

**Errors**
- 404: 일정 없음 또는 접근 권한 없음

---
````

5. 같은 `place-search` 절의 첫 문단을 바꾸고, 오류 목록에 503 을 더한다.

전:

```text
Authenticated trip members (owner/editor/viewer) can search Kakao-registered places for selection in the trip detail add-place sheet. Saving a selected place still uses `POST /trips/{trip_id}/days/{day_number}/places` with `expectedRevision`; this endpoint does not mutate itinerary data.
```

후:

```text
Authenticated trip members (owner/editor/viewer) can search Kakao-registered places in the trip detail add-place sheet. The results are display-only: the server passes them through without storing or logging them. A picked place is not saved as it is - the client matches it against our public places (`POST /places/match`) and saves a `publicPlace` reference or a user-written `customPlace` with `POST /trips/{trip_id}/days/{day_number}/places` (only the Kakao place id is kept, as `kakaoPlaceId`). This endpoint does not mutate itinerary data. If Kakao is switched off (`KAKAO_LOCAL_ENABLED=false`) or the Kakao request fails, the response is an empty array. If Kakao is switched on but misconfigured (for example the REST key is missing), the response is 503 `Place search is unavailable` - the key and the settings are never in the response or the logs. The DB connection is released before Kakao is called.
```

전:

```text
- 422: `query` 누락/길이 위반

### GET /places/search
```

후:

```text
- 422: `query` 누락/길이 위반
- 503: 카카오 로컬을 켜 두었는데 설정이 틀림(예: REST 키 없음). `detail` 은 `Place search is unavailable` 이다. 카카오를 일부러 껐거나 카카오 요청이 실패한 경우는 오류가 아니라 빈 배열이다

### GET /places/search
```

6. `### GET /trips/{trip_id}/recommendations` 절 전체(끝의 `---` 앞까지)를 바꾼다.

````markdown
### GET /trips/{trip_id}/recommendations

추천 장소 후보. 카카오 로컬을 부르지 않고 일정 지역(`travelAreaId`)의 공공데이터 장소(`public_places`)에서 고른다. 지역은 `GET /trips/{trip_id}/area-center` 와 같은 규칙으로 가린다. 순서는 TourAPI 사진 있는 곳 → TourAPI 사진 없는 곳 → 상가정보이고, 같은 묶음 안은 일정마다 고정된 섞음(`md5(출처 ID + 일정 ID)`)이라 같은 일정은 늘 같은 순서로, 다른 일정은 다르게 보인다. 관광(`sight` · `culture` · `leisure` · `shopping`) 3곳 · 음식(`food` · `cafe`) 3곳 · 숙박(`stay`) 2곳을 먼저 채우고 남는 자리는 세 묶음이 번갈아 채워 최대 18곳이다(모자라면 있는 만큼만 - 가짜로 채우지 않는다). 이미 일정에 담은 장소 - (`publicSource`, `publicSourceId`)가 같거나 정규화한 이름이 같은 곳 - 와 상가정보 예술·스포츠(동네 헬스장 · 당구장 같은 시설)는 뺀다. `suggestedDay` 는 일정의 날을 번갈아 준다. 고를 공공데이터 장소가 없으면(표가 비었거나, 지역을 가리지 못하거나, 모두 이미 담았다) `recommendations.result` 의 저장 요약(`sourceType="savedSummary"`)을 읽는다. 새 일정 생성은 저장 요약을 만들지 않는다.

Additional `Recommendation` fields:
- `id`: string | null (공공데이터 추천은 `public:{source}:{sourceId}`)
- `categoryGroup`: `attraction`(`sight` · `culture` · `leisure` · `shopping`) | `food` | `cafe` | `stay` | `other` | null
- `categoryCode` · `categoryName` · `phone` · `placeUrl` · `sourceProvider` · `externalPlaceId`: 공공데이터 추천은 모두 `null` (카카오 값이 없다)
- `address` · `latitude` · `longitude`: 공공데이터 값
- `suggestedDay`: number | null
- `aiReview`: string | null (공공데이터 추천은 `null`)
- `sourceType`: `freshCandidate` | `savedSummary` | `public_place` | null - `public_place` 가 공공데이터 추천이다. `freshCandidate`(카카오 추천)는 이 경로가 더는 만들지 않는다.
- `publicSource`: `tourapi` | `sangga` | null, `publicSourceId`: string | null, `publicCategory`: `sight` · `culture` · `leisure` · `stay` · `shopping` · `food` · `cafe` | null - 담을 때 `publicPlace: { source: publicSource, sourceId: publicSourceId }` 로 보낸다.
- `photoUrl`: string | null (https 주소), `photoLicense`: `Type1` | `Type3` | null (TourAPI 사진만, 공공누리 출처 표시용)

**Response 200** → `Recommendation[]`
```json
[
  {
    "id": "public:tourapi:126508",
    "label": "오동도",
    "title": "오동도",
    "meta": "관광지 · 전남광주통합특별시 여수시 오동도로 222",
    "reason": "여수 일정에 추가로 검토할 만한 공공데이터 장소입니다.",
    "categoryGroup": "attraction",
    "address": "전남광주통합특별시 여수시 오동도로 222",
    "latitude": 34.7443,
    "longitude": 127.7663,
    "suggestedDay": 1,
    "sourceType": "public_place",
    "publicSource": "tourapi",
    "publicSourceId": "126508",
    "publicCategory": "sight",
    "photoUrl": "https://tong.visitkorea.or.kr/cms/resource/23/3074123_image2_1.jpg",
    "photoLicense": "Type3"
  }
]
```

**Errors**
- 404: 일정 없음
````

7. 타입 참조의 `### ItineraryPlace` 표 - `label` 행의 설명을 바꾸고, `externalPlaceId` 행 뒤에 여덟 행과 설명 문단을 더한다.

전:

```markdown
| label | string | 장소명 |
```

후:

```markdown
| label | string | 화면에 보이는 장소 이름. 사용자가 붙인 이름(공공데이터 장소를 `PATCH` 의 `label` 로 고친 이름)이 있으면 그것, 없으면 저장된 이름(공공데이터 장소는 공공데이터 이름, 나만의 장소는 사용자가 쓴 이름) |
```

`externalPlaceId` 행 뒤:

전:

```markdown
| externalPlaceId | string \| null | 외부 장소 ID |

`externalPlaceId` is scoped by `sourceProvider`;
```

후:

```markdown
| externalPlaceId | string \| null | 외부 장소 ID |
| memo | string \| null | 사용자가 쓴 메모(`trip_places.memo` 그대로). `meta` 는 메모가 있으면 메모, 없으면 주소다. 새로 담은 행은 `null` 이고 `PATCH` 의 `memo` 로 채운다. 예전 카카오 행에는 카카오 '분류 · 주소' 문구가 들어 있을 수 있다 |
| placeOrigin | `"public"` \| `"custom"` \| `"needs_review"` \| null | 저장한 값의 출처. `public` = 공공데이터 장소 값, `custom` = 나만의 장소(사용자가 쓴 이름 + 찍은 위치), `needs_review` = 변환 뒤 확인 필요(4단계). `null` = 예전 행 |
| publicSource | `"tourapi"` \| `"sangga"` \| null | `placeOrigin="public"` 일 때 공공데이터 출처 |
| publicSourceId | string \| null | 그 출처의 장소 ID(TourAPI contentid · 상가업소번호) |
| publicCategory | `sight` \| `culture` \| `leisure` \| `stay` \| `shopping` \| `food` \| `cafe` \| null | 공공데이터 장소 분류. 일정 화면이 시간대와 분류 표시에 쓴다 |
| photoUrl | string \| null | 공공데이터 사진 주소(https). TourAPI 장소만 |
| photoLicense | string \| null | 사진 저작권 유형(`Type1` · `Type3`, 공공누리). 출처 표시에 쓴다 |
| needsConfirmation | boolean | 예전 카카오 행(`placeOrigin` 이 `null` 이고 `sourceProvider` 가 `kakao` · `kakao_local`)이면 `true` - 이름 · 주소 · 좌표가 카카오 값이라 이름을 다시 적게 한다 |

3단계부터 새로 담는 행에는 카카오 값이 없다. `label` · `address` · `latitude` · `longitude` 는 공공데이터 값 또는 사용자가 쓴 값이고(나만의 장소는 `address` 가 `null`, 위치를 안 찍었으면 좌표도 `null`), `category` · `categoryCode` 는 `null` 이다. `sourceProvider` 는 카카오 장소를 골랐을 때만 `kakao` 이고 `externalPlaceId` · `placeUrl` 은 '카카오맵에서 보기' 링크용이다.

`externalPlaceId` is scoped by `sourceProvider`;
```

8. `### POST /places/match` 절 - 조회 상자와 https 사진 주소를 반영한다(맞는 곳을 고르는 규칙 설명은 그대로다 - 'TourAPI 와 상가정보에 함께 있어도 둘로 센다'가 계속 맞다).

전:

```text
반경은 카카오 분류가 관광명소 · 문화시설(`AT4` · `CT1`)이면 TourAPI 1km, 그 밖과 상가정보는 200m. 이름은
```

후:

```text
반경은 카카오 분류가 관광명소 · 문화시설(`AT4` · `CT1`)이면 TourAPI 1km, 그 밖과 상가정보는 200m(조회도 그렇게 나눈다 - 1km 상자는 TourAPI 만, 상가정보는 200m 상자만 읽는다). 이름은
```

예시의 사진 주소는 https 로 나간다.

전:

```text
      "photoUrl": "http://tong.visitkorea.or.kr/cms/resource/23/3074123_image2_1.jpg",
      "photoLicense": "Type3",
      "distanceMeters": 0
```

후:

```text
      "photoUrl": "https://tong.visitkorea.or.kr/cms/resource/23/3074123_image2_1.jpg",
      "photoLicense": "Type3",
      "distanceMeters": 0
```

전:

```text
`photoUrl` · `photoLicense`(공공누리 `Type1` · `Type3`)는 TourAPI 만.
```

후:

```text
`photoUrl` · `photoLicense`(공공누리 `Type1` · `Type3`)는 TourAPI 만이고, `photoUrl` 은 https 주소로 내보낸다.
```

**`.agent/evals/api-contract-golden.json`** - 아래 문자열에는 큰따옴표를 넣지 않았다(JSON 이스케이프가 필요 없다). 바꾼 뒤 JSON 으로 읽히는지 4단계에서 확인한다.

1. `days` 모양 문자열 - `GET /api/trips` · `POST /api/trips` · `GET /api/trips/1` 세 곳에 같은 글이 있다. 세 곳 모두 바꾼다.

전:

```json
"days": "object (id:string, time:string, label:string, meta:string, address:string|null, latitude:number|null, longitude:number|null, category:string|null, categoryCode:string|null, placeUrl:string|null, sourceProvider:string|null, externalPlaceId:string|null)",
```

후:

```json
"days": "object ({dayNumber}: array of { id:string, time:string, label:string, meta:string, memo:string|null, address:string|null, latitude:number|null, longitude:number|null, category:string|null, categoryCode:string|null, placeUrl:string|null, sourceProvider:string|null, externalPlaceId:string|null, placeOrigin:string enum(public|custom|needs_review)|null, publicSource:string enum(tourapi|sangga)|null, publicSourceId:string|null, publicCategory:string enum(sight|culture|leisure|stay|shopping|food|cafe)|null, photoUrl:string|null, photoLicense:string|null, needsConfirmation:boolean })",
```

2. `POST /api/trips/1/days/1/places` - `request` 를 바꾸고 `customPlaceRequestExample` 을 더한다.

전:

```json
      "path": "/api/trips/1/days/1/places",
      "status": 200,
      "request": {
        "expectedRevision": 1,
        "time": "10:30",
        "label": "함덕해수욕장",
        "meta": "제주시 조천읍"
      },
```

후:

```json
      "path": "/api/trips/1/days/1/places",
      "status": 200,
      "request": {
        "expectedRevision": 1,
        "time": "10:30",
        "publicPlace": {
          "source": "tourapi",
          "sourceId": "126508"
        },
        "kakaoPlaceId": "12345"
      },
      "customPlaceRequestExample": {
        "expectedRevision": 1,
        "time": "10:30",
        "customPlace": {
          "name": "우리 아지트",
          "latitude": 34.75,
          "longitude": 127.75
        }
      },
```

같은 항목의 `dbModeBehavior`(이 글은 이 항목에만 있다):

전:

```text
"dbModeBehavior": "Requires owner/editor access, atomically compares and increments trips.revision, inserts trip_places, and returns the updated Trip. Viewer access returns 403 Trip edit permission required."
```

후:

```text
"dbModeBehavior": "Requires owner/editor access. The body takes exactly one of publicPlace {source: tourapi|sangga, sourceId} or customPlace {name 1-100 chars after trimming, latitude 33-39 and longitude 124-132 both or neither}, plus optional time (HH:MM or empty) and optional kakaoPlaceId (1-20 digits); any other field (label, meta, address, latitude, longitude, category, categoryCode, placeUrl, sourceProvider, externalPlaceId) returns 422, and so does an unknown field inside publicPlace or customPlace (for example publicPlace.name or customPlace.address). The server never stores Kakao names, addresses, coordinates or categories: a publicPlace row copies name, address, coordinates, category and photo from public_places (placeOrigin=public; 404 Public place not found, without touching the revision, when it does not exist), a customPlace row keeps only the user-written name and the picked point (placeOrigin=custom). kakaoPlaceId becomes sourceProvider=kakao, externalPlaceId and a server-built placeUrl https://place.map.kakao.com/{id}. Atomically compares and increments trips.revision, inserts trip_places, and returns the updated Trip. Viewer access returns 403 Trip edit permission required."
```

3. `POST /api/trips/1/days/1/places/batch` - `request` 의 `places` 와 `dbModeBehavior`.

전:

```json
        "places": [
          {
            "label": "Basket cafe",
            "time": "",
            "meta": "1 Basket road",
            "address": "1 Basket road",
            "latitude": 33.45,
            "longitude": 126.57,
            "category": "Cafe",
            "categoryCode": "CE7",
            "placeUrl": "https://place.map.kakao.com/123",
            "sourceProvider": "kakao",
            "externalPlaceId": "123"
          }
        ]
```

후:

```json
        "places": [
          {
            "publicPlace": {
              "source": "tourapi",
              "sourceId": "126508"
            },
            "kakaoPlaceId": "123"
          },
          {
            "customPlace": {
              "name": "우리 아지트",
              "latitude": 34.75,
              "longitude": 127.75
            },
            "time": "15:00"
          }
        ]
```

전:

```text
"dbModeBehavior": "Requires owner/editor access, atomically compares and increments trips.revision once, appends 1-50 selected search-place candidates to the requested trip day, and returns the updated Trip. Viewer access returns 403 Trip edit permission required."
```

후:

```text
"dbModeBehavior": "Requires owner/editor access. Each of the 1-50 items has the same shape and rules as the single add (exactly one of publicPlace or customPlace, optional time and kakaoPlaceId; old Kakao fields and unknown fields inside publicPlace or customPlace return 422). Every public place reference is looked up before the revision is touched; if any is missing the response is 404 Public place not found and nothing is written. Then atomically compares and increments trips.revision once, appends the places to the requested trip day in order, and returns the updated Trip. Viewer access returns 403 Trip edit permission required."
```

4. `PATCH /api/trips/1/places/2` - `request`, `replaceRequestExamples`, `dbModeBehavior`.

전:

```json
      "path": "/api/trips/1/places/2",
      "status": 200,
      "request": {
        "expectedRevision": 1,
        "time": "11:00",
        "label": "함덕해수욕장",
        "meta": "제주시 조천읍"
      },
```

후:

```json
      "path": "/api/trips/1/places/2",
      "status": 200,
      "request": {
        "expectedRevision": 1,
        "time": "11:00",
        "label": "우리 단골집",
        "memo": "일몰 때 가기"
      },
      "replaceRequestExamples": [
        {"expectedRevision": 1, "publicPlace": {"source": "tourapi", "sourceId": "126508"}},
        {"expectedRevision": 1, "customPlace": {"name": "우리 아지트", "latitude": 34.75, "longitude": 127.75}}
      ],
```

전:

```text
"dbModeBehavior": "Requires owner/editor access, atomically compares and increments trips.revision, updates editable trip_places fields, and returns the updated Trip. Viewer access returns 403 Trip edit permission required."
```

후:

```text
"dbModeBehavior": "Requires owner/editor access; send only the changed fields (old fields such as meta return 422, and so do unknown fields inside publicPlace or customPlace, for example publicPlace.latitude). time applies to every row. label is the user-written name (1-100 chars): on a public-place row (placeOrigin=public) it is stored apart as user_label and the public name, address, coordinates, category, photo and source stay as they are, so the response label shows the user name; on a custom row (placeOrigin=custom) the place name itself changes; a legacy Kakao row (needsConfirmation=true) becomes a custom place when only label is sent (name=label, address, coordinates, category and memo cleared) and a time-only change on a legacy row converts nothing. memo is the user note (0-500 chars, empty or null clears it; it comes back as ItineraryPlace.memo). publicPlace or customPlace (not both, else 422) replaces the place with public_places values (404 Public place not found without touching the revision) or the user-written name and picked point, clears user_label, and a label sent in the same request is then applied to the new row; a legacy Kakao row also loses its Kakao style memo. The Kakao place id, placeUrl and sourceProvider are always kept. Atomically compares and increments trips.revision, and returns the updated Trip. Viewer access returns 403 Trip edit permission required."
```

5. 새 경로 항목 둘을 `GET /api/trips/1/place-search` 항목 바로 앞에 끼운다(`DELETE`/`batch-delete` 항목 다음).

```json
    {
      "method": "GET",
      "path": "/api/trips/1/places/2/public-candidates",
      "status": 200,
      "authRequired": true,
      "requiredFields": {
        "places": "array of { source:string enum(tourapi|sangga), sourceId:string, name:string, address:string|null, latitude:number, longitude:number, category:string enum(sight|culture|leisure|stay|shopping|food|cafe), sido:string|null, city:string|null, photoUrl:string|null, photoLicense:string|null, distanceMeters:number }"
      },
      "dbModeBehavior": "Requires owner/editor access (viewer 403, non-member or unknown trip or place 404). For a legacy Kakao row (placeOrigin null and sourceProvider kakao or kakao_local, so needsConfirmation=true) with stored coordinates, the server runs the same in-memory match as POST /api/places/match with the stored name, coordinates and Kakao category code and returns up to 3 candidates nearest first, a direct match included. The stored values are used only for the comparison and are never logged, stored or returned. Any other row, or a row without coordinates, returns places=[]. Read-only: the trip revision does not change. A candidate is chosen with PATCH /api/trips/{tripId}/places/{placeId} publicPlace."
    },
    {
      "method": "GET",
      "path": "/api/trips/1/area-center",
      "status": 200,
      "authRequired": true,
      "requiredFields": {
        "latitude": "number|null",
        "longitude": "number|null"
      },
      "dbModeBehavior": "Requires trip access (owner/editor/viewer; non-member or unknown trip 404). Returns the median latitude and longitude of the public places (public_places) in the trip travel area; the map-point picker opens there instead of on a Kakao coordinate. Area: whole:{sido}, legacy *-all areas and 세종 use the whole sido; other areas use the sido plus its included cities (the same city name exists in several sidos, so both are matched). TourAPI places are used when the area has any, otherwise store data. Both values are null when the travel area cannot be resolved or has no public places (not an error)."
    },
```

6. `GET /api/trips/1/place-search` 의 `dbModeBehavior`.

전:

```text
"dbModeBehavior": "Authenticated trip members can search Kakao Local places for selection. The endpoint returns candidate metadata only and does not mutate itinerary data; saving still uses POST /api/trips/{tripId}/days/{dayNumber}/places with expectedRevision."
```

후:

```text
"dbModeBehavior": "Authenticated trip members can search Kakao Local places in the add-place sheet. The results are display-only and are never stored or logged; the endpoint does not mutate itinerary data. A picked place is matched against public places (POST /api/places/match) and saved as a publicPlace reference or a user-written customPlace with POST /api/trips/{tripId}/days/{dayNumber}/places (only kakaoPlaceId is kept). If Kakao is switched off or the Kakao request fails, the response is an empty array. If Kakao is switched on but misconfigured (for example the REST key is missing), the response is 503 Place search is unavailable, with no key or setting in the response or the logs. The DB session is released before Kakao is called."
```

7. `POST /api/places/match` 의 `dbModeBehavior` 안에서 문장 둘을 바꾼다(조회 상자 · https). `result=match only when ...` 문장은 그대로 둔다.

전:

```text
Radius: TourAPI 1 km when the Kakao category is AT4/CT1, otherwise 200 m; store data always 200 m.
```

후:

```text
Radius: TourAPI 1 km when the Kakao category is AT4/CT1, otherwise 200 m; store data always 200 m (the lookup is split the same way: a 1 km box for TourAPI rows and a 200 m box for store rows).
```

전:

```text
photoUrl|null, photoLicense|null (TourAPI only), distanceMeters. latitude 33-39
```

후:

```text
photoUrl|null (https), photoLicense|null (TourAPI only), distanceMeters. latitude 33-39
```

8. `GET /api/trips/1/recommendations` - `optionalArrayItemFields` 의 끝, `categoryGroupValues`, `dbModeBehavior`.

전:

```json
        "phone": "string|null",
        "sourceType": "string enum(freshCandidate|savedSummary)|null"
      },
      "dbModeBehavior": "Returns additional place candidates for the trip, excluding places already in the itinerary. Kakao-backed candidates include official Local API map metadata such as categoryName, phone, address, coordinates, and placeUrl when available, and use sourceType=freshCandidate. New trip creation does not seed saved summaries; the current savedSummary row is a development-seed specimen rather than proven production legacy history, and future persistence requires an explicit product contract."
```

후:

```json
        "phone": "string|null",
        "sourceType": "string enum(freshCandidate|savedSummary|public_place)|null",
        "publicSource": "string enum(tourapi|sangga)|null",
        "publicSourceId": "string|null",
        "publicCategory": "string enum(sight|culture|leisure|stay|shopping|food|cafe)|null",
        "photoUrl": "string|null",
        "photoLicense": "string|null"
      },
      "categoryGroupValues": "attraction (sight/culture/leisure/shopping) | food | cafe | stay | other",
      "dbModeBehavior": "Returns up to 18 place candidates from our public places (public_places) in the trip travel area instead of Kakao Local: TourAPI places with a photo first, then TourAPI without a photo, then store data, shuffled stably per trip (md5 of source id and trip id); 3 attraction, 3 food/cafe and 2 stay first, the rest filled by taking turns, fewer when there are not enough. Places already in the itinerary (same publicSource and publicSourceId, or the same normalized name) and store arts-and-sports places are excluded. Items use sourceType=public_place with id public:{source}:{sourceId}, label=title=name, meta=category label and address, the public address and coordinates, publicSource, publicSourceId, publicCategory, photoUrl (https) and photoLicense; Kakao fields (categoryCode, categoryName, phone, placeUrl, sourceProvider, externalPlaceId) are null. The area is whole:{sido}, legacy *-all and 세종 by sido, otherwise the sido plus its included cities. When there is nothing to pick (empty table, unresolved area, everything already added) the stored recommendations.result rows are returned as sourceType=savedSummary. New trip creation does not seed saved summaries."
```

**`docs/implemented-feature-spec.md`**

1. '추천 조회' 행(`| 추천 조회 |` 로 시작)의 해당 구절을 바꾼다.

전:

```text
새 후보는 `sourceType="freshCandidate"`로 내려오며, `sourceType="savedSummary"`는
```

후:

```text
후보는 일정 지역의 공공데이터 장소(`sourceType="public_place"` - 사진 있는 TourAPI 장소 먼저, 이미 담은 장소 제외, 최대 18곳)로 내려오며 카카오 검색을 쓰지 않고, 고를 장소가 없을 때만 `sourceType="savedSummary"`가 나온다. `savedSummary`는
```

2. '공공데이터 장소 기반(화면 없음)' 행의 끝을 바꾸고(조회 상자), 그 아래에 새 행을 더한다.

전:

```text
담는 화면은 3단계(설계: `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`). 서버 적재는 실행할 때마다 승인받는다. | `POST /api/places/match` |
```

후:

```text
담는 화면은 3단계(설계: `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`). 서버 적재는 실행할 때마다 승인받는다. 밀집 지역에서는 1km 상자는 TourAPI 만, 상가정보는 200m 상자만 읽는다. | `POST /api/places/match` |
| 일정 장소 저장 규칙(카카오 값 미저장) | 장소 추가 · 묶음 추가 · 수정 API 는 카카오 장소명 · 주소 · 좌표 · 분류를 받지 않고(422), 공공데이터 장소 참조(`publicPlace`)나 나만의 장소(`customPlace` - 이름과 지도에서 찍은 위치)만 받아 서버가 `trip_places` 를 채운다. 카카오에서 고른 장소는 `kakaoPlaceId` 만 받아 서버가 만든 `place_url` 로 '카카오맵에서 보기' 링크를 남긴다. `publicPlace` · `customPlace` 안에 모르는 필드가 있어도 422 다. 예전 카카오 행은 `needsConfirmation` 으로 알리고, 이름만 고치거나 공공데이터 · 나만의 장소로 바꾸면 카카오 값을 지우고 나만의 장소로 바꾼다(시간만 바꾸면 그대로). 공공데이터 장소의 이름을 고치면 공공데이터 값은 그대로 두고 사용자 이름(`user_label`)을 따로 담으며 화면 이름이 그것이 된다. 일정 안 장소 검색은 카카오 설정이 틀리면 503 이다. `GET /api/trips/{tripId}/places/{placeId}/public-candidates` 는 예전 행과 겹치는 공공데이터 후보를 서버 메모리에서만 견주어 돌려주고, `GET /api/trips/{tripId}/area-center` 는 위치 찍기 지도를 일정 지역에서 열 점을 준다. | `POST /api/trips/{tripId}/days/{dayNumber}/places`, `.../places/batch`, `PATCH /api/trips/{tripId}/places/{placeId}`, `GET .../public-candidates`, `GET .../area-center` |
```

**`docs/superpowers/specs/2026-10-03-public-place-storage-design.md`** - 2절 '장소를 담는 흐름'의 `- 이미 담은 장소의 이름을 ...` 항목 끝에 문장을 더한다.

전:

```text
- 이미 담은 장소의 이름을 사용자가 고치면 사용자 입력으로 저장한다.
```

후:

```text
- 이미 담은 장소의 이름을 사용자가 고치면 사용자 입력으로 저장한다. 공공데이터 장소는 이름을 `trip_places.user_label` 에 따로 담아 공공데이터 이름 · 주소 · 좌표 · 출처를 그대로 두고(이름을 섞어 쓰지 않는다), 화면 이름은 `user_label` 이 있으면 그것이다. 나만의 장소는 이름 자체가 사용자 입력이다.
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_places_contract_docs.py && cd .. && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -c "import json; d = json.load(open('.agent/evals/api-contract-golden.json', encoding='utf-8')); print('golden ok', len(d['endpoints']))"`
기대: `6 passed`, `golden ok 82`(항목 둘이 늘었다). 이어서 `git diff --check -- docs .agent` 가 비어 있다.

- [ ] **5단계: 백엔드 전체 검증**(이 계획의 마지막 점검 - CHECKLIST · 커밋은 통합 계획의 마지막 과제가 맡는다)

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --deselect tests/test_stay_discount_semantics_snapshot.py`
기대: 모두 PASS(`1329 passed, 24 skipped` - 이 계획 적용 전 같은 명령은 `1250 passed, 24 skipped`다).

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m alembic upgrade 0048_public_places:0049_trip_place_public_category --sql > /dev/null && echo SQL_OK`
기대: `SQL_OK`(전체 `upgrade head --sql` 은 위 '알려진 한계'대로 `0044` 에서 멈춘다 - 이 변경과 무관하다).

실행: `git diff --check`
기대: 출력 없음.

실행(바꾸거나 새로 만든 파일이 UTF-8 로 읽히고 U+FFFD 가 없는지): `/c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -c "import pathlib, subprocess; names = subprocess.check_output('git diff --name-only HEAD && git ls-files --others --exclude-standard', shell=True, text=True).split(); print([name for name in names if pathlib.Path(name).is_file() and '\\ufffd' in pathlib.Path(name).read_text(encoding='utf-8')])"`
기대: `[]`(깨진 파일 없음. UTF-8 이 아닌 파일이 있으면 `UnicodeDecodeError` 로 멈춘다).

---

---

## 프론트 담는 화면 공통 사항 (과제 7 ~ 9)

### 이 부분의 범위와 다른 부분과의 경계

프론트엔드 중 **'API 경계'와 '담는 흐름'**(과제 7 ~ 9)이 이 부분이다. 같은 파일(`ItineraryDetailPage.tsx`)을 만지는 다른 부분과 겹치지 않게 선을 긋는다.

- **이 부분이 고치는 곳(추가 경로):** 장소 추가 시트의 검색 → 고르기 → 맞춰 보기 → 바구니 → 저장, `PlaceEditorSheet`의 추가 모드, 지도 미리보기(`PlacePreviewCandidate` · `placePreviewMarker`), 바구니와 검색 보조 함수, `?addPlace=` 받는 쪽의 `openAddPlace` 호출 한 줄(임시).
- **건드리지 않는 곳(다른 부분 과제의 몫):**
  - 수정 · 초안 · 예전 행: `openEditPlace` · `submitPlaceEditor`의 수정 분기 · `updatePlaceForm` · `discardPlaceDraft` · `PlaceSheetDetail`, `utils/draftStorage.ts`, `LegacyPlaceConfirm`.
  - 추천 미리보기: `recommendationPlacePayload`(약 1118) · `previewPlacesFromRecommendations`(약 1326) · `timelinePlaceFromPreviewPlace`(약 1384) · `tripPlaceMutationFromDisplayedPlace`(약 1599) · `commitRecommendationPreview`. 처음 정리 목록은 이 넷도 '카카오 값을 옮기던 함수'로 꼽았지만 추천 미리보기는 지금도 쓰는 코드라, 지우지 않고 추천 부분 과제가 `publicPlace` 참조로 바꾼다. (`commitRecommendationPreview`에서 과제 9가 고치는 것은 시간만 바꾼 기존 장소의 `updateTripPlace` 호출 한 곳뿐이다 - 새 `memo` 타입과 어긋나는 `...currentPlace` 펴기를 `time`만 보내게 줄인다.)
  - 표시(마커 · 시간대 분류 · 장소 카드의 사진 - 공용 `PlacePhoto`는 과제 9가 만들고 과제 11이 가져다 쓴다).
  - 홈 넘김(과제 12): `utils/placeHandoff.ts`(+ 시험), 홈 넘김 시험, e2e 시드 두 곳. 과제 9는 컴파일에 필요한 만큼만 지운다(`tripPlaceFromSearchItem`과 그 시험).
- **과제 10~12가 닻으로 쓰는 이름 - 과제 9가 끝난 뒤의 모양(이름은 그대로, 안쪽이 바뀐 것):**
  - `openAddPlace(initial?: PlacePickInput)` - 옛 `TripPlaceRequest`가 아니라 `pick`에 넘길 카카오 장소 한 곳(`id` · `title` · `latitude` · `longitude` · `categoryCode`)을 받는다. 홈 넘김 효과가 `readPlaceParam`의 결과를 이 모양으로 줄여 넘긴다.
  - `TripPlaceEditDraft = PlaceEditorForm & { placeId: string }` - `PlaceEditorForm`은 옛 `TripPlaceRequest`와 같은 필드의 화면 안 타입이다. `placeForm` · `updatePlaceForm` · `PlaceEditorSheet.form`도 이 타입이다.
  - `recommendationPlacePayload` · `tripPlaceMutationFromDisplayedPlace` - 위에 안내 주석이 붙고 반환 타입 표기만 없다(값은 그대로).
  - `PlaceEditorSheet`에 선택 props `matchPanel` · `hidePreview`가 생겼다. 바구니 줄은 `basketItemTitle` · `basketItemBadge` · `basketItemDetail`로 그린다. 시트는 `error` 가 `STALE_SCREEN_MESSAGE` 일 때 '새로 고침' 단추를 더 그린다(새 prop 없음 - 과제 10 의 수정 저장도 이 단추를 쓴다).
  - 페이지 안 `STALE_SCREEN_MESSAGE` · `isStaleScreenError(error)`(422 이고 응답 `detail` 에 `extra_forbidden` · `missing` 이 있을 때 - 값 오류의 422 는 아니다) - 내보내지 않는다. `PlaceMatchState` 의 `custom` 갈래에는 `pickId` 가 있다.
  - 없어진 이름: `previewFromPayload` · `previewFromRecommendation` · `previewPlaceFromRecommendation` · `tripPlaceMutationFromPreviewPlace` · `placeSearchCandidatePayload` · `previewFromSearchCandidate` · `placeBasketIdRef`(대신 `previewFromSearchResult` · `previewFromBasketItem` · `addToBasket` · `addCustomPlace`가 생겼다).
- **과제 9가 임시로 남기는 것과 지우는 주체:**
  - 화면 안 `PlaceEditorForm`(옛 `TripPlaceRequest`의 값 묶음) - 수정 · 초안 과제가 카카오 값 복사와 함께 줄인다.
  - `recommendationPlacePayload` · `tripPlaceMutationFromDisplayedPlace`의 옛 값 묶음 - 추천 과제.
  - `?addPlace=` 의 JSON(`readPlaceParam`) - 넘김 과제가 `readAddPlaceParam` + `usePlaceById`로 바꾼다. 과제 9는 그 JSON에서 꺼낸 카카오 장소를 `usePlaceMatch.pick`에 넘겨 새 흐름에 태울 뿐이다.
- **런타임 주의:** 과제 9가 끝난 시점에도 수정 저장(PATCH)과 추천 담기는 옛 모양(`meta` · 카카오 필드)을 그대로 보낸다. 3단계 백엔드는 `extra=forbid`라 이 둘은 422가 난다. 수정 · 추천 부분 과제가 끝나기 전에는 이 두 길을 손으로 시험하지 않는다(시험은 `appDataApi` 스파이로 가려져 통과한다).
- **요청 안쪽 객체:** 서버는 `publicPlace` · `customPlace` 안쪽의 모르는 필드도 422 로 거절한다. 그래서 두 객체는 늘 정의된 필드만 직접 만들어 싣는다(`publicPlace` = `source` · `sourceId`, `customPlace` = `name` · `latitude` · `longitude`) - 검색 결과나 공공데이터 항목(`PublicPlaceItem`)을 통째로 펴 넣지 않는다. `basketItemPayload`(과제 8) · `LegacyPlaceConfirm`(과제 10) · `previewAddItem`(과제 11)이 그렇게 만들고, 시험이 키 목록으로 확인한다.

### 사전 준비 · 검증 명령 (과제 7 ~ 12)

- 워크트리(`.superpowers/worktrees/place-add-flow/frontend`)에 `node_modules`가 없으면 먼저 저장소 루트의 것으로 junction을 건다: `cd frontend && cmd /c mklink /J node_modules ..\..\..\..\frontend\node_modules`(워크트리 `frontend`에서 루트 `frontend\node_modules`까지 네 단계 위). 워크트리를 지울 때는 `rmdir node_modules`로 링크부터 끊는다(메모리 '워크트리 삭제가 node_modules junction 을 먹는다').
- **순수 단위 · 컴포넌트 시험**(과제 7 · 8, 과제 9의 부품 시험)은 백엔드 없이 `cd frontend && npx vitest run <파일>`로 돈다.
- **라우트 시험**(`login()` · `renderAppRoute`를 쓰는 `trip-detail.test.tsx` · `trip-place-basket.test.tsx`)은 실제 백엔드가 필요하다(`src/test/README.md`: 공유 개발 백엔드, 파일 병렬 실행 안 함). 아래 중 하나로 돌린다.
  - 로컬 백엔드가 `127.0.0.1:8000`에 떠 있으면 `npx vitest run <파일>`.
  - 아니면 `cd frontend && node scripts/run-backend-command.cjs npx vitest run <파일>` - 로컬 DB(55432)를 띄우고 `alembic upgrade head` · 시드를 적용한 뒤 `8001`에서 백엔드를 켠다. **로컬 DB를 바꾸는 일이라** 백엔드 부분 과제의 로컬 DB 절차(덤프 · 검증 · 지문 게이트)를 먼저 거친다.
- 타입 검사: `cd frontend && npx tsc --noEmit -p .`
- **`tsc` 기대는 과제마다 다르다.** 과제 7은 `TripPlaceRequest`를 `@deprecated`로 남겨 화면이 거의 그대로 컴파일되지만, 요청 타입이 바뀌어 `ItineraryDetailPage.tsx`의 두 함수(`tripPlaceMutationFromPreviewPlace` · `tripPlaceMutationFromDisplayedPlace`)에서 오류가 난다. 과제 8은 새 파일만 더하므로 같다. **과제 9가 끝나면 `tsc`가 0건이어야 한다.**
- 한글 파일은 UTF-8로 유지한다. 줄바꿈이 CRLF인 파일은 편집 도구가 줄바꿈을 그대로 둔다. 끝나면 `npm run test:mojibake`와 `git diff --check`를 돌린다.
- 커밋은 과제마다 하지 않는다(3단계 전체 계획의 마지막 과제에서 검증 뒤 사용자 승인을 받아 한다).

### 시안 v59 표시 규칙 (과제 9 ~ 12)

화면 모양은 이 과제들보다 먼저 만드는 시안 v59가 확정한다. 시안과 다른 문구 · 클래스는 시안을 따른다. 시안에서 온 것은 한 가지 표시로 찾을 수 있게 둔다.

- TSX: 문구 옆에 `{/* 시안 v59 */}` 또는 `/* 시안 v59 */` 주석.
- CSS: 규칙 묶음 위에 `/* 시안 v59: ... */` 주석.
- 모아 찾기: `grep -rn "시안 v59" frontend/src`.
- 시안이 구조까지 바꾸면 데이터 흐름(훅 · 바구니 · 요청 모양)은 그대로 두고 부품 안쪽 마크업만 고친다.

이 부분이 시안에 요청하는 화면(문구 · 클래스 목록은 과제 9 끝의 '시안 v59 대응표'):
- **위치 찍기는 키보드로도 된다:** 지도 가운데 고정 십자선 + 방향키로 지도 옮기기 + `+` · `-` 확대 · 축소 + Enter 또는 '이 위치로'로 고르기, 지도 칸의 초점 표시와 도움말 문구, 지도를 누르면 그 자리가 가운데로 온다. 지도가 멈추면 가운데 위도 · 경도를 화면 읽기 프로그램에 알리고(화면에는 숨김), 가운데가 대한민국 밖이면 '이 위치로'가 꺼지고 안내가 보인다.
- **저장이 요청 모양 오류(422)로 거절됐을 때:** '화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.' 안내와 '새로 고침' 단추(추가 창 · 수정 창 · 예전 행 확인 화면 공통). 값 오류의 422 는 지금의 일반 문구다.
- **이름을 고친 공공데이터 장소:** 일정 카드 · 상세 · 수정 창에 사용자가 쓴 이름이 보이고 사진 · 주소 · 핀은 공공데이터 그대로다(표시는 과제 10 · 11).
- **장소 검색을 쓸 수 없을 때(503):** '장소 검색을 지금 쓸 수 없어요. 직접 적기로 담을 수 있어요.' - '결과 없음'과 다른 상태이고 '찾는 곳이 없어요 · 직접 적기' 입구는 그대로 쓸 수 있다.

---

### Task 7: API 경계 - 타입 · 요청 모양 · 새 메서드

**파일:**
- 고치기: `frontend/src/api/types.ts`, `frontend/src/api/dataApi.ts`, `frontend/src/api/backendApi.ts`
- 고치기: `frontend/src/api/backendApi.test.ts`

**인터페이스:**
- 받는 것: 백엔드 과제 2 ~ 6 이 정한 요청 · 응답(스키마 · 새 경로). 2단계의 `PublicPlaceItem` · `PlaceMatchResult` · `matchPlace`.
- 내놓는 것(`../api`에서 import):
  - 타입 `PublicPlaceRef { source: "tourapi" | "sangga"; sourceId: string }`, `CustomPlaceInput { name: string; latitude?: number | null; longitude?: number | null }`, `TripPlaceAddItem { time?: string | null; publicPlace?: PublicPlaceRef; customPlace?: CustomPlaceInput; kakaoPlaceId?: string | null }`, `TripAreaCenter { latitude: number | null; longitude: number | null }`, `LegacyPlaceCandidatesResponse { places: PublicPlaceItem[] }`.
  - `ItineraryPlace` 새 필드(모두 optional): `placeOrigin` · `publicSource` · `publicSourceId` · `publicCategory` · `photoUrl` · `photoLicense` · `needsConfirmation` · `memo`(사용자가 쓴 메모 그대로 - `meta`와 따로 온다). `Recommendation` 새 필드: `publicSource` · `publicSourceId` · `publicCategory` · `photoUrl` · `photoLicense`. `RecommendationSourceType`에 `"public_place"`, `RecommendationCategoryGroup`에 `"cafe"`.
  - 요청 타입 `TripPlaceMutationRequest = TripPlaceAddItem & { expectedRevision: number }`, `TripPlacesBatchRequest { expectedRevision; places: TripPlaceAddItem[] }`, `TripPlaceUpdateRequest { expectedRevision; time?; label?; memo?; publicPlace?; customPlace? }`.
  - `AppDataApi.getTripAreaCenter(tripId): Promise<TripAreaCenter>`, `AppDataApi.listLegacyPlaceCandidates(tripId, placeId): Promise<PublicPlaceItem[]>`(응답의 `places`만 벗겨 돌려준다).
- 호환: `TripPlaceRequest`(옛 카카오 값 묶음)는 `@deprecated` 주석을 달고 **남긴다**. 화면(`ItineraryDetailPage`)이 수정 폼과 추천 미리보기에서 아직 타입으로 쓰고, 지금 지우면 다른 부분 과제가 끝날 때까지 `tsc`가 붉다. 과제 9가 화면 안으로 옮기고 여기서 지운다. 이 타입은 어떤 `AppDataApi` 메서드의 인자에도 쓰이지 않는다.

- [ ] **1단계: 실패하는 시험 쓰기** - `frontend/src/api/backendApi.test.ts`

묶음 추가 시험을 새 모양으로 바꾸고, 단일 추가 · 수정 · 지역 중심 · 예전 행 후보 · 타입 시험을 더한다.

**고치기 `frontend/src/api/backendApi.test.ts`**

찾기:

```ts
import { apiConfig, setApiAccessToken } from "./client";
```

바꾸기:

```ts
import { apiConfig, setApiAccessToken } from "./client";
import type { PublicPlaceItem, TripPlaceAddItem } from "./types";
```

찾기:

```ts
  it("posts multiple places through the batch endpoint", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(tripResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);

    await expect(
      backendApi.addTripPlaces("7", 2, {
        expectedRevision: 4,
        places: [
          {
            time: "",
            label: "Cafe stop",
            meta: "Dessert",
            sourceProvider: "kakao",
          },
        ],
      }),
    ).resolves.toMatchObject({ id: "7" });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/days/2/places/batch`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          expectedRevision: 4,
          places: [
            {
              time: "",
              label: "Cafe stop",
              meta: "Dessert",
              sourceProvider: "kakao",
            },
          ],
        }),
      }),
    );
  });
```

바꾸기:

```ts
  it("posts public and custom places through the batch endpoint without Kakao place values", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(tripResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchSpy);
    const places: TripPlaceAddItem[] = [
      { publicPlace: { source: "tourapi", sourceId: "126508" }, kakaoPlaceId: "8193468" },
      { customPlace: { name: "할머니 댁", latitude: 35.1, longitude: 129.03 } },
    ];

    await expect(
      backendApi.addTripPlaces("7", 2, { expectedRevision: 4, places }),
    ).resolves.toMatchObject({ id: "7" });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/days/2/places/batch`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ expectedRevision: 4, places }),
      }),
    );
  });
```

**끝에 더하기 `frontend/src/api/backendApi.test.ts`**

```ts

describe("backendApi place add flow", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setApiAccessToken(null);
  });

  const tripResponse = {
    id: "7",
    title: "담는 흐름 여행",
    status: "draft",
    revision: 5,
    region: "전남",
    travelAreaId: "whole:%EC%A0%84%EB%82%A8",
    dates: "2026.11.01 - 11.02",
    startDate: "2026-11-01",
    endDate: "2026-11-02",
    people: ["Test User"],
    participantCount: 1,
    expectedSaving: "0원",
    linkedPolicies: [],
    recommendedPolicies: [],
    days: { 1: [] },
    currentUserRole: "owner",
  };
  const jsonResponse = (body: unknown) =>
    new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });

  it("posts one custom place with the Kakao place id as a link key only", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse(tripResponse));
    vi.stubGlobal("fetch", fetchSpy);

    await backendApi.addTripPlace("7", 1, {
      expectedRevision: 4,
      customPlace: { name: "숙소 앞 편의점" },
      kakaoPlaceId: "8193468",
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/days/1/places`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          expectedRevision: 4,
          customPlace: { name: "숙소 앞 편의점" },
          kakaoPlaceId: "8193468",
        }),
      }),
    );
  });

  it("patches a place with only the changed fields", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse(tripResponse));
    vi.stubGlobal("fetch", fetchSpy);

    await backendApi.updateTripPlace("7", "31", {
      expectedRevision: 5,
      customPlace: { name: "다시 적은 이름", latitude: 35.1, longitude: 129.03 },
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/places/31`,
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          expectedRevision: 5,
          customPlace: { name: "다시 적은 이름", latitude: 35.1, longitude: 129.03 },
        }),
      }),
    );
  });

  it("reads the trip area center that the map picker opens on", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse({ latitude: 34.76, longitude: 127.66 }));
    vi.stubGlobal("fetch", fetchSpy);

    await expect(backendApi.getTripAreaCenter("7")).resolves.toEqual({ latitude: 34.76, longitude: 127.66 });

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/area-center`,
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("unwraps the public candidates of a legacy Kakao place", async () => {
    const candidate: PublicPlaceItem = {
      source: "sangga",
      sourceId: "MA010120220800000001",
      name: "여수 해물집",
      address: "전남 여수시 중앙로 1",
      latitude: 34.74,
      longitude: 127.74,
      category: "food",
      distanceMeters: 40,
    };
    const fetchSpy = vi.fn().mockResolvedValue(jsonResponse({ places: [candidate] }));
    vi.stubGlobal("fetch", fetchSpy);

    await expect(backendApi.listLegacyPlaceCandidates("7", "31")).resolves.toEqual([candidate]);

    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/trips/7/places/31/public-candidates`,
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("keeps Kakao place values out of the add request type", () => {
    // tsc 가 보는 시험이다 - 카카오 값(이름 · 주소 · 좌표 · 분류)을 싣는 칸은 담기 요청에 없다
    const request: TripPlaceAddItem = {
      customPlace: { name: "직접 적은 곳" },
      // @ts-expect-error label 은 담기 요청에 없다(사용자가 쓴 이름은 customPlace.name)
      label: "카카오가 준 이름",
    };

    expect(Object.keys(request)).toContain("customPlace");
  });
});
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd frontend && npx vitest run src/api/backendApi.test.ts`
기대: FAIL 2개 - `backendApi.getTripAreaCenter is not a function`, `backendApi.listLegacyPlaceCandidates is not a function`. 단일 추가 · 수정 · 묶음 시험은 클라이언트가 본문을 그대로 넘기므로 지금도 통과한다 - 타입 쪽 실패는 아래 `tsc`가 잡는다.

실행: `cd frontend && npx tsc --noEmit -p .`
기대: 오류. `backendApi.test.ts`가 아직 없는 타입 `TripPlaceAddItem` · `PublicPlaceItem`(후자는 이미 있다)의 새 모양과 `getTripAreaCenter` · `listLegacyPlaceCandidates`를 쓴다. 대표 메시지: `Module '"./types"' has no exported member 'TripPlaceAddItem'`, `Property 'getTripAreaCenter' does not exist on type`.

- [ ] **3단계: 구현**

`addTripPlace` · `addTripPlaces` · `updateTripPlace`는 요청 본문을 그대로 보내므로 `backendApi.ts`의 코드는 그대로이고, 새 모양은 `dataApi.ts`의 요청 타입이 정한다(`backendApi.ts`는 새 메서드 둘과 가져오기만 바뀐다).

**고치기 `frontend/src/api/types.ts`**

`ItineraryPlace`에 새 필드를 더한다.

찾기:

```ts
  placeUrl?: string | null;
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
};

export type RecommendationCategoryGroup = "stay" | "food" | "attraction" | "other";
export type RecommendationSourceType = "freshCandidate" | "savedSummary";
```

바꾸기:

```ts
  placeUrl?: string | null;
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
  /** 3단계: public = 공공데이터 장소 · custom = 나만의 장소 · needs_review = 변환 뒤 확인 필요. 예전 카카오 행은 null */
  placeOrigin?: "public" | "custom" | "needs_review" | null;
  /** 공공데이터 행은 사진 · 주소 · 위치 · 분류가 공공데이터 그대로다. 사용자가 이름을 고쳤으면 `label` 에 그 이름이 온다(서버가 user_label 에 따로 담는다) */
  publicSource?: "tourapi" | "sangga" | null;
  publicSourceId?: string | null;
  publicCategory?: PublicPlaceCategory | null;
  photoUrl?: string | null;
  photoLicense?: string | null;
  /** 예전 카카오 행(place_origin 이 없고 카카오에서 온 행) - 이름을 다시 적어야 한다 */
  needsConfirmation?: boolean;
  /** 사용자가 쓴 메모 그대로. meta 는 표시용 문구라 따로 온다 */
  memo?: string | null;
};

/* cafe 는 공공데이터 추천(public_place)의 분류다 */
export type RecommendationCategoryGroup = "stay" | "food" | "cafe" | "attraction" | "other";
export type RecommendationSourceType = "freshCandidate" | "savedSummary" | "public_place";
```

`Recommendation`에 공공데이터 추천 필드를 더한다.

찾기:

```ts
  aiReview?: string | null;
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
  sourceType?: RecommendationSourceType | null;
};
```

바꾸기:

```ts
  aiReview?: string | null;
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
  sourceType?: RecommendationSourceType | null;
  /** 3단계: sourceType 이 public_place 인 추천에만 - 공공데이터 장소 참조와 사진 */
  publicSource?: "tourapi" | "sangga" | null;
  publicSourceId?: string | null;
  publicCategory?: PublicPlaceCategory | null;
  photoUrl?: string | null;
  photoLicense?: string | null;
};
```

담기 요청 · 지역 중심 · 예전 행 후보 응답 타입을 `PlaceMatchResult` 뒤에 더한다.

찾기:

```ts
export type PlaceMatchResult = {
  result: "match" | "candidates" | "none";
  places: PublicPlaceItem[];
};
```

바꾸기:

```ts
export type PlaceMatchResult = {
  result: "match" | "candidates" | "none";
  places: PublicPlaceItem[];
};

/** 장소 담기 요청의 공공데이터 참조 - 서버가 자기 표(public_places)에서 값을 채운다. 클라이언트가 이름 · 주소 · 좌표를 보내지 않는다 */
export type PublicPlaceRef = {
  source: "tourapi" | "sangga";
  sourceId: string;
};

/** 나만의 장소 - 사용자가 쓴 이름과 지도에서 직접 찍은 위치뿐이다. 위치는 둘 다 있거나 둘 다 없다 */
export type CustomPlaceInput = {
  name: string;
  latitude?: number | null;
  longitude?: number | null;
};

/** 일정에 장소를 담는 한 건(단일 · 묶음 공통). publicPlace 와 customPlace 중 정확히 하나. kakaoPlaceId 는 '카카오맵에서 보기' 링크용 숫자 ID 뿐이다 */
export type TripPlaceAddItem = {
  time?: string | null;
  publicPlace?: PublicPlaceRef;
  customPlace?: CustomPlaceInput;
  kakaoPlaceId?: string | null;
};

/** GET /trips/{id}/area-center - 일정 지역 공공데이터 장소의 위경도 중앙값. 가릴 수 없으면 둘 다 null */
export type TripAreaCenter = {
  latitude: number | null;
  longitude: number | null;
};

/** GET /trips/{id}/places/{placeId}/public-candidates 의 응답. 클라이언트는 places 만 쓴다(listLegacyPlaceCandidates) */
export type LegacyPlaceCandidatesResponse = {
  places: PublicPlaceItem[];
};
```

**고치기 `frontend/src/api/dataApi.ts`**

가져오는 타입을 더한다.

찾기:

```ts
  PlaceMatchRequest,
  PlaceMatchResult,
  Policy,
  Profile,
  ProfileSkipResponse,
```

바꾸기:

```ts
  CustomPlaceInput,
  PlaceMatchRequest,
  PlaceMatchResult,
  Policy,
  Profile,
  ProfileSkipResponse,
  PublicPlaceItem,
  PublicPlaceRef,
```

찾기:

```ts
  TravelAreaRecommendationResponse,
  Trip,
  User,
} from "./types";
```

바꾸기:

```ts
  TravelAreaRecommendationResponse,
  Trip,
  TripAreaCenter,
  TripPlaceAddItem,
  User,
} from "./types";
```

요청 타입을 계약 모양으로 바꾼다. 옛 값 묶음은 `@deprecated`로 남긴다.

찾기:

```ts
export type TripPlaceRequest = {
  time?: string;
  label: string;
  meta?: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  category?: string | null;
  categoryCode?: string | null;
  placeUrl?: string | null;
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
};

export type TripPlaceMutationRequest = TripPlaceRequest & {
  expectedRevision: number;
};

export type TripPlacesBatchRequest = {
  expectedRevision: number;
  places: TripPlaceRequest[];
};
```

바꾸기:

```ts
/** @deprecated 3단계 이전의 카카오 값 묶음. 저장 요청에는 쓰지 않는다(요청은 TripPlaceAddItem). 일정 화면의 수정 폼 · 추천 미리보기가 아직 타입으로 쓰고 있어 과제 9가 화면 안으로 옮기고 이 타입을 지운다 */
export type TripPlaceRequest = {
  time?: string;
  label: string;
  meta?: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  category?: string | null;
  categoryCode?: string | null;
  placeUrl?: string | null;
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
};

/** 장소 추가(단일) - 공공데이터 참조나 나만의 장소 값, 카카오 장소 ID 뿐이다. 카카오가 준 이름 · 주소 · 좌표는 담지 않는다 */
export type TripPlaceMutationRequest = TripPlaceAddItem & {
  expectedRevision: number;
};

/** 장소 추가(묶음, 1~50건) */
export type TripPlacesBatchRequest = {
  expectedRevision: number;
  places: TripPlaceAddItem[];
};
```

찾기:

```ts
export type TripPlaceUpdateRequest = Partial<TripPlaceRequest> & {
  expectedRevision: number;
};
```

바꾸기:

```ts
/** 장소 수정 - 바뀐 필드만 보낸다. label 은 사용자가 쓴 이름, memo 는 사용자 메모. publicPlace 와 customPlace 는 함께 보내지 않는다 */
export type TripPlaceUpdateRequest = {
  expectedRevision: number;
  time?: string | null;
  label?: string;
  memo?: string;
  publicPlace?: PublicPlaceRef;
  customPlace?: CustomPlaceInput;
};
```

`AppDataApi`에 두 메서드를 더한다.

찾기:

```ts
  matchPlace: (request: PlaceMatchRequest) => Promise<PlaceMatchResult>;
  getInviteState: (tripId: string) => Promise<InviteState>;
```

바꾸기:

```ts
  matchPlace: (request: PlaceMatchRequest) => Promise<PlaceMatchResult>;
  /** 일정 지역 공공데이터 장소의 중앙 - 지도에서 위치 찍기가 여는 자리. 가릴 수 없으면 둘 다 null */
  getTripAreaCenter: (tripId: string) => Promise<TripAreaCenter>;
  /** 예전 카카오 행과 겹치는 공공데이터 후보 0~3곳(편집 권한) */
  listLegacyPlaceCandidates: (tripId: string, placeId: string) => Promise<PublicPlaceItem[]>;
  getInviteState: (tripId: string) => Promise<InviteState>;
```

**고치기 `frontend/src/api/backendApi.ts`**

찾기:

```ts
  PlaceMatchRequest,
  PlaceMatchResult,
  Policy,
  Profile,
  ProfileOptions,
  Recommendation,
  RegionRecommendation,
  TravelAreaCatalog,
  TravelAreaRecommendationResponse,
  Trip,
  User,
} from "./types";
```

바꾸기:

```ts
  LegacyPlaceCandidatesResponse,
  PlaceMatchRequest,
  PlaceMatchResult,
  Policy,
  Profile,
  ProfileOptions,
  PublicPlaceItem,
  Recommendation,
  RegionRecommendation,
  TravelAreaCatalog,
  TravelAreaRecommendationResponse,
  Trip,
  TripAreaCenter,
  User,
} from "./types";
```

찾기:

```ts
  matchPlace: (request: PlaceMatchRequest): Promise<PlaceMatchResult> =>
    apiClient.post<PlaceMatchResult>("/api/places/match", request),
```

바꾸기:

```ts
  matchPlace: (request: PlaceMatchRequest): Promise<PlaceMatchResult> =>
    apiClient.post<PlaceMatchResult>("/api/places/match", request),
  getTripAreaCenter: (tripId: string): Promise<TripAreaCenter> =>
    apiClient.get<TripAreaCenter>(`/api/trips/${tripId}/area-center`),
  listLegacyPlaceCandidates: async (tripId: string, placeId: string): Promise<PublicPlaceItem[]> =>
    (await apiClient.get<LegacyPlaceCandidatesResponse>(`/api/trips/${tripId}/places/${placeId}/public-candidates`)).places,
```

추천 담기 시험은 `addTripPlace`로 간 요청의 `label`을 읽는다. 추천 담기는 추천 부분 과제가 바꾸기 전까지 옛 모양으로 가므로 시험은 그대로 두고, 새 요청 타입에 없는 `label`만 타입에서 열어 준다(실행 결과는 그대로).

**고치기 `frontend/src/app/__tests__/trip-detail.test.tsx`**

찾기:

```ts
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockImplementation(async (_tripId, _dayNumber, payload) => {
      if (payload.label === "오설록") return afterFirstSave;
```

바꾸기:

```ts
    // 추천 담기는 아직 옛 모양(label)으로 보낸다 - 추천 부분 과제가 publicPlace 참조로 바꾸면 이 시험도 같이 바뀐다
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockImplementation(async (_tripId, _dayNumber, request) => {
      const payload = request as typeof request & { label?: string };
      if (payload.label === "오설록") return afterFirstSave;
```

찾기:

```ts
      expect(addPlaceSpy.mock.calls.map((call) => call[2].label)).toEqual(["오설록", "한라산", "한라산"]);
```

바꾸기:

```ts
      expect(addPlaceSpy.mock.calls.map((call) => (call[2] as { label?: string }).label)).toEqual(["오설록", "한라산", "한라산"]);
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd frontend && npx vitest run src/api/backendApi.test.ts`
기대: PASS(전부 통과).

실행: `cd frontend && npx tsc --noEmit -p .`
기대: `src/api/`와 시험 파일 오류 0건. 남는 오류는 `ItineraryDetailPage.tsx` 세 곳뿐이다 - 과제 9가 고친다.
- `tripPlaceMutationFromPreviewPlace` · `tripPlaceMutationFromDisplayedPlace`가 반환 타입 `TripPlaceMutationRequest`에 옛 카카오 필드를 싣는다(`Object literal may only specify known properties, and 'label' does not exist in type 'TripPlaceMutationRequest'`) - 두 줄.
- `commitRecommendationPreview`가 `updateTripPlace`에 `ItineraryPlace` 전체를 펴 보낸다(`Argument of type '{ time: string; expectedRevision: number; id?: string; ... }' is not assignable to parameter of type 'TripPlaceUpdateRequest'` - 새 `ItineraryPlace.memo?: string | null`이 요청의 `memo?: string`과 어긋난다).

---

### Task 8: 담는 흐름 모듈 - 바구니 · 맞춰 보기 상태기계 · 공공데이터 문구

**파일:**
- 만들기: `frontend/src/components/itinerary/placeAdd/publicPlaceText.ts`, `publicPlaceText.test.ts`
- 만들기: `frontend/src/components/itinerary/placeAdd/placeBasket.ts`, `placeBasket.test.ts`
- 만들기: `frontend/src/components/itinerary/placeAdd/usePlaceMatch.ts`, `usePlaceMatch.test.ts`

**인터페이스:**
- 받는 것: 과제 7의 `PublicPlaceItem` · `PublicPlaceCategory` · `TripPlaceAddItem` · `PlaceSearchCandidate`, 2단계의 `appDataApi.matchPlace`.
- 내놓는 것:
  - `publicPlaceText.ts`: `PUBLIC_CATEGORY_LABEL: Record<PublicPlaceCategory, string>`, `photoCredit(license: string | null | undefined): string`, `publicTimeSlotGroup(category: PublicPlaceCategory): "attraction" | "food" | "cafe" | "stay"`, 그리고 후보 카드용 `distanceText(meters: number): string`(계약 밖 추가).
  - `placeBasket.ts`: `type PlaceBasketItem`(아래 정의 그대로), `publicBasketItem(place, kakaoPlaceId)`, `customBasketItem(input, kakaoPlaceId)`, `basketItemPayload(item): TripPlaceAddItem`, `basketItemTitle(item): string`, 그리고 바구니 줄 표시용 `basketItemBadge(item)` · `basketItemDetail(item)`(계약 밖 추가).
  - `usePlaceMatch.ts`: `type PlaceMatchState`(아래 정의에 `custom` 갈래의 `pickId: number` 를 더했다 - 나만의 장소 칸을 열 때마다 달라지는 번호), `type PlacePickInput`, `kakaoPlaceIdOf(candidate)`, `usePlaceMatch({ onMatched }) → { state, pick, chooseCandidate, chooseCustom, startDirect, reset }`. `pick(candidate: PlacePickInput): Promise<void>` - 검색 후보(`PlaceSearchCandidate`)가 그대로 맞고, 홈 넘김은 `PlaceSearchItem`에서 `{ id, title: name, latitude, longitude, categoryCode }`를 만들어 넘긴다.
- 규칙: 카카오 이름 · 주소 · 좌표는 `matchPlace` 요청에만 쓰고 훅 상태 · 바구니 · 저장 요청 어디에도 두지 않는다. 훅 상태에 남는 카카오 값은 장소 ID 숫자뿐이다.

- [ ] **1단계: 실패하는 시험 쓰기**

**새 파일 `frontend/src/components/itinerary/placeAdd/publicPlaceText.test.ts`**

```ts
import { describe, expect, it } from "vitest";
import type { PublicPlaceCategory } from "../../../api";
import { PUBLIC_CATEGORY_LABEL, distanceText, photoCredit, publicTimeSlotGroup } from "./publicPlaceText";

describe("공공데이터 장소 문구", () => {
  it("names all seven categories", () => {
    expect(PUBLIC_CATEGORY_LABEL).toEqual({
      sight: "관광지",
      culture: "문화시설",
      leisure: "레포츠",
      stay: "숙박",
      shopping: "쇼핑",
      food: "음식점",
      cafe: "카페",
    });
  });

  it("credits the Korea Tourism Organization and adds the no-change notice for Type3 only", () => {
    expect(photoCredit("Type1")).toBe("사진: 한국관광공사");
    expect(photoCredit(null)).toBe("사진: 한국관광공사");
    expect(photoCredit(undefined)).toBe("사진: 한국관광공사");
    expect(photoCredit("Type3")).toBe("사진: 한국관광공사 · 변경 금지");
  });

  it("groups the categories into the four time-slot groups", () => {
    const expected: Record<PublicPlaceCategory, string> = {
      sight: "attraction",
      culture: "attraction",
      leisure: "attraction",
      shopping: "attraction",
      food: "food",
      cafe: "cafe",
      stay: "stay",
    };
    for (const [category, group] of Object.entries(expected)) {
      expect(publicTimeSlotGroup(category as PublicPlaceCategory)).toBe(group);
    }
  });

  it("says how far a candidate is from the picked place", () => {
    expect(distanceText(0)).toBe("고른 곳과 같은 자리");
    expect(distanceText(120.4)).toBe("고른 곳에서 약 120m");
    expect(distanceText(1250)).toBe("고른 곳에서 약 1.3km");
  });
});
```

**새 파일 `frontend/src/components/itinerary/placeAdd/placeBasket.test.ts`**

```ts
import { describe, expect, it } from "vitest";
import type { PublicPlaceItem } from "../../../api";
import {
  basketItemBadge,
  basketItemDetail,
  basketItemPayload,
  basketItemTitle,
  customBasketItem,
  publicBasketItem,
} from "./placeBasket";

const odongdo: PublicPlaceItem = {
  source: "tourapi",
  sourceId: "126508",
  name: "오동도",
  address: "전남 여수시 오동도로 222",
  latitude: 34.7443,
  longitude: 127.7663,
  category: "sight",
  sido: "전남",
  city: "여수",
  photoUrl: "https://tong.visitkorea.or.kr/cms/resource/23/3074123_image2_1.jpg",
  photoLicense: "Type3",
  distanceMeters: 12,
};

describe("장소 바구니", () => {
  it("sends a public place as a reference plus the Kakao place id, nothing else", () => {
    const item = publicBasketItem(odongdo, "8193468");

    expect(item).toMatchObject({ kind: "public", place: odongdo, kakaoPlaceId: "8193468" });
    expect(basketItemPayload(item)).toEqual({
      publicPlace: { source: "tourapi", sourceId: "126508" },
      kakaoPlaceId: "8193468",
    });
    // 공공데이터 값(이름 · 주소 · 좌표 · 사진)도 보내지 않는다 - 서버가 자기 표에서 채운다
    expect(JSON.stringify(basketItemPayload(item))).not.toContain("오동도");
    expect(JSON.stringify(basketItemPayload(item))).not.toContain("34.74");
  });

  it("fills publicPlace and customPlace with exactly the fields the server defines, because it rejects unknown ones inside them", () => {
    const publicPayload = basketItemPayload(publicBasketItem(odongdo, "8193468"));
    const customPayload = basketItemPayload(
      customBasketItem({ name: "숙소 앞 편의점", latitude: 35.1, longitude: 129.03 }, "123456"),
    );

    expect(Object.keys(publicPayload).sort()).toEqual(["kakaoPlaceId", "publicPlace"]);
    expect(Object.keys(publicPayload.publicPlace ?? {}).sort()).toEqual(["source", "sourceId"]);
    expect(Object.keys(customPayload).sort()).toEqual(["customPlace", "kakaoPlaceId"]);
    expect(Object.keys(customPayload.customPlace ?? {}).sort()).toEqual(["latitude", "longitude", "name"]);
  });

  it("leaves the Kakao place id out when there is none", () => {
    expect(basketItemPayload(publicBasketItem(odongdo, null))).toEqual({
      publicPlace: { source: "tourapi", sourceId: "126508" },
    });
    expect(basketItemPayload(customBasketItem({ name: "할머니 댁" }, null))).toEqual({
      customPlace: { name: "할머니 댁" },
    });
  });

  it("sends a custom place as the typed name and the picked point only", () => {
    const item = customBasketItem({ name: "  숙소 앞 편의점  ", latitude: 35.1, longitude: 129.03 }, "123456");

    expect(item).toMatchObject({
      kind: "custom",
      name: "숙소 앞 편의점",
      latitude: 35.1,
      longitude: 129.03,
      kakaoPlaceId: "123456",
    });
    expect(basketItemPayload(item)).toEqual({
      customPlace: { name: "숙소 앞 편의점", latitude: 35.1, longitude: 129.03 },
      kakaoPlaceId: "123456",
    });
  });

  it("drops half a point so the pair is always both or neither", () => {
    const item = customBasketItem({ name: "반쪽 위치", latitude: 35.1, longitude: null }, null);

    expect(item).toMatchObject({ latitude: null, longitude: null });
    expect(basketItemPayload(item)).toEqual({ customPlace: { name: "반쪽 위치" } });
  });

  it("gives every item its own basket id", () => {
    const first = publicBasketItem(odongdo, null);
    const second = publicBasketItem(odongdo, null);

    expect(first.basketId).not.toBe(second.basketId);
  });

  it("titles each row with public data or the typed name and describes it without Kakao values", () => {
    const publicItem = publicBasketItem(odongdo, "8193468");
    const pinned = customBasketItem({ name: "내 쉼터", latitude: 35.1, longitude: 129.03 }, null);
    const nameOnly = customBasketItem({ name: "내 쉼터" }, null);

    expect(basketItemTitle(publicItem)).toBe("오동도");
    expect(basketItemBadge(publicItem)).toBe("관광지");
    expect(basketItemDetail(publicItem)).toBe("전남 여수시 오동도로 222");
    expect(basketItemDetail(publicBasketItem({ ...odongdo, address: null }, null))).toBe("주소 정보 없음");

    expect(basketItemTitle(pinned)).toBe("내 쉼터");
    expect(basketItemBadge(pinned)).toBe("직접 적은 장소");
    expect(basketItemDetail(pinned)).toBe("지도에서 찍은 위치");
    expect(basketItemDetail(nameOnly)).toBe("위치 없이 이름만");
  });
});
```

**새 파일 `frontend/src/components/itinerary/placeAdd/usePlaceMatch.test.ts`**

```ts
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { appDataApi, type PlaceMatchResult, type PublicPlaceItem } from "../../../api";
import type { PlaceBasketItem } from "./placeBasket";
import { kakaoPlaceIdOf, usePlaceMatch, type PlaceMatchState, type PlacePickInput } from "./usePlaceMatch";

const odongdo: PublicPlaceItem = {
  source: "tourapi",
  sourceId: "126508",
  name: "오동도",
  address: "전남 여수시 오동도로 222",
  latitude: 34.7443,
  longitude: 127.7663,
  category: "sight",
  distanceMeters: 12,
};
const yeosuPark: PublicPlaceItem = {
  source: "sangga",
  sourceId: "MA010120220800000002",
  name: "오동도 공원",
  address: "전남 여수시 수정동 1",
  latitude: 34.745,
  longitude: 127.766,
  category: "sight",
  distanceMeters: 95,
};

function kakaoPick(overrides: Partial<PlacePickInput> = {}): PlacePickInput {
  return { id: "kakao:8193468", title: "오동도", latitude: 34.744, longitude: 127.766, categoryCode: "AT4", ...overrides };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function setup() {
  const onMatched = vi.fn<(item: PlaceBasketItem) => void>();
  const hook = renderHook(() => usePlaceMatch({ onMatched }));
  return { onMatched, ...hook };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("kakaoPlaceIdOf", () => {
  it("takes only the digits of a kakao:{id} candidate id", () => {
    expect(kakaoPlaceIdOf({ id: "kakao:8193468" })).toBe("8193468");
    expect(kakaoPlaceIdOf({ id: "kakao:abc" })).toBeNull();
    expect(kakaoPlaceIdOf({ id: "kakao:12ab" })).toBeNull();
    expect(kakaoPlaceIdOf({ id: "kakao:" })).toBeNull();
    expect(kakaoPlaceIdOf({ id: "search-a" })).toBeNull();
    expect(kakaoPlaceIdOf({ id: `kakao:${"9".repeat(21)}` })).toBeNull();
    expect(kakaoPlaceIdOf({ id: null })).toBeNull();
    expect(kakaoPlaceIdOf({})).toBeNull();
  });
});

describe("usePlaceMatch", () => {
  it("goes straight to a custom place when the pick has no coordinates", async () => {
    const matchSpy = vi.spyOn(appDataApi, "matchPlace");
    const { result, onMatched } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick({ latitude: null, longitude: undefined }));
    });

    expect(result.current.state).toEqual({ status: "custom", kakaoPlaceId: "8193468", reason: "noCoords", pickId: expect.any(Number) });
    expect(matchSpy).not.toHaveBeenCalled();
    expect(onMatched).not.toHaveBeenCalled();
  });

  it("hands one exact match to onMatched as a public basket item", async () => {
    const matchSpy = vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "match", places: [odongdo] });
    const { result, onMatched } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick());
    });

    // 맞춰 보기에는 이름 · 좌표 · 분류만 간다 - 카카오 장소 ID 는 보내지 않는다
    expect(matchSpy).toHaveBeenCalledWith({ name: "오동도", latitude: 34.744, longitude: 127.766, categoryCode: "AT4" });
    expect(onMatched).toHaveBeenCalledTimes(1);
    expect(onMatched).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "public", place: odongdo, kakaoPlaceId: "8193468" }),
    );
    expect(result.current.state).toEqual({ status: "idle" });
  });

  it("asks which place is right when candidates come back, then adds the chosen one", async () => {
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "candidates", places: [odongdo, yeosuPark] });
    const { result, onMatched } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick());
    });

    expect(result.current.state).toEqual({
      status: "choose",
      kakaoPlaceId: "8193468",
      candidates: [odongdo, yeosuPark],
    });
    expect(onMatched).not.toHaveBeenCalled();

    act(() => {
      result.current.chooseCandidate(yeosuPark);
    });

    expect(onMatched).toHaveBeenCalledTimes(1);
    expect(onMatched).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "public", place: yeosuPark, kakaoPlaceId: "8193468" }),
    );
    expect(result.current.state).toEqual({ status: "idle" });
  });

  it("shows at most three candidates", async () => {
    const four = [odongdo, yeosuPark, { ...odongdo, sourceId: "3" }, { ...odongdo, sourceId: "4" }];
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "candidates", places: four });
    const { result } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick());
    });

    expect(result.current.state).toMatchObject({ status: "choose" });
    expect(result.current.state.status === "choose" && result.current.state.candidates).toHaveLength(3);
  });

  it("turns to a custom place with the same Kakao id when the user says none of the candidates is right", async () => {
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "candidates", places: [odongdo] });
    const { result, onMatched } = setup();
    await act(async () => {
      await result.current.pick(kakaoPick());
    });

    act(() => {
      result.current.chooseCustom();
    });

    expect(result.current.state).toEqual({ status: "custom", kakaoPlaceId: "8193468", reason: "none", pickId: expect.any(Number) });
    expect(onMatched).not.toHaveBeenCalled();
  });

  it("goes to a custom place when nothing matches", async () => {
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "none", places: [] });
    const { result, onMatched } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick());
    });

    expect(result.current.state).toEqual({ status: "custom", kakaoPlaceId: "8193468", reason: "none", pickId: expect.any(Number) });
    expect(onMatched).not.toHaveBeenCalled();
  });

  it("treats an answer that names a result but carries no place as none", async () => {
    vi.spyOn(appDataApi, "matchPlace")
      .mockResolvedValueOnce({ result: "match", places: [] })
      .mockResolvedValueOnce({ result: "candidates", places: [] });
    const { result, onMatched } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick());
    });
    expect(result.current.state).toMatchObject({ status: "custom", reason: "none" });

    await act(async () => {
      await result.current.pick(kakaoPick());
    });
    expect(result.current.state).toMatchObject({ status: "custom", reason: "none" });
    expect(onMatched).not.toHaveBeenCalled();
  });

  it("goes to a custom place when the match request fails", async () => {
    vi.spyOn(appDataApi, "matchPlace").mockRejectedValue(new Error("network down"));
    const { result, onMatched } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick());
    });

    expect(result.current.state).toEqual({ status: "custom", kakaoPlaceId: "8193468", reason: "failed", pickId: expect.any(Number) });
    expect(onMatched).not.toHaveBeenCalled();
  });

  it("keeps no Kakao id when the candidate id is not kakao:digits", async () => {
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "none", places: [] });
    const { result } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick({ id: "search-a" }));
    });

    expect(result.current.state).toEqual({ status: "custom", kakaoPlaceId: null, reason: "none", pickId: expect.any(Number) });
  });

  it("ignores the answer to an earlier pick when the user picks again", async () => {
    const first = deferred<PlaceMatchResult>();
    const second = deferred<PlaceMatchResult>();
    vi.spyOn(appDataApi, "matchPlace").mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const { result, onMatched } = setup();
    let firstPick!: Promise<void>;
    let secondPick!: Promise<void>;

    act(() => {
      firstPick = result.current.pick(kakaoPick({ id: "kakao:1", title: "첫째" }));
    });
    act(() => {
      secondPick = result.current.pick(kakaoPick({ id: "kakao:2", title: "둘째" }));
    });
    expect(result.current.state).toEqual({ status: "matching" });

    await act(async () => {
      second.resolve({ result: "match", places: [yeosuPark] });
      await secondPick;
    });
    await act(async () => {
      first.resolve({ result: "candidates", places: [odongdo] });
      await firstPick;
    });

    expect(onMatched).toHaveBeenCalledTimes(1);
    expect(onMatched).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "public", place: yeosuPark, kakaoPlaceId: "2" }),
    );
    expect(result.current.state).toEqual({ status: "idle" });
  });

  it("ignores a failure of an earlier pick too", async () => {
    const first = deferred<PlaceMatchResult>();
    const second = deferred<PlaceMatchResult>();
    vi.spyOn(appDataApi, "matchPlace").mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const { result } = setup();
    let firstPick!: Promise<void>;
    let secondPick!: Promise<void>;

    act(() => {
      firstPick = result.current.pick(kakaoPick({ id: "kakao:1" }));
    });
    act(() => {
      secondPick = result.current.pick(kakaoPick({ id: "kakao:2" }));
    });
    await act(async () => {
      second.resolve({ result: "none", places: [] });
      await secondPick;
    });
    await act(async () => {
      first.reject(new Error("late failure"));
      await firstPick;
    });

    expect(result.current.state).toEqual({ status: "custom", kakaoPlaceId: "2", reason: "none", pickId: expect.any(Number) });
  });

  it("drops a pending answer after reset", async () => {
    const pending = deferred<PlaceMatchResult>();
    vi.spyOn(appDataApi, "matchPlace").mockReturnValue(pending.promise);
    const { result, onMatched } = setup();
    let pickDone!: Promise<void>;

    act(() => {
      pickDone = result.current.pick(kakaoPick());
    });
    act(() => {
      result.current.reset();
    });
    await act(async () => {
      pending.resolve({ result: "match", places: [odongdo] });
      await pickDone;
    });

    expect(onMatched).not.toHaveBeenCalled();
    expect(result.current.state).toEqual({ status: "idle" });
  });

  it("opens an empty custom place from the direct entry without any Kakao id", () => {
    const { result } = setup();

    act(() => {
      result.current.startDirect();
    });

    expect(result.current.state).toEqual({ status: "custom", kakaoPlaceId: null, reason: "direct", pickId: expect.any(Number) });
  });

  it("gives every custom place form its own pick id, so a name typed for one pick cannot follow the next pick", async () => {
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "candidates", places: [odongdo] });
    const { result } = setup();
    const pickIdOf = (state: PlaceMatchState) => {
      if (state.status !== "custom") throw new Error(`expected a custom place form, got ${state.status}`);
      return state.pickId;
    };
    const noCoords = (id: string) => kakaoPick({ id, latitude: null, longitude: null });

    await act(async () => {
      await result.current.pick(noCoords("kakao:1"));
    });
    const first = pickIdOf(result.current.state);
    await act(async () => {
      await result.current.pick(noCoords("kakao:2"));
    });
    const second = pickIdOf(result.current.state);
    // 같은 카카오 장소를 다시 골라도 새 칸이다
    await act(async () => {
      await result.current.pick(noCoords("kakao:2"));
    });
    const third = pickIdOf(result.current.state);
    // 후보에서 '아니요, 직접 적을게요' 와 직접 적기 입구도 새 칸이다
    await act(async () => {
      await result.current.pick(kakaoPick());
    });
    act(() => {
      result.current.chooseCustom();
    });
    const fourth = pickIdOf(result.current.state);
    act(() => {
      result.current.startDirect();
    });
    const fifth = pickIdOf(result.current.state);

    expect(new Set([first, second, third, fourth, fifth]).size).toBe(5);
  });

  it("calls the newest onMatched even when the answer arrives after a re-render", async () => {
    const pending = deferred<PlaceMatchResult>();
    vi.spyOn(appDataApi, "matchPlace").mockReturnValue(pending.promise);
    const stale = vi.fn();
    const latest = vi.fn();
    const { result, rerender } = renderHook(({ onMatched }) => usePlaceMatch({ onMatched }), {
      initialProps: { onMatched: stale },
    });
    let pickDone!: Promise<void>;

    act(() => {
      pickDone = result.current.pick(kakaoPick());
    });
    rerender({ onMatched: latest });
    await act(async () => {
      pending.resolve({ result: "match", places: [odongdo] });
      await pickDone;
    });

    expect(stale).not.toHaveBeenCalled();
    expect(latest).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd frontend && npx vitest run src/components/itinerary/placeAdd`
기대: FAIL 3개 파일. 모두 `Failed to resolve import "./publicPlaceText"`(또는 `./placeBasket` · `./usePlaceMatch`) - 구현 파일이 아직 없다.

- [ ] **3단계: 구현**

**새 파일 `frontend/src/components/itinerary/placeAdd/publicPlaceText.ts`**

```ts
import type { PublicPlaceCategory } from "../../../api";

/* 공공데이터 장소 분류(서버 public_places.category 와 같은 7개)를 사람이 읽는 말로 */
export const PUBLIC_CATEGORY_LABEL: Record<PublicPlaceCategory, string> = {
  sight: "관광지",
  culture: "문화시설",
  leisure: "레포츠",
  stay: "숙박",
  shopping: "쇼핑",
  food: "음식점",
  cafe: "카페",
};

/* 한국관광공사 사진의 출처 표시. 공공누리 Type1 은 출처 표시, Type3 는 출처 표시 + 변경 금지다 */
export function photoCredit(license: string | null | undefined): string {
  return license === "Type3" ? "사진: 한국관광공사 · 변경 금지" : "사진: 한국관광공사";
}

/* 추천 미리보기의 시간대 묶음(오전 · 점심 · 카페 · 숙소)과 같은 네 갈래. 카카오 분류 코드 없이 공공데이터 분류만으로 가른다 */
export type PublicTimeSlotGroup = "attraction" | "food" | "cafe" | "stay";

export function publicTimeSlotGroup(category: PublicPlaceCategory): PublicTimeSlotGroup {
  if (category === "food") return "food";
  if (category === "cafe") return "cafe";
  if (category === "stay") return "stay";
  return "attraction";
}

/* 후보 카드의 거리 문구 - 고른 카카오 장소에서 얼마나 떨어졌는지(서버가 잰 값). 시안 v59 */
export function distanceText(meters: number): string {
  if (meters < 10) return "고른 곳과 같은 자리";
  if (meters < 1000) return `고른 곳에서 약 ${Math.round(meters)}m`;
  return `고른 곳에서 약 ${(meters / 1000).toFixed(1)}km`;
}
```

**새 파일 `frontend/src/components/itinerary/placeAdd/placeBasket.ts`**

```ts
import type { PublicPlaceItem, TripPlaceAddItem } from "../../../api";
import { PUBLIC_CATEGORY_LABEL } from "./publicPlaceText";

/* 장소 추가 창 바구니의 한 칸. 공공데이터 장소(public)이거나 사용자가 직접 쓴 장소(custom)다.
   카카오가 준 이름 · 주소 · 좌표는 여기에 들어오지 않는다. 카카오에서는 장소 ID 숫자만 받아 '카카오맵에서 보기' 링크용으로 둔다 */
export type PlaceBasketItem =
  | { basketId: string; kind: "public"; place: PublicPlaceItem; kakaoPlaceId: string | null }
  | {
      basketId: string;
      kind: "custom";
      name: string;
      latitude: number | null;
      longitude: number | null;
      kakaoPlaceId: string | null;
    };

let basketSequence = 0;
const nextBasketId = () => `place-basket-${++basketSequence}`;

export function publicBasketItem(place: PublicPlaceItem, kakaoPlaceId: string | null): PlaceBasketItem {
  return { basketId: nextBasketId(), kind: "public", place, kakaoPlaceId };
}

export function customBasketItem(
  input: { name: string; latitude?: number | null; longitude?: number | null },
  kakaoPlaceId: string | null,
): PlaceBasketItem {
  // 위치는 둘 다 있거나 둘 다 없다 - 반쪽이면 버린다
  const point =
    typeof input.latitude === "number" && typeof input.longitude === "number"
      ? { latitude: input.latitude, longitude: input.longitude }
      : { latitude: null, longitude: null };
  return { basketId: nextBasketId(), kind: "custom", name: input.name.trim(), ...point, kakaoPlaceId };
}

/* 저장 요청 한 건. 공공데이터 장소는 참조(source · sourceId)만 보낸다 - 이름 · 주소 · 좌표 · 사진은 서버가 자기 표에서 채운다 */
export function basketItemPayload(item: PlaceBasketItem): TripPlaceAddItem {
  const kakao = item.kakaoPlaceId ? { kakaoPlaceId: item.kakaoPlaceId } : {};
  if (item.kind === "public") {
    return { publicPlace: { source: item.place.source, sourceId: item.place.sourceId }, ...kakao };
  }
  const point =
    item.latitude !== null && item.longitude !== null
      ? { latitude: item.latitude, longitude: item.longitude }
      : {};
  return { customPlace: { name: item.name, ...point }, ...kakao };
}

export function basketItemTitle(item: PlaceBasketItem): string {
  return item.kind === "public" ? item.place.name : item.name;
}

/* 바구니 줄의 분류 이름. 시안 v59 */
export function basketItemBadge(item: PlaceBasketItem): string {
  return item.kind === "public" ? PUBLIC_CATEGORY_LABEL[item.place.category] : "직접 적은 장소";
}

/* 바구니 줄의 보조 글 - 공공데이터 주소, 또는 직접 찍은 위치가 있는지. 시안 v59 */
export function basketItemDetail(item: PlaceBasketItem): string {
  if (item.kind === "public") return item.place.address ?? "주소 정보 없음";
  return item.latitude !== null ? "지도에서 찍은 위치" : "위치 없이 이름만";
}
```

**새 파일 `frontend/src/components/itinerary/placeAdd/usePlaceMatch.ts`**

```ts
import { useCallback, useEffect, useRef, useState } from "react";
import { appDataApi, type PlaceMatchResult, type PlaceSearchCandidate, type PublicPlaceItem } from "../../../api";
import { publicBasketItem, type PlaceBasketItem } from "./placeBasket";

/* 고른 카카오 장소를 공공데이터와 맞춰 본 결과의 상태.
   choose = '이 장소가 맞나요?' 후보 1~3곳, custom = 나만의 장소 칸(reason 은 왜 열렸는지).
   pickId = 칸을 열 때마다 달라지는 번호 - 화면이 이 번호로 칸을 새로 그려, 앞 장소에 적던 이름이 새로 고른 카카오 ID 에 붙지 않는다.
   카카오가 준 이름 · 주소 · 좌표는 상태에 두지 않는다 - 남는 카카오 값은 장소 ID 숫자뿐이다 */
export type PlaceMatchState =
  | { status: "idle" }
  | { status: "matching" }
  | { status: "choose"; kakaoPlaceId: string | null; candidates: PublicPlaceItem[] }
  | { status: "custom"; kakaoPlaceId: string | null; reason: "none" | "noCoords" | "failed" | "direct"; pickId: number };

/* pick 이 읽는 카카오 값은 이 다섯 칸뿐이다. 검색 후보(PlaceSearchCandidate)가 그대로 맞고,
   홈 넘김은 PlaceSearchItem 에서 { id, title: name, latitude, longitude, categoryCode } 를 만들어 넘긴다 */
export type PlacePickInput = Pick<PlaceSearchCandidate, "id" | "title" | "latitude" | "longitude" | "categoryCode">;

const IDLE: PlaceMatchState = { status: "idle" };
const KAKAO_ID = /^kakao:(\d{1,20})$/;

/** 후보 id `kakao:{숫자}` 에서 숫자만. 모양이 다르면 null (externalPlaceId 로 돌아가지 않는다) */
export function kakaoPlaceIdOf(candidate: Pick<PlaceSearchCandidate, "id">): string | null {
  return KAKAO_ID.exec(candidate.id ?? "")?.[1] ?? null;
}

export function usePlaceMatch({ onMatched }: { onMatched: (item: PlaceBasketItem) => void }) {
  const [state, setState] = useState<PlaceMatchState>(IDLE);
  const stateRef = useRef<PlaceMatchState>(IDLE);
  const onMatchedRef = useRef(onMatched);
  // 새로 고르거나 닫을 때마다 올린다 - 늦게 도착한 앞 요청의 답을 걸러 낸다
  const turnRef = useRef(0);

  useEffect(() => {
    onMatchedRef.current = onMatched;
  }, [onMatched]);

  useEffect(
    () => () => {
      turnRef.current += 1;
    },
    [],
  );

  const commit = useCallback((next: PlaceMatchState) => {
    stateRef.current = next;
    setState(next);
  }, []);

  const reset = useCallback(() => {
    turnRef.current += 1;
    commit(IDLE);
  }, [commit]);

  const pick = useCallback(
    async (candidate: PlacePickInput): Promise<void> => {
      const turn = ++turnRef.current;
      const kakaoPlaceId = kakaoPlaceIdOf(candidate);
      const { latitude, longitude } = candidate;
      if (
        typeof latitude !== "number" ||
        typeof longitude !== "number" ||
        !Number.isFinite(latitude) ||
        !Number.isFinite(longitude)
      ) {
        commit({ status: "custom", kakaoPlaceId, reason: "noCoords", pickId: turn });
        return;
      }
      commit({ status: "matching" });
      let answer: PlaceMatchResult;
      try {
        answer = await appDataApi.matchPlace({
          name: candidate.title,
          latitude,
          longitude,
          categoryCode: candidate.categoryCode ?? null,
        });
      } catch {
        if (turnRef.current === turn) commit({ status: "custom", kakaoPlaceId, reason: "failed", pickId: turn });
        return;
      }
      if (turnRef.current !== turn) return;
      const [first] = answer.places;
      if (answer.result === "match" && first) {
        commit(IDLE);
        onMatchedRef.current(publicBasketItem(first, kakaoPlaceId));
      } else if (answer.result === "candidates" && answer.places.length > 0) {
        commit({ status: "choose", kakaoPlaceId, candidates: answer.places.slice(0, 3) });
      } else {
        commit({ status: "custom", kakaoPlaceId, reason: "none", pickId: turn });
      }
    },
    [commit],
  );

  const chooseCandidate = useCallback(
    (place: PublicPlaceItem) => {
      const current = stateRef.current;
      if (current.status !== "choose") return;
      turnRef.current += 1;
      commit(IDLE);
      onMatchedRef.current(publicBasketItem(place, current.kakaoPlaceId));
    },
    [commit],
  );

  const chooseCustom = useCallback(() => {
    const current = stateRef.current;
    if (current.status !== "choose") return;
    turnRef.current += 1;
    commit({ status: "custom", kakaoPlaceId: current.kakaoPlaceId, reason: "none", pickId: turnRef.current });
  }, [commit]);

  const startDirect = useCallback(() => {
    turnRef.current += 1;
    commit({ status: "custom", kakaoPlaceId: null, reason: "direct", pickId: turnRef.current });
  }, [commit]);

  return { state, pick, chooseCandidate, chooseCustom, startDirect, reset };
}
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd frontend && npx vitest run src/components/itinerary/placeAdd`
기대: PASS(3개 파일 전부 통과).

실행: `cd frontend && npx tsc --noEmit -p .`
기대: `src/components/itinerary/placeAdd/` 아래 오류 0건. 남는 오류는 과제 7과 같다(`ItineraryDetailPage.tsx` 두 곳).

---

### Task 8b: 미리 맞춤 - 일정 안 검색 결과에 맞춰 본 갈래 싣기 · 같은 후보 하나로 (시안 v62)

**파일:**
- 고치기: `backend/app/repositories/public_places.py` - 여러 상자를 질의 한 번으로 읽는 `public_places_in_boxes`
- 고치기: `backend/app/services/public_places.py` - 규칙 함수(`_near` · `_decide`)를 나눠 `match_place` 와 새 `match_places`(묶음)가 같이 쓴다. 같은 줄은 하나로(결정 27)
- 고치기: `backend/app/services/trips.py` - `search_places_for_trip` 이 카카오에서 6곳을 받고 줄마다 `publicMatch` 를 싣는다(결정 23)
- 고치기: `backend/app/schemas/trip.py` - `PlaceSearchCandidate.publicMatch`
- 고치기: `docs/mvp-api-contract.md`(`### GET /trips/{trip_id}/place-search`), `.agent/evals/api-contract-golden.json`, `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`(2절)
- 고치기: `frontend/src/api/types.ts`, `frontend/src/components/itinerary/placeAdd/usePlaceMatch.ts`, `frontend/src/components/itinerary/placeAdd/publicPlaceText.ts`
- 시험: `backend/tests/test_public_places.py`, `backend/tests/test_trip_db_service.py`, `backend/tests/test_trip_db_routes.py`, `backend/tests/test_places_contract_docs.py`, `frontend/src/components/itinerary/placeAdd/usePlaceMatch.test.ts`, `frontend/src/components/itinerary/placeAdd/publicPlaceText.test.ts`

**인터페이스:**
- 쓰는 것: `match_place(db, *, name, latitude, longitude, category_code) -> PlaceMatch`, `public_place_item(place, distance) -> dict`(2단계), `PlaceMatchResponse`(`app/schemas/places.py`), 프론트 `PlaceMatchResult` · `PublicPlaceItem` · `usePlaceMatch`(과제 7 · 8).
- 내놓는 것:
  - 서버: `PlaceMatchInput(name, latitude, longitude, category_code)`, `match_places(db, rows: Sequence[PlaceMatchInput | None]) -> list[dict | None]`(`public_places` 서비스), `public_places_in_boxes(db, boxes, *, source) -> list[PublicPlace]`(저장소).
  - 응답: `PlaceSearchCandidate.publicMatch: PlaceMatchResponse | None` - 늘 있고 값은 null 일 수 있다.
  - 프론트: `publicMatch?: PlaceMatchResult | null`, `PlacePickInput` 의 `publicMatch`, `publicMatchBadge(match) -> PublicMatchBadge | null`(`{ tone: "ready" | "similar" | "custom"; text: string }`). 과제 9 의 5 ~ 8단계가 쓴다.

- [ ] **1단계: 실패하는 시험 쓰기(백엔드)**

`backend/tests/test_public_places.py` - 들여오기를 더한다.

찾기:

```python
from app.services import public_places
from app.services.public_places import (
    METERS_PER_DEGREE,
    WIDE_RADIUS_M,
    iter_sangga_rows,
    load_sangga_places,
    match_place,
    name_key,
```

바꾸기:

```python
from app.services import public_places
from app.services import trips as trip_service
from app.services.kakao_local import KakaoLocalPlace
from app.services.public_places import (
    METERS_PER_DEGREE,
    WIDE_RADIUS_M,
    PlaceMatchInput,
    iter_sangga_rows,
    load_sangga_places,
    match_place,
    match_place_response,
    match_places,
    name_key,
```

(이미 들여온 이름이 있으면 빼고 더한다. `from sqlalchemy import create_engine, func, select` 줄에는 `event` 를 더한다.)

`place_row` 가 주소를 받게 한다(기본값은 지금 주소).

찾기:

```python
def place_row(source: str, source_id: str, name: str, lat: float = 34.7443, lng: float = 127.7663,
              category: str = "food", *, photo: str | None = None, synced_at: datetime = T1, sido: str = "전남") -> dict[str, object]:
    return {
        "source": source, "source_id": source_id, "name": name, "name_key": name_key(name),
        "address": "전남광주통합특별시 여수시 수정동 1", "latitude": lat, "longitude": lng, "category": category,
```

바꾸기:

```python
def place_row(source: str, source_id: str, name: str, lat: float = 34.7443, lng: float = 127.7663,
              category: str = "food", *, photo: str | None = None, synced_at: datetime = T1, sido: str = "전남",
              address: str = "전남광주통합특별시 여수시 수정동 1") -> dict[str, object]:
    return {
        "source": source, "source_id": source_id, "name": name, "name_key": name_key(name),
        "address": address, "latitude": lat, "longitude": lng, "category": category,
```

같은 이름의 다른 가게 시험은 주소를 달리 둔다(같은 주소면 이제 한 곳이다).

찾기:

```python
    seed(db, place_row("sangga", "A", "이디야커피", 34.7443, 127.7663), place_row("sangga", "B", "이디야커피", 34.7455, 127.7663))
```

바꾸기:

```python
    seed(db, place_row("sangga", "A", "이디야커피", 34.7443, 127.7663),
         place_row("sangga", "B", "이디야커피", 34.7455, 127.7663, address="전남광주통합특별시 여수시 수정동 9"))
```

그 시험(`test_two_shops_with_the_same_name_ask_which_one`) 바로 아래에 더한다.

```python
def test_identical_rows_of_one_source_count_as_one_place(db: Session) -> None:
    # 결정 27: 상가정보에 같은 가게가 두 줄(이름 열쇠 · 주소 · 분류 같음) - 후보에 두 번 나오지 않고, 하나뿐이면 바로 담긴다(가까운 줄)
    seed(db, place_row("sangga", "A", "이디야커피", 34.7443, 127.7663, "cafe"), place_row("sangga", "B", "이디야 커피", 34.7444, 127.7663, "cafe"))
    found = match_place(db, name="이디야커피", latitude=34.7443, longitude=127.7663, category_code="CE7")
    assert found.result == "match"
    assert [place.source_id for place, _ in found.places] == ["A"]


def test_rows_without_an_address_are_never_folded_together(db: Session) -> None:
    seed(db, place_row("sangga", "A", "이디야커피", 34.7443, 127.7663, "cafe", address=""),
         place_row("sangga", "B", "이디야커피", 34.7444, 127.7663, "cafe", address=""))
    assert match_place(db, name="이디야커피", latitude=34.7443, longitude=127.7663, category_code="CE7").result == "candidates"


def test_rows_of_another_kind_at_the_same_address_are_not_folded(db: Session) -> None:
    # 결정 27: 분류가 다르면 같은 곳으로 보지 않는다 - 가까운 줄의 분류로 바로 담기가 나지 않게
    seed(db, place_row("sangga", "A", "바다정원", 34.7443, 127.7663, "cafe"), place_row("sangga", "B", "바다정원", 34.7444, 127.7663, "food"))
    found = match_place(db, name="바다정원", latitude=34.7443, longitude=127.7663, category_code="CE7")
    assert found.result == "candidates"
    assert {place.source_id for place, _ in found.places} == {"A", "B"}


def test_match_places_answers_each_row_like_match_place(db: Session) -> None:
    # 결정 23: 묶음 맞춰 보기는 줄마다 match_place 와 같은 답이다. 좌표 없는 줄(None)은 None
    seed(db, place_row("tourapi", "T1", "죽녹원", 35.3270, 126.9860, "sight"),
         place_row("sangga", "S1", "오동도횟집1", 34.7443, 127.7663), place_row("sangga", "S2", "오동도횟집2", 34.7445, 127.7663))
    rows = [PlaceMatchInput("죽녹원", 35.3271, 126.9861, "AT4"), None,
            PlaceMatchInput("오동도", 34.7443, 127.7663, "FD6"), PlaceMatchInput("없는 곳", 34.7443, 127.7663, "FD6")]
    answers = match_places(db, rows)
    assert answers[1] is None
    for row, answer in zip(rows, answers):
        if row is not None:
            assert answer == match_place_response(db, name=row.name, latitude=row.latitude, longitude=row.longitude, category_code=row.category_code)
    assert [answer["result"] if answer else None for answer in answers] == ["match", None, "candidates", "none"]


def test_match_places_reads_each_source_once_for_all_rows(db: Session) -> None:
    # 결정 23 · 코덱스 검토: 여섯 줄이어도 질의는 출처마다 한 번(두 번)
    seed(db, place_row("tourapi", "T1", "죽녹원", 35.3270, 126.9860, "sight"))
    statements: list[str] = []
    event.listen(db.get_bind(), "before_cursor_execute", lambda *args: statements.append(args[2]))
    match_places(db, [PlaceMatchInput(f"장소{n}", 35.3270 + n * 0.01, 126.9860, "AT4") for n in range(6)])
    assert len([sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]) == 2


def test_match_places_keeps_the_other_rows_when_one_row_fails(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    # 코덱스 검토: 한 줄을 가리다 실패해도 앞뒤 줄의 답은 남는다(성공 → 실패 → 성공)
    seed(db, place_row("tourapi", "T1", "죽녹원", 35.3270, 126.9860, "sight"), place_row("tourapi", "T2", "관방제림", 35.3290, 126.9850, "sight"),
         place_row("tourapi", "T3", "메타세쿼이아길", 35.3230, 126.9870, "sight"))
    real_decide = public_places._decide

    def flaky(key, near, category_code):
        if key == name_key("관방제림"):
            raise ValueError("boom")
        return real_decide(key, near, category_code)

    monkeypatch.setattr(public_places, "_decide", flaky)
    answers = match_places(db, [PlaceMatchInput("죽녹원", 35.3270, 126.9860, "AT4"), PlaceMatchInput("관방제림", 35.3290, 126.9850, "AT4"),
                                PlaceMatchInput("메타세쿼이아길", 35.3230, 126.9870, "AT4")])
    assert [answer["result"] if answer else None for answer in answers] == ["match", None, "match"]


def test_match_places_without_live_rows_reads_nothing(db: Session) -> None:
    statements: list[str] = []
    event.listen(db.get_bind(), "before_cursor_execute", lambda *args: statements.append(args[2]))
    assert match_places(db, [None, None]) == [None, None]
    assert statements == []


def test_trip_search_prematches_with_the_session_it_released_before_kakao(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    # 코덱스 검토: 접근 확인 뒤 놓은(close) 실제 세션을 미리 맞춤이 다시 쓴다 - 가짜 db 가 아니라 실제 Session 으로 close → 다시 읽기
    seed(db, place_row("tourapi", "126", "죽녹원", 35.3270, 126.9860, "sight"))

    class FakeSearchProvider:
        def search_keyword(self, *, query: str, size: int = 10):
            return [KakaoLocalPlace(external_place_id="1", name="죽녹원", category_name="여행 > 관광,명소", category_group_code="AT4",
                                    category_group_name="관광명소", phone=None, address="전남 담양군 담양읍", latitude=35.3270,
                                    longitude=126.9861, place_url="https://place.map.kakao.com/1")]

    closed: list[bool] = []
    real_close = db.close

    def spy_close() -> None:
        closed.append(True)
        real_close()

    monkeypatch.setattr(trip_service.trip_repository, "has_trip_access", lambda db, trip_id, user_id: True, raising=False)
    monkeypatch.setattr(trip_service, "build_kakao_local_client", lambda: FakeSearchProvider())
    monkeypatch.setattr(db, "close", spy_close)

    rows = trip_service.search_places_for_trip(db, USER, trip_handle="7", query="죽녹원")

    assert closed == [True]
    assert rows[0]["publicMatch"]["result"] == "match"
    assert rows[0]["publicMatch"]["places"][0]["sourceId"] == "126"
```

`backend/tests/test_trip_db_service.py` - 카카오 결과를 고치는 시험(`test_search_places_for_trip_maps_kakao_candidates`)은 6곳을 묻고, 묶음 맞춰 보기를 대신한다.

찾기:

```python
            assert query == "성산일출봉"
            assert size == 10
```

바꾸기:

```python
            assert query == "성산일출봉"
            assert size == 6
```

찾기:

```python
    monkeypatch.setattr(trip_service, "build_kakao_local_client", lambda: FakeSearchProvider())

    candidates = trip_service.search_places_for_trip(
        object(),
        user,
        trip_handle="7",
        query="성산일출봉",
    )
```

바꾸기:

```python
    monkeypatch.setattr(trip_service, "build_kakao_local_client", lambda: FakeSearchProvider())
    monkeypatch.setattr(trip_service.public_place_service, "match_places", lambda db, rows: [{"result": "none", "places": []} for _ in rows])

    candidates = trip_service.search_places_for_trip(
        object(),
        user,
        trip_handle="7",
        query="성산일출봉",
    )
```

찾기:

```python
    assert candidates[0]["externalPlaceId"] == "kakao-1"


def test_search_places_for_trip_answers_503_when_kakao_is_misconfigured(monkeypatch, caplog) -> None:
```

바꾸기:

```python
    assert candidates[0]["externalPlaceId"] == "kakao-1"
    assert candidates[0]["publicMatch"] == {"result": "none", "places": []}


def kakao_place(external_place_id: str, name: str, latitude: float | None, longitude: float | None) -> KakaoLocalPlace:
    return KakaoLocalPlace(
        external_place_id=external_place_id,
        name=name,
        category_name="여행 > 관광,명소",
        category_group_code="AT4",
        category_group_name="관광명소",
        phone=None,
        address=f"전남 담양군 담양읍 {name}로 1",
        latitude=latitude,
        longitude=longitude,
        place_url=f"https://place.map.kakao.com/{external_place_id}",
    )


def test_search_places_for_trip_sends_every_row_to_one_batch_match(monkeypatch) -> None:
    # 결정 23: 줄마다 따로 부르지 않고 한 번에. 좌표가 없는 줄은 None 으로 자리만 지킨다
    received: list[list[object]] = []

    class FakeSearchProvider:
        def search_keyword(self, *, query: str, size: int = 10):
            return [kakao_place("1", "죽녹원", 35.3270, 126.9860), kakao_place("2", "좌표 없는 곳", None, None)]

    def fake_match_places(db, rows):
        received.append(list(rows))
        return [{"result": "match", "places": []}, None]

    monkeypatch.setattr(trip_service.trip_repository, "has_trip_access", lambda db, trip_id, user_id: True, raising=False)
    monkeypatch.setattr(trip_service, "build_kakao_local_client", lambda: FakeSearchProvider())
    monkeypatch.setattr(trip_service.public_place_service, "match_places", fake_match_places)

    rows = trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="담양 죽녹원")

    assert received == [[trip_service.public_place_service.PlaceMatchInput("죽녹원", 35.3270, 126.9860, "AT4"), None]]
    assert [row["publicMatch"] for row in rows] == [{"result": "match", "places": []}, None]


def test_search_places_for_trip_still_answers_when_prematching_fails(monkeypatch, caplog) -> None:
    # DB 읽기가 실패해도 검색은 보인다 - 모든 줄이 null 이고 화면이 고른 뒤 예전처럼 맞춰 본다. 로그에는 예외 이름뿐(코덱스 검토: 여섯 줄 전부 확인)
    places = [kakao_place(f"9{n}7531", f"비밀장소{n}", 35.31 + n / 100, 126.91 + n / 100) for n in range(6)]

    class FakeSearchProvider:
        def search_keyword(self, *, query: str, size: int = 10):
            return places

    def broken_match_places(db, rows):
        raise RuntimeError("db down")

    monkeypatch.setattr(trip_service.trip_repository, "has_trip_access", lambda db, trip_id, user_id: True, raising=False)
    monkeypatch.setattr(trip_service, "build_kakao_local_client", lambda: FakeSearchProvider())
    monkeypatch.setattr(trip_service.public_place_service, "match_places", broken_match_places)
    monkeypatch.setattr(trip_service.logger, "handlers", [caplog.handler])
    caplog.set_level(logging.WARNING)

    rows = trip_service.search_places_for_trip(object(), make_user(), trip_handle="7", query="담양 비밀검색어")

    assert [row["publicMatch"] for row in rows] == [None] * 6
    assert "trip_place_search_prematch_failed" in caplog.text and "RuntimeError" in caplog.text
    assert "비밀검색어" not in caplog.text
    for place in places:
        for value in (place.name, place.address, str(place.latitude), str(place.longitude), place.external_place_id, place.place_url):
            assert value not in caplog.text


def test_search_places_for_trip_answers_503_when_kakao_is_misconfigured(monkeypatch, caplog) -> None:
```

(장소 ID 를 `9{n}7531` 처럼 길게 둔다 - 한 글자 ID 는 로그의 줄 번호와 섞여 거짓 실패한다.)

`backend/tests/test_trip_db_routes.py` - 라우트가 `publicMatch` 를 그대로 내보내는지. `test_db_trip_place_search_route_returns_candidates` 의 후보 사전에 한 줄을 더하고 확인한다.

찾기:

```python
                "sourceProvider": "kakao",
                "externalPlaceId": "kakao-1",
            }
        ]
        if db is fake_db and current_user is user and trip_handle == "7" and query == "성산일출봉"
```

바꾸기:

```python
                "sourceProvider": "kakao",
                "externalPlaceId": "kakao-1",
                "publicMatch": {"result": "candidates", "places": [{
                    "source": "tourapi", "sourceId": "126", "name": "성산일출봉", "address": "제주특별자치도 서귀포시 성산읍 일출로 284-12",
                    "latitude": 33.458, "longitude": 126.942, "category": "sight", "sido": "제주", "city": "서귀포",
                    "photoUrl": None, "photoLicense": None, "distanceMeters": 40}]},
            }
        ]
        if db is fake_db and current_user is user and trip_handle == "7" and query == "성산일출봉"
```

찾기:

```python
    assert response.json()[0]["externalPlaceId"] == "kakao-1"


def test_db_trip_place_search_route_answers_503_when_kakao_is_misconfigured(monkeypatch) -> None:
```

바꾸기:

```python
    assert response.json()[0]["externalPlaceId"] == "kakao-1"
    assert response.json()[0]["publicMatch"]["result"] == "candidates"
    assert response.json()[0]["publicMatch"]["places"][0]["sourceId"] == "126"


def test_db_trip_place_search_route_answers_503_when_kakao_is_misconfigured(monkeypatch) -> None:
```

`backend/tests/test_places_contract_docs.py` - 계약 문서 · 골든 · 설계 문서가 미리 맞춤을 적는지. `test_the_search_docs_say_503_for_a_misconfigured_kakao_and_an_empty_list_for_an_off_one` 아래에 더한다.

```python
def test_the_search_docs_describe_the_prematch_on_each_row() -> None:
    search = section("### GET /trips/{trip_id}/place-search", "### GET /places/search")
    assert '"publicMatch"' in search and "6곳" in search and "always present" in search
    entry = golden("GET", "/api/trips/1/place-search")
    assert entry["requiredArrayItemFields"]["publicMatch"] == "object|null"
    assert "publicMatch" not in entry["optionalArrayItemFields"]
    assert "publicMatch" in entry["dbModeBehavior"] and "6 places" in entry["dbModeBehavior"]
    design = (ROOT / "docs/superpowers/specs/2026-10-03-public-place-storage-design.md").read_text(encoding="utf-8")
    assert "검색 결과 6곳을 검색 요청 안에서 한꺼번에 맞춰" in design
```

- [ ] **2단계: 실패하는지 확인(백엔드)**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_public_places.py tests/test_trip_db_service.py tests/test_trip_db_routes.py tests/test_places_contract_docs.py`
기대: 들여오기 오류로 `test_public_places.py` 전체가 모이지 않는다(`PlaceMatchInput` · `match_places` 가 없다). 나머지 셋: `test_search_places_for_trip_maps_kakao_candidates`(`size == 6` 아님), 새 미리 맞춤 시험 둘(`match_places` 가 없다), 라우트 시험(`publicMatch` 가 응답에 없음), 문서 시험(`publicMatch` 없음)이 실패한다.

- [ ] **3단계: 구현(백엔드 · 계약 · 설계)**

`backend/app/repositories/public_places.py` - 들여오기에 `or_` 를 더한다.

찾기:

```python
from sqlalchemy import and_, case, delete, func, not_, select, tuple_
```

바꾸기:

```python
from sqlalchemy import and_, case, delete, func, not_, or_, select, tuple_
```

`public_places_in_box` 바로 아래에 더한다.

```python
def public_places_in_boxes(db: Session, boxes: Sequence[dict[str, float]], *, source: str) -> list[PublicPlace]:
    """여러 상자 가운데 하나에라도 드는 그 출처의 장소 - 검색 결과 여러 줄을 질의 한 번으로 맞추려고(결정 23).
    상자마다 ix_public_places_lat_lng 를 쓴다(PostgreSQL 은 BitmapOr). 반경 거르기는 서비스가 한다."""

    if not boxes:
        return []
    statement = select(PublicPlace).where(
        PublicPlace.source == source,
        or_(
            *(
                and_(
                    PublicPlace.latitude.between(box["south"], box["north"]),
                    PublicPlace.longitude.between(box["west"], box["east"]),
                )
                for box in boxes
            )
        ),
    )
    return list(db.scalars(statement))
```

`backend/app/services/public_places.py` - 들여오기. 서비스는 이제 한 상자 함수를 쓰지 않는다(저장소 함수와 그 시험은 그대로 둔다).

찾기:

```python
    public_places_in_box,
    record_sync_state,
    upsert_public_places,
)
from app.services.place_search import resolve_city, resolve_region
```

바꾸기:

```python
    public_places_in_boxes,
    record_sync_state,
    upsert_public_places,
)
from app.services.place_search import resolve_city, resolve_region
```

`match_place` 를 규칙 함수로 나눈다. 찾기:

```python
    key = name_key(name)
    if not key:
        return PlaceMatch("none", [])
    tour_radius = WIDE_RADIUS_M if category_code in WIDE_KAKAO_CATEGORIES else NEAR_RADIUS_M
    if tour_radius > NEAR_RADIUS_M:
        # 넓은 반경(1km)은 TourAPI 만 쓴다. 가게는 200m 상자만 읽는다 - 명동 · 종로에서는 1km 상자가 가게 수천 줄을 읽고 버렸다
        in_boxes = [
            *public_places_in_box(db, **_box(latitude, longitude, tour_radius), source=TOURAPI),
            *public_places_in_box(db, **_box(latitude, longitude, NEAR_RADIUS_M), source=SANGGA),
        ]
    else:
        in_boxes = public_places_in_box(db, **_box(latitude, longitude, NEAR_RADIUS_M))
    near: list[tuple[PublicPlace, float]] = []
    for place in in_boxes:
        distance = distance_m(latitude, longitude, place.latitude, place.longitude)
        if distance <= (tour_radius if place.source == TOURAPI else NEAR_RADIUS_M):
            near.append((place, distance))
    near.sort(key=lambda pair: pair[1])
    exact = [pair for pair in near if pair[0].name_key == key]
    if exact:
        if len(exact) == 1 and _fits(category_code, exact[0][0]):
            return PlaceMatch("match", exact)
        return PlaceMatch("candidates", exact[:MAX_CANDIDATES])
    if len(key) >= 2:
        loose = [pair for pair in near if len(pair[0].name_key) >= 2 and (key in pair[0].name_key or pair[0].name_key in key)]
        if loose:
            return PlaceMatch("candidates", loose[:MAX_CANDIDATES])
    return PlaceMatch("none", [])
```

바꾸기:

```python
    key = name_key(name)
    if not key:
        return PlaceMatch("none", [])
    places = _read_boxes(db, [(latitude, longitude, category_code)])
    return _decide(key, _near(latitude, longitude, category_code, places), category_code)


def _tour_radius(category_code: str | None) -> int:
    return WIDE_RADIUS_M if category_code in WIDE_KAKAO_CATEGORIES else NEAR_RADIUS_M


def _read_boxes(db: Session, points: Sequence[tuple[float, float, str | None]]) -> list[PublicPlace]:
    """맞춰 볼 자리들의 상자를 출처마다 질의 한 번으로 읽는다(결정 23). 넓은 반경(1km)은 TourAPI 만 쓰고 가게는 200m 상자만 읽는다
    - 명동 · 종로에서는 1km 상자가 가게 수천 줄을 읽고 버렸다(결정 16)."""

    if not points:
        return []
    return [
        *public_places_in_boxes(db, [_box(lat, lng, _tour_radius(code)) for lat, lng, code in points], source=TOURAPI),
        *public_places_in_boxes(db, [_box(lat, lng, NEAR_RADIUS_M) for lat, lng, _ in points], source=SANGGA),
    ]


def _one_per_listing(near: list[tuple[PublicPlace, float]]) -> list[tuple[PublicPlace, float]]:
    """같은 출처에 이름 열쇠 · 주소 · 분류가 같은 줄이 여럿이면(상가정보 중복 등록) 가까운 하나만 남긴다(결정 27).
    주소가 빈 줄은 같은 곳인지 알 수 없어 묶지 않는다. 분류가 다르거나 출처가 다르면 그대로 둘이다(결정 15)."""

    seen: set[tuple[str, str, str, str]] = set()
    kept: list[tuple[PublicPlace, float]] = []
    for place, distance in near:   # 가까운 순
        address = (place.address or "").strip()
        listing = (place.source, place.name_key, address, place.category)
        if address and listing in seen:
            continue
        seen.add(listing)
        kept.append((place, distance))
    return kept


def _near(latitude: float, longitude: float, category_code: str | None, places: Iterable[PublicPlace]) -> list[tuple[PublicPlace, float]]:
    """반경 안의 장소를 가까운 순으로(TourAPI 는 분류에 따라 1km · 200m, 상가정보는 200m), 같은 줄은 하나로."""

    tour_radius = _tour_radius(category_code)
    near: list[tuple[PublicPlace, float]] = []
    for place in places:
        distance = distance_m(latitude, longitude, place.latitude, place.longitude)
        if distance <= (tour_radius if place.source == TOURAPI else NEAR_RADIUS_M):
            near.append((place, distance))
    near.sort(key=lambda pair: pair[1])
    return _one_per_listing(near)


def _decide(key: str, near: list[tuple[PublicPlace, float]], category_code: str | None) -> PlaceMatch:
    """바로 담기는 이름이 같은 곳이 반경 안에 하나뿐이고 분류가 맞을 때만. 같은 이름이 여럿이거나 이름 일부만 겹치면 후보(가까운 순 3곳)."""

    exact = [pair for pair in near if pair[0].name_key == key]
    if exact:
        if len(exact) == 1 and _fits(category_code, exact[0][0]):
            return PlaceMatch("match", exact)
        return PlaceMatch("candidates", exact[:MAX_CANDIDATES])
    if len(key) >= 2:
        loose = [pair for pair in near if len(pair[0].name_key) >= 2 and (key in pair[0].name_key or pair[0].name_key in key)]
        if loose:
            return PlaceMatch("candidates", loose[:MAX_CANDIDATES])
    return PlaceMatch("none", [])
```

`match_place_response` 바로 아래에 더한다.

```python
@dataclass(frozen=True)
class PlaceMatchInput:
    """미리 맞춤 한 줄 - 카카오 결과의 이름 · 좌표 · 분류. 맞춰 보는 동안만 쓰고 버린다(저장 · 로그 금지)."""

    name: str
    latitude: float
    longitude: float
    category_code: str | None


def match_places(db: Session, rows: Sequence[PlaceMatchInput | None]) -> list[dict[str, object] | None]:
    """검색 결과 여러 줄을 한 번에 맞춘다(결정 23) - 출처마다 질의 한 번으로 읽고 줄마다 match_place 와 같은 규칙으로 가린다.
    None 줄(좌표 없음)은 None, 한 줄을 가리다 실패하면 그 줄만 None 이다. DB 읽기가 실패하면 예외를 올린다 - 부른 쪽이 모든 줄을 None 으로 둔다."""

    live = [row for row in rows if row is not None and name_key(row.name)]
    places = _read_boxes(db, [(row.latitude, row.longitude, row.category_code) for row in live])
    answers: list[dict[str, object] | None] = []
    for row in rows:
        if row is None:
            answers.append(None)
            continue
        try:
            key = name_key(row.name)
            found = _decide(key, _near(row.latitude, row.longitude, row.category_code, places), row.category_code) if key else PlaceMatch("none", [])
            answers.append({"result": found.result, "places": [public_place_item(place, distance) for place, distance in found.places]})
        except Exception:   # 한 줄의 실패가 다른 줄의 답을 지우지 않게 - 값은 로그에 남기지 않는다
            answers.append(None)
    return answers
```

(`_decide` 는 모듈 이름으로 부른다 - 시험이 `public_places._decide` 를 바꿔 끼운다. 위 `match_places` 처럼 함수 안에서 이름을 찾으면 된다.)

`backend/app/services/trips.py` - 카카오 장소 타입을 들여온다.

찾기:

```python
from app.services.kakao_local import KakaoLocalClient, KakaoLocalConfigurationError, build_kakao_local_client
```

바꾸기:

```python
from app.services.kakao_local import KakaoLocalClient, KakaoLocalConfigurationError, KakaoLocalPlace, build_kakao_local_client
```

찾기:

```python
    try:
        places = provider.search_keyword(query=trimmed_query, size=10)
    except Exception:
        logger.warning("trip_place_search_failed trip=%s", trip_handle, exc_info=True)
        return []
    candidates: list[dict[str, object]] = []
    for place in places:
```

바꾸기:

```python
    try:
        places = provider.search_keyword(query=trimmed_query, size=PLACE_SEARCH_SIZE)
    except Exception:
        logger.warning("trip_place_search_failed trip=%s", trip_handle, exc_info=True)
        return []
    matches = _prematch(db, places)
    candidates: list[dict[str, object]] = []
    for place, public_match in zip(places, matches):
```

찾기:

```python
                "sourceProvider": "kakao",
                "externalPlaceId": place.external_place_id,
            }
        )
    return candidates
```

바꾸기:

```python
                "sourceProvider": "kakao",
                "externalPlaceId": place.external_place_id,
                "publicMatch": public_match,
            }
        )
    return candidates


PLACE_SEARCH_SIZE = 6   # 담기 창이 보이는 결과 수(시안 v61) - 줄마다 맞춰 보므로 더 받지 않는다


def _prematch(db: Session, places: list[KakaoLocalPlace]) -> list[dict[str, object] | None]:
    """검색 결과를 우리 장소 기반과 한 번에 미리 맞춰 본다(결정 23). 카카오 값은 이 안에서 견주고 버린다 - 저장 · 로그 금지.
    세션은 카카오를 부르기 전에 놓았다(_release_session) - SQLAlchemy 2 의 Session 은 close 뒤 다시 쓰면 새 연결을 잡는다(실제 Session 시험이 붙잡는다).
    좌표가 없는 줄은 None. DB 읽기가 실패하면 모든 줄이 None 이고, 화면은 고른 뒤 예전처럼 맞춰 본다."""

    rows = [
        public_place_service.PlaceMatchInput(place.name, place.latitude, place.longitude, place.category_group_code)
        if place.latitude is not None and place.longitude is not None
        else None
        for place in places
    ]
    try:
        return public_place_service.match_places(db, rows)
    except Exception as error:
        logger.warning("trip_place_search_prematch_failed error=%s", type(error).__name__)   # 검색어 · 장소 값은 싣지 않는다
        return [None] * len(places)
```

`backend/app/schemas/trip.py` - 응답 필드.

찾기:

```python
    sourceProvider: str | None = "kakao"
    externalPlaceId: str | None = None


class InviteState(BaseModel):
```

바꾸기:

```python
    sourceProvider: str | None = "kakao"
    externalPlaceId: str | None = None
    # 결정 23: 서버가 같은 요청 안에서 맞춰 본 결과(POST /api/places/match 와 같은 모양). 늘 내보내고, 좌표가 없거나 실패하면 null
    publicMatch: PlaceMatchResponse | None = None


class InviteState(BaseModel):
```

같은 파일 위쪽 들여오기에 `from app.schemas.places import PlaceMatchResponse` 를 더한다(이미 `app.schemas.places` 를 들여오는 줄이 있으면 그 줄에 이름만 더한다).

`docs/mvp-api-contract.md` - `### GET /trips/{trip_id}/place-search` 절. 첫 문단의 한 줄 안에서 아래 문장만 바꾼다(앞뒤 문장은 그대로).

찾기:

```
A picked place is not saved as it is - the client matches it against our public places (`POST /places/match`) and saves a `publicPlace` reference or a user-written `customPlace` with `POST /trips/{trip_id}/days/{day_number}/places` (only the Kakao place id is kept, as `kakaoPlaceId`).
```

바꾸기:

```
A picked place is not saved as it is. Every row carries `publicMatch` (always present, possibly null): the server asks Kakao for 6 places (6곳) and, in the same request, matches all rows with coordinates against our public places in one batch - one read per source, the same rules and the same shape as `POST /places/match`; the Kakao values are compared in memory and discarded. `publicMatch` is null for a row without coordinates, for a row whose matching failed, and for every row when the read fails - the client then matches the picked row with `POST /places/match`. The client saves a `publicPlace` reference or a user-written `customPlace` with `POST /trips/{trip_id}/days/{day_number}/places` (only the Kakao place id is kept, as `kakaoPlaceId`).
```

찾기:

```
    "sourceProvider": "kakao",
    "externalPlaceId": "12345"
  }
]
```

바꾸기:

```
    "sourceProvider": "kakao",
    "externalPlaceId": "12345",
    "publicMatch": {
      "result": "match",
      "places": [
        {
          "source": "tourapi",
          "sourceId": "126437",
          "name": "성산일출봉",
          "address": "제주특별자치도 서귀포시 성산읍 일출로 284-12",
          "latitude": 33.4583,
          "longitude": 126.9425,
          "category": "sight",
          "sido": "제주",
          "city": "서귀포",
          "photoUrl": null,
          "photoLicense": null,
          "distanceMeters": 22
        }
      ]
    }
  }
]
```

(찾을 글이 이 절 밖에도 있으면 이 절의 것만 바꾼다.)

`.agent/evals/api-contract-golden.json` - `GET /api/trips/1/place-search` 항목. `requiredArrayItemFields` 에 `"publicMatch": "object|null"` 을 더하고(늘 있는 필드라 선택 필드가 아니다 - 코덱스 검토), `dbModeBehavior` 의 `A picked place is matched against public places (POST /api/places/match) and saved` 를 `Every row carries publicMatch (always present, possibly null) - Kakao is asked for 6 places and all rows with coordinates are matched against public places in one batch in the same request (one read per source, same rules and shape as POST /api/places/match); null for a row without coordinates or whose matching failed, and for every row when the read fails, in which case the client matches the picked row itself. A picked place is saved` 로 바꾼다. JSON 은 `json.load` → 고침 → `json.dump(..., ensure_ascii=False, indent=2)` 로 쓰고 파일 끝 줄바꿈과 기존 들여쓰기를 지킨다(`git diff` 가 그 항목만 보이는지 본다).

`docs/superpowers/specs/2026-10-03-public-place-storage-design.md` - 2절 2번(코덱스 검토: 승인된 설계는 고른 뒤에만 맞춰 본다고 적었다).

찾기:

```
(실측과 같은 기준). 받은 값은 저장하거나 로그에 남기지 않는다.
```

바꾸기:

```
(실측과 같은 기준). 받은 값은 저장하거나 로그에 남기지 않는다. 일정 안 추가 창은 검색 결과 6곳을 검색 요청 안에서 한꺼번에 맞춰(출처마다 질의 한 번, 같은 규칙) 줄마다 갈래를 미리 보인다 - 고르면 그 갈래로 바로 간다(3단계 결정 23 · 24). 좌표가 없거나 미리 맞춤이 실패한 줄과 홈 넘김은 고른 뒤 맞춰 보기 API 를 부른다. 같은 출처에 이름 열쇠 · 주소 · 분류가 같은 줄은 한 곳으로 센다(결정 27).
```

- [ ] **4단계: 통과하는지 확인(백엔드)**

실행: 2단계와 같은 명령.
기대: PASS - 네 파일 전부.

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --deselect tests/test_stay_discount_semantics_snapshot.py`
기대: 과제 2 ~ 8 뒤 1,329개에 새 시험 열하나(`test_public_places` 여덟 - 같은 줄 셋 · 묶음 넷 · 실제 세션 하나, 검색 서비스 둘, 계약 문서 하나)를 더한 1,340개가 통과한다. 라우트 시험은 기존 시험에 확인을 더했다.

- [ ] **5단계: 로컬 PostgreSQL 실측(읽기 전용, 코덱스 검토 - 화면을 만들기 전에 구조를 확정한다)**

로컬 DB(`travel-hunter-onprem-db-1`, `public_places` 108만 행)에 묶음 질의 두 개를 `EXPLAIN (ANALYZE, BUFFERS)` 로 돌린다. 좌표는 공공 장소 여섯 곳(명동 · 종로 · 해운대 · 오동도 · 죽녹원 · 성산일출봉)이고 상자는 `_box` 와 같은 식이다. 관광명소 · 문화시설은 TourAPI 1km, 그 밖은 200m 다 - 여기서는 가장 무거운 경우로 여섯 곳 모두 1km(TourAPI) · 200m(상가정보)로 잰다.

실행(Git Bash):

```bash
python - <<'PY' > "$TEMP/prematch_explain.sql"
import math
R = 6_371_000 * math.pi / 180
pts = [(37.5633, 126.9873), (37.5700, 126.9830), (35.1587, 129.1604), (34.7443, 127.7663), (35.3270, 126.9860), (33.4583, 126.9425)]
def box(lat, lng, m):
    dlat = m * 1.01 / R
    dlng = dlat / math.cos(math.radians(lat + dlat))
    return f"(latitude between {lat - dlat:.6f} and {lat + dlat:.6f} and longitude between {lng - dlng:.6f} and {lng + dlng:.6f})"
for source, meters in (("tourapi", 1000), ("sangga", 200)):
    print(f"explain (analyze, buffers) select * from public_places where source = '{source}' and (" + " or ".join(box(a, b, meters) for a, b in pts) + ");")
PY
docker exec -i travel-hunter-onprem-db-1 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' < "$TEMP/prematch_explain.sql" | grep -E "Execution Time|Index Scan|Seq Scan|rows="
rm -f "$TEMP/prematch_explain.sql"
```

기대: 두 질의 모두 `ix_public_places_lat_lng` 를 쓰고(`Bitmap Index Scan`, `Seq Scan` 없음), 같은 질의를 한 번 더 돌린 값(캐시에 있을 때)의 `Execution Time` 이 각각 50ms 이하다. 처음 값(캐시가 빈 때)도 적는다 - 10/6 실행: 처음 TourAPI 1,567ms · 상가정보 709ms(디스크 읽기), 다시 돌린 값 7 ~ 15ms · 2ms. 로컬 처음 값은 윈도우 도커 디스크 탓이 커서 사용자 결정(10/6)으로 기준을 '캐시가 찬 뒤'로 두고, 처음 값은 머지 뒤 개발서버에서 잰다(아래 '머지 뒤 서버 작업'). 결과(두 시간 · 읽은 행 수)를 실행 기록에 적는다. 넘으면 멈추고 보고한다 - 그때는 상자를 줄마다 따로 읽는 대신 반경을 줄이거나 밀집 지역에서 상가정보 상자를 100m 로 좁히는 안을 계획에 더해 다시 확인받는다.

- [ ] **6단계: 실패하는 시험 쓰기(프론트)**

`frontend/src/components/itinerary/placeAdd/publicPlaceText.test.ts` - 들여오는 이름에 `publicMatchBadge` 를 더하고 끝에 붙인다.

찾기:

```ts
import { PUBLIC_CATEGORY_LABEL, distanceText, photoCredit, publicTimeSlotGroup } from "./publicPlaceText";
```

바꾸기:

```ts
import { PUBLIC_CATEGORY_LABEL, distanceText, photoCredit, publicMatchBadge, publicTimeSlotGroup } from "./publicPlaceText";
```

파일 끝에 더한다.

```ts
describe("publicMatchBadge", () => {
  const place = { source: "tourapi", sourceId: "1", name: "죽녹원", latitude: 35.3, longitude: 126.9, category: "sight", distanceMeters: 3 } as const;

  it("says which path a search row will take (시안 v62)", () => {
    expect(publicMatchBadge({ result: "match", places: [place] })).toEqual({ tone: "ready", text: "바로 담기" });
    expect(publicMatchBadge({ result: "candidates", places: [place, place] })).toEqual({ tone: "similar", text: "비슷한 곳 2" });
    expect(publicMatchBadge({ result: "candidates", places: [place, place, place, place] })).toEqual({ tone: "similar", text: "비슷한 곳 3" });
    expect(publicMatchBadge({ result: "none", places: [] })).toEqual({ tone: "custom", text: "직접 적기" });
  });

  it("shows nothing for a row the server could not match, and treats an empty answer as none", () => {
    expect(publicMatchBadge(null)).toBeNull();
    expect(publicMatchBadge(undefined)).toBeNull();
    expect(publicMatchBadge({ result: "match", places: [] })).toEqual({ tone: "custom", text: "직접 적기" });
  });
});
```

`frontend/src/components/itinerary/placeAdd/usePlaceMatch.test.ts` - 파일 끝에 더한다(위쪽의 `odongdo` · `yeosuPark` · `kakaoPick` · `setup` 을 쓴다).

```ts
describe("usePlaceMatch with a prematch from the search (시안 v62)", () => {
  it("puts a ready row straight into the basket without asking the server again", async () => {
    const matchSpy = vi.spyOn(appDataApi, "matchPlace");
    const { onMatched, result } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick({ publicMatch: { result: "match", places: [odongdo] } }));
    });

    expect(matchSpy).not.toHaveBeenCalled();
    expect(onMatched).toHaveBeenCalledTimes(1);
    expect(onMatched.mock.calls[0][0]).toMatchObject({ kind: "public", place: odongdo, kakaoPlaceId: "8193468" });
    expect(result.current.state).toEqual({ status: "idle" });
  });

  it("opens the candidates or the own-place form right away", async () => {
    const matchSpy = vi.spyOn(appDataApi, "matchPlace");
    const { result } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick({ publicMatch: { result: "candidates", places: [odongdo, yeosuPark] } }));
    });
    expect(result.current.state).toEqual({ status: "choose", kakaoPlaceId: "8193468", candidates: [odongdo, yeosuPark] });

    await act(async () => {
      await result.current.pick(kakaoPick({ id: "kakao:42", publicMatch: { result: "none", places: [] } }));
    });
    expect(result.current.state).toMatchObject({ status: "custom", kakaoPlaceId: "42", reason: "none" });
    expect(matchSpy).not.toHaveBeenCalled();
  });

  it("still asks the server when the search carried no prematch", async () => {
    const matchSpy = vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "none", places: [] } satisfies PlaceMatchResult);
    const { result } = setup();

    await act(async () => {
      await result.current.pick(kakaoPick({ publicMatch: null }));
    });

    expect(matchSpy).toHaveBeenCalledTimes(1);
    expect(result.current.state).toMatchObject({ status: "custom", reason: "none" });
  });
});
```

- [ ] **7단계: 실패하는지 확인(프론트)**

실행: `cd frontend && npx vitest run src/components/itinerary/placeAdd`
기대: FAIL - `publicMatchBadge` 가 없다(가져오기 오류), 미리 맞춤 시험 셋 중 앞의 둘은 `matchPlace` 가 불렸거나(`publicMatch` 를 읽지 않음) 형식 검사에서 `publicMatch` 가 `PlacePickInput` 에 없다고 나온다. 셋째는 지금도 통과한다.

- [ ] **8단계: 구현(프론트 경계 · 훅 · 문구)**

`frontend/src/api/types.ts` - 서버는 늘 내보내지만 프론트 타입은 선택으로 둔다(없거나 null 이면 같은 뜻 - 고른 뒤 묻는다. 필수로 하면 시험 고정값 열두 곳에 `publicMatch: null` 만 늘어난다).

찾기:

```ts
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
};

/** 통합 검색의 장소 한 곳(place) 또는 동 · 읍 · 면 구역(area). sido · city 는 서버가 주소로 가린 지도 도 · 시군 */
```

바꾸기:

```ts
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
  /** 결정 23: 서버가 검색과 같은 요청에서 맞춰 본 결과. 좌표가 없거나 실패하면 null */
  publicMatch?: PlaceMatchResult | null;
};

/** 통합 검색의 장소 한 곳(place) 또는 동 · 읍 · 면 구역(area). sido · city 는 서버가 주소로 가린 지도 도 · 시군 */
```

(`PlaceMatchResult` 는 같은 파일 아래쪽에 있다 - 타입이라 선언 순서와 상관없다.)

`frontend/src/components/itinerary/placeAdd/publicPlaceText.ts` - 첫 줄을 고치고 끝에 더한다.

찾기:

```ts
import type { PublicPlaceCategory } from "../../../api";
```

바꾸기:

```ts
import type { PlaceMatchResult, PublicPlaceCategory } from "../../../api";
```

끝에 더한다.

```ts
/* 검색 결과 줄 · 지도 미리보기에 붙이는 미리 맞춘 갈래(시안 v62). 맞춰 보지 못한 줄(null)은 표시가 없다.
   후보 수는 고른 뒤 보이는 후보 칸과 같게 3곳까지 센다 */
export type PublicMatchBadge = { tone: "ready" | "similar" | "custom"; text: string };

export function publicMatchBadge(match: PlaceMatchResult | null | undefined): PublicMatchBadge | null {
  if (!match) return null;
  if (match.result === "match" && match.places.length > 0) return { tone: "ready", text: "바로 담기" };
  if (match.result === "candidates" && match.places.length > 0)
    return { tone: "similar", text: `비슷한 곳 ${Math.min(match.places.length, 3)}` };
  return { tone: "custom", text: "직접 적기" };
}
```

`frontend/src/components/itinerary/placeAdd/usePlaceMatch.ts` - 홈 넘김처럼 미리 맞춤이 없는 입력은 `publicMatch` 를 두지 않는다(선택 칸, 코덱스 검토).

찾기:

```ts
/* pick 이 읽는 카카오 값은 이 다섯 칸뿐이다. 검색 후보(PlaceSearchCandidate)가 그대로 맞고,
   홈 넘김은 PlaceSearchItem 에서 { id, title: name, latitude, longitude, categoryCode } 를 만들어 넘긴다 */
export type PlacePickInput = Pick<PlaceSearchCandidate, "id" | "title" | "latitude" | "longitude" | "categoryCode">;
```

바꾸기:

```ts
/* pick 이 읽는 카카오 값은 이 다섯 칸뿐이다(+ 서버가 미리 맞춘 publicMatch - 공공데이터 값, 검색 후보에만 있다). 검색 후보(PlaceSearchCandidate)가 그대로 맞고,
   홈 넘김은 PlaceSearchItem 에서 { id, title: name, latitude, longitude, categoryCode } 를 만들어 넘긴다(publicMatch 없음 → 서버에 묻는다) */
export type PlacePickInput = Pick<PlaceSearchCandidate, "id" | "title" | "latitude" | "longitude" | "categoryCode"> & {
  publicMatch?: PlaceMatchResult | null;
};
```

찾기:

```ts
  const pick = useCallback(
    async (candidate: PlacePickInput): Promise<void> => {
      const turn = ++turnRef.current;
      const kakaoPlaceId = kakaoPlaceIdOf(candidate);
      const { latitude, longitude } = candidate;
```

바꾸기:

```ts
  /* 맞춰 본 답(서버가 미리 준 것이든 고른 뒤 물은 것이든)을 상태로 옮긴다 */
  const settle = useCallback(
    (answer: PlaceMatchResult, kakaoPlaceId: string | null, turn: number) => {
      const [first] = answer.places;
      if (answer.result === "match" && first) {
        commit(IDLE);
        onMatchedRef.current(publicBasketItem(first, kakaoPlaceId));
      } else if (answer.result === "candidates" && answer.places.length > 0) {
        commit({ status: "choose", kakaoPlaceId, candidates: answer.places.slice(0, 3) });
      } else {
        commit({ status: "custom", kakaoPlaceId, reason: "none", pickId: turn });
      }
    },
    [commit],
  );

  const pick = useCallback(
    async (candidate: PlacePickInput): Promise<void> => {
      const turn = ++turnRef.current;
      const kakaoPlaceId = kakaoPlaceIdOf(candidate);
      if (candidate.publicMatch) {
        // 결정 24: 검색 응답에 미리 맞춘 갈래가 있으면 '맞춰 보는 중' 없이 바로 간다
        settle(candidate.publicMatch, kakaoPlaceId, turn);
        return;
      }
      const { latitude, longitude } = candidate;
```

찾기:

```ts
      if (turnRef.current !== turn) return;
      const [first] = answer.places;
      if (answer.result === "match" && first) {
        commit(IDLE);
        onMatchedRef.current(publicBasketItem(first, kakaoPlaceId));
      } else if (answer.result === "candidates" && answer.places.length > 0) {
        commit({ status: "choose", kakaoPlaceId, candidates: answer.places.slice(0, 3) });
      } else {
        commit({ status: "custom", kakaoPlaceId, reason: "none", pickId: turn });
      }
    },
    [commit],
  );
```

바꾸기:

```ts
      if (turnRef.current !== turn) return;
      settle(answer, kakaoPlaceId, turn);
    },
    [commit, settle],
  );
```

- [ ] **9단계: 통과하는지 확인(프론트)**

실행: `cd frontend && npx vitest run src/components/itinerary/placeAdd src/api/backendApi.test.ts`
기대: PASS - 새 시험 다섯(문구 둘 · 훅 셋)을 포함해 전부.

실행: `cd frontend && npx tsc --noEmit -p .`
기대: 과제 7 뒤에 남은 `ItineraryDetailPage.tsx` 의 세 오류(과제 9 가 없앤다) 말고 새 오류 0건.

실행: `git diff --check` · 바꾼 파일의 U+FFFD 0건.

---

### Task 9: 담는 화면 - 후보 확인 · 나만의 장소 · 위치 찍기와 추가 시트 연결

**파일:**
- 만들기: `frontend/src/components/itinerary/PlacePhoto.tsx`와 `PlacePhoto.test.tsx`(공용 사진 부품 - 과제 11이 가져다 쓴다)
- 만들기: `frontend/src/components/itinerary/placeAdd/PlaceMatchChoices.tsx`, `CustomPlaceForm.tsx`, `MapPointPicker.tsx`, `PlaceMatchPanel.tsx`와 각각의 `.test.tsx`
- 고치기: `frontend/src/lib/kakaoMap.ts`, `frontend/src/test/kakaoMock.ts`
- 고치기: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`, `frontend/src/styles/app.css`
- 고치기(컴파일에 필요한 만큼만 - 과제 12의 파일): `frontend/src/api/dataApi.ts`(`TripPlaceRequest` 삭제), `frontend/src/utils/placeHandoff.ts`(`tripPlaceFromSearchItem`만 삭제)와 `placeHandoff.test.ts`(그 함수의 시험만 삭제)
- 고치기(옛 동작을 확인하던 시험): `frontend/src/app/__tests__/trip-detail.test.tsx`, `frontend/src/app/__tests__/trip-place-basket.test.tsx`, `frontend/e2e-backend/backend-mode.spec.ts`(추가 시트 확인 부분만)
- 건드리지 않는다(과제 12의 몫): `placeHandoff.ts`의 나머지, 홈 넘김 시험 쪽 개편, e2e 시드 두 곳(`backend-mode.spec.ts` 약 297 · `itinerary-cross-day-drag.spec.ts` 약 47).

**인터페이스:**
- 받는 것: 과제 7의 타입 · 메서드(`getTripAreaCenter` 포함), 과제 8의 `usePlaceMatch` · `placeBasket` · `photoCredit`.
- 내놓는 것:
  - `PlacePhoto({ url, license, alt, compact })`(`components/itinerary/PlacePhoto.tsx`, 공용) - `url`이 비면 아무것도 그리지 않고, 사진(불러오지 못하면 숨김)과 `photoCredit(license)` 출처 칩을 그린다. 클래스 `place-photo` · `place-photo-credit`, `compact`면 `place-photo--compact`가 더해진다. 서버가 받아 둔 사진 경로(`/api/media/...`)는 `mediaUrl`로 API 주소를 붙인다.
  - `PlaceMatchChoices({ candidates, onChoose, onNone })` - '이 장소가 맞나요?' 후보 1~3곳(이름 · 분류 · 주소 · 거리, 사진이 있으면 `PlacePhoto compact`로 작은 사진과 출처) + '아니요, 직접 적을게요'.
  - `CustomPlaceForm({ reason, tripId, fallbackCenter, onSubmit, onCancel })` - 빈 이름 칸(`name="custom-place-name"`, 라벨 '장소 이름'), 지도 키가 있을 때만 '지도에서 위치 찍기', 담기 · 취소. `onSubmit({ name, latitude, longitude })`(위치가 없으면 둘 다 `null`). 위치 찍기를 닫으면(고르기 · 취소) 초점을 '다시 찍기' · '지도에서 위치 찍기' 단추로 되돌린다.
  - `MapPointPicker({ tripId, fallbackCenter, onPick, onCancel })` - 일정 지역 중심(`getTripAreaCenter`, 없으면 `fallbackCenter`, 그것도 없으면 대한민국 중심 36.5, 127.8)에서 연다. 카카오 좌표를 받는 인자가 아예 없다. **십자선은 지도 가운데에 고정**이고(핀을 꽂지 않는다) 지도를 끌거나 누르면(`setCenter`) 십자선 밑으로 온다. 지도 칸은 초점을 받고(`role="application"`, 이름 '위치 고르기 지도', 열리면 초점을 둔다) **방향키로 `panBy` 60px**, **`+`(`=`) · `-` 로 `setLevel` 한 단계(1 ~ 14 안)**, **Enter 나 '이 위치로'가 `getCenter()` 를 고른다**(지도가 뜨면 단추가 켜진다). 지도가 멈출 때(`idle`)마다 가운데를 읽어 `role="status"` 한 줄로 알린다 - 대한민국 안이면 위도 · 경도(화면에는 숨김), 밖이면 '대한민국 밖이에요. 대한민국 안으로 옮겨 주세요.'를 보이고 '이 위치로' · Enter 를 막는다(서버 `customPlace` 범위와 같은 위도 33 ~ 39, 경도 124 ~ 132). `pickerStart(area, fallback)`, `firstPublicPlacePoint(days)`, `KOREA_CENTER`, `type MapPoint`도 내보낸다.
  - `PlaceMatchPanel({ state, tripId, fallbackCenter, onChooseCandidate, onChooseCustom, onStartDirect, onSubmitCustom, onCancel })` - `PlaceMatchState`에 따라 직접 적기 입구 · 맞춰 보는 중 · 후보 확인 · 나만의 장소 칸 중 하나를 그린다(계약 밖 추가: 추가 시트에 `matchPanel` 한 칸으로 꽂으려고 갈래 고르기를 한곳에 모았다). 나만의 장소 칸은 `state.pickId` 를 `key` 로 써서 고를 때마다 새로 연다.
  - `PlaceEditorSheet`의 새 선택 props `matchPanel?: ReactNode`, `hidePreview?: boolean`(맞춰 보는 동안 지도 미리보기를 접는다). 시트는 `error` 가 `STALE_SCREEN_MESSAGE` 일 때만 '새로 고침' 단추를 더 그린다(새 prop 없음).
  - `lib/kakaoMap.ts` 타입: `LatLng.getLat/getLng`, 지도 클릭 이벤트(`event.latLng`), `Map.getCenter` · `Map.panBy` · `Map.getLevel` · `Map.setLevel`. (`Map.setCenter`는 이미 있다. 가운데 고정 십자선이라 `Marker.setPosition`은 더하지 않는다 - 계약 문구 '누른 곳에 핀'에서 벗어난다.)
  - `PlaceMatchState`의 `custom` 갈래에 `pickId: number`(계약 밖 추가) - 칸을 열 때마다 달라지는 번호다(`usePlaceMatch` 의 `turnRef` 를 그대로 쓴다).
  - 페이지 안(내보내지 않는다): `STALE_SCREEN_MESSAGE` · `isStaleScreenError(error)`(HTTP 422 이고 응답 `detail` 의 오류 종류가 `extra_forbidden` · `missing` 일 때 - 이름 길이 · 시간 형식 같은 값 오류의 422 는 일반 문구다) - 추가 창 묶음 저장이 요청 모양 때문에 거절되면 일반 문구 대신 '화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.' 와 '새로 고침' 단추(`window.location.reload()`)를 보인다. 과제 10 이 수정 저장 · 예전 행 바꾸기에도 같은 것을 쓴다.
  - 검색 실패 안내(페이지 안): 일정 안 장소 검색(`GET /trips/{id}/place-search`)이 503(`Place search is unavailable` - 카카오를 켜 두고 설정이 틀린 경우)이면 '장소 검색을 지금 쓸 수 없어요. 직접 적기로 담을 수 있어요.' 를 보이고(시안 v59), 그 밖의 실패는 지금 문구('장소 검색 결과를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.')다. 둘 다 '검색 결과가 없어요'(빈 목록)와 다른 상태이고, '찾는 곳이 없어요 · 직접 적기' 입구는 검색 상태와 상관없이 쓸 수 있다.
- 지켜야 할 것: 나만의 장소 칸은 카카오 이름을 미리 채우지도 옆에 보이지도 않는다. 위치 없는 결과를 연달아 골라도 앞 장소에 적던 이름이 새 카카오 ID 에 붙지 않는다(칸을 새로 연다). 맞춰 보는 중이거나 후보 · 나만의 장소 칸이 열려 있으면 지도 미리보기를 접어 카카오 이름이 칸 옆에 남지 않게 한다. 담기 요청은 `basketItemPayload`만 쓴다. 위치 찍기는 마우스 없이 키보드만으로도 끝낼 수 있고(확대 · 축소 포함), 옮긴 뒤 가운데가 상태 한 줄로 알려진다. 대한민국 밖은 고르지 않는다.
- 시안 v59: 아래 문구 · 클래스 중 `시안 v59` 주석이 달린 것은 시안이 확정한다.

- [ ] **1단계: 실패하는 시험 쓰기**

먼저 지도 시험 도구(`kakaoMock`)를 위치 찍기 시험에 맞게 넓힌다. 지도가 가운데를 기억하게 하고(`setCenter`로 바꾸고 `getCenter`로 읽는다, `panBy`는 부른 것만 기록한다), 지도 누르기를 흉내 내는 `emitMapClick`, 지도 끌기를 흉내 내는 `dragMapTo`(`setCenter`를 거치지 않고 가운데만 옮긴다), 지도가 멈춘 것을 흉내 내는 `emitMapIdle`, 확대 수준을 기억하는 `getLevel` · `setLevel`, `LatLng.getLat/getLng`을 더한다. 기존 시험이 쓰던 반환 값(`mapInstances` 길이 · `markerInstances` 길이 · `customOverlayInstances[i].options`)은 그대로다.

**새 파일 `frontend/src/test/kakaoMock.ts`** - 같은 이름의 파일을 통째로 바꾼다.

```ts
import { vi } from "vitest";

type MockLatLng = { lat: number; lng: number; getLat: () => number; getLng: () => number };
type MockMarker = { setMap: ReturnType<typeof vi.fn> };
type MockMap = {
  setBounds: ReturnType<typeof vi.fn>;
  setCenter: ReturnType<typeof vi.fn>;
  getCenter: ReturnType<typeof vi.fn>;
  panBy: ReturnType<typeof vi.fn>;
  getLevel: ReturnType<typeof vi.fn>;
  setLevel: ReturnType<typeof vi.fn>;
};

const makeLatLng = (lat: number, lng: number): MockLatLng => ({ lat, lng, getLat: () => lat, getLng: () => lng });

export function installAppKakaoSdkMock({
  resolvedLatitude = "35.096",
  resolvedLongitude = "129.03",
}: {
  resolvedLatitude?: string;
  resolvedLongitude?: string;
} = {}) {
  const addressQueries: string[] = [];
  const keywordQueries: string[] = [];
  const mapInstances: Array<{
    container: HTMLElement;
    options: Record<string, unknown>;
    map: MockMap;
    /** 사용자가 지도를 끌어 가운데를 옮긴 것을 흉내 낸다 - setCenter 를 부르지 않는다 */
    moveCenter: (latitude: number, longitude: number) => void;
  }> = [];
  const markerInstances: Array<{ marker: MockMarker; options: Record<string, unknown> }> = [];
  const customOverlayInstances: Array<{
    overlay: { setMap: ReturnType<typeof vi.fn> };
    options: Record<string, unknown>;
  }> = [];
  const eventListeners: Array<{ target: unknown; eventName: string; handler: (event: unknown) => void }> = [];

  function LatLng(this: MockLatLng, lat: number, lng: number) {
    Object.assign(this, makeLatLng(lat, lng));
  }

  function LatLngBounds(this: { extend: ReturnType<typeof vi.fn> }) {
    this.extend = vi.fn();
  }

  /* 가운데와 확대 수준을 기억하는 지도 - setCenter · setLevel 로 바꾸고 getCenter · getLevel 로 읽는다. panBy 는 부른 것만 기록한다(픽셀을 좌표로 바꾸지 않는다) */
  function Map(this: MockMap, container: HTMLElement, options: Record<string, unknown>) {
    let center = (options.center as MockLatLng | undefined) ?? makeLatLng(0, 0);
    this.setBounds = vi.fn();
    this.setCenter = vi.fn((next: MockLatLng) => {
      center = next;
    });
    this.getCenter = vi.fn(() => center);
    this.panBy = vi.fn();
    let level = (options.level as number | undefined) ?? 3;
    this.getLevel = vi.fn(() => level);
    this.setLevel = vi.fn((next: number) => {
      level = next;
    });
    mapInstances.push({
      container,
      options,
      map: this,
      moveCenter: (latitude, longitude) => {
        center = makeLatLng(latitude, longitude);
      },
    });
  }

  function Marker(this: MockMarker, options: Record<string, unknown>) {
    this.setMap = vi.fn();
    markerInstances.push({ marker: this, options });
  }

  function CustomOverlay(
    this: { setMap: ReturnType<typeof vi.fn> },
    options: Record<string, unknown>,
  ) {
    this.setMap = vi.fn();
    customOverlayInstances.push({ overlay: this, options });
  }

  const addressSearch = vi.fn(
    (
      query: string,
      callback: (
        results: Array<{ x: string; y: string }>,
        status: string,
      ) => void,
    ) => {
      addressQueries.push(query);
      callback([], "ZERO_RESULT");
    },
  );
  const keywordSearch = vi.fn(
    (
      query: string,
      callback: (
        results: Array<{ x: string; y: string }>,
        status: string,
      ) => void,
    ) => {
      keywordQueries.push(query);
      callback([{ x: resolvedLongitude, y: resolvedLatitude }], "OK");
    },
  );

  window.kakao = {
    maps: {
      LatLng,
      LatLngBounds,
      Map,
      Marker,
      CustomOverlay,
      event: {
        addListener: vi.fn((target: unknown, eventName: string, handler: (event: unknown) => void) => {
          eventListeners.push({ target, eventName, handler });
        }),
      },
      services: {
        Status: { OK: "OK" },
        Geocoder: function Geocoder(this: {
          addressSearch: typeof addressSearch;
        }) {
          this.addressSearch = addressSearch;
        },
        Places: function Places(this: { keywordSearch: typeof keywordSearch }) {
          this.keywordSearch = keywordSearch;
        },
      },
      load: vi.fn((callback: () => void) => callback()),
    },
  } as unknown as Window["kakao"];

  /** 지도(마커가 아니다)를 눌렀을 때를 흉내 낸다 - 위치 찍기 시험용. 상태를 바꾸므로 act 로 감싸 부른다 */
  function emitMapClick(latitude: number, longitude: number) {
    const event = { latLng: makeLatLng(latitude, longitude) };
    for (const listener of eventListeners) {
      const onMap = mapInstances.some((entry) => entry.map === listener.target);
      if (listener.eventName === "click" && onMap) listener.handler(event);
    }
  }

  /** 가장 나중에 만든 지도를 끌어 가운데가 이 자리로 온 것처럼 만든다(setCenter 를 거치지 않는다) */
  function dragMapTo(latitude: number, longitude: number) {
    mapInstances[mapInstances.length - 1]?.moveCenter(latitude, longitude);
  }

  /** 지도가 옮겨 가거나 확대 수준이 바뀐 뒤 멈춘 것(idle)을 흉내 낸다 - 위치 찍기 알림 시험용. 상태를 바꾸므로 act 로 감싸 부른다 */
  function emitMapIdle() {
    for (const listener of eventListeners) {
      const onMap = mapInstances.some((entry) => entry.map === listener.target);
      if (listener.eventName === "idle" && onMap) listener.handler(undefined);
    }
  }

  return {
    addressQueries,
    addressSearch,
    customOverlayInstances,
    dragMapTo,
    emitMapClick,
    emitMapIdle,
    eventListeners,
    keywordQueries,
    keywordSearch,
    mapInstances,
    markerInstances,
  };
}
```

**새 파일 `frontend/src/components/itinerary/PlacePhoto.test.tsx`**

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { apiConfig } from "../../api";
import { PlacePhoto } from "./PlacePhoto";

const url = "https://tong.visitkorea.or.kr/cms/resource/23/3074123_image2_1.jpg";

describe("PlacePhoto", () => {
  it("renders nothing without a url", () => {
    const { container, rerender } = render(<PlacePhoto alt="오동도" license="Type1" url={null} />);
    expect(container).toBeEmptyDOMElement();

    rerender(<PlacePhoto alt="오동도" license="Type1" url={undefined} />);
    expect(container).toBeEmptyDOMElement();

    rerender(<PlacePhoto alt="오동도" license="Type1" url="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the photo with its credit chip", () => {
    const { container } = render(<PlacePhoto alt="오동도 전경" license="Type1" url={url} />);

    const photo = screen.getByRole("img", { name: "오동도 전경" });
    expect(photo).toHaveAttribute("src", url);
    expect(container.querySelector(".place-photo")).not.toBeNull();
    expect(container.querySelector(".place-photo--compact")).toBeNull();
    expect(container.querySelector(".place-photo-credit")).toHaveTextContent("사진: 한국관광공사");
  });

  it("adds the no-change notice for a Type3 photo", () => {
    const { container } = render(<PlacePhoto alt="" license="Type3" url={url} />);

    expect(container.querySelector(".place-photo-credit")).toHaveTextContent("사진: 한국관광공사 · 변경 금지");
  });

  it("adds the compact modifier", () => {
    const { container } = render(<PlacePhoto alt="" compact license="Type1" url={url} />);

    expect(container.querySelector(".place-photo")).toHaveClass("place-photo--compact");
  });

  it("puts the API address in front of a photo the server stored", () => {
    render(<PlacePhoto alt="저장한 사진" license="Type1" url="/api/media/policy-photos/1.jpg" />);

    expect(screen.getByRole("img", { name: "저장한 사진" })).toHaveAttribute(
      "src",
      `${apiConfig.baseUrl}/api/media/policy-photos/1.jpg`,
    );
  });

  it("hides the photo and its credit when the image fails to load", () => {
    const { container } = render(<PlacePhoto alt="오동도" license="Type1" url={url} />);

    fireEvent.error(screen.getByRole("img", { name: "오동도" }));

    expect(container).toBeEmptyDOMElement();
  });

  it("tries the next url after a failure", () => {
    const { container, rerender } = render(<PlacePhoto alt="오동도" license="Type1" url={url} />);
    fireEvent.error(screen.getByRole("img", { name: "오동도" }));
    expect(container).toBeEmptyDOMElement();

    rerender(<PlacePhoto alt="오동도" license="Type1" url={`${url}?v=2`} />);

    expect(screen.getByRole("img", { name: "오동도" })).toHaveAttribute("src", `${url}?v=2`);
  });
});
```

**새 파일 `frontend/src/components/itinerary/placeAdd/PlaceMatchChoices.test.tsx`**

```tsx
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { PublicPlaceItem } from "../../../api";
import { PlaceMatchChoices } from "./PlaceMatchChoices";

const withPhoto: PublicPlaceItem = {
  source: "tourapi",
  sourceId: "126508",
  name: "오동도",
  address: "전남 여수시 오동도로 222",
  latitude: 34.7443,
  longitude: 127.7663,
  category: "sight",
  photoUrl: "https://tong.visitkorea.or.kr/cms/resource/23/3074123_image2_1.jpg",
  photoLicense: "Type3",
  distanceMeters: 4,
};
const withoutPhoto: PublicPlaceItem = {
  source: "sangga",
  sourceId: "MA010120220800000002",
  name: "오동도 공원",
  address: "전남 여수시 수정동 1",
  latitude: 34.745,
  longitude: 127.766,
  category: "culture",
  distanceMeters: 340,
};

function renderChoices(onChoose = vi.fn(), onNone = vi.fn()) {
  render(<PlaceMatchChoices candidates={[withPhoto, withoutPhoto]} onChoose={onChoose} onNone={onNone} />);
  return screen.getByRole("region", { name: "이 장소가 맞나요?" });
}

describe("PlaceMatchChoices", () => {
  it("lists each candidate with its name, category, address and distance", () => {
    const group = renderChoices();

    const first = within(group).getByRole("button", { name: "오동도 선택" });
    expect(first).toHaveTextContent("관광지");
    expect(first).toHaveTextContent("전남 여수시 오동도로 222");
    expect(first).toHaveTextContent("고른 곳과 같은 자리");
    const second = within(group).getByRole("button", { name: "오동도 공원 선택" });
    expect(second).toHaveTextContent("문화시설");
    expect(second).toHaveTextContent("고른 곳에서 약 340m");
  });

  it("shows a small photo with its credit only for a candidate that has a photo", () => {
    const group = renderChoices();

    const first = within(group).getByRole("button", { name: "오동도 선택" });
    expect(first.querySelector("img")).toHaveAttribute("src", withPhoto.photoUrl);
    expect(first).toHaveTextContent("사진: 한국관광공사 · 변경 금지");
    const second = within(group).getByRole("button", { name: "오동도 공원 선택" });
    expect(second.querySelector("img")).toBeNull();
    expect(second).not.toHaveTextContent("사진:");
  });

  it("hides a photo that fails to load together with its credit", () => {
    const group = renderChoices();
    const first = within(group).getByRole("button", { name: "오동도 선택" });

    fireEvent.error(first.querySelector("img") as HTMLImageElement);

    expect(first.querySelector("img")).toBeNull();
    expect(first).not.toHaveTextContent("사진:");
  });

  it("reports the candidate the user picked", () => {
    const onChoose = vi.fn();
    const group = renderChoices(onChoose);

    fireEvent.click(within(group).getByRole("button", { name: "오동도 공원 선택" }));

    expect(onChoose).toHaveBeenCalledExactlyOnceWith(withoutPhoto);
  });

  it("offers to write the place by hand when none of the candidates is right", () => {
    const onNone = vi.fn();
    const group = renderChoices(vi.fn(), onNone);

    fireEvent.click(within(group).getByRole("button", { name: "아니요, 직접 적을게요" }));

    expect(onNone).toHaveBeenCalledTimes(1);
  });
});
```

**새 파일 `frontend/src/components/itinerary/placeAdd/MapPointPicker.test.tsx`**

```tsx
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { appDataApi, type ItineraryPlace } from "../../../api";
import { installAppKakaoSdkMock } from "../../../test/kakaoMock";
import { KOREA_CENTER, MapPointPicker, firstPublicPlacePoint, pickerStart } from "./MapPointPicker";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  delete window.kakao;
});

function openPicker(area: { latitude: number | null; longitude: number | null } | Error, fallbackCenter = null as null | { latitude: number; longitude: number }) {
  vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
  const kakao = installAppKakaoSdkMock();
  const spy = vi.spyOn(appDataApi, "getTripAreaCenter");
  if (area instanceof Error) spy.mockRejectedValue(area);
  else spy.mockResolvedValue(area);
  const onPick = vi.fn();
  const onCancel = vi.fn();
  render(<MapPointPicker fallbackCenter={fallbackCenter} onCancel={onCancel} onPick={onPick} tripId="7" />);
  return { kakao, onPick, onCancel, spy };
}

describe("MapPointPicker", () => {
  it("opens on the trip area center with a fixed crosshair and picks the point the crosshair ends on", async () => {
    const { kakao, onPick, spy } = openPicker({ latitude: 34.76, longitude: 127.66 });

    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    expect(spy).toHaveBeenCalledWith("7");
    expect(kakao.mapInstances[0].options).toMatchObject({ center: { lat: 34.76, lng: 127.66 }, level: 6 });
    // 핀을 꽂지 않는다 - 십자선은 지도 가운데에 고정돼 있고 스크린 리더에는 숨긴다
    expect(document.querySelector(".map-point-picker-pin")).toHaveAttribute("aria-hidden", "true");
    expect(kakao.markerInstances).toHaveLength(0);
    // 가운데는 늘 있으므로 지도가 뜨면 바로 고를 수 있다
    const confirm = screen.getByRole("button", { name: "이 위치로" });
    await waitFor(() => expect(confirm).toBeEnabled());

    kakao.dragMapTo(34.7443123456, 127.7663987654);
    await userEvent.click(confirm);

    // 소수 여섯 자리까지만 남긴다
    expect(onPick).toHaveBeenCalledExactlyOnceWith({ latitude: 34.744312, longitude: 127.766399 });
  });

  it("moves the center to the clicked point instead of dropping a pin", async () => {
    const { kakao, onPick } = openPicker({ latitude: 34.76, longitude: 127.66 });
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));

    act(() => kakao.emitMapClick(34.7, 127.6));
    act(() => kakao.emitMapClick(34.8, 127.7));

    const { setCenter } = kakao.mapInstances[0].map;
    expect(setCenter).toHaveBeenCalledTimes(2);
    expect(setCenter.mock.calls[1][0].getLat()).toBe(34.8);
    expect(kakao.markerInstances).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", { name: "이 위치로" }));
    expect(onPick).toHaveBeenCalledExactlyOnceWith({ latitude: 34.8, longitude: 127.7 });
  });

  it("is a labelled map the keyboard can use: focus on open, arrow keys pan, Enter picks the center", async () => {
    const { kakao, onPick } = openPicker({ latitude: 34.76, longitude: 127.66 });
    const user = userEvent.setup();

    const map = await screen.findByRole("application", { name: "위치 고르기 지도" });
    expect(map).toHaveAttribute("tabindex", "0");
    expect(map).toHaveAccessibleDescription(/방향키/);
    await waitFor(() => expect(map).toHaveFocus());

    await user.keyboard("{ArrowRight}{ArrowDown}{ArrowLeft}{ArrowUp}");
    expect(kakao.mapInstances[0].map.panBy.mock.calls).toEqual([
      [60, 0],
      [0, 60],
      [-60, 0],
      [0, -60],
    ]);

    // 지도가 옮겨 간 자리를 Enter 가 고른다 - 단추를 누른 것과 같다
    kakao.dragMapTo(34.771, 127.672);
    await user.keyboard("{Enter}");
    expect(onPick).toHaveBeenCalledExactlyOnceWith({ latitude: 34.771, longitude: 127.672 });
  });

  it("keeps the page from scrolling on handled keys and leaves browser shortcuts alone", async () => {
    const { kakao } = openPicker({ latitude: 34.76, longitude: 127.66 });
    const map = await screen.findByRole("application", { name: "위치 고르기 지도" });
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    const { panBy } = kakao.mapInstances[0].map;

    // fireEvent 는 기본 동작을 막았으면 false 를 돌려준다
    expect(fireEvent.keyDown(map, { key: "ArrowDown" })).toBe(false);
    expect(panBy).toHaveBeenCalledTimes(1);
    expect(fireEvent.keyDown(map, { key: "ArrowLeft", altKey: true })).toBe(true);
    expect(fireEvent.keyDown(map, { key: "a" })).toBe(true);
    expect(panBy).toHaveBeenCalledTimes(1);
  });

  it("zooms one level per + (or =) and -, and stops at the widest level", async () => {
    const { kakao } = openPicker(new Error("offline"));   // 대한민국 전체(수준 13)에서 연다
    const map = await screen.findByRole("application", { name: "위치 고르기 지도" });
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    const { setLevel } = kakao.mapInstances[0].map;

    // fireEvent 는 기본 동작을 막았으면 false 를 돌려준다 - 키가 쪽으로 새지 않는다
    expect(fireEvent.keyDown(map, { key: "+" })).toBe(false);
    fireEvent.keyDown(map, { key: "=" });
    fireEvent.keyDown(map, { key: "-" });
    fireEvent.keyDown(map, { key: "-" });
    fireEvent.keyDown(map, { key: "-" });
    fireEvent.keyDown(map, { key: "-" });   // 14 가 가장 넓다 - 더 부르지 않는다
    // Ctrl + - 는 브라우저 화면 축소라 건드리지 않는다
    expect(fireEvent.keyDown(map, { key: "-", ctrlKey: true })).toBe(true);
    expect(setLevel.mock.calls.map(([level]) => level)).toEqual([12, 11, 12, 13, 14]);
  });

  it("tells a screen reader where the center is each time the map stops, and will not pick outside Korea", async () => {
    const { kakao, onPick } = openPicker({ latitude: 34.76, longitude: 127.66 });
    const user = userEvent.setup();
    const map = await screen.findByRole("application", { name: "위치 고르기 지도" });
    await waitFor(() => expect(map).toHaveFocus());
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("지도 가운데 위도 34.7600, 경도 127.6600");

    // 방향키로 옮긴 지도가 멈추면(idle) 새 가운데를 알린다
    await user.keyboard("{ArrowUp}");
    kakao.dragMapTo(34.79, 127.66);
    act(() => kakao.emitMapIdle());
    expect(status).toHaveTextContent("지도 가운데 위도 34.7900, 경도 127.6600");

    // 가운데가 대한민국 밖(위도 39 너머)이면 그렇게 알리고, '이 위치로'도 Enter 도 고르지 않는다
    kakao.dragMapTo(40.2, 127.66);
    act(() => kakao.emitMapIdle());
    expect(status).toHaveTextContent("대한민국 밖이에요. 대한민국 안으로 옮겨 주세요.");
    expect(screen.getByRole("button", { name: "이 위치로" })).toBeDisabled();
    await user.keyboard("{Enter}");
    expect(onPick).not.toHaveBeenCalled();

    // 다시 안으로 옮기면 고를 수 있다
    kakao.dragMapTo(34.79, 127.66);
    act(() => kakao.emitMapIdle());
    expect(screen.getByRole("button", { name: "이 위치로" })).toBeEnabled();
    await user.keyboard("{Enter}");
    expect(onPick).toHaveBeenCalledExactlyOnceWith({ latitude: 34.79, longitude: 127.66 });
  });

  it("opens on the first public place of the trip when the area has no center", async () => {
    const { kakao } = openPicker({ latitude: null, longitude: null }, { latitude: 35.1, longitude: 129.03 });

    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    expect(kakao.mapInstances[0].options).toMatchObject({ center: { lat: 35.1, lng: 129.03 }, level: 6 });
  });

  it("opens on the middle of Korea when nothing else is known, and still opens if the center request fails", async () => {
    const { kakao } = openPicker(new Error("offline"));

    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    expect(kakao.mapInstances[0].options).toMatchObject({
      center: { lat: KOREA_CENTER.latitude, lng: KOREA_CENTER.longitude },
      level: 13,
    });
  });

  it("closes with cancel and says so when the map cannot load", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");   // 키가 없어 SDK 를 불러올 수 없다
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const onCancel = vi.fn();
    render(<MapPointPicker fallbackCenter={null} onCancel={onCancel} onPick={vi.fn()} tripId="7" />);

    expect(await screen.findByText(/지도를 불러오지 못했어요/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "취소" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "이 위치로" })).toBeDisabled();
  });
});

describe("pickerStart", () => {
  it("never starts from a Kakao point - area center, then the trip's own public place, then Korea", () => {
    expect(pickerStart({ latitude: 1, longitude: 2 }, { latitude: 3, longitude: 4 })).toEqual({
      center: { latitude: 1, longitude: 2 },
      level: 6,
    });
    expect(pickerStart({ latitude: null, longitude: null }, { latitude: 3, longitude: 4 })).toEqual({
      center: { latitude: 3, longitude: 4 },
      level: 6,
    });
    expect(pickerStart(null, null)).toEqual({ center: KOREA_CENTER, level: 13 });
  });
});

describe("firstPublicPlacePoint", () => {
  const place = (overrides: Partial<ItineraryPlace>): ItineraryPlace => ({ time: "", label: "장소", meta: "", ...overrides });

  it("takes the first public place with a point, in day order", () => {
    const days = {
      2: [place({ placeOrigin: "public", latitude: 35.2, longitude: 129.2 })],
      1: [
        place({ placeOrigin: "custom", latitude: 37, longitude: 127 }),
        place({ placeOrigin: "public", latitude: null, longitude: null }),
        place({ placeOrigin: "public", latitude: 34.1, longitude: 126.1 }),
      ],
    };

    expect(firstPublicPlacePoint(days)).toEqual({ latitude: 34.1, longitude: 126.1 });
  });

  it("is null when the trip has no public place with a point", () => {
    expect(firstPublicPlacePoint({ 1: [place({ placeOrigin: "custom", latitude: 37, longitude: 127 })] })).toBeNull();
    expect(firstPublicPlacePoint({ 1: [place({})] })).toBeNull();
    expect(firstPublicPlacePoint({})).toBeNull();
  });
});
```

**새 파일 `frontend/src/components/itinerary/placeAdd/CustomPlaceForm.test.tsx`**

```tsx
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { appDataApi } from "../../../api";
import { installAppKakaoSdkMock } from "../../../test/kakaoMock";
import { CustomPlaceForm, type CustomPlaceReason } from "./CustomPlaceForm";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  delete window.kakao;
});

function renderForm(reason: CustomPlaceReason = "none") {
  const onSubmit = vi.fn();
  const onCancel = vi.fn();
  render(<CustomPlaceForm fallbackCenter={null} onCancel={onCancel} onSubmit={onSubmit} reason={reason} tripId="7" />);
  return { onSubmit, onCancel, form: screen.getByRole("form", { name: "나만의 장소" }) };
}

describe("CustomPlaceForm", () => {
  it("starts with an empty name field that is not pre-filled or hinted with any place name", () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const { form } = renderForm();

    const name = within(form).getByLabelText("장소 이름");
    expect(name).toHaveValue("");
    expect(name).toHaveAttribute("name", "custom-place-name");
    expect(within(form).getByRole("button", { name: "담기" })).toBeDisabled();
  });

  it("explains why it opened", () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const expected: Record<CustomPlaceReason, RegExp> = {
      none: /같은 곳을 찾지 못했어요/,
      noCoords: /위치 정보가 없어서/,
      failed: /맞춰 보지 못했어요/,
      direct: /찾는 곳의 이름을 직접 적어/,
    };
    for (const [reason, text] of Object.entries(expected)) {
      const { unmount } = render(
        <CustomPlaceForm fallbackCenter={null} onCancel={vi.fn()} onSubmit={vi.fn()} reason={reason as CustomPlaceReason} tripId="7" />,
      );
      expect(screen.getByText(text)).toBeInTheDocument();
      unmount();
    }
  });

  it("submits the trimmed name without a point when no point was picked", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const { form, onSubmit } = renderForm();
    const user = userEvent.setup();

    await user.type(within(form).getByLabelText("장소 이름"), "  할머니 댁  ");
    await user.click(within(form).getByRole("button", { name: "담기" }));

    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "할머니 댁", latitude: null, longitude: null });
  });

  it("submits with Enter and ignores a blank name", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const { form, onSubmit } = renderForm("direct");
    const user = userEvent.setup();
    const name = within(form).getByLabelText("장소 이름");

    await user.type(name, "   {Enter}");
    expect(onSubmit).not.toHaveBeenCalled();

    await user.clear(name);
    await user.type(name, "숙소{Enter}");
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "숙소", latitude: null, longitude: null });
  });

  it("hides the map pin button when there is no map key", () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const { form } = renderForm();

    expect(within(form).queryByRole("button", { name: "지도에서 위치 찍기" })).not.toBeInTheDocument();
  });

  it("lets the user pick a point on the map and submits it with the name", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const { form, onSubmit } = renderForm();
    const user = userEvent.setup();

    await user.type(within(form).getByLabelText("장소 이름"), "내 쉼터");
    await user.click(within(form).getByRole("button", { name: "지도에서 위치 찍기" }));
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    act(() => kakao.emitMapClick(34.75, 127.65));
    await user.click(within(form).getByRole("button", { name: "이 위치로" }));

    expect(within(form).getByText("지도에서 위치를 찍었어요")).toBeInTheDocument();
    // 지도가 닫혀도 초점이 사라지지 않는다 - 다시 찍는 단추로 돌아온다
    expect(within(form).getByRole("button", { name: "다시 찍기" })).toHaveFocus();
    await user.click(within(form).getByRole("button", { name: "담기" }));

    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "내 쉼터", latitude: 34.75, longitude: 127.65 });
  });

  it("lets the user pick the point with the keyboard alone and puts the focus back on cancel", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const { form, onSubmit } = renderForm();
    const user = userEvent.setup();

    await user.type(within(form).getByLabelText("장소 이름"), "내 쉼터");
    await user.click(within(form).getByRole("button", { name: "지도에서 위치 찍기" }));
    // 지도가 열리면 지도에 초점이 있어 바로 방향키를 쓴다
    const map = await within(form).findByRole("application", { name: "위치 고르기 지도" });
    await waitFor(() => expect(map).toHaveFocus());
    await user.keyboard("{ArrowRight}");
    expect(kakao.mapInstances[0].map.panBy).toHaveBeenCalledWith(60, 0);
    kakao.dragMapTo(34.77, 127.67);
    await user.keyboard("{Enter}");

    expect(within(form).getByText("지도에서 위치를 찍었어요")).toBeInTheDocument();
    expect(within(form).getByRole("button", { name: "다시 찍기" })).toHaveFocus();
    await user.click(within(form).getByRole("button", { name: "담기" }));
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "내 쉼터", latitude: 34.77, longitude: 127.67 });
  });

  it("puts the focus back on the open-map button when the map is cancelled", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const { form } = renderForm();
    const user = userEvent.setup();

    await user.click(within(form).getByRole("button", { name: "지도에서 위치 찍기" }));
    await within(form).findByRole("application", { name: "위치 고르기 지도" });
    // 양식 자체의 취소와 지도의 취소가 둘 다 있다 - 지도 쪽을 누른다
    await user.click(within(within(form).getByRole("region", { name: "지도에서 위치 찍기" })).getByRole("button", { name: "취소" }));

    expect(within(form).queryByRole("application")).not.toBeInTheDocument();
    expect(within(form).getByRole("button", { name: "지도에서 위치 찍기" })).toHaveFocus();
  });

  it("lets the user clear a picked point before submitting", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 34.76, longitude: 127.66 });
    const { form, onSubmit } = renderForm();
    const user = userEvent.setup();

    await user.type(within(form).getByLabelText("장소 이름"), "내 쉼터");
    await user.click(within(form).getByRole("button", { name: "지도에서 위치 찍기" }));
    await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
    act(() => kakao.emitMapClick(34.75, 127.65));
    await user.click(within(form).getByRole("button", { name: "이 위치로" }));
    await user.click(within(form).getByRole("button", { name: "지우기" }));
    await user.click(within(form).getByRole("button", { name: "담기" }));

    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({ name: "내 쉼터", latitude: null, longitude: null });
  });

  it("cancels", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const { form, onCancel } = renderForm();

    await userEvent.click(within(form).getByRole("button", { name: "취소" }));

    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
```

**새 파일 `frontend/src/components/itinerary/placeAdd/PlaceMatchPanel.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { PublicPlaceItem, TripPlaceAddItem } from "../../../api";
import { basketItemPayload, customBasketItem } from "./placeBasket";
import { PlaceMatchPanel } from "./PlaceMatchPanel";
import { usePlaceMatch, type PlaceMatchState } from "./usePlaceMatch";

const odongdo: PublicPlaceItem = {
  source: "tourapi",
  sourceId: "126508",
  name: "오동도",
  address: "전남 여수시 오동도로 222",
  latitude: 34.7443,
  longitude: 127.7663,
  category: "sight",
  distanceMeters: 12,
};

afterEach(() => {
  vi.unstubAllEnvs();
});

function renderPanel(state: PlaceMatchState) {
  vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
  const handlers = {
    onChooseCandidate: vi.fn(),
    onChooseCustom: vi.fn(),
    onStartDirect: vi.fn(),
    onSubmitCustom: vi.fn(),
    onCancel: vi.fn(),
  };
  render(<PlaceMatchPanel {...handlers} fallbackCenter={null} state={state} tripId="7" />);
  return handlers;
}

describe("PlaceMatchPanel", () => {
  it("shows only the direct entry while idle", async () => {
    const { onStartDirect } = renderPanel({ status: "idle" });

    await userEvent.click(screen.getByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" }));

    expect(onStartDirect).toHaveBeenCalledTimes(1);
    expect(screen.queryByLabelText("장소 이름")).not.toBeInTheDocument();
  });

  it("says it is matching", () => {
    renderPanel({ status: "matching" });

    expect(screen.getByRole("status")).toHaveTextContent("맞춰 보는 중");
    expect(screen.queryByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" })).not.toBeInTheDocument();
  });

  it("shows the candidates and passes the choices through", async () => {
    const { onChooseCandidate, onChooseCustom } = renderPanel({
      status: "choose",
      kakaoPlaceId: "8193468",
      candidates: [odongdo],
    });

    await userEvent.click(screen.getByRole("button", { name: "오동도 선택" }));
    await userEvent.click(screen.getByRole("button", { name: "아니요, 직접 적을게요" }));

    expect(onChooseCandidate).toHaveBeenCalledExactlyOnceWith(odongdo);
    expect(onChooseCustom).toHaveBeenCalledTimes(1);
  });

  it("shows the custom place form and passes the typed place and the cancel through", async () => {
    const { onSubmitCustom, onCancel } = renderPanel({ status: "custom", kakaoPlaceId: null, reason: "direct", pickId: 1 });
    const user = userEvent.setup();

    await user.type(screen.getByLabelText("장소 이름"), "숙소");
    await user.click(screen.getByRole("button", { name: "담기" }));
    await user.click(screen.getByRole("button", { name: "취소" }));

    expect(onSubmitCustom).toHaveBeenCalledExactlyOnceWith({ name: "숙소", latitude: null, longitude: null });
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("opens a fresh custom place form for a new pick, so the name typed for the previous place does not stay", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const handlers = {
      onChooseCandidate: vi.fn(),
      onChooseCustom: vi.fn(),
      onStartDirect: vi.fn(),
      onSubmitCustom: vi.fn(),
      onCancel: vi.fn(),
    };
    const panel = (state: PlaceMatchState) => <PlaceMatchPanel {...handlers} fallbackCenter={null} state={state} tripId="7" />;
    const { rerender } = render(panel({ status: "custom", kakaoPlaceId: "1", reason: "noCoords", pickId: 1 }));
    await userEvent.type(screen.getByLabelText("장소 이름"), "앞 장소에 적던 이름");

    // 위치가 없는 결과를 연달아 고르면 상태가 곧바로 custom 에서 custom 으로 바뀐다 - 같은 칸이 남으면 안 된다
    rerender(panel({ status: "custom", kakaoPlaceId: "2", reason: "noCoords", pickId: 2 }));

    expect(screen.getByLabelText("장소 이름")).toHaveValue("");
  });

  it("never saves the name typed for one Kakao place under the Kakao id of the next one", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "");
    const added = vi.fn<(payload: TripPlaceAddItem) => void>();
    const withoutPoint = (id: string, title: string) => ({ id: `kakao:${id}`, title, latitude: null, longitude: null });
    // 일정 화면의 연결과 같다: 이름은 칸에서, 카카오 ID 는 지금 상태에서 꺼내 바구니 항목을 만든다
    function Harness() {
      const match = usePlaceMatch({ onMatched: () => undefined });
      return (
        <>
          <button onClick={() => void match.pick(withoutPoint("1", "첫째"))} type="button">
            첫째 고르기
          </button>
          <button onClick={() => void match.pick(withoutPoint("2", "둘째"))} type="button">
            둘째 고르기
          </button>
          <PlaceMatchPanel
            fallbackCenter={null}
            onCancel={match.reset}
            onChooseCandidate={match.chooseCandidate}
            onChooseCustom={match.chooseCustom}
            onStartDirect={match.startDirect}
            onSubmitCustom={(input) => {
              if (match.state.status === "custom") added(basketItemPayload(customBasketItem(input, match.state.kakaoPlaceId)));
            }}
            state={match.state}
            tripId="7"
          />
        </>
      );
    }
    render(<Harness />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "첫째 고르기" }));
    await user.type(await screen.findByLabelText("장소 이름"), "첫째 장소 이름");
    await user.click(screen.getByRole("button", { name: "둘째 고르기" }));

    expect(await screen.findByLabelText("장소 이름")).toHaveValue("");
    await user.type(screen.getByLabelText("장소 이름"), "둘째 장소 이름");
    await user.click(screen.getByRole("button", { name: "담기" }));

    expect(added).toHaveBeenCalledExactlyOnceWith({ customPlace: { name: "둘째 장소 이름" }, kakaoPlaceId: "2" });
  });
});
```

옛 시험을 새 흐름에 맞춘다. 홈 넘김 파일(`placeHandoff.ts` · `placeHandoff.test.ts`)은 과제 12의 몫이라 컴파일에 필요한 만큼만 건드린다 - 카카오 값을 저장 요청 모양으로 옮기던 `tripPlaceFromSearchItem`과 그 함수의 시험 하나만 지운다(구현 단계 3-4에서 함수를 없앤다). 나머지 `readPlaceParam` · `writePlaceParam` 시험은 그대로다.

**고치기 `frontend/src/utils/placeHandoff.test.ts`**

찾기:

```ts
import { readPlaceParam, tripPlaceFromSearchItem, writePlaceParam } from "./placeHandoff";
```

바꾸기:

```ts
import { readPlaceParam, writePlaceParam } from "./placeHandoff";
```

찾기:

```ts

  it("becomes the same trip place the trip's own place search would add", () => {
    expect(tripPlaceFromSearchItem(odongdo)).toEqual({
      time: "",
      label: "오동도",
      meta: "여행 > 관광,명소 > 섬 > 섬(내륙) · 전남광주통합특별시 여수시 수정동 1-1",
      address: "전남광주통합특별시 여수시 수정동 1-1",
      latitude: 34.744,
      longitude: 127.766,
      category: "여행 > 관광,명소 > 섬 > 섬(내륙)",
      categoryCode: "AT4",
      placeUrl: "http://place.map.kakao.com/8193468",
      sourceProvider: "kakao",
      externalPlaceId: "8193468",
    });
  });
```

바꾸기:

```ts
```

다음은 추가 시트의 라우트 시험이다. `trip-place-basket.test.tsx`를 새 흐름의 갈래별 시험으로 통째로 바꾼다. 이 시험들은 백엔드가 필요하다(`login()` - 위 '사전 준비' 참고).

**새 파일 `frontend/src/app/__tests__/trip-place-basket.test.tsx`** - 같은 이름의 파일을 통째로 바꾼다.

```tsx
import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  appDataApi,
  type PlaceMatchResult,
  type PlaceSearchCandidate,
  type PublicPlaceItem,
  type Trip,
} from "../../api";
import { getPreviewTrip } from "../../test/fixtures";
import { installAppKakaoSdkMock } from "../../test/kakaoMock";
import { login, renderAppRoute } from "../../test/renderAppRoute";

/* 카카오가 준 값과 공공데이터 값을 일부러 다르게 둔다 - 바구니 · 요청에 카카오 값이 새면 바로 드러난다 */
function kakaoCandidate(id: string, title: string, overrides: Partial<PlaceSearchCandidate> = {}): PlaceSearchCandidate {
  return {
    id: `kakao:${id}`,
    label: "📍",
    title,
    meta: `카카오 주소 ${title}`,
    address: `카카오 주소 ${title}`,
    categoryName: "카카오 분류",
    categoryCode: "CE7",
    latitude: 34.7443,
    longitude: 127.7663,
    placeUrl: `https://place.map.kakao.com/${id}`,
    sourceProvider: "kakao",
    externalPlaceId: id,
    ...overrides,
  };
}

function publicPlace(name: string, sourceId: string, overrides: Partial<PublicPlaceItem> = {}): PublicPlaceItem {
  return {
    source: "tourapi",
    sourceId,
    name,
    address: `공공데이터 주소 ${name}`,
    latitude: 34.74,
    longitude: 127.76,
    category: "cafe",
    distanceMeters: 30,
    ...overrides,
  };
}

function addTrip(id: string, revision = 3): Trip {
  return {
    ...getPreviewTrip(),
    id,
    title: "담는 흐름 여행",
    revision,
    days: { 1: [], 2: [] },
    currentUserRole: "owner",
  };
}

async function openAddSheet(trip: Trip) {
  vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
  await login();
  cleanup();
  renderAppRoute(`/trips/${trip.id}?day=1`);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: /장소 추가/ }));
  const dialog = await screen.findByRole("dialog", { name: "장소 추가" });
  return { user, dialog };
}

async function searchAndPick(user: ReturnType<typeof userEvent.setup>, dialog: HTMLElement, query: string, title: string) {
  fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: query } });
  await user.click(await within(dialog).findByRole("button", { name: `${title} 선택` }));
}

function mockSearch(...candidates: PlaceSearchCandidate[]) {
  return vi
    .spyOn(appDataApi, "searchTripPlaces")
    .mockImplementation(async (_tripId, request) => candidates.filter((candidate) => request.query.includes(candidate.title.slice(0, 2))));
}

/** 담기 요청 본문에 카카오가 준 이름 · 주소 · 분류가 한 글자도 없어야 한다 */
function expectNoKakaoValues(body: unknown) {
  const text = JSON.stringify(body);
  expect(text).not.toContain("카카오");
  expect(text).not.toContain("34.7443");
  expect(text).not.toContain("7663");
  expect(text).not.toContain("address");
  expect(text).not.toContain("label");
  expect(text).not.toContain("meta");
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  delete window.kakao;
});

describe("Travel Hunter app trip place add flow", () => {
  it("puts a place that matches our data straight into the basket and saves only its reference", async () => {
    const trip = addTrip("92");
    mockSearch(kakaoCandidate("8001", "스타벅스 여수점"));
    const matchSpy = vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "match",
      places: [publicPlace("스타벅스 여수오동도점", "T-1")],
    });
    const savedTrip: Trip = { ...trip, revision: 4 };
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue(savedTrip);
    const addSingleSpy = vi.spyOn(appDataApi, "addTripPlace");
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "스타", "스타벅스 여수점");

    // 맞춰 보기에는 이름 · 좌표 · 분류만 간다
    await waitFor(() =>
      expect(matchSpy).toHaveBeenCalledWith({ name: "스타벅스 여수점", latitude: 34.7443, longitude: 127.7663, categoryCode: "CE7" }),
    );
    const basket = await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    expect(basket).toHaveTextContent("스타벅스 여수오동도점");
    expect(basket).toHaveTextContent("카페");
    expect(basket).toHaveTextContent("공공데이터 주소 스타벅스 여수오동도점");
    expect(basket).not.toHaveTextContent("카카오");
    expect(within(dialog).queryByLabelText("장소 이름")).not.toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Day 1에 1개 저장하기" }));

    await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
    const request = addBatchSpy.mock.calls[0][2];
    expect(addBatchSpy).toHaveBeenCalledWith("92", 1, {
      expectedRevision: 3,
      places: [{ publicPlace: { source: "tourapi", sourceId: "T-1" }, kakaoPlaceId: "8001" }],
    });
    expectNoKakaoValues(request);
    expect(addSingleSpy).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "장소 추가" })).not.toBeInTheDocument());
  });

  it("asks which place is right when candidates come back and adds the one the user chooses", async () => {
    const trip = addTrip("93");
    mockSearch(kakaoCandidate("8002", "오동도"));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "candidates",
      places: [
        publicPlace("오동도", "T-10", { category: "sight", distanceMeters: 0 }),
        publicPlace("오동도 공원", "S-11", { source: "sangga", category: "culture", distanceMeters: 220 }),
      ],
    });
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "오동", "오동도");

    const choices = await within(dialog).findByRole("region", { name: "이 장소가 맞나요?" });
    expect(within(choices).getByRole("button", { name: "오동도 선택" })).toHaveTextContent("고른 곳과 같은 자리");
    expect(within(choices).getByRole("button", { name: "오동도 공원 선택" })).toHaveTextContent("고른 곳에서 약 220m");
    // 맞춰 보는 동안과 후보를 묻는 동안은 지도 미리보기를 접는다(카카오 이름이 칸 옆에 남지 않게)
    expect(within(dialog).queryByLabelText("장소 지도 미리보기")).not.toBeInTheDocument();

    await user.click(within(choices).getByRole("button", { name: "오동도 공원 선택" }));

    const basket = await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    expect(basket).toHaveTextContent("오동도 공원");
    expect(basket).toHaveTextContent("문화시설");
    expect(within(dialog).queryByRole("region", { name: "이 장소가 맞나요?" })).not.toBeInTheDocument();
    expect(within(dialog).getByLabelText("장소 지도 미리보기")).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Day 1에 1개 저장하기" }));

    await waitFor(() =>
      expect(addBatchSpy).toHaveBeenCalledWith("93", 1, {
        expectedRevision: 3,
        places: [{ publicPlace: { source: "sangga", sourceId: "S-11" }, kakaoPlaceId: "8002" }],
      }),
    );
  });

  it("lets the user say none of the candidates is right and write the place by hand, starting from an empty name", async () => {
    const trip = addTrip("94");
    mockSearch(kakaoCandidate("8003", "바다횟집 본점"));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "candidates",
      places: [publicPlace("바다횟집", "S-20", { source: "sangga", category: "food" })],
    });
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "바다", "바다횟집 본점");
    await user.click(await within(dialog).findByRole("button", { name: "아니요, 직접 적을게요" }));

    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    const name = within(form).getByLabelText("장소 이름");
    // 카카오 이름을 미리 채우지도, 옆에 보이지도 않는다
    expect(name).toHaveValue("");
    expect(dialog).not.toHaveTextContent("바다횟집 본점");
    expect(within(dialog).queryByDisplayValue("바다횟집 본점")).not.toBeInTheDocument();
    expect(within(dialog).queryByLabelText("장소 지도 미리보기")).not.toBeInTheDocument();

    await user.type(name, "  우리가 가던 횟집  ");
    await user.click(within(form).getByRole("button", { name: "담기" }));

    const basket = await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    expect(basket).toHaveTextContent("우리가 가던 횟집");
    expect(basket).toHaveTextContent("직접 적은 장소");
    expect(within(dialog).queryByRole("form", { name: "나만의 장소" })).not.toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Day 1에 1개 저장하기" }));

    await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
    expect(addBatchSpy).toHaveBeenCalledWith("94", 1, {
      expectedRevision: 3,
      places: [{ customPlace: { name: "우리가 가던 횟집" }, kakaoPlaceId: "8003" }],
    });
    expectNoKakaoValues(addBatchSpy.mock.calls[0][2]);
  });

  it("opens the custom place form straight away when nothing matches", async () => {
    const trip = addTrip("95");
    mockSearch(kakaoCandidate("8004", "새로 생긴 가게"));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "none", places: [] });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "새로", "새로 생긴 가게");

    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    expect(within(form).getByLabelText("장소 이름")).toHaveValue("");
    expect(form).toHaveTextContent("같은 곳을 찾지 못했어요");
    expect(dialog).not.toHaveTextContent("새로 생긴 가게");
  });

  it("asks for a name without calling match when the picked place has no coordinates", async () => {
    const trip = addTrip("96");
    mockSearch(kakaoCandidate("8005", "좌표없는곳", { latitude: null, longitude: null }));
    const matchSpy = vi.spyOn(appDataApi, "matchPlace");
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "좌표", "좌표없는곳");

    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    expect(form).toHaveTextContent("위치 정보가 없어서");
    expect(matchSpy).not.toHaveBeenCalled();
  });

  it("falls back to the custom place form when matching fails", async () => {
    const trip = addTrip("97");
    mockSearch(kakaoCandidate("8006", "맞춰보기실패"));
    vi.spyOn(appDataApi, "matchPlace").mockRejectedValue(
      new ApiError("server error", { status: 500, statusText: "Internal Server Error" }),
    );
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "맞춰", "맞춰보기실패");

    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    expect(form).toHaveTextContent("맞춰 보지 못했어요");
    expect(within(form).getByLabelText("장소 이름")).toHaveValue("");
  });

  it("lets the user write a place by hand without searching, and saves it together with a matched one", async () => {
    const trip = addTrip("98");
    mockSearch(kakaoCandidate("8007", "해변카페"));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "match",
      places: [publicPlace("해변 카페", "T-30")],
    });
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "해변", "해변카페");
    await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    await user.click(within(dialog).getByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" }));
    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    await user.type(within(form).getByLabelText("장소 이름"), "친구네 집");
    await user.click(within(form).getByRole("button", { name: "담기" }));

    await waitFor(() =>
      expect(within(dialog).getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("추가할 장소 2개"),
    );
    await user.click(within(dialog).getByRole("button", { name: "Day 1에 2개 저장하기" }));

    await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
    expect(addBatchSpy).toHaveBeenCalledWith("98", 1, {
      expectedRevision: 3,
      places: [
        { publicPlace: { source: "tourapi", sourceId: "T-30" }, kakaoPlaceId: "8007" },
        // 직접 적기로 연 칸은 카카오 장소가 없으므로 ID 도 없다
        { customPlace: { name: "친구네 집" } },
      ],
    });
  });

  it("saves a custom place with a point picked on the map that opened on the trip area, not on the Kakao place", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    const trip = addTrip("99");
    mockSearch(kakaoCandidate("8008", "동네 쉼터", { latitude: 33.4584, longitude: 126.9425 }));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "none", places: [] });
    const areaSpy = vi.spyOn(appDataApi, "getTripAreaCenter").mockResolvedValue({ latitude: 35.5, longitude: 127.7 });
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "동네", "동네 쉼터");
    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    await user.type(within(form).getByLabelText("장소 이름"), "우리 쉼터");
    await user.click(within(form).getByRole("button", { name: "지도에서 위치 찍기" }));
    await waitFor(() => expect(kakao.mapInstances.length).toBeGreaterThan(0));

    // 일정 지역 중심에서 열린다 - 고른 카카오 장소(33.4584, 126.9425)의 자리가 아니다
    expect(areaSpy).toHaveBeenCalledWith("99");
    const pickerMap = kakao.mapInstances[kakao.mapInstances.length - 1];
    expect(pickerMap.options).toMatchObject({ center: { lat: 35.5, lng: 127.7 } });

    act(() => kakao.emitMapClick(35.51, 127.71));
    await user.click(within(form).getByRole("button", { name: "이 위치로" }));
    await user.click(within(form).getByRole("button", { name: "담기" }));
    await user.click(await within(dialog).findByRole("button", { name: "Day 1에 1개 저장하기" }));

    await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
    expect(addBatchSpy).toHaveBeenCalledWith("99", 1, {
      expectedRevision: 3,
      places: [{ customPlace: { name: "우리 쉼터", latitude: 35.51, longitude: 127.71 }, kakaoPlaceId: "8008" }],
    });
  });

  it("drops a pending match when the user starts a new search", async () => {
    const trip = addTrip("100");
    mockSearch(kakaoCandidate("8009", "느린곳"), kakaoCandidate("8010", "빠른곳"));
    let finishFirst!: (answer: PlaceMatchResult) => void;
    vi.spyOn(appDataApi, "matchPlace").mockReturnValueOnce(
      new Promise<PlaceMatchResult>((resolve) => {
        finishFirst = resolve;
      }),
    );
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "느린", "느린곳");
    expect(await within(dialog).findByRole("status")).toHaveTextContent("맞춰 보는 중");

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "빠른" } });
    await within(dialog).findByRole("button", { name: "빠른곳 선택" });
    expect(within(dialog).queryByRole("status")).not.toBeInTheDocument();

    await act(async () => {
      finishFirst({ result: "match", places: [publicPlace("느린 곳", "T-40")] });
    });

    expect(within(dialog).queryByRole("region", { name: "추가할 장소 목록" })).not.toBeInTheDocument();
  });

  it("starts the custom place form empty for each picked result, even when two results without coordinates come in a row", async () => {
    const trip = addTrip("101");
    mockSearch(
      kakaoCandidate("8021", "첫째좌표없음", { latitude: null, longitude: null }),
      kakaoCandidate("8022", "둘째좌표없음", { latitude: null, longitude: null }),
    );
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "첫째", "첫째좌표없음");
    const first = await within(dialog).findByRole("form", { name: "나만의 장소" });
    await user.type(within(first).getByLabelText("장소 이름"), "첫째에 적은 이름");

    await searchAndPick(user, dialog, "둘째", "둘째좌표없음");
    const second = await within(dialog).findByRole("form", { name: "나만의 장소" });
    expect(within(second).getByLabelText("장소 이름")).toHaveValue("");
    await user.type(within(second).getByLabelText("장소 이름"), "둘째에 적은 이름");
    await user.click(within(second).getByRole("button", { name: "담기" }));
    await user.click(await within(dialog).findByRole("button", { name: "Day 1에 1개 저장하기" }));

    // 저장 요청에는 둘째 장소의 카카오 ID 와 방금 적은 이름뿐이다
    await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
    expect(addBatchSpy).toHaveBeenCalledWith("101", 1, {
      expectedRevision: 3,
      places: [{ customPlace: { name: "둘째에 적은 이름" }, kakaoPlaceId: "8022" }],
    });
    expect(JSON.stringify(addBatchSpy.mock.calls[0][2])).not.toContain("첫째");
  });

  it("asks for a refresh instead of the generic message when saving the basket is refused with 422", async () => {
    const trip = addTrip("102");
    mockSearch(kakaoCandidate("8031", "오래된화면카페"));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "match",
      places: [publicPlace("오래된 화면 카페", "T-60")],
    });
    const addBatchSpy = vi
      .spyOn(appDataApi, "addTripPlaces")
      .mockRejectedValue(
        new ApiError("Unprocessable Entity", {
          status: 422,
          statusText: "Unprocessable Entity",
          // 옛 화면이 보낸 모양 - 서버가 모르는 필드(예전 카카오 이름 칸)를 거절했다
          detail: [{ type: "extra_forbidden", loc: ["body", "places", 0, "label"], msg: "Extra inputs are not permitted" }],
        }),
      );
    const reload = vi.fn();
    vi.stubGlobal("location", { ...window.location, reload });
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "오래", "오래된화면카페");
    await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    await user.click(within(dialog).getByRole("button", { name: "Day 1에 1개 저장하기" }));

    await waitFor(() => expect(addBatchSpy).toHaveBeenCalledTimes(1));
    expect(await within(dialog).findByText("화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.")).toBeInTheDocument();
    expect(within(dialog).queryByText(/입력값을 확인하고 다시 시도해 주세요/)).not.toBeInTheDocument();
    // 담아 둔 장소는 그대로 남는다
    expect(within(dialog).getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("오래된 화면 카페");
    expect(reload).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "새로 고침" }));
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("keeps the generic message and no refresh button for other save failures", async () => {
    const trip = addTrip("103");
    mockSearch(kakaoCandidate("8032", "그냥실패카페"));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "match",
      places: [publicPlace("그냥 실패 카페", "T-61")],
    });
    vi.spyOn(appDataApi, "addTripPlaces").mockRejectedValue(
      new ApiError("Internal Server Error", { status: 500, statusText: "Internal Server Error" }),
    );
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "그냥", "그냥실패카페");
    await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    await user.click(within(dialog).getByRole("button", { name: "Day 1에 1개 저장하기" }));

    expect(await within(dialog).findByText(/입력값을 확인하고 다시 시도해 주세요/)).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "새로 고침" })).not.toBeInTheDocument();
  });

  it("keeps the generic message for a 422 about a value rather than the request shape", async () => {
    const trip = addTrip("106");
    mockSearch(kakaoCandidate("8034", "값오류카페"));
    vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "match",
      places: [publicPlace("값 오류 카페", "T-63")],
    });
    vi.spyOn(appDataApi, "addTripPlaces").mockRejectedValue(
      new ApiError("Unprocessable Entity", {
        status: 422,
        statusText: "Unprocessable Entity",
        // 값 오류 - 새로 고쳐도 그대로라 새로 고침을 권하지 않는다
        detail: [{ type: "string_too_long", loc: ["body", "places", 0, "customPlace", "name"], msg: "String should have at most 100 characters" }],
      }),
    );
    const { user, dialog } = await openAddSheet(trip);

    await searchAndPick(user, dialog, "값오류", "값오류카페");
    await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    await user.click(within(dialog).getByRole("button", { name: "Day 1에 1개 저장하기" }));

    expect(await within(dialog).findByText(/입력값을 확인하고 다시 시도해 주세요/)).toBeInTheDocument();
    expect(within(dialog).queryByText("화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.")).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "새로 고침" })).not.toBeInTheDocument();
  });

  it("says the place search is unavailable on a 503, not that nothing was found, and the direct entry still saves a place", async () => {
    const trip = addTrip("104");
    vi.spyOn(appDataApi, "searchTripPlaces").mockRejectedValue(
      new ApiError("Place search is unavailable", {
        status: 503,
        statusText: "Service Unavailable",
        detail: "Place search is unavailable",
      }),
    );
    const addBatchSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const { user, dialog } = await openAddSheet(trip);

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "여수" } });

    expect(await within(dialog).findByText("장소 검색을 지금 쓸 수 없어요. 직접 적기로 담을 수 있어요.")).toBeInTheDocument();
    // '결과 없음'이나 일반 실패 문구와 다른 상태다
    expect(within(dialog).queryByText(/검색 결과가 없어요/)).not.toBeInTheDocument();
    expect(within(dialog).queryByText(/불러오지 못했어요/)).not.toBeInTheDocument();
    // 직접 적기 입구는 그대로 쓸 수 있다
    await user.click(within(dialog).getByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" }));
    const form = await within(dialog).findByRole("form", { name: "나만의 장소" });
    await user.type(within(form).getByLabelText("장소 이름"), "여수 밤바다 쉼터");
    await user.click(within(form).getByRole("button", { name: "담기" }));
    await user.click(await within(dialog).findByRole("button", { name: "Day 1에 1개 저장하기" }));

    await waitFor(() =>
      expect(addBatchSpy).toHaveBeenCalledWith("104", 1, {
        expectedRevision: 3,
        places: [{ customPlace: { name: "여수 밤바다 쉼터" } }],
      }),
    );
  });

  it("keeps the generic search failure message for other search errors", async () => {
    const trip = addTrip("105");
    vi.spyOn(appDataApi, "searchTripPlaces").mockRejectedValue(new Error("offline"));
    const { dialog } = await openAddSheet(trip);

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "여수" } });

    expect(await within(dialog).findByText("장소 검색 결과를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.")).toBeInTheDocument();
    expect(within(dialog).queryByText(/지금 쓸 수 없어요/)).not.toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" })).toBeInTheDocument();
  });
});
```

다음은 일정 상세 시험(`trip-detail.test.tsx`)이다. 추가 시트가 카카오 값을 바구니에 담던 시험 일곱 개를 새 흐름(맞춰 보기를 거쳐 공공데이터 장소를 담는다)으로 바꾼다. 검색 후보는 좌표와 `kakao:{숫자}` ID가 있어야 맞춰 보기를 거치고, 이름이 같은 공공데이터 장소로 바로 맞는 것으로 한다.

**고치기 `frontend/src/app/__tests__/trip-detail.test.tsx`**

찾기:

```tsx
import { describe, expect, it, vi } from "vitest";
import {
  ApiError,
  appDataApi,
  type LinkedTripPolicy,
  type PlaceSearchItem,
  type Recommendation,
  type Trip,
} from "../../api";
import { tripPlaceFromSearchItem, writePlaceParam } from "../../utils/placeHandoff";
```

바꾸기:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  appDataApi,
  type LinkedTripPolicy,
  type PlaceSearchCandidate,
  type PlaceSearchItem,
  type PublicPlaceItem,
  type Recommendation,
  type Trip,
} from "../../api";
import { writePlaceParam } from "../../utils/placeHandoff";
```

찾기:

```tsx
describe("Travel Hunter app — trip detail & itinerary", () => {
```

바꾸기:

```tsx
/* 3단계 담는 흐름: 검색 후보를 고르면 공공데이터와 맞춰 본다(matchPlace). 후보에 좌표가 있어야 맞춰 보고, 장소 ID 는 kakao:{숫자}다 */
function kakaoCandidate(id: string, title: string): PlaceSearchCandidate {
  return {
    id: `kakao:${id}`,
    label: "📍",
    title,
    meta: `카카오 주소 ${title}`,
    address: `카카오 주소 ${title}`,
    categoryCode: "AT4",
    categoryName: "카카오 분류",
    latitude: 33.4584,
    longitude: 126.9425,
    placeUrl: `https://place.map.kakao.com/${id}`,
    sourceProvider: "kakao",
    externalPlaceId: id,
  };
}

function publicPlaceFor(name: string, sourceId = name.replace(/\s+/g, "-")): PublicPlaceItem {
  return {
    source: "tourapi",
    sourceId,
    name,
    address: `공공데이터 주소 ${name}`,
    latitude: 33.46,
    longitude: 126.94,
    category: "sight",
    distanceMeters: 15,
  };
}

/* 이름이 같은 공공데이터 장소 하나로 바로 맞는다 */
function mockMatchByName() {
  return vi.spyOn(appDataApi, "matchPlace").mockImplementation(async (request) => ({
    result: "match",
    places: [publicPlaceFor(request.name)],
  }));
}

describe("Travel Hunter app — trip detail & itinerary", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

```

추가 시트에 입구가 보이고 이름 칸은 입구를 눌러야 열린다.

찾기:

```tsx
      expect(screen.getByLabelText("장소 검색")).toBeInTheDocument();
      expect(screen.queryByLabelText("장소명")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("메모")).not.toBeInTheDocument();

      await user.type(screen.getByLabelText("장소 검색"), "등록되지 않은 장소");
```

바꾸기:

```tsx
      expect(screen.getByLabelText("장소 검색")).toBeInTheDocument();
      expect(screen.queryByLabelText("장소명")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("메모")).not.toBeInTheDocument();
      // 직접 적는 칸은 입구를 눌러야 열린다 - 검색 전에는 이름 칸이 없다(3단계)
      expect(screen.queryByLabelText("장소 이름")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" })).toBeInTheDocument();

      await user.type(screen.getByLabelText("장소 검색"), "등록되지 않은 장소");
```

바구니 시험을 공공데이터 장소 기준으로 바꾼다.

찾기:

```tsx
  it("keeps selected place search candidates in an add-sheet place basket", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "126",
      title: "장소 바구니 여행",
      days: { 1: [], 2: [] },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const searchTripPlacesSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockImplementation(async (_tripId, request) => {
        if (request.query.includes("성산")) {
          return [
            {
              id: "search-a",
              label: "성산일출봉",
              title: "성산일출봉",
              meta: "제주 서귀포시",
              address: "제주 서귀포시 성산읍",
              categoryCode: "AT4",
              categoryName: "관광명소",
              sourceProvider: "kakao",
              externalPlaceId: "kakao-a",
            },
          ];
        }
        if (request.query.includes("시장")) {
          return [
            {
              id: "search-b",
              label: "동문시장",
              title: "동문시장",
              meta: "제주 제주시",
              address: "제주 제주시 관덕로",
              categoryCode: "FD6",
              categoryName: "음식점",
              sourceProvider: "kakao",
              externalPlaceId: "kakao-b",
            },
          ];
        }
        return [];
      });
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace");

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/126");
      const user = userEvent.setup();

      await user.click(await screen.findByRole("button", { name: /장소 추가/ }));
      const searchInput = screen.getByLabelText("장소 검색");
      await user.type(searchInput, "성산");
      await user.click(await screen.findByRole("button", { name: "성산일출봉 선택" }));

      expect(screen.getByRole("dialog", { name: "장소 추가" })).toBeInTheDocument();
      expect(searchInput).toHaveValue("");
      expect(screen.queryByRole("button", { name: "성산일출봉 선택" })).not.toBeInTheDocument();
      expect(screen.getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("추가할 장소 1개");
      expect(screen.getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("관광명소");
      expect(screen.getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("제주 서귀포시 성산읍");
      expect(screen.queryByLabelText("장소명")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("메모")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Day 1에 1개 저장하기" })).toBeInTheDocument();

      await user.type(searchInput, "시장");
      await user.click(await screen.findByRole("button", { name: "동문시장 선택" }));
      await user.type(searchInput, "성산");
      await user.click(await screen.findByRole("button", { name: "성산일출봉 선택" }));

      const basket = screen.getByRole("region", { name: "추가할 장소 목록" });
      expect(basket).toHaveTextContent("추가할 장소 3개");
      expect(within(basket).getAllByText("성산일출봉")).toHaveLength(2);
      expect(within(basket).getByText("동문시장")).toBeInTheDocument();

      const removeButton = within(basket).getAllByRole("button", { name: "성산일출봉 제거" })[0];
      expect(removeButton).toHaveTextContent(/^제거$/);
      await user.click(removeButton);

      expect(basket).toHaveTextContent("추가할 장소 2개");
      expect(within(basket).getAllByText("성산일출봉")).toHaveLength(1);
      expect(screen.getByRole("button", { name: "Day 1에 2개 저장하기" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "Day 1에 2개 저장하기" }));

      expect(addPlaceSpy).not.toHaveBeenCalled();
      expect(screen.getByRole("dialog", { name: "장소 추가" })).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      searchTripPlacesSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });
```

바꾸기:

```tsx
  it("keeps matched public places in an add-sheet place basket", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "126",
      title: "장소 바구니 여행",
      days: { 1: [], 2: [] },
      currentUserRole: "owner",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const searchTripPlacesSpy = vi
      .spyOn(appDataApi, "searchTripPlaces")
      .mockImplementation(async (_tripId, request) => {
        if (request.query.includes("성산")) return [kakaoCandidate("8001", "성산일출봉")];
        if (request.query.includes("시장")) return [kakaoCandidate("8002", "동문시장")];
        return [];
      });
    const matchPlaceSpy = vi.spyOn(appDataApi, "matchPlace").mockImplementation(async (request) => ({
      result: "match",
      // 공공데이터의 표기가 카카오와 다르다 - 바구니에는 공공데이터 이름 · 주소가 보여야 한다
      places: [
        request.name === "동문시장" ? publicPlaceFor("동문 시장", "200") : publicPlaceFor("성산 일출봉", "126508"),
      ],
    }));
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace");
    const addPlacesSpy = vi.spyOn(appDataApi, "addTripPlaces").mockRejectedValue(new Error("offline"));

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/126");
      const user = userEvent.setup();

      await user.click(await screen.findByRole("button", { name: /장소 추가/ }));
      const searchInput = screen.getByLabelText("장소 검색");
      await user.type(searchInput, "성산");
      await user.click(await screen.findByRole("button", { name: "성산일출봉 선택" }));

      expect(screen.getByRole("dialog", { name: "장소 추가" })).toBeInTheDocument();
      // 맞춰 보기에는 이름 · 좌표 · 분류만 간다
      await waitFor(() =>
        expect(matchPlaceSpy).toHaveBeenCalledWith({
          name: "성산일출봉",
          latitude: 33.4584,
          longitude: 126.9425,
          categoryCode: "AT4",
        }),
      );
      const firstBasket = await screen.findByRole("region", { name: "추가할 장소 목록" });
      expect(searchInput).toHaveValue("");
      expect(screen.queryByRole("button", { name: "성산일출봉 선택" })).not.toBeInTheDocument();
      expect(firstBasket).toHaveTextContent("추가할 장소 1개");
      expect(firstBasket).toHaveTextContent("성산 일출봉");
      expect(firstBasket).toHaveTextContent("관광지");
      expect(firstBasket).toHaveTextContent("공공데이터 주소 성산 일출봉");
      // 카카오가 준 주소 · 분류는 바구니에 없다
      expect(firstBasket).not.toHaveTextContent("카카오");
      expect(screen.queryByLabelText("장소명")).not.toBeInTheDocument();
      expect(screen.queryByLabelText("메모")).not.toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Day 1에 1개 저장하기" })).toBeInTheDocument();

      await user.type(searchInput, "시장");
      await user.click(await screen.findByRole("button", { name: "동문시장 선택" }));
      await waitFor(() =>
        expect(screen.getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("추가할 장소 2개"),
      );
      await user.type(searchInput, "성산");
      await user.click(await screen.findByRole("button", { name: "성산일출봉 선택" }));

      await waitFor(() =>
        expect(screen.getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("추가할 장소 3개"),
      );
      const basket = screen.getByRole("region", { name: "추가할 장소 목록" });
      expect(within(basket).getAllByText("성산 일출봉")).toHaveLength(2);
      expect(within(basket).getByText("동문 시장")).toBeInTheDocument();

      const removeButton = within(basket).getAllByRole("button", { name: "성산 일출봉 제거" })[0];
      expect(removeButton).toHaveTextContent(/^제거$/);
      await user.click(removeButton);

      expect(basket).toHaveTextContent("추가할 장소 2개");
      expect(within(basket).getAllByText("성산 일출봉")).toHaveLength(1);
      expect(screen.getByRole("button", { name: "Day 1에 2개 저장하기" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "Day 1에 2개 저장하기" }));

      await waitFor(() => expect(addPlacesSpy).toHaveBeenCalledTimes(1));
      expect(addPlaceSpy).not.toHaveBeenCalled();
      // 저장이 실패해도 창과 바구니는 그대로다
      expect(screen.getByRole("dialog", { name: "장소 추가" })).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
      searchTripPlacesSpy.mockRestore();
      matchPlaceSpy.mockRestore();
      addPlaceSpy.mockRestore();
      addPlacesSpy.mockRestore();
    }
  });
```

홈에서 넘어온 장소도 같은 맞춰 보기를 거친다. (홈 넘김 시험은 과제 12가 새 주소 형식에 맞춰 다시 쓴다. 여기서는 `?addPlace=` 받는 효과가 `pick`을 부르게 바뀐 만큼 기대 값만 세 줄 고쳐 통과시킨다.)

찾기:

```tsx
    const addPlacesSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    try {
      await login();
      cleanup();
      renderAppRoute(`/trips/128?${new URLSearchParams({ addPlace: writePlaceParam(odongdo) })}`);
```

바꾸기:

```tsx
    const addPlacesSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    const matchPlaceSpy = vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({
      result: "match",
      places: [publicPlaceFor("오동도", "126508")],
    });
    try {
      await login();
      cleanup();
      renderAppRoute(`/trips/128?${new URLSearchParams({ addPlace: writePlaceParam(odongdo) })}`);
```

찾기:

```tsx
      expect(within(sheet).getByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("오동도");
```

바꾸기:

```tsx
      expect(await within(sheet).findByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("오동도");
      // 넘어온 카카오 장소는 검색 결과를 고른 것과 같이 맞춰 본다 - 이름 · 좌표 · 분류만 간다
      expect(matchPlaceSpy).toHaveBeenCalledWith({ name: "오동도", latitude: 34.745, longitude: 127.766, categoryCode: "AT4" });
```

찾기:

```tsx
      // 일정 안 장소 검색으로 같은 곳을 담을 때와 같은 기록(카카오 id · 분류 전체 경로)
      expect(addPlacesSpy).toHaveBeenCalledWith("128", 2, { expectedRevision: 3, places: [tripPlaceFromSearchItem(odongdo)] });
```

바꾸기:

```tsx
      // 일정 안 장소 검색으로 같은 곳을 담을 때와 같은 기록 - 공공데이터 참조와 카카오 장소 ID 뿐이다
      expect(addPlacesSpy).toHaveBeenCalledWith("128", 2, {
        expectedRevision: 3,
        places: [{ publicPlace: { source: "tourapi", sourceId: "126508" }, kakaoPlaceId: "8193468" }],
      });
```

묶음 저장 시험의 검색 후보와 기대 요청을 바꾼다.

찾기:

```tsx
      .mockImplementation(async (_tripId, request) => {
        if (request.query.includes("Alpha")) {
          return [
            {
              id: "alpha",
              label: "Alpha cafe",
              title: "Alpha cafe",
              meta: "Cafe",
              address: "Alpha address",
              categoryCode: "CE7",
              categoryName: "Cafe",
              sourceProvider: "kakao",
              externalPlaceId: "kakao-alpha",
            },
          ];
        }
        if (request.query.includes("Beta")) {
          return [
            {
              id: "beta",
              label: "Beta park",
              title: "Beta park",
              meta: "Park",
              address: "Beta address",
              categoryCode: "AT4",
              categoryName: "Park",
              sourceProvider: "kakao",
              externalPlaceId: "kakao-beta",
            },
          ];
        }
        return [];
      });
```

바꾸기:

```tsx
      .mockImplementation(async (_tripId, request) => {
        if (request.query.includes("Alpha")) return [kakaoCandidate("9001", "Alpha cafe")];
        if (request.query.includes("Beta")) return [kakaoCandidate("9002", "Beta park")];
        return [];
      });
    mockMatchByName();
```

찾기:

```tsx
      await user.click(document.querySelector<HTMLButtonElement>(".place-search-results button")!);
      await user.type(searchInput, "Beta");
```

바꾸기:

```tsx
      await user.click(document.querySelector<HTMLButtonElement>(".place-search-results button")!);
      await screen.findByText("추가할 장소 1개");
      await user.type(searchInput, "Beta");
```

찾기:

```tsx
      expect(addPlacesSpy).toHaveBeenCalledWith("127", 1, {
        expectedRevision: 7,
        places: [
          {
            time: "",
            label: "Alpha cafe",
            meta: "Cafe",
            address: "Alpha address",
            latitude: null,
            longitude: null,
            category: "Cafe",
            categoryCode: "CE7",
            placeUrl: null,
            sourceProvider: "kakao",
            externalPlaceId: "kakao-alpha",
          },
          {
            time: "",
            label: "Beta park",
            meta: "Park",
            address: "Beta address",
            latitude: null,
            longitude: null,
            category: "Park",
            categoryCode: "AT4",
            placeUrl: null,
            sourceProvider: "kakao",
            externalPlaceId: "kakao-beta",
          },
        ],
      });
```

바꾸기:

```tsx
      expect(addPlacesSpy).toHaveBeenCalledWith("127", 1, {
        expectedRevision: 7,
        places: [
          { publicPlace: { source: "tourapi", sourceId: "Alpha-cafe" }, kakaoPlaceId: "9001" },
          { publicPlace: { source: "tourapi", sourceId: "Beta-park" }, kakaoPlaceId: "9002" },
        ],
      });
```

저장 실패를 다루는 네 시험은 검색 후보만 바꾼다(좌표 · `kakao:{숫자}` ID가 있고, 이름이 같은 공공데이터 장소로 맞는다).

찾기:

```tsx
      .mockResolvedValue([
        {
          id: "gamma",
          label: "Gamma beach",
          title: "Gamma beach",
          meta: "Beach",
        },
      ]);
```

바꾸기:

```tsx
      .mockResolvedValue([kakaoCandidate("8301", "Gamma beach")]);
    mockMatchByName();
```

찾기:

```tsx
      .mockResolvedValue([
        {
          id: "delta",
          label: "Delta museum",
          title: "Delta museum",
          meta: "Museum",
        },
      ]);
```

바꾸기:

```tsx
      .mockResolvedValue([kakaoCandidate("8302", "Delta museum")]);
    mockMatchByName();
```

찾기:

```tsx
      .mockResolvedValue([
        {
          id: "delta-refresh-failure",
          label: "Delta museum",
          title: "Delta museum",
          meta: "Museum",
        },
      ]);
```

바꾸기:

```tsx
      .mockResolvedValue([kakaoCandidate("8303", "Delta museum")]);
    mockMatchByName();
```

찾기:

```tsx
      .mockResolvedValue([
        {
          id: "epsilon",
          label: "Epsilon market",
          title: "Epsilon market",
          meta: "Market",
        },
      ]);
```

바꾸기:

```tsx
      .mockResolvedValue([kakaoCandidate("8304", "Epsilon market")]);
    mockMatchByName();
```

e2e도 추가 시트를 확인하던 곳만 고친다 - 빈 검색 뒤에 직접 적기 입구가 이름 칸을 여는지, 그 칸이 다섯 폭에서 넘치지 않는지 본다. 장소 추가 요청을 API로 바로 보내는 시드 두 곳(`backend-mode.spec.ts` 약 297 · `itinerary-cross-day-drag.spec.ts` 약 47)은 과제 12의 몫이라 건드리지 않는다(3단계 백엔드가 옛 모양을 거부하므로 과제 12 전에는 이 e2e 둘이 시드에서 실패한다).

**고치기 `frontend/e2e-backend/backend-mode.spec.ts`**

찾기:

```ts
    await expect(responsiveSheet.getByLabel("장소 지도 미리보기")).toBeVisible();
    await expectNoDocumentOverflow(page);
    await responsiveSheet.getByRole("button", { name: "닫기" }).click();
```

바꾸기:

```ts
    await expect(responsiveSheet.getByLabel("장소 지도 미리보기")).toBeVisible();
    await expectNoDocumentOverflow(page);
    // 직접 적기 칸(나만의 장소)도 같은 폭에서 가로로 넘치지 않는다 - 시안 v59 로 모양이 바뀐 뒤에도 같은 확인을 한다
    await responsiveSheet.getByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" }).click();
    await expect(responsiveSheet.getByRole("form", { name: "나만의 장소" })).toBeVisible();
    await expectNoDocumentOverflow(page);
    await responsiveSheet.getByRole("button", { name: "닫기" }).click();
```

찾기:

```ts
  // 장소 추가는 검색 후보를 담아 저장하는 방식이다. 이름만 적어 넣는 칸은 편집 모드에만 있다(2026-08-25 fcf797f).
  await expect(sheet.locator('input[name="place-label"]')).toHaveCount(0);
```

바꾸기:

```ts
  // 장소 추가는 검색 후보를 공공데이터와 맞춰 담고, 찾는 곳이 없으면 직접 적는다(3단계).
  // 수정 창의 이름 칸(place-label)은 추가 창에 없고, 직접 적는 칸은 입구를 눌러야 열리며 카카오 이름 없이 빈 채로 시작한다.
  await expect(sheet.locator('input[name="place-label"]')).toHaveCount(0);
  await expect(sheet.locator('input[name="custom-place-name"]')).toHaveCount(0);
  await sheet.getByRole("button", { name: "찾는 곳이 없어요 · 직접 적기" }).click();
  const customName = sheet.locator('input[name="custom-place-name"]');
  await expect(customName).toBeVisible();
  await expect(customName).toHaveValue("");
  await expectNoDocumentOverflow(page);
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd frontend && npx vitest run src/components/itinerary src/utils/placeHandoff.test.ts`
기대: FAIL 5개 파일 - `PlacePhoto.test.tsx` · `PlaceMatchChoices.test.tsx` · `MapPointPicker.test.tsx` · `CustomPlaceForm.test.tsx` · `PlaceMatchPanel.test.tsx`가 `Failed to resolve import "./PlacePhoto"`(등)로 실패한다(구현 파일이 아직 없다). 과제 8의 시험과 `placeHandoff.test.ts`는 통과한다.

실행(백엔드 필요 - 위 '사전 준비'): `cd frontend && node scripts/run-backend-command.cjs npx vitest run src/app/__tests__/trip-place-basket.test.tsx src/app/__tests__/trip-detail.test.tsx`
기대: FAIL 17개(관찰한 값).
- `trip-place-basket.test.tsx` 13개(새 시험 15개 중). 메시지는 `expected "matchPlace" to be called with ...`(옛 구현은 맞춰 보기를 부르지 않는다), `Unable to find role="region" and name "이 장소가 맞나요?"`, `Unable to find role="form" and name "나만의 장소"`, `Unable to find an accessible element with the role "button" and name "찾는 곳이 없어요 · 직접 적기"`, `Unable to find role="status"`, `Unable to find an element with the text: 화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.`, `Unable to find an element with the text: 장소 검색을 지금 쓸 수 없어요. 직접 적기로 담을 수 있어요.` 중 하나다. 나머지 둘(`keeps the generic message and no refresh button for other save failures` · `keeps the generic message for a 422 about a value rather than the request shape`)은 옛 구현에서도 통과하는 보호 시험이다.
- `trip-detail.test.tsx` 4개: `keeps the add-sheet search-only before a place selection`(입구 버튼이 없다), `keeps matched public places in an add-sheet place basket` · `opens the add sheet with a place handed over from the home search and saves it on the picked day`(`matchPlace` 호출이 없다), `saves an add-sheet place basket with one batch request and closes the sheet`(옛 카카오 값 요청이 간다).
- 나머지 `trip-detail.test.tsx` 시험(저장 실패 · 충돌 · Day 복구 네 개 포함)은 지금도 통과한다 - 옛 구현이 새 후보 mock 을 그대로 담기 때문이다.

이 과제에서 새로 더한 동작의 시험이 정말 그 동작을 지키는지는 구현을 다 쓴 뒤(4단계) 아래 한 조각씩만 되돌려 확인했다(계획서를 겹친 작업장에서 되돌리고 돌린 뒤 원래대로 돌렸다). 직접 돌려 볼 때 쓴다.
- `PlaceMatchPanel.tsx` 의 `key={state.pickId}` 한 줄을 빼면 `PlaceMatchPanel.test.tsx` 의 두 시험이 `expect(element).toHaveValue()  Expected the element to have value:  Received: 앞 장소에 적던 이름` 으로 실패한다. 이 시험들이 위치 없는 결과를 연달아 고르는 일을 재현한다. `trip-place-basket.test.tsx` 의 `starts the custom place form empty for each picked result ...` 는 이 줄이 없어도 통과한다 - 검색창에 입력하면 맞춰 보던 것을 놓아 칸이 먼저 닫히기 때문이다(그 길을 지키는 보호 시험이다).
- `MapPointPicker.tsx` 에서 `panBy` 줄을 빼면 `AssertionError: expected [] to deeply equal [ [ 60, +0 ], [ +0, 60 ], ...]`, Enter 가지를 빼면 `expected "vi.fn()" to be called once with arguments: [ { latitude: 34.771, ... } ]`, 지도 누르기 줄(`map.setCenter(event.latLng)`)을 빼면 `expected "vi.fn()" to be called 2 times, but got 0 times` 로 실패한다.
- 추가 창 묶음 저장의 `else if (isStaleScreenError(error))` 가지를 빼면 `Unable to find an element with the text: 화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.`, 시트의 `새로 고침` 단추를 빼면 `Unable to find an accessible element with the role "button" and name "새로 고침"` 으로 실패한다.
- 검색 실패의 `error.status === 503` 가지를 빼면 `Unable to find an element with the text: 장소 검색을 지금 쓸 수 없어요. 직접 적기로 담을 수 있어요.` 로 실패한다.
- 코덱스 재검토로 더한 시험도 같은 방법으로 확인했다. `isStaleScreenError` 를 `status === 422` 만 보게 되돌리면 `keeps the generic message for a 422 about a value rather than the request shape` 가 `Unable to find an element with the text: /입력값을 확인하고 다시 시도해 주세요/` 로, `MapPointPicker.tsx` 의 `idle` 줄을 빼면 알림 시험이 `toHaveTextContent` 에서, 단추의 범위 검사(`disabled={!inside}`)를 빼면 `toBeDisabled` 에서, 고르기의 범위 검사를 빼면 `expected "vi.fn()" to not be called at all` 로, 확대 키를 빼면 `expected true to be false` 로, 확대 범위(1 ~ 14)를 빼면 `expected [ 12, 11, 12, 13, 14, 15 ] to deeply equal [ 12, 11, 12, 13, 14 ]` 로 실패한다.

- [ ] **3단계: 구현**

**3-1. 지도 타입** - 위치 찍기가 쓰는 클릭 이벤트 · 좌표 읽기 · 지도 가운데 읽기 · 지도 옮기기를 타입에 더한다. 기존 호출(`() => ...` 핸들러)은 그대로 맞는다.

**고치기 `frontend/src/lib/kakaoMap.ts`**

찾기:

```ts
export type KakaoMapsNamespace = {
  maps: {
    LatLng: new (lat: number, lng: number) => unknown;
```

바꾸기:

```ts
/** 카카오맵 SDK 의 좌표 - 지도를 눌렀을 때 이벤트가 이것을 준다 */
export type KakaoLatLng = { getLat: () => number; getLng: () => number };
/** 지도를 눌렀을 때(click) 이벤트 */
export type KakaoMouseEvent = { latLng: KakaoLatLng };

export type KakaoMapsNamespace = {
  maps: {
    LatLng: new (lat: number, lng: number) => KakaoLatLng;
```

찾기:

```ts
    Map: new (container: HTMLElement, options: Record<string, unknown>) => {
      setBounds: (bounds: unknown) => void;
      setCenter: (latLng: unknown) => void;
    };
```

바꾸기:

```ts
    Map: new (container: HTMLElement, options: Record<string, unknown>) => {
      setBounds: (bounds: unknown) => void;
      setCenter: (latLng: unknown) => void;
      /** 지도 가운데 - 위치 찍기가 십자선이 가리키는 곳을 읽는다 */
      getCenter: () => KakaoLatLng;
      /** 지도를 화면 픽셀만큼 옮긴다(양수 dx = 오른쪽, 양수 dy = 아래쪽) - 방향키로 옮길 때 쓴다 */
      panBy: (dx: number, dy: number) => void;
      /** 확대 수준(1 이 가장 가깝다) - 위치 찍기의 + · - 키가 한 단계씩 바꾼다 */
      getLevel: () => number;
      setLevel: (level: number) => void;
    };
```

찾기:

```ts
    event: { addListener: (target: unknown, eventName: string, handler: () => void) => void };
```

바꾸기:

```ts
    event: { addListener: (target: unknown, eventName: string, handler: (event: KakaoMouseEvent) => void) => void };
```

**3-2. 화면 부품** - 공용 `PlacePhoto`와 `placeAdd/`의 부품 넷이다. 모양(마크업 · 문구 · 클래스)은 시안 v59가 확정한다. 데이터 흐름(props · 콜백)은 그대로 둔다.

**새 파일 `frontend/src/components/itinerary/PlacePhoto.tsx`** - 공공데이터 사진과 출처를 그리는 공용 부품이다. 후보 카드(이 과제)와 일정 장소 카드 · 추천 미리보기(과제 11)가 같이 쓴다. 모양(크기 · 칩 위치)은 시안 v59가 확정한다.

```tsx
import { useState } from "react";
import { mediaUrl } from "../../api";
import { photoCredit } from "./placeAdd/publicPlaceText";

/* 공공데이터(한국관광공사) 사진 한 장과 출처 칩. url 이 비면 아무것도 그리지 않는다.
   사진이 죽으면 출처 글도 함께 숨는다 - 사진 없이 출처만 남지 않게. 다른 url 이 오면 다시 시도한다 */
export function PlacePhoto({
  url,
  license,
  alt,
  compact = false,
}: {
  url?: string | null;
  license?: string | null;
  alt: string;
  compact?: boolean;
}) {
  const [brokenUrl, setBrokenUrl] = useState<string | null>(null);
  if (!url || brokenUrl === url) return null;
  return (
    <span className={compact ? "place-photo place-photo--compact" : "place-photo"}>
      <img alt={alt} loading="lazy" onError={() => setBrokenUrl(url)} src={mediaUrl(url)} />
      <span className="place-photo-credit">{photoCredit(license)}</span>
    </span>
  );
}
```

**새 파일 `frontend/src/components/itinerary/placeAdd/PlaceMatchChoices.tsx`**

```tsx
import type { PublicPlaceItem } from "../../../api";
import { PlacePhoto } from "../PlacePhoto";
import { PUBLIC_CATEGORY_LABEL, distanceText } from "./publicPlaceText";

/* '이 장소가 맞나요?' - 맞춰 보기에서 후보가 하나뿐이 아니거나 분류가 안 맞을 때. 후보는 모두 공공데이터 값이다(카카오 값 아님) */
export function PlaceMatchChoices({
  candidates,
  onChoose,
  onNone,
}: {
  candidates: PublicPlaceItem[];
  onChoose: (place: PublicPlaceItem) => void;
  onNone: () => void;
}) {
  return (
    <section aria-label="이 장소가 맞나요?" className="place-match-choices">
      <div className="place-match-head">
        <strong>이 장소가 맞나요?</strong>
        {/* 시안 v59 */}
        <p>고른 곳과 비슷한 곳을 찾았어요. 맞는 곳을 누르면 목록에 담겨요.</p>
      </div>
      <div className="place-match-list" role="list">
        {candidates.map((place) => (
          <div key={`${place.source}:${place.sourceId}`} role="listitem">
            <button
              aria-label={`${place.name} 선택`}
              className={place.photoUrl ? "place-match-card has-photo" : "place-match-card"}
              onClick={() => onChoose(place)}
              type="button"
            >
              <PlacePhoto alt="" compact license={place.photoLicense} url={place.photoUrl} />
              <span className="place-match-body">
                <strong>{place.name}</strong>
                <em>{PUBLIC_CATEGORY_LABEL[place.category]}</em>
                <small>{place.address ?? "주소 정보 없음"}</small>
                <small>{distanceText(place.distanceMeters)}</small>
              </span>
            </button>
          </div>
        ))}
      </div>
      {/* 시안 v59 */}
      <button className="btn sm line place-match-none" onClick={onNone} type="button">
        아니요, 직접 적을게요
      </button>
    </section>
  );
}
```

**새 파일 `frontend/src/components/itinerary/placeAdd/MapPointPicker.tsx`**

```tsx
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { appDataApi, useAsyncResource, type ItineraryPlace, type TripAreaCenter } from "../../../api";
import { loadKakaoMaps, type KakaoMapsNamespace } from "../../../lib/kakaoMap";

export type MapPoint = { latitude: number; longitude: number };

/** 일정 지역도 공공데이터 장소도 가릴 수 없을 때 여는 자리 - 대한민국 가운데 */
export const KOREA_CENTER: MapPoint = { latitude: 36.5, longitude: 127.8 };
const AREA_LEVEL = 6;
const COUNTRY_LEVEL = 13;
/** 카카오 지도의 확대 수준 범위 - 1 이 가장 가깝고 14 가 가장 넓다 */
const MIN_LEVEL = 1;
const MAX_LEVEL = 14;
/** 방향키 한 번에 지도를 옮기는 화면 픽셀(양수 dx = 오른쪽, 양수 dy = 아래쪽) */
const KEY_PAN_PX = 60;
const PAN_KEYS: Record<string, [number, number]> = {
  ArrowLeft: [-KEY_PAN_PX, 0],
  ArrowRight: [KEY_PAN_PX, 0],
  ArrowUp: [0, -KEY_PAN_PX],
  ArrowDown: [0, KEY_PAN_PX],
};
/** 확대 · 축소 키 - 한 번에 한 단계(수준이 작을수록 가깝다). '=' 는 Shift 없이 누른 '+' 자리다 */
const ZOOM_KEYS: Record<string, number> = { "+": -1, "=": -1, "-": 1 };

type KakaoMap = InstanceType<KakaoMapsNamespace["maps"]["Map"]>;

/* 지도가 처음 여는 자리. 일정 지역 중심 → 일정에 이미 담긴 공공데이터 장소 → 대한민국 가운데 순이다.
   고른 카카오 장소의 좌표로는 열지 않는다 - 사용자가 누른 점이 사실상 카카오 좌표가 되는 우회를 막는다(설계 2절) */
export function pickerStart(
  area: TripAreaCenter | null,
  fallback: MapPoint | null,
): { center: MapPoint; level: number } {
  if (area && typeof area.latitude === "number" && typeof area.longitude === "number") {
    return { center: { latitude: area.latitude, longitude: area.longitude }, level: AREA_LEVEL };
  }
  if (fallback) return { center: fallback, level: AREA_LEVEL };
  return { center: KOREA_CENTER, level: COUNTRY_LEVEL };
}

/** 일정에 이미 담긴 공공데이터 장소 중 첫 좌표(Day 순서) - 지역 중심을 못 받았을 때 대신 쓴다 */
export function firstPublicPlacePoint(days: Record<number, ItineraryPlace[]>): MapPoint | null {
  const dayNumbers = Object.keys(days)
    .map(Number)
    .filter((day) => Number.isFinite(day))
    .sort((a, b) => a - b);
  for (const day of dayNumbers) {
    for (const place of days[day] ?? []) {
      if (
        place.placeOrigin === "public" &&
        typeof place.latitude === "number" &&
        typeof place.longitude === "number"
      ) {
        return { latitude: place.latitude, longitude: place.longitude };
      }
    }
  }
  return null;
}

const round6 = (value: number) => Math.round(value * 1e6) / 1e6;

/** 십자선 밑의 자리 - 소수 여섯 자리까지만 남긴다 */
function centerOf(map: KakaoMap): MapPoint {
  const point = map.getCenter();
  return { latitude: round6(point.getLat()), longitude: round6(point.getLng()) };
}

/** 서버가 받는 나만의 장소 위치 범위(customPlace 의 위도 33 ~ 39, 경도 124 ~ 132)와 같다 */
function isInKorea(point: MapPoint): boolean {
  return point.latitude >= 33 && point.latitude <= 39 && point.longitude >= 124 && point.longitude <= 132;
}

/* 지도에서 위치 찍기(나만의 장소의 선택 사항). 십자선은 지도 가운데에 고정돼 있고 지도를 옮겨 맞춘다:
   끌기 · 누르기(누른 자리가 가운데로 온다) · 방향키(지도가 화면 픽셀만큼 옮겨 간다) · + · -(확대 · 축소). '이 위치로' 단추나 Enter 가 십자선 밑의 자리를 고른다.
   마우스 없이도 쓸 수 있게 지도 칸이 초점을 받고 이름이 있다. 열리면 지도에 초점을 두어 바로 방향키를 쓴다.
   지도가 멈출 때마다 가운데를 상태 한 줄로 알린다 - 화면을 보지 못해도 어디를 고르는지 안다. 대한민국 밖은 고르지 않는다(서버도 받지 않는다) */
export function MapPointPicker({
  tripId,
  fallbackCenter = null,
  onPick,
  onCancel,
}: {
  tripId: string;
  fallbackCenter?: MapPoint | null;
  onPick: (point: MapPoint) => void;
  onCancel: () => void;
}) {
  const { data: area, isLoading } = useAsyncResource(() => appDataApi.getTripAreaCenter(tripId), [tripId]);
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<KakaoMap | null>(null);
  // 지도가 마지막으로 멈춘 자리의 가운데 - 지도가 뜨기 전에는 null
  const [center, setCenterPoint] = useState<MapPoint | null>(null);
  const [failed, setFailed] = useState(false);
  const helpId = useId();
  // 중심 요청이 실패해도(data 가 null) 지도는 연다 - fallbackCenter 나 대한민국 가운데에서
  const start = pickerStart(area, fallbackCenter);
  const inside = center !== null && isInKorea(center);

  useEffect(() => {
    if (isLoading || failed || !canvasRef.current) return;
    let disposed = false;
    loadKakaoMaps()
      .then((kakao) => {
        const canvas = canvasRef.current;
        if (disposed || !canvas) return;
        const map = new kakao.maps.Map(canvas, {
          center: new kakao.maps.LatLng(start.center.latitude, start.center.longitude),
          level: start.level,
        });
        mapRef.current = map;
        // 누른 자리가 십자선 밑(가운데)으로 온다 - 핀을 따로 꽂지 않는다
        kakao.maps.event.addListener(map, "click", (event) => map.setCenter(event.latLng));
        // 끌기 · 방향키 · 확대 · 축소가 끝나 지도가 멈추면 가운데를 다시 읽는다 - 알림과 '이 위치로' 켜기에 쓴다
        const readCenter = () => {
          if (!disposed) setCenterPoint(centerOf(map));
        };
        kakao.maps.event.addListener(map, "idle", readCenter);
        readCenter();
        // 방향키를 바로 쓰게 지도에 초점을 둔다. 그 사이 사용자가 다른 곳에 초점을 뒀으면 뺏지 않는다
        if (!document.activeElement || document.activeElement === document.body) canvas.focus();
      })
      .catch(() => {
        if (!disposed) setFailed(true);
      });
    return () => {
      disposed = true;
      mapRef.current = null;
    };
  }, [isLoading, start.center.latitude, start.center.longitude, start.level]);

  const pickCenter = () => {
    const map = mapRef.current;
    if (!map) return;
    // 멈추기 전(알림 전)에 눌러도 지금 가운데로 다시 본다 - 대한민국 밖은 고르지 않는다
    const point = centerOf(map);
    if (isInKorea(point)) onPick(point);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    // 브라우저 단축키(Alt+← 뒤로가기, Ctrl+- 화면 축소 등)는 건드리지 않는다
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const map = mapRef.current;
    const pan = PAN_KEYS[event.key];
    const zoom = ZOOM_KEYS[event.key];
    if (pan) {
      event.preventDefault();
      map?.panBy(pan[0], pan[1]);
    } else if (zoom) {
      event.preventDefault();
      if (!map) return;
      const level = Math.min(MAX_LEVEL, Math.max(MIN_LEVEL, map.getLevel() + zoom));
      if (level !== map.getLevel()) map.setLevel(level);
    } else if (event.key === "Enter") {
      event.preventDefault();
      pickCenter();
    }
  };

  return (
    <section aria-label="지도에서 위치 찍기" className="map-point-picker">
      {failed ? (
        <p className="form-error">지도를 불러오지 못했어요. 위치 없이 이름만 담을 수 있어요.</p>
      ) : isLoading ? (
        <p className="place-search-status" role="status">
          지도를 준비하는 중이에요.
        </p>
      ) : (
        <>
          {/* 시안 v59 */}
          <p className="map-point-picker-help" id={helpId}>
            지도를 끌거나 눌러서 십자선을 원하는 곳에 맞추세요. 키보드로는 방향키로 지도를 옮기고 + · - 로 확대 · 축소하고 Enter 로 고릅니다.
          </p>
          <div className="map-point-picker-map">
            <div
              aria-describedby={helpId}
              aria-label="위치 고르기 지도"
              className="map-point-picker-canvas"
              onKeyDown={handleKeyDown}
              ref={canvasRef}
              role="application"
              tabIndex={0}
            />
            {/* 시안 v59: 가운데에 고정된 십자선 - 지도가 움직이고 십자선은 그대로다 */}
            <span aria-hidden="true" className="map-point-picker-pin" />
          </div>
          {/* 시안 v59: 지도가 멈출 때마다 바뀌는 상태 한 줄 - 대한민국 안이면 화면에는 숨기고(화면 읽기 프로그램만 읽는다) 밖이면 보인다 */}
          <p className={center && !inside ? "form-error" : "sr-only"} role="status">
            {center === null
              ? ""
              : inside
                ? `지도 가운데 위도 ${center.latitude.toFixed(4)}, 경도 ${center.longitude.toFixed(4)}`
                : "대한민국 밖이에요. 대한민국 안으로 옮겨 주세요."}
          </p>
        </>
      )}
      <div className="map-point-picker-actions">
        <button className="btn sm line" onClick={onCancel} type="button">
          취소
        </button>
        <button className="btn sm primary" disabled={!inside} onClick={pickCenter} type="button">
          이 위치로
        </button>
      </div>
    </section>
  );
}
```

**새 파일 `frontend/src/components/itinerary/placeAdd/CustomPlaceForm.tsx`**

```tsx
import { useEffect, useRef, useState, type FormEvent } from "react";
import { hasKakaoMapKey } from "../../../lib/kakaoMap";
import { Button } from "../../ui";
import { MapPointPicker, type MapPoint } from "./MapPointPicker";

export type CustomPlaceReason = "none" | "noCoords" | "failed" | "direct";

/* 왜 이 칸이 열렸는지 한 줄. 시안 v59 */
const INTRO: Record<CustomPlaceReason, string> = {
  none: "우리 장소 목록에서 같은 곳을 찾지 못했어요. 이름을 직접 적어 담을 수 있어요.",
  noCoords: "이 장소는 위치 정보가 없어서 우리 장소 목록과 맞춰 보지 못했어요. 이름을 직접 적어 담을 수 있어요.",
  failed: "장소를 맞춰 보지 못했어요. 이름을 직접 적어 담을 수 있어요.",
  direct: "찾는 곳의 이름을 직접 적어 담을 수 있어요.",
};

/* 나만의 장소 - 사용자가 쓴 이름과(선택) 지도에서 찍은 위치만 저장한다.
   이름 칸은 비어 있다: 카카오 이름을 미리 채우지도, 옆에 보여 주지도, placeholder 로 쓰지도 않는다(카카오 운영정책).
   그래서 이 부품은 카카오 이름을 받는 props 가 아예 없다 */
export function CustomPlaceForm({
  reason,
  tripId,
  fallbackCenter,
  onSubmit,
  onCancel,
}: {
  reason: CustomPlaceReason;
  tripId: string;
  fallbackCenter: MapPoint | null;
  onSubmit: (input: { name: string; latitude: number | null; longitude: number | null }) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState("");
  const [point, setPoint] = useState<MapPoint | null>(null);
  const [picking, setPicking] = useState(false);
  const nameRef = useRef<HTMLInputElement | null>(null);
  const reopenRef = useRef<HTMLButtonElement | null>(null);
  const wasPicking = useRef(false);
  const trimmed = name.trim();

  useEffect(() => {
    nameRef.current?.focus();
  }, []);

  useEffect(() => {
    // 위치 찍기를 닫으면(고르기 · 취소) 초점이 사라지지 않게 다시 찍는 단추로 되돌린다
    if (wasPicking.current && !picking) reopenRef.current?.focus();
    wasPicking.current = picking;
  }, [picking]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!trimmed) return;
    onSubmit({ name: trimmed, latitude: point?.latitude ?? null, longitude: point?.longitude ?? null });
  };

  return (
    <form aria-label="나만의 장소" className="custom-place-form" onSubmit={submit}>
      <p className="custom-place-intro">{INTRO[reason]}</p>
      <label className="field">
        장소 이름
        <input
          maxLength={100}
          name="custom-place-name"
          onChange={(event) => setName(event.target.value)}
          placeholder="예: 할머니 댁, 숙소 앞 편의점"
          ref={nameRef}
          value={name}
        />
      </label>
      {picking ? (
        <MapPointPicker
          fallbackCenter={fallbackCenter}
          onCancel={() => setPicking(false)}
          onPick={(next) => {
            setPoint(next);
            setPicking(false);
          }}
          tripId={tripId}
        />
      ) : point ? (
        <div className="custom-place-point">
          <span>지도에서 위치를 찍었어요</span>
          <button className="btn sm ghost" onClick={() => setPicking(true)} ref={reopenRef} type="button">
            다시 찍기
          </button>
          <button className="btn sm ghost" onClick={() => setPoint(null)} type="button">
            지우기
          </button>
        </div>
      ) : (
        hasKakaoMapKey() && (
          <button className="btn sm line" onClick={() => setPicking(true)} ref={reopenRef} type="button">
            지도에서 위치 찍기
          </button>
        )
      )}
      <div className="custom-place-actions">
        <Button onClick={onCancel} variant="line">
          취소
        </Button>
        <Button disabled={!trimmed} type="submit">
          담기
        </Button>
      </div>
    </form>
  );
}
```

**새 파일 `frontend/src/components/itinerary/placeAdd/PlaceMatchPanel.tsx`**

```tsx
import type { PublicPlaceItem } from "../../../api";
import { CustomPlaceForm } from "./CustomPlaceForm";
import type { MapPoint } from "./MapPointPicker";
import { PlaceMatchChoices } from "./PlaceMatchChoices";
import type { PlaceMatchState } from "./usePlaceMatch";

/* 장소 추가 시트 한 칸에 꽂는 갈래 고르기: 평소에는 '직접 적기' 입구, 고른 검색 결과를 맞춰 보는 동안에는 상태에 맞는 부분 하나 */
export function PlaceMatchPanel({
  state,
  tripId,
  fallbackCenter,
  onChooseCandidate,
  onChooseCustom,
  onStartDirect,
  onSubmitCustom,
  onCancel,
}: {
  state: PlaceMatchState;
  tripId: string;
  fallbackCenter: MapPoint | null;
  onChooseCandidate: (place: PublicPlaceItem) => void;
  onChooseCustom: () => void;
  onStartDirect: () => void;
  onSubmitCustom: (input: { name: string; latitude: number | null; longitude: number | null }) => void;
  onCancel: () => void;
}) {
  if (state.status === "matching") {
    return (
      <p className="place-search-status" role="status">
        {/* 시안 v59 */}
        우리 장소 목록과 맞춰 보는 중이에요.
      </p>
    );
  }
  if (state.status === "choose") {
    return <PlaceMatchChoices candidates={state.candidates} onChoose={onChooseCandidate} onNone={onChooseCustom} />;
  }
  if (state.status === "custom") {
    return (
      <CustomPlaceForm
        fallbackCenter={fallbackCenter}
        key={state.pickId}
        onCancel={onCancel}
        onSubmit={onSubmitCustom}
        reason={state.reason}
        tripId={tripId}
      />
    );
  }
  return (
    <button className="place-direct-entry" onClick={onStartDirect} type="button">
      {/* 시안 v59 */}
      찾는 곳이 없어요 · 직접 적기
    </button>
  );
}
```

**3-3. 스타일** - 토큰(`--primary-*` · `--gray-*`)만 쓴다. 규칙 묶음 전체가 시안 v59 대상이다.

**고치기 `frontend/src/styles/app.css`**

찾기:

```css
.place-preview-helper {
  margin: 0;
  color: var(--gray-600);
  font-size: 12px;
  font-weight: 800;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.place-time-picker {
```

바꾸기:

```css
.place-preview-helper {
  margin: 0;
  color: var(--gray-600);
  font-size: 12px;
  font-weight: 800;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

/* 시안 v59: 담는 흐름 - '직접 적기' 입구 · 후보 확인 · 나만의 장소 · 위치 찍기 */
.place-direct-entry {
  min-height: 44px;
  padding: 0 12px;
  border: 1px dashed var(--primary-500);
  border-radius: var(--radius-sm);
  background: var(--primary-50);
  color: var(--primary-600);
  font-size: 13px;
  font-weight: 800;
  text-align: left;
}

.place-direct-entry:hover,
.place-direct-entry:focus-visible {
  border-style: solid;
  outline: none;
  box-shadow: 0 0 0 3px rgba(var(--primary-rgb), 0.12);
}

.place-match-choices,
.custom-place-form {
  display: grid;
  gap: 10px;
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-sm);
  background: var(--primary-50);
}

.place-match-head strong {
  display: block;
  color: var(--ink);
  font-size: 14px;
  font-weight: 900;
}

.place-match-head p,
.custom-place-intro {
  margin: 4px 0 0;
  color: var(--gray-600);
  font-size: 12px;
  line-height: 1.45;
}

.place-match-list {
  display: grid;
  gap: 8px;
}

.place-match-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: start;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-sm);
  background: var(--white);
  color: var(--ink);
  text-align: left;
}

.place-match-card.has-photo {
  grid-template-columns: 72px minmax(0, 1fr);
}

.place-match-card:hover,
.place-match-card:focus-visible {
  border-color: var(--primary-500);
  outline: none;
  box-shadow: 0 0 0 3px rgba(var(--primary-rgb), 0.12);
}

.place-photo {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.place-photo img {
  width: 100%;
  aspect-ratio: 16 / 10;
  object-fit: cover;
  border-radius: var(--radius-sm);
  background: var(--gray-100);
}

.place-photo-credit {
  color: var(--gray-500);
  font-size: 11px;
  line-height: 1.3;
}

.place-photo--compact {
  width: 72px;
}

.place-photo--compact img {
  height: 56px;
  aspect-ratio: auto;
  border-radius: var(--radius-xs);
}

.place-photo--compact .place-photo-credit {
  font-size: 10px;
}

.place-match-body {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.place-match-body strong {
  font-size: 14px;
  overflow-wrap: anywhere;
}

.place-match-body em {
  color: var(--primary-600);
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.place-match-body small {
  color: var(--gray-600);
  font-size: 12px;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.custom-place-point {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--primary-600);
  font-size: 12px;
  font-weight: 800;
}

.custom-place-actions,
.map-point-picker-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.map-point-picker {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.map-point-picker-help {
  margin: 0;
  color: var(--gray-600);
  font-size: 12px;
  font-weight: 700;
}

.map-point-picker-map {
  position: relative;
}

.map-point-picker-canvas {
  height: 220px;
  overflow: hidden;
  isolation: isolate;
  border: 1px solid var(--gray-200);
  border-radius: var(--radius-sm);
  background: var(--gray-100);
}

.map-point-picker-canvas:focus-visible {
  outline: 3px solid var(--primary-500);
  outline-offset: 2px;
}

/* 지도 가운데에 고정된 십자선 - 지도가 움직이고 십자선은 그대로다. 누르기 · 끌기는 지도로 보낸다 */
.map-point-picker-pin {
  position: absolute;
  top: 50%;
  left: 50%;
  z-index: 1;
  width: 28px;
  height: 28px;
  margin: -14px 0 0 -14px;
  border: 2px solid var(--primary-600);
  border-radius: 50%;
  background: rgba(var(--primary-rgb), 0.12);
  box-shadow: 0 0 0 2px var(--white);
  pointer-events: none;
}

.map-point-picker-pin::before,
.map-point-picker-pin::after {
  content: "";
  position: absolute;
  background: var(--primary-600);
}

.map-point-picker-pin::before {
  top: 50%;
  right: -8px;
  left: -8px;
  height: 2px;
  margin-top: -1px;
}

.map-point-picker-pin::after {
  top: -8px;
  bottom: -8px;
  left: 50%;
  width: 2px;
  margin-left: -1px;
}

.place-time-picker {
```

**3-4. 홈 넘김 정리(컴파일에 필요한 만큼만)** - 카카오 값을 저장 요청 모양으로 옮기던 `tripPlaceFromSearchItem`만 지운다(받는 쪽은 `usePlaceMatch.pick`을 부른다). 이 파일은 과제 12의 몫이라 나머지(`readPlaceParam` · `writePlaceParam`, 새 형식 `readAddPlaceParam`)는 건드리지 않는다.

**고치기 `frontend/src/utils/placeHandoff.ts`**

찾기:

```ts
import type { PlaceSearchItem, TripPlaceRequest } from "../api";
```

바꾸기:

```ts
import type { PlaceSearchItem } from "../api";
```

찾기:

```ts

/** 일정 장소로 - 일정 안 장소 검색(GET /trips/{id}/place-search)이 같은 카카오 장소를 담을 때와 같은 값이 되게 */
export function tripPlaceFromSearchItem(item: PlaceSearchItem): TripPlaceRequest {
  return {
    time: "",
    label: item.name,
    meta: [item.category, item.address].filter(Boolean).join(" · ") || "장소 정보 확인",
    address: item.address ?? null,
    latitude: item.latitude ?? null,
    longitude: item.longitude ?? null,
    category: item.category ?? null,
    categoryCode: item.categoryCode ?? null,
    placeUrl: item.placeUrl ?? null,
    sourceProvider: "kakao",
    externalPlaceId: item.id.startsWith("kakao:") ? item.id.slice("kakao:".length) : item.id,
  };
}
```

바꾸기:

```ts
```

**3-5. 일정 상세 화면 연결** - `ItineraryDetailPage.tsx`를 위에서 아래로 고친다. 추가 경로만 만지고 새 논리는 `placeAdd/`에 있다. 아래 `찾기` 글은 과제 7까지 적용한 파일과 글자 그대로 맞아야 한다(맞지 않으면 다른 부분 과제가 같은 줄을 먼저 고친 것이니 그쪽 모양에 맞춰 옮긴다).

**고치기 `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`**

가져오기부터. `ReactNode`를 react 가져오기에 더한다.

찾기:

```tsx
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
```

바꾸기:

```tsx
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
```

옛 값 묶음 타입 둘(`TripPlaceMutationRequest` · `TripPlaceRequest`)은 더 쓰지 않는다. 대신 `CustomPlaceInput`을 가져온다.

찾기:

```tsx
  isApiError,
  type ItineraryPlace,
  type LinkedTripPolicy,
  type PlaceSearchCandidate,
  type Recommendation,
  type Trip,
  type TripPlaceMutationRequest,
  type TripPlaceRequest,
} from "../../api";
```

바꾸기:

```tsx
  isApiError,
  type CustomPlaceInput,
  type ItineraryPlace,
  type LinkedTripPolicy,
  type PlaceSearchCandidate,
  type Recommendation,
  type Trip,
} from "../../api";
```

찾기:

```tsx
import { readPlaceParam, tripPlaceFromSearchItem } from "../../utils/placeHandoff";
```

바꾸기:

```tsx
import { readPlaceParam } from "../../utils/placeHandoff";
import { firstPublicPlacePoint } from "../../components/itinerary/placeAdd/MapPointPicker";
import {
  basketItemBadge,
  basketItemDetail,
  basketItemPayload,
  basketItemTitle,
  customBasketItem,
  type PlaceBasketItem,
} from "../../components/itinerary/placeAdd/placeBasket";
import { PlaceMatchPanel } from "../../components/itinerary/placeAdd/PlaceMatchPanel";
import { usePlaceMatch, type PlacePickInput } from "../../components/itinerary/placeAdd/usePlaceMatch";
```

타입들. 수정 창이 아직 들고 있는 옛 값 묶음은 화면 안으로 옮기고(`PlaceEditorForm`), 바구니 타입은 새 모듈 것을 쓴다.

찾기:

```tsx
type TripPlaceEditDraft = TripPlaceRequest & {
  placeId: string;
};
```

바꾸기:

```tsx
/* 수정 창이 아직 들고 있는 옛 값 묶음(옛 TripPlaceRequest) - 수정 · 초안 과제(3단계)가 카카오 값 복사와 함께 줄인다.
   추가 흐름과 저장 요청(TripPlaceAddItem)은 쓰지 않는다 */
type PlaceEditorForm = {
  time?: string;
  label: string;
  meta?: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  category?: string | null;
  categoryCode?: string | null;
  placeUrl?: string | null;
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
};
type TripPlaceEditDraft = PlaceEditorForm & {
  placeId: string;
};
```

찾기:

```tsx
type PlaceBasketItem = TripPlaceRequest & {
  basketId: string;
};
type BatchPlaceRecovery =
```

바꾸기:

```tsx
type BatchPlaceRecovery =
```

찾기:

```tsx
type PlacePreviewCandidate = TripPlaceRequest & {
  previewId: string;
  source: Exclude<PlacePreviewSource, "empty">;
  dayNumber: number;
};
```

바꾸기:

```tsx
/* 지도 미리보기 한 곳 - 화면에 그리기만 한다(저장 요청으로 나가지 않는다).
   카카오 검색 결과는 실시간 표시로만 쓰고, 담은 장소는 공공데이터 값이나 사용자가 쓴 값이다 */
type PlacePreviewCandidate = {
  previewId: string;
  source: Exclude<PlacePreviewSource, "empty">;
  dayNumber: number;
  label: string;
  meta?: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
};
```

추천 미리보기 쪽 함수는 지우지 않는다. 옛 값 묶음 타입 이름만 걷고 안내 주석을 단다.

찾기:

```tsx
function recommendationPlacePayload(
  item: Recommendation,
  time: string | undefined,
): TripPlaceRequest {
```

바꾸기:

```tsx
/* 추천 미리보기 부분 과제(3단계)가 publicPlace 참조로 바꾼다 - 그때까지 옛 값 묶음을 그대로 돌려준다 */
function recommendationPlacePayload(
  item: Recommendation,
  time: string | undefined,
) {
```

추천 미리보기에서 시간만 바꾼 기존 장소의 저장은 바뀐 필드(`time`)만 보낸다. `ItineraryPlace` 전체를 펴 보내면 새 `memo` 타입이 요청과 어긋나고(과제 7), 3단계 백엔드(`extra=forbid`)도 거부한다. 같은 호출의 기대 값(`expect.objectContaining({ time, expectedRevision })`)은 그대로 맞는다.

찾기:

```tsx
          currentTrip = await appDataApi.updateTripPlace(
            currentTrip.id,
            place.id,
            {
              ...currentPlace,
              time: place.time ?? "",
              expectedRevision: currentTrip.revision,
            },
          );
```

바꾸기:

```tsx
          currentTrip = await appDataApi.updateTripPlace(
            currentTrip.id,
            place.id,
            { time: place.time ?? "", expectedRevision: currentTrip.revision },
          );
```

쓰는 곳이 없는 함수 셋을 지운다(`previewPlaceFromRecommendation` · `tripPlaceMutationFromPreviewPlace` · `previewFromRecommendation`).

찾기:

```tsx
function previewPlaceFromRecommendation(
  item: Recommendation,
  index: number,
  dayNumber: number,
): PreviewPlace {
  const payload = recommendationPlacePayload(
    item,
    recommendationPlaceTime(item),
  );
  return {
    previewId: recommendationPreviewId(item, index),
    dayNumber,
    time: payload.time,
    label: payload.label,
    meta: payload.meta,
    address: payload.address,
    latitude: payload.latitude,
    longitude: payload.longitude,
    category: payload.category,
    categoryCode: payload.categoryCode,
    placeUrl: payload.placeUrl,
    sourceProvider: payload.sourceProvider,
    externalPlaceId: payload.externalPlaceId,
  };
}

type RecommendationPreviewOrderFields = Pick<
```

바꾸기:

```tsx
type RecommendationPreviewOrderFields = Pick<
```

찾기:

```tsx
function tripPlaceMutationFromPreviewPlace(
  place: PreviewPlace,
  expectedRevision: number,
): TripPlaceMutationRequest {
  return {
    time: place.time ?? "",
    label: place.label,
    meta: place.meta,
    address: place.address,
    latitude: place.latitude,
    longitude: place.longitude,
    category: place.category,
    categoryCode: place.categoryCode,
    placeUrl: place.placeUrl,
    sourceProvider: place.sourceProvider,
    externalPlaceId: place.externalPlaceId,
    expectedRevision,
  };
}

function timelinePlaceFromPreviewPlace(
```

바꾸기:

```tsx
function timelinePlaceFromPreviewPlace(
```

추천 담기 함수는 반환 타입 이름만 걷는다(내용은 추천 부분 과제가 바꾼다).

찾기:

```tsx
function tripPlaceMutationFromDisplayedPlace(
  place: DisplayedPlace,
  expectedRevision: number,
): TripPlaceMutationRequest {
  return {
```

바꾸기:

```tsx
/* 추천 미리보기 부분 과제(3단계)가 publicPlace 참조로 바꾼다 - 그때까지 옛 값 묶음을 그대로 보낸다
   (3단계 백엔드는 거부하므로 그 과제가 끝나기 전에는 이 길을 손으로 시험하지 않는다) */
function tripPlaceMutationFromDisplayedPlace(
  place: DisplayedPlace,
  expectedRevision: number,
) {
  return {
```

카카오 값을 요청 모양으로 옮기던 추가 경로의 함수들을 지우고, 지도에 그리기만 하는 미리보기 만들기 둘로 바꾼다. 미리보기 마커는 이름으로 위치를 다시 찾지 않는다 - 카카오 검색 결과를 그릴 때만 예전처럼 찾고, 담은 장소는 좌표가 없으면 핀을 그리지 않는다.

찾기:

```tsx
function previewFromPayload(
  payload: TripPlaceRequest,
  source: Exclude<PlacePreviewSource, "empty">,
  dayNumber: number,
  previewId: string,
): PlacePreviewCandidate {
  return {
    ...payload,
    label: payload.label,
    meta: payload.meta ?? "",
    previewId,
    source,
    dayNumber,
  };
}

function previewFromRecommendation(
  item: Recommendation,
  index: number,
  dayNumber: number,
): PlacePreviewCandidate {
  const time = recommendationPlaceTime(item);
  return previewFromPayload(
    recommendationPlacePayload(item, time),
    "recommendation",
    dayNumber,
    recommendationPreviewId(item, index),
  );
}

function placeSearchCandidatePayload(
  item: PlaceSearchCandidate,
  time: string | undefined,
): TripPlaceRequest {
  return {
    time: time ?? "",
    label: item.title,
    meta: item.meta,
    address: item.address ?? null,
    latitude: item.latitude ?? null,
    longitude: item.longitude ?? null,
    category: item.categoryName ?? null,
    categoryCode: item.categoryCode ?? null,
    placeUrl: item.placeUrl ?? null,
    sourceProvider: item.sourceProvider ?? null,
    externalPlaceId: item.externalPlaceId ?? item.id ?? null,
  };
}

function previewFromSearchCandidate(
  item: PlaceSearchCandidate,
  dayNumber: number,
  source: "searchPreview" | "selected",
  time = "",
): PlacePreviewCandidate {
  return previewFromPayload(
    placeSearchCandidatePayload(item, time),
    source,
    dayNumber,
    item.id ??
      item.externalPlaceId ??
      `${item.title}:${item.address ?? item.meta}`,
  );
}

function placePreviewMarker(
  place: PlacePreviewCandidate,
): KakaoMapMarker | null {
  const query =
    place.address?.trim() || place.label.trim() || place.meta?.trim() || null;
  if (!place.label.trim() && !query) return null;
  return {
```

바꾸기:

```tsx
/* 카카오 검색 결과를 지도에 그리기만 한다(실시간 표시). 저장 요청에는 쓰지 않는다 */
function previewFromSearchResult(
  item: PlaceSearchCandidate,
  dayNumber: number,
): PlacePreviewCandidate {
  return {
    previewId:
      item.id ??
      item.externalPlaceId ??
      `${item.title}:${item.address ?? item.meta}`,
    source: "searchPreview",
    dayNumber,
    label: item.title,
    meta: item.meta,
    address: item.address ?? null,
    latitude: item.latitude ?? null,
    longitude: item.longitude ?? null,
  };
}

/* 방금 바구니에 담은 장소를 지도에 그린다 - 공공데이터 값이거나 사용자가 쓴 값이다 */
function previewFromBasketItem(
  item: PlaceBasketItem,
  dayNumber: number,
): PlacePreviewCandidate {
  if (item.kind === "public") {
    return {
      previewId: item.basketId,
      source: "selected",
      dayNumber,
      label: item.place.name,
      address: item.place.address ?? null,
      latitude: item.place.latitude,
      longitude: item.place.longitude,
    };
  }
  return {
    previewId: item.basketId,
    source: "selected",
    dayNumber,
    label: item.name,
    address: null,
    latitude: item.latitude,
    longitude: item.longitude,
  };
}

function placePreviewMarker(
  place: PlacePreviewCandidate,
): KakaoMapMarker | null {
  /* 이름으로 위치를 다시 찾는 건 카카오 검색 결과를 그릴 때만이다.
     담은 장소(공공데이터 · 나만의 장소)는 좌표가 없으면 핀을 그리지 않는다 - 이름이 곧 카카오 좌표가 되는 우회를 막는다 */
  const query =
    place.source === "searchPreview"
      ? place.address?.trim() || place.label.trim() || place.meta?.trim() || null
      : null;
  if (!place.label.trim() && !query) return null;
  return {
```

이제 컴포넌트 안이다. 상태 선언: 바구니 번호 ref를 지우고 맞춰 보기 훅을 둔다.

찾기:

```tsx
  const placeSearchAbortControllerRef = useRef<AbortController | null>(null);
  const placeBasketIdRef = useRef(0);
```

바꾸기:

```tsx
  const placeSearchAbortControllerRef = useRef<AbortController | null>(null);
  // 검색 결과를 고르면 공공데이터와 맞춰 본다 - 바로 맞으면 바구니로, 아니면 후보 확인이나 나만의 장소 칸이 열린다
  const placeMatch = usePlaceMatch({ onMatched: (item) => addToBasket(item) });
```

찾기:

```tsx
  const [placeForm, setPlaceForm] = useState<TripPlaceRequest>({
```

바꾸기:

```tsx
  const [placeForm, setPlaceForm] = useState<PlaceEditorForm>({
```

검색 흐름. 새로 검색하면 맞춰 보던 것을 놓는다.

찾기:

```tsx
  const invalidatePlaceSearch = () => {
    placeSearchRequestRef.current += 1;
    cancelPendingPlaceSearch();
  };
```

바꾸기:

```tsx
  const invalidatePlaceSearch = () => {
    placeSearchRequestRef.current += 1;
    cancelPendingPlaceSearch();
    placeMatch.reset();   // 새로 검색하면 맞춰 보던 것(과 늦게 오는 답)을 놓는다
  };
```

검색이 실패하면 '결과 없음'과 다른 상태로 알린다. 서버는 카카오를 일부러 껐을 때만 빈 목록을 주고, 켜 두고 설정이 틀리면 503(`Place search is unavailable`)을 준다. 503 이면 검색을 못 쓴다고 말하고 직접 적기를 권한다 - 입구('찾는 곳이 없어요 · 직접 적기')는 검색 상태와 무관하게 늘 쓸 수 있다. 다른 실패는 지금 문구 그대로다.

찾기:

```tsx
    } catch {
      if (controller.signal.aborted) return;
      if (
        placeEditorSessionRef.current !== sessionId ||
        placeSearchRequestRef.current !== requestId
      )
        return;
      setPlaceSearchCandidates([]);
      setPlaceSearchError(
        "장소 검색 결과를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
      );
```

바꾸기:

```tsx
    } catch (error) {
      if (controller.signal.aborted) return;
      if (
        placeEditorSessionRef.current !== sessionId ||
        placeSearchRequestRef.current !== requestId
      )
        return;
      setPlaceSearchCandidates([]);
      // 서버가 카카오 검색을 쓸 수 없다고 하면(503) '결과 없음'이 아니라 검색을 못 쓴다고 알리고 직접 적기를 권한다
      setPlaceSearchError(
        isApiError(error) && error.status === 503
          ? /* 시안 v59 */ "장소 검색을 지금 쓸 수 없어요. 직접 적기로 담을 수 있어요."
          : "장소 검색 결과를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
      );
```

찾기:

```tsx
  /* initial: 홈 장소 카드의 '일정에 담기'로 넘어온 장소(시안 v57) - 바구니에 담은 채 연다 */
  const openAddPlace = (initial?: TripPlaceRequest) => {
```

바꾸기:

```tsx
  /* initial: 홈 장소 카드의 '일정에 담기'로 넘어온 카카오 장소(시안 v57) - 검색 결과를 고른 것과 같이 공공데이터와 맞춰 본 뒤 바구니에 담긴다 */
  const openAddPlace = (initial?: PlacePickInput) => {
```

찾기:

```tsx
    placeBasketIdRef.current += 1;
    setPlaceBasket(initial ? [{ ...initial, basketId: `place-basket-${placeBasketIdRef.current}` }] : []);
    setBatchPlaceRecovery({ kind: "none" });
    setPlaceEditor({ mode: "add", dayNumber: visibleDay });
    setPlaceForm({ time: "", label: "", meta: "" });
    clearPlacePreview();
    if (initial) {
      updatePlacePreview({
        source: "selected",
        place: previewFromPayload(initial, "selected", visibleDay, initial.externalPlaceId ?? initial.label),
      });
    }
    setPlaceSaveEligibility("empty");
```

바꾸기:

```tsx
    setPlaceBasket([]);
    setBatchPlaceRecovery({ kind: "none" });
    setPlaceEditor({ mode: "add", dayNumber: visibleDay });
    setPlaceForm({ time: "", label: "", meta: "" });
    clearPlacePreview();
    placeMatch.reset();
    if (initial) void placeMatch.pick(initial);
    setPlaceSaveEligibility("empty");
```

받는 쪽은 JSON에서 꺼낸 카카오 장소를 `pick`에 넘길 값(이름 · 좌표 · 분류 · ID)으로만 줄여 넘긴다.

찾기:

```tsx
    const item = readPlaceParam(handoffPlace);
    if (item) openAddPlace(tripPlaceFromSearchItem(item));
```

바꾸기:

```tsx
    const item = readPlaceParam(handoffPlace);
    if (item)
      openAddPlace({
        id: item.id,
        title: item.name,
        latitude: item.latitude,
        longitude: item.longitude,
        categoryCode: item.categoryCode,
      });
```

찾기:

```tsx
        const preview = previewFromSearchCandidate(
          candidates[0],
          placeEditor.dayNumber,
          "searchPreview",
          placeForm.time ?? "",
        );
```

바꾸기:

```tsx
        const preview = previewFromSearchResult(
          candidates[0],
          placeEditor.dayNumber,
        );
```

검색 결과를 고르는 함수를 바꾼다. 수정 모드로 가던 뒷분기는 수정 창에 검색 칸이 없어 닿지 않는 죽은 코드라 함께 지운다. 바구니에 넣는 일은 `addToBasket`이 맡는다.

찾기:

```tsx
  const selectPlaceSearchCandidate = (candidate: PlaceSearchCandidate) => {
    if (placeEditor?.mode === "add") {
      const basketPayload = placeSearchCandidatePayload(candidate, "");
      placeBasketIdRef.current += 1;
      setPlaceBasket((current) => [
        ...current,
        {
          ...basketPayload,
          basketId: `place-basket-${placeBasketIdRef.current}`,
        },
      ]);
      updatePlacePreview({
        source: "selected",
        place: previewFromSearchCandidate(
          candidate,
          placeEditor.dayNumber,
          "selected",
          "",
        ),
      });
      cancelPendingPlaceSearch();
      placeSearchRequestRef.current += 1;
      setPlaceSearchQuery("");
      setPlaceSearchCandidates([]);
      setPlaceSearchError("");
      setIsLoadingPlaceSearch(false);
      setPlaceSaveEligibility("empty");
      setPlaceForm({ time: "", label: "", meta: "" });
      setBatchPlaceRecovery({ kind: "none" });
      setPlaceError("");
      return;
    }
    const preview = previewFromSearchCandidate(
      candidate,
      placeEditor?.dayNumber ?? visibleDay,
      "selected",
      placeForm.time ?? "",
    );
    updatePlacePreview({ source: "selected", place: preview });
    setPlaceSaveEligibility("saveSelected");
    updatePlaceForm(placeSearchCandidatePayload(candidate, placeForm.time));
    setPlaceSearchQuery(candidate.title);
    setPlaceError("");
  };
```

바꾸기:

```tsx
  const selectPlaceSearchCandidate = (candidate: PlaceSearchCandidate) => {
    if (placeEditor?.mode !== "add") return;
    cancelPendingPlaceSearch();
    placeSearchRequestRef.current += 1;
    setPlaceSearchQuery("");
    setPlaceSearchCandidates([]);
    setPlaceSearchError("");
    setIsLoadingPlaceSearch(false);
    clearPlacePreview();
    setPlaceForm({ time: "", label: "", meta: "" });
    setBatchPlaceRecovery({ kind: "none" });
    setPlaceError("");
    // 카카오 값은 맞춰 보기 요청에만 쓰고 버린다 - 바구니에는 공공데이터 장소나 사용자가 쓴 값만 들어간다
    void placeMatch.pick(candidate);
  };

  const addToBasket = (item: PlaceBasketItem) => {
    setPlaceBasket((current) => [...current, item]);
    updatePlacePreview({
      source: "selected",
      place: previewFromBasketItem(item, visibleDay),
    });
    setPlaceSaveEligibility("empty");
    setBatchPlaceRecovery({ kind: "none" });
    setPlaceError("");
  };

  /* 나만의 장소 칸에서 담기 - 이름 · 위치는 사용자가 쓴 것, 카카오 값은 장소 ID 뿐이다 */
  const addCustomPlace = (input: CustomPlaceInput) => {
    const current = placeMatch.state;
    if (current.status !== "custom") return;
    addToBasket(customBasketItem(input, current.kakaoPlaceId));
    placeMatch.reset();
  };
```

저장.

찾기:

```tsx
    const places = placeBasket.map(({ basketId: _basketId, ...place }) => place);
```

바꾸기:

```tsx
    const places = placeBasket.map(basketItemPayload);
```

찾기:

```tsx
      setPlaceBasket([]);
      setPlaceEditor(null);
      clearPlacePreview();
      setPlaceDraftNotice("");
      setNotice("장소를 일정에 추가했어요.");
```

바꾸기:

```tsx
      setPlaceBasket([]);
      placeMatch.reset();
      setPlaceEditor(null);
      clearPlacePreview();
      setPlaceDraftNotice("");
      setNotice("장소를 일정에 추가했어요.");
```

저장이 요청 모양 오류(422 의 `extra_forbidden` · `missing`)로 거절되면 일반 문구 대신 새로 고침을 안내한다. 배포 때 열려 있던 옛 화면은 옛 모양(카카오 필드)으로 보내 서버가 422 로 거절하고, 새로 고쳐야 풀린다(사용자 결정). 이름 길이 · 시간 형식 같은 값 오류의 422 는 새로 고쳐도 그대로라 일반 문구로 둔다(코덱스 재검토). 먼저 판별 함수와 문구를 `isTripConflict` 옆에 둔다. 이 상수와 함수는 내보내지 않는다 - 과제 10 이 같은 파일 안에서 수정 저장에도 쓴다.

찾기:

```tsx
function isTripConflict(error: unknown): boolean {
  return isApiError(error) && error.status === 409;
}
```

바꾸기:

```tsx
function isTripConflict(error: unknown): boolean {
  return isApiError(error) && error.status === 409;
}

/* 서버가 요청 모양을 거절한 422 만 '화면이 오래됨'으로 본다. 배포 때 열려 있던 화면이 옛 모양으로 보내면 응답 detail 에
   모르는 필드(extra_forbidden)나 빠진 필드(missing)가 있고, 새로 고침하면 풀린다 - 일반 문구 대신 새로 고침을 안내한다(사용자 결정).
   이름 길이 · 시간 형식 · 위치 범위 같은 값 오류의 422 는 새로 고쳐도 그대로라 일반 문구로 둔다(코덱스 재검토) */
const STALE_SCREEN_MESSAGE = "화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.";
const STALE_REQUEST_ERRORS = new Set(["extra_forbidden", "missing"]);

function isStaleScreenError(error: unknown): boolean {
  if (!isApiError(error) || error.status !== 422 || !Array.isArray(error.detail)) return false;
  return error.detail.some((item: { type?: unknown } | null) => STALE_REQUEST_ERRORS.has(String(item?.type)));
}
```

묶음 저장의 `catch` 에서 충돌(409) · 없는 Day 다음, 일반 문구 앞에 둔다.

찾기:

```tsx
      } else {
        setPlaceError(
          "장소 정보를 저장하지 못했어요. 입력값을 확인하고 다시 시도해 주세요.",
        );
      }
    } finally {
      setIsSavingPlace(false);
    }
  };

  const retryPlaceBasket = (dayNumber: number) => {
```

바꾸기:

```tsx
      } else if (isStaleScreenError(error)) {
        setPlaceError(STALE_SCREEN_MESSAGE);
      } else {
        setPlaceError(
          "장소 정보를 저장하지 못했어요. 입력값을 확인하고 다시 시도해 주세요.",
        );
      }
    } finally {
      setIsSavingPlace(false);
    }
  };

  const retryPlaceBasket = (dayNumber: number) => {
```

수정 경로는 타입 이름만 바꾼다(내용은 수정 · 초안 과제의 몫).

찾기:

```tsx
      const payload: TripPlaceRequest & { expectedRevision: number } = {
```

바꾸기:

```tsx
      const payload: PlaceEditorForm & { expectedRevision: number } = {
```

찾기:

```tsx
  const updatePlaceForm = (nextForm: TripPlaceRequest) => {
```

바꾸기:

```tsx
  const updatePlaceForm = (nextForm: PlaceEditorForm) => {
```

창을 닫을 때 맞춰 보던 것을 놓는다.

찾기:

```tsx
    cancelPendingPlaceSearch();
    placeEditorSessionRef.current += 1;
    setPlaceDraftNotice("");
    setMoveError("");
```

바꾸기:

```tsx
    cancelPendingPlaceSearch();
    placeMatch.reset();
    placeEditorSessionRef.current += 1;
    setPlaceDraftNotice("");
    setMoveError("");
```

시트에 갈래 고르기 칸을 꽂는다.

찾기:

```tsx
          onSubmit={submitPlaceEditor}
          batchRecovery={batchPlaceRecovery}
          placeBasket={placeBasket}
          preview={placePreview}
```

바꾸기:

```tsx
          onSubmit={submitPlaceEditor}
          batchRecovery={batchPlaceRecovery}
          placeBasket={placeBasket}
          hidePreview={placeMatch.state.status !== "idle"}
          matchPanel={
            placeEditor.mode === "add" ? (
              <PlaceMatchPanel
                fallbackCenter={firstPublicPlacePoint(trip.days)}
                onCancel={placeMatch.reset}
                onChooseCandidate={placeMatch.chooseCandidate}
                onChooseCustom={placeMatch.chooseCustom}
                onStartDirect={placeMatch.startDirect}
                onSubmitCustom={addCustomPlace}
                state={placeMatch.state}
                tripId={trip.id}
              />
            ) : undefined
          }
          preview={placePreview}
```

`PlaceEditorSheet` 본체. props를 더하고 타입 이름을 바꾼다.

찾기:

```tsx
  form,
  isLoadingSearch,
  isMovingDay = false,
  isSaving,
  mode,
  onChange,
```

바꾸기:

```tsx
  form,
  hidePreview = false,
  isLoadingSearch,
  isMovingDay = false,
  isSaving,
  matchPanel,
  mode,
  onChange,
```

찾기:

```tsx
  form: TripPlaceRequest;
  isLoadingSearch: boolean;
  isMovingDay?: boolean;
  isSaving: boolean;
  mode: "add" | "edit";
  onChange: (form: TripPlaceRequest) => void;
```

바꾸기:

```tsx
  form: PlaceEditorForm;
  /** 맞춰 보는 동안 지도 미리보기를 접는다(카카오 이름이 나만의 장소 칸 옆에 남지 않게) */
  hidePreview?: boolean;
  isLoadingSearch: boolean;
  isMovingDay?: boolean;
  isSaving: boolean;
  /** 추가 모드의 갈래 고르기 칸(후보 확인 · 나만의 장소 · 직접 적기 입구) - PlaceMatchPanel */
  matchPanel?: ReactNode;
  mode: "add" | "edit";
  onChange: (form: PlaceEditorForm) => void;
```

시트 안: 먼저 맨 아래의 '검색 결과 없음' 글을 지우고 미리보기 카드를 `hidePreview`로 접는다.

찾기:

```tsx
              {!hasPlaceBasket && searchQuery.trim() && !isLoadingSearch && searchCandidates.length === 0 && !searchError && (
                <p className="place-search-status">
                  검색 결과가 없어요. 다른 검색어로 다시 찾아주세요.
                </p>
              )}
            </div>
          )}
          {mode === "add" && (
            <PlacePreviewMapCard
              preview={preview}
              saveEligibility={saveEligibility}
            />
          )}
```

바꾸기:

```tsx
            </div>
          )}
          {mode === "add" && !hidePreview && (
            <PlacePreviewMapCard
              preview={preview}
              saveEligibility={saveEligibility}
            />
          )}
```

'검색 결과 없음' 글을 검색 결과 바로 아래로 올리고 그 아래에 갈래 고르기 칸을 둔다. 직접 적기 입구가 이 글 바로 밑에 온다.

찾기:

```tsx
              {hasPlaceBasket && (
                <section
                  className="place-basket"
```

바꾸기:

```tsx
              {!hasPlaceBasket && searchQuery.trim() && !isLoadingSearch && searchCandidates.length === 0 && !searchError && (
                <p className="place-search-status">
                  검색 결과가 없어요. 다른 검색어로 다시 찾아주세요.
                </p>
              )}
              {/* 시안 v59: 고른 검색 결과를 공공데이터와 맞춰 본 갈래(후보 확인 · 나만의 장소)와 '직접 적기' 입구 */}
              {matchPanel}
              {hasPlaceBasket && (
                <section
                  className="place-basket"
```

바구니 줄은 공공데이터 값 · 사용자가 쓴 값으로 그린다.

찾기:

```tsx
                        <span>
                          <strong>{item.label}</strong>
                          <em>{item.category ?? item.categoryCode ?? "장소"}</em>
                          <small>{item.address ?? item.meta ?? "장소 정보 확인"}</small>
                        </span>
                        <button
                          aria-label={`${item.label} 제거`}
```

바꾸기:

```tsx
                        <span>
                          <strong>{basketItemTitle(item)}</strong>
                          <em>{basketItemBadge(item)}</em>
                          <small>{basketItemDetail(item)}</small>
                        </span>
                        <button
                          aria-label={`${basketItemTitle(item)} 제거`}
```

시트의 오류 줄 아래에 '새로 고침' 단추를 더한다. 단추는 `error` 가 위의 `STALE_SCREEN_MESSAGE` 일 때만 나온다 - 새 prop 이 없고, `setPlaceError("")` 로 오류를 지우는 기존 길이 그대로 단추도 지운다. 이 단추는 수정 모드의 저장 오류(과제 10)에도 같이 쓰인다.

찾기:

```tsx
          {error && <p className="form-error">{error}</p>}
        </div>
        {!readOnly && (
```

바꾸기:

```tsx
          {error && <p className="form-error">{error}</p>}
          {/* 시안 v59: 저장이 422 로 거절됐을 때의 새로 고침 안내 */}
          {error === STALE_SCREEN_MESSAGE && (
            <button className="btn sm line" onClick={() => window.location.reload()} type="button">
              새로 고침
            </button>
          )}
        </div>
        {!readOnly && (
```

**3-6. 옛 타입 지우기** - 이제 화면이 `TripPlaceRequest`를 쓰지 않는다. API 경계에서 지운다.

**고치기 `frontend/src/api/dataApi.ts`**

찾기:

```ts
/** @deprecated 3단계 이전의 카카오 값 묶음. 저장 요청에는 쓰지 않는다(요청은 TripPlaceAddItem). 일정 화면의 수정 폼 · 추천 미리보기가 아직 타입으로 쓰고 있어 과제 9가 화면 안으로 옮기고 이 타입을 지운다 */
export type TripPlaceRequest = {
  time?: string;
  label: string;
  meta?: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  category?: string | null;
  categoryCode?: string | null;
  placeUrl?: string | null;
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
};

/** 장소 추가(단일)
```

바꾸기:

```ts
/** 장소 추가(단일)
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd frontend && npx vitest run src/components/itinerary src/utils/placeHandoff.test.ts src/lib/kakaoMap.test.ts src/api/backendApi.test.ts src/components/map/KakaoMapView.test.tsx`
기대: PASS - 12개 파일, 시험 93개(과제 7 · 8의 시험과 `PlacePhoto` · 후보 확인 · 나만의 장소 · 위치 찍기(키보드 · 확대 · 알림 포함) · 패널 시험 포함).

실행(백엔드 필요): `cd frontend && node scripts/run-backend-command.cjs npx vitest run src/app/__tests__/trip-place-basket.test.tsx src/app/__tests__/trip-detail.test.tsx src/app/__tests__/place-edit.test.tsx`
기대: PASS - 3개 파일, 시험 153개: `trip-place-basket` 15개, `trip-detail` 129개, `place-edit` 9개(수정 · 삭제 · 초안 시험은 이 과제가 건드리지 않았다).

실행: `cd frontend && npx tsc --noEmit -p .`
기대: 오류 0건. (과제 7에서 남았던 `ItineraryDetailPage.tsx`의 세 오류가 사라진다.)

실행: `cd frontend && npm run test:mojibake && cd .. && git diff --check`
기대: `No mojibake-like frontend text found.`, `git diff --check`는 출력 없음(CRLF 경고는 무시).

실행: `cd frontend && npm test`
기대: 기존 시험 파일 전부 통과 - 이 과제로 새로 깨진 시험이 없다(알려진 `mypage` 실패가 있으면 따로 적는다). 이 부분을 쓰는 동안 로그인 · 세션 · 프로필 옵션 응답만 가짜로 대신한 채 과제 9 까지 겹친 전체를 돌렸다 - 56개 파일 605개 중 5개가 실패했고(`home` 2 · `invite-oauth` 2 · `policies` 1), 처음 상태(48개 파일 523개)도 같은 5개가 실패한다(가짜 로그인 환경의 한계). 새로 깨진 시험은 없었다.

e2e는 이 계획에서 돌리지 않는다. `backend-mode.spec.ts`의 추가 시트 확인(폭별 · 빈 검색 뒤)은 컨테이너를 이 워크트리로 다시 빌드한 뒤 3단계 전체 검증 과제에서 `npm run test:e2e:containers`로 돈다. 시드 두 곳은 과제 12가 고치기 전에는 실패한다.

- [ ] **5단계: 실패하는 시험 쓰기 - 시안 v60 ~ v62(결정 22 ~ 25)**

과제 8b 가 끝난 뒤에 한다. `frontend/src/app/__tests__/trip-place-basket.test.tsx`(1단계에서 통째로 바꾼 파일)의 `describe("Travel Hunter app trip place add flow", …)` 맨 끝에 더한다. 위쪽 도우미(`kakaoCandidate` · `publicPlace` · `addTrip` · `openAddSheet` · `mockSearch`)를 쓴다.

```tsx
  it("marks each row with its prematched path and adds a ready row without asking again (시안 v62)", async () => {
    const trip = addTrip("97");
    mockSearch(
      kakaoCandidate("8101", "죽녹원", { categoryCode: "AT4", publicMatch: { result: "match", places: [publicPlace("죽녹원", "T-31", { category: "sight" })] } }),
      kakaoCandidate("8102", "죽녹원 대숲길", {
        publicMatch: { result: "candidates", places: [publicPlace("죽녹원", "T-31"), publicPlace("죽녹원 후문", "S-2", { source: "sangga" })] },
      }),
      kakaoCandidate("8103", "죽녹원 앞 노점", { publicMatch: { result: "none", places: [] } }),
    );
    const matchSpy = vi.spyOn(appDataApi, "matchPlace");
    const { user, dialog } = await openAddSheet(trip);

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "죽녹원" } });
    const ready = await within(dialog).findByRole("button", { name: "죽녹원 선택, 바로 담기" });
    expect(within(dialog).getByRole("button", { name: "죽녹원 대숲길 선택, 비슷한 곳 2" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "죽녹원 앞 노점 선택, 직접 적기" })).toBeInTheDocument();
    // 지도 미리보기 배지는 첫 줄의 갈래와 같다(결정 25)
    expect(within(dialog).getByRole("region", { name: "장소 지도 미리보기" })).toHaveTextContent("바로 담기");

    await user.click(ready);

    const basket = await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    expect(basket).toHaveTextContent("공공데이터 주소 죽녹원");
    expect(matchSpy).not.toHaveBeenCalled();
    expect(within(dialog).queryByText("우리 장소 목록과 맞춰 보는 중이에요.")).not.toBeInTheDocument();
    expect(within(dialog).getByLabelText("장소 검색")).toHaveFocus();
    // 담은 뒤 미리보기는 '저장 가능'(결정 25)
    expect(within(dialog).getByRole("region", { name: "장소 지도 미리보기" })).toHaveTextContent("저장 가능");
  });

  it("opens the candidates or the own-place form right away for the other rows (시안 v62)", async () => {
    const trip = addTrip("98");
    mockSearch(
      kakaoCandidate("8102", "죽녹원 대숲길", {
        publicMatch: { result: "candidates", places: [publicPlace("죽녹원", "T-31"), publicPlace("죽녹원 후문", "S-2", { source: "sangga" })] },
      }),
      kakaoCandidate("8103", "죽녹원 앞 노점", { publicMatch: { result: "none", places: [] } }),
    );
    const matchSpy = vi.spyOn(appDataApi, "matchPlace");
    const { user, dialog } = await openAddSheet(trip);

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "죽녹원" } });
    await user.click(await within(dialog).findByRole("button", { name: "죽녹원 대숲길 선택, 비슷한 곳 2" }));
    expect(within(dialog).getByRole("region", { name: "이 장소가 맞나요?" })).toBeInTheDocument();

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "죽녹원 앞" } });
    await user.click(await within(dialog).findByRole("button", { name: "죽녹원 앞 노점 선택, 직접 적기" }));
    const form = within(dialog).getByRole("form", { name: "나만의 장소" });
    expect(within(form).getByLabelText("장소 이름")).toHaveValue("");
    expect(matchSpy).not.toHaveBeenCalled();
  });

  it("keeps a row without a prematch on the old path: no mark, matched after the pick (코덱스 검토)", async () => {
    const trip = addTrip("102");
    mockSearch(
      kakaoCandidate("8501", "죽녹원", { publicMatch: { result: "match", places: [publicPlace("죽녹원", "T-31")] } }),
      kakaoCandidate("8502", "죽녹원길 카페", { publicMatch: null }),
    );
    const matchSpy = vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "none", places: [] });
    const { user, dialog } = await openAddSheet(trip);

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "죽녹원" } });
    expect(await within(dialog).findByRole("button", { name: "죽녹원 선택, 바로 담기" })).toBeInTheDocument();
    const plain = within(dialog).getByRole("button", { name: "죽녹원길 카페 선택" });
    expect(plain.querySelector(".place-search-result-state")).toBeNull();

    await user.click(plain);

    await waitFor(() => expect(matchSpy).toHaveBeenCalledTimes(1));
    expect(await within(dialog).findByRole("form", { name: "나만의 장소" })).toBeInTheDocument();
  });

  it("keeps the server's results for a two-word query (시안 v61)", async () => {
    const trip = addTrip("99");
    vi.spyOn(appDataApi, "searchTripPlaces").mockResolvedValue([kakaoCandidate("8201", "죽녹원")]);
    const { dialog } = await openAddSheet(trip);

    fireEvent.change(within(dialog).getByLabelText("장소 검색"), { target: { value: "담양 죽녹원" } });

    expect(await within(dialog).findByRole("button", { name: "죽녹원 선택" })).toBeInTheDocument();
  });

  it("keeps the earlier results dimmed and unclickable inside a fixed area while the next search loads (시안 v61 · 코덱스 검토)", async () => {
    const trip = addTrip("100");
    let release!: (rows: PlaceSearchCandidate[]) => void;
    vi.spyOn(appDataApi, "searchTripPlaces")
      .mockResolvedValueOnce([kakaoCandidate("8301", "오동도", { publicMatch: { result: "match", places: [publicPlace("오동도", "T-41")] } })])
      .mockImplementationOnce(() => new Promise<PlaceSearchCandidate[]>((resolve) => { release = resolve; }));
    const { dialog } = await openAddSheet(trip);
    const input = within(dialog).getByLabelText("장소 검색");

    fireEvent.change(input, { target: { value: "오동도" } });
    await within(dialog).findByRole("button", { name: "오동도 선택, 바로 담기" });
    fireEvent.change(input, { target: { value: "오동도 등대" } });

    await within(dialog).findByText("장소 검색 결과를 불러오는 중입니다.");
    const list = within(dialog).getByRole("list", { name: "장소 검색 결과" });
    expect(list).toHaveAttribute("aria-busy", "true");
    expect(list).toHaveClass("is-stale");
    expect(list.closest(".place-search-area")).not.toBeNull();
    const stale = within(list).getByRole("button", { name: "오동도 선택, 바로 담기" });
    expect(stale).toBeDisabled();
    fireEvent.click(stale);
    expect(within(dialog).queryByRole("region", { name: "추가할 장소 목록" })).not.toBeInTheDocument();

    await act(async () => release([kakaoCandidate("8302", "오동도 등대")]));

    expect(await within(dialog).findByRole("button", { name: "오동도 등대 선택" })).toBeEnabled();
    expect(within(dialog).getByRole("list", { name: "장소 검색 결과" })).toHaveAttribute("aria-busy", "false");
  });

  it("lists the results as list items and announces how many came, keeping focus in the search box (코덱스 검토)", async () => {
    const trip = addTrip("103");
    mockSearch(kakaoCandidate("8601", "오동도"), kakaoCandidate("8602", "오동도 등대"), kakaoCandidate("8603", "오동도 유람선"));
    const { dialog } = await openAddSheet(trip);
    const input = within(dialog).getByLabelText("장소 검색");
    input.focus();

    fireEvent.change(input, { target: { value: "오동도" } });

    await within(dialog).findByText("검색 결과 3곳");
    const list = within(dialog).getByRole("list", { name: "장소 검색 결과" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    expect(input).toHaveFocus();
  });

  it("shows 'no results' inside the fixed area even with places in the basket (코덱스 검토)", async () => {
    const trip = addTrip("104");
    vi.spyOn(appDataApi, "searchTripPlaces")
      .mockResolvedValueOnce([kakaoCandidate("8701", "죽녹원", { publicMatch: { result: "match", places: [publicPlace("죽녹원", "T-31")] } })])
      .mockResolvedValueOnce([]);
    const { user, dialog } = await openAddSheet(trip);
    const input = within(dialog).getByLabelText("장소 검색");

    fireEvent.change(input, { target: { value: "죽녹원" } });
    await user.click(await within(dialog).findByRole("button", { name: "죽녹원 선택, 바로 담기" }));
    await within(dialog).findByRole("region", { name: "추가할 장소 목록" });
    fireEvent.change(input, { target: { value: "없는 장소" } });

    const empty = await within(dialog).findByText("검색 결과가 없어요. 다른 검색어로 다시 찾아주세요.");
    expect(empty.closest(".place-search-area")).not.toBeNull();
  });
```

- [ ] **6단계: 실패하는지 확인**

실행(백엔드 필요): `cd frontend && node scripts/run-backend-command.cjs npx vitest run src/app/__tests__/trip-place-basket.test.tsx`
기대: FAIL 6개 - 줄 이름에 표시가 없다(`죽녹원 선택, 바로 담기` 를 못 찾음) 둘, 두 낱말 검색의 결과가 걸러진다, 불러오는 동안 목록에 `aria-busy` · `is-stale` · `place-search-area` · `disabled` 가 없다, `listitem` 과 '검색 결과 3곳'이 없다, 바구니가 있을 때 '결과 없음'이 칸 밖이다(지금은 아예 나오지 않는다). '미리 맞춤 없는 줄' 시험은 지금도 통과한다(지켜야 할 경계). 1단계의 기존 시험 15개는 그대로 통과한다.

- [ ] **7단계: 구현**

**7-1. `ItineraryDetailPage.tsx` - 거르기를 지우고(결정 22), 미리보기에 갈래를 싣는다(결정 25).**

들여오기. 찾기:

```tsx
import { usePlaceMatch, type PlacePickInput } from "../../components/itinerary/placeAdd/usePlaceMatch";
```

바꾸기:

```tsx
import { usePlaceMatch, type PlacePickInput } from "../../components/itinerary/placeAdd/usePlaceMatch";
import { publicMatchBadge, type PublicMatchBadge } from "../../components/itinerary/placeAdd/publicPlaceText";
```

거르기 함수를 통째로 지운다(다른 곳에서 쓰지 않는다). 지울 글:

```tsx
function placeSearchText(item: PlaceSearchCandidate): string {
  return [item.title, item.meta, item.categoryName, item.address]
    .filter((part): part is string => Boolean(part))
    .join(" ")
    .toLocaleLowerCase("ko-KR");
}

```

찾기:

```tsx
  const normalizedPlaceSearchQuery = placeSearchQuery
    .trim()
    .toLocaleLowerCase("ko-KR");
  const placeSearchResults = placeSearchCandidates
    .filter((candidate) => {
      if (!normalizedPlaceSearchQuery) return true;
      return placeSearchText(candidate).includes(normalizedPlaceSearchQuery);
    })
    .slice(0, 6);
```

바꾸기:

```tsx
  // 서버가 준 순서대로 6곳 - 친 말로 다시 거르지 않는다(결정 22: 거르면 칠 때마다 목록이 비었다 늘어 창이 흔들렸고, 두 낱말 검색의 결과가 숨었다)
  const placeSearchResults = placeSearchCandidates.slice(0, 6);
```

미리보기 한 곳에 갈래를 싣는다. 찾기(과제 9 3-5 가 만든 `type PlacePreviewCandidate = {` 안의 끝 - 파일에 같은 글이 여럿이면 이 타입 안의 것만):

```tsx
  latitude?: number | null;
  longitude?: number | null;
};
```

바꾸기:

```tsx
  latitude?: number | null;
  longitude?: number | null;
  /** 검색 결과를 보일 때만 - 그 줄의 미리 맞춘 갈래(결정 25) */
  matchBadge?: PublicMatchBadge | null;
};
```

찾기(과제 9 3-5 의 `previewFromSearchResult` 끝):

```tsx
    label: item.title,
    meta: item.meta,
    address: item.address ?? null,
    latitude: item.latitude ?? null,
    longitude: item.longitude ?? null,
  };
}
```

바꾸기:

```tsx
    label: item.title,
    meta: item.meta,
    address: item.address ?? null,
    latitude: item.latitude ?? null,
    longitude: item.longitude ?? null,
    matchBadge: publicMatchBadge(item.publicMatch),
  };
}
```

담은 뒤에는 '저장 가능'(결정 25). 찾기(과제 9 3-5 의 `addToBasket`):

```tsx
    updatePlacePreview({
      source: "selected",
      place: previewFromBasketItem(item, visibleDay),
    });
    setPlaceSaveEligibility("empty");
```

바꾸기:

```tsx
    updatePlacePreview({
      source: "selected",
      place: previewFromBasketItem(item, visibleDay),
    });
    setPlaceSaveEligibility("saveSelected");
```

**7-2. `PlaceEditorSheet` - 고정 높이 결과 칸 · 누를 수 없는 흐린 앞 결과 · 목록 항목 · 줄 표시(결정 22 · 24).**

찾기:

```tsx
  const [inputSearchQuery, setInputSearchQuery] = useState(searchQuery);
  const searchDebounceTimerRef = useRef<number | null>(null);
```

바꾸기:

```tsx
  const [inputSearchQuery, setInputSearchQuery] = useState(searchQuery);
  const searchDebounceTimerRef = useRef<number | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  // 친 말이 아직 검색되지 않았거나(350ms 대기) 불러오는 중 - 앞 결과를 흐리게, 누를 수 없게 남긴다(결정 22 · 24)
  const isSearchPending = isLoadingSearch || inputSearchQuery.trim() !== searchQuery.trim();
  const hasSearched = searchQuery.trim() !== "" && !isSearchPending && !searchError;
  const searchStatus = isSearchPending
    ? "장소 검색 결과를 불러오는 중입니다."
    : hasSearched && searchCandidates.length > 0
      ? `검색 결과 ${searchCandidates.length}곳`
      : hasSearched
        ? "검색 결과가 없어요. 다른 검색어로 다시 찾아주세요."
        : "";
```

찾기:

```tsx
                <input
                  name="place-search"
                  placeholder="장소명이나 주소 검색"
                  value={inputSearchQuery}
```

바꾸기:

```tsx
                <input
                  name="place-search"
                  placeholder="장소명이나 주소 검색"
                  ref={searchInputRef}
                  value={inputSearchQuery}
```

상태 줄 · 결과 · '검색 결과 없음'을 한 칸에 모은다. 찾기:

```tsx
              {isLoadingSearch && (
                <p className="place-search-status">
                  장소 검색 결과를 불러오는 중입니다.
                </p>
              )}
              {searchError && (
                <p className="place-search-status error">{searchError}</p>
              )}
              {searchCandidates.length > 0 && (
                <div
                  className="place-search-results"
                  role="list"
                  aria-label="장소 검색 결과"
                >
                  {searchCandidates.map((candidate, index) => (
                    <button
                      aria-label={`${candidate.title} 선택`}
                      className="place-search-result"
                      key={
                        candidate.id ??
                        candidate.externalPlaceId ??
                        `${candidate.title}:${index}`
                      }
                      type="button"
                      onClick={() => onSelectSearchCandidate(candidate)}
                    >
                      <span>
                        <strong>{candidate.title}</strong>
                        <em>{candidate.categoryName ?? "장소"}</em>
                      </span>
                      <small>{candidate.address ?? candidate.meta}</small>
                    </button>
                  ))}
                </div>
              )}
              {!hasPlaceBasket && searchQuery.trim() && !isLoadingSearch && searchCandidates.length === 0 && !searchError && (
                <p className="place-search-status">
                  검색 결과가 없어요. 다른 검색어로 다시 찾아주세요.
                </p>
              )}
```

바꾸기:

```tsx
              {/* 시안 v61: 검색어가 있는 동안 결과 칸 높이를 고정하고 상태 줄도 그 안에 - 칠 때 아래 칸이 오르내리지 않는다 */}
              {inputSearchQuery.trim() && (
                <div className="place-search-area">
                  {/* 상태 한 줄: 불러오는 중 · 결과 없음은 보이고, 'N곳'은 화면 읽기 프로그램에만(초점은 검색 칸에 그대로) */}
                  {searchStatus && (
                    <p
                      className={
                        hasSearched && searchCandidates.length > 0
                          ? "place-search-status sr-only"
                          : "place-search-status"
                      }
                      role="status"
                    >
                      {searchStatus}
                    </p>
                  )}
                  {searchError && (
                    <p className="place-search-status error">{searchError}</p>
                  )}
                  {searchCandidates.length > 0 && (
                    <div
                      aria-busy={isSearchPending}
                      aria-label="장소 검색 결과"
                      className={isSearchPending ? "place-search-results is-stale" : "place-search-results"}
                      role="list"
                    >
                      {searchCandidates.map((candidate, index) => {
                        const badge = publicMatchBadge(candidate.publicMatch);
                        return (
                          <div
                            key={
                              candidate.id ??
                              candidate.externalPlaceId ??
                              `${candidate.title}:${index}`
                            }
                            role="listitem"
                          >
                            <button
                              aria-label={badge ? `${candidate.title} 선택, ${badge.text}` : `${candidate.title} 선택`}
                              className="place-search-result"
                              disabled={isSearchPending}
                              type="button"
                              onClick={() => {
                                onSelectSearchCandidate(candidate);
                                // 결정 24: 바로 담기는 바구니에 들어가고 다음 장소를 찾게 검색 칸으로 돌아온다
                                if (badge?.tone === "ready") searchInputRef.current?.focus();
                              }}
                            >
                              <span>
                                <strong>{candidate.title}</strong>
                                <em>{candidate.categoryName ?? "장소"}</em>
                              </span>
                              <span className="place-search-result-foot">
                                <small>{candidate.address ?? candidate.meta}</small>
                                {badge && (
                                  <i className={`place-search-result-state ${badge.tone}`}>{badge.text}</i>
                                )}
                              </span>
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
```

`PlaceEditorSheet` 의 props 에 `searchQuery` · `isLoadingSearch` · `searchError` · `searchCandidates` 가 이미 있다(1단계 이전부터). 이름이 다르면 같은 뜻의 props 를 쓴다. `sr-only` 는 과제 9 의 위치 찍기 상태 줄이 쓰는 클래스와 같다.

**7-3. `PlacePreviewMapCard` - 배지와 도움말(결정 25).** 찾기:

```tsx
  const place = preview.place;
  const marker = place ? placePreviewMarker(place) : null;
  const helperText =
    saveEligibility === "requiresExplicitCandidate"
      ? "검색 결과를 지도에 미리 표시했어요. 저장하려면 후보를 직접 선택해 주세요."
      : saveEligibility === "saveSelected"
        ? "저장할 장소로 선택되어 있어요."
        : "장소를 검색하면 지도에 표시돼요.";
```

바꾸기:

```tsx
  const place = preview.place;
  const marker = place ? placePreviewMarker(place) : null;
  // 결정 25: 검색 결과 첫 곳이면 그 줄의 갈래, 담은 뒤면 '저장 가능'
  const badge = place?.source === "searchPreview" ? place.matchBadge ?? null : null;
  const SEARCH_HELP: Record<PublicMatchBadge["tone"], string> = {
    ready: "우리 장소 목록에 있는 곳이에요. 누르면 바로 담겨요.",
    similar: "비슷한 곳을 찾았어요. 누르면 맞는 곳을 고를 수 있어요.",
    custom: "우리 장소 목록에 없어요. 누르면 이름을 직접 적어 담을 수 있어요.",
  };
  const helperText = badge
    ? SEARCH_HELP[badge.tone]
    : saveEligibility === "requiresExplicitCandidate"
      ? "검색 결과를 지도에 미리 표시했어요. 저장하려면 후보를 직접 선택해 주세요."
      : saveEligibility === "saveSelected"
        ? "저장할 장소로 선택되어 있어요."
        : "장소를 검색하면 지도에 표시돼요.";
  const stateClass = badge
    ? `place-preview-state${badge.tone === "ready" ? " ready" : badge.tone === "similar" ? " similar" : ""}`
    : saveEligibility === "saveSelected"
      ? "place-preview-state ready"
      : "place-preview-state";
  const stateText = badge ? badge.text : saveEligibility === "saveSelected" ? "저장 가능" : "확인 필요";
```

찾기:

```tsx
        <span
          className={
            saveEligibility === "saveSelected"
              ? "place-preview-state ready"
              : "place-preview-state"
          }
        >
          {saveEligibility === "saveSelected"
            ? "저장 가능"
            : "확인 필요"}
        </span>
```

바꾸기:

```tsx
        <span className={stateClass}>{stateText}</span>
```

**7-4. `frontend/src/styles/app.css`** - `.place-search-status {` 규칙 바로 앞에 더한다.

```css
/* 시안 v61: 검색어가 있는 동안 결과 칸 높이를 고정한다 - 상태 줄도 칸 안이라 칠 때 아래 칸이 오르내리지 않는다 */
.place-search-area {
  display: grid;
  align-content: start;
  gap: 8px;
  height: 220px;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.place-search-area .place-search-results {
  max-height: none;
  overflow: visible;
}

.place-search-area > .place-search-status:not(.sr-only) {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 2px 0 4px;
  background: var(--gray-50);
}

.place-search-results.is-stale {
  opacity: 0.55;
}

.place-search-result:disabled {
  cursor: default;
}

/* 시안 v62: 미리 맞춘 갈래 - 주소 줄 오른쪽 끝 */
.place-search-result .place-search-result-foot {
  align-items: flex-end;
}

.place-search-result-state {
  flex: 0 0 auto;
  padding: 4px 8px;
  border-radius: 999px;
  background: var(--gray-100);
  color: var(--gray-600);
  font-size: 11px;
  font-style: normal;
  font-weight: 900;
  white-space: nowrap;
}

.place-search-result-state.ready,
.place-preview-state.ready {
  background: #eaf8ef;
  color: #177245;
}

.place-search-result-state.similar,
.place-preview-state.similar {
  background: #fff4e0;
  color: #8a5300;
}

```

검색 칸 배경이 `--gray-50` 이 아니면(패널 배경 토큰을 확인한다) 고정 상태 줄의 `background` 를 그 토큰으로 맞춘다. `.place-preview-state.ready` 가 이미 있으면 위 묶음에서 그 선택자를 빼고 `similar` 만 더한다.

- [ ] **8단계: 통과하는지 확인**

실행(백엔드 필요): `cd frontend && node scripts/run-backend-command.cjs npx vitest run src/app/__tests__/trip-place-basket.test.tsx src/app/__tests__/trip-detail.test.tsx src/app/__tests__/place-edit.test.tsx`
기대: PASS - `trip-place-basket` 22개(15 + 5단계의 7), `trip-detail` 129개, `place-edit` 9개. 기존 시험이 '검색 결과가 없어요' 를 다른 자리에서 찾다 실패하면 같은 글이 결과 칸 안 상태 줄로 옮겨진 것이다 - 찾는 방법(글)은 그대로 맞는다.

실행: `cd frontend && npx vitest run src/components/itinerary` · `npx tsc --noEmit -p .` · `npm run test:mojibake` · `cd .. && git diff --check`
기대: 통과, 오류 0건, `No mojibake-like frontend text found.`, 출력 없음.

**시안 v59 대응표** - 시안이 확정할 때 이 목록만 훑으면 된다(`grep -rn "시안 v59" frontend/src`로도 찾는다). 데이터 흐름(props · 콜백 · 요청 모양)은 시안이 바꾸지 않는 한 그대로 둔다.
- 문구: '찾는 곳이 없어요 · 직접 적기' · '우리 장소 목록과 맞춰 보는 중이에요.' · '이 장소가 맞나요?'와 보조 문장 · '아니요, 직접 적을게요' · 나만의 장소 안내 네 줄(`CustomPlaceForm`의 `INTRO`) · '장소 이름'(라벨 · placeholder) · '지도에서 위치 찍기' · '지도에서 위치를 찍었어요' · '다시 찍기' · '지우기' · '이 위치로' · '취소' · '담기' · 후보 거리 문구(`distanceText`) · 바구니 줄의 '직접 적은 장소' · '지도에서 찍은 위치' · '위치 없이 이름만'.
- **위치 찍기(키보드로도 된다):** 지도 가운데 고정 십자선(`map-point-picker-pin`)은 모양 · 크기를 시안이 정한다. 조작은 지도를 끌거나 누르면(누른 자리가 가운데로 온다) 십자선 밑이 바뀌고, 방향키는 지도를 60px 씩 옮기고(`KEY_PAN_PX`), `+`(`=`) · `-` 는 한 단계씩 확대 · 축소하고, Enter 나 '이 위치로'가 십자선 밑을 고른다. 지도가 열리면 지도 칸에 초점이 가고 초점 테두리(`:focus-visible`)가 보이며, 고르거나 취소하면 초점이 '다시 찍기' · '지도에서 위치 찍기' 단추로 돌아온다. 도움말 문구: '지도를 끌거나 눌러서 십자선을 원하는 곳에 맞추세요. 키보드로는 방향키로 지도를 옮기고 + · - 로 확대 · 축소하고 Enter 로 고릅니다.' 지도 칸의 접근성 이름은 '위치 고르기 지도'. 지도 아래 상태 한 줄(`role="status"`): 대한민국 안이면 '지도 가운데 위도 …, 경도 …'(화면에는 숨김 - `sr-only`), 밖이면 '대한민국 밖이에요. 대한민국 안으로 옮겨 주세요.'(`form-error` 로 보임)이고 '이 위치로'가 꺼진다.
- **저장이 요청 모양 오류(422)로 거절됐을 때:** 오류 줄 '화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.' 와 그 아래 '새로 고침' 단추(`btn sm line`). 값 오류의 422 는 지금의 일반 문구다. 추가 창 · 수정 창 · 예전 행 확인 화면이 같은 자리 · 같은 문구를 쓴다.
- **검색을 쓸 수 없을 때(503):** 검색 결과 자리의 한 줄 '장소 검색을 지금 쓸 수 없어요. 직접 적기로 담을 수 있어요.' (`place-search-status error`) - 입구 '찾는 곳이 없어요 · 직접 적기'가 바로 아래에 보이는 배치를 시안이 확인한다.
- 클래스: `place-direct-entry`, `place-match-choices`, `place-match-head`, `place-match-list`, `place-match-card`(`has-photo`), `place-match-body`, `place-match-none`, `place-photo` · `place-photo-credit` · `place-photo--compact`(공용 `PlacePhoto` - 과제 11도 쓴다), `custom-place-form`, `custom-place-intro`, `custom-place-point`, `custom-place-actions`, `map-point-picker`, `map-point-picker-help`, `map-point-picker-map`, `map-point-picker-canvas`, `map-point-picker-pin`, `map-point-picker-actions`.
- 기존 지도 미리보기 카드(`PlacePreviewMapCard`)의 글: 새 흐름에서 `saveEligibility`는 거의 늘 `"empty"`라 바구니에 담은 뒤에도 '확인 필요'와 '장소를 검색하면 지도에 표시돼요.'가 보인다. 이 배지(`place-preview-state`)와 안내 글을 시안이 새 흐름에 맞게 정한다(숨기거나 '담았어요'로 바꾸는 한 줄 고침이다). → 결정 25 로 정했다(5 ~ 8단계).
- 시험이 붙잡는 접근성 이름(시안이 문구를 바꾸면 시험의 이름만 같이 바꾼다): region '이 장소가 맞나요?', form '나만의 장소', 입력 '장소 이름'(`name="custom-place-name"`), 버튼 `{이름} 선택` · '아니요, 직접 적을게요' · '찾는 곳이 없어요 · 직접 적기' · '지도에서 위치 찍기' · '이 위치로' · '다시 찍기' · '지우기' · '담기' · '취소' · '새로 고침', 상태 '맞춰 보는 중' · '지도 가운데 위도 …'(위치 찍기), application '위치 고르기 지도'(도움말 문구가 접근성 설명).
- 폭: 360 · 390 · 430 · 1024 · 1440에서 가로 넘침이 없어야 한다(e2e가 직접 적기 칸을 연 채로 확인한다).

---

---

## 프론트 수정 · 표시 · 넘김 공통 사항 (과제 10 ~ 12)

### 이 부분이 기대는 것 (과제 7~9 가 내놓는다 - 이름만 쓰고 다시 정의하지 않는다)

- **과제 7(`frontend/src/api`):** `PublicPlaceRef`, `CustomPlaceInput`, `PublicPlaceItem`, `PublicPlaceCategory`, `TripPlaceAddItem`, `TripPlaceMutationRequest`, `TripPlaceUpdateRequest { expectedRevision; time?; label?; memo?; publicPlace?; customPlace? }`, `TripAreaCenter`. `ItineraryPlace` 새 필드(`placeOrigin: "public" | "custom" | "needs_review" | null` · `publicSource: "tourapi" | "sangga" | null` · `publicSourceId` · `publicCategory` · `photoUrl` · `photoLicense` · `needsConfirmation`), `Recommendation` 새 필드(`publicSource` · `publicSourceId` · `publicCategory` · `photoUrl` · `photoLicense`), `RecommendationSourceType` 의 `"public_place"`. `appDataApi.listLegacyPlaceCandidates(tripId, placeId): Promise<PublicPlaceItem[]>`.
- **과제 8(`components/itinerary/placeAdd/`):** `publicPlaceText.ts` 의 `PUBLIC_CATEGORY_LABEL` · `photoCredit(license)` · `publicTimeSlotGroup(category): "attraction" | "food" | "cafe" | "stay"`, `usePlaceMatch.ts` 의 `usePlaceMatch({ onMatched })` · `type PlacePickInput`(= `Pick<PlaceSearchCandidate, "id" | "title" | "latitude" | "longitude" | "categoryCode">`) · `kakaoPlaceIdOf(candidate)`.
- **과제 9:** `PlaceMatchChoices({ candidates, onChoose, onNone })`, `CustomPlaceForm({ reason, tripId, fallbackCenter, onSubmit, onCancel })`(+ `type CustomPlaceReason`, `onSubmit({ name, latitude, longitude })` 위치가 없으면 둘 다 `null`), `MapPointPicker.tsx` 의 `firstPublicPlacePoint(days)` · `type MapPoint`, `PlaceEditorSheet` 의 새 props `matchPanel` · `hidePreview`. 페이지 안에서는 `const placeMatch = usePlaceMatch(...)`, `openAddPlace(initial?: PlacePickInput)`(안에서 `placeMatch.reset()` 뒤 `placeMatch.pick(initial)`), 화면 안 `type PlaceEditorForm`(옛 `TripPlaceRequest` 값 묶음)과 `type TripPlaceEditDraft`, 그리고 `?addPlace=` 의 JSON(`readPlaceParam`)을 `PlacePickInput` 으로 줄여 `openAddPlace` 에 넘기는 **임시 연결**을 남긴다.
- **과제 9 가 이 부분에 남기는 것(과제 9 문서 '건드리지 않는 곳'):** 수정 · 초안 · 예전 행(`openEditPlace` · `submitPlaceEditor` 수정 분기 · `updatePlaceForm` · `discardPlaceDraft` · `PlaceSheetDetail` · `utils/draftStorage.ts` · `LegacyPlaceConfirm`), 추천 미리보기(`recommendationPlacePayload` · `previewPlacesFromRecommendations` · `timelinePlaceFromPreviewPlace` · `tripPlaceMutationFromDisplayedPlace` · `commitRecommendationPreview`), 표시(마커 · 시간대 분류), 홈 넘김 형식(`readAddPlaceParam` · `writeAddPlaceParam`). 쓰이지 않던 `previewPlaceFromRecommendation` · `tripPlaceMutationFromPreviewPlace` · `previewFromRecommendation` 은 과제 9 가 지운다.
- **과제 9 가 페이지 안에 두는 것(내보내지 않는다):** `STALE_SCREEN_MESSAGE`(= '화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.') · `isStaleScreenError(error)`(HTTP 422 이고 응답 `detail` 에 `extra_forbidden` · `missing` 이 있을 때 - 값 오류의 422 는 아니다). 추가 창 묶음 저장이 이미 쓰고, `PlaceEditorSheet` 는 `error` 가 그 문구일 때 '새로 고침'(`window.location.reload()`) 단추를 더 그린다. 과제 10 은 수정 저장 · 예전 행 바꾸기의 `catch` 에 같은 분기를 더하기만 한다.
- **과제 9 직후의 상태:** `tsc` 0건. 런타임으로는 수정 저장(PATCH)과 추천 담기가 옛 모양(`meta` · 카카오 필드)을 그대로 보내 3단계 백엔드(`extra=forbid`)가 422 로 막는다 - 그 두 길은 과제 10 · 11 이 닫는다. 그 전에는 손으로 시험하지 않는다(시험은 `appDataApi` 스파이로 가려져 통과한다).

### 과제 10 ~ 12 에서 정한 것

1. **예전 카카오 행 = `needsConfirmation === true` 인 행만.** 기존 시험 · 시안의 행(`placeOrigin` 도 `needsConfirmation` 도 없는 행)은 지금 그대로다(수정 창 · 지도 질의 · 길찾기 링크).
2. **확인 화면은 수정 창 본문만 바꾼다.** 제목 '장소 확인', 본문 `LegacyPlaceConfirm`, 아래는 날짜 칩 · 방문 시간 · 삭제 · '시간만 저장' 그대로. 본문은 과제 9 의 부품을 다시 쓴다: 서버가 찾아 준 공공데이터 후보가 있으면 `PlaceMatchChoices`('이 장소가 맞나요?' + '아니요, 직접 적을게요'), 없거나 '아니요' 면 `CustomPlaceForm`(빈 이름 칸 + 선택 위치 찍기). 확인 화면에는 예전 이름 · 주소 · 좌표 · 메모를 쓰지도 입력칸에 채우지도 않는다(타임라인 카드에는 그대로 보인다 - 지금 표시는 건드리지 않는다). 보기 권한이면 지금처럼 읽기 전용 상세다.
3. **수정 요청은 바뀐 칸만 보낸다.** `time` · `label`(사용자가 고친 이름) · `memo`(사용자 메모). 바뀐 게 없으면 요청 없이 닫는다. 예전 행은 시간만 바꿔도 되고(`{ time }`), 후보를 고르면 `publicPlace`, 이름을 적으면 `customPlace` 를 보낸다.
4. **초안은 2판.** `{ placeId, time, label?, memo? }` - label · memo 는 사용자가 고친 것만. 예전 행은 초안을 아예 남기지 않는다. 1판 키는 앱을 켤 때 한 번 지운다(`AppProviders` 의 효과 - 경로 시험도 거치도록 `main.tsx` 가 아니라 여기에 둔다).
5. **수정 폼의 메모 칸 이름은 `meta` 로 둔다.** 과제 9 의 추가 창 코드가 아직 `setPlaceForm({ time: "", label: "", meta: "" })` 와 `form.meta` 를 쓰고, 칸 이름(`place-meta`)을 쥔 시험도 많다. 폼 값 `meta` 가 PATCH 의 `memo` 로, 초안의 `memo` 로 오갈 뿐이다(`placeEdit.ts` 한 곳). 타입은 과제 9 가 화면 안에 둔 `PlaceEditorForm` 을 지우고 같은 이름으로 `placeEdit.ts` 에서 내보낸다 - 그래서 `useState<PlaceEditorForm>` · 시트 props 의 `form: PlaceEditorForm` 은 손대지 않는다.
6. **서버가 `memo`(사용자 메모)를 따로 내려 준다**(과제 3). 수정 창 메모 칸의 처음 값은 `memo` 이고, `meta` 가 주소와 같으면 빈 칸으로 보는 `userMemoOf` 는 `memo` 가 없는 응답에만 쓰는 대체 길이다.
7. **저장 요약(`savedSummary`) 추천 - 공공데이터 참조가 없는 항목 - 은 이름만 나만의 장소로 담는다.** 주소 · 좌표 · 분류는 옮기지 않는다(카카오 값일 수 있다). 숫자인 카카오 장소 ID 가 있으면 `kakaoPlaceId` 로 남겨 링크가 살게 한다.
8. **지도 질의:** `placeOrigin` 이 `custom` 또는 `needs_review` 이면 `query: null`(이름 · 주소로 지오코딩하지 않는다). 공공데이터 행은 늘 좌표가 있어 질의를 쓰지 않는다. 예전 행(`placeOrigin` 없음)은 지금 그대로 `address || label`.
9. **카카오맵 링크:** 우리가 담은 행(`public` · `custom`)은 저장된 `placeUrl` 이 있을 때만, 예전 행은 지금처럼 주소 · 이름 검색 링크까지. 길찾기(`PlaceMapBottomSheet`)는 그대로다.
10. **넘김 주소:** `addPlace=kakao:{숫자 ID}` 와 `q`(친 말, 100자까지) 만. 일정 만들기로 가는 주소에도 `sido`(`region`) 를 싣지 않는다 - 시도도 카카오 주소에서 나온 값이다(계약: URL 에는 둘뿐, 코덱스 검토 · 사용자 결정). 지역은 일정 만들기에서 사용자가 직접 고른다(처음에는 관심 지역 첫째, 없으면 제주가 눌려 있다).
11. **넘김 받기(상세):** 주소를 한 번 읽어 state 에 쥐고 바로 주소에서 지운다 → `usePlaceById(id, q)` 로 장소가 나오면 `openAddPlace(pick 입력)`(과제 9 가 안에서 맞춰 보기를 시작한다), 못 찾으면 좌표 없는 입력(ID 만)으로 `openAddPlace`(바로 나만의 장소 칸, 카카오 ID 는 남는다).
12. **공공데이터 행의 이름 고치기는 변환이 아니다.** 서버가 공공데이터 이름 · 주소 · 사진 · 위치 · 분류는 그대로 두고 사용자 이름을 `user_label` 에 따로 담아 DTO 의 `label` 로 내려 준다. 그래서 수정 창은 이름 칸을 보이는 이름(`label`)으로 시작하고, 고쳤을 때만 PATCH 에 `label` 하나를 싣는다(`publicPlace` · `customPlace` 는 싣지 않는다). 초안도 고친 이름일 때만 `label` 을 담는다. '나만의 장소로 바뀐다'는 안내는 두지 않는다. 변환은 예전 카카오 행뿐이고 그 길은 확인 화면(`LegacyPlaceConfirm`)이 맡는다 - 예전 행은 시간 말고 `label` 을 보내지 않는다(서버가 `label` 만 와도 나만의 장소로 바꾸므로).
13. **저장이 요청 모양 오류로 거절되면 새로 고침을 안내한다**(사용자 결정 · 코덱스 재검토). 판별은 과제 9 의 `isStaleScreenError` 하나다 - 422 이고 응답 `detail` 에 모르는 필드(`extra_forbidden`)나 빠진 필드(`missing`)가 있을 때. 추가 창 묶음 저장은 과제 9, 수정 저장 · 예전 행 바꾸기(`submitPlaceEditor`)는 과제 10 이 같은 `STALE_SCREEN_MESSAGE` 와 '새로 고침' 단추를 쓴다. 일반 문구('입력값을 확인하고 다시 시도해 주세요')는 값 오류의 422 와 그 밖의 실패에 남는다. 추천 미리보기 저장(`commitRecommendationPreview`)은 이번에 넣지 않았다(질문 참조).

### 시안 v59 에서 정하는 것 (지금은 아래 문구 · 클래스로 시작한다)

구현 전에 시안 v59 로 확정한다. 코드에는 과제 9 와 같은 표시(`시안 v59` 주석)를 달았다 - `grep -rn "시안 v59" frontend/src`.

- 예전 행 확인 화면: 제목 '장소 확인', 머리글 '장소 이름을 다시 적어 주세요', 안내 문구, 푸터 단추 '시간만 저장', 클래스 `legacy-place-confirm`. 후보 · 이름 칸의 문구('이 장소가 맞나요?' 안내 · '담기' 단추 · 안내 한 줄)는 과제 9 의 부품 것을 그대로 쓰므로 '목록에 담겨요' · '담기' 같은 말이 확인 화면에 어색할 수 있다.
- 사진 + 출처: `PlacePhoto` 의 크기 · 위치(상세 시트 위쪽, 추천 미리보기 카드 아래), 클래스 `place-photo` · `place-photo-credit`. 타임라인 카드에 작은 사진을 넣을지는 시안이 정한다(지금은 넣지 않는다).
- 일정 만들기 배너 문구 '만들고 나면 고른 장소를 담을 날을 골라요'.
- 홈 '일정에 담기' 단추(`home-place-primary`) · 일정 고르기 상자(`home-trip-pick*`) - 10/4 이전(v57) CSS 를 그대로 되살린다. 새 일정 만들기 주소에는 지역이 없으므로 일정 만들기 첫 화면이 지역 고르기로 열린다(처음에는 관심 지역 첫째, 없으면 제주가 눌려 있다).
- **이름을 고친 공공데이터 행:** 일정 카드 · 상세 시트 · 수정 창 이름 칸에는 사용자가 쓴 이름이 보이고, 사진 + 출처 · 분류 · 주소 · 핀 · 카카오맵 링크는 공공데이터 그대로다. 수정 창에는 '나만의 장소로 바뀐다'는 안내를 두지 않는다(이름만 바뀐다). 고친 행에 '내가 부르는 이름' 같은 보조 표시를 둘지는 시안이 정한다(지금은 없다).
- **저장이 요청 모양 오류(422)로 거절됐을 때:** '화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.' 한 줄과 '새로 고침' 단추를 수정 창 · 예전 행 확인 화면의 오류 줄 자리에 보인다(과제 9 가 추가 창에서 쓴 것과 같은 문구 · 같은 자리, 시안 v59 주석으로 표시).
- **위치 찍기(예전 행 확인 화면의 이름 칸에서도 같은 부품):** 가운데 고정 십자선 + 방향키 + Enter(또는 '이 위치로') - 과제 9 의 시안 항목을 따른다.

### 실행 메모

- 저장소(index)의 소스는 LF 이고 작업 트리는 CRLF 다(`core.autocrlf=true` - `git ls-files --eol` 로 `i/lf w/crlf`). 여러 줄 찾아바꾸기가 안 맞으면 줄바꿈 때문이다 - 한 줄씩 찾거나, `fs.readFileSync(path, "utf8")` · `writeFileSync(path, text, "utf8")` 로 바꾼다(AGENTS.md: 한글 파일을 PowerShell `Set-Content` 로 쓰지 않는다). 이 문서의 찾을 글 · 바꿀 글은 줄바꿈을 LF 로 적었다.
- 화면 시험(`login()` 을 쓰는 것)은 시험 백엔드가 떠 있어야 한다(과제 7~9 문서의 '사전 준비 · 검증 명령' 과 같다). 순수 함수 · 컴포넌트 시험(`draftStorage` · `placeEdit` · `placeDisplay` · `PlacePhoto` · `LegacyPlaceConfirm` · `placeHandoff`)은 백엔드 없이 `cd frontend && npx vitest run <파일>` 로 돈다.
- 커밋은 과제마다 하지 않는다. 마지막 검증 과제에서 전체 검증 뒤 사용자 승인을 받아 한다. 이 부분의 e2e 는 시드 두 곳만 맞춘다(과제 12) - 실행은 마지막 검증 과제가 한다.

---

### Task 10: 초안 · 수정 · 예전 행

**파일:**
- 고치기: `frontend/src/utils/draftStorage.ts`, `frontend/src/utils/draftStorage.test.ts`
- 고치기: `frontend/src/app/AppRoot.tsx`
- 만들기: `frontend/src/components/itinerary/placeEdit.ts`, `frontend/src/components/itinerary/placeEdit.test.ts`
- 만들기: `frontend/src/components/itinerary/LegacyPlaceConfirm.tsx`, `frontend/src/components/itinerary/LegacyPlaceConfirm.test.tsx`
- 고치기: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`, `frontend/src/styles/app.css`
- 고치기: `frontend/src/app/__tests__/place-edit.test.tsx`, `frontend/src/app/__tests__/trip-detail.test.tsx`
- 만들기: `frontend/src/app/__tests__/trip-legacy-place.test.tsx`

**인터페이스:**
- 받는 것: 위 '기대는 것' 의 타입 · `listLegacyPlaceCandidates` · `PUBLIC_CATEGORY_LABEL` · `PlaceMatchChoices` · `CustomPlaceForm` · `MapPoint` · `firstPublicPlacePoint` · 페이지의 `PlaceEditorForm`/`TripPlaceEditDraft`(이 과제가 지운다).
- 내놓는 것:
  - `draftStorage.ts`: `DRAFT_VERSION`(= 2, export), `purgeStaleDrafts(storage?)`.
  - `placeEdit.ts`: `PlaceEditorForm = { time: string; label: string; meta: string }`(`meta` = 사용자 메모), `PlaceEditDraft = { placeId; time; label?; memo? }`, `PlaceReplacement = { publicPlace: PublicPlaceRef } | { customPlace: CustomPlaceInput }`, `userMemoOf(place)`, `placeEditFormFor(place, draft)`, `placeEditDraftOf(place, form)`, `placeUpdateOf(place, form, expectedRevision, replacement?)`.
  - `LegacyPlaceConfirm({ tripId, placeId, placeUrl, fallbackCenter, onReplace })`.
  - `PlaceEditorSheet` 의 새 선택 prop `legacyConfirm?: ReactNode`.

- [ ] **1단계: 실패하는 시험 쓰기**

**(1) `frontend/src/utils/draftStorage.test.ts`** - 파일 전체를 아래로 바꾼다. ('만료' 시험은 이제 현재 판으로 써야 만료 때문에 지워지는 것을 본다.)

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { DRAFT_VERSION, clearDraft, createDraftKey, purgeStaleDrafts, readDraft, saveDraft } from "./draftStorage";

describe("draftStorage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("saves, reads, and clears a draft", () => {
    const key = createDraftKey("example");

    saveDraft(key, { label: "Cafe stop" });

    expect(readDraft<{ label: string }>(key)).toEqual({ label: "Cafe stop" });

    clearDraft(key);
    expect(readDraft(key)).toBeNull();
  });

  it("ignores expired drafts", () => {
    const key = createDraftKey("expired");
    window.localStorage.setItem(
      key,
      JSON.stringify({
        version: DRAFT_VERSION,
        savedAt: Date.now() - 10_000,
        value: { label: "Old draft" },
      }),
    );

    expect(readDraft(key, 1)).toBeNull();
    expect(window.localStorage.getItem(key)).toBeNull();
  });

  it("ignores malformed draft payloads", () => {
    const key = createDraftKey("broken");
    window.localStorage.setItem(key, "{not-json");

    expect(readDraft(key)).toBeNull();
    expect(window.localStorage.getItem(key)).toBeNull();
  });

  it("is on version 2 and ignores and removes a draft that version 1 wrote", () => {
    expect(DRAFT_VERSION).toBe(2);
    const key = createDraftKey("trip-place:55:edit:1");
    window.localStorage.setItem(
      key,
      JSON.stringify({ version: 1, savedAt: Date.now(), value: { placeId: "1", label: "카카오 예전 식당", meta: "음식점 · 부산 중구 카카오로 1" } }),
    );

    expect(readDraft(key)).toBeNull();
    expect(window.localStorage.getItem(key)).toBeNull();
  });
});

describe("purgeStaleDrafts", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("removes every draft key that is not on the current version, including unreadable ones, and nothing else", () => {
    const old = { version: 1, savedAt: Date.now(), value: { label: "카카오 예전 식당", meta: "음식점 · 부산 중구 카카오로 1" } };
    // 이웃한 키 셋 - 지우면 색인이 당겨지므로 앞에서부터 지우면 하나를 건너뛴다
    for (const name of ["a", "b", "c"]) window.localStorage.setItem(createDraftKey(`trip-place:55:edit:${name}`), JSON.stringify(old));
    window.localStorage.setItem(createDraftKey("broken"), "{not-json");
    window.localStorage.setItem(createDraftKey("no-version"), JSON.stringify({ savedAt: Date.now(), value: {} }));
    const current = createDraftKey("trip-place:55:edit:9");
    saveDraft(current, { placeId: "9", time: "10:00" });
    window.localStorage.setItem("travel-hunter-production-auth", "keep");

    purgeStaleDrafts();

    const left = Array.from({ length: window.localStorage.length }, (_, index) => window.localStorage.key(index)).sort();
    expect(left).toEqual([current, "travel-hunter-production-auth"].sort());
    expect(readDraft(current)).toEqual({ placeId: "9", time: "10:00" });
  });

  it("does nothing when storage is unavailable", () => {
    expect(() => purgeStaleDrafts(null)).not.toThrow();
  });
});
```

**(2) `frontend/src/components/itinerary/placeEdit.test.ts`** - 새 파일. (폼의 `meta` 가 사용자 메모이고, 초안 · 요청에서는 `memo` 다.)

```ts
import { describe, expect, it } from "vitest";
import type { ItineraryPlace } from "../../api";
import { placeEditDraftOf, placeEditFormFor, placeUpdateOf, userMemoOf } from "./placeEdit";

const legacy: ItineraryPlace = {
  id: "9",
  time: "09:00",
  label: "카카오 예전 식당",
  meta: "음식점 · 부산 중구 카카오로 1",
  address: "부산 중구 카카오로 1",
  latitude: 35.1,
  longitude: 129.03,
  category: "음식점 > 한식",
  categoryCode: "FD6",
  placeUrl: "http://place.map.kakao.com/777",
  sourceProvider: "kakao",
  externalPlaceId: "777",
  needsConfirmation: true,
};

const address = "전남광주통합특별시 여수시 오동도로 222";
const publicRow: ItineraryPlace = {
  id: "1",
  time: "09:00",
  label: "오동도",
  meta: address,
  address,
  latitude: 34.7443,
  longitude: 127.7663,
  placeOrigin: "public",
  publicSource: "tourapi",
  publicSourceId: "126508",
  publicCategory: "sight",
};
const withMemo: ItineraryPlace = { ...publicRow, meta: "동백꽃 철에 가기" };

describe("userMemoOf", () => {
  it("is empty when the server only filled meta with the address", () => {
    expect(userMemoOf(publicRow)).toBe("");
    expect(userMemoOf({ ...publicRow, meta: "" })).toBe("");
  });

  it("is the user's memo when meta differs from the address", () => {
    expect(userMemoOf(withMemo)).toBe("동백꽃 철에 가기");
  });

  it("prefers a separate memo field when the server sends one", () => {
    expect(userMemoOf({ ...publicRow, memo: null })).toBe("");
    expect(userMemoOf({ ...publicRow, memo: "따로 받은 메모" })).toBe("따로 받은 메모");
  });
});

describe("placeEditFormFor", () => {
  it("fills the form from the row", () => {
    expect(placeEditFormFor(withMemo, null)).toEqual({ time: "09:00", label: "오동도", meta: "동백꽃 철에 가기" });
  });

  it("takes back only what the draft kept", () => {
    expect(placeEditFormFor(withMemo, { placeId: "1", time: "11:20" })).toEqual({ time: "11:20", label: "오동도", meta: "동백꽃 철에 가기" });
    expect(placeEditFormFor(withMemo, { placeId: "1", time: "09:00", label: "내가 부르는 이름", memo: "" })).toEqual({
      time: "09:00",
      label: "내가 부르는 이름",
      meta: "",
    });
  });

  it("never copies an old Kakao row's name, address or memo into the form", () => {
    const form = placeEditFormFor(legacy, null);
    expect(form).toEqual({ time: "09:00", label: "", meta: "" });
    expect(JSON.stringify(form)).not.toMatch(/카카오|부산 중구|음식점/);
  });
});

describe("placeEditDraftOf", () => {
  it("keeps only the time while the name and memo are untouched", () => {
    expect(placeEditDraftOf(publicRow, { time: "10:00", label: "오동도", meta: "" })).toEqual({ placeId: "1", time: "10:00" });
  });

  it("adds the name and memo only when the user changed them", () => {
    expect(placeEditDraftOf(withMemo, { time: "09:00", label: "내가 부르는 이름", meta: "동백꽃 철에 가기" })).toEqual({
      placeId: "1",
      time: "09:00",
      label: "내가 부르는 이름",
    });
    expect(placeEditDraftOf(withMemo, { time: "09:00", label: "오동도", meta: "" })).toEqual({ placeId: "1", time: "09:00", memo: "" });
  });

  it("never holds an address, coordinates or a category", () => {
    const draft = placeEditDraftOf(publicRow, { time: "10:00", label: "새 이름", meta: "새 메모" });
    expect(Object.keys(draft ?? {}).sort()).toEqual(["label", "memo", "placeId", "time"]);
  });

  it("leaves no draft at all for an old Kakao row", () => {
    expect(placeEditDraftOf(legacy, { time: "10:00", label: "", meta: "" })).toBeNull();
  });
});

describe("placeUpdateOf", () => {
  it("sends only the changed fields", () => {
    expect(placeUpdateOf(withMemo, { time: "10:00", label: "오동도", meta: "동백꽃 철에 가기" }, 3)).toEqual({ expectedRevision: 3, time: "10:00" });
    expect(placeUpdateOf(withMemo, { time: "09:00", label: "새 이름", meta: "동백꽃 철에 가기" }, 3)).toEqual({ expectedRevision: 3, label: "새 이름" });
    expect(placeUpdateOf(withMemo, { time: "09:00", label: "오동도", meta: "새 메모" }, 3)).toEqual({ expectedRevision: 3, memo: "새 메모" });
  });

  it("sends nothing when nothing changed", () => {
    expect(placeUpdateOf(withMemo, { time: "09:00", label: "오동도", meta: "동백꽃 철에 가기" }, 3)).toBeNull();
    expect(placeUpdateOf(publicRow, { time: "09:00", label: " 오동도 ", meta: "" }, 3)).toBeNull();
  });

  it("trims the typed name and memo, and sends an emptied memo as an empty string", () => {
    expect(placeUpdateOf(withMemo, { time: "09:00", label: "  새 이름  ", meta: "" }, 3)).toEqual({ expectedRevision: 3, label: "새 이름", memo: "" });
  });

  it("sends an emptied time as an empty string", () => {
    expect(placeUpdateOf(publicRow, { time: "", label: "오동도", meta: "" }, 3)).toEqual({ expectedRevision: 3, time: "" });
  });

  it("sends only the time for an old Kakao row, never a name or memo", () => {
    expect(placeUpdateOf(legacy, { time: "10:00", label: "", meta: "" }, 4)).toEqual({ expectedRevision: 4, time: "10:00" });
    expect(placeUpdateOf(legacy, { time: "09:00", label: "", meta: "" }, 4)).toBeNull();
  });

  it("replaces an old Kakao row by reference, keeping a changed time", () => {
    const publicPlace = { source: "tourapi" as const, sourceId: "126508" };
    expect(placeUpdateOf(legacy, { time: "09:00", label: "", meta: "" }, 4, { publicPlace })).toEqual({ expectedRevision: 4, publicPlace });
    expect(placeUpdateOf(legacy, { time: "10:00", label: "", meta: "" }, 4, { publicPlace })).toEqual({ expectedRevision: 4, time: "10:00", publicPlace });
  });

  it("replaces an old Kakao row with the user's own place", () => {
    const customPlace = { name: "내가 아는 식당", latitude: 35.2, longitude: 129.1 };
    expect(placeUpdateOf(legacy, { time: "09:00", label: "", meta: "" }, 4, { customPlace })).toEqual({ expectedRevision: 4, customPlace });
  });

  it("renames a public place by sending the label alone, never swapping it for another place", () => {
    const update = placeUpdateOf(publicRow, { time: "09:00", label: "내가 부르는 이름", meta: "" }, 3);

    // 서버가 공공데이터 이름 · 주소 · 사진 · 위치는 그대로 두고 사용자 이름만 따로 담는다 - 클라이언트는 이름 하나만 보낸다
    expect(update).toEqual({ expectedRevision: 3, label: "내가 부르는 이름" });
    expect(update).not.toHaveProperty("publicPlace");
    expect(update).not.toHaveProperty("customPlace");
  });

  it("starts from the name the row shows, which is the name the user gave once the place was renamed", () => {
    const renamed: ItineraryPlace = { ...publicRow, label: "내가 부르는 이름" };

    expect(placeEditFormFor(renamed, null).label).toBe("내가 부르는 이름");
    // 이름을 안 건드리면 요청도 초안도 이름을 싣지 않는다
    expect(placeUpdateOf(renamed, { time: "10:00", label: "내가 부르는 이름", meta: "" }, 3)).toEqual({ expectedRevision: 3, time: "10:00" });
    expect(placeEditDraftOf(renamed, { time: "10:00", label: "내가 부르는 이름", meta: "" })).toEqual({ placeId: "1", time: "10:00" });
  });
});
```

**(3) `frontend/src/components/itinerary/LegacyPlaceConfirm.test.tsx`** - 새 파일. 과제 9 의 실제 부품(`PlaceMatchChoices` · `CustomPlaceForm`)을 그대로 쓴다.

```tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { appDataApi, type PublicPlaceItem } from "../../api";
import { LegacyPlaceConfirm } from "./LegacyPlaceConfirm";

const jagalchi: PublicPlaceItem = {
  source: "tourapi",
  sourceId: "126508",
  name: "자갈치시장",
  address: "부산 중구 자갈치해안로 52",
  latitude: 35.0966,
  longitude: 129.0306,
  category: "shopping",
  distanceMeters: 40,
};

afterEach(() => {
  vi.restoreAllMocks();
});

function renderConfirm(props: Partial<Parameters<typeof LegacyPlaceConfirm>[0]> = {}) {
  const onReplace = vi.fn();
  render(
    <LegacyPlaceConfirm
      fallbackCenter={null}
      onReplace={onReplace}
      placeId="9"
      placeUrl="http://place.map.kakao.com/777"
      tripId="70"
      {...props}
    />,
  );
  return onReplace;
}

describe("LegacyPlaceConfirm", () => {
  it("asks for the name again and offers the public places the server found for the old row", async () => {
    const listSpy = vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    const onReplace = renderConfirm();

    expect(screen.getByText("장소 이름을 다시 적어 주세요")).toBeInTheDocument();
    expect(listSpy).toHaveBeenCalledWith("70", "9");
    const choices = await screen.findByRole("region", { name: "이 장소가 맞나요?" });
    const candidate = within(choices).getByRole("button", { name: "자갈치시장 선택" });
    expect(candidate).toHaveTextContent("쇼핑");
    expect(candidate).toHaveTextContent("부산 중구 자갈치해안로 52");

    await userEvent.setup().click(candidate);
    expect(onReplace).toHaveBeenCalledWith({ publicPlace: { source: "tourapi", sourceId: "126508" } });
  });

  it("opens the name field when none of the candidates is right, and turns the name into the user's own place", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    const onReplace = renderConfirm();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "아니요, 직접 적을게요" }));
    const form = screen.getByRole("form", { name: "나만의 장소" });
    expect(within(form).getByLabelText("장소 이름")).toHaveValue("");
    await user.type(within(form).getByLabelText("장소 이름"), "  내가 아는 식당  ");
    await user.click(within(form).getByRole("button", { name: "담기" }));

    expect(onReplace).toHaveBeenCalledWith({ customPlace: { name: "내가 아는 식당", latitude: null, longitude: null } });
  });

  it("goes back to the candidates when the name field is cancelled", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    renderConfirm();
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "아니요, 직접 적을게요" }));
    await user.click(within(screen.getByRole("form", { name: "나만의 장소" })).getByRole("button", { name: "취소" }));

    expect(await screen.findByRole("region", { name: "이 장소가 맞나요?" })).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "나만의 장소" })).toBeNull();
  });

  it("shows the name field straight away when the server finds no candidate, and cancel clears what was typed", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([]);
    renderConfirm();
    const user = userEvent.setup();

    const form = await screen.findByRole("form", { name: "나만의 장소" });
    expect(screen.queryByRole("region", { name: "이 장소가 맞나요?" })).toBeNull();
    await user.type(within(form).getByLabelText("장소 이름"), "쓰다 만 이름");
    await user.click(within(form).getByRole("button", { name: "취소" }));

    expect(within(screen.getByRole("form", { name: "나만의 장소" })).getByLabelText("장소 이름")).toHaveValue("");
  });

  it("falls back to the name field when the candidate request fails", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockRejectedValue(new Error("network"));
    renderConfirm();

    expect(await screen.findByText("비슷한 장소를 불러오지 못했어요. 이름을 직접 적어 주세요.")).toBeInTheDocument();
    expect(screen.getByRole("form", { name: "나만의 장소" })).toBeInTheDocument();
  });

  it("links to Kakao Map only when the row kept a place url", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([]);
    const { unmount } = render(
      <LegacyPlaceConfirm fallbackCenter={null} onReplace={vi.fn()} placeId="9" placeUrl="http://place.map.kakao.com/777" tripId="70" />,
    );
    const link = screen.getByRole("link", { name: "카카오맵에서 보기" });
    expect(link).toHaveAttribute("href", "http://place.map.kakao.com/777");
    expect(link).toHaveAttribute("target", "_blank");
    unmount();

    render(<LegacyPlaceConfirm fallbackCenter={null} onReplace={vi.fn()} placeId="9" placeUrl={null} tripId="70" />);
    expect(screen.queryByRole("link", { name: "카카오맵에서 보기" })).toBeNull();
  });
});
```

**(4) `frontend/src/app/__tests__/trip-legacy-place.test.tsx`** - 새 파일(화면 시험: 예전 행 한 줄이 든 일정으로 수정 창을 연다).

```tsx
import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, appDataApi, type ItineraryPlace, type PublicPlaceItem, type Trip } from "../../api";
import { getPreviewTrip } from "../../test/fixtures";
import { login, renderAppRoute } from "../../test/renderAppRoute";

// jsdom 에는 scrollIntoView 가 없다. 이동 후 카드로 스크롤하는 코드가 여기서 터진다.
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? vi.fn();

const kakaoName = "카카오 예전 식당";
const kakaoAddress = "부산 중구 카카오로 1";
const legacyPlace: ItineraryPlace = {
  id: "9",
  time: "09:00",
  label: kakaoName,
  meta: `음식점 · ${kakaoAddress}`,
  address: kakaoAddress,
  latitude: 35.1,
  longitude: 129.03,
  category: "음식점 > 한식",
  categoryCode: "FD6",
  placeUrl: "http://place.map.kakao.com/777",
  sourceProvider: "kakao",
  externalPlaceId: "777",
  needsConfirmation: true,
};
const jagalchi: PublicPlaceItem = {
  source: "tourapi",
  sourceId: "126508",
  name: "자갈치시장",
  address: "부산 중구 자갈치해안로 52",
  latitude: 35.0966,
  longitude: 129.0306,
  category: "shopping",
  distanceMeters: 40,
};

function tripWith(places: ItineraryPlace[], role: Trip["currentUserRole"] = "owner"): Trip {
  return { ...getPreviewTrip(), id: "70", revision: 4, title: "예전 행 확인 여행", currentUserRole: role, days: { 1: places, 2: [] } };
}

async function openLegacyRow(trip: Trip) {
  vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
  await login();
  cleanup();
  renderAppRoute(`/trips/${trip.id}?day=1`);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: `${kakaoName} 상세 열기` }));
  return user;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("Travel Hunter app — old Kakao place rows", () => {
  it("opens the confirm screen instead of the edit form and keeps the old Kakao values out of it", async () => {
    const listSpy = vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    await openLegacyRow(tripWith([legacyPlace]));

    const sheet = await screen.findByRole("dialog", { name: "장소 확인" });
    expect(within(sheet).getByText("장소 이름을 다시 적어 주세요")).toBeInTheDocument();
    expect(listSpy).toHaveBeenCalledWith("70", "9");
    expect(await within(sheet).findByRole("region", { name: "이 장소가 맞나요?" })).toBeInTheDocument();
    // 수정 창의 장소명 · 메모 칸은 없다 - 예전 이름 · 주소 · 메모를 폼에 옮기지 않는다
    expect(sheet.querySelector('input[name="place-label"]')).toBeNull();
    expect(sheet.querySelector('textarea[name="place-meta"]')).toBeNull();
    expect(sheet).not.toHaveTextContent(kakaoName);
    expect(sheet).not.toHaveTextContent(kakaoAddress);
    expect(within(sheet).getByRole("link", { name: "카카오맵에서 보기" })).toHaveAttribute("href", "http://place.map.kakao.com/777");
    // 시간 바꾸기는 그대로
    expect(within(sheet).getByRole("button", { name: "방문 시간 1시간 증가" })).toBeInTheDocument();
  });

  it("replaces the old row with the picked public place by reference only", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    const trip = tripWith([legacyPlace]);
    const updateSpy = vi.spyOn(appDataApi, "updateTripPlace").mockResolvedValue({
      ...trip,
      revision: 5,
      days: {
        1: [{ id: "9", time: "09:00", label: "자갈치시장", meta: "부산 중구 자갈치해안로 52", address: "부산 중구 자갈치해안로 52", placeOrigin: "public", publicSource: "tourapi", publicSourceId: "126508" }],
        2: [],
      },
    });
    const user = await openLegacyRow(trip);
    const sheet = await screen.findByRole("dialog", { name: "장소 확인" });

    await user.click(await within(sheet).findByRole("button", { name: "자갈치시장 선택" }));

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith("70", "9", { expectedRevision: 4, publicPlace: { source: "tourapi", sourceId: "126508" } }),
    );
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "장소 확인" })).not.toBeInTheDocument());
    expect(document.body).toHaveTextContent("자갈치시장");
    expect(document.body).not.toHaveTextContent(kakaoName);
  });

  it("replaces the old row with a name the user typed", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([]);
    const trip = tripWith([legacyPlace]);
    const updateSpy = vi.spyOn(appDataApi, "updateTripPlace").mockResolvedValue({
      ...trip,
      revision: 5,
      days: { 1: [{ id: "9", time: "09:00", label: "내가 아는 식당", meta: "", placeOrigin: "custom" }], 2: [] },
    });
    const user = await openLegacyRow(trip);
    const sheet = await screen.findByRole("dialog", { name: "장소 확인" });

    const form = await within(sheet).findByRole("form", { name: "나만의 장소" });
    await user.type(within(form).getByLabelText("장소 이름"), "내가 아는 식당");
    await user.click(within(form).getByRole("button", { name: "담기" }));

    await waitFor(() =>
      expect(updateSpy).toHaveBeenCalledWith("70", "9", {
        expectedRevision: 4,
        customPlace: { name: "내가 아는 식당", latitude: null, longitude: null },
      }),
    );
    await waitFor(() => expect(document.body).toHaveTextContent("내가 아는 식당"));
  });

  it("changes only the time of an old row", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([]);
    const trip = tripWith([legacyPlace]);
    const updateSpy = vi.spyOn(appDataApi, "updateTripPlace").mockResolvedValue({
      ...trip,
      revision: 5,
      days: { 1: [{ ...legacyPlace, time: "10:00" }], 2: [] },
    });
    const user = await openLegacyRow(trip);
    const sheet = await screen.findByRole("dialog", { name: "장소 확인" });

    await user.click(within(sheet).getByRole("button", { name: "방문 시간 1시간 증가" }));
    await user.click(within(sheet).getByRole("button", { name: "시간만 저장" }));

    // 이름 · 메모 · 주소 · 좌표 · 분류는 한 글자도 보내지 않는다
    await waitFor(() => expect(updateSpy).toHaveBeenCalledWith("70", "9", { time: "10:00", expectedRevision: 4 }));
  });

  it("keeps the old Kakao name and address out of local drafts", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([]);
    const user = await openLegacyRow(tripWith([legacyPlace]));
    const sheet = await screen.findByRole("dialog", { name: "장소 확인" });

    await user.click(within(sheet).getByRole("button", { name: "방문 시간 1시간 증가" }));

    const keys = Array.from({ length: window.localStorage.length }, (_, index) => window.localStorage.key(index) ?? "");
    const draftKeys = keys.filter((key) => key.startsWith("travel-hunter:draft:"));
    expect(draftKeys).toEqual([]);
    expect(keys.map((key) => window.localStorage.getItem(key) ?? "").join("\n")).not.toContain(kakaoName);
  });

  it("keeps the read-only detail for viewers", async () => {
    const listSpy = vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    await openLegacyRow(tripWith([legacyPlace], "viewer"));

    const sheet = await screen.findByRole("dialog", { name: "장소 상세" });
    expect(within(sheet).getByText(kakaoAddress)).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "장소 확인" })).not.toBeInTheDocument();
    expect(listSpy).not.toHaveBeenCalled();
  });

  it("asks for a refresh when replacing the old row is refused with 422", async () => {
    vi.spyOn(appDataApi, "listLegacyPlaceCandidates").mockResolvedValue([jagalchi]);
    const updateSpy = vi
      .spyOn(appDataApi, "updateTripPlace")
      .mockRejectedValue(
        new ApiError("Unprocessable Entity", {
          status: 422,
          statusText: "Unprocessable Entity",
          // 옛 화면이 보낸 모양 - 서버가 모르는 필드(예전 메모 칸 meta)를 거절했다
          detail: [{ type: "extra_forbidden", loc: ["body", "meta"], msg: "Extra inputs are not permitted" }],
        }),
      );
    const reload = vi.fn();
    vi.stubGlobal("location", { ...window.location, reload });
    const user = await openLegacyRow(tripWith([legacyPlace]));
    const sheet = await screen.findByRole("dialog", { name: "장소 확인" });

    await user.click(await within(sheet).findByRole("button", { name: "자갈치시장 선택" }));

    await waitFor(() => expect(updateSpy).toHaveBeenCalledTimes(1));
    expect(await within(sheet).findByText("화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.")).toBeInTheDocument();
    expect(within(sheet).queryByText(/입력값을 확인하고 다시 시도해 주세요/)).not.toBeInTheDocument();
    await user.click(within(sheet).getByRole("button", { name: "새로 고침" }));
    expect(reload).toHaveBeenCalledTimes(1);
  });
});
```

**(5) `frontend/src/app/__tests__/place-edit.test.tsx`** - 메모 칸 이름(`place-meta`)은 그대로다. 요청의 `meta` 가 `memo` 로 바뀌고, 요청 본문이 정확히 바뀐 칸뿐이다. 기존 시험 네 곳을 고치고 새 시험 다섯을 더한다(마지막 둘이 공공데이터 행 이름 고치기와 422 새로 고침 안내다).

 가. 맨 위 `from "../../api"` 목록에 `type ItineraryPlace,` 를 `ApiError,` `appDataApi,` 다음 줄에 더한다.

 나. `edits places from the itinerary detail` 의 단언을 바꾼다.

```tsx
      await waitFor(() =>
        expect(updatePlaceSpy).toHaveBeenCalledWith(
          "55",
          "1",
          expect.objectContaining({
            time: "10:20",
            label: "Updated peak",
            meta: "New memo",
            expectedRevision: 1,
          }),
        ),
      );
```
→
```tsx
      await waitFor(() =>
        expect(updatePlaceSpy).toHaveBeenCalledWith("55", "1", {
          time: "10:20",
          label: "Updated peak",
          memo: "New memo",
          expectedRevision: 1,
        }),
      );
```

 다. `refreshes the trip and preserves edit drafts when a stale place save conflicts` 의 단언을 정확한 본문으로 좁힌다.

```tsx
          expect.objectContaining({ label: "My unsaved edit", expectedRevision: 1 }),
```
→
```tsx
          { label: "My unsaved edit", expectedRevision: 1 },
```

 라. `restores and clears edit-place drafts` 의 초안 저장을 확인하는 `waitFor`(`toContain("Draft peak")`) 바로 다음에 아래를 더한다 - 초안의 메모 칸 이름은 `memo` 다.

```tsx
      expect(
        JSON.parse(window.localStorage.getItem("travel-hunter:draft:trip-place:55:edit:1")!).value,
      ).toEqual({ placeId: "1", time: "11:20", label: "Draft peak", memo: "Draft memo" });
```

 마. `moves the place immediately when a day chip is chosen and saves fields without a move` 의 단언을 좁힌다.

```tsx
        expect(updateSpy).toHaveBeenCalledWith("58", "1", expect.objectContaining({ label: "Renamed peak", expectedRevision: 6 })),
```
→
```tsx
        expect(updateSpy).toHaveBeenCalledWith("58", "1", { label: "Renamed peak", expectedRevision: 6 }),
```

 바. `describe` 닫는 `});` 바로 앞(마지막 시험 `reports a failed day move from the sheet instead of swallowing it` 뒤)에 새 시험 셋을 더한다.

```tsx
  it("keeps untouched name and memo out of the draft and sends only the changed time", async () => {
    const address = "전남광주통합특별시 여수시 오동도로 222";
    const publicRow: ItineraryPlace = {
      id: "1",
      time: "09:00",
      label: "오동도",
      meta: address,
      address,
      latitude: 34.7443,
      longitude: 127.7663,
      placeOrigin: "public",
      publicSource: "tourapi",
      publicSourceId: "126508",
      publicCategory: "sight",
    };
    const trip: Trip = { ...getPreviewTrip(), id: "81", revision: 3, currentUserRole: "owner", days: { 1: [publicRow] } };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const updateSpy = vi
      .spyOn(appDataApi, "updateTripPlace")
      .mockResolvedValue({ ...trip, revision: 4, days: { 1: [{ ...publicRow, time: "10:00" }] } });
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/81");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: "오동도 상세 열기" }));

      // 서버가 meta 를 주소로 채운 행 - 메모 칸은 비어 있다
      expect(document.querySelector('input[name="place-label"]')).toHaveValue("오동도");
      expect(document.querySelector('textarea[name="place-meta"]')).toHaveValue("");

      await user.click(screen.getByRole("button", { name: "방문 시간 1시간 증가" }));
      const stored = JSON.parse(window.localStorage.getItem("travel-hunter:draft:trip-place:81:edit:1")!);
      expect(stored.value).toEqual({ placeId: "1", time: "10:00" });

      await user.click(screen.getByRole("button", { name: "저장하기" }));
      await waitFor(() => expect(updateSpy).toHaveBeenCalledWith("81", "1", { time: "10:00", expectedRevision: 3 }));
    } finally {
      getTripSpy.mockRestore();
      updateSpy.mockRestore();
    }
  });

  it("closes the edit sheet without a request when nothing changed", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "82",
      revision: 3,
      currentUserRole: "owner",
      days: { 1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const updateSpy = vi.spyOn(appDataApi, "updateTripPlace");
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/82");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: "Sunrise peak 상세 열기" }));
      await user.click(screen.getByRole("button", { name: "저장하기" }));

      await waitFor(() => expect(screen.queryByRole("dialog", { name: "장소 수정" })).not.toBeInTheDocument());
      expect(updateSpy).not.toHaveBeenCalled();
    } finally {
      getTripSpy.mockRestore();
      updateSpy.mockRestore();
    }
  });

  it("drops drafts that an older version wrote when the app starts", async () => {
    await login();
    cleanup();
    const stale = "travel-hunter:draft:trip-place:55:edit:1";
    window.localStorage.setItem(
      stale,
      JSON.stringify({ version: 1, savedAt: Date.now(), value: { placeId: "1", time: "09:00", label: "카카오 예전 이름", meta: "음식점 · 부산 중구 카카오로 1" } }),
    );

    renderAppRoute("/login");

    await waitFor(() => expect(window.localStorage.getItem(stale)).toBeNull());
  });

  it("renames a public place by sending only the label, without any notice that the place changes kind", async () => {
    const address = "전남광주통합특별시 여수시 오동도로 222";
    const publicRow: ItineraryPlace = {
      id: "1",
      time: "09:00",
      label: "오동도",
      meta: address,
      address,
      latitude: 34.7443,
      longitude: 127.7663,
      placeOrigin: "public",
      publicSource: "tourapi",
      publicSourceId: "126508",
      publicCategory: "sight",
    };
    const trip: Trip = { ...getPreviewTrip(), id: "83", revision: 3, currentUserRole: "owner", days: { 1: [publicRow] } };
    // 서버는 사용자 이름을 따로 담고 화면에는 고친 이름을 내려 준다 - 공공데이터 값은 그대로다
    const renamed: ItineraryPlace = { ...publicRow, label: "내가 부르는 이름" };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const updateSpy = vi
      .spyOn(appDataApi, "updateTripPlace")
      .mockResolvedValue({ ...trip, revision: 4, days: { 1: [renamed] } });
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/83");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: "오동도 상세 열기" }));
      const sheet = await screen.findByRole("dialog", { name: "장소 수정" });

      // 이름 칸은 보이는 이름으로 시작한다
      const nameField = sheet.querySelector('input[name="place-label"]') as HTMLInputElement;
      expect(nameField).toHaveValue("오동도");
      await user.clear(nameField);
      await user.type(nameField, "내가 부르는 이름");
      // 고쳐도 나만의 장소로 바뀐다는 안내는 없다
      expect(sheet).not.toHaveTextContent(/나만의 장소|바뀌|변환/);
      // 초안에는 고친 이름만 남는다
      expect(JSON.parse(window.localStorage.getItem("travel-hunter:draft:trip-place:83:edit:1")!).value).toEqual({
        placeId: "1",
        time: "09:00",
        label: "내가 부르는 이름",
      });

      await user.click(within(sheet).getByRole("button", { name: "저장하기" }));

      // 이름 하나만 보낸다 - 다른 장소로 바꾸는 publicPlace · customPlace 는 없다
      await waitFor(() => expect(updateSpy).toHaveBeenCalledWith("83", "1", { label: "내가 부르는 이름", expectedRevision: 3 }));
      await waitFor(() => expect(screen.queryByRole("dialog", { name: "장소 수정" })).not.toBeInTheDocument());
      // 일정에는 고친 이름이 보이고, 다시 열면 이름 칸이 그 이름으로 시작한다
      await user.click(await screen.findByRole("button", { name: "내가 부르는 이름 상세 열기" }));
      expect(document.querySelector('input[name="place-label"]')).toHaveValue("내가 부르는 이름");
    } finally {
      getTripSpy.mockRestore();
      updateSpy.mockRestore();
    }
  });

  it("asks for a refresh instead of the generic message when saving an edit is refused with 422", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "84",
      revision: 3,
      currentUserRole: "owner",
      days: { 1: [{ id: "1", time: "09:00", label: "Sunrise peak", meta: "Nature" }] },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const updateSpy = vi
      .spyOn(appDataApi, "updateTripPlace")
      .mockRejectedValue(
        new ApiError("Unprocessable Entity", {
          status: 422,
          statusText: "Unprocessable Entity",
          // 옛 화면이 보낸 모양 - 서버가 모르는 필드(예전 메모 칸 meta)를 거절했다
          detail: [{ type: "extra_forbidden", loc: ["body", "meta"], msg: "Extra inputs are not permitted" }],
        }),
      );
    const reload = vi.fn();
    vi.stubGlobal("location", { ...window.location, reload });
    try {
      await login();
      cleanup();
      renderAppRoute("/trips/84");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: "Sunrise peak 상세 열기" }));
      const sheet = await screen.findByRole("dialog", { name: "장소 수정" });
      const nameField = sheet.querySelector('input[name="place-label"]') as HTMLInputElement;
      await user.clear(nameField);
      await user.type(nameField, "Renamed peak");

      await user.click(within(sheet).getByRole("button", { name: "저장하기" }));

      await waitFor(() => expect(updateSpy).toHaveBeenCalledTimes(1));
      expect(await within(sheet).findByText("화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.")).toBeInTheDocument();
      expect(within(sheet).queryByText(/입력값을 확인하고 다시 시도해 주세요/)).not.toBeInTheDocument();
      // 쓰던 내용은 그대로 남는다
      expect(nameField).toHaveValue("Renamed peak");
      expect(reload).not.toHaveBeenCalled();
      await user.click(within(sheet).getByRole("button", { name: "새로 고침" }));
      expect(reload).toHaveBeenCalledTimes(1);
    } finally {
      getTripSpy.mockRestore();
      updateSpy.mockRestore();
      vi.unstubAllGlobals();
    }
  });
```

**(6) `frontend/src/app/__tests__/trip-detail.test.tsx`** - `persists existing place time edits on completion even without selected candidates` 의 단언을 정확한 본문으로 좁힌다 - 기존 장소의 시간 수정에 예전처럼 장소 전체를 펼쳐 보내지 않는다. (`PlaceEditorSheet` 단독 렌더의 `form={{ time: "", label: "", meta: "" }}` 은 `meta` 를 그대로 쓰므로 바꾸지 않는다.)

```tsx
      expect(updatePlaceSpy).toHaveBeenCalledWith("121", "existing-time-1", expect.objectContaining({ time: "10:00", expectedRevision: 8 }));
```
→
```tsx
      expect(updatePlaceSpy).toHaveBeenCalledWith("121", "existing-time-1", { time: "10:00", expectedRevision: 8 });
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd frontend && npx vitest run src/utils/draftStorage.test.ts src/components/itinerary/placeEdit.test.ts src/components/itinerary/LegacyPlaceConfirm.test.tsx src/app/__tests__/place-edit.test.tsx src/app/__tests__/trip-legacy-place.test.tsx src/app/__tests__/trip-detail.test.tsx`
기대: FAIL 5개 파일 - 시험 18개(관찰한 값).
- `draftStorage.test.ts`: 3개 - `is on version 2 ...`(`expected undefined to be 2` - `DRAFT_VERSION` 이 아직 내보내지 않은 값이다), `purgeStaleDrafts` 두 개(`purgeStaleDrafts is not a function`).
- `placeEdit.test.ts` · `LegacyPlaceConfirm.test.tsx`: 파일 자체가 못 읽힌다(`Failed to resolve import "./placeEdit"` · `"./LegacyPlaceConfirm"`).
- `place-edit.test.tsx`: 9개. 수정 PATCH 가 아직 `meta` 와 장소 전체 값을 보내 `toHaveBeenCalledWith` 가 어긋나고(`edits places ...` · 충돌 · 이동 시험), 초안 저장 값에 `label`/`meta` 가 그대로 들어 있고(`restores and clears ...` · 이름 고치기 시험의 초안 단언), 새 시험 다섯(이름 고치기 · 422 포함)도 실패한다.
- `trip-legacy-place.test.tsx`: 7개 중 6개 - `Unable to find role="dialog" and name "장소 확인"`(보기 권한 시험 하나는 옛 구현에서도 통과하는 보호 시험이다).
- `trip-detail.test.tsx`: 통과한다 - `persists existing place time edits ...` 의 단언(`{ time, expectedRevision }` 만)은 과제 9 가 그 호출을 이미 줄여 두었기 때문에 이 단계 전에 맞는다. (과제 9 의 시험은 이 단계에서 따로 판단한다 - 이 과제가 건드린 시험만 본다.)

422 안내가 정말 시험을 지키는지는 구현 뒤 `submitPlaceEditor` 의 `else if (isStaleScreenError(error))` 가지를 빼서 확인했다 - `place-edit.test.tsx` 와 `trip-legacy-place.test.tsx` 의 422 시험이 `Unable to find an element with the text: 화면이 오래됐을 수 있어요. 새로 고침한 뒤 다시 시도해 주세요.` 로 실패한다.

- [ ] **3단계: 구현**

**(1) `frontend/src/utils/draftStorage.ts`**

`const DRAFT_VERSION = 1;` 줄을 아래로 바꾼다.

```ts
/** 판을 올리면 예전 판 초안은 읽지 않고(readDraft) 앱을 켤 때 지운다(purgeStaleDrafts).
    2판 = 장소 수정 초안에서 카카오 이름 · 메모(1판 label · meta)를 뺀 모양(설계 2026-10-03 3절 6번) */
export const DRAFT_VERSION = 2;
```

`export function clearDraft(key: string): void {...}` 바로 뒤, `function getDraftStorage(): Storage | null {` 앞에 더한다.

```ts
/** 앱을 켤 때 한 번 - 현재 판이 아닌(또는 읽을 수 없는) 초안 키를 지운다. 1판 장소 수정 초안에는 카카오 이름 · 메모가 들어 있을 수 있다.
    지우면 색인이 당겨지므로 뒤에서부터 돈다. 저장소를 못 쓰면 조용히 넘어간다 - readDraft 가 예전 판을 읽지 않는 것으로 충분하다 */
export function purgeStaleDrafts(storage: Storage | null = getDraftStorage()): void {
  if (!storage) return;
  try {
    for (let index = storage.length - 1; index >= 0; index -= 1) {
      const key = storage.key(index);
      if (!key?.startsWith(DRAFT_STORAGE_PREFIX)) continue;
      if (draftVersionOf(storage.getItem(key)) !== DRAFT_VERSION) storage.removeItem(key);
    }
  } catch {
    // 초안 정리는 최선만 한다.
  }
}

function draftVersionOf(rawValue: string | null): unknown {
  try {
    return (JSON.parse(rawValue ?? "null") as { version?: unknown } | null)?.version;
  } catch {
    return undefined;
  }
}
```

**(2) `frontend/src/app/AppRoot.tsx`** - 파일 전체를 아래로 바꾼다.

```tsx
import { ReactNode, useEffect } from "react";
import { BrowserRouter } from "react-router-dom";
import { purgeStaleDrafts } from "../utils/draftStorage";
import { App } from "./App";
import { SessionProvider } from "./session";

export function AppProviders({ children }: { children: ReactNode }) {
  // 앱을 켤 때 한 번 - 예전 판 초안(1판 장소 수정 초안에는 카카오 이름 · 메모가 있다)을 지운다. 경로 시험도 이 래퍼를 거친다
  useEffect(() => {
    purgeStaleDrafts();
  }, []);
  return <SessionProvider>{children}</SessionProvider>;
}

export function AppRoot() {
  return (
    <BrowserRouter>
      <AppProviders>
        <App />
      </AppProviders>
    </BrowserRouter>
  );
}
```

**(3) `frontend/src/components/itinerary/placeEdit.ts`** - 새 파일.

```ts
import type { CustomPlaceInput, ItineraryPlace, PublicPlaceRef, TripPlaceUpdateRequest } from "../../api";

/* 장소 수정 창의 입력칸 · 초안 · 수정 요청 본문(카카오 운영정책 3단계, 설계 docs/superpowers/specs/2026-10-03-public-place-storage-design.md 2절).
   예전 카카오 행의 이름 · 주소 · 좌표 · 분류 · 메모는 폼 · 초안 · 요청 어디에도 옮기지 않는다 - `{ ...place }` 로 펴지 않는다.
   공공데이터 행의 이름을 고치는 것은 변환이 아니다: 이름 칸은 행이 보이는 이름(label - 고친 이름이 있으면 그 이름)으로 시작하고,
   고치면 label 하나만 보낸다. 서버가 공공데이터 이름 · 주소 · 사진 · 위치는 그대로 두고 사용자 이름만 따로 담는다(user_label). */

/** 수정 창 입력칸. meta 칸이 사용자 메모다(서버 PATCH 의 memo) - 추가 창 코드가 아직 { time, label, meta } 로 폼을 비우고 칸 이름(place-meta)을
    쥔 곳이 많아 이름을 그대로 둔다. 예전 카카오 행에서는 label · meta 를 비워 둔다 */
export type PlaceEditorForm = { time: string; label: string; meta: string };

/** localStorage 초안(2판). label · memo 는 사용자가 고친 것만 담는다. 주소 · 좌표 · 분류는 담지 않는다 */
export type PlaceEditDraft = { placeId: string; time: string; label?: string; memo?: string };

/** 예전 카카오 행 확인 화면에서 고른 바꿀 장소 - 공공데이터 후보(참조) 또는 사용자가 적은 이름(+ 찍은 위치) */
export type PlaceReplacement = { publicPlace: PublicPlaceRef } | { customPlace: CustomPlaceInput };

type MemoSource = Pick<ItineraryPlace, "meta" | "address"> & { memo?: string | null };

/** 사용자가 쓴 메모. 서버가 memo 를 따로 내려 주면 그대로, 아니면 meta 에서 가린다 -
    서버는 meta 를 '메모 → 없으면 주소' 로 채우므로(trips.py) 주소와 같으면 메모가 아니다 */
export function userMemoOf(place: MemoSource): string {
  if (place.memo !== undefined) return place.memo ?? "";
  const meta = (place.meta ?? "").trim();
  return meta && meta !== (place.address ?? "").trim() ? meta : "";
}

const text = (value: unknown) => (typeof value === "string" ? value : undefined);

export function placeEditFormFor(place: ItineraryPlace, draft: PlaceEditDraft | null): PlaceEditorForm {
  // 예전 카카오 행은 이름 · 메모를 비워 연다 - 시간만 값이 있다
  if (place.needsConfirmation) return { time: place.time ?? "", label: "", meta: "" };
  return {
    time: text(draft?.time) ?? place.time ?? "",
    label: text(draft?.label) ?? place.label,
    meta: text(draft?.memo) ?? userMemoOf(place),
  };
}

/** 초안으로 남길 것. 예전 카카오 행은 null - 초안을 남기지 않는다 */
export function placeEditDraftOf(place: ItineraryPlace, form: PlaceEditorForm): PlaceEditDraft | null {
  if (place.needsConfirmation || !place.id) return null;
  const draft: PlaceEditDraft = { placeId: place.id, time: form.time };
  if (form.label !== place.label) draft.label = form.label;
  if (form.meta !== userMemoOf(place)) draft.memo = form.meta;
  return draft;
}

/** 바뀐 칸만 담은 PATCH 본문. 바뀐 게 없으면 null(요청하지 않는다).
    공공데이터 · 나만의 장소 행은 고친 label · memo 만 담는다(publicPlace · customPlace 로 바꾸지 않는다).
    replacement 는 예전 카카오 행을 바꿀 때만 온다 - 서버가 그 장소로 바꾸며 주소 · 좌표 · 분류 · 메모를 새 값으로 채우므로 label · memo 는 보내지 않는다 */
export function placeUpdateOf(
  place: ItineraryPlace,
  form: PlaceEditorForm,
  expectedRevision: number,
  replacement?: PlaceReplacement,
): TripPlaceUpdateRequest | null {
  const update: TripPlaceUpdateRequest = { expectedRevision };
  const time = form.time.trim();
  if (time !== (place.time ?? "")) update.time = time;
  if (replacement) return { ...update, ...replacement };
  if (!place.needsConfirmation) {
    const label = form.label.trim();
    if (label !== place.label) update.label = label;
    const memo = form.meta.trim();
    if (memo !== userMemoOf(place)) update.memo = memo;
  }
  return Object.keys(update).length > 1 ? update : null;
}
```

**(4) `frontend/src/components/itinerary/LegacyPlaceConfirm.tsx`** - 새 파일.

```tsx
import { useState } from "react";
import { appDataApi, useAsyncResource } from "../../api";
import { CustomPlaceForm } from "./placeAdd/CustomPlaceForm";
import type { MapPoint } from "./placeAdd/MapPointPicker";
import { PlaceMatchChoices } from "./placeAdd/PlaceMatchChoices";
import type { PlaceReplacement } from "./placeEdit";

/* 예전 카카오 행을 열면 수정 창 본문 대신 이 확인 화면이 뜬다(설계 2026-10-03 2절 · 3단계).
   예전 행의 이름 · 주소 · 좌표 · 메모는 여기에 쓰지도 입력칸에 채우지도 않는다 - 서버가 저장된 값으로 찾아 준 공공데이터 후보(받은 값은 서버가 저장 · 로그하지 않는다)와
   빈 이름 칸(+ 선택 위치 찍기), 카카오맵 링크만 보인다. 고르면 부모(수정 창)가 PATCH 로 그 장소(publicPlace) 또는 사용자 글(customPlace)로 바꾼다.
   후보 · 이름 칸은 장소 추가 창의 부품(PlaceMatchChoices · CustomPlaceForm)을 그대로 쓴다. 문구 · 클래스는 시안 v59 확정 때 맞춘다. */
export function LegacyPlaceConfirm({
  fallbackCenter,
  onReplace,
  placeId,
  placeUrl,
  tripId,
}: {
  fallbackCenter: MapPoint | null;
  onReplace: (replacement: PlaceReplacement) => void;
  placeId: string;
  placeUrl?: string | null;
  tripId: string;
}) {
  const { data, error, isLoading } = useAsyncResource(() => appDataApi.listLegacyPlaceCandidates(tripId, placeId), [tripId, placeId]);
  const candidates = data ?? [];
  // typing = 후보가 있는데 '아니요, 직접 적을게요' 를 눌렀다. formVersion = 후보가 없을 때 '취소' 가 칸을 비우는 데 쓴다
  const [typing, setTyping] = useState(false);
  const [formVersion, setFormVersion] = useState(0);
  const choosing = !isLoading && candidates.length > 0 && !typing;
  const writing = !isLoading && !choosing;
  return (
    <section aria-labelledby="legacy-place-confirm-title" className="place-sheet-detail legacy-place-confirm">
      <h3 id="legacy-place-confirm-title">장소 이름을 다시 적어 주세요</h3>
      {/* 시안 v59 */}
      <p className="meta">예전에 담은 장소라 이름을 한 번 더 확인해요. 맞는 장소를 고르거나 이름을 직접 적어 주세요.</p>
      {placeUrl && (
        <a className="btn sm line" href={placeUrl} rel="noreferrer" target="_blank">
          카카오맵에서 보기
        </a>
      )}
      {isLoading && (
        <p className="place-search-status" role="status">
          비슷한 장소를 찾는 중입니다.
        </p>
      )}
      {error && <p className="place-search-status">비슷한 장소를 불러오지 못했어요. 이름을 직접 적어 주세요.</p>}
      {choosing && (
        <PlaceMatchChoices
          candidates={candidates}
          onChoose={(place) => onReplace({ publicPlace: { source: place.source, sourceId: place.sourceId } })}
          onNone={() => setTyping(true)}
        />
      )}
      {writing && (
        <CustomPlaceForm
          fallbackCenter={fallbackCenter}
          key={formVersion}
          onCancel={() => (candidates.length > 0 ? setTyping(false) : setFormVersion((version) => version + 1))}
          onSubmit={(input) => onReplace({ customPlace: input })}
          reason="none"
          tripId={tripId}
        />
      )}
    </section>
  );
}
```

**(5) `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`** - 아래 가~카 순서로 고친다(찾을 글은 과제 9 까지 적용한 파일에서 모두 한 번만 나온다).

 가. 가져오기. `import { DraftRestoreNotice } from "./_shared";` 줄 다음에 더한다. (`ReactNode` 타입 가져오기는 과제 9 가 `matchPanel` 때문에 이미 더했다 - 없으면 `react` 가져오기 목록에 `type ReactNode,` 를 더한다.)

```ts
import {
  placeEditDraftOf,
  placeEditFormFor,
  placeUpdateOf,
  type PlaceEditDraft,
  type PlaceEditorForm,
  type PlaceReplacement,
} from "../../components/itinerary/placeEdit";
import { LegacyPlaceConfirm } from "../../components/itinerary/LegacyPlaceConfirm";
```

 나. 과제 9 가 화면 안에 둔 옛 값 묶음과 초안 타입을 통째로 지운다(위 가져오기의 `PlaceEditorForm` · `PlaceEditDraft` 가 대신한다 - 이름이 같아 `useState<PlaceEditorForm>` · 시트 props 는 그대로 쓴다).

```ts
/* 수정 창이 아직 들고 있는 옛 값 묶음(옛 TripPlaceRequest) - 수정 · 초안 과제(3단계)가 카카오 값 복사와 함께 줄인다.
   추가 흐름과 저장 요청(TripPlaceAddItem)은 쓰지 않는다 */
type PlaceEditorForm = {
  time?: string;
  label: string;
  meta?: string;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  category?: string | null;
  categoryCode?: string | null;
  placeUrl?: string | null;
  sourceProvider?: string | null;
  externalPlaceId?: string | null;
};
type TripPlaceEditDraft = PlaceEditorForm & {
  placeId: string;
};
```
→ (통째로 지운다)

 다. `openEditPlace`: 초안은 예전 행에서 읽지 않고, 폼은 `placeEditFormFor` 로 만든다.

```ts
    const draft =
      canEditTrip && trip && place.id
        ? readDraft<TripPlaceEditDraft>(
            tripPlaceEditDraftKey(trip.id, place.id),
          )
        : null;
```
→
```ts
    const draft =
      canEditTrip && trip && place.id && !place.needsConfirmation
        ? readDraft<PlaceEditDraft>(tripPlaceEditDraftKey(trip.id, place.id))
        : null;
```
그리고
```ts
    setPlaceForm(
      draft
        ? { time: draft.time ?? "", label: draft.label, meta: draft.meta ?? "" }
        : { ...place, time: place.time, label: place.label, meta: place.meta },
    );
```
→
```ts
    setPlaceForm(placeEditFormFor(place, draft));
```

 라. `submitPlaceEditor`: 인자와 PATCH 본문. 먼저 줄 하나.

```ts
  const submitPlaceEditor = async () => {
```
→
```ts
  const submitPlaceEditor = async (replacement?: PlaceReplacement) => {
```
그리고 `const label = placeForm.label.trim();` 부터 `payload,\n      );` 까지(수정 모드 검증과 요청 본문 만들기 전체)를 바꾼다.

```ts
    const label = placeForm.label.trim();
    if (!label) {
      setPlaceError("장소명을 입력해 주세요.");
      return;
    }
    const time = placeForm.time?.trim() ?? "";
    if (!isTenMinutePlaceTime(time)) {
      setPlaceError(placeTimeErrorMessage);
      return;
    }
    setIsSavingPlace(true);
    setPlaceError("");
    try {
      const payload: PlaceEditorForm & { expectedRevision: number } = {
        time,
        label,
        meta: placeForm.meta?.trim() || undefined,
        expectedRevision: trip.revision,
      };
      if (placeForm.address !== undefined) payload.address = placeForm.address;
      if (placeForm.latitude !== undefined)
        payload.latitude = placeForm.latitude;
      if (placeForm.longitude !== undefined)
        payload.longitude = placeForm.longitude;
      if (placeForm.category !== undefined)
        payload.category = placeForm.category;
      if (placeForm.categoryCode !== undefined)
        payload.categoryCode = placeForm.categoryCode;
      if (placeForm.placeUrl !== undefined)
        payload.placeUrl = placeForm.placeUrl;
      if (placeForm.sourceProvider !== undefined)
        payload.sourceProvider = placeForm.sourceProvider;
      if (placeForm.externalPlaceId !== undefined)
        payload.externalPlaceId = placeForm.externalPlaceId;
      let nextTrip = await appDataApi.updateTripPlace(
        trip.id,
        placeEditor.place.id ?? "",
        payload,
      );
```
→
```ts
    // 확인 화면의 후보 · 이름 칸에는 저장 중 막는 단추가 없다 - 같은 요청이 두 번 나가지 않게 여기서 막는다
    if (isSavingPlace) return;
    // 예전 카카오 행은 이름 칸이 비어 열린다 - 이름은 확인 화면에서 고르거나 적어서 바꾼다
    const label = placeForm.label.trim();
    if (!label && !placeEditor.place.needsConfirmation) {
      setPlaceError("장소명을 입력해 주세요.");
      return;
    }
    const time = placeForm.time.trim();
    if (!isTenMinutePlaceTime(time)) {
      setPlaceError(placeTimeErrorMessage);
      return;
    }
    /* 바뀐 칸만 보낸다 - 주소 · 좌표 · 분류 같은 카카오 값은 폼에도 요청에도 없다. 바뀐 게 없으면 요청 없이 닫는다 */
    const update = placeUpdateOf(placeEditor.place, placeForm, trip.revision, replacement);
    if (!update) {
      closePlaceEditor();
      return;
    }
    setIsSavingPlace(true);
    setPlaceError("");
    try {
      let nextTrip = await appDataApi.updateTripPlace(
        trip.id,
        placeEditor.place.id ?? "",
        update,
      );
```

 마. 수정 저장과 예전 행 바꾸기(`submitPlaceEditor(replacement)`)가 요청 모양 오류(422 의 `extra_forbidden` · `missing`)로 거절되면 '새로 고침' 안내를 보인다(과제 9 가 추가 창 저장에 쓴 `isStaleScreenError` · `STALE_SCREEN_MESSAGE` 를 그대로 쓰고, 단추는 시트가 `error` 가 그 문구일 때 그린다). 배포 때 열려 있던 옛 화면이 옛 모양으로 보낸 요청을 서버가 거절하는 경우다. 값 오류의 422 는 일반 문구다.
(추천 미리보기 저장 중 '기존 장소 시간 고치기' PATCH 를 `{ time, expectedRevision }` 으로 줄이는 일은 과제 9 가 이미 했다 - 여기서 다시 하지 않는다.)

```ts
      if (isTripConflict(error)) {
        await refreshTripAfterConflict(setPlaceError);
      } else {
        setPlaceError(
          "장소 정보를 저장하지 못했어요. 입력값을 확인하고 다시 시도해 주세요.",
        );
      }
    } finally {
      setIsSavingPlace(false);
    }
  };

  const requestDeletePlace = (place: ItineraryPlace) => {
```
→
```ts
      if (isTripConflict(error)) {
        await refreshTripAfterConflict(setPlaceError);
      } else if (isStaleScreenError(error)) {
        setPlaceError(STALE_SCREEN_MESSAGE);
      } else {
        setPlaceError(
          "장소 정보를 저장하지 못했어요. 입력값을 확인하고 다시 시도해 주세요.",
        );
      }
    } finally {
      setIsSavingPlace(false);
    }
  };

  const requestDeletePlace = (place: ItineraryPlace) => {
```

 바. `updatePlaceForm`(과제 9 가 인자 타입 이름만 `PlaceEditorForm` 으로 바꿔 둔 모양).

```ts
  const updatePlaceForm = (nextForm: PlaceEditorForm) => {
    setPlaceForm(nextForm);
    if (!trip || !placeEditor) return;
    if (placeEditor.mode === "edit" && placeEditor.place.id) {
      saveDraft<TripPlaceEditDraft>(
        tripPlaceEditDraftKey(trip.id, placeEditor.place.id),
        {
          placeId: placeEditor.place.id,
          time: nextForm.time ?? "",
          label: nextForm.label,
          meta: nextForm.meta ?? "",
        },
      );
    }
  };
```
→
```ts
  const updatePlaceForm = (nextForm: PlaceEditorForm) => {
    setPlaceForm(nextForm);
    if (!trip || !placeEditor) return;
    if (placeEditor.mode === "edit" && placeEditor.place.id) {
      // 사용자가 고친 이름 · 메모만, 예전 카카오 행은 초안 없음(placeEditDraftOf 가 null)
      const draft = placeEditDraftOf(placeEditor.place, nextForm);
      if (draft) saveDraft<PlaceEditDraft>(tripPlaceEditDraftKey(trip.id, placeEditor.place.id), draft);
    }
  };
```

 사. `discardPlaceDraft`.

```ts
      setPlaceForm({
        time: placeEditor.place.time,
        label: placeEditor.place.label,
        meta: placeEditor.place.meta,
      });
```
→
```ts
      setPlaceForm(placeEditFormFor(placeEditor.place, null));
```

 아. 수정 창 렌더(`<PlaceEditorSheet`)에 넘기는 props. 과제 9 가 `matchPanel` 을 꽂은 같은 자리다. 아래 한 줄을

```tsx
          onSubmit={submitPlaceEditor}
```
→
```tsx
          onSubmit={() => void submitPlaceEditor()}
          legacyConfirm={
            placeEditor.mode === "edit" && placeEditor.place.needsConfirmation && placeEditor.place.id ? (
              <LegacyPlaceConfirm
                fallbackCenter={firstPublicPlacePoint(trip.days)}
                onReplace={(replacement) => void submitPlaceEditor(replacement)}
                placeId={placeEditor.place.id}
                placeUrl={placeEditor.place.placeUrl}
                tripId={trip.id}
              />
            ) : undefined
          }
```
(`onSubmit` 에 함수를 그대로 넘기면 클릭 이벤트가 `replacement` 로 들어간다 - 반드시 감싼다.)

 자. `PlaceEditorSheet` props. 구조 분해에서

```ts
  onSelectSearchCandidate,
  onSubmit,
  place = null,
```
→
```ts
  legacyConfirm,
  onSelectSearchCandidate,
  onSubmit,
  place = null,
```
타입에서
```ts
  onDelete?: () => void;
```
→
```ts
  onDelete?: () => void;
  /** 예전 카카오 행의 확인 화면(LegacyPlaceConfirm) - 수정 모드에서 이 행일 때만 본문을 대신한다 */
  legacyConfirm?: ReactNode;
```

 차. `PlaceEditorSheet` 본문. `const hasPlaceBasket = mode === "add" && placeBasket.length > 0;` 다음 줄에 더한다.

```ts
  /* 예전 카카오 행은 수정 창 본문 대신 확인 화면을 쓴다(시안 v59). 보기 권한이면 지금처럼 읽기 전용 상세 */
  const isLegacyConfirm = mode === "edit" && !readOnly && Boolean(place?.needsConfirmation);
```
제목 줄을 바꾼다.

```tsx
              {mode === "add" ? "장소 추가" : readOnly ? "장소 상세" : "장소 수정"}
```
→
```tsx
              {mode === "add"
                ? "장소 추가"
                : readOnly
                  ? "장소 상세"
                  : isLegacyConfirm
                    ? "장소 확인"
                    : "장소 수정"}
```
상세 줄을 바꾸고 그 뒤에 확인 화면 칸을 더한다.

```tsx
          {mode === "edit" && place && <PlaceSheetDetail place={place} />}
```
→
```tsx
          {mode === "edit" && place && !isLegacyConfirm && <PlaceSheetDetail place={place} />}
          {isLegacyConfirm && legacyConfirm}
```
장소명 칸의 여는 줄을 바꾼다.

```tsx
          {mode === "edit" ? (
            <label className="field">
              장소명
```
→
```tsx
          {mode === "edit" && !isLegacyConfirm ? (
            <label className="field">
              장소명
```
메모 칸의 여는 줄을 바꾼다(칸 이름 `place-meta` · 값 `form.meta` 는 그대로).

```tsx
          {mode === "edit" && (
            <label className="field">
              메모
```
→
```tsx
          {mode === "edit" && !isLegacyConfirm && (
            <label className="field">
              메모
```
저장 단추 글자를 바꾼다(예전 행의 푸터 저장은 시간만 저장한다 - 시안 v59).

```tsx
              {isSaving
                ? "저장 중입니다"
                : hasPlaceBasket
                  ? `Day ${dayNumber}에 ${placeBasket.length}개 저장하기`
                  : "저장하기"}
```
→
```tsx
              {isSaving
                ? "저장 중입니다"
                : hasPlaceBasket
                  ? `Day ${dayNumber}에 ${placeBasket.length}개 저장하기`
                  : isLegacyConfirm
                    ? "시간만 저장"
                    : "저장하기"}
```

**(6) `frontend/src/styles/app.css`** - 파일 끝에 더한다(시안 v59 확정 때 다듬는다).

```css
/* 시안 v59: 예전 카카오 행 확인 화면 - 후보 · 이름 칸은 장소 추가 창 부품(place-match-choices · custom-place-form)의 모양을 따른다 */
.legacy-place-confirm h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 900;
}

.legacy-place-confirm .meta {
  margin: 0;
}
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd frontend && npx vitest run src/utils/draftStorage.test.ts src/components/itinerary/placeEdit.test.ts src/components/itinerary/LegacyPlaceConfirm.test.tsx src/app/__tests__/place-edit.test.tsx src/app/__tests__/trip-legacy-place.test.tsx`
기대: PASS - 5개 파일, 시험 52개(관찰한 값).
실행: `cd frontend && npx vitest run src/app/__tests__/trip-detail.test.tsx -t "persists existing place time edits|keeps place search input responsive"`
기대: PASS - 2개(과제 9 가 같은 시험의 나머지를 맞춘 상태여야 한다).
실행: `cd frontend && npx tsc --noEmit -p .`
기대: 타입 오류 없음.

---

### Task 11: 표시 · 추천

**파일:**
- 만들기: `frontend/src/components/itinerary/placeDisplay.ts`, `frontend/src/components/itinerary/placeDisplay.test.ts`
- 쓰기만: `frontend/src/components/itinerary/PlacePhoto.tsx`(과제 9 가 시험과 함께 만든다)
- 고치기: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`, `frontend/src/api/types.ts`(한 줄), `frontend/src/styles/app.css`
- 고치기: `frontend/src/app/__tests__/trip-detail.test.tsx`

**인터페이스:**
- 받는 것: `PUBLIC_CATEGORY_LABEL` · `photoCredit(license)` · `publicTimeSlotGroup(category)`(과제 8), 타입(`ItineraryPlace` · `Recommendation` 의 새 필드 · `TripPlaceAddItem`), `mediaUrl`(`api/client`), `PlacePhoto({ url, license, alt, compact })`(과제 9). 과제 9 가 남겨 둔 추천 쪽 함수(`recommendationPlacePayload` · `tripPlaceMutationFromDisplayedPlace` 의 옛 값 묶음)를 이 과제가 바꾼다.
- 내놓는 것:
  - `placeDisplay.ts`: `isOwnPlace(place)`, `markerQueryOf(place)`, `placeCategoryText(place)`, `previewAddItem(place)`.
  - 페이지에서 `findAddedPlaceId` 를 export 한다(시험이 직접 부른다).
- 과제 9 가 이미 한 것(확인만): 쓰이지 않던 `previewPlaceFromRecommendation` · `tripPlaceMutationFromPreviewPlace` · `previewFromRecommendation` 을 지웠고, 추가 창 미리보기 마커(`placePreviewMarker`)는 담은 장소에 `query: null` 을 쓴다. 이 과제는 일정 지도 마커(`PrototypeTripMap`)와 추천 길을 맡는다.

- [ ] **1단계: 실패하는 시험 쓰기**

**(1) `frontend/src/components/itinerary/placeDisplay.test.ts`** - 새 파일.

```ts
import { describe, expect, it } from "vitest";
import { markerQueryOf, placeCategoryText, previewAddItem } from "./placeDisplay";

describe("markerQueryOf", () => {
  it("keeps looking up an old row by its address, then by its name", () => {
    expect(markerQueryOf({ label: "자갈치시장", address: "부산 중구 자갈치해안로 52" })).toBe("부산 중구 자갈치해안로 52");
    expect(markerQueryOf({ label: "자갈치시장", address: null })).toBe("자갈치시장");
  });

  it("does not look up the user's own place or a row waiting for confirmation by its name", () => {
    expect(markerQueryOf({ placeOrigin: "custom", label: "내가 아는 식당", address: null })).toBeNull();
    expect(markerQueryOf({ placeOrigin: "needs_review", label: "장소 이름을 다시 적어 주세요", address: null })).toBeNull();
  });

  it("keeps the query for a public place, which always has coordinates anyway", () => {
    expect(markerQueryOf({ placeOrigin: "public", label: "오동도", address: "전남광주통합특별시 여수시 오동도로 222" })).toBe("전남광주통합특별시 여수시 오동도로 222");
  });
});

describe("placeCategoryText", () => {
  it("names a public place by its category, an own place by what it is, and an old row as before", () => {
    expect(placeCategoryText({ placeOrigin: "public", publicCategory: "sight" })).toBe("관광지");
    expect(placeCategoryText({ placeOrigin: "custom" })).toBe("나만의 장소");
    expect(placeCategoryText({ category: "관광명소", categoryCode: "AT4" })).toBe("관광명소");
    expect(placeCategoryText({ categoryCode: "AT4" })).toBe("AT4");
    expect(placeCategoryText({})).toBe("장소");
  });
});

describe("previewAddItem", () => {
  it("sends only the reference for a public recommendation", () => {
    expect(
      previewAddItem({ time: "10:00", label: "오동도", publicSource: "tourapi", publicSourceId: "126508", sourceProvider: null, externalPlaceId: null }),
    ).toEqual({ time: "10:00", publicPlace: { source: "tourapi", sourceId: "126508" } });
  });

  it("sends only the name, as the user's own place, when a recommendation has no public reference", () => {
    expect(previewAddItem({ time: "", label: "성산일출봉", sourceProvider: "kakao_local", externalPlaceId: "rec-1" })).toEqual({
      time: "",
      customPlace: { name: "성산일출봉" },
    });
  });

  it("keeps a numeric Kakao place id so the Kakao Map link survives", () => {
    expect(previewAddItem({ time: "12:00", label: "해녀의 집", sourceProvider: "kakao", externalPlaceId: "12345" })).toEqual({
      time: "12:00",
      customPlace: { name: "해녀의 집" },
      kakaoPlaceId: "12345",
    });
  });
});
```

**(2) `PlacePhoto` 시험** - 과제 9 가 만든 `PlacePhoto.test.tsx` 를 그대로 쓴다(이 과제에서 새로 쓰지 않는다).

**(3) `frontend/src/app/__tests__/trip-detail.test.tsx`**

 가. 맨 위 페이지 가져오기 목록(`} from "../../pages/itinerary/ItineraryDetailPage";`)에 `findAddedPlaceId,` 를 `buildTimelineSortableIds,` 다음 줄에 더한다.

 나. 지도 시험 - `renders a trip detail coordinate-less Kakao map through the shared query fallback` 의 제목을 예전 행 시험임이 드러나게 바꾸고(내용은 그대로 - 예전 행은 지금처럼 주소로 찾는다), 바로 뒤에 새 시험 다섯을 더한다(마지막이 이름을 고친 공공데이터 행 - 카드 · 이름 칸 · 사진 설명이 고친 이름이고 사진 · 분류 · 주소는 공공데이터 그대로다).

```tsx
  it("renders a trip detail coordinate-less Kakao map through the shared query fallback", async () => {
```
→
```tsx
  it("renders a coordinate-less old Kakao row on the trip detail map through the shared query fallback", async () => {
```
이 시험이 끝나는 `});` 다음(다음 시험 `uses stored Kakao place URL and address in the trip map detail sheet` 앞)에 더한다.

```tsx
  it("does not look up a coordinate-less custom place by its name", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      title: "나만의 장소 지도 여행",
      dates: "2026.06.15 - 06.17",
      days: {
        1: [{ id: "custom-no-spot", time: "10:00", label: "내가 아는 식당", meta: "", placeOrigin: "custom", latitude: null, longitude: null }],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55?day=1&view=map");

      // 좌표도 찾을 말도 없으니 실제 지도는 그리지 않고 폴백 지도만 남는다 - 이름으로 카카오에 다시 묻지 않는다
      expect(await screen.findByRole("button", { name: "1번 장소: 내가 아는 식당" })).toBeInTheDocument();
      expect(kakao.addressSearch).not.toHaveBeenCalled();
      expect(kakao.keywordSearch).not.toHaveBeenCalled();
      expect(kakao.mapInstances).toHaveLength(0);
    } finally {
      getTripSpy.mockRestore();
      vi.unstubAllEnvs();
      delete window.kakao;
    }
  });

  it("draws a pin for a custom place only when the user picked a spot", async () => {
    vi.stubEnv("VITE_KAKAO_MAP_JS_KEY", "test-js-key");
    const kakao = installAppKakaoSdkMock();
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "55",
      title: "나만의 장소 지도 여행",
      dates: "2026.06.15 - 06.17",
      days: {
        1: [
          { id: "custom-spot", time: "10:00", label: "찍은 곳", meta: "", placeOrigin: "custom", latitude: 35.1, longitude: 129.1 },
          { id: "custom-no-spot", time: "12:00", label: "안 찍은 곳", meta: "", placeOrigin: "custom", latitude: null, longitude: null },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/55?day=1&view=map");

      await waitFor(() => expect(kakao.mapInstances).toHaveLength(1));
      expect(kakao.markerInstances).toHaveLength(1);
      expect(kakao.addressQueries).toEqual([]);
      expect(kakao.keywordQueries).toEqual([]);
    } finally {
      getTripSpy.mockRestore();
      vi.unstubAllEnvs();
      delete window.kakao;
    }
  });

  it("shows a public place's photo with its credit, its address and the Kakao link in the detail sheet", async () => {
    const address = "전남광주통합특별시 여수시 오동도로 222";
    const photoUrl = "https://tong.visitkorea.or.kr/cms/resource/23/3074123_image2_1.jpg";
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "57",
      currentUserRole: "owner",
      days: {
        1: [
          {
            id: "1",
            time: "09:00",
            label: "오동도",
            meta: address,
            address,
            latitude: 34.7443,
            longitude: 127.7663,
            placeOrigin: "public",
            publicSource: "tourapi",
            publicSourceId: "126508",
            publicCategory: "sight",
            photoUrl,
            photoLicense: "Type3",
            placeUrl: "https://place.map.kakao.com/8193468",
          },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/57?day=1");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: "오동도 상세 열기" }));

      const sheet = await screen.findByRole("dialog", { name: "장소 수정" });
      expect(within(sheet).getByRole("img", { name: "오동도 사진" })).toHaveAttribute("src", photoUrl);
      expect(within(sheet).getByText("사진: 한국관광공사 · 변경 금지")).toBeInTheDocument();
      expect(within(sheet).getByText("관광지")).toBeInTheDocument();
      expect(within(sheet).getByText(address)).toBeInTheDocument();
      expect(within(sheet).getByRole("link", { name: "카카오맵에서 보기" })).toHaveAttribute("href", "https://place.map.kakao.com/8193468");
      // 위치는 지도 핀이 보여 준다 - 좌표 글자는 예전 행에만 있다
      expect(within(sheet).queryByText("좌표")).not.toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("links an own place to Kakao Map only when a place url was kept, and shows no address or coordinates it does not have", async () => {
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "58",
      currentUserRole: "owner",
      days: {
        1: [
          { id: "1", time: "09:00", label: "내가 아는 식당", meta: "", placeOrigin: "custom", latitude: null, longitude: null },
          { id: "2", time: "11:00", label: "링크 있는 곳", meta: "", placeOrigin: "custom", latitude: 35.1, longitude: 129.1, placeUrl: "https://place.map.kakao.com/555" },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/58?day=1");
      const user = userEvent.setup();

      await user.click(await screen.findByRole("button", { name: "내가 아는 식당 상세 열기" }));
      let sheet = await screen.findByRole("dialog", { name: "장소 수정" });
      expect(within(sheet).getByText("나만의 장소")).toBeInTheDocument();
      expect(within(sheet).queryByRole("link", { name: "카카오맵에서 보기" })).not.toBeInTheDocument();
      expect(within(sheet).queryByText("주소")).not.toBeInTheDocument();
      expect(within(sheet).queryByText("좌표")).not.toBeInTheDocument();
      await user.click(within(sheet).getByRole("button", { name: "닫기" }));

      await user.click(screen.getByRole("button", { name: "링크 있는 곳 상세 열기" }));
      sheet = await screen.findByRole("dialog", { name: "장소 수정" });
      expect(within(sheet).getByRole("link", { name: "카카오맵에서 보기" })).toHaveAttribute("href", "https://place.map.kakao.com/555");
    } finally {
      getTripSpy.mockRestore();
    }
  });

  it("shows the name the user gave a public place on its card and in its sheet while the photo, address and category stay public", async () => {
    const address = "전남광주통합특별시 여수시 오동도로 222";
    const photoUrl = "https://tong.visitkorea.or.kr/cms/resource/23/3074123_image2_1.jpg";
    const trip: Trip = {
      ...getPreviewTrip(),
      id: "59",
      currentUserRole: "owner",
      days: {
        1: [
          {
            id: "1",
            time: "09:00",
            label: "내가 부르는 이름",
            meta: address,
            address,
            latitude: 34.7443,
            longitude: 127.7663,
            placeOrigin: "public",
            publicSource: "tourapi",
            publicSourceId: "126508",
            publicCategory: "sight",
            photoUrl,
            photoLicense: "Type1",
          },
        ],
      },
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/59?day=1");
      const user = userEvent.setup();
      // 서버가 label 에 사용자 이름을 내려 주므로 카드 · 이름 칸 · 사진 설명이 모두 그 이름이다
      await user.click(await screen.findByRole("button", { name: "내가 부르는 이름 상세 열기" }));

      const sheet = await screen.findByRole("dialog", { name: "장소 수정" });
      expect(sheet.querySelector('input[name="place-label"]')).toHaveValue("내가 부르는 이름");
      expect(within(sheet).getByRole("img", { name: "내가 부르는 이름 사진" })).toHaveAttribute("src", photoUrl);
      expect(within(sheet).getByText("사진: 한국관광공사")).toBeInTheDocument();
      expect(within(sheet).getByText("관광지")).toBeInTheDocument();
      expect(within(sheet).getByText(address)).toBeInTheDocument();
    } finally {
      getTripSpy.mockRestore();
    }
  });
```

 다. 추천 미리보기 시험. `describe` 닫는 `});` 바로 앞(마지막 시험 `does not delete existing places when full-save preview candidates fail` 뒤)에 더한다.

```tsx
  it("shows public recommendations with their photo and credit, files them by category, and saves them by reference", async () => {
    const photoUrl = "https://tong.visitkorea.or.kr/cms/resource/23/3074123_image2_1.jpg";
    const trip: Trip = { ...getPreviewTrip(), id: "130", revision: 6, title: "공공데이터 추천 여행", days: { 1: [], 2: [] } };
    const savedTrip: Trip = {
      ...trip,
      revision: 7,
      days: {
        1: [{ id: "new-1", time: "10:00", label: "오동도", meta: "관광지 · 전남광주통합특별시 여수시 오동도로 222", placeOrigin: "public", publicSource: "tourapi", publicSourceId: "126508" }],
        2: [],
      },
    };
    const recommendations: Recommendation[] = [
      {
        id: "public:tourapi:126508",
        title: "오동도",
        label: "📍",
        meta: "관광지 · 전남광주통합특별시 여수시 오동도로 222",
        reason: "일정 지역의 관광지",
        categoryGroup: "attraction",
        address: "전남광주통합특별시 여수시 오동도로 222",
        latitude: 34.7443,
        longitude: 127.7663,
        suggestedDay: 1,
        sourceType: "public_place",
        publicSource: "tourapi",
        publicSourceId: "126508",
        publicCategory: "sight",
        photoUrl,
        photoLicense: "Type3",
      },
      {
        id: "public:tourapi:2",
        title: "바다 카페",
        label: "📍",
        meta: "카페 · 관광로 12",
        reason: "일정 지역의 카페",
        categoryGroup: "cafe",
        address: "관광로 12",
        latitude: 34.74,
        longitude: 127.74,
        suggestedDay: 1,
        sourceType: "public_place",
        publicSource: "tourapi",
        publicSourceId: "2",
        publicCategory: "cafe",
      },
      {
        id: "public:sangga:3",
        title: "여수 횟집",
        label: "📍",
        meta: "음식점 · 여수시 중앙로 3",
        reason: "일정 지역의 음식점",
        categoryGroup: "food",
        address: "여수시 중앙로 3",
        latitude: 34.76,
        longitude: 127.66,
        suggestedDay: 1,
        sourceType: "public_place",
        publicSource: "sangga",
        publicSourceId: "3",
        publicCategory: "food",
      },
      {
        id: "public:tourapi:4",
        title: "여수 호텔",
        label: "📍",
        meta: "숙박 · 여수시 해안로 4",
        reason: "일정 지역의 숙박",
        categoryGroup: "stay",
        address: "여수시 해안로 4",
        latitude: 34.75,
        longitude: 127.7,
        suggestedDay: 1,
        sourceType: "public_place",
        publicSource: "tourapi",
        publicSourceId: "4",
        publicCategory: "stay",
      },
    ];
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const recommendationsSpy = vi.spyOn(appDataApi, "listRecommendations").mockResolvedValue(recommendations);
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockResolvedValue(savedTrip);

    try {
      await login();
      cleanup();
      renderAppRoute("/trips/130");
      const user = userEvent.setup();
      await user.click(await screen.findByRole("button", { name: /추천 일정만들기/ }));
      expect(await screen.findByText("저장 전 미리보기")).toBeInTheDocument();

      // 분류는 공공데이터 분류로 가른다 - 주소의 '관광로' 글자 때문에 카페가 관광지가 되지 않는다
      const previewOrder = screen
        .getAllByRole("button", { name: /지도에서 보기$/ })
        .map((button) => button.getAttribute("aria-label")?.replace(" 지도에서 보기", ""));
      expect(previewOrder).toEqual(["오동도", "여수 횟집", "바다 카페", "여수 호텔"]);
      const cafeCard = screen.getByRole("button", { name: "바다 카페 지도에서 보기" });
      expect(within(cafeCard).getByText("15:00")).toBeInTheDocument();
      expect(within(cafeCard).getByText("카페")).toHaveClass("preview-phase-label");
      expect(within(screen.getByRole("button", { name: "여수 횟집 지도에서 보기" })).getByText("점심")).toBeInTheDocument();
      expect(within(screen.getByRole("button", { name: "여수 호텔 지도에서 보기" })).getByText("숙소")).toBeInTheDocument();

      // 사진과 출처는 사진이 있는 추천에만
      const odongdoCard = screen.getByRole("button", { name: "오동도 지도에서 보기" });
      expect(odongdoCard.querySelector("img")).toHaveAttribute("src", photoUrl);
      expect(within(odongdoCard).getByText("사진: 한국관광공사 · 변경 금지")).toBeInTheDocument();
      expect(cafeCard.querySelector("img")).toBeNull();

      await user.click(screen.getByRole("button", { name: "오동도 후보 저장" }));
      await user.click(screen.getByRole("button", { name: "선택 저장" }));

      // 담는 요청에는 공공데이터 참조뿐이다 - 이름 · 주소 · 좌표 · 분류는 서버가 자기 표에서 채운다
      await waitFor(() => expect(addPlaceSpy).toHaveBeenCalledTimes(1));
      expect(addPlaceSpy).toHaveBeenCalledWith("130", 1, {
        time: "10:00",
        publicPlace: { source: "tourapi", sourceId: "126508" },
        expectedRevision: 6,
      });
    } finally {
      getTripSpy.mockRestore();
      recommendationsSpy.mockRestore();
      addPlaceSpy.mockRestore();
    }
  });

  it("matches an added place by its public source id before its name and time", () => {
    const previous = { ...getPreviewTrip(), days: { 1: [] } } as Trip;
    const next = {
      ...previous,
      days: {
        1: [
          { id: "a1", time: "10:00", label: "스타벅스 여수점", meta: "", publicSource: "tourapi", publicSourceId: "1" },
          { id: "a2", time: "10:00", label: "스타벅스 여수점", meta: "", publicSource: "sangga", publicSourceId: "2" },
        ],
      },
    } as Trip;

    // 이름 · 시간이 같아도 출처 ID 가 가른다
    expect(findAddedPlaceId(previous, next, 1, { time: "10:00", label: "스타벅스 여수점", publicSource: "sangga", publicSourceId: "2" }, new Set())).toBe("a2");
    // 공공데이터 참조가 없는 추천(나만의 장소로 담김)은 지금처럼 이름 · 시간으로
    expect(findAddedPlaceId(previous, next, 1, { time: "10:00", label: "스타벅스 여수점" }, new Set())).toBe("a1");
  });
```

 라. 추천을 담는 기존 시험의 단언을 새 요청 모양으로 바꾼다(찾을 줄 → 바꿀 줄). 참조가 없는 추천은 이름만 나만의 장소로 담긴다.

 - `shows unsaved recommendation preview cards in the timeline before save`
```tsx
      expect(addPlaceSpy).toHaveBeenCalledWith("102", 1, expect.objectContaining({ label: "성산일출봉", time: "10:00", meta: "관광명소", category: "관광명소", categoryCode: "AT4", expectedRevision: 4 }));
```
→
```tsx
      expect(addPlaceSpy).toHaveBeenCalledWith("102", 1, { time: "10:00", customPlace: { name: "성산일출봉" }, expectedRevision: 4 });
```
 - `adds an individual recommendation preview candidate while preserving existing places`
```tsx
      expect(addPlaceSpy).toHaveBeenCalledWith("104", 1, expect.objectContaining({ label: "오설록", expectedRevision: 10 }));
```
→
```tsx
      expect(addPlaceSpy).toHaveBeenCalledWith("104", 1, expect.objectContaining({ customPlace: { name: "오설록" }, expectedRevision: 10 }));
```
 - `saves all recommendation preview candidates without deleting existing places`
```tsx
      expect(addPlaceSpy).toHaveBeenCalledWith("105", 1, expect.objectContaining({ label: "새 추천", expectedRevision: 20 }));
```
→
```tsx
      expect(addPlaceSpy).toHaveBeenCalledWith("105", 1, expect.objectContaining({ customPlace: { name: "새 추천" }, expectedRevision: 20 }));
```
 - `refreshes on recommendation preview 409 and preserves hidden candidates for global retry`
```tsx
      expect(addPlaceSpy).toHaveBeenLastCalledWith("106", 1, expect.objectContaining({ label: "우도", time: "10:00", meta: "섬", expectedRevision: 31 }));
```
→
```tsx
      expect(addPlaceSpy).toHaveBeenLastCalledWith("106", 1, { time: "10:00", customPlace: { name: "우도" }, expectedRevision: 31 });
```
 - `does not retry transient recommendation preview save automatically and preserves hidden candidates for manual retry` (두 줄)
```tsx
      expect(addPlaceSpy).toHaveBeenNthCalledWith(1, "107", 1, expect.objectContaining({ label: "동백정원", time: "10:00", meta: "꽃", expectedRevision: 40 }));
      expect(addPlaceSpy).toHaveBeenNthCalledWith(2, "107", 1, expect.objectContaining({ label: "동백정원", time: "10:00", meta: "꽃", expectedRevision: 40 }));
```
→
```tsx
      expect(addPlaceSpy).toHaveBeenNthCalledWith(1, "107", 1, { time: "10:00", customPlace: { name: "동백정원" }, expectedRevision: 40 });
      expect(addPlaceSpy).toHaveBeenNthCalledWith(2, "107", 1, { time: "10:00", customPlace: { name: "동백정원" }, expectedRevision: 40 });
```
 - `keeps only unsaved recommendation preview candidates after a partial save failure` - 과제 7 이 이 시험을 컴파일되게 해 둔 모양(옛 `label` 을 읽도록 타입을 여는 줄과 안내 주석)에서 출발한다. 구현 흉내가 `label` 로 갈리므로 `customPlace.name` 으로 바꾸고 타입 여는 줄과 주석은 걷는다. 아래 셋을 바꾼다.
```tsx
    // 추천 담기는 아직 옛 모양(label)으로 보낸다 - 추천 부분 과제가 publicPlace 참조로 바꾸면 이 시험도 같이 바뀐다
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockImplementation(async (_tripId, _dayNumber, request) => {
      const payload = request as typeof request & { label?: string };
      if (payload.label === "오설록") return afterFirstSave;
      if (payload.label === "한라산") {
```
→
```tsx
    const addPlaceSpy = vi.spyOn(appDataApi, "addTripPlace").mockImplementation(async (_tripId, _dayNumber, payload) => {
      if (payload.customPlace?.name === "오설록") return afterFirstSave;
      if (payload.customPlace?.name === "한라산") {
```
```tsx
      throw new Error(`Unexpected place ${payload.label}`);
```
→
```tsx
      throw new Error(`Unexpected place ${payload.customPlace?.name}`);
```
```tsx
      expect(addPlaceSpy.mock.calls.map((call) => (call[2] as { label?: string }).label)).toEqual(["오설록", "한라산", "한라산"]);
      expect(addPlaceSpy).toHaveBeenLastCalledWith("108", 2, expect.objectContaining({ label: "한라산", expectedRevision: 51 }));
```
→
```tsx
      expect(addPlaceSpy.mock.calls.map((call) => call[2].customPlace?.name)).toEqual(["오설록", "한라산", "한라산"]);
      expect(addPlaceSpy).toHaveBeenLastCalledWith("108", 2, expect.objectContaining({ customPlace: { name: "한라산" }, expectedRevision: 51 }));
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd frontend && npx vitest run src/components/itinerary/placeDisplay.test.ts src/app/__tests__/trip-detail.test.tsx`
기대: FAIL.
- `placeDisplay.test.ts`: 파일을 못 읽는다(`Failed to resolve import "./placeDisplay"`).
- `trip-detail.test.tsx`: 13개(관찰한 값). `does not look up a coordinate-less custom place ...` 는 `expect(element).toBeInTheDocument()`(이름으로 지오코딩해 폴백 지도가 안 남는다), `draws a pin for a custom place only when the user picked a spot` 는 `expected [ …(3) ] to have a length of 1 but got 3`(찍지 않은 곳에도 핀), 공공데이터 상세 시험 둘(사진 + 출처, 이름을 고친 행)은 `Unable to find an accessible element with the role "img" and name "… 사진"`, 나만의 장소 상세는 `Unable to find an element with the text: 나만의 장소`, 추천 시험은 카페가 10:00 으로 묶여 순서가 어긋나고(`expected [ '오동도', '바다 카페', '여수 횟집', '여수 호텔' ] to deeply equal [ '오동도', '여수 횟집', '바다 카페', '여수 호텔' ]`) 사진이 없다, `matches an added place ...` 는 `findAddedPlaceId is not a function`, 바뀐 단언들은 `addTripPlace` 가 아직 `label · meta` 를 보내 어긋난다(`expected "addTripPlace" to be called with arguments: ...`).

- [ ] **3단계: 구현**

**(1) `frontend/src/components/itinerary/placeDisplay.ts`** - 새 파일.

```ts
import type { ItineraryPlace, TripPlaceAddItem } from "../../api";
import { PUBLIC_CATEGORY_LABEL } from "./placeAdd/publicPlaceText";

/* 일정 행 표시 규칙(카카오 운영정책 3단계). 우리가 담은 행(공공데이터 · 나만의 장소)은 place_origin 이 있고,
   없는 행이 예전 카카오 행이다 - 예전 행은 지금 그대로 보인다. */

/** 우리가 담은 행 - 공공데이터 장소 또는 나만의 장소 */
export function isOwnPlace(place: Pick<ItineraryPlace, "placeOrigin">): boolean {
  return place.placeOrigin === "public" || place.placeOrigin === "custom";
}

/** 지도가 이름 · 주소로 위치를 다시 찾을 말. 나만의 장소 · 확인 필요 행은 이름이 사용자 글(또는 안내 문구)이라 찾지 않는다 -
    좌표가 있는 행은 지도가 이 말을 보지 않으므로 '좌표 없는 행만 null' 과 같다. 공공데이터 행은 늘 좌표가 있다. 예전 행은 지금 그대로 */
export function markerQueryOf(place: Pick<ItineraryPlace, "placeOrigin" | "address" | "label">): string | null {
  if (place.placeOrigin === "custom" || place.placeOrigin === "needs_review") return null;
  return place.address || place.label;
}

/** 상세 시트 윗줄의 분류 글자 */
export function placeCategoryText(
  place: Pick<ItineraryPlace, "placeOrigin" | "publicCategory" | "category" | "categoryCode">,
): string {
  if (place.placeOrigin === "public" && place.publicCategory) return PUBLIC_CATEGORY_LABEL[place.publicCategory];
  if (place.placeOrigin === "custom") return "나만의 장소";
  return place.category || place.categoryCode || "장소";
}

type PreviewSource = Pick<
  ItineraryPlace,
  "time" | "label" | "publicSource" | "publicSourceId" | "sourceProvider" | "externalPlaceId"
>;

/** 추천 미리보기 한 곳을 일정에 담는 요청(expectedRevision 은 부르는 쪽이 더한다).
    공공데이터 추천은 참조만, 그 밖(저장 요약)은 이름만 나만의 장소로 보낸다 - 추천이 들고 있던 주소 · 좌표 · 분류는 옮기지 않는다.
    숫자인 카카오 장소 ID 는 '카카오맵에서 보기' 링크용으로 남긴다 */
export function previewAddItem(place: PreviewSource): TripPlaceAddItem {
  const time = place.time ?? "";
  const external = place.externalPlaceId ?? "";
  const kakao = place.sourceProvider?.startsWith("kakao") && /^\d{1,20}$/.test(external) ? { kakaoPlaceId: external } : {};
  if (place.publicSource && place.publicSourceId) {
    return { time, publicPlace: { source: place.publicSource, sourceId: place.publicSourceId }, ...kakao };
  }
  return { time, customPlace: { name: place.label }, ...kakao };
}
```

**(2) `PlacePhoto`** - 과제 9 가 만들었다(가져다 쓰기만 한다).

**(3) `frontend/src/api/types.ts`** - 과제 7 이 `RecommendationCategoryGroup` 에 `"cafe"` 를 이미 더했다(확인만 한다).

**(4) `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`** - 아래 가~더 순서로 고친다(찾을 글은 과제 9 까지 적용한 파일 기준이다).

 가. 가져오기. 과제 10 의 `LegacyPlaceConfirm` 가져오기 줄 다음에 더한다.

```ts
import { PlacePhoto } from "../../components/itinerary/PlacePhoto";
import { isOwnPlace, markerQueryOf, placeCategoryText, previewAddItem } from "../../components/itinerary/placeDisplay";
import { publicTimeSlotGroup } from "../../components/itinerary/placeAdd/publicPlaceText";
```
그리고 `../../api` 가져오기에 `PublicPlaceCategory` 를 더한다.

```ts
  type PlaceSearchCandidate,
  type Recommendation,
```
→
```ts
  type PlaceSearchCandidate,
  type PublicPlaceCategory,
  type Recommendation,
```

 나. 미리보기 한 곳의 타입에 공공데이터 칸을 더한다. 첫 줄만 바꾼다.

```ts
type PreviewPlace = {
  previewId: string;
```
→
```ts
type PreviewPlace = Pick<
  ItineraryPlace,
  "publicSource" | "publicSourceId" | "publicCategory" | "photoUrl" | "photoLicense"
> & {
  previewId: string;
```

 다. `recommendationPlaceDescription` - 공공데이터 추천은 서버가 만든 `meta`('분류 · 주소')를 그대로 쓴다.

```ts
function recommendationPlaceDescription(item: Recommendation): string {
  const parts = [item.categoryName, item.address].filter(
```
→
```ts
function recommendationPlaceDescription(item: Recommendation): string {
  if (item.publicSource) return item.meta || item.address || "장소 정보 확인";
  const parts = [item.categoryName, item.address].filter(
```

 라. `recommendationPlacePayload`(과제 9 가 반환형을 걷고 안내 주석을 단 모양)를 통째로 아래로 바꾼다 - 이제 담는 요청이 아니라 미리보기 칸만 채운다(담는 요청은 `previewAddItem`).

```ts
/* 추천 미리보기 부분 과제(3단계)가 publicPlace 참조로 바꾼다 - 그때까지 옛 값 묶음을 그대로 돌려준다 */
function recommendationPlacePayload(
  item: Recommendation,
  time: string | undefined,
) {
  return {
    time: time ?? "",
    label: item.title,
    meta: recommendationPlaceDescription(item),
    address: item.address ?? null,
    latitude: item.latitude ?? null,
    longitude: item.longitude ?? null,
    category: item.categoryName ?? item.categoryGroup ?? null,
    categoryCode: item.categoryCode ?? null,
    placeUrl: item.placeUrl ?? null,
    sourceProvider: item.sourceProvider ?? null,
    externalPlaceId: item.externalPlaceId ?? null,
  };
}
```
→
```ts
/* 화면에 그리기 위한 칸만 - 일정에 담는 요청은 previewAddItem 이 공공데이터 참조(또는 이름)로만 만든다 */
function recommendationPreviewFields(
  item: Recommendation,
  time: string | undefined,
): Omit<PreviewPlace, "previewId" | "dayNumber"> {
  return {
    time: time ?? "",
    label: item.title,
    meta: recommendationPlaceDescription(item),
    address: item.address ?? null,
    latitude: item.latitude ?? null,
    longitude: item.longitude ?? null,
    category: item.categoryName ?? item.categoryGroup ?? null,
    categoryCode: item.categoryCode ?? null,
    placeUrl: item.placeUrl ?? null,
    sourceProvider: item.sourceProvider ?? null,
    externalPlaceId: item.externalPlaceId ?? null,
    publicSource: item.publicSource ?? null,
    publicSourceId: item.publicSourceId ?? null,
    publicCategory: item.publicCategory ?? null,
    photoUrl: item.photoUrl ?? null,
    photoLicense: item.photoLicense ?? null,
  };
}
```

 마. 시간대 분류. `recommendationTimeBucketFromFields` 머리를 바꾼다 - 공공데이터 분류가 있으면 그것으로(주소의 '관광로' 같은 글자로 짐작하지 않는다), 카페 묶음도 분류 묶음(`categoryGroup`)으로 받는다.

```ts
function recommendationTimeBucketFromFields(fields: {
  category?: string | null;
  categoryCode?: string | null;
  categoryGroup?: string | null;
  label?: string | null;
  meta?: string | null;
  reason?: string | null;
}): RecommendationTimeBucket {
  const categoryCode = fields.categoryCode?.toUpperCase();
  if (categoryCode === "FD6") return "food";
  if (categoryCode === "CE7") return "cafe";
  if (categoryCode === "AD5") return "stay";
  if (fields.categoryGroup === "food") return "food";
  if (fields.categoryGroup === "stay") return "stay";
```
→
```ts
function recommendationTimeBucketFromFields(fields: {
  category?: string | null;
  categoryCode?: string | null;
  categoryGroup?: string | null;
  publicCategory?: PublicPlaceCategory | null;
  label?: string | null;
  meta?: string | null;
  reason?: string | null;
}): RecommendationTimeBucket {
  if (fields.publicCategory) return publicTimeSlotGroup(fields.publicCategory);
  const categoryCode = fields.categoryCode?.toUpperCase();
  if (categoryCode === "FD6") return "food";
  if (categoryCode === "CE7") return "cafe";
  if (categoryCode === "AD5") return "stay";
  if (fields.categoryGroup === "food") return "food";
  if (fields.categoryGroup === "cafe") return "cafe";
  if (fields.categoryGroup === "stay") return "stay";
```

 바. `recommendationTimeBucket(item)` 가 공공데이터 분류를 넘긴다.

```ts
    categoryGroup: item.categoryGroup,
    label: item.title,
```
→
```ts
    categoryGroup: item.categoryGroup,
    publicCategory: item.publicCategory,
    label: item.title,
```

 사. 미리보기 정렬 칸에 공공데이터 분류를 더한다.

```ts
type RecommendationPreviewOrderFields = Pick<
  PreviewPlace,
  "category" | "categoryCode" | "label" | "meta" | "time"
>;
```
→
```ts
type RecommendationPreviewOrderFields = Pick<
  PreviewPlace,
  "category" | "categoryCode" | "label" | "meta" | "time" | "publicCategory"
>;
```

 아. `previewPlacesFromRecommendations` 의 만들기 부분.

```ts
    const payload = recommendationPlacePayload(
      item,
      recommendationPlaceTime(item, offset),
    );
    return {
      previewId: recommendationPreviewId(item, index),
      dayNumber,
      time: payload.time,
      label: payload.label,
      meta: payload.meta,
      address: payload.address,
      latitude: payload.latitude,
      longitude: payload.longitude,
      category: payload.category,
      categoryCode: payload.categoryCode,
      placeUrl: payload.placeUrl,
      sourceProvider: payload.sourceProvider,
      externalPlaceId: payload.externalPlaceId,
    };
  });
  return sortRecommendationPreviewPlaces(places);
```
→
```ts
    return {
      previewId: recommendationPreviewId(item, index),
      dayNumber,
      ...recommendationPreviewFields(item, recommendationPlaceTime(item, offset)),
    };
  });
  return sortRecommendationPreviewPlaces(places);
```

 자. `timelinePlaceFromPreviewPlace` 가 공공데이터 칸을 옮긴다.

```ts
    externalPlaceId: place.externalPlaceId,
    isRecommendationPreview: true,
```
→
```ts
    externalPlaceId: place.externalPlaceId,
    publicSource: place.publicSource,
    publicSourceId: place.publicSourceId,
    publicCategory: place.publicCategory,
    photoUrl: place.photoUrl,
    photoLicense: place.photoLicense,
    isRecommendationPreview: true,
```

 차. `tripPlaceMutationFromDisplayedPlace`(과제 9 가 반환형을 걷고 안내 주석 두 줄을 단 모양)를 주석까지 통째로 지운다(`function tripPlaceMutationFromDisplayedPlace(` 부터 닫는 `}` 까지). 바로 뒤의 `findAddedPlaceId` 는 아래로 바꾼다 - 공공데이터 출처 ID 로 먼저 짝짓는다. 시험이 직접 부르도록 export 한다.

```ts
function findAddedPlaceId(
  previousTrip: Trip,
  nextTrip: Trip,
  dayNumber: number,
  place: DisplayedPlace,
  usedPlaceIds: Set<string>,
): string | null {
  const previousIds = new Set(
    (previousTrip.days[dayNumber] ?? []).map((item) => item.id).filter(Boolean),
  );
  const candidates = (nextTrip.days[dayNumber] ?? []).filter(
    (item) =>
      item.id && !previousIds.has(item.id) && !usedPlaceIds.has(item.id),
  );
  const exact = candidates.find(
    (item) =>
      item.externalPlaceId && item.externalPlaceId === place.externalPlaceId,
  );
```
→
```ts
export function findAddedPlaceId(
  previousTrip: Trip,
  nextTrip: Trip,
  dayNumber: number,
  place: Pick<DisplayedPlace, "label" | "time" | "externalPlaceId" | "publicSource" | "publicSourceId">,
  usedPlaceIds: Set<string>,
): string | null {
  const previousIds = new Set(
    (previousTrip.days[dayNumber] ?? []).map((item) => item.id).filter(Boolean),
  );
  const candidates = (nextTrip.days[dayNumber] ?? []).filter(
    (item) =>
      item.id && !previousIds.has(item.id) && !usedPlaceIds.has(item.id),
  );
  // 공공데이터 추천은 출처 ID 가 가장 확실하다 - 같은 이름의 다른 장소(체인점)와 헷갈리지 않는다
  const samePublic =
    place.publicSource && place.publicSourceId
      ? candidates.find(
          (item) =>
            item.publicSource === place.publicSource &&
            item.publicSourceId === place.publicSourceId,
        )
      : undefined;
  const exact =
    samePublic ??
    candidates.find(
      (item) =>
        item.externalPlaceId && item.externalPlaceId === place.externalPlaceId,
    );
```
(함수 나머지 `const matched = exact ?? ...` 부터는 그대로다.)

 카. 추천 미리보기 저장 요청.

```ts
        currentTrip = await appDataApi.addTripPlace(
          currentTrip.id,
          dayNumber,
          tripPlaceMutationFromDisplayedPlace(place, currentTrip.revision),
        );
```
→
```ts
        currentTrip = await appDataApi.addTripPlace(currentTrip.id, dayNumber, {
          ...previewAddItem(place),
          expectedRevision: currentTrip.revision,
        });
```

 타. 지도 마커 질의(`PrototypeTripMap`).

```ts
    query: place.address || place.label,
```
→
```ts
    query: markerQueryOf(place),
```

 파. 상세 시트(`PlaceSheetDetail`)를 통째로 아래로 바꾼다. 예전 행은 그대로 보이고, 우리가 담은 행은 사진 + 출처 · 분류 글자를 보이며 주소 · 링크는 값이 있을 때만 보인다.

```tsx
function PlaceSheetDetail({ place }: { place: ItineraryPlace }) {
  const addressText = place.address || "주소 정보 없음";
  const categoryText = place.category || place.categoryCode || "장소";
  const coordinateText =
    Number.isFinite(place.latitude) && Number.isFinite(place.longitude)
      ? `${place.latitude}, ${place.longitude}`
      : "좌표 정보 없음";
  const kakaoPlaceUrl =
    place.placeUrl ||
    `https://map.kakao.com/link/search/${encodeURIComponent(place.address || place.label)}`;
  return (
    <div className="place-sheet-detail">
      <div className="place-detail-summary" aria-label="장소 요약">
        <span>{categoryText}</span>
        {place.time && <span>{place.time}</span>}
      </div>
      <div className="place-detail-fields">
        <section>
          <strong>주소</strong>
          <p>{addressText}</p>
        </section>
        <section>
          <strong>좌표</strong>
          <p>{coordinateText}</p>
        </section>
      </div>
      <a className="btn sm line" href={kakaoPlaceUrl} rel="noreferrer" target="_blank">
        카카오맵에서 보기
      </a>
    </div>
  );
}
```
→
```tsx
function PlaceSheetDetail({ place }: { place: ItineraryPlace }) {
  // 우리가 담은 행(공공데이터 · 나만의 장소)과 예전 행(place_origin 없음)을 가른다 - 예전 행은 지금 그대로
  const isOwn = isOwnPlace(place);
  const categoryText = placeCategoryText(place);
  const coordinateText =
    Number.isFinite(place.latitude) && Number.isFinite(place.longitude)
      ? `${place.latitude}, ${place.longitude}`
      : "좌표 정보 없음";
  // 우리가 담은 행은 저장된 카카오 place_url 이 있을 때만 링크한다. 예전 행은 주소 · 이름 검색 링크까지
  const kakaoPlaceUrl =
    place.placeUrl ||
    (isOwn ? null : `https://map.kakao.com/link/search/${encodeURIComponent(place.address || place.label)}`);
  const showAddress = Boolean(place.address) || !isOwn;
  return (
    <div className="place-sheet-detail">
      {place.placeOrigin === "public" && (
        <PlacePhoto alt={`${place.label} 사진`} license={place.photoLicense} url={place.photoUrl} />
      )}
      <div className="place-detail-summary" aria-label="장소 요약">
        <span>{categoryText}</span>
        {place.time && <span>{place.time}</span>}
      </div>
      {showAddress && (
        <div className="place-detail-fields">
          <section>
            <strong>주소</strong>
            <p>{place.address || "주소 정보 없음"}</p>
          </section>
          {!isOwn && (
            <section>
              <strong>좌표</strong>
              <p>{coordinateText}</p>
            </section>
          )}
        </div>
      )}
      {kakaoPlaceUrl && (
        <a className="btn sm line" href={kakaoPlaceUrl} rel="noreferrer" target="_blank">
          카카오맵에서 보기
        </a>
      )}
    </div>
  );
}
```

 더. 추천 미리보기 카드에 사진 + 출처. `SortablePlaceItem` 의 추천 미리보기 갈래(`recommendation-preview-place-select` 단추 안) 끝에서만 나오는 아래 줄에 더한다.

```tsx
            <h4>{place.label}</h4>
            <div className="meta">{place.meta}</div>
          </button>
```
→
```tsx
            <h4>{place.label}</h4>
            <div className="meta">{place.meta}</div>
            <PlacePhoto alt={`${place.label} 사진`} compact license={place.photoLicense} url={place.photoUrl} />
          </button>
```

**(5) `frontend/src/styles/app.css`** - 더할 것이 없다. 사진 CSS(`place-photo` · `place-photo-credit` · `place-photo--compact`)는 과제 9 가 넣었다.

- [ ] **4단계: 통과하는지 확인**

실행: `cd frontend && npx vitest run src/components/itinerary/placeDisplay.test.ts src/app/__tests__/trip-detail.test.tsx`
기대: PASS - 2개 파일, 시험 143개(관찰한 값. 과제 9 가 같은 파일의 추가 창 시험을 맞춘 상태여야 한다).
실행: `cd frontend && npx tsc --noEmit -p .`
기대: 타입 오류 없음.

---

### Task 12: 넘김 · 홈 '일정에 담기'

**파일:**
- 고치기: `frontend/src/utils/placeHandoff.ts`, `frontend/src/utils/placeHandoff.test.ts`(둘 다 파일 전체를 바꾼다 - 과제 9 가 `tripPlaceFromSearchItem` 만 먼저 지워 둔 파일이다)
- 고치기: `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`, `frontend/src/pages/itinerary/ItineraryCreatePage.tsx`
- 고치기: `frontend/src/components/HomeSearch.tsx`, `frontend/src/styles/home.css`
- 고치기: `frontend/src/app/__tests__/home.test.tsx`, `frontend/src/app/__tests__/trip-detail.test.tsx`, `frontend/src/app/__tests__/trip-create.test.tsx`
- 고치기: `frontend/e2e-backend/backend-mode.spec.ts`, `frontend/e2e-backend/itinerary-cross-day-drag.spec.ts`(과제 9 가 같은 시드를 이미 고쳤으면 확인만 한다)

**인터페이스:**
- 받는 것: `usePlaceById(id, query): { place: PlaceSearchItem | null; missing: boolean }`(1단계 `components/map/placeMemory.ts`), 과제 8 의 `kakaoPlaceIdOf(candidate)` · `type PlacePickInput`(`components/itinerary/placeAdd/usePlaceMatch.ts`), 상세 페이지의 `openAddPlace(initial?: PlacePickInput)`(과제 9 - 안에서 맞춰 보기를 시작한다), `appDataApi.matchPlace` · `listTrips`.
- 내놓는 것: `placeHandoff.ts` 의 `AddPlaceHandoff = { kakaoPlaceId: string; query: string }`, `readAddPlaceParam(search: string | URLSearchParams)`, `writeAddPlaceParam(params, handoff)`(주어진 `URLSearchParams` 에 `addPlace=kakao:{id}` 와 `q` 만 쓰고 그대로 돌려준다), `pickInputFromItem(item)`(메모리의 카카오 장소 → `openAddPlace`/`pick` 이 읽는 `PlacePickInput`), `pickInputFromKakaoId(id)`(못 찾았을 때 좌표 없는 입력 - `pick` 이 바로 나만의 장소 칸으로 보낸다). 옛 `readPlaceParam` · `writePlaceParam` 은 없앤다.
- 지켜야 할 것: 홈 → 새 일정 만들기 주소(`/trips/new?...`)에도 키는 `addPlace` 와 `q` 둘뿐이다. 지역(`sido` · `region`)을 싣지 않는다 - 시도도 카카오 주소에서 나온 값이다(코덱스 검토 · 사용자 결정). 일정 만들기가 지역 고르기로 열리고 사용자가 직접 고른다. 시험이 이를 둘로 지킨다: 홈 시험이 `TripPicker` 가 만든 링크의 키가 정확히 `["addPlace", "q"]` 인지, 일정 만들기 시험이 `region` 없는 주소에서 사용자가 지역을 눌러 고르고 만든 뒤 일정 화면 주소에도 그 둘뿐인지 본다.

- [ ] **1단계: 실패하는 시험 쓰기**

**(1) `frontend/src/utils/placeHandoff.test.ts`** - 파일 전체를 아래로 바꾼다.

```ts
import { describe, expect, it } from "vitest";
import type { PlaceSearchItem } from "../api";
import { pickInputFromItem, pickInputFromKakaoId, readAddPlaceParam, writeAddPlaceParam } from "./placeHandoff";

const odongdo: PlaceSearchItem = {
  kind: "place",
  id: "kakao:8193468",
  name: "오동도",
  category: "여행 > 관광,명소 > 섬(내륙)",
  categoryCode: "AT4",
  address: "전남광주통합특별시 여수시 수정동 1-1",
  latitude: 34.744,
  longitude: 127.766,
  placeUrl: "http://place.map.kakao.com/8193468",
  sido: "전남",
  city: "여수",
};

describe("일정으로 넘기는 장소 - 주소에는 카카오 장소 ID 와 친 말만", () => {
  it("writes only the Kakao id and the typed words", () => {
    const params = writeAddPlaceParam(new URLSearchParams(), { kakaoPlaceId: "8193468", query: " 오동도 " });

    expect(params.get("addPlace")).toBe("kakao:8193468");
    expect(params.get("q")).toBe("오동도");
    expect([...params.keys()].sort()).toEqual(["addPlace", "q"]);
  });

  it("leaves other params alone and writes no q when nothing was typed", () => {
    const params = writeAddPlaceParam(new URLSearchParams({ day: "2" }), { kakaoPlaceId: "8193468", query: "  " });

    expect(params.get("day")).toBe("2");
    expect(params.has("q")).toBe(false);
  });

  it("reads what it wrote, from a search string or from URLSearchParams", () => {
    const params = writeAddPlaceParam(new URLSearchParams(), { kakaoPlaceId: "8193468", query: "오동도" });

    expect(readAddPlaceParam(params)).toEqual({ kakaoPlaceId: "8193468", query: "오동도" });
    expect(readAddPlaceParam(`?${params.toString()}`)).toEqual({ kakaoPlaceId: "8193468", query: "오동도" });
  });

  it("drops anything that is not a numeric Kakao id", () => {
    expect(readAddPlaceParam("")).toBeNull();
    expect(readAddPlaceParam("addPlace=kakao:abc")).toBeNull();
    expect(readAddPlaceParam("addPlace=area:4613010100")).toBeNull();
    expect(readAddPlaceParam(`addPlace=kakao:${"1".repeat(21)}`)).toBeNull();
    // 예전 형식(장소 값을 통째로 실은 JSON)은 받지 않는다
    expect(readAddPlaceParam(new URLSearchParams({ addPlace: JSON.stringify({ kind: "place", id: "kakao:8193468", name: "오동도" }) }))).toBeNull();
  });

  it("treats a missing q as empty and caps the typed words", () => {
    expect(readAddPlaceParam("addPlace=kakao:8193468")).toEqual({ kakaoPlaceId: "8193468", query: "" });
    expect(readAddPlaceParam(new URLSearchParams({ addPlace: "kakao:8193468", q: "가".repeat(300) }))?.query).toHaveLength(100);
  });

  it("hands the picked place to the match step as just the five values it reads, in memory only", () => {
    expect(pickInputFromItem(odongdo)).toEqual({
      id: "kakao:8193468",
      title: "오동도",
      latitude: 34.744,
      longitude: 127.766,
      categoryCode: "AT4",
    });
  });

  it("falls back to an input without coordinates that keeps only the Kakao id", () => {
    expect(pickInputFromKakaoId("8193468")).toEqual({ id: "kakao:8193468", title: "" });
  });
});
```

**(2) `frontend/src/app/__tests__/trip-create.test.tsx`**

 가. 맨 위 `import { login, renderAppRoute } from "../../test/renderAppRoute";` 를 `import { login, renderAppRoute, routeLocation } from "../../test/renderAppRoute";` 로 바꾼다.

 나. `describe` 닫는 `});` 바로 앞(마지막 시험 뒤)에 더한다.

```tsx
  it("lets the user pick the region of a new trip that carries a place from the home search, and hands only the Kakao id and typed words on", async () => {
    await login();
    cleanup();
    const travelAreasSpy = vi
      .spyOn(appDataApi, "listTravelAreaRecommendations")
      .mockResolvedValue(getBusanTravelAreaResponse());
    const createdTrip: Trip = {
      ...getPreviewTrip(),
      id: "46",
      title: "부산 추천 여행",
      dates: "2026.06.15 - 06.17",
      days: { 1: [], 2: [], 3: [] },
    };
    const createTripSpy = vi.spyOn(appDataApi, "createTrip").mockResolvedValue(createdTrip);
    // 일정 화면은 열지 않는다 - 만든 뒤 넘긴 주소만 본다
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockReturnValue(new Promise<Trip>(() => undefined));

    try {
      // 홈이 만든 주소 그대로다: 지역(region · sido)은 카카오 주소에서 나온 값이라 싣지 않는다
      renderAppRoute(`/trips/new?${new URLSearchParams({ addPlace: "kakao:8193468", q: "오동도" })}`);
      const user = userEvent.setup();
      // 주소에는 이름이 없다 - 배너도 이름 없이 알린다
      expect(await screen.findByText("만들고 나면 고른 장소를 담을 날을 골라요")).toBeInTheDocument();
      // 지역은 여기서 고른다
      await user.click(screen.getByRole("button", { name: "부산" }));
      await waitFor(() => expect(screen.getByRole("button", { name: /부산 전체/ })).toHaveAttribute("aria-pressed", "true"));
      const nextButton = screen.getByRole("button", { name: "다음" });
      await waitFor(() => expect(nextButton).toBeEnabled());
      await user.click(nextButton);
      const titleInput = screen.getByRole("textbox", { name: "일정 제목" });
      await user.clear(titleInput);
      await user.type(titleInput, "부산 추천 여행");
      await user.click(screen.getByRole("button", { name: "일정 생성" }));

      await waitFor(() => expect(createTripSpy).toHaveBeenCalledWith(expect.objectContaining({ region: "부산 전체", travelAreaId: "busan-all" })));
      await waitFor(() => expect(routeLocation().pathname).toBe("/trips/46"));
      const params = new URLSearchParams(routeLocation().search);
      expect(params.get("addPlace")).toBe("kakao:8193468");
      expect(params.get("q")).toBe("오동도");
      expect([...params.keys()].sort()).toEqual(["addPlace", "q"]);
    } finally {
      createTripSpy.mockRestore();
      getTripSpy.mockRestore();
      travelAreasSpy.mockRestore();
    }
  });
```

**(3) `frontend/src/app/__tests__/trip-detail.test.tsx`** - 과제 9 가 이 홈 넘김 시험을 이미 맞춘 모양(`matchPlaceSpy` 로 맞춰 보기를 가리고 `writePlaceParam(odongdo)` 로 주소를 만든다)에서 출발한다.

 가. 가져오기. 과제 9 가 남긴 아래 한 줄을 바꾼다.

```tsx
import { writePlaceParam } from "../../utils/placeHandoff";
```
→
```tsx
import { rememberPlaces } from "../../components/map/placeMemory";
import { writeAddPlaceParam } from "../../utils/placeHandoff";
```

 나. 같은 시험 `opens the add sheet with a place handed over from the home search and saves it on the picked day` 에서 주소 만들기 한 줄을 바꾼다 - 주소에는 카카오 장소 ID 와 친 말뿐이고, 장소는 화면 메모리에 있다(홈에서 막 본 장소).

```tsx
      renderAppRoute(`/trips/128?${new URLSearchParams({ addPlace: writePlaceParam(odongdo) })}`);
```
→
```tsx
      rememberPlaces([odongdo]);
      renderAppRoute(`/trips/128?${writeAddPlaceParam(new URLSearchParams(), { kakaoPlaceId: "8193468", query: "오동도" })}`);
```
그리고 같은 시험에서 주소의 넘김을 지웠는지 보는 줄 바로 다음에 `q` 도 지웠는지, 저장 요청에 카카오 값이 없는지 본다.

```tsx
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).get("addPlace")).toBeNull());
```
→
```tsx
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).get("addPlace")).toBeNull());
      expect(new URLSearchParams(routeLocation().search).has("q")).toBe(false);
```
```tsx
      expect(addPlacesSpy).toHaveBeenCalledWith("128", 2, {
        expectedRevision: 3,
        places: [{ publicPlace: { source: "tourapi", sourceId: "126508" }, kakaoPlaceId: "8193468" }],
      });
```
→
```tsx
      expect(addPlacesSpy).toHaveBeenCalledWith("128", 2, {
        expectedRevision: 3,
        places: [{ publicPlace: { source: "tourapi", sourceId: "126508" }, kakaoPlaceId: "8193468" }],
      });
      // 카카오 이름 · 주소 · 좌표 · 분류는 요청 어디에도 없다
      expect(JSON.stringify(addPlacesSpy.mock.calls[0][2])).not.toMatch(/수정동|34\.745|127\.766|AT4|관광,명소/);
```

 다. 그 시험이 끝나는 `});` 바로 뒤에 시험 셋을 더한다.

```tsx
  it("asks Kakao again with the same words when the handed-over place is no longer in memory", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "128", revision: 3, days: { 1: [], 2: [] }, currentUserRole: "owner" };
    const odongdo: PlaceSearchItem = {
      kind: "place",
      id: "kakao:8193468",
      name: "오동도",
      category: "여행 > 관광,명소 > 섬",
      categoryCode: "AT4",
      address: "전남광주통합특별시 여수시 수정동 1-1",
      latitude: 34.745,
      longitude: 127.766,
      placeUrl: "http://place.map.kakao.com/8193468",
      sido: "전남",
      city: "여수",
    };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const searchSpy = vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([odongdo]);
    const matchSpy = vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "match", places: [publicPlaceFor("오동도", "126508")] });
    try {
      await login();
      cleanup();
      renderAppRoute(`/trips/128?${writeAddPlaceParam(new URLSearchParams(), { kakaoPlaceId: "8193468", query: "오동도" })}`);

      const sheet = await screen.findByRole("dialog", { name: "장소 추가" });
      expect(searchSpy).toHaveBeenCalledWith("오동도", expect.anything());
      await waitFor(() => expect(matchSpy).toHaveBeenCalledTimes(1));
      expect(await within(sheet).findByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("오동도");
    } finally {
      getTripSpy.mockRestore();
      searchSpy.mockRestore();
      matchSpy.mockRestore();
    }
  });

  it("goes to the custom-place step with only the Kakao id when the handed-over place cannot be found again", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "128", revision: 3, days: { 1: [], 2: [] }, currentUserRole: "owner" };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const searchSpy = vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([]);
    const matchSpy = vi.spyOn(appDataApi, "matchPlace");
    const addPlacesSpy = vi.spyOn(appDataApi, "addTripPlaces").mockResolvedValue({ ...trip, revision: 4 });
    try {
      await login();
      cleanup();
      renderAppRoute(`/trips/128?${writeAddPlaceParam(new URLSearchParams(), { kakaoPlaceId: "8193468", query: "오동도" })}`);
      const user = userEvent.setup();

      const sheet = await screen.findByRole("dialog", { name: "장소 추가" });
      await waitFor(() => expect(searchSpy).toHaveBeenCalled());
      // 맞춰 볼 이름 · 좌표가 없다 - 바로 나만의 장소 칸(빈 이름 칸)이다
      const form = await within(sheet).findByRole("form", { name: "나만의 장소" });
      expect(within(form).getByLabelText("장소 이름")).toHaveValue("");
      expect(matchSpy).not.toHaveBeenCalled();
      // 카카오 장소 ID 는 남는다 - '카카오맵에서 보기' 링크용
      await user.type(within(form).getByLabelText("장소 이름"), "오동도 앞 매점");
      await user.click(within(form).getByRole("button", { name: "담기" }));
      await user.click(await within(sheet).findByRole("button", { name: "Day 1에 1개 저장하기" }));
      await waitFor(() =>
        expect(addPlacesSpy).toHaveBeenCalledWith("128", 1, {
          expectedRevision: 3,
          places: [{ customPlace: { name: "오동도 앞 매점" }, kakaoPlaceId: "8193468" }],
        }),
      );
    } finally {
      getTripSpy.mockRestore();
      searchSpy.mockRestore();
      matchSpy.mockRestore();
      addPlacesSpy.mockRestore();
    }
  });

  it("only tells a viewer that editing needs permission when a place is handed over", async () => {
    const trip: Trip = { ...getPreviewTrip(), id: "128", revision: 3, days: { 1: [], 2: [] }, currentUserRole: "viewer" };
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(trip);
    const matchSpy = vi.spyOn(appDataApi, "matchPlace");
    try {
      await login();
      cleanup();
      rememberPlaces([
        {
          kind: "place",
          id: "kakao:8193468",
          name: "오동도",
          categoryCode: "AT4",
          latitude: 34.745,
          longitude: 127.766,
        },
      ]);
      renderAppRoute(`/trips/128?${writeAddPlaceParam(new URLSearchParams(), { kakaoPlaceId: "8193468", query: "오동도" })}`);

      expect(await screen.findByText(/편집 권한이 필요해요/)).toBeInTheDocument();
      expect(screen.queryByRole("dialog", { name: "장소 추가" })).not.toBeInTheDocument();
      await waitFor(() => expect(new URLSearchParams(routeLocation().search).has("addPlace")).toBe(false));
      expect(matchSpy).not.toHaveBeenCalled();
    } finally {
      getTripSpy.mockRestore();
      matchSpy.mockRestore();
    }
  });
```

**(4) `frontend/src/app/__tests__/home.test.tsx`**

 가. 가져오기 목록에 `type PublicPlaceItem,` 를 `type Policy,` 다음 줄에 더한다.

 나. `searches places from the home search bar and opens a place card by its Kakao id, with no trip hand-off yet` 시험을 고친다.
 - 제목: `"searches places from the home search bar and opens a place card by its Kakao id, with no trip hand-off yet"` → `"searches places from the home search bar, opens a place card by its Kakao id and hands the place to a trip by id and typed words only"`.
 - 이 시험 안의 `const searchPlacesSpy = vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([odongdo]);` 줄 바로 다음에 더한다.

```tsx
    const publicOdongdo: PublicPlaceItem = {
      source: "tourapi",
      sourceId: "126508",
      name: "오동도",
      address: "전남광주통합특별시 여수시 오동도로 222",
      latitude: 34.7443,
      longitude: 127.7663,
      category: "sight",
      sido: "전남",
      city: "여수",
      distanceMeters: 0,
    };
    const upcoming = (id: string, title: string, role: Trip["currentUserRole"], from: number): Trip => ({
      ...getPreviewTrip(),
      id,
      title,
      startDate: testIsoDateFromToday(from),
      endDate: testIsoDateFromToday(from + 2),
      days: { 1: [], 2: [], 3: [] },
      currentUserRole: role,
    });
    const listTripsSpy = vi.spyOn(appDataApi, "listTrips").mockResolvedValue([
      upcoming("301", "여수 여행", "owner", 10),
      upcoming("302", "지난 여행", "owner", -30),
      upcoming("303", "보기만 하는 여행", "viewer", 10),
    ]);
    const getTripSpy = vi.spyOn(appDataApi, "getTrip").mockResolvedValue(upcoming("301", "여수 여행", "owner", 10));
    const matchSpy = vi.spyOn(appDataApi, "matchPlace").mockResolvedValue({ result: "match", places: [publicOdongdo] });
```
 - '일정에 담기' 가 없다는 두 줄을 바꾼다.
```tsx
      // 카카오 장소값을 일정에 저장하지 않게 될 때(3단계)까지 '일정에 담기'는 없다
      expect(within(card).queryByRole("button", { name: "일정에 담기" })).toBeNull();
```
→
```tsx
      // 일정에 담기가 되살아났다 - 담는 흐름이 카카오 값을 저장하지 않게 되었다(3단계)
      expect(within(card).getByRole("button", { name: "일정에 담기" })).toHaveAttribute("aria-expanded", "false");
```
 - 이 시험의 끝, `// 다시 찾기는 결과 목록 검색과 같은 요청 하나다` 와 `expect(searchPlacesSpy).toHaveBeenCalledTimes(1);` 다음 줄에 더한다.
```tsx

      // 일정에 담기: 끝나지 않은 · 고칠 수 있는 일정만. 고르면 그 일정의 장소 추가 창이 열린다(시안 v57) - 넘기는 것은 카카오 장소 ID 와 친 말뿐
      card = screen.getByRole("article", { name: "오동도 장소 카드" });
      await user.click(within(card).getByRole("button", { name: "일정에 담기" }));
      const picker = await within(card).findByRole("group", { name: "일정 고르기" });
      await within(picker).findByRole("button", { name: /여수 여행/ });
      expect(within(picker).queryByText("지난 여행")).toBeNull();
      expect(within(picker).queryByText("보기만 하는 여행")).toBeNull();
      await user.click(within(picker).getByRole("button", { name: /여수 여행/ }));
      await waitFor(() => expect(routeLocation().pathname).toBe("/trips/301"));
      const sheet = await screen.findByRole("dialog", { name: "장소 추가" });
      // 홈에서 본 카카오 장소를 서버가 우리 장소와 맞춰 본 결과가 바구니에 든다
      await waitFor(() =>
        expect(matchSpy).toHaveBeenCalledWith({ name: "오동도", latitude: 34.745, longitude: 127.766, categoryCode: "AT4" }),
      );
      expect(await within(sheet).findByRole("region", { name: "추가할 장소 목록" })).toHaveTextContent("오동도");
      expect(within(sheet).getByRole("button", { name: "Day 1에 1개 저장하기" })).toBeInTheDocument();
```
 - 이 시험의 `finally` 에서 `searchPlacesSpy.mockRestore();` 다음에 `listTripsSpy.mockRestore();` `getTripSpy.mockRestore();` `matchSpy.mockRestore();` 를 더한다.

 다. 위 시험 바로 뒤에 새 시험을 더한다.

```tsx
  it("offers a new trip carrying only the Kakao id and the typed words when there is no upcoming trip", async () => {
    const odongdo: PlaceSearchItem = {
      kind: "place",
      id: "kakao:8193468",
      name: "오동도",
      category: "여행 > 관광,명소 > 섬",
      categoryCode: "AT4",
      address: "전남광주통합특별시 여수시 수정동 1-1",
      latitude: 34.745,
      longitude: 127.766,
      placeUrl: "http://place.map.kakao.com/8193468",
      sido: "전남",
      city: "여수",
    };
    const listPoliciesSpy = vi.spyOn(appDataApi, "listPolicies").mockResolvedValue([policy({ id: "ys", title: "[여수] 숙박 할인", region: "전남" })]);
    const getProfileSpy = withoutPreferredRegions();
    const searchPlacesSpy = vi.spyOn(appDataApi, "searchPlaces").mockResolvedValue([odongdo]);
    const listTripsSpy = vi.spyOn(appDataApi, "listTrips").mockResolvedValue([]);
    try {
      await login();
      cleanup();
      renderAppRoute("/home");
      const user = userEvent.setup();
      const searchbox = await screen.findByRole("searchbox", { name: "지역 · 혜택 · 장소 검색" });
      await user.click(searchbox);
      await user.type(searchbox, "오동도");
      await user.click(await screen.findByRole("button", { name: /오동도.*섬/ }));
      const card = await screen.findByRole("article", { name: "오동도 장소 카드" });

      await user.click(within(card).getByRole("button", { name: "일정에 담기" }));
      const picker = await within(card).findByRole("group", { name: "일정 고르기" });
      expect(await within(picker).findByText("다가오는 일정이 없어요")).toBeInTheDocument();
      const href = within(picker).getByRole("link", { name: "새 일정 만들기" }).getAttribute("href")!;
      const params = new URLSearchParams(href.split("?")[1]);
      expect(href.startsWith("/trips/new?")).toBe(true);
      // 시도(sido)도 싣지 않는다 - 카카오 장소에서 나온 값은 ID 와 친 말뿐이다
      expect([...params.keys()].sort()).toEqual(["addPlace", "q"]);
      expect(params.get("addPlace")).toBe("kakao:8193468");
      expect(params.get("q")).toBe("오동도");
    } finally {
      listPoliciesSpy.mockRestore();
      getProfileSpy.mockRestore();
      searchPlacesSpy.mockRestore();
      listTripsSpy.mockRestore();
    }
  });
```

**(5) e2e 시드** - 새 서버는 옛 카카오 필드(`label` · `meta`)를 422 로 거절한다. 시드를 나만의 장소 요청으로 바꾼다. (과제 9 가 같은 두 곳을 이미 같은 모양으로 고쳤으면 건너뛴다.)

`frontend/e2e-backend/backend-mode.spec.ts`
```ts
      expectedRevision: 1,
      time: "10:00",
      label: "광안리 테스트 장소",
      meta: "E2E 편집 컨트롤 확인",
```
→
```ts
      expectedRevision: 1,
      time: "10:00",
      customPlace: { name: "광안리 테스트 장소" },
```
`frontend/e2e-backend/itinerary-cross-day-drag.spec.ts`
```ts
        expectedRevision: 1,
        time: "10:00",
        label: placeLabel,
        meta: "Day 1 에서 Day 2 로 옮길 카드",
```
→
```ts
        expectedRevision: 1,
        time: "10:00",
        customPlace: { name: placeLabel },
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd frontend && npx vitest run src/utils/placeHandoff.test.ts src/app/__tests__/trip-create.test.tsx src/app/__tests__/home.test.tsx src/app/__tests__/trip-detail.test.tsx`
기대: FAIL 4개 파일 - 시험 16개(관찰한 값. 그중 `home.test.tsx` 의 `renders the deadline row ...` · `shows the profile prompt ...` 둘은 이 과제와 무관한 기존 환경 의존 실패일 수 있다 - 처음 상태에서도 같은 결과면 뺀다).
- `placeHandoff.test.ts`: 7개 - `writeAddPlaceParam is not a function` · `readAddPlaceParam is not a function` · `pickInputFromItem is not a function` · `pickInputFromKakaoId is not a function`(새 export 가 없다).
- `trip-create.test.tsx`: 1개 - `Unable to find an element with the text: 만들고 나면 고른 장소를 담을 날을 골라요`(주소에 지역 없이 `addPlace` · `q` 만 있는 새 일정 만들기 주소).
- `home.test.tsx`: 2개 - `Unable to find an accessible element with the role "button" and name "일정에 담기"`(바뀐 시험과 새 시험이 같은 이유).
- `trip-detail.test.tsx`: 4개 - 모두 `TypeError: writeAddPlaceParam is not a function`(가져오기가 아직 없어 홈 넘김 시험 넷이 시작도 못 한다).

- [ ] **3단계: 구현**

**(1) `frontend/src/utils/placeHandoff.ts`** - 파일 전체를 아래로 바꾼다.

```ts
import type { PlaceSearchItem } from "../api";
import { kakaoPlaceIdOf, type PlacePickInput } from "../components/itinerary/placeAdd/usePlaceMatch";

/* 홈 장소 카드의 '일정에 담기'가 일정 화면으로 넘기는 것(카카오 운영정책 3단계, 설계 docs/superpowers/specs/2026-10-03-public-place-storage-design.md 4절).
   주소에는 카카오 장소 ID(addPlace=kakao:{id})와 사용자가 친 말(q)만 싣는다 - 이름 · 주소 · 좌표는 싣지 않는다.
   받는 쪽이 화면 메모리(없으면 같은 말 재검색, components/map/placeMemory.ts)에서 장소를 꺼내 맞춰 보기를 시작한다. */
const MAX_QUERY_LENGTH = 100;

export type AddPlaceHandoff = { kakaoPlaceId: string; query: string };

export function readAddPlaceParam(search: string | URLSearchParams): AddPlaceHandoff | null {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;
  const kakaoPlaceId = kakaoPlaceIdOf({ id: params.get("addPlace") });
  if (!kakaoPlaceId) return null;
  return { kakaoPlaceId, query: (params.get("q") ?? "").trim().slice(0, MAX_QUERY_LENGTH) };
}

/** 주어진 params 에 addPlace · q 만 쓰고 그대로 돌려준다(다른 키는 건드리지 않는다) */
export function writeAddPlaceParam(params: URLSearchParams, { kakaoPlaceId, query }: AddPlaceHandoff): URLSearchParams {
  params.set("addPlace", `kakao:${kakaoPlaceId}`);
  const typed = query.trim().slice(0, MAX_QUERY_LENGTH);
  if (typed) params.set("q", typed);
  else params.delete("q");
  return params;
}

/** 메모리에서 꺼낸 카카오 장소를 맞춰 보기 입구(openAddPlace · usePlaceMatch.pick)가 읽는 다섯 값으로. 화면 메모리 안에서만 쓰고 저장하지 않는다 */
export function pickInputFromItem(item: PlaceSearchItem): PlacePickInput {
  return { id: item.id, title: item.name, latitude: item.latitude, longitude: item.longitude, categoryCode: item.categoryCode };
}

/** 장소를 다시 못 찾았을 때(새로 고침 · 오래된 링크) - 좌표 없는 입력으로 보내면 pick 이 바로 나만의 장소 칸으로 간다. 카카오 ID 는 남아 링크가 산다 */
export function pickInputFromKakaoId(kakaoPlaceId: string): PlacePickInput {
  return { id: `kakao:${kakaoPlaceId}`, title: "" };
}
```

**(2) `frontend/src/pages/itinerary/ItineraryDetailPage.tsx`**

 가. 가져오기.

```ts
import { readPlaceParam } from "../../utils/placeHandoff";
```
→
```ts
import { usePlaceById } from "../../components/map/placeMemory";
import {
  pickInputFromItem,
  pickInputFromKakaoId,
  readAddPlaceParam,
  type AddPlaceHandoff,
} from "../../utils/placeHandoff";
```

 나. 넘김 받기. 과제 9 가 JSON 에서 꺼낸 값을 `openAddPlace` 에 넘기게 해 둔 아래 블록(주석 두 줄 + `handoffPlace` effect)을 통째로 바꾼다.

```tsx
  /* 홈 장소 카드의 '일정에 담기'(시안 v57): ?addPlace= 로 넘어온 장소를 바구니에 담은 장소 추가 창으로 연다.
     한 번 읽고 주소에서 지운다(새로 고쳐도 다시 열리지 않게). 고칠 수 없는 일정이면 openAddPlace 가 권한 안내를 띄운다 */
  const handoffPlace = searchParams.get("addPlace");
  useEffect(() => {
    if (!handoffPlace || !trip) return;
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete("addPlace");
        return next;
      },
      { replace: true },
    );
    const item = readPlaceParam(handoffPlace);
    if (item)
      openAddPlace({
        id: item.id,
        title: item.name,
        latitude: item.latitude,
        longitude: item.longitude,
        categoryCode: item.categoryCode,
      });
  }, [handoffPlace, trip?.id]);
```
→
```tsx
  /* 홈 장소 카드의 '일정에 담기'(시안 v57): ?addPlace=kakao:{id}&q={친 말} 로 넘어온 카카오 장소를 화면 메모리(없으면 같은 말 재검색)에서
     꺼내 맞춰 보기를 시작한다 - 바구니에는 공공데이터 장소(또는 사용자가 적은 이름)만 담긴다. 주소에는 ID 와 친 말뿐이다.
     넘김은 한 번 읽어 state 에 쥐고 바로 주소에서 지운다(새로 고쳐도 다시 열리지 않게). 장소가 나오면 추가 창을 열고 맞춰 본다.
     고칠 수 없는 일정이면 openAddPlace 가 권한 안내만 띄우고 맞춰 보지 않는다 */
  const urlHandoff = readAddPlaceParam(searchParams);
  const [handoff, setHandoff] = useState<AddPlaceHandoff | null>(null);
  useEffect(() => {
    if (!urlHandoff || !trip) return;
    setHandoff(urlHandoff);
    setSearchParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete("addPlace");
        next.delete("q");
        return next;
      },
      { replace: true },
    );
  }, [urlHandoff?.kakaoPlaceId, urlHandoff?.query, trip?.id]);
  const handedPlace = usePlaceById(handoff ? `kakao:${handoff.kakaoPlaceId}` : null, handoff?.query ?? "");
  useEffect(() => {
    if (!handoff || (!handedPlace.place && !handedPlace.missing)) return;
    setHandoff(null);
    // 못 찾았으면 좌표 없는 입력으로 - pick 이 바로 나만의 장소 칸으로 보낸다(카카오 ID 만 남는다)
    openAddPlace(handedPlace.place ? pickInputFromItem(handedPlace.place) : pickInputFromKakaoId(handoff.kakaoPlaceId));
  }, [handoff, handedPlace.place, handedPlace.missing]);
```

**(3) `frontend/src/pages/itinerary/ItineraryCreatePage.tsx`**

 가. 가져오기.

```ts
import { readPlaceParam } from "../../utils/placeHandoff";
```
→
```ts
import { readAddPlaceParam, writeAddPlaceParam } from "../../utils/placeHandoff";
```

 나. 읽기.

```ts
  /* 홈 장소 카드에서 왔으면(시안 v57) 만든 일정에서 그 장소를 담은 장소 추가 창이 열리게 넘긴다 */
  const handoffPlace = searchParams.get("addPlace");
  const handoffPlaceName = readPlaceParam(handoffPlace)?.name ?? null;
```
→
```ts
  /* 홈 장소 카드에서 왔으면(시안 v57) 만든 일정에서 그 장소를 맞춰 보고 담는 창이 열리게 넘긴다.
     주소에는 카카오 장소 ID 와 친 말뿐이라 이름을 모른다 - 배너도 이름 없이 알린다(카카오 값을 화면 밖에 두지 않는다) */
  const handoff = readAddPlaceParam(searchParams);
```

 다. 일정을 만든 뒤 넘기기.

```ts
      navigate(
        handoffPlace && handoffPlaceName
          ? `/trips/${trip.id}?${new URLSearchParams({ addPlace: handoffPlace })}`
          : `/trips/${trip.id}`,
      );
```
→
```ts
      navigate(
        handoff
          ? `/trips/${trip.id}?${writeAddPlaceParam(new URLSearchParams(), handoff)}`
          : `/trips/${trip.id}`,
      );
```

 라. 배너.

```tsx
        {handoffPlaceName && (
          <div className="prototype-linked-policy-banner">
            <span aria-hidden="true">장소</span>
            <strong>만들고 나면 ‘{handoffPlaceName}’ 담을 날을 골라요</strong>
          </div>
        )}
```
→
```tsx
        {handoff && (
          <div className="prototype-linked-policy-banner">
            <span aria-hidden="true">장소</span>
            {/* 시안 v59 */}
            <strong>만들고 나면 고른 장소를 담을 날을 골라요</strong>
          </div>
        )}
```

**(4) `frontend/src/components/HomeSearch.tsx`** - 되살린다(`git show f07fa06^:frontend/src/components/HomeSearch.tsx` 의 `TripPicker` 를 새 넘김 형식으로).

 가. 가져오기. `import { appDataApi, type NearbyCategory, type PlaceSearchItem, type Policy } from "../api";` 다음 줄에 더한다.

```ts
import { useAsyncResource } from "../api/useAsyncResource";
import { tripStatus } from "../utils";
import { writeAddPlaceParam } from "../utils/placeHandoff";
import { kakaoPlaceIdOf } from "./itinerary/placeAdd/usePlaceMatch";
```

 나. 장소 카드 상태. `HomePlaceCard` 안에서

```tsx
  const xy = xyOf(item);
  const target = nearTarget(policies, item.sido ?? null, item.city ?? null, xy);
  /* 근처 혜택 = 정책 탭 위치로 찾기와 같은 화면(핀 · '근처' 줄 · 가까운 시군) */
  const nearUrl = nearUrlOf(item, target, query);
```
→
```tsx
  const [picking, setPicking] = useState(false);
  const kakaoPlaceId = kakaoPlaceIdOf(item);
  const xy = xyOf(item);
  const target = nearTarget(policies, item.sido ?? null, item.city ?? null, xy);
  /* 근처 혜택 = 정책 탭 위치로 찾기와 같은 화면(핀 · '근처' 줄 · 가까운 시군) */
  const nearUrl = nearUrlOf(item, target, query);
```

 다. 단추와 일정 고르기 상자.

```tsx
      <div className="home-place-acts">
        {target.note && <p className="home-place-note">{target.note}</p>}
```
→
```tsx
      <div className="home-place-acts">
        {kakaoPlaceId && (
          <button className="home-place-primary" type="button" aria-expanded={picking} onClick={() => setPicking((value) => !value)}>
            일정에 담기
          </button>
        )}
        {target.note && <p className="home-place-note">{target.note}</p>}
```
그리고
```tsx
      </div>
      <NearbySection item={item} policies={policies} code={nearCode} cache={nearbyCache} onCode={onNearCode} onOpen={onOpenNearby} />
```
→
```tsx
      </div>
      {picking && kakaoPlaceId && <TripPicker kakaoPlaceId={kakaoPlaceId} query={query} />}
      <NearbySection item={item} policies={policies} code={nearCode} cache={nearbyCache} onCode={onNearCode} onOpen={onOpenNearby} />
```

 라. `TripPicker` 를 `HomePlaceCard` 함수가 끝난 뒤(`/* 이 근처(시안 v58): ...` 주석 앞)에 더한다.

```tsx
/* 일정에 담기(시안 v57): 일정만 고른다. 고르면 그 일정 상세의 '장소 추가' 창이 이 장소를 우리 장소와 맞춰 본 뒤 바구니에 담아 열리고 날은 거기서 고른다.
   주소에는 카카오 장소 ID 와 친 말만 싣는다(카카오 운영정책) - 이름 · 주소 · 좌표는 받는 쪽이 화면 메모리(없으면 같은 말 재검색)에서 꺼낸다.
   담을 곳은 끝나지 않은 일정 중 고칠 수 있는 것만(보기 권한이면 열자마자 막힌다) */
function TripPicker({ kakaoPlaceId, query }: { kakaoPlaceId: string; query: string }) {
  const navigate = useNavigate();
  const { data, error, isLoading } = useAsyncResource(() => appDataApi.listTrips(), []);
  const trips = (data ?? [])
    .filter((trip) => tripStatus(trip.startDate, trip.endDate)?.tone !== "past" && trip.currentUserRole !== "viewer")
    .sort((left, right) => left.startDate.localeCompare(right.startDate));
  const handoff = writeAddPlaceParam(new URLSearchParams(), { kakaoPlaceId, query }).toString();
  const newTripUrl = `/trips/new?${handoff}`;
  return (
    <div className="home-trip-pick" role="group" aria-label="일정 고르기">
      {isLoading ? (
        <p className="home-nearby-tip">일정을 불러오는 중…</p>
      ) : error ? (
        <p className="home-nearby-tip">일정 목록을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.</p>
      ) : trips.length > 0 ? (
        <>
          <h4>어느 일정에 담을까요?</h4>
          <p className="home-nearby-tip">고르면 그 일정의 장소 추가 창이 열려요. 날은 거기서 골라요.</p>
          {trips.map((trip) => (
            <button
              className="home-trip-pick-row"
              key={trip.id}
              type="button"
              onClick={() => navigate(`/trips/${trip.id}?${handoff}`)}
            >
              <b>{trip.title}</b>
              <span>{trip.dates}</span>
            </button>
          ))}
          <Link className="home-trip-pick-new" to={newTripUrl}>새 일정 만들기</Link>
        </>
      ) : (
        <>
          <h4>다가오는 일정이 없어요</h4>
          <p className="home-nearby-tip">일정을 만들면 그 일정의 장소 추가 창이 이 장소를 담은 채 열려요.</p>
          <Link className="home-place-primary" to={newTripUrl}>새 일정 만들기</Link>
        </>
      )}
    </div>
  );
}
```

 마. 처음 안내 문구.

```tsx
              <p>지역이나 혜택 이름은 정책 탭으로, 장소는 카드로 열려요. 장소 카드에서 그 근처 혜택을 볼 수 있어요.</p>
```
→
```tsx
              <p>지역이나 혜택 이름은 정책 탭으로, 장소는 카드로 열려요. 장소 카드에서 그 근처 혜택을 보거나 일정에 담을 수 있어요.</p>
```

**(5) `frontend/src/styles/home.css`** - 10/4 이전(v57) 규칙을 그대로 되살린다(시안 v59 확정 때 다듬는다).

`.home-place-acts { display: grid; gap: 8px; }` 줄 바로 다음에 더한다.

```css
.home-place-primary {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 50px;
  border: 0;
  border-radius: 14px;
  background: var(--primary-600);
  color: #fff;
  font: inherit;
  font-size: 16px;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}
```
`.home-nearby-tip { margin: 0; font-size: 13px; color: var(--gray-600); }` 줄 바로 다음에 더한다.

```css
/* 시안 v59: 일정에 담기 - 일정 고르기 상자 */
.home-trip-pick { display: grid; gap: 8px; margin-top: 4px; padding: 12px; border: 1px solid var(--gray-200); border-radius: 16px; background: var(--gray-50); }
.home-trip-pick h4 { margin: 0; font-size: 15px; }
.home-trip-pick-row {
  display: grid;
  gap: 2px;
  min-height: 56px;
  padding: 8px 12px;
  border: 1px solid var(--gray-200);
  border-radius: 12px;
  background: var(--color-bg-card);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.home-trip-pick-row b { font-size: 15px; }
.home-trip-pick-row span { font-size: 13px; color: var(--gray-600); }
.home-trip-pick-new {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 46px;
  border: 1px solid var(--color-border-default);
  border-radius: 14px;
  background: var(--color-bg-card);
  color: inherit;
  font-size: 15px;
  text-decoration: none;
}
```

**(6) e2e 시드** - 1단계 (5)에서 이미 고쳤다.

- [ ] **4단계: 통과하는지 확인**

실행: `cd frontend && npx vitest run src/utils/placeHandoff.test.ts src/app/__tests__/trip-create.test.tsx src/app/__tests__/home.test.tsx src/app/__tests__/trip-detail.test.tsx`
기대: PASS - 4개 파일, 시험 192개(과제 7~9 · 10 · 11 이 적용된 상태). 관찰: 가짜 로그인 환경에서는 `home.test.tsx` 의 `renders the deadline row ...` · `shows the profile prompt ...` 둘이 처음 상태에서도 실패해 190개 통과 · 2개 실패였다 - 실제 백엔드에서는 전부 통과해야 하니 이 파일은 한 번 더 확인한다.
실행: `cd frontend && npx tsc --noEmit -p .`
기대: 타입 오류 없음. 남는 오류가 있으면 앞 과제가 정한 이름(과제 9 의 `openAddPlace` 인자 · `PlaceEditorSheet` 의 `ReactNode` 가져오기)과 어긋난 곳이다.
실행(한글 파일): `cd frontend && npm run test:mojibake` 기대: 통과. 이 부분에서 바꾼 한글 파일의 diff 에 U+FFFD 가 없어야 하고 `git diff --check` 를 통과해야 한다.

---

---

### Task 13: 문서 · 로컬 실측 · 전체 검증 · 커밋

**파일:**
- 고치기: `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`, `docs/implemented-feature-spec.md`, `CHECKLIST.md`

- [ ] **1단계: 설계 문서를 계획의 결정에 맞춘다(문장 그대로 바꾼다)** - 미리 맞춤 · 실패 때 고른 뒤 맞춰 보기 · 같은 줄 하나로(결정 23 · 27)는 과제 8b 3단계가 이미 2절에 적었다.
  - 2절 '편집 초안(`localStorage`)에는 공공데이터 값과 사용자 입력만 들어간다.' 문단 끝에 이어 쓴다: ` 초안 모양이 3단계에서 바뀌므로 초안 판을 3단계에서 올리고, 앱이 시작할 때 예전 판 키를 지운다(4단계의 초안 무효화를 앞당김).`
  - 2절 '나만의 장소에서는 카카오 이름을 미리 채우지도, 옆에 참고로 보여 주지도 않는다.' 끝에 이어 쓴다: ` 검색 결과 아래 '직접 적기' 입구로 카카오에 없는 곳도 나만의 장소로 담을 수 있다(카카오 ID 없음).`
  - 2절 '위치 찍기 지도는 일정 지역에서 시작한다.' 끝에 이어 쓴다: ` 처음 중심은 일정 지역 공공데이터 장소 위경도의 중앙값이다(값이 없으면 대한민국 중심).`
  - 3절 6번 '브라우저의 예전 편집 초안을 무효화한다.' 끝에 이어 쓴다: ` - 3단계에서 했다.`
  - 2절 '이미 담은 장소의 이름을 사용자가 고치면 사용자 입력으로 저장한다.' 끝에 이어 쓴다: ` 공공데이터 장소는 고친 이름을 따로 두는 칸(\`user_label\`)에 담아 공공데이터 이름 · 주소 · 사진 · 위치와 섞지 않는다.`
- [ ] **2단계: `docs/implemented-feature-spec.md`** - '공공데이터 장소 기반(화면 없음)' 행을 '장소 담기(공공데이터 · 나만의 장소)' 행으로 바꿔, 세 갈래 담기 · 직접 적기 · 위치 찍기 · 예전 장소 확인 · 공공데이터 추천 · 홈 '일정에 담기'를 한 문단으로 적고, API 칸에 `POST /api/trips/{trip_id}/days/{day}/places(/batch)` · `PATCH /api/trips/{trip_id}/places/{place_id}` · `GET .../public-candidates` · `GET .../area-center` · `POST /api/places/match` 를 적는다. '장소로 근처 혜택 찾기' 행의 "홈 '일정에 담기'는 … 3단계(담는 흐름) 전까지 숨긴다" 문장을 "홈 '일정에 담기'는 일정 화면의 같은 담는 흐름으로 잇는다"로 바꾼다.
- [ ] **3단계: 로컬 실측(로컬 DB 만, 이 계획 승인으로 함께 승인)** - 순서는 `.codex/skills/travel-hunter-workflow/SKILL.md` 4절.
  - 덤프(저장소 밖, 600) → `pg_restore -l` 목차 확인 → SHA-256 기록, 행 수(전) `policies` · `trips` · `users` · `external_source_records` · `trip_places`.
  - 세 컨테이너를 이 워크트리로 다시 만든다(DB 볼륨 유지, `--force-recreate db backend frontend`), 출처 라벨 확인. `alembic upgrade head` → `0049_trip_place_public_category (head)`. 5173 Vite 도 이 워크트리에서.
  - 공공데이터가 들어 있는지 본다(2단계 점검에서 TourAPI 전체 · 상가정보 전체를 넣었다). 비어 있으면 2단계 스크립트로 넣는다(TourAPI 약 50회 호출).
  - 실제 API 확인(로컬 시험 계정, 자격은 스크립트 안에서만 읽는다): 공공데이터 담기 · 나만의 장소 담기(좌표 있음 · 없음) · 카카오 필드를 보낸 담기 422(응답 `detail` 에 `extra_forbidden` - 화면의 새로 고침 판별이 기대는 모양) · 없는 참조 404 와 revision 그대로 · 예전 행 시간만 PATCH · 예전 행 이름 PATCH 뒤 카카오 값 지워짐 · 후보 경로 · 지역 중심 · 추천(공공데이터).
  - 새로 담은 행 확인(값을 찍지 않고 건수만): `select count(*) from trip_places where place_origin in ('public','custom') and trip_day_id in (select id from trip_days where trip_id in (<이번 실측으로 만든 일정 id>)) and (category_group_code is not null or category_group_name is not null or memo is not null)` → 0(코덱스 검토: 실측 일정으로만 좁힌다), `place_origin = 'custom'` 행의 `address` 는 0건이 null 아님.
  - 맞춰 보기 속도(읽기 전용): 명동 · 종로 관광명소 맞춰 보기가 출처별 상자(결정 16) 뒤 10ms 안팎으로 돌아오는지 본다(2단계 점검 때 약 70ms).
  - 검색 미리 맞춤 속도(읽기 전용, 결정 23 · 코덱스 검토): 카카오 호출은 빼고 미리 맞춤만 잰다. 이 워크트리로 다시 만든 백엔드 컨테이너 안에서 고정된 여섯 줄(과제 8b 5단계의 공공 좌표 여섯 곳, 이름은 그 곳의 TourAPI 이름, 분류 `AT4`)로 `public_places.match_places` 를 스무 번 불러 최대 · p95(ms)와 한 번의 질의 수(2)를 적는다. p95 100ms 를 넘으면 멈추고 보고한다.
  - 미리 맞춤 갈래 비율(건수만): 실제 검색 다섯 개('명동 카페' · '종로 맛집' · '여수 오동도' · '담양 죽녹원' · '해운대 호텔')를 한 번씩 불러 나온 줄(최대 5 × 6 = 30줄)의 `match` · `candidates` · `none` · null 수를 적는다(10/3 실측 바로 담기 약 60% 와 견줄 값).
  - 0049 색인(결정 17): `CREATE INDEX CONCURRENTLY` 가 로컬 108만 행에서 걸린 시간을 적는다(개발서버 배포 때 참고). 시험은 SQLite 와 오프라인 SQL 까지였으므로 로컬 Postgres 에서 `upgrade → downgrade → upgrade` 를 한 번 돌린다. 다시 돌리기도 본다(결정 17): `downgrade` 로 0048 에 둔 채 같은 이름의 색인을 하나 만들어 두고(실패한 시도가 남긴 색인 흉내) `upgrade` 가 그것을 지우고 새로 만들어 끝나는지. 끝나면 `select indisvalid from pg_index i join pg_class c on c.oid = i.indexrelid where c.relname = 'ix_public_places_sido_city'` 가 `t` 다.
  - **추천 · 지역 중심 질의 비용(머지 전 필수, 결정 20)**: `whole:경기` · `whole:서울` · `admin:서울:종로구` · `whole:세종` 일정으로 추천과 지역 중심 경로를 각각 다섯 번 불러 시간을 재고, 가장 느린 것의 질의를 `EXPLAIN ANALYZE` 로 본다. 1초를 넘기면 과제 5 에 적은 대안(분류별 후보를 먼저 줄인 뒤 섞기, 중앙값은 DB 집계)으로 고치고 다시 잰다 - 그래도 넘으면 멈추고 보고한다.
  - 행 수(후): 실측으로 만든 일정 · 장소 말고는 같아야 한다(30% 넘게 변하면 멈추고 보고). 실측용 일정은 끝나면 지운다.
- [ ] **4단계: 전체 검증**
  - 백엔드: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --deselect tests/test_stay_discount_semantics_snapshot.py`, `python -m alembic upgrade 0045_traffic_detail:head --sql > /dev/null && echo SQL_OK`(처음부터는 기존 `0044` 에서 멈춘다)
  - compose: `docker compose --env-file /c/dev/travel-hunter/travel-hunter-onprem/.env -f compose.yaml config > /dev/null && echo COMPOSE_OK`
  - 프론트: `npx tsc --noEmit -p .`, `npm run test:mojibake`, `npx vitest run`(알려진 mypage 6개 실패는 따로 적는다), `npm run build`, `npm run test:e2e:containers`
  - `git diff --check`, 바꾼 diff 와 새 파일의 U+FFFD 0건 · 한자 0건
- [ ] **5단계: 사용자 화면 확인 목록 넘기기** - 브라우저 확인은 사용자 몫이다(Claude 는 Chrome 에 붙지 않는다). 5173 에서 볼 것: 세 갈래 담기, 직접 적기, 위치 찍기(일정 지역에서 열림), 예전 장소 '확인 필요', 공공데이터 사진과 출처, 추천 일정 저장, 홈 '일정에 담기' → 일정 고르기 → 담기, 결과 줄의 '바로 담기' · '비슷한 곳 N' · '직접 적기'와 고른 뒤 바로 가는 것, 칠 때 창이 흔들리지 않음, 휴대폰 폭(390)과 넓은 화면.
- [ ] **6단계: CHECKLIST** - Current Status(이 브랜치 머지 준비, 범위, DB `0049`, 화면 변화), Recent Validation(이번 실행 결과), Active Risks 에 '장소 담기(`feature/place-add-flow`)' 절: 예전 카카오 행은 4단계 전까지 그대로 남음, 두 출처 같은 이름은 후보로 남음(바로 담기 74% - 사람이 표본을 확인한 뒤 합칠지 정함), 1단계 `near` 의 지역 · 시군이 카카오 주소에서 나온 값과 통합 검색이 카카오 설정 오류를 빈 목록으로 숨기는 것(다음 작업), 배포 때 열려 있던 옛 화면은 새로 고칠 때까지 담기 실패(배포 절차), `incheon-ganghwa` 지역 데이터는 강화만 추천, 위치 찍기는 카카오 지도 키가 없으면 숨김, 브라우저 확인 결과. 검색 결과 제목이 긴 카카오 분류 때문에 한 글자씩 꺾이는 문제는 다음 작업(결정 28, 사용자 결정).
- [ ] **7단계: 커밋 승인받기** - 아래 세 커밋을 보이고 승인받은 뒤 만든다.
  1. `feat: 장소를 담을 때 공공데이터 참조와 직접 쓴 값만 받는다`(과제 2 ~ 6 백엔드 · 계약)
  2. `feat: 일정에 장소를 세 갈래로 담고 예전 장소는 확인받는다`(과제 7 ~ 12 프론트, 설계 · 기능 문서, 이 계획)
  3. `docs: CHECKLIST 를 장소 담기 PR 기준으로 갱신한다`
- [ ] **8단계: 푸시와 Draft PR** - PR #90 이 develop 에 머지된 뒤 `git fetch` → develop 위로 다시 쌓기(2단계 커밋은 develop 에 이미 있어 빠진다) → 따로 승인받아 푸시 · Draft PR(base develop). `.codex/local-workflow.md` 의 PR 게이트를 따른다(최종 HEAD 리뷰 SHA 일치).

## 머지 뒤 서버 작업(실행할 때마다 승인)

1. 개발서버 배포(Jenkins)가 `alembic upgrade head` 로 `0049` 를 올린다. 새 백엔드는 `public_category` · `user_label` 열을 읽으므로 마이그레이션이 새 백엔드 기동보다 먼저여야 한다 - PR 전에 배포 스크립트의 순서를 확인해 PR 본문에 적는다. 색인은 `CONCURRENTLY` 라 쓰기를 막지 않는다.
   **색인 확인(결정 17):** 배포 뒤 읽기만 해서 확인한다 - `echo "select indisvalid from pg_index i join pg_class c on c.oid = i.indexrelid where c.relname = 'ix_public_places_sido_city';" | docker exec -i <db 컨테이너> sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At'` → `t`. 0049 에서 배포가 실패했으면 배포를 다시 돌린다 - 마이그레이션이 남은 색인을 먼저 지우고 다시 만든다(손으로 `DROP INDEX` 하지 않는다). 색인 단계가 로컬 실측보다 훨씬 오래 걸리면 `CONCURRENTLY` 가 오래 열린 트랜잭션을 기다리는 것이다 - `pg_stat_activity` 를 읽기만 하고 보고한다. 이 확인 명령과 다시 돌리기 규칙을 PR 본문에도 적는다.
   **옛 화면 전환 절차(결정 1):** 사용이 적은 때 배포하고, 배포 직후 시험하는 분들께 '열어 둔 앱을 새로 고쳐 달라'고 알린다. 열려 있던 옛 화면은 새로 고칠 때까지 장소 담기 · 수정이 '저장하지 못했어요'로 실패한다.
2. 개발서버 `public_places` 가 채워져 있어야 추천 · 맞춰 보기가 의미 있다(2단계 머지 뒤 서버 작업).
   **미리 맞춤 질의 속도(결정 23, 사용자 결정 10/6, 읽기 전용 · 실행 때 승인):** 개발서버 DB 에서 과제 8b 5단계의 두 질의를 `EXPLAIN (ANALYZE, BUFFERS)` 로 처음 값 · 다시 돌린 값을 잰다(같은 `docker exec ... psql` 방식, 값 출력 없음). 처음 값이 300ms 를 넘으면 다음 작업으로 TourAPI 장소만 담는 작은 위치 색인(`WHERE source = 'tourapi'`, `CONCURRENTLY`)을 더하거나 미리 맞춤 줄 수를 줄인다.
3. 운영은 최신 develop 배포 뒤 같은 순서.
