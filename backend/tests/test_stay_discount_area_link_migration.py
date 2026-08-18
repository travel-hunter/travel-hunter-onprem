from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import Policy, Trip, TripPolicy, User, UserSavedPolicy
from app.scripts.migrate_stay_discount_area_policy_links import (
    migrate_stay_discount_area_policy_links,
)


def _make_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return TestingSessionLocal()


def test_migrates_stay_discount_canonical_links_to_matching_area_policy() -> None:
    db = _make_session()
    try:
        user = User(id=1, email="stay-link@example.com", nickname="stay-link")
        trip = Trip(
            id=7,
            owner_id=1,
            title="강원 고성 여행",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 2),
            region="강원",
        )
        canonical = Policy(
            id=23,
            slug="travelmonth-88",
            title="2026 대한민국 숙박세일 페스타 숙박 할인",
            region="전국",
            source_category="stay_discount",
            external_source_record_id=88,
            status="hidden",
        )
        gangwon_goseong = Policy(
            id=188,
            slug="stay-discount-gangwon-goseong",
            title="[고성] 2026 대한민국 숙박세일 페스타 숙박 할인",
            region="강원",
            source_category="stay_discount",
            external_source_record_id=88,
            status="active",
        )
        gyeongnam_goseong = Policy(
            id=189,
            slug="stay-discount-gyeongnam-goseong",
            title="[고성] 2026 대한민국 숙박세일 페스타 숙박 할인",
            region="경남",
            source_category="stay_discount",
            external_source_record_id=88,
            status="active",
        )
        db.add_all([user, trip, canonical, gangwon_goseong, gyeongnam_goseong])
        db.flush()
        db.add_all(
            [
                TripPolicy(id=1, trip_id=7, policy_id=23),
                UserSavedPolicy(id=1, user_id=1, policy_id=23),
            ]
        )
        db.commit()

        dry_run = migrate_stay_discount_area_policy_links(db)

        assert dry_run.trip_links_moved == 1
        assert dry_run.saved_links_moved == 1
        assert db.query(TripPolicy).one().policy_id == 23
        assert db.query(UserSavedPolicy).one().policy_id == 23

        applied = migrate_stay_discount_area_policy_links(db, apply=True)
        db.commit()

        assert applied.trip_links_moved == 1
        assert applied.saved_links_moved == 1
        assert db.query(TripPolicy).one().policy_id == 188
        assert db.query(UserSavedPolicy).one().policy_id == 188
    finally:
        db.close()
