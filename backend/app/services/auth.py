from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.models import User as UserModel
from app.repositories import auth_tokens as token_repository
from app.repositories import pending_signups as pending_signup_repository
from app.repositories import password_resets as password_reset_repository
from app.repositories import users as user_repository
from app.schemas.user import (
    EmailAvailabilityRequest,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RequiredAgreement,
    SignupCompleteRequest,
    SignupRequest,
    SignupVerifyRequest,
    WithdrawRequest,
)
from app.services import nicknames
from app.services.email import (
    EmailDeliveryError,
    send_password_reset_email,
    send_signup_verification_email,
)
from app.services.profile_preferences import parse_preferred_regions


class AuthServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class AuthResult:
    access_token: str
    refresh_token: str
    user: dict[str, object]


SIGNUP_EMAIL_DELIVERY_ERROR = "인증 메일을 보낼 수 없습니다. 잠시 후 다시 시도해 주세요."
SIGNUP_VERIFICATION_EXPIRE_MINUTES = 30
CURRENT_TERMS_VERSION = "2026-06-26"
CURRENT_PRIVACY_VERSION = "2026-06-26"
REQUIRED_AGREEMENT_ERROR = "Required agreements must be accepted"
WITHDRAW_CONFIRMATION_PHRASE = "탈퇴합니다"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_required_agreements(agreements: RequiredAgreement) -> datetime:
    if (
        not agreements.termsAccepted
        or not agreements.privacyAccepted
        or agreements.termsVersion != CURRENT_TERMS_VERSION
        or agreements.privacyVersion != CURRENT_PRIVACY_VERSION
    ):
        raise AuthServiceError(400, REQUIRED_AGREEMENT_ERROR)
    return security.utc_now_naive()


def _iso_datetime(value: datetime | None) -> str:
    current = value or security.utc_now_naive()
    return current.isoformat()


def user_to_api(user: UserModel) -> dict[str, object]:
    social_accounts = [
        {
            "provider": account.provider,
            "providerNickname": account.provider_nickname,
            "connectedAt": _iso_datetime(account.created_at),
        }
        for account in user.social_accounts
    ]

    return {
        "id": str(user.id),
        "nickname": user.nickname,
        "email": user.email,
        "role": getattr(user, "role", "user") or "user",
        "hasPassword": bool(user.password_hash),
        "preferredRegions": parse_preferred_regions(user.preferred_regions),
        "persona": "Travel Hunter 사용자",
        "savedAmount": 0,
        "onboardingCompleted": bool(user.onboarding_completed),
        "nicknameSetupCompleted": bool(user.nickname_setup_completed),
        "socialAccounts": social_accounts,
        "createdAt": _iso_datetime(user.created_at),
        "updatedAt": _iso_datetime(user.updated_at),
    }


def _issue_tokens(db: Session, user: UserModel) -> AuthResult:
    refresh_token = security.create_refresh_token()
    token_repository.create_refresh_token(
        db,
        user_id=int(user.id),
        refresh_token_hash=security.hash_refresh_token(refresh_token),
        expires_at=security.refresh_token_expires_at(),
    )
    access_token = security.create_access_token(user.id)
    return AuthResult(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_to_api(user),
    )


def signup(db: Session, request: SignupRequest) -> dict[str, object]:
    email = normalize_email(str(request.email))
    accepted_at = validate_required_agreements(request.agreements)
    if user_repository.get_active_user_by_email(db, email) is not None:
        raise AuthServiceError(409, "Email already registered")

    raw_token = security.create_urlsafe_token()
    token_hash = security.hash_token(raw_token)
    expires_at = security.utc_now_naive() + timedelta(minutes=SIGNUP_VERIFICATION_EXPIRE_MINUTES)
    verify_url = f"{_frontend_base_url()}/signup/verify?token={raw_token}"

    try:
        send_signup_verification_email(to_email=email, verify_url=verify_url)
    except EmailDeliveryError as error:
        db.rollback()
        raise AuthServiceError(503, SIGNUP_EMAIL_DELIVERY_ERROR) from error

    pending_signup_repository.delete_pending_signup_by_email(db, email)
    pending_signup_repository.create_pending_signup(
        db,
        email=email,
        token_hash=token_hash,
        expires_at=expires_at,
        terms_accepted=True,
        terms_accepted_at=accepted_at,
        terms_version=request.agreements.termsVersion,
        privacy_accepted=True,
        privacy_accepted_at=accepted_at,
        privacy_version=request.agreements.privacyVersion,
    )
    db.commit()
    return {"verificationRequired": True, "email": email}


def _get_verified_pending_signup(db: Session, token: str):
    pending = pending_signup_repository.get_active_pending_signup_by_token(
        db,
        token_hash=security.hash_token(token),
        now=security.utc_now_naive(),
    )
    if pending is None:
        raise AuthServiceError(400, "Invalid or expired signup verification token")
    if user_repository.get_active_user_by_email(db, pending.email) is not None:
        pending_signup_repository.delete_pending_signup(db, pending)
        db.commit()
        raise AuthServiceError(409, "Email already registered")
    return pending


def verify_signup(db: Session, request: SignupVerifyRequest) -> dict[str, object]:
    pending = _get_verified_pending_signup(db, request.token)
    return {"verified": True, "email": pending.email}


