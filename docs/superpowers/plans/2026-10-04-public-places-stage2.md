# 카카오 장소값 2단계 - 공공데이터 장소 기반(`public_places`) 구현 계획

> **에이전트 작업자용:** 이 계획은 superpowers:subagent-driven-development(권장) 또는 superpowers:executing-plans로 과제별로 실행한다. 단계는 체크박스(`- [ ]`)로 추적한다.

**목표:** 카카오 값 없이 장소를 담을 수 있도록 공공데이터로 우리 장소 기반을 만든다. 표 `public_places`, TourAPI 주 1회 동기화, 상가정보 적재 스크립트, 맞춰 보기 API(`POST /api/places/match`)를 더하고, `debug_capture`가 장소 경로를 늘 빼게 한다. 화면은 바뀌지 않는다.

**구조:** `public_places`는 (출처, 출처 ID)를 기본키로 하는 공공데이터 장소 표이고, `public_place_sync_state`는 출처마다 마지막 시도(시작 전에 `running`으로 남긴다)와 끝까지 받은 마지막 시각을 둔다. 이름 정규화 · 행 만들기 · 적재 · 맞춰 보기는 `services/public_places.py`, DB 쿼리는 `repositories/public_places.py`에 둔다. TourAPI는 기존 클라이언트에 결과 코드 · `totalCount`를 확인하는 전국 목록 한 페이지 메서드를 더하고, DB 상태로 때를 가리는 작은 반복 작업으로 주 1회 동기화한다(따로 켜는 설정, 기본 꺼짐). 상가정보는 분기 zip을 한 줄씩 읽는 스크립트로 넣는다. 오래된 행은 단위(TourAPI 유형 · 상가정보 시도)마다 끝까지 받았는지 확인한 뒤 통과한 단위만 지운다. 맞춰 보기는 위경도 상자 조회 뒤 서버 메모리에서 이름 · 분류를 견주고 버린다.

**기술:** FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL(시험은 SQLite) · httpx · React/TypeScript(API 경계만)

**설계:** `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`(develop 반영됨). 1절 '데이터', 2절의 맞춰 보기 규칙, 배포 순서 2단계를 구현한다. 이 계획에서 정한 차이(카카오 ID를 보내지 않음, 출처별 반경, 두 출처 같은 이름 · 분류가 다르거나 모르면 후보, 단위별 지우기, 동기화 상태)는 과제 7에서 설계 문서에 반영한다. 1단계는 PR #89로 머지됐다.

## 전체 제약

- 카카오 로컬 API 응답의 장소명 · 주소 · 좌표 · 전화번호는 DB · 로그 · 주소(URL)에 남기지 않는다. 맞춰 보기는 받은 값을 서버 메모리에서만 견주고 버린다.
- 카카오 값을 외부로 보내지 않는다. 공공 API 질의도 포함한다. 공공데이터를 우리 DB에 받아 두고 서버 안에서 비교한다.
- `public_places` 행은 TourAPI 6개 유형(12 관광지 · 14 문화시설 · 28 레포츠 · 32 숙박 · 38 쇼핑 · 39 음식점) 전체와 상가정보 대분류 음식(`I2`) · 숙박(`I1`) · 예술·스포츠(`R1`)뿐이다. 소매 · 교육 · 부동산 같은 업종은 넣지 않는다.
- 열: 출처(`tourapi`·`sangga`), 출처 ID(contentid · 상가업소번호), 이름, 비교용 이름, 주소, 위도 · 경도, 분류, 시도 · 시군, 사진 URL · 저작권 유형(TourAPI만), 갱신 시각. 색인: (출처, 출처 ID) 고유, 위도 · 경도 범위 조회, 비교용 이름. 분류 값은 7개로 DB · API · TS 모두 고정한다.
- 갱신: TourAPI는 주 1회(약 50회 호출, 개발 계정 하루 1,000회). 상가정보는 분기 파일. **서버 적재는 실행할 때마다 승인받는다.**
- **오래된 행은 단위마다 끝까지 받았다는 증거가 있을 때 그 단위만 지운다.**
  - TourAPI 단위는 유형이다. 페이지마다 `totalCount`가 같고, 받은 항목 수와 고유 contentid 수가 모두 `totalCount`와 같고, 그 유형의 이번 고유 행이 기존의 80% 이상이어야 한다.
  - 상가정보 단위는 시도다. 파일을 끝까지 읽었고, 그 시도의 이번 고유 행이 기존의 80% 이상이어야 한다. 읽은 시도는 여행 업종이 아닌 줄까지 포함해 정한다(0건이 된 시도도 알아보게).
  - 하나라도 통과하지 못한 단위가 있거나, DB에 있는데 이번에 읽지 않은 시도가 있으면 `partial`이다. 통과한 단위만 지운다.
- 행의 `synced_at`(행 갱신 시각)과 출처의 시도 · 성공 기록(`public_place_sync_state`)은 따로 둔다. 시도는 첫 호출 전에 `running`으로 남긴다. 자동 동기화는 오늘(KST) 이미 시도했으면 쉬고, 마지막 성공이 7일 안이면 쉰다.
- 맞춰 보기 반경: 카카오 분류가 관광명소 · 문화시설(`AT4` · `CT1`)이면 TourAPI 장소는 1km, 그 밖과 상가정보 장소는 200m.
- 바로 담기(`match`)는 반경 안에 이름이 같은 공공데이터 장소가 **하나뿐이고 분류가 맞을 때만**이다. 두 출처에 같은 이름이 함께 있으면 둘로 센다. 카카오 분류가 없거나 아래 표에 없는 코드면 분류가 맞는지 모르므로 후보다.
- 이름 비교는 2026-10-03 실측과 같다: 소문자로 바꾸고 `[\s\-·・()\[\]{}<>.,'"/&+_~!?:;|]` 를 뺀다. '포함'은 두 이름이 모두 두 글자 이상일 때만 센다.
- `debug_capture`는 장소 경로를 설정과 무관하게 늘 뺀다(`ALWAYS_EXCLUDED_MARKERS`에 `place`).
- Alembic `0048`은 표와 nullable 열을 더하기만 한다. 앞 버전 코드가 그대로 돈다.
- 새 API는 `docs/mvp-api-contract.md` · `.agent/evals/api-contract-golden.json` · 프론트 타입 · `AppDataApi`를 함께 고친다. 화면은 바꾸지 않는다(3단계).
- 비밀값은 출력하지 않는다. TourAPI 키는 클라이언트가 이미 오류 문구에서 뺀다. 스크립트 · 상태 표에는 건수와 짧은 이유만 남긴다. `docker inspect`는 `--format`으로 라벨만 본다.
- 로컬 DB를 바꾸기 전에는 `.codex/skills/travel-hunter-workflow/SKILL.md` 4절을 따른다: `pg_dump -Fc` 덤프(저장소 밖, 600, 폴더 700) → `pg_restore -l` 검증 → SHA-256 기록 → `policies` · `trips` · `users` · `external_source_records` 행 수 전후 비교(30% 넘게 변하면 멈추고 보고). `db` · `backend` · `frontend` 세 컨테이너는 같은 워크트리에서 띄운다.
- 한글 파일은 UTF-8로 유지한다. 바꾼 diff에 U+FFFD가 없어야 하고 `git diff --check`를 통과해야 한다.
- 커밋은 과제마다 하지 않는다. 과제 8에서 전체 검증 뒤 사용자 승인을 받아 한다. 푸시와 PR은 따로 승인받는다. PR base는 develop이고 머지하지 않는다.

## 계획에서 정한 것

설계가 계획에 맡겼거나 글자만으로는 갈리는 것이다. 코덱스 검토 두 번(2026-10-04)을 반영했다.

1. `0048`에 `public_places`와 함께 `trip_places`의 출처 열(`place_origin` · `public_source` · `public_source_id` · `photo_url` · `photo_license`)을 더한다. 설계 1절 문구대로다. 2단계에서는 쓰지 않고 3단계 담는 흐름부터 채운다.
2. 상가정보는 반경을 늘 200m로 본다(실측 기준). 분류별 반경(1km)은 TourAPI에만 쓴다. 바로 담기에는 분류가 맞는지도 본다: 관광명소 → `sight` · `culture` · `leisure` · `shopping`, 문화시설 → `culture` · `sight` · `leisure`, 음식점 · 카페 → `food` · `cafe`, 숙박 → `stay`. 분류가 없거나 이 다섯 코드가 아니면 맞는지 알 수 없으므로 후보다.
3. TourAPI와 상가정보에 같은 이름이 함께 있으면 같은 곳으로 단정하지 않고 둘로 센다 - 후보 확인이다. 그래서 바로 담기 비율은 실측 63%보다 낮다. 3단계에서 실데이터로 다시 재고, 분류 · 주소까지 맞을 때 하나로 보는 규칙은 그때 정한다.
4. 상가정보 이름은 '상호명 + 지점명' 하나로 비교한다. 지점명 없는 카카오 이름('스타벅스')은 '포함' 후보가 된다.
5. 맞춰 보기 요청은 카카오 장소 ID를 받지 않는다(비교에 쓰지 않는다). 설계 문서를 이에 맞춘다(과제 7).
6. TourAPI 주 1회 동기화는 정책 수집 스케줄러와 같은 꼴(앱 수명 주기의 asyncio 작업 + 켜는 설정 + `RUN_AT` + 폴링)이지만, 그 클래스를 빌려 쓰지 않고 때를 DB 상태로 가린다. 폴링마다 `tourapi_sync_due`가 'KST로 `RUN_AT` 뒤 · 오늘 아직 시도하지 않음 · 마지막 성공이 7일 넘음'을 모두 만족할 때만 받는다. 시도는 첫 호출 전에 `running`으로 남겨, 앱을 다시 띄우거나 도중에 죽어도 그날은 다시 하지 않는다(할당량). 일부 · 오류는 다음 날 다시 받는다. `PUBLIC_PLACES_SYNC_ENABLED`로 따로 켜고 기본은 꺼짐이다. 손으로 돌리는 스크립트는 때를 가리지 않고, `partial`이면 종료 코드 2, 오류면 1이다.
7. 오래된 행 지우기는 단위별이다. TourAPI는 유형마다(받은 항목 · 고유 contentid가 `totalCount`와 정확히 같고 페이지마다 `totalCount`가 같으며 이번 고유 행이 기존의 80% 이상), 상가정보는 시도마다(파일을 끝까지 읽었고 이번 고유 행이 기존의 80% 이상) 본다. 통과한 단위만 지운다. 일부 시도만 넣는 `--only`는 지우지 않는다. 지우지 못한 단위는 결과의 `kept`(예: `39:10000->7000`, `39:incomplete`, `세종:missing`)로 드러난다. 끝까지 받았는데 80% 미만이면 운영자가 원인을 확인한 뒤 손 스크립트 `--accept-shrink`로 그 단위만 80% 기준 없이 지운다. 끝까지 받지 못한 단위와 파일이 빠진 시도는 받아들여도 지우지 않는다(최종 검토 뒤 사용자 결정, 2026-10-04).
8. 분류 코드는 `sight`(관광지) · `culture`(문화시설, 상가정보 도서관·사적지) · `leisure`(레포츠, 상가정보 예술·스포츠) · `stay` · `shopping` · `food` · `cafe`(TourAPI 소분류 `A05020900`, 상가정보 중분류 `I212` 비알코올)다. DB CHECK · Pydantic `Literal` · TS 유니언으로 고정한다. TourAPI 유형은 분류로 그대로 갈린다(39만 `food` · `cafe`). 3단계 추천 카드가 쓴다.
9. 행의 `synced_at`은 그 행을 마지막으로 넣거나 고친 시각(UTC)이다. 출처의 시도 · 성공 기록은 `public_place_sync_state`에 따로 둔다(`running` · `success` · `partial` · `error`, 성공만 `last_success_at`을 바꾼다).
10. 위도 · 경도는 `Float`(double precision)로 둔다. 상자 조회 색인을 그대로 쓰기 위해서다. 로컬 실측과 개발서버 적재 뒤 `EXPLAIN`으로 색인을 쓰는지 본다.

## 검토 초점

1. 단위마다 끝까지 받았다는 증거가 없으면 그 단위를 지우지 않는지 - 앞 페이지 성공 뒤 실패, `totalCount`보다 적게 온 유형, 한 유형만 0건, 같은 페이지가 두 번 온 경우, 결과 코드 오류, 한 시도만 급감, 시도 파일이 빠진 판, 읽다 깨진 파일. 과제 4 · 5가 시험한다.
2. 같은 ID가 묶음 경계 · 두 파일에 다시 와도 '고유 행 수' 판정이 부풀지 않는지. 과제 4 · 5가 시험한다.
3. 맞춰 보기: 두 출처 같은 이름은 후보, 분류가 다르거나 모르면 후보, 같은 이름 체인점, 한 글자 · 기호뿐인 이름, 반경 바로 안쪽(상자 끝). 과제 6이 시험한다.
4. 맞춰 보기 요청의 이름이 로그 · DB · debug capture 어디에도 남지 않는지. 과제 6이 시험한다.
5. 자동 동기화: 기본 꺼짐, `RUN_AT` 전에는 쉼, 오늘 이미 시도했으면 재기동 · 도중 죽음에도 쉼, 일부 · 오류 다음 날 다시, 성공 뒤 7일. 과제 4가 시험한다.

## 코덱스 검토 반영(2026-10-04)

첫 검토:
- HIGH 반영: TourAPI 결과 코드 · `totalCount` 확인, 고유 행 수 판정, 출처별 동기화 상태 표와 성공 시각 분리, 두 출처 자동 병합 철회.
- MEDIUM 반영: 설계 문서 맞추기(과제 7), 시험 DB `StaticPool` · `check_same_thread=False`, 상자를 거리 함수와 같은 지구 반경으로(여유 1%) + 반경 바로 안쪽 경계 시험, 분류 값 범위 고정 + 묶음 경계 중복 시험.

재검토:
- HIGH 반영: 지우기를 단위별로 - TourAPI 유형마다 `totalCount` 일관성 · 받은 수 · 고유 ID 수 · 80%, 상가정보 시도마다 80%(읽은 시도는 모든 줄로 정함), 빠진 시도는 `partial`. 로컬 DB 백업 게이트(`pg_restore -l` 검증 · SHA-256 · `external_source_records` 포함 행 수 비교).
- MEDIUM 반영: 시도를 첫 호출 전에 DB에 `running`으로 남기고 '오늘(KST) 이미 시도'를 DB로 가림(재기동 · 도중 죽음에도 같은 날 다시 하지 않음), 정책 수집 스케줄러 클래스를 빌려 쓰지 않고 DB 상태로 가리는 반복 작업으로 바꿈(오류를 '완료'로 남기지 않음), 분류가 없거나 모르면 후보, 자동 동기화를 켤 때 운영자 주간 점검 절차.
- LOW 반영: 받은 항목 수를 페이지마다 누적.
- 반영하지 않음: 운영자에게 닿는 오류 알림. 에러 알림 작업은 사용자가 보류했다. 대신 실패 · 일부는 다음 날 자동으로 다시 받고, 로그(`public_places_sync_failed` · `public_places_prune_limited` · `public_places_sync_finished`), 상태 표, 운영자 주간 점검으로 드러난다.

자체 점검(재검토 반영 뒤): 맞춰 보기 라우트는 다른 라우트처럼 `get_optional_db`(로그인 확인과 같은 세션)로 받는다. 7일은 날짜(KST)로 세어 매주 실행 시각이 밀리지 않게 했다. 쓰이지 않던 `commit` 인자를 없앴다 - 늘 묶음마다 확정한다(끄면 '첫 호출 전에 남긴 시도'가 지켜지지 않는다).

최종 검토(구현 뒤, 새 검토자): Critical - TourAPI 키가 오류 로그에 남는다(공용 로그 함수가 `raise ... from None`으로 숨긴 맥락을 따라가고, 가리기가 `serviceKey=`를 놓친다). `app/core/logging.py`에서 고치고 회귀 시험 3개를 더했다. 개발서버 로그에서 2026-10-02 사진 후보 수집 실패 한 줄에 지금 키가 남은 것을 확인해(개수 · 같은지만 셌다) 키 교체를 보고했다. Important - 손 복구가 실제로 줄어든 단위를 지우지 못한다 → `--accept-shrink`와 `kept` 요약(사용자 결정). Minor 9건은 CHECKLIST 위험과 다음 단계로 넘겼다.

---

### Task 1: 표와 마이그레이션

**파일:**
- 고치기: `backend/app/models/tables.py`(import, `TripPlace`, 새 `PublicPlace` · `PublicPlaceSyncState`), `backend/app/models/__init__.py`
- 만들기: `backend/alembic/versions/0048_public_places.py`
- 고치기: `backend/tests/test_db_schema.py`, `docs/db-schema-current.md`, `docs/db-schema-current.sql`

**인터페이스:**
- 내놓는 것: 모델 `PublicPlace`, `PublicPlaceSyncState`(`app.models`에서 import). `PublicPlace` 열 `source`(PK) · `source_id`(PK) · `name` · `name_key` · `address` · `latitude` · `longitude` · `category` · `sido` · `city` · `photo_url` · `photo_license` · `synced_at`. `PublicPlaceSyncState` 열 `source`(PK) · `last_attempt_at` · `last_outcome`(`running`/`success`/`partial`/`error`) · `last_success_at` · `received_count` · `written_count` · `pruned_count` · `last_error`. `TripPlace`의 새 열 5개.

- [ ] **1단계: 실패하는 시험 쓰기** - `backend/tests/test_db_schema.py`

`test_current_schema_tables_are_registered`의 `expected_tables`에 `"public_places",`와 `"public_place_sync_state",`를 `"photo_review_candidates",` 다음 줄에 더한다. 파일 끝에 아래를 더한다.

