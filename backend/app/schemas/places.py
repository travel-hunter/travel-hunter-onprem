from typing import Literal

from pydantic import BaseModel


class PlaceSearchItem(BaseModel):
    """통합 검색의 장소 한 곳(place) 또는 동 · 읍 · 면 구역(area). sido · city 는 서버가 주소로 가린 지도 도 · 시군."""

    kind: Literal["place", "area"]
    id: str
    name: str
    category: str | None = None
    categoryCode: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    placeUrl: str | None = None
    sido: str | None = None
    city: str | None = None
    # 이 근처(GET /places/nearby)일 때만 - 기준 좌표에서의 거리(m). 검색 결과는 null
    distanceMeters: int | None = None
