from __future__ import annotations

from datetime import date, datetime
import logging

import app.models  # noqa: F401
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Integer, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import policies as policy_routes
from app.db.base import Base
from app.data.stay_discount_campaign import (
    STAY_DISCOUNT_CAMPAIGN_KEY,
    select_current_stay_discount_record,
)
from app.main import app
from app.models import (
    ExternalSourceRecord,
    Policy,
    Trip,
    TripPolicy,
    User,
    UserSavedPolicy,
)
from app.repositories.external_sources import upsert_external_source_records
from app.repositories.policies import get_policy_by_slug, get_policy_by_slug_any_status
from app.schemas.external_sources import ExternalBenefitSource

client = TestClient(app)


def make_source(**overrides) -> ExternalBenefitSource:
    data = {
        "source_name": "여행가는 달",
        "source_type": "official_campaign",
        "source_url": "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
        "source_category": "local_half_trip",
        "external_id": "external-1",
        "canonical_key": "canonical-1",
        "detail_url": "https://example.com/detail",
        "collected_page_url": "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
        "title": "Official regional benefit",
        "organizer_text": "Official organizer",
        "organizers": ["Official organizer"],
        "region": "Busan",
        "city": None,
        "is_nationwide": False,
        "status_text": "active",
        "status": "active",
        "start_date": None,
        "end_date": None,
        "benefit_text": "Official benefit text",
        "benefit_value_text": "Up to 50,000 KRW",
        "extracted_amount_krw": 50000,
        "extracted_discount_percent": None,
        "benefit_value_type": "amount",
        "tags": [],
        "contact_text": None,
        "inferred_travel_styles": [],
        "confidence": 90,
        "field_completeness": 90,
        "raw_list_text": "Official regional benefit",
        "raw_detail_text": "Official benefit detail",
        "raw_payload": {},
        "last_fetched_at": "2026-05-22T09:00:00",
        "last_verified_at": "2026-05-22T10:00:00",
        "freshness_status": "fresh",
    }
    data.update(overrides)
    return ExternalBenefitSource(**data)


def make_external_source_record(**overrides) -> ExternalSourceRecord:
    data = {
        "id": 20,
        "source_name": "여행가는 달",
        "source_type": "official_campaign",
        "source_url": "https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        "source_category": "local_half_trip",
        "external_id": "tour50-20",
        "canonical_key": "tour50-20",
        "detail_url": "https://example.com/detail",
        "collected_page_url": "https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        "title": "대한민국 구석구석 반값여행",
        "organizer_text": "한국관광공사",
        "organizers": ["한국관광공사"],
        "region": "경남",
        "city": "거창",
        "is_nationwide": False,
        "status_text": "신청접수중",
        "status": "active",
        "benefit_text": "대한민국 구석구석 반값여행",
        "benefit_value_text": "여행비 50% 환급",
        "extracted_amount_krw": 100000,
        "extracted_discount_percent": 50,
        "benefit_value_type": "refund",
        "tags": [],
        "contact_text": None,
        "inferred_travel_styles": [],
        "confidence": 90,
        "field_completeness": 90,
        "raw_list_text": "대한민국 구석구석 반값여행",
        "raw_detail_text": "legacy polluted detail",
        "raw_payload": {"notes": "영수증과 인증사진이 섞인 legacy 원문"},
        "last_fetched_at": datetime(2026, 7, 16, 9, 0, 0),
        "last_verified_at": datetime(2026, 7, 16, 10, 0, 0),
        "freshness_status": "fresh",
    }
    data.update(overrides)
    return ExternalSourceRecord(**data)


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    patched_columns = [
        ExternalSourceRecord.__table__.c.id,
        Policy.__table__.c.id,
    ]
    original_types = [column.type for column in patched_columns]
    for column in patched_columns:
        column.type = Integer()
    try:
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(bind=engine)
        with TestingSessionLocal() as session:
            yield session
        Base.metadata.drop_all(engine)
    finally:
        for column, original_type in zip(patched_columns, original_types, strict=True):
            column.type = original_type


def _policy_identity_state(db: Session) -> dict[str, object]:
    return {
        "policies": [
            (
                policy.id,
                policy.slug,
                policy.status,
                policy.external_source_record_id,
                policy.title,
            )
            for policy in db.query(Policy).order_by(Policy.id)
        ],
        "sources": [
            (record.id, record.canonical_key, record.logical_key)
            for record in db.query(ExternalSourceRecord).order_by(ExternalSourceRecord.id)
        ],
        "saved": [(row.user_id, row.policy_id) for row in db.query(UserSavedPolicy)],
        "trip": [(row.trip_id, row.policy_id) for row in db.query(TripPolicy)],
    }