```python
def _check_names(table: sa.Table) -> set[str]:
    return {constraint.name for constraint in table.constraints if constraint.__class__.__name__ == "CheckConstraint"}


def test_public_places_table_is_registered() -> None:
    places = Base.metadata.tables["public_places"]
    assert [column.name for column in places.primary_key.columns] == ["source", "source_id"]
    for column in ("name", "name_key", "latitude", "longitude", "category", "synced_at"):
        assert places.c[column].nullable is False
    for column in ("address", "sido", "city", "photo_url", "photo_license"):
        assert places.c[column].nullable is True
    index_columns = {index.name: [column.name for column in index.columns] for index in places.indexes}
    assert index_columns["ix_public_places_lat_lng"] == ["latitude", "longitude"]
    assert index_columns["ix_public_places_name_key"] == ["name_key"]
    assert {"ck_public_places_source", "ck_public_places_category"} <= _check_names(places)


def test_public_place_sync_state_table_is_registered() -> None:
    state = Base.metadata.tables["public_place_sync_state"]
    assert [column.name for column in state.primary_key.columns] == ["source"]
    assert state.c["last_success_at"].nullable is True
    assert state.c["last_attempt_at"].nullable is False
    assert {"ck_public_place_sync_state_source", "ck_public_place_sync_state_outcome"} <= _check_names(state)


def test_trip_place_public_origin_columns_are_registered() -> None:
    trip_places = Base.metadata.tables["trip_places"]
    for column in ("place_origin", "public_source", "public_source_id", "photo_url", "photo_license"):
        assert column in trip_places.c
        assert trip_places.c[column].nullable is True
    assert "ck_trip_places_place_origin" in _check_names(trip_places)
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_db_schema.py`
기대: FAIL 4개. 새 표가 없고(`KeyError`) `trip_places`에 새 열이 없다.

- [ ] **3단계: 구현**

`backend/app/models/tables.py`의 `from sqlalchemy import (...)`에 `Float,`를 `DateTime,` 다음에, `Index,`를 `ForeignKey,` 다음에 더한다.

`TripPlace`의 `__tablename__ = "trip_places"` 다음 줄에 아래를 넣는다.

```python
    __table_args__ = (
        CheckConstraint(
            "place_origin IS NULL OR place_origin IN ('public', 'custom', 'needs_review')",
            name="ck_trip_places_place_origin",
        ),
    )
```

같은 클래스의 `place_url` 줄 다음에 아래를 넣는다.

```python
    # 담는 값의 출처(카카오 운영정책, 0048): public = 공공데이터 장소, custom = 나만의 장소, needs_review = 변환 뒤 확인 필요.
    # 3단계 담는 흐름부터 채운다. 비어 있으면 예전 행(카카오 값 - 4단계에서 변환)
    place_origin: Mapped[str | None] = mapped_column(String(20))
    public_source: Mapped[str | None] = mapped_column(String(10))
    public_source_id: Mapped[str | None] = mapped_column(String(40))
    photo_url: Mapped[str | None] = mapped_column(String(500))
    photo_license: Mapped[str | None] = mapped_column(String(20))
```

`TripPlace` 클래스 바로 뒤(`class TripMember(Base):` 앞)에 아래를 넣는다.

```python
class PublicPlace(Base):
    """우리 장소 기반(카카오 운영정책 2단계, 0048) - TourAPI 6개 유형 + 상가정보 음식 · 숙박 · 예술·스포츠. 카카오 값은 없다.
    일정 장소는 담을 때 값을 복사한다(외래키 없음 - 공공데이터가 바뀌거나 지워져도 일정은 담은 값 그대로)."""

    __tablename__ = "public_places"
    __table_args__ = (
        CheckConstraint("source IN ('tourapi', 'sangga')", name="ck_public_places_source"),
        CheckConstraint(
            "category IN ('sight', 'culture', 'leisure', 'stay', 'shopping', 'food', 'cafe')",
            name="ck_public_places_category",
        ),
        Index("ix_public_places_lat_lng", "latitude", "longitude"),
        Index("ix_public_places_name_key", "name_key"),
    )

    # tourapi = contentid, sangga = 상가업소번호
    source: Mapped[str] = mapped_column(String(10), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # 비교용 이름 - 소문자, 띄어쓰기 · 기호를 뺀 것(services/public_places.name_key)
    name_key: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300))
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    sido: Mapped[str | None] = mapped_column(String(20))
    city: Mapped[str | None] = mapped_column(String(40))
    # TourAPI 만 - 저작권 유형은 cpyrhtDivCd(Type1 · Type3)
    photo_url: Mapped[str | None] = mapped_column(String(500))
    photo_license: Mapped[str | None] = mapped_column(String(20))
    # 이 행을 마지막으로 넣거나 고친 시각(UTC). 출처의 시도 · 성공 기록은 public_place_sync_state 에 따로 있다
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PublicPlaceSyncState(Base):
    """출처마다 한 줄(0048). 받기 시작할 때(첫 호출 전) running, 끝나면 success · partial · error 로 바꾼다. success 만
    last_success_at 을 바꾼다. 자동 동기화는 last_attempt_at(오늘 이미 시도했나)과 last_success_at(7일)을 본다."""

    __tablename__ = "public_place_sync_state"
    __table_args__ = (
        CheckConstraint("source IN ('tourapi', 'sangga')", name="ck_public_place_sync_state_source"),
        CheckConstraint(
            "last_outcome IN ('running', 'success', 'partial', 'error')", name="ck_public_place_sync_state_outcome"
        ),
    )

    source: Mapped[str] = mapped_column(String(10), primary_key=True)
    last_attempt_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    received_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    written_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    pruned_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # 짧은 이유만 - TourAPI 오류 문구(키 없음) 또는 예외 이름
    last_error: Mapped[str | None] = mapped_column(String(300))
```

`backend/app/models/__init__.py`의 import 목록에 `PublicPlace,`와 `PublicPlaceSyncState,`를 `PhotoReviewTarget,` 다음에, `__all__`에 `"PublicPlace",`와 `"PublicPlaceSyncState",`를 `"PhotoReviewTarget",` 다음에 더한다.

`backend/alembic/versions/0048_public_places.py`를 만든다.

```python
"""public places: our own place base from public data (Kakao Local policy, stage 2)

Revision ID: 0048_public_places
Revises: 0047_photo_review
Create Date: 2026-10-04

카카오 로컬 값(장소명 · 주소 · 좌표)을 저장하지 않으려고 공공데이터로 우리 장소 기반을 만든다(설계
docs/superpowers/specs/2026-10-03-public-place-storage-design.md). public_places 는 TourAPI 6개 유형과 상가정보
음식 · 숙박 · 예술·스포츠를 담는다(적재: scripts/sync_public_places_tourapi.py · scripts/load_public_places_sangga.py).
public_place_sync_state 는 출처마다 마지막 시도(running 포함)와 끝까지 받은 마지막 시각을 둔다. trip_places 에는 담는 값의
출처 열을 더한다 - 3단계 담는 흐름부터 채운다. 표와 nullable 열을 더하기만 하므로 앞 버전 코드가 그대로 돈다. downgrade 는 모두 지운다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0048_public_places"
down_revision: str | None = "0047_photo_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_places",
        sa.Column("source", sa.String(length=10), primary_key=True),
        sa.Column("source_id", sa.String(length=40), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_key", sa.String(length=200), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("sido", sa.String(length=20), nullable=True),
        sa.Column("city", sa.String(length=40), nullable=True),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("photo_license", sa.String(length=20), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("source IN ('tourapi', 'sangga')", name="ck_public_places_source"),
        sa.CheckConstraint(
            "category IN ('sight', 'culture', 'leisure', 'stay', 'shopping', 'food', 'cafe')",
            name="ck_public_places_category",
        ),
    )
    op.create_index("ix_public_places_lat_lng", "public_places", ["latitude", "longitude"])
    op.create_index("ix_public_places_name_key", "public_places", ["name_key"])
    op.create_table(
        "public_place_sync_state",
        sa.Column("source", sa.String(length=10), primary_key=True),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("last_outcome", sa.String(length=20), nullable=False),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("received_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("written_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pruned_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.CheckConstraint("source IN ('tourapi', 'sangga')", name="ck_public_place_sync_state_source"),
        sa.CheckConstraint(
            "last_outcome IN ('running', 'success', 'partial', 'error')", name="ck_public_place_sync_state_outcome"
        ),
    )
    op.add_column("trip_places", sa.Column("place_origin", sa.String(length=20), nullable=True))
    op.add_column("trip_places", sa.Column("public_source", sa.String(length=10), nullable=True))
    op.add_column("trip_places", sa.Column("public_source_id", sa.String(length=40), nullable=True))
    op.add_column("trip_places", sa.Column("photo_url", sa.String(length=500), nullable=True))
    op.add_column("trip_places", sa.Column("photo_license", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        "ck_trip_places_place_origin",
        "trip_places",
        "place_origin IS NULL OR place_origin IN ('public', 'custom', 'needs_review')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_trip_places_place_origin", "trip_places", type_="check")
    for column in ("photo_license", "photo_url", "public_source_id", "public_source", "place_origin"):
        op.drop_column("trip_places", column)
    op.drop_table("public_place_sync_state")
    op.drop_index("ix_public_places_name_key", table_name="public_places")
    op.drop_index("ix_public_places_lat_lng", table_name="public_places")
    op.drop_table("public_places")
```

`docs/db-schema-current.md`의 '사진 검토 (2026-10-02, `0047_photo_review`):' 절이 끝난 바로 뒤(다음 `## ` 제목 앞)에 아래 절을 더한다.

```markdown
공공데이터 장소 (2026-10-04, `0048_public_places`):

- `public_places`: 우리 장소 기반(카카오 운영정책 2단계, 설계 `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`). PK `(source, source_id)` - `source` 는 `tourapi`(contentid) · `sangga`(상가업소번호), CHECK. `name`(상가정보는 상호명 + 지점명), `name_key`(비교용 - 소문자, 띄어쓰기 · 기호를 뺌), `address`(TourAPI `addr1`, 상가정보 도로명 → 없으면 지번), `latitude` · `longitude`(double precision), `category`(`sight`/`culture`/`leisure`/`stay`/`shopping`/`food`/`cafe`, CHECK), `sido` · `city`(지도 도 · 시군 짧은 이름, 가리지 못하면 NULL), `photo_url` · `photo_license`(TourAPI 만, `cpyrhtDivCd`), `synced_at`(이 행을 마지막으로 넣거나 고친 시각 UTC). 색인 `ix_public_places_lat_lng`(위도, 경도) · `ix_public_places_name_key`. 일정 장소와 외래키로 묶지 않는다. 오래된 행은 단위마다 끝까지 받았을 때 그 단위만 지운다(TourAPI 유형 · 상가정보 시도).
- `public_place_sync_state`: 출처마다 한 줄(PK `source`). `last_attempt_at` · `last_outcome`(`running`/`success`/`partial`/`error`, CHECK - 받기 시작할 때 `running`) · `last_success_at`(끝까지 받은 마지막 시각 - 성공만 바꾼다) · `received_count` · `written_count`(이번 실행의 고유 행) · `pruned_count` · `last_error`(짧은 이유). 자동 TourAPI 동기화는 오늘(KST) 시도 여부와 `last_success_at`(7일)을 본다.
- `trip_places` 에 `place_origin`(`public`/`custom`/`needs_review`, CHECK `ck_trip_places_place_origin`) · `public_source` · `public_source_id` · `photo_url` · `photo_license` 를 더했다. 모두 nullable - 3단계 담는 흐름부터 채우고, 비어 있으면 예전 행이다.
```

`docs/db-schema-current.sql`을 pg_dump 모양 그대로 고친다.
- `CREATE TABLE public.trip_places (` 블록의 마지막 열 뒤에 아래 열과 제약을 더한다(앞 줄 끝에 쉼표).

```sql
    place_origin character varying(20),
    public_source character varying(10),
    public_source_id character varying(40),
    photo_url character varying(500),
    photo_license character varying(20),
    CONSTRAINT ck_trip_places_place_origin CHECK (((place_origin IS NULL) OR ((place_origin)::text = ANY ((ARRAY['public'::character varying, 'custom'::character varying, 'needs_review'::character varying])::text[]))))
```

- `-- Name: recommendations; Type: TABLE;` 주석 블록 바로 앞에 아래를 더한다.

```sql
--
-- Name: public_place_sync_state; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.public_place_sync_state (
    source character varying(10) NOT NULL,
    last_attempt_at timestamp without time zone NOT NULL,
    last_outcome character varying(20) NOT NULL,
    last_success_at timestamp without time zone,
    received_count integer DEFAULT 0 NOT NULL,
    written_count integer DEFAULT 0 NOT NULL,
    pruned_count integer DEFAULT 0 NOT NULL,
    last_error character varying(300),
    CONSTRAINT ck_public_place_sync_state_outcome CHECK (((last_outcome)::text = ANY ((ARRAY['running'::character varying, 'success'::character varying, 'partial'::character varying, 'error'::character varying])::text[]))),
    CONSTRAINT ck_public_place_sync_state_source CHECK (((source)::text = ANY ((ARRAY['tourapi'::character varying, 'sangga'::character varying])::text[])))
);


--
-- Name: public_places; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.public_places (
    source character varying(10) NOT NULL,
    source_id character varying(40) NOT NULL,
    name character varying(200) NOT NULL,
    name_key character varying(200) NOT NULL,
    address character varying(300),
    latitude double precision NOT NULL,
    longitude double precision NOT NULL,
    category character varying(20) NOT NULL,
    sido character varying(20),
    city character varying(40),
    photo_url character varying(500),
    photo_license character varying(20),
    synced_at timestamp without time zone NOT NULL,
    CONSTRAINT ck_public_places_category CHECK (((category)::text = ANY ((ARRAY['sight'::character varying, 'culture'::character varying, 'leisure'::character varying, 'stay'::character varying, 'shopping'::character varying, 'food'::character varying, 'cafe'::character varying])::text[]))),
    CONSTRAINT ck_public_places_source CHECK (((source)::text = ANY ((ARRAY['tourapi'::character varying, 'sangga'::character varying])::text[])))
);

```

- `-- Name: recommendations recommendations_pkey; Type: CONSTRAINT;` 블록 바로 앞에 아래를 더한다.

```sql
--
-- Name: public_place_sync_state public_place_sync_state_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_place_sync_state
    ADD CONSTRAINT public_place_sync_state_pkey PRIMARY KEY (source);


--
-- Name: public_places public_places_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.public_places
    ADD CONSTRAINT public_places_pkey PRIMARY KEY (source, source_id);

```

- 색인 블록들 가운데 알파벳 자리(`ix_photo_review_...` 다음, 그다음 `ix_` 앞)에 아래를 더한다.

```sql
--
-- Name: ix_public_places_lat_lng; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_public_places_lat_lng ON public.public_places USING btree (latitude, longitude);


--
-- Name: ix_public_places_name_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_public_places_name_key ON public.public_places USING btree (name_key);

```

