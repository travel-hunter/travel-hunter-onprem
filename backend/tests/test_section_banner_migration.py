"""0054: 여행가는 달 칸별 요약 배너 4건을 정책에서 내린다(2026-10-15 사용자 결정)."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import ExternalSourceRecord, Policy, Trip, TripPolicy, User, UserSavedPolicy
from app.services.travelmonth_traffic_parser import traffic_canonical_key

MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0054_traffic_section_banners.py"

# (배너 정책 id, 배너 제목) → (같은 칸 혜택 정책 id, 제목)
PAIRS = [
    ((173, "대한민국 구석구석 자유로운 기차여행"), (169, "인구감소지역 자유여행상품 할인")),
    ((175, "비행기타고 떠나는 방방곡곡 국내 여행"), (174, "’네이버 항공권‘에서 국내선 이용 시 네이버 페이 N포인트 지급 (최대 4만 포인트)")),
    ((177, "지구를 지키는 친환경여행 모두를 지키는 안전운전"), (176, "인구감소지역 자동차 여행 할인")),
    ((179, "바다가는 달"), (178, "연안지역 제약환경(교통) 개선 및 체류 확대를 위한 렌터카 할인")),
]


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _record_and_policy(policy_id: int, title: str) -> list[object]:
    from tests.test_policy_candidate_review import make_record

    record = make_record()
    record.id = policy_id - 65  # 정책 169 ↔ 기록 104 처럼 실제와 같은 간격
    record.source_category = "traffic_benefit"
    record.title = record.raw_list_text = title
    record.external_id = record.canonical_key = traffic_canonical_key(title)
    record.is_nationwide = True
    record.region = "전국"
    record.city = None
    record.freshness_status = "fresh"
    policy = Policy(id=policy_id, slug=f"travelmonth-{record.id}", title=title, region="전국", status="active",
                    source_category="traffic_benefit", external_source_record_id=record.id)
    return [record, policy]


def _run_upgrade(db: Session) -> None:
    spec = importlib.util.spec_from_file_location("migration_0054", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.op = SimpleNamespace(get_bind=lambda: db.connection())
    module.upgrade()
    db.commit()
    db.expire_all()


def test_banners_are_hidden_and_their_user_links_move_to_the_benefit_in_the_same_section() -> None:
    db = _make_session()
    try:
        rows: list[object] = []
        for (banner_id, banner_title), (host_id, host_title) in PAIRS:
            rows += _record_and_policy(banner_id, banner_title) + _record_and_policy(host_id, host_title)
        user = User(id=1, email="u@example.com", nickname="u")
        trip = Trip(id=7, owner_id=1, title="t", start_date=date(2026, 10, 1), end_date=date(2026, 10, 2), region="전국")
        db.add_all([
            *rows, user, trip,
            # sqlite: BigInteger PK 는 자동 채번이 안 된다
            TripPolicy(id=1, trip_id=7, policy_id=173), TripPolicy(id=2, trip_id=7, policy_id=179),
            TripPolicy(id=3, trip_id=7, policy_id=178), UserSavedPolicy(id=1, user_id=1, policy_id=175),
        ])
        db.commit()

        _run_upgrade(db)

        for (banner_id, _), (host_id, _) in PAIRS:
            assert db.get(Policy, banner_id).status == "hidden"
            assert db.get(ExternalSourceRecord, banner_id - 65).freshness_status == "stale"  # 다음 수집이 되살리지 않게
            assert db.get(Policy, host_id).status == "active"
        assert sorted(link.policy_id for link in db.query(TripPolicy).all()) == [169, 178]  # 179 는 이미 178 을 담아 하나만
        assert [saved.policy_id for saved in db.query(UserSavedPolicy).all()] == [174]
    finally:
        db.close()


def test_upgrade_is_a_noop_without_banner_policies() -> None:
    db = _make_session()
    try:
        db.add_all(_record_and_policy(169, "인구감소지역 자유여행상품 할인"))
        db.commit()
        _run_upgrade(db)
        assert db.get(Policy, 169).status == "active"
    finally:
        db.close()
