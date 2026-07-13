from __future__ import annotations

import app.models  # noqa: F401
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Integer, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import policies as policy_routes
from app.db.base import Base
from app.main import app
from app.models import ExternalSourceRecord, Policy
from app.repositories.external_sources import upsert_external_source_records
from app.repositories.policies import get_policy_by_slug
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
    assert policy.structured_detail["benefits"][0]["description"] == "Up to 50,000 KRW"
    assert policy.structured_detail["conditions"][0]["description"] == "공식 혜택 안내에서 조건을 확인하세요."
    assert policy.structured_detail["links"][0]["url"] == "https://example.com/detail"

    assert policy_to_api(policy)["sourceType"] == "external"


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
    assert [item["description"] for item in policy.structured_detail["conditions"]] == [
        "강진군 관광지 2개소 이상 방문",
        "모바일 강진사랑상품권(Chak)으로 결제",
    ]
    assert [item["description"] for item in policy.structured_detail["documents"]] == [
        "거래내역(영수증)",
    ]
    assert [item["description"] for item in policy.structured_detail["notices"]] == [
        "홈페이지 공지사항(고시공고) 필독",
    ]
    api_policy = policy_to_api(policy)
    assert api_policy["structuredDetail"]["conditions"] == [
        {"title": "혜택 적용 조건", "description": "강진군 관광지 2개소 이상 방문"},
        {"title": "혜택 적용 조건", "description": "모바일 강진사랑상품권(Chak)으로 결제"},
    ]
    assert api_policy["structuredDetail"]["documents"] == [
        {"title": "필요 서류", "description": "거래내역(영수증)"}
    ]
    assert api_policy["structuredDetail"]["notices"] == [
        {"title": "확인 필요 사항", "description": "홈페이지 공지사항(고시공고) 필독"}
    ]
    assert "거래내역(영수증)" not in [
        item["description"] for item in api_policy["structuredDetail"]["conditions"]
    ]
    assert "홈페이지 공지사항(고시공고) 필독" not in [
        item["description"] for item in api_policy["structuredDetail"]["documents"]
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
    assert [item["description"] for item in structured_detail["conditions"]] == [
        notes,
        "chak 앱(모바일 강진사랑상품권) 사용",
    ]
    assert [item["description"] for item in structured_detail["periods"]] == [
        "신청 기간: 2026.06.10-2026.08.31",
        "여행 기간: 6.10~8.31",
    ]
    assert structured_detail["documents"] == []
    assert structured_detail["notices"] == []


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

    from app.services.policy_normalization import (
        DEFAULT_TARGET_CONDITION,
        promote_external_benefits_to_policies,
    )

    promote_external_benefits_to_policies(db)

    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert policy is not None
    assert policy.target_condition == DEFAULT_TARGET_CONDITION


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

    from app.services.policy_normalization import (
        DEFAULT_TARGET_CONDITION,
        promote_external_benefits_to_policies,
    )

    promote_external_benefits_to_policies(db)

    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert policy is not None
    assert policy.target_condition == DEFAULT_TARGET_CONDITION


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


def test_promotes_active_fresh_stay_discount_as_lodging_policy(db: Session) -> None:
    rows = upsert_external_source_records(
        db,
        [
            make_source(
                source_name="대한민국 숙박세일 페스타",
                source_url="https://korean.visitkorea.or.kr/travelmonth/benefits/stay.do",
                collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/stay.do",
                source_category="stay_discount",
                canonical_key="stay-discount",
                external_id="stay-discount",
                title="숙박세일 페스타 7만원 할인",
                benefit_text="숙박상품 2/3/5/7만원 할인권",
                benefit_value_text="2/3/5/7만원 할인권",
                extracted_amount_krw=70000,
            )
        ],
    )

    from app.services.policy_normalization import promote_external_benefits_to_policies

    promote_external_benefits_to_policies(db)

    policy = get_policy_by_slug(db, f"travelmonth-{rows[0].id}")
    assert policy is not None
    assert policy.source_category == "stay_discount"
    assert policy.policy_type == "숙박"
    assert policy.benefit_amount == 70000
    assert policy.official_url == "https://example.com/detail"


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
