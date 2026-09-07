# 정책별 지역 사진 배정 설계

## 목표

정책 목록에서 같은 지역의 여러 정책이 동일한 대표 사진만 반복해서 사용하는 문제를 줄인다. 정책의 지역과 내용에 더 가까운 사진 후보를 수집하고, 정책별로 안정적으로 하나의 사진을 배정한다.

지역별 고유 사진을 억지로 만들지는 않는다. 관련 후보가 부족하면 기존 지역 대표 사진을 fallback으로 사용한다.

## 범위

포함:

- 정책별 사진 후보 수집 및 관련도 계산
- 정책별 최종 사진 배정 결과 저장
- 기존 `photo` API 응답 필드에 배정 결과 연결
- 정책 목록 카드의 확대된 사진 레이아웃 유지
- 재실행해도 같은 후보가 유지되는 멱등 백필

제외:

- 외부 이미지 파일 자체의 자체 저장소 이전
- 정책 상세 API 계약의 필드명 변경
- 지도 UI 변경
- TourAPI 수집·승격 정책 자체의 전면 개편

## 데이터 모델

기존 `region_photos`는 시도·시군 대표 사진과 fallback 용도로 유지한다. 정책별 결과는 별도 테이블에 저장한다.

```text
policy_photos
- id
- policy_id                 FK policies.id
- provider                  tour_api
- provider_content_id      외부 관광지 ID
- image_url
- thumbnail_url
- alt_text
- attribution_text
- relevance_score
- assignment_reason         city_match | policy_keyword | region_fallback
- status                    active | hidden
- fetched_at
- created_at
- updated_at
```

`policy_id`에 unique 제약을 두어 정책당 활성 배정은 하나만 유지한다. 기존 정책 데이터에는 사진이 없어도 유효하며, API는 현재처럼 `photo: null`을 허용한다.

## 후보 수집 및 배정

정책별 후보를 다음 순서로 수집한다.

1. 정책의 `region + city`로 TourAPI 지역 관광지를 조회한다.
2. 정책 제목에서 행정구역명과 일반 불용어를 제외한 핵심어를 추출해 키워드 검색한다.
3. 후보가 부족하면 시도 단위 관광지 목록을 조회한다.

후보 점수는 다음 우선순위를 따른다.

1. 주소가 정책의 시·군과 정확히 일치
2. 관광지 제목 또는 설명에 정책 핵심어가 포함
3. 같은 시·도에 속함
4. 이미지와 제목·주소가 모두 존재함

같은 정책의 후보는 `provider_content_id`와 이미지 URL을 기준으로 중복 제거한다. 최종 배정 시 같은 지역에서 이미 다른 정책에 배정된 URL을 우선 제외하지만, 남은 후보가 없으면 지역 대표 사진을 fallback으로 사용한다.

배정 결과는 DB에 저장하므로 새로고침·재배포·정책 정렬 변경에도 사진이 임의로 바뀌지 않는다.

## API 연결

`PolicyPhoto`의 기존 필드(`imageUrl`, `thumbnailUrl`, `alt`, `attribution`)는 유지한다.

정책 API 조립 순서:

1. active `policy_photos` 조회
2. 정책별 배정 사진이 있으면 사용
3. 없으면 기존 `region_photos` 지역·시도 fallback 사용
4. 둘 다 없으면 `photo: null`

API 계약 문서의 필드 변경은 없다. 내부 저장소와 조회 경로만 추가한다.

## 백필 멱등성

백필은 기본적으로 이미 active 배정이 있는 정책을 건너뛴다. `--refresh-older-than-days`를 사용한 경우에만 오래된 후보를 다시 평가한다.

재실행해도 다음이 보장되어야 한다.

- 같은 정책의 active 배정은 하나
- 후보가 변하지 않으면 image URL이 유지됨
- 실패한 정책은 전체 작업을 중단하지 않고 다음 정책으로 진행
- 후보가 없으면 기존 지역 fallback을 삭제하지 않음

## 화면 설계

정책 목록 카드의 현재 확대된 사진 영역을 유지한다.

- 데스크톱: 카드 왼쪽 `148 × 148px`
- 모바일: 카드 왼쪽 `112 × 112px`
- `object-fit: cover`
- 정책별 사진이 없으면 기존 아이콘 fallback
- 사진 출처 표시는 기존 정책 목록 출처 규칙을 유지

정책 상세 hero는 같은 `photo` 응답을 사용하므로 별도 UI 계약을 추가하지 않는다.

## 검증 계획

백엔드:

- 정책별 후보 점수와 우선순위 테스트
- 동일 URL 후보 제거 테스트
- 정책별 active 배정 unique 제약 테스트
- 정책 사진 우선, 지역 fallback, null 순서 테스트
- 백필 재실행 멱등성 테스트

프런트:

- 정책별 `photo` 렌더링 테스트
- 사진이 없을 때 아이콘 fallback 테스트
- 확대 카드 media 클래스와 이미지 `object-fit` 스타일 검증

운영 데이터:

- 기존 `region_photos`와 정책 링크 수를 백업 전후 비교
- 개발 격리 DB에서 먼저 백필
- 운영 DB 적용 전 정책별 중복 배정과 fallback 비율을 보고

## 위험과 완화

- TourAPI 후보가 부족해 관련 없는 사진이 선택될 위험: 점수 기준을 통과하지 못한 후보는 지역 fallback으로 낮춘다.
- 외부 URL 만료 위험: 현재 remote 저장 정책을 유지하되 `fetched_at`과 refresh 옵션으로 재수집한다.
- 기존 API 응답 회귀: `photo` 필드를 nullable로 유지하고 기존 지역 fallback 테스트를 보존한다.
- 마이그레이션 중 기존 정책 링크 영향: `policy_photos`는 추가 테이블만 생성하며 기존 정책·사용자 링크를 변경하지 않는다.
