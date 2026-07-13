from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable

from app.core.config import settings
from app.data.travel_areas import TravelArea, get_travel_area
from app.services import itinerary_recommendations
from app.services.kakao_local import KakaoLocalClient, KakaoLocalConfigurationError
from app.services.trips import KakaoItineraryPlaceProvider


DEFAULT_AREA_IDS = (
    "jeju-all",
    "busan-all",
    "gangwon-sokcho-goseong-yangyang",
    "jeonnam-yeosu-suncheon",
    "gyeongbuk-gyeongju",
)
DEFAULT_STYLE = "휴식"
DEFAULT_DAY_COUNT = 3
DEFAULT_MIN_CANDIDATES = 6


@dataclass(frozen=True)
class SmokeRow:
    travelAreaId: str
    area: str
    sido: str
    mode: str
    candidateCount: int
    categoryCounts: dict[str, int]
    metadata: dict[str, int]
    status: str
    sampleTitles: list[str]


def _category_counts(candidates: Iterable[itinerary_recommendations.ExternalPlaceCandidate]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for candidate in candidates:
        category = itinerary_recommendations.category_group_for_code(candidate.category_group_code)
        counts[category] = counts.get(category, 0) + 1
    return counts


def _metadata_counts(candidates: list[itinerary_recommendations.ExternalPlaceCandidate]) -> dict[str, int]:
    return {
        "withAddress": sum(1 for candidate in candidates if candidate.address),
        "withCoordinates": sum(1 for candidate in candidates if candidate.latitude is not None and candidate.longitude is not None),
        "withPlaceUrl": sum(1 for candidate in candidates if candidate.place_url),
        "withExternalPlaceId": sum(1 for candidate in candidates if candidate.external_place_id),
    }


def _fallback_candidates(area: TravelArea, *, style: str, day_count: int) -> list[itinerary_recommendations.ExternalPlaceCandidate]:
    course = itinerary_recommendations.generate_auto_course(
        region=area.name,
        style=style,
        start_date=date(2026, 7, 12),
        day_count=day_count,
        travel_area_id=area.id,
    )
    return [
        itinerary_recommendations.ExternalPlaceCandidate(
            source_provider="catalog_fallback",
            external_place_id=f"{area.id}:{index}",
            title=place.title,
            category_group_code=None,
            category_group_name=place.label,
            address=None,
            city=area.name,
        )
        for index, place in enumerate(course.places, start=1)
    ]


def _kakao_candidates(
    area: TravelArea,
    *,
    style: str,
    day_count: int,
    limit: int,
    provider: KakaoItineraryPlaceProvider,
) -> list[itinerary_recommendations.ExternalPlaceCandidate]:
    return itinerary_recommendations.additional_place_candidates(
        region=area.name,
        style=style,
        day_count=day_count,
        travel_area_id=area.id,
        external_provider=provider,
        limit=limit,
    )


def _row_for_candidates(
    area: TravelArea,
    *,
    mode: str,
    candidates: list[itinerary_recommendations.ExternalPlaceCandidate],
    min_candidates: int,
) -> SmokeRow:
    return SmokeRow(
        travelAreaId=area.id,
        area=area.name,
        sido=area.sido,
        mode=mode,
        candidateCount=len(candidates),
        categoryCounts=_category_counts(candidates),
        metadata=_metadata_counts(candidates),
        status="PASS" if len(candidates) >= min_candidates else "FAIL",
        sampleTitles=[candidate.title for candidate in candidates[:5]],
    )


def resolve_areas(area_ids: Iterable[str]) -> list[TravelArea]:
    areas: list[TravelArea] = []
    missing: list[str] = []
    for area_id in area_ids:
        area = get_travel_area(area_id)
        if area is None:
            missing.append(area_id)
            continue
        areas.append(area)
    if missing:
        raise ValueError(f"Unknown travel area id(s): {', '.join(missing)}")
    return areas


def run_smoke(
    *,
    areas: Iterable[TravelArea],
    style: str,
    day_count: int,
    limit: int,
    min_candidates: int,
    require_kakao: bool,
) -> list[SmokeRow]:
    provider: KakaoItineraryPlaceProvider | None = None
    mode = "catalog_fallback"
    if settings.kakao_local_enabled and settings.kakao_local_rest_api_key:
        provider = KakaoItineraryPlaceProvider(KakaoLocalClient(settings_obj=settings))
        mode = "kakao_local"
    elif require_kakao:
        raise KakaoLocalConfigurationError(
            "KAKAO_LOCAL_ENABLED=true and KAKAO_LOCAL_REST_API_KEY are required for Kakao Local smoke."
        )

    rows: list[SmokeRow] = []
    for area in areas:
        candidates = (
            _kakao_candidates(area, style=style, day_count=day_count, limit=limit, provider=provider)
            if provider is not None
            else _fallback_candidates(area, style=style, day_count=day_count)
        )
        rows.append(_row_for_candidates(area, mode=mode, candidates=candidates, min_candidates=min_candidates))
    return rows


def print_report(rows: list[SmokeRow], *, include_json: bool) -> None:
    print("| travelAreaId | area | mode | candidateCount | categories | metadata | status | sampleTitles |")
    print("| --- | --- | --- | ---: | --- | --- | --- | --- |")
    for row in rows:
        categories = ", ".join(f"{key}:{value}" for key, value in sorted(row.categoryCounts.items())) or "-"
        metadata = ", ".join(f"{key}:{value}" for key, value in sorted(row.metadata.items()))
        samples = ", ".join(row.sampleTitles)
        print(
            f"| {row.travelAreaId} | {row.area} | {row.mode} | {row.candidateCount} | "
            f"{categories} | {metadata} | {row.status} | {samples} |"
        )
    failures = [row for row in rows if row.status == "FAIL"]
    print()
    print(f"Summary: {len(rows) - len(failures)} PASS / {len(failures)} FAIL / {len(rows)} total")
    if include_json:
        print()
        print(json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Smoke Kakao Local place candidates, or catalog fallback when Kakao Local credentials are absent."
    )
    parser.add_argument("--area-id", action="append", dest="area_ids", help="Travel area id to smoke. Repeatable.")
    parser.add_argument("--style", default=DEFAULT_STYLE, help="Trip style used for candidate ranking.")
    parser.add_argument("--day-count", type=int, default=DEFAULT_DAY_COUNT, help="Trip day count used for candidate targets.")
    parser.add_argument("--limit", type=int, default=12, help="Maximum additional candidates per area.")
    parser.add_argument("--min-candidates", type=int, default=DEFAULT_MIN_CANDIDATES, help="Minimum candidates per area.")
    parser.add_argument(
        "--require-kakao",
        action="store_true",
        help="Fail with exit 2 instead of running fallback-only smoke when Kakao Local credentials are absent.",
    )
    parser.add_argument("--json", action="store_true", help="Also print JSON rows.")
    args = parser.parse_args(argv)

    try:
        areas = resolve_areas(args.area_ids or DEFAULT_AREA_IDS)
        rows = run_smoke(
            areas=areas,
            style=args.style,
            day_count=args.day_count,
            limit=args.limit,
            min_candidates=args.min_candidates,
            require_kakao=args.require_kakao,
        )
    except (ValueError, KakaoLocalConfigurationError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print_report(rows, include_json=args.json)
    return 1 if any(row.status == "FAIL" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
