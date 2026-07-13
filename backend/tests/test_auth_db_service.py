from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core import security
from app.models import AuthRefreshToken, PendingSignup
from app.models import User as UserModel
from app.schemas.user import LoginRequest, RequiredAgreement, SignupCompleteRequest, SignupRequest, SignupVerifyRequest
from app.services import auth as auth_service


class FakeDb:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


def accepted_agreements() -> RequiredAgreement:
    return RequiredAgreement(
        termsAccepted=True,
        privacyAccepted=True,
        termsVersion=auth_service.CURRENT_TERMS_VERSION,
        privacyVersion=auth_service.CURRENT_PRIVACY_VERSION,
    )


def make_user(
    *,
    user_id: int = 1,
    email: str = "test.user@example.com",
    password: str = "password123",
) -> UserModel:
    return UserModel(
        id=user_id,
        email=email,
        password_hash=security.hash_password(password),
        nickname="Test User",
        onboarding_completed=False,
        nickname_setup_completed=True,
        profile_setup_skipped=False,
        created_at=datetime(2026, 5, 4, 0, 0, 0),
        updated_at=datetime(2026, 5, 4, 0, 0, 0),
    )


def test_signup_creates_pending_signup_and_sends_verification_email(monkeypatch) -> None:
    db = FakeDb()
    captured: dict[str, object] = {}

    monkeypatch.setattr(auth_service.user_repository, "get_active_user_by_email", lambda _db, email: None)
    monkeypatch.setattr(auth_service.security, "create_urlsafe_token", lambda: "raw-signup-token")
    monkeypatch.setattr(
        auth_service,
        "send_signup_verification_email",
        lambda **kwargs: captured.update({"sent_email": kwargs}),
    )
    monkeypatch.setattr(
        auth_service.pending_signup_repository,
        "delete_pending_signup_by_email",
        lambda _db, email: captured.update({"deleted_email": email}),
    )

    def create_pending(_db, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr(
        auth_service.pending_signup_repository,
        "create_pending_signup",
        create_pending,
    )

    result = auth_service.signup(
        db,
        SignupRequest(email="TEST.USER@EXAMPLE.COM", agreements=accepted_agreements()),
    )

    assert db.committed is True
    assert result == {"verificationRequired": True, "email": "test.user@example.com"}
    assert captured["email"] == "test.user@example.com"
    assert captured["token_hash"] == security.hash_token("raw-signup-token")
    assert captured["sent_email"]["to_email"] == "test.user@example.com"
    assert "raw-signup-token" in captured["sent_email"]["verify_url"]
    assert captured["deleted_email"] == "test.user@example.com"


def test_signup_send_failure_rolls_back_without_replacing_existing_pending(monkeypatch) -> None:
    db = FakeDb()
    calls: list[str] = []

    monkeypatch.setattr(auth_service.user_repository, "get_active_user_by_email", lambda _db, email: None)

    def fail_send(**_kwargs):
        raise auth_service.EmailDeliveryError("boom")

    monkeypatch.setattr(auth_service, "send_signup_verification_email", fail_send)
    monkeypatch.setattr(
        auth_service.pending_signup_repository,
        "delete_pending_signup_by_email",
        lambda *_args, **_kwargs: calls.append("delete"),
    )
    monkeypatch.setattr(
        auth_service.pending_signup_repository,
        "create_pending_signup",
        lambda *_args, **_kwargs: calls.append("create"),
    )

    with pytest.raises(auth_service.AuthServiceError) as error:
        auth_service.signup(
            db,
            SignupRequest(email="test.user@example.com", agreements=accepted_agreements()),
        )

    assert error.value.status_code == 503
    assert error.value.detail == auth_service.SIGNUP_EMAIL_DELIVERY_ERROR
    assert db.rolled_back is True
    assert calls == []


def test_verify_signup_confirms_token_without_creating_user(monkeypatch) -> None:
    db = FakeDb()
    pending = PendingSignup(
        id=1,
        email="test.user@example.com",
        token_hash=security.hash_token("raw-signup-token"),
        expires_at=security.utc_now_naive() + timedelta(minutes=30),
        terms_accepted=True,
        terms_accepted_at=security.utc_now_naive(),
        terms_version=auth_service.CURRENT_TERMS_VERSION,
        privacy_accepted=True,
        privacy_accepted_at=security.utc_now_naive(),
        privacy_version=auth_service.CURRENT_PRIVACY_VERSION,
    )

    monkeypatch.setattr(
        auth_service.pending_signup_repository,
        "get_active_pending_signup_by_token",
        lambda _db, **kwargs: pending if kwargs["token_hash"] == pending.token_hash else None,
    )
    monkeypatch.setattr(auth_service.user_repository, "get_active_user_by_email", lambda _db, email: None)

    result = auth_service.verify_signup(db, SignupVerifyRequest(token="raw-signup-token"))

    assert db.committed is False
    assert result == {"verified": True, "email": "test.user@example.com"}


def test_complete_signup_creates_user_and_refresh_token(monkeypatch) -> None:
    db = FakeDb()
    captured: dict[str, object] = {}
    pending = PendingSignup(
        id=1,
        email="test.user@example.com",
        token_hash=security.hash_token("raw-signup-token"),
        expires_at=security.utc_now_naive() + timedelta(minutes=30),
        terms_accepted=True,
        terms_accepted_at=security.utc_now_naive(),
        terms_version=auth_service.CURRENT_TERMS_VERSION,
        privacy_accepted=True,
        privacy_accepted_at=security.utc_now_naive(),
        privacy_version=auth_service.CURRENT_PRIVACY_VERSION,
    )

    def create_user(
        _db,
        *,
        email: str,
        nickname: str,
        password_hash: str,
        nickname_setup_completed: bool,
        **kwargs,
    ) -> UserModel:
        captured["email"] = email
        captured["nickname"] = nickname
        captured["password_hash"] = password_hash
        captured["nickname_setup_completed"] = nickname_setup_completed
        captured.update(kwargs)
        user = make_user(email=email)
        user.nickname = nickname
        user.password_hash = password_hash
        return user

    monkeypatch.setattr(
        auth_service.pending_signup_repository,
        "get_active_pending_signup_by_token",
        lambda _db, **kwargs: pending if kwargs["token_hash"] == pending.token_hash else None,
    )
    monkeypatch.setattr(auth_service.user_repository, "get_active_user_by_email", lambda _db, email: None)
    monkeypatch.setattr(auth_service.user_repository, "create_user", create_user)
    monkeypatch.setattr(auth_service.nicknames, "generate_random_nickname", lambda: "알뜰한여행자482")
    monkeypatch.setattr(
        auth_service.pending_signup_repository,
        "delete_pending_signup",
        lambda _db, value: captured.update({"deleted_pending": value}),
    )
    monkeypatch.setattr(
        auth_service.token_repository,
        "create_refresh_token",
        lambda _db, **kwargs: captured.update({"refresh": kwargs}),
    )

    result = auth_service.complete_signup(db, SignupCompleteRequest(token="raw-signup-token", password="password123"))

    assert db.committed is True
    assert result.access_token
    assert result.refresh_token
    assert result.user["email"] == "test.user@example.com"
    assert result.user["nicknameSetupCompleted"] is True
    assert captured["email"] == "test.user@example.com"
    assert captured["nickname"] == "알뜰한여행자482"
    assert captured["nickname_setup_completed"] is True
    assert captured["password_hash"] != "password123"
    assert security.verify_password("password123", str(captured["password_hash"]))
    assert captured["deleted_pending"] is pending
    assert captured["refresh"]["user_id"] == 1


def test_verify_signup_rejects_invalid_or_expired_token(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_service.pending_signup_repository,
        "get_active_pending_signup_by_token",
        lambda _db, **kwargs: None,
    )

    with pytest.raises(auth_service.AuthServiceError) as error:
        auth_service.verify_signup(FakeDb(), SignupVerifyRequest(token="bad-token"))

    assert error.value.status_code == 400
    assert error.value.detail == "Invalid or expired signup verification token"

def test_signup_rejects_duplicate_email(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_service.user_repository,
        "get_active_user_by_email",
        lambda _db, email: make_user(email=email),
    )

    with pytest.raises(auth_service.AuthServiceError) as error:
        auth_service.signup(
            FakeDb(),
            SignupRequest(email="test.user@example.com", agreements=accepted_agreements()),
        )

    assert error.value.status_code == 409
    assert error.value.detail == "Email already registered"


def test_email_availability_checks_duplicate_email(monkeypatch) -> None:
    monkeypatch.setattr(auth_service.user_repository, "get_active_user_by_email", lambda _db, email: None)
    assert auth_service.check_email_availability(FakeDb(), auth_service.EmailAvailabilityRequest(email="NEW@EXAMPLE.COM")) == {"available": True}

    monkeypatch.setattr(
        auth_service.user_repository,
        "get_active_user_by_email",
        lambda _db, email: make_user(email=email),
    )
    assert auth_service.check_email_availability(FakeDb(), auth_service.EmailAvailabilityRequest(email="test.user@example.com")) == {"available": False}


def test_login_issues_tokens_for_valid_credentials(monkeypatch) -> None:
    db = FakeDb()
    user = make_user()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        auth_service.user_repository,
        "get_active_user_by_email",
        lambda _db, email: user if email == user.email else None,
    )
    monkeypatch.setattr(
        auth_service.token_repository,
        "create_refresh_token",
        lambda _db, **kwargs: captured.update(kwargs),
    )

    result = auth_service.login(
        db,
        LoginRequest(email="test.user@example.com", password="password123"),
    )

    assert db.committed is True
    assert result.access_token
    assert result.refresh_token
    assert result.user["id"] == "1"
    assert captured["user_id"] == 1


