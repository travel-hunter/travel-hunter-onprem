"""Approval must work under the app session settings (autoflush=False), not only the test default."""

from __future__ import annotations

from datetime import datetime

import itertools

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.models import ExternalSourceRecord, Policy, User
from app.services.policy_candidate_review import approve_candidate, classify_candidate


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    # Mirror app.db.session.get_session_factory: autoflush is OFF in production.
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    # policies.id is a plain BigInteger, which sqlite does not autoincrement: emulate it for new rows.
    counter = itertools.count(1000)

    def assign_id(_mapper, _connection, target: Policy) -> None:
        if target.id is None:
            target.id = next(counter)

    event.listen(Policy, "before_insert", assign_id)
    try:
        with TestingSessionLocal() as session:
            yield session
    finally:
        event.remove(Policy, "before_insert", assign_id)


def make_stay_discount_record() -> ExternalSourceRecord:
    return ExternalSourceRecord(
        id=76,
        source_name="Korea Stay Discount Festa",
        source_type="official_campaign",
        source_url="https://official.example/stay",
        source_category="stay_discount",
        external_id="stay-76",
        canonical_key="stay-76",
        logical_key="stay-discount:2026-summer",
        collected_page_url="https://official.example/stay",
        title="숙박세일 페스타",
        organizer_text="문화체육관광부",
        organizers=["문화체육관광부"],
        region="비수도권",
        city=None,
        is_nationwide=False,
        status="ended",
        benefit_text="숙박 할인권",
        benefit_value_type="mixed",
        tags=["숙박"],
        inferred_travel_styles=[],
        confidence=90,
        field_completeness=80,
        raw_list_text="숙박세일 페스타",
        raw_detail_text="숙박 할인권",
        raw_payload={},
        last_fetched_at=datetime(2026, 9, 13, 12, 0, 0),
        freshness_status="unknown",
    )


def test_stay_discount_candidate_approves_with_autoflush_disabled(db: Session) -> None:
    record = make_stay_discount_record()
    admin = User(id=10, email="admin@example.com", nickname="admin", role="admin")
    db.add_all([record, admin])
    db.flush()
    candidate = classify_candidate(db, record=record)

    approved = approve_candidate(db, candidate=candidate, record=record, admin=admin)

    assert approved.review_status == "approved"
    assert approved.published_policy_id is not None
