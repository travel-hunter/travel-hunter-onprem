from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.models import AuthRefreshToken, User


def create_refresh_token(
    db: Session,
    *,
    user_id: int,
    refresh_token_hash: str,
    expires_at: datetime,
) -> AuthRefreshToken:
    token = AuthRefreshToken(
        user_id=user_id,
        refresh_token_hash=refresh_token_hash,
        expires_at=expires_at,
    )
    db.add(token)
    db.flush()
    return token


def get_active_refresh_token_by_hash(
    db: Session,
    *,
    refresh_token_hash: str,
    now: datetime,
) -> AuthRefreshToken | None:
    statement = (
        select(AuthRefreshToken)
        .options(
            selectinload(AuthRefreshToken.user),
            selectinload(AuthRefreshToken.user).selectinload(User.social_accounts),
        )
        .where(AuthRefreshToken.refresh_token_hash == refresh_token_hash)
        .where(AuthRefreshToken.revoked_at.is_(None))
        .where(AuthRefreshToken.expires_at > now)
    )
    return db.scalar(statement)


def revoke_refresh_token(
    db: Session,
    token: AuthRefreshToken,
    *,
    revoked_at: datetime,
) -> None:
    token.revoked_at = revoked_at
    db.add(token)


def revoke_user_refresh_tokens(
    db: Session,
    *,
    user_id: int,
    revoked_at: datetime,
) -> None:
    db.execute(
        update(AuthRefreshToken)
        .where(AuthRefreshToken.user_id == user_id)
        .where(AuthRefreshToken.revoked_at.is_(None))
        .values(revoked_at=revoked_at)
    )
