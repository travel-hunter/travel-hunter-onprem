from fastapi import APIRouter, HTTPException, Query

from app.schemas.travel_areas import TravelAreaCatalogResponse, TravelAreaOptionResponse
from app.services.travel_area_catalog import TravelAreaCatalog, TravelAreaOption, list_travel_area_catalog

router = APIRouter(tags=["travel-areas"])


@router.get("/travel-areas", response_model=TravelAreaCatalogResponse)
def get_travel_area_catalog(sido: str = Query(...)) -> TravelAreaCatalogResponse:
    try:
        catalog = list_travel_area_catalog(sido)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _catalog_response(catalog)


def _catalog_response(catalog: TravelAreaCatalog) -> TravelAreaCatalogResponse:
    return TravelAreaCatalogResponse(
        sido=catalog.sido,
        sourceAsOf=catalog.source_as_of,
        wholeArea=_option_response(catalog.whole_area),
        recommendedAreas=[_option_response(option) for option in catalog.recommended_areas],
        administrativeAreas=[_option_response(option) for option in catalog.administrative_areas],
    )


def _option_response(option: TravelAreaOption) -> TravelAreaOptionResponse:
    if option.area_type == "policy":
        raise ValueError("Policy travel areas are not exposed in the catalog response")
    return TravelAreaOptionResponse(
        travelAreaId=option.id,
        travelAreaName=option.name,
        sido=option.sido,
        areaType=option.area_type,
        includedCities=list(option.included_cities),
        group=option.group,
    )