- [ ] **4단계: 통과하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_db_schema.py && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m alembic upgrade 0047_photo_review:0048_public_places --sql | grep -c "public_place"`
기대: PASS. 오프라인 SQL에 두 표가 나온다(1 이상).

---

### Task 2: 이름 정규화와 공공데이터 행 만들기

**파일:**
- 만들기: `backend/app/services/public_places.py`
- 만들기: `backend/tests/test_public_places.py`

**인터페이스:**
- 내놓는 것(뒤 과제가 쓴다):
  - 상수 `TOURAPI = "tourapi"`, `SANGGA = "sangga"`, `TOURAPI_CONTENT_TYPES: dict[str, str]`
  - `name_key(name: str | None) -> str`
  - `distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float`
  - `utc_now() -> datetime`(naive UTC)
  - `_region_city(first: str, second: str) -> tuple[str | None, str | None]`(캐시)
  - `tourapi_row(entry: dict[str, Any], synced_at: datetime) -> dict[str, object] | None`
  - `sangga_row(row: dict[str, str], synced_at: datetime) -> dict[str, object] | None`
  - 행 사전의 열쇠는 `PublicPlace` 열 이름과 같다(`source` · `source_id` · `name` · `name_key` · `address` · `latitude` · `longitude` · `category` · `sido` · `city` · `photo_url` · `photo_license` · `synced_at`).

- [ ] **1단계: 실패하는 시험 쓰기** - `backend/tests/test_public_places.py`

```python
"""공공데이터 장소 기반(카카오 운영정책 2단계) - 이름 정규화 · 행 만들기 · 저장소 · 적재 · 맞춰 보기.
DB 는 운영과 같은 autoflush=False 세션의 SQLite 다. 공공데이터 모양은 2026-10-03 에 받은 TourAPI · 상가정보 20260630판과 같다."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.services.public_places import name_key, sangga_row, tourapi_row

SYNCED = datetime(2026, 10, 4, 3, 0)

ODONGDO = {
    "contentid": "126508", "contenttypeid": "12", "title": "오동도", "addr1": "전남광주통합특별시 여수시 오동도로 222",
    "mapx": "127.7663", "mapy": "34.7443", "firstimage": "http://tong.visitkorea.or.kr/a.jpg", "cpyrhtDivCd": "Type3",
    "cat3": "A01010400",
}

CAFE = {
    "상가업소번호": "MA0101202210A0094848", "상호명": "카페마레", "지점명": "여수점",
    "상권업종대분류코드": "I2", "상권업종중분류코드": "I212", "시도명": "전남광주통합특별시", "시군구명": "여수시",
    "지번주소": "전남광주통합특별시 여수시 수정동 1-1", "도로명주소": "전남광주통합특별시 여수시 오동도로 1",
    "경도": "127.7660", "위도": "34.7440",
}


def test_name_key_drops_case_spaces_and_symbols() -> None:
    assert name_key(" 스타벅스 여수엑스포점 ") == "스타벅스여수엑스포점"
    assert name_key("CAFE (마레)·Bay") == "cafe마레bay"
    assert name_key(None) == ""


def test_tourapi_entry_becomes_a_row_with_region_category_and_photo() -> None:
    assert tourapi_row(ODONGDO, SYNCED) == {
        "source": "tourapi", "source_id": "126508", "name": "오동도", "name_key": "오동도",
        "address": "전남광주통합특별시 여수시 오동도로 222", "latitude": 34.7443, "longitude": 127.7663, "category": "sight",
        "sido": "전남", "city": "여수", "photo_url": "http://tong.visitkorea.or.kr/a.jpg", "photo_license": "Type3",
        "synced_at": SYNCED,
    }


def test_tourapi_cafe_food_and_entries_that_are_not_places() -> None:
    assert tourapi_row({**ODONGDO, "contenttypeid": "39", "cat3": "A05020900"}, SYNCED)["category"] == "cafe"
    assert tourapi_row({**ODONGDO, "contenttypeid": "39", "cat3": ""}, SYNCED)["category"] == "food"
    assert tourapi_row({**ODONGDO, "firstimage": ""}, SYNCED)["photo_license"] is None   # 사진이 없으면 유형도 비운다
    assert tourapi_row({**ODONGDO, "contenttypeid": "25"}, SYNCED) is None   # 여행코스는 장소가 아니다
    assert tourapi_row({**ODONGDO, "contentid": ""}, SYNCED) is None
    assert tourapi_row({**ODONGDO, "mapx": ""}, SYNCED) is None
    assert tourapi_row({**ODONGDO, "mapy": "0"}, SYNCED) is None   # 좌표 0 은 한국 밖


def test_sangga_row_joins_the_branch_and_keeps_only_travel_categories() -> None:
    row = sangga_row(CAFE, SYNCED)
    assert row == {
        "source": "sangga", "source_id": "MA0101202210A0094848", "name": "카페마레 여수점", "name_key": "카페마레여수점",
        "address": "전남광주통합특별시 여수시 오동도로 1", "latitude": 34.744, "longitude": 127.766, "category": "cafe",
        "sido": "전남", "city": "여수", "photo_url": None, "photo_license": None, "synced_at": SYNCED,
    }
    assert sangga_row({**CAFE, "상권업종중분류코드": "I201"}, SYNCED)["category"] == "food"
    assert sangga_row({**CAFE, "상권업종대분류코드": "I1", "상권업종중분류코드": "I101"}, SYNCED)["category"] == "stay"
    assert sangga_row({**CAFE, "상권업종대분류코드": "R1", "상권업종중분류코드": "R102"}, SYNCED)["category"] == "culture"
    assert sangga_row({**CAFE, "상권업종대분류코드": "R1", "상권업종중분류코드": "R104"}, SYNCED)["category"] == "leisure"
    assert sangga_row({**CAFE, "상권업종대분류코드": "G2"}, SYNCED) is None   # 소매는 넣지 않는다
    assert sangga_row({**CAFE, "위도": ""}, SYNCED) is None
    assert sangga_row({**CAFE, "지점명": ""}, SYNCED)["name"] == "카페마레"
    assert sangga_row({**CAFE, "도로명주소": ""}, SYNCED)["address"] == "전남광주통합특별시 여수시 수정동 1-1"
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_public_places.py`
기대: FAIL. `app.services.public_places`가 없다.

- [ ] **3단계: 구현** - `backend/app/services/public_places.py`

```python
"""우리 장소 기반(카카오 운영정책 2단계) - 공공데이터 장소를 받아 두고, 고른 카카오 장소와 서버 안에서 맞춰 본다.

설계: docs/superpowers/specs/2026-10-03-public-place-storage-design.md. 카카오 값(장소명 · 주소 · 좌표)은 맞춰 볼 때 메모리에서만
견주고 버린다 - 저장하거나 로그에 남기지 않고, 외부(공공 API 포함)로 보내지 않는다. 공공데이터는 TourAPI 6개 유형(주 1회 동기화)과
소상공인 상가정보의 음식 · 숙박 · 예술·스포츠(분기 파일)다. 이름 비교 · 반경은 2026-10-03 실측(366곳)과 같은 기준이다.
"""

from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from app.services.place_search import resolve_city, resolve_region

logger = logging.getLogger(__name__)

TOURAPI = "tourapi"
SANGGA = "sangga"
# TourAPI contentTypeId → 우리 분류. 25(여행코스)는 장소가 아니라 받지 않는다
TOURAPI_CONTENT_TYPES = {"12": "sight", "14": "culture", "28": "leisure", "32": "stay", "38": "shopping", "39": "food"}
TOURAPI_CAFE_CAT3 = "A05020900"   # 음식점 > 카페/전통찻집
# 상가정보 대분류 음식 · 숙박 · 예술·스포츠만 - 소매 · 교육 · 부동산 등은 넣지 않는다
SANGGA_MAJOR_CATEGORIES = {"I2": "food", "I1": "stay", "R1": "leisure"}
SANGGA_MIDDLE_CATEGORIES = {"I212": "cafe", "R102": "culture"}   # 비알코올(카페) · 도서관·사적지
_NAME_NOISE = re.compile(r"[\s\-·・()\[\]{}<>.,'\"/&+_~!?:;|]+")


def name_key(name: str | None) -> str:
    """비교용 이름 - 소문자로 바꾸고 띄어쓰기 · 기호를 뺀다(실측과 같은 규칙)."""

    return _NAME_NOISE.sub("", (name or "").lower())


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 점 사이 거리(m) - 수 km 안에서 쓰는 평면 근사(실측과 같다)."""

    rad = math.pi / 180
    x = (lng2 - lng1) * rad * math.cos((lat1 + lat2) / 2 * rad)
    y = (lat2 - lat1) * rad
    return 6_371_000 * math.hypot(x, y)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _in_korea(latitude: float, longitude: float) -> bool:
    return 33.0 <= latitude <= 39.0 and 124.0 <= longitude <= 132.0


def _float(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=4096)
def _region_city(first: str, second: str) -> tuple[str | None, str | None]:
    """주소 첫 · 둘째 낱말 → 지도 도 · 시군(통합 검색과 같은 규칙). 104만 행이라 같은 쌍은 한 번만 푼다."""

    return resolve_region(first, second), (resolve_city(second) if second else None)


def tourapi_row(entry: dict[str, Any], synced_at: datetime) -> dict[str, object] | None:
    """TourAPI 목록 항목 하나 → public_places 행. 장소가 아니거나 ID · 좌표가 없으면 None."""

    content_id = str(entry.get("contentid") or "").strip()
    category = TOURAPI_CONTENT_TYPES.get(str(entry.get("contenttypeid") or "").strip())
    title = str(entry.get("title") or "").strip()
    latitude, longitude = _float(entry.get("mapy")), _float(entry.get("mapx"))
    if not content_id or not category or not title or latitude is None or longitude is None:
        return None
    if not _in_korea(latitude, longitude):
        return None
    if category == "food" and entry.get("cat3") == TOURAPI_CAFE_CAT3:
        category = "cafe"
    address = str(entry.get("addr1") or "").strip() or None
    words = (address or "").split()
    sido, city = _region_city(*(words + ["", ""])[:2])
    photo = str(entry.get("firstimage") or "").strip() or None
    return {
        "source": TOURAPI,
        "source_id": content_id,
        "name": title[:200],
        "name_key": name_key(title)[:200],
        "address": address[:300] if address else None,
        "latitude": latitude,
        "longitude": longitude,
        "category": category,
        "sido": sido,
        "city": city,
        "photo_url": photo[:500] if photo else None,
        "photo_license": (str(entry.get("cpyrhtDivCd") or "").strip() or None) if photo else None,
        "synced_at": synced_at,
    }


def sangga_row(row: dict[str, str], synced_at: datetime) -> dict[str, object] | None:
    """상가정보 CSV 한 줄 → public_places 행. 여행 업종이 아니거나 번호 · 좌표가 없으면 None."""

    category = SANGGA_MAJOR_CATEGORIES.get((row.get("상권업종대분류코드") or "").strip())
    store_id = (row.get("상가업소번호") or "").strip()
    name = (row.get("상호명") or "").strip()
    latitude, longitude = _float(row.get("위도")), _float(row.get("경도"))
    if not category or not store_id or not name or latitude is None or longitude is None:
        return None
    if not _in_korea(latitude, longitude):
        return None
    category = SANGGA_MIDDLE_CATEGORIES.get((row.get("상권업종중분류코드") or "").strip(), category)
    branch = (row.get("지점명") or "").strip()
    full = f"{name} {branch}" if branch else name
    address = (row.get("도로명주소") or "").strip() or (row.get("지번주소") or "").strip() or None
    sido, city = _region_city((row.get("시도명") or "").strip(), (row.get("시군구명") or "").strip())
    return {
        "source": SANGGA,
        "source_id": store_id,
        "name": full[:200],
        "name_key": name_key(full)[:200],
        "address": address[:300] if address else None,
        "latitude": latitude,
        "longitude": longitude,
        "category": category,
        "sido": sido,
        "city": city,
        "photo_url": None,
        "photo_license": None,
        "synced_at": synced_at,
    }
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_public_places.py`
기대: 4개 PASS.

---

### Task 3: 저장소와 동기화 상태

**파일:**
- 만들기: `backend/app/repositories/public_places.py`
- 고치기: `backend/tests/test_public_places.py`

**인터페이스:**
- 받는 것: 과제 1의 `PublicPlace` · `PublicPlaceSyncState`, 과제 2의 행 사전.
- 내놓는 것:
  - `upsert_public_places(db, rows: Sequence[dict[str, object]]) -> int` - 한 묶음. 같은 열쇠가 한 묶음에 두 번이면 뒤의 것만 쓴다.
  - `count_public_places(db, *, source: str) -> int`
  - `count_public_places_by(db, *, source: str, column: Literal["category", "sido"], since: datetime | None = None) -> dict[str | None, int]` - `since`를 주면 그 뒤에 넣거나 고친 행만(이번 실행의 고유 행)
  - `prune_public_places(db, *, source: str, synced_before: datetime, categories: Collection[str] | None = None, sidos: Collection[str] | None = None) -> int`
  - `record_sync_state(db, *, source, attempted_at, outcome, received=0, written=0, pruned=0, error=None) -> None`
  - `get_sync_state(db, *, source: str) -> PublicPlaceSyncState | None`
  - `public_places_in_box(db, *, south: float, north: float, west: float, east: float) -> list[PublicPlace]`

- [ ] **1단계: 실패하는 시험 쓰기** - `backend/tests/test_public_places.py`

파일 위쪽 import에 아래를 더한다.

```python
from collections.abc import Iterator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.models import PublicPlace
from app.repositories.public_places import (
    count_public_places,
    count_public_places_by,
    get_sync_state,
    prune_public_places,
    public_places_in_box,
    record_sync_state,
    upsert_public_places,
)
```

`SYNCED` 줄 다음에 아래 픽스처 · 도우미를 더하고, 파일 끝에 시험을 더한다.

```python
T1, T2, T3 = datetime(2026, 10, 1, 4, 0), datetime(2026, 10, 8, 4, 0), datetime(2026, 10, 15, 4, 0)


@pytest.fixture
def db() -> Iterator[Session]:
    # TestClient 는 라우트를 다른 스레드에서 돌린다 - 한 연결을 같이 쓰게 StaticPool · check_same_thread=False(기존 라우트 시험과 같다).
    # 운영 세션과 같이 autoflush 를 끈다. 두 표 모두 문자열 키라 sqlite 의 BigInteger 함정이 없다
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    with sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)() as session:
        yield session


def place_row(source: str, source_id: str, name: str, lat: float = 34.7443, lng: float = 127.7663,
              category: str = "food", *, photo: str | None = None, synced_at: datetime = T1, sido: str = "전남") -> dict[str, object]:
    return {
        "source": source, "source_id": source_id, "name": name, "name_key": name_key(name),
        "address": "전남광주통합특별시 여수시 수정동 1", "latitude": lat, "longitude": lng, "category": category,
        "sido": sido, "city": "여수", "photo_url": photo, "photo_license": "Type3" if photo else None, "synced_at": synced_at,
    }


def seed(db: Session, *rows: dict[str, object]) -> None:
    upsert_public_places(db, list(rows))
    db.commit()
```

```python
def test_upsert_keeps_one_row_per_key_and_the_later_value_wins(db: Session) -> None:
    seed(db, place_row("tourapi", "1", "오동도", synced_at=T1))
    # 같은 열쇠가 한 묶음에 두 번 - Postgres 는 거부하므로 뒤의 것만 쓴다
    written = upsert_public_places(db, [place_row("tourapi", "1", "오동도 등대", synced_at=T2), place_row("tourapi", "1", "오동도", synced_at=T2)])
    db.commit()
    assert written == 1
    rows = db.scalars(select(PublicPlace)).all()
    assert [(row.source_id, row.name, row.synced_at) for row in rows] == [("1", "오동도", T2)]


def test_counts_by_category_or_province_and_since_a_time(db: Session) -> None:
    seed(db, place_row("tourapi", "1", "a", category="sight", synced_at=T1), place_row("tourapi", "2", "b", category="food", synced_at=T2),
         place_row("sangga", "S", "c", synced_at=T2, sido="세종"))
    assert count_public_places_by(db, source="tourapi", column="category") == {"sight": 1, "food": 1}
    assert count_public_places_by(db, source="tourapi", column="category", since=T2) == {"food": 1}
    assert count_public_places_by(db, source="sangga", column="sido") == {"세종": 1}
    assert count_public_places(db, source="tourapi") == 2


def test_prune_removes_only_older_rows_of_the_units_that_passed(db: Session) -> None:
    seed(db, place_row("tourapi", "old-sight", "a", category="sight", synced_at=T1),
         place_row("tourapi", "old-food", "b", category="food", synced_at=T1),
         place_row("tourapi", "new", "c", category="sight", synced_at=T2),
         place_row("sangga", "Y", "d", synced_at=T1), place_row("sangga", "S", "e", synced_at=T1, sido="세종"))
    assert prune_public_places(db, source="tourapi", synced_before=T2, categories=["sight"]) == 1   # 음식점 유형은 통과하지 못했다
    assert prune_public_places(db, source="sangga", synced_before=T2, sidos=["전남"]) == 1   # 세종은 통과하지 못했다
    assert prune_public_places(db, source="sangga", synced_before=T2, sidos=[]) == 0
    db.commit()
    assert {row.source_id for row in db.scalars(select(PublicPlace))} == {"old-food", "new", "S"}


def test_sync_state_keeps_the_last_success_through_running_partial_and_error(db: Session) -> None:
    record_sync_state(db, source="tourapi", attempted_at=T1, outcome="running")
    record_sync_state(db, source="tourapi", attempted_at=T1, outcome="success", received=10, written=10)
    record_sync_state(db, source="tourapi", attempted_at=T2, outcome="running")
    record_sync_state(db, source="tourapi", attempted_at=T2, outcome="partial", received=5, written=5)
    record_sync_state(db, source="tourapi", attempted_at=T3, outcome="error", error="x" * 400)
    db.commit()
    state = get_sync_state(db, source="tourapi")
    assert (state.last_outcome, state.last_attempt_at, state.last_success_at, len(state.last_error)) == ("error", T3, T1, 300)
    assert get_sync_state(db, source="sangga") is None


