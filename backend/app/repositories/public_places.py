"""public_places · public_place_sync_state 쓰기 · 조회(0048). 적재는 (source, source_id) 기준 upsert, 단위(TourAPI 유형 ·
상가정보 시도)마다 끝까지 받았는지 본 뒤 통과한 단위의 오래된 행만 지우기, 출처별 시도 · 성공 기록, 맞춰 보기는 위경도 상자 조회.
완성 검색어는 이름에 검색어가 든 후보 묶음 조회(suggest_candidates)."""

from __future__ import annotations

import logging
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import Integer, and_, case, delete, false, func, literal_column, not_, or_, select, text, tuple_, union_all
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import PublicPlace, PublicPlaceSyncState

logger = logging.getLogger(__name__)

UPDATED_COLUMNS = (
    "name", "name_key", "address", "latitude", "longitude", "category", "sido", "city", "photo_url", "photo_license", "synced_at",
)
_GROUP_COLUMNS = {"category": PublicPlace.category, "sido": PublicPlace.sido}
# 관광지로 치는 분류 - 완성 검색어의 지역 밖 채우기와 순위(관광지 줄)가 같이 쓴다
ATTRACTION_CATEGORIES = ("sight", "culture", "leisure")
# 완성 검색어 후보 상한. 이름 길이 순으로 자르므로 넘치면 긴 이름부터 빠진다(걸리면 경고)
SUGGEST_CANDIDATE_LIMIT = 4000
# 상가정보 이름에 이 말이 들면 유흥업소로 보고 뺀다(음식 · 숙박 분류에 노래주점 · 단란주점이 섞여 있다)
_NIGHTLIFE = ("노래", "단란", "유흥", "룸살롱", "가라오케", "나이트클럽")


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


def get_public_place(db: Session, source: str, source_id: str) -> PublicPlace | None:
    """(출처, 출처 ID)로 한 곳 - 일정에 담을 때 서버가 이 값으로 장소 열을 채운다."""

    return db.get(PublicPlace, (source, source_id))


def _area_clause(sido: str, cities: Collection[str] | None):
    return PublicPlace.sido == sido if cities is None else and_(PublicPlace.sido == sido, PublicPlace.city.in_(sorted(cities)))


def _in_area(statement, *, sido: str, cities: Collection[str] | None):
    """일정 지역(시도 + 시군)의 장소로 거른다. cities 가 None 이면 시도 전체 - 같은 시군 이름이 여러 시도에 있어 시도와 함께 건다(ix_public_places_sido_city)."""

    return statement.where(_area_clause(sido, cities))


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


@dataclass(frozen=True)
class SuggestCandidate:
    """완성 검색어 후보 한 묶음 - (tier, 이름, 출처, 분류, 시도, 시군)이 같은 행 count 개. tier 0 = 일정 지역 안(지역이 없으면 전국
    TourAPI), 1 = 지역 밖(지역이 있을 때만). 순위는 services/place_suggest 가 매긴다."""

    name: str
    source: str
    category: str
    sido: str | None
    city: str | None
    tier: int
    count: int


def suggest_candidates(
    db: Session,
    *,
    query: str,
    scope: tuple[str, tuple[str, ...] | None] | None,
    limit: int = SUGGEST_CANDIDATE_LIMIT,
) -> list[SuggestCandidate]:
    """이름에 query(앞뒤 공백을 자른 2~80자)가 든 후보(ix_public_places_name_trgm). scope = (시도, 시군 목록 | None) 또는 지역 없음(None).
    - 지역 안(tier 0): TourAPI 전부 + 상가정보 중 예술·스포츠가 아닌 것(유흥 이름 제외).
    - 지역 밖(tier 1, 지역이 있을 때만): TourAPI 관광지(sight · culture · leisure)만.
    - 지역 없음: 전국 TourAPI(tier 0).
    - 2자 검색어는 지역 안 TourAPI 만 어절 속을 맞추고 나머지는 어절 앞만 맞춘다(스타 -> 블라스타 같은 잡음).
    갈래마다 정렬 · 상한을 달지 않고(SQLite 가 거부한다) 합친 뒤 한 번에 묶고 tier -> 이름 길이 -> 이름 순으로 limit 개만 받는다."""

    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    contains = PublicPlace.name.ilike(f"%{escaped}%", escape="\\")
    # 이름 맨 앞이거나 공백 바로 뒤
    word_start = or_(PublicPlace.name.ilike(f"{escaped}%", escape="\\"), PublicPlace.name.ilike(f"% {escaped}%", escape="\\"))
    short = len(query) < 3

    def branch(tier: int, *conditions):
        columns = (PublicPlace.name, PublicPlace.source, PublicPlace.category, PublicPlace.sido, PublicPlace.city)
        return select(*columns, literal_column(str(tier), Integer).label("tier")).where(contains, *conditions)

    if scope is None:
        branches = [branch(0, PublicPlace.source == "tourapi")]
    else:
        sido, cities = scope
        nightlife = and_(PublicPlace.source == "sangga", or_(*(PublicPlace.name.contains(word, autoescape=True) for word in _NIGHTLIFE)))
        inside = branch(0, or_(PublicPlace.source == "tourapi", PublicPlace.category != "leisure"), not_(nightlife))
        outside = branch(
            1,
            PublicPlace.source == "tourapi",
            PublicPlace.category.in_(ATTRACTION_CATEGORIES),
            # sido · city 가 비어 있으면 '지역 안인지'가 NULL 이 된다 - 비어 있으면 지역 밖으로 친다
            not_(func.coalesce(_area_clause(sido, cities), false())),
        )
        if short:
            inside = inside.where(or_(PublicPlace.source == "tourapi", word_start))
            outside = outside.where(word_start)
        branches = [_in_area(inside, sido=sido, cities=cities), outside]
    union = union_all(*branches).subquery()
    group = (union.c.tier, union.c.name, union.c.source, union.c.category, union.c.sido, union.c.city)
    statement = (
        select(*group, func.count())
        .group_by(*group)
        .order_by(union.c.tier, func.length(union.c.name), union.c.name)
        .limit(limit)
    )
    if db.get_bind().dialect.name == "postgresql":
        # psycopg 는 같은 문장을 5번 넘게 보내면 서버 쪽 준비문으로 바꾸고, PostgreSQL 은 그 뒤 검색어를 모르는 일반 계획으로 갈아탄다.
        # 일반 계획은 trigram 색인을 못 써서 2자 검색어가 15ms 에서 340ms 로 느려진다(2026-10-12 로컬 실측) - 매번 검색어를 보고 계획하게 한다
        db.execute(text("SET LOCAL plan_cache_mode = force_custom_plan"))
    rows = [
        SuggestCandidate(name=name, source=source, category=category, sido=sido_, city=city, tier=tier, count=count)
        for tier, name, source, category, sido_, city, count in db.execute(statement).all()
    ]
    if len(rows) == limit:
        logger.warning("place_suggest_candidates_capped count=%s", len(rows))
    return rows
