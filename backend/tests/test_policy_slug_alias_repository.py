from __future__ import annotations

from datetime import datetime, timezone

import app.models  # noqa: F401
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import Policy, PolicySlugAlias
from app.repositories.policies import (
    get_active_slug_alias_by_old_slug,
    list_slug_aliases_by_policy_id,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    with TestingSessionLocal() as session:
        yield session
    Base.metadata.drop_all(engine)


def make_policy(**overrides) -> Policy:
    data = {
        "id": 10,
        "slug": "canonical-policy",
        "title": "Canonical policy",
        "region": "전국",
    }
    data.update(overrides)
    return Policy(**data)


def test_get_active_slug_alias_by_old_slug_returns_active_alias_with_policy(
    db: Session,
) -> None:
    policy = make_policy()
    alias = PolicySlugAlias(
        id=1,
        old_slug="legacy-policy",
        policy_id=policy.id,
        canonical_slug="canonical-policy",
        alias_kind="legacy",
        source_kind="manual",
    )
    inactive_alias = PolicySlugAlias(
        id=2,
        old_slug="inactive-policy",
        policy_id=policy.id,
        canonical_slug="canonical-policy",
        is_active=False,
        superseded_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
    )
    db.add_all([policy, alias, inactive_alias])
    db.commit()

    found = get_active_slug_alias_by_old_slug(db, "legacy-policy")

    assert found is not None
    assert found.old_slug == "legacy-policy"
    assert found.canonical_slug == "canonical-policy"
    assert found.policy.slug == "canonical-policy"
    assert get_active_slug_alias_by_old_slug(db, "inactive-policy") is None
    assert get_active_slug_alias_by_old_slug(db, "missing") is None


def test_list_slug_aliases_by_policy_id_returns_history_and_active_subset(
    db: Session,
) -> None:
    policy = make_policy(id=20, slug="new-policy")
    older_active = PolicySlugAlias(
        id=1,
        old_slug="legacy-1",
        policy_id=policy.id,
        canonical_slug="new-policy",
        created_at=datetime(2026, 7, 17, 9, 0, 0),
    )
    inactive = PolicySlugAlias(
        id=2,
        old_slug="legacy-2",
        policy_id=policy.id,
        canonical_slug="new-policy",
        is_active=False,
        superseded_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        created_at=datetime(2026, 7, 18, 9, 0, 0),
    )
    other_policy_alias = PolicySlugAlias(
        id=3,
        old_slug="other-legacy",
        policy_id=999,
        canonical_slug="other-policy",
        created_at=datetime(2026, 7, 19, 9, 0, 0),
    )
    other_policy = make_policy(id=999, slug="other-policy")
    db.add_all([policy, other_policy, older_active, inactive, other_policy_alias])
    db.commit()

    history = list_slug_aliases_by_policy_id(db, policy_id=policy.id)
    active_history = list_slug_aliases_by_policy_id(
        db, policy_id=policy.id, active_only=True
    )

    assert [row.old_slug for row in history] == ["legacy-2", "legacy-1"]
    assert [row.old_slug for row in active_history] == ["legacy-1"]
