from datetime import date, datetime, time
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import trips as trip_routes
from app.db.base import Base
from app.main import app
from app.models import Policy, Trip, TripDay, TripMember, TripPlace, TripPolicy
from app.models import User as UserModel
from app.services import trips as trip_service


client = TestClient(app)


def make_user() -> UserModel:
    return UserModel(
        id=1,
        email="test.user@example.com",
        nickname="Test User",
        onboarding_completed=True,
        created_at=datetime(2026, 5, 4, 0, 0, 0),
        updated_at=datetime(2026, 5, 4, 0, 0, 0),
    )


def trip_payload(trip_id: str = "7") -> dict[str, object]:
    return {
        "id": trip_id,
        "title": "Jeju 3-day trip",
        "status": "confirmed",
        "revision": 1,
        "region": "Jeju",
        "dates": "2026.06.15 - 06.17",
        "startDate": date(2026, 6, 15),
        "endDate": date(2026, 6, 17),
        "people": ["Test User"],
        "participantCount": 1,
        "expectedSaving": "30만원",
        "linkedPolicies": [
            {
                "slug": "fixture-policy",
                "title": "Vacation policy",
                "amount": "30만원",
                "region": "Jeju",
            }
        ],
        "days": {1: [{"id": "1", "time": "09:00", "label": "Sunrise peak", "meta": "Nature"}]},
        "currentUserRole": "owner",
    }


def invite_payload(trip_id: str = "7") -> dict[str, object]:
    return {
        "id": "9",
        "tripId": trip_id,
        "inviteToken": "editor-token",
        "inviteUrl": "http://127.0.0.1:5173/invites/editor-token/accept",
        "expiresAt": "2026-06-30T00:00:00Z",
        "createdAt": "2026-05-04T00:00:00Z",
        "acceptedAt": None,
        "invited": False,
        "copied": False,
        "role": "editor",
        "alreadyMember": False,
    }


def clear_overrides() -> None:
    app.dependency_overrides.pop(trip_routes.get_optional_db, None)
    app.dependency_overrides.pop(trip_routes.get_current_user, None)


def install_db_route_dependencies(monkeypatch, fake_db: object, user: UserModel | None = None) -> None:
    app.dependency_overrides[trip_routes.get_optional_db] = lambda: fake_db
    if user is not None:
        app.dependency_overrides[trip_routes.get_current_user] = lambda: user


@pytest.fixture
def sqlite_db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with TestingSessionLocal() as session:
        yield session
    Base.metadata.drop_all(engine)


def seed_trip_for_region_update(sqlite_db_session, *, viewer: bool = False) -> tuple[UserModel, int]:
    owner = UserModel(
        id=101,
        email="trip-owner@example.com",
        password_hash="hashed",
        nickname="Trip Owner",
        onboarding_completed=True,
    )
    viewer_user = UserModel(
        id=102,
        email="trip-viewer@example.com",
        password_hash="hashed",
        nickname="Trip Viewer",
        onboarding_completed=True,
    )
    policy = Policy(
        id=103,
        slug="fixture-policy",
        title="Fixture policy",
        benefit_amount=300000,
        region="Jeju",
        status="active",
    )
    trip = Trip(
        id=104,
        owner_id=owner.id,
        title="Original trip",
        status="draft",
        revision=1,
        start_date=date(2026, 6, 15),
        end_date=date(2026, 6, 16),
        region="Jeju",
        travel_area_id=None,
        participant_count=2,
        description="Rest trip",
    )
    day = TripDay(id=105, trip_id=trip.id, day_number=1, date=date(2026, 6, 15))
    place = TripPlace(
        id=106,
        trip_day_id=day.id,
        place_name="Original place",
        visit_time=time(9, 0),
        order_num=1,
        memo="Original memo",
    )
    membership = TripMember(
        id=107,
        trip_id=trip.id,
        user_id=viewer_user.id,
        role="viewer" if viewer else "editor",
    )
    trip_policy = TripPolicy(id=108, trip_id=trip.id, policy_id=policy.id)
    sqlite_db_session.add_all([owner, viewer_user, policy, trip, day, place, membership, trip_policy])
    sqlite_db_session.commit()
    return (viewer_user if viewer else owner), trip.id


