from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.security import hash_password
from app.data import seed
from app.db.session import get_session_factory
from app.models import (
    Policy,
    PolicyDocument,
    NotificationDelivery,
    Recommendation,
    Trip,
    TripDay,
    TripInvite,
    TripMember,
    TripPlace,
    TripPolicy,
    User,
    UserSavedPolicy,
)


LEGACY_DUMMY_POLICY_SLUGS = {"local-vacation", "sokcho-stay", "busan-cashback"}
BENEFIT_AMOUNTS: dict[str, int | None] = {}


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def parse_time(value: str | None) -> time | None:
    if not value:
        return None
    return time.fromisoformat(value)


def get_or_create_user(db: Session, *, email: str, nickname: str, **values: Any) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, nickname=nickname, **values)
        db.add(user)
        db.flush()
        return user

    user.nickname = nickname
    for key, value in values.items():
        setattr(user, key, value)
    return user


def seed_users(db: Session) -> dict[str, User]:
    main_user = get_or_create_user(
        db,
        email=str(seed.USER["email"]),
        nickname=str(seed.USER["nickname"]),
        password_hash=hash_password("password123"),
        preferred_regions=seed.USER["preferredRegions"],
        travel_style=seed.USER["travelStyle"],
        travel_budget=seed.USER["travelBudget"],
        onboarding_completed=bool(seed.USER["onboardingCompleted"]),
        created_at=parse_datetime(str(seed.USER["createdAt"])),
        updated_at=parse_datetime(str(seed.USER["updatedAt"])),
    )

    companions = {
        "민서": get_or_create_user(db, email="minseo@travel.kr", nickname="민서"),
        "현우": get_or_create_user(db, email="hyunwoo@travel.kr", nickname="현우"),
    }
    return {str(seed.USER["nickname"]): main_user, **companions}


def seed_policies(db: Session) -> dict[str, Policy]:
    legacy_policy_ids = db.scalars(
        select(Policy.id).where(Policy.slug.in_(LEGACY_DUMMY_POLICY_SLUGS))
    ).all()
    if legacy_policy_ids:
        for model in (TripPolicy, UserSavedPolicy, NotificationDelivery, PolicyDocument):
            db.execute(delete(model).where(model.policy_id.in_(legacy_policy_ids)))
        db.execute(delete(Policy).where(Policy.id.in_(legacy_policy_ids)))
        db.flush()

    seed_policy_items = list(seed.POLICIES)
    active_seed_slugs = {str(item["slug"]) for item in seed_policy_items}
    _cleanup_legacy_dgtour_policies(db, active_seed_slugs)

    policies: dict[str, Policy] = {}
    for item in seed_policy_items:
        slug = str(item["slug"])
        policy = db.scalar(select(Policy).where(Policy.slug == slug))
        if policy is None:
            policy = Policy(slug=slug)
            db.add(policy)

        policy.title = str(item["title"])
        policy.organization = str(item["org"])
        policy.policy_type = str(item["category"])
        policy.description = str(item["summary"])
        policy.benefit_amount = BENEFIT_AMOUNTS.get(slug)
        policy.benefit_detail = str(item["amount"])
        policy.target_condition = "\n".join(str(value) for value in item["requirements"])
        policy.region = str(item["region"])
        policy.end_date = parse_date(str(item["deadline"]))
        policy.official_url = item.get("officialUrl")
        policy.apply_url = item.get("applyUrl")
        policy.status = str(item.get("status") or "active")
        policy.source_name = item.get("sourceName")
        policy.source_category = item.get("sourceCategory")
        policy.source_url = item.get("sourceUrl")
        policy.source_canonical_key = item.get("sourceCanonicalKey")
        policy.policy_comment = str(item["summary"])
        policy.policy_period = f"~ {item['deadline']}"
        db.flush()

        policy.documents = [
            PolicyDocument(document_name=str(document_name))
            for document_name in item["documents"]
        ]
        policies[slug] = policy

    db.flush()
    return policies


def _policy_has_links(policy: Policy) -> bool:
    return bool(policy.user_saves or policy.trip_links or policy.notification_deliveries)


def _cleanup_legacy_dgtour_policies(db: Session, active_seed_slugs: set[str]) -> None:
    legacy_policies = list(
        db.scalars(
            select(Policy)
            .options(
                selectinload(Policy.user_saves),
                selectinload(Policy.trip_links),
                selectinload(Policy.notification_deliveries),
            )
            .where(Policy.slug.like("dgtour-%"))
            .order_by(Policy.id)
        ).all()
    )
    for policy in legacy_policies:
        if policy.slug in active_seed_slugs:
            continue
        if _policy_has_links(policy):
            policy.status = "hidden"
        else:
            db.delete(policy)


