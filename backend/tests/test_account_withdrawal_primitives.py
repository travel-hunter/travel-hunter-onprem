from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.models import AuthRefreshToken, SocialAccount, User
from app.services import account_withdrawal


def make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return TestingSessionLocal()


def test_withdrawn_email_fingerprint_is_hmac_deterministic_and_normalized() -> None:
    first = account_withdrawal.withdrawn_email_fingerprint(
        "  User@Example.COM ",
        secret="test-pepper",
    )
    second = account_withdrawal.withdrawn_email_fingerprint(
        "user@example.com",
        secret="test-pepper",
    )
    different_secret = account_withdrawal.withdrawn_email_fingerprint(
        "user@example.com",
        secret="different-pepper",
    )

    assert first == second
    assert first != different_secret
    assert len(first) == 64
    assert "user@example.com" not in first


def test_soft_withdraw_user_anonymizes_and_preserves_related_rows(monkeypatch) -> None:
    db = make_db()
    now = datetime(2026, 7, 12, 1, 2, 3)
    monkeypatch.setattr(account_withdrawal.security, "utc_now_naive", lambda: now)

    user = User(
        id=1001,
        email="User@Example.COM",
        password_hash="hashed-password",
        nickname="Original Nickname",
        preferred_regions="서울,부산",
        travel_style="healing",
        travel_budget="mid",
        onboarding_completed=True,
        profile_setup_skipped=True,
        created_at=now,
        updated_at=now,
    )
    db.add_all(
        [
            user,
            SocialAccount(
                id=2001,
                user_id=1001,
                provider="google",
                provider_id="provider-subject",
                provider_nickname="Provider Nickname",
                created_at=now,
            ),
            AuthRefreshToken(
                id=3001,
                user_id=1001,
                refresh_token_hash="refresh-token-hash",
                created_at=now,
                expires_at=now + timedelta(days=14),
            ),
        ]
    )
    db.commit()

    withdrawn = account_withdrawal.soft_withdraw_user(db, user)
    db.commit()

    assert account_withdrawal.is_withdrawn_user(withdrawn) is True
    assert account_withdrawal.is_active_user(withdrawn) is False
    assert withdrawn.withdrawn_at == now
    assert withdrawn.withdrawn_email_hash == account_withdrawal.withdrawn_email_fingerprint(
        "User@Example.COM"
    )
    assert withdrawn.email == "withdrawn-1001-20260712010203@withdrawn.local"
    assert withdrawn.nickname == "탈퇴한 사용자 #1001"
    assert withdrawn.password_hash is None
    assert withdrawn.social_accounts == []
    assert withdrawn.preferred_regions is None
    assert withdrawn.travel_style is None
    assert withdrawn.travel_budget is None
    assert withdrawn.onboarding_completed is False
    assert withdrawn.profile_setup_skipped is False
    assert db.scalar(select(SocialAccount).where(SocialAccount.user_id == 1001)) is None

    token = db.scalar(select(AuthRefreshToken).where(AuthRefreshToken.user_id == 1001))
    assert token is not None
    assert token.revoked_at == now
