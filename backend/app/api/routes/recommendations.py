from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_optional_db
from app.schemas.recommendations import RegionRecommendation, TravelAreaRecommendationResponse
from app.services import region_recommendations as region_recommendation_service
from app.services import travel_areas as travel_area_service

router = APIRouter(tags=["recommendations"])


@router.get("/recommendations/regions", response_model=list[RegionRecommendation])
def list_region_recommendations(
    style: str | None = None,
    region: str | None = None,
    preferredRegions: list[str] | None = Query(default=None),
    limit: int = Query(default=3, ge=1, le=10),
    db: Session | None = Depends(get_optional_db),
) -> list[RegionRecommendation]:
    if db is None:
        raise HTTPException(status_code=500, detail="DB session is required.")
    try:
        return region_recommendation_service.recommend_regions(
            db,
            style=style,
            region=region,
            preferred_regions=preferredRegions,
            limit=limit,
        )
    except region_recommendation_service.RegionRecommendationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error



@router.get("/recommendations/travel-areas", response_model=TravelAreaRecommendationResponse)
def list_travel_area_recommendations(
    sido: str | None = None,
    query: str | None = None,
    mode: str | None = None,
    style: str | None = None,
    limit: int = Query(default=6, ge=1, le=20),
    db: Session | None = Depends(get_optional_db),
) -> TravelAreaRecommendationResponse:
    if db is None:
        raise HTTPException(status_code=500, detail="DB session is required.")
    return travel_area_service.recommend_travel_areas(
        db,
        sido=sido,
        query=query,
        mode=mode,
        style=style,
        limit=limit,
    )
