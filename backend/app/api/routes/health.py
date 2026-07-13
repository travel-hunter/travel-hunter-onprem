from fastapi import APIRouter

from app.schemas.health import HealthResponse
from app.services.health import get_health_payload

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(**get_health_payload())
