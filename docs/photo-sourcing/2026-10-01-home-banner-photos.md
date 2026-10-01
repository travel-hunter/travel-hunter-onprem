# 홈 배너 사진: 어디서 가져왔고 왜 골랐나 (2026-10-01)

홈 맨 위 배너(시안 v45 겹침 배너)의 장마다 깔 사진을 고른 기록이다. 나중에 사진을 더 모으거나 바꿀 때
같은 기준으로 다시 고르고 비교할 수 있게 출처·검색어·후보 전부·고른 이유를 남긴다.
시안: 디자인 시안(담당자 비공개 페이지) v48. 앱(4173) 반영은 사용자 승인 뒤.

## 왜 새로 찾았나

- 처음(시안 v47)에는 수집해 둔 시군 사진(한국관광공사 TourAPI, `policy.photo`)을 장마다 깔았다.
  사용자 확인 결과 **어울리지 않는 사진이 섞여 있었다** - 수집 사진은 그 시군의 '관광지 대표 사진'이라
  태양광 단지·어두운 해변처럼 여행 느낌과 먼 사진이 나온다.
- 앱에 들어 있는 도별 사진 17장(`frontend/src/assets/regions`)은 출처 기록이 저장소에 없어 새로 쓰지 않았다.
- 사용자 결정: 웹에서 이용 조건이 분명한 사진을 찾아 쓴다.

## 고르는 규칙

**출처·라이선스** - 위키미디어 공용(commons.wikimedia.org)에서 아래만 쓴다.

| 쓸 수 있음 | 화면 표시 | 비고 |
|---|---|---|
| CC0 · 퍼블릭 도메인 | 사진 이름 · 작가 · CC0 (예의상) | 조건 없음 - 가장 가볍다 |
| CC BY x.x | 사진 이름 · 작가 · CC BY x.x | 출처 표시 필수 |
| CC BY-SA x.x | 사진 이름 · 작가 · CC BY-SA x.x | 출처 표시 + 고친 사진(자르기·줄이기)도 같은 라이선스 |
| 공공누리 1유형 | 출처 기관 | 한국관광공사 등 |

CC BY-NC(상업 이용 불가)·ND(변경 금지)·라이선스 불명은 쓰지 않는다.

**화면 표시(2026-10-02, 시안 v53)** - 홈 배너는 장마다 적지 않고 배너 아래 오른쪽 '사진 출처' 창에 모은다: 사진마다 주제 · 작가 · 라이선스(라이선스 본문 링크) · 원본 보기(위키미디어 공용 링크). CC 가 요구하는 링크까지 둔다. 로그인 사진은 한 장이라 사진 위에 한 줄로 적는다. 데이터는 `frontend/src/components/heroPhotos.ts`(subject · author · license · licenseUrl · page).

**장과 사진 짝** - 시군마다 사진을 두면 그날 데이터에 따라 바뀌는 곳마다 사진이 필요해 끝이 없다. 장의 성격으로 고른다.

| 배너 장 | 사진 열쇠 | 사진 성격 |
|---|---|---|
| 혜택이 가장 많은 지역 | `region:<도>` (17개) | 그 도를 대표하는 여행 풍경 |
| 마감이 가장 가까운 혜택 | `theme:<refund·stay·partner·move>` | 혜택 종류 - 환급·여행상품 = 여행지 풍경, 숙박 = 숙소, 제휴 할인 = 가게·시장, 교통 = 기차·도로 |
| 전국 공통 | `theme:move` | 교통 |

맞는 사진이 없으면 사진 없이 혜택 형태 색 바탕으로 둔다(어울리지 않는 사진보다 낫다).

**사진 자체 기준(점수 매긴 순서)**

1. 장 성격과 맞는가 - 지역 장이면 그 도라는 것이 한눈에 보이는가
2. 글 얹을 자리 - 배너는 왼쪽부터 어둡게 눌러 흰 글씨를 올린다. 왼쪽이 단순하거나 어두울수록 좋다
3. 여행 느낌 - 풍경·빛·계절감. 설명용 사진(차량 연결기, 실내, 안내판)은 뺀다
4. 라이선스 부담 - CC0 > CC BY > CC BY-SA
5. 크기 - 가로 1200px 이상 가로 사진(데스크톱 가운데 장 ≈ 620px × 2배)

## 검색과 결과

