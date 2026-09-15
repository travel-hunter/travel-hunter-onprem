from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.models import ExternalSourceRecord, Policy, User
from app.services.policy_candidate_review import (
    approve_candidate,
    approve_pending_candidates,
    classify_candidate,
    get_candidate_with_record,
    reject_candidate,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with TestingSessionLocal() as session:
        yield session


def make_record() -> ExternalSourceRecord:
    return ExternalSourceRecord(
        id=1,
        source_name="Official source",
        source_type="official_campaign",
        source_url="https://official.example/source",
        source_category="local_half_trip",
        external_id="example-1",
        canonical_key="example-1",
        collected_page_url="https://official.example/source",
        title="Example travel support",
        organizer_text="Official organizer",
        organizers=["Official organizer"],
        region="Gangwon",
        city="Example city",
        is_nationwide=False,
        status="active",
        benefit_text="Example benefit",
        benefit_value_type="mixed",
        tags=["travel"],
        inferred_travel_styles=[],
        confidence=90,
        field_completeness=90,
        raw_list_text="Example travel support",
        raw_detail_text="Example benefit",
        raw_payload={},
        last_fetched_at=datetime(2026, 9, 13, 12, 0, 0),
        freshness_status="fresh",
    )


def test_new_external_record_becomes_pending_candidate(db: Session) -> None:
    record = make_record()
    db.add(record)
    db.flush()

    candidate = classify_candidate(db, record=record)

    assert candidate.review_status == "pending"
    assert candidate.change_kind == "new"


def test_same_evidence_does_not_create_a_second_candidate(db: Session) -> None:
    record = make_record()
    db.add(record)
    db.flush()

    first = classify_candidate(db, record=record)
    second = classify_candidate(db, record=record)

    assert first.id == second.id


def test_material_change_supersedes_prior_rejected_candidate(db: Session) -> None:
    record = make_record()
    admin = User(id=10, email="admin@example.com", nickname="admin", role="admin")
    db.add_all([record, admin])
    db.flush()
    rejected = classify_candidate(db, record=record)
    reject_candidate(db, candidate=rejected, admin=admin, note="missing period")
    record.benefit_text = "Changed benefit"

    changed = classify_candidate(db, record=record)

    assert changed.review_status == "pending"
    assert changed.change_kind == "material_change"
    assert rejected.review_status == "superseded"


def test_reintroduced_evidence_creates_a_new_pending_candidate(db: Session) -> None:
    record = make_record()
    admin = User(id=10, email="admin@example.com", nickname="admin", role="admin")
    db.add_all([record, admin])
    db.flush()

    original = classify_candidate(db, record=record)
    approve_candidate(db, candidate=original, record=record, admin=admin)
    record.benefit_text = "Changed benefit"
    changed = classify_candidate(db, record=record)
    approve_candidate(db, candidate=changed, record=record, admin=admin)
    record.benefit_text = "Example benefit"

    restored = classify_candidate(db, record=record)

    assert restored.id not in {original.id, changed.id}
    assert restored.review_status == "pending"
    assert restored.change_kind == "material_change"


def test_approval_publishes_only_the_reviewed_candidate(db: Session) -> None:
    record = make_record()
    admin = User(id=10, email="admin@example.com", nickname="admin", role="admin")
    unrelated = Policy(
        id=9, slug="unrelated", title="Unrelated", region="Gangwon", status="active"
    )
    db.add_all([record, admin, unrelated])
    db.flush()
    candidate = classify_candidate(db, record=record)

    approved = approve_candidate(db, candidate=candidate, record=record, admin=admin)

    assert approved.review_status == "approved"
    assert approved.published_policy_id is not None
    published = db.get(Policy, approved.published_policy_id)
    assert published is not None
    assert published.external_source_record_id == record.id
    assert db.get(Policy, unrelated.id).title == "Unrelated"


def test_batch_approval_publishes_selected_pending_candidates(db: Session) -> None:
    first = make_record()
    second = make_record()
    second.id = 2
    second.external_id = "example-2"
    second.canonical_key = "example-2"
    second.title = "Second travel support"
    admin = User(id=10, email="admin@example.com", nickname="admin", role="admin")
    db.add_all([first, second, admin])
    db.flush()
    first_candidate = classify_candidate(db, record=first)
    second_candidate = classify_candidate(db, record=second)

    approved = approve_pending_candidates(
        db,
        candidate_ids=[str(first_candidate.id), str(second_candidate.id)],
        approve_all=False,
        admin=admin,
    )

    assert [candidate.id for candidate in approved] == [first_candidate.id, second_candidate.id]
    assert all(candidate.review_status == "approved" for candidate in approved)


def test_decision_candidate_lookup_requests_a_row_lock() -> None:
    captured = []

    class Result:
        def one_or_none(self):
            return None

    class RecordingSession:
        def execute(self, statement):
            captured.append(statement)
            return Result()

    get_candidate_with_record(RecordingSession(), candidate_id=1, lock=True)

    assert "FOR UPDATE" in str(captured[0].compile(dialect=postgresql.dialect()))
