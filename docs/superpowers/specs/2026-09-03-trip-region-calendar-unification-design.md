# 일정 지역·기간 선택 통합 설계

## 배경

현재 일정 생성 화면의 세부 지역은 전국 행정구역 카탈로그가 아니라 `backend/app/data/travel_areas.py`에 수동 등록된 관광권역을 사용한다. 제주에는 `제주 전체`, `제주 동부`, `제주 서부`, `서귀포`가 있지만 다른 광역시도는 일부 권역만 있어 사용자가 무엇을 기준으로 고르는지 알기 어렵고 선택 가능한 지역도 불완전하다.

일정 편집 화면은 제목과 날짜만 변경할 수 있다. 저장된 `travelAreaId`를 다른 지역으로 바꿀 UI와 API 계약이 없으므로 `제주 동부` 일정을 `제주 서부`로 변경할 수 없다. 날짜 편집도 일정 생성의 범위 달력과 달리 네이티브 날짜 입력 두 개를 사용한다.

## 목표

- 세부 지역의 기본 기준을 전국 행정 시·군·구 카탈로그로 명확히 정의한다.
- 행정구역과 관광 동선을 묶은 추천 여행권역을 서로 다른 그룹으로 표시한다.
- 일정 생성과 일정 편집에서 같은 지역 선택기를 사용한다.
- 기존 일정의 지역을 복원하고 다른 세부 지역이나 추천 여행권역으로 변경할 수 있게 한다.
- 일정 생성과 일정 편집에서 같은 날짜 범위 달력을 사용한다.
- 기간 축소 시 제외되는 날짜의 장소 처리 규칙은 현재 동작을 유지한다.

## 범위 밖

- 프로필 관심 지역 선택기와 정책 목록 지역 필터를 이번 작업에서 바꾸지 않는다.
- 기존 일정의 지역을 일괄 변환하는 데이터 마이그레이션을 하지 않는다.
- 행정구역을 런타임 외부 API에서 매 요청마다 내려받지 않는다.
- 지역 변경 시 기존 장소나 연결 정책을 자동 삭제하지 않는다.
- 추천 여행권역을 자동 생성하거나 관리자 UI에서 편집하는 기능을 추가하지 않는다.

## 지역 분류 기준

### 기본 행정지역

행정지역은 다음 단위로 제공한다.

- 도: 시·군
- 광역시: 자치구·군
- 제주: 제주시·서귀포시
- 세종: 하위 시·군·구 없이 `세종 전체`
- 일반시 산하 일반구: 제외

현재 제품 계약의 17개 광역시도 버튼은 유지한다. 각 광역시도에는 `전체` 선택지를 항상 제공한다.