def test_login_rejects_invalid_credentials(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_service.user_repository,
        "get_active_user_by_email",
        lambda _db, email: make_user(email=email),
    )

    with pytest.raises(auth_service.AuthServiceError) as error:
        auth_service.login(
            FakeDb(),
            LoginRequest(email="test.user@example.com", password="wrong-password"),
        )

    assert error.value.status_code == 401
    assert error.value.detail == "Invalid email or password"


def test_refresh_rotates_active_token(monkeypatch) -> None:
    db = FakeDb()
    user = make_user()
    old_raw_token = "old-refresh-token"
    token = AuthRefreshToken(
        id=1,
        user_id=1,
        refresh_token_hash=security.hash_refresh_token(old_raw_token),
        expires_at=security.utc_now_naive() + timedelta(days=1),
    )
    token.user = user
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        auth_service.token_repository,
        "get_active_refresh_token_by_hash",
        lambda _db, **kwargs: token,
    )
    monkeypatch.setattr(
        auth_service.token_repository,
        "create_refresh_token",
        lambda _db, **kwargs: captured.update(kwargs),
    )

    result = auth_service.refresh(db, old_raw_token)

    assert db.committed is True
    assert token.revoked_at is not None
    assert result.access_token
    assert result.refresh_token
    assert captured["user_id"] == 1
    assert captured["refresh_token_hash"] != token.refresh_token_hash


