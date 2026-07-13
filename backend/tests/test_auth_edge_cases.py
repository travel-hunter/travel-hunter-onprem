"""Auth edge case tests.

Covers:
- Signup email-first and completion password boundary validation (Pydantic schema)
- Invalid email format rejection (Pydantic schema)
- Expired / invalid password reset token -> AuthServiceError(400)
- OAuth state mismatch / missing -> OAuthServiceError(400)
- OAuth redirect path safety (open redirect guard)
- Unknown OAuth provider -> OAuthServiceError(404)
"""
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.models import User as UserModel
from app.schemas.user import LoginRequest, NicknameUpdate, RequiredAgreement, SignupCompleteRequest, SignupRequest
from app.services import auth as auth_service
from app.services import oauth as oauth_service
from app.services.auth import AuthServiceError


KAKAO_PROVIDER_ID = "12345"
KAKAO_PLACEHOLDER_EMAIL = f"kakao_{KAKAO_PROVIDER_ID}@oauth.local"
KAKAO_VERIFIED_EMAIL = "real.user@example.com"


def accepted_agreements() -> RequiredAgreement:
    return RequiredAgreement(
        termsAccepted=True,
        privacyAccepted=True,
        termsVersion=auth_service.CURRENT_TERMS_VERSION,
        privacyVersion=auth_service.CURRENT_PRIVACY_VERSION,
    )


def _kakao_profile(
    *,
    email: str | None = KAKAO_VERIFIED_EMAIL,
    email_verified: bool = True,
    provider_id: str = KAKAO_PROVIDER_ID,
) -> oauth_service.OAuthProfile:
    return oauth_service.OAuthProfile(
        provider_id=provider_id,
        email=email,
        email_verified=email_verified,
        nickname="Kakao User",
    )


def _user(
    *,
    user_id: int,
    email: str,
    nickname: str = "Kakao User",
    password_hash: str | None = None,
) -> UserModel:
    user = UserModel(email=email, nickname=nickname, password_hash=password_hash)
    user.id = user_id
    return user


# ---------------------------------------------------------------------------
# Schema: signup email-first and completion password length boundary
# ---------------------------------------------------------------------------


def test_signup_request_is_email_first() -> None:
    req = SignupRequest(email="a@example.com", agreements=accepted_agreements())
    assert req.email == "a@example.com"


def test_signup_complete_rejects_password_shorter_than_8_chars() -> None:
    with pytest.raises(ValidationError):
        SignupCompleteRequest(token="verified-token", password="short7")


def test_signup_complete_accepts_password_of_exactly_8_chars() -> None:
    req = SignupCompleteRequest(token="verified-token", password="exactly8")
    assert req.password == "exactly8"


def test_login_rejects_empty_password() -> None:
    with pytest.raises(ValidationError):
        LoginRequest(email="a@example.com", password="")


def test_login_accepts_single_char_password() -> None:
    req = LoginRequest(email="a@example.com", password="x")
    assert req.password == "x"


# ---------------------------------------------------------------------------
# Schema: email format validation
# ---------------------------------------------------------------------------


def test_signup_rejects_invalid_email_formats() -> None:
    for bad_email in ["notanemail", "missing@", "@domain.com", "two@@domain.com", "space @domain.com"]:
        with pytest.raises(ValidationError):
            SignupRequest(email=bad_email, agreements=accepted_agreements())


def test_signup_normalizes_valid_email() -> None:
    req = SignupRequest(email="User@Example.COM", agreements=accepted_agreements())
    assert "@" in req.email


# ---------------------------------------------------------------------------
# Schema: nickname pattern validation
# ---------------------------------------------------------------------------


def test_nickname_update_rejects_special_chars() -> None:
    for bad in ["hello!", "nick@", "닉!네임"]:
        with pytest.raises(ValidationError):
            NicknameUpdate(nickname=bad)


def test_nickname_update_rejects_single_char() -> None:
    with pytest.raises(ValidationError):
        NicknameUpdate(nickname="a")


def test_nickname_update_accepts_valid_formats() -> None:
    for good in ["ab", "김철수", "TravelKing", "nick_123", "여행자99", "nick name", "여행 헌터"]:
        req = NicknameUpdate(nickname=good)
        assert req.nickname == good


