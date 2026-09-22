from __future__ import annotations

import importlib.util
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import ExternalSourceRecord, Policy, PolicyReviewCandidate, Trip, TripPolicy, User
from app.services.travelmonth_traffic_parser import traffic_canonical_key

MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0044_traffic_canonical_key.py"


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _record(id: int, title: str, key: str) -> ExternalSourceRecord:
    # 필수 컬럼이 많아 후보 검토 테스트의 완성된 헬퍼를 빌려 쓴다
    from tests.test_policy_candidate_review import make_record

    record = make_record()
    record.id = id
    record.source_category = "traffic_benefit"
    record.title = title
    record.raw_list_text = title
    record.external_id = key
    record.canonical_key = key
    record.is_nationwide = True
    record.region = "전국"
    record.city = None
    return record


def _run_upgrade(db: Session) -> None:
    spec = importlib.util.spec_from_file_location("migration_0044", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    # alembic 의 op.get_bind() 대신 세션 연결을 넘긴다
    module.op = SimpleNamespace(get_bind=lambda: db.connection())
    module.upgrade()
    db.commit()
    db.expire_all()  # 마이그레이션은 세션을 거치지 않고 썼다 - 캐시된 행을 버린다


def test_rekeys_the_published_row_and_drops_scrape_leftovers_without_touching_links() -> None:
    db = _make_session()
    try:
        # 옛 행(원문 해시 key)에 정책과 사용자 링크가 붙어 있고, 같은 정책의 수집 잔여물 두 개가 다른 key 로 남아 있다
        old = _record(114, "바다가는 달", "48c01094929fabc077d530691dfe5499")
        leftover_a = _record(122, "바다가는 달", "cb5268728ca6255469b7442b595da4a3")
        leftover_b = _record(130, "바다가는 달", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        other = _record(106, "테마열차 할인", "1bf68fd579efc03750913ab62d3a59e9")
        policy = Policy(id=179, slug="travelmonth-114", title="바다가는 달", region="전국", status="active",
                        source_category="traffic_benefit", external_source_record_id=114)
        user = User(id=1, email="u@example.com", nickname="u")
        trip = Trip(id=7, owner_id=1, title="t", start_date=date(2026, 10, 1), end_date=date(2026, 10, 2), region="전국")
        link = TripPolicy(id=1, trip_id=7, policy_id=179)  # sqlite: BigInteger PK 는 자동 채번이 안 된다
        cand = PolicyReviewCandidate(id=92, external_source_record_id=122, change_kind="new", evidence_fingerprint="f" * 64)
        db.add_all([old, leftover_a, leftover_b, other, policy, user, trip, link, cand])
        db.commit()

        _run_upgrade(db)

        rows = {r.id: r for r in db.query(ExternalSourceRecord).all()}
        assert set(rows) == {114, 106}                                  # 잔여물 122·130 삭제
        assert rows[114].canonical_key == traffic_canonical_key("바다가는 달")
        assert rows[114].external_id == rows[114].canonical_key
        assert rows[106].canonical_key == traffic_canonical_key("테마열차 할인")
        assert db.query(PolicyReviewCandidate).count() == 0            # 잔여물의 후보도 같이
        # 정책·링크는 그대로
        kept = db.get(Policy, 179)
        assert kept is not None and kept.slug == "travelmonth-114" and kept.external_source_record_id == 114
        assert db.query(TripPolicy).count() == 1
    finally:
        db.close()


def test_upgrade_is_a_noop_on_a_database_without_traffic_records() -> None:
    db = _make_session()
    try:
        stay = _record(5, "[고성] 숙박 할인", "k")
        stay.source_category = "stay_discount"
        db.add(stay)
        db.commit()
        _run_upgrade(db)
        assert db.execute(text("SELECT canonical_key FROM external_source_records WHERE id = 5")).scalar() == "k"
    finally:
        db.close()
