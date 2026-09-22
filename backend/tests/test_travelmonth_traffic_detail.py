from __future__ import annotations

import importlib.util
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import ExternalSourceRecord, Policy, Trip, TripPolicy, User
from app.services.travelmonth_traffic_detail import (
    DEPOPULATION_REGIONS,
    depopulation_region_count,
    SECTION_KEYS,
    TRAFFIC_DETAIL_BY_TITLE,
    structured_detail_for_traffic,
)
from app.services.travelmonth_traffic_parser import core_traffic_title, parse_traffic_benefits

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "traffic_benefits_2026-09-22.html"
MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0045_traffic_structured_detail.py"


def _parsed_sources():
    return parse_traffic_benefits(
        FIXTURE.read_text(encoding="utf-8"),
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do",
        fetched_at=datetime(2026, 9, 22, 9, 0),
        today=date(2026, 9, 22),
    )


def _record_from_source(source) -> SimpleNamespace:
    return SimpleNamespace(
        title=source.title,
        benefit_text=source.benefit_text,
        raw_payload=source.raw_payload,
        source_category=source.source_category,
        start_date=source.start_date,
        end_date=source.end_date,
        last_fetched_at=source.last_fetched_at,
        created_at=None,
    )


def test_depopulation_region_list_adds_up_to_the_announced_89() -> None:
    assert sum(depopulation_region_count(names) for _, names in DEPOPULATION_REGIONS) == 89


def test_depopulation_regions_render_as_two_lines_not_eighty_nine_names() -> None:
    detail = TRAFFIC_DETAIL_BY_TITLE["인구감소지역 자동차 여행 할인"]
    items = [item for item in detail["supportContent"] if item["title"].startswith("대상 지역")]
    assert len(items) == 2
    assert items[0]["description"].startswith("부산 3 · 대구 3 ·")
    assert items[1]["url"].endswith("/depopulation.do")
    # 지명이 통째로 들어가지 않는다
    assert "영도구" not in items[0]["description"]


def test_every_card_on_the_live_page_resolves_to_a_curated_entry() -> None:
    # 페이지가 제목을 바꾸면 그 카드는 표에서 빠져 혜택 원문만 남는다. 그때 여기서 터져야 한다.
    titles = [core_traffic_title(source.title) for source in _parsed_sources()]
    assert len(titles) == 11
    assert [title for title in titles if title not in TRAFFIC_DETAIL_BY_TITLE] == []


def test_curated_items_never_carry_amount() -> None:
    # 프런트는 amount 가 있으면 description 대신 그것을 그린다(PolicyPages.structuredBenefitText).
    for title, detail in TRAFFIC_DETAIL_BY_TITLE.items():
        for section in SECTION_KEYS:
            for item in detail.get(section, []):
                assert "amount" not in item, f"{title} / {section}"


def test_unknown_title_falls_back_to_the_benefit_text() -> None:
    record = SimpleNamespace(
        title="여행가는 달 새 교통 혜택",
        benefit_text="새 혜택 원문",
        raw_payload={},
        source_category="traffic_benefit",
        start_date=date(2026, 9, 15),
        end_date=date(2026, 11, 30),
        last_fetched_at=None,
        created_at=None,
    )
    detail = structured_detail_for_traffic(record)
    assert detail["supportContent"] == [{"title": "혜택", "description": "새 혜택 원문"}]
    # 근거 문장이 없어도 레코드에 날짜가 있으면 기간은 보여 준다
    assert detail["periods"] == [
        {
            "title": "기간",
            "description": "9월 15일 ~ 11월 30일",
            "startDate": "2026-09-15",
            "endDate": "2026-11-30",
        }
    ]


def test_parsed_periods_win_over_the_curated_table() -> None:
    sources = {core_traffic_title(source.title): source for source in _parsed_sources()}

    rental = structured_detail_for_traffic(
        _record_from_source(sources["연안지역 제약환경(교통) 개선 및 체류 확대를 위한 렌터카 할인"])
    )
    assert [(item["title"], item["startDate"], item["endDate"]) for item in rental["periods"]] == [
        ("예약 기간", "2026-09-15", "2026-10-31"),
        ("탑승 및 이용 기간", "2026-10-01", "2026-10-31"),
    ]

    # 바다가는 달은 레코드에 기간이 없다. 표에 적어 둔 공식 캠페인 기간이 그대로 남는다.
    sea = structured_detail_for_traffic(_record_from_source(sources["바다가는 달"]))
    assert [item["title"] for item in sea["periods"]] == ["쿠폰 발급 기간", "탑승 기간"]


def test_dead_anchor_is_not_a_link_and_the_air_card_drops_the_four_person_guess() -> None:
    sources = {core_traffic_title(source.title): source for source in _parsed_sources()}
    assert len(sources) == 11
    assert sources["모두를 지키는 안전운전"].detail_url is None  # href="#"
    for title in ("네이버 페이 N포인트 지급 (최대 4만 포인트)", "방방곡곡 국내 여행"):
        assert "4인" not in sources[title].raw_payload["cardCopy"]["summary"]


def _run_upgrade(db: Session) -> None:
    spec = importlib.util.spec_from_file_location("migration_0045", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.op = SimpleNamespace(get_bind=lambda: db.connection())
    module.upgrade()
    db.commit()
    db.expire_all()  # 마이그레이션은 세션을 거치지 않고 썼다


def test_migration_fills_detail_without_touching_policy_identity_or_links() -> None:
    from tests.test_policy_candidate_review import make_record

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        source = next(
            source for source in _parsed_sources() if core_traffic_title(source.title) == "바다가는 달"
        )
        record = make_record()
        record.id = 114
        record.source_category = "traffic_benefit"
        record.title = source.title
        record.benefit_text = source.benefit_text
        record.raw_payload = source.raw_payload
        record.start_date = None
        record.collected_page_url = "https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do"
        policy = Policy(
            id=179,
            slug="travelmonth-114",
            title=source.title,
            region="전국",
            status="active",
            source_category="traffic_benefit",
            external_source_record_id=114,
            official_url="#",
            card_summary="카모아 렌터카 2만원 쿠폰(4인)",
        )
        user = User(id=1, email="u@example.com", nickname="u")
        trip = Trip(id=7, owner_id=1, title="t", start_date=date(2026, 10, 1), end_date=date(2026, 10, 2), region="전국")
        link = TripPolicy(id=1, trip_id=7, policy_id=179)  # sqlite: BigInteger PK 는 자동 채번이 안 된다
        db.add_all([record, policy, user, trip, link])
        db.commit()

        _run_upgrade(db)

        updated = db.get(Policy, 179)
        assert updated is not None
        assert updated.slug == "travelmonth-114" and updated.external_source_record_id == 114
        assert db.query(TripPolicy).count() == 1
        assert updated.card_summary == "카모아 렌터카 2만원 쿠폰"
        assert updated.official_url == "https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do"
        assert updated.structured_detail["supportContent"][0]["title"] == "지원 내용"
        assert [item["title"] for item in updated.structured_detail["periods"]] == ["쿠폰 발급 기간", "탑승 기간"]
        assert db.query(ExternalSourceRecord).count() == 1
    finally:
        db.close()