def test_box_query_returns_only_places_inside_the_bounds(db: Session) -> None:
    seed(db, place_row("tourapi", "in", "a", 34.7443, 127.7663), place_row("tourapi", "north", "b", 34.80, 127.7663),
         place_row("sangga", "east", "c", 34.7443, 127.80))
    found = public_places_in_box(db, south=34.74, north=34.75, west=127.76, east=127.77)
    assert [row.source_id for row in found] == ["in"]
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_public_places.py`
기대: FAIL. `app.repositories.public_places`가 없다.

- [ ] **3단계: 구현** - `backend/app/repositories/public_places.py`

```python
"""public_places · public_place_sync_state 쓰기 · 조회(0048). 적재는 (source, source_id) 기준 upsert, 단위(TourAPI 유형 ·
상가정보 시도)마다 끝까지 받았는지 본 뒤 통과한 단위의 오래된 행만 지우기, 출처별 시도 · 성공 기록, 맞춰 보기는 위경도 상자 조회."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Literal

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import PublicPlace, PublicPlaceSyncState

UPDATED_COLUMNS = (
    "name", "name_key", "address", "latitude", "longitude", "category", "sido", "city", "photo_url", "photo_license", "synced_at",
)
_GROUP_COLUMNS = {"category": PublicPlace.category, "sido": PublicPlace.sido}


def upsert_public_places(db: Session, rows: Sequence[dict[str, object]]) -> int:
    """한 묶음(1,000개 안팎 - Postgres 매개변수 65,535개 안)을 넣거나 고친다. 같은 열쇠가 한 묶음에 두 번 오면 Postgres 가
    'cannot affect row a second time'으로 거부하므로 뒤의 것만 남긴다."""

    unique = list({(row["source"], row["source_id"]): row for row in rows}.values())
    if not unique:
        return 0
    insert = postgresql_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    statement = insert(PublicPlace).values(unique)
    db.execute(
        statement.on_conflict_do_update(
            index_elements=["source", "source_id"],
            set_={column: statement.excluded[column] for column in UPDATED_COLUMNS},
        )
    )
    return len(unique)


def count_public_places(db: Session, *, source: str) -> int:
    return db.scalar(select(func.count()).select_from(PublicPlace).where(PublicPlace.source == source)) or 0


def count_public_places_by(
    db: Session, *, source: str, column: Literal["category", "sido"], since: datetime | None = None
) -> dict[str | None, int]:
    """출처의 행 수를 분류 또는 시도별로. since 를 주면 그 뒤에 넣거나 고친 행만 - 이번 실행의 고유 행 수다
    (묶음마다 센 수를 더하면 같은 ID 가 두 번 올 때 부푼다)."""

    field = _GROUP_COLUMNS[column]
    statement = select(field, func.count()).where(PublicPlace.source == source)
    if since is not None:
        statement = statement.where(PublicPlace.synced_at >= since)
    return {key: count for key, count in db.execute(statement.group_by(field)).all()}


def prune_public_places(
    db: Session,
    *,
    source: str,
    synced_before: datetime,
    categories: Collection[str] | None = None,
    sidos: Collection[str] | None = None,
) -> int:
    """이번에 다시 받지 않은 오래된 행을 지운다. categories · sidos 를 주면 그 분류 · 시도만(검사를 통과한 단위만)."""

    if (categories is not None and not categories) or (sidos is not None and not sidos):
        return 0
    statement = delete(PublicPlace).where(PublicPlace.source == source, PublicPlace.synced_at < synced_before)
    if categories is not None:
        statement = statement.where(PublicPlace.category.in_(sorted(categories)))
    if sidos is not None:
        statement = statement.where(PublicPlace.sido.in_(sorted(sidos)))
    return db.execute(statement).rowcount or 0


def record_sync_state(
    db: Session,
    *,
    source: str,
    attempted_at: datetime,
    outcome: str,
    received: int = 0,
    written: int = 0,
    pruned: int = 0,
    error: str | None = None,
) -> None:
    """출처마다 한 줄. running 은 받기 시작할 때(첫 호출 전), success · partial · error 는 끝날 때. success 만 last_success_at 을 바꾼다."""

    state = db.get(PublicPlaceSyncState, source)
    if state is None:
        state = PublicPlaceSyncState(source=source)
        db.add(state)
    state.last_attempt_at = attempted_at
    state.last_outcome = outcome
    if outcome == "success":
        state.last_success_at = attempted_at
    state.received_count = received
    state.written_count = written
    state.pruned_count = pruned
    state.last_error = error[:300] if error else None
    db.flush()


def get_sync_state(db: Session, *, source: str) -> PublicPlaceSyncState | None:
    return db.get(PublicPlaceSyncState, source)


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

- [ ] **4단계: 통과하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_public_places.py`
기대: 9개 PASS.

---

### Task 4: TourAPI 동기화와 주 1회 실행

**파일:**
- 고치기: `backend/app/services/tour_api.py`(`_request_payload` 분리, `TourApiPage`, `list_area_based_page`)
- 고치기: `backend/app/services/public_places.py`(적재 결과 · 단위 판정 · TourAPI 동기화 · 때 가리기)
- 만들기: `backend/app/services/public_places_scheduler.py`
- 고치기: `backend/app/core/config.py`, `backend/app/main.py`, `.env.example`, `compose.local.yaml`
- 만들기: `backend/scripts/sync_public_places_tourapi.py`
- 고치기: `backend/tests/test_tour_api_client.py`, `backend/tests/test_public_places.py`
- 만들기: `backend/tests/test_public_places_scheduler.py`

**인터페이스:**
- 받는 것: 과제 2 · 3의 함수.
- 내놓는 것:
  - `TourApiPage(items: list[dict[str, Any]], total_count: int)`, `TourApiClient.list_area_based_page(*, content_type_id: str, page: int, rows: int, timeout: float | None = None) -> TourApiPage` - 결과 코드가 정상이 아니거나 `totalCount`가 없으면 `TourApiConfigurationError`
  - `PublicPlacesLoadResult(source, received_count, parsed_count, skipped_count, pruned_count, outcome)` - `parsed_count`는 이번 실행의 고유 행, `outcome`은 `success` · `partial` · `skipped` · `error`
  - `sync_tourapi_places(db, client, *, now: datetime) -> PublicPlacesLoadResult` - 첫 호출 전에 `running`을 남겨 확정하고, 묶음마다 확정하며, 실패하면 상태를 `error`로 남기고 예외를 올린다
  - `tourapi_sync_due(db, *, now: datetime, run_at: time) -> bool`
  - 과제 5가 쓴다: `UPSERT_BATCH`, `PRUNE_MIN_RATIO`, `_write`, `_start_run`, `_record_failure`, `_unit_passes`, `_close_run`
  - `run_public_places_sync_once(settings_obj=settings, *, now=None) -> PublicPlacesLoadResult`, `start_public_places_sync_scheduler(settings_obj) -> asyncio.Task | None`, `stop_public_places_sync_scheduler(task)`
  - 설정 `public_places_sync_enabled`(기본 False) · `public_places_sync_run_at`(`"04:00"`, KST) · `public_places_sync_poll_seconds`(300)

- [ ] **1단계: 실패하는 시험 쓰기**

`backend/tests/test_tour_api_client.py` 끝에 더한다(파일의 `make_settings` · `tour_api_body` · `FakeResponse`를 쓴다).

```python
def _client_returning(payload: dict[str, Any], seen: dict[str, Any] | None = None) -> TourApiClient:
    def http_get(url: str, *, params: dict[str, object], timeout: float) -> FakeResponse:
        if seen is not None:
            seen.update(url=url, params=params, timeout=timeout)
        return FakeResponse(payload)

    return TourApiClient(settings_obj=make_settings(), http_get=http_get)


def test_area_based_page_asks_one_whole_country_type_page_and_keeps_the_total() -> None:
    seen: dict[str, Any] = {}
    client = _client_returning(tour_api_body([{"contentid": "1", "mapx": "127.7", "mapy": "34.7"}]), seen)
    page = client.list_area_based_page(content_type_id="39", page=3, rows=1000, timeout=60.0)

    assert page.items == [{"contentid": "1", "mapx": "127.7", "mapy": "34.7"}]
    assert page.total_count == 2   # tour_api_body 의 totalCount
    assert seen["url"].endswith("/areaBasedList2")
    assert {key: seen["params"][key] for key in ("contentTypeId", "pageNo", "numOfRows", "arrange")} == {
        "contentTypeId": "39", "pageNo": 3, "numOfRows": 1000, "arrange": "A",
    }
    assert "areaCode" not in seen["params"]   # 전국
    assert seen["timeout"] == 60.0


def test_area_based_page_refuses_an_error_code_or_a_missing_total_instead_of_an_empty_page() -> None:
    quota = {"response": {"header": {"resultCode": "22", "resultMsg": "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"}}}
    with pytest.raises(TourApiConfigurationError, match="resultCode 22"):
        _client_returning(quota).list_area_based_page(content_type_id="12", page=1, rows=1000)
    no_total = {"response": {"header": {"resultCode": "0000", "resultMsg": "OK"}, "body": {"items": ""}}}
    with pytest.raises(TourApiConfigurationError, match="totalCount"):
        _client_returning(no_total).list_area_based_page(content_type_id="12", page=1, rows=1000)
```

`backend/tests/test_public_places.py` import에 `from datetime import time, timedelta`와 아래를 더하고, 파일 끝에 시험을 더한다.

```python
from app.services import public_places
from app.services.public_places import sync_tourapi_places, tourapi_sync_due
from app.services.tour_api import TourApiConfigurationError, TourApiPage
```

```python
class FakeTourPages:
    """TourAPI 전국 목록 - 유형마다 항목을 rows 개씩 자른다. totals 로 totalCount 를 바꾸고, fail_at 페이지에서 실패한다."""

    def __init__(self, per_type: dict[str, list[dict[str, str]]], *, totals: dict[str, int] | None = None,
                 fail_at: tuple[str, int] | None = None) -> None:
        self.per_type, self.totals, self.fail_at = per_type, totals or {}, fail_at
        self.calls: list[tuple[str, int]] = []

    def list_area_based_page(self, *, content_type_id: str, page: int, rows: int, timeout: float | None = None) -> TourApiPage:
        self.calls.append((content_type_id, page))
        if (content_type_id, page) == self.fail_at:
            raise TourApiConfigurationError("TourAPI request failed (HTTP 500).")
        items = self.per_type.get(content_type_id, [])
        return TourApiPage(items[(page - 1) * rows: page * rows], self.totals.get(content_type_id, len(items)))


def tour_entry(content_id: str, title: str, content_type: str = "12") -> dict[str, str]:
    return {"contentid": content_id, "contenttypeid": content_type, "title": title, "addr1": "전남광주통합특별시 여수시 1",
            "mapx": "127.7663", "mapy": "34.7443"}


TEN = [tour_entry(str(n), f"장소{n}") for n in range(10)]


def test_tourapi_sync_reads_every_page_the_total_count_promises(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "TOURAPI_PAGE_ROWS", 3)
    pages = FakeTourPages({"12": TEN[:7], "39": [tour_entry("90", "식당", "39")]})
    result = sync_tourapi_places(db, pages, now=T1)
    assert (result.received_count, result.parsed_count, result.outcome) == (8, 8, "success")
    assert [call for call in pages.calls if call[0] == "12"] == [("12", 1), ("12", 2), ("12", 3)]   # 7건 = 3 + 3 + 1
    assert {call[0] for call in pages.calls} == set(public_places.TOURAPI_CONTENT_TYPES)
    assert get_sync_state(db, source="tourapi").last_success_at == T1


def test_tourapi_sync_prunes_a_type_only_after_reading_it_completely(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "TOURAPI_PAGE_ROWS", 3)
    sync_tourapi_places(db, FakeTourPages({"12": TEN}), now=T1)
    gone = sync_tourapi_places(db, FakeTourPages({"12": TEN[:9]}), now=T2)   # 하나가 사라졌다(totalCount 9)
    assert (gone.pruned_count, gone.outcome) == (1, "success")
    short = sync_tourapi_places(db, FakeTourPages({"12": TEN[:5]}, totals={"12": 9}), now=T3)   # 9건이라더니 5건만 왔다
    assert (short.pruned_count, short.outcome) == (0, "partial")
    assert count_public_places(db, source="tourapi") == 9
    assert get_sync_state(db, source="tourapi").last_success_at == T2   # 일부는 성공 시각을 바꾸지 않는다


def test_a_type_that_suddenly_comes_back_empty_keeps_its_rows(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "TOURAPI_PAGE_ROWS", 3)
    food = [tour_entry(f"F{n}", f"식당{n}", "39") for n in range(2)]
    sync_tourapi_places(db, FakeTourPages({"12": TEN, "39": food}), now=T1)
    # 다음 주 음식점 유형이 0건으로 왔다 - 관광지는 다 왔고 전체로는 10/12(83%)지만 음식점 행은 지우지 않는다
    result = sync_tourapi_places(db, FakeTourPages({"12": TEN}), now=T2)
    assert (result.pruned_count, result.outcome) == (0, "partial")
    assert count_public_places(db, source="tourapi") == 12


def test_a_repeated_page_is_an_incomplete_read_even_across_batch_edges(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "TOURAPI_PAGE_ROWS", 3)
    monkeypatch.setattr(public_places, "UPSERT_BATCH", 2)   # 같은 ID 가 묶음 경계를 넘어 다시 온다
    sync_tourapi_places(db, FakeTourPages({"12": TEN}), now=T1)
    shifted = TEN[:3] + TEN[:3] + TEN[6:]   # 둘째 페이지가 첫 페이지와 같다(순서가 밀림) - 10건이 왔지만 고유 7곳
    result = sync_tourapi_places(db, FakeTourPages({"12": shifted}), now=T2)
    assert (result.received_count, result.parsed_count, result.pruned_count, result.outcome) == (10, 7, 0, "partial")
    assert count_public_places(db, source="tourapi") == 10


def test_a_failure_after_good_pages_deletes_nothing_and_is_recorded(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "TOURAPI_PAGE_ROWS", 3)
    sync_tourapi_places(db, FakeTourPages({"12": TEN}), now=T1)
    with pytest.raises(TourApiConfigurationError):
        sync_tourapi_places(db, FakeTourPages({"12": TEN[:9]}, fail_at=("12", 3)), now=T2)   # 앞 두 페이지는 왔다
    assert count_public_places(db, source="tourapi") == 10   # 지운 것 없음
    state = get_sync_state(db, source="tourapi")
    assert (state.last_outcome, state.last_success_at, state.received_count, state.last_error) == (
        "error", T1, 6, "TourAPI request failed (HTTP 500).",
    )


def test_an_interrupted_run_still_counts_as_todays_attempt(db: Session) -> None:
    class Crash(BaseException):
        pass

    class Dying(FakeTourPages):
        def list_area_based_page(self, **_kwargs) -> TourApiPage:
            raise Crash()   # 프로세스가 죽은 것처럼 - except Exception 이 잡지 않는다

    with pytest.raises(Crash):
        sync_tourapi_places(db, Dying({}), now=T1)
    db.rollback()
    state = get_sync_state(db, source="tourapi")
    assert (state.last_attempt_at, state.last_outcome) == (T1, "running")   # 첫 호출 전에 남겼다


def test_a_sync_that_writes_nothing_is_partial_not_success(db: Session) -> None:
    result = sync_tourapi_places(db, FakeTourPages({}), now=T1)
    assert (result.parsed_count, result.pruned_count, result.outcome) == (0, 0, "partial")


def test_automatic_sync_runs_once_a_day_after_run_at_and_weekly_after_a_success(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "TOURAPI_PAGE_ROWS", 3)
    run_at = time(4, 0)
    morning = datetime(2026, 9, 30, 19, 30)   # UTC - KST 10/1 04:30
    assert tourapi_sync_due(db, now=morning - timedelta(hours=1), run_at=run_at) is False   # KST 03:30 - 아직 이르다
    assert tourapi_sync_due(db, now=morning, run_at=run_at) is True
    with pytest.raises(TourApiConfigurationError):
        sync_tourapi_places(db, FakeTourPages({}, fail_at=("12", 1)), now=morning)
    assert tourapi_sync_due(db, now=morning + timedelta(hours=3), run_at=run_at) is False   # 오늘 이미 시도 - 재기동해도 같다
    next_morning = morning + timedelta(days=1)
    assert tourapi_sync_due(db, now=next_morning, run_at=run_at) is True   # 실패 다음 날 다시
    sync_tourapi_places(db, FakeTourPages({"12": TEN[:1]}), now=next_morning)
    assert tourapi_sync_due(db, now=next_morning + timedelta(days=6), run_at=run_at) is False   # 성공 뒤 7일 안
    assert tourapi_sync_due(db, now=next_morning + timedelta(days=7), run_at=run_at) is True
```

`backend/tests/test_public_places_scheduler.py`를 만든다.

```python
"""주 1회 TourAPI 공공데이터 장소 동기화 - 기본 꺼짐, 때(오늘 시도 · 7일)는 DB 상태로 가리고, 실패는 오류 결과로 남긴다."""

from __future__ import annotations

import logging
from contextlib import nullcontext
from dataclasses import replace

import pytest

from app.core.config import Settings
from app.services import public_places_scheduler
from app.services.public_places_scheduler import run_public_places_sync_once, start_public_places_sync_scheduler


def _fake_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places_scheduler, "build_tour_api_client", lambda *_: object())
    monkeypatch.setattr(public_places_scheduler, "get_session_factory", lambda: (lambda: nullcontext(object())))


def test_sync_scheduler_is_off_by_default() -> None:
    assert Settings().public_places_sync_enabled is False
    assert start_public_places_sync_scheduler(replace(Settings(), public_places_sync_enabled=False)) is None


def test_sync_once_is_skipped_when_tour_api_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places_scheduler, "build_tour_api_client", lambda *_: None)
    assert run_public_places_sync_once().outcome == "skipped"


def test_sync_once_does_nothing_when_it_is_not_time(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_session(monkeypatch)
    monkeypatch.setattr(public_places_scheduler, "tourapi_sync_due", lambda *_, **__: False)
    monkeypatch.setattr(public_places_scheduler, "sync_tourapi_places", lambda *_, **__: pytest.fail("must not sync"))
    assert run_public_places_sync_once().outcome == "skipped"


def test_sync_once_turns_a_failure_into_an_error_result(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    def boom(*_args, **_kwargs):
        raise RuntimeError("TourAPI request failed.")

    _fake_session(monkeypatch)
    monkeypatch.setattr(public_places_scheduler, "tourapi_sync_due", lambda *_, **__: True)
    monkeypatch.setattr(public_places_scheduler, "sync_tourapi_places", boom)
    caplog.set_level(logging.ERROR)
    assert run_public_places_sync_once().outcome == "error"
    assert "public_places_sync_failed" in caplog.text
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_tour_api_client.py tests/test_public_places.py tests/test_public_places_scheduler.py`
기대: FAIL. `TourApiPage` · `list_area_based_page` · `sync_tourapi_places` · `tourapi_sync_due` · `public_places_scheduler`가 없다.

- [ ] **3단계: 구현**

`backend/app/services/tour_api.py`
- 파일 위쪽 상수 묶음(`AREA_BASED_LIST_PATH` 근처)에 `TOUR_API_OK_CODES = frozenset({"0000", "00"})`를 더한다.
- `TourApiSpot` 데이터클래스 다음에 더한다.

```python
@dataclass(frozen=True)
class TourApiPage:
    """목록 한 페이지 - 항목과 전체 건수(totalCount). 공공데이터 장소 동기화가 유형마다 끝까지 받았는지 이것으로 가린다."""

    items: list[dict[str, Any]]
    total_count: int
```

- `_items_from_payload` 함수 다음에 더한다.

```python
def _page_from_payload(payload: object) -> TourApiPage:
    """결과 코드가 정상이고 totalCount 가 있어야 한 페이지다 - 아니면 설정 오류로 올린다(오류 응답을 빈 마지막 페이지로 읽지 않게)."""

    response = payload.get("response") if isinstance(payload, dict) else None
    header = response.get("header") if isinstance(response, dict) else None
    body = response.get("body") if isinstance(response, dict) else None
    code = str(header.get("resultCode", "")).strip() if isinstance(header, dict) else ""
    if code not in TOUR_API_OK_CODES:
        raise TourApiConfigurationError(f"TourAPI returned resultCode {code or 'missing'}.")
    try:
        total = int(body.get("totalCount"))   # type: ignore[union-attr]
    except (AttributeError, TypeError, ValueError):
        raise TourApiConfigurationError("TourAPI response has no totalCount.") from None
    return TourApiPage(_items_from_payload(payload), total)
```

- `TourApiClient._request_items`를 둘로 나눈다. 지금 본문(키 확인부터 `payload = response.json()`과 예외 처리까지)을 `_request_payload`로 옮겨 `payload`를 돌려주게 하고, 시그니처에 `*, timeout: float | None = None`을 더해 `timeout=timeout or self._settings.tour_api_timeout_seconds,`로 쓴다. `_request_items`는 아래 한 줄로 바꾼다.

```python
    def _request_payload(
        self, path: str, params: dict[str, object], *, timeout: float | None = None
    ) -> object:
        ...   # 지금 _request_items 본문 그대로 - 마지막 return _items_from_payload(payload) 대신 return payload

    def _request_items(self, path: str, params: dict[str, object]) -> list[dict[str, Any]]:
        return _items_from_payload(self._request_payload(path, params))
```

- `search_spots_by_keyword` 메서드 다음(`@staticmethod def _parse_spots` 앞)에 더한다.

```python
    def list_area_based_page(
        self, *, content_type_id: str, page: int, rows: int, timeout: float | None = None
    ) -> TourApiPage:
        """전국 한 유형의 한 페이지 - 원본 항목과 totalCount(공공데이터 장소 동기화, public_places). 제목순이라 받는 사이에
        수정된 항목이 있어도 페이지가 밀리지 않는다."""

        params: dict[str, object] = {
            "contentTypeId": content_type_id,
            "numOfRows": rows,
            "pageNo": page,
            "arrange": "A",
        }
        return _page_from_payload(self._request_payload(AREA_BASED_LIST_PATH, params, timeout=timeout))
```

`backend/app/services/public_places.py`
- import에 `from collections.abc import Sequence`, `from dataclasses import dataclass`, `from datetime import time, timedelta`(기존 `datetime, timezone` 줄에 합친다), `from typing import Protocol`(기존 `Any` 줄에 합친다), `from sqlalchemy.orm import Session`, `from app.services.tour_api import TourApiConfigurationError, TourApiPage`, 그리고 아래를 더한다.

```python
from app.repositories.public_places import (
    count_public_places_by,
    get_sync_state,
    prune_public_places,
    record_sync_state,
    upsert_public_places,
)
```

- 파일 끝에 더한다.

```python
TOURAPI_PAGE_ROWS = 1000
TOURAPI_TIMEOUT_SECONDS = 60.0   # 1,000건 한 페이지는 기본 5초를 넘길 때가 있다
TOURAPI_SYNC_DAYS = 7   # 마지막 성공 날짜(KST)에서 이만큼 지나면 다시 받는다
# TourAPI 유형 → 그 유형이 만드는 분류(유형별로 지울 때 쓴다 - 카페는 음식점 유형에서만 나온다)
TOURAPI_TYPE_CATEGORIES = {
    "12": ("sight",), "14": ("culture",), "28": ("leisure",), "32": ("stay",), "38": ("shopping",), "39": ("food", "cafe"),
}
KST_OFFSET = timedelta(hours=9)   # 자동 동기화의 '오늘'과 RUN_AT 은 KST 로 본다
UPSERT_BATCH = 1000
# 단위(TourAPI 유형 · 상가정보 시도)의 이번 고유 행이 기존의 80% 미만이면 그 단위는 지우지 않는다
PRUNE_MIN_RATIO = 0.8


class TourApiPageSource(Protocol):
    def list_area_based_page(
        self, *, content_type_id: str, page: int, rows: int, timeout: float | None = None
    ) -> TourApiPage: ...


@dataclass(frozen=True)
class PublicPlacesLoadResult:
    source: str
    received_count: int   # 받은 원본 항목(TourAPI 항목 · 상가정보 줄)
    parsed_count: int     # 이번 실행에서 넣거나 고친 고유 행
    skipped_count: int    # 넣지 않은 항목 - ID · 좌표 없음, 다른 업종
    pruned_count: int     # 지운 오래된 행
    outcome: str          # success · partial(못 지운 단위가 있음) · skipped(때가 아님 · 꺼짐) · error


def _write(db: Session, rows: Sequence[dict[str, object]]) -> None:
    """묶음마다 확정한다 - 도중에 실패해도 넣은 묶음은 남는다. 지우기는 끝까지 받은 뒤에만 한다."""

    for start in range(0, len(rows), UPSERT_BATCH):
        upsert_public_places(db, rows[start:start + UPSERT_BATCH])
        db.commit()


def _written_since(db: Session, *, source: str, since: datetime) -> int:
    return sum(count_public_places_by(db, source=source, column="category", since=since).values())


def _unit_passes(before: int, touched: int) -> bool:
    """단위(TourAPI 유형 · 상가정보 시도)의 이번 고유 행이 기존의 80% 이상인가 - 기존이 없으면 통과."""

    return not before or touched >= before * PRUNE_MIN_RATIO


def _failure_reason(exc: Exception) -> str:
    """상태 표에 남길 짧은 이유 - TourAPI 오류 문구는 키를 빼고 만들어져 있다. 그 밖은 예외 이름만(값이 섞이지 않게)."""

    return str(exc)[:300] if isinstance(exc, TourApiConfigurationError) else type(exc).__name__


def _start_run(db: Session, *, source: str, started: datetime) -> None:
    """첫 호출 · 첫 줄 전에 시도를 남기고 확정한다 - 도중에 죽거나 앱을 다시 띄워도 그날은 다시 하지 않게."""

    record_sync_state(db, source=source, attempted_at=started, outcome="running")
    db.commit()


def _record_failure(db: Session, *, source: str, started: datetime, received: int, exc: Exception) -> None:
    try:
        record_sync_state(
            db, source=source, attempted_at=started, outcome="error", received=received,
            written=_written_since(db, source=source, since=started), error=_failure_reason(exc),
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("public_places_sync_state_not_saved source=%s", source)


def _close_run(
    db: Session, *, source: str, started: datetime, received: int, skipped: int, pruned: int, outcome: str,
) -> PublicPlacesLoadResult:
    written = _written_since(db, source=source, since=started)
    if outcome == "success" and written == 0:
        outcome = "partial"   # 한 건도 못 썼다 - 깨끗한 성공처럼 보이면 안 된다
    record_sync_state(
        db, source=source, attempted_at=started, outcome=outcome, received=received, written=written, pruned=pruned,
    )
    db.commit()
    return PublicPlacesLoadResult(source, received, written, skipped, pruned, outcome)


def sync_tourapi_places(
    db: Session, client: TourApiPageSource, *, now: datetime
) -> PublicPlacesLoadResult:
    """TourAPI 6개 유형 전국 목록을 다시 받는다(약 50회 호출). 유형마다 첫 페이지 totalCount 만큼 페이지를 받고, 그 유형을
    끝까지 받았는지(페이지마다 totalCount 가 같고, 받은 항목 · 고유 contentid 가 totalCount 와 정확히 같고, 이번 고유 행이 기존의
    80% 이상) 본 뒤 통과한 유형의 오래된 행만 지운다. 도중에 실패하면 상태를 error 로 남기고 예외를 올린다 - 지운 행은 없다."""

    before = count_public_places_by(db, source=TOURAPI, column="category")
    _start_run(db, source=TOURAPI, started=now)
    received = skipped = 0
    complete_types: list[str] = []
    try:
        for content_type_id in TOURAPI_CONTENT_TYPES:
            first = client.list_area_based_page(
                content_type_id=content_type_id, page=1, rows=TOURAPI_PAGE_ROWS, timeout=TOURAPI_TIMEOUT_SECONDS
            )
            entries = 0
            ids: set[str] = set()
            consistent = True
            for number in range(1, max(1, math.ceil(first.total_count / TOURAPI_PAGE_ROWS)) + 1):
                page = first if number == 1 else client.list_area_based_page(
                    content_type_id=content_type_id, page=number, rows=TOURAPI_PAGE_ROWS, timeout=TOURAPI_TIMEOUT_SECONDS
                )
                consistent = consistent and page.total_count == first.total_count
                rows = [row for row in (tourapi_row(entry, now) for entry in page.items) if row is not None]
                entries += len(page.items)
                received += len(page.items)   # 페이지마다 누적 - 도중에 실패해도 받은 만큼 남는다
                skipped += len(page.items) - len(rows)
                ids.update(str(entry.get("contentid") or "").strip() for entry in page.items)
                _write(db, rows)
            ids.discard("")
            if consistent and entries == first.total_count and len(ids) == first.total_count:
                complete_types.append(content_type_id)
    except Exception as exc:
        db.rollback()
        _record_failure(db, source=TOURAPI, started=now, received=received, exc=exc)
        raise
    touched = count_public_places_by(db, source=TOURAPI, column="category", since=now)
    passed = [
        content_type_id for content_type_id in complete_types
        if _unit_passes(
            sum(before.get(category, 0) for category in TOURAPI_TYPE_CATEGORIES[content_type_id]),
            sum(touched.get(category, 0) for category in TOURAPI_TYPE_CATEGORIES[content_type_id]),
        )
    ]
    if len(passed) < len(TOURAPI_CONTENT_TYPES):
        logger.warning("public_places_prune_limited source=tourapi kept_types=%s", sorted(set(TOURAPI_CONTENT_TYPES) - set(passed)))
    pruned = prune_public_places(
        db, source=TOURAPI, synced_before=now,
        categories=[category for content_type_id in passed for category in TOURAPI_TYPE_CATEGORIES[content_type_id]],
    )
    outcome = "success" if len(passed) == len(TOURAPI_CONTENT_TYPES) else "partial"
    return _close_run(
        db, source=TOURAPI, started=now, received=received, skipped=skipped, pruned=pruned, outcome=outcome,
    )


def tourapi_sync_due(db: Session, *, now: datetime, run_at: time) -> bool:
    """자동 동기화를 지금 돌릴 때인가 - KST 로 RUN_AT 뒤이고, 오늘(KST) 아직 시도하지 않았고, 마지막 성공 날짜(KST)에서 7일이 지났을 때(날짜로 세어 매주 같은 시각에 돈다).
    상태가 DB 에 있어 앱을 다시 띄워도 판단이 같다. 손으로 돌리는 스크립트는 이것을 보지 않는다."""

    local = now + KST_OFFSET
    if local.time() < run_at:
        return False
    state = get_sync_state(db, source=TOURAPI)
    if state is None:
        return True
    if (state.last_attempt_at + KST_OFFSET).date() == local.date():
        return False
    if state.last_success_at is None:
        return True
    return (local.date() - (state.last_success_at + KST_OFFSET).date()).days >= TOURAPI_SYNC_DAYS
```

`backend/app/services/public_places_scheduler.py`를 만든다.

```python
"""주 1회 TourAPI 공공데이터 장소 동기화(카카오 운영정책 2단계, public_places).

