from datetime import datetime

from fastapi.testclient import TestClient

from app.api.routes import invites as invite_routes
from app.main import app
from app.models import User as UserModel


client = TestClient(app)


def make_user() -> UserModel:
    return UserModel(
        id=2,
        email="friend@travel.kr",
        nickname="Friend",
        onboarding_completed=True,
        created_at=datetime(2026, 5, 4, 0, 0, 0),
        updated_at=datetime(2026, 5, 4, 0, 0, 0),
    )


def invite_payload() -> dict[str, object]:
    return {
        "id": "9",
        "tripId": "7",
        "inviteToken": "abc",
        "inviteUrl": "http://127.0.0.1:5173/invites/abc/accept",
        "expiresAt": "2026-06-30T00:00:00Z",
        "createdAt": "2026-05-04T00:00:00Z",
        "acceptedAt": "2026-05-05T00:00:00Z",
        "invited": True,
        "copied": False,
        "role": "viewer",
        "alreadyMember": False,
    }


def clear_overrides() -> None:
    app.dependency_overrides.pop(invite_routes.get_optional_db, None)
    app.dependency_overrides.pop(invite_routes.get_current_user, None)


def install_db_route_dependencies(
    monkeypatch,
    fake_db: object,
    user: UserModel | None = None,
) -> None:
    app.dependency_overrides[invite_routes.get_optional_db] = lambda: fake_db
    app.dependency_overrides[invite_routes.get_current_user] = lambda: user


def test_db_invite_accept_requires_user(monkeypatch) -> None:
    fake_db = object()
    install_db_route_dependencies(monkeypatch, fake_db)

    try:
        response = client.post("/api/invites/abc/accept")
    finally:
        clear_overrides()

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_db_invite_accept_missing_token_returns_404(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)
    monkeypatch.setattr(invite_routes.trip_service, "accept_invite", lambda *_args: None)

    try:
        response = client.post("/api/invites/missing/accept")
    finally:
        clear_overrides()

    assert response.status_code == 404
    assert response.json() == {"detail": "Invite not found"}


def test_db_invite_accept_returns_service_conflict(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)

    def raise_participant_limit(*_args):
        raise invite_routes.trip_service.TripServiceError(409, "Trip participant limit reached")

    monkeypatch.setattr(invite_routes.trip_service, "accept_invite", raise_participant_limit)

    try:
        response = client.post("/api/invites/abc/accept")
    finally:
        clear_overrides()

    assert response.status_code == 409
    assert response.json() == {"detail": "Trip participant limit reached"}


def test_db_invite_accept_returns_invite_state(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    install_db_route_dependencies(monkeypatch, fake_db, user)
    monkeypatch.setattr(
        invite_routes.trip_service,
        "accept_invite",
        lambda db, current_user, token: invite_payload()
        if db is fake_db and current_user is user and token == "abc"
        else None,
    )

    try:
        response = client.post("/api/invites/abc/accept")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["tripId"] == "7"
    assert response.json()["acceptedAt"] == "2026-05-05T00:00:00Z"
    assert response.json()["invited"] is True
    assert response.json()["role"] == "viewer"
