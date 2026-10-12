"""장소 검색 첫 요청 데우기 - 앱이 뜰 때 뒤에서 한 번.

차가운 DB 에서 첫 '스타벅'(전남 일정)이 7.6초, 데운 뒤 0.45초였다(10/12 로컬 실측). 이 가운데
① public_places 표 · 색인(약 460MB)을 처음 읽는 값(완성어 · 미리 맞춤 · 지역 중심 합 약 2.3초)은 pg_prewarm 'read'(운영체제 캐시)로,
② PostGIS · 좌표계를 처음 올리는 값(약 1.7초)은 고정 좌표 한 점 조회로 미리 낸다.
geo 건물 · 땅 표(11GB)는 다 읽을 수 없어 검색 쪽 시간 한도(trips.PREMATCH_FILL_BUDGET_MS)가 맡는다.
무엇이 실패해도 경고 1줄만 - 앱 시작 · 검색을 막지 않는다. 좌표 · 결과 값은 로그에 싣지 않는다.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.db.session import get_session_factory
from app.repositories import geo as geo_repository

logger = logging.getLogger(__name__)

PREWARM_RELATIONS = (
    "public_places",
    "ix_public_places_name_trgm",
    "ix_public_places_lat_lng",
    "ix_public_places_name_key",
    "ix_public_places_sido_city",
)
WARM_POINT = (37.5663, 126.9779)   # 서울시청 - 고정 좌표(위도, 경도). 값은 버린다
PREWARM_SQL = text("SELECT pg_prewarm(CAST(:rel AS regclass), 'read')")


def _prewarm(db: Session) -> None:
    for name in PREWARM_RELATIONS:
        db.execute(PREWARM_SQL, {"rel": name})


def _touch_geo(db: Session) -> None:
    geo_repository.locate(db, [WARM_POINT])


def warm_place_search(make_session: Callable[[], Session] | None = None) -> None:
    started = time.perf_counter()
    with (make_session or get_session_factory())() as db:
        for step, run in (("prewarm", _prewarm), ("geo", _touch_geo)):
            try:
                run(db)
            except Exception as error:
                db.rollback()
                logger.warning("place_search_warmup_failed step=%s error=%s", step, type(error).__name__)
    logger.info("place_search_warmup_done ms=%d", (time.perf_counter() - started) * 1000)


def start_place_search_warmup(settings_obj: Settings = settings) -> None:
    """Postgres 일 때만, 데몬 스레드로(기다리지 않는다 - 끝나기 전에 온 검색은 지금처럼 차갑게 돈다)."""

    if not (settings_obj.database_url or "").startswith("postgresql"):
        return
    threading.Thread(target=warm_place_search, name="travel-hunter-search-warmup", daemon=True).start()
