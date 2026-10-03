from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_current_user
from app.models import User
from app.schemas.places import PlaceSearchItem
from app.services import place_search

router = APIRouter(prefix="/places", tags=["places"])


@router.get("/search", response_model=list[PlaceSearchItem])
def search_places(
    query: str = Query(min_length=1, max_length=80),
    current_user: User | None = Depends(get_current_user),
) -> list[PlaceSearchItem]:
    """홈 · 정책 탭 통합 검색의 장소 찾기(카카오 로컬). 두 글자 미만이거나 카카오가 꺼져 있으면 빈 목록."""

    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return [PlaceSearchItem(**item) for item in place_search.search_places(query)]


@router.get("/nearby", response_model=list[PlaceSearchItem])
def nearby_places(
    lat: float = Query(ge=33.0, le=39.0),
    lng: float = Query(ge=124.0, le=132.0),
    category: Literal["FD6", "CE7", "AD5", "AT4"] = Query(),
    current_user: User | None = Depends(get_current_user),
) -> list[PlaceSearchItem]:
    """홈 장소 카드의 '이 근처'(시안 v58) - 좌표 반경 2km 안의 그 분류(맛집 · 카페 · 숙소 · 볼거리) 장소, 가까운 순."""

    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return [PlaceSearchItem(**item) for item in place_search.nearby_places(latitude=lat, longitude=lng, category=category)]