정책 수집 스케줄러와 같은 꼴(앱 수명 주기의 asyncio 작업, 켜는 설정 · RUN_AT · 폴링)이지만 때는 DB 상태로 가린다 -
폴링마다 tourapi_sync_due 가 'KST RUN_AT 뒤 · 오늘 아직 시도 안 함 · 마지막 성공이 7일 넘음'일 때만 받는다. 시도는 첫 호출 전에
running 으로 남기므로 앱을 다시 띄우거나 도중에 죽어도 그날은 다시 하지 않는다(TourAPI 개발 계정은 하루 1,000회). 일부 · 오류는
다음 날 다시 받는다. PUBLIC_PLACES_SYNC_ENABLED 로 따로 켠다(기본 꺼짐). 처음 적재는 scripts/sync_public_places_tourapi.py.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.core.config import Settings, settings
from app.db.session import get_session_factory
from app.services.notification_scheduler import parse_run_at
from app.services.public_places import (
    TOURAPI,
    PublicPlacesLoadResult,
    sync_tourapi_places,
    tourapi_sync_due,
    utc_now,
)
from app.services.tour_api import TourApiConfigurationError, build_tour_api_client

logger = logging.getLogger(__name__)


def _quiet(outcome: str) -> PublicPlacesLoadResult:
    return PublicPlacesLoadResult(TOURAPI, 0, 0, 0, 0, outcome)


def run_public_places_sync_once(settings_obj: Settings = settings, *, now: datetime | None = None) -> PublicPlacesLoadResult:
    try:
        client = build_tour_api_client(settings_obj)
    except TourApiConfigurationError:
        logger.warning("public_places_sync_tour_api_misconfigured")
        return _quiet("skipped")
    if client is None:
        return _quiet("skipped")
    moment = now or utc_now()
    try:
        with get_session_factory()() as db:
            if not tourapi_sync_due(db, now=moment, run_at=parse_run_at(settings_obj.public_places_sync_run_at)):
                return _quiet("skipped")
            result = sync_tourapi_places(db, client, now=moment)
    except Exception:
        logger.exception("public_places_sync_failed")   # 상태 표에는 sync 가 error 로 남겼다
        return _quiet("error")
    log = logger.info if result.outcome == "success" else logger.warning
    log(
        "public_places_sync_finished outcome=%s received=%s written=%s pruned=%s",
        result.outcome, result.received_count, result.parsed_count, result.pruned_count,
    )
    return result


async def _run_forever(settings_obj: Settings) -> None:
    try:
        while True:
            await asyncio.to_thread(run_public_places_sync_once, settings_obj)
            await asyncio.sleep(settings_obj.public_places_sync_poll_seconds)
    except asyncio.CancelledError:
        logger.info("public_places_sync_scheduler_stopped")
        raise


def start_public_places_sync_scheduler(settings_obj: Settings = settings) -> asyncio.Task[None] | None:
    if not settings_obj.public_places_sync_enabled:
        return None
    parse_run_at(settings_obj.public_places_sync_run_at)   # 잘못된 값이면 앱이 뜰 때 멈춘다
    if settings_obj.public_places_sync_poll_seconds < 1:
        raise ValueError("PUBLIC_PLACES_SYNC_POLL_SECONDS must be greater than 0.")
    return asyncio.create_task(_run_forever(settings_obj), name="travel-hunter-public-places-sync")


