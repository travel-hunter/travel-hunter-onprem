from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Policy,
    Recommendation,
    Trip,
    TripDay,
    TripInvite,
    TripMember,
    TripPlace,
    TripPolicy,
)


def _trip_options():
    return (
        selectinload(Trip.days).selectinload(TripDay.places),
        selectinload(Trip.owner),
        selectinload(Trip.members).selectinload(TripMember.user),
        selectinload(Trip.policies).selectinload(TripPolicy.policy),
        selectinload(Trip.invites),
        selectinload(Trip.recommendations),
    )


def _accessible_trip_filter(user_id: int):
    return or_(Trip.owner_id == user_id, Trip.members.any(TripMember.user_id == user_id))


def list_accessible_trips(db: Session, user_id: int) -> list[Trip]:
    statement = (
        select(Trip)
        .options(*_trip_options())
        .where(_accessible_trip_filter(user_id))
        .order_by(Trip.start_date, Trip.id)
    )
    return list(db.scalars(statement).all())


def get_accessible_trip_by_id(db: Session, trip_id: int, user_id: int) -> Trip | None:
    statement = (
        select(Trip)
        .options(*_trip_options())
        .where(Trip.id == trip_id)
        .where(_accessible_trip_filter(user_id))
    )
    return db.scalar(statement)


def get_owned_trip_by_id(db: Session, trip_id: int, user_id: int) -> Trip | None:
    statement = select(Trip).where(Trip.id == trip_id, Trip.owner_id == user_id)
    return db.scalar(statement)


def create_trip(
    db: Session,
    *,
    owner_id: int,
    title: str,
    start_date: date,
    end_date: date,
    status: str,
    region: str | None,
    travel_area_id: str | None,
    participant_count: int,
    description: str | None,
) -> Trip:
    trip = Trip(
        owner_id=owner_id,
        title=title,
        start_date=start_date,
        end_date=end_date,
        status=status,
        region=region,
        travel_area_id=travel_area_id,
        participant_count=participant_count,
        description=description,
    )
    db.add(trip)
    db.flush()
    return trip


def add_trip_day(db: Session, *, trip_id: int, day_number: int, date_value: date) -> TripDay:
    trip_day = TripDay(trip_id=trip_id, day_number=day_number, date=date_value)
    db.add(trip_day)
    db.flush()
    return trip_day


def add_trip_place(
    db: Session,
    *,
    trip_day_id: int,
    place_name: str,
    visit_time,
    order_num: int,
    memo: str | None,
    address: str | None = None,
    latitude = None,
    longitude = None,
    source_provider: str | None = None,
    external_place_id: str | None = None,
    category_group_code: str | None = None,
    category_group_name: str | None = None,
    place_url: str | None = None,
) -> TripPlace:
    place = TripPlace(
        trip_day_id=trip_day_id,
        place_name=place_name,
        address=address,
        latitude=latitude,
        longitude=longitude,
        visit_time=visit_time,
        order_num=order_num,
        memo=memo,
        source_provider=source_provider,
        external_place_id=external_place_id,
        category_group_code=category_group_code,
        category_group_name=category_group_name,
        place_url=place_url,
    )
    db.add(place)
    db.flush()
    return place


def bump_trip_revision_if_current(db: Session, *, trip_id: int, expected_revision: int) -> bool:
    result = db.execute(
        update(Trip)
        .where(Trip.id == trip_id)
        .where(Trip.revision == expected_revision)
        .values(revision=Trip.revision + 1)
        .execution_options(synchronize_session=False)
    )
    return (result.rowcount or 0) == 1


def add_trip_member(db: Session, *, trip_id: int, user_id: int, role: str) -> TripMember:
    membership = TripMember(trip_id=trip_id, user_id=user_id, role=role)
    db.add(membership)
    return membership


def get_trip_member(db: Session, *, trip_id: int, user_id: int) -> TripMember | None:
    statement = select(TripMember).where(
        TripMember.trip_id == trip_id,
        TripMember.user_id == user_id,
    )
    return db.scalar(statement)


