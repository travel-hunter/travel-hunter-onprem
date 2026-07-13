from __future__ import annotations

from datetime import datetime

import app.models  # noqa: F401
import pytest
from sqlalchemy import Integer, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import ExternalSourceRecord
from app.repositories.external_sources import (
    get_external_source_record_by_policy_slug,
    list_external_source_records,
    list_policy_deactivation_records,
    list_policy_promotion_records,
    upsert_external_source_records,
)
from app.schemas.external_sources import ExternalBenefitSource


FETCHED_AT = datetime(2026, 5, 21, 9, 0, 0)
VERIFIED_AT = datetime(2026, 5, 21, 10, 0, 0)


def make_source(**overrides) -> ExternalBenefitSource:
    data = {
        "source_name": "여행가는 달",
        "source_type": "official_campaign",
        "source_url": "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
        "source_category": "regional_benefit",
        "external_id": "external-1",
        "canonical_key": "canonical-1",
        "detail_url": "https://www.yw.go.kr",
        "collected_page_url": "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
        "title": "영월박물관 사진 체험 할인",
        "organizer_text": "강원특별자치도, 영월군",
        "organizers": ["강원특별자치도", "영월군"],
        "region": "강원",
        "city": "영월군",
        "is_nationwide": False,
        "status_text": "[진행중]",
        "status": "active",
        "start_date": None,
        "end_date": None,
        "benefit_text": "영월박물관 사진관 체험 최대 50% 할인",
        "benefit_value_text": "최대 50% 할인",
        "extracted_amount_krw": None,
        "extracted_discount_percent": 50,
        "benefit_value_type": "percent",
        "tags": ["사진관", "영월박물관"],
        "contact_text": None,
        "inferred_travel_styles": ["체험", "사진"],
        "confidence": 90,
        "field_completeness": 95,
        "raw_list_text": "영월박물관 사진 체험 할인",
        "raw_detail_text": "영월박물관 사진관 체험 최대 50% 할인",
        "raw_payload": {"periodText": "2026-05-01 ~ 2026-05-31"},
        "last_fetched_at": FETCHED_AT,
        "last_verified_at": VERIFIED_AT,
        "freshness_status": "fresh",
    }
    data.update(overrides)
    return ExternalBenefitSource(**data)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    id_column = ExternalSourceRecord.__table__.c.id
    original_type = id_column.type
    id_column.type = Integer()
    try:
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(bind=engine)
        with TestingSessionLocal() as session:
            yield session
        Base.metadata.drop_all(engine)
    finally:
        id_column.type = original_type


def test_upsert_external_source_records_creates_rows(db: Session) -> None:
    rows = upsert_external_source_records(db, [make_source()])

    assert len(rows) == 1
    listed = list_external_source_records(db, source_name="여행가는 달")
    assert len(listed) == 1
    assert listed[0].canonical_key == "canonical-1"
    assert listed[0].region == "강원"


def test_upsert_external_source_records_updates_existing_row(db: Session) -> None:
    upsert_external_source_records(db, [make_source()])

    rows = upsert_external_source_records(
        db,
        [make_source(title="Updated title")],
    )

    assert rows[0].title == "Updated title"
    listed = list_external_source_records(db, source_name="여행가는 달")
    assert len(listed) == 1
    assert listed[0].title == "Updated title"


def test_policy_slug_fallback_allows_active_fresh_local_half_trip(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                source_name="대한민국 반값여행",
                source_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
                source_category="local_half_trip",
                external_id="half-trip-1",
                canonical_key="half-trip-1",
                collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
            )
        ],
    )

    found = get_external_source_record_by_policy_slug(db, f"travelmonth-{rows[0].id}")

    assert found is not None
    assert found.source_category == "local_half_trip"


def test_policy_slug_fallback_excludes_non_active_or_non_fresh_records(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(canonical_key="scheduled", external_id="scheduled", status="scheduled"),
            make_source(canonical_key="ended", external_id="ended", status="ended"),
            make_source(canonical_key="unknown", external_id="unknown", status="unknown"),
            make_source(canonical_key="stale", external_id="stale", freshness_status="stale"),
        ],
    )

    assert [
        get_external_source_record_by_policy_slug(db, f"travelmonth-{row.id}") for row in rows
    ] == [None, None, None, None]


def test_policy_promotion_records_include_scheduled_local_half_trip(
    db: Session,
) -> None:
    upsert_external_source_records(
        db,
        [
            make_source(
                source_category="local_half_trip",
                canonical_key="scheduled-half-trip",
                external_id="scheduled-half-trip",
                status="scheduled",
                freshness_status="unknown",
            ),
            make_source(
                source_category="local_half_trip",
                canonical_key="ended-half-trip",
                external_id="ended-half-trip",
                status="ended",
                freshness_status="unknown",
            ),
            make_source(
                source_category="stay_discount",
                canonical_key="scheduled-stay",
                external_id="scheduled-stay",
                status="scheduled",
                freshness_status="unknown",
            ),
        ],
    )

    promoted = list_policy_promotion_records(db)
    deactivated = list_policy_deactivation_records(db)

    assert [record.canonical_key for record in promoted] == ["scheduled-half-trip"]
    assert [record.canonical_key for record in deactivated] == [
        "ended-half-trip",
        "scheduled-stay",
    ]


def test_policy_slug_fallback_allows_active_fresh_stay_discount(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                source_category="stay_discount",
                external_id="stay-1",
                canonical_key="stay-1",
            )
        ],
    )

    found = get_external_source_record_by_policy_slug(db, f"travelmonth-{rows[0].id}")

    assert found is not None
    assert found.source_category == "stay_discount"


def test_policy_slug_fallback_excludes_active_fresh_regional_benefit(
    db: Session,
) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                source_category="regional_benefit",
                external_id="regional-1",
                canonical_key="regional-1",
            )
        ],
    )

    assert get_external_source_record_by_policy_slug(db, f"travelmonth-{rows[0].id}") is None


def test_policy_slug_fallback_excludes_active_fresh_traffic_benefit(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                source_category="traffic_benefit",
                external_id="traffic-1",
                canonical_key="traffic-1",
            )
        ],
    )

    assert get_external_source_record_by_policy_slug(db, f"travelmonth-{rows[0].id}") is None


def test_list_policy_deactivation_records_returns_non_active_or_non_fresh_records(
    db: Session,
) -> None:
    upsert_external_source_records(
        db,
        [
            make_source(canonical_key="active", external_id="active"),
            make_source(canonical_key="ended", external_id="ended", status="ended"),
            make_source(canonical_key="unknown", external_id="unknown", status="unknown"),
            make_source(canonical_key="stale", external_id="stale", freshness_status="stale"),
        ],
    )

    records = list_policy_deactivation_records(db)

    assert [record.canonical_key for record in records] == [
        "active",
        "ended",
        "unknown",
        "stale",
    ]
