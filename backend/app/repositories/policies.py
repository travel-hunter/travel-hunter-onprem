from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.policy_status import POLICY_STATUS_ACTIVE, policy_visibility_date
from app.models import Policy, Trip, TripMember, TripPolicy, UserSavedPolicy


def _public_policy_clause(today: date | None = None):
    effective_today = today or policy_visibility_date()
    return and_(
        Policy.status == POLICY_STATUS_ACTIVE,
        or_(Policy.end_date.is_(None), Policy.end_date >= effective_today),
    )


def list_policies(db: Session, *, today: date | None = None) -> list[Policy]:
    statement = (
        select(Policy)
        .options(selectinload(Policy.documents))
        .where(_public_policy_clause(today))
        .order_by(Policy.id)
    )
    return list(db.scalars(statement).all())


def list_active_policies_for_photo_backfill(
    db: Session,
    *,
    today: date | None = None,
) -> list[Policy]:
    """Return the minimal, stable policy set used by the photo backfill job."""

    statement = select(Policy).where(_public_policy_clause(today)).order_by(Policy.id)
    return list(db.scalars(statement).all())


def get_policy_by_slug(
    db: Session,
    policy_slug: str,
    *,
    today: date | None = None,
) -> Policy | None:
    statement = (
        select(Policy)
        .options(selectinload(Policy.documents))
        .where(Policy.slug == policy_slug, _public_policy_clause(today))
    )
    return db.scalar(statement)


def get_policy_by_slug_any_status(db: Session, policy_slug: str) -> Policy | None:
    statement = (
        select(Policy)
        .options(selectinload(Policy.documents))
        .where(Policy.slug == policy_slug)
    )
    return db.scalar(statement)


def get_saved_policy(
    db: Session,
    *,
    user_id: int,
    policy_id: int,
) -> UserSavedPolicy | None:
    statement = select(UserSavedPolicy).where(
        UserSavedPolicy.user_id == user_id,
        UserSavedPolicy.policy_id == policy_id,
    )
    return db.scalar(statement)


def add_saved_policy(
    db: Session,
    *,
    user_id: int,
    policy_id: int,
) -> UserSavedPolicy:
    saved_policy = UserSavedPolicy(user_id=user_id, policy_id=policy_id)
    db.add(saved_policy)
    db.flush()
    return saved_policy


def list_saved_policies(
    db: Session,
    *,
    user_id: int,
    today: date | None = None,
) -> list[Policy]:
    statement = (
        select(UserSavedPolicy)
        .join(UserSavedPolicy.policy)
        .options(selectinload(UserSavedPolicy.policy).selectinload(Policy.documents))
        .where(UserSavedPolicy.user_id == user_id)
        .where(_public_policy_clause(today))
        .order_by(UserSavedPolicy.saved_at.desc(), UserSavedPolicy.id.desc())
    )
    saved_rows = list(db.scalars(statement).all())
    return [row.policy for row in saved_rows]


def list_applied_policies(
    db: Session,
    *,
    user_id: int,
    today: date | None = None,
) -> list[Policy]:
    statement = (
        select(Policy)
        .join(TripPolicy, TripPolicy.policy_id == Policy.id)
        .join(Trip, Trip.id == TripPolicy.trip_id)
        .options(selectinload(Policy.documents))
        .where(
            (Trip.owner_id == user_id)
            | (Trip.members.any(TripMember.user_id == user_id))
        )
        .where(_public_policy_clause(today))
        .distinct()
        .order_by(Policy.id)
    )
    return list(db.scalars(statement).all())


def list_applied_policy_links(
    db: Session,
    *,
    user_id: int,
    today: date | None = None,
) -> list[TripPolicy]:
    statement = (
        select(TripPolicy)
        .join(Policy, Policy.id == TripPolicy.policy_id)
        .join(Trip, Trip.id == TripPolicy.trip_id)
        .options(
            selectinload(TripPolicy.policy).selectinload(Policy.documents),
            selectinload(TripPolicy.trip),
        )
        .where(
            (Trip.owner_id == user_id)
            | (Trip.members.any(TripMember.user_id == user_id))
        )
        # Island support can outlive its card deadline on trips (travel and document steps); the service decides.
        .where(
            or_(
                _public_policy_clause(today),
                and_(Policy.status == POLICY_STATUS_ACTIVE, Policy.source_category == "island_visit"),
            )
        )
        .order_by(Policy.id, Trip.start_date, Trip.id)
    )
    return list(db.scalars(statement).all())


def remove_saved_policy(
    db: Session,
    *,
    user_id: int,
    policy_id: int,
) -> bool:
    saved_policy = get_saved_policy(db, user_id=user_id, policy_id=policy_id)
    if saved_policy is None:
        return False
    db.delete(saved_policy)
    db.flush()
    return True