def lock_trip_row(db: Session, *, trip_id: int) -> None:
    """Trip 기본 행만 FOR UPDATE 로 잠근다.

    정책 연결은 확인 후 삽입 구조라, 잠금이 없으면 서로 다른 숙박세일 정책을
    동시에 요청했을 때 두 요청이 모두 "기존 없음"을 보고 각각 삽입한다.
    DB 제약도 (trip_id, policy_id) 뿐이라 이를 막지 못한다.

    접근 권한 조회는 eager-load 가 섞여 있어 잠금 대상으로 쓰기에 위험하다.
    관계를 건드리지 않는 최소 조회로 잠근다. SQLite 는 FOR UPDATE 를 조용히
    생략하므로 단위 테스트에서는 사실상 no-op 이다.
    """
    db.execute(select(Trip.id).where(Trip.id == trip_id).with_for_update())


def get_trip_policy(db: Session, *, trip_id: int, policy_id: int) -> TripPolicy | None:
    statement = select(TripPolicy).where(
        TripPolicy.trip_id == trip_id,
        TripPolicy.policy_id == policy_id,
    )
    return db.scalar(statement)


def has_trip_policy_in_source_category(
    db: Session, *, trip_id: int, source_category: str
) -> bool:
    """일정에 해당 분류의 정책이 이미 붙어 있는지 본다.

    Trip.policies 관계는 같은 세션에서 방금 추가한 링크를 반영하지 않을 수
    있으므로 직접 조회한다.
    """
    statement = (
        select(TripPolicy.id)
        .join(Policy, Policy.id == TripPolicy.policy_id)
        .where(TripPolicy.trip_id == trip_id)
        .where(Policy.source_category == source_category)
        .limit(1)
    )
    return db.scalar(statement) is not None


def add_trip_policy(db: Session, *, trip_id: int, policy_id: int) -> TripPolicy:
    link = TripPolicy(trip_id=trip_id, policy_id=policy_id)
    db.add(link)
    return link


def remove_trip_policy(db: Session, link: TripPolicy) -> None:
    db.delete(link)


def list_recommendations(db: Session, *, trip_id: int, user_id: int) -> list[Recommendation]:
    statement = (
        select(Recommendation)
        .where(Recommendation.trip_id == trip_id)
        .where(Recommendation.user_id == user_id)
        .order_by(Recommendation.created_at, Recommendation.id)
    )
    return list(db.scalars(statement).all())


def add_recommendation(
    db: Session,
    *,
    user_id: int,
    trip_id: int,
    query: str,
    result,
) -> Recommendation:
    recommendation = Recommendation(user_id=user_id, trip_id=trip_id, query=query, result=result)
    db.add(recommendation)
    return recommendation


def detach_recommendations_from_trip(db: Session, *, trip_id: int) -> None:
    db.execute(
        update(Recommendation)
        .where(Recommendation.trip_id == trip_id)
        .values(trip_id=None)
    )


def delete_trip(db: Session, trip: Trip) -> None:
    db.delete(trip)


def delete_trip_place(db: Session, place: TripPlace) -> None:
    db.delete(place)


def reorder_trip_day_places(trip_day: TripDay, places: list[TripPlace]) -> None:
    trip_day.places = list(places)
    for order_num, place in enumerate(places, start=1):
        place.trip_day = trip_day
        place.trip_day_id = trip_day.id
        place.order_num = order_num


def get_latest_active_invite(db: Session, *, trip_id: int, now, role: str | None = None) -> TripInvite | None:
    statement = (
        select(TripInvite)
        .where(TripInvite.trip_id == trip_id)
        .where(TripInvite.expires_at > now)
    )
    if role is not None:
        statement = statement.where(TripInvite.role == role)
    statement = statement.order_by(TripInvite.created_at.desc(), TripInvite.id.desc())
    return db.scalar(statement)


def get_active_invite_by_token(db: Session, *, invite_token: str, now) -> TripInvite | None:
    statement = (
        select(TripInvite)
        .options(selectinload(TripInvite.trip).selectinload(Trip.members))
        .where(TripInvite.invite_token == invite_token)
        .where(TripInvite.expires_at > now)
        .where(TripInvite.role == "editor")
    )
    return db.scalar(statement)


def create_invite(
    db: Session,
    *,
    trip_id: int,
    invite_token: str,
    created_by: int,
    expires_at,
    role: str = "editor",
) -> TripInvite:
    invite = TripInvite(
        trip_id=trip_id,
        invite_token=invite_token,
        created_by=created_by,
        expires_at=expires_at,
        role=role,
    )
    db.add(invite)
    db.flush()
    return invite
