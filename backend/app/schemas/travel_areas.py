from typing import Literal

from pydantic import BaseModel


class TravelAreaOptionResponse(BaseModel):
    travelAreaId: str
    travelAreaName: str
    sido: str
    areaType: Literal["whole", "recommended", "administrative"]
    includedCities: list[str]


class TravelAreaCatalogResponse(BaseModel):
    sido: str
    sourceAsOf: str
    wholeArea: TravelAreaOptionResponse
    recommendedAreas: list[TravelAreaOptionResponse]
    administrativeAreas: list[TravelAreaOptionResponse]
