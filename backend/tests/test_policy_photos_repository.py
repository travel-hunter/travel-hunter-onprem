"""Persistence tests for one stable photo assignment per policy."""

from __future__ import annotations

import app.models  # noqa: F401
import pytest
from sqlalchemy import Integer, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import PolicyPhotoAssignment
from app.repositories.policy_photos import (
    get_policy_photo,
    list_active_policy_photos,
    upsert_policy_photo,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    id_column = PolicyPhotoAssignment.__table__.c.id
    original_type = id_column.type
    id_column.type = Integer()
    try:
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(bind=engine)
        with TestingSessionLocal() as db:
            yield db
        Base.metadata.drop_all(engine)
    finally:
        id_column.type = original_type


def test_upsert_policy_photo_keeps_one_current_assignment(session: Session) -> None:
    first = upsert_policy_photo(
        session,
        policy_id=42,
        provider="tour_api",
        provider_content_id="100",
        image_url="https://example.test/first.jpg",
        thumbnail_url="https://example.test/first-thumb.jpg",
        alt_text="해남 첫 관광지",
        attribution_text="사진: 한국관광공사",
        relevance_score=100,
        assignment_reason="city_match",
        status="active",
    )
    second = upsert_policy_photo(
        session,
        policy_id=42,
        provider="tour_api",
        provider_content_id="200",
        image_url="https://example.test/better.jpg",
        thumbnail_url=None,
        alt_text="해남 더 적합한 관광지",
        attribution_text="사진: 한국관광공사",
        relevance_score=150,
        assignment_reason="policy_keyword",
        status="active",
        copyright_type="Type1",
        image_width=940,
        image_height=626,
    )
    session.commit()
    session.expire_all()

    assert first.id == second.id
    stored = get_policy_photo(session, policy_id=42)
    assert stored is not None
    assert stored.image_url.endswith("better.jpg")
    assert (stored.copyright_type, stored.image_width, stored.image_height) == ("Type1", 940, 626)
    assert stored.relevance_score == 150
    assert stored.assignment_reason == "policy_keyword"
    assert len(list_active_policy_photos(session)) == 1
