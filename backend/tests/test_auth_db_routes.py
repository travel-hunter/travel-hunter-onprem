from datetime import datetime

from fastapi.testclient import TestClient

from app.api.routes import auth as auth_routes
from app.api.routes import profile as profile_routes
from app.main import app
from app.models import User as UserModel
from app.services import auth as auth_service
from app.services import oauth as oauth_service


client = TestClient(app)


def make_user() -> UserModel:
    return UserModel(
        id=1,
        email="test.user@example.com",
        nickname="Test User",
        onboarding_completed=True,
        nickname_setup_completed=True,
        profile_setup_skipped=False,
        created_at=datetime(2026, 5, 4, 0, 0, 0),
        updated_at=datetime(2026, 5, 4, 0, 0, 0),
    )


def clear_overrides() -> None:
    app.dependency_overrides.pop(auth_routes.get_optional_db, None)
    app.dependency_overrides.pop(profile_routes.get_current_user, None)
    app.dependency_overrides.pop(auth_routes.get_current_user, None)


def test_db_login_route_sets_refresh_cookie(monkeypatch) -> None:
    fake_db = object()
    result = auth_service.AuthResult(
        access_token="access-token",
        refresh_token="refresh-token",
        user=auth_service.user_to_api(make_user()),
    )

    monkeypatch.setattr(auth_routes.auth_service, "login", lambda db, request: result)
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db

    try:
        response = client.post(
            "/api/auth/login",
            json={"email": "test.user@example.com", "password": "password123"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["accessToken"] == "access-token"
    assert response.json()["user"]["email"] == "test.user@example.com"
    assert "travel_hunter_refresh=refresh-token" in response.headers["set-cookie"]


def test_db_login_route_returns_invalid_credentials(monkeypatch) -> None:
    fake_db = object()

    def reject(_db, _request):
        raise auth_service.AuthServiceError(401, "Invalid email or password")

    monkeypatch.setattr(auth_routes.auth_service, "login", reject)
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db

    try:
        response = client.post(
            "/api/auth/login",
            json={"email": "test.user@example.com", "password": "wrong-password"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}



def test_db_signup_route_requests_email_verification(monkeypatch) -> None:
    fake_db = object()

    monkeypatch.setattr(
        auth_routes.auth_service,
        "signup",
        lambda db, request: {"verificationRequired": True, "email": str(request.email)},
    )
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db

    try:
        response = client.post(
            "/api/auth/signup",
            json={"email": "new@example.com", "agreements": {"termsAccepted": True, "privacyAccepted": True, "termsVersion": "2026-06-26", "privacyVersion": "2026-06-26"}},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == {"verificationRequired": True, "email": "new@example.com"}
    assert "travel_hunter_refresh=" not in response.headers.get("set-cookie", "")


def test_db_signup_verify_route_returns_verified_email_without_cookie(monkeypatch) -> None:
    fake_db = object()

    monkeypatch.setattr(auth_routes.auth_service, "verify_signup", lambda db, request: {"verified": True, "email": "new@example.com"})
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db

    try:
        response = client.post("/api/auth/signup/verify", json={"token": "signup-token"})
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == {"verified": True, "email": "new@example.com"}
    assert "travel_hunter_refresh=" not in response.headers.get("set-cookie", "")


def test_db_signup_complete_route_sets_refresh_cookie(monkeypatch) -> None:
    fake_db = object()
    result = auth_service.AuthResult(
        access_token="access-token",
        refresh_token="refresh-token",
        user=auth_service.user_to_api(make_user()),
    )

    monkeypatch.setattr(auth_routes.auth_service, "complete_signup", lambda db, request: result)
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db

    try:
        response = client.post("/api/auth/signup/complete", json={"token": "signup-token", "password": "password123"})
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["accessToken"] == "access-token"
    assert response.json()["user"]["email"] == "test.user@example.com"
    assert "travel_hunter_refresh=refresh-token" in response.headers["set-cookie"]

def test_email_check_route_returns_availability(monkeypatch) -> None:
    fake_db = object()

    monkeypatch.setattr(
        auth_routes.auth_service,
        "check_email_availability",
        lambda db, request: {"available": request.email != "taken@example.com"},
    )
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db

    try:
        response = client.post("/api/auth/email-check", json={"email": "new@example.com"})
        duplicate_response = client.post("/api/auth/email-check", json={"email": "taken@example.com"})
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == {"available": True}
    assert duplicate_response.status_code == 200
    assert duplicate_response.json() == {"available": False}


def test_db_me_requires_bearer_token(monkeypatch) -> None:

    response = client.get("/api/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_db_me_returns_current_user(monkeypatch) -> None:
    user = make_user()

    app.dependency_overrides[profile_routes.get_current_user] = lambda: user

    try:
        response = client.get("/api/me", headers={"Authorization": "Bearer access-token"})
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["id"] == "1"
    assert response.json()["email"] == "test.user@example.com"
    assert response.json()["nicknameSetupCompleted"] is True
    assert response.json()["hasPassword"] is False
    assert response.json()["socialAccounts"] == []


def test_db_logout_clears_refresh_cookie(monkeypatch) -> None:
    fake_db = object()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        auth_routes.auth_service,
        "logout",
        lambda db, token: captured.update({"db": db, "token": token}),
    )
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db

    try:
        client.cookies.set("travel_hunter_refresh", "refresh-token")
        response = client.post(
            "/api/auth/logout",
        )
    finally:
        client.cookies.clear()
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == {"loggedOut": True}
    assert captured == {"db": fake_db, "token": "refresh-token"}
    assert "travel_hunter_refresh=" in response.headers["set-cookie"]


def test_password_reset_request_route_hides_account_existence(monkeypatch) -> None:
    fake_db = object()

    monkeypatch.setattr(
        auth_routes.auth_service,
        "request_password_reset",
        lambda db, request: {"requested": True},
    )
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db

    try:
        response = client.post(
            "/api/auth/password-reset/request",
            json={"email": "unknown@example.com"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == {"requested": True}


def test_password_reset_confirm_route(monkeypatch) -> None:
    fake_db = object()

    monkeypatch.setattr(
        auth_routes.auth_service,
        "confirm_password_reset",
        lambda db, request: {"reset": True},
    )
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db

    try:
        response = client.post(
            "/api/auth/password-reset/confirm",
            json={"token": "reset-token", "newPassword": "new-password123"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == {"reset": True}


def test_oauth_start_sets_state_cookie(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_routes.oauth_service,
        "build_authorization_redirect",
        lambda provider, redirect: oauth_service.OAuthStartResult(
            authorization_url="https://provider.example/authorize",
            state="state-token:/home",
            redirect="/home",
        ),
    )

    response = client.get("/api/auth/oauth/google/start?redirect=/home", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://provider.example/authorize"
    assert "travel_hunter_oauth_state=" in response.headers["set-cookie"]
    assert "state-token:/home" in response.headers["set-cookie"]


def test_oauth_callback_sets_refresh_cookie_and_redirects(monkeypatch) -> None:
    fake_db = object()
    result = oauth_service.OAuthCallbackResult(
        auth=auth_service.AuthResult(
            access_token="access-token",
            refresh_token="refresh-token",
            user=auth_service.user_to_api(make_user()),
        ),
        frontend_redirect_url="http://127.0.0.1:5173/oauth/callback?redirect=%2Fhome",
    )

    monkeypatch.setattr(
        auth_routes.oauth_service,
        "complete_oauth_callback",
        lambda *args, **kwargs: result,
    )
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db

    try:
        client.cookies.set("travel_hunter_oauth_state", "state-token:/home")
        response = client.get(
            "/api/auth/oauth/google/callback?code=abc&state=state-token:/home",
            follow_redirects=False,
        )
    finally:
        client.cookies.clear()
        clear_overrides()

    assert response.status_code == 302
    assert response.headers["location"] == "http://127.0.0.1:5173/oauth/callback?redirect=%2Fhome"
    assert "travel_hunter_refresh=refresh-token" in response.headers["set-cookie"]


def test_oauth_callback_provider_access_denied_redirects_without_refresh_cookie() -> None:
    try:
        client.cookies.set("travel_hunter_oauth_state", "state-token:/trips")
        response = client.get(
            "/api/auth/oauth/google/callback?error=access_denied&state=state-token:/trips&error_description=raw-provider-message",
            follow_redirects=False,
        )
    finally:
        client.cookies.clear()

    assert response.status_code == 302
    assert response.headers["location"] == (
        "http://127.0.0.1:5173/oauth/callback?error=access_denied&redirect=%2Ftrips"
    )
    assert "raw-provider-message" not in response.headers["location"]
    assert "travel_hunter_refresh=" not in response.headers.get("set-cookie", "")
    assert "travel_hunter_oauth_state=" in response.headers["set-cookie"]


def test_oauth_callback_provider_error_with_invalid_state_redirects_invalid_state() -> None:
    try:
        client.cookies.set("travel_hunter_oauth_state", "state-token:/trips")
        response = client.get(
            "/api/auth/oauth/google/callback?error=access_denied&state=other-state:/trips",
            follow_redirects=False,
        )
    finally:
        client.cookies.clear()

    assert response.status_code == 302
    assert response.headers["location"] == (
        "http://127.0.0.1:5173/oauth/callback?error=invalid_state&redirect=%2Fhome"
    )
    assert "travel_hunter_refresh=" not in response.headers.get("set-cookie", "")
    assert "travel_hunter_oauth_state=" in response.headers["set-cookie"]


def test_oauth_callback_service_error_redirects_without_refresh_cookie(monkeypatch) -> None:
    fake_db = object()

    def fail_callback(*args, **kwargs):
        raise oauth_service.OAuthServiceError(400, "OAuth email policy requires a verified Google email")

    monkeypatch.setattr(auth_routes.oauth_service, "complete_oauth_callback", fail_callback)
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db

    try:
        client.cookies.set("travel_hunter_oauth_state", "state-token:/home")
        response = client.get(
            "/api/auth/oauth/google/callback?code=abc&state=state-token:/home",
            follow_redirects=False,
        )
    finally:
        client.cookies.clear()
        clear_overrides()

    assert response.status_code == 302
    assert response.headers["location"] == (
        "http://127.0.0.1:5173/oauth/callback?error=email_policy&redirect=%2Fhome"
    )
    assert "travel_hunter_refresh=" not in response.headers.get("set-cookie", "")
    assert "travel_hunter_oauth_state=" in response.headers["set-cookie"]


def test_oauth_callback_service_invalid_state_redirects_home_without_refresh_cookie(monkeypatch) -> None:
    fake_db = object()

    def fail_callback(*args, **kwargs):
        raise oauth_service.OAuthServiceError(400, "invalid_state")

    monkeypatch.setattr(auth_routes.oauth_service, "complete_oauth_callback", fail_callback)
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db

    try:
        client.cookies.set("travel_hunter_oauth_state", "state-token:/trips")
        response = client.get(
            "/api/auth/oauth/google/callback?code=abc&state=state-token:/trips",
            follow_redirects=False,
        )
    finally:
        client.cookies.clear()
        clear_overrides()

    assert response.status_code == 302
    assert response.headers["location"] == (
        "http://127.0.0.1:5173/oauth/callback?error=invalid_state&redirect=%2Fhome"
    )
    assert "travel_hunter_refresh=" not in response.headers.get("set-cookie", "")
    assert "travel_hunter_oauth_state=" in response.headers["set-cookie"]


def test_agreement_versions_match_frontend_contract() -> None:
    """Guard the lightweight shared-contract boundary until versions are API-driven."""
    import re
    from pathlib import Path

    frontend_source = Path(__file__).resolve().parents[2] / "frontend/src/pages/AuthPages.tsx"
    text = frontend_source.read_text(encoding="utf-8")
    terms = re.search(r'CURRENT_TERMS_VERSION = "([^"]+)"', text)
    privacy = re.search(r'CURRENT_PRIVACY_VERSION = "([^"]+)"', text)

    assert terms is not None
    assert privacy is not None
    assert terms.group(1) == auth_service.CURRENT_TERMS_VERSION
    assert privacy.group(1) == auth_service.CURRENT_PRIVACY_VERSION

def test_db_login_response_includes_has_password(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    user.password_hash = "hash"
    result = auth_service.AuthResult(
        access_token="access-token",
        refresh_token="refresh-token",
        user=auth_service.user_to_api(user),
    )

    monkeypatch.setattr(auth_routes.auth_service, "login", lambda db, request: result)
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db

    try:
        response = client.post(
            "/api/auth/login",
            json={"email": "test.user@example.com", "password": "password123"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["user"]["hasPassword"] is True


def test_password_change_route_returns_changed(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    captured: dict[str, object] = {}

    def change_password(db, current_user, request):
        captured.update({"db": db, "user": current_user, "current": request.currentPassword})
        return {"changed": True}

    monkeypatch.setattr(auth_routes.auth_service, "change_password", change_password)
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db
    app.dependency_overrides[auth_routes.get_current_user] = lambda: user

    try:
        response = client.post(
            "/api/auth/password/change",
            json={"currentPassword": "old-password", "newPassword": "new-password123"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == {"changed": True}
    assert captured == {"db": fake_db, "user": user, "current": "old-password"}


def test_withdraw_route_clears_refresh_cookie(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    captured: dict[str, object] = {}

    def withdraw(db, current_user, request):
        captured.update({"db": db, "user": current_user, "password": request.password})
        return {"withdrawn": True}

    monkeypatch.setattr(auth_routes.auth_service, "withdraw", withdraw)
    app.dependency_overrides[auth_routes.get_optional_db] = lambda: fake_db
    app.dependency_overrides[auth_routes.get_current_user] = lambda: user

    try:
        client.cookies.set("travel_hunter_refresh", "refresh-token")
        response = client.post(
            "/api/auth/withdraw",
            json={"password": "password123"},
            headers={"Authorization": "Bearer access-token"},
        )
    finally:
        client.cookies.clear()
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == {"withdrawn": True}
    assert captured == {"db": fake_db, "user": user, "password": "password123"}
    assert "travel_hunter_refresh=" in response.headers["set-cookie"]
