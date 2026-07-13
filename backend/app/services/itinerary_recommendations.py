from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import logging
import time
from typing import Callable, Protocol

from app.data.itinerary_catalog import ITINERARY_PLACE_CATALOG

try:
    from app.data.travel_areas import get_travel_area
except ModuleNotFoundError:
    def get_travel_area(_area_id: str | None):
        return None


TIME_SLOTS = ("10:00", "14:00", "18:00")
DAYTIME_SLOT_PLAN = (
    ("10:00", "AT4", "AT"),
    ("13:00", "FD6", "FO"),
    ("16:00", "CE7", "CA"),
)
OVERNIGHT_SLOT = ("20:00", "AD5", "ST")
EXTERNAL_CATEGORY_CODES = ("AT4", "CT1", "FD6", "CE7", "AD5")
FALLBACK_MIN_DAYTIME_RATIO = 0.5
EXTERNAL_MAX_CITY_QUERIES = 2
EXTERNAL_SEARCH_TIME_BUDGET_SECONDS = 8.0
ADDITIONAL_RECOMMENDATION_CATEGORY_TARGETS = {
    "attraction": 3,
    "food": 3,
    "stay": 2,
}

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class CatalogPlace:
    region: str
    style: str
    label: str
    title: str
    meta: str
    reason: str


@dataclass(frozen=True)
class GeneratedPlace:
    day_number: int
    date: date
    time: str
    order_num: int
    region: str
    style: str
    label: str
    title: str
    meta: str
    reason: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    source_provider: str | None = None
    external_place_id: str | None = None
    category_group_code: str | None = None
    category_group_name: str | None = None
    place_url: str | None = None


@dataclass(frozen=True)
class GeneratedCourse:
    places: list[GeneratedPlace]
    recommendations: list[dict[str, object]]


@dataclass(frozen=True)
class ExternalPlaceCandidate:
    source_provider: str
    external_place_id: str
    title: str
    category_name: str | None = None
    category_group_code: str | None = None
    category_group_name: str | None = None
    phone: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    place_url: str | None = None
    city: str | None = None


class ExternalPlaceProvider(Protocol):
    def search(
        self,
        *,
        area_name: str,
        city: str,
        category_group_code: str,
    ) -> list[ExternalPlaceCandidate]:
        ...


def _load_catalog() -> list[CatalogPlace]:
    return [
        CatalogPlace(
            region=str(item["region"]).strip(),
            style=str(item["style"]).strip(),
            label=str(item["label"]),
            title=str(item["title"]),
            meta=str(item["meta"]),
            reason=str(item["reasonSeed"]),
        )
        for item in ITINERARY_PLACE_CATALOG
    ]


CATALOG = _load_catalog()


def _select_candidates(region: str, style: str, requested_count: int) -> list[CatalogPlace]:
    if requested_count <= 0:
        return []

    normalized_region = region.strip()
    normalized_style = style.strip()

    region_matches = [item for item in CATALOG if item.region == normalized_region]
    if not region_matches:
        return []

    preferred = [item for item in region_matches if item.style == normalized_style]
    fallback = [item for item in region_matches if item.style != normalized_style]
    selected: list[CatalogPlace] = []
    seen_titles: set[str] = set()

    for item in [*preferred, *fallback]:
        if item.title in seen_titles:
            continue
        selected.append(item)
        seen_titles.add(item.title)
        if len(selected) >= requested_count:
            break

    return selected


def _recommendations_for_places(places: list[GeneratedPlace]) -> list[dict[str, str]]:
    return [
        {
            "label": place.label,
            "title": place.title,
            "meta": f"Day {place.day_number} · {place.time} · {place.meta}",
            "reason": place.reason,
        }
        for place in places
    ]


def category_group_for_code(category_code: str | None) -> str:
    if category_code in {"AT4", "CT1"}:
        return "attraction"
    if category_code in {"FD6", "CE7"}:
        return "food"
    if category_code == "AD5":
        return "stay"
    return "other"