def test_promotes_active_fresh_external_record_to_policy(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                title="Busan official benefit",
                region="Busan",
                canonical_key="busan-benefit",
                external_id="busan-benefit",
                benefit_value_text="Up to 50,000 KRW",
                extracted_amount_krw=50000,
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies
    from app.services.policies import policy_to_api

    result = promote_external_benefits_to_policies(db)

    assert result.promoted_count == 1
    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert policy is not None
    assert policy.title == "Busan official benefit"
    assert policy.region == "Busan"
    assert policy.benefit_amount == 50000
    assert policy.external_source_record_id == rows[0].id
    assert policy.source_category == "local_half_trip"
    assert policy.verification_status == "fresh"
    assert policy.structured_detail is not None
    assert policy.structured_detail["supportContent"][0]["description"] == "Up to 50,000 KRW"
    assert any(
        "반값여행 참여 혜택" in item["description"]
        for item in policy.structured_detail["applicationTarget"]
    )
    assert any("영수증" in item["description"] for item in policy.structured_detail["requiredDocuments"])
    assert any("공식 혜택 안내" in item["description"] for item in policy.structured_detail["notes"])
    assert "links" not in policy.structured_detail

    api_payload = policy_to_api(policy)
    assert api_payload["sourceType"] == "external"
    assert any("반값여행 참여 혜택" in item for item in api_payload["requirements"])


def test_local_half_trip_five_manifest_backfill_preserves_identity_and_hides_unverified(
    db: Session,
) -> None:
    db.add_all(
        [
            make_external_source_record(id=20, external_id="tour50-20", canonical_key="tour50-20"),
            make_external_source_record(
                id=32,
                external_id="tour50-32",
                canonical_key="tour50-32",
                city="고창",
                region="전북",
                status_text="마감",
            ),
        ]
    )
    existing_public = Policy(
        id=920,
        slug="travelmonth-20",
        title="legacy public half trip",
        organization="legacy",
        policy_type="지역할인",
        description="legacy",
        benefit_detail="legacy",
        target_condition="방문 인증사진 및 영수증",
        structured_detail={"conditions": [{"title": "조건", "description": "방문 인증사진 및 영수증"}]},
        region="경남",
        source_category="local_half_trip",
        external_source_record_id=20,
    )
    existing_unverified = Policy(
        id=932,
        slug="travelmonth-32",
        title="legacy unverified half trip",
        organization="legacy",
        policy_type="지역할인",
        description="legacy",
        benefit_detail="legacy",
        target_condition="결제내역과 숙박이용확인서",
        structured_detail={"conditions": [{"title": "조건", "description": "결제내역과 숙박이용확인서"}]},
        region="전북",
        source_category="local_half_trip",
        external_source_record_id=32,
    )
    frozen_dgtour = Policy(
        id=904,
        slug="dgtour-거창-4",
        title="거창 legacy dgtour",
        organization="legacy",
        policy_type="지역할인",
        description="legacy",
        benefit_detail="legacy",
        target_condition="legacy target",
        region="경남",
        status="active",
        verification_status="verified",
    )
    db.add_all([existing_public, existing_unverified, frozen_dgtour])
    db.flush()

    from app.services.policy_normalization import promote_external_benefits_to_policies
    from app.services.policies import policy_to_api

    promote_external_benefits_to_policies(db)

    public_policy = get_policy_by_slug(db, "travelmonth-20")
    hidden_policy = get_policy_by_slug_any_status(db, "travelmonth-32")
    legacy_policy = get_policy_by_slug(db, "dgtour-거창-4")
    assert public_policy is not None
    assert hidden_policy is not None
    assert legacy_policy is not None
    assert (public_policy.id, public_policy.slug, public_policy.external_source_record_id) == (
        920,
        "travelmonth-20",
        20,
    )
    assert public_policy.status == "active"
    assert public_policy.verification_status == "fresh"
    assert "영수증" not in public_policy.target_condition
    assert "인증사진" not in public_policy.target_condition
    public_payload = policy_to_api(public_policy)
    assert public_payload["requirements"] == [
        "거창을 여행하고 싶은 타지역 거주 관광객으로, 관내 당일 또는 숙박 관광 일정을 사전 신청하여 승인받은 사람.",
        "거창군, 김천시, 함양군, 산청군, 합천군, 무주군 거주자는 제외한다.",
    ]
    public_target_text = " ".join(
        item["description"] for item in public_payload["structuredDetail"]["applicationTarget"]
    )
    public_document_text = " ".join(
        item["description"] for item in public_payload["structuredDetail"]["requiredDocuments"]
    )
    assert "영수증" not in public_target_text
    assert "인증 사진" not in public_target_text
    assert "영수증" in public_document_text
    assert "인증 사진" in public_document_text

    assert (hidden_policy.id, hidden_policy.slug, hidden_policy.external_source_record_id) == (
        932,
        "travelmonth-32",
        32,
    )
    assert hidden_policy.status == "hidden"
    assert hidden_policy.verification_status == "needs_review"
    assert "결제내역" not in hidden_policy.target_condition
    assert "숙박이용확인서" not in hidden_policy.target_condition
    assert legacy_policy.status == "active"
    assert legacy_policy.target_condition == "legacy target"


def test_unknown_source_mapper_preserves_raw_evidence_but_fails_closed() -> None:
    composite = "할인혜택과 발급기간, 입실기간, 사용방법을 합친 긴 원문 상세"
    record = ExternalSourceRecord(
        id=999,
        source_name="미지원 지역 혜택",
        source_type="official_campaign",
        source_url="https://example.com/source",
        source_category="regional_benefit",
        external_id="future-unknown",
        canonical_key="future-unknown",
        detail_url="https://example.com/detail",
        collected_page_url="https://example.com/detail",
        title="미지원 지역 혜택",
        organizer_text="공식 주관기관",
        organizers=["공식 주관기관"],
        region="부산",
        is_nationwide=False,
        status="active",
        benefit_text="공식 혜택 원문",
        benefit_value_text=None,
        benefit_value_type="text",
        tags=[],
        contact_text=composite,
        inferred_travel_styles=[],
        confidence=90,
        field_completeness=90,
        raw_list_text="미지원 지역 혜택",
        raw_detail_text=composite,
        raw_payload={"untypedDetail": composite},
        last_fetched_at=datetime(2026, 5, 22, 9, 0, 0),
        freshness_status="fresh",
    )
    policy = Policy(region="전국", status="active")

    from app.services.policy_normalization import _assign_policy_from_external_record
    from app.services.policies import policy_to_api

    _assign_policy_from_external_record(policy, record)

    assert record.contact_text == composite
    assert record.raw_detail_text == composite
    assert record.raw_payload == {"untypedDetail": composite}
    assert policy.target_condition is None
    assert policy.structured_detail == {
        "supportContent": [],
        "applicationTarget": [],
        "periods": [],
        "requiredDocuments": [],
        "notes": [],
    }
    payload = policy_to_api(policy)
    assert payload["structuredDetail"] is None
    assert payload["requirements"] == []


@pytest.mark.parametrize(
    ("source_category", "raw_payload", "expected_status"),
    [
        ("local_half_trip", {"notes": "지정관광지 방문"}, "mapped"),
        ("regional_benefit", {"untypedDetail": "민감 원문"}, "missing"),
        ("stay_discount", {"discountTiers": ["해석할 수 없는 혜택"]}, "invalid"),
    ],
)
def test_semantic_mapping_log_is_private_and_safe(
    caplog: pytest.LogCaptureFixture,
    source_category: str,
    raw_payload: dict[str, object],
    expected_status: str,
) -> None:
    record = ExternalSourceRecord(
        id=999,
        source_name="비공개 원문 출처",
        source_type="official_campaign",
        source_category=source_category,
        external_id="private-external-id",
        canonical_key="private-canonical-key",
        detail_url="https://secret.example/private-path",
        title="정규화 로그 테스트",
        status="active",
        benefit_text="민감 원문 혜택",
        raw_detail_text="로그에 남으면 안 되는 민감 원문",
        raw_payload=raw_payload,
        freshness_status="fresh",
    )
    policy = Policy(region="전국", status="active")

    from app.services.policy_normalization import _assign_policy_from_external_record

    with caplog.at_level(logging.INFO, logger="app.services.policy_normalization"):
        _assign_policy_from_external_record(policy, record)

    event = next(item for item in caplog.records if item.message == "policy_semantic_mapping")
    assert event.source_category == source_category
    assert event.mapper_status == expected_status
    assert len(event.record_identity_hash) == 16
    assert set(event.section_counts) == {
        "supportContent",
        "applicationTarget",
        "periods",
        "requiredDocuments",
        "notes",
    }
    rendered = caplog.text
    assert "민감 원문" not in rendered
    assert "secret.example" not in rendered
    assert "private-external-id" not in rendered
    assert "private-canonical-key" not in rendered



def test_promotion_uses_safe_representative_deadline_and_preserves_typed_periods(
    db: Session,
) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                title="Typed period half trip",
                canonical_key="typed-period-half-trip",
                external_id="typed-period-half-trip",
                start_date=None,
                end_date=None,
                raw_payload={
                    "applicationPeriod": "2026.06.10 ~ 2026.08.31",
                    "tripPeriod": "2026.06.10 ~ 2026.12.31",
                },
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies
    from app.services.policies import policy_to_api

    promote_external_benefits_to_policies(db)

    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert policy is not None
    assert policy.end_date.isoformat() == "2026-08-31"
    api_policy = policy_to_api(policy)
    assert api_policy["deadline"] == "2026-08-31"
    assert api_policy["structuredDetail"]["periods"] == [
        {
            "title": "신청 기간",
            "description": "신청 기간: 2026.06.10 ~ 2026.08.31",
            "type": "application",
            "startDate": "2026-06-10",
            "endDate": "2026-08-31",
        },
        {
            "title": "여행 기간",
            "description": "여행 기간: 2026.06.10 ~ 2026.12.31",
            "type": "usage",
            "startDate": "2026-06-10",
            "endDate": "2026-12-31",
        },
    ]


def test_promotion_leaves_unsafe_representative_deadline_empty(
    db: Session,
) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                title="Unsafe default-like half trip",
                canonical_key="unsafe-default-like-half-trip",
                external_id="unsafe-default-like-half-trip",
                start_date=None,
                end_date=date(2026, 12, 31),
                raw_payload={"periodText": "12.31까지"},
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies
    from app.services.policies import policy_to_api

    promote_external_benefits_to_policies(db)

    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert policy is not None
    assert policy.start_date is None
    assert policy.end_date is None
    api_policy = policy_to_api(policy)
    assert api_policy["deadline"] == ""
    assert api_policy["structuredDetail"]["periods"] == [
        {
            "title": "기간",
            "description": "12.31까지",
            "type": "unknown",
            "endDate": "2026-12-31",
        }
    ]

def test_promotes_scheduled_local_half_trip_to_public_policy(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                title="밀양 대한민국 반값여행 지원",
                region="경남",
                city="밀양",
                canonical_key="miryang-scheduled",
                external_id="miryang-scheduled",
                status="scheduled",
                status_text="준비중",
                freshness_status="unknown",
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies

    result = promote_external_benefits_to_policies(db)

    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert result.promoted_count == 1
    assert policy is not None
    assert policy.status == "active"
    assert policy.title == "밀양 대한민국 반값여행 지원"
    assert policy.source_category == "local_half_trip"
    assert policy.verification_status == "unknown"


def test_promotion_is_idempotent_by_external_source_record_id(db: Session) -> None:
    rows = upsert_external_source_records(db, [make_source(canonical_key="stable")])

    from app.services.policy_normalization import promote_external_benefits_to_policies

    first = promote_external_benefits_to_policies(db)
    second = promote_external_benefits_to_policies(db)

    assert first.promoted_count == 1
    assert second.promoted_count == 1
    assert len(db.query(Policy).filter(Policy.external_source_record_id == rows[0].id).all()) == 1


def test_post_0027_stay_promotion_hides_canonical_survivor_and_hidden_snapshot(
    db: Session,
) -> None:
    legacy_record, current_record = upsert_external_source_records(
        db,
        [
            make_source(
                source_name="대한민국 숙박세일 페스타",
                source_category="stay_discount",
                canonical_key="legacy-snapshot",
                logical_key="stay-discount:2026-summer",
                canonical_key_version="snapshot-v1",
                end_date=date(2026, 7, 31),
            ),
            make_source(
                source_name="대한민국 숙박세일 페스타",
                source_category="stay_discount",
                canonical_key="current-snapshot",
                logical_key="stay-discount:2026-summer",
                canonical_key_version="snapshot-v1",
                title="Current stay campaign",
                end_date=date(2026, 8, 31),
            ),
        ],
    )
    survivor = Policy(
        id=23,
        slug="travelmonth-33",
        title="Current stay campaign",
        region="전국",
        status="active",
        source_category="stay_discount",
        external_source_record_id=current_record.id,
    )
    retired = Policy(
        id=26,
        slug="travelmonth-35",
        title="Current stay campaign",
        region="전국",
        status="hidden",
        source_category="stay_discount",
        external_source_record_id=None,
    )
    db.add_all([survivor, retired])
    db.flush()

    from app.services.policy_normalization import promote_external_benefits_to_policies

    promote_external_benefits_to_policies(db)
    promote_external_benefits_to_policies(db)

    assert survivor.slug == "travelmonth-33"
    assert survivor.external_source_record_id == current_record.id
    assert survivor.title == "Current stay campaign"
    assert survivor.status == "hidden"
    assert retired.slug == "travelmonth-35"
    assert retired.external_source_record_id is None
    assert retired.status == "hidden"
    assert legacy_record.id != current_record.id


def test_post_0028_single_snapshot_updates_existing_stay_canonical_as_hidden(
    db: Session,
) -> None:
    legacy_record, current_record = upsert_external_source_records(
        db,
        [
            make_source(
                source_name="대한민국 숙박세일 페스타",
                source_category="stay_discount",
                canonical_key="legacy-snapshot",
                logical_key=STAY_DISCOUNT_CAMPAIGN_KEY,
                canonical_key_version="snapshot-v1",
                end_date=date(2026, 7, 31),
            ),
            make_source(
                source_name="대한민국 숙박세일 페스타",
                source_category="stay_discount",
                canonical_key="current-snapshot",
                logical_key=STAY_DISCOUNT_CAMPAIGN_KEY,
                canonical_key_version="snapshot-v1",
                title="Current stay campaign",
                end_date=date(2026, 8, 31),
            ),
        ],
    )
    user = User(id=1, email="stay-owner@example.com", nickname="stay-owner")
    trip = Trip(
        id=1,
        owner_id=1,
        title="Stay identity trip",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
    )
    survivor = Policy(
        id=23,
        slug=f"travelmonth-{legacy_record.id}",
        title="Legacy stay campaign",
        region="전국",
        status="active",
        source_category="stay_discount",
        external_source_record_id=legacy_record.id,
        source_canonical_key=legacy_record.canonical_key,
    )
    db.add_all([user, trip, survivor])
    db.flush()
    db.add_all(
        [
            TripPolicy(id=1, trip_id=1, policy_id=23),
            UserSavedPolicy(id=1, user_id=1, policy_id=23),
        ]
    )
    db.flush()

    from app.services.policy_normalization import promote_external_benefits_to_policies

    promote_external_benefits_to_policies(db)
    promote_external_benefits_to_policies(db)

    stay_policies = db.query(Policy).filter(Policy.source_category == "stay_discount").all()
    assert [(policy.id, policy.slug) for policy in stay_policies] == [
        (23, f"travelmonth-{legacy_record.id}")
    ]
    assert survivor.external_source_record_id == current_record.id
    assert survivor.source_canonical_key == current_record.canonical_key
    assert survivor.title == "Current stay campaign"
    assert survivor.status == "hidden"
    assert db.query(Policy).filter(Policy.slug == f"travelmonth-{current_record.id}").count() == 0
    assert db.query(TripPolicy).one().policy_id == 23
    assert db.query(UserSavedPolicy).one().policy_id == 23


def test_stay_selector_prefers_newer_missing_logical_key_snapshot() -> None:
    old_record = ExternalSourceRecord(
        id=33,
        source_category="stay_discount",
        canonical_key="old-stay-snapshot",
        logical_key=STAY_DISCOUNT_CAMPAIGN_KEY,
        end_date=date(2026, 8, 17),
        last_fetched_at=datetime(2026, 8, 6, 13, 29, 24),
        last_verified_at=datetime(2026, 8, 6, 13, 29, 24),
    )
    new_record = ExternalSourceRecord(
        id=139,
        source_category="stay_discount",
        canonical_key="new-stay-snapshot",
        logical_key=None,
        end_date=date(2026, 8, 31),
        last_fetched_at=datetime(2026, 8, 19, 9, 0, 0),
        last_verified_at=datetime(2026, 8, 19, 9, 0, 0),
    )

    assert select_current_stay_discount_record([old_record, new_record]) is new_record


def test_stay_logical_campaign_with_zero_policy_matches_creates_one_policy(
    db: Session,
) -> None:
    record = upsert_external_source_records(
        db,
        [
            make_source(
                source_name="대한민국 숙박세일 페스타",
                source_category="stay_discount",
                canonical_key="zero-match-current",
                logical_key=STAY_DISCOUNT_CAMPAIGN_KEY,
                canonical_key_version="snapshot-v1",
                end_date=date(2026, 8, 31),
            )
        ],
    )[0]

    from app.services.policy_normalization import promote_external_benefits_to_policies

    result = promote_external_benefits_to_policies(db)

    assert result.promoted_count == 1
    assert [
        (policy.slug, policy.external_source_record_id)
        for policy in db.query(Policy).filter_by(source_category="stay_discount")
    ] == [(f"travelmonth-{record.id}", record.id)]


def test_stay_logical_campaign_with_one_policy_match_reuses_policy_23(
    db: Session,
) -> None:
    legacy_record, current_record = upsert_external_source_records(
        db,
        [
            make_source(
                source_name="대한민국 숙박세일 페스타",
                source_category="stay_discount",
                canonical_key="one-match-legacy",
                logical_key=STAY_DISCOUNT_CAMPAIGN_KEY,
                canonical_key_version="snapshot-v1",
                end_date=date(2026, 8, 17),
            ),
            make_source(
                source_name="대한민국 숙박세일 페스타",
                source_category="stay_discount",
                canonical_key="one-match-current",
                logical_key=STAY_DISCOUNT_CAMPAIGN_KEY,
                canonical_key_version="snapshot-v1",
                title="Current one-match stay campaign",
                end_date=date(2026, 8, 31),
            ),
        ],
    )
    survivor = Policy(
        id=23,
        slug=f"travelmonth-{legacy_record.id}",
        title="Legacy one-match stay campaign",
        region="전국",
        status="active",
        source_category="stay_discount",
        external_source_record_id=legacy_record.id,
        source_canonical_key=legacy_record.canonical_key,
    )
    db.add(survivor)
    db.flush()

    from app.services.policy_normalization import promote_external_benefits_to_policies

    promote_external_benefits_to_policies(db)

    assert [(policy.id, policy.slug) for policy in db.query(Policy)] == [
        (23, f"travelmonth-{legacy_record.id}")
    ]
    assert survivor.external_source_record_id == current_record.id
    assert survivor.title == "Current one-match stay campaign"


def test_stay_logical_campaign_with_multiple_policy_matches_fails_before_mutation(
    db: Session,
) -> None:
    first_legacy, second_legacy, current_record = upsert_external_source_records(
        db,
        [
            make_source(
                source_name="대한민국 숙박세일 페스타",
                source_category="stay_discount",
                canonical_key="multiple-match-legacy-a",
                logical_key=STAY_DISCOUNT_CAMPAIGN_KEY,
                canonical_key_version="snapshot-v1",
                end_date=date(2026, 7, 31),
            ),
            make_source(
                source_name="대한민국 숙박세일 페스타",
                source_category="stay_discount",
                canonical_key="multiple-match-legacy-b",
                logical_key=STAY_DISCOUNT_CAMPAIGN_KEY,
                canonical_key_version="snapshot-v1",
                end_date=date(2026, 8, 17),
            ),
            make_source(
                source_name="대한민국 숙박세일 페스타",
                source_category="stay_discount",
                canonical_key="multiple-match-current",
                logical_key=STAY_DISCOUNT_CAMPAIGN_KEY,
                canonical_key_version="snapshot-v1",
                title="Current multiple-match stay campaign",
                end_date=date(2026, 8, 31),
            ),
        ],
    )
    user = User(id=1, email="multiple-match@example.com", nickname="multiple-match")
    trip = Trip(
        id=1,
        owner_id=1,
        title="Multiple-match invariant trip",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
    )
    first_policy = Policy(
        id=23,
        slug=f"travelmonth-{first_legacy.id}",
        title="First legacy stay campaign",
        region="전국",
        status="active",
        source_category="stay_discount",
        external_source_record_id=first_legacy.id,
        source_canonical_key=first_legacy.canonical_key,
    )
    second_policy = Policy(
        id=26,
        slug=f"travelmonth-{second_legacy.id}",
        title="Second legacy stay campaign",
        region="전국",
        status="active",
        source_category="stay_discount",
        external_source_record_id=second_legacy.id,
        source_canonical_key=second_legacy.canonical_key,
    )
    db.add_all([user, trip, first_policy, second_policy])
    db.flush()
    db.add_all(
        [
            TripPolicy(id=1, trip_id=1, policy_id=23),
            UserSavedPolicy(id=1, user_id=1, policy_id=23),
        ]
    )
    db.commit()

    before = _policy_identity_state(db)

    from app.services.policy_normalization import (
        PolicyNormalizationError,
        promote_external_benefits_to_policies,
    )

    with pytest.raises(
        PolicyNormalizationError,
        match="multiple active policies match stay logical campaign",
    ):
        promote_external_benefits_to_policies(db)
    assert _policy_identity_state(db) == before
    db.rollback()

    after = _policy_identity_state(db)
    assert after == before
    assert first_policy.id == 23
    assert current_record.id not in {policy[3] for policy in after["policies"]}


def test_stay_duplicate_is_prevalidated_before_earlier_local_policy_mutation(
    db: Session,
) -> None:
    local_record, first_legacy, second_legacy, current_record = (
        upsert_external_source_records(
            db,
            [
                make_source(
                    title="Earlier local half-trip benefit",
                    canonical_key="earlier-local-half-trip",
                    external_id="earlier-local-half-trip",
                ),
                make_source(
                    source_name="대한민국 숙박세일 페스타",
                    source_category="stay_discount",
                    canonical_key="prevalidation-legacy-a",
                    logical_key=STAY_DISCOUNT_CAMPAIGN_KEY,
                    canonical_key_version="snapshot-v1",
                    end_date=date(2026, 7, 31),
                ),
                make_source(
                    source_name="대한민국 숙박세일 페스타",
                    source_category="stay_discount",
                    canonical_key="prevalidation-legacy-b",
                    logical_key=STAY_DISCOUNT_CAMPAIGN_KEY,
                    canonical_key_version="snapshot-v1",
                    end_date=date(2026, 8, 17),
                ),
                make_source(
                    source_name="대한민국 숙박세일 페스타",
                    source_category="stay_discount",
                    canonical_key="prevalidation-current",
                    logical_key=STAY_DISCOUNT_CAMPAIGN_KEY,
                    canonical_key_version="snapshot-v1",
                    title="Current prevalidation stay campaign",
                    end_date=date(2026, 8, 31),
                ),
            ],
        )
    )
    user = User(id=1, email="prevalidation@example.com", nickname="prevalidation")
    trip = Trip(
        id=1,
        owner_id=1,
        title="Prevalidation invariant trip",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 2),
    )
    first_policy = Policy(
        id=23,
        slug=f"travelmonth-{first_legacy.id}",
        title="First prevalidation stay campaign",
        region="전국",
        status="active",
        source_category="stay_discount",
        external_source_record_id=first_legacy.id,
        source_canonical_key=first_legacy.canonical_key,
    )
    second_policy = Policy(
        id=26,
        slug=f"travelmonth-{second_legacy.id}",
        title="Second prevalidation stay campaign",
        region="전국",
        status="active",
        source_category="stay_discount",
        external_source_record_id=second_legacy.id,
        source_canonical_key=second_legacy.canonical_key,
    )
    db.add_all([user, trip, first_policy, second_policy])
    db.flush()
    db.add_all(
        [
            TripPolicy(id=1, trip_id=1, policy_id=23),
            UserSavedPolicy(id=1, user_id=1, policy_id=23),
        ]
    )
    db.commit()
    before = _policy_identity_state(db)

    from app.services.policy_normalization import (
        PolicyNormalizationError,
        promote_external_benefits_to_policies,
    )

    with pytest.raises(
        PolicyNormalizationError,
        match="multiple active policies match stay logical campaign",
    ):
        promote_external_benefits_to_policies(db)

    assert not db.new
    assert _policy_identity_state(db) == before
    db.rollback()
    assert _policy_identity_state(db) == before
    assert local_record.id < current_record.id


def test_local_half_trip_uses_usage_condition_instead_of_contact_phone(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                title="합천 대한민국 반값여행 지원",
                region="경남",
                city="합천",
                canonical_key="hapcheon-half-trip",
                external_id="hapcheon-half-trip",
                contact_text="1660-3067",
                raw_detail_text="문의전화 : 1660-3067 특이사항 : 지정관광지 2개소 방문 인증사진 및 제로페이 가맹점 2개소 결제내역",
                raw_payload={
                    "contact": "1660-3067",
                    "field_values": {
                        "문의전화": "1660-3067",
                        "지역화폐": "제로페이 앱",
                        "특이사항": "지정관광지 2개소 방문 인증사진 및 제로페이 가맹점 2개소 결제내역",
                    },
                },
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies

    promote_external_benefits_to_policies(db)

    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert policy is not None
    assert policy.target_condition == "지정관광지 2개소 방문 인증사진 및 제로페이 가맹점 2개소 결제내역"


def test_local_half_trip_builds_semantic_structured_detail_for_gangjin(
    db: Session,
) -> None:
    combined_detail = (
        "강진군 관광지 2개소 이상 방문, 모바일 강진사랑상품권(Chak)으로 결제한 "
        "거래내역(영수증) *홈페이지 공지사항(고시공고) 필독"
    )
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                title="[강진] 대한민국 반값여행 지원",
                region="전남",
                city="강진",
                canonical_key="gangjin-half-trip",
                external_id="gangjin-half-trip",
                benefit_text="대한민국 반값여행 지원",
                benefit_value_text="여행비 50% 환급",
                contact_text="061-000-0000",
                raw_detail_text=f"문의전화 : 061-000-0000 특이사항 : {combined_detail}",
                raw_payload={
                    "field_values": {
                        "문의전화": "061-000-0000",
                        "특이사항": combined_detail,
                    },
                },
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies
    from app.services.policies import policy_to_api

    promote_external_benefits_to_policies(db)

    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert policy is not None
    assert policy.target_condition == combined_detail
    assert policy.structured_detail is not None
    application_targets = [item["description"] for item in policy.structured_detail["applicationTarget"]]
    support_items = [item["description"] for item in policy.structured_detail["supportContent"]]
    assert application_targets == [
        "강진 지역 반값여행 참여 혜택을 신청하고, 공식 안내의 사전 신청·승인·이용 조건을 충족한 여행자"
    ]
    assert "강진군 관광지 2개소 이상 방문" in support_items
    assert "모바일 강진사랑상품권(Chak)으로 결제" in support_items
    assert [item["description"] for item in policy.structured_detail["requiredDocuments"]][:1] == [
        "거래내역(영수증)",
    ]
    assert any("영수증" in item["description"] for item in policy.structured_detail["requiredDocuments"])
    assert [item["description"] for item in policy.structured_detail["notes"]][:1] == [
        "홈페이지 공지사항(고시공고) 필독",
    ]
    assert any("공식 혜택 안내" in item["description"] for item in policy.structured_detail["notes"])
    api_policy = policy_to_api(policy)
    assert api_policy["structuredDetail"]["applicationTarget"] == [
        {
            "title": "신청대상",
            "description": "강진 지역 반값여행 참여 혜택을 신청하고, 공식 안내의 사전 신청·승인·이용 조건을 충족한 여행자",
        }
    ]
    assert {"title": "혜택 적용 조건", "description": "강진군 관광지 2개소 이상 방문"} in api_policy["structuredDetail"]["supportContent"]
    assert {"title": "혜택 적용 조건", "description": "모바일 강진사랑상품권(Chak)으로 결제"} in api_policy["structuredDetail"]["supportContent"]
    assert api_policy["structuredDetail"]["requiredDocuments"][0] == {
        "title": "필요 서류", "description": "거래내역(영수증)"
    }
    assert any(
        item["title"] == "필요서류" and "지자체별 요구 증빙" in item["description"]
        for item in api_policy["structuredDetail"]["requiredDocuments"]
    )
    assert api_policy["structuredDetail"]["notes"][0] == {
        "title": "비고", "description": "홈페이지 공지사항(고시공고) 필독"
    }
    assert any("공식 혜택 안내" in item["description"] for item in api_policy["structuredDetail"]["notes"])
    assert "거래내역(영수증)" not in [
        item["description"] for item in api_policy["structuredDetail"]["applicationTarget"]
    ]
    assert "홈페이지 공지사항(고시공고) 필독" not in [
        item["description"] for item in api_policy["structuredDetail"]["requiredDocuments"]
    ]


def test_local_half_trip_structured_detail_uses_source_record_fields_without_duplicates(
    db: Session,
) -> None:
    notes = "강진군 관광지 2개소 이상 방문"
    local_currency = "chak 앱(모바일 강진사랑상품권)"
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                title="[강진] 대한민국 반값여행 지원",
                region="전남",
                city="강진",
                canonical_key="gangjin-half-trip-fields",
                external_id="gangjin-half-trip-fields",
                benefit_text="대한민국 반값여행 지원",
                benefit_value_text="여행비 50% 환급",
                contact_text="061-000-0000",
                raw_detail_text=(
                    "문의전화 : 061-000-0000 특이사항 : 강진군 관광지 2개소 이상 방문 "
                    "지역화폐 : chak 앱(모바일 강진사랑상품권)"
                ),
                raw_payload={
                    "applicationPeriod": "2026.06.10-2026.08.31",
                    "tripPeriod": "6.10~8.31",
                    "localCurrency": local_currency,
                    "notes": notes,
                    "field_values": {
                        "문의전화": "061-000-0000",
                        "특이사항": notes,
                        "지역화폐": local_currency,
                    },
                },
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies
    from app.services.policies import policy_to_api

    promote_external_benefits_to_policies(db)

    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert policy is not None
    api_policy = policy_to_api(policy)
    structured_detail = api_policy["structuredDetail"]
    assert [item["description"] for item in structured_detail["applicationTarget"]] == [
        "강진 지역 반값여행 참여 혜택을 신청하고, 공식 안내의 사전 신청·승인·이용 조건을 충족한 여행자"
    ]
    support_descriptions = [item["description"] for item in structured_detail["supportContent"]]
    assert notes in support_descriptions
    assert "chak 앱(모바일 강진사랑상품권) 사용" in support_descriptions
    assert [item["description"] for item in structured_detail["periods"]] == [
        "신청 기간: 2026.06.10-2026.08.31",
        "여행 기간: 6.10~8.31",
    ]
    assert any("지자체별 요구 증빙" in item["description"] for item in structured_detail["requiredDocuments"])
    assert any("공식 혜택 안내" in item["description"] for item in structured_detail["notes"])


def test_local_half_trip_replaces_existing_phone_target_condition_on_backfill(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                title="합천 대한민국 반값여행 지원",
                region="경남",
                city="합천",
                canonical_key="hapcheon-existing-phone",
                external_id="hapcheon-existing-phone",
                contact_text="1660-3067",
                raw_detail_text="문의전화 : 1660-3067 특이사항 : 제로페이 가맹점 결제내역",
                raw_payload={
                    "field_values": {
                        "문의전화": "1660-3067",
                        "특이사항": "제로페이 가맹점 결제내역",
                    },
                },
            )
        ],
    )
    existing = Policy(
        slug=f"travelmonth-{rows[0].id}",
        title="합천 대한민국 반값여행 지원",
        organization="합천 지자체",
        policy_type="지역할인",
        description="legacy",
        benefit_detail="최대 20만원 환급",
        target_condition="1660-3067",
        region="경남",
        source_category="local_half_trip",
        external_source_record_id=rows[0].id,
    )
    db.add(existing)
    db.flush()

    from app.services.policy_normalization import promote_external_benefits_to_policies

    promote_external_benefits_to_policies(db)

    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert policy is not None
    assert policy.target_condition == "제로페이 가맹점 결제내역"