도구: `tools/commons_search.py`(공용 API 검색, 라이선스·크기로 거름) → 후보 전부를
`2026-10-01-home-banner-candidates.json` 에 남겼다(검색어, 제목, 라이선스, 작가, 크기, 원본 주소, 거른 이유).

| 검색어 | 쓸 만함 / 찾음 |
|---|---|
| Boseong green tea field | 9 / 12 |
| Jeonju Hanok Village rooftops | 2 / 2 |
| KTX-Sancheon | 10 / 12 |
| Korail ITX train | 10 / 12 |
| Jeju coastal road | 12 / 12 |
| Korea countryside train | 4 / 5 |
| Hahoe Folk Village | 10 / 12 |
| Suncheon Bay wetland reeds | 0 / 0 (검색 결과 없음 - 다음엔 'Suncheonman' 으로) |
| KTX train landscape Korea | 0 / 0 |

거른 이유: 작은 사진 8, 세로 사진 3. 라이선스로 걸린 것은 이번 검색어에선 없었다.

## 눈으로 비교한 후보(8장)와 판단

| # | 사진 | 라이선스 · 작가 | 판단 |
|---|---|---|---|
| 1 | Boseong Green Tea Field South Korea Travel Photography | CC BY 3.0 · Giuseppe Milo | **전남 지역 장으로 고름.** 노을 녹차밭 - 여행 느낌 가장 강함, 왼쪽이 어두워 글 얹기 좋음 |
| 2 | Boseong Green Tea Field | CC BY-SA 3.0 · Jakob Reichmann | 맑은 낮 녹차밭. 무난하나 1번보다 밋밋하고 SA 부담 |
| 3 | Boseong Green Tea Field in summer 2017 | CC BY-SA 4.0 · S Shamima Nasrin | 앞쪽 찻잎이 커서 글 자리 복잡 |
| 4 | Jeonju- Part II - Jeonju3094 | CC0 · lumoplank | **여행비 환급(theme:refund)으로 고름.** 한옥 지붕 - '여행 가서 쓰는 돈' 느낌, CC0 |
| 5 | Jeonju- Part I - Jeonju3120 | CC0 · lumoplank | 4번과 같은 곳, 앞쪽 주차장·차가 보여 뺌 |
| 6 | KTX-Sancheon | CC BY-SA 4.0 · Minseong Kim | **교통(theme:move)으로 고름.** 기차가 오른쪽에 크게 - 왼쪽 글 자리 비어 있음 |
| 7 | Korail KTX-2 | CC BY 3.0 · G43 | 위에서 내려다본 차량기지, 트럭이 같이 보여 뺌 |
| 8 | Sinchang Windmill Coastal Road 01 | CC BY-SA 4.0 · Grapesurgeon | 정자·잔디가 주인공이라 '해안도로'가 안 읽힘 |

## 고른 사진(시안 v48)

| 열쇠 | 사진 | 작가 · 라이선스 | 원본 |
|---|---|---|---|
| `region:전남` | 보성 녹차밭 | Giuseppe Milo · CC BY 3.0 | https://commons.wikimedia.org/wiki/File:Boseong_Green_Tea_Field_South_Korea_Travel_Photography_(253061695).jpeg |
| `theme:refund` | 전주 한옥마을 | lumoplank · CC0 | https://commons.wikimedia.org/wiki/File:Jeonju-_Part_II_-_Jeonju3094.jpg |
| `theme:move` | KTX-산천 | Minseong Kim · CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:KTX-Sancheon.jpg |

받기·변환: `tools/hero_photos.py` - 공용 API 의 1600px 썸네일을 받아 WebP(품질 68)로 줄이고 출처 문자열을 만든다
(한 장 200~290KB). 화면에는 장 오른쪽 아래에 `사진 이름 · 작가 · 라이선스` 를 적는다.

## 숙박 · 제휴 할인 사진(2026-10-01 추가)

검색: `2026-10-01-stay-partner-candidates.json`(시장·카페 등), `2026-10-01-stay-candidates.json`(한옥·숙소).
여러 낱말 검색어('hanok guesthouse room', 'Korean pension ocean view' 등)는 0건이 많았다 - 짧은 고유명사
('Rakkojae', 'Bukchon hanok', 'Gwangjang Market')가 잘 걸린다. 공용은 요청이 잦으면 429 로 막아 도구에 쉬기·다시 하기를 넣었다.
비교: `tools/commons_preview.py` 로 10장을 한 장에 모아 봤다.