def test_refresh_rejects_missing_or_invalid_token(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_service.token_repository,
        "get_active_refresh_token_by_hash",
        lambda _db, **kwargs: None,
    )

    for token in [None, "invalid-token"]:
        with pytest.raises(auth_service.AuthServiceError) as error:
            auth_service.refresh(FakeDb(), token)
        assert error.value.status_code == 401
        assert error.value.detail == "Invalid refresh token"


def test_logout_revokes_active_refresh_token(monkeypatch) -> None:
    db = FakeDb()
    token = SimpleNamespace(revoked_at=None)

    monkeypatch.setattr(
        auth_service.token_repository,
        "get_active_refresh_token_by_hash",
        lambda _db, **kwargs: token,
    )

    auth_service.logout(db, "refresh-token")

    assert token.revoked_at is not None
    assert db.committed is True


def test_password_reset_request_does_not_expose_unknown_email(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_service.user_repository,
        "get_active_user_by_email",
        lambda _db, _email: None,
    )

    result = auth_service.request_password_reset(
        FakeDb(),
        auth_service.PasswordResetRequest(email="unknown@example.com"),
    )

    assert result == {"requested": True}


def test_password_reset_request_stores_hash_and_sends_email(monkeypatch) -> None:
    db = FakeDb()
    user = make_user()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        auth_service.user_repository,
        "get_active_user_by_email",
        lambda _db, email: user if email == user.email else None,
    )
    monkeypatch.setattr(auth_service.security, "create_urlsafe_token", lambda: "raw-reset-token")
    monkeypatch.setattr(
        auth_service.password_reset_repository,
        "create_password_reset_token",
        lambda _db, **kwargs: captured.update(kwargs),
    )
    monkeypatch.setattr(
        auth_service,
        "send_password_reset_email",
        lambda **kwargs: captured.update({"sent_email": kwargs}),
    )

    result = auth_service.request_password_reset(
        db,
        auth_service.PasswordResetRequest(email="TEST.USER@EXAMPLE.COM"),
    )

    assert result == {"requested": True}
    assert db.committed is True
    assert captured["user_id"] == 1
    assert captured["token_hash"] != "raw-reset-token"
    assert captured["sent_email"]["to_email"] == user.email
    assert "raw-reset-token" in captured["sent_email"]["reset_url"]


