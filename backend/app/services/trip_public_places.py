"""일정 장소와 공공데이터 장소(카카오 운영정책 3단계) - 담을 때 저장하는 열 값과 예전 카카오 행 판별.

일정에 저장하는 값은 공공데이터 장소(public_places)의 값과 사용자가 직접 쓴 값뿐이다. 카카오 로컬 값(장소명 · 주소 · 좌표 · 전화 · 분류)은
저장하지 않고, 카카오 장소 ID 와 place_url 만 '카카오맵에서 보기' 링크로 남긴다.
설계: docs/superpowers/specs/2026-10-03-public-place-storage-design.md.
"""

from __future__ import annotations

import statistics

from sqlalchemy.orm import Session

from app.data.travel_areas import WHOLE_AREA_ID_PREFIX, TravelArea
from app.models import PublicPlace, Trip, TripPlace
from app.repositories import public_places as public_place_repository
from app.services.public_places import name_key, secure_photo_url
from app.services.travel_area_catalog import _is_legacy_whole_area

LEGACY_KAKAO_PROVIDERS = frozenset({"kakao", "kakao_local"})
KAKAO_PLACE_URL = "https://place.map.kakao.com/{kakao_place_id}"


def is_legacy_kakao_place(place: TripPlace) -> bool:
    """예전 카카오 행 - 출처 열(place_origin)이 비어 있고 카카오에서 온 행. 이름 · 주소 · 좌표가 카카오 값이라 4단계에서 변환한다."""

    return place.place_origin is None and place.source_provider in LEGACY_KAKAO_PROVIDERS


def public_place_columns(place: PublicPlace) -> dict[str, object]:
    """공공데이터 장소 → trip_places 열. 이름 · 주소 · 좌표 · 분류 · 사진을 복사하고 출처를 남긴다(외래키는 없다).
    사용자가 붙인 이름(user_label)은 비운다 - 장소를 바꿀 때 예전 이름이 따라오지 않게 값 열을 모두 이 함수가 정한다."""

    return {
        "place_name": place.name,
        "address": place.address,
        "latitude": place.latitude,
        "longitude": place.longitude,
        "category_group_code": None,
        "category_group_name": None,
        "place_origin": "public",
        "public_source": place.source,
        "public_source_id": place.source_id,
        "public_category": place.category,
        "photo_url": secure_photo_url(place.photo_url),
        "photo_license": place.photo_license,
        "user_label": None,
        "geo_kind": None,
        "geo_pnu": None,
    }


def custom_place_columns(
    name: str, *, address: str | None = None, latitude: float | None = None, longitude: float | None = None,
    geo_kind: str | None = None, geo_pnu: str | None = None,
) -> dict[str, object]:
    """나만의 장소 → trip_places 열. 사용자가 쓴 이름, 주소 채움이면 건물 · 땅 지번(공공데이터)과 그 출처, 좌표는 그 중심(pin 일 때)뿐."""

    return {
        "place_name": name,
        "address": address,
        "latitude": latitude,
        "longitude": longitude,
        "category_group_code": None,
        "category_group_name": None,
        "place_origin": "custom",
        "public_source": None,
        "public_source_id": None,
        "public_category": None,
        "photo_url": None,
        "photo_license": None,
        "user_label": None,
        "geo_kind": geo_kind,
        "geo_pnu": geo_pnu,
    }


def kakao_link_columns(kakao_place_id: str | None) -> dict[str, object]:
    """카카오 장소 ID → '카카오맵에서 보기' 링크 열. place_url 은 서버가 만든다(클라이언트가 보낸 주소는 받지 않는다)."""

    if not kakao_place_id:
        return {"source_provider": None, "external_place_id": None, "place_url": None}
    return {
        "source_provider": "kakao",
        "external_place_id": kakao_place_id,
        "place_url": KAKAO_PLACE_URL.format(kakao_place_id=kakao_place_id),
    }


PUBLIC_CATEGORY_LABELS = {
    "sight": "관광지",
    "culture": "문화시설",
    "leisure": "레포츠",
    "stay": "숙박",
    "shopping": "쇼핑",
    "food": "음식점",
    "cafe": "카페",
}
# 추천 항목의 categoryGroup - 프론트가 시간대(오전 · 점심 · 카페 · 숙소)를 고르는 데 쓴다
CATEGORY_GROUPS = {
    "sight": "attraction",
    "culture": "attraction",
    "leisure": "attraction",
    "shopping": "attraction",
    "food": "food",
    "cafe": "cafe",
    "stay": "stay",
}
# 추천은 최대 18곳이다. 관광 3 · 음식 3 · 숙박 2 를 먼저 채우고, 남는 자리는 세 묶음을 번갈아 채운다
RECOMMENDATION_LIMIT = 18
RECOMMENDATION_GROUPS = (
    (("sight", "culture", "leisure", "shopping"), 3),
    (("food", "cafe"), 3),
    (("stay",), 2),
)
SEJONG = "세종"   # 세종은 시군 자리에 읍 · 면 · 동 이름이 들어 있어 시도만으로 고른다


