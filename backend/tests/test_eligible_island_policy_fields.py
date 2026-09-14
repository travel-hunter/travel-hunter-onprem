"""Island policy detail fields and exact-match itinerary recommendation from the approved catalog."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.models import Policy, Trip, TripDay, TripPlace, User
from app.repositories.eligible_islands import CATALOG_KEY_ISLAND_VISIT_2026 as KEY
from app.services import trips as trip_service
from app.services.eligible_island_catalog import approve_snapshot, build_eligible_island_summary, stage_snapshot
from app.services.eligible_island_notice import ParsedIsland, SourceDocument
from app.services.policies import list_policies, policy_to_api

ISLAND_SLUG = "2026-island-visit-support"


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with TestingSessionLocal() as session:
        yield session


def approve_fixture_snapshot(db: Session, pairs) -> None:
    admin = db.get(User, 10) or User(id=10, email="admin@example.com", nickname="admin", role="admin")
    db.add(admin)
    db.flush()
    staged = stage_snapshot(
        db,
        catalog_key=KEY,
        entries=[ParsedIsland(name, name, jurisdiction) for name, jurisdiction in pairs],
        notice_url="https://www.visitisland.kr/notice/1",
        notice_title="대상 섬",
        documents=[SourceDocument("https://www.visitisland.kr/files/list.xlsx", "list.xlsx", f"{len(pairs):064d}")],
        fetched_at=datetime(2026, 9, 14, tzinfo=UTC),
    )
    approve_snapshot(db, catalog_key=KEY, snapshot_id=staged.snapshot.id, admin=admin)


_policy_ids = iter(range(100, 10_000))  # policies.id is BigInteger: sqlite does not autoincrement it


def make_policy(db: Session, *, slug: str, title: str, source_category: str | None, benefit_detail: str) -> Policy:
    policy = Policy(
        id=next(_policy_ids),
        slug=slug,
        title=title,
        benefit_detail=benefit_detail,
        region="전국",
        status="active",
        source_category=source_category,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    db.add(policy)
    db.commit()
    return policy


def make_trip(place_names: list[str]) -> Trip:
    trip = Trip(id=7, owner_id=1, title="섬 여행", status="draft", revision=1, start_date=date(2026, 6, 15), end_date=date(2026, 6, 17), region="전남")
    day = TripDay(id=1, trip_id=7, day_number=1, date=date(2026, 6, 15))
    day.places = [TripPlace(id=index + 1, trip_day_id=1, place_name=name, order_num=index + 1) for index, name in enumerate(place_names)]
    trip.days = [day]
    trip.policies = []
    return trip


def recommended_slugs_for_places(db: Session, place_names: list[str]) -> set[str]:
    candidates = trip_service._list_recommended_policy_candidates(db)
    return {item["slug"] for item in trip_service._recommended_policies(make_trip(place_names), candidates, limit=10)}


def test_island_policy_exposes_approved_count_without_changing_text(db: Session) -> None:
    policy = make_policy(db, slug=ISLAND_SLUG, title="2026 섬 여행비 지원", source_category="island_visit", benefit_detail="최대 10만원")
    approve_fixture_snapshot(db, [("가거도", "전남 신안군")])
    payload = policy_to_api(policy, islands=build_eligible_island_summary(db))
    assert payload["eligibleIslandCount"] == 1
    assert payload["eligibleIslandsOfficialUrl"] == "https://www.visitisland.kr/notice/1"
    assert payload["title"] == "2026 섬 여행비 지원"
    assert payload["amount"] == "최대 10만원"


def test_island_fields_absent_for_other_policies_and_zero_before_approval(db: Session) -> None:
    make_policy(db, slug=ISLAND_SLUG, title="2026 섬 여행비 지원", source_category="island_visit", benefit_detail="최대 10만원")
    make_policy(db, slug="busan-cashback", title="부산 캐시백", source_category="regional_benefit", benefit_detail="5%")
    payloads = {item["slug"]: item for item in list_policies(db)}
    assert "eligibleIslandCount" not in payloads["busan-cashback"]
    assert payloads[ISLAND_SLUG]["eligibleIslandCount"] == 0
    assert payloads[ISLAND_SLUG]["eligibleIslandsOfficialUrl"] == "https://www.visitisland.kr/promotion2"


def test_island_recommendation_requires_exact_normalized_place_name(db: Session) -> None:
    make_policy(db, slug=ISLAND_SLUG, title="2026 섬 여행비 지원", source_category="island_visit", benefit_detail="최대 10만원")
    approve_fixture_snapshot(db, [("가거도", "전남 신안군")])
    assert recommended_slugs_for_places(db, [" 가거도 "]) == {ISLAND_SLUG}
    assert recommended_slugs_for_places(db, ["가거도 선착장"]) == set()
    assert recommended_slugs_for_places(db, []) == set()


def test_island_policy_never_recommended_before_any_approval_but_others_are(db: Session) -> None:
    make_policy(db, slug=ISLAND_SLUG, title="2026 섬 여행비 지원", source_category="island_visit", benefit_detail="최대 10만원")
    make_policy(db, slug="jeonnam-stay", title="전남 숙박 할인", source_category="regional_benefit", benefit_detail="30%")
    assert recommended_slugs_for_places(db, ["가거도"]) == {"jeonnam-stay"}
