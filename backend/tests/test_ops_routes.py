from datetime import date, datetime, timedelta, time
from typing import get_args

import app.models  # noqa: F401
from fastapi.testclient import TestClient
from sqlalchemy import Integer, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import dependencies as api_dependencies
from app.api.routes import ops as ops_routes
from app.db.base import Base
from app.main import app
from app.models import ExternalSourceRecord, User
from app.repositories.external_sources import upsert_external_source_records
from app.schemas.external_sources import ExternalBenefitSource, TravelStyle
from app.services.external_benefit_collection import (
    ExternalBenefitCollectionResult,
    SourceCollectionResult,
)
from app.services import external_collection_scheduler
from app.services.region_recommendations import NATIONWIDE_REGION
from app.services.travelmonth_collection import CollectionResult


client = TestClient(app)
FETCHED_AT = datetime(2026, 5, 21, 9, 0, 0)
SOURCE_NAME = "대한민국 반값여행"
STYLE_FOOD = get_args(TravelStyle)[1]
STYLE_EXPERIENCE = get_args(TravelStyle)[2]


def make_ops_user(*, role: str = "admin") -> User:
    return User(
        id=1,
        email="ops@example.com",
        nickname="Ops User",
        role=role,
        onboarding_completed=True,
        created_at=datetime(2026, 5, 21, 0, 0, 0),
        updated_at=datetime(2026, 5, 21, 0, 0, 0),
    )


def authenticate_ops_user() -> None:
    app.dependency_overrides[ops_routes.require_admin_user] = make_ops_user


def clear_ops_user() -> None:
    app.dependency_overrides.pop(ops_routes.require_admin_user, None)
    app.dependency_overrides.pop(api_dependencies.get_current_user, None)


def make_source(
    canonical_key: str,
    *,
    region: str,
    title: str,
    amount: int | None = None,
    end_date: date | None = None,
    styles: list[str] | None = None,
    is_nationwide: bool = False,
    status: str = "active",
    freshness_status: str = "fresh",
) -> ExternalBenefitSource:
    return ExternalBenefitSource(
        source_name=SOURCE_NAME,
        source_type="official_campaign",
        source_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        source_category="local_half_trip",
        external_id=canonical_key,
        canonical_key=canonical_key,
        detail_url=None,
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        title=title,
        organizer_text=f"{region} organizer",
        organizers=[f"{region} organizer"],
        region=region,
        city=None,
        is_nationwide=is_nationwide,
        status_text="[active]",
        status=status,
        start_date=date(2026, 5, 1),
        end_date=end_date,
        benefit_text=title,
        benefit_value_text=f"max {amount}" if amount else None,
        extracted_amount_krw=amount,
        extracted_discount_percent=None,
        benefit_value_type="amount" if amount else "unknown",
        tags=styles or [],
        contact_text=None,
        inferred_travel_styles=styles or [],
        confidence=90,
        field_completeness=95,
        raw_list_text=title,
        raw_detail_text=title,
        raw_payload={"periodText": "2026-05-01 ~ 2026-05-31"},
        last_fetched_at=FETCHED_AT,
        last_verified_at=FETCHED_AT,
        freshness_status=freshness_status,
    )


def with_test_db(sources: list[ExternalBenefitSource]):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    id_column = ExternalSourceRecord.__table__.c.id
    original_type = id_column.type
    id_column.type = Integer()
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()
    upsert_external_source_records(session, sources)
    session.commit()
    app.dependency_overrides[ops_routes.get_optional_db] = lambda: session
    return session, engine, id_column, original_type


def cleanup_test_db(
    session: Session,
    engine,
    id_column,
    original_type,
) -> None:
    app.dependency_overrides.pop(ops_routes.get_optional_db, None)
    session.close()
    Base.metadata.drop_all(engine)
    id_column.type = original_type


def test_external_collection_ops_health_returns_scheduler_snapshot() -> None:
    authenticate_ops_user()
    try:
        response = client.get("/api/ops/external-collection")
    finally:
        clear_ops_user()

    assert response.status_code == 200
    assert response.json() == {
        "schedulerEnabled": False,
        "runAt": "03:00",
        "pollSeconds": 60,
        "minParsedCount": 1,
        "lastAttemptedRunDate": None,
        "lastSuccessfulRunDate": None,
        "lastParsedCount": None,
        "lastOutcome": None,
        "lastError": None,
    }


