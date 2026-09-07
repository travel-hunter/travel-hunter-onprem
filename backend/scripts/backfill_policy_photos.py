"""Assign policy-specific card photos from TourAPI without changing policy data.

Run this after policy normalization and region-photo backfill.  It only writes
to ``policy_photos``; policies without a suitable specific image continue to
use the region/city fallback at API response time.
"""

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.repositories.policies import list_active_policies_for_photo_backfill
from app.repositories.policy_photos import get_policy_photo, upsert_policy_photo
from app.services.pixabay import PixabayImage, PixabayPhotoProvider, build_pixabay_client
from scripts.backfill_region_photos import (
    PROVIDER,
    _addr_matches_sido,
    resolve_area_code_for_sido,
)
from app.services.tour_api import (
    TourApiPhotoProvider,
    TourApiSpot,
    build_tour_api_client,
)

_GENERIC_KEYWORDS = frozenset(
    {
        "지원",
        "할인",
        "여행",
        "관광",
        "정책",
        "사업",
        "혜택",
        "신청",
        "모집",
        "참여",
        "대상",
        "지역",
    }
)
_TITLE_TOKEN = re.compile(r"[가-힣A-Za-z0-9]{2,}")
_TITLE_CITY_MARKER = re.compile(r"^\[([^\]]+)\]")


@dataclass(frozen=True)
class PhotoCandidate:
    spot: TourApiSpot
    relevance_score: int
    assignment_reason: str


def policy_keywords(*, title: str, region: str, city: str | None) -> list[str]:
    """Extract a small, deterministic keyword set without making title a contract."""

    excluded = {region, city or "", *_GENERIC_KEYWORDS}
    keywords: list[str] = []
    for token in _TITLE_TOKEN.findall(title):
        if token in excluded or token in keywords:
            continue
        keywords.append(token)
    return keywords[:2]


def policy_city_hint(policy: object) -> str | None:
    """Use normalized policy data first, then the visible `[city]` title marker."""

    region = str(policy.region).strip()
    city = str(policy.city).strip() if policy.city else ""
    if city and city != region:
        return city
    marker = _TITLE_CITY_MARKER.match(str(policy.title).strip())
    if marker:
        city = marker.group(1).strip()
        if city and city != region:
            return city
    return None


def _city_matches(spot: TourApiSpot, city: str | None) -> bool:
    if not city:
        return False
    return city in (spot.addr1 or "") or city in spot.title


def _keyword_matches(spot: TourApiSpot, keywords: Iterable[str]) -> bool:
    title = spot.title.casefold()
    return any(keyword.casefold() in title for keyword in keywords)


def choose_policy_photo(
    spots: Iterable[TourApiSpot],
    *,
    sido: str,
    city: str | None,
    keywords: Iterable[str],
    excluded_image_urls: Collection[str] = frozenset(),
) -> PhotoCandidate | None:
    """Rank specific candidates; leave generic regional fallback to the resolver."""

    keyword_list = list(keywords)
    candidates: list[PhotoCandidate] = []
    for spot in spots:
        if not spot.first_image:
            continue
        city_match = _city_matches(spot, city)
        keyword_match = _keyword_matches(spot, keyword_list)
        sido_match = _addr_matches_sido(spot.addr1, sido)
        if not (city_match or keyword_match or sido_match):
            continue
        if city_match:
            score, reason = 300, "city_match"
        elif keyword_match:
            score, reason = 200, "policy_keyword"
        else:
            score, reason = 100, "sido_match"
        if keyword_match and reason != "policy_keyword":
            score += 25
        candidates.append(
            PhotoCandidate(
                spot=spot,
                relevance_score=score,
                assignment_reason=reason,
            )
        )

    candidates.sort(
        key=lambda candidate: (-candidate.relevance_score, candidate.spot.content_id)
    )
    for candidate in candidates:
        if candidate.spot.first_image not in excluded_image_urls:
            return candidate
    return candidates[0] if candidates else None


def choose_city_photo(
    spots: Iterable[TourApiSpot],
    *,
    city: str | None,
    excluded_image_urls: Collection[str] = frozenset(),
) -> PhotoCandidate | None:
    """Persist only a genuine city match; regional images stay resolver fallbacks."""

    if not city:
        return None
    candidates = [
        PhotoCandidate(spot=spot, relevance_score=300, assignment_reason="city_match")
        for spot in spots
        if spot.first_image and _city_matches(spot, city)
    ]
    candidates.sort(key=lambda candidate: candidate.spot.content_id)
    for candidate in candidates:
        if candidate.spot.first_image not in excluded_image_urls:
            return candidate
    return candidates[0] if candidates else None


def _unique_spots(groups: Iterable[Iterable[TourApiSpot]]) -> list[TourApiSpot]:
    unique: list[TourApiSpot] = []
    seen: set[str] = set()
    for group in groups:
        for spot in group:
            key = spot.content_id or spot.first_image or spot.title
            if key in seen:
                continue
            seen.add(key)
            unique.append(spot)
    return unique


def _spots_for_city(
    provider: TourApiPhotoProvider,
    *,
    region: str,
    city: str | None,
    area_code: str | None,
) -> list[TourApiSpot]:
    groups: list[list[TourApiSpot]] = []
    if area_code:
        groups.append(provider.list_area_spots(area_code=area_code, rows=50))
    if city:
        groups.append(provider.search_spots_by_keyword(keyword=f"{city} 관광지", rows=30))
    return _unique_spots(groups)


