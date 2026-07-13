import json
from datetime import datetime

import app.models  # noqa: F401
import pytest
from sqlalchemy import Integer, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import ExternalSourceRecord, Policy


class NonClosingSessionFactory:
    def __init__(self, db: Session) -> None:
        self.db = db

    def __call__(self) -> "NonClosingSessionFactory":
        return self

    def __enter__(self) -> Session:
        return self.db

    def __exit__(self, *_args: object) -> None:
        return None


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    external_id_column = ExternalSourceRecord.__table__.c.id
    policy_id_column = Policy.__table__.c.id
    original_external_id_type = external_id_column.type
    original_policy_id_type = policy_id_column.type
    external_id_column.type = Integer()
    policy_id_column.type = Integer()
    try:
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(bind=engine)
        with TestingSessionLocal() as session:
            yield session
        Base.metadata.drop_all(engine)
    finally:
        external_id_column.type = original_external_id_type
        policy_id_column.type = original_policy_id_type


def add_promoted_policy(db: Session) -> Policy:
    fetched_at = datetime(2026, 5, 23, 9, 0, 0)
    source = ExternalSourceRecord(
        source_name="여행가는 달",
        source_type="official_campaign",
        source_url="https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
        source_category="regional_benefit",
        external_id="namdo-train",
        canonical_key="namdo-train",
        detail_url=None,
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
        title="남도 기차둘레길 1박 2일 최대 35% 할인행사",
        organizer_text="한국관광공사",
        organizers=["한국관광공사"],
        region="전남",
        city=None,
        is_nationwide=False,
        status="active",
        benefit_text="남도 기차 여행상품 최대 35% 할인",
        benefit_value_text="최대 35%",
        benefit_value_type="percent",
        tags=[],
        inferred_travel_styles=[],
        confidence=90,
        field_completeness=90,
        raw_list_text="남도 기차둘레길 1박 2일 최대 35% 할인행사",
        raw_detail_text="남도 기차 여행상품 최대 35% 할인",
        raw_payload={},
        last_fetched_at=fetched_at,
        freshness_status="fresh",
    )
    db.add(source)
    db.flush()
    policy = Policy(
        slug="travelmonth-1",
        title=source.title,
        policy_type="지역할인",
        region="전남",
        external_source_record_id=source.id,
    )
    db.add(policy)
    db.flush()
    return policy


def test_reclassification_cli_dry_run_reports_without_mutating(db: Session, monkeypatch, capsys) -> None:
    from app.scripts import reclassify_external_policy_categories as script

    policy = add_promoted_policy(db)
    monkeypatch.setattr(script, "get_session_factory", lambda: NonClosingSessionFactory(db))

    exit_code = script.main([])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["checkedCount"] == 1
    assert payload["changedCount"] == 1
    assert payload["applied"] is False
    assert payload["changes"][0]["from"] == "지역할인"
    assert payload["changes"][0]["to"] == "교통"
    assert policy.policy_type == "지역할인"


def test_reclassification_cli_apply_updates_policy(db: Session, monkeypatch, capsys) -> None:
    from app.scripts import reclassify_external_policy_categories as script

    policy = add_promoted_policy(db)
    monkeypatch.setattr(script, "get_session_factory", lambda: NonClosingSessionFactory(db))

    exit_code = script.main(["--apply"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["checkedCount"] == 1
    assert payload["changedCount"] == 1
    assert payload["applied"] is True
    assert policy.policy_type == "교통"
