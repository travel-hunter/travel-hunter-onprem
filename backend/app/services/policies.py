from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.data.policy_display import DISPLAY_OVERRIDES, SUPPORTED_CATEGORIES
from app.models import ExternalSourceRecord
from app.models import User
from app.models import Policy as PolicyModel
from app.repositories import external_sources as external_source_repository
from app.repositories import policies as policy_repository
from app.services.policy_category_classifier import classify_external_policy_category
from app.services import stay_discount_aliases
from app.services import digital_tourism_policy_aliases
from app.services import digital_tourism_resident_card as dgtour_identity
from app.services import local_half_trip_display
from app.services.policy_semantics import (
    api_policy_source_type,
    api_policy_source_type_for_policy,
    benefit_display_amount_for_policy,
    format_benefit_amount,
    is_public_policy,
    policy_url_fields,
    policy_url_fields_for_policy,
    requirement_items_for_policy,
)
from app.services.policy_periods import (
    representative_deadline_from_payload,
)
from app.services.policy_structured_detail import structured_detail_for_api
from app.services.region_photos import (
    EMPTY_REGION_PHOTO_INDEX,
    RegionPhotoIndex,
    build_region_photo_index,
)
from app.services.policy_semantic_mapping import map_external_source_semantics
from app.services.eligible_island_catalog import (
    ISLAND_POLICY_SOURCE_CATEGORY,
    EligibleIslandSummary,
    build_eligible_island_summary,
)
from app.models.policy_status import policy_visibility_date
from app.services import island_application
from app.services.island_application_guide import application_guide_for_api


LEGACY_CATEGORY_MAP = {
    "추천": "지역할인",
    "환급": "지역할인",
    "캐시백": "지역할인",
}


def _normalize_policy_category(policy_type: str | None) -> str:
    if policy_type in SUPPORTED_CATEGORIES:
        return policy_type
    return LEGACY_CATEGORY_MAP.get(policy_type or "", "기타")


def _external_policy_category(record: ExternalSourceRecord) -> str:
    return classify_external_policy_category(record).category


def _requirements_for_projection(
    policy: PolicyModel,
    structured_detail: dict[str, object] | None,
) -> list[str]:
    conditions = None
    if isinstance(structured_detail, dict):
        conditions = structured_detail.get("applicationTarget") or structured_detail.get("conditions")
    if isinstance(conditions, list) and conditions:
        return [
            str(item.get("description"))
            for item in conditions
            if isinstance(item, dict) and item.get("description")
        ]
    if policy.source_category == "local_half_trip" and policy.external_source_record_id is not None:
        return ["공식 혜택 안내에서 조건을 확인하세요."]
    if policy.external_source_record_id is not None:
        return []
    return requirement_items_for_policy(policy)


def _attach_region_photo(
    payload: dict[str, object],
    photos: RegionPhotoIndex | None,
    region: str | None,
    city: str | None,
    *,
    policy_id: int | None = None,
) -> None:
    index = photos or EMPTY_REGION_PHOTO_INDEX
    resolved = (
        index.resolve_policy(policy_id, region, city)
        if policy_id is not None
        else index.resolve(region, city)
    )
    if resolved is not None:
        payload["photo"] = resolved.to_api()


def _attach_eligible_islands(
    payload: dict[str, object],
    islands: EligibleIslandSummary | None,
    source_category: str | None,
) -> None:
    if islands is not None and source_category == ISLAND_POLICY_SOURCE_CATEGORY:
        payload.update(islands.policy_fields())


