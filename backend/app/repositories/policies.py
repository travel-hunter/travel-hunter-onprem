from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.policy_status import POLICY_STATUS_ACTIVE
from app.models import Policy, Trip, TripMember, TripPolicy, UserSavedPolicy


def _active_policy_clause():
    return Policy.status == POLICY_STATUS_ACTIVE


def list_policies(db: Session) -> list[Policy]:
    statement = (
        select(Policy)
        .options(selectinload(Policy.documents))
        .where(_active_policy_clause())
        .order_by(Policy.id)
    )
    return list(db.scalars(statement).all())


def get_policy_by_slug(db: Session, policy_slug: str) -> Policy | None:
    statement = (
        select(Policy)
        .options(selectinload(Policy.documents))
        .where(Policy.slug == policy_slug, _active_policy_clause())
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


def list_saved_policies(db: Session, *, user_id: int) -> list[Policy]:
    statement = (
        select(UserSavedPolicy)
        .join(UserSavedPolicy.policy)
        .options(selectinload(UserSavedPolicy.policy).selectinload(Policy.documents))
        .where(UserSavedPolicy.user_id == user_id)
        .where(_active_policy_clause())
        .order_by(UserSavedPolicy.saved_at.desc(), UserSavedPolicy.id.desc())
    )
    saved_rows = list(db.scalars(statement).all())
    return [row.policy for row in saved_rows]


def list_applied_policies(db: Session, *, user_id: int) -> list[Policy]:
    statement = (
        select(Policy)
        .join(TripPolicy, TripPolicy.policy_id == Policy.id)
        .join(Trip, Trip.id == TripPolicy.trip_id)
        .options(selectinload(Policy.documents))
        .where(
            (Trip.owner_id == user_id)
            | (Trip.members.any(TripMember.user_id == user_id))
        )
        .where(_active_policy_clause())
        .distinct()
        .order_by(Policy.id)
    )
    return list(db.scalars(statement).all())


def list_applied_policy_links(db: Session, *, user_id: int) -> list[TripPolicy]:
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
        .where(_active_policy_clause())
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
