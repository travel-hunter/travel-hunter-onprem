from typing import Literal

from pydantic import BaseModel, Field


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


PublicPlaceCategory = Literal["sight", "culture", "leisure", "stay", "shopping", "food", "cafe"]


class PlaceMatchRequest(BaseModel):
    """맞춰 보기(카카오 운영정책 2단계) - 고른 카카오 장소의 이름 · 좌표 · 분류. 서버는 비교에만 쓰고 저장 · 로그에 남기지 않는다.
    카카오 장소 ID 는 비교에 쓰지 않아 받지 않는다."""

    name: str = Field(min_length=1, max_length=100)
    latitude: float = Field(ge=33.0, le=39.0)
    longitude: float = Field(ge=124.0, le=132.0)
    categoryCode: str | None = Field(default=None, max_length=10)


class PublicPlaceItem(BaseModel):
    """우리 장소 기반(public_places)의 한 곳 - 공공데이터 값이다. source + sourceId 가 3단계에서 담을 때 쓰는 열쇠다."""

    source: Literal["tourapi", "sangga"]
    sourceId: str
    name: str
    address: str | None = None
    latitude: float
    longitude: float
    category: PublicPlaceCategory
    sido: str | None = None
    city: str | None = None
    photoUrl: str | None = None
    photoLicense: str | None = None
    distanceMeters: int


class PlaceMatchResponse(BaseModel):
    """match = 이름이 같은 곳이 하나이고 분류가 맞음(바로 담기), candidates = 확인할 후보 1~3곳, none = 나만의 장소로."""

    result: Literal["match", "candidates", "none"]
    places: list[PublicPlaceItem]