def test_external_collection_ops_health_requires_admin() -> None:
    clear_ops_user()

    response = client.get("/api/ops/external-collection")

    assert response.status_code == 401

    app.dependency_overrides[api_dependencies.get_current_user] = lambda: make_ops_user(role="user")
    try:
        response = client.get("/api/ops/external-collection")
    finally:
        clear_ops_user()

    assert response.status_code == 403


def test_regular_api_health_contract_is_unchanged() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert set(response.json()) == {"status", "service", "environment", "database"}


def test_external_collection_ops_health_exposes_active_scheduler_status(
    monkeypatch,
) -> None:
    scheduler = external_collection_scheduler.ExternalCollectionScheduler(
        run_at=time(3, 0),
        poll_seconds=60,
        now_provider=lambda: datetime(2026, 5, 21, 3, 0, 0),
        collect=lambda _today: CollectionResult(
            source_name="travelmonth",
            source_category="regional_benefit",
            parsed_count=58,
            created_or_updated_count=58,
        ),
    )
    scheduler.run_once_if_due()
    external_collection_scheduler.set_active_external_collection_scheduler(scheduler)

    authenticate_ops_user()
    try:
        response = client.get("/api/ops/external-collection")
    finally:
        clear_ops_user()
        external_collection_scheduler.set_active_external_collection_scheduler(None)

    assert response.status_code == 200
    assert {
        "lastAttemptedRunDate": "2026-05-21",
        "lastSuccessfulRunDate": "2026-05-21",
        "lastParsedCount": 58,
        "lastOutcome": "success",
        "lastError": None,
    }.items() <= response.json().items()


def test_external_collection_run_triggers_live_collection_for_admin(monkeypatch) -> None:
    fake_db = object()
    app.dependency_overrides[ops_routes.get_optional_db] = lambda: fake_db
    authenticate_ops_user()
    calls: list[object] = []

    def fake_collect(db):
        calls.append(db)
        return ExternalBenefitCollectionResult(
            source_name="official external benefits",
            source_category="multiple",
            parsed_count=3,
            created_or_updated_count=2,
            outcome="partial_success",
            sources=[
                SourceCollectionResult(
                    source_category="local_half_trip",
                    parsed_count=2,
                    created_or_updated_count=2,
                    outcome="success",
                ),
                SourceCollectionResult(
                    source_category="traffic_benefit",
                    parsed_count=0,
                    created_or_updated_count=0,
                    outcome="source_unavailable",
                    error="404 Client Error: Not Found for url",
                ),
            ],
        )

    monkeypatch.setattr(ops_routes, "collect_external_benefits_from_live_sources", fake_collect)

    try:
        response = client.post("/api/ops/external-collection/run")
    finally:
        clear_ops_user()
        app.dependency_overrides.pop(ops_routes.get_optional_db, None)

    assert response.status_code == 200
    assert calls == [fake_db]
    assert response.json() == {
        "sourceName": "official external benefits",
        "sourceCategory": "multiple",
        "parsedCount": 3,
        "createdOrUpdatedCount": 2,
        "outcome": "partial_success",
        "sources": [
            {
            "sourceCategory": "local_half_trip",
                "parsedCount": 2,
                "createdOrUpdatedCount": 2,
                "outcome": "success",
                "error": None,
            },
            {
                "sourceCategory": "traffic_benefit",
                "parsedCount": 0,
                "createdOrUpdatedCount": 0,
                "outcome": "source_unavailable",
                "error": "404 Client Error: Not Found for url",
            },
        ],
    }


def test_external_collection_quality_report_returns_empty_counts() -> None:
    session, engine, id_column, original_type = with_test_db([])
    authenticate_ops_user()
    try:
        response = client.get("/api/ops/external-collection/quality")
    finally:
        clear_ops_user()
        cleanup_test_db(session, engine, id_column, original_type)

    assert response.status_code == 200
    assert response.json() == {
        "sourceName": SOURCE_NAME,
        "sourceCategory": "local_half_trip",
        "totalRecords": 0,
        "freshRecords": 0,
        "activeRecords": 0,
        "regionalRecords": 0,
        "nationwideRecords": 0,
        "recordsWithAmount": 0,
        "recordsWithStyles": 0,
        "latestFetchedAt": None,
        "latestVerifiedAt": None,
        "regions": [],
        "recommendationPreview": [],
    }