def run_backfill(
    db,
    provider: TourApiPhotoProvider,
    *,
    policies: Sequence[object],
    dry_run: bool,
    refresh_older_than: datetime | None = None,
    fallback_provider: PixabayPhotoProvider | None = None,
    force: bool = False,
) -> dict[str, int]:
    area_codes = None
    area_code_by_region: dict[str, str | None] = {}
    tour_spots_by_location: dict[tuple[str, str], list[TourApiSpot]] = {}
    pixabay_images_by_city: dict[str, list[PixabayImage]] = {}
    used_image_urls: set[str] = set()
    filled = refreshed = skipped = failed = 0

    for policy in policies:
        policy_id = int(policy.id)
        existing = get_policy_photo(db, policy_id=policy_id)
        if (
            not force
            and existing is not None
            and existing.status == "active"
            and existing.image_url
        ):
            is_fresh = (
                refresh_older_than is None
                or existing.fetched_at is not None
                and existing.fetched_at >= refresh_older_than
            )
            if is_fresh:
                used_image_urls.add(existing.image_url)
                skipped += 1
                continue

        region = str(policy.region)
        city = policy_city_hint(policy)
        if region not in area_code_by_region:
            if area_codes is None:
                area_codes = provider.list_area_codes()
            area_code_by_region[region] = resolve_area_code_for_sido(region, area_codes)
        try:
            location = (region, city or "")
            if location not in tour_spots_by_location:
                tour_spots_by_location[location] = _spots_for_city(
                    provider,
                    region=region,
                    city=city,
                    area_code=area_code_by_region[region],
                )
            candidate = choose_city_photo(
                tour_spots_by_location[location],
                city=city,
                excluded_image_urls=used_image_urls,
            )
            fallback_image = None
            if candidate is None and fallback_provider is not None and city:
                if city not in pixabay_images_by_city:
                    pixabay_images_by_city[city] = fallback_provider.search_images(
                        query=f"{city} landscape", rows=20
                    )
                images = pixabay_images_by_city[city]
                fallback_image = next(
                    (image for image in images if image.image_url not in used_image_urls),
                    images[0] if images else None,
                )
        except Exception as exc:
            print(f"failed policy_id={policy_id} error={exc}")
            failed += 1
            continue
        if candidate is None and fallback_image is None:
            # A forced refresh is an explicit request to replace old choices.  Do
            # not keep a now-unverifiable city photo active: hiding it lets the
            # API use the region-level fallback instead.
            if not dry_run and force and existing is not None:
                upsert_policy_photo(db, policy_id=policy_id, status="hidden")
            print(f"no_specific_photo policy_id={policy_id}")
            failed += 1
            continue

        if not dry_run:
            if candidate is not None:
                upsert_policy_photo(
                    db,
                    policy_id=policy_id,
                    provider=PROVIDER,
                    provider_content_id=candidate.spot.content_id,
                    image_url=candidate.spot.first_image,
                    thumbnail_url=candidate.spot.first_image2 or candidate.spot.first_image,
                    alt_text=candidate.spot.title or str(policy.title),
                    attribution_text="Photo: Korea Tourism Organization TourAPI",
                    relevance_score=candidate.relevance_score,
                    assignment_reason=candidate.assignment_reason,
                    status="active",
                    fetched_at=datetime.now(UTC).replace(tzinfo=None),
                )
            else:
                assert fallback_image is not None
                upsert_policy_photo(
                    db,
                    policy_id=policy_id,
                    provider="pixabay",
                    provider_content_id=fallback_image.content_id,
                    image_url=fallback_image.image_url,
                    thumbnail_url=fallback_image.thumbnail_url,
                    alt_text=fallback_image.alt_text,
                    attribution_text=fallback_image.attribution,
                    relevance_score=100,
                    assignment_reason="pixabay_city_fallback",
                    status="active",
                    fetched_at=datetime.now(UTC).replace(tzinfo=None),
                )
        used_image_urls.add(
            candidate.spot.first_image if candidate is not None else fallback_image.image_url
        )
        if existing is None:
            filled += 1
        else:
            refreshed += 1

    if not dry_run:
        db.commit()
    return {
        "filled": filled,
        "refreshed": refreshed,
        "skipped": skipped,
        "failed": failed,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill policy-specific photos from TourAPI."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--refresh-older-than-days", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    provider = build_tour_api_client()
    if provider is None:
        print("tour_api_disabled; no-op")
        return 0

    refresh_older_than = None
    if args.refresh_older_than_days is not None:
        refresh_older_than = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            days=args.refresh_older_than_days
        )

    from app.db.session import get_session_factory

    session_factory = get_session_factory()
    with session_factory() as db:
        policies = list_active_policies_for_photo_backfill(db)
        if args.limit is not None:
            policies = policies[: args.limit]
        summary = run_backfill(
            db,
            provider,
            policies=policies,
            dry_run=args.dry_run,
            refresh_older_than=refresh_older_than,
            fallback_provider=build_pixabay_client(),
            force=args.force,
        )
    print("filled={filled} refreshed={refreshed} skipped={skipped} failed={failed}".format(**summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