def test_nickname_update_rejects_over_20_chars() -> None:
    with pytest.raises(ValidationError):
        NicknameUpdate(nickname="a" * 21)


# ---------------------------------------------------------------------------
# Service: expired / invalid password reset token
# ---------------------------------------------------------------------------


class FakeDb:
    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def test_confirm_password_reset_rejects_expired_token(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_service.password_reset_repository,
        "get_active_password_reset_token",
        lambda _db, **kwargs: None,
    )

    with pytest.raises(AuthServiceError) as exc_info:
        auth_service.confirm_password_reset(
            FakeDb(),
            auth_service.PasswordResetConfirm(token="expired-token", newPassword="newpassword123"),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid or expired reset token"


def test_confirm_password_reset_rejects_tampered_token(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_service.password_reset_repository,
        "get_active_password_reset_token",
        lambda _db, **kwargs: None,
    )

    with pytest.raises(AuthServiceError) as exc_info:
        auth_service.confirm_password_reset(
            FakeDb(),
            auth_service.PasswordResetConfirm(token="tampered-xyz-999", newPassword="newpassword123"),
        )

    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Service: OAuth state validation
# ---------------------------------------------------------------------------


def test_oauth_callback_rejects_state_mismatch() -> None:
    with pytest.raises(oauth_service.OAuthServiceError) as exc_info:
        oauth_service.complete_oauth_callback(
            db=FakeDb(),
            provider="kakao",
            code="some-code",
            state="state-A:/home",
            state_cookie="state-B:/home",
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "invalid_state"


def test_oauth_callback_rejects_missing_code() -> None:
    with pytest.raises(oauth_service.OAuthServiceError) as exc_info:
        oauth_service.complete_oauth_callback(
            db=FakeDb(),
            provider="kakao",
            code=None,
            state="state:/home",
            state_cookie="state:/home",
        )

    assert exc_info.value.status_code == 400


def test_google_profile_requires_verified_email() -> None:
    profile = oauth_service._extract_profile(
        "google",
        {
            "sub": "google-user-1",
            "email": "owner@example.com",
            "email_verified": False,
            "name": "Google User",
        },
    )

    with pytest.raises(oauth_service.OAuthServiceError) as exc_info:
        oauth_service._candidate_email_or_error("google", profile)

    assert exc_info.value.status_code == 400
    assert "email policy" in exc_info.value.detail


def test_google_verified_email_links_existing_user(monkeypatch) -> None:
    existing_user = UserModel(email="owner@example.com", nickname="Owner", password_hash="hash")
    captured: dict[str, object] = {}
    profile = oauth_service.OAuthProfile(
        provider_id="google-user-1",
        email="Owner@Example.com",
        email_verified=True,
        nickname="Google User",
    )

    monkeypatch.setattr(oauth_service.user_repository, "get_active_social_account", lambda *args, **kwargs: None)
    monkeypatch.setattr(oauth_service.user_repository, "get_active_user_by_email", lambda _db, email: existing_user)
    monkeypatch.setattr(
        oauth_service.user_repository,
        "create_social_account",
        lambda _db, **kwargs: captured.update(kwargs),
    )

    user = oauth_service._find_existing_oauth_user(FakeDb(), provider="google", profile=profile)

    assert user is existing_user
    assert captured["user"] is existing_user
    assert captured["provider"] == "google"
    assert captured["provider_id"] == "google-user-1"


def test_kakao_unverified_email_creates_pending_placeholder_without_linking_existing_email_user(monkeypatch) -> None:
    existing_user = UserModel(email="owner@example.com", nickname="Owner", password_hash="hash")
    calls: dict[str, list[str] | object] = {"lookups": []}
    profile = _kakao_profile(
        email="owner@example.com",
        email_verified=False,
    )

    monkeypatch.setattr(oauth_service.security, "create_urlsafe_token", lambda: "pending-social-token")
    monkeypatch.setattr(
        oauth_service.pending_social_signup_repository,
        "delete_pending_social_signup_by_provider",
        lambda *_args, **kwargs: calls.update({"deleted": kwargs}),
    )
    monkeypatch.setattr(
        oauth_service.pending_social_signup_repository,
        "create_pending_social_signup",
        lambda *_args, **kwargs: calls.update({"pending": kwargs}),
    )

    def get_active_user_by_email(_db, email):
        calls["lookups"].append(email)
        return existing_user if email == "owner@example.com" else None

    monkeypatch.setattr(oauth_service.user_repository, "get_active_user_by_email", get_active_user_by_email)

    token = oauth_service._create_pending_social_signup(
        FakeDb(),
        provider="kakao",
        profile=profile,
        redirect="/invites/abc/accept",
    )

    assert token == "pending-social-token"
    assert calls["lookups"] == []
    pending = calls["pending"]
    assert pending["email"] == KAKAO_PLACEHOLDER_EMAIL
    assert pending["redirect_path"] == "/invites/abc/accept"


def test_existing_kakao_placeholder_email_upgrades_to_verified_email(monkeypatch) -> None:
    linked_user = _user(user_id=10, email=KAKAO_PLACEHOLDER_EMAIL)
    social_account = SimpleNamespace(user=linked_user)
    profile = _kakao_profile(
        email="Real.User@Example.com",
    )
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        oauth_service.user_repository,
        "get_active_social_account",
        lambda *args, **kwargs: social_account,
    )
    monkeypatch.setattr(oauth_service.user_repository, "get_active_user_by_email", lambda _db, email: None)

    def update_user_email(_db, user, *, email):
        calls["email"] = email
        user.email = email
        return user

    monkeypatch.setattr(oauth_service.user_repository, "update_user_email", update_user_email)

    user = oauth_service._find_existing_oauth_user(FakeDb(), provider="kakao", profile=profile)

    assert user is linked_user
    assert user.email == KAKAO_VERIFIED_EMAIL
    assert calls["email"] == KAKAO_VERIFIED_EMAIL


def test_existing_kakao_placeholder_email_does_not_upgrade_when_email_belongs_to_other_user(monkeypatch) -> None:
    linked_user = _user(user_id=10, email=KAKAO_PLACEHOLDER_EMAIL)
    other_user = _user(
        user_id=20,
        email=KAKAO_VERIFIED_EMAIL,
        nickname="Email Owner",
        password_hash="hash",
    )
    social_account = SimpleNamespace(user=linked_user)
    profile = _kakao_profile()

    monkeypatch.setattr(
        oauth_service.user_repository,
        "get_active_social_account",
        lambda *args, **kwargs: social_account,
    )
    monkeypatch.setattr(oauth_service.user_repository, "get_active_user_by_email", lambda _db, email: other_user)

    def fail_update(*args, **kwargs):
        raise AssertionError("conflicting email must not be updated automatically")

    monkeypatch.setattr(oauth_service.user_repository, "update_user_email", fail_update)

    user = oauth_service._find_existing_oauth_user(FakeDb(), provider="kakao", profile=profile)

    assert user is linked_user
    assert user.email == KAKAO_PLACEHOLDER_EMAIL


def test_existing_social_account_wins_even_when_email_unverified(monkeypatch) -> None:
    linked_user = UserModel(email="linked@example.com", nickname="Linked", password_hash=None)
    social_account = type("SocialAccountStub", (), {"user": linked_user})()
    profile = oauth_service.OAuthProfile(
        provider_id="google-user-1",
        email="changed@example.com",
        email_verified=False,
        nickname="Google User",
    )

    monkeypatch.setattr(
        oauth_service.user_repository,
        "get_active_social_account",
        lambda *args, **kwargs: social_account,
    )

    assert oauth_service._find_existing_oauth_user(FakeDb(), provider="google", profile=profile) is linked_user


def test_oauth_callback_rejects_missing_state() -> None:
    with pytest.raises(oauth_service.OAuthServiceError) as exc_info:
        oauth_service.complete_oauth_callback(
            db=FakeDb(),
            provider="kakao",
            code="some-code",
            state=None,
            state_cookie="state:/home",
        )

    assert exc_info.value.status_code == 400


def test_oauth_callback_rejects_missing_state_cookie() -> None:
    with pytest.raises(oauth_service.OAuthServiceError) as exc_info:
        oauth_service.complete_oauth_callback(
            db=FakeDb(),
            provider="kakao",
            code="some-code",
            state="state:/home",
            state_cookie=None,
        )

    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Service: OAuth redirect path safety (open redirect guard)
# ---------------------------------------------------------------------------


def test_safe_redirect_path_allows_relative_paths() -> None:
    assert oauth_service.safe_redirect_path("/home") == "/home"
    assert oauth_service.safe_redirect_path("/trips/new") == "/trips/new"


def test_safe_redirect_path_rejects_external_urls() -> None:
    assert oauth_service.safe_redirect_path("https://evil.com") == "/home"
    assert oauth_service.safe_redirect_path("http://evil.com/steal") == "/home"


def test_safe_redirect_path_rejects_protocol_relative_urls() -> None:
    assert oauth_service.safe_redirect_path("//evil.com") == "/home"


def test_safe_redirect_path_falls_back_for_empty_or_none() -> None:
    assert oauth_service.safe_redirect_path(None) == "/home"
    assert oauth_service.safe_redirect_path("") == "/home"


# ---------------------------------------------------------------------------
# Service: OAuth provider authorization parameters
# ---------------------------------------------------------------------------


def test_kakao_authorization_redirect_requests_configured_email_scope(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        oauth_service,
        "settings",
        Settings(
            kakao_client_id="kakao-rest-key",
            kakao_client_secret="kakao-client-secret",
            kakao_redirect_uri=(
                "https://dev.travel-hunter.co.kr/api/auth/oauth/kakao/callback"
            ),
        ),
    )

    result = oauth_service.build_authorization_redirect("kakao", redirect="/home")
    query = parse_qs(urlparse(result.authorization_url).query)

    assert query["client_id"] == ["kakao-rest-key"]
    assert query["redirect_uri"] == [
        "https://dev.travel-hunter.co.kr/api/auth/oauth/kakao/callback"
    ]
    assert query["scope"] == ["account_email"]


# ---------------------------------------------------------------------------
# Service: unknown OAuth provider
# ---------------------------------------------------------------------------


def test_unknown_oauth_provider_raises_404() -> None:
    with pytest.raises(oauth_service.OAuthServiceError) as exc_info:
        oauth_service.build_authorization_redirect("naver", redirect=None)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail.lower()


def test_oauth_lookup_uses_active_user_paths_for_withdrawn_fail_closed(monkeypatch) -> None:
    profile = oauth_service.OAuthProfile(
        provider_id="google-user-1",
        email="withdrawn@example.com",
        email_verified=True,
        nickname="Withdrawn User",
    )
    calls: dict[str, object] = {}

    def get_active_social_account(_db, **kwargs):
        calls["social"] = kwargs
        return None

    def get_active_user_by_email(_db, email):
        calls["email"] = email
        return None

    monkeypatch.setattr(oauth_service.user_repository, "get_active_social_account", get_active_social_account)
    monkeypatch.setattr(oauth_service.user_repository, "get_active_user_by_email", get_active_user_by_email)
    monkeypatch.setattr(
        oauth_service.user_repository,
        "create_social_account",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("withdrawn user linked")),
    )

    assert oauth_service._find_existing_oauth_user(FakeDb(), provider="google", profile=profile) is None
    assert calls["social"] == {"provider": "google", "provider_id": "google-user-1"}
    assert calls["email"] == "withdrawn@example.com"


def test_get_current_user_rejects_withdrawn_user(monkeypatch) -> None:
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    from app.api import dependencies

    monkeypatch.setattr(dependencies.security, "decode_access_token", lambda token: "1")
    monkeypatch.setattr(dependencies.user_repository, "get_active_user_by_id", lambda _db, user_id: None)

    with pytest.raises(HTTPException) as error:
        dependencies.get_current_user(
            credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials="access-token"),
            db=FakeDb(),
        )

    assert error.value.status_code == 401
    assert error.value.detail == "Not authenticated"


def test_password_change_and_withdraw_requests_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        auth_service.PasswordChangeRequest(
            currentPassword="old-password",
            newPassword="new-password123",
            unexpected=True,
        )

    with pytest.raises(ValidationError):
        auth_service.WithdrawRequest(password="password123", unexpected=True)
