from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.data.policy_display import SUPPORTED_CATEGORIES
from app.db.base import Base
from app.models import ExternalSourceRecord, Policy, PolicyDocument, Trip, TripPolicy, User
from app.schemas.admin import AdminPolicyCreateRequest, AdminUserUpdateRequest
from app.services import admin as admin_service
from app.services import policies as policy_service
from app.services import trips as trip_service

CATEGORY = sorted(SUPPORTED_CATEGORIES)[0]


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with TestingSessionLocal() as session:
        yield session


def make_user(user_id: int, *, email: str, role: str = "user") -> User:
    return User(
        id=user_id,
        email=email,
        nickname=f"user-{user_id}",
        role=role,
        onboarding_completed=True,
        created_at=datetime(2026, 5, 27, 0, 0, 0),
        updated_at=datetime(2026, 5, 27, 0, 0, 0),
    )


def make_policy(policy_id: int, *, slug: str, status: str = "active") -> Policy:
    policy = Policy(
        id=policy_id,
        slug=slug,
        title=f"Policy {policy_id}",
        organization="Travel Hunter",
        policy_type=CATEGORY,
        description="Policy description",
        benefit_amount=10000,
        benefit_detail="10000 KRW discount",
        target_condition="Domestic traveler",
        region="Nationwide",
        end_date=date(2026, 12, 31),
        official_url="https://example.com/official",
        apply_url=None,
        policy_comment="Policy summary",
        status=status,
    )
    policy.documents = [PolicyDocument(id=policy_id * 100, document_name="ID card")]
    return policy


def test_admin_user_update_changes_allowed_fields_and_records_audit(db: Session) -> None:
    admin = make_user(1, email="admin@example.com", role="admin")
    user = make_user(2, email="user@example.com", role="user")
    db.add_all([admin, user])
    db.commit()

    result = admin_service.update_user(
        db,
        admin,
        "2",
        AdminUserUpdateRequest(
            nickname="updated-user",
            preferredRegions=" 부산,강원, 부산 ",
            travelStyle="Food",
            travelBudget="under 400000 KRW",
            onboardingCompleted=False,
            role="admin",
        ),
    )

    assert result["nickname"] == "updated-user"
    assert result["role"] == "admin"
    assert user.preferred_regions == "부산,강원"
    assert result["preferredRegions"] == "부산,강원"
    assert user.travel_style == "Food"
    assert user.travel_budget == "under 400000 KRW"
    assert user.onboarding_completed is False
    audit_logs = admin_service.list_audit_logs(db, admin, limit=10, offset=0)
    assert audit_logs["total"] == 1
    assert audit_logs["items"][0]["action"] == "user.update"
    assert "password" not in str(audit_logs["items"][0]["beforeJson"]).lower()


def test_admin_user_update_rejects_self_or_final_admin_demotion(db: Session) -> None:
    admin = make_user(1, email="admin@example.com", role="admin")
    db.add(admin)
    db.commit()

    with pytest.raises(admin_service.AdminServiceError) as error:
        admin_service.update_user(
            db,
            admin,
            "1",
            AdminUserUpdateRequest(role="user"),
        )

    assert error.value.status_code == 409


def test_admin_user_update_validates_preferred_regions(db: Session) -> None:
    admin = make_user(1, email="admin@example.com", role="admin")
    user = make_user(2, email="user@example.com", role="user")
    db.add_all([admin, user])
    db.commit()

    with pytest.raises(admin_service.AdminServiceError) as invalid_error:
        admin_service.update_user(
            db,
            admin,
            "2",
            AdminUserUpdateRequest(preferredRegions="부산,달나라"),
        )

    assert invalid_error.value.status_code == 422
    assert user.preferred_regions is None

    with pytest.raises(admin_service.AdminServiceError) as too_many_error:
        admin_service.update_user(
            db,
            admin,
            "2",
            AdminUserUpdateRequest(preferredRegions="서울,부산,대구,인천"),
        )

    assert too_many_error.value.status_code == 422
    assert user.preferred_regions is None

    result = admin_service.update_user(
        db,
        admin,
        "2",
        AdminUserUpdateRequest(preferredRegions="  "),
    )

    assert result["preferredRegions"] is None
    assert user.preferred_regions is None


