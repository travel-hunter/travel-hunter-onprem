"""0053: 자유여행상품 추가 혜택을 할인 정책에 합친다(2026-10-15 사용자 결정)."""

from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import ExternalSourceRecord, Policy, Trip, TripPolicy, User, UserSavedPolicy
from app.services.travelmonth_traffic_parser import traffic_canonical_key

MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0053_free_tour_add_on_merge.py"
HOST = "인구감소지역 자유여행상품 할인"
ADD_ON = "인구감소지역 자유여행상품 추가 혜택"


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _record(id: int, title: str) -> ExternalSourceRecord:
    from tests.test_policy_candidate_review import make_record

    record = make_record()
    record.id = id
    record.source_category = "traffic_benefit"
    record.title = title
    record.raw_list_text = title
    record.external_id = record.canonical_key = traffic_canonical_key(title)
    record.is_nationwide = True
    record.region = "전국"
    record.city = None
    record.freshness_status = "fresh"
    return record


def _policy(id: int, record_id: int, title: str) -> Policy:
    return Policy(id=id, slug=f"travelmonth-{record_id}", title=title, region="전국", status="active",
                  source_category="traffic_benefit", external_source_record_id=record_id)


def _run_upgrade(db: Session) -> None:
    spec = importlib.util.spec_from_file_location("migration_0053", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.op = SimpleNamespace(get_bind=lambda: db.connection())
    module.upgrade()
    db.commit()
    db.expire_all()


def test_add_on_policy_folds_into_the_discount_policy_and_keeps_user_links() -> None:
    db = _make_session()
    try:
        user = User(id=1, email="u@example.com", nickname="u")
        both = Trip(id=7, owner_id=1, title="둘 다", start_date=date(2026, 10, 1), end_date=date(2026, 10, 2), region="전국")
        add_on_only = Trip(id=8, owner_id=1, title="추가만", start_date=date(2026, 10, 1), end_date=date(2026, 10, 2), region="전국")
        db.add_all([
            _record(104, HOST), _record(105, ADD_ON), _policy(169, 104, HOST), _policy(170, 105, ADD_ON),
            user, both, add_on_only,
            # sqlite: BigInteger PK 는 자동 채번이 안 된다
            TripPolicy(id=1, trip_id=7, policy_id=169), TripPolicy(id=2, trip_id=7, policy_id=170),
            TripPolicy(id=3, trip_id=8, policy_id=170), UserSavedPolicy(id=1, user_id=1, policy_id=170),
        ])
        db.commit()

        _run_upgrade(db)

        assert db.get(Policy, 170).status == "hidden"
        assert db.get(ExternalSourceRecord, 105).freshness_status == "stale"  # 다음 수집이 되살리지 않게
        links = sorted((link.trip_id, link.policy_id) for link in db.query(TripPolicy).all())
        assert links == [(7, 169), (8, 169)]                                  # 담은 일정은 합친 정책으로
        assert [saved.policy_id for saved in db.query(UserSavedPolicy).all()] == [169]
        host = db.get(Policy, 169)
        assert host.status == "active"
        assert host.card_summary == "방문 인증 운임 쿠폰·온누리 2만원"
        detail = host.structured_detail if isinstance(host.structured_detail, dict) else json.loads(host.structured_detail)
        assert any(item["title"].startswith("추가 혜택") for item in detail["supportContent"])
    finally:
        db.close()


def test_upgrade_is_a_noop_without_the_add_on_policy() -> None:
    db = _make_session()
    try:
        db.add_all([_record(104, HOST), _policy(169, 104, HOST)])
        db.commit()
        _run_upgrade(db)
        assert db.get(Policy, 169).status == "active"
    finally:
        db.close()
