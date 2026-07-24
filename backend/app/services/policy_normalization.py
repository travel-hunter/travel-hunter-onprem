from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, object_session

from app.models import ExternalSourceRecord, Policy
from app.repositories import external_sources as external_source_repository
from app.services.policies import _external_policy_category
from app.services import digital_tourism_resident_card as dgtour_identity
from app.services.legacy_dgtour_reconciliation import frozen_legacy_dgtour_slugs
from app.services.policy_periods import (
    PeriodEvidence,
    RepresentativeDeadlineDecision,
    evidence_from_payload,
    select_representative_deadline,
)
from app.services.policy_semantic_mapping import map_external_source_semantics
from app.services.travelmonth_normalizer import extract_benefit_value


logger = logging.getLogger(__name__)
STAY_DISCOUNT_SOURCE_CATEGORY = "stay_discount"
DIGITAL_TOURISM_SOURCE_CATEGORY = dgtour_identity.SOURCE_CATEGORY


@dataclass(frozen=True)
class PolicyPromotionResult:
    promoted_count: int


class PolicyNormalizationError(RuntimeError):
    """Raised when source-to-policy identity cannot be resolved safely."""


def _period_evidence_for_record(record: ExternalSourceRecord) -> list[PeriodEvidence]:
    fetched_at = record.last_fetched_at
    default_year = fetched_at.year if fetched_at is not None else 2026
    return evidence_from_payload(
        record.raw_payload if isinstance(record.raw_payload, dict) else {},
        default_year=default_year,
        source=record.source_category,
    )


def _representative_deadline_for_record(
    record: ExternalSourceRecord,
) -> RepresentativeDeadlineDecision:
    return select_representative_deadline(_period_evidence_for_record(record))


def _policy_slug_for_external_record(record: ExternalSourceRecord) -> str:
    return f"{external_source_repository.EXTERNAL_POLICY_SLUG_PREFIX}{record.id}"


def _official_url_for_external_record(record: ExternalSourceRecord) -> str | None:
    if record.source_category == DIGITAL_TOURISM_SOURCE_CATEGORY:
        return dgtour_identity.official_url_for_city(record.city, record.detail_url)
    return record.detail_url or record.collected_page_url


def _source_url_for_external_record(record: ExternalSourceRecord) -> str | None:
    if record.source_category == DIGITAL_TOURISM_SOURCE_CATEGORY:
        return dgtour_identity.official_url_for_city(record.city, record.detail_url)
    return record.detail_url or record.collected_page_url or record.source_url


def _digital_tourism_city(record: ExternalSourceRecord) -> str:
    return dgtour_identity.display_city_name(record.city) or dgtour_identity.city_from_title(
        record.title or ""
    )


def _digital_tourism_existing_policy_condition(record: ExternalSourceRecord):
    city = _digital_tourism_city(record)
    city_conditions = []
    if city:
        city_conditions.extend(
            [
                Policy.title.ilike(f"%[{city}]%"),
                Policy.title.ilike(f"%{city}%디지털관광주민증%"),
                Policy.source_canonical_key == dgtour_identity.canonical_key_for_city(city),
            ]
        )
    if not city_conditions:
        city_conditions.append(Policy.source_canonical_key == record.canonical_key)
    statement_condition = [
        Policy.status != "hidden",
        Policy.source_category == DIGITAL_TOURISM_SOURCE_CATEGORY,
        Policy.external_source_record_id.is_(None),
        or_(*city_conditions),
    ]
    if record.region:
        statement_condition.append(Policy.region == record.region)
    return and_(*statement_condition)