def recommendation_from_candidate(
    candidate: ExternalPlaceCandidate,
    *,
    suggested_day: int,
    region: str,
    style: str = "",
) -> dict[str, object]:
    category = candidate.category_group_name or candidate.category_name or "place"
    address = candidate.address or ""
    meta = " · ".join(part for part in (category, address) if part)
    reason = f"{region} 일정에 추가로 검토할 만한 Kakao 장소 후보입니다."
    if style:
        reason = f"{region} 일정과 {style} 취향을 함께 고려한 Kakao 장소 후보입니다."
    source_provider = candidate.source_provider
    external_place_id = candidate.external_place_id
    recommendation_id = f"{source_provider}:{external_place_id}" if source_provider and external_place_id else None
    return {
        "id": recommendation_id,
        "label": category_group_for_code(candidate.category_group_code),
        "title": candidate.title,
        "meta": meta or category,
        "reason": reason,
        "categoryGroup": category_group_for_code(candidate.category_group_code),
        "categoryCode": candidate.category_group_code,
        "categoryName": candidate.category_name,
        "phone": candidate.phone,
        "address": candidate.address,
        "latitude": candidate.latitude,
        "longitude": candidate.longitude,
        "placeUrl": candidate.place_url,
        "suggestedDay": suggested_day,
        "aiReview": f"Day {suggested_day} 동선에 추가해도 부담이 적은 후보로 검토했습니다.",
        "sourceProvider": source_provider,
        "externalPlaceId": external_place_id,
        "sourceType": "freshCandidate",
    }


