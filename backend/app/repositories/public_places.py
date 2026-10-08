"""public_places · public_place_sync_state 쓰기 · 조회(0048). 적재는 (source, source_id) 기준 upsert, 단위(TourAPI 유형 ·
상가정보 시도)마다 끝까지 받았는지 본 뒤 통과한 단위의 오래된 행만 지우기, 출처별 시도 · 성공 기록, 맞춰 보기는 위경도 상자 조회."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Literal

from sqlalchemy import and_, case, delete, func, not_, or_, select, tuple_
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