async def stop_public_places_sync_scheduler(task: asyncio.Task[None] | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
```

`backend/app/core/config.py`의 `external_collection_min_parsed_count` 정의 다음에 더한다.

```python
    # 공공데이터 장소(public_places) TourAPI 주 1회 동기화 - 기본 꺼짐. RUN_AT 은 KST. 처음 적재는 scripts/sync_public_places_tourapi.py
    public_places_sync_enabled: bool = os.getenv(
        "PUBLIC_PLACES_SYNC_ENABLED", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}
    public_places_sync_run_at: str = os.getenv("PUBLIC_PLACES_SYNC_RUN_AT", "04:00")
    public_places_sync_poll_seconds: int = int(
        os.getenv("PUBLIC_PLACES_SYNC_POLL_SECONDS", "300")
    )
```

`backend/app/main.py`
- import 묶음에 `from app.services.public_places_scheduler import start_public_places_sync_scheduler, stop_public_places_sync_scheduler`를 더한다.
- `lifespan`을 아래로 바꾼다.

```python
async def lifespan(_app: FastAPI):
    notification_scheduler_task = start_notification_scheduler()
    external_collection_scheduler_task = start_external_collection_scheduler()
    public_places_sync_task = start_public_places_sync_scheduler()
    try:
        yield
    finally:
        await stop_public_places_sync_scheduler(public_places_sync_task)
        await stop_external_collection_scheduler(external_collection_scheduler_task)
        await stop_notification_scheduler(notification_scheduler_task)
```

`.env.example`의 `EXTERNAL_COLLECTION_MIN_PARSED_COUNT=1` 줄 다음에 더한다.

```
# 공공데이터 장소(public_places) TourAPI 주 1회 동기화 - 기본 꺼짐, RUN_AT 은 KST. 처음 적재는 scripts/sync_public_places_tourapi.py 로 손으로(서버는 승인 뒤)
PUBLIC_PLACES_SYNC_ENABLED=change-me-{true | false}
PUBLIC_PLACES_SYNC_RUN_AT=04:00
PUBLIC_PLACES_SYNC_POLL_SECONDS=300
```

`compose.local.yaml`의 `EXTERNAL_COLLECTION_POLL_SECONDS: ${EXTERNAL_COLLECTION_POLL_SECONDS:-60}` 줄 다음에 더한다(같은 들여쓰기).

```yaml
      PUBLIC_PLACES_SYNC_ENABLED: ${PUBLIC_PLACES_SYNC_ENABLED:-false}
      PUBLIC_PLACES_SYNC_RUN_AT: ${PUBLIC_PLACES_SYNC_RUN_AT:-04:00}
      PUBLIC_PLACES_SYNC_POLL_SECONDS: ${PUBLIC_PLACES_SYNC_POLL_SECONDS:-300}
```

`backend/scripts/sync_public_places_tourapi.py`를 만든다.

```python
"""TourAPI 공공데이터 장소를 지금 받는다(카카오 운영정책 2단계 - public_places).

    cd backend
    python scripts/sync_public_places_tourapi.py

6개 유형 전국 목록(약 50회 호출 - 개발 계정 하루 1,000회 몫)을 받아 넣는다. 유형마다 끝까지 받았는지 본 뒤 통과한 유형의 오래된
행만 지운다. 자동 동기화(PUBLIC_PLACES_SYNC_ENABLED)와 같은 함수지만 때(오늘 시도 · 7일)를 가리지 않는다 - 처음 적재나 손으로 다시
받을 때 쓴다. 종료 코드: success 0, partial 2(못 지운 유형이 있음), error 1. 서버에서 돌리는 것은 실행할 때마다 승인받는다.
TOUR_API_ENABLED=true + TOUR_API_SERVICE_KEY 가 없으면 아무것도 하지 않는다. 키는 찍지 않는다.
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.services.public_places import sync_tourapi_places, utc_now
from app.services.tour_api import build_tour_api_client


def main() -> int:
    client = build_tour_api_client()
    if client is None:
        print("tour_api_disabled; no-op")
        return 0

    from app.db.session import get_session_factory

    try:
        with get_session_factory()() as db:
            result = sync_tourapi_places(db, client, now=utc_now())
    except Exception as exc:   # 상태 표(public_place_sync_state)에는 error 로 남았다
        print(f"source=tourapi outcome=error reason={type(exc).__name__}")
        return 1
    print(
        f"source={result.source} received={result.received_count} written={result.parsed_count} "
        f"skipped={result.skipped_count} pruned={result.pruned_count} outcome={result.outcome}"
    )
    return 0 if result.outcome == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_tour_api_client.py tests/test_public_places.py tests/test_public_places_scheduler.py tests/test_photo_review.py`
기대: 모두 PASS. 사진 검토 시험(TourAPI 클라이언트를 쓴다)도 그대로 PASS - `_request_items`의 동작이 같다. 정책 수집 스케줄러 코드는 건드리지 않는다.

---

### Task 5: 상가정보 적재

**파일:**
- 고치기: `backend/app/services/public_places.py`
- 만들기: `backend/scripts/load_public_places_sangga.py`
- 고치기: `backend/tests/test_public_places.py`

**인터페이스:**
- 받는 것: 과제 2의 `sangga_row` · `_region_city`, 과제 4의 `UPSERT_BATCH` · `_write` · `_start_run` · `_record_failure` · `_unit_passes` · `_close_run` · `PublicPlacesLoadResult`.
- 내놓는 것:
  - `iter_sangga_rows(paths: Sequence[Path], *, only: str | None = None) -> Iterator[dict[str, str]]`
  - `load_sangga_places(db, rows: Iterable[dict[str, str]], *, now: datetime, prune: bool = True) -> PublicPlacesLoadResult` - `prune=True`면 끝까지 읽은 뒤 시도마다 80%를 넘은 시도의 오래된 행만 지운다

- [ ] **1단계: 실패하는 시험 쓰기** - `backend/tests/test_public_places.py`

import에 `import csv`, `import io`, `import zipfile`, `from pathlib import Path`와 `from app.services.public_places import iter_sangga_rows, load_sangga_places`를 더하고, 파일 끝에 더한다.

```python
SANGGA_FIELDS = ["상가업소번호", "상호명", "지점명", "상권업종대분류코드", "상권업종중분류코드", "시도명", "시군구명", "지번주소", "도로명주소", "경도", "위도"]


def store(store_id: str, name: str, major: str = "I2", middle: str = "I201", lat: str = "34.7440") -> dict[str, str]:
    return {**CAFE, "상가업소번호": store_id, "상호명": name, "지점명": "", "상권업종대분류코드": major, "상권업종중분류코드": middle, "위도": lat}


def sejong(store_id: str, name: str, major: str = "I2") -> dict[str, str]:
    return {**store(store_id, name, major), "시도명": "세종특별자치시", "시군구명": "세종특별자치시"}


def write_zip(tmp_path: Path, members: dict[str, list[dict[str, str]]]) -> Path:
    path = tmp_path / "sangga.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for member, rows in members.items():
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=SANGGA_FIELDS)
            writer.writeheader()
            writer.writerows([{field: row.get(field, "") for field in SANGGA_FIELDS} for row in rows])
            archive.writestr(member, buffer.getvalue().encode("utf-8-sig"))   # 20260630판과 같은 BOM 붙은 UTF-8
    return path


def test_sangga_zip_is_read_row_by_row_and_only_filters_member_files(tmp_path: Path) -> None:
    path = write_zip(tmp_path, {
        "소상공인시장진흥공단_상가(상권)정보_세종_202606.csv": [sejong("A", "세종식당")],
        "소상공인시장진흥공단_상가(상권)정보_전남광주_202606.csv": [store("B", "여수식당"), store("C", "여수마트", "G2", "G204")],
        "readme.txt": [],
    })
    assert [row["상가업소번호"] for row in iter_sangga_rows([path])] == ["A", "B", "C"]
    assert [row["상가업소번호"] for row in iter_sangga_rows([path], only="세종")] == ["A"]


def test_sangga_load_keeps_travel_rows_and_only_full_loads_prune(db: Session) -> None:
    rows = [store(f"S{n}", f"식당{n}") for n in range(10)] + [store("M", "마트", "G2", "G204"), store("X", "좌표없음", lat="")]
    first = load_sangga_places(db, iter(rows), now=T1)
    assert (first.received_count, first.parsed_count, first.skipped_count, first.outcome) == (12, 10, 2, "success")
    partial = load_sangga_places(db, iter(rows[:1]), now=T2, prune=False)   # --only 처럼 일부만 - 다른 행을 지우지 않는다
    assert (partial.pruned_count, partial.outcome) == (0, "partial")
    full = load_sangga_places(db, iter(rows[:9]), now=T3)   # 새 판에서 하나가 문을 닫았다
    assert (full.pruned_count, full.outcome) == (1, "success")
    assert count_public_places(db, source="sangga") == 9


def test_a_province_missing_from_the_file_is_kept_and_the_load_is_partial(db: Session) -> None:
    yeosu = [store(f"Y{n}", f"여수식당{n}") for n in range(20)]
    assert load_sangga_places(db, iter(yeosu + [sejong("S0", "세종식당0"), sejong("S1", "세종식당1")]), now=T1).outcome == "success"
    # 새 판에서 여수 가게 하나가 문을 닫았고 세종 파일이 빠졌다 - 전남은 지우고, 세종은 남기고, 판이 덜 왔으니 partial
    full = load_sangga_places(db, iter(yeosu[:19]), now=T2)
    assert (full.pruned_count, full.outcome) == (1, "partial")
    assert {row.source_id for row in db.scalars(select(PublicPlace).where(PublicPlace.sido == "세종"))} == {"S0", "S1"}


def test_a_province_that_shrinks_sharply_keeps_its_rows(db: Session) -> None:
    yeosu = [store(f"Y{n}", f"여수식당{n}") for n in range(10)]
    sejongs = [sejong(f"S{n}", f"세종식당{n}") for n in range(10)]
    load_sangga_places(db, iter(yeosu + sejongs), now=T1)
    # 새 판에서 세종이 10 → 1 곳으로 줄었다 - 전체로는 11/20 이지만 시도마다 본다
    shrunk = load_sangga_places(db, iter(yeosu + sejongs[:1]), now=T2)
    assert (shrunk.pruned_count, shrunk.outcome) == (0, "partial")
    # 세종 줄이 소매뿐이어도(여행 업종 0건) 읽은 시도로 센다 - 0건이 된 시도도 지우지 않는다
    emptied = load_sangga_places(db, iter(yeosu + [sejong("M", "세종마트", "G2")]), now=T3)
    assert (emptied.pruned_count, emptied.outcome) == (0, "partial")
    assert count_public_places(db, source="sangga") == 20


def test_the_same_store_in_two_files_is_counted_once(db: Session, tmp_path: Path) -> None:
    path = write_zip(tmp_path, {"a_세종_202606.csv": [sejong("A", "가게")], "b_세종_202606.csv": [sejong("A", "가게")]})
    result = load_sangga_places(db, iter_sangga_rows([path]), now=T1)
    assert (result.received_count, result.parsed_count) == (2, 1)


def test_a_sangga_load_that_breaks_midway_keeps_written_batches_and_deletes_nothing(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(public_places, "UPSERT_BATCH", 2)
    seed(db, place_row("sangga", "OLD", "예전가게", synced_at=T1))

    def broken() -> Iterator[dict[str, str]]:
        yield store("S1", "식당1")
        yield store("S2", "식당2")
        yield store("S3", "식당3")
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad byte")   # 판이 바뀌어 인코딩이 다른 파일

    with pytest.raises(UnicodeDecodeError):
        load_sangga_places(db, broken(), now=T2)
    assert {row.source_id for row in db.scalars(select(PublicPlace))} == {"OLD", "S1", "S2"}   # 넣은 한 묶음만, 지운 것 없음
    state = get_sync_state(db, source="sangga")
    assert (state.last_outcome, state.received_count, state.last_error) == ("error", 3, "UnicodeDecodeError")
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_public_places.py`
기대: FAIL. `iter_sangga_rows` · `load_sangga_places`가 없다.

- [ ] **3단계: 구현**

`backend/app/services/public_places.py`의 import에 `import csv`, `import io`, `import zipfile`, `from collections.abc import Iterable, Iterator`(기존 `Sequence`와 같은 줄), `from pathlib import Path`를 더하고, 파일 끝에 더한다.

```python
SANGGA_ENCODING = "utf-8-sig"   # 20260630판. 판이 바뀌어 cp949 면 읽다 멈춘다 - 넣은 묶음만 남고 지운 행은 없다


def iter_sangga_rows(paths: Sequence[Path], *, only: str | None = None) -> Iterator[dict[str, str]]:
    """분기 파일(zip 안의 시도별 CSV, 또는 CSV)을 한 줄씩 - 1.4GB 를 메모리에 올리지 않는다. only 는 파일 이름에 든 말(예: 세종)."""

    for path in paths:
        if path.suffix.lower() == ".zip":
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    if not info.filename.lower().endswith(".csv") or (only and only not in info.filename):
                        continue
                    with archive.open(info) as raw:
                        yield from csv.DictReader(io.TextIOWrapper(raw, encoding=SANGGA_ENCODING, newline=""))
        elif not only or only in path.name:
            with path.open(encoding=SANGGA_ENCODING, newline="") as handle:
                yield from csv.DictReader(handle)


def load_sangga_places(
    db: Session, rows: Iterable[dict[str, str]], *, now: datetime, prune: bool = True,
) -> PublicPlacesLoadResult:
    """상가정보 한 판을 넣는다(여행 업종만). 1,000줄씩 묶어 쓰고 묶음마다 확정한다. prune=True 면 끝까지 읽은 뒤 읽은 시도마다
    이번 고유 행이 기존의 80% 이상인 시도의 오래된 행만 지운다. 읽은 시도는 여행 업종이 아닌 줄까지 포함해 정한다(0건이 된 시도도
    알아보게). DB 에 있는데 이번에 읽지 않은 시도(파일이 빠진 판)는 남기고 partial 이다. prune=False(일부 시도만)면 지우지 않는다."""

    before = count_public_places_by(db, source=SANGGA, column="sido")
    _start_run(db, source=SANGGA, started=now)
    received = skipped = 0
    read_sidos: set[str] = set()
    batch: list[dict[str, object]] = []
    try:
        for raw in rows:
            received += 1
            sido, _city = _region_city((raw.get("시도명") or "").strip(), (raw.get("시군구명") or "").strip())
            if sido:
                read_sidos.add(sido)
            row = sangga_row(raw, now)
            if row is None:
                skipped += 1
                continue
            batch.append(row)
            if len(batch) >= UPSERT_BATCH:
                _write(db, batch)
                batch = []
        _write(db, batch)
    except Exception as exc:
        db.rollback()
        _record_failure(db, source=SANGGA, started=now, received=received, exc=exc)
        raise
    if not prune:
        return _close_run(
            db, source=SANGGA, started=now, received=received, skipped=skipped, pruned=0, outcome="partial",
        )
    touched = count_public_places_by(db, source=SANGGA, column="sido", since=now)
    passed = sorted(sido for sido in read_sidos if _unit_passes(before.get(sido, 0), touched.get(sido, 0)))
    missing = sorted(sido for sido in before if sido and sido not in read_sidos)
    if len(passed) < len(read_sidos) or missing:
        logger.warning(
            "public_places_prune_limited source=sangga kept_sidos=%s missing_sidos=%s", sorted(read_sidos - set(passed)), missing,
        )
    pruned = prune_public_places(db, source=SANGGA, synced_before=now, sidos=passed)
    outcome = "success" if len(passed) == len(read_sidos) and not missing else "partial"
    return _close_run(
        db, source=SANGGA, started=now, received=received, skipped=skipped, pruned=pruned, outcome=outcome,
    )
```

`backend/scripts/load_public_places_sangga.py`를 만든다.

```python
"""소상공인 상가(상권)정보 분기 파일을 public_places 에 넣는다(카카오 운영정책 2단계).

    cd backend
    python scripts/load_public_places_sangga.py <파일.zip|파일.csv ...> [--only 세종] [--dry-run]

음식(I2) · 숙박(I1) · 예술·스포츠(R1)만 넣는다(20260630판 약 104만 건). 끝까지 읽은 뒤 시도마다 이번 고유 행이 기존의 80% 이상인
시도의 오래된 행만 지운다. --only 는 그 말이 이름에 든 시도 파일만 넣고 지우지 않는다(로컬 시험용). --dry-run 은 DB 를 건드리지
않고 분류별 건수만 센다. 종료 코드: success 0, partial 2(못 지운 시도가 있거나 빠진 시도가 있음), error 1.
파일은 data.go.kr 15083033 의 분기판. 서버에서 돌리는 것은 실행할 때마다 승인받는다.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.services.public_places import iter_sangga_rows, load_sangga_places, sangga_row, utc_now


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load SBIZ store data (food/stay/arts-sports) into public_places.")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--only", default=None, help="이 말이 이름에 든 시도 파일만(지우지 않는다)")
    parser.add_argument("--dry-run", action="store_true", help="DB 를 건드리지 않고 분류별 건수만 센다")
    args = parser.parse_args(argv)

    rows = iter_sangga_rows(args.paths, only=args.only)
    if args.dry_run:
        now = utc_now()
        counts = Counter((sangga_row(raw, now) or {}).get("category", "excluded") for raw in rows)
        print(" ".join(f"{key}={value}" for key, value in sorted(counts.items())), "(dry-run)")
        return 0

    from app.db.session import get_session_factory

    try:
        with get_session_factory()() as db:
            result = load_sangga_places(db, rows, now=utc_now(), prune=args.only is None)
    except Exception as exc:   # 상태 표(public_place_sync_state)에는 error 로 남았다
        print(f"source=sangga outcome=error reason={type(exc).__name__}")
        return 1
    print(
        f"source={result.source} received={result.received_count} written={result.parsed_count} "
        f"skipped={result.skipped_count} pruned={result.pruned_count} outcome={result.outcome}"
    )
    return 0 if result.outcome == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_public_places.py`
기대: 모두 PASS. 하나를 더 확인한다 - 로컬에 받아 둔 20260630판 zip(저장소 밖)으로 `python scripts/load_public_places_sangga.py <zip> --dry-run`을 돌려 `food` · `cafe` · `stay` · `leisure` · `culture` 합이 약 104만인지 본다(DB 안 건드림, 1~2분).

---

### Task 6: 맞춰 보기 API와 로그 제외

**파일:**
- 고치기: `backend/app/services/public_places.py`(맞춰 보기)
- 고치기: `backend/app/schemas/places.py`, `backend/app/api/routes/places.py`
- 고치기: `backend/app/core/debug_capture.py`
- 고치기: `backend/tests/test_public_places.py`, `backend/tests/test_debug_capture.py`

**인터페이스:**
- 받는 것: 과제 2 · 3의 `name_key` · `distance_m` · `public_places_in_box`.
- 내놓는 것:
  - `match_place(db, *, name: str, latitude: float, longitude: float, category_code: str | None) -> PlaceMatch` - `PlaceMatch(result: str, places: list[tuple[PublicPlace, float]])`
  - `match_place_response(db, *, name, latitude, longitude, category_code) -> dict` - API 모양(camelCase)
  - `POST /api/places/match` - 요청 `PlaceMatchRequest{name, latitude, longitude, categoryCode?}`, 응답 `PlaceMatchResponse{result, places: PublicPlaceItem[]}`

- [ ] **1단계: 실패하는 시험 쓰기**

`backend/tests/test_public_places.py` import에 아래를 더하고(`from app.models import PublicPlace`는 `from app.models import PublicPlace, User`로 바꾼다), 파일 끝에 시험을 더한다.

```python
import logging
import math

from fastapi.testclient import TestClient
from sqlalchemy import func

from app.api.dependencies import get_current_user
from app.db.session import get_optional_db
from app.main import app
from app.models import User
from app.services.public_places import WIDE_RADIUS_M, match_place
```

```python
def test_one_same_named_place_of_a_fitting_kind_is_a_match(db: Session) -> None:
    seed(db, place_row("tourapi", "1", "오동도", 34.7443, 127.7663, "sight"))
    found = match_place(db, name="오동도 ", latitude=34.7450, longitude=127.7670, category_code="AT4")
    assert found.result == "match"
    assert [place.source_id for place, _ in found.places] == ["1"]


def test_the_same_name_in_both_sources_asks_instead_of_guessing(db: Session) -> None:
    # TourAPI 와 상가정보가 약 48m 떨어져 같은 이름 - 같은 곳이라 단정하지 않는다(가까운 순 후보)
    seed(db, place_row("tourapi", "1", "오동도", 34.7443, 127.7663, "sight"), place_row("sangga", "S1", "오동도", 34.7447, 127.7665, "leisure"))
    found = match_place(db, name="오동도", latitude=34.7450, longitude=127.7670, category_code="AT4")
    assert found.result == "candidates"
    assert [place.source_id for place, _ in found.places] == ["S1", "1"]   # 약 57m · 101m


def test_a_same_named_place_of_another_or_unknown_kind_is_only_a_candidate(db: Session) -> None:
    seed(db, place_row("sangga", "S", "바다정원", 34.7443, 127.7663, "stay"))
    assert match_place(db, name="바다정원", latitude=34.7443, longitude=127.7663, category_code="CE7").result == "candidates"
    assert match_place(db, name="바다정원", latitude=34.7443, longitude=127.7663, category_code="AD5").result == "match"
    assert match_place(db, name="바다정원", latitude=34.7443, longitude=127.7663, category_code=None).result == "candidates"   # 분류를 모르면 맞는지 알 수 없다
    assert match_place(db, name="바다정원", latitude=34.7443, longitude=127.7663, category_code="MT1").result == "candidates"   # 표에 없는 코드