def test_external_collection_quality_accepts_source_category_filter() -> None:
    traffic_source = ExternalBenefitSource(
        source_name="여행가는 달",
        source_type="official_campaign",
        source_url="https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do",
        source_category="traffic_benefit",
        external_id="traffic-1",
        canonical_key="traffic-1",
        detail_url=None,
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do",
        title="Theme train discount",
        organizer_text="Korail",
        organizers=["Korail"],
        region="전국",
        city=None,
        is_nationwide=True,
        status_text="active",
        status="active",
        start_date=None,
        end_date=None,
        benefit_text="Theme train fare 50% discount",
        benefit_value_text="50% discount",
        extracted_amount_krw=None,
        extracted_discount_percent=50,
        benefit_value_type="percent",
        tags=["traffic"],
        contact_text=None,
        inferred_travel_styles=[],
        confidence=90,
        field_completeness=90,
        raw_list_text="Theme train fare 50% discount",
        raw_detail_text="Theme train fare 50% discount",
        raw_payload={},
        last_fetched_at=FETCHED_AT,
        last_verified_at=FETCHED_AT,
        freshness_status="fresh",
    )
    session, engine, id_column, original_type = with_test_db([traffic_source])
    authenticate_ops_user()
    try:
        response = client.get(
            "/api/ops/external-collection/quality?sourceCategory=traffic_benefit"
        )
    finally:
        clear_ops_user()
        cleanup_test_db(session, engine, id_column, original_type)

    assert response.status_code == 200
    payload = response.json()
    assert payload["sourceCategory"] == "traffic_benefit"
    assert payload["totalRecords"] == 1
    assert payload["recordsWithAmount"] == 0


def test_external_collection_quality_report_summarizes_saved_records() -> None:
    today = date.today()
    session, engine, id_column, original_type = with_test_db(
        [
            make_source(
                "busan-1",
                region="Busan",
                title="Busan food support",
                amount=50000,
                end_date=today + timedelta(days=3),
                styles=[STYLE_FOOD],
            ),
            make_source(
                "busan-2",
                region="Busan",
                title="Busan experience support",
                amount=None,
                end_date=today + timedelta(days=30),
                styles=[STYLE_EXPERIENCE],
            ),
            make_source(
                "jeju-1",
                region="Jeju",
                title="Jeju stale support",
                amount=70000,
                freshness_status="stale",
            ),
            make_source(
                "nationwide-1",
                region=NATIONWIDE_REGION,
                title="Nationwide support",
                amount=10000,
                is_nationwide=True,
            ),
        ]
    )
    authenticate_ops_user()
    try:
        response = client.get(
            f"/api/ops/external-collection/quality?style={STYLE_FOOD}&region=Busan&limit=2"
        )
    finally:
        clear_ops_user()
        cleanup_test_db(session, engine, id_column, original_type)

    assert response.status_code == 200
    payload = response.json()
    assert payload["totalRecords"] == 4
    assert payload["freshRecords"] == 3
    assert payload["activeRecords"] == 4
    assert payload["regionalRecords"] == 3
    assert payload["nationwideRecords"] == 1
    assert payload["recordsWithAmount"] == 3
    assert payload["recordsWithStyles"] == 2
    assert payload["latestFetchedAt"] == "2026-05-21T09:00:00"
    assert payload["latestVerifiedAt"] == "2026-05-21T09:00:00"
    assert payload["regions"][0] == {
        "region": "Busan",
        "totalRecords": 2,
        "activeFreshRecords": 2,
        "endingSoonRecords": 1,
        "recordsWithAmount": 1,
        "estimatedValueKrw": 50000,
        "styleCounts": {STYLE_EXPERIENCE: 1, STYLE_FOOD: 1},
    }
    assert payload["recommendationPreview"][0]["region"] == "Busan"
    assert payload["recommendationPreview"][0]["policyCount"] == 2


def test_external_collection_quality_meets_release_candidate_gate_for_fresh_active_records() -> None:
    session, engine, id_column, original_type = with_test_db(
        [
            make_source(
                "busan-release-gate",
                region="Busan",
                title="Busan release gate support",
                amount=50000,
                styles=[STYLE_FOOD],
            )
        ]
    )
    authenticate_ops_user()
    try:
        health_response = client.get("/api/ops/external-collection")
        quality_response = client.get("/api/ops/external-collection/quality")
    finally:
        clear_ops_user()
        cleanup_test_db(session, engine, id_column, original_type)

    assert health_response.status_code == 200
    assert quality_response.status_code == 200
    min_parsed_count = health_response.json()["minParsedCount"]
    payload = quality_response.json()
    assert payload["totalRecords"] >= min_parsed_count
    assert payload["freshRecords"] > 0
    assert payload["activeRecords"] > 0
    assert payload["latestFetchedAt"] is not None
    assert payload["latestVerifiedAt"] is not None
