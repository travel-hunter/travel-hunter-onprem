from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core import security
from app.models import SocialAccount, User

UNSET = object()


def is_user_withdrawn(user: User) -> bool:
    return getattr(user, "withdrawn_at", None) is not None


def is_user_active(user: User) -> bool:
    return not is_user_withdrawn(user)


def get_user_by_email(db: Session, email: str) -> User | None:
    statement = (
        select(User)
        .options(selectinload(User.social_accounts))
        .where(User.email == email)
    )
    return db.scalar(statement)


def get_active_user_by_email(db: Session, email: str) -> User | None:
    user = get_user_by_email(db, email)
    return user if user is not None and is_user_active(user) else None


def get_user_by_id(db: Session, user_id: int) -> User | None:
    statement = (
        select(User)
        .options(selectinload(User.social_accounts))
        .where(User.id == user_id)
    )
    return db.scalar(statement)


def get_active_user_by_id(db: Session, user_id: int) -> User | None:
    user = get_user_by_id(db, user_id)
    return user if user is not None and is_user_active(user) else None


def create_user(
    db: Session,
    *,
    email: str,
    nickname: str,
    password_hash: str | None,
    nickname_setup_completed: bool = True,
    profile_setup_skipped: bool = False,
    terms_accepted: bool = False,
    terms_accepted_at=None,
    terms_version: str | None = None,
    privacy_accepted: bool = False,
    privacy_accepted_at=None,
    privacy_version: str | None = None,
) -> User:
    user = User(
        email=email,
        nickname=nickname,
        password_hash=password_hash,
        onboarding_completed=False,
        nickname_setup_completed=nickname_setup_completed,
        profile_setup_skipped=profile_setup_skipped,
        terms_accepted=terms_accepted,
        terms_accepted_at=terms_accepted_at,
        terms_version=terms_version,
        privacy_accepted=privacy_accepted,
        privacy_accepted_at=privacy_accepted_at,
        privacy_version=privacy_version,
    )
    db.add(user)
    db.flush()
    return user


def update_user_password(
    db: Session,
    user: User,
    *,
    password_hash: str,
) -> User:
    user.password_hash = password_hash
    user.updated_at = security.utc_now_naive()
    db.add(user)
    db.flush()
    return user


def update_user_email(
    db: Session,
    user: User,
    *,
    email: str,
) -> User:
    user.email = email
    user.updated_at = security.utc_now_naive()
    db.add(user)
    db.flush()
    return user


def get_social_account(
    db: Session,
    *,
    provider: str,
    provider_id: str,
) -> SocialAccount | None:
    statement = (
        select(SocialAccount)
        .options(selectinload(SocialAccount.user).selectinload(User.social_accounts))
        .where(
            SocialAccount.provider == provider,
            SocialAccount.provider_id == provider_id,
        )
    )
    return db.scalar(statement)


def get_active_social_account(
    db: Session,
    *,
    provider: str,
    provider_id: str,
) -> SocialAccount | None:
    account = get_social_account(db, provider=provider, provider_id=provider_id)
    if account is None or account.user is None:
        return None
    return account if is_user_active(account.user) else None


def create_social_account(
    db: Session,
    *,
    user: User,
    provider: str,
    provider_id: str,
    provider_nickname: str | None = None,
) -> SocialAccount:
    account = SocialAccount(
        user_id=int(user.id),
        user=user,
        provider=provider,
        provider_id=provider_id,
        provider_nickname=provider_nickname,
    )
    db.add(account)
    db.flush()
    return account


def update_user_profile(
    db: Session,
    user: User,
    *,
    preferred_regions: str | None | object = UNSET,
    style: str | None | object = UNSET,
    budget: str | None | object = UNSET,
) -> User:
    if preferred_regions is not UNSET:
        user.preferred_regions = preferred_regions
    if style is not UNSET:
        user.travel_style = style
    if budget is not UNSET:
        user.travel_budget = budget
    user.onboarding_completed = True
    user.profile_setup_skipped = False
    user.updated_at = security.utc_now_naive()
    db.add(user)
    db.flush()
    return user


def mark_nickname_setup_completed(db: Session, user: User) -> User:
    user.nickname_setup_completed = True
    user.updated_at = security.utc_now_naive()
    db.add(user)
    db.flush()
    return user


def mark_profile_setup_skipped(db: Session, user: User) -> User:
    user.onboarding_completed = True
    user.profile_setup_skipped = True
    user.updated_at = security.utc_now_naive()
    db.add(user)
    db.flush()
    return user


def clear_user_preferences(db: Session, user: User, *, updated_at: datetime) -> User:
    user.preferred_regions = None
    user.travel_style = None
    user.travel_budget = None
    user.onboarding_completed = False
    user.profile_setup_skipped = False
    user.updated_at = updated_at
    db.add(user)
    db.flush()
    return user


def disconnect_social_accounts(db: Session, user: User) -> None:
    accounts = list(
        db.scalars(select(SocialAccount).where(SocialAccount.user_id == int(user.id)))
    )
    for account in accounts:
        db.delete(account)
    if "social_accounts" in user.__dict__:
        user.social_accounts = []
    db.add(user)
    db.flush()


def mark_user_withdrawn(
    db: Session,
    user: User,
    *,
    withdrawn_at: datetime,
    withdrawn_email_hash: str,
    anonymized_email: str,
    withdrawn_nickname: str,
) -> User:
    user.withdrawn_at = withdrawn_at
    user.withdrawn_email_hash = withdrawn_email_hash
    user.email = anonymized_email
    user.nickname = withdrawn_nickname
    user.password_hash = None
    user.updated_at = withdrawn_at
    db.add(user)
    db.flush()
    return user
