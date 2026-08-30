from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Policy
from app.models.policy_status import POLICY_STATUS_ACTIVE
from app.repositories import external_sources as external_source_repository
from app.services import digital_tourism_resident_card as dgtour_identity


def _policy_for_city(
    db: Session,
    city: str,
    *,
    active_only: bool = True,
) -> Policy | None:
    canonical_slug = dgtour_identity.canonical_policy_slug_for_city(city)
    canonical_key = dgtour_identity.canonical_key_for_city(city)
    statement = (
        select(Policy)
        .where(
            Policy.source_category == dgtour_identity.SOURCE_CATEGORY,
            Policy.source_canonical_key == canonical_key,
        )
        .order_by(Policy.id)
    )
    if active_only:
        statement = statement.where(Policy.status == POLICY_STATUS_ACTIVE)
    candidates = list(db.scalars(statement).all())
    if not candidates:
        return None
    if canonical_slug:
        for policy in candidates:
            if policy.slug == canonical_slug:
                return policy
    return candidates[0]


def resolve_digital_tourism_alias_slug(
    db: Session,
    policy_slug: str,
    *,
    active_only: bool = True,
) -> Policy | None:
    city = dgtour_identity.city_from_policy_slug(policy_slug)
    if city:
        return _policy_for_city(db, city, active_only=active_only)

    external_record = external_source_repository.get_external_source_record_by_policy_slug(
        db,
        policy_slug,
    )
    if external_record is None or external_record.source_category != dgtour_identity.SOURCE_CATEGORY:
        return None
    return _policy_for_city(db, external_record.city or "", active_only=active_only)