def test_two_shops_with_the_same_name_ask_which_one(db: Session) -> None:
    seed(db, place_row("sangga", "A", "이디야커피", 34.7443, 127.7663), place_row("sangga", "B", "이디야커피", 34.7455, 127.7663))
    found = match_place(db, name="이디야 커피", latitude=34.7449, longitude=127.7663, category_code="CE7")
    assert found.result == "candidates"
    assert {place.source_id for place, _ in found.places} == {"A", "B"}


def test_radius_is_1km_for_tourapi_sights_and_200m_otherwise_and_for_sangga(db: Session) -> None:
    far = 34.7443 + 0.006   # 약 667m 북쪽
    seed(db, place_row("tourapi", "T", "향일암", far, 127.7663, "sight"), place_row("sangga", "S", "향일암", far, 127.7663))
    sight = match_place(db, name="향일암", latitude=34.7443, longitude=127.7663, category_code="AT4")
    assert sight.result == "match" and [place.source for place, _ in sight.places] == ["tourapi"]   # 상가정보는 200m 밖
    assert match_place(db, name="향일암", latitude=34.7443, longitude=127.7663, category_code="FD6").result == "none"


def test_places_just_inside_the_radius_are_not_lost_at_the_box_edge(db: Session) -> None:
    step = (WIDE_RADIUS_M - 1) / (6_371_000 * math.pi / 180)   # 거리 함수 기준 정북 999m
    seed(db, place_row("tourapi", "T", "향일암", 34.7443 + step, 127.7663, "sight"))
    assert match_place(db, name="향일암", latitude=34.7443, longitude=127.7663, category_code="AT4").result == "match"


def test_a_partial_name_gives_up_to_three_candidates_nearest_first(db: Session) -> None:
    seed(db, *[place_row("sangga", f"S{n}", f"오동도횟집{n}", 34.7443 + n * 0.0002, 127.7663) for n in range(5)])
    found = match_place(db, name="오동도", latitude=34.7443, longitude=127.7663, category_code="FD6")
    assert found.result == "candidates"
    assert [place.source_id for place, _ in found.places] == ["S0", "S1", "S2"]


def test_one_letter_and_symbol_only_names_never_match_loosely(db: Session) -> None:
    seed(db, place_row("sangga", "S", "섬마을", 34.7443, 127.7663))
    assert match_place(db, name="섬", latitude=34.7443, longitude=127.7663, category_code=None).result == "none"
    assert match_place(db, name=" - · ", latitude=34.7443, longitude=127.7663, category_code=None).result == "none"


USER = User(id=1, email="u@example.com", nickname="u", onboarding_completed=True,
            created_at=datetime(2026, 10, 4), updated_at=datetime(2026, 10, 4))


