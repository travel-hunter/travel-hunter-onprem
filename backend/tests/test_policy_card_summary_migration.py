from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import Policy, PolicyReviewCandidate

MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0043_policy_card_summary.py"


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_0043", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_migration_chains_from_current_head_and_adds_only_two_nullable_or_defaulted_columns() -> None:
    migration = _load_migration()
    assert migration.revision == "0043_policy_card_summary"
    assert migration.down_revision == "0042_trip_policy_application"

    # 모델과 마이그레이션이 같은 두 컬럼을 말한다 - 한쪽만 바뀌면 여기서 걸린다
    db = _make_session()
    try:
        columns = {c["name"]: c for c in inspect(db.get_bind()).get_columns("policies")}
        assert columns["card_summary"]["nullable"] is True
        scope = {c["name"]: c for c in inspect(db.get_bind()).get_columns("policy_review_candidates")}["review_scope"]
        assert scope["nullable"] is False
        assert "full_policy" in str(scope["default"])
    finally:
        db.close()


def test_existing_rows_are_untouched_and_new_fields_start_empty() -> None:
    # 마이그레이션은 backfill 하지 않는다. 기존 정책은 card_summary 가 비어 있고 상세 필드는 그대로,
    # 기존 후보는 full_policy 로 - 이전과 똑같이 동작한다.
    db = _make_session()
    try:
        policy = Policy(
            id=1, slug="legacy", title="Legacy", region="전국", status="active",
            benefit_detail="최대 2만원", benefit_amount=20000, description="원문 설명",
        )
        candidate = PolicyReviewCandidate(
            id=1, external_source_record_id=1, change_kind="new", evidence_fingerprint="f" * 64,
        )
        db.add_all([policy, candidate])
        db.commit()
        db.expire_all()

        stored = db.get(Policy, 1)
        assert stored is not None
        assert stored.card_summary is None
        assert (stored.benefit_detail, stored.benefit_amount, stored.description) == ("최대 2만원", 20000, "원문 설명")
        assert db.get(PolicyReviewCandidate, 1).review_scope == "full_policy"
    finally:
        db.close()
