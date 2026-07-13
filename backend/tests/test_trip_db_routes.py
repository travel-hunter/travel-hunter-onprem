from datetime import date, datetime

from fastapi.testclient import TestClient

from app.api.routes import trips as trip_routes
from app.main import app
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
        "dates": "2026.06.15 - 06.17",
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
        "inviteToken": "abc",
        "inviteUrl": "http://127.0.0.1:5173/invites/abc/accept",
        "expiresAt": "2026-06-30T00:00:00Z",
        "createdAt": "2026-05-04T00:00:00Z",
        "acceptedAt": None,
        "invited": False,
        "copied": False,
        "role": "editor",
        "alreadyMember": False,
    }




def invite_links_payload(trip_id: str = "7") -> dict[str, object]:
    viewer = {**invite_payload(trip_id), "id": "10", "inviteToken": "viewer-token", "inviteUrl": "http://127.0.0.1:5173/invites/viewer-token/accept", "role": "viewer"}
    editor = {**invite_payload(trip_id), "id": "11", "inviteToken": "editor-token", "inviteUrl": "http://127.0.0.1:5173/invites/editor-token/accept", "role": "editor"}
    return {"tripId": trip_id, "viewer": viewer, "editor": editor}

def clear_overrides() -> None:
    app.dependency_overrides.pop(trip_routes.get_optional_db, None)
    app.dependency_overrides.pop(trip_routes.get_current_user, None)


def install_db_route_dependencies(monkeypatch, fake_db: object, user: UserModel | None = None) -> None:
    app.dependency_overrides[trip_routes.get_optional_db] = lambda: fake_db
    if user is not None:
        app.dependency_overrides[trip_routes.get_current_user] = lambda: user


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


def test_db_trip_create_route_rejects_out_of_range_duration() -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(None, fake_db, user)

    try:
        response = client.post("/api/trips", json={"durationDays": 8})
    finally:
        clear_overrides()

    assert response.status_code == 422


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


def test_db_trip_create_route_rejects_invalid_date_ranges() -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(None, fake_db, user)

    try:
        responses = [
            client.post("/api/trips", json={"startDate": "2026-07-12"}),
            client.post("/api/trips", json={"startDate": "2026-07-12", "endDate": "2026-07-12"}),
            client.post("/api/trips", json={"startDate": "2026-07-15", "endDate": "2026-07-12"}),
            client.post("/api/trips", json={"startDate": "2026-07-12", "endDate": "2026-07-19"}),
        ]
    finally:
        clear_overrides()

    assert [response.status_code for response in responses] == [422, 422, 422, 422]


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
        lambda db, current_user, trip_id: invite_links_payload(trip_id)
        if db is fake_db and current_user is user and trip_id == "7"
        else None,
    )
    monkeypatch.setattr(
        trip_routes.trip_service,
        "confirm_invite_sent",
        lambda db, current_user, trip_id, role="editor": {**invite_payload(trip_id), "invited": True, "role": role}
        if db is fake_db and current_user is user and trip_id == "7"
        else None,
    )

    try:
        recommendations = client.get("/api/trips/7/recommendations")
        invite = client.get("/api/trips/7/invite")
        confirm = client.post("/api/trips/7/invite", json={"role": "viewer"})
    finally:
        clear_overrides()

    assert recommendations.status_code == 200
    assert recommendations.json()[0]["title"] == "Cafe"
    assert "sourceType" in recommendations.json()[0]
    assert invite.status_code == 200
    assert invite.json()["tripId"] == "7"
    assert invite.json()["viewer"]["role"] == "viewer"
    assert invite.json()["editor"]["role"] == "editor"
    assert invite.json()["viewer"]["inviteToken"] != invite.json()["editor"]["inviteToken"]
    assert confirm.status_code == 200
    assert confirm.json()["invited"] is True
    assert confirm.json()["role"] == "viewer"


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
            json={"email": "friend@example.com", "role": "viewer"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["deliveryStatus"] == "sent"
    assert response.json()["invite"]["tripId"] == "7"
    assert response.json()["invite"]["role"] == "viewer"


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
