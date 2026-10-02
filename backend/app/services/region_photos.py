"""Region photo lookup for policy cards.

The resolver is a pure in-memory index built once per request. Photos are the
candidates an admin approved in photo review (0047): region targets are keyed by
(sido, city) - `city == ""` is the sido-level photo - and policy targets by
policy id. Only candidates whose original was stored on our media volume are
served (`/api/media/...`); the resolver never hotlinks TourAPI URLs. Callers that
have no DB session use ``EMPTY_REGION_PHOTO_INDEX`` so every payload builder
degrades to "no photo" without branching.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.data.travel_areas import normalize_municipality_name
from app.repositories.photo_review import list_published
from app.services.photo_criteria import attribution_for
from app.services.photo_storage import media_url

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
    _by_policy_id: Mapping[int, ResolvedRegionPhoto] = field(default_factory=dict)

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
            # 시군 사진이 없으면 도 대표 사진으로 넘어가지 않는다(2026-10-01 사용자 결정) - 같은 도의 여러 시군이
            # 한 장을 나눠 써 같은 사진이 되풀이됐다. 사진 없음 → 화면은 혜택 그림.
            return None
        return self._by_key.get((region, SIDO_LEVEL_CITY))

    def resolve_policy(
        self, policy_id: int, region: str | None, city: str | None
    ) -> ResolvedRegionPhoto | None:
        return self._by_policy_id.get(policy_id) or self.resolve(region, city)


EMPTY_REGION_PHOTO_INDEX = RegionPhotoIndex({})


def build_region_photo_index(db: Session | None) -> RegionPhotoIndex:
    if db is None:
        return EMPTY_REGION_PHOTO_INDEX
    try:
        published = list_published(db)
    except Exception:
        # 사진은 장식이다. 조회 실패(테이블 미생성, 세션 이상 등)가
        # 정책 응답 자체를 깨뜨리면 안 되므로 "사진 없음"으로 강등한다.
        logger.debug("photo review index unavailable; serving without photos")
        return EMPTY_REGION_PHOTO_INDEX
    by_key: dict[tuple[str, str], ResolvedRegionPhoto] = {}
    by_policy_id: dict[int, ResolvedRegionPhoto] = {}
    for target, candidate in published:
        photo = ResolvedRegionPhoto(
            image_url=media_url(candidate.stored_path),
            thumbnail_url=None,   # 관광공사 축소판은 120x80 이라 쓰지 않는다 - 화면은 원본을 줄여 쓴다
            alt=candidate.title or f"{target.sido} 대표 관광지",
            attribution=attribution_for(candidate.copyright_type),
        )
        if target.target_type == "policy" and target.policy_id is not None:
            by_policy_id[target.policy_id] = photo
        elif target.target_type == "region":
            by_key[(target.sido, target.city)] = photo
    if not by_key and not by_policy_id:
        return EMPTY_REGION_PHOTO_INDEX
    return RegionPhotoIndex(by_key, by_policy_id)
