"""Backfill region_photos from TourAPI for policy card hero images.

Run after deploy (and after normalize_external_policies.py so policies.city
is populated):
    cd backend
    python scripts/backfill_region_photos.py [--dry-run] [--limit N]
        [--refresh-older-than-days N] [--only-sido 전남]

Without TOUR_API_ENABLED=true + TOUR_API_SERVICE_KEY this is a no-op that
exits 0, so it is safe to wire into deploy scripts before a key exists.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
from collections.abc import Collection, Iterable, Sequence

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.data.travel_areas import normalize_municipality_name
from app.repositories.region_photos import get_region_photo, upsert_region_photo
from app.services.tour_api import (
    TourApiAreaCode,
    TourApiPhotoProvider,
    TourApiSpot,
    build_tour_api_client,
)

PROVIDER = "tour_api"
SIDO_LEVEL_CITY = ""

# policies.region의 축약형 → TourAPI areaCode 정식명 후보.
# 강원특별자치도/전북특별자치도 개칭 케이스 때문에 단순 일치는 조용히 0장이 된다.
# 변환은 이 스크립트의 TourAPI 경계 한 곳에서만 한다. DB에는 축약형만 저장한다.
_TOUR_API_SIDO_CANDIDATES: dict[str, tuple[str, ...]] = {
    "서울": ("서울특별시", "서울"),
    "부산": ("부산광역시", "부산"),
    "대구": ("대구광역시", "대구"),
    "인천": ("인천광역시", "인천"),
    "광주": ("광주광역시", "광주"),
    "대전": ("대전광역시", "대전"),
    "울산": ("울산광역시", "울산"),
    "세종": ("세종특별자치시", "세종"),
    "경기": ("경기도", "경기"),
    "강원": ("강원특별자치도", "강원도", "강원"),
    "충북": ("충청북도", "충북"),
    "충남": ("충청남도", "충남"),
    "전북": ("전북특별자치도", "전라북도", "전북"),
    "전남": ("전라남도", "전남"),
    "경북": ("경상북도", "경북"),
    "경남": ("경상남도", "경남"),
    "제주": ("제주특별자치도", "제주도", "제주"),
}


def resolve_area_code_for_sido(
    sido: str, area_codes: Sequence[TourApiAreaCode]
) -> str | None:
    candidates = _TOUR_API_SIDO_CANDIDATES.get(sido, (sido,))
    for candidate in candidates:
        for area in area_codes:
            if area.name == candidate or area.name.startswith(candidate):
                return area.code
    return None


def _addr_matches_sido(addr1: str | None, sido: str) -> bool:
    if not addr1:
        return False
    for candidate in _TOUR_API_SIDO_CANDIDATES.get(sido, (sido,)):
        if addr1.startswith(candidate):
            return True
    return False


def choose_representative_spot(
    spots: Iterable[TourApiSpot],
    *,
    sido: str,
    excluded_image_urls: Collection[str] = frozenset(),
) -> TourApiSpot | None:
    with_image = [
        spot
        for spot in spots
        if spot.first_image and spot.first_image not in excluded_image_urls
    ]
    for spot in with_image:
        if _addr_matches_sido(spot.addr1, sido):
            return spot
    # addr1이 없어 시도 일치를 못 가리는 항목만 남았다면 그것이라도 쓴다.
    for spot in with_image:
        if not spot.addr1:
            return spot
    return None


def build_target_keys(
    *,
    policy_pairs: Iterable[tuple[str | None, str | None]],
    record_pairs: Iterable[tuple[str | None, str | None]],
) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    sidos: list[str] = []
    for sido, city in [*policy_pairs, *record_pairs]:
        if not sido or sido == "전국":
            continue
        if sido not in sidos:
            sidos.append(sido)
        normalized_city = normalize_municipality_name(city) if city else None
        if not normalized_city:
            continue
        key = (sido, normalized_city)
        if key in seen:
            continue
        seen.add(key)
        keys.append(key)
    for sido in sidos:
        sentinel = (sido, SIDO_LEVEL_CITY)
        if sentinel not in seen:
            seen.add(sentinel)
            keys.append(sentinel)
    return keys


def _spots_for_target(
    provider: TourApiPhotoProvider,
    *,
    sido: str,
    city: str,
    area_code: str | None,
) -> list[TourApiSpot]:
    if area_code:
        spots = provider.list_area_spots(area_code=area_code)
        if city:
            matching = [
                spot
                for spot in spots
                if spot.addr1 and city in spot.addr1
            ]
            if matching:
                return matching
        elif spots:
            return spots
    keyword = f"{city} 관광지" if city else f"{sido} 관광지"
    return provider.search_spots_by_keyword(keyword=keyword)


def run_backfill(
    db,
    provider: TourApiPhotoProvider,
    *,
    targets: Sequence[tuple[str, str]],
    dry_run: bool,
    refresh_older_than: datetime | None = None,
) -> dict[str, object]:
    area_codes = provider.list_area_codes()
    area_code_by_sido: dict[str, str | None] = {}
    used_image_urls: set[str] = set()
    unmapped_sidos: list[str] = []
    filled = refreshed = skipped = failed = 0

    for sido, city in targets:
        if sido not in area_code_by_sido:
            area_code_by_sido[sido] = resolve_area_code_for_sido(sido, area_codes)
            if area_code_by_sido[sido] is None:
                unmapped_sidos.append(sido)
        existing = None
        if not dry_run:
            existing = get_region_photo(db, provider=PROVIDER, sido=sido, city=city)
            if existing is not None and existing.hero_image_url:
                fetched_at = existing.fetched_at
                if refresh_older_than is None or (
                    fetched_at is not None and fetched_at >= refresh_older_than
                ) and existing.hero_image_url not in used_image_urls:
                    used_image_urls.add(existing.hero_image_url)
                    skipped += 1
                    continue
        try:
            spots = _spots_for_target(
                provider,
                sido=sido,
                city=city,
                area_code=area_code_by_sido[sido],
            )
            spot = choose_representative_spot(
                spots, sido=sido, excluded_image_urls=used_image_urls
            )
            if spot is None and city:
                fallback_spots = _spots_for_target(
                    provider,
                    sido=sido,
                    city=SIDO_LEVEL_CITY,
                    area_code=area_code_by_sido[sido],
                )
                spot = choose_representative_spot(
                    fallback_spots,
                    sido=sido,
                    excluded_image_urls=used_image_urls,
                )
            if spot is None:
                spot = choose_representative_spot(spots, sido=sido)
        except Exception as exc:  # 개별 타깃 실패가 전체를 죽이면 안 된다.
            print(f"failed sido={sido} city={city or '(sido)'} error={exc}")
            failed += 1
            continue
        if spot is None:
            print(f"no_photo sido={sido} city={city or '(sido)'}")
            failed += 1
            continue
        if not dry_run:
            upsert_region_photo(
                db,
                provider=PROVIDER,
                sido=sido,
                city=city,
                provider_content_id=spot.content_id,
                content_title=spot.title or None,
                hero_image_url=spot.first_image,
                thumb_image_url=spot.first_image2 or spot.first_image,
                provider_image_url=spot.first_image,
                storage_kind="remote",
                fetched_at=datetime.now(UTC).replace(tzinfo=None),
            )
        if spot.first_image:
            used_image_urls.add(spot.first_image)
        if existing is not None:
            refreshed += 1
        else:
            filled += 1

    if not dry_run:
        db.commit()
    if unmapped_sidos:
        # 침묵 금지 — 매핑 실패는 곧 그 시도 정책 전체의 사진 0장이다.
        print(f"WARNING unmapped_sidos={unmapped_sidos}")
    return {
        "filled": filled,
        "refreshed": refreshed,
        "skipped": skipped,
        "failed": failed,
        "unmappedSidos": unmapped_sidos,
        "dryRun": dry_run,
    }


def _gather_targets(db, only_sido: str | None) -> list[tuple[str, str]]:
    from sqlalchemy import select

    from app.models import ExternalSourceRecord, Policy

    policy_pairs = list(
        db.execute(
            select(Policy.region, Policy.city).where(Policy.status == "active")
        ).all()
    )
    record_pairs = list(
        db.execute(select(ExternalSourceRecord.region, ExternalSourceRecord.city)).all()
    )
    keys = build_target_keys(policy_pairs=policy_pairs, record_pairs=record_pairs)
    if only_sido:
        keys = [key for key in keys if key[0] == only_sido]
    return keys


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Backfill region_photos from TourAPI for policy hero images.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--refresh-older-than-days", type=int, default=None)
    parser.add_argument("--only-sido", type=str, default=None)
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
        targets = _gather_targets(db, args.only_sido)
        if args.limit is not None:
            targets = targets[: args.limit]
        summary = run_backfill(
            db,
            provider,
            targets=targets,
            dry_run=args.dry_run,
            refresh_older_than=refresh_older_than,
        )
    print(
        "filled={filled} refreshed={refreshed} skipped={skipped} failed={failed}".format(
            **summary
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
