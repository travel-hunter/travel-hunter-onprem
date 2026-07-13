from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import PasswordResetToken, User


def create_password_reset_token(
    db: Session,
    *,
    user_id: int,
    token_hash: str,
    expires_at: datetime,
) -> PasswordResetToken:
    token = PasswordResetToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(token)
    db.flush()
    return token


def get_active_password_reset_token(
    db: Session,
    *,
    token_hash: str,
    now: datetime,
) -> PasswordResetToken | None:
    statement = (
        select(PasswordResetToken)
        .options(selectinload(PasswordResetToken.user).selectinload(User.social_accounts))
        .where(PasswordResetToken.token_hash == token_hash)
        .where(PasswordResetToken.used_at.is_(None))
        .where(PasswordResetToken.expires_at > now)
    )
    return db.scalar(statement)


def mark_password_reset_token_used(
    db: Session,
    token: PasswordResetToken,
    *,
    used_at: datetime,
) -> None:
    token.used_at = used_at
    db.add(token)
