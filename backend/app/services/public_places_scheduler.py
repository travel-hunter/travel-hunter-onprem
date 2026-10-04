"""주 1회 TourAPI 공공데이터 장소 동기화(카카오 운영정책 2단계, public_places).

정책 수집 스케줄러와 같은 꼴(앱 수명 주기의 asyncio 작업, 켜는 설정 · RUN_AT · 폴링)이지만 때는 DB 상태로 가린다 -
폴링마다 tourapi_sync_due 가 'KST RUN_AT 뒤 · 오늘 아직 시도 안 함 · 마지막 성공에서 7일 지남'일 때만 받는다. 시도는 첫 호출 전에
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
        "public_places_sync_finished outcome=%s received=%s written=%s pruned=%s kept=%s",
        result.outcome, result.received_count, result.parsed_count, result.pruned_count, ",".join(result.kept) or "-",
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
