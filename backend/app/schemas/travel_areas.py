from typing import Literal

from pydantic import BaseModel


class TravelAreaOptionResponse(BaseModel):
    travelAreaId: str
    travelAreaName: str
    sido: str
    areaType: Literal["whole", "recommended", "administrative"]
    includedCities: list[str]
    # 시·군·구가 많은 광역시도에서만 채워진다. 나머지는 null 이다.
    group: str | None = None


class TravelAreaCatalogResponse(BaseModel):
    sido: str
    sourceAsOf: str
    wholeArea: TravelAreaOptionResponse
    recommendedAreas: list[TravelAreaOptionResponse]
    administrativeAreas: list[TravelAreaOptionResponse]
