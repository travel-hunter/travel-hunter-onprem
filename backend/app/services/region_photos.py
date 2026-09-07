"""Region photo lookup for policy cards.

The resolver is a pure in-memory index built once per request. Photos live in
the `region_photos` table keyed by (sido, city); `city == ""` is the sido-level
representative photo. Callers that have no DB session use
``EMPTY_REGION_PHOTO_INDEX`` so every payload builder degrades to "no photo"
without branching.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.data.travel_areas import normalize_municipality_name
from app.repositories.region_photos import list_active_region_photos

SIDO_LEVEL_CITY = ""


@dataclass(frozen=True)
class ResolvedRegionPhoto:
    image_url: str
    thumbnail_url: str | None
    alt: str
    attribution: str

    def to_api(self) -> dict[str, object]:
        return {
            "imageUrl": self.image_url,
            "thumbnailUrl": self.thumbnail_url,
            "alt": self.alt,
            "attribution": self.attribution,
        }


@dataclass(frozen=True)
class RegionPhotoIndex:
    _by_key: Mapping[tuple[str, str], ResolvedRegionPhoto]

    def resolve(
        self, region: str | None, city: str | None
    ) -> ResolvedRegionPhoto | None:
        if not region:
            return None
        if city:
            exact = self._by_key.get((region, city))
            if exact is not None:
                return exact
            normalized = normalize_municipality_name(city)
            if normalized and normalized != city:
                normalized_hit = self._by_key.get((region, normalized))
                if normalized_hit is not None:
                    return normalized_hit
        return self._by_key.get((region, SIDO_LEVEL_CITY))


EMPTY_REGION_PHOTO_INDEX = RegionPhotoIndex({})


def build_region_photo_index(db: Session | None) -> RegionPhotoIndex:
    if db is None:
        return EMPTY_REGION_PHOTO_INDEX
    try:
        photos = list_active_region_photos(db)
    except Exception:
        # 사진은 장식이다. 조회 실패(테이블 미생성, 세션 이상 등)가
        # 정책 응답 자체를 깨뜨리면 안 되므로 "사진 없음"으로 강등한다.
        logger.debug("region photo index unavailable; serving without photos")
        return EMPTY_REGION_PHOTO_INDEX
    by_key: dict[tuple[str, str], ResolvedRegionPhoto] = {}
    for photo in photos:
        if not photo.hero_image_url:
            continue
        by_key[(photo.sido, photo.city)] = ResolvedRegionPhoto(
            image_url=photo.hero_image_url,
            thumbnail_url=photo.thumb_image_url,
            alt=photo.content_title or f"{photo.sido} 대표 관광지",
            attribution=photo.attribution_text,
        )
    if not by_key:
        return EMPTY_REGION_PHOTO_INDEX
    return RegionPhotoIndex(by_key)