def _get_policy_for_external_record(
    db: Session,
    record: ExternalSourceRecord,
    *,
    match_stay_logical_campaign: bool = False,
) -> Policy | None:
    if (
        match_stay_logical_campaign
        and record.source_category == STAY_DISCOUNT_SOURCE_CATEGORY
        and record.logical_key is not None
    ):
        logical_campaign_matches = list(
            db.scalars(
                select(Policy)
                .join(
                    ExternalSourceRecord,
                    Policy.external_source_record_id == ExternalSourceRecord.id,
                )
                .where(
                    Policy.source_category == STAY_DISCOUNT_SOURCE_CATEGORY,
                    Policy.status != "hidden",
                    ExternalSourceRecord.logical_key == record.logical_key,
                )
                .order_by(Policy.id)
            ).all()
        )
        if len(logical_campaign_matches) > 1:
            raise PolicyNormalizationError(
                "multiple active policies match stay logical campaign: "
                f"{record.logical_key}"
            )
        if logical_campaign_matches:
            return logical_campaign_matches[0]
    if record.source_category == DIGITAL_TOURISM_SOURCE_CATEGORY and record.logical_key is not None:
        logical_matches = list(
            db.scalars(
                select(Policy)
                .join(
                    ExternalSourceRecord,
                    Policy.external_source_record_id == ExternalSourceRecord.id,
                    isouter=True,
                )
                .where(
                    Policy.status != "hidden",
                    Policy.source_category == DIGITAL_TOURISM_SOURCE_CATEGORY,
                    ExternalSourceRecord.logical_key == record.logical_key,
                )
                .order_by(Policy.id)
            ).all()
        )
        if len(logical_matches) > 1:
            raise PolicyNormalizationError(
                "multiple active policies match digital tourism logical key: "
                f"{record.logical_key}"
            )
        if logical_matches:
            return logical_matches[0]
        unlinked_seed_matches = list(
            db.scalars(
                select(Policy)
                .where(_digital_tourism_existing_policy_condition(record))
                .order_by(Policy.id)
            ).all()
        )
        if len(unlinked_seed_matches) > 1:
            raise PolicyNormalizationError(
                "multiple active policies match digital tourism municipality: "
                f"{record.logical_key}"
            )
        if unlinked_seed_matches:
            return unlinked_seed_matches[0]
    if record.id is not None:
        by_source_record = db.scalar(
            select(Policy).where(Policy.external_source_record_id == record.id)
        )
        if by_source_record is not None:
            return by_source_record
    return db.scalar(
        select(Policy).where(
            Policy.slug == _policy_slug_for_external_record(record),
            Policy.status != "hidden",
            Policy.external_source_record_id.is_(None),
        )
    )


def _assign_policy_from_external_record(
    policy: Policy,
    record: ExternalSourceRecord,
) -> Policy:
    if policy.slug in frozen_legacy_dgtour_slugs() and record.source_category != DIGITAL_TOURISM_SOURCE_CATEGORY:
        return policy
    semantic_mapping = map_external_source_semantics(record)
    policy.status = semantic_mapping.policy_status or "active"
    if getattr(policy, "admin_override_enabled", False) is True:
        policy.source_type = record.source_type
        policy.source_name = record.source_name
        policy.source_category = record.source_category
        policy.external_source_record_id = record.id
        policy.source_url = _source_url_for_external_record(record)
        policy.source_canonical_key = record.canonical_key
        policy.normalized_at = record.last_fetched_at
        policy.last_verified_at = record.last_verified_at
        policy.verification_status = record.freshness_status
        return policy

    benefit_value = extract_benefit_value(record.benefit_text or "", title=record.title)
    benefit_detail = record.benefit_value_text or benefit_value.value_text or record.benefit_text
    if not policy.slug:
        policy.slug = _policy_slug_for_external_record(record)
    policy.title = record.title
    policy.organization = record.organizer_text or record.source_name
    policy.policy_type = _external_policy_category(record)
    policy.description = record.raw_detail_text or record.benefit_text
    policy.benefit_amount = record.extracted_amount_krw or benefit_value.amount_krw
    policy.benefit_detail = benefit_detail
    policy.target_condition = semantic_mapping.target_condition
    policy.region = record.region or "전국"
    representative_deadline = _representative_deadline_for_record(record)
    policy.start_date = representative_deadline.start_date
    policy.end_date = representative_deadline.deadline
    policy.official_url = _official_url_for_external_record(record)
    policy.apply_url = None
    policy.policy_comment = record.benefit_text[:300] if record.benefit_text else None
    policy.policy_period = None
    policy.source_type = record.source_type
    policy.source_name = record.source_name
    policy.source_category = record.source_category
    policy.external_source_record_id = record.id
    policy.source_url = _source_url_for_external_record(record)
    policy.source_canonical_key = record.canonical_key
    policy.normalized_at = record.last_fetched_at
    policy.last_verified_at = record.last_verified_at
    policy.verification_status = semantic_mapping.verification_status or record.freshness_status
    policy.structured_detail = semantic_mapping.structured_detail
    if policy.source_category == DIGITAL_TOURISM_SOURCE_CATEGORY:
        _hide_duplicate_digital_tourism_policies(policy)
    identity = f"{record.source_category}:{record.canonical_key or record.external_id or record.id}"
    logger.info(
        "policy_semantic_mapping",
        extra={
            "source_category": record.source_category,
            "mapper_status": semantic_mapping.mapper_status,
            "record_identity_hash": hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16],
            "section_counts": {
                section: len(items)
                for section, items in policy.structured_detail.items()
            },
        },
    )
    return policy


