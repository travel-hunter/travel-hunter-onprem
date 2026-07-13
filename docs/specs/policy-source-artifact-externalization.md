# 정책 수집 원문 Artifact 외부화 설계 착수

## 목적

정책 수집 파이프라인에서 원문 HTML, 파싱 중간 산출물, 화면용 정규화 결과의 책임을 분리한다. 단기에는 현재 DB 기반 동작을 유지하면서 수집/정규화/승격 책임을 명확히 하고, 장기에는 원문 artifact를 DB 밖 저장소로 옮겨 재파싱과 품질 검수를 쉽게 만든다.

## 현재 구조 요약

현재 외부 정책 수집 흐름은 다음 순서다.

1. `external_benefit_collection.py`
   - source registry에서 여행가는 달, 디지털관광주민증, 숙박/교통 혜택 URL을 순회한다.
   - HTML을 직접 fetch한다.
   - source별 parser를 호출한다.
2. parser 계층
   - `travelmonth_parser.py`
   - `travelmonth_stay_parser.py`
   - `travelmonth_traffic_parser.py`
   - `dgtourcard_parser.py`
   - HTML에서 `ExternalBenefitSource` 형태의 수집 record를 만든다.
3. `external_source_records`
   - parsed record를 DB에 upsert한다.
   - 현재 `raw_list_text`, `raw_detail_text`, `raw_payload`가 원문/중간 산출물/정규화 힌트를 함께 가진다.
4. `policy_normalization.py`
   - public 조건에 맞는 `external_source_records`를 `policies`로 승격한다.
   - `target_condition`, `benefit_detail`, `structured_detail`을 화면 표시용으로 재구성한다.
5. frontend
   - `policies` API의 `requirements`, `documents`, `structuredDetail`을 카드별로 렌더링한다.

## 문제 정의

현재 문제는 “원문 저장 위치” 하나만의 문제가 아니다.

- 수집 원문, parser 산출물, 화면 표시용 정규화 결과가 `external_source_records`와 `policies`에 섞여 있다.
- HTML fetch와 parse가 한 실행 경로에 붙어 있어, 같은 원문으로 재파싱/회귀 테스트를 반복하기 어렵다.
- 화면 카드 품질 문제를 고칠 때 원문, parser, DB record, policy 승격 결과 중 어느 책임인지 추적하기 어렵다.
- 원문 HTML을 DB text/json에 계속 쌓으면 DB가 커지고, 반대로 원문을 잃으면 나중에 parser 수정 시 재현성이 떨어진다.

## 목표 구조

장기 목표는 아래 네 층을 분리하는 것이다.

```text
Source Fetch
  -> Raw Artifact 저장
  -> Parser Snapshot 생성
  -> External Source Record upsert
  -> Policy Promotion / Display Normalization
```

각 층의 책임:

- Raw Artifact: HTML, response metadata, fetch 시각, URL, checksum을 보관한다.
- Parser Snapshot: parser가 추출한 필드와 parser version을 보관한다.
- External Source Record: 검색, 추천, 승격에 필요한 정규화 중간 record만 보관한다.
- Policy: 사용자 화면과 API에 필요한 최종 표시 계약만 보관한다.

## 단기 원칙: DB 유지 + 책임 분리

바로 object storage를 붙이지 않는다. 먼저 현재 DB 구조 안에서 책임을 분리한다.

1. fetch 결과를 `CollectedSourceArtifact` 개념으로 감싼다.
   - 초기 구현은 DB schema 변경 없이 dataclass/service boundary만 만든다.
   - 필드 예: `source_name`, `source_category`, `url`, `fetched_at`, `content`, `content_hash`, `content_type`.
2. parser 입력을 HTML string이 아니라 artifact로 바꿀 준비를 한다.
   - 첫 단계에서는 parser 함수 내부 시그니처를 모두 바꾸지 않고 adapter를 둔다.
3. parser 산출물과 policy 승격 산출물을 테스트 fixture로 고정한다.
   - 특히 `local_half_trip` 계열의 `requirements/documents/structuredDetail` 분리 규칙을 회귀 테스트로 유지한다.
4. `external_source_records.raw_*`는 당분간 유지한다.
   - 단, 의미를 “화면 표시 원문”이 아니라 “parser/debug snapshot”으로 문서화한다.

장점:

- 배포 위험이 낮다.
- 현재 운영 DB와 관리자 흐름을 크게 흔들지 않는다.
- 기존 회귀 테스트를 확장하기 쉽다.

단점:

- DB에는 여전히 raw text/json이 남는다.
- 대용량 원문 HTML 보존에는 적합하지 않다.
- fetch 원문 재현성은 artifact 저장소 도입 전까지 제한적이다.

## 장기 원칙: 원문 artifact 외부화

DB에는 artifact pointer와 checksum만 남기고, 원문 HTML/response body는 외부 저장소에 둔다.

후보 저장소:

- 로컬/서버 파일시스템 artifact directory
- S3 호환 object storage
- Cloudflare R2

DB에 남길 최소 정보:

- `artifact_key`
- `source_name`
- `source_category`
- `source_url`
- `fetched_at`
- `content_hash`
- `content_type`
- `byte_size`
- `parser_version`
- `parse_status`

장점:

- DB 크기와 책임이 줄어든다.
- 동일 원문으로 parser를 다시 돌릴 수 있다.
- 수집 실패/정규화 실패를 artifact 단위로 재현할 수 있다.
- 원문 보존 기간, 압축, 삭제 정책을 별도로 운영할 수 있다.

단점:

- 저장소 권한, 백업, retention, lifecycle 관리가 추가된다.
- DB와 artifact 저장소 간 정합성 문제가 생긴다.
- 개발/스테이징/운영 환경별 artifact 설정이 필요하다.
- 배포 전 보안/개인정보/저작권 보존 정책을 정해야 한다.

## 권장 단계

### 1단계: 수집 boundary만 분리

- `fetch_external_source_html()` 결과를 artifact 객체로 감싼다.
- live collection과 HTML fixture collection이 같은 parser entrypoint를 쓰게 만든다.
- DB schema 변경 없이 시작한다.

완료 기준:

- 기존 parser 테스트 통과
- `collect_external_benefits_from_html_sources()`와 live collection 모두 같은 artifact adapter 사용
- 정책 승격 결과 변화 없음

### 2단계: parser snapshot 테스트 강화

- source별 fixture를 “원문 입력 → parsed record → policy structuredDetail” 3단계로 검증한다.
- 강진/`local_half_trip` 계열처럼 카드 분류가 깨졌던 사례를 고정한다.
- `documents`가 `requirements`/`conditions` 카드로 섞이지 않는지 검증한다.

완료 기준:

- `local_half_trip` 다중 fixture 회귀 테스트
- `structuredDetail.conditions/documents/notices/periods` snapshot 검증
- `requirements`와 `documents` API 필드 중복/오분류 방지 검증

### 3단계: artifact 저장소 interface 도입

- `ArtifactStore` protocol을 만든다.
- 첫 구현은 local filesystem store로 둔다.
- 운영 object storage 구현은 나중에 붙인다.

예상 interface:

```python
class ArtifactStore(Protocol):
    def put(self, artifact: SourceArtifact) -> StoredArtifactRef: ...
    def get(self, key: str) -> SourceArtifact: ...
```

완료 기준:

- local filesystem 저장소로 원문 저장/조회 테스트
- 저장 실패 시 collection 전체 실패/부분 성공 정책 명확화
- secret/env 없이 로컬 테스트 가능

### 4단계: DB pointer migration

새 테이블 또는 `external_source_records` 확장 중 하나를 선택한다.

권장안은 별도 테이블이다.

```text
external_source_artifacts
- id
- source_name
- source_category
- source_url
- artifact_key
- content_hash
- content_type
- byte_size
- fetched_at
- parser_version
- parse_status
- created_at
```

`external_source_records`는 `source_artifact_id`만 참조한다.

완료 기준:

- Alembic migration
- artifact ref와 parsed record 정합성 테스트
- 기존 raw fields 제거 여부는 별도 단계로 결정

### 5단계: raw field 축소 또는 제거

원문 artifact 외부화가 안정화된 뒤에만 진행한다.

선택지:

- `raw_list_text`, `raw_detail_text`, `raw_payload` 유지하되 summary/debug snapshot으로 축소
- 원문성 필드는 제거하고 parser snapshot만 남김
- 일정 기간 dual-write 후 제거

완료 기준:

- 개발서버에서 artifact 조회/재파싱 smoke 완료
- 운영 retention 정책 확정
- raw field 제거 migration 전 백업/복구 계획 확정

## 다음 작업 체크리스트

- [ ] `SourceArtifact` / `StoredArtifactRef` dataclass 초안 작성
- [ ] live HTML fetch와 fixture HTML collection의 공통 adapter 설계
- [ ] 강진 `local_half_trip` 원문 fixture 위치 확인
- [ ] parser snapshot 테스트 범위 확정
- [ ] artifact 저장소 후보를 local filesystem 우선으로 고정할지 결정
- [ ] DB pointer를 별도 테이블로 둘지, `external_source_records` 확장으로 둘지 비교
- [ ] artifact retention 정책 초안 작성

## 지금은 하지 않는 것

- 관리자 UI 대개편
- 운영 object storage 즉시 도입
- 기존 raw DB 필드 즉시 삭제
- 수집 scheduler 동작 변경
- 정책 slug 체계 변경
- public API shape 변경

## 첫 구현 후보

가장 안전한 첫 PR은 다음 범위다.

1. `SourceArtifact` dataclass 추가
2. `fetch_external_source_html()`을 artifact 생성 함수로 감싸기
3. 기존 parser 호출은 adapter로 유지
4. `local_half_trip` fixture 기반 parser/structuredDetail 회귀 테스트 추가
5. behavior change 없음 확인

이 범위는 DB migration 없이 구조만 분리하므로 개발서버 반영 위험이 낮다.