def test_local_half_trip_extracts_condition_from_raw_detail_without_contact_phone(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                title="합천 대한민국 반값여행 지원",
                region="경남",
                city="합천",
                canonical_key="hapcheon-raw-detail-only",
                external_id="hapcheon-raw-detail-only",
                contact_text="1660-3067",
                raw_detail_text="문의전화 : 1660-3067 특이사항 : 지정관광지 2개소 방문 인증사진 및 제로페이 가맹점 2개소 결제내역",
                raw_payload={"contact": "1660-3067"},
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies

    promote_external_benefits_to_policies(db)

    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert policy is not None
    assert policy.target_condition == "지정관광지 2개소 방문 인증사진 및 제로페이 가맹점 2개소 결제내역"
    assert "1660-3067" not in policy.target_condition


def test_local_half_trip_does_not_use_mixed_unlabeled_raw_detail_with_phone(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                title="비라벨 문의 혼합 반값여행",
                canonical_key="mixed-unlabeled-phone",
                external_id="mixed-unlabeled-phone",
                contact_text="1660-3067",
                raw_detail_text="1660-3067로 문의 후 지정관광지 방문 인증사진과 제로페이 결제내역을 준비",
                raw_payload={},
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies
    from app.services.policies import policy_to_api

    promote_external_benefits_to_policies(db)

    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert policy is not None
    assert policy.target_condition is None
    assert policy.structured_detail is not None
    assert any(
        "반값여행 참여 혜택" in item["description"]
        for item in policy.structured_detail["applicationTarget"]
    )
    assert any("반값여행 참여 혜택" in item for item in policy_to_api(policy)["requirements"])


def test_local_half_trip_uses_default_condition_when_only_contact_exists(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                title="문의만 있는 반값여행",
                canonical_key="contact-only-half-trip",
                external_id="contact-only-half-trip",
                contact_text="1660-3067",
                raw_detail_text="문의전화 : 1660-3067",
                raw_payload={"field_values": {"문의전화": "1660-3067"}},
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies
    from app.services.policies import policy_to_api

    promote_external_benefits_to_policies(db)

    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert policy is not None
    assert policy.target_condition is None
    assert policy.structured_detail is not None
    assert any(
        "반값여행 참여 혜택" in item["description"]
        for item in policy.structured_detail["applicationTarget"]
    )
    assert any("반값여행 참여 혜택" in item for item in policy_to_api(policy)["requirements"])


def test_promotion_reclassifies_existing_policy_type(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                canonical_key="namdo-train",
                title="남도 기차둘레길 1박 2일 최대 35% 할인행사",
                benefit_text="남도 기차 여행상품 최대 35% 할인",
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies

    result = promote_external_benefits_to_policies(db)
    policy = db.query(Policy).filter(Policy.external_source_record_id == rows[0].id).one()
    policy.policy_type = "지역할인"
    db.flush()

    second = promote_external_benefits_to_policies(db)

    assert result.promoted_count == 1
    assert second.promoted_count == 1
    assert policy.policy_type == "여행상품"


def test_promotion_derives_missing_percent_value_from_title(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                canonical_key="welchon-percent-title",
                external_id="welchon-percent-title",
                title="웰촌 체험상품 30% 할인",
                benefit_text="행사 기간 중 온라인 체험상품 예약 결제 후 사용 완료 참여자 26년 4월 중순부터 5월 말",
                benefit_value_text=None,
                extracted_amount_krw=None,
                extracted_discount_percent=None,
                benefit_value_type="unknown",
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies

    promote_external_benefits_to_policies(db)

    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert policy is not None
    assert policy.benefit_detail == "최대 30%"
    assert policy.benefit_amount is None
    assert policy.policy_comment == "행사 기간 중 온라인 체험상품 예약 결제 후 사용 완료 참여자 26년 4월 중순부터 5월 말"


def test_promotes_active_fresh_stay_discount_as_area_policy_rows(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                source_name="대한민국 숙박세일 페스타",
                source_url="https://korean.visitkorea.or.kr/travelmonth/benefits/stay.do",
                collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/stay.do",
                source_category="stay_discount",
                canonical_key="stay-discount",
                logical_key=STAY_DISCOUNT_CAMPAIGN_KEY,
                external_id="stay-discount",
                title="2026 대한민국 숙박세일 페스타 숙박 할인",
                region="비수도권·인구감소지역",
                benefit_text="숙박상품 2/3/5/7만원 할인권",
                benefit_value_text="2/3/5/7만원 할인권",
                extracted_amount_krw=70000,
                raw_payload={
                    "eligibleAreas": [
                        {"sido": "전남", "cities": ["강진군", "순천시"]},
                    ],
                    "eligibleAreaCount": 2,
                },
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies

    promote_external_benefits_to_policies(db)

    canonical = get_policy_by_slug_any_status(db, f"travelmonth-{rows[0].id}")
    gangjin = get_policy_by_slug_any_status(db, "stay-discount-jeonnam-gangjin")
    suncheon = get_policy_by_slug_any_status(db, "stay-discount-jeonnam-suncheon")
    assert canonical is not None
    assert canonical.status == "hidden"
    assert gangjin is not None
    assert gangjin.status == "active"
    assert gangjin.external_source_record_id == rows[0].id
    assert gangjin.slug == "stay-discount-jeonnam-gangjin"
    assert gangjin.title == "[강진] 2026 대한민국 숙박세일 페스타 숙박 할인"
    assert gangjin.region == "전남"
    assert gangjin.policy_type == "숙박"
    assert gangjin.benefit_amount == 70000
    assert gangjin.source_canonical_key == "stay-discount:stay-discount-jeonnam-gangjin"
    assert suncheon is not None
    assert suncheon.status == "active"


def test_skips_inactive_or_stale_records(db: Session) -> None:
    upsert_external_source_records(
        db,
        [
            make_source(canonical_key="inactive", status="ended"),
            make_source(canonical_key="stale", freshness_status="stale"),
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies

    result = promote_external_benefits_to_policies(db)

    assert result.promoted_count == 0
    assert db.query(Policy).count() == 0


def test_upsert_accepts_non_regional_external_source(db: Session) -> None:
    source = ExternalBenefitSource(
        source_name="여행가는 달",
        source_type="official_campaign",
        source_url="https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do",
        source_category="traffic_benefit",
        external_id="traffic-rail-1",
        canonical_key="traffic-rail-1",
        detail_url="https://www.korail.com",
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do",
        title="TravelMonth rail discount",
        organizer_text="Korail",
        organizers=["Korail"],
        region="Nationwide",
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
        tags=["traffic", "rail"],
        contact_text="Korail customer center",
        inferred_travel_styles=[],
        confidence=90,
        field_completeness=90,
        raw_list_text="Theme train fare 50% discount",
        raw_detail_text="Theme train fare 50% discount",
        raw_payload={"source": "traffic"},
        last_fetched_at="2026-05-23T09:00:00",
        last_verified_at="2026-05-23T09:00:00",
        freshness_status="fresh",
    )

    rows = upsert_external_source_records(db, [source])

    assert len(rows) == 1
    assert rows[0].source_category == "traffic_benefit"
    assert rows[0].benefit_value_type == "percent"


def test_promotes_half_trip_but_keeps_traffic_benefit_legacy_only(db: Session) -> None:
    traffic = make_source(
        canonical_key="traffic",
        external_id="traffic",
        title="Theme train discount",
        source_url="https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do",
        source_category="traffic_benefit",
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do",
        detail_url=None,
        region="전국",
        benefit_text="Theme train fare 50% discount",
        benefit_value_text="50% discount",
        extracted_amount_krw=None,
        extracted_discount_percent=50,
        benefit_value_type="percent",
    )
    half_trip = make_source(
        canonical_key="hapcheon-half-trip",
        external_id="hapcheon-half-trip",
        title="Hapcheon half trip support",
        source_name="대한민국 반값여행",
        source_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        source_category="local_half_trip",
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        region="경남",
        city="합천",
        benefit_text="Travel expense 50% refund",
        benefit_value_text="Up to 200,000 KRW refund",
        extracted_amount_krw=200000,
    )
    upsert_external_source_records(db, [traffic, half_trip])

    from app.services.policy_normalization import promote_external_benefits_to_policies

    result = promote_external_benefits_to_policies(db)

    policies = db.query(Policy).order_by(Policy.id).all()
    assert result.promoted_count == 1
    assert len(policies) == 1
    assert policies[0].policy_type == "지역할인"
    assert policies[0].source_category == "local_half_trip"
    assert policies[0].official_url == half_trip.detail_url


def test_hides_legacy_regional_benefit_instead_of_promoting_duplicate_policy(
    db: Session,
) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                canonical_key="legacy-regional",
                external_id="legacy-regional",
                title="여행가는 달 지역사랑 휴가지원 - 제천",
                source_category="regional_benefit",
                source_url="https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
                collected_page_url=(
                    "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do"
                ),
                detail_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
                region="충북",
                city="제천",
            )
        ],
    )
    legacy_policy = Policy(
        slug=f"travelmonth-{rows[0].id}",
        title="여행가는 달 지역사랑 휴가지원 - 제천",
        organization="한국관광공사",
        policy_type="지역할인",
        description="Legacy regional duplicate",
        benefit_detail="Legacy regional duplicate",
        target_condition="Legacy regional duplicate",
        region="충북",
        status="active",
        source_category="regional_benefit",
        external_source_record_id=rows[0].id,
    )
    db.add(legacy_policy)
    db.flush()

    from app.services.policy_normalization import promote_external_benefits_to_policies

    result = promote_external_benefits_to_policies(db)

    assert result.promoted_count == 0
    assert legacy_policy.status == "hidden"
    assert db.query(Policy).filter(Policy.external_source_record_id == rows[0].id).count() == 1


def test_hides_promoted_local_half_trip_when_source_becomes_ended_or_unknown(
    db: Session,
) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                canonical_key="half-trip-ended",
                external_id="half-trip-ended",
                source_category="local_half_trip",
            ),
            make_source(
                canonical_key="half-trip-unknown",
                external_id="half-trip-unknown",
                source_category="local_half_trip",
            ),
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies

    promote_external_benefits_to_policies(db)
    rows[0].status = "ended"
    rows[1].status = "unknown"

    result = promote_external_benefits_to_policies(db)

    policies = (
        db.query(Policy)
        .filter(Policy.external_source_record_id.in_([row.id for row in rows]))
        .order_by(Policy.external_source_record_id)
        .all()
    )
    assert result.promoted_count == 0
    assert [policy.status for policy in policies] == ["hidden", "hidden"]
    assert [policy.verification_status for policy in policies] == ["fresh", "fresh"]


def test_reactivates_hidden_policy_when_source_returns_active_fresh(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                canonical_key="half-trip-reactivate",
                external_id="half-trip-reactivate",
                source_category="local_half_trip",
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies

    promote_external_benefits_to_policies(db)
    policy = db.query(Policy).filter(Policy.external_source_record_id == rows[0].id).one()
    rows[0].status = "ended"
    promote_external_benefits_to_policies(db)
    assert policy.status == "hidden"

    rows[0].status = "active"
    rows[0].freshness_status = "fresh"
    result = promote_external_benefits_to_policies(db)

    assert result.promoted_count == 1
    assert policy.status == "active"


def test_deactivation_hides_admin_override_without_overwriting_protected_fields(
    db: Session,
) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                canonical_key="admin-override-half-trip",
                external_id="admin-override-half-trip",
                source_category="local_half_trip",
                title="Source title",
            )
        ],
    )
    policy = Policy(
        slug=f"travelmonth-{rows[0].id}",
        title="Admin title",
        organization="Admin org",
        policy_type="etc",
        description="Admin description",
        benefit_detail="Admin benefit",
        target_condition="Admin target",
        region="Admin region",
        status="active",
        admin_override_enabled=True,
        external_source_record_id=rows[0].id,
    )
    db.add(policy)
    db.flush()
    rows[0].status = "ended"

    from app.services.policy_normalization import promote_external_benefits_to_policies

    promote_external_benefits_to_policies(db)

    assert policy.status == "hidden"
    assert policy.title == "Admin title"
    assert policy.organization == "Admin org"
    assert policy.source_category == "local_half_trip"
    assert policy.verification_status == "fresh"


def test_reactivates_admin_override_when_source_returns_active_fresh(
    db: Session,
) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                canonical_key="admin-override-reactivate",
                external_id="admin-override-reactivate",
                source_category="local_half_trip",
                title="Source title",
            )
        ],
    )
    policy = Policy(
        slug=f"travelmonth-{rows[0].id}",
        title="Admin title",
        organization="Admin org",
        policy_type="etc",
        description="Admin description",
        benefit_detail="Admin benefit",
        target_condition="Admin target",
        region="Admin region",
        status="hidden",
        admin_override_enabled=True,
        external_source_record_id=rows[0].id,
    )
    db.add(policy)
    db.flush()

    from app.services.policy_normalization import promote_external_benefits_to_policies

    result = promote_external_benefits_to_policies(db)

    assert result.promoted_count == 1
    assert policy.status == "active"
    assert policy.title == "Admin title"
    assert policy.organization == "Admin org"
    assert policy.source_category == "local_half_trip"