행정지역 스냅샷의 기준 원천은 행정안전부 [행정표준코드관리시스템](https://www.code.go.kr/indexFrame.do)과 [전체자료 다운로드](https://www.code.go.kr/stdcodesrch/codeAllDownloadL.do)다. 저장소에는 애플리케이션에 필요한 광역시도·시군구만 정규화한 UTF-8 정적 카탈로그와 원천 확인일을 함께 둔다. 외부 서비스 장애가 일정 생성에 영향을 주지 않도록 런타임 네트워크 호출은 하지 않는다.

### 추천 여행권역

`제주 동부`, `제주 서부`, `속초·고성·양양`처럼 여행 동선을 묶은 기존 `TRAVEL_AREAS`는 유지한다. 다만 행정지역과 같은 목록에 섞지 않고 `추천 여행권역` 그룹에서만 보여준다.

광역 전체를 의미하는 기존 `*-all` 권역은 새 `전체` 선택지와 중복 표시하지 않는다. 기존 일정이 이 ID를 저장하고 있으면 호환 해석은 유지하되 새 선택에서는 canonical `whole` ID를 사용한다.

### 안정적인 식별자

지역 ID는 클라이언트가 분석하지 않는 opaque string으로 취급한다.

- 전체: `whole:{urlencoded-sido}`
- 행정지역: `admin:{urlencoded-sido}:{urlencoded-locality}`
- 추천 여행권역: 기존 ID 유지, 예: `jeju-east`, `jeju-west`
- 정책 기반 동적 권역: 기존 `policy-region:{urlencoded-sido}:{urlencoded-city}` 호환 유지

표시 이름이 바뀌어도 ID가 같으면 기존 일정 연결이 유지된다.

## 백엔드 구조

### 카탈로그 데이터

`backend/app/data/administrative_areas.py`가 광역시도별 행정지역과 원천 메타데이터를 소유한다. 기존 `backend/app/data/travel_areas.py`는 추천 여행권역 정의를 계속 소유한다.

`backend/app/services/travel_area_catalog.py`가 두 원천을 합쳐 선택용 카탈로그를 만든다. 기존 추천 점수 계산 API는 전체 행정지역 때문에 결과와 성능이 바뀌지 않도록 기존 추천 여행권역만 사용한다.

`get_travel_area()`는 기존 추천권역, 새 전체/행정지역, 기존 정책 기반 동적 ID를 모두 해석하도록 확장한다. 일정 생성과 편집 서비스는 같은 resolver를 사용한다.

### 선택용 API

새 엔드포인트를 추가한다.

```http
GET /api/travel-areas?sido=제주
```

응답 예시:

```json
{
  "sido": "제주",
  "sourceAsOf": "2026-09-03",
  "wholeArea": {
    "travelAreaId": "whole:%EC%A0%9C%EC%A3%BC",
    "travelAreaName": "제주 전체",
    "sido": "제주",
    "areaType": "whole",
    "includedCities": ["제주"]
  },
  "recommendedAreas": [
    {
      "travelAreaId": "jeju-east",
      "travelAreaName": "제주 동부",
      "sido": "제주",
      "areaType": "recommended",
      "includedCities": ["제주", "서귀포"]
    }
  ],
  "administrativeAreas": [
    {
      "travelAreaId": "admin:%EC%A0%9C%EC%A3%BC:%EC%A0%9C%EC%A3%BC%EC%8B%9C",
      "travelAreaName": "제주시",
      "sido": "제주",
      "areaType": "administrative",
      "includedCities": ["제주"]
    },
    {
      "travelAreaId": "admin:%EC%A0%9C%EC%A3%BC:%EC%84%9C%EA%B7%80%ED%8F%AC%EC%8B%9C",
      "travelAreaName": "서귀포시",
      "sido": "제주",
      "areaType": "administrative",
      "includedCities": ["서귀포"]
    }
  ]
}
```

지원하지 않는 `sido`는 422가 아니라 400 `Unsupported travel area sido`로 응답한다. 등록된 광역시도는 항상 `wholeArea`를 반환하며 추천권역이나 하위 행정지역이 없으면 해당 배열만 비어 있다.

### 일정 응답과 수정 계약

`Trip` 응답에 저장된 표시 지역을 명시하는 `region: string`을 추가한다. 기존 `travelAreaId`는 유지한다.

`PATCH /api/trips/{tripId}/settings` 요청에 선택 필드 `travelAreaId`를 추가한다.

```json
{
  "expectedRevision": 4,
  "title": "제주 서부 여행",
  "travelAreaId": "jeju-west",
  "startDate": "2026-09-10",
  "endDate": "2026-09-12",
  "overflowPlaceStrategy": "moveToLastDay"
}
```

`travelAreaId`가 전달되면 backend는 catalog resolver로 ID를 검증하고 `trips.travel_area_id`와 `trips.region`을 한 트랜잭션에서 함께 갱신한다. 알 수 없는 ID는 400 `Travel area not found`로 거부한다. 필드가 생략되면 기존 지역을 유지한다.

지역 변경은 기존 일정 장소, 일정 Day, 연결 정책을 변경하지 않는다. 저장 이후 장소 검색과 추천은 갱신된 지역을 사용한다.

## 프론트엔드 구조

### 공통 지역 선택기

`frontend/src/components/trip/TripRegionSelector.tsx`를 생성과 편집에서 함께 사용한다.

선택 흐름은 다음과 같다.

1. 17개 광역시도 중 하나를 선택한다.
2. 해당 광역시도의 선택용 카탈로그를 요청한다.
3. `전체`, `추천 여행권역`, `시·군·구` 순서로 그룹을 표시한다.
4. 사용자는 정확히 하나의 `travelAreaId`를 선택한다.

`전체`도 명시적인 세부 선택으로 취급한다. 따라서 광역시도 버튼만 누르고 다음 단계로 진행할 수 없으며, 사용자는 `전체` 또는 구체적인 지역/권역을 선택해야 한다.

카탈로그 로딩 중에는 기존 선택을 지우지 않는다. 요청 실패 시 오류와 재시도 버튼을 표시하고 다음 진행 또는 저장을 막는다. 결과가 많아도 누락되지 않도록 추천 API의 `limit=20`을 재사용하지 않는다.

일정 생성 화면은 현재 지역 상태와 URL 사전 선택 로직을 공통 선택기 어댑터로 옮긴다. 정책 링크나 홈 추천에서 넘어온 `travelAreaId`는 해당 항목을 선택하고, 광역시도만 넘어오면 사용자가 그 안의 항목을 고르게 한다.

일정 편집 화면은 `trip.travelAreaId`로 먼저 현재 선택을 복원한다. ID가 없는 레거시 일정은 `trip.region`과 정확히 일치하는 선택지를 찾고, 찾지 못하면 해당 광역시도의 `전체`를 화면 기본값으로 보여주되 사용자가 저장하기 전에는 DB를 변경하지 않는다.

지역을 변경해도 사용자가 작성한 일정 제목은 자동으로 덮어쓰지 않는다. 생성 화면에서 아직 직접 편집하지 않은 자동 제목만 현재 규칙대로 새 지역에 맞춰 바뀐다.

### 공통 날짜 범위 달력

`frontend/src/components/trip/TripDateRangePicker.tsx`를 controlled component로 만든다.

```ts
type TripDateRangeValue = {
  startDate: string;
  endDate: string;
};

type TripDateRangePickerProps = {
  value: TripDateRangeValue;
  onChange: (value: TripDateRangeValue) => void;
  disabled?: boolean;
  error?: string;
};
```

생성 화면의 날짜 파싱, 월 계산, 42칸 달력 구성, 범위 포함 판정, 역순 정규화 로직을 `frontend/src/utils/tripDateRange.ts`로 이동한다. 생성과 편집은 같은 컴포넌트와 유틸리티를 사용한다.

상호작용은 현재 생성 화면을 기준으로 한다.

- 날짜 요약 카드를 누르면 달력이 열린다.
- 시작일과 종료일을 차례로 선택한다.
- 선택 범위를 달력에서 강조한다.
- 종료일을 시작일보다 앞서 선택하면 날짜를 정방향으로 정규화한다.
- 이전 달과 다음 달로 이동할 수 있다.
- 완료 버튼으로 달력을 닫는다.

직접 편집 화면의 네이티브 `date` 입력 두 개는 제거한다. 일정 상세 안의 `여행기간 수정` 시트도 같은 공통 날짜 범위 선택기를 사용해, 생성 화면·직접 편집 화면·상세 편집 시트의 달력 동작을 하나로 맞춘다. 기간 축소로 사라지는 Day에 장소가 있으면 기존 `moveToLastDay` 또는 `delete` 선택 UI를 그대로 표시한다.

## 접근성·반응형

- 광역시도와 세부 지역 버튼은 선택 상태를 `aria-pressed`로 제공한다.
- 지역 그룹은 제목과 연결된 section 또는 fieldset으로 구분한다.
- 달력 dialog는 현재 선택 범위와 시작/종료 선택 단계를 안내한다.
- 키보드로 지역 선택, 달력 월 이동, 날짜 선택, 완료가 가능해야 한다.
- 360, 390, 430px에서는 지역 버튼이 잘리지 않고 세로 스크롤로 모두 접근 가능해야 한다.
- 1024, 1440px에서는 카탈로그가 과도하게 긴 한 열이 되지 않도록 기존 카드 grid를 재사용한다.

## 오류·동시성 처리

- 지역 카탈로그 조회 실패: 현재 선택 유지, 오류 문구와 재시도 제공, 저장 차단
- 잘못된 `travelAreaId`: backend 400, 편집 폼 오류로 표시
- 일정 revision 충돌: 기존 409 처리 유지
- 날짜 범위 오류: frontend에서 저장 차단하고 backend validator도 동일 규칙을 적용
- 기간 축소 장소 처리 누락: backend의 기존 필수 전략과 검증 유지

## 하위 호환성

- DB의 `trips.region`, `trips.travel_area_id` 컬럼을 그대로 사용하므로 Alembic 마이그레이션은 없다.
- 기존 추천 여행권역 ID와 정책 기반 동적 ID는 계속 해석한다.
- `Trip.region`은 응답 필드 추가이므로 기존 클라이언트를 깨지 않는다.
- `UpdateTripSettingsRequest.travelAreaId`는 선택 필드이므로 기존 편집 요청을 깨지 않는다.
- 기존 일정은 조회만으로 자동 변환하지 않는다.

## 테스트 전략

### Backend

- 행정 카탈로그가 제품의 17개 광역시도를 모두 포함하는지 검사한다.
- 각 광역시도에 `wholeArea`가 정확히 하나인지 검사한다.
- 행정지역 ID와 표시 이름이 광역시도 내에서 중복되지 않는지 검사한다.
- 대표 누락 회귀 사례로 경기, 강원, 전남의 기존 미등록 시·군이 응답되는지 검사한다.
- 제주 응답에서 `제주 동부/서부`는 추천권역, `제주시/서귀포시`는 행정지역으로 분리되는지 검사한다.
- 일정 생성과 편집이 전체/행정/추천/정책 동적 ID를 같은 resolver로 검증하는지 검사한다.
- 지역 변경 시 `region`과 `travel_area_id`가 함께 갱신되고 장소·정책 연결은 보존되는지 검사한다.

### Frontend

- 광역시도 선택 후 전체, 추천 여행권역, 시·군·구 그룹을 모두 표시하는지 검사한다.
- 목록이 20개를 넘는 지역에서도 모든 행정지역이 표시되는지 검사한다.
- 생성 화면이 선택한 `travelAreaId`를 `createTrip`에 보내는지 검사한다.
- 편집 화면이 기존 `jeju-east`를 복원하고 `jeju-west`로 바꿔 `updateTripSettings`에 보내는지 검사한다.
- 레거시 `travelAreaId=null` 일정의 지역 복원 fallback을 검사한다.
- 생성과 편집에서 같은 달력으로 정방향·역방향 날짜 범위를 선택하는지 검사한다.
- 기간 축소 시 기존 장소 처리 선택 UI가 계속 동작하는지 검사한다.
- viewer는 지역과 날짜를 수정할 수 없는 기존 권한 규칙을 유지하는지 검사한다.

### 계약·릴리스 검증

- backend schema/route/service/repository 테스트
- frontend API serialization 테스트
- `docs/mvp-api-contract.md`, `docs/requirements.md`, `docs/implemented-feature-spec.md` 동기화
- `npm run typecheck`, 대상 Vitest, 전체 frontend test, backend pytest, frontend build
- 5173에서 생성·편집 지역 변경과 날짜 범위 달력 수동 확인
- 360×780, 390×844, 430×932, 1024×768, 1440×900 반응형 확인

## 완료 조건

- 모든 광역시도에서 정의된 행정 단위가 누락 없이 선택 가능하다.
- 행정지역과 추천 여행권역의 구분이 화면에 명시된다.
- 제주 동부 일정을 편집해 제주 서부로 저장할 수 있다.
- 일정 생성과 편집의 날짜 범위 선택 동작과 표현이 동일하다.
- 지역 변경 후 일정 추천과 장소 검색이 새 지역을 기준으로 동작한다.
- 기존 장소, 연결 정책, 권한, revision, 기간 축소 처리 동작에 회귀가 없다.
