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
