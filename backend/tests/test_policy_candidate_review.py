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


def test_card_summary_change_creates_a_new_pending_candidate(db: Session) -> None:
    record = make_record()
    record.benefit_value_text = "최대 1만원 할인"
    record.raw_payload = {
        "cardCopy": {
            "version": 1,
            "summary": "최대 1만원 할인",
            "evidence": "공식 본문",
            "issues": [],
        }
    }
    db.add(record)
    db.flush()

    first = classify_candidate(db, record=record)
    record.benefit_value_text = "최대 2만원 할인"
    record.raw_payload = {
        "cardCopy": {
            "version": 1,
            "summary": "최대 2만원 할인",
            "evidence": "공식 본문",
            "issues": [],
        }
    }
    second = classify_candidate(db, record=record)

    assert first.id != second.id
    assert first.review_status == "superseded"
    assert second.review_status == "pending"


def test_card_evidence_only_change_does_not_create_candidate(db: Session) -> None:
    record = make_record()
    record.benefit_value_text = "최대 1만원 할인"
    record.raw_payload = {
        "cardCopy": {
            "version": 1,
            "summary": "최대 1만원 할인",
            "evidence": "첫 원문",
            "issues": [],
        }
    }
    db.add(record)
    db.flush()

    first = classify_candidate(db, record=record)
    record.raw_payload = {
        "cardCopy": {
            "version": 1,
            "summary": "최대 1만원 할인",
            "evidence": "푸터만 달라진 원문",
            "issues": [],
        }
    }
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


def test_manual_approval_keeps_detail_mapping_and_source_text(db: Session) -> None:
    # 카드 문구가 오염(CTA)이라도 상세(benefit_detail)에 카드용 고정 문구를 박지 않는다 -
    # amount 와 일정 금액이 거기서 파생된다. 오염 문구를 카드에서 걸러내는 일은 카드 계층(cardSummary)의 몫이다.
    record = make_record()
    record.benefit_value_text = "할인혜택 보러가기"
    record.raw_payload = {
        "cardCopy": {
            "version": 1,
            "summary": "할인혜택 보러가기",
            "evidence": "공식 본문",
            "issues": [],
        }
    }
    admin = User(id=10, email="admin@example.com", nickname="admin", role="admin")
    db.add_all([record, admin])
    db.flush()
    candidate = classify_candidate(db, record=record)

    approved = approve_candidate(db, candidate=candidate, record=record, admin=admin)

    policy = db.get(Policy, approved.published_policy_id)
    assert policy is not None
    assert policy.benefit_detail == "할인혜택 보러가기"
    assert policy.benefit_detail != "혜택 상세 확인"
    assert record.benefit_value_text == "할인혜택 보러가기"


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


# --- 카드 문구만 바뀐 후보(card_copy_only) ------------------------------------------------------


def _publish_baseline(db: Session, admin: User, *, benefit_value_text: str = "최대 2만원 체험 할인"):
    """승인돼 공개된 정책 하나를 만든다. 이후 재수집 후보가 이 정책에 매칭된다."""
    record = make_record()
    record.benefit_value_text = benefit_value_text
    record.raw_payload = {"cardCopy": {"version": 1, "summary": benefit_value_text, "evidence": "본문", "issues": []}}
    db.add_all([record, admin])
    db.flush()
    candidate = classify_candidate(db, record=record)
    approved = approve_candidate(db, candidate=candidate, record=record, admin=admin)
    policy = db.get(Policy, approved.published_policy_id)
    assert policy is not None
    return record, policy


def _policy_snapshot(db: Session, policy: Policy) -> tuple:
    from app.services.policy_semantics import benefit_display_amount_for_policy

    db.refresh(policy)
    return (
        benefit_display_amount_for_policy(policy),
        policy.benefit_detail,
        policy.benefit_amount,
        policy.description,
        policy.structured_detail,
        policy.title,
        policy.slug,
        policy.id,
    )


def test_recollection_that_only_changes_card_copy_is_a_card_copy_only_candidate(db: Session) -> None:
    admin = User(id=10, email="admin@example.com", nickname="admin", role="admin")
    record, _policy = _publish_baseline(db, admin)

    # 같은 원문·같은 상세, 카드 요약만 더 짧게 다듬어진 재수집
    record.raw_payload = {"cardCopy": {"version": 1, "summary": "최대 2만원 할인", "evidence": "본문", "issues": []}}
    db.flush()
    candidate = classify_candidate(db, record=record)

    assert candidate.review_status == "pending"
    assert candidate.review_scope == "card_copy_only"
    assert candidate.review_reason == "card_copy_changed"
    # 같은 evidence 를 다시 수집하면 후보가 늘지 않는다
    assert classify_candidate(db, record=record).id == candidate.id


def test_recollection_that_changes_the_detail_is_a_full_policy_candidate(db: Session) -> None:
    admin = User(id=10, email="admin@example.com", nickname="admin", role="admin")
    record, _policy = _publish_baseline(db, admin)

    record.benefit_value_text = "최대 3만원 체험 할인"  # 상세 금액이 달라졌다
    record.raw_payload = {"cardCopy": {"version": 1, "summary": "최대 3만원 할인", "evidence": "본문", "issues": []}}
    db.flush()
    candidate = classify_candidate(db, record=record)

    assert candidate.review_scope == "full_policy"


def test_first_candidate_for_a_record_is_always_full_policy(db: Session) -> None:
    record = make_record()
    record.raw_payload = {"cardCopy": {"version": 1, "summary": "최대 2만원 할인", "evidence": "본문", "issues": []}}
    db.add(record)
    db.flush()

    assert classify_candidate(db, record=record).review_scope == "full_policy"


def test_approving_a_card_copy_only_candidate_changes_nothing_but_card_summary(db: Session) -> None:
    admin = User(id=10, email="admin@example.com", nickname="admin", role="admin")
    record, policy = _publish_baseline(db, admin)
    before = _policy_snapshot(db, policy)
    assert policy.card_summary == "최대 2만원 체험 할인"

    record.raw_payload = {"cardCopy": {"version": 1, "summary": "최대 2만원 할인", "evidence": "본문", "issues": []}}
    db.flush()
    candidate = classify_candidate(db, record=record)
    approved = approve_candidate(db, candidate=candidate, record=record, admin=admin)

    assert approved.review_status == "approved"
    assert approved.published_policy_id == policy.id
    assert _policy_snapshot(db, policy) == before
    assert policy.card_summary == "최대 2만원 할인"


def test_card_copy_only_approval_refuses_an_unsafe_summary(db: Session) -> None:
    # 판정을 통과 못 한 요약은 카드 문구로 저장할 수 없다 - 후보는 대기 상태로 남는다
    admin = User(id=10, email="admin@example.com", nickname="admin", role="admin")
    record, policy = _publish_baseline(db, admin)

    record.raw_payload = {"cardCopy": {"version": 1, "summary": "할인혜택 보러가기", "evidence": "본문", "issues": []}}
    db.flush()
    candidate = classify_candidate(db, record=record)
    assert candidate.review_scope == "card_copy_only"

    with pytest.raises(ValueError):
        approve_candidate(db, candidate=candidate, record=record, admin=admin)
    db.refresh(policy)
    assert policy.card_summary == "최대 2만원 체험 할인"