def test_password_reset_confirm_changes_password_and_revokes_sessions(monkeypatch) -> None:
    db = FakeDb()
    user = make_user()
    token = SimpleNamespace(user=user, user_id=user.id, used_at=None)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        auth_service.password_reset_repository,
        "get_active_password_reset_token",
        lambda _db, **kwargs: token,
    )
    monkeypatch.setattr(
        auth_service.user_repository,
        "update_user_password",
        lambda _db, _user, **kwargs: captured.update(kwargs),
    )
    monkeypatch.setattr(
        auth_service.password_reset_repository,
        "mark_password_reset_token_used",
        lambda _db, _token, **kwargs: captured.update({"used_at": kwargs["used_at"]}),
    )
    monkeypatch.setattr(
        auth_service.token_repository,
        "revoke_user_refresh_tokens",
        lambda _db, **kwargs: captured.update({"revoked": kwargs}),
    )

    result = auth_service.confirm_password_reset(
        db,
        auth_service.PasswordResetConfirm(token="raw-reset-token", newPassword="new-password123"),
    )

    assert result == {"reset": True}
    assert db.committed is True
    assert captured["password_hash"] != "new-password123"
    assert security.verify_password("new-password123", str(captured["password_hash"]))
    assert captured["used_at"] is not None
    assert captured["revoked"]["user_id"] == 1


def test_user_to_api_exposes_has_password() -> None:
    assert auth_service.user_to_api(make_user(password="password123"))["hasPassword"] is True
    assert auth_service.user_to_api(make_user(password="password123", email="oauth@example.com"))[
        "hasPassword"
    ] is True
    passwordless = make_user(email="oauth-only@example.com")
    passwordless.password_hash = None
    assert auth_service.user_to_api(passwordless)["hasPassword"] is False


def test_change_password_updates_hash_and_revokes_refresh_tokens(monkeypatch) -> None:
    db = FakeDb()
    user = make_user(password="old-password123")
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        auth_service.user_repository,
        "update_user_password",
        lambda _db, _user, **kwargs: captured.update(kwargs),
    )
    monkeypatch.setattr(
        auth_service.token_repository,
        "revoke_user_refresh_tokens",
        lambda _db, **kwargs: captured.update({"revoked": kwargs}),
    )

    result = auth_service.change_password(
        db,
        user,
        auth_service.PasswordChangeRequest(
            currentPassword="old-password123",
            newPassword="new-password123",
        ),
    )

    assert result == {"changed": True}
    assert db.committed is True
    assert captured["password_hash"] != "new-password123"
    assert security.verify_password("new-password123", str(captured["password_hash"]))
    assert captured["revoked"]["user_id"] == 1


def test_change_password_rejects_wrong_password_and_passwordless(monkeypatch) -> None:
    def fail_update(*_args, **_kwargs):
        raise AssertionError("password should not be updated")

    monkeypatch.setattr(auth_service.user_repository, "update_user_password", fail_update)
    user = make_user(password="old-password123")

    with pytest.raises(auth_service.AuthServiceError) as wrong_password:
        auth_service.change_password(
            FakeDb(),
            user,
            auth_service.PasswordChangeRequest(
                currentPassword="wrong-password",
                newPassword="new-password123",
            ),
        )
    assert wrong_password.value.status_code == 401

    passwordless = make_user()
    passwordless.password_hash = None
    with pytest.raises(auth_service.AuthServiceError) as passwordless_error:
        auth_service.change_password(
            FakeDb(),
            passwordless,
            auth_service.PasswordChangeRequest(
                currentPassword="anything",
                newPassword="new-password123",
            ),
        )
    assert passwordless_error.value.status_code == 400


def test_withdraw_password_user_requires_password_and_soft_withdraws(monkeypatch) -> None:
    db = FakeDb()
    user = make_user(password="password123")
    captured: dict[str, object] = {}

    def soft_withdraw(_db, current_user):
        captured["user"] = current_user
        return current_user

    from app.services import account_withdrawal

    monkeypatch.setattr(account_withdrawal, "soft_withdraw_user", soft_withdraw)

    result = auth_service.withdraw(
        db,
        user,
        auth_service.WithdrawRequest(password="password123"),
    )

    assert result == {"withdrawn": True}
    assert captured["user"] is user
    assert db.committed is True

    with pytest.raises(auth_service.AuthServiceError) as missing:
        auth_service.withdraw(FakeDb(), user, auth_service.WithdrawRequest())
    assert missing.value.status_code == 400

    with pytest.raises(auth_service.AuthServiceError) as extra:
        auth_service.withdraw(
            FakeDb(),
            user,
            auth_service.WithdrawRequest(password="password123", confirmationPhrase="탈퇴합니다"),
        )
    assert extra.value.status_code == 400

    with pytest.raises(auth_service.AuthServiceError) as explicit_null_extra:
        auth_service.withdraw(
            FakeDb(),
            user,
            auth_service.WithdrawRequest(password="password123", confirmationPhrase=None),
        )
    assert explicit_null_extra.value.status_code == 400

    with pytest.raises(auth_service.AuthServiceError) as wrong:
        auth_service.withdraw(FakeDb(), user, auth_service.WithdrawRequest(password="wrong"))
    assert wrong.value.status_code == 401