def test_promoting_local_half_trip_hides_legacy_dgtour_seed_policies(
    db: Session,
) -> None:
    upsert_external_source_records(
        db,
        [
            make_source(
                canonical_key="active-half-trip",
                external_id="active-half-trip",
                source_name="대한민국 반값여행",
                source_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
                source_category="local_half_trip",
                collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
                title="Hadong half trip support",
                region="Gyeongnam",
                city="Hadong",
            )
        ],
    )
    legacy_policy = Policy(
        slug="dgtour-hadong-3",
        title="Legacy dgtour policy",
        organization="KTO",
        policy_type="지역할인",
        description="Legacy",
        benefit_detail="Legacy",
        target_condition="Legacy",
        region="Gyeongnam",
        status="active",
    )
    db.add(legacy_policy)
    db.flush()

    from app.services.policy_normalization import promote_external_benefits_to_policies

    result = promote_external_benefits_to_policies(db)

    assert result.promoted_count == 1
    assert legacy_policy.status == "hidden"
    assert db.query(Policy).filter(Policy.slug.like("travelmonth-%")).one().status == "active"



def test_promoting_digital_tourism_prefers_hidden_canonical_slug_over_active_legacy_seed(
    db: Session,
) -> None:
    from app.services import digital_tourism_resident_card as dgtour
    from app.services import policies as policy_service
    from app.services.policy_normalization import promote_external_benefits_to_policies

    hidden_canonical = Policy(
        slug="dgtour-영광",
        title="[영광] 디지털관광주민증 혜택",
        organization="한국관광공사",
        policy_type="지역할인",
        description="hidden canonical",
        benefit_detail="지역 제휴 혜택",
        target_condition="디지털관광주민증 발급자",
        region="전남",
        status="hidden",
        source_category=dgtour.SOURCE_CATEGORY,
        source_canonical_key=dgtour.canonical_key_for_city("영광"),
    )
    active_legacy = Policy(
        slug="dgtour-영광-8",
        title="[영광] 디지털관광주민증 혜택",
        organization="한국관광공사",
        policy_type="지역할인",
        description="active legacy",
        benefit_detail="지역 제휴 혜택",
        target_condition="디지털관광주민증 발급자",
        region="전남",
        status="active",
        source_category=dgtour.SOURCE_CATEGORY,
        source_canonical_key=dgtour.canonical_key_for_city("영광"),
    )
    db.add_all([hidden_canonical, active_legacy])
    db.flush()
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                source_name=dgtour.SOURCE_NAME,
                source_url=dgtour.SOURCE_URL,
                source_category=dgtour.SOURCE_CATEGORY,
                external_id="digital-yeonggwang-canonical",
                canonical_key=dgtour.canonical_key_for_city("영광"),
                logical_key="digital-tourism-resident-card:2026:전남:영광",
                detail_url=dgtour.official_url_for_city("영광"),
                collected_page_url=dgtour.SOURCE_URL,
                title="[영광] 디지털관광주민증 혜택",
                organizer_text="영광 지자체 · 한국관광공사",
                organizers=["영광 지자체", "한국관광공사"],
                region="전남",
                city="영광",
                benefit_text=dgtour.DEFAULT_BENEFIT_TEXT,
                benefit_value_text=dgtour.DEFAULT_BENEFIT_VALUE_TEXT,
                extracted_amount_krw=None,
                extracted_discount_percent=None,
                benefit_value_type="mixed",
                raw_payload={
                    "partnerBenefits": [
                        {
                            "memberId": "yeonggwang-1",
                            "categoryName": "관광지",
                            "name": "영광 관광지",
                            "summary": "입장 할인",
                            "detail": "입장료 1,000원 할인",
                        }
                    ],
                    "partnerBenefitSummary": {
                        "totalCount": 1,
                        "categoryCounts": {"관광지": 1},
                        "displayLimit": 8,
                    },
                },
            )
        ],
    )

    promote_external_benefits_to_policies(db)
    db.flush()

    assert hidden_canonical.status == "active"
    assert hidden_canonical.slug == "dgtour-영광"
    assert hidden_canonical.external_source_record_id == rows[0].id
    assert active_legacy.status == "hidden"

    canonical_payload = policy_service.get_policy("dgtour-영광", db)
    legacy_payload = policy_service.get_policy("dgtour-영광-8", db)
    assert canonical_payload is not None
    assert legacy_payload is not None
    assert canonical_payload["slug"] == "dgtour-영광"
    assert legacy_payload["slug"] == "dgtour-영광"

