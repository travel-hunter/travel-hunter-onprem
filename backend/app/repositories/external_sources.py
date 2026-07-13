from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import and_, not_, or_, select
from sqlalchemy.orm import Session

from app.models import ExternalSourceRecord
from app.schemas.external_sources import ExternalBenefitSource


EXTERNAL_POLICY_SLUG_PREFIX = "travelmonth-"
POLICY_PROMOTION_SOURCE_CATEGORIES = (
    "local_half_trip",
    "stay_discount",
)
POLICY_DEACTIVATION_SOURCE_CATEGORIES = (
    *POLICY_PROMOTION_SOURCE_CATEGORIES,
    "regional_benefit",
    "traffic_benefit",
)
RECOMMENDATION_SOURCE_CATEGORIES = (
    "local_half_trip",
    "stay_discount",
)
LOCAL_HALF_TRIP_PUBLIC_STATUSES = ("active", "scheduled")
LOCAL_HALF_TRIP_PUBLIC_FRESHNESS_STATUSES = ("fresh", "unknown")


def _assign_record(
    record: ExternalSourceRecord,
    source: ExternalBenefitSource,
) -> ExternalSourceRecord:
    column_names = set(ExternalSourceRecord.__table__.columns.keys())
    for key, value in source.model_dump().items():
        if key in column_names:
            setattr(record, key, value)
    return record


def get_external_source_record(
    db: Session,
    *,
    source_name: str,
    source_category: str,
    canonical_key: str,
) -> ExternalSourceRecord | None:
    statement = select(ExternalSourceRecord).where(
        ExternalSourceRecord.source_name == source_name,
        ExternalSourceRecord.source_category == source_category,
        ExternalSourceRecord.canonical_key == canonical_key,
    )
    return db.scalar(statement)


def upsert_external_source_records(
    db: Session,
    sources: Iterable[ExternalBenefitSource],
) -> list[ExternalSourceRecord]:
    records: list[ExternalSourceRecord] = []
    for source in sources:
        record = get_external_source_record(
            db,
            source_name=source.source_name,
            source_category=source.source_category,
            canonical_key=source.canonical_key,
        )
        if record is None:
            record = ExternalSourceRecord()
            db.add(record)
        records.append(_assign_record(record, source))
    db.flush()
    return records


def list_external_source_records(
    db: Session,
    *,
    source_name: str,
    status: str | None = None,
    region: str | None = None,
) -> list[ExternalSourceRecord]:
    statement = select(ExternalSourceRecord).where(
        ExternalSourceRecord.source_name == source_name
    )
    if status is not None:
        statement = statement.where(ExternalSourceRecord.status == status)
    if region is not None:
        statement = statement.where(ExternalSourceRecord.region == region)
    statement = statement.order_by(ExternalSourceRecord.id)
    return list(db.scalars(statement).all())


def list_regional_benefit_recommendation_records(
    db: Session,
) -> list[ExternalSourceRecord]:
    statement = (
        select(ExternalSourceRecord)
        .where(ExternalSourceRecord.source_category.in_(RECOMMENDATION_SOURCE_CATEGORIES))
        .where(ExternalSourceRecord.status == "active")
        .where(ExternalSourceRecord.freshness_status == "fresh")
        .order_by(ExternalSourceRecord.id)
    )
    return list(db.scalars(statement).all())


def list_policy_promotion_records(
    db: Session,
) -> list[ExternalSourceRecord]:
    statement = (
        select(ExternalSourceRecord)
        .where(ExternalSourceRecord.source_category.in_(POLICY_PROMOTION_SOURCE_CATEGORIES))
        .where(_policy_public_condition())
        .order_by(ExternalSourceRecord.id)
    )
    return list(db.scalars(statement).all())


def list_policy_deactivation_records(
    db: Session,
) -> list[ExternalSourceRecord]:
    statement = (
        select(ExternalSourceRecord)
        .where(ExternalSourceRecord.source_category.in_(POLICY_DEACTIVATION_SOURCE_CATEGORIES))
        .where(
            or_(
                ExternalSourceRecord.source_category.not_in(POLICY_PROMOTION_SOURCE_CATEGORIES),
                not_(_policy_public_condition()),
            )
        )
        .order_by(ExternalSourceRecord.id)
    )
    return list(db.scalars(statement).all())


def _policy_public_condition():
    return or_(
        and_(
            ExternalSourceRecord.source_category == "local_half_trip",
            ExternalSourceRecord.status.in_(LOCAL_HALF_TRIP_PUBLIC_STATUSES),
            ExternalSourceRecord.freshness_status.in_(LOCAL_HALF_TRIP_PUBLIC_FRESHNESS_STATUSES),
        ),
        and_(
            ExternalSourceRecord.source_category == "stay_discount",
            ExternalSourceRecord.status == "active",
            ExternalSourceRecord.freshness_status == "fresh",
        ),
    )


def get_external_source_record_by_policy_slug(
    db: Session,
    policy_slug: str,
) -> ExternalSourceRecord | None:
    if not policy_slug.startswith(EXTERNAL_POLICY_SLUG_PREFIX):
        return None
    raw_id = policy_slug.removeprefix(EXTERNAL_POLICY_SLUG_PREFIX)
    if not raw_id.isdigit():
        return None
    statement = (
        select(ExternalSourceRecord)
        .where(ExternalSourceRecord.id == int(raw_id))
        .where(
            ExternalSourceRecord.source_category.in_(
                (
                    "local_half_trip",
                    "stay_discount",
                )
            )
        )
        .where(ExternalSourceRecord.status == "active")
        .where(ExternalSourceRecord.freshness_status == "fresh")
    )
    return db.scalar(statement)


def get_external_source_record_by_id(
    db: Session,
    record_id: int | None,
) -> ExternalSourceRecord | None:
    if record_id is None or not hasattr(db, "get"):
        return None
    return db.get(ExternalSourceRecord, record_id)


def list_external_source_records_by_category(
    db: Session,
    *,
    source_category: str,
) -> list[ExternalSourceRecord]:
    statement = (
        select(ExternalSourceRecord)
        .where(ExternalSourceRecord.source_category == source_category)
        .order_by(ExternalSourceRecord.id)
    )
    return list(db.scalars(statement).all())
