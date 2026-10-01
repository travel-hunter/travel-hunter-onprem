"""Assign policy-specific card photos from TourAPI without changing policy data.

Run this after policy normalization and region-photo backfill.  It only writes
to ``policy_photos``; policies without a suitable specific image continue to
use the region/city fallback at API response time.

사진은 수집 기준(app/services/photo_criteria.py, 지역 사진과 같은 기준)을 거친다(2026-10-01): 그 시군 관광지(시군 코드)에서
저작권 유형 · 시설 · 겹침 · 가로/크기를 통과한 첫 곳. 이미 쓴 사진은 다시 쓰지 않는다. 기준 이전에 넣은 줄(저작권 유형 없음)과
다른 정책과 같은 사진을 쓰는 줄은 다시 고르고, 맞는 곳이 없으면 숨긴다(응답은 시군 사진 차례).
"""

from __future__ import annotations

import argparse
import json
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
from app.services.photo_criteria import ImageSizeProbe, attribution_for
from app.services.pixabay import PixabayImage, PixabayPhotoProvider
from scripts.backfill_region_photos import (
    CITY_SPOT_ROWS,
    PROVIDER,
    REPORT_REJECTED_LIMIT,
    Rejected,
    SizeOf,
    _addr_matches_sido,
    _report_spot,
    resolve_area_code_for_sido,
    resolve_sigungu_code,
    spot_rejections,
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
    sido: str | None = None,
    size_of: SizeOf | None = None,
    rejected: Rejected | None = None,
    sigungu_code: str | None = None,
) -> PhotoCandidate | None:
    """Persist only a genuine city match; regional images stay resolver fallbacks.

    받은 순서(조회순)대로 수집 기준을 다 통과한 첫 시군 관광지. 이미 쓴 사진은 다시 쓰지 않는다(없으면 None).
    시군 코드가 같으면 주소에 정책 표기('부산동구')가 없어도 그 시군 관광지다.
    """

    if not city:
        return None
    for spot in spots:
        in_city = bool(sigungu_code) and spot.sigungu_code == sigungu_code
        if not spot.first_image or not (in_city or _city_matches(spot, city)):
            continue
        reasons = spot_rejections(
            spot, sido=sido, excluded_image_urls=excluded_image_urls, size_of=size_of
        )
        if not reasons:
            return PhotoCandidate(spot=spot, relevance_score=300, assignment_reason="city_match")
        if rejected is not None:
            rejected.append((spot, reasons))
    return None


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
    sigungu_code: str | None = None,
) -> list[TourApiSpot]:
    # 시군 코드가 있으면 그 시군 관광지만. 2026-10-01 실측: '{시군} 관광지' 키워드 검색은 0건이라 시군 코드가 없을 때만 덧붙인다
    if area_code and sigungu_code:
        return provider.list_area_spots(
            area_code=area_code, sigungu_code=sigungu_code, rows=CITY_SPOT_ROWS
        )
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
    size_of: SizeOf | None = None,
    report: list[dict[str, object]] | None = None,
) -> dict[str, int]:
    area_codes = None
    area_code_by_region: dict[str, str | None] = {}
    sigungu_codes_by_area: dict[str, list] = {}
    tour_spots_by_location: dict[tuple[str, str], list[TourApiSpot]] = {}
    pixabay_images_by_city: dict[str, list[PixabayImage]] = {}
    used_image_urls: set[str] = set()
    filled = refreshed = skipped = failed = emptied = 0

    # dry-run 은 기존 줄을 읽지 않는다 - 지금 기준으로 새로 고르면 무엇을 고르는지 보는 보고서용(지역 사진 스크립트와 같다)
    existing_by_policy = {
        int(policy.id): None if dry_run else get_policy_photo(db, policy_id=int(policy.id)) for policy in policies
    }
    # 다른 정책과 같은 사진을 쓰는 줄은 다시 고른다 - 먼저 나온 정책 하나만 그 사진을 지킨다
    claimed: dict[str, int] = {}
    for policy_id, row in existing_by_policy.items():
        if row is not None and row.status == "active" and row.image_url:
            claimed.setdefault(row.image_url, policy_id)

    for policy in policies:
        policy_id = int(policy.id)
        existing = existing_by_policy[policy_id]
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
            meets_criteria = getattr(existing, "copyright_type", None) is not None  # 기준이 생긴 뒤 고른 줄
            unique = claimed.get(existing.image_url) == policy_id
            if is_fresh and meets_criteria and unique:
                used_image_urls.add(existing.image_url)
                skipped += 1
                continue

        region = str(policy.region)
        city = policy_city_hint(policy)
        rejected: Rejected = []
        if region not in area_code_by_region:
            if area_codes is None:
                area_codes = provider.list_area_codes()
            area_code_by_region[region] = resolve_area_code_for_sido(region, area_codes)
        try:
            area_code = area_code_by_region[region]
            sigungu_code = None
            if city and area_code:
                if area_code not in sigungu_codes_by_area:
                    sigungu_codes_by_area[area_code] = provider.list_area_codes(area_code=area_code)
                sigungu_code = resolve_sigungu_code(city, sigungu_codes_by_area[area_code], region)
            location = (region, city or "")
            if location not in tour_spots_by_location:
                tour_spots_by_location[location] = _spots_for_city(
                    provider,
                    region=region,
                    city=city,
                    area_code=area_code,
                    sigungu_code=sigungu_code,
                )
            candidate = choose_city_photo(
                tour_spots_by_location[location],
                city=city,
                excluded_image_urls=used_image_urls,
                sido=region,
                size_of=size_of,
                rejected=rejected,
                sigungu_code=sigungu_code,
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
        size = (
            size_of(candidate.spot.first_image)
            if candidate is not None and size_of is not None and candidate.spot.first_image
            else None
        )
        if report is not None:
            report.append({
                "policyId": policy_id,
                "title": str(policy.title),
                "sido": region,
                "city": city,
                "chosen": None if candidate is None else {**_report_spot(candidate.spot), "size": size},
                "rejected": [
                    {**_report_spot(item), "reasons": reasons}
                    for item, reasons in rejected[:REPORT_REJECTED_LIMIT]
                ],
            })
        if candidate is None and fallback_image is None:
            # 맞는 시군 사진이 없으면 있던 줄을 숨긴다 - 기준 이전 줄이거나(저작권 유형 없음) 다른 정책과
            # 같은 사진이다. 강제 갱신(--force)이면 늘 숨긴다. 응답은 시군 사진(region_photos) 차례가 된다.
            if not dry_run and existing is not None and existing.status == "active":
                upsert_policy_photo(db, policy_id=policy_id, status="hidden")
                emptied += 1
            print(f"no_specific_photo policy_id={policy_id} rejected={len(rejected)}")
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
                    attribution_text=attribution_for(candidate.spot.copyright_type),
                    copyright_type=candidate.spot.copyright_type,
                    image_width=size[0] if size else None,
                    image_height=size[1] if size else None,
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
        "emptied": emptied,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill policy-specific photos from TourAPI."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--refresh-older-than-days", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--report", type=str, default=None, help="고른 것·뺀 것(이유)을 이 JSON 파일에 쓴다")
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

    report: list[dict[str, object]] | None = [] if args.report else None
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
            # Pixabay 폴백은 끈다. API 가 주는 이미지 주소는 임시라 저장하면 며칠 뒤 죽는다 -
            # 9/07 배정분 16건이 그렇게 전부 만료됐다. 내려받아 보관하는 길이 생기기 전까지는
            # 시군 사진이 없으면 저장하지 않고 응답 시점의 지역 폴백에 맡긴다.
            # (2026-09-17-policy-photo-managed-storage.md 에서 managed 저장과 함께 되살린다)
            fallback_provider=None,
            force=args.force,
            size_of=ImageSizeProbe(),
            report=report,
        )
    if report is not None:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        "filled={filled} refreshed={refreshed} skipped={skipped} failed={failed} emptied={emptied}".format(
            **summary
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
