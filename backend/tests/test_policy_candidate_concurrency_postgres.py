from __future__ import annotations

import os
import threading
from datetime import datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models import ExternalSourceRecord, PolicyReviewCandidate, User
from app.services import policy_candidate_review

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_CONCURRENCY_TESTS") != "1",
    reason="set RUN_POSTGRES_CONCURRENCY_TESTS=1 for PostgreSQL concurrency tests",
)

USER_ID = 991_001
RECORD_ID = 991_002


def _url() -> str:
    return os.environ["POSTGRES_CONCURRENCY_TEST_DATABASE_URL"]


def _cleanup(engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("delete from admin_audit_logs where admin_user_id = :id"), {"id": USER_ID})
        connection.execute(text("delete from policy_review_candidates where external_source_record_id = :id"), {"id": RECORD_ID})
        connection.execute(text("delete from external_source_records where id = :id"), {"id": RECORD_ID})
        connection.execute(text("delete from users where id = :id"), {"id": USER_ID})


@pytest.fixture
def seeded_engine():
    engine = create_engine(_url())
    _cleanup(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        admin = User(id=USER_ID, email="candidate-concurrency@example.test", nickname="Candidate concurrency", role="admin")
        record = ExternalSourceRecord(
            id=RECORD_ID, source_name="Official source", source_type="official_campaign",
            source_url="https://example.test/source", source_category="local_half_trip",
            external_id="candidate-concurrency", canonical_key="candidate-concurrency",
            collected_page_url="https://example.test/source", title="Candidate concurrency",
            organizer_text="Official organizer", organizers=["Official organizer"], region="Gangwon", city="Example",
            is_nationwide=False, status="active", benefit_text="Example benefit", benefit_value_type="mixed",
            tags=["travel"], inferred_travel_styles=[], confidence=90, field_completeness=90,
            raw_list_text="Candidate concurrency", raw_detail_text="Example benefit", raw_payload={},
            last_fetched_at=datetime(2026, 9, 16, 0, 0), freshness_status="fresh",
        )
        session.add_all([admin, record])
        session.flush()
        policy_candidate_review.classify_candidate(session, record=record)
        session.commit()
    try:
        yield engine
    finally:
        _cleanup(engine)
        engine.dispose()


def test_approve_and_reject_have_one_winner(seeded_engine) -> None:
    Session = sessionmaker(bind=seeded_engine, expire_on_commit=False)
    with Session() as session:
        candidate_id = session.query(PolicyReviewCandidate.id).filter_by(external_source_record_id=RECORD_ID).scalar()
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def decide(action: str) -> None:
        with Session() as session:
            admin = session.get(User, USER_ID)
            candidate, record = policy_candidate_review.get_candidate_with_record(session, candidate_id=candidate_id)
            barrier.wait(timeout=10)
            try:
                if action == "approve":
                    policy_candidate_review.approve_candidate(session, candidate=candidate, record=record, admin=admin)
                else:
                    policy_candidate_review.reject_candidate(session, candidate=candidate, admin=admin, note="not ready")
                session.commit()
                outcomes.append(action)
            except ValueError:
                session.rollback()
                outcomes.append("conflict")

    threads = [threading.Thread(target=decide, args=(action,)) for action in ("approve", "reject")]
    for thread in threads: thread.start()
    for thread in threads: thread.join(timeout=20)
    assert sorted(outcomes) in (["approve", "conflict"], ["conflict", "reject"])
    with Session() as session:
        candidate = session.get(PolicyReviewCandidate, candidate_id)
        assert candidate.review_status in {"approved", "rejected"}