| # | 사진 | 라이선스 · 작가 | 판단 |
|---|---|---|---|
| 1 | Hwangnamguan Hotel at night | CC BY-SA 3.0 · Choi2451 | **숙박(theme:stay)으로 고름.** 경주의 실제 한옥 숙소, 불 켜진 저녁이라 '묵는' 느낌. 왼쪽 위가 어두워 글 자리 좋음 |
| 2 | Interior of a traditional Korean house | CC BY-SA 3.0 · Adbar | 박물관 같은 실내 - 숙소 느낌 아님 |
| 3 | Simujang 20150127 05 | CC BY-SA 2.0 · 대한민국 정부(Korea.net) | 기념관 실내, 인물 초상이 걸려 있음 - 뺌 |
| 4 | Traditional hanok houses at golden hour in Bukchon | CC BY-SA 4.0 · Basile Morin | 아름답지만 환급 사진(전주 한옥)과 겹치고 숙박과 무관 |
| 5 | Korean pancakes and pan-fried foods at Gwangjang Market | 퍼블릭 도메인 · Bo Park(US Army) | **제휴 할인(theme:partner)으로 고름.** 지역 먹거리 할인 느낌, 라이선스 부담 없음 |
| 6 | Gyedong-gil street with climbing plants at golden hour | CC BY-SA 4.0 · Basile Morin | 골목 풍경 - 가게·할인과 연결이 약함 |
| 7 | Jeju cafe overlooking woljeongri beach | CC BY-SA 4.0 · Sgroey | 바다 카페 - 후보 2순위(사람이 작게 보임) |
| 8 | Gwangjang Market | CC BY-SA 3.0 · ChongDae | 간판 글자가 많아 배너 글과 부딪힘 |
| 9 | Bojung Cafe street view in Spring | CC BY-SA 4.0 · SungMinSeung | 벚꽃만 보이고 카페가 안 읽힘 |
| 10 | Korea GwangjangMarket Eats 08 | CC BY-SA 2.0 · Korea.net | 얼굴이 크게 나온 상인 - 라이선스와 별개로 초상권 걱정이 있어 뺌 |

추가 기준(이번에 생김): **알아볼 수 있는 사람 얼굴이 주인공인 사진은 쓰지 않는다** - CC 라이선스는 저작권만 다루고 초상권은 따로다.

| 열쇠 | 사진 | 작가 · 라이선스 | 원본 |
|---|---|---|---|
| `theme:stay` | 경주 황남관 한옥 숙소 | Choi2451 · CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:Hwangnamguan_Hotel_at_night.jpg |
| `theme:partner` | 광장시장 전 | Bo Park(US Army) · 퍼블릭 도메인 | https://commons.wikimedia.org/wiki/File:Korean_pancakes_and_pan-fried_foods_at_Gwangjang_Market.jpg |

## 앱에 넣은 것(2026-10-01)

- 파일: `frontend/src/assets/hero/` - boseong-green-tea.webp(227KB) · jeonju-hanok.webp(196KB) · ktx-sancheon.webp(160KB) ·
  hwangnamguan-hanok-stay.webp(75KB) · gwangjang-market-jeon.webp(121KB),
  가로 1280px WebP(품질 64). 받기: `python tools/hero_photos.py --out-dir ../../../frontend/src/assets/hero`.
- 표: `frontend/src/components/heroPhotos.ts` - 사진 열쇠 → 파일 · 출처 문자열. 혜택 종류 → 주제는 `heroThemeOf`.
  사진을 바꾸거나 더하면 이 표, `tools/hero_photos.py` 의 PICKS, 이 문서의 '고른 사진' 표를 같이 고친다.
- 화면: 장 오른쪽 아래에 출처 문자열. 열쇠에 사진이 없으면 그 장은 혜택 형태 색 바탕.

## 더 할 일

- 같은 규칙으로 `region:` 16곳(서울·부산·…·제주, 전남 외)을 더 모은다(주제 네 가지는 다 채움).
  앱은 그날 데이터로 장이 바뀐다(10/1 마감 장 = 합천 외 9곳 반값여행, 지역 장 = 전남 - 지금 세 장으로 다 채워진다).
- CC BY-SA 사진을 줄이거나 자른 파일도 CC BY-SA 다 - 출처 문자열에 라이선스를 빼지 않는다.
