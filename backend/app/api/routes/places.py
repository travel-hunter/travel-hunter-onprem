from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_optional_db
from app.models import User
from app.schemas.places import PlaceSearchItem
from app.services import place_search

router = APIRouter(prefix="/places", tags=["places"])


def _signed_in(current_user: User | None, db: Session | None) -> None:
    """로그인 확인 뒤 DB 세션을 바로 놓는다 - 카카오를 부르는 동안(최대 수 초) 연결을 쥐고 있으면 몰린 요청이 풀을 말린다(10/3 리뷰).
    get_current_user 와 같은 요청의 같은 세션이고, 뒤의 close 는 한 번 더 불려도 괜찮다."""

    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if db is not None:
        db.close()


@router.get("/search", response_model=list[PlaceSearchItem])
def search_places(
    query: str = Query(min_length=1, max_length=80),
    current_user: User | None = Depends(get_current_user),
    db: Session | None = Depends(get_optional_db),
) -> list[PlaceSearchItem]:
    """홈 · 정책 탭 통합 검색의 장소 찾기(카카오 로컬). 두 글자 미만이거나 카카오가 꺼져 있으면 빈 목록."""

    _signed_in(current_user, db)
    return [PlaceSearchItem(**item) for item in place_search.search_places(query)]


@router.get("/nearby", response_model=list[PlaceSearchItem])
def nearby_places(
    lat: float = Query(ge=33.0, le=39.0),
    lng: float = Query(ge=124.0, le=132.0),
    category: Literal["FD6", "CE7", "AD5", "AT4"] = Query(),
    current_user: User | None = Depends(get_current_user),
    db: Session | None = Depends(get_optional_db),
) -> list[PlaceSearchItem]:
    """홈 장소 카드의 '이 근처'(시안 v58) - 좌표 반경 2km 안의 그 분류(맛집 · 카페 · 숙소 · 볼거리) 장소, 가까운 순."""

    _signed_in(current_user, db)
    return [PlaceSearchItem(**item) for item in place_search.nearby_places(latitude=lat, longitude=lng, category=category)]