def policy_to_api(
    policy: PolicyModel,
    *,
    photos: RegionPhotoIndex | None = None,
    islands: EligibleIslandSummary | None = None,
) -> dict[str, object]:
    slug = policy.slug or str(policy.id)
    display = DISPLAY_OVERRIDES.get(slug, {})
    benefit_prefix = format_benefit_amount(policy.benefit_amount)
    amount = benefit_display_amount_for_policy(policy)
    category = _normalize_policy_category(policy.policy_type)
    source_type = api_policy_source_type_for_policy(policy)

    title = local_half_trip_display.policy_title(
        policy.title,
        policy.source_category,
    )
    structured_detail = structured_detail_for_api(policy)

    payload = {
        "id": slug,
        "slug": slug,
        "label": str(display.get("label", slug[:2].upper())),
        "tag": str(display.get("tag", benefit_prefix or category)),
        "title": title,
        "org": policy.organization or "",
        "region": policy.region,
        "startDate": policy.start_date.isoformat() if policy.start_date else None,
        "deadline": policy.end_date.isoformat() if policy.end_date else "",
        "amount": amount,
        "summary": policy.policy_comment or policy.description or "",
        "match": int(display.get("match", 90)),
        "category": category,
        "requirements": _requirements_for_projection(policy, structured_detail),
        "documents": [document.document_name for document in policy.documents],
        "structuredDetail": structured_detail,
        **policy_url_fields_for_policy(policy),
        "sourceType": source_type,
    }
    _attach_region_photo(
        payload,
        photos,
        policy.region,
        policy.city,
        policy_id=policy.id,
    )
    _attach_eligible_islands(payload, islands, policy.source_category)
    guide = application_guide_for_api(policy.structured_detail, today=policy_visibility_date())
    if guide is not None:
        payload["applicationGuide"] = guide
        # The reviewed column stays empty; offer the official form only while its round is open.
        if guide["applyFormUrl"] and not payload.get("applyUrl"):
            payload["applyUrl"] = guide["applyFormUrl"]
    if (
        stay_discount_aliases.is_stay_discount_canonical_policy(policy)
        or stay_discount_aliases.is_stay_discount_area_policy(policy)
    ):
        stay_discount_aliases.apply_detail_display_fields(
            payload,
            benefit_amount=policy.benefit_amount,
        )
    return payload


def _policy_to_stay_discount_alias_api(
    policy: PolicyModel,
    alias_area: stay_discount_aliases.StayDiscountAliasArea,
    *,
    photos: RegionPhotoIndex | None = None,
) -> dict[str, object]:
    payload = policy_to_api(policy, photos=photos)
    payload.update(
        {
            "id": alias_area.slug,
            "slug": alias_area.slug,
            "label": alias_area.sido[:2],
            "title": stay_discount_aliases.alias_title(policy.title, alias_area),
            "region": alias_area.sido,
            "category": "숙박",
            "sourceType": "external",
        }
    )
    # region을 alias sido로 덮어썼으므로 canonical 사진이 남지 않게 재계산한다.
    payload.pop("photo", None)
    _attach_region_photo(payload, photos, alias_area.sido, None)
    stay_discount_aliases.apply_alias_structured_detail(payload, alias_area)
    payload.pop("actionStatus", None)
    return payload


def _policy_detail_with_alias(
    policy: PolicyModel,
    alias_area: stay_discount_aliases.StayDiscountAliasArea,
    *,
    photos: RegionPhotoIndex | None = None,
) -> dict[str, object]:
    payload = policy_to_api(policy, photos=photos)
    payload["id"] = alias_area.slug
    payload["slug"] = alias_area.slug
    payload["title"] = stay_discount_aliases.alias_title(policy.title, alias_area)
    payload["region"] = alias_area.sido
    payload["category"] = "숙박"
    # region을 alias sido로 덮어썼으므로 canonical 사진이 남지 않게 재계산한다.
    payload.pop("photo", None)
    _attach_region_photo(payload, photos, alias_area.sido, None)
    stay_discount_aliases.apply_alias_structured_detail(payload, alias_area)
    payload.pop("actionStatus", None)
    return payload


def external_policy_slug(record: ExternalSourceRecord) -> str:
    if record.source_category == dgtour_identity.SOURCE_CATEGORY:
        canonical_slug = dgtour_identity.canonical_policy_slug_for_city(record.city)
        if canonical_slug:
            return canonical_slug
    return f"{external_source_repository.EXTERNAL_POLICY_SLUG_PREFIX}{record.id}"


def _external_policy_label(record: ExternalSourceRecord) -> str:
    region = record.region or ("전국" if record.is_nationwide else "")
    if region:
        return region[:2]
    return "공식"


