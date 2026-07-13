from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from app.api.routes import admin as admin_routes
from app.main import app
from app.models import User


client = TestClient(app)


def make_user(user_id: int, *, role: str) -> User:
    return User(
        id=user_id,
        email=f"user-{user_id}@example.com",
        nickname=f"user-{user_id}",
        role=role,
        onboarding_completed=True,
        created_at=datetime(2026, 5, 27, 0, 0, 0),
        updated_at=datetime(2026, 5, 27, 0, 0, 0),
    )


def clear_overrides() -> None:
    app.dependency_overrides.pop(admin_routes.get_optional_db, None)
    app.dependency_overrides.pop(admin_routes.get_current_user, None)


def install_admin_dependencies(fake_db: object, user: User | None) -> None:
    app.dependency_overrides[admin_routes.get_optional_db] = lambda: fake_db
    if user is not None:
        app.dependency_overrides[admin_routes.get_current_user] = lambda: user


def test_admin_routes_reject_normal_users() -> None:
    fake_db = object()
    install_admin_dependencies(fake_db, make_user(2, role="user"))

    try:
        response = client.get("/api/admin/users")
    finally:
        clear_overrides()

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin permission required"}


def test_admin_routes_list_users_for_admin(monkeypatch) -> None:
    fake_db = object()
    admin = make_user(1, role="admin")
    install_admin_dependencies(fake_db, admin)
    monkeypatch.setattr(
        admin_routes.admin_service,
        "list_users",
        lambda db, current_admin, **kwargs: {
            "items": [
                {
                    "id": "2",
                    "email": "user@example.com",
                    "nickname": "traveler",
                    "role": "user",
                    "onboardingCompleted": True,
                    "createdAt": "2026-05-27T00:00:00",
                    "updatedAt": "2026-05-27T00:00:00",
                }
            ],
            "total": 1,
            "limit": kwargs["limit"],
            "offset": kwargs["offset"],
        },
    )

    try:
        response = client.get("/api/admin/users")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["items"][0]["email"] == "user@example.com"


def test_admin_routes_external_source_summary_for_admin(monkeypatch) -> None:
    fake_db = object()
    admin = make_user(1, role="admin")
    install_admin_dependencies(fake_db, admin)
    monkeypatch.setattr(
        admin_routes.admin_service,
        "get_external_source_summary",
        lambda db, current_admin: {
            "items": [
                {
                    "sourceCategory": "local_half_trip",
                    "label": "반값여행",
                    "sourceName": "대한민국 반값여행",
                    "totalRecords": 16,
                    "activeRecords": 5,
                    "scheduledRecords": 7,
                    "endedRecords": 4,
                    "unknownRecords": 0,
                    "freshRecords": 5,
                    "promotedPolicyCount": 5,
                    "activePromotedPolicyCount": 5,
                    "latestFetchedAt": "2026-05-27T09:00:00",
                    "latestVerifiedAt": "2026-05-27T09:00:00",
                }
            ],
            "totalRecords": 16,
            "activeRecords": 5,
            "freshRecords": 5,
            "promotedPolicyCount": 5,
            "latestFetchedAt": "2026-05-27T09:00:00",
        },
    )

    try:
        response = client.get("/api/admin/external-sources/summary")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["items"][0]["label"] == "반값여행"