def test_promoting_local_half_trip_does_not_hide_canonical_digital_tourism_policy(
    db: Session,
) -> None:
    from app.services import digital_tourism_resident_card as dgtour
    from app.services.policy_normalization import promote_external_benefits_to_policies

    rows = upsert_external_source_records(
        db,
        [
            make_source(
                canonical_key="active-half-trip-with-canonical-dgtour",
                external_id="active-half-trip-with-canonical-dgtour",
                source_category="local_half_trip",
            ),
            make_source(
                source_name=dgtour.SOURCE_NAME,
                source_url=dgtour.SOURCE_URL,
                source_category=dgtour.SOURCE_CATEGORY,
                external_id="digital-hadong-preserve",
                canonical_key=dgtour.canonical_key_for_city("하동"),
                logical_key="digital-tourism-resident-card:2026:경남:하동",
                title="[하동] 디지털관광주민증 혜택",
                region="경남",
                city="하동",
                benefit_text=dgtour.DEFAULT_BENEFIT_TEXT,
                benefit_value_text=dgtour.DEFAULT_BENEFIT_VALUE_TEXT,
                extracted_amount_krw=None,
                extracted_discount_percent=None,
                benefit_value_type="mixed",
                raw_payload={
                    "partnerBenefits": [
                        {
                            "memberId": "hadong-preserve-1",
                            "categoryName": "체험",
                            "name": "하동 체험",
                            "summary": "체험 할인",
                            "detail": "체험 2,000원 할인",
                        }
                    ]
                },
            ),
        ],
    )

    result = promote_external_benefits_to_policies(db)

    assert result.promoted_count == 2
    digital_policy = db.query(Policy).filter(Policy.external_source_record_id == rows[1].id).one()
    assert digital_policy.slug == "dgtour-하동"
    assert digital_policy.status == "active"


