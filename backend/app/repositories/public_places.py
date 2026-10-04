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