def complete_signup(db: Session, request: SignupCompleteRequest) -> AuthResult:
    pending = _get_verified_pending_signup(db, request.token)
    if (
        not pending.terms_accepted
        or not pending.privacy_accepted
        or pending.terms_version != CURRENT_TERMS_VERSION
        or pending.privacy_version != CURRENT_PRIVACY_VERSION
        or pending.terms_accepted_at is None
        or pending.privacy_accepted_at is None
    ):
        raise AuthServiceError(400, REQUIRED_AGREEMENT_ERROR)
    user = user_repository.create_user(
        db,
        email=pending.email,
        nickname=nicknames.generate_random_nickname(),
        password_hash=security.hash_password(request.password),
        nickname_setup_completed=True,
        terms_accepted=True,
        terms_accepted_at=pending.terms_accepted_at,
        terms_version=pending.terms_version,
        privacy_accepted=True,
        privacy_accepted_at=pending.privacy_accepted_at,
        privacy_version=pending.privacy_version,
    )
    pending_signup_repository.delete_pending_signup(db, pending)
    result = _issue_tokens(db, user)
    db.commit()
    return result


def check_email_availability(db: Session, request: EmailAvailabilityRequest) -> dict[str, bool]:
    email = normalize_email(str(request.email))
    return {"available": user_repository.get_active_user_by_email(db, email) is None}


def login(db: Session, request: LoginRequest) -> AuthResult:
    email = normalize_email(str(request.email))
    user = user_repository.get_active_user_by_email(db, email)
    if user is None or not security.verify_password(request.password, user.password_hash):
        raise AuthServiceError(401, "Invalid email or password")

    result = _issue_tokens(db, user)
    db.commit()
    return result


def refresh(db: Session, refresh_token: str | None) -> AuthResult:
    if not refresh_token:
        raise AuthServiceError(401, "Invalid refresh token")

    now = security.utc_now_naive()
    token = token_repository.get_active_refresh_token_by_hash(
        db,
        refresh_token_hash=security.hash_refresh_token(refresh_token),
        now=now,
    )
    if token is None:
        raise AuthServiceError(401, "Invalid refresh token")

    if not user_repository.is_user_active(token.user):
        token_repository.revoke_refresh_token(db, token, revoked_at=now)
        db.commit()
        raise AuthServiceError(401, "Invalid refresh token")

    token_repository.revoke_refresh_token(db, token, revoked_at=now)
    result = _issue_tokens(db, token.user)
    db.commit()
    return result


def logout(db: Session, refresh_token: str | None) -> None:
    if not refresh_token:
        return

    token = token_repository.get_active_refresh_token_by_hash(
        db,
        refresh_token_hash=security.hash_refresh_token(refresh_token),
        now=security.utc_now_naive(),
    )
    if token is None:
        return

    token_repository.revoke_refresh_token(db, token, revoked_at=security.utc_now_naive())
    db.commit()


def change_password(db: Session, user: UserModel, request: PasswordChangeRequest) -> dict[str, bool]:
    if not user_repository.is_user_active(user):
        raise AuthServiceError(401, "Not authenticated")
    if not user.password_hash:
        raise AuthServiceError(400, "Password change is not available for this account")
    if not security.verify_password(request.currentPassword, user.password_hash):
        raise AuthServiceError(401, "Invalid password")

    now = security.utc_now_naive()
    user_repository.update_user_password(
        db,
        user,
        password_hash=security.hash_password(request.newPassword),
    )
    token_repository.revoke_user_refresh_tokens(db, user_id=int(user.id), revoked_at=now)
    db.commit()
    return {"changed": True}


def withdraw(db: Session, user: UserModel, request: WithdrawRequest) -> dict[str, bool]:
    if not user_repository.is_user_active(user):
        raise AuthServiceError(401, "Not authenticated")

    password = request.password
    phrase = request.confirmationPhrase
    provided_fields = request.model_fields_set
    has_password = bool(user.password_hash)

    if has_password:
        if password is None or "confirmationPhrase" in provided_fields:
            raise AuthServiceError(400, "Password is required for withdrawal")
        if not security.verify_password(password, user.password_hash):
            raise AuthServiceError(401, "Invalid password")
    else:
        if "password" in provided_fields or phrase != WITHDRAW_CONFIRMATION_PHRASE:
            raise AuthServiceError(400, "Confirmation phrase is required for withdrawal")

    from app.services import account_withdrawal

    account_withdrawal.soft_withdraw_user(db, user)
    db.commit()
    return {"withdrawn": True}


def _frontend_base_url() -> str:
    return settings.frontend_base_url()


def request_password_reset(db: Session, request: PasswordResetRequest) -> dict[str, bool]:
    email = normalize_email(str(request.email))
    user = user_repository.get_active_user_by_email(db, email)
    if user is None or not user.password_hash:
        return {"requested": True}

    raw_token = security.create_urlsafe_token()
    expires_at = security.utc_now_naive() + timedelta(
        minutes=settings.password_reset_expire_minutes
    )
    password_reset_repository.create_password_reset_token(
        db,
        user_id=int(user.id),
        token_hash=security.hash_token(raw_token),
        expires_at=expires_at,
    )
    reset_url = f"{_frontend_base_url()}/reset-password?token={raw_token}"
    try:
        send_password_reset_email(to_email=user.email, reset_url=reset_url)
    except EmailDeliveryError as error:
        db.rollback()
        raise AuthServiceError(503, str(error)) from error

    db.commit()
    return {"requested": True}


def confirm_password_reset(db: Session, request: PasswordResetConfirm) -> dict[str, bool]:
    now = security.utc_now_naive()
    token = password_reset_repository.get_active_password_reset_token(
        db,
        token_hash=security.hash_token(request.token),
        now=now,
    )
    if token is None or not user_repository.is_user_active(token.user) or not token.user.password_hash:
        raise AuthServiceError(400, "Invalid or expired reset token")

    user_repository.update_user_password(
        db,
        token.user,
        password_hash=security.hash_password(request.newPassword),
    )
    password_reset_repository.mark_password_reset_token_used(db, token, used_at=now)
    token_repository.revoke_user_refresh_tokens(db, user_id=int(token.user_id), revoked_at=now)
    db.commit()
    return {"reset": True}
