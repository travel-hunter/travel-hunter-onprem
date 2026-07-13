from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_user
from app.db.session import get_optional_db
from app.models import User
from app.schemas.ops import (
    ExternalCollectionOpsHealth,
    ExternalCollectionQualityReport,
    ExternalCollectionRunResponse,
    ExternalCollectionSourceRunResult,
)
from app.services import external_collection_quality
from app.services.external_benefit_collection import collect_external_benefits_from_live_sources
from app.services.external_collection_scheduler import (
    get_external_collection_ops_health,
)

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/external-collection", response_model=ExternalCollectionOpsHealth)
def external_collection_ops_health(
    _current_admin: User = Depends(require_admin_user),
) -> ExternalCollectionOpsHealth:
    return ExternalCollectionOpsHealth(**get_external_collection_ops_health())


@router.post("/external-collection/run", response_model=ExternalCollectionRunResponse)
def run_external_collection(
    _current_admin: User = Depends(require_admin_user),
    db: Session | None = Depends(get_optional_db),
) -> ExternalCollectionRunResponse:
    if db is None:
        raise HTTPException(status_code=500, detail="DB session is required.")
    result = collect_external_benefits_from_live_sources(db)
    return ExternalCollectionRunResponse(
        sourceName=result.source_name,
        sourceCategory=result.source_category,
        parsedCount=result.parsed_count,
        createdOrUpdatedCount=result.created_or_updated_count,
        outcome=result.outcome,
        sources=[
            ExternalCollectionSourceRunResult(
                sourceCategory=source.source_category,
                parsedCount=source.parsed_count,
                createdOrUpdatedCount=source.created_or_updated_count,
                outcome=source.outcome,
                error=source.error,
            )
            for source in result.sources
        ],
    )


@router.get(
    "/external-collection/quality",
    response_model=ExternalCollectionQualityReport,
)
def external_collection_quality_report(
    style: str | None = None,
    region: str | None = None,
    sourceCategory: str | None = None,
    limit: int = Query(default=3, ge=1, le=10),
    _current_admin: User = Depends(require_admin_user),
    db: Session | None = Depends(get_optional_db),
) -> ExternalCollectionQualityReport:
    if db is None:
        raise HTTPException(status_code=500, detail="DB session is required.")
    return external_collection_quality.get_external_collection_quality_report(
        db,
        style=style,
        region=region,
        source_category=sourceCategory,
        limit=limit,
    )
