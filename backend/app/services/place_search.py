"""통합 검색의 장소 찾기(시안 v56) - 홈 장소 목록과 정책 탭 '위치로 찾기'가 같이 쓴다.

카카오 로컬 키워드 검색으로 장소를 찾고, 친 말이 동 · 읍 · 면 · 리 · 가로 끝나면 주소 검색도 부른다 - 키워드 검색은 '중앙동'을
한 동네 위주로만 주지만 주소 검색은 전국의 같은 이름 동을 다 준다(10/2 실측). 항목마다 도 · 시군을 붙여 화면이 그 지역 혜택으로
바로 잇게 한다. 카카오가 꺼져 있거나 실패하면 빈 목록(검색 칸의 다른 결과는 그대로 쓸 수 있다).
"""

from __future__ import annotations

import logging
import re

from app.data.travel_areas import normalize_municipality_name
from app.services.kakao_local import KakaoLocalConfigurationError, KakaoLocalSearchProvider, build_kakao_local_client
from app.services.travelmonth_normalizer import REGION_ALIASES

logger = logging.getLogger(__name__)

MIN_QUERY_LENGTH = 2
KEYWORD_SIZE = 15
AREA_SIZE = 30
AREA_SUFFIX = re.compile(r"(동|읍|면|리|[0-9]가)$")
# 2026 행정 통합 주소: 카카오가 광주 · 전남 주소를 이 첫 낱말로 준다
MERGED_GWANGJU_JEONNAM = "전남광주통합특별시"


def resolve_region(first: str, second: str) -> str | None:
    """주소 첫 낱말 → 지도 도(짧은 이름). 통합 주소는 둘째 낱말이 구면 광주, 시 · 군이면 전남."""

    if first.startswith(MERGED_GWANGJU_JEONNAM):
        return "광주" if second.endswith("구") else "전남"
    region = REGION_ALIASES.get(first)
    if region is None and first:
        logger.info("place_search_unknown_region token=%s", first)
    return region


def resolve_city(second: str) -> str | None:
    """둘째 낱말(시 · 군 · 구) → 시군 이름(정책 제목 [시군]과 맞추는 짧은 이름). '성남시 중원구'는 성남."""

    word = second.split()[0] if second.strip() else ""
    return normalize_municipality_name(word) if word else None


def _client_or_none() -> KakaoLocalSearchProvider | None:
    """카카오가 꺼져 있거나 설정이 틀렸으면(켜 두고 키가 비었으면) None - 계약대로 빈 목록이 되게. 키 값은 남기지 않는다."""

    try:
        return build_kakao_local_client()
    except KakaoLocalConfigurationError:
        logger.warning("place_search_kakao_misconfigured")
        return None


def _place_item(place) -> dict[str, object]:
    words = (place.address or "").split()
    first, second = (words + ["", ""])[:2]
    return {
        "kind": "place",
        "id": f"kakao:{place.external_place_id}",
        "name": place.name,
        # 일정 안 장소 검색(categoryName)과 같은 전체 경로 - 홈에서 일정에 담아도 같은 장소 기록이 된다. 화면은 마지막 칸만
        "category": place.category_name or None,
        "categoryCode": place.category_group_code,
        "address": place.address,
        "latitude": place.latitude,
        "longitude": place.longitude,
        "placeUrl": place.place_url,
        "sido": resolve_region(first, second),
        "city": resolve_city(second),
    }


def _area_item(area) -> dict[str, object]:
    city_word = area.region_2depth_name.split()[0] if area.region_2depth_name else ""
    name = " ".join(part for part in (city_word, area.region_3depth_name) if part)
    return {
        "kind": "area",
        "id": f"area:{area.b_code or area.address_name}",
        "name": name or area.address_name,
        "category": None,
        "categoryCode": None,
        "address": area.address_name,
        "latitude": area.latitude,
        "longitude": area.longitude,
        "placeUrl": None,
        "sido": resolve_region(area.region_1depth_name, area.region_2depth_name),
        "city": resolve_city(area.region_2depth_name),
    }


def search_places(query: str, provider: KakaoLocalSearchProvider | None = None) -> list[dict[str, object]]:
    q = query.strip()
    if len(q) < MIN_QUERY_LENGTH:
        return []
    client = provider or _client_or_none()
    if client is None:
        return []
    items: list[dict[str, object]] = []
    if AREA_SUFFIX.search(q.split()[-1]):
        try:
            seen: set[str] = set()
            for area in client.search_address(query=q, size=AREA_SIZE):
                item = _area_item(area)
                key = f"{item['sido']}|{item['city']}|{item['name']}"
                if key not in seen:   # '중앙동1가 · 2가'처럼 잘게 나뉜 구역은 같은 시군 같은 이름이면 한 줄
                    seen.add(key)
                    items.append(item)
        except Exception:   # noqa: BLE001 - 장소 검색이 안 돼도 키워드 결과는 쓴다
            logger.warning("place_search_area_failed", exc_info=True)
    try:
        items += [_place_item(place) for place in client.search_keyword(query=q, size=KEYWORD_SIZE)]
    except Exception:   # noqa: BLE001
        logger.warning("place_search_keyword_failed", exc_info=True)
    return items


NEARBY_CATEGORIES = ("FD6", "CE7", "AD5", "AT4")   # 맛집 · 카페 · 숙소 · 볼거리
NEARBY_RADIUS_M = 2000
NEARBY_SIZE = 6   # 기준 장소 자신이 끼면 화면이 빼고 다섯을 보인다


def nearby_places(
    *,
    latitude: float,
    longitude: float,
    category: str,
    provider: KakaoLocalSearchProvider | None = None,
) -> list[dict[str, object]]:
    """장소 카드 '이 근처'(시안 v58): 좌표 반경 2km 안의 그 분류 장소를 가까운 순으로. 카카오 분류 검색 그대로라
    별점 · 리뷰 · 인기 지표는 없다. 카카오가 꺼져 있거나 실패하면 빈 목록."""

    if category not in NEARBY_CATEGORIES:
        return []
    client = provider or _client_or_none()
    if client is None:
        return []
    try:
        places = client.search_category(
            category_group_code=category, x=longitude, y=latitude, radius=NEARBY_RADIUS_M, size=NEARBY_SIZE, sort="distance"
        )
    except Exception:  # noqa: BLE001 - 이 근처가 안 돼도 카드의 나머지는 쓴다
        logger.warning("place_search_nearby_failed", exc_info=True)
        return []
    return [{**_place_item(place), "distanceMeters": place.distance_meters} for place in places]