def area_scope(area: TravelArea | None) -> tuple[str, tuple[str, ...] | None] | None:
    """일정 지역 → (시도, 시군 목록). 시군 목록이 None 이면 시도 전체다. 지역을 가리지 못하면 None.
    whole: · 옛 `*-all` · 세종은 시도만, 그 밖은 시도 + included_cities(같은 시군 이름이 여러 시도에 있으니 시도와 함께)."""

    if area is None:
        return None
    if area.id.startswith(WHOLE_AREA_ID_PREFIX) or _is_legacy_whole_area(area) or area.sido == SEJONG:
        return area.sido, None
    return area.sido, tuple(area.included_cities)


def existing_place_keys(trip: Trip) -> tuple[set[tuple[str, str]], set[str]]:
    """이미 담은 장소 - (공공데이터 출처, 출처 ID)와 비교용 이름. 이름은 예전 카카오 행의 것도 견주기만 한다(저장 · 로그 없음).
    사용자가 붙인 이름(user_label)은 보지 않는다 - 공공데이터 장소는 (출처, ID)로 걸러지고, 나만의 장소는 place_name 이 곧 사용자 이름이다."""

    keys: set[tuple[str, str]] = set()
    names: set[str] = set()
    for trip_day in trip.days:
        for place in trip_day.places:
            if place.public_source and place.public_source_id:
                keys.add((place.public_source, place.public_source_id))
            if key := name_key(place.place_name):
                names.add(key)
    return keys, names


def recommendation_item(place: PublicPlace, *, suggested_day: int, region: str) -> dict[str, object]:
    return {
        "id": f"public:{place.source}:{place.source_id}",
        "label": place.name,
        "title": place.name,
        "meta": " · ".join(part for part in (PUBLIC_CATEGORY_LABELS[place.category], place.address) if part),
        "reason": f"{region} 일정에 추가로 검토할 만한 공공데이터 장소입니다.",
        "categoryGroup": CATEGORY_GROUPS[place.category],
        "categoryCode": None,
        "categoryName": None,
        "phone": None,
        "address": place.address,
        "latitude": place.latitude,
        "longitude": place.longitude,
        "placeUrl": None,
        "suggestedDay": suggested_day,
        "aiReview": None,
        "sourceProvider": None,
        "externalPlaceId": None,
        "sourceType": "public_place",
        "publicSource": place.source,
        "publicSourceId": place.source_id,
        "publicCategory": place.category,
        "photoUrl": secure_photo_url(place.photo_url),
        "photoLicense": place.photo_license,
    }


def recommend_public_places(db: Session, *, trip: Trip, area: TravelArea | None, region: str) -> list[dict[str, object]]:
    """일정 지역의 공공데이터 장소로 추천 항목을 만든다(카카오 검색 없음). 지역을 못 가리거나 고를 장소가 없으면 빈 목록 -
    부르는 쪽이 저장 요약으로 넘어간다. 순서 · 섞음은 recommended_public_places 가 정한다(일정 번호가 섞음의 씨앗)."""

    scope = area_scope(area)
    if scope is None:
        return []
    sido, cities = scope
    keys, names = existing_place_keys(trip)
    pools = [
        public_place_repository.recommended_public_places(
            db, sido=sido, cities=cities, categories=categories, shuffle_key=str(trip.id),
            exclude_keys=keys, exclude_names=names, limit=RECOMMENDATION_LIMIT,
        )
        for categories, _target in RECOMMENDATION_GROUPS
    ]
    picked = [place for pool, (_categories, target) in zip(pools, RECOMMENDATION_GROUPS) for place in pool[:target]]
    leftovers = [pool[target:] for pool, (_categories, target) in zip(pools, RECOMMENDATION_GROUPS)]
    while len(picked) < RECOMMENDATION_LIMIT and any(leftovers):
        for rest in leftovers:
            if rest and len(picked) < RECOMMENDATION_LIMIT:
                picked.append(rest.pop(0))
    day_numbers = sorted(day.day_number for day in trip.days) or [1]
    return [
        recommendation_item(place, suggested_day=day_numbers[index % len(day_numbers)], region=region)
        for index, place in enumerate(picked)
    ]


def area_center(db: Session, area: TravelArea | None) -> dict[str, float | None]:
    """일정 지역 공공데이터 장소 위경도의 중앙값(평균이 아니라 - 먼 외딴 장소 하나가 지도 중심을 끌지 않게)."""

    scope = area_scope(area)
    points = public_place_repository.area_coordinates(db, sido=scope[0], cities=scope[1]) if scope else []
    if not points:
        return {"latitude": None, "longitude": None}
    return {
        "latitude": statistics.median(latitude for latitude, _longitude in points),
        "longitude": statistics.median(longitude for _latitude, longitude in points),
    }
