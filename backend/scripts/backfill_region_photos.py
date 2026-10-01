"""Backfill region_photos from TourAPI for policy card hero images.

Run after deploy (and after normalize_external_policies.py so policies.city
is populated):
    cd backend
    python scripts/backfill_region_photos.py [--dry-run] [--limit N]
        [--refresh-older-than-days N] [--only-sido 전남] [--report out.json]

Without TOUR_API_ENABLED=true + TOUR_API_SERVICE_KEY this is a no-op that
exits 0, so it is safe to wire into deploy scripts before a key exists.

사진은 수집 기준(app/services/photo_criteria.py - 홈 배너 사진과 같은 기준)을 거친다(2026-10-01):
저작권 유형 · 시설 · 다른 시군과 같은 사진 · 도 일치 · 가로/크기. 시군 줄은 그 시군 관광지(시군 코드)에서만 고르고,
맞는 사진이 없으면 도 대표 사진으로 넘어가지 않고 비운다(있던 줄은 숨긴다 - 화면은 혜택 그림).
기준이 생기기 전에 넣은 줄(저작권 유형 없음)과 다른 줄과 같은 사진을 쓰는 줄은 갱신 날짜와 상관없이 다시 고른다.
--report 는 대상마다 고른 것과 뺀 것(이유)을 JSON 으로 남긴다 - 사람 검토용(docs/photo-sourcing/tools/report_sheet.py).
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Collection, Iterable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.data.travel_areas import normalize_municipality_name
from app.repositories.region_photos import get_region_photo, upsert_region_photo
from app.services.photo_criteria import (
    ImageSizeProbe,
    attribution_for,
    metadata_rejections,
    size_rejections,
)
from app.services.tour_api import (
    TourApiAreaCode,
    TourApiPhotoProvider,
    TourApiSpot,
    build_tour_api_client,
)

PROVIDER = "tour_api"
# 전국 정책은 시도가 없어 지역코드로 못 찾는다 - 나라 전체를 대표하는 사진 한 장을 키워드로 찾아
# (전국, "") 행에 둔다. 전국 정책은 시군이 없으니 resolve() 가 이 행을 쓴다.
NATIONWIDE_SIDO = "전국"
NATIONWIDE_KEYWORD = "대한민국 여행"
SIDO_LEVEL_CITY = ""
CITY_SPOT_ROWS = 30
SIDO_SPOT_ROWS = 30
REPORT_REJECTED_LIMIT = 12

# policies.region의 축약형 → TourAPI areaCode 정식명 · 주소 앞머리 후보.
# 강원특별자치도/전북특별자치도 개칭 케이스 때문에 단순 일치는 조용히 0장이 된다.
# 2026-10-01 실측: 전남·광주 관광지 주소가 모두 '전남광주통합특별시'로 시작한다 - 주소만으로는 둘을 못 가르므로
# 두 곳 다 받아들이고, 도 구분은 지역코드(areaCode)로 한다. 지역코드 이름 맞추기에는 걸리지 않게 맨 뒤에 둔다.
# 변환은 이 스크립트의 TourAPI 경계 한 곳에서만 한다. DB에는 축약형만 저장한다.
_TOUR_API_SIDO_CANDIDATES: dict[str, tuple[str, ...]] = {
    "서울": ("서울특별시", "서울"),
    "부산": ("부산광역시", "부산"),
    "대구": ("대구광역시", "대구"),
    "인천": ("인천광역시", "인천"),
    "광주": ("광주광역시", "광주", "전남광주통합특별시"),
    "대전": ("대전광역시", "대전"),
    "울산": ("울산광역시", "울산"),
    "세종": ("세종특별자치시", "세종"),
    "경기": ("경기도", "경기"),
    "강원": ("강원특별자치도", "강원도", "강원"),
    "충북": ("충청북도", "충북"),
    "충남": ("충청남도", "충남"),
    "전북": ("전북특별자치도", "전라북도", "전북"),
    "전남": ("전라남도", "전남", "전남광주통합특별시"),
    "경북": ("경상북도", "경북"),
    "경남": ("경상남도", "경남"),
    "제주": ("제주특별자치도", "제주도", "제주"),
}

SizeOf = Callable[[str], "tuple[int, int] | None"]
Rejected = list[tuple[TourApiSpot, list[str]]]


def resolve_area_code_for_sido(
    sido: str, area_codes: Sequence[TourApiAreaCode]
) -> str | None:
    candidates = _TOUR_API_SIDO_CANDIDATES.get(sido, (sido,))
    for candidate in candidates:
        for area in area_codes:
            if area.name == candidate or area.name.startswith(candidate):
                return area.code
    return None


def resolve_sigungu_code(
    city: str, sigungu_codes: Sequence[TourApiAreaCode], sido: str | None = None
) -> str | None:
    """'영광' ↔ '영광군', 정책 표기 '부산동'(부산 동구) ↔ '동구'. 이름이 같은 시군 코드."""

    names = {city, city.removeprefix(sido or "")}
    for area in sigungu_codes:
        if names & {area.name, normalize_municipality_name(area.name), area.name[:-1]}:
            return area.code
    return None


def _addr_matches_sido(addr1: str | None, sido: str) -> bool:
    if not addr1:
        return False
    for candidate in _TOUR_API_SIDO_CANDIDATES.get(sido, (sido,)):
        if addr1.startswith(candidate):
            return True
    return False


def spot_rejections(
    spot: TourApiSpot,
    *,
    sido: str | None,
    excluded_image_urls: Collection[str],
    size_of: SizeOf | None,
) -> list[str]:
    """수집 기준(photo_criteria) + 겹침 + 도 일치. 앞의 것이 다 통과할 때만 사진을 받아 크기를 잰다."""

    reasons = metadata_rejections(
        title=spot.title, image_url=spot.first_image, copyright_type=spot.copyright_type
    )
    if spot.first_image and spot.first_image in excluded_image_urls:
        reasons.append("duplicate")
    # 주소가 없으면 도 일치를 확인할 수 없다 - 지역코드로 받은 목록이라 그대로 둔다
    if sido and spot.addr1 and not _addr_matches_sido(spot.addr1, sido):
        reasons.append("other-sido")
    if not reasons and size_of is not None and spot.first_image:
        reasons = size_rejections(size_of(spot.first_image))
    return reasons


def choose_representative_spot(
    spots: Iterable[TourApiSpot],
    *,
    sido: str | None,
    excluded_image_urls: Collection[str] = frozenset(),
    size_of: SizeOf | None = None,
    rejected: Rejected | None = None,
) -> TourApiSpot | None:
    """받은 순서(조회순)대로 기준을 다 통과한 첫 곳. 없으면 None - 이미 쓴 사진을 다시 쓰지 않는다."""

    for spot in spots:
        reasons = spot_rejections(
            spot, sido=sido, excluded_image_urls=excluded_image_urls, size_of=size_of
        )
        if not reasons:
            return spot
        if rejected is not None:
            rejected.append((spot, reasons))
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
        if not sido:
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
    sigungu_code: str | None = None,
) -> list[TourApiSpot]:
    if area_code:
        if not city:
            return provider.list_area_spots(area_code=area_code, rows=SIDO_SPOT_ROWS)
        # 시군 줄은 그 시군 관광지에서만 - 도 전체 앞쪽 몇 곳을 주소로 고르면 대부분 비어 도 사진으로 넘어갔다
        if sigungu_code:
            return provider.list_area_spots(
                area_code=area_code, sigungu_code=sigungu_code, rows=CITY_SPOT_ROWS
            )
        spots = provider.list_area_spots(area_code=area_code, rows=CITY_SPOT_ROWS * 2)
        return [spot for spot in spots if spot.addr1 and city in spot.addr1]
    if sido == NATIONWIDE_SIDO and not city:
        keyword = NATIONWIDE_KEYWORD
    else:
        keyword = f"{city} 관광지" if city else f"{sido} 관광지"
    return provider.search_spots_by_keyword(keyword=keyword)


def _report_spot(spot: TourApiSpot) -> dict[str, object]:
    return {
        "contentId": spot.content_id,
        "title": spot.title,
        "imageUrl": spot.first_image,
        "copyright": spot.copyright_type,
        "category": spot.category_code,
    }


def run_backfill(
    db,
    provider: TourApiPhotoProvider,
    *,
    targets: Sequence[tuple[str, str]],
    dry_run: bool,
    refresh_older_than: datetime | None = None,
    size_of: SizeOf | None = None,
    report: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    area_codes = provider.list_area_codes()
    area_code_by_sido: dict[str, str | None] = {}
    sigungu_codes_by_area: dict[str, list[TourApiAreaCode]] = {}
    unmapped_sidos: list[str] = []
    filled = refreshed = skipped = failed = emptied = 0

    existing_by_target = {}
    if not dry_run:
        for sido, city in targets:
            existing_by_target[(sido, city)] = get_region_photo(
                db, provider=PROVIDER, sido=sido, city=city
            )
    # 다른 줄과 같은 사진을 쓰는 줄은 다시 고른다 - 먼저 나온 줄 하나만 그 사진을 지킨다
    claimed: dict[str, tuple[str, str]] = {}
    for target, row in existing_by_target.items():
        if row is not None and row.status == "active" and row.hero_image_url:
            claimed.setdefault(row.hero_image_url, target)
    used_image_urls: set[str] = set()

    for sido, city in targets:
        if sido not in area_code_by_sido:
            if sido == NATIONWIDE_SIDO:
                area_code_by_sido[sido] = None  # 지역코드가 없는 게 정상 - 경고 대상 아님
            else:
                area_code_by_sido[sido] = resolve_area_code_for_sido(sido, area_codes)
                if area_code_by_sido[sido] is None:
                    unmapped_sidos.append(sido)
        area_code = area_code_by_sido[sido]
        existing = existing_by_target.get((sido, city))
        if existing is not None and existing.status == "active" and existing.hero_image_url:
            is_fresh = refresh_older_than is None or (
                existing.fetched_at is not None and existing.fetched_at >= refresh_older_than
            )
            meets_criteria = existing.copyright_type is not None  # 기준이 생긴 뒤 고른 줄
            unique = claimed.get(existing.hero_image_url) == (sido, city)
            if is_fresh and meets_criteria and unique:
                used_image_urls.add(existing.hero_image_url)
                skipped += 1
                continue
        rejected: Rejected = []
        try:
            sigungu_code = None
            if city and area_code:
                if area_code not in sigungu_codes_by_area:
                    sigungu_codes_by_area[area_code] = provider.list_area_codes(area_code=area_code)
                sigungu_code = resolve_sigungu_code(city, sigungu_codes_by_area[area_code], sido)
            spots = _spots_for_target(
                provider, sido=sido, city=city, area_code=area_code, sigungu_code=sigungu_code
            )
            spot = choose_representative_spot(
                spots,
                sido=None if sido == NATIONWIDE_SIDO else sido,
                excluded_image_urls=used_image_urls,
                size_of=size_of,
                rejected=rejected,
            )
        except Exception as exc:  # 개별 타깃 실패가 전체를 죽이면 안 된다.
            print(f"failed sido={sido} city={city or '(sido)'} error={exc}")
            failed += 1
            continue
        size = size_of(spot.first_image) if spot is not None and size_of and spot.first_image else None
        if report is not None:
            report.append({
                "sido": sido,
                "city": city,
                "chosen": None if spot is None else {**_report_spot(spot), "size": size},
                "rejected": [
                    {**_report_spot(item), "reasons": reasons}
                    for item, reasons in rejected[:REPORT_REJECTED_LIMIT]
                ],
            })
        if spot is None:
            # 도 대표 사진으로 넘어가지 않고 비운다 - 있던 줄은 숨겨 응답에서 빠지게(화면은 혜택 그림)
            if not dry_run and existing is not None and existing.status == "active":
                upsert_region_photo(db, provider=PROVIDER, sido=sido, city=city, status="hidden")
                emptied += 1
            print(f"no_photo sido={sido} city={city or '(sido)'} rejected={len(rejected)}")
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
                attribution_text=attribution_for(spot.copyright_type),
                copyright_type=spot.copyright_type,
                image_width=size[0] if size else None,
                image_height=size[1] if size else None,
                selection_reason="criteria_v1",
                status="active",
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
        "emptied": emptied,
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
        targets = _gather_targets(db, args.only_sido)
        if args.limit is not None:
            targets = targets[: args.limit]
        summary = run_backfill(
            db,
            provider,
            targets=targets,
            dry_run=args.dry_run,
            refresh_older_than=refresh_older_than,
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