def test_frozen_reviewed_policy_is_excluded_from_normalizer_writers(db: Session) -> None:
    record = upsert_external_source_records(
        db,
        [
            make_source(
                canonical_key="frozen-hadong-source",
                external_id="frozen-hadong-source",
                title="Overwrite attempt",
                region="경남",
                city="하동",
            )
        ],
    )[0]
    policy = Policy(
        slug="dgtour-하동-3",
        title="Reviewed title",
        organization="Reviewed org",
        policy_type="지역할인",
        description="Reviewed description",
        benefit_detail="Reviewed benefit",
        target_condition="Reviewed condition",
        region="경남",
        status="hidden",
    )
    db.add(policy)
    db.flush()

    from app.services.policy_normalization import (
        _assign_policy_from_external_record,
        _hide_legacy_dgtour_seed_policies,
    )

    _assign_policy_from_external_record(policy, record)
    _hide_legacy_dgtour_seed_policies(db)

    assert policy.title == "Reviewed title"
    assert policy.status == "hidden"
    assert policy.external_source_record_id is None


def test_promoted_policy_is_exposed_by_list_and_detail_then_hidden_when_source_stales(
    db: Session,
) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                canonical_key="route-visible",
                external_id="route-visible",
                title="Route visible collected support",
                region="Busan",
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies

    promote_external_benefits_to_policies(db)
    slug = f"travelmonth-{rows[0].id}"
    app.dependency_overrides[policy_routes.get_optional_db] = lambda: db
    try:
        list_response = client.get("/api/policies")
        detail_response = client.get(f"/api/policies/{slug}")

        assert list_response.status_code == 200
        listed = {policy["slug"]: policy for policy in list_response.json()}
        assert listed[slug]["title"] == "Route visible collected support"
        assert listed[slug]["sourceType"] == "external"
        assert detail_response.status_code == 200
        assert detail_response.json()["slug"] == slug

        rows[0].freshness_status = "stale"
        promote_external_benefits_to_policies(db)

        stale_list_response = client.get("/api/policies")
        stale_detail_response = client.get(f"/api/policies/{slug}")
    finally:
        app.dependency_overrides.pop(policy_routes.get_optional_db, None)

    assert stale_list_response.status_code == 200
    assert slug not in {policy["slug"] for policy in stale_list_response.json()}
    assert stale_detail_response.status_code == 404


