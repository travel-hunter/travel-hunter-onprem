from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core import security
from app.models import User
from app.repositories import auth_tokens as token_repository
from app.repositories import users as user_repository
from app.services import auth as auth_service


WITHDRAWN_EMAIL_DOMAIN = "withdrawn.local"
WITHDRAWN_NICKNAME_PREFIX = "탈퇴한 사용자 #"


@dataclass(frozen=True)
class WithdrawalIdentity:
    withdrawn_at: datetime
    original_email: str
    withdrawn_email_hash: str
    anonymized_email: str
    withdrawn_nickname: str


def is_withdrawn_user(user: User) -> bool:
    return user_repository.is_user_withdrawn(user)


def is_active_user(user: User) -> bool:
    return user_repository.is_user_active(user)


def withdrawn_email_fingerprint(email: str, *, secret: str | None = None) -> str:
    normalized = auth_service.normalize_email(email)
    return security.hmac_sha256_hex(f"withdrawn-email:{normalized}", secret=secret)


def anonymized_email_for_user(user_id: int | str, withdrawn_at: datetime) -> str:
    timestamp = withdrawn_at.strftime("%Y%m%d%H%M%S")
    return f"withdrawn-{user_id}-{timestamp}@{WITHDRAWN_EMAIL_DOMAIN}"


def withdrawn_display_nickname(user_id: int | str) -> str:
    return f"{WITHDRAWN_NICKNAME_PREFIX}{user_id}"


def build_withdrawal_identity(
    user: User,
    *,
    withdrawn_at: datetime | None = None,
) -> WithdrawalIdentity:
    current_time = withdrawn_at or security.utc_now_naive()
    return WithdrawalIdentity(
        withdrawn_at=current_time,
        original_email=user.email,
        withdrawn_email_hash=withdrawn_email_fingerprint(user.email),
        anonymized_email=anonymized_email_for_user(user.id, current_time),
        withdrawn_nickname=withdrawn_display_nickname(user.id),
    )


def clear_preferences(db: Session, user: User, *, updated_at: datetime | None = None) -> User:
    return user_repository.clear_user_preferences(
        db,
        user,
        updated_at=updated_at or security.utc_now_naive(),
    )


def disconnect_social_accounts(db: Session, user: User) -> None:
    user_repository.disconnect_social_accounts(db, user)


def revoke_refresh_tokens(db: Session, user: User, *, revoked_at: datetime | None = None) -> None:
    token_repository.revoke_user_refresh_tokens(
        db,
        user_id=int(user.id),
        revoked_at=revoked_at or security.utc_now_naive(),
    )


def soft_withdraw_user(db: Session, user: User) -> User:
    """Soft-disable and anonymize a user while preserving relational rows.

    The auth route calls this primitive through the auth service. It clears
    profile preferences, disconnects social providers, revokes refresh tokens,
    stores a deterministic HMAC email fingerprint, and anonymizes direct login
    identity.
    """

    if is_withdrawn_user(user):
        return user

    identity = build_withdrawal_identity(user)
    clear_preferences(db, user, updated_at=identity.withdrawn_at)
    disconnect_social_accounts(db, user)
    revoke_refresh_tokens(db, user, revoked_at=identity.withdrawn_at)
    return user_repository.mark_user_withdrawn(
        db,
        user,
        withdrawn_at=identity.withdrawn_at,
        withdrawn_email_hash=identity.withdrawn_email_hash,
        anonymized_email=identity.anonymized_email,
        withdrawn_nickname=identity.withdrawn_nickname,
    )