def _hide_duplicate_digital_tourism_policies(policy: Policy) -> None:
    if policy.id is None or policy.source_category != DIGITAL_TOURISM_SOURCE_CATEGORY:
        return
    session = object_session(policy)
    if session is None:
        return
    city = dgtour_identity.city_from_title(policy.title or "")
    if not city:
        return
    duplicates = list(
        session.scalars(
            select(Policy)
            .where(
                Policy.id != policy.id,
                Policy.status != "hidden",
                Policy.source_category == DIGITAL_TOURISM_SOURCE_CATEGORY,
                Policy.region == policy.region,
                or_(
                    Policy.title.ilike(f"%[{city}]%"),
                    Policy.title.ilike(f"%{city}%디지털관광주민증%"),
                    Policy.source_canonical_key == f"digital-tourism-resident-card:{policy.region}:{city}",
                ),
            )
            .order_by(Policy.id)
        ).all()
    )
    for duplicate in duplicates:
        duplicate.status = "hidden"


def _hide_policy_for_external_record(
    db: Session,
    record: ExternalSourceRecord,
) -> bool:
    policy = None
    if record.id is not None:
        policy = db.scalar(
            select(Policy).where(Policy.external_source_record_id == record.id)
        )
        if policy is None:
            policy = db.scalar(
                select(Policy).where(
                    Policy.slug == _policy_slug_for_external_record(record),
                    Policy.status != "hidden",
                    Policy.external_source_record_id.is_(None),
                )
            )
    record_is_nonparticipant_digital = (
        record.source_category == DIGITAL_TOURISM_SOURCE_CATEGORY
        and not dgtour_identity.is_participating_city(_digital_tourism_city(record))
    )
    if policy is None and (
        record.source_category != DIGITAL_TOURISM_SOURCE_CATEGORY
        or record_is_nonparticipant_digital
    ):
        policy = _get_policy_for_external_record(db, record)
    if policy is None:
        return False
    if policy.slug in frozen_legacy_dgtour_slugs() and not record_is_nonparticipant_digital:
        return False
    policy.status = "hidden"
    policy.source_type = record.source_type
    policy.source_name = record.source_name
    policy.source_category = record.source_category
    policy.external_source_record_id = record.id
    policy.source_url = _source_url_for_external_record(record)
    policy.source_canonical_key = record.canonical_key
    policy.normalized_at = record.last_fetched_at
    policy.last_verified_at = record.last_verified_at
    policy.verification_status = record.freshness_status
    return True


def promote_external_benefits_to_policies(db: Session) -> PolicyPromotionResult:
    records = external_source_repository.list_policy_promotion_records(db)
    resolved_stay_policies = {
        record: _get_policy_for_external_record(
            db,
            record,
            match_stay_logical_campaign=True,
        )
        for record in records
        if record.source_category == STAY_DISCOUNT_SOURCE_CATEGORY
        and record.logical_key is not None
    }
    resolved_digital_policies = {
        record: _get_policy_for_external_record(db, record)
        for record in records
        if record.source_category == DIGITAL_TOURISM_SOURCE_CATEGORY
        and record.logical_key is not None
    }
    promoted_count = 0
    promoted_categories: set[str] = set()
    for record in records:
        if record in resolved_stay_policies:
            policy = resolved_stay_policies[record]
        elif record in resolved_digital_policies:
            policy = resolved_digital_policies[record]
        else:
            policy = _get_policy_for_external_record(db, record)
        if policy is None:
            policy = Policy()
            db.add(policy)
        _assign_policy_from_external_record(policy, record)
        promoted_categories.add(record.source_category)
        promoted_count += 1
    for record in external_source_repository.list_policy_deactivation_records(db):
        _hide_policy_for_external_record(db, record)
    if "local_half_trip" in promoted_categories:
        _hide_legacy_dgtour_seed_policies(db)
    db.flush()
    return PolicyPromotionResult(promoted_count=promoted_count)


def _hide_legacy_dgtour_seed_policies(db: Session) -> None:
    frozen_slugs = frozen_legacy_dgtour_slugs()
    legacy_policies = db.scalars(
        select(Policy).where(Policy.slug.like("dgtour-%"))
    ).all()
    for policy in legacy_policies:
        if policy.slug in frozen_slugs:
            continue
        policy.status = "hidden"