def get_or_create_trip(db: Session, owner: User) -> Trip:
    start_date = date(2026, 6, 15)
    trip = db.scalar(
        select(Trip).where(
            Trip.owner_id == owner.id,
            Trip.title == seed.TRIP["title"],
            Trip.start_date == start_date,
        )
    )
    if trip is None:
        trip = Trip(owner_id=owner.id, title=str(seed.TRIP["title"]), start_date=start_date)
        db.add(trip)

    trip.end_date = date(2026, 6, 17)
    trip.status = "confirmed"
    trip.region = "제주"
    trip.description = "휴식 중심 여행"
    db.flush()
    return trip


def seed_trip_days_and_places(db: Session, trip: Trip) -> None:
    start_date = trip.start_date
    for day_number, places in seed.TRIP["days"].items():
        trip_day_date = start_date + timedelta(days=int(day_number) - 1)
        trip_day = db.scalar(
            select(TripDay).where(
                TripDay.trip_id == trip.id,
                TripDay.day_number == int(day_number),
            )
        )
        if trip_day is None:
            trip_day = TripDay(
                trip_id=trip.id,
                day_number=int(day_number),
                date=trip_day_date,
            )
            db.add(trip_day)
        else:
            trip_day.date = trip_day_date
        db.flush()

        for order_num, place in enumerate(places, start=1):
            place_name = str(place["label"])
            trip_place = db.scalar(
                select(TripPlace).where(
                    TripPlace.trip_day_id == trip_day.id,
                    TripPlace.order_num == order_num,
                )
            )
            if trip_place is None:
                trip_place = TripPlace(trip_day_id=trip_day.id, order_num=order_num)
                db.add(trip_place)

            trip_place.place_name = place_name
            trip_place.visit_time = parse_time(str(place["time"]))
            trip_place.memo = str(place["meta"])


def seed_trip_members(db: Session, trip: Trip, users_by_name: dict[str, User]) -> None:
    for person in seed.TRIP["people"]:
        user = users_by_name[str(person)]
        membership = db.scalar(
            select(TripMember).where(
                TripMember.trip_id == trip.id,
                TripMember.user_id == user.id,
            )
        )
        if membership is None:
            membership = TripMember(trip_id=trip.id, user_id=user.id)
            db.add(membership)
        membership.role = "owner" if user.id == trip.owner_id else "editor"


def seed_trip_policy(db: Session, trip: Trip, policy: Policy) -> None:
    existing = db.scalar(
        select(TripPolicy).where(
            TripPolicy.trip_id == trip.id,
            TripPolicy.policy_id == policy.id,
        )
    )
    if existing is None:
        db.add(TripPolicy(trip_id=trip.id, policy_id=policy.id))


def seed_trip_invite(db: Session, trip: Trip, creator: User) -> None:
    invite = db.scalar(
        select(TripInvite).where(TripInvite.invite_token == seed.INVITE_TOKEN)
    )
    if invite is None:
        invite = TripInvite(invite_token=seed.INVITE_TOKEN)
        db.add(invite)

    invite.trip_id = trip.id
    invite.created_by = creator.id
    invite.role = "editor"
    invite.accepted_at = None
    invite.created_at = parse_datetime(seed.INVITE_CREATED_AT)
    invite.expires_at = parse_datetime(seed.INVITE_EXPIRES_AT)


def seed_recommendations(db: Session, user: User, trip: Trip) -> None:
    query = "제주 3일 여행 추천"
    recommendation = db.scalar(
        select(Recommendation).where(
            Recommendation.user_id == user.id,
            Recommendation.trip_id == trip.id,
            Recommendation.query == query,
        )
    )
    if recommendation is None:
        recommendation = Recommendation(user_id=user.id, trip_id=trip.id, query=query)
        db.add(recommendation)
    recommendation.result = seed.RECOMMENDATIONS


def seed_dev_data(db: Session) -> None:
    users_by_name = seed_users(db)
    policies = seed_policies(db)
    main_user = users_by_name[str(seed.USER["nickname"])]
    trip = get_or_create_trip(db, main_user)
    seed_trip_days_and_places(db, trip)
    seed_trip_members(db, trip, users_by_name)
    first_policy = next(
        (policy for policy in policies.values() if policy.status == "active"),
        None,
    )
    if first_policy is not None:
        seed_trip_policy(db, trip, first_policy)
    seed_trip_invite(db, trip, main_user)
    seed_recommendations(db, main_user, trip)


def main() -> None:
    session_factory = get_session_factory()
    with session_factory() as db:
        seed_dev_data(db)
        db.commit()
    print("Travel Hunter development seed data applied.")


if __name__ == "__main__":
    main()
