"""Trip authorization edge case tests.

Covers:
- Viewer role attempting place mutations → TripServiceError(403)
- Non-member accessing a trip → TripServiceError(404)
- Expired invite token acceptance → returns None
"""
from datetime import date, datetime, time, timedelta

import pytest

from app.models import Trip, TripDay, TripInvite, TripMember, TripPlace
from app.models import User as UserModel
from app.schemas.trip import (
    CreateTripPlaceRequest,
    MoveTripPlaceRequest,
    UpdateTripPlaceRequest,
)
from app.services import trips as trip_service
from app.services.trips import TripServiceError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_user(user_id: int = 1, nickname: str = "Test User") -> UserModel:
    return UserModel(
        id=user_id,
        email=f"user-{user_id}@travel.kr",
        nickname=nickname,
        onboarding_completed=True,
        created_at=datetime(2026, 5, 4),
        updated_at=datetime(2026, 5, 4),
    )


def make_trip_with_viewer() -> tuple[Trip, UserModel]:
    """Return a trip where user 2 has viewer role."""
    owner = make_user(1, "Owner")
    viewer = make_user(2, "Viewer")

    trip = Trip(
        id=10,
        owner_id=1,
        title="Test Trip",
        status="confirmed",
        revision=1,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 3),
        created_at=datetime(2026, 5, 4),
        updated_at=datetime(2026, 5, 4),
    )
    trip.owner = owner

    owner_member = TripMember(id=1, trip_id=10, user_id=1, role="owner")
    owner_member.user = owner
    viewer_member = TripMember(id=2, trip_id=10, user_id=2, role="viewer")
    viewer_member.user = viewer
    trip.members = [owner_member, viewer_member]

    place = TripPlace(id=5, trip_day_id=1, place_name="Test Place", order_num=1)
    day = TripDay(id=1, trip_id=10, day_number=1, date=date(2026, 7, 1))
    day.places = [place]
    trip.days = [day]
    trip.policies = []
    trip.invites = []
    trip.recommendations = []

    return trip, viewer


# ---------------------------------------------------------------------------
# Viewer role — place mutations must raise 403
# ---------------------------------------------------------------------------


def test_viewer_cannot_add_place(monkeypatch) -> None:
    trip, viewer = make_trip_with_viewer()
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip if trip_id == 10 else None,
    )

    with pytest.raises(TripServiceError) as exc_info:
        trip_service.add_place_to_trip_day(
            db=object(),
            user=viewer,
            trip_handle="10",
            day_number=1,
            payload=CreateTripPlaceRequest(expectedRevision=1, label="New Place"),
        )

    assert exc_info.value.status_code == 403


def test_viewer_cannot_update_place(monkeypatch) -> None:
    trip, viewer = make_trip_with_viewer()
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip if trip_id == 10 else None,
    )

    with pytest.raises(TripServiceError) as exc_info:
        trip_service.update_trip_place(
            db=object(),
            user=viewer,
            trip_handle="10",
            place_id=5,
            payload=UpdateTripPlaceRequest(expectedRevision=1, label="Renamed"),
        )

    assert exc_info.value.status_code == 403


def test_viewer_cannot_move_place(monkeypatch) -> None:
    trip, viewer = make_trip_with_viewer()
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip if trip_id == 10 else None,
    )

    with pytest.raises(TripServiceError) as exc_info:
        trip_service.move_trip_place(
            db=object(),
            user=viewer,
            trip_handle="10",
            place_id=5,
            payload=MoveTripPlaceRequest(expectedRevision=1, dayNumber=1, position=1),
        )

    assert exc_info.value.status_code == 403


def test_viewer_cannot_delete_place(monkeypatch) -> None:
    trip, viewer = make_trip_with_viewer()
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip if trip_id == 10 else None,
    )

    with pytest.raises(TripServiceError) as exc_info:
        trip_service.delete_trip_place(
            db=object(),
            user=viewer,
            trip_handle="10",
            place_id=5,
            expected_revision=1,
        )

    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Non-member access — trip lookup must raise 404
# ---------------------------------------------------------------------------


