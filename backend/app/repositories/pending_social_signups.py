from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import PendingSocialSignup


def create_pending_social_signup(
    db: Session,
    *,
    token_hash: str,
    provider: str,
    provider_id: str,
    email: str,
    email_verified: bool,
    nickname: str | None,
    redirect_path: str,
    expires_at: datetime,
) -> PendingSocialSignup:
    pending = PendingSocialSignup(
        token_hash=token_hash,
        provider=provider,
        provider_id=provider_id,
        email=email,
        email_verified=email_verified,
        nickname=nickname,
        redirect_path=redirect_path,
        expires_at=expires_at,
    )
    db.add(pending)
    db.flush()
    return pending


def delete_pending_social_signup_by_provider(
    db: Session,
    *,
    provider: str,
    provider_id: str,
) -> None:
    db.execute(
        delete(PendingSocialSignup).where(
            PendingSocialSignup.provider == provider,
            PendingSocialSignup.provider_id == provider_id,
        )
    )
    db.flush()


def get_active_pending_social_signup_by_token(
    db: Session,
    *,
    token_hash: str,
    now: datetime,
) -> PendingSocialSignup | None:
    statement = (
        select(PendingSocialSignup)
        .where(PendingSocialSignup.token_hash == token_hash)
        .where(PendingSocialSignup.expires_at > now)
    )
    return db.scalar(statement)


def delete_pending_social_signup(db: Session, pending: PendingSocialSignup) -> None:
    db.delete(pending)
    db.flush()