def test_withdraw_passwordless_user_requires_confirmation_phrase(monkeypatch) -> None:
    db = FakeDb()
    user = make_user()
    user.password_hash = None
    captured: dict[str, object] = {}

    from app.services import account_withdrawal

    monkeypatch.setattr(
        account_withdrawal,
        "soft_withdraw_user",
        lambda _db, current_user: captured.update({"user": current_user}),
    )

    result = auth_service.withdraw(
        db,
        user,
        auth_service.WithdrawRequest(confirmationPhrase="탈퇴합니다"),
    )

    assert result == {"withdrawn": True}
    assert captured["user"] is user
    assert db.committed is True

    for request in [
        auth_service.WithdrawRequest(),
        auth_service.WithdrawRequest(confirmationPhrase="wrong"),
        auth_service.WithdrawRequest(password="password123", confirmationPhrase="탈퇴합니다"),
        auth_service.WithdrawRequest(password=None, confirmationPhrase="탈퇴합니다"),
    ]:
        with pytest.raises(auth_service.AuthServiceError) as error:
            auth_service.withdraw(FakeDb(), user, request)
        assert error.value.status_code == 400


def test_refresh_rejects_withdrawn_token_user(monkeypatch) -> None:
    db = FakeDb()
    user = make_user()
    user.withdrawn_at = security.utc_now_naive()
    token = AuthRefreshToken(
        id=1,
        user_id=1,
        refresh_token_hash=security.hash_refresh_token("old-refresh-token"),
        expires_at=security.utc_now_naive() + timedelta(days=1),
    )
    token.user = user

    monkeypatch.setattr(
        auth_service.token_repository,
        "get_active_refresh_token_by_hash",
        lambda _db, **kwargs: token,
    )
    monkeypatch.setattr(
        auth_service.token_repository,
        "create_refresh_token",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("new token issued")),
    )

    with pytest.raises(auth_service.AuthServiceError) as error:
        auth_service.refresh(db, "old-refresh-token")

    assert error.value.status_code == 401
    assert token.revoked_at is not None
    assert db.committed is True


def test_password_reset_request_ignores_passwordless_user(monkeypatch) -> None:
    passwordless = make_user()
    passwordless.password_hash = None

    monkeypatch.setattr(
        auth_service.user_repository,
        "get_active_user_by_email",
        lambda _db, email: passwordless,
    )
    monkeypatch.setattr(
        auth_service.password_reset_repository,
        "create_password_reset_token",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("token created")),
    )

    result = auth_service.request_password_reset(
        FakeDb(),
        auth_service.PasswordResetRequest(email="oauth@example.com"),
    )

    assert result == {"requested": True}


def test_password_reset_confirm_rejects_withdrawn_or_passwordless_user(monkeypatch) -> None:
    user = make_user()
    token = SimpleNamespace(user=user, user_id=user.id, used_at=None)

    monkeypatch.setattr(
        auth_service.password_reset_repository,
        "get_active_password_reset_token",
        lambda _db, **kwargs: token,
    )
    monkeypatch.setattr(
        auth_service.user_repository,
        "update_user_password",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("password updated")),
    )

    user.withdrawn_at = security.utc_now_naive()
    with pytest.raises(auth_service.AuthServiceError) as withdrawn:
        auth_service.confirm_password_reset(
            FakeDb(),
            auth_service.PasswordResetConfirm(token="raw-reset-token", newPassword="new-password123"),
        )
    assert withdrawn.value.status_code == 400

    user.withdrawn_at = None
    user.password_hash = None
    with pytest.raises(auth_service.AuthServiceError) as passwordless:
        auth_service.confirm_password_reset(
            FakeDb(),
            auth_service.PasswordResetConfirm(token="raw-reset-token", newPassword="new-password123"),
        )
    assert passwordless.value.status_code == 400