def test_db_trip_routes_require_bearer_user(monkeypatch) -> None:
    fake_db = object()
    install_db_route_dependencies(monkeypatch, fake_db)

    try:
        response = client.get("/api/trips")
    finally:
        clear_overrides()

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_db_trip_list_and_numeric_detail_routes(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)
    monkeypatch.setattr(
        trip_routes.trip_service,
        "list_trips",
        lambda db, current_user: [trip_payload()] if db is fake_db and current_user is user else [],
    )
    monkeypatch.setattr(
        trip_routes.trip_service,
        "get_trip",
        lambda db_handle, db, current_user: trip_payload(db_handle)
        if db_handle == "7" and db is fake_db and current_user is user
        else None,
    )

    try:
        list_response = client.get("/api/trips")
        detail_response = client.get("/api/trips/7")
    finally:
        clear_overrides()

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == "7"
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == "7"


def test_db_trip_create_route_returns_created_numeric_id(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)
    def create_trip_stub(db, current_user, payload):
        if (
            db is fake_db
            and current_user is user
            and payload
            and payload.title == "New trip"
            and payload.startDate == date(2026, 7, 12)
            and payload.endDate == date(2026, 7, 15)
            and payload.participantCount == 3
        ):
            created = trip_payload("8")
            created["participantCount"] = 3
            created["days"] = {1: [], 2: [], 3: [], 4: []}
            return created
        return trip_payload("7")

    monkeypatch.setattr(trip_routes.trip_service, "create_trip", create_trip_stub)

    try:
        response = client.post("/api/trips", json={"title": "New trip", "startDate": "2026-07-12", "endDate": "2026-07-15", "participantCount": 3})
    finally:
        clear_overrides()

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "8"
    assert body["participantCount"] == 3
    assert body["days"] == {"1": [], "2": [], "3": [], "4": []}


