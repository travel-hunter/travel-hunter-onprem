from __future__ import annotations

import secrets
import re
import logging
from functools import lru_cache
import time as monotonic_time
from datetime import date, datetime, timedelta, time
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core import security
from app.data import seed

DEFAULT_TRIP_REGION = "제주"
from app.models import ExternalSourceRecord, Policy, PublicPlace, Trip, TripDay, TripInvite, TripPlace, TripPolicy, User
from app.models.policy_status import is_policy_deadline_current
from app.repositories import external_sources as external_source_repository
from app.repositories import geo as geo_repository
from app.repositories import policies as policy_repository
from app.repositories import public_places as public_place_repository
from app.repositories import trips as trip_repository
from app.schemas.trip import (
    CreateTripPlacesRequest,
    CreateTripPlaceRequest,
    CreateTripRequest,
    CustomPlaceInput,
    GeoRef,
    MAX_TRIP_PARTICIPANTS,
    MoveTripPlaceRequest,
    PublicPlaceRef,
    SendInviteEmailRequest,
    TripPlaceAddItem,
    UpdateTripSettingsRequest,
    UpdateTripPlaceRequest,
    UpdateTripStatusRequest,
)
from app.repositories.eligible_islands import normalize_island_name
from app.models import policy_status as policy_status_module
from app.schemas.trip import UpdateTripPolicyApplicationRequest
from app.services import address_fill
from app.services import island_application
from app.services import email as email_service
from app.services import itinerary_recommendations
from app.services import public_places as public_place_service
from app.services import trip_public_places
from app.services.geo_reference import GeoHit
from app.services.eligible_island_catalog import (
    ISLAND_POLICY_SOURCE_CATEGORY,
    EligibleIslandSummary,
    build_eligible_island_summary,
)
from app.services import local_half_trip_display
from app.services import stay_discount_aliases
from app.services import digital_tourism_policy_aliases
from app.services.kakao_local import KakaoLocalClient, KakaoLocalConfigurationError, KakaoLocalPlace, build_kakao_local_client
from app.services.policy_semantics import (
    benefit_display_amount,
    is_public_policy,
    policy_status,
)

try:
    from app.data.travel_areas import list_travel_areas
    from app.services.travel_area_catalog import resolve_travel_area
except ModuleNotFoundError:
    def resolve_travel_area(_area_id: str | None):
        return None

    def list_travel_areas():
        return ()


get_travel_area = resolve_travel_area


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


class TripServiceError(Exception):
    # detail 은 대개 문장이지만, 화면이 목록을 보여 줘야 하는 거부는 객체로 낸다
    def __init__(self, status_code: int, detail: str | dict[str, object]) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail if isinstance(detail, str) else str(detail.get("message") or ""))


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
        if (
            link.policy is not None
            and is_policy_deadline_current(link.policy.end_date)
            and link.policy.benefit_amount
        ):
            total += int(link.policy.benefit_amount)
    return total


def _trip_policy_amount(policy: Policy) -> str:
    detail_amount = benefit_display_amount(
        benefit_detail=policy.benefit_detail,
        benefit_amount=None,
    )
    return detail_amount or _format_saving(policy.benefit_amount or 0)


def _people_by_id(trip: Trip) -> dict[int, str]:
    people: dict[int, str] = {}
    if trip.owner is not None and trip.owner.id is not None:
        people[int(trip.owner.id)] = trip.owner.nickname
    for membership in trip.members:
        if membership.user is not None and membership.user.id is not None:
            people[int(membership.user.id)] = membership.user.nickname
    return people


def _approved_island_names(db: Session, trip: Trip) -> frozenset[str] | None:
    if not any(
        link.policy is not None and link.policy.source_category == island_application.ISLAND_SOURCE_CATEGORY
        for link in trip.policies
    ):
        return None
    return build_eligible_island_summary(db).normalized_names