def external_source_record_to_policy_api(
    record: ExternalSourceRecord,
    *,
    photos: RegionPhotoIndex | None = None,
    islands: EligibleIslandSummary | None = None,
) -> dict[str, object]:
    amount = record.benefit_value_text or record.benefit_text or "혜택 확인 필요"
    category = _external_policy_category(record)
    tag = record.benefit_value_text or record.benefit_text or category
    summary_parts = [
        value
        for value in [record.benefit_text, record.raw_detail_text]
        if value
    ]
    summary = summary_parts[0] if summary_parts else "공식 혜택 안내를 확인해 주세요."
    if len(summary) > 180:
        summary = f"{summary[:177].rstrip()}..."

    title = local_half_trip_display.policy_title(
        record.title,
        record.source_category,
        record.city,
    )
    default_year = (
        record.last_fetched_at.year if record.last_fetched_at is not None else 2026
    )
    raw_payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    representative_deadline = representative_deadline_from_payload(
        raw_payload,
        default_year=default_year,
    )
    semantic_mapping = map_external_source_semantics(record)
    structured_detail = semantic_mapping.structured_detail
    conditions = structured_detail["applicationTarget"]
    requirements = [
        str(item["description"])
        for item in conditions
        if item.get("description")
    ]
    if record.source_category == "local_half_trip" and not requirements:
        requirements = ["공식 혜택 안내에서 조건을 확인하세요."]

    payload = {
        "id": external_policy_slug(record),
        "slug": external_policy_slug(record),
        "label": _external_policy_label(record),
        "tag": tag,
        "title": title,
        "org": record.organizer_text or record.source_name,
        "region": record.region or "전국",
        "startDate": representative_deadline.start_date.isoformat()
        if representative_deadline.start_date
        else None,
        "deadline": representative_deadline.deadline.isoformat()
        if representative_deadline.deadline
        else "",
        "amount": amount,
        "summary": summary,
        "match": 80,
        "category": category,
        "requirements": requirements,
        "documents": [],
        "structuredDetail": structured_detail if any(structured_detail.values()) else None,
        **policy_url_fields(
            apply_url=None,
            official_url=record.detail_url or record.collected_page_url,
        ),
        "sourceType": api_policy_source_type(
            source_type="external",
            external_source_record_id=record.id,
        ),
        "actionStatus": "infoOnly",
    }
    _attach_region_photo(payload, photos, record.region, record.city)
    _attach_eligible_islands(payload, islands, record.source_category)
    if record.source_category == stay_discount_aliases.SOURCE_CATEGORY:
        stay_discount_aliases.apply_detail_display_fields(payload)
    return payload


def list_policies(db: Session | None = None) -> list[dict[str, object]]:
    if db is None:
        raise RuntimeError("DB session is required.")
    photos = build_region_photo_index(db)
    islands = build_eligible_island_summary(db)
    return [
        policy_to_api(policy, photos=photos, islands=islands)
        for policy in policy_repository.list_policies(db)
    ]


def get_policy(
    policy_slug: str,
    db: Session | None = None,
    *,
    today: date | None = None,
) -> dict[str, object] | None:
    if db is None:
        raise RuntimeError("DB session is required.")

    photos = build_region_photo_index(db)
    islands = build_eligible_island_summary(db)
    policy = policy_repository.get_policy_by_slug_any_status(db, policy_slug)
    if policy is not None:
        if is_public_policy(policy, today=today):
            return policy_to_api(policy, photos=photos, islands=islands)
        digital_alias_policy = digital_tourism_policy_aliases.resolve_digital_tourism_alias_slug(
            db,
            policy_slug,
        )
        if digital_alias_policy is not None and is_public_policy(
            digital_alias_policy,
            today=today,
        ):
            return policy_to_api(digital_alias_policy, photos=photos)
        return None

    digital_alias_policy = digital_tourism_policy_aliases.resolve_digital_tourism_alias_slug(
        db,
        policy_slug,
    )
    if digital_alias_policy is not None:
        if not is_public_policy(digital_alias_policy, today=today):
            return None
        return policy_to_api(digital_alias_policy, photos=photos)

    alias_resolution = stay_discount_aliases.resolve_stay_discount_alias_slug(db, policy_slug)
    if alias_resolution is not None:
        policy = alias_resolution.canonical_policy
        if not is_public_policy(policy, today=today):
            return None
        if alias_resolution.alias_area is None:
            return policy_to_api(policy, photos=photos)
        return _policy_detail_with_alias(
            policy, alias_resolution.alias_area, photos=photos
        )

    external_record = external_source_repository.get_external_source_record_by_policy_slug(
        db,
        policy_slug,
        today=today,
    )
    if external_record is None:
        return None
    return external_source_record_to_policy_api(external_record, photos=photos, islands=islands)