def test_db_trip_create_route_accepts_long_duration(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(None, fake_db, user)

    def create_trip_stub(db, current_user, payload):
        assert db is fake_db
        assert current_user is user
        assert payload.durationDays == 8
        created = trip_payload("8")
        created["days"] = {day: [] for day in range(1, 9)}
        return created

    monkeypatch.setattr(trip_routes.trip_service, "create_trip", create_trip_stub)

    try:
        response = client.post("/api/trips", json={"durationDays": 8})
    finally:
        clear_overrides()

    assert response.status_code == 200


def test_db_trip_create_route_rejects_out_of_range_participant_count() -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(None, fake_db, user)

    try:
        responses = [
            client.post("/api/trips", json={"participantCount": 0}),
            client.post("/api/trips", json={"participantCount": 11}),
        ]
    finally:
        clear_overrides()

    assert [response.status_code for response in responses] == [422, 422]


def test_db_trip_create_route_accepts_valid_one_day_and_long_date_ranges(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(None, fake_db, user)
    captured_ranges: list[tuple[date, date]] = []

    def create_trip_stub(db, current_user, payload):
        assert db is fake_db
        assert current_user is user
        captured_ranges.append((payload.startDate, payload.endDate))
        created = trip_payload(str(len(captured_ranges)))
        day_count = (payload.endDate - payload.startDate).days + 1
        created["days"] = {day: [] for day in range(1, day_count + 1)}
        return created

    monkeypatch.setattr(trip_routes.trip_service, "create_trip", create_trip_stub)

    try:
        responses = [
            client.post("/api/trips", json={"startDate": "2026-07-12", "endDate": "2026-07-12"}),
            client.post("/api/trips", json={"startDate": "2026-07-12", "endDate": "2026-07-19"}),
        ]
    finally:
        clear_overrides()

    assert [response.status_code for response in responses] == [200, 200]
    assert captured_ranges == [
        (date(2026, 7, 12), date(2026, 7, 12)),
        (date(2026, 7, 12), date(2026, 7, 19)),
    ]


def test_db_trip_create_route_rejects_missing_or_reversed_date_ranges() -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(None, fake_db, user)

    try:
        responses = [
            client.post("/api/trips", json={"startDate": "2026-07-12"}),
            client.post("/api/trips", json={"startDate": "2026-07-15", "endDate": "2026-07-12"}),
        ]
    finally:
        clear_overrides()

    assert [response.status_code for response in responses] == [422, 422]


def test_db_trip_create_route_maps_policy_error(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    def reject(*_args):
        raise trip_service.TripServiceError(404, "Policy not found")

    monkeypatch.setattr(trip_routes.trip_service, "create_trip", reject)

    try:
        response = client.post("/api/trips", json={"policySlug": "missing-policy"})
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json() == {"detail": "Policy not found"}


def test_db_trip_non_numeric_handle_returns_404(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    non_numeric_path = "/api/trips/" + "-".join(["jeju", "3", "days"])
    install_db_route_dependencies(monkeypatch, fake_db, user)
    monkeypatch.setattr(
        trip_routes.trip_service,
        "get_trip",
        lambda *_args: None,
    )

    try:
        response = client.get(non_numeric_path)
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json() == {"detail": "Trip not found"}


def test_db_trip_detail_missing_returns_404(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)
    monkeypatch.setattr(trip_routes.trip_service, "get_trip", lambda *_args: None)

    try:
        response = client.get("/api/trips/999")
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json() == {"detail": "Trip not found"}


def test_db_trip_delete_route_requires_bearer_user(monkeypatch) -> None:
    fake_db = object()
    install_db_route_dependencies(monkeypatch, fake_db)

    try:
        response = client.delete("/api/trips/7")
    finally:
        clear_overrides()

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_db_trip_delete_route_returns_deleted(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)
    monkeypatch.setattr(
        trip_routes.trip_service,
        "delete_trip",
        lambda trip_id, db, current_user: {"tripId": trip_id, "deleted": True}
        if trip_id == "7" and db is fake_db and current_user is user
        else None,
    )

    try:
        response = client.delete("/api/trips/7")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == {"tripId": "7", "deleted": True}


def test_db_trip_delete_route_missing_returns_404(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)
    monkeypatch.setattr(trip_routes.trip_service, "delete_trip", lambda *_args: None)

    try:
        response = client.delete("/api/trips/999")
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json() == {"detail": "Trip not found"}


def test_db_add_policy_maps_service_errors(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    def reject(*_args):
        raise trip_service.TripServiceError(404, "Policy not found")

    monkeypatch.setattr(trip_routes.trip_service, "add_policy_to_trip", reject)

    try:
        response = client.post("/api/trips/7/policies/missing-policy")
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json() == {"detail": "Policy not found"}


def test_db_remove_policy_from_trip_route_returns_response(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    def remove_policy(db, current_user, trip_id, policy_slug):
        assert db is fake_db
        assert current_user is user
        assert trip_id == "7"
        assert policy_slug == "fixture-policy"
        return {"tripId": "7", "policyId": "fixture-policy", "added": False}

    monkeypatch.setattr(trip_routes.trip_service, "remove_policy_from_trip", remove_policy)

    try:
        response = client.delete("/api/trips/7/policies/fixture-policy")
    finally:
      clear_overrides()

    assert response.status_code == 200
    assert response.json() == {"tripId": "7", "policyId": "fixture-policy", "added": False}


def test_db_trip_status_update_route_returns_updated_trip(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    def update_status(db, current_user, trip_id, payload):
        if db is fake_db and current_user is user and trip_id == "7" and payload.status == "confirmed":
            return {**trip_payload(trip_id), "status": "confirmed"}
        return None

    monkeypatch.setattr(trip_routes.trip_service, "update_trip_status", update_status)

    try:
        response = client.patch("/api/trips/7/status", json={"status": "confirmed"})
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["id"] == "7"
    assert response.json()["status"] == "confirmed"


def test_db_trip_status_update_route_maps_permission_error(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    def reject(*_args):
        raise trip_service.TripServiceError(403, "Trip edit permission required")

    monkeypatch.setattr(trip_routes.trip_service, "update_trip_status", reject)

    try:
        response = client.patch("/api/trips/7/status", json={"status": "confirmed"})
    finally:
        clear_overrides()

    assert response.status_code == 403
    assert response.json() == {"detail": "Trip edit permission required"}


def test_db_trip_status_update_route_rejects_invalid_status(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    try:
        response = client.patch("/api/trips/7/status", json={"status": "done"})
    finally:
        clear_overrides()

    assert response.status_code == 422


def test_db_trip_settings_update_route_returns_updated_trip(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    def update_settings(db, current_user, trip_id, payload):
        assert db is fake_db
        assert current_user is user
        assert trip_id == "7"
        assert payload.expectedRevision == 1
        assert payload.title == "Updated trip"
        assert payload.travelAreaId == "jeju-west"
        assert payload.startDate == date(2026, 6, 15)
        assert payload.endDate == date(2026, 6, 20)
        assert payload.overflowPlaceStrategy == "moveToLastDay"
        return {
            **trip_payload(trip_id),
            "title": "Updated trip",
            "region": "Jeju West",
            "travelAreaId": "jeju-west",
            "dates": "2026.06.15 - 06.20",
        }

    monkeypatch.setattr(trip_routes.trip_service, "update_trip_settings", update_settings)

    try:
        response = client.patch(
            "/api/trips/7/settings",
            json={
                "expectedRevision": 1,
                "title": "Updated trip",
                "travelAreaId": "jeju-west",
                "startDate": "2026-06-15",
                "endDate": "2026-06-20",
                "overflowPlaceStrategy": "moveToLastDay",
            },
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["id"] == "7"
    assert response.json()["title"] == "Updated trip"
    assert response.json()["region"] == "Jeju West"
    assert response.json()["travelAreaId"] == "jeju-west"
    assert response.json()["dates"] == "2026.06.15 - 06.20"


def test_db_trip_settings_updates_region_without_replacing_trip_content(sqlite_db_session) -> None:
    user, trip_id = seed_trip_for_region_update(sqlite_db_session)
    install_db_route_dependencies(None, sqlite_db_session, user)
    before = client.get(f"/api/trips/{trip_id}").json()

    try:
        response = client.patch(
            f"/api/trips/{trip_id}/settings",
            json={"expectedRevision": before["revision"], "travelAreaId": "jeju-west"},
        )
        detail = client.get(f"/api/trips/{trip_id}")
    finally:
        clear_overrides()

    assert response.status_code == 200
    after = response.json()
    assert after["travelAreaId"] == "jeju-west"
    assert after["region"] == "\uc81c\uc8fc \uc11c\ubd80"
    assert after["revision"] == before["revision"] + 1
    assert after["title"] == before["title"]
    assert after["days"] == before["days"]
    assert after["linkedPolicies"] == before["linkedPolicies"]
    assert detail.json()["travelAreaId"] == "jeju-west"
    assert detail.json()["region"] == "\uc81c\uc8fc \uc11c\ubd80"


@pytest.mark.parametrize(
    ("travel_area_id", "expected_region"),
    [
        ("whole:%EC%A0%9C%EC%A3%BC", "\uc81c\uc8fc \uc804\uccb4"),
        ("admin:%EC%A0%9C%EC%A3%BC:%EC%A0%9C%EC%A3%BC%EC%8B%9C", "\uc81c\uc8fc\uc2dc"),
        ("jeju-west", "\uc81c\uc8fc \uc11c\ubd80"),
        ("policy-region:%EC%A0%9C%EC%A3%BC:%EC%95%A0%EC%9B%94", "\uc560\uc6d4"),
    ],
)
def test_db_trip_settings_updates_region_for_supported_area_ids(
    sqlite_db_session,
    travel_area_id: str,
    expected_region: str,
) -> None:
    user, trip_id = seed_trip_for_region_update(sqlite_db_session)
    install_db_route_dependencies(None, sqlite_db_session, user)

    try:
        response = client.patch(
            f"/api/trips/{trip_id}/settings",
            json={"expectedRevision": 1, "travelAreaId": travel_area_id},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["travelAreaId"] == travel_area_id
    assert response.json()["region"] == expected_region


def test_db_trip_settings_rejects_unknown_area_without_mutation(sqlite_db_session) -> None:
    user, trip_id = seed_trip_for_region_update(sqlite_db_session)
    install_db_route_dependencies(None, sqlite_db_session, user)
    before = client.get(f"/api/trips/{trip_id}").json()

    try:
        response = client.patch(
            f"/api/trips/{trip_id}/settings",
            json={"expectedRevision": before["revision"], "travelAreaId": "missing-area"},
        )
        after = client.get(f"/api/trips/{trip_id}").json()
    finally:
        clear_overrides()

    assert response.status_code == 400
    assert response.json() == {"detail": "Travel area not found"}
    assert after["revision"] == before["revision"]
    assert after["region"] == before["region"]
    assert after["travelAreaId"] == before["travelAreaId"]
    assert after["title"] == before["title"]
    assert after["days"] == before["days"]
    assert after["linkedPolicies"] == before["linkedPolicies"]


def test_db_trip_settings_rejects_unknown_policy_region_area_without_mutation(sqlite_db_session) -> None:
    user, trip_id = seed_trip_for_region_update(sqlite_db_session)
    install_db_route_dependencies(None, sqlite_db_session, user)
    before = client.get(f"/api/trips/{trip_id}").json()

    try:
        response = client.patch(
            f"/api/trips/{trip_id}/settings",
            json={
                "expectedRevision": before["revision"],
                "travelAreaId": "policy-region:%EC%97%86%EB%8A%94:%EC%97%86%EB%8A%94",
            },
        )
        after = client.get(f"/api/trips/{trip_id}").json()
    finally:
        clear_overrides()

    assert response.status_code == 400
    assert response.json() == {"detail": "Travel area not found"}
    assert after["revision"] == before["revision"]
    assert after["region"] == before["region"]
    assert after["travelAreaId"] == before["travelAreaId"]
    assert after["title"] == before["title"]
    assert after["days"] == before["days"]
    assert after["linkedPolicies"] == before["linkedPolicies"]


def test_db_trip_settings_rejects_viewer_region_update(sqlite_db_session) -> None:
    user, trip_id = seed_trip_for_region_update(sqlite_db_session, viewer=True)
    install_db_route_dependencies(None, sqlite_db_session, user)

    try:
        response = client.patch(
            f"/api/trips/{trip_id}/settings",
            json={"expectedRevision": 1, "travelAreaId": "jeju-west"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 403
    assert response.json() == {"detail": "Trip edit permission required"}


def test_db_trip_settings_rejects_stale_region_update(sqlite_db_session) -> None:
    user, trip_id = seed_trip_for_region_update(sqlite_db_session)
    install_db_route_dependencies(None, sqlite_db_session, user)

    try:
        response = client.patch(
            f"/api/trips/{trip_id}/settings",
            json={"expectedRevision": 2, "travelAreaId": "jeju-west"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 409
    assert response.json() == {"detail": "Trip has changed. Refresh before saving."}


def test_db_trip_place_crud_routes_return_updated_trip(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)
    calls: list[tuple[str, object]] = []

    def add_place(db, current_user, trip_id, day_number, payload):
        calls.append(("add", payload))
        return trip_payload(trip_id) if db is fake_db and current_user is user and day_number == 1 else None

    def update_place(db, current_user, trip_id, place_id, payload):
        calls.append(("update", payload))
        return trip_payload(trip_id) if db is fake_db and current_user is user and place_id == 1 else None

    def delete_place(db, current_user, trip_id, place_id, expected_revision):
        calls.append(("delete", place_id, expected_revision))
        return trip_payload(trip_id) if db is fake_db and current_user is user and place_id == 1 else None

    def move_place(db, current_user, trip_id, place_id, payload):
        calls.append(("move", payload))
        return trip_payload(trip_id) if db is fake_db and current_user is user and place_id == 1 else None

    monkeypatch.setattr(trip_routes.trip_service, "add_place_to_trip_day", add_place)
    monkeypatch.setattr(trip_routes.trip_service, "update_trip_place", update_place)
    monkeypatch.setattr(trip_routes.trip_service, "move_trip_place", move_place)
    monkeypatch.setattr(trip_routes.trip_service, "delete_trip_place", delete_place)

    try:
        add_response = client.post(
            "/api/trips/7/days/1/places",
            json={"time": "10:00", "label": "Cafe", "meta": "Dessert", "expectedRevision": 1},
        )
        update_response = client.patch(
            "/api/trips/7/places/1",
            json={"time": "11:00", "label": "Updated cafe", "expectedRevision": 1},
        )
        move_response = client.patch(
            "/api/trips/7/places/1/move",
            json={"dayNumber": 2, "position": 1, "expectedRevision": 1},
        )
        delete_response = client.delete("/api/trips/7/places/1?expectedRevision=1")
    finally:
        clear_overrides()

    assert add_response.status_code == 200
    assert update_response.status_code == 200
    assert move_response.status_code == 200
    assert delete_response.status_code == 200
    assert add_response.json()["id"] == "7"
    assert calls[0][0] == "add"
    assert calls[0][1].label == "Cafe"
    assert calls[1][0] == "update"
    assert calls[1][1].label == "Updated cafe"
    assert calls[2][0] == "move"
    assert calls[2][1].dayNumber == 2
    assert calls[2][1].position == 1
    assert calls[3] == ("delete", 1, 1)


def test_db_trip_place_batch_route_returns_updated_trip(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    def add_places(db, current_user, trip_id, day_number, payload):
        assert db is fake_db
        assert current_user is user
        assert trip_id == "7"
        assert day_number == 1
        assert payload.expectedRevision == 1
        assert [place.label for place in payload.places] == ["Cafe stop", "Beach stop"]
        return trip_payload(trip_id)

    monkeypatch.setattr(trip_routes.trip_service, "add_places_to_trip_day", add_places)

    try:
        response = client.post(
            "/api/trips/7/days/1/places/batch",
            json={
                "expectedRevision": 1,
                "places": [
                    {"label": "Cafe stop", "time": "", "sourceProvider": "kakao"},
                    {"label": "Beach stop"},
                ],
            },
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["id"] == "7"


def test_db_trip_place_batch_route_rejects_empty_places(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    try:
        response = client.post(
            "/api/trips/7/days/1/places/batch",
            json={"expectedRevision": 1, "places": []},
        )
    finally:
        clear_overrides()

    assert response.status_code == 422


def test_db_trip_place_batch_route_maps_missing_day_error(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    def reject(*_args):
        raise trip_service.TripServiceError(404, "Trip day not found")

    monkeypatch.setattr(trip_routes.trip_service, "add_places_to_trip_day", reject)

    try:
        response = client.post(
            "/api/trips/7/days/99/places/batch",
            json={"expectedRevision": 1, "places": [{"label": "Cafe stop"}]},
        )
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json() == {"detail": "Trip day not found"}


def test_db_trip_place_routes_map_service_errors(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    def reject(*_args):
        raise trip_service.TripServiceError(404, "Trip not found")

    monkeypatch.setattr(trip_routes.trip_service, "add_place_to_trip_day", reject)
    monkeypatch.setattr(trip_routes.trip_service, "update_trip_place", reject)
    monkeypatch.setattr(trip_routes.trip_service, "move_trip_place", reject)
    monkeypatch.setattr(trip_routes.trip_service, "delete_trip_place", reject)

    try:
        add_response = client.post("/api/trips/7/days/99/places", json={"label": "Missing", "expectedRevision": 1})
        update_response = client.patch("/api/trips/7/places/999", json={"label": "Missing", "expectedRevision": 1})
        move_response = client.patch("/api/trips/7/places/999/move", json={"dayNumber": 1, "position": 1, "expectedRevision": 1})
        delete_response = client.delete("/api/trips/7/places/999?expectedRevision=1")
    finally:
        clear_overrides()

    assert add_response.status_code == 404
    assert update_response.status_code == 404
    assert move_response.status_code == 404
    assert delete_response.status_code == 404
    assert add_response.json() == {"detail": "Trip not found"}


def test_db_trip_place_routes_map_revision_conflict(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    def reject(*_args):
        raise trip_service.TripServiceError(409, "Trip has changed. Refresh before saving.")

    monkeypatch.setattr(trip_routes.trip_service, "update_trip_place", reject)

    try:
        response = client.patch(
            "/api/trips/7/places/1",
            json={"label": "Stale edit", "expectedRevision": 1},
        )
    finally:
        clear_overrides()

    assert response.status_code == 409
    assert response.json() == {"detail": "Trip has changed. Refresh before saving."}


def test_db_trip_place_delete_route_requires_expected_revision(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    try:
        response = client.delete("/api/trips/7/places/1")
    finally:
        clear_overrides()

    assert response.status_code == 422


def test_db_trip_place_routes_map_viewer_permission_error(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    def reject(*_args):
        raise trip_service.TripServiceError(403, "Trip edit permission required")

    monkeypatch.setattr(trip_routes.trip_service, "add_place_to_trip_day", reject)
    monkeypatch.setattr(trip_routes.trip_service, "move_trip_place", reject)

    try:
        response = client.post("/api/trips/7/days/1/places", json={"label": "Read only", "expectedRevision": 1})
        move_response = client.patch("/api/trips/7/places/1/move", json={"dayNumber": 1, "position": 1, "expectedRevision": 1})
    finally:
        clear_overrides()

    assert response.status_code == 403
    assert response.json() == {"detail": "Trip edit permission required"}
    assert move_response.status_code == 403


def test_db_trip_place_move_route_rejects_invalid_position(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    try:
        response = client.patch("/api/trips/7/places/1/move", json={"dayNumber": 1, "position": 0, "expectedRevision": 1})
    finally:
        clear_overrides()

    assert response.status_code == 422


def test_db_recommendation_and_invite_routes(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)
    monkeypatch.setattr(
        trip_routes.trip_service,
        "list_recommendations",
        lambda db, current_user, trip_id: [{"label": "CA", "title": "Cafe", "meta": "Day 2", "reason": "Route"}]
        if db is fake_db and current_user is user and trip_id == "7"
        else None,
    )
    monkeypatch.setattr(
        trip_routes.trip_service,
        "get_invite_state",
        lambda db, current_user, trip_id: invite_payload(trip_id)
        if db is fake_db and current_user is user and trip_id == "7"
        else None,
    )
    monkeypatch.setattr(
        trip_routes.trip_service,
        "confirm_invite_sent",
        lambda db, current_user, trip_id, role="editor": {**invite_payload(trip_id), "invited": True, "role": "editor"}
        if db is fake_db and current_user is user and trip_id == "7" and role == "editor"
        else None,
    )

    try:
        recommendations = client.get("/api/trips/7/recommendations")
        invite = client.get("/api/trips/7/invite")
        confirm = client.post("/api/trips/7/invite")
        viewer_confirm = client.post("/api/trips/7/invite", json={"role": "viewer"})
    finally:
        clear_overrides()

    assert recommendations.status_code == 200
    assert recommendations.json()[0]["title"] == "Cafe"
    assert "sourceType" in recommendations.json()[0]
    assert invite.status_code == 200
    assert invite.json()["tripId"] == "7"
    assert invite.json()["role"] == "editor"
    assert invite.json()["inviteToken"] == "editor-token"
    assert confirm.status_code == 200
    assert confirm.json()["invited"] is True
    assert confirm.json()["role"] == "editor"
    assert viewer_confirm.status_code == 422


def test_db_trip_place_search_route_returns_candidates(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)
    monkeypatch.setattr(
        trip_routes.trip_service,
        "search_places_for_trip",
        lambda db, current_user, *, trip_handle, query: [
            {
                "id": "kakao:kakao-1",
                "label": "📍",
                "title": "성산일출봉",
                "meta": "관광명소 · 제주 서귀포시 성산읍",
                "categoryCode": "AT4",
                "categoryName": "관광명소",
                "phone": "064-000-0000",
                "address": "제주 서귀포시 성산읍",
                "latitude": 33.4581,
                "longitude": 126.9425,
                "placeUrl": "https://place.map.kakao.com/kakao-1",
                "sourceProvider": "kakao",
                "externalPlaceId": "kakao-1",
            }
        ]
        if db is fake_db and current_user is user and trip_handle == "7" and query == "성산일출봉"
        else [],
    )

    try:
        response = client.get("/api/trips/7/place-search?query=성산일출봉")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()[0]["title"] == "성산일출봉"
    assert response.json()[0]["sourceProvider"] == "kakao"
    assert response.json()[0]["externalPlaceId"] == "kakao-1"


def test_db_trip_invite_email_route_returns_delivery_status(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)
    monkeypatch.setattr(
        trip_routes.trip_service,
        "send_invite_email",
        lambda db, current_user, trip_id, payload: {
            "invite": {**invite_payload(trip_id), "invited": True, "role": payload.role},
            "deliveryStatus": "sent",
            "message": "Invite email sent.",
        }
        if db is fake_db and current_user is user and trip_id == "7"
        else None,
    )

    try:
        response = client.post(
            "/api/trips/7/invite/email",
            json={"email": "friend@example.com"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["deliveryStatus"] == "sent"
    assert response.json()["invite"]["tripId"] == "7"
    assert response.json()["invite"]["role"] == "editor"


def test_db_trip_invite_email_route_rejects_viewer_role(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)
    send_invite_email = Mock()
    monkeypatch.setattr(trip_routes.trip_service, "send_invite_email", send_invite_email)

    try:
        response = client.post(
            "/api/trips/7/invite/email",
            json={"email": "friend@example.com", "role": "viewer"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 422
    assert not send_invite_email.called


def test_db_trip_invite_email_route_returns_404_for_non_owner(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)
    monkeypatch.setattr(trip_routes.trip_service, "send_invite_email", lambda *_args: None)

    try:
        response = client.post(
            "/api/trips/7/invite/email",
            json={"email": "friend@example.com", "role": "editor"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 404


def test_db_trip_invite_route_rejects_invalid_role(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    try:
        response = client.post("/api/trips/7/invite", json={"role": "owner"})
    finally:
        clear_overrides()

    assert response.status_code == 422