def _linked_policies(
    trip: Trip,
    alias_overrides: dict[str, stay_discount_aliases.StayDiscountAliasArea] | None = None,
    approved_island_names: frozenset[str] | None = None,
) -> list[dict[str, object]]:
    alias_overrides = alias_overrides or {}
    linked: list[dict[str, object]] = []
    on = island_application.today()
    people_by_id = _people_by_id(trip)
    for link in sorted(trip.policies, key=lambda item: item.id or 0):
        policy = link.policy
        if policy is None:
            continue
        guide = island_application.active_guide(policy, on=on)
        # Island support stays on the trip past its card deadline while travelers still have steps to do.
        if not is_policy_deadline_current(policy.end_date) and guide is None:
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
        item: dict[str, object] = {
            "slug": slug,
            "title": title,
            "amount": amount,
            "region": region,
            "status": policy_status(policy),
            "deadline": policy.end_date.isoformat() if policy.end_date else None,
            "officialUrl": policy.official_url or None,
            "applyUrl": policy.apply_url or None,
        }
        if guide is not None:
            item["application"] = island_application.application_view(
                trip, link, guide, approved_island_names=approved_island_names, people_by_id=people_by_id
            )
        linked.append(item)
    return linked


def _policy_to_trip_policy_candidate(
    policy: Policy,
    external_record: ExternalSourceRecord | None = None,
) -> dict[str, object]:
    slug = policy.slug or str(policy.id)
    amount = _trip_policy_amount(policy)
    # 붙이기 경로는 외부 기록을 넘기지 않는다. 그때는 정책 자신의 city 가 시군을 말해 준다 -
    # 안 보면 제목에 지명이 없는 정책은 시도만 같은 아무 일정에나 붙는다.
    city = (external_record.city if external_record is not None else None) or policy.city
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


def _policy_attachment_candidate(
    policy: Policy,
    alias_area: stay_discount_aliases.StayDiscountAliasArea | None,
) -> dict[str, object]:
    if alias_area is not None:
        return _stay_alias_to_trip_policy_candidate(policy, alias_area)
    return _policy_to_trip_policy_candidate(policy)


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
    # 낱말 머리에서만 찾는다. 공백을 지운 제목에서 부분 문자열로 찾으면 "디지털관광주민증" 안의
    # "광주"가 지명으로 잡혀, 경기 광주시 일정에 연천 정책이 붙었다. "광주 비엔날레"·"여수에서"는 그대로 잡힌다.
    title_words = [_normalized_text(word) for word in re.split(r"[^0-9A-Za-z가-힣]+", title) if word]
    for term in _known_municipal_terms():
        key = _normalized_text(term)
        if any(word.startswith(key) for word in title_words):
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


def _policy_is_attachable_to_trip(
    policy: Policy,
    trip: Trip,
    alias_area: stay_discount_aliases.StayDiscountAliasArea | None,
) -> bool:
    candidate = _policy_attachment_candidate(policy, alias_area)
    if not _candidate_has_explicit_locality(candidate):
        candidate_sido = _candidate_sido(candidate)
        if not candidate_sido:
            return _normalized_text(candidate.get("region")) == _normalized_text(NATIONWIDE_REGION)
        # 시군 단서 없이 시도만 있는 정책("강원 전역 …")은 그 시도 안의 일정이면 붙는다.
        # 이 갈래가 없으면 시도 단위 정책은 어떤 일정에도 붙일 수 없다.
        area = get_travel_area(trip.travel_area_id)
        return area is not None and _normalized_text(area.sido) == _normalized_text(candidate_sido)
    if not trip.travel_area_id:
        return False
    return _candidate_matches_trip_locality(candidate, trip)


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
    if source_category in {"local_half_trip", "digital_tourism_resident_card", "regional_benefit"} or policy_type == "지역할인":
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


def _matches_approved_island(candidate: dict[str, object], trip: Trip) -> bool:
    """Island support is recommended only when a trip place name exactly equals an approved island name.

    Exact NFC + whitespace normalization only: `거문도 선착장` does not match `거문도` (spec).
    """
    approved_names = candidate.get("eligibleIslandNames")
    if approved_names is None:
        return True
    return any(
        normalize_island_name(place.place_name or "") in approved_names
        for day in trip.days
        for place in day.places
    )


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
        and _matches_approved_island(candidate, trip)
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
    island_summary: EligibleIslandSummary | None = None
    for policy in policies:
        if (
            policy.external_source_record_id is not None
            and policy.verification_status
            and policy.verification_status != "fresh"
        ):
            continue
        if stay_discount_aliases.is_stay_discount_canonical_policy(policy):
            continue
        external_record = (
            external_source_repository.get_external_source_record_by_id(
                db,
                policy.external_source_record_id,
            )
            if policy.external_source_record_id is not None
            else None
        )
        candidate = _policy_to_trip_policy_candidate(policy, external_record)
        if policy.source_category == ISLAND_POLICY_SOURCE_CATEGORY:
            if island_summary is None:
                island_summary = build_eligible_island_summary(db)
            candidate["eligibleIslandNames"] = island_summary.normalized_names
        candidates.append(candidate)
    return candidates