def test_match_route_needs_login_and_answers_in_camel_case(db: Session) -> None:
    seed(db, place_row("tourapi", "126508", "오동도", 34.7443, 127.7663, "sight", photo="http://tong.visitkorea.or.kr/a.jpg"))
    client = TestClient(app)
    app.dependency_overrides[get_optional_db] = lambda: db
    try:
        anonymous = client.post("/api/places/match", json={"name": "오동도", "latitude": 34.7443, "longitude": 127.7663})
        app.dependency_overrides[get_current_user] = lambda: USER
        found = client.post("/api/places/match", json={"name": "오동도", "latitude": 34.7443, "longitude": 127.7663, "categoryCode": "AT4"})
        outside = client.post("/api/places/match", json={"name": "오동도", "latitude": 10.0, "longitude": 127.7663})
    finally:
        app.dependency_overrides.pop(get_optional_db, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert anonymous.status_code == 401
    assert found.status_code == 200
    assert found.json() == {"result": "match", "places": [{
        "source": "tourapi", "sourceId": "126508", "name": "오동도", "address": "전남광주통합특별시 여수시 수정동 1",
        "latitude": 34.7443, "longitude": 127.7663, "category": "sight", "sido": "전남", "city": "여수",
        "photoUrl": "http://tong.visitkorea.or.kr/a.jpg", "photoLicense": "Type3", "distanceMeters": 0,
    }]}
    assert outside.status_code == 422


def test_match_never_writes_or_logs_the_values_it_received(db: Session, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    client = TestClient(app)
    app.dependency_overrides[get_optional_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: USER
    try:
        response = client.post("/api/places/match", json={"name": "카카오에서온가게이름", "latitude": 34.7443, "longitude": 127.7663})
    finally:
        app.dependency_overrides.pop(get_optional_db, None)
        app.dependency_overrides.pop(get_current_user, None)
    assert response.json() == {"result": "none", "places": []}
    assert "카카오에서온가게이름" not in caplog.text
    assert db.scalar(select(func.count()).select_from(PublicPlace)) == 0
```

`backend/tests/test_debug_capture.py`의 `test_auth_and_password_paths_are_excluded_even_if_the_rule_names_them` 다음에 더한다(파일의 `build` · `lines` · `debug_lines`를 쓴다. 이 파일의 규칙은 `policyId`를 남기는 필드로 둔다).

```python
def test_place_paths_are_excluded_even_if_the_rule_names_them(lines):
    # 일정 장소 · 맞춰 보기 본문에는 카카오 장소값(이름 · 주소 · 좌표)이 온다 - 설정과 무관하게 남기지 않는다(카카오 운영정책)
    capture = build(log_debug_body_paths=("POST /api/places/*", "POST /api/trips/*", "PATCH /api/trips/*"))
    for method, path in (
        ("POST", "/api/places/match"),
        ("POST", "/api/trips/1/days/1/places"),
        ("POST", "/api/trips/1/days/1/places/batch"),
        ("PATCH", "/api/trips/1/places/2"),
    ):
        capture.observe(method=method, path=path, user_id=42, body=b'{"policyId": 1}')
    assert debug_lines(lines) == []
    capture.observe(method="POST", path="/api/trips/1/policies", user_id=42, body=b'{"policyId": 1}')
    assert len(debug_lines(lines)) == 1   # 장소가 아닌 일정 경로는 그대로 잡는다
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_public_places.py tests/test_debug_capture.py`
기대: FAIL. `match_place` · `WIDE_RADIUS_M`이 없고, 라우트가 없어 404/405, 장소 경로가 debug capture에 잡힌다.

- [ ] **3단계: 구현**

`backend/app/services/public_places.py`의 import에 `from app.models import PublicPlace`를 더하고, 저장소 import 묶음에 `public_places_in_box`를 합친다. 파일 끝에 더한다.

```python
# 맞춰 보기 반경(2026-10-03 실측과 같은 기준): 카카오 분류가 관광명소 · 문화시설이면 TourAPI 1km, 그 밖과 상가정보는 200m
WIDE_KAKAO_CATEGORIES = frozenset({"AT4", "CT1"})
WIDE_RADIUS_M = 1000
NEAR_RADIUS_M = 200
# 고른 카카오 분류와 맞는 공공데이터 분류. 분류가 없거나 이 다섯 코드가 아니면 맞는지 알 수 없으므로 바로 담지 않고 후보로 보인다
KAKAO_TO_PUBLIC_CATEGORIES = {
    "AT4": frozenset({"sight", "culture", "leisure", "shopping"}),
    "CT1": frozenset({"culture", "sight", "leisure"}),
    "FD6": frozenset({"food", "cafe"}),
    "CE7": frozenset({"cafe", "food"}),
    "AD5": frozenset({"stay"}),
}
MAX_CANDIDATES = 3
METERS_PER_DEGREE = 6_371_000 * math.pi / 180   # distance_m 과 같은 지구 반경(약 111,195m)
BOX_MARGIN = 1.01   # 상자가 반경 안쪽 끝을 놓치지 않게 조금 넓게


@dataclass(frozen=True)
class PlaceMatch:
    result: str   # match · candidates · none
    places: list[tuple[PublicPlace, float]]


def _fits(category_code: str | None, place: PublicPlace) -> bool:
    allowed = KAKAO_TO_PUBLIC_CATEGORIES.get(category_code or "")
    return allowed is not None and place.category in allowed


def match_place(
    db: Session, *, name: str, latitude: float, longitude: float, category_code: str | None
) -> PlaceMatch:
    """고른 카카오 장소의 이름 · 좌표를 우리 장소 기반과 견준다. 받은 값은 이 함수 안에서만 쓰고 버린다(저장 · 로그 금지).
    바로 담기는 이름이 같은 곳이 반경 안에 하나뿐이고 분류가 맞을 때만 - 두 출처에 같은 이름이 있으면 둘로 센다."""

    key = name_key(name)
    if not key:
        return PlaceMatch("none", [])
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


def public_place_item(place: PublicPlace, distance: float) -> dict[str, object]:
    return {
        "source": place.source,
        "sourceId": place.source_id,
        "name": place.name,
        "address": place.address,
        "latitude": place.latitude,
        "longitude": place.longitude,
        "category": place.category,
        "sido": place.sido,
        "city": place.city,
        "photoUrl": place.photo_url,
        "photoLicense": place.photo_license,
        "distanceMeters": round(distance),
    }


def match_place_response(
    db: Session, *, name: str, latitude: float, longitude: float, category_code: str | None
) -> dict[str, object]:
    found = match_place(db, name=name, latitude=latitude, longitude=longitude, category_code=category_code)
    return {"result": found.result, "places": [public_place_item(place, distance) for place, distance in found.places]}
```

`backend/app/schemas/places.py`
- `from pydantic import BaseModel`을 `from pydantic import BaseModel, Field`로 바꾸고 파일 끝에 더한다.

```python
PublicPlaceCategory = Literal["sight", "culture", "leisure", "stay", "shopping", "food", "cafe"]


class PlaceMatchRequest(BaseModel):
    """맞춰 보기(카카오 운영정책 2단계) - 고른 카카오 장소의 이름 · 좌표 · 분류. 서버는 비교에만 쓰고 저장 · 로그에 남기지 않는다.
    카카오 장소 ID 는 비교에 쓰지 않아 받지 않는다."""

    name: str = Field(min_length=1, max_length=100)
    latitude: float = Field(ge=33.0, le=39.0)
    longitude: float = Field(ge=124.0, le=132.0)
    categoryCode: str | None = Field(default=None, max_length=10)


class PublicPlaceItem(BaseModel):
    """우리 장소 기반(public_places)의 한 곳 - 공공데이터 값이다. source + sourceId 가 3단계에서 담을 때 쓰는 열쇠다."""

    source: Literal["tourapi", "sangga"]
    sourceId: str
    name: str
    address: str | None = None
    latitude: float
    longitude: float
    category: PublicPlaceCategory
    sido: str | None = None
    city: str | None = None
    photoUrl: str | None = None
    photoLicense: str | None = None
    distanceMeters: int


class PlaceMatchResponse(BaseModel):
    """match = 이름이 같은 곳이 하나이고 분류가 맞음(바로 담기), candidates = 확인할 후보 1~3곳, none = 나만의 장소로."""

    result: Literal["match", "candidates", "none"]
    places: list[PublicPlaceItem]
```

`backend/app/api/routes/places.py`
- import를 고친다: `from app.schemas.places import PlaceMatchRequest, PlaceMatchResponse, PlaceSearchItem`, `from app.services import place_search, public_places`. DB 는 다른 라우트처럼 이미 있는 `get_optional_db`로 받는다(로그인 확인과 같은 세션).
- 파일 끝에 더한다.

```python
@router.post("/match", response_model=PlaceMatchResponse)
def match_place(
    request: PlaceMatchRequest,
    current_user: User | None = Depends(get_current_user),
    db: Session | None = Depends(get_optional_db),
) -> PlaceMatchResponse:
    """고른 카카오 장소를 우리 장소 기반(public_places)과 맞춰 본다(카카오 운영정책 2단계). 로그인 확인과 같은 세션을 쓴다.
    받은 값은 비교에만 쓰고 저장 · 로그에 남기지 않는다 - debug_capture 도 장소 경로를 늘 뺀다."""

    if current_user is None or db is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return PlaceMatchResponse(
        **public_places.match_place_response(
            db,
            name=request.name,
            latitude=request.latitude,
            longitude=request.longitude,
            category_code=request.categoryCode,
        )
    )
```

`backend/app/core/debug_capture.py`의 `ALWAYS_EXCLUDED_MARKERS` 줄을 아래로 바꾼다.

```python
# place: 일정 장소 · 통합 검색 · 맞춰 보기 본문에는 카카오 장소값(이름 · 주소 · 좌표)이 온다 - 설정과 무관하게 남기지 않는다(카카오 운영정책)
ALWAYS_EXCLUDED_MARKERS = ("password", "token", "invite", "reset", "place")
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_public_places.py tests/test_debug_capture.py tests/test_place_search.py`
기대: 모두 PASS. 상자 끝 시험은 예전 계산(`111_320m/도`, 여유 없음)으로는 FAIL 이 나는지도 한 번 확인한다.

---

### Task 7: 설계 문서 · API 계약 · 골든 · 프론트 경계

**파일:**
- 고치기: `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`
- 고치기: `docs/mvp-api-contract.md`, `.agent/evals/api-contract-golden.json`
- 고치기: `frontend/src/api/types.ts`, `frontend/src/api/dataApi.ts`, `frontend/src/api/backendApi.ts`, `frontend/src/api/backendApi.test.ts`

**인터페이스:**
- 받는 것: 과제 6의 요청 · 응답 모양.
- 내놓는 것: 타입 `PlaceMatchRequest` · `PublicPlaceCategory` · `PublicPlaceItem` · `PlaceMatchResult`, `AppDataApi.matchPlace(request: PlaceMatchRequest): Promise<PlaceMatchResult>`. 3단계 화면이 쓴다.

- [ ] **1단계: 실패하는 시험 쓰기** - `frontend/src/api/backendApi.test.ts` 끝에 더한다.

```ts
describe("backendApi place matching", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts the picked place to the match endpoint and returns the server's answer", async () => {
    const answer = { result: "none", places: [] };
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(answer), { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    vi.stubGlobal("fetch", fetchSpy);
    const request = { name: "오동도", latitude: 34.7443, longitude: 127.7663, categoryCode: "AT4" };

    await expect(backendApi.matchPlace(request)).resolves.toEqual(answer);
    expect(fetchSpy).toHaveBeenCalledWith(
      `${apiConfig.baseUrl}/api/places/match`,
      expect.objectContaining({ method: "POST", body: JSON.stringify(request) }),
    );
  });
});
```

- [ ] **2단계: 실패하는지 확인**

실행: `cd frontend && npx vitest run src/api/backendApi.test.ts`
기대: FAIL. `backendApi.matchPlace is not a function`.

- [ ] **3단계: 구현**

`frontend/src/api/types.ts`의 `export type NearbyCategory = ...` 줄 다음에 더한다.

```ts
/** 맞춰 보기(POST /places/match) - 고른 카카오 장소를 우리 장소 기반과 견준다. 서버는 받은 값을 저장 · 로그에 남기지 않는다(카카오 운영정책) */
export type PlaceMatchRequest = {
  name: string;
  latitude: number;
  longitude: number;
  categoryCode?: string | null;
};

/** 공공데이터 장소 분류 - 서버 public_places.category 와 같은 7개 */
export type PublicPlaceCategory = "sight" | "culture" | "leisure" | "stay" | "shopping" | "food" | "cafe";

/** 우리 장소 기반(public_places)의 한 곳 - 공공데이터 값. source + sourceId 가 담을 때 쓰는 열쇠다(3단계) */
export type PublicPlaceItem = {
  source: "tourapi" | "sangga";
  sourceId: string;
  name: string;
  address?: string | null;
  latitude: number;
  longitude: number;
  category: PublicPlaceCategory;
  sido?: string | null;
  city?: string | null;
  photoUrl?: string | null;
  photoLicense?: string | null;
  distanceMeters: number;
};

/** match = 바로 담기, candidates = '이 장소가 맞나요?' 후보 1~3곳, none = 나만의 장소 */
export type PlaceMatchResult = {
  result: "match" | "candidates" | "none";
  places: PublicPlaceItem[];
};
```

`frontend/src/api/dataApi.ts`
- `./types`에서 가져오는 목록의 `NearbyCategory,` 다음 줄에 `PlaceMatchRequest,`와 `PlaceMatchResult,`를 더한다.
- `AppDataApi`의 `listNearbyPlaces: ...` 줄 다음에 `  matchPlace: (request: PlaceMatchRequest) => Promise<PlaceMatchResult>;`를 더한다.

`frontend/src/api/backendApi.ts`
- `./types`에서 가져오는 목록의 `NearbyCategory,` 다음 줄에 `PlaceMatchRequest,`와 `PlaceMatchResult,`를 더한다.
- `listNearbyPlaces: ...` 두 줄 다음에 더한다.

```ts
  matchPlace: (request: PlaceMatchRequest): Promise<PlaceMatchResult> =>
    apiClient.post<PlaceMatchResult>("/api/places/match", request),
```

`docs/superpowers/specs/2026-10-03-public-place-storage-design.md`를 이 계획의 결정에 맞춘다(문장 그대로 바꾼다).
- 1절 '갱신' 줄 `- 갱신: TourAPI는 주 1회 동기화한다(약 50회 호출). 실행 방식은 기존 정책 수집 스케줄러를 따르며 2단계 계획에서 정한다. 상가정보는 분기 파일을 받아 적재한다. 서버 적재는 실행할 때마다 승인받는다.` 끝에 이어 쓴다: ` 오래된 행은 단위마다 끝까지 받았을 때 그 단위만 지운다 - TourAPI 는 유형마다(페이지마다 totalCount 가 같고, 받은 항목 · 고유 contentid 가 totalCount 와 같고, 이번 고유 행이 기존의 80% 이상), 상가정보는 시도마다(파일을 끝까지 읽었고, 이번 고유 행이 기존의 80% 이상). 출처마다 시도(받기 전에 running)와 끝까지 받은 마지막 시각을 \`public_place_sync_state\`에 따로 둔다. 자동 동기화는 오늘(KST) 이미 시도했으면 쉬고, 마지막 성공이 7일 안이면 쉰다(일부 · 오류면 다음 날 다시).`
- 2절 2번 `2. 사용자가 장소를 고르면 프론트가 그 항목(카카오 ID, 이름, 좌표, 분류)을 맞춰 보기 API(\`POST /api/places/match\`, 로그인 필요)로 보낸다. 서버는 \`public_places\`에서 분류별 반경(관광명소·문화시설 1km, 나머지 200m) 안의 후보를 찾아 비교용 이름을 견준다. 받은 값은 저장하거나 로그에 남기지 않는다.`를 아래로 바꾼다.
  `2. 사용자가 장소를 고르면 프론트가 그 항목의 이름 · 좌표 · 분류를 맞춰 보기 API(\`POST /api/places/match\`, 로그인 필요)로 보낸다. 카카오 장소 ID 는 비교에 쓰지 않아 보내지 않는다. 서버는 \`public_places\`에서 반경 안의 후보를 찾아 비교용 이름을 견준다 - 카카오 분류가 관광명소 · 문화시설이면 TourAPI 장소는 1km, 그 밖과 상가정보 장소는 200m(실측과 같은 기준). 받은 값은 저장하거나 로그에 남기지 않는다.`
- `- 바로 담는 것은 반경 안에 이름이 같은 공공데이터 장소가 **하나뿐일 때**만이다. 둘 이상이면 후보 확인으로 보낸다.` 끝에 이어 쓴다: ` TourAPI 와 상가정보에 같은 이름이 함께 있어도 둘로 센다(같은 곳인지 단정하지 않는다). 고른 카카오 분류와 맞지 않거나(예: 카페를 골랐는데 같은 이름 숙소) 카카오 분류가 없거나 모르는 코드면 맞는지 알 수 없으므로 후보 확인이다. 그래서 바로 담기 비율은 실측 63%보다 낮다 - 3단계에서 실데이터로 다시 잰다.`

`docs/mvp-api-contract.md`의 `### GET /places/nearby` 절이 끝난 뒤(다음 `### ` 앞)에 더한다.

````markdown
### POST /places/match

카카오 운영정책 2단계(설계 `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`). 사용자가 고른 카카오 장소의 이름 · 좌표 · 분류를 우리 장소 기반(`public_places` - TourAPI 6개 유형, 소상공인 상가정보 음식 · 숙박 · 예술·스포츠)과 맞춰 본다. 서버는 받은 값을 비교에만 쓰고 저장하거나 로그에 남기지 않는다(`debug_capture` 도 장소 경로를 늘 뺀다). 반경은 카카오 분류가 관광명소 · 문화시설(`AT4` · `CT1`)이면 TourAPI 1km, 그 밖과 상가정보는 200m. 이름은 소문자로 바꾸고 띄어쓰기 · 기호를 빼고 견준다. 화면은 3단계 담는 흐름에서 쓴다. 로그인 필요.

- `match`: 이름이 같은 공공데이터 장소가 반경 안에 하나뿐이고, 고른 카카오 분류와 맞는다(관광명소 → `sight` · `culture` · `leisure` · `shopping`, 문화시설 → `culture` · `sight` · `leisure`, 음식점 · 카페 → `food` · `cafe`, 숙박 → `stay`). `places` 에 한 곳.
- `candidates`: 이름이 같은 곳이 둘 이상이거나(TourAPI 와 상가정보에 함께 있어도 둘로 센다), 하나뿐인데 분류가 맞지 않거나 카카오 분류가 없거나 위 다섯 코드가 아니거나, 한쪽 이름이 다른 쪽에 들어 있다(두 이름 모두 두 글자 이상). 가까운 순 최대 3곳.
- `none`: 맞는 곳이 없다 - 나만의 장소로 담는다. `places` 는 빈 배열.

**Request**
```json
{ "name": "오동도", "latitude": 34.7443, "longitude": 127.7663, "categoryCode": "AT4" }
```
- `name`: string, 1-100 chars. `latitude` 33-39, `longitude` 124-132. `categoryCode`: 카카오 분류 코드(선택, 10자 이하). 카카오 장소 ID 는 받지 않는다.

**Response 200** → `PlaceMatchResult`
```json
{
  "result": "match",
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
      "photoUrl": "http://tong.visitkorea.or.kr/cms/resource/23/3074123_image2_1.jpg",
      "photoLicense": "Type3",
      "distanceMeters": 0
    }
  ]
}
```
- `category`: `sight` · `culture` · `leisure` · `stay` · `shopping` · `food` · `cafe`. `photoUrl` · `photoLicense`(공공누리 `Type1` · `Type3`)는 TourAPI 만.

**Errors**
- 401: 인증 필요
- 422: 필드 누락 · 범위 위반
````

`.agent/evals/api-contract-golden.json`의 `"path": "/api/places/nearby"` 항목 바로 뒤에 아래 항목을 더한다(앞 항목 끝에 쉼표).

```json
{
  "method": "POST",
  "path": "/api/places/match",
  "status": 200,
  "authRequired": true,
  "request": {"name": "오동도", "latitude": 34.7443, "longitude": 127.7663, "categoryCode": "AT4"},
  "requiredFields": {"result": "string enum(match|candidates|none)", "places": "array"},
  "dbModeBehavior": "Authenticated users match a Kakao place they picked (name, coordinates, optional Kakao category code; no Kakao place id) against our own public place base (public_places: TourAPI six content types and SBIZ store data food/stay/arts-sports). The server compares in memory and never stores or logs the received values (debug capture always excludes place paths). Radius: TourAPI 1 km when the Kakao category is AT4/CT1, otherwise 200 m; store data always 200 m. Names compare lowercased without spaces or symbols. result=match only when exactly one same-named place is within the radius and its category fits the Kakao category (AT4: sight/culture/leisure/shopping, CT1: culture/sight/leisure, FD6/CE7: food/cafe, AD5: stay); candidates when two or more same-named places (a TourAPI row and a store row count as two), a single same-named place whose category does not fit or when the Kakao category is missing or not one of those five codes, or a partial name overlap (both names 2+ chars), nearest first, at most 3; none otherwise with an empty places array. Each place has source (tourapi|sangga), sourceId, name, address|null, latitude, longitude, category (sight|culture|leisure|stay|shopping|food|cafe), sido|null, city|null, photoUrl|null, photoLicense|null (TourAPI only), distanceMeters. latitude 33-39, longitude 124-132, name 1-100 chars or 422; 401 without login."
}
```

- [ ] **4단계: 통과하는지 확인**

실행: `cd frontend && npx vitest run src/api/backendApi.test.ts && npx tsc --noEmit -p . && cd .. && python -c "import json; json.load(open('.agent/evals/api-contract-golden.json', encoding='utf-8')); print('golden ok')"`
기대: PASS, 타입 오류 없음, `golden ok`.

---

### Task 8: 로컬 실측 · 문서 · 전체 검증 · 커밋

**파일:**
- 고치기: `docs/implemented-feature-spec.md`, `CHECKLIST.md`

- [ ] **1단계: 문서**
  - `docs/implemented-feature-spec.md`의 '장소로 근처 혜택 찾기' 행 바로 아래에 행을 더한다.

    > | 공공데이터 장소 기반(화면 없음) | 카카오 장소값을 저장하지 않으려고 공공데이터로 우리 장소 기반(`public_places`)을 만든다 - TourAPI 6개 유형(주 1회 동기화, `PUBLIC_PLACES_SYNC_ENABLED` 로 켬, 기본 꺼짐)과 소상공인 상가정보 음식 · 숙박 · 예술·스포츠(분기 파일, `scripts/load_public_places_sangga.py`). 오래된 행은 단위(TourAPI 유형 · 상가정보 시도)마다 끝까지 받았을 때만 지우고, 출처마다 시도 · 성공을 `public_place_sync_state` 에 둔다. 맞춰 보기 API 는 고른 카카오 장소의 이름 · 좌표 · 분류를 서버 안에서 견주고 버린다(바로 담기 · 후보 · 없음). 담는 화면은 3단계(설계: `docs/superpowers/specs/2026-10-03-public-place-storage-design.md`). 서버 적재는 실행할 때마다 승인받는다. | `POST /api/places/match` |

- [ ] **2단계: 로컬 실측(로컬 DB만 - 서버 · 개발서버 데이터는 건드리지 않는다)**

이 로컬 마이그레이션 · 적재는 이 계획 승인으로 함께 승인받는다(`.codex/local-runtime-notes.md` '승인 없이 공식 수집기/동기화 절차를 재실행하지 않는다'에 해당). 순서는 `.codex/skills/travel-hunter-workflow/SKILL.md` 4절을 따른다.

  - **덤프 → 검증 → 지문:** 저장소 밖 로컬 백업 폴더(700)에
    - `docker exec travel-hunter-onprem-db-1 sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > <백업 폴더>/local-before-0048-20261004.dump`
    - `chmod 600 <그 파일>` 뒤 `stat -c "%a %n" <그 파일>` → `600`
    - `docker exec -i travel-hunter-onprem-db-1 pg_restore -l < <그 파일> | head -5` → 목차가 나오면 되살릴 수 있다(나오지 않으면 멈춘다)
    - `sha256sum <그 파일>` → 지문을 작업 기록(CHECKLIST Recent Validation)에 남긴다. 문제가 나면 이 덤프를 `pg_restore --clean`으로 되돌린다.
  - **행 수(전):** `docker exec travel-hunter-onprem-db-1 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select (select count(*) from policies), (select count(*) from trips), (select count(*) from users), (select count(*) from external_source_records), (select count(*) from trip_places)"'`
  - **세 컨테이너를 이 워크트리로**(DB 볼륨은 그대로): 이 워크트리 루트에서 `docker compose --env-file /c/dev/travel-hunter/travel-hunter-onprem/.env -p travel-hunter-onprem -f compose.local.yaml up -d --build --force-recreate db backend frontend`. 세 컨테이너의 출처 라벨이 이 워크트리인지 본다(라벨만 - 환경 변수는 찍지 않는다): `for c in db backend frontend; do docker inspect --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' travel-hunter-onprem-$c-1; done`.
  - **마이그레이션:** `docker exec travel-hunter-onprem-backend-1 sh -c 'alembic upgrade head && alembic current'` → `0048_public_places (head)`.
  - **TourAPI 전체:** `docker exec travel-hunter-onprem-backend-1 python scripts/sync_public_places_tourapi.py` → 종료 코드 0, `received` 약 47,650, `outcome=success`(약 50회 호출).
  - **상가정보 한 시도:** 로컬에 받아 둔 20260630판 zip(저장소 밖)을 `docker cp <zip> travel-hunter-onprem-backend-1:/tmp/sangga.zip`으로 넣고 `docker exec travel-hunter-onprem-backend-1 python scripts/load_public_places_sangga.py /tmp/sangga.zip --only 세종` → 종료 코드 2(`partial` - 지우지 않음)이고 `written`이 수천 건이어야 한다. 0이면 이름 필터가 아무 파일도 고르지 못한 것이다(zip 안 파일 이름의 인코딩) - 멈추고 본다. 끝나면 `docker exec travel-hunter-onprem-backend-1 rm -f /tmp/sangga.zip`.
  - **건수 · 상태:** `docker exec travel-hunter-onprem-db-1 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select source, count(*) from public_places group by source order by 1; select source, last_outcome, last_success_at is not null from public_place_sync_state order by 1"'`
  - **실행계획:** `docker exec travel-hunter-onprem-db-1 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "explain analyze select * from public_places where latitude between 34.735 and 34.754 and longitude between 127.755 and 127.778"'` → `ix_public_places_lat_lng`를 쓰는 Index Scan 또는 Bitmap Index Scan.
  - **맞춰 보기(공공데이터 값으로 - 카카오 값 아님):** `docker exec travel-hunter-onprem-backend-1 python -c "from app.db.session import get_session_factory; from app.services.public_places import match_place_response; db = get_session_factory()(); r = match_place_response(db, name='오동도', latitude=34.7443, longitude=127.7663, category_code='AT4'); print(r['result'], [(p['source'], p['category'], p['distanceMeters']) for p in r['places']])"` → `match` · `tourapi` · `sight`(같은 이름이 상가정보 세종 쪽에는 없으므로).
  - **행 수(후):** 위와 같은 쿼리로 비교한다. `policies` · `trips` · `users` · `external_source_records` · `trip_places` 가 전과 같아야 한다 - 30% 넘게 변했으면 멈추고 보고한다.
  - 로컬 DB 가 개발서버(0047)보다 앞서므로, 머지 · 배포 전에는 로컬 정책 동기화 스크립트가 Alembic 불일치로 멈춘다(알고 넘어간다).

- [ ] **3단계: 전체 검증**
  - 백엔드: `cd backend && /c/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --deselect tests/test_stay_discount_semantics_snapshot.py`, `python -m alembic upgrade head --sql > /dev/null && echo SQL_OK`
  - compose: `docker compose --env-file /c/dev/travel-hunter/travel-hunter-onprem/.env -f compose.yaml config > /dev/null && echo COMPOSE_OK`(출력은 버린다 - 비밀값)
  - 프론트: `npx tsc --noEmit -p .`, `npm run test:mojibake`, `npx vitest run`(알려진 mypage 6개 실패는 따로 적는다), `npm run build`, `npm run test:e2e:containers`
  - `git diff --check`, 바꾼 diff와 새 파일의 U+FFFD 0건 · 한자 0건

- [ ] **4단계: CHECKLIST**
  - Current Status: `feature/public-places` 머지 준비 - 범위(새 표 2개 · 적재 · 맞춰 보기 API, 화면 없음, DB `0048`, env 3개 · 기본 꺼짐). 통합 검색은 #89로 머지됐다고 적는다.
  - Recent Validation: 이번 실행 결과(로컬 덤프 SHA-256 · `pg_restore -l` 확인, 행 수 전후, 로컬 실측 건수 · 실행계획 포함).
  - Active Risks에 '공공데이터 장소 기반(`feature/public-places`)' 절을 더한다.
    - 서버 적재는 머지 뒤 승인받아 손으로 한다: 개발서버 TourAPI 첫 동기화, 상가정보 zip(336MB)을 서버로 옮겨 104만 행 적재, 주 1회 동기화는 서버 env 에 `PUBLIC_PLACES_SYNC_ENABLED=true`(사용자 수정). 운영은 최신 develop 배포 뒤.
    - DB 가 수백 MB 커진다 - 덤프 · 백업 · 로컬 동기화가 그만큼 커진다.
    - 두 출처에 같은 이름이 있거나 카카오 분류가 없으면 후보 확인이라 바로 담기 비율이 실측 63%보다 낮다 - 3단계에서 실데이터로 다시 잰다.
    - 상가정보 '예술·스포츠'에는 헬스장 · 당구장 같은 동네 시설이 섞인다. 추천 카드(3단계)에서 거른다.
    - 동기화 실패 · 일부는 알림 없이 로그(`public_places_sync_failed` · `public_places_prune_limited` · `public_places_sync_finished`)와 `public_place_sync_state` 로만 드러난다(다음 날 자동으로 다시 받는다). 자동 동기화를 켜면 운영자가 매주 동기화 다음 날 상태를 본다. 에러 알림은 보류 중.
    - 맞춰 보기를 쓰는 화면은 3단계다. 지금은 API 만 있다.

- [ ] **5단계: 커밋 승인받기** - 아래 두 커밋을 보이고 승인받은 뒤 만든다.
  1. `feat: 공공데이터 장소 표와 맞춰 보기 API 를 더한다`: 과제 1~7, `docs/implemented-feature-spec.md`, 이 계획
  2. `docs: CHECKLIST 를 공공데이터 장소 PR 기준으로 갱신한다`

- [ ] **6단계: 푸시와 Draft PR** - 따로 승인받은 뒤 `.codex/local-workflow.md`의 PR 게이트를 따른다. 본문 '참고'에 머지 뒤 서버 작업(승인 필요)과 '화면 변화 없음'을 적는다.

## 머지 뒤 서버 작업(실행할 때마다 승인)

1. 개발서버 배포(Jenkins)가 `alembic upgrade head`로 `0048`을 올린다.
2. TourAPI 첫 동기화: 개발서버 백엔드 컨테이너에서 `python scripts/sync_public_places_tourapi.py` - 종료 코드 0과 `outcome=success`를 확인한다.
3. 상가정보: 20260630판 zip을 서버로 옮기고(600) 컨테이너에 넣어 `python scripts/load_public_places_sangga.py <zip>` - 종료 코드 0. 끝나면 서버 · 컨테이너의 zip을 지운다.
4. 읽기 전용으로 건수 · `public_place_sync_state` · 상자 조회 `EXPLAIN`(약 108만 행에서 색인을 쓰는지)을 본다.
5. 주 1회 동기화를 켜려면 사용자가 서버 env 에 `PUBLIC_PLACES_SYNC_ENABLED=true`를 넣고 다시 배포한다. **켠 뒤에는 운영자(사용자)가 매주 동기화 다음 날 읽기 전용으로 상태를 본다** - `docker exec <db 컨테이너> sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select source, last_outcome, last_attempt_at, last_success_at, last_error from public_place_sync_state"'`. `last_outcome`이 `success`가 아니거나 `last_success_at`이 8일을 넘었으면 백엔드 로그의 `public_places_sync_failed` · `public_places_prune_limited`를 보고 원인을 찾는다. `public_places_prune_limited`의 `kept=`가 지우지 못한 단위와 까닭이다 - `39:10000->7000`처럼 끝까지 받았는데 줄었으면 관광공사 쪽에서 정말 줄었는지 확인한 뒤 `python scripts/sync_public_places_tourapi.py --accept-shrink 39`로 한 번 돌린다(승인 필요). 상태 표 시각은 UTC다(KST는 +9시간). 스크립트 종료 코드는 자동 실행의 실패를 알려 주지 않는다.
6. 운영은 최신 develop 배포 뒤 같은 순서로 한다.
