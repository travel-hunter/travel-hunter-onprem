from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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
    # 친 말로 카카오가 0곳이라 우리 공공데이터 완성어로 대신 찾은 줄이면 그 말(카카오 값 아님), 아니면 null
    viaWord: str | None = None


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


GeoKind = Literal["building", "parcel"]


class AddressFill(BaseModel):
    """주소 채움(방식1) - 고른 자리를 품은 건물, 또는 땅의 지번 주소와 중심. 국토교통부 공공데이터 값이다(카카오 값 아님).
    id 는 이 판의 행 번호 - 담을 때 kind · id 만 customPlace.geoRef 로 보낸다(판이 바뀌면 404). 주소 · 좌표는 서버가 다시 읽는다."""

    kind: GeoKind
    id: int
    pnu: str
    address: str
    latitude: float
    longitude: float
    distanceMeters: int


class PlaceMatchResponse(BaseModel):
    """match = 이름이 같은 곳이 하나이고 분류가 맞음(바로 담기), candidates = 확인할 후보 1~3곳, none = 나만의 장소로."""

    result: Literal["match", "candidates", "none"]
    places: list[PublicPlaceItem]
    # 방식1: match 가 아니면 그 자리의 건물, 또는 중심이 30m 안인 땅의 지번(없으면 null) - 화면의 '주소 채움'
    fill: AddressFill | None = None


class LocateRequest(BaseModel):
    """위치 찍기 - 지도에서 찍은 자리. 서버는 건물 · 땅을 찾는 데만 쓰고 저장 · 로그하지 않는다(데브톡 151842 · 151916-4)."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=33.0, le=39.0)
    longitude: float = Field(ge=124.0, le=132.0)


class LocateResponse(BaseModel):
    """fill = 찍은 자리를 품은 건물 · 땅(30m 와 상관없이). nearCenter = 건물이거나 땅 중심이 30m 안 - 화면이 핀까지 담는다(아니면 주소만)."""

    fill: AddressFill | None = None
    nearCenter: bool = False
