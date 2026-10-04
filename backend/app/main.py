from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.media import MediaFiles
from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.core.config import settings
from app.core.debug_capture import build_debug_capture
from app.core.logging import configure_logging
from app.core.request_context import RequestContextMiddleware
from app.db.session import get_session_factory
from app.services.external_collection_scheduler import (
    start_external_collection_scheduler,
    stop_external_collection_scheduler,
)
from app.services.notification_scheduler import (
    start_notification_scheduler,
    stop_notification_scheduler,
)
from app.services.public_places_scheduler import (
    start_public_places_sync_scheduler,
    stop_public_places_sync_scheduler,
)

settings.validate_runtime()
configure_logging(
    settings.log_level,
    file_path=settings.log_file_path,
    file_max_bytes=settings.log_file_max_mb * 1024 * 1024,
    file_backups=settings.log_file_backups,
)


@asynccontextmanager
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

app = FastAPI(
    title="Travel Hunter API",
    version="0.1.0",
    description="Travel Hunter production app API foundation.",
    lifespan=lifespan,
)

# add_middleware 는 마지막 등록이 바깥이다. RequestContext 를 먼저 등록해 CORS 가 바깥에 서게 한다 -
# 그래야 미들웨어가 만든 500 응답에도 CORS 헤더가 붙는다.
app.add_middleware(
    RequestContextMiddleware,
    trusted_proxy_cidrs=settings.trusted_proxy_cidrs,
    exclude_paths=settings.access_log_exclude_paths,
    admin_domain=settings.admin_domain,
    # 잠긴 디버그 스위치 - 설정이 전부 있어야 켜진다. 없으면 None.
    debug_capture=build_debug_capture(settings, session_factory=get_session_factory if settings.database_url else None),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
)

app.include_router(health_router)
app.include_router(api_router, prefix="/api")
if settings.media_root:   # 확정 사진 파일(0047) - Caddy 는 /api 를 넘기기만 한다
    app.mount("/api/media", MediaFiles(directory=settings.media_root, check_dir=False), name="media")
