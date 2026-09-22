"""Auto-publish gate: normal updates publish themselves, everything else waits for a human."""

from __future__ import annotations

import itertools
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.models import AdminAuditLog, ExternalSourceRecord, Policy, PolicyReviewCandidate, User
from app.repositories import policy_collection_sources
from app.services import external_benefit_collection
from app.services.external_benefit_collection import SourceCollectionResult
from app.services.policy_candidate_review import approve_candidate, classify_candidate

CATEGORY = "local_half_trip"


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
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


def make_record(record_id: int = 1, **overrides) -> ExternalSourceRecord:
    values = dict(
        id=record_id,
        source_name="Official source",
        source_type="official_campaign",
        source_url="https://official.example/source",
        source_category=CATEGORY,
        external_id=f"example-{record_id}",
        canonical_key=f"example-{record_id}",
        collected_page_url="https://official.example/source",
        title="Example travel support",
        organizer_text="Official organizer",
        organizers=["Official organizer"],
        region="Gangwon",
        city="Example city",
        is_nationwide=False,
        status="active",
        benefit_text="Example benefit",
        benefit_value_text="Example benefit",
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
    values.update(overrides)
    return ExternalSourceRecord(**values)


def success(parsed: int = 10, category: str = CATEGORY) -> SourceCollectionResult:
    return SourceCollectionResult(source_category=category, parsed_count=parsed, created_or_updated_count=parsed, outcome="success")


def set_source(db: Session, *, mode: str = "auto_after_reviewed_baseline", expected_min: int = 0, last_parsed: int | None = None):
    source = policy_collection_sources.get_collection_source_by_key(db, key=CATEGORY)
    source.publication_mode = mode
    source.expected_min_records = expected_min
    source.last_parsed_count = last_parsed
    db.flush()
    return source


def human_baseline(db: Session, record: ExternalSourceRecord) -> PolicyReviewCandidate:
    admin = db.get(User, 10) or User(id=10, email="admin@example.com", nickname="admin", role="admin")
    db.add(admin)
    db.flush()
    candidate = classify_candidate(db, record=record)
    return approve_candidate(db, candidate=candidate, record=record, admin=admin)


def run_collection_queue(db: Session, records: list[ExternalSourceRecord], results: list[SourceCollectionResult]) -> None:
    external_benefit_collection._queue_review_candidates(db, records, source_results=results)
    db.flush()


def latest_candidate(db: Session, record: ExternalSourceRecord) -> PolicyReviewCandidate:
    return db.scalar(
        select(PolicyReviewCandidate)
        .where(PolicyReviewCandidate.external_source_record_id == record.id)
        .order_by(PolicyReviewCandidate.id.desc())
    )


# --- 1. review mode never auto-approves -------------------------------------------------


def test_review_mode_keeps_every_candidate_pending(db: Session) -> None:
    record = make_record()
    db.add(record)
    db.flush()
    human_baseline(db, record)
    set_source(db, mode="review")
    record.benefit_text = "Bigger benefit"

    run_collection_queue(db, [record], [success()])

    candidate = latest_candidate(db, record)
    assert (candidate.review_status, candidate.review_reason) == ("pending", "source_mode_review")


# --- 2. auto mode needs a human baseline --------------------------------------------------


def test_auto_mode_without_human_baseline_holds_first_baseline(db: Session) -> None:
    record = make_record()
    db.add(record)
    db.flush()
    set_source(db)

    run_collection_queue(db, [record], [success()])

    candidate = latest_candidate(db, record)
    assert (candidate.review_status, candidate.review_reason) == ("pending", "first_baseline")


# --- 3. benefit-only update on a published policy publishes itself -----------------------------


def test_benefit_update_after_baseline_is_auto_approved_and_audited(db: Session) -> None:
    record = make_record()
    db.add(record)
    db.flush()
    baseline = human_baseline(db, record)
    set_source(db, last_parsed=10)
    record.benefit_text = "Bigger benefit"
    record.benefit_value_text = "Bigger benefit"

    run_collection_queue(db, [record], [success(parsed=9)])

    candidate = latest_candidate(db, record)
    assert candidate.id != baseline.id
    assert (candidate.review_status, candidate.review_reason, candidate.review_note) == ("approved", "auto", "auto")
    assert candidate.reviewed_by_user_id is None
    assert candidate.published_policy_id == baseline.published_policy_id
    assert db.get(Policy, baseline.published_policy_id).benefit_detail == "Bigger benefit"
    log = db.scalar(select(AdminAuditLog).where(AdminAuditLog.action == "policy_review.auto_approve"))
    assert log is not None
    assert log.admin_user_id == 10  # the human who approved the baseline owns the automation
    assert log.after_json["actor"] == "system"


# --- 4. unsafe card copy waits for review ----------------------------------------------------


def test_unsafe_card_copy_is_held_for_review(db: Session) -> None:
    record = make_record(benefit_value_text="최대 1만원 할인")
    db.add(record)
    db.flush()
    baseline = human_baseline(db, record)
    set_source(db, last_parsed=10)
    record.benefit_value_text = "할인혜택 보러가기"
    record.raw_payload = {
        "cardCopy": {
            "version": 1,
            "summary": "할인혜택 보러가기",
            "evidence": "공식 본문",
            "issues": [],
        }
    }

    run_collection_queue(db, [record], [success(parsed=10)])

    candidate = latest_candidate(db, record)
    assert (candidate.review_status, candidate.review_reason) == (
        "pending",
        "card_quality_review",
    )
    assert db.get(Policy, baseline.published_policy_id).benefit_detail == "최대 1만원 할인"


# --- 5. identity change / new policy wait -----------------------------------------------------


def test_title_change_is_held_as_identity_changed(db: Session) -> None:
    record = make_record()
    db.add(record)
    db.flush()
    human_baseline(db, record)
    set_source(db)
    record.title = "Renamed travel support"

    run_collection_queue(db, [record], [success()])

    candidate = latest_candidate(db, record)
    assert (candidate.review_status, candidate.review_reason) == ("pending", "identity_changed")


def test_new_policy_is_held_even_with_baseline(db: Session) -> None:
    first = make_record(1)
    second = make_record(2)
    db.add_all([first, second])
    db.flush()
    human_baseline(db, first)
    set_source(db)

    run_collection_queue(db, [second], [success()])

    candidate = latest_candidate(db, second)
    assert (candidate.review_status, candidate.review_reason) == ("pending", "new_policy")


# --- 5. source anomalies hold the whole run -----------------------------------------------------


@pytest.mark.parametrize(
    ("result", "expected_min", "last_parsed"),
    [
        (SourceCollectionResult(source_category=CATEGORY, parsed_count=0, created_or_updated_count=0, outcome="parser_changed", error="x"), 0, None),
        (success(parsed=3), 5, None),
        (success(parsed=69), 0, 100),
    ],
    ids=["parser_failed", "below_expected_min", "shrunk_over_30_percent"],
)
def test_source_anomaly_holds_updates(db: Session, result: SourceCollectionResult, expected_min: int, last_parsed: int | None) -> None:
    record = make_record()
    db.add(record)
    db.flush()
    human_baseline(db, record)
    set_source(db, expected_min=expected_min, last_parsed=last_parsed)
    record.benefit_text = "Bigger benefit"

    run_collection_queue(db, [record], [result])

    candidate = latest_candidate(db, record)
    assert (candidate.review_status, candidate.review_reason) == ("pending", "source_anomaly")


def test_shrink_at_exactly_30_percent_still_publishes(db: Session) -> None:
    record = make_record()
    db.add(record)
    db.flush()
    human_baseline(db, record)
    set_source(db, last_parsed=100)
    record.benefit_text = "Bigger benefit"

    run_collection_queue(db, [record], [success(parsed=70)])

    assert latest_candidate(db, record).review_status == "approved"


# --- 6. would publish hidden / 7. stay discount -------------------------------------------------


def test_ended_record_is_held_as_would_publish_hidden(db: Session) -> None:
    record = make_record()
    db.add(record)
    db.flush()
    human_baseline(db, record)
    set_source(db)
    record.benefit_text = "Bigger benefit"
    record.status = "ended"

    run_collection_queue(db, [record], [success()])

    candidate = latest_candidate(db, record)
    assert (candidate.review_status, candidate.review_reason) == ("pending", "would_publish_hidden")


def test_low_confidence_is_held(db: Session) -> None:
    record = make_record()
    db.add(record)
    db.flush()
    human_baseline(db, record)
    set_source(db)
    record.benefit_text = "Bigger benefit"
    record.confidence = 40

    run_collection_queue(db, [record], [success()])

    assert latest_candidate(db, record).review_reason == "low_confidence"


def test_stay_discount_is_manual_regardless_of_mode(db: Session) -> None:
    record = make_record(source_category="stay_discount", logical_key="stay-discount:2026-summer")
    db.add(record)
    db.flush()
    human_baseline(db, record)
    source = policy_collection_sources.get_collection_source_by_key(db, key="stay_discount")
    source.publication_mode = "auto_after_reviewed_baseline"
    db.flush()
    record.benefit_text = "Bigger benefit"

    run_collection_queue(db, [record], [success(category="stay_discount")])

    candidate = latest_candidate(db, record)
    assert (candidate.review_status, candidate.review_reason) == ("pending", "stay_discount_manual")


# --- last_parsed_count bookkeeping -------------------------------------------------------------


def test_successful_run_records_last_parsed_count_but_failed_run_keeps_it(db: Session) -> None:
    set_source(db, last_parsed=None)
    external_benefit_collection._record_source_results(db, [success(parsed=12)], collected_at=datetime(2026, 9, 14, 0, 0, 0))
    source = policy_collection_sources.get_collection_source_by_key(db, key=CATEGORY)
    assert source.last_parsed_count == 12
    external_benefit_collection._record_source_results(
        db,
        [SourceCollectionResult(source_category=CATEGORY, parsed_count=0, created_or_updated_count=0, outcome="error", error="boom")],
        collected_at=datetime(2026, 9, 14, 1, 0, 0),
    )
    assert policy_collection_sources.get_collection_source_by_key(db, key=CATEGORY).last_parsed_count == 12


# --- island_visit: a changed application procedure always waits for a human ------------------------------


def _island_record():
    from test_island_application_guide import island_record

    return island_record()


def _island_auto_source(db: Session):
    source = policy_collection_sources.get_collection_source_by_key(db, key="island_visit")
    source.publication_mode = "auto_after_reviewed_baseline"
    db.flush()
    return source


def test_island_procedure_change_holds_as_procedure_changed(db: Session) -> None:
    from copy import deepcopy

    record = _island_record()
    db.add(record)
    db.flush()
    human_baseline(db, record)
    _island_auto_source(db)
    payload = deepcopy(record.raw_payload)
    payload["procedure"]["rounds"][1]["documentFormUrl"] = "https://forms.gle/NewDocumentForm"
    record.raw_payload = payload
    db.flush()

    run_collection_queue(db, [record], [success(category="island_visit")])

    candidate = latest_candidate(db, record)
    assert (candidate.review_status, candidate.review_reason) == ("pending", "procedure_changed")


def test_island_benefit_change_with_the_same_procedure_auto_publishes(db: Session) -> None:
    record = _island_record()
    db.add(record)
    db.flush()
    human_baseline(db, record)
    _island_auto_source(db)
    record.benefit_text = "여행비 10만원 (숙박비, 왕복 배편 승선권, 식비 등) 지급"
    db.flush()

    run_collection_queue(db, [record], [success(category="island_visit")])

    candidate = latest_candidate(db, record)
    assert (candidate.review_status, candidate.review_reason) == ("approved", "auto")