def _catalog_course(
    *,
    region: str,
    style: str,
    start_date: date,
    day_count: int,
) -> GeneratedCourse:
    requested_count = max(day_count, 0) * len(TIME_SLOTS)
    candidates = _select_candidates(region, style, requested_count)
    places: list[GeneratedPlace] = []

    for index, candidate in enumerate(candidates):
        day_number = (index // len(TIME_SLOTS)) + 1
        slot_index = index % len(TIME_SLOTS)
        places.append(
            GeneratedPlace(
                day_number=day_number,
                date=start_date + timedelta(days=day_number - 1),
                time=TIME_SLOTS[slot_index],
                order_num=slot_index + 1,
                region=candidate.region,
                style=candidate.style,
                label=candidate.label,
                title=candidate.title,
                meta=candidate.meta,
                reason=candidate.reason,
            )
        )

    return GeneratedCourse(places=places, recommendations=_recommendations_for_places(places))


def _catalog_course_for_area(
    *,
    region: str,
    style: str,
    start_date: date,
    day_count: int,
    travel_area_id: str | None,
) -> GeneratedCourse:
    candidate_regions = [region]
    area = get_travel_area(travel_area_id)
    if area is not None:
        candidate_regions.extend([area.sido, *area.included_cities])

    seen: set[str] = set()
    for candidate_region in candidate_regions:
        normalized = _normalize_text(candidate_region)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        course = _catalog_course(
            region=candidate_region,
            style=style,
            start_date=start_date,
            day_count=day_count,
        )
        if course.places:
            return GeneratedCourse(
                places=[
                    GeneratedPlace(
                        day_number=place.day_number,
                        date=place.date,
                        time=place.time,
                        order_num=place.order_num,
                        region=region,
                        style=place.style,
                        label=place.label,
                        title=place.title,
                        meta=place.meta,
                        reason=place.reason,
                    )
                    for place in course.places
                ],
                recommendations=[
                    {
                        "label": item["label"],
                        "title": item["title"],
                        "meta": item["meta"],
                        "reason": item["reason"],
                    }
                    for item in course.recommendations
                ],
            )
    return GeneratedCourse(places=[], recommendations=[])


def _normalize_text(value: object) -> str:
    return "".join(str(value or "").lower().split())


def _travel_area_terms(region: str, travel_area_id: str | None) -> tuple[str, list[str]]:
    area = get_travel_area(travel_area_id)
    if area is None:
        return region, [region]
    included_cities = [term for term in area.included_cities if str(term).strip()]
    search_anchor = included_cities[0] if included_cities else area.name
    terms = [search_anchor, *included_cities[1:], area.name, *area.aliases, area.sido]
    deduped_terms: list[str] = []
    seen_terms: set[str] = set()
    for term in terms:
        normalized = _normalize_text(term)
        if not normalized or normalized in seen_terms:
            continue
        deduped_terms.append(term)
        seen_terms.add(normalized)
    return search_anchor, deduped_terms


def _travel_area_filter(region: str, travel_area_id: str | None) -> tuple[str | None, list[str]]:
    area = get_travel_area(travel_area_id)
    if area is None:
        return None, []
    local_terms = [area.name, *area.included_cities, *area.aliases]
    return area.sido, [term for term in local_terms if str(term).strip()]


def _candidate_matches_area(
    candidate: ExternalPlaceCandidate,
    *,
    required_sido: str | None,
    local_terms: list[str],
) -> bool:
    if required_sido is None and not local_terms:
        return True
    text = _normalize_text(" ".join([candidate.address or "", candidate.title, candidate.city or ""]))
    if required_sido and _normalize_text(required_sido) not in text:
        return False
    if local_terms and not any(_normalize_text(term) and _normalize_text(term) in text for term in local_terms):
        return False
    return True


def _candidate_score(
    candidate: ExternalPlaceCandidate,
    *,
    category_group_code: str,
    style: str,
    area_terms: list[str],
) -> int:
    text = _normalize_text(
        " ".join(
            [
                candidate.title,
                candidate.category_name or "",
                candidate.category_group_name or "",
                candidate.address or "",
                candidate.city or "",
            ]
        )
    )
    normalized_style = _normalize_text(style)
    score = 0
    if candidate.category_group_code == category_group_code:
        score += 100
    if any(_normalize_text(term) and _normalize_text(term) in text for term in area_terms):
        score += 70
    if normalized_style and normalized_style in text:
        score += 30
    if category_group_code == "FD6" and any(term in normalized_style for term in ("food", "맛집", "미식", "식당")):
        score += 25
    if category_group_code == "CE7" and any(term in normalized_style for term in ("cafe", "카페", "휴식")):
        score += 20
    if category_group_code in {"AT4", "CT1"} and any(term in normalized_style for term in ("nature", "photo", "sea", "자연", "사진", "바다", "체험")):
        score += 20
    if candidate.address:
        score += 5
    if candidate.place_url:
        score += 5
    return score


def _external_candidates(
    *,
    region: str,
    style: str,
    day_count: int,
    travel_area_id: str | None,
    external_provider: ExternalPlaceProvider,
) -> dict[str, list[ExternalPlaceCandidate]]:
    area_name, area_terms = _travel_area_terms(region, travel_area_id)
    required_sido, local_terms = _travel_area_filter(region, travel_area_id)
    cities = area_terms[:]
    if area_name not in cities:
        cities.insert(0, area_name)

    grouped: dict[str, list[ExternalPlaceCandidate]] = {code: [] for code in EXTERNAL_CATEGORY_CODES}
    seen: set[tuple[str, str]] = set()
    started_at = time.monotonic()
    target_counts = {
        "AT4": max(day_count, 0),
        "FD6": max(day_count, 0),
        "CE7": max(day_count, 0),
        "AD5": max(day_count - 1, 0),
    }

    def budget_exhausted() -> bool:
        return time.monotonic() - started_at >= EXTERNAL_SEARCH_TIME_BUDGET_SECONDS

    def has_enough(category_group_code: str) -> bool:
        target_code = "AT4" if category_group_code == "CT1" else category_group_code
        target = target_counts.get(target_code)
        return target is not None and len(grouped.get(target_code, [])) >= target

    for category_group_code in EXTERNAL_CATEGORY_CODES:
        if has_enough(category_group_code):
            continue
        for city in cities[:EXTERNAL_MAX_CITY_QUERIES]:
            if budget_exhausted():
                logger.info(
                    "kakao_external_search_budget_exhausted region=%s travel_area_id=%s elapsed_seconds=%.3f",
                    region,
                    travel_area_id,
                    time.monotonic() - started_at,
                )
                return grouped
            try:
                search_started_at = time.monotonic()
                candidates = external_provider.search(
                    area_name=area_name,
                    city=city,
                    category_group_code=category_group_code,
                )
                logger.info(
                    "kakao_external_search_timing category=%s city=%s elapsed_seconds=%.3f candidates=%s",
                    category_group_code,
                    city,
                    time.monotonic() - search_started_at,
                    len(candidates),
                )
            except Exception:
                continue
            for candidate in candidates:
                if not candidate.title.strip():
                    continue
                if any(marker in candidate.title for marker in ("휴업", "폐업")):
                    continue
                if not _candidate_matches_area(
                    candidate,
                    required_sido=required_sido,
                    local_terms=local_terms,
                ):
                    continue
                candidate_code = candidate.category_group_code or category_group_code
                key = (
                    candidate.external_place_id or "",
                    _normalize_text(candidate.title),
                )
                if key in seen:
                    continue
                seen.add(key)
                target_code = "AT4" if candidate_code == "CT1" else candidate_code
                if target_code not in grouped:
                    target_code = category_group_code
                grouped.setdefault(target_code, []).append(candidate)
                if has_enough(category_group_code):
                    break
            if has_enough(category_group_code):
                break

    for code, candidates in grouped.items():
        candidates.sort(
            key=lambda candidate: (
                -_candidate_score(
                    candidate,
                    category_group_code=code,
                    style=style,
                    area_terms=area_terms,
                ),
                candidate.title,
            )
        )
    return grouped


def _pop_candidate(
    candidates_by_code: dict[str, list[ExternalPlaceCandidate]],
    category_group_code: str,
    used_ids: set[str],
) -> ExternalPlaceCandidate | None:
    candidate_codes = [category_group_code]
    if category_group_code == "AT4":
        candidate_codes.append("CT1")
    for code in candidate_codes:
        candidates = candidates_by_code.get(code, [])
        while candidates:
            candidate = candidates.pop(0)
            key = candidate.external_place_id or _normalize_text(candidate.title)
            if key in used_ids:
                continue
            used_ids.add(key)
            return candidate
    return None


def _candidate_identity(candidate: ExternalPlaceCandidate) -> str:
    return candidate.external_place_id or _normalize_text(candidate.title)


def _append_unique_candidate(
    selected: list[ExternalPlaceCandidate],
    candidate: ExternalPlaceCandidate,
    used_ids: set[str],
    *,
    limit: int,
) -> bool:
    if len(selected) >= limit:
        return False
    key = _candidate_identity(candidate)
    if key in used_ids:
        return False
    used_ids.add(key)
    selected.append(candidate)
    return True


def _flatten_additional_candidates(
    candidates_by_code: dict[str, list[ExternalPlaceCandidate]],
) -> list[ExternalPlaceCandidate]:
    flattened: list[ExternalPlaceCandidate] = []
    seen: set[str] = set()
    for code in ("AT4", "CT1", "FD6", "CE7", "AD5"):
        for candidate in candidates_by_code.get(code, []):
            key = _candidate_identity(candidate)
            if key in seen:
                continue
            seen.add(key)
            flattened.append(candidate)
    return flattened


def _balanced_additional_candidates(
    candidates_by_code: dict[str, list[ExternalPlaceCandidate]],
    *,
    limit: int,
) -> list[ExternalPlaceCandidate]:
    if limit <= 0:
        return []

    all_candidates = _flatten_additional_candidates(candidates_by_code)
    candidates_by_category: dict[str, list[ExternalPlaceCandidate]] = {
        "attraction": [],
        "food": [],
        "stay": [],
        "other": [],
    }
    for candidate in all_candidates:
        candidates_by_category.setdefault(
            category_group_for_code(candidate.category_group_code),
            [],
        ).append(candidate)

    selected: list[ExternalPlaceCandidate] = []
    used_ids: set[str] = set()
    for category, target in ADDITIONAL_RECOMMENDATION_CATEGORY_TARGETS.items():
        for candidate in candidates_by_category.get(category, [])[:target]:
            _append_unique_candidate(selected, candidate, used_ids, limit=limit)

    for candidate in all_candidates:
        _append_unique_candidate(selected, candidate, used_ids, limit=limit)
        if len(selected) >= limit:
            break

    return selected


def additional_place_candidates(
    *,
    region: str,
    style: str,
    day_count: int,
    travel_area_id: str | None,
    external_provider: ExternalPlaceProvider,
    limit: int = 12,
    exclude_candidate: Callable[[ExternalPlaceCandidate], bool] | None = None,
) -> list[ExternalPlaceCandidate]:
    candidates_by_code = _external_candidates(
        region=region,
        style=style,
        day_count=day_count,
        travel_area_id=travel_area_id,
        external_provider=external_provider,
    )
    if exclude_candidate is not None:
        candidates_by_code = {
            code: [candidate for candidate in candidates if not exclude_candidate(candidate)]
            for code, candidates in candidates_by_code.items()
        }
    return _balanced_additional_candidates(candidates_by_code, limit=limit)


def _generated_from_candidate(
    *,
    candidate: ExternalPlaceCandidate,
    day_number: int,
    start_date: date,
    visit_time: str,
    order_num: int,
    region: str,
    style: str,
    label: str,
) -> GeneratedPlace:
    category = candidate.category_group_name or candidate.category_name or "place"
    address = candidate.address or ""
    meta = " · ".join(part for part in (category, address) if part)
    reason = f"{region} 여행권역과 {style} 취향에 맞는 Kakao 장소 후보입니다."
    return GeneratedPlace(
        day_number=day_number,
        date=start_date + timedelta(days=day_number - 1),
        time=visit_time,
        order_num=order_num,
        region=region,
        style=style,
        label=label,
        title=candidate.title,
        meta=meta or category,
        reason=reason,
        address=candidate.address,
        latitude=candidate.latitude,
        longitude=candidate.longitude,
        source_provider=candidate.source_provider,
        external_place_id=candidate.external_place_id,
        category_group_code=candidate.category_group_code,
        category_group_name=candidate.category_group_name,
        place_url=candidate.place_url,
    )


def _external_course(
    *,
    region: str,
    style: str,
    start_date: date,
    day_count: int,
    travel_area_id: str | None,
    external_provider: ExternalPlaceProvider,
) -> GeneratedCourse | None:
    if day_count <= 0:
        return GeneratedCourse(places=[], recommendations=[])

    candidates_by_code = _external_candidates(
        region=region,
        style=style,
        day_count=day_count,
        travel_area_id=travel_area_id,
        external_provider=external_provider,
    )
    required_daytime_count = day_count * len(DAYTIME_SLOT_PLAN)
    available_daytime_count = (
        len(candidates_by_code.get("AT4", []))
        + len(candidates_by_code.get("FD6", []))
        + len(candidates_by_code.get("CE7", []))
    )
    if available_daytime_count < max(1, int(required_daytime_count * FALLBACK_MIN_DAYTIME_RATIO)):
        return None

    used_ids: set[str] = set()
    places: list[GeneratedPlace] = []
    for day_number in range(1, day_count + 1):
        for order_num, (visit_time, category_code, label) in enumerate(DAYTIME_SLOT_PLAN, start=1):
            candidate = _pop_candidate(candidates_by_code, category_code, used_ids)
            if candidate is None and category_code == "AT4":
                candidate = _pop_candidate(candidates_by_code, "CE7", used_ids)
            if candidate is None:
                continue
            places.append(
                _generated_from_candidate(
                    candidate=candidate,
                    day_number=day_number,
                    start_date=start_date,
                    visit_time=visit_time,
                    order_num=order_num,
                    region=region,
                    style=style,
                    label=label,
                )
            )
        if day_number < day_count:
            stay_candidate = _pop_candidate(candidates_by_code, "AD5", used_ids)
            if stay_candidate is not None:
                places.append(
                    _generated_from_candidate(
                        candidate=stay_candidate,
                        day_number=day_number,
                        start_date=start_date,
                        visit_time=OVERNIGHT_SLOT[0],
                        order_num=len(DAYTIME_SLOT_PLAN) + 1,
                        region=region,
                        style=style,
                        label=OVERNIGHT_SLOT[2],
                    )
                )

    return GeneratedCourse(places=places, recommendations=_recommendations_for_places(places))


def generate_auto_course(
    *,
    region: str,
    style: str,
    start_date: date,
    day_count: int,
    travel_area_id: str | None = None,
    external_provider: ExternalPlaceProvider | None = None,
) -> GeneratedCourse:
    if external_provider is not None:
        external_course = _external_course(
            region=region,
            style=style,
            start_date=start_date,
            day_count=day_count,
            travel_area_id=travel_area_id,
            external_provider=external_provider,
        )
        if external_course is not None:
            return external_course
    return _catalog_course_for_area(
        region=region,
        style=style,
        start_date=start_date,
        day_count=day_count,
        travel_area_id=travel_area_id,
    )