def save_policy(
    policy_slug: str,
    db: Session | None = None,
    user: User | None = None,
    *,
    today: date | None = None,
) -> dict[str, object] | None:
    if db is None:
        raise RuntimeError("DB session is required.")
    if user is None:
        raise RuntimeError("User is required.")

    policy = (
        policy_repository.get_policy_by_slug(db, policy_slug)
        or digital_tourism_policy_aliases.resolve_digital_tourism_alias_slug(db, policy_slug)
    )
    if policy is None:
        alias_resolution = stay_discount_aliases.resolve_stay_discount_alias_slug(db, policy_slug)
        policy = alias_resolution.canonical_policy if alias_resolution is not None else None
    if policy is not None and not is_public_policy(policy, today=today):
        policy = None
    if policy is None:
        return None

    existing = policy_repository.get_saved_policy(
        db,
        user_id=user.id,
        policy_id=policy.id,
    )
    if existing is None:
        policy_repository.add_saved_policy(
            db,
            user_id=user.id,
            policy_id=policy.id,
        )
        db.commit()

    return {
        "policyId": policy_slug,
        "saved": True,
    }


def list_saved_policies(
    db: Session | None = None,
    user: User | None = None,
) -> list[dict[str, object]]:
    if db is None:
        raise RuntimeError("DB session is required.")
    if user is None:
        raise RuntimeError("User is required.")

    photos = build_region_photo_index(db)
    islands = build_eligible_island_summary(db)
    seen_slugs: set[str] = set()
    saved_policies: list[dict[str, object]] = []
    for policy in policy_repository.list_saved_policies(db, user_id=user.id):
        policy_payload = policy_to_api(policy, photos=photos, islands=islands)
        slug = str(policy_payload["slug"])
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)
        saved_policies.append(policy_payload)
    return saved_policies


def list_applied_policies(
    db: Session | None = None,
    user: User | None = None,
) -> list[dict[str, object]]:
    if db is None:
        raise RuntimeError("DB session is required.")
    if user is None:
        raise RuntimeError("User is required.")

    photos = build_region_photo_index(db)
    islands = build_eligible_island_summary(db)
    return [
        policy_to_api(policy, photos=photos, islands=islands)
        for policy in policy_repository.list_applied_policies(db, user_id=user.id)
    ]


def list_applied_policy_links(
    db: Session | None = None,
    user: User | None = None,
) -> list[dict[str, object]]:
    if db is None:
        raise RuntimeError("DB session is required.")
    if user is None:
        raise RuntimeError("User is required.")

    photos = build_region_photo_index(db)
    islands = build_eligible_island_summary(db)
    on = island_application.today()
    grouped: dict[int, dict[str, object]] = {}
    for link in policy_repository.list_applied_policy_links(db, user_id=user.id, today=on):
        policy = link.policy
        trip = link.trip
        if policy is None or trip is None:
            continue
        if not is_public_policy(policy, today=on) and island_application.active_guide(policy, on=on) is None:
            continue
        if policy.id not in grouped:
            grouped[policy.id] = {
                "policy": policy_to_api(policy, photos=photos, islands=islands),
                "linkedTrips": [],
            }
        linked_trips = grouped[policy.id]["linkedTrips"]
        assert isinstance(linked_trips, list)
        linked_trips.append(
            {
                "id": str(trip.id),
                "title": trip.title,
                "region": trip.region or "",
                "startDate": trip.start_date.isoformat() if trip.start_date else None,
                "endDate": trip.end_date.isoformat() if trip.end_date else None,
                "applicationStatus": link.application_status,
            }
        )
    return list(grouped.values())


def remove_saved_policy(
    policy_slug: str,
    db: Session | None = None,
    user: User | None = None,
    *,
    today: date | None = None,
) -> dict[str, object] | None:
    if db is None:
        raise RuntimeError("DB session is required.")
    if user is None:
        raise RuntimeError("User is required.")

    policy = (
        policy_repository.get_policy_by_slug(db, policy_slug)
        or digital_tourism_policy_aliases.resolve_digital_tourism_alias_slug(db, policy_slug)
    )
    if policy is None:
        alias_resolution = stay_discount_aliases.resolve_stay_discount_alias_slug(db, policy_slug)
        policy = alias_resolution.canonical_policy if alias_resolution is not None else None
    if policy is not None and not is_public_policy(policy, today=today):
        policy = None
    if policy is None:
        return None

    policy_repository.remove_saved_policy(
        db,
        user_id=user.id,
        policy_id=policy.id,
    )
    db.commit()
    return {
        "policyId": policy_slug,
        "saved": False,
    }