def test_admin_policy_create_maps_save_fields_and_records_audit(db: Session) -> None:
    admin = make_user(1, email="admin@example.com", role="admin")
    db.add(admin)
    db.commit()

    result = admin_service.create_policy(
        db,
        admin,
        AdminPolicyCreateRequest(
            slug="admin-created-policy",
            title="Admin created policy",
            organization="Travel Hunter",
            policyType=CATEGORY,
            region="Nationwide",
            startDate=date(2026, 6, 1),
            endDate=date(2026, 12, 31),
            benefitAmount=30000,
            benefitDetail="30000 KRW discount",
            description="Policy registered by admin",
            requirements=["Domestic traveler", "Receipt required"],
            documents=["ID card", "Receipt"],
            officialUrl="https://example.com/official",
            applyUrl=None,
            status="hidden",
        ),
    )

    policy = db.get(Policy, int(result["id"]))
    assert policy is not None
    assert policy.source_type == "internal"
    assert policy.target_condition == "Domestic traveler\nReceipt required"
    assert policy.status == "hidden"
    assert [document.document_name for document in policy.documents] == ["ID card", "Receipt"]
    assert policy.structured_detail is not None
    assert policy.structured_detail["benefits"][0]["description"] == "30000 KRW discount"
    assert policy.structured_detail["conditions"] == [
        {"title": "조건", "description": "Domestic traveler"},
        {"title": "조건", "description": "Receipt required"},
    ]
    assert policy.structured_detail["documents"] == [
        {"title": "필요 서류", "description": "ID card"},
        {"title": "필요 서류", "description": "Receipt"},
    ]
    assert admin_service.list_audit_logs(db, admin, limit=10, offset=0)["items"][0]["action"] == "policy.create"


def test_admin_policy_create_filters_phone_contact_requirements(db: Session) -> None:
    admin = make_user(1, email="admin@example.com", role="admin")
    db.add(admin)
    db.commit()

    result = admin_service.create_policy(
        db,
        admin,
        AdminPolicyCreateRequest(
            slug="admin-phone-filtered-policy",
            title="Admin phone filtered policy",
            organization="Travel Hunter",
            policyType=CATEGORY,
            region="Nationwide",
            requirements=[
                "1660-3067",
                "문의전화 1660-3067 특이사항 지정관광지 방문 인증",
                "국내 거주자",
            ],
        ),
    )

    policy = db.get(Policy, int(result["id"]))
    assert policy is not None
    assert policy.target_condition == "국내 거주자"
    assert result["requirements"] == ["국내 거주자"]


def test_admin_policy_create_replaces_only_phone_requirements_with_default(db: Session) -> None:
    admin = make_user(1, email="admin@example.com", role="admin")
    db.add(admin)
    db.commit()

    result = admin_service.create_policy(
        db,
        admin,
        AdminPolicyCreateRequest(
            slug="admin-only-phone-policy",
            title="Admin only phone policy",
            organization="Travel Hunter",
            policyType=CATEGORY,
            region="Nationwide",
            requirements=["1660-3067"],
        ),
    )

    policy = db.get(Policy, int(result["id"]))
    assert policy is not None
    assert policy.target_condition == "공식 혜택 안내에서 조건을 확인하세요."
    assert result["requirements"] == ["공식 혜택 안내에서 조건을 확인하세요."]


def test_hidden_policy_is_excluded_from_public_surfaces_but_trip_link_keeps_status(db: Session) -> None:
    admin = make_user(1, email="admin@example.com", role="admin")
    active = make_policy(10, slug="active-policy", status="active")
    hidden = make_policy(11, slug="hidden-policy", status="hidden")
    trip = Trip(
        id=99,
        owner_id=1,
        title="Gangwon trip",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 3),
        status="draft",
        region="Gangwon",
        participant_count=1,
    )
    link = TripPolicy(id=1, trip_id=99, policy_id=11)
    link.policy = hidden
    trip.owner = admin
    trip.policies = [link]
    db.add_all([admin, active, hidden, trip, link])
    db.commit()

    assert [policy["slug"] for policy in policy_service.list_policies(db)] == ["active-policy"]
    assert policy_service.get_policy("hidden-policy", db) is None
    payload = trip_service.trip_to_api(trip, admin, recommended_policies=[])
    assert payload["linkedPolicies"][0]["slug"] == "hidden-policy"
    assert payload["linkedPolicies"][0]["status"] == "hidden"


def test_admin_update_external_policy_sets_override_enabled(db: Session) -> None:
    admin = make_user(1, email="admin@example.com", role="admin")
    policy = make_policy(20, slug="external-policy", status="active")
    policy.external_source_record_id = 100
    policy.source_type = "external"
    db.add_all([admin, policy])
    db.commit()

    result = admin_service.update_policy(
        db,
        admin,
        "20",
        admin_service.AdminPolicyUpdateRequest(title="Edited external policy"),
    )

    assert result["adminOverrideEnabled"] is True
    assert policy.admin_override_enabled is True


def test_admin_policy_update_refreshes_structured_detail(db: Session) -> None:
    admin = make_user(1, email="admin@example.com", role="admin")
    policy = make_policy(21, slug="structured-refresh-policy", status="active")
    policy.structured_detail = {
        "benefits": [{"title": "혜택", "description": "Old benefit"}],
        "conditions": [],
        "periods": [],
        "links": [],
        "documents": [],
        "notices": [],
    }
    db.add_all([admin, policy])
    db.commit()

    admin_service.update_policy(
        db,
        admin,
        "21",
        admin_service.AdminPolicyUpdateRequest(
            benefitDetail="Updated benefit",
            requirements=["문의전화 1660-3067", "국내 거주자"],
            documents=["Updated document"],
        ),
    )

    assert policy.structured_detail is not None
    assert policy.structured_detail["benefits"][0]["description"] == "Updated benefit"
    assert policy.structured_detail["conditions"] == [{"title": "조건", "description": "국내 거주자"}]
    assert policy.structured_detail["documents"] == [{"title": "필요 서류", "description": "Updated document"}]