def test_digital_tourism_seed_matching_is_municipality_scoped(db: Session) -> None:
    from app.services.policy_normalization import promote_external_benefits_to_policies

    yeonggwang_seed = Policy(
        slug="dgtour-영광-8",
        title="[영광] 디지털관광주민증 혜택",
        organization="한국관광공사",
        policy_type="지역할인",
        description="영광 seed",
        benefit_detail="지역 제휴 혜택",
        target_condition="VisitKorea 디지털관광주민증 발급 및 제시",
        region="전남",
        status="active",
        source_category="digital_tourism_resident_card",
        source_canonical_key="digital-tourism-resident-card:전남:영광",
    )
    haenam_seed = Policy(
        slug="dgtour-해남-10",
        title="[해남] 디지털관광주민증 혜택",
        organization="한국관광공사",
        policy_type="지역할인",
        description="해남 seed",
        benefit_detail="지역 제휴 혜택",
        target_condition="VisitKorea 디지털관광주민증 발급 및 제시",
        region="전남",
        status="active",
        source_category="digital_tourism_resident_card",
        source_canonical_key="digital-tourism-resident-card:전남:해남",
    )
    db.add_all([yeonggwang_seed, haenam_seed])
    db.flush()

    rows = upsert_external_source_records(
        db,
        [
            make_source(
                source_name="디지털관광주민증",
                source_url="https://korean.visitkorea.or.kr/dgtourcard/",
                source_category="digital_tourism_resident_card",
                external_id="digital-yeonggwang",
                canonical_key="digital-tourism-resident-card:전남:영광",
                logical_key="digital-tourism-resident-card:2026:전남:영광",
                detail_url="https://korean.visitkorea.or.kr/dgtourcard/",
                collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/",
                title="[영광] 디지털관광주민증 혜택",
                organizer_text="영광 지자체 · 한국관광공사",
                organizers=["영광 지자체", "한국관광공사"],
                region="전남",
                city="영광",
                benefit_text="디지털관광주민증 지역 제휴 혜택",
                benefit_value_text="지역 제휴 혜택",
                extracted_amount_krw=None,
                extracted_discount_percent=None,
                benefit_value_type="mixed",
            )
        ],
    )

    result = promote_external_benefits_to_policies(db)

    assert result.promoted_count == 1
    assert yeonggwang_seed.external_source_record_id == rows[0].id
    assert haenam_seed.external_source_record_id is None
    assert yeonggwang_seed.status == "active"
    assert haenam_seed.status == "active"