def _resolve_policy_for_request_slug(
    db: Session,
    policy_slug: str,
) -> tuple[Policy | None, stay_discount_aliases.StayDiscountAliasArea | None]:
    policy = policy_repository.get_policy_by_slug(db, policy_slug)
    if policy is not None:
        return policy, None
    alias_resolution = stay_discount_aliases.resolve_stay_discount_alias_slug(db, policy_slug)
    if alias_resolution is not None:
        policy = alias_resolution.canonical_policy
        if not is_public_policy(policy):
            return None, None
        return policy, alias_resolution.alias_area
    digital_policy = digital_tourism_policy_aliases.resolve_digital_tourism_alias_slug(
        db,
        policy_slug,
    )
    if digital_policy is not None:
        if is_public_policy(digital_policy):
            return digital_policy, None
        return None, None
    return None, None


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
    approved_island_names: frozenset[str] | None = None,
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
                "label": place.user_label or place.place_name,   # 사용자가 붙인 이름이 있으면 그것(공공데이터 장소의 이름은 place_name 에 그대로 있다)
                "meta": place.memo or place.address or "",
                "address": place.address,
                "latitude": float(place.latitude) if place.latitude is not None else None,
                "longitude": float(place.longitude) if place.longitude is not None else None,
                "category": getattr(place, "category_group_name", None),
                "categoryCode": getattr(place, "category_group_code", None),
                "placeUrl": getattr(place, "place_url", None),
                "sourceProvider": getattr(place, "source_provider", None),
                "externalPlaceId": getattr(place, "external_place_id", None),
                "memo": place.memo,
                "placeOrigin": place.place_origin,
                "publicSource": place.public_source,
                "publicSourceId": place.public_source_id,
                "publicCategory": place.public_category,
                "photoUrl": place.photo_url,
                "photoLicense": place.photo_license,
                "geoKind": place.geo_kind,
                "needsConfirmation": trip_public_places.is_legacy_kakao_place(place),
            }
            for place in places
        ]

    return {
        "id": str(trip.id),
        "title": trip.title,
        "status": trip.status or "confirmed",
        "revision": trip.revision or 1,
        "travelAreaId": trip.travel_area_id,
        "region": trip.region or "",
        "dates": _format_dates(trip.start_date, trip.end_date),
        "startDate": trip.start_date,
        "endDate": trip.end_date,
        "people": people,
        "participantCount": trip.participant_count or max(1, len(people)),
        "expectedSaving": _format_saving(_policy_saving(trip)),
        "linkedPolicies": _linked_policies(trip, linked_policy_alias_overrides, approved_island_names),
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
    return trip_to_api(
        trip,
        user,
        _list_recommended_policy_candidates(db),
        approved_island_names=_approved_island_names(db, trip),
    )


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


def _find_trip_day_for_batch(trip: Trip, day_number: int) -> TripDay:
    for trip_day in trip.days:
        if trip_day.day_number == day_number:
            return trip_day
    raise TripServiceError(404, "Trip day not found")


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


def _delete_trip_day(db: Session, trip_day: TripDay) -> None:
    if hasattr(db, "delete"):
        db.delete(trip_day)


def _flush(db: Session) -> None:
    if hasattr(db, "flush"):
        db.flush()


def _release_session(db: Session) -> None:
    """접근 확인이 끝난 세션을 놓는다 - 카카오를 기다리는 동안(최대 수 초) DB 연결을 쥐고 있으면 몰린 요청이 풀을 말린다(/api/places 와 같은 꼴)."""
    close = getattr(db, "close", None)
    if close is not None:
        close()


def _apply_trip_date_range(
    db: Session,
    trip: Trip,
    *,
    start_date: date,
    end_date: date,
    overflow_place_strategy: str,
) -> None:
    next_day_count = (end_date - start_date).days + 1
    ordered_days = sorted(trip.days, key=lambda day: day.day_number)
    kept_days = [day for day in ordered_days if day.day_number <= next_day_count]
    overflow_days = [day for day in ordered_days if day.day_number > next_day_count]

    # trip_days 에는 UniqueConstraint("trip_id", "date") 가 걸려 있다.
    # 한 flush 안에서 날짜를 한꺼번에 바꾸면 SQLAlchemy 가 UPDATE 를 DELETE 보다 먼저,
    # 그것도 PK 순서대로 내보내므로 "어떤 날의 새 날짜 == 아직 남아 있는 다른 행의 옛 날짜"
    # 인 순간(예: 범위 전체를 하루 뒤로 밀기) 제약에 걸린다.
    # 그래서 ① 넘치는 날 삭제 → ② 충돌할 수 없는 임시 날짜 → ③ 최종 날짜 로 나눠 flush 한다.
    if overflow_place_strategy == "moveToLastDay" and overflow_days and kept_days:
        target_day = kept_days[-1]
        target_places = _ordered_places(target_day)
        for overflow_day in overflow_days:
            target_places.extend(_ordered_places(overflow_day))
            overflow_day.places = []
        trip_repository.reorder_trip_day_places(target_day, target_places)

    for overflow_day in overflow_days:
        _delete_trip_day(db, overflow_day)
        if overflow_day in trip.days:
            trip.days.remove(overflow_day)
    _flush(db)

    if not kept_days:
        kept_days = [
            trip_repository.add_trip_day(
                db,
                trip_id=trip.id,
                day_number=1,
                date_value=start_date,
            )
        ]
    else:
        for day in kept_days:
            day.date = start_date + timedelta(days=10_000 + day.day_number)
        _flush(db)
        for day in kept_days:
            day.date = start_date + timedelta(days=day.day_number - 1)
        _flush(db)

    existing_numbers = {day.day_number for day in kept_days}
    for day_number in range(1, next_day_count + 1):
        if day_number not in existing_numbers:
            day = trip_repository.add_trip_day(
                db,
                trip_id=trip.id,
                day_number=day_number,
                date_value=start_date + timedelta(days=day_number - 1),
            )
            kept_days.append(day)
            existing_numbers.add(day_number)

    trip.start_date = start_date
    trip.end_date = end_date
    trip.days = sorted(kept_days, key=lambda day: day.day_number)


def list_trips(db: Session, user: User) -> list[dict[str, object]]:
    recommended_policy_candidates = _list_recommended_policy_candidates(db)
    return [trip_to_api(trip, user, recommended_policy_candidates) for trip in trip_repository.list_accessible_trips(db, user.id)]


def get_trip(trip_handle: str, db: Session, user: User) -> dict[str, object] | None:
    trip = _resolve_trip(db, trip_handle, user)
    if trip is None:
        return None
    return trip_to_api(
        trip,
        user,
        _list_recommended_policy_candidates(db),
        approved_island_names=_approved_island_names(db, trip),
    )


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
    policy_slug = str(payload["policySlug"]) if payload.get("policySlug") else None
    policy = None
    alias_area = None
    if policy_slug:
        policy, alias_area = _resolve_policy_for_request_slug(db, policy_slug)
        if policy is None:
            raise TripServiceError(404, "Policy not found")
        prospective_trip = Trip(
            region=region,
            travel_area_id=travel_area.id if travel_area else None,
        )
        if not _policy_is_attachable_to_trip(policy, prospective_trip, alias_area):
            raise TripServiceError(409, "Policy does not match trip travel area")

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
    if policy is not None:
        trip_repository.add_trip_policy(db, trip_id=trip.id, policy_id=policy.id)
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

    # 확인과 삽입 사이에 다른 요청이 끼어들면 숙박세일이 둘 이상 붙는다.
    # 잠금을 얻을 때까지 앞선 트랜잭션이 커밋을 마치지 못하므로, 아래 확인은
    # 항상 최신 상태를 본다.
    trip_repository.lock_trip_row(db, trip_id=trip.id)
    existing = trip_repository.get_trip_policy(db, trip_id=trip.id, policy_id=policy.id)
    if existing is None:
        if not _policy_is_attachable_to_trip(policy, trip, _alias_area):
            raise TripServiceError(409, "Policy does not match trip travel area")
        # 숙박세일 페스타는 지역마다 정책 행이 따로 있어 policy_id 중복 검사를
        # 통과한다. 일정 하나에는 지역 하나만 붙는다. 같은 지역을 다시 누르면
        # existing이 있어 여기까지 오지 않으므로 기존처럼 조용히 성공한다.
        if (
            policy.source_category or ""
        ) == stay_discount_aliases.SOURCE_CATEGORY and trip_repository.has_trip_policy_in_source_category(
            db,
            trip_id=trip.id,
            source_category=stay_discount_aliases.SOURCE_CATEGORY,
        ):
            raise TripServiceError(409, "Trip already has a stay discount policy")
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


def update_trip_policy_application(
    db: Session,
    user: User,
    trip_handle: str,
    policy_slug: str,
    payload: UpdateTripPolicyApplicationRequest,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    # Looked up regardless of the card deadline: progress continues through travel and document submission.
    policy = policy_repository.get_policy_by_slug_any_status(db, policy_slug)
    guide = (
        island_application.active_guide(policy, on=island_application.today())
        if policy is not None and policy.status == "active"
        else None
    )
    if policy is None or guide is None:
        raise TripServiceError(404, "Application guide not found")

    trip_repository.lock_trip_row(db, trip_id=trip.id)
    link = trip_repository.get_trip_policy(db, trip_id=trip.id, policy_id=policy.id)
    if link is None:
        raise TripServiceError(404, "Policy is not linked to this trip")

    if payload.status is not None and not island_application.can_transition(
        link.application_status or "not_started", payload.status
    ):
        raise TripServiceError(409, "Invalid application status transition")
    if payload.checklist is not None and any(key not in guide["requiredDocuments"] for key in payload.checklist):
        raise TripServiceError(422, "Unknown application document")

    if payload.status is not None:
        link.application_status = payload.status
    if payload.checklist is not None:
        checked = dict(link.application_checklist or {})
        for key, value in payload.checklist.items():
            if value:
                checked[key] = True
            else:
                checked.pop(key, None)
        link.application_checklist = checked
    link.application_updated_at = security.utc_now_naive()
    link.application_updated_by_user_id = user.id
    db.commit()

    return island_application.application_view(
        trip,
        link,
        guide,
        approved_island_names=_approved_island_names(db, trip),
        people_by_id=_people_by_id(trip),
    )


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


def _links_outside_travel_area(db: Session, trip: Trip, travel_area) -> list[TripPolicy]:
    """지역이 실제로 바뀔 때, 새 지역에 붙일 수 없게 되는 연결들.
    붙일 때와 같은 판정을 쓴다 - 기준이 둘이면 붙였다 뺐다를 되풀이하게 된다.
    지역을 안 바꾸는 요청(제목·날짜만)은 옛 연결이 어떻든 막지 않는다."""
    if travel_area is None or travel_area.id == trip.travel_area_id:
        return []
    prospective_trip = Trip(region=travel_area.name, travel_area_id=travel_area.id)
    # 관계 컬렉션이 아니라 DB 에서 읽는다 - 같은 세션에서 방금 붙인 연결이 컬렉션에 없을 수 있다
    links = db.query(TripPolicy).filter(TripPolicy.trip_id == trip.id).order_by(TripPolicy.id).all()
    return [
        link
        for link in links
        if link.policy is not None
        and not _policy_is_attachable_to_trip(link.policy, prospective_trip, None)
    ]


def update_trip_settings(
    db: Session,
    user: User,
    trip_handle: str,
    payload: UpdateTripSettingsRequest,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    travel_area = None
    if payload.travelAreaId is not None:
        travel_area = resolve_travel_area(payload.travelAreaId.strip())
        if travel_area is None:
            raise TripServiceError(400, "Travel area not found")
    # 리비전을 올리기 전에 본다 - 거부된 요청은 revision 을 건드리지 않는다.
    stranded_links = _links_outside_travel_area(db, trip, travel_area)
    # 낡은 요청이면 아래 리비전 검사가 먼저 거절하게 둔다 - 화면이 낡았으면 정책 목록도 낡았다
    is_current = payload.expectedRevision == trip.revision
    if stranded_links and is_current and payload.mismatchedPolicyStrategy != "remove":
        raise TripServiceError(
            409,
            {
                "code": "trip_policies_outside_travel_area",
                "message": "Trip has policies outside the new travel area",
                "policies": [
                    {
                        "slug": link.policy.slug or str(link.policy.id),
                        "title": link.policy.title,
                        "hasApplicationProgress": bool(
                            link.application_status or link.application_checklist
                        ),
                    }
                    for link in stranded_links
                ],
            },
        )
    _bump_trip_revision_or_conflict(db, trip, payload.expectedRevision)
    for link in stranded_links:
        trip_repository.remove_trip_policy(db, link)
        if link in trip.policies:
            trip.policies.remove(link)

    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise TripServiceError(422, "Trip title is required")
        trip.title = title

    if travel_area is not None:
        trip.travel_area_id = travel_area.id
        trip.region = travel_area.name

    if payload.startDate is not None and payload.endDate is not None:
        _apply_trip_date_range(
            db,
            trip,
            start_date=payload.startDate,
            end_date=payload.endDate,
            overflow_place_strategy=payload.overflowPlaceStrategy,
        )

    db.commit()
    return _refresh_trip_payload(db, trip.id, user)


PUBLIC_PLACE_NOT_FOUND = "Public place not found"
GEO_REF_NOT_FOUND = "Address reference not found"
GEO_LOOKUP_UNAVAILABLE = "Address lookup is unavailable"


def _geo_ref_hit(db: Session, ref: GeoRef) -> GeoHit:
    """담을 때 지번 참조를 다시 읽는다 - SAVEPOINT 안에서(실패가 이 요청의 트랜잭션을 막지 않게). revision 을 올리기 전에 부른다."""

    try:
        with db.begin_nested():
            hit = geo_repository.get_by_ref(db, ref.kind, ref.id)
    except SQLAlchemyError as error:   # geo 표가 없거나 DB 가 실패 - 값은 싣지 않는다. 그 밖의 오류(코드 결함)는 숨기지 않고 올린다
        logger.warning("trip_place_geo_ref_failed error=%s", type(error).__name__)
        raise TripServiceError(503, GEO_LOOKUP_UNAVAILABLE) from None
    if hit is None:
        raise TripServiceError(404, GEO_REF_NOT_FOUND)   # 월 갱신으로 바뀐 판 - 화면이 다시 찾게 한다
    return hit


def _value_columns(
    db: Session,
    public_ref: PublicPlaceRef | None,
    custom: CustomPlaceInput | None,
    found: dict[tuple[str, str], PublicPlace],
) -> dict[str, object] | None:
    """공공데이터 참조 또는 나만의 장소 → trip_places 열 값(둘 다 없으면 None). 참조는 서버 표에서 찾아 그 값을 복사한다 -
    없으면 404. 나만의 장소의 geoRef 도 geo 표에서 다시 읽는다(주소 · 출처 · pin 이면 중심) - 그 id 가 없으면 404,
    geo 조회가 실패하면 503. revision 을 올리기 전에 부른다. found 는 같은 요청에서 이미 찾은 장소(묶음 추가에서 되풀이를 줄인다)."""

    if public_ref is not None:
        key = (public_ref.source, public_ref.sourceId)
        if key not in found:
            public_place = public_place_repository.get_public_place(db, *key)
            if public_place is None:
                raise TripServiceError(404, PUBLIC_PLACE_NOT_FOUND)
            found[key] = public_place
        return trip_public_places.public_place_columns(found[key])
    if custom is not None:
        if custom.geoRef is None:
            return trip_public_places.custom_place_columns(custom.name)
        hit = _geo_ref_hit(db, custom.geoRef)
        point = {"latitude": hit.latitude, "longitude": hit.longitude} if custom.geoRef.pin else {}
        return trip_public_places.custom_place_columns(custom.name, address=hit.address, geo_kind=hit.kind, geo_pnu=hit.pnu, **point)
    return None


def _new_place_columns(db: Session, items: list[TripPlaceAddItem]) -> list[dict[str, object]]:
    """담을 장소마다 trip_places 열 값을 만든다(trip_public_places). 공공데이터 참조는 revision 을 올리기 전에 모두 찾는다 -
    하나라도 없으면 404 로 멈춰 아무것도 쓰지 않고 revision 도 그대로다. 시간 형식 오류(422)도 여기서 먼저 걸린다."""

    found: dict[tuple[str, str], PublicPlace] = {}
    rows: list[dict[str, object]] = []
    for item in items:
        columns = _value_columns(db, item.publicPlace, item.customPlace, found)   # 스키마가 둘 중 정확히 하나를 보장한다
        columns.update(trip_public_places.kakao_link_columns(item.kakaoPlaceId))
        columns["visit_time"] = _parse_optional_time(item.time)
        rows.append(columns)
    return rows


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
    (columns,) = _new_place_columns(db, [payload])
    _bump_trip_revision_or_conflict(db, trip, payload.expectedRevision)

    next_order = max((place.order_num or 0 for place in trip_day.places), default=0) + 1
    trip_repository.add_trip_place(db, trip_day_id=trip_day.id, order_num=next_order, memo=None, **columns)
    db.commit()
    return _refresh_trip_payload(db, trip.id, user)


def add_places_to_trip_day(
    db: Session,
    user: User,
    trip_handle: str,
    day_number: int,
    payload: CreateTripPlacesRequest,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    trip_day = _find_trip_day_for_batch(trip, day_number)
    rows = _new_place_columns(db, payload.places)
    _bump_trip_revision_or_conflict(db, trip, payload.expectedRevision)

    next_order = max((place.order_num or 0 for place in trip_day.places), default=0) + 1
    for index, columns in enumerate(rows):
        trip_repository.add_trip_place(db, trip_day_id=trip_day.id, order_num=next_order + index, memo=None, **columns)

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

    label = None
    if "label" in values:
        label = (values["label"] or "").strip()
        if not label:
            raise TripServiceError(422, "Place label is required")
    visit_time = _parse_optional_time(values["time"]) if "time" in values else None
    replacement = _value_columns(db, payload.publicPlace, payload.customPlace, {})   # 없는 공공데이터 장소는 revision 전에 404
    _bump_trip_revision_or_conflict(db, trip, payload.expectedRevision)

    legacy = trip_public_places.is_legacy_kakao_place(place)
    if replacement is None and legacy and label is not None:
        # 예전 카카오 행은 이름만 고쳐도 나만의 장소로 바뀐다 - 카카오 이름 · 주소 · 좌표 · 분류를 남기지 않는다
        replacement = trip_public_places.custom_place_columns(label)
    if replacement is not None:
        for column, value in replacement.items():
            setattr(place, column, value)   # 사용자가 붙인 이름(user_label)도 이때 비워진다
        if legacy:
            place.memo = None   # 카카오 '분류 · 주소' 문구. 카카오 ID · place_url · source_provider 는 남긴다
    if label is not None:
        if place.place_origin == "public":
            place.user_label = label   # 공공데이터 장소는 이름을 따로 담는다 - place_name · 주소 · 좌표 · 사진 · 출처는 공공데이터 값 그대로
        else:
            place.place_name = label
    if "time" in values:
        place.visit_time = visit_time
    if "memo" in values:
        place.memo = (values["memo"] or "").strip() or None

    db.commit()
    return _refresh_trip_payload(db, trip.id, user)


def list_legacy_place_candidates(
    db: Session,
    user: User,
    trip_handle: str,
    place_id: int,
) -> list[dict[str, object]]:
    """예전 카카오 행과 겹치는 공공데이터 후보(가까운 순 최대 3곳, 바로 맞는 곳 포함). 저장된 이름 · 좌표 · 분류는 서버 메모리에서
    견주기만 하고 저장 · 로그에 남기지 않는다. 예전 행이 아니거나 이름 · 좌표가 없으면 빈 목록."""

    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    place = _find_trip_place(trip, place_id)
    if (
        not trip_public_places.is_legacy_kakao_place(place)
        or not place.place_name
        or place.latitude is None
        or place.longitude is None
    ):
        return []
    found = public_place_service.match_place(
        db,
        name=place.place_name,
        latitude=float(place.latitude),
        longitude=float(place.longitude),
        category_code=place.category_group_code,
    )
    return [public_place_service.public_place_item(candidate, distance) for candidate, distance in found.places]


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


def delete_trip_places(
    db: Session,
    user: User,
    trip_handle: str,
    place_ids: list[int],
    expected_revision: int,
) -> dict[str, object]:
    trip = _resolve_required_trip(db, trip_handle, user)
    _require_trip_editor(trip, user)
    # 하나라도 없으면 리비전을 올리기 전에 404. 부분 삭제는 없다.
    unique_ids = list(dict.fromkeys(place_ids))
    places = [_find_trip_place(trip, place_id) for place_id in unique_ids]
    _bump_trip_revision_or_conflict(db, trip, expected_revision)
    for place in places:
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


def list_recommendations(
    db: Session,
    user: User,
    trip_handle: str,
) -> list[dict[str, object]] | None:
    trip = _resolve_trip(db, trip_handle, user)
    if trip is None:
        return None

    # 카카오 검색 대신 공공데이터(public_places)에서 일정 지역으로 고른다. 지역을 못 가리거나 고를 장소가 없으면 저장 요약으로 넘어간다
    public_items = trip_public_places.recommend_public_places(
        db, trip=trip, area=get_travel_area(trip.travel_area_id), region=trip.region or trip.title
    )
    if public_items:
        return public_items

    items: list[dict[str, object]] = []
    for recommendation in trip_repository.list_recommendations(db, trip_id=trip.id, user_id=user.id):
        items.extend(_recommendation_items(recommendation.result))
    return items


def get_trip_area_center(db: Session, user: User, trip_handle: str) -> dict[str, float | None]:
    """일정 지역의 공공데이터 장소 위경도 중앙값 - 위치 찍기 지도가 여기서 연다. 보기 권한이면 된다."""

    trip = _resolve_required_trip(db, trip_handle, user)
    return trip_public_places.area_center(db, get_travel_area(trip.travel_area_id))


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
    if not NUMERIC_TRIP_ID_PATTERN.fullmatch(trip_handle) or not trip_repository.has_trip_access(
        db,
        int(trip_handle),
        user.id,
    ):
        raise TripServiceError(404, "Trip not found")
    trimmed_query = query.strip()
    if not trimmed_query:
        return []
    _release_session(db)   # 접근 확인이 끝났다 - 카카오를 기다리는 동안 DB 연결을 쥐지 않는다
    try:
        provider = build_kakao_local_client()
    except KakaoLocalConfigurationError:
        # 켜 두었는데 설정이 틀렸다(키 없음 등) - 500 이 아니라 503. 일부러 끈 경우(None)의 빈 목록과 구별한다. 키 · 설정 값은 로그 · 응답에 남기지 않는다
        logger.warning("trip_place_search_kakao_misconfigured")
        raise TripServiceError(503, "Place search is unavailable") from None
    if provider is None:
        return []
    try:
        places = provider.search_keyword(query=trimmed_query, size=PLACE_SEARCH_SIZE)
    except Exception as error:
        logger.warning("trip_place_search_failed trip=%s error=%s", trip_handle, type(error).__name__)
        return []
    matches = _prematch(db, places)
    candidates: list[dict[str, object]] = []
    for place, public_match in zip(places, matches):
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
                "publicMatch": public_match,
            }
        )
    return candidates


PLACE_SEARCH_SIZE = 6   # 담기 창이 보이는 결과 수(시안 v61) - 줄마다 맞춰 보므로 더 받지 않는다


def _prematch(db: Session, places: list[KakaoLocalPlace]) -> list[dict[str, object] | None]:
    """검색 결과를 우리 장소 기반과 한 번에 미리 맞춰 본다(결정 23). 카카오 값은 이 안에서 견주고 버린다 - 저장 · 로그 금지.
    세션은 카카오를 부르기 전에 놓았다(_release_session) - SQLAlchemy 2 의 Session 은 close 뒤 다시 쓰면 새 연결을 잡는다(실제 Session 시험이 붙잡는다).
    좌표가 없는 줄은 None. DB 읽기가 실패하면 모든 줄이 None 이고, 화면은 고른 뒤 예전처럼 맞춰 본다."""

    rows = [
        public_place_service.PlaceMatchInput(place.name, place.latitude, place.longitude, place.category_group_code)
        if place.latitude is not None and place.longitude is not None
        else None
        for place in places
    ]
    try:
        answers = public_place_service.match_places(db, rows)
    except Exception as error:
        logger.warning("trip_place_search_prematch_failed error=%s", type(error).__name__)   # 검색어 · 장소 값은 싣지 않는다
        return [None] * len(places)
    return address_fill.with_fill(db, rows, answers)   # 방식1: match 가 아닌 줄에 건물 · 땅 지번(같은 세션, 질의 1번)


def _new_invite_token() -> str:
    return secrets.token_urlsafe(12)


def _invite_accept_url(invite_token: str) -> str:
    return f"{settings.frontend_base_url()}/invites/{invite_token}/accept"


INVITE_ROLE = "editor"


def _require_editor_invite_role(role: str | None) -> str:
    invite_role = role or INVITE_ROLE
    if invite_role != INVITE_ROLE:
        raise TripServiceError(422, "Only editor invites are supported")
    return INVITE_ROLE


def _ensure_invite(db: Session, trip: Trip, user: User, role: str | None = None) -> TripInvite:
    invite_role = _require_editor_invite_role(role)
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


def get_invite_state(
    db: Session,
    user: User,
    trip_handle: str,
) -> dict[str, object] | None:
    trip = _resolve_editable_trip(db, trip_handle, user)
    if trip is None:
        return None
    invite = _ensure_invite(db, trip, user, INVITE_ROLE)
    db.commit()
    return invite_to_api(invite, trip_id=trip.id)


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
