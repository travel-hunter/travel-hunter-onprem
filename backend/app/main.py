from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.core.config import settings
from app.services.external_collection_scheduler import (
    start_external_collection_scheduler,
    stop_external_collection_scheduler,
)
from app.services.notification_scheduler import (
    start_notification_scheduler,
    stop_notification_scheduler,
)

settings.validate_runtime()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    notification_scheduler_task = start_notification_scheduler()
    external_collection_scheduler_task = start_external_collection_scheduler()
    try:
        yield
    finally:
        await stop_external_collection_scheduler(external_collection_scheduler_task)
        await stop_notification_scheduler(notification_scheduler_task)

app = FastAPI(
    title="Travel Hunter API",
    version="0.1.0",
    description="Travel Hunter production app API foundation.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(api_router, prefix="/api")
