from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.core import security
from app.schemas.user import CompleteSocialSignupRequest, RequiredAgreement
from app.services import auth as auth_service
from app.services import oauth as oauth_service


class FakeDb:
    def __init__(self) -> None:
        self.committed = False

    def commit(self) -> None:
        self.committed = True


def accepted_agreements() -> RequiredAgreement:
    return RequiredAgreement(
        termsAccepted=True,
        privacyAccepted=True,
        termsVersion=auth_service.CURRENT_TERMS_VERSION,
        privacyVersion=auth_service.CURRENT_PRIVACY_VERSION,
    )


def test_new_oauth_callback_creates_pending_social_signup_without_auth(monkeypatch) -> None:
    db = FakeDb()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        oauth_service,
        "_provider_config",
        lambda provider: oauth_service.OAuthProviderConfig(
            provider=provider,
            client_id="client",
            client_secret="secret",
            redirect_uri="https://api.example.com/callback",
            authorize_url="https://provider.example.com/auth",
            token_url="https://provider.example.com/token",
            userinfo_url="https://provider.example.com/me",
            scope="openid email profile",
        ),
    )
    monkeypatch.setattr(oauth_service, "_exchange_code", lambda _config, _code: "access-token")
    monkeypatch.setattr(
        oauth_service,
        "_fetch_userinfo",
        lambda _config, _token: {
            "sub": "google-123",
            "email": "New.User@Example.COM",
            "email_verified": True,
            "name": "신규 소셜",
        },
    )
    monkeypatch.setattr(oauth_service.user_repository, "get_active_social_account", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(oauth_service.user_repository, "get_active_user_by_email", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(oauth_service.security, "create_urlsafe_token", lambda: "pending-social-token")
    monkeypatch.setattr(
        oauth_service.pending_social_signup_repository,
        "delete_pending_social_signup_by_provider",
        lambda *_args, **kwargs: captured.update({"deleted": kwargs}),
    )
    monkeypatch.setattr(
        oauth_service.pending_social_signup_repository,
        "create_pending_social_signup",
        lambda *_args, **kwargs: captured.update(kwargs),
    )

    result = oauth_service.complete_oauth_callback(
        db,
        provider="google",
        code="callback-code",
        state="state-value:/invites/abc/accept",
        state_cookie="state-value:/invites/abc/accept",
    )

    assert result.auth is None
    assert result.frontend_redirect_url.endswith(
        "/signup/social-agreement?token=pending-social-token&redirect=%2Finvites%2Fabc%2Faccept"
    )
    assert captured["provider"] == "google"
    assert captured["provider_id"] == "google-123"
    assert captured["email"] == "new.user@example.com"
    assert captured["email_verified"] is True
    assert captured["token_hash"] == security.hash_token("pending-social-token")
    assert db.committed is True


def test_complete_pending_social_signup_stores_required_agreement_metadata(monkeypatch) -> None:
    db = FakeDb()
    pending = SimpleNamespace(
        provider="google",
        provider_id="google-123",
        email="new.user@example.com",
        nickname="신규 소셜",
        expires_at=security.utc_now_naive() + timedelta(minutes=30),
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(oauth_service, "_get_active_pending_social_signup", lambda _db, token: pending)
    monkeypatch.setattr(oauth_service.user_repository, "get_active_social_account", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(oauth_service.user_repository, "get_active_user_by_email", lambda *_args, **_kwargs: None)

    def create_user(_db, **kwargs):
        captured["created_user"] = kwargs
        return SimpleNamespace(id=42, email=kwargs["email"], nickname=kwargs["nickname"], social_accounts=[])

    def create_social_account(_db, **kwargs):
        captured["social_account"] = kwargs
        return SimpleNamespace(provider=kwargs["provider"], provider_nickname=kwargs["provider_nickname"])

    monkeypatch.setattr(oauth_service.user_repository, "create_user", create_user)
    monkeypatch.setattr(oauth_service.user_repository, "create_social_account", create_social_account)
    monkeypatch.setattr(
        oauth_service.pending_social_signup_repository,
        "delete_pending_social_signup",
        lambda *_args: captured.update({"pending_deleted": True}),
    )
    monkeypatch.setattr(
        oauth_service.auth_service,
        "_issue_tokens",
        lambda _db, user: auth_service.AuthResult(
            access_token="access",
            refresh_token="refresh",
            user={"id": str(user.id), "email": user.email},
        ),
    )

    result = oauth_service.complete_pending_social_signup(
        db,
        CompleteSocialSignupRequest(token="pending-social-token", agreements=accepted_agreements()),
    )

    created_user = captured["created_user"]
    assert created_user["email"] == "new.user@example.com"
    assert created_user["terms_accepted"] is True
    assert created_user["terms_version"] == auth_service.CURRENT_TERMS_VERSION
    assert created_user["privacy_accepted"] is True
    assert created_user["privacy_version"] == auth_service.CURRENT_PRIVACY_VERSION
    assert captured["social_account"].get("provider") == "google"
    assert captured["pending_deleted"] is True
    assert result.access_token == "access"
    assert db.committed is True


def test_complete_pending_social_signup_rejects_missing_required_agreement(monkeypatch) -> None:
    db = FakeDb()
    pending = SimpleNamespace(
        provider="google",
        provider_id="google-123",
        email="new.user@example.com",
        nickname="신규 소셜",
        expires_at=security.utc_now_naive() + timedelta(minutes=30),
    )
    monkeypatch.setattr(oauth_service, "_get_active_pending_social_signup", lambda _db, token: pending)

    with pytest.raises(auth_service.AuthServiceError) as error:
        oauth_service.complete_pending_social_signup(
            db,
            CompleteSocialSignupRequest(
                token="pending-social-token",
                agreements=RequiredAgreement(
                    termsAccepted=True,
                    privacyAccepted=False,
                    termsVersion=auth_service.CURRENT_TERMS_VERSION,
                    privacyVersion=auth_service.CURRENT_PRIVACY_VERSION,
                ),
            ),
        )

    assert error.value.status_code == 400
    assert error.value.detail == auth_service.REQUIRED_AGREEMENT_ERROR
    assert db.committed is False


def test_pending_social_signup_response_returns_server_redirect_path(monkeypatch) -> None:
    pending = SimpleNamespace(
        provider="google",
        email="new.user@example.com",
        nickname="신규 소셜",
        expires_at=security.utc_now_naive() + timedelta(minutes=30),
        redirect_path="https://evil.example/phish",
    )
    monkeypatch.setattr(oauth_service, "_get_active_pending_social_signup", lambda _db, token: pending)

    result = oauth_service.get_pending_social_signup(FakeDb(), "pending-social-token")

    assert result.redirect_path == "/home"
