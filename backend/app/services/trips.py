from __future__ import annotations

import secrets
import re
import logging
from functools import lru_cache
import time as monotonic_time
from datetime import date, datetime, timedelta, time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core import security
from app.data import seed

DEFAULT_TRIP_REGION = "제주"
from app.models import ExternalSourceRecord, Policy, Trip, TripDay, TripInvite, TripPlace, User
from app.repositories import external_sources as external_source_repository
from app.repositories import policies as policy_repository
from app.repositories import trips as trip_repository
from app.schemas.trip import (
    CreateTripPlaceRequest,
    CreateTripRequest,
    MAX_TRIP_PARTICIPANTS,
    MoveTripPlaceRequest,
    SendInviteEmailRequest,
    UpdateTripPlaceRequest,
    UpdateTripStatusRequest,
)
from app.services import email as email_service
from app.services import itinerary_recommendations
from app.services import local_half_trip_display
from app.services import stay_discount_aliases
from app.services.kakao_local import KakaoLocalClient, build_kakao_local_client
from app.services.policy_semantics import (
    benefit_display_amount,
    is_public_policy,
    policy_status,
)

try:
    from app.data.travel_areas import get_travel_area, list_travel_areas
except ModuleNotFoundError:
    def get_travel_area(_area_id: str | None):
        return None

    def list_travel_areas():
        return ()


NUMERIC_TRIP_ID_PATTERN = re.compile(r"^[1-9][0-9]*$")
TRIP_EDIT_ROLES = {"owner", "editor"}
NATIONWIDE_REGION = "\uc804\uad6d"
MIN_RECOMMENDED_POLICY_SCORE = 40
CONDITIONAL_POLICY_KEYWORDS = (
    "\ub2e4\uc790\ub140",
    "\uc7a5\uc560\uc778",
    "\ud720\uccb4\uc5b4",
    "\uc784\uc0b0\ubd80",
    "\uccad\ub144",
    "\ud55c\ubd80\ubaa8",
)

logger = logging.getLogger("uvicorn.error")


class KakaoItineraryPlaceProvider:
    def __init__(self, client: KakaoLocalClient) -> None:
        self._client = client

    def _queries_for_code(
        self,
        *,
        area_name: str,
        city: str,
        category_group_code: str,
    ) -> list[str]:
        location = city or area_name
        keyword_by_code = {
            "AT4": ("가볼만한곳", "관광명소"),
            "CT1": ("문화시설", "박물관"),
            "FD6": ("맛집", "식당"),
            "CE7": ("카페", "디저트"),
            "AD5": ("숙소", "호텔"),
        }
        keywords = keyword_by_code.get(category_group_code, ("",))
        return [f"{location} {keyword}".strip() for keyword in keywords]

    def search(
        self,
        *,
        area_name: str,
        city: str,
        category_group_code: str,
    ) -> list[itinerary_recommendations.ExternalPlaceCandidate]:
        candidates: list[itinerary_recommendations.ExternalPlaceCandidate] = []
        seen_ids: set[str] = set()
        for query in self._queries_for_code(
            area_name=area_name,
            city=city,
            category_group_code=category_group_code,
        ):
            started_at = monotonic_time.monotonic()
            places = self._client.search_keyword(
                query=query,
                category_group_code=category_group_code,
            )
            logger.info(
                "kakao_local_keyword_timing category=%s city=%s query=%s elapsed_seconds=%.3f places=%s",
                category_group_code,
                city,
                query,
                monotonic_time.monotonic() - started_at,
                len(places),
            )
            for place in places:
                if place.external_place_id in seen_ids:
                    continue
                seen_ids.add(place.external_place_id)
                candidates.append(
                    itinerary_recommendations.ExternalPlaceCandidate(
                        source_provider="kakao_local",
                        external_place_id=place.external_place_id,
                        title=place.name,
                        category_name=place.category_name,
                        category_group_code=place.category_group_code or category_group_code,
                        category_group_name=place.category_group_name,
                        phone=place.phone,
                        address=place.address,
                        latitude=place.latitude,
                        longitude=place.longitude,
                        place_url=place.place_url,
                        city=city,
                    )
                )
        return candidates


def _build_external_place_provider() -> KakaoItineraryPlaceProvider | None:
    if not settings.kakao_local_enabled:
        return None
    try:
        return KakaoItineraryPlaceProvider(KakaoLocalClient(settings_obj=settings))
    except Exception:
        logger.warning("kakao_local_provider_bootstrap_failed", exc_info=True)
        return None


class TripServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _parse_time(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def _parse_optional_time(value: str | None) -> time | None:
    if value is None or value.strip() == "":
        return None
    try:
        return _parse_time(value.strip())
    except ValueError as exc:
        raise TripServiceError(422, "Invalid visit time") from exc


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return f"{value.isoformat()}Z"


def _format_dates(start_date: date, end_date: date) -> str:
    return f"{start_date.year}.{start_date.month:02d}.{start_date.day:02d} - {end_date.month:02d}.{end_date.day:02d}"


def _format_saving(value: int) -> str:
    if value <= 0:
        return "0원"
    if value % 10000 == 0:
        return f"{value // 10000}만원"
    return f"{value:,}원"


def _policy_saving(trip: Trip) -> int:
    total = 0
    for link in trip.policies:
        if link.policy is not None and link.policy.benefit_amount:
            total += int(link.policy.benefit_amount)
    return total


def _trip_policy_amount(policy: Policy) -> str:
    detail_amount = benefit_display_amount(
        benefit_detail=policy.benefit_detail,
        benefit_amount=None,
    )
    return detail_amount or _format_saving(policy.benefit_amount or 0)


def _linked_policies(
    trip: Trip,
    alias_overrides: dict[str, stay_discount_aliases.StayDiscountAliasArea] | None = None,
) -> list[dict[str, str]]:
    alias_overrides = alias_overrides or {}
    linked: list[dict[str, str]] = []
    for link in sorted(trip.policies, key=lambda item: item.id or 0):
        policy = link.policy
        if policy is None:
            continue
        slug = policy.slug or str(policy.id)
        alias_area = alias_overrides.get(slug)
        region = policy.region or ""
        title = local_half_trip_display.policy_title(policy.title, policy.source_category)
        if alias_area is not None:
            slug = alias_area.slug
            region = alias_area.sido
            title = stay_discount_aliases.alias_title(policy.title, alias_area)
        amount = _trip_policy_amount(policy)
        linked.append(
            {
                "slug": slug,
                "title": title,
                "amount": amount,
                "region": region,
                "status": policy_status(policy),
            }
        )
    return linked


def _policy_to_trip_policy_candidate(
    policy: Policy,
    external_record: ExternalSourceRecord | None = None,
) -> dict[str, object]:
    slug = policy.slug or str(policy.id)
    amount = _trip_policy_amount(policy)
    city = external_record.city if external_record is not None else None
    title = local_half_trip_display.policy_title(policy.title, policy.source_category, city)
    local_terms = _candidate_local_terms(
        title=title,
        region=policy.region,
        city=city,
        source_category=policy.source_category,
    )
    return {
        "slug": slug,
        "title": title,
        "amount": amount,
        "region": policy.region or "",
        "sido": policy.region or "",
        "localTerms": local_terms,
        "benefitAmount": policy.benefit_amount or 0,
        "startDate": policy.start_date,
        "endDate": policy.end_date,
        "sourceCategory": policy.source_category or "",
        "policyType": policy.policy_type or "",
        "verificationStatus": policy.verification_status or "",
        "externalSourceRecordId": policy.external_source_record_id,
        "sortId": policy.id or 0,
    }


def _stay_alias_to_trip_policy_candidate(
    policy: Policy,
    alias_area: stay_discount_aliases.StayDiscountAliasArea,
) -> dict[str, object]:
    amount = _trip_policy_amount(policy)
    title = stay_discount_aliases.alias_title(policy.title, alias_area)
    local_terms = _candidate_local_terms(
        title=title,
        region=alias_area.sido,
        city=alias_area.city,
        source_category=policy.source_category,
    )
    return {
        "slug": alias_area.slug,
        "canonicalSlug": policy.slug or str(policy.id),
        "canonicalPolicyId": policy.id,
        "title": title,
        "amount": amount,
        "region": alias_area.sido,
        "sido": alias_area.sido,
        "localTerms": local_terms,
        "benefitAmount": policy.benefit_amount or 0,
        "startDate": policy.start_date,
        "endDate": policy.end_date,
        "sourceCategory": policy.source_category or "",
        "policyType": policy.policy_type or "",
        "verificationStatus": policy.verification_status or "",
        "externalSourceRecordId": policy.external_source_record_id,
        "sortId": policy.id or 0,
    }


def _external_source_record_to_trip_policy_candidate(record: ExternalSourceRecord) -> dict[str, object]:
    title = local_half_trip_display.policy_title(record.title, record.source_category, record.city)
    local_terms = _candidate_local_terms(
        title=title,
        region=record.region,
        city=record.city,
        source_category=record.source_category,
    )
    return {
        "slug": f"{external_source_repository.EXTERNAL_POLICY_SLUG_PREFIX}{record.id}",
        "title": title,
        "amount": record.benefit_value_text or record.benefit_text,
        "region": record.region or (NATIONWIDE_REGION if record.is_nationwide else ""),
        "sido": record.region or "",
        "localTerms": local_terms,
        "benefitAmount": record.extracted_amount_krw or 0,
        "startDate": record.start_date,
        "endDate": record.end_date,
        "sourceCategory": record.source_category or "",
        "policyType": "",
        "tags": record.tags or [],
        "styles": record.inferred_travel_styles or [],
        "sortId": record.id or 0,
    }


def _normalized_text(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def _split_region_terms(value: str | None) -> list[str]:
    return [
        term.strip()
        for term in re.split(r"[\u00b7,/|()\-\s]+", value or "")
        if term.strip()
    ]


def _unique_terms(values: list[str]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalized_text(value)
        if not normalized or normalized == _normalized_text(NATIONWIDE_REGION) or normalized in seen:
            continue
        seen.add(normalized)
        terms.append(value)
    return terms


def _term_variants(value: str | None) -> list[str]:
    value = (value or "").strip()
    if not value:
        return []
    variants = [value]
    if len(value) > 1 and value.endswith(("시", "군")):
        variants.append(value[:-1])
    return _unique_terms(variants)


@lru_cache(maxsize=1)
def _known_municipal_terms() -> tuple[str, ...]:
    values: list[str] = []
    for area in list_travel_areas():
        for city in area.included_cities:
            values.extend(_term_variants(city))
        for alias in area.aliases:
            if alias.endswith(("시", "군", "구")):
                values.extend(_term_variants(alias))
    return tuple(_unique_terms(values))


def _candidate_local_terms(
    *,
    title: str,
    region: str | None,
    city: str | None,
    source_category: str | None,
) -> list[str]:
    values: list[str] = []
    values.extend(_term_variants(city))
    if source_category == local_half_trip_display.SOURCE_CATEGORY:
        values.extend(_term_variants(local_half_trip_display.city_from_title(title)))
    if title.startswith("[") and "]" in title:
        values.extend(_term_variants(title[1 : title.index("]")]))
    title_text = _normalized_text(title)
    for term in _known_municipal_terms():
        if _normalized_text(term) in title_text:
            values.extend(_term_variants(term))
    region_terms = _split_region_terms(region)
    if len(region_terms) >= 2:
        values.extend(_term_variants(region_terms[-1]))
    return _unique_terms(values)


def _trip_policy_match_terms(trip: Trip) -> tuple[list[str], str | None]:
    area = get_travel_area(trip.travel_area_id)
    values: list[str] = []
    area_sido = None
    if area is not None:
        area_sido = area.sido
        values.extend([area.sido, area.name])
        values.extend(area.included_cities)
        values.extend(area.aliases)
    values.extend(_split_region_terms(trip.region))
    if trip.region:
        values.append(trip.region)
    return _unique_terms(values), area_sido


def _trip_local_match_terms(trip: Trip) -> tuple[list[str], str | None, bool]:
    area = get_travel_area(trip.travel_area_id)
    values: list[str] = []
    area_sido = None
    is_whole_sido_area = False
    if area is not None:
        area_sido = area.sido
        is_whole_sido_area = any(
            _normalized_text(city) == _normalized_text(area.sido)
            for city in area.included_cities
        )
        for city in area.included_cities:
            values.extend(_term_variants(city))
    else:
        for term in _split_region_terms(trip.region):
            values.extend(_term_variants(term))
    return _unique_terms(values), area_sido, is_whole_sido_area


def _candidate_sido(candidate: dict[str, object]) -> str:
    value = str(candidate.get("sido") or candidate.get("region") or "").strip()
    if _normalized_text(value) == _normalized_text(NATIONWIDE_REGION):
        return ""
    return value


def _candidate_has_explicit_locality(candidate: dict[str, object]) -> bool:
    terms = candidate.get("localTerms")
    return isinstance(terms, list) and any(_normalized_text(term) for term in terms)


def _candidate_matches_trip_locality(candidate: dict[str, object], trip: Trip) -> bool:
    local_terms, area_sido, is_whole_sido_area = _trip_local_match_terms(trip)
    if not local_terms and not area_sido:
        return True

    candidate_sido = _normalized_text(_candidate_sido(candidate))
    normalized_area_sido = _normalized_text(area_sido)
    candidate_local_terms = (
        {
            normalized
            for term in candidate.get("localTerms", [])
            if (normalized := _normalized_text(term))
        }
        if isinstance(candidate.get("localTerms"), list)
        else set()
    )
    normalized_local_terms = {
        normalized for term in local_terms if (normalized := _normalized_text(term))
    }

    if is_whole_sido_area:
        return (
            bool(normalized_area_sido)
            and candidate_sido == normalized_area_sido
            and _candidate_has_explicit_locality(candidate)
        )

    if not candidate_local_terms:
        return False
    if normalized_area_sido and candidate_sido and candidate_sido != normalized_area_sido:
        return False
    return bool(candidate_local_terms & normalized_local_terms)


def _known_destination_terms() -> list[str]:
    values: list[str] = []
    for area in list_travel_areas():
        values.extend([area.sido, area.name])
        values.extend(area.included_cities)
        values.extend(area.aliases)
    return _unique_terms(values)


def _candidate_policy_text(candidate: dict[str, object]) -> str:
    tags = candidate.get("tags")
    styles = candidate.get("styles")
    return _normalized_text(
        " ".join(
            [
                str(candidate.get("title") or ""),
                str(candidate.get("amount") or ""),
                str(candidate.get("region") or ""),
                str(candidate.get("sourceCategory") or ""),
                str(candidate.get("policyType") or ""),
                " ".join(str(tag) for tag in tags if tag) if isinstance(tags, list) else "",
                " ".join(str(style) for style in styles if style) if isinstance(styles, list) else "",
            ]
        )
    )


def _trip_policy_candidate_score(
    candidate: dict[str, object],
    *,
    trip: Trip,
    match_terms: list[str],
    area_sido: str | None,
    known_destination_terms: list[str],
) -> int:
    score = 0
    candidate_region = _normalized_text(candidate.get("region"))
    candidate_text = _candidate_policy_text(candidate)
    normalized_terms = {normalized for term in match_terms if (normalized := _normalized_text(term))}
    normalized_sido = _normalized_text(area_sido)

    if normalized_sido and candidate_region == normalized_sido:
        score += 120
    elif candidate_region and candidate_region in normalized_terms:
        score += 120
    elif candidate_region == _normalized_text(NATIONWIDE_REGION):
        score += 40

    if any(term and term in candidate_text for term in normalized_terms):
        score += 90

    conflicting_terms = [
        normalized
        for term in known_destination_terms
        if (normalized := _normalized_text(term)) and normalized not in normalized_terms
    ]
    if any(term in candidate_text for term in conflicting_terms):
        score -= 120

    if any(_normalized_text(keyword) in candidate_text for keyword in CONDITIONAL_POLICY_KEYWORDS):
        score -= 80

    score += _trip_policy_date_score(candidate, trip)
    score += _trip_policy_category_score(candidate, trip)
    score += _trip_policy_style_score(candidate, trip)

    if candidate.get("benefitAmount"):
        score += 10

    return score


def _is_expired_external_trip_policy_candidate(candidate: dict[str, object], trip: Trip) -> bool:
    end_date = candidate.get("endDate")
    return bool(candidate.get("externalSourceRecordId")) and isinstance(end_date, date) and end_date < trip.start_date


def _trip_policy_date_score(candidate: dict[str, object], trip: Trip) -> int:
    start_date = candidate.get("startDate")
    end_date = candidate.get("endDate")
    if not isinstance(start_date, date) and not isinstance(end_date, date):
        return 0
    candidate_start = start_date if isinstance(start_date, date) else date.min
    candidate_end = end_date if isinstance(end_date, date) else date.max
    if candidate_start <= trip.end_date and candidate_end >= trip.start_date:
        return 60
    if candidate_end < trip.start_date:
        return -40
    if candidate_start > trip.end_date:
        return -20
    return 0


def _trip_policy_category_score(candidate: dict[str, object], trip: Trip) -> int:
    text = _candidate_policy_text(candidate)
    source_category = str(candidate.get("sourceCategory") or "")
    policy_type = str(candidate.get("policyType") or "")
    trip_days = max((trip.end_date - trip.start_date).days + 1, 1)
    score = 0
    if source_category == "stay_discount" or policy_type == "숙박" or "숙박" in text:
        score += 55 if trip_days >= 2 else 15
    if source_category == "traffic_benefit" or policy_type == "교통":
        score += 15
    if source_category in {"local_half_trip", "regional_benefit"} or policy_type == "지역할인":
        score += 10
    return score


def _trip_policy_style_score(candidate: dict[str, object], trip: Trip) -> int:
    trip_text = _normalized_text(
        " ".join(
            [
                trip.title or "",
                trip.description or "",
                *(place.place_name or "" for day in trip.days for place in day.places),
                *(place.category_group_name or "" for day in trip.days for place in day.places),
            ]
        )
    )
    candidate_text = _candidate_policy_text(candidate)
    matched = 0
    style_keywords = {
        "휴식": ("휴식", "힐링", "숙박", "호텔", "리조트"),
        "맛집": ("맛집", "식당", "음식", "카페"),
        "체험": ("체험", "투어", "관광", "박물관"),
        "자연": ("자연", "바다", "해변", "숲"),
        "사진": ("사진", "포토", "전망"),
    }
    for keywords in style_keywords.values():
        if any(_normalized_text(keyword) in trip_text for keyword in keywords) and any(
            _normalized_text(keyword) in candidate_text for keyword in keywords
        ):
            matched += 1
    return min(matched * 15, 30)


def _recommended_policies(trip: Trip, candidates: list[dict[str, object]] | None = None, limit: int = 3) -> list[dict[str, str]]:
    if not candidates:
        return []

    linked_slugs = {
        link.policy.slug or str(link.policy.id)
        for link in trip.policies
        if link.policy is not None
    }
    linked_policy_ids = {
        link.policy.id
        for link in trip.policies
        if link.policy is not None and link.policy.id is not None
    }
    available_candidates = [
        candidate
        for candidate in candidates
        if str(candidate["slug"]) not in linked_slugs
        and str(candidate.get("canonicalSlug") or "") not in linked_slugs
        and candidate.get("canonicalPolicyId") not in linked_policy_ids
        and not _is_expired_external_trip_policy_candidate(candidate, trip)
    ]
    trip_region = (trip.region or "").strip()
    if trip.travel_area_id:
        available_candidates = [
            candidate
            for candidate in available_candidates
            if _candidate_matches_trip_locality(candidate, trip)
        ]
    else:
        region_candidates = [
            candidate
            for candidate in available_candidates
            if trip_region and str(candidate["region"]).startswith(trip_region)
        ]
        if region_candidates:
            available_candidates = region_candidates
    match_terms, area_sido = _trip_policy_match_terms(trip)
    known_destination_terms = _known_destination_terms()
    scored_candidates = [
        (
            _trip_policy_candidate_score(
                candidate,
                trip=trip,
                match_terms=match_terms,
                area_sido=area_sido,
                known_destination_terms=known_destination_terms,
            ),
            candidate,
        )
        for candidate in available_candidates
    ]
    if trip.travel_area_id:
        scored_candidates = [
            (score, candidate)
            for score, candidate in scored_candidates
            if score >= MIN_RECOMMENDED_POLICY_SCORE
        ]
    scored_candidates.sort(
        key=lambda scored_candidate: (
            -scored_candidate[0],
            scored_candidate[1]["endDate"] or date.max,
            scored_candidate[1]["sortId"],
        )
    )
    return [
        {
            "slug": str(candidate["slug"]),
            "title": str(candidate["title"]),
            "amount": str(candidate["amount"] or ""),
            "region": str(candidate["region"] or ""),
        }
        for _score, candidate in scored_candidates[:limit]
    ]


def _list_recommended_policy_candidates(db: Session) -> list[dict[str, object]]:
    try:
        policies = policy_repository.list_policies(db)
    except AttributeError:
        if not hasattr(db, "scalars"):
            return []
        raise
    candidates: list[dict[str, object]] = []
    for policy in policies:
        if (
            policy.external_source_record_id is not None
            and policy.verification_status
            and policy.verification_status != "fresh"
        ):
            continue
        if stay_discount_aliases.is_stay_discount_canonical_policy(policy):
            alias_areas = stay_discount_aliases.alias_areas_for_policy(db, policy)
            if alias_areas:
                candidates.extend(_stay_alias_to_trip_policy_candidate(policy, area) for area in alias_areas)
            continue
        external_record = (
            external_source_repository.get_external_source_record_by_id(
                db,
                policy.external_source_record_id,
            )
            if policy.external_source_record_id is not None
            else None
        )
        candidates.append(_policy_to_trip_policy_candidate(policy, external_record))
    return candidates


def _resolve_policy_for_request_slug(
    db: Session,
    policy_slug: str,
) -> tuple[Policy | None, stay_discount_aliases.StayDiscountAliasArea | None]:
    alias_resolution = stay_discount_aliases.resolve_stay_discount_alias_slug(db, policy_slug)
    if alias_resolution is not None:
        policy = alias_resolution.canonical_policy
        if not is_public_policy(policy):
            return None, None
        return policy, alias_resolution.alias_area
    return policy_repository.get_policy_by_slug(db, policy_slug), None


def _trip_role_for_user(trip: Trip, user: User | None) -> str:
    if user is None or trip.owner_id == user.id:
        return "owner"
    for membership in trip.members:
        if membership.user_id == user.id:
            return membership.role if membership.role in {"owner", "editor", "viewer"} else "viewer"
    return "viewer"


def _actual_participant_user_ids(trip: Trip | None) -> set[int]:
    if trip is None:
        return set()
    user_ids = {int(trip.owner_id)}
    for membership in trip.members:
        if membership.user_id is not None:
            user_ids.add(int(membership.user_id))
    return user_ids


def _require_trip_editor(trip: Trip, user: User) -> None:
    if _trip_role_for_user(trip, user) not in TRIP_EDIT_ROLES:
        raise TripServiceError(403, "Trip edit permission required")


def trip_to_api(
    trip: Trip,
    user: User | None = None,
    recommended_policies: list[dict[str, object]] | None = None,
    linked_policy_alias_overrides: dict[str, stay_discount_aliases.StayDiscountAliasArea] | None = None,
) -> dict[str, object]:
    people: list[str] = []
    seen_people: set[str] = set()
    if trip.owner is not None:
        people.append(trip.owner.nickname)
        seen_people.add(trip.owner.nickname)

    members = sorted(
        trip.members,
        key=lambda membership: (membership.role != "owner", membership.id or 0),
    )
    for membership in members:
        if membership.user is None or membership.user.nickname in seen_people:
            continue
        people.append(membership.user.nickname)
        seen_people.add(membership.user.nickname)

    days: dict[int, list[dict[str, str]]] = {}
    for trip_day in sorted(trip.days, key=lambda day: day.day_number):
        places = sorted(
            trip_day.places,
            key=lambda place: (place.order_num is None, place.order_num or 0, place.id or 0),
        )
        days[trip_day.day_number] = [
            {
                "id": str(place.id) if place.id is not None else None,
                "time": place.visit_time.strftime("%H:%M") if place.visit_time else "",
                "label": place.place_name,
                "meta": place.memo or place.address or "",
                "address": place.address,
                "latitude": float(place.latitude) if place.latitude is not None else None,
                "longitude": float(place.longitude) if place.longitude is not None else None,
                "category": getattr(place, "category_group_name", None),
                "categoryCode": getattr(place, "category_group_code", None),
                "placeUrl": getattr(place, "place_url", None),
                "sourceProvider": getattr(place, "source_provider", None),
                "externalPlaceId": getattr(place, "external_place_id", None),
            }
            for place in places
        ]

    return {
        "id": str(trip.id),
        "title": trip.title,
        "status": trip.status or "confirmed",
        "revision": trip.revision or 1,
        "travelAreaId": trip.travel_area_id,
        "dates": _format_dates(trip.start_date, trip.end_date),
        "people": people,
        "participantCount": trip.participant_count or max(1, len(people)),
        "expectedSaving": _format_saving(_policy_saving(trip)),
        "linkedPolicies": _linked_policies(trip, linked_policy_alias_overrides),
        "recommendedPolicies": _recommended_policies(trip, recommended_policies),
        "days": days,
        "currentUserRole": _trip_role_for_user(trip, user),
    }


def _resolve_trip(db: Session, trip_handle: str, user: User) -> Trip | None:
    if NUMERIC_TRIP_ID_PATTERN.fullmatch(trip_handle):
        return trip_repository.get_accessible_trip_by_id(db, int(trip_handle), user.id)
    return None


def _resolve_editable_trip(db: Session, trip_handle: str, user: User) -> Trip | None:
    trip = _resolve_trip(db, trip_handle, user)
    if trip is None:
        return None
    _require_trip_editor(trip, user)
    return trip


def _resolve_required_trip(db: Session, trip_handle: str, user: User) -> Trip:
    trip = _resolve_trip(db, trip_handle, user)
    if trip is None:
        raise TripServiceError(404, "Trip not found")
    return trip


def _refresh_trip_payload(db: Session, trip_id: int, user: User) -> dict[str, object]:
    if hasattr(db, "expire_all"):
        db.expire_all()
    trip = trip_repository.get_accessible_trip_by_id(db, trip_id, user.id)
    if trip is None:
        raise TripServiceError(404, "Trip not found")
    return trip_to_api(trip, user, _list_recommended_policy_candidates(db))


def _bump_trip_revision_or_conflict(db: Session, trip: Trip, expected_revision: int) -> None:
    if not trip_repository.bump_trip_revision_if_current(
        db,
        trip_id=trip.id,
        expected_revision=expected_revision,
    ):
        raise TripServiceError(409, "Trip has changed. Refresh before saving.")
    trip.revision = expected_revision + 1


def _find_trip_day(trip: Trip, day_number: int) -> TripDay:
    for trip_day in trip.days:
        if trip_day.day_number == day_number:
            return trip_day
    raise TripServiceError(404, "Trip not found")


def _find_trip_place(trip: Trip, place_id: int) -> TripPlace:
    for trip_day in trip.days:
        for place in trip_day.places:
            if place.id == place_id:
                return place
    raise TripServiceError(404, "Trip not found")


def _find_trip_day_for_place(trip: Trip, place: TripPlace) -> TripDay:
    for trip_day in trip.days:
        for candidate in trip_day.places:
            if candidate is place or candidate.id == place.id:
                return trip_day
    raise TripServiceError(404, "Trip not found")


def _ordered_places(trip_day: TripDay) -> list[TripPlace]:
    return sorted(
        trip_day.places,
        key=lambda place: (place.order_num is None, place.order_num or 0, place.id or 0),
    )


def list_trips(db: Session, user: User) -> list[dict[str, object]]:
    recommended_policy_candidates = _list_recommended_policy_candidates(db)
    return [trip_to_api(trip, user, recommended_policy_candidates) for trip in trip_repository.list_accessible_trips(db, user.id)]


def get_trip(trip_handle: str, db: Session, user: User) -> dict[str, object] | None:
    trip = _resolve_trip(db, trip_handle, user)
    if trip is None:
        return None
    return trip_to_api(trip, user, _list_recommended_policy_candidates(db))


def delete_trip(trip_handle: str, db: Session, user: User) -> dict[str, object] | None:
    if not NUMERIC_TRIP_ID_PATTERN.fullmatch(trip_handle):
        return None

    trip = trip_repository.get_owned_trip_by_id(db, int(trip_handle), user.id)
    if trip is None:
        return None

    trip_id = int(trip.id)
    trip_repository.detach_recommendations_from_trip(db, trip_id=trip_id)
    trip_repository.delete_trip(db, trip)
    db.commit()
    return {"tripId": str(trip_id), "deleted": True}


def create_trip(
    db: Session,
    user: User,
    payload: CreateTripRequest | None = None,
) -> dict[str, object]:
    payload = (payload or CreateTripRequest()).model_dump()
    if payload.get("description") is None and payload.get("style") is not None:
        payload["description"] = payload["style"]
    travel_area_id = str(payload.get("travelAreaId") or "").strip() or None
    travel_area = get_travel_area(travel_area_id)
    if travel_area_id and travel_area is None:
        raise TripServiceError(400, "Travel area not found")
    region = str(travel_area.name if travel_area else payload.get("region") or DEFAULT_TRIP_REGION)
    start_date_value = payload.get("startDate")
    end_date_value = payload.get("endDate")
    if isinstance(start_date_value, date) and isinstance(end_date_value, date):
        start_date = start_date_value
        end_date = end_date_value
        duration_days = (end_date - start_date).days + 1
    else:
        duration_days = int(payload.get("durationDays") or 3)
        start_date = date(2026, 6, 15)
        end_date = start_date + timedelta(days=duration_days - 1)
    title = str(payload.get("title") or f"{region} {duration_days}일 여행")
    participant_count = int(payload.get("participantCount") or 1)

    trip = trip_repository.create_trip(
        db,
        owner_id=user.id,
        title=title,
        start_date=start_date,
        end_date=end_date,
        status="draft",
        region=region,
        travel_area_id=travel_area.id if travel_area else None,
        participant_count=participant_count,
        description=str(payload.get("description") or seed.PROFILE["style"]),
    )
    trip_repository.add_trip_member(db, trip_id=trip.id, user_id=user.id, role="owner")

    for day_number in range(1, duration_days + 1):
        trip_repository.add_trip_day(
            db,
            trip_id=trip.id,
            day_number=day_number,
            date_value=start_date + timedelta(days=day_number - 1),
        )

    _ensure_invite(db, trip, user)
    if payload.get("policySlug"):
        policy_slug = str(payload["policySlug"])
        policy, alias_area = _resolve_policy_for_request_slug(db, policy_slug)
        if policy is None:
            raise TripServiceError(404, "Policy not found")
        trip_repository.add_trip_policy(db, trip_id=trip.id, policy_id=policy.id)
    else:
        alias_area = None
        policy = None
    db.commit()

    created = trip_repository.get_accessible_trip_by_id(db, trip.id, user.id)
    if created is None:
        raise TripServiceError(404, "Trip not found")
    alias_overrides: dict[str, stay_discount_aliases.StayDiscountAliasArea] | None = None
    if policy is not None and alias_area is not None:
        alias_overrides = {policy.slug or str(policy.id): alias_area}
    return trip_to_api(created, user, _list_recommended_policy_candidates(db), alias_overrides)


def add_policy_to_trip(
    db: Session,
    user: User,
    trip_handle: str,
    policy_slug: str,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    policy, _alias_area = _resolve_policy_for_request_slug(db, policy_slug)
    if policy is None:
        raise TripServiceError(404, "Policy not found")

    existing = trip_repository.get_trip_policy(db, trip_id=trip.id, policy_id=policy.id)
    if existing is None:
        trip_repository.add_trip_policy(db, trip_id=trip.id, policy_id=policy.id)
        db.commit()

    return {"tripId": str(trip.id), "policyId": policy_slug, "added": True}


def remove_policy_from_trip(
    db: Session,
    user: User,
    trip_handle: str,
    policy_slug: str,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    policy, _alias_area = _resolve_policy_for_request_slug(db, policy_slug)
    if policy is None:
        raise TripServiceError(404, "Policy not found")

    existing = trip_repository.get_trip_policy(db, trip_id=trip.id, policy_id=policy.id)
    if existing is not None:
        trip_repository.remove_trip_policy(db, existing)
        db.commit()

    return {"tripId": str(trip.id), "policyId": policy_slug, "added": False}


def update_trip_status(
    db: Session,
    user: User,
    trip_handle: str,
    payload: UpdateTripStatusRequest,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    trip.status = payload.status
    db.commit()
    return _refresh_trip_payload(db, trip.id, user)


def add_place_to_trip_day(
    db: Session,
    user: User,
    trip_handle: str,
    day_number: int,
    payload: CreateTripPlaceRequest,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    trip_day = _find_trip_day(trip, day_number)
    label = payload.label.strip()
    if not label:
        raise TripServiceError(422, "Place label is required")
    _bump_trip_revision_or_conflict(db, trip, payload.expectedRevision)

    next_order = max((place.order_num or 0 for place in trip_day.places), default=0) + 1
    trip_repository.add_trip_place(
        db,
        trip_day_id=trip_day.id,
        place_name=label,
        visit_time=_parse_optional_time(payload.time),
        order_num=next_order,
        memo=payload.meta.strip() if payload.meta is not None else None,
        address=payload.address.strip() if payload.address else None,
        latitude=payload.latitude,
        longitude=payload.longitude,
        category_group_code=payload.categoryCode,
        category_group_name=payload.category,
        place_url=payload.placeUrl,
        source_provider=payload.sourceProvider,
        external_place_id=payload.externalPlaceId,
    )
    db.commit()
    return _refresh_trip_payload(db, trip.id, user)


def update_trip_place(
    db: Session,
    user: User,
    trip_handle: str,
    place_id: int,
    payload: UpdateTripPlaceRequest,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    place = _find_trip_place(trip, place_id)
    values = payload.model_dump(exclude_unset=True, exclude={"expectedRevision"})

    if "label" in values:
        label = (values["label"] or "").strip()
        if not label:
            raise TripServiceError(422, "Place label is required")
    _bump_trip_revision_or_conflict(db, trip, payload.expectedRevision)

    if "label" in values:
        place.place_name = label
    if "time" in values:
        place.visit_time = _parse_optional_time(values["time"])
    if "meta" in values:
        place.memo = values["meta"].strip() if values["meta"] is not None else None

    db.commit()
    return _refresh_trip_payload(db, trip.id, user)


def move_trip_place(
    db: Session,
    user: User,
    trip_handle: str,
    place_id: int,
    payload: MoveTripPlaceRequest,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    place = _find_trip_place(trip, place_id)
    source_day = _find_trip_day_for_place(trip, place)
    target_day = _find_trip_day(trip, payload.dayNumber)

    source_places_without_place = [
        candidate for candidate in _ordered_places(source_day) if candidate.id != place.id
    ]
    same_day = source_day.id == target_day.id
    target_places = source_places_without_place if same_day else _ordered_places(target_day)
    max_position = len(target_places) + 1
    if payload.position > max_position:
        raise TripServiceError(422, "Invalid place position")
    _bump_trip_revision_or_conflict(db, trip, payload.expectedRevision)

    target_places.insert(payload.position - 1, place)
    if same_day:
        trip_repository.reorder_trip_day_places(source_day, target_places)
    else:
        trip_repository.reorder_trip_day_places(source_day, source_places_without_place)
        trip_repository.reorder_trip_day_places(target_day, target_places)

    db.commit()
    return _refresh_trip_payload(db, trip.id, user)


def delete_trip_place(
    db: Session,
    user: User,
    trip_handle: str,
    place_id: int,
    expected_revision: int,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    place = _find_trip_place(trip, place_id)
    _bump_trip_revision_or_conflict(db, trip, expected_revision)
    trip_repository.delete_trip_place(db, place)
    db.commit()
    return _refresh_trip_payload(db, trip.id, user)


def _recommendation_items(value: Any, *, source_type: str = "savedSummary") -> list[dict[str, object]]:
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, dict):
        maybe_items = value.get("items")
        raw_items = maybe_items if isinstance(maybe_items, list) else [value]
    else:
        raw_items = []

    optional_keys = (
        "id",
        "categoryGroup",
        "categoryCode",
        "categoryName",
        "phone",
        "address",
        "latitude",
        "longitude",
        "placeUrl",
        "suggestedDay",
        "aiReview",
        "sourceProvider",
        "externalPlaceId",
        "sourceType",
    )
    items: list[dict[str, object]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        mapped: dict[str, object] = {
            "label": str(item.get("label") or ""),
            "title": str(item.get("title") or ""),
            "meta": str(item.get("meta") or ""),
            "reason": str(item.get("reason") or ""),
        }
        for key in optional_keys:
            if key in item:
                mapped[key] = item.get(key)
        mapped.setdefault("sourceType", source_type)
        items.append(mapped)
    return items


def _existing_place_keys(trip: Trip) -> tuple[set[tuple[str, str]], set[str], set[str]]:
    provider_ids: set[tuple[str, str]] = set()
    external_ids: set[str] = set()
    titles: set[str] = set()
    for trip_day in trip.days:
        for place in trip_day.places:
            source_provider = getattr(place, "source_provider", None)
            external_place_id = getattr(place, "external_place_id", None)
            if source_provider and external_place_id:
                provider_ids.add((source_provider, external_place_id))
            if external_place_id:
                external_ids.add(external_place_id)
            normalized_title = _normalized_text(place.place_name)
            if normalized_title:
                titles.add(normalized_title)
    return provider_ids, external_ids, titles


def _is_duplicate_candidate(
    candidate: itinerary_recommendations.ExternalPlaceCandidate,
    *,
    provider_ids: set[tuple[str, str]],
    external_ids: set[str],
    titles: set[str],
) -> bool:
    if candidate.source_provider and candidate.external_place_id:
        if (candidate.source_provider, candidate.external_place_id) in provider_ids:
            return True
    if candidate.external_place_id and candidate.external_place_id in external_ids:
        return True
    normalized_title = _normalized_text(candidate.title)
    return bool(normalized_title and normalized_title in titles)


def _additional_recommendation_items(trip: Trip) -> list[dict[str, object]]:
    provider = _build_external_place_provider()
    if provider is None:
        return []

    day_numbers = sorted(day.day_number for day in trip.days) or [1]
    region = trip.region or trip.title
    style = trip.description or ""
    provider_ids, external_ids, titles = _existing_place_keys(trip)
    candidates = itinerary_recommendations.additional_place_candidates(
        region=region,
        style=style,
        day_count=max(len(day_numbers), 6),
        travel_area_id=trip.travel_area_id,
        external_provider=provider,
        limit=18,
        exclude_candidate=lambda candidate: _is_duplicate_candidate(
            candidate,
            provider_ids=provider_ids,
            external_ids=external_ids,
            titles=titles,
        ),
    )
    items: list[dict[str, object]] = []
    for candidate in candidates:
        suggested_day = day_numbers[len(items) % len(day_numbers)]
        items.append(
            itinerary_recommendations.recommendation_from_candidate(
                candidate,
                suggested_day=suggested_day,
                region=region,
                style=style,
            )
        )
    return items


def list_recommendations(
    db: Session,
    user: User,
    trip_handle: str,
) -> list[dict[str, object]] | None:
    trip = _resolve_trip(db, trip_handle, user)
    if trip is None:
        return None

    additional_items = _additional_recommendation_items(trip)
    if additional_items:
        return additional_items

    items: list[dict[str, object]] = []
    for recommendation in trip_repository.list_recommendations(db, trip_id=trip.id, user_id=user.id):
        items.extend(_recommendation_items(recommendation.result))
    return items


def _place_search_meta(*, category_name: str | None, address: str | None) -> str:
    parts = [category_name, address]
    text = " · ".join(part for part in parts if part)
    return text or "장소 정보 확인"


def search_places_for_trip(
    db: Session,
    user: User,
    *,
    trip_handle: str,
    query: str,
) -> list[dict[str, object]]:
    trip = _resolve_required_trip(db, trip_handle, user)
    del trip
    trimmed_query = query.strip()
    if not trimmed_query:
        return []
    provider = build_kakao_local_client()
    if provider is None:
        return []
    try:
        places = provider.search_keyword(query=trimmed_query, size=10)
    except Exception:
        logger.warning("trip_place_search_failed trip=%s", trip_handle, exc_info=True)
        return []
    candidates: list[dict[str, object]] = []
    for place in places:
        candidates.append(
            {
                "id": f"kakao:{place.external_place_id}",
                "label": "📍",
                "title": place.name,
                "meta": _place_search_meta(category_name=place.category_name, address=place.address),
                "categoryCode": place.category_group_code,
                "categoryName": place.category_name,
                "phone": place.phone,
                "address": place.address,
                "latitude": place.latitude,
                "longitude": place.longitude,
                "placeUrl": place.place_url,
                "sourceProvider": "kakao",
                "externalPlaceId": place.external_place_id,
            }
        )
    return candidates


def _new_invite_token() -> str:
    return secrets.token_urlsafe(12)


def _invite_accept_url(invite_token: str) -> str:
    return f"{settings.frontend_base_url()}/invites/{invite_token}/accept"


INVITE_ROLES: tuple[str, str] = ("viewer", "editor")


def _ensure_invite(db: Session, trip: Trip, user: User, role: str | None = None) -> TripInvite:
    invite_role = role or "editor"
    now = security.utc_now_naive()
    invite = trip_repository.get_latest_active_invite(
        db,
        trip_id=trip.id,
        now=now,
        role=invite_role,
    )
    if invite is not None:
        return invite

    return trip_repository.create_invite(
        db,
        trip_id=trip.id,
        invite_token=_new_invite_token(),
        created_by=user.id,
        expires_at=now + timedelta(days=60),
        role=invite_role,
    )


def invite_to_api(
    invite: TripInvite,
    *,
    trip_id: int,
    invited: bool = False,
    already_member: bool = False,
) -> dict[str, object]:
    return {
        "id": str(invite.id),
        "tripId": str(trip_id),
        "inviteToken": invite.invite_token,
        "inviteUrl": _invite_accept_url(invite.invite_token),
        "expiresAt": _iso(invite.expires_at) or "",
        "createdAt": _iso(invite.created_at) or "",
        "acceptedAt": _iso(invite.accepted_at),
        "invited": invited or invite.expires_at > security.utc_now_naive(),
        "copied": False,
        "role": invite.role or "editor",
        "alreadyMember": already_member,
    }


def invite_links_to_api(
    *,
    trip_id: int,
    viewer: TripInvite | None,
    editor: TripInvite | None,
) -> dict[str, object]:
    return {
        "tripId": str(trip_id),
        "viewer": invite_to_api(viewer, trip_id=trip_id) if viewer is not None else None,
        "editor": invite_to_api(editor, trip_id=trip_id) if editor is not None else None,
    }


def get_invite_state(
    db: Session,
    user: User,
    trip_handle: str,
) -> dict[str, object] | None:
    trip = _resolve_editable_trip(db, trip_handle, user)
    if trip is None:
        return None
    viewer = _ensure_invite(db, trip, user, "viewer")
    editor = _ensure_invite(db, trip, user, "editor")
    db.commit()
    return invite_links_to_api(trip_id=trip.id, viewer=viewer, editor=editor)


def confirm_invite_sent(
    db: Session,
    user: User,
    trip_handle: str,
    role: str = "editor",
) -> dict[str, object] | None:
    trip = _resolve_editable_trip(db, trip_handle, user)
    if trip is None:
        return None
    invite = _ensure_invite(db, trip, user, role)
    db.commit()
    return invite_to_api(invite, trip_id=trip.id, invited=True)


def send_invite_email(
    db: Session,
    user: User,
    trip_handle: str,
    payload: SendInviteEmailRequest,
) -> dict[str, object] | None:
    trip = _resolve_editable_trip(db, trip_handle, user)
    if trip is None:
        return None
    invite = _ensure_invite(db, trip, user, payload.role)
    db.commit()
    invite_payload = invite_to_api(invite, trip_id=trip.id, invited=True)

    try:
        email_service.send_trip_invite_email(
            to_email=payload.email,
            invite_url=str(invite_payload["inviteUrl"]),
        )
    except email_service.EmailNotConfiguredError:
        return {
            "invite": invite_payload,
            "deliveryStatus": "notConfigured",
            "message": "Email delivery is not configured. Share the invite link directly.",
        }
    except email_service.EmailDeliveryError:
        return {
            "invite": invite_payload,
            "deliveryStatus": "failed",
            "message": "Email delivery failed. Share the invite link directly.",
        }

    return {
        "invite": invite_payload,
        "deliveryStatus": "sent",
        "message": "Invite email sent.",
    }


def accept_invite(db: Session, user: User, invite_token: str) -> dict[str, object] | None:
    now = security.utc_now_naive()
    invite = trip_repository.get_active_invite_by_token(
        db,
        invite_token=invite_token,
        now=now,
    )
    if invite is None:
        return None

    is_owner = invite.trip is not None and invite.trip.owner_id == user.id
    existing_member = trip_repository.get_trip_member(
        db,
        trip_id=invite.trip_id,
        user_id=user.id,
    )
    already_member = is_owner or existing_member is not None
    if not already_member and len(_actual_participant_user_ids(invite.trip)) >= MAX_TRIP_PARTICIPANTS:
        raise TripServiceError(409, "Trip participant limit reached")

    if invite.accepted_at is None:
        invite.accepted_at = now

    if not already_member:
        trip_repository.add_trip_member(
            db,
            trip_id=invite.trip_id,
            user_id=user.id,
            role=invite.role or "editor",
        )

    db.commit()
    return invite_to_api(
        invite,
        trip_id=invite.trip_id,
        invited=True,
        already_member=already_member,
    )