def test_admin_policy_update_rejects_slug_source_type_label_and_tag() -> None:
    from pydantic import ValidationError
    from app.schemas.admin import AdminPolicyUpdateRequest

    with pytest.raises(ValidationError):
        AdminPolicyUpdateRequest.model_validate({"slug": "new-slug"})
    with pytest.raises(ValidationError):
        AdminPolicyUpdateRequest.model_validate({"sourceType": "external"})
    with pytest.raises(ValidationError):
        AdminPolicyUpdateRequest.model_validate({"label": "badge"})
    with pytest.raises(ValidationError):
        AdminPolicyUpdateRequest.model_validate({"tag": "tag"})


def test_admin_external_source_summary_groups_records_and_promoted_policies(db: Session) -> None:
    admin = make_user(1, email="admin@example.com", role="admin")
    first = ExternalSourceRecord(
        id=101,
        source_name="대한민국 반값여행",
        source_type="official_campaign",
        source_category="local_half_trip",
        source_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        external_id="half-1",
        canonical_key="half-1",
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        title="하동 대한민국 반값여행 지원",
        organizer_text="하동 지자체",
        organizers=["하동 지자체"],
        region="경남",
        city="하동",
        is_nationwide=False,
        status="active",
        benefit_text="반값여행 지원",
        benefit_value_type="mixed",
        tags=["반값여행"],
        inferred_travel_styles=[],
        confidence=90,
        field_completeness=90,
        raw_list_text="하동",
        raw_detail_text="하동",
        raw_payload={},
        last_fetched_at=datetime(2026, 5, 27, 9, 0, 0),
        last_verified_at=datetime(2026, 5, 27, 9, 0, 0),
        freshness_status="fresh",
    )
    second = ExternalSourceRecord(
        id=102,
        source_name="대한민국 반값여행",
        source_type="official_campaign",
        source_category="local_half_trip",
        source_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        external_id="half-2",
        canonical_key="half-2",
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        title="제천 대한민국 반값여행 지원",
        organizer_text="제천 지자체",
        organizers=["제천 지자체"],
        region="충북",
        city="제천",
        is_nationwide=False,
        status="ended",
        benefit_text="반값여행 지원",
        benefit_value_type="mixed",
        tags=["반값여행"],
        inferred_travel_styles=[],
        confidence=90,
        field_completeness=90,
        raw_list_text="제천",
        raw_detail_text="제천",
        raw_payload={},
        last_fetched_at=datetime(2026, 5, 27, 10, 0, 0),
        last_verified_at=None,
        freshness_status="unknown",
    )
    db.add_all([admin, first, second])
    db.flush()
    db.add(
        Policy(
            id=201,
            slug=f"travelmonth-{first.id}",
            title="하동 대한민국 반값여행 지원",
            policy_type=CATEGORY,
            region="경남",
            status="active",
            source_type="official_campaign",
            source_category="local_half_trip",
            external_source_record_id=first.id,
        )
    )
    db.flush()

    result = admin_service.get_external_source_summary(db, admin)

    assert result["totalRecords"] == 2
    assert result["activeRecords"] == 1
    assert result["freshRecords"] == 1
    assert result["promotedPolicyCount"] == 1
    assert result["latestFetchedAt"] == "2026-05-27T10:00:00"
    assert result["items"][0]["sourceCategory"] == "local_half_trip"
    assert result["items"][0]["label"] == "반값여행"
    assert result["items"][0]["totalRecords"] == 2
    assert result["items"][0]["activeRecords"] == 1
    assert result["items"][0]["endedRecords"] == 1
    assert result["items"][0]["promotedPolicyCount"] == 1
    assert result["items"][0]["activePromotedPolicyCount"] == 1


def test_admin_policy_list_includes_source_category_and_label(db: Session) -> None:
    admin = make_user(1, email="admin-policy-source@example.com", role="admin")
    external_policy = Policy(
        id=301,
        slug="travelmonth-1",
        title="영광 대한민국 반값여행 지원",
        policy_type=CATEGORY,
        region="전남",
        status="active",
        source_type="official_campaign",
        source_category="local_half_trip",
        external_source_record_id=1,
    )
    internal_policy = Policy(
        id=302,
        slug="internal-policy",
        title="내부 정책",
        policy_type=CATEGORY,
        region="전국",
        status="active",
        source_type="internal",
    )
    db.add_all([admin, external_policy, internal_policy])
    db.flush()

    result = admin_service.list_policies(db, admin)
    items = {item["slug"]: item for item in result["items"]}

    assert items["travelmonth-1"]["sourceCategory"] == "local_half_trip"
    assert items["travelmonth-1"]["sourceLabel"] == "반값여행"
    assert items["internal-policy"]["sourceCategory"] is None
    assert items["internal-policy"]["sourceLabel"] == "내부"
