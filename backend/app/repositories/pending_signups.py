from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import PendingSignup


def create_pending_signup(
    db: Session,
    *,
    email: str,
    token_hash: str,
    expires_at: datetime,
    terms_accepted: bool,
    terms_accepted_at: datetime,
    terms_version: str,
    privacy_accepted: bool,
    privacy_accepted_at: datetime,
    privacy_version: str,
) -> PendingSignup:
    pending = PendingSignup(
        email=email,
        token_hash=token_hash,
        expires_at=expires_at,
        terms_accepted=terms_accepted,
        terms_accepted_at=terms_accepted_at,
        terms_version=terms_version,
        privacy_accepted=privacy_accepted,
        privacy_accepted_at=privacy_accepted_at,
        privacy_version=privacy_version,
    )
    db.add(pending)
    db.flush()
    return pending


def delete_pending_signup_by_email(db: Session, email: str) -> None:
    db.execute(delete(PendingSignup).where(PendingSignup.email == email))
    db.flush()


def get_active_pending_signup_by_token(
    db: Session,
    *,
    token_hash: str,
    now: datetime,
) -> PendingSignup | None:
    statement = (
        select(PendingSignup)
        .where(PendingSignup.token_hash == token_hash)
        .where(PendingSignup.expires_at > now)
    )
    return db.scalar(statement)


def delete_pending_signup(db: Session, pending: PendingSignup) -> None:
    db.delete(pending)
    db.flush()