def test_promoting_digital_tourism_uses_regional_visitkorea_url_not_half_trip(
    db: Session,
) -> None:
    from app.services import digital_tourism_resident_card as dgtour
    from app.services.policy_normalization import promote_external_benefits_to_policies

    seed = Policy(
        slug="dgtour-하동-3",
        title="[하동] 디지털관광주민증 혜택",
        organization="한국관광공사",
        policy_type="지역할인",
        description="polluted",
        benefit_detail="50% 환급",
        target_condition="대한민국 반값여행",
        region="경남",
        status="active",
        source_category=dgtour.SOURCE_CATEGORY,
        source_canonical_key=dgtour.canonical_key_for_city("하동"),
    )
    db.add(seed)
    db.flush()
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                source_name=dgtour.SOURCE_NAME,
                source_url=dgtour.SOURCE_URL,
                source_category=dgtour.SOURCE_CATEGORY,
                external_id="digital-hadong",
                canonical_key=dgtour.canonical_key_for_city("하동"),
                logical_key="digital-tourism-resident-card:2026:경남:하동",
                detail_url="https://hadongtrip.kr/index.php",
                collected_page_url=dgtour.SOURCE_URL,
                title="[하동] 디지털관광주민증 혜택",
                organizer_text="하동 지자체 · 한국관광공사",
                organizers=["하동 지자체", "한국관광공사"],
                region="경남",
                city="하동",
                benefit_text="대한민국 반값여행 최대 20만원 50% 환급",
                benefit_value_text="50% 환급",
                extracted_amount_krw=None,
                extracted_discount_percent=None,
                benefit_value_type="mixed",
                raw_detail_text="대한민국 반값여행 최대 20만원 50% 환급",
                raw_payload={"notes": "대한민국 반값여행 최대 20만원 50% 환급"},
            )
        ],
    )

    result = promote_external_benefits_to_policies(db)

    assert result.promoted_count == 1
    assert seed.external_source_record_id == rows[0].id
    assert seed.official_url == dgtour.HADONG_REGIONAL_URL
    assert seed.source_url == dgtour.HADONG_REGIONAL_URL
    assert seed.apply_url is None
    assert seed.benefit_detail == dgtour.DEFAULT_BENEFIT_VALUE_TEXT
    assert "반값여행" not in str(seed.structured_detail)
    assert "50% 환급" not in str(seed.structured_detail)


def test_promoting_digital_tourism_uses_stable_city_slug_and_old_slug_aliases(
    db: Session,
) -> None:
    from app.services import digital_tourism_resident_card as dgtour
    from app.services import policies as policy_service
    from app.services.policy_normalization import promote_external_benefits_to_policies

    seed = Policy(
        slug="travelmonth-999",
        title="[가평] 디지털관광주민증 혜택",
        organization="한국관광공사",
        policy_type="지역할인",
        description="seed",
        benefit_detail="지역 제휴 혜택",
        target_condition="디지털관광주민증 발급자",
        region="경기",
        status="active",
        source_category=dgtour.SOURCE_CATEGORY,
        source_canonical_key=dgtour.canonical_key_for_city("가평"),
    )
    db.add(seed)
    db.flush()
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                source_name=dgtour.SOURCE_NAME,
                source_url=dgtour.SOURCE_URL,
                source_category=dgtour.SOURCE_CATEGORY,
                external_id="digital-gapyeong",
                canonical_key=dgtour.canonical_key_for_city("가평"),
                logical_key="digital-tourism-resident-card:2026:경기:가평",
                detail_url=dgtour.official_url_for_city("가평"),
                collected_page_url=dgtour.SOURCE_URL,
                title="[가평] 디지털관광주민증 혜택",
                organizer_text="가평 지자체 · 한국관광공사",
                organizers=["가평 지자체", "한국관광공사"],
                region="경기",
                city="가평",
                benefit_text=dgtour.DEFAULT_BENEFIT_TEXT,
                benefit_value_text=dgtour.DEFAULT_BENEFIT_VALUE_TEXT,
                extracted_amount_krw=None,
                extracted_discount_percent=None,
                benefit_value_type="mixed",
                raw_payload={
                    "partnerBenefits": [
                        {
                            "memberId": "gapyeong-1",
                            "categoryName": "숙박",
                            "name": "가평 숙소",
                            "summary": "숙박 할인",
                            "detail": "숙박 10% 할인",
                        }
                    ],
                    "partnerBenefitSummary": {
                        "totalCount": 1,
                        "categoryCounts": {"숙박": 1},
                        "displayLimit": 8,
                    },
                },
            )
        ],
    )

    result = promote_external_benefits_to_policies(db)

    assert result.promoted_count == 1
    assert seed.external_source_record_id == rows[0].id
    assert seed.slug == "dgtour-가평"
    assert len(seed.structured_detail["supportContent"]) == 3

    canonical_payload = policy_service.get_policy("dgtour-가평", db)
    legacy_payload = policy_service.get_policy(f"travelmonth-{rows[0].id}", db)

    assert canonical_payload is not None
    assert legacy_payload is not None
    assert canonical_payload["slug"] == "dgtour-가평"
    assert legacy_payload["slug"] == "dgtour-가평"
    assert legacy_payload["structuredDetail"]["supportContent"][1]["title"] == "카테고리별 인기 혜택"
    assert legacy_payload["structuredDetail"]["supportContent"][2]["description"].startswith("🏨 가평 숙소")
    assert legacy_payload["structuredDetail"]["supportContent"][2]["url"].endswith("mbrbId=gapyeong-1")


def test_promoting_legacy_numbered_dgtour_slug_renames_to_city_slug_and_keeps_alias(
    db: Session,
) -> None:
    from app.services import digital_tourism_resident_card as dgtour
    from app.services import policies as policy_service
    from app.services.policy_normalization import promote_external_benefits_to_policies

    seed = Policy(
        slug="dgtour-하동-3",
        title="[하동] 디지털관광주민증 혜택",
        organization="한국관광공사",
        policy_type="지역할인",
        description="seed",
        benefit_detail="지역 제휴 혜택",
        target_condition="디지털관광주민증 발급자",
        region="경남",
        status="active",
        source_category=dgtour.SOURCE_CATEGORY,
        source_canonical_key=dgtour.canonical_key_for_city("하동"),
    )
    db.add(seed)
    db.flush()
    upsert_external_source_records(
        db,
        [
            make_source(
                source_name=dgtour.SOURCE_NAME,
                source_url=dgtour.SOURCE_URL,
                source_category=dgtour.SOURCE_CATEGORY,
                external_id="digital-hadong-canonical",
                canonical_key=dgtour.canonical_key_for_city("하동"),
                logical_key="digital-tourism-resident-card:2026:경남:하동",
                detail_url=dgtour.HADONG_REGIONAL_URL,
                collected_page_url=dgtour.SOURCE_URL,
                title="[하동] 디지털관광주민증 혜택",
                organizer_text="하동 지자체 · 한국관광공사",
                organizers=["하동 지자체", "한국관광공사"],
                region="경남",
                city="하동",
                benefit_text=dgtour.DEFAULT_BENEFIT_TEXT,
                benefit_value_text=dgtour.DEFAULT_BENEFIT_VALUE_TEXT,
                extracted_amount_krw=None,
                extracted_discount_percent=None,
                benefit_value_type="mixed",
                raw_payload={
                    "partnerBenefits": [
                        {
                            "memberId": "hadong-1",
                            "categoryName": "체험",
                            "name": "하동 체험",
                            "summary": "체험 할인",
                            "detail": "체험 2,000원 할인",
                        }
                    ],
                    "partnerBenefitSummary": {
                        "totalCount": 1,
                        "categoryCounts": {"체험": 1},
                        "displayLimit": 8,
                    },
                },
            )
        ],
    )

    promote_external_benefits_to_policies(db)

    assert seed.slug == "dgtour-하동"
    assert len(seed.structured_detail["supportContent"]) == 3
    old_slug_payload = policy_service.get_policy("dgtour-하동-3", db)
    assert old_slug_payload is not None
    assert old_slug_payload["slug"] == "dgtour-하동"
    assert old_slug_payload["structuredDetail"]["supportContent"][1]["title"] == "카테고리별 인기 혜택"
    assert old_slug_payload["structuredDetail"]["supportContent"][2]["description"].startswith("🎡 하동 체험")
    assert old_slug_payload["structuredDetail"]["supportContent"][2]["url"].endswith("mbrbId=hadong-1")