def test_nonmember_get_trip_returns_none(monkeypatch) -> None:
    """Non-member cannot see the trip — get_trip returns None."""
    outsider = make_user(99, "Outsider")

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: None,
    )

    result = trip_service.get_trip("10", db=object(), user=outsider)

    assert result is None


def test_nonmember_cannot_add_place(monkeypatch) -> None:
    """Non-member gets 404 when attempting to add a place."""
    outsider = make_user(99, "Outsider")

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: None,
    )

    with pytest.raises(TripServiceError) as exc_info:
        trip_service.add_place_to_trip_day(
            db=object(),
            user=outsider,
            trip_handle="10",
            day_number=1,
            payload=CreateTripPlaceRequest(expectedRevision=1, label="Sneaky Place"),
        )

    assert exc_info.value.status_code == 404


def test_nonmember_cannot_delete_place(monkeypatch) -> None:
    """Non-member gets 404 when attempting to delete a place."""
    outsider = make_user(99, "Outsider")

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: None,
    )

    with pytest.raises(TripServiceError) as exc_info:
        trip_service.delete_trip_place(
            db=object(),
            user=outsider,
            trip_handle="10",
            place_id=5,
            expected_revision=1,
        )

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Expired invite token — accept must return None
# ---------------------------------------------------------------------------


def test_accept_expired_invite_returns_none(monkeypatch) -> None:
    """Expired invite token causes accept_invite to return None (route → 404)."""
    user = make_user()

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_active_invite_by_token",
        lambda db, invite_token, now: None,
    )

    result = trip_service.accept_invite(
        db=object(),
        user=user,
        invite_token="expired-token-xyz",
    )

    assert result is None


def test_accept_valid_invite_joins_trip(monkeypatch) -> None:
    """Valid (non-expired) invite adds the user as a trip member."""
    user = make_user(5, "Newcomer")
    now = datetime(2026, 5, 18, 12, 0, 0)
    invite = TripInvite(
        id=1,
        trip_id=10,
        invite_token="valid-token",
        created_by=1,
        expires_at=now + timedelta(days=30),
        role="editor",
    )
    added_members: list[dict] = []

    class FakeDb:
        def commit(self) -> None:
            pass

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_active_invite_by_token",
        lambda db, invite_token, now: invite if invite_token == "valid-token" else None,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_trip_member",
        lambda db, trip_id, user_id: None,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "add_trip_member",
        lambda db, trip_id, user_id, role: added_members.append(
            {"trip_id": trip_id, "user_id": user_id, "role": role}
        ),
    )
    monkeypatch.setattr(
        trip_service.security,
        "utc_now_naive",
        lambda: now,
    )

    result = trip_service.accept_invite(
        db=FakeDb(),
        user=user,
        invite_token="valid-token",
    )

    assert result is not None
    assert result["tripId"] == "10"
    assert len(added_members) == 1
    assert added_members[0] == {"trip_id": 10, "user_id": 5, "role": "editor"}


def test_accept_invite_skips_duplicate_membership(monkeypatch) -> None:
    """Accepting an invite when already a member does not add a duplicate entry."""
    user = make_user(2, "Already Member")
    now = datetime(2026, 5, 18, 12, 0, 0)
    invite = TripInvite(
        id=2,
        trip_id=10,
        invite_token="dup-token",
        created_by=1,
        expires_at=now + timedelta(days=30),
        role="editor",
    )
    existing_member = TripMember(id=2, trip_id=10, user_id=2, role="editor")
    added_members: list[dict] = []

    class FakeDb:
        def commit(self) -> None:
            pass

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_active_invite_by_token",
        lambda db, invite_token, now: invite,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_trip_member",
        lambda db, trip_id, user_id: existing_member,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "add_trip_member",
        lambda db, trip_id, user_id, role: added_members.append(role),
    )
    monkeypatch.setattr(
        trip_service.security,
        "utc_now_naive",
        lambda: now,
    )

    result = trip_service.accept_invite(
        db=FakeDb(),
        user=user,
        invite_token="dup-token",
    )

    assert result is not None
    assert added_members == []
