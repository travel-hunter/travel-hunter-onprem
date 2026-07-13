from datetime import date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import BigInteger, Integer, create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import (
    ExternalSourceRecord,
    Policy,
    Recommendation,
    Trip,
    TripDay,
    TripInvite,
    TripMember,
    TripPlace,
    TripPolicy,
    UserSavedPolicy,
)
from app.models import User as UserModel
from app.repositories import policies as policy_repository
from app.schemas.trip import (
    CreateTripPlaceRequest,
    CreateTripRequest,
    MoveTripPlaceRequest,
    SendInviteEmailRequest,
    UpdateTripPlaceRequest,
    UpdateTripStatusRequest,
)
from app.services.kakao_local import KakaoLocalPlace
from app.services import itinerary_recommendations, trips as trip_service


def make_user(user_id: int = 1, nickname: str = "Test User") -> UserModel:
    return UserModel(
        id=user_id,
        email=f"user-{user_id}@travel.kr",
        nickname=nickname,
        onboarding_completed=True,
        created_at=datetime(2026, 5, 4, 0, 0, 0),
        updated_at=datetime(2026, 5, 4, 0, 0, 0),
    )


def make_invite(*, role: str = "editor", accepted_at: datetime | None = None) -> TripInvite:
    return TripInvite(
        id=9,
        trip_id=7,
        invite_token="abc",
        created_by=1,
        role=role,
        created_at=datetime(2026, 5, 4, 0, 0, 0),
        expires_at=datetime(2026, 6, 30, 0, 0, 0),
        accepted_at=accepted_at,
    )


def make_trip() -> Trip:
    owner = make_user(1, "Test User")
    friend = make_user(2, "Minseo")
    trip = Trip(
        id=7,
        owner_id=1,
        title="Jeju 3-day trip",
        status="confirmed",
        revision=1,
        start_date=date(2026, 6, 15),
        end_date=date(2026, 6, 17),
        region="Jeju",
        travel_area_id=None,
        participant_count=2,
        description="Rest trip",
        created_at=datetime(2026, 5, 4, 0, 0, 0),
        updated_at=datetime(2026, 5, 4, 0, 0, 0),
    )

    trip.owner = owner

    owner_membership = TripMember(id=1, trip_id=7, user_id=1, role="owner")
    owner_membership.user = owner
    friend_membership = TripMember(id=2, trip_id=7, user_id=2, role="editor")
    friend_membership.user = friend
    trip.members = [friend_membership, owner_membership]

    day = TripDay(id=1, trip_id=7, day_number=1, date=date(2026, 6, 15))
    day.places = [
        TripPlace(
            id=1,
            trip_day_id=1,
            place_name="Sunrise peak",
            visit_time=time(9, 0),
            order_num=1,
            memo="Nature",
        )
    ]
    trip.days = [day]

    policy = Policy(id=3, slug="fixture-policy", title="Vacation policy", benefit_amount=300000)
    trip_policy = TripPolicy(id=1, trip_id=7, policy_id=3)
    trip_policy.policy = policy
    trip.policies = [trip_policy]
    trip.invites = []
    trip.recommendations = []
    return trip

def test_search_places_for_trip_maps_kakao_candidates(monkeypatch) -> None:
    class FakeSearchProvider:
        def search_keyword(self, *, query: str, size: int = 10):
            assert query == "성산일출봉"
            assert size == 10
            return [
                KakaoLocalPlace(
                    external_place_id="kakao-1",
                    name="성산일출봉",
                    category_name="관광명소",
                    category_group_code="AT4",
                    category_group_name="관광명소",
                    phone="064-000-0000",
                    address="제주 서귀포시 성산읍",
                    latitude=33.4581,
                    longitude=126.9425,
                    place_url="https://place.map.kakao.com/kakao-1",
                )
            ]

    user = make_user()
    trip = make_trip()
    monkeypatch.setattr(trip_service, "_resolve_required_trip", lambda db, trip_handle, current_user: trip)
    monkeypatch.setattr(trip_service, "build_kakao_local_client", lambda: FakeSearchProvider())

    candidates = trip_service.search_places_for_trip(
        object(),
        user,
        trip_handle="7",
        query="성산일출봉",
    )

    assert candidates[0]["title"] == "성산일출봉"
    assert candidates[0]["meta"] == "관광명소 · 제주 서귀포시 성산읍"
    assert candidates[0]["sourceProvider"] == "kakao"
    assert candidates[0]["externalPlaceId"] == "kakao-1"


def make_stay_policy() -> Policy:
    return Policy(
        id=88,
        slug="travelmonth-88",
        title="2026 대한민국 숙박세일 페스타 숙박 할인",
        benefit_detail="2/3/5/7만원 할인권",
        benefit_amount=70000,
        region="비수도권 인구감소지역",
        start_date=date(2026, 6, 11),
        end_date=date(2026, 7, 31),
        source_category="stay_discount",
        policy_type="숙박",
        external_source_record_id=88,
        verification_status="fresh",
        status="active",
    )


def make_stay_record() -> ExternalSourceRecord:
    return ExternalSourceRecord(
        id=88,
        source_name="대한민국 숙박세일 페스타",
        source_type="official_campaign",
        source_category="stay_discount",
        external_id="stay-discount",
        canonical_key="stay-discount",
        detail_url="https://ktostay.visitkorea.or.kr/",
        collected_page_url="https://ktostay.visitkorea.or.kr/",
        title="2026 대한민국 숙박세일 페스타 숙박 할인",
        organizer_text="문화체육관광부, 한국관광공사",
        region="비수도권 인구감소지역",
        is_nationwide=False,
        status="active",
        start_date=date(2026, 6, 11),
        end_date=date(2026, 7, 31),
        benefit_text="2/3/5/7만원 할인권",
        benefit_value_text="2/3/5/7만원 할인권",
        extracted_amount_krw=70000,
        tags=["숙박", "휴식"],
        inferred_travel_styles=["휴식"],
        freshness_status="fresh",
        raw_payload={
            "eligibleAreas": [
                {"sido": "강원", "cities": ["고성군", "삼척시"]},
                {"sido": "경남", "cities": ["고성군"]},
            ],
            "eligibleAreaCount": 3,
        },
    )


def test_trip_to_api_includes_place_map_metadata(monkeypatch) -> None:
    trip = make_trip()
    day = TripDay(id=10, trip_id=7, day_number=1, date=date(2026, 7, 12))
    place = TripPlace(
        id=99,
        trip_day_id=10,
        place_name="강원 속초 맛집",
        address="강원 속초시 중앙로 47",
        latitude=Decimal("38.2041234"),
        longitude=Decimal("128.5901234"),
        visit_time=time(13, 0),
        order_num=1,
        memo="식사 추천 장소",
    )
    place.category_group_code = "FD6"
    place.category_group_name = "음식점"
    place.place_url = "http://place.map.kakao.com/12345"
    place.source_provider = "kakao_local"
    place.external_place_id = "12345"
    day.places = [place]
    trip.days = [day]
    trip.members = []
    trip.policies = []
    trip.recommendations = []

    payload = trip_service.trip_to_api(trip, make_user(1), recommended_policies=[])

    api_place = payload["days"][1][0]
    assert api_place["address"] == "강원 속초시 중앙로 47"
    assert api_place["latitude"] == 38.2041234
    assert api_place["longitude"] == 128.5901234
    assert api_place["category"] == "음식점"
    assert api_place["categoryCode"] == "FD6"
    assert api_place["placeUrl"] == "http://place.map.kakao.com/12345"
    assert api_place["sourceProvider"] == "kakao_local"
    assert api_place["externalPlaceId"] == "12345"


def test_trip_to_api_returns_numeric_string_id_and_contract_shape() -> None:
    payload = trip_service.trip_to_api(make_trip())

    assert payload["id"] == "7"
    assert payload["title"] == "Jeju 3-day trip"
    assert payload["status"] == "confirmed"
    assert payload["revision"] == 1
    assert payload["travelAreaId"] is None
    assert payload["dates"] == "2026.06.15 - 06.17"
    assert payload["people"] == ["Test User", "Minseo"]
    assert payload["participantCount"] == 2
    assert payload["expectedSaving"] == "30만원"
    assert payload["linkedPolicies"] == [
        {
            "slug": "fixture-policy",
            "title": "Vacation policy",
            "amount": "30만원",
            "region": "",
            "status": "active",
        }
    ]
    place = payload["days"][1][0]
    assert place["id"] == "1"
    assert place["time"] == "09:00"
    assert place["label"] == "Sunrise peak"
    assert place["meta"] == "Nature"
    assert place["address"] is None
    assert place["latitude"] is None
    assert place["longitude"] is None
    assert place["category"] is None
    assert place["categoryCode"] is None
    assert place["placeUrl"] is None
    assert place["sourceProvider"] is None
    assert place["externalPlaceId"] is None
    assert payload["currentUserRole"] == "owner"


def test_trip_to_api_includes_current_user_role() -> None:
    trip = make_trip()

    owner_payload = trip_service.trip_to_api(trip, make_user(1))
    editor_payload = trip_service.trip_to_api(trip, make_user(2))
    trip.members[0].role = "viewer"
    viewer_payload = trip_service.trip_to_api(trip, make_user(2))

    assert owner_payload["currentUserRole"] == "owner"
    assert editor_payload["currentUserRole"] == "editor"
    assert viewer_payload["currentUserRole"] == "viewer"


def test_trip_to_api_includes_owner_when_owner_is_not_a_member() -> None:
    trip = make_trip()
    trip.members = [member for member in trip.members if member.user_id != trip.owner_id]

    payload = trip_service.trip_to_api(trip)

    assert payload["people"] == ["Test User", "Minseo"]


def test_get_trip_resolves_numeric_id_only(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    trip = make_trip()

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip if db is fake_db and trip_id == 7 and user_id == 1 else None,
    )

    numeric = trip_service.get_trip("7", fake_db, user)
    missing_numeric = trip_service.get_trip("8", fake_db, user)

    assert numeric is not None
    assert numeric["id"] == "7"
    assert missing_numeric is None


def test_get_trip_includes_region_matched_recommended_policies(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    trip = make_trip()
    trip.region = "부산"
    trip.title = "부산 3일 여행"
    linked_policy = trip.policies[0].policy
    linked_policy.slug = "fixture-policy"
    linked_policy.title = "지역사랑 휴가지원"
    linked_policy.region = "전국"
    recommended_policy = Policy(
        id=4,
        slug="fixture-busan-cashback",
        title="부산 여행 캐시백",
        benefit_detail="카드 결제 5% 캐시백",
        region="부산",
        end_date=date(2026, 6, 30),
    )
    other_policy = Policy(
        id=5,
        slug="gangwon-stay",
        title="속초 숙박 할인권",
        benefit_detail="숙박비 50% 할인",
        region="강원",
        end_date=date(2026, 6, 30),
    )

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip if db is fake_db and trip_id == 7 and user_id == 1 else None,
    )
    monkeypatch.setattr(
        trip_service.policy_repository,
        "list_policies",
        lambda db: [linked_policy, other_policy, recommended_policy] if db is fake_db else [],
    )

    payload = trip_service.get_trip("7", fake_db, user)

    assert payload is not None
    assert payload["recommendedPolicies"] == [
        {
            "slug": "fixture-busan-cashback",
            "title": "부산 여행 캐시백",
            "amount": "카드 결제 5% 캐시백",
            "region": "부산",
        }
    ]


def test_get_trip_recommendations_prioritize_travel_area_terms(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    trip = make_trip()
    trip.region = "\uc18d\ucd08\u00b7\uace0\uc131\u00b7\uc591\uc591"
    trip.travel_area_id = "gangwon-sokcho-goseong-yangyang"
    linked_policy = trip.policies[0].policy
    linked_policy.slug = "fixture-policy"
    linked_policy.title = "\uc774\ubbf8 \uc5f0\uacb0\ub41c \uc815\ucc45"
    linked_policy.region = "\uc804\uad6d"
    jeju_family_policy = Policy(
        id=4,
        slug="jeju-family-stay",
        title="\uc548\uc804 \uc778\uc99d \ub18d\uc5b4\ucd0c\ubbfc\ubc15 \uc774\uc6a9 \ub2e4\uc790\ub140\uac00\uad6c \uc81c\uc8fc\uc5ec\ud589 \ud658\uc601 \ucea0\ud398\uc778",
        benefit_detail="\uc219\ubc15\ube44 4\ub9cc\uc6d0 \uc9c0\uc6d0",
        benefit_amount=40000,
        region="\uc804\uad6d",
        end_date=date(2026, 5, 31),
    )
    sokcho_policy = Policy(
        id=5,
        slug="sokcho-stay",
        title="\uc18d\ucd08 \uc219\ubc15 \ud560\uc778",
        benefit_detail="\uc18d\ucd08 \uc219\ubc15\ube44 \ud560\uc778",
        benefit_amount=0,
        region="\uac15\uc6d0",
        end_date=date(2026, 7, 31),
    )
    yangyang_policy = Policy(
        id=6,
        slug="yangyang-experience",
        title="\uc591\uc591 \ubc14\ub2e4 \uccb4\ud5d8 \ud560\uc778",
        benefit_detail="\uc591\uc591 \uccb4\ud5d8\uad8c \ud560\uc778",
        benefit_amount=0,
        region="\uc804\uad6d",
        end_date=date(2026, 8, 31),
    )

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip if db is fake_db and trip_id == 7 and user_id == 1 else None,
    )
    monkeypatch.setattr(
        trip_service.policy_repository,
        "list_policies",
        lambda db: [linked_policy, jeju_family_policy, sokcho_policy, yangyang_policy] if db is fake_db else [],
    )

    payload = trip_service.get_trip("7", fake_db, user)

    assert payload is not None
    assert [policy["slug"] for policy in payload["recommendedPolicies"]] == ["sokcho-stay", "yangyang-experience"]


def test_get_trip_recommendations_downrank_unverified_conditional_policies(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    trip = make_trip()
    trip.region = "\uc18d\ucd08\u00b7\uace0\uc131\u00b7\uc591\uc591"
    trip.travel_area_id = "gangwon-sokcho-goseong-yangyang"
    linked_policy = trip.policies[0].policy
    linked_policy.slug = "fixture-policy"
    linked_policy.region = "\uc804\uad6d"
    general_policy = Policy(
        id=4,
        slug="sokcho-general-stay",
        title="\uc18d\ucd08 \uc219\ubc15 \ud560\uc778",
        benefit_detail="\uc18d\ucd08 \uc219\ubc15\ube44 \ud560\uc778",
        benefit_amount=0,
        region="\uc804\uad6d",
        end_date=date(2026, 8, 31),
    )
    youth_policy = Policy(
        id=5,
        slug="sokcho-youth-stay",
        title="\uc18d\ucd08 \uccad\ub144 \uc219\ubc15 \ud560\uc778",
        benefit_detail="\uc18d\ucd08 \uccad\ub144 \uc804\uc6a9 \uc219\ubc15\ube44 5\ub9cc\uc6d0 \uc9c0\uc6d0",
        benefit_amount=50000,
        region="\uc804\uad6d",
        end_date=date(2026, 5, 31),
    )

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip if db is fake_db and trip_id == 7 and user_id == 1 else None,
    )
    monkeypatch.setattr(
        trip_service.policy_repository,
        "list_policies",
        lambda db: [linked_policy, youth_policy, general_policy] if db is fake_db else [],
    )

    payload = trip_service.get_trip("7", fake_db, user)

    assert payload is not None
    assert [policy["slug"] for policy in payload["recommendedPolicies"]] == ["sokcho-general-stay", "sokcho-youth-stay"]


def test_get_trip_recommendations_return_up_to_three_area_matched_policies(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    trip = make_trip()
    trip.region = "\uc18d\ucd08\u00b7\uace0\uc131\u00b7\uc591\uc591"
    trip.travel_area_id = "gangwon-sokcho-goseong-yangyang"
    linked_policy = trip.policies[0].policy
    linked_policy.slug = "fixture-policy"
    linked_policy.region = "\uc804\uad6d"
    policies = [
        linked_policy,
        Policy(id=4, slug="sokcho-stay", title="\uc18d\ucd08 \uc219\ubc15 \ud560\uc778", benefit_detail="\uc18d\ucd08 \uc219\ubc15\ube44 \ud560\uc778", region="\uac15\uc6d0", end_date=date(2026, 7, 31)),
        Policy(id=5, slug="goseong-cafe", title="\uace0\uc131 \uce74\ud398 \ud560\uc778", benefit_detail="\uace0\uc131 \uce74\ud398 \uc774\uc6a9\uad8c", region="\uc804\uad6d", end_date=date(2026, 8, 31)),
        Policy(id=6, slug="yangyang-surf", title="\uc591\uc591 \uc11c\ud551 \uccb4\ud5d8 \ud560\uc778", benefit_detail="\uc591\uc591 \uccb4\ud5d8\uad8c", region="\uc804\uad6d", end_date=date(2026, 9, 30)),
        Policy(id=7, slug="gangwon-extra", title="\uac15\uc6d0 \uc5ec\ud589 \uc0c1\ud488 \ud560\uc778", benefit_detail="\uac15\uc6d0 \uc5ec\ud589 \ud560\uc778", region="\uac15\uc6d0", end_date=date(2026, 10, 31)),
    ]

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip if db is fake_db and trip_id == 7 and user_id == 1 else None,
    )
    monkeypatch.setattr(
        trip_service.policy_repository,
        "list_policies",
        lambda db: policies if db is fake_db else [],
    )

    payload = trip_service.get_trip("7", fake_db, user)

    assert payload is not None
    assert [policy["slug"] for policy in payload["recommendedPolicies"]] == ["sokcho-stay", "goseong-cafe", "yangyang-surf"]


def test_get_trip_recommendations_hide_candidates_below_area_score_threshold(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    trip = make_trip()
    trip.region = "\uc18d\ucd08\u00b7\uace0\uc131\u00b7\uc591\uc591"
    trip.travel_area_id = "gangwon-sokcho-goseong-yangyang"
    linked_policy = trip.policies[0].policy
    linked_policy.slug = "fixture-policy"
    linked_policy.region = "\uc804\uad6d"
    jeju_family_policy = Policy(
        id=4,
        slug="jeju-family-stay",
        title="\uc548\uc804 \uc778\uc99d \ub18d\uc5b4\ucd0c\ubbfc\ubc15 \uc774\uc6a9 \ub2e4\uc790\ub140\uac00\uad6c \uc81c\uc8fc\uc5ec\ud589 \ud658\uc601 \ucea0\ud398\uc778",
        benefit_detail="\uc81c\uc8fc \uc219\ubc15\ube44 4\ub9cc\uc6d0 \uc9c0\uc6d0",
        benefit_amount=40000,
        region="\uc804\uad6d",
        end_date=date(2026, 5, 31),
    )

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip if db is fake_db and trip_id == 7 and user_id == 1 else None,
    )
    monkeypatch.setattr(
        trip_service.policy_repository,
        "list_policies",
        lambda db: [linked_policy, jeju_family_policy] if db is fake_db else [],
    )

    payload = trip_service.get_trip("7", fake_db, user)

    assert payload is not None
    assert payload["recommendedPolicies"] == []


def test_get_trip_recommendations_ignore_raw_collected_benefits(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    trip = make_trip()
    trip.region = "부산"

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip if db is fake_db and trip_id == 7 and user_id == 1 else None,
    )
    monkeypatch.setattr(
        trip_service.policy_repository,
        "list_policies",
        lambda db: [] if db is fake_db else [],
    )
    payload = trip_service.get_trip("7", fake_db, user)

    assert payload is not None
    assert payload["recommendedPolicies"] == []


def test_get_trip_recommends_normalized_travelmonth_policy(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    trip = make_trip()
    trip.region = "Busan"
    normalized_policy = Policy(
        id=58,
        slug="travelmonth-58",
        title="Busan official benefit",
        benefit_detail="Up to 20,000 KRW",
        region="Busan",
        end_date=date(2026, 6, 30),
        source_category="regional_benefit",
        external_source_record_id=58,
    )

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip if db is fake_db and trip_id == 7 and user_id == 1 else None,
    )
    monkeypatch.setattr(
        trip_service.policy_repository,
        "list_policies",
        lambda db: [normalized_policy] if db is fake_db else [],
    )
    payload = trip_service.get_trip("7", fake_db, user)

    assert payload is not None
    assert payload["recommendedPolicies"] == [
        {
            "slug": "travelmonth-58",
            "title": "Busan official benefit",
            "amount": "Up to 20,000 KRW",
            "region": "Busan",
        }
    ]


def test_get_trip_rejects_noncanonical_and_non_numeric_handles(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    calls: list[str] = []
    non_numeric_handle = "-".join(["jeju", "3", "days"])

    def unexpected_numeric_lookup(*_args):
        calls.append("numeric")
        return None

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        unexpected_numeric_lookup,
    )

    assert trip_service.get_trip(non_numeric_handle, fake_db, user) is None
    assert trip_service.get_trip("missing-trip", fake_db, user) is None
    assert trip_service.get_trip("001", fake_db, user) is None
    assert trip_service.get_trip("0", fake_db, user) is None
    assert trip_service.get_trip("1.0", fake_db, user) is None
    assert calls == []


class FakeDb:
    def __init__(self) -> None:
        self.commits = 0

    def execute(self, *_args, **_kwargs):
        return SimpleNamespace(rowcount=1)

    def commit(self) -> None:
        self.commits += 1


@pytest.fixture
def sqlite_db_session():
    engine = create_engine("sqlite:///:memory:")
    mutated_columns = []
    for table in Base.metadata.tables.values():
        for column in table.c:
            if column.primary_key and isinstance(column.type, BigInteger):
                mutated_columns.append((column, column.type))
                column.type = Integer()

    try:
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        with TestingSessionLocal() as session:
            yield session
        Base.metadata.drop_all(engine)
    finally:
        for column, original_type in mutated_columns:
            column.type = original_type


def add_visibility_policy_rows(sqlite_db_session):
    user = make_user(60, "Visibility User")
    active_policy = Policy(
        id=610,
        slug="active-policy",
        title="Active policy",
        benefit_detail="1만원 할인",
        region="전국",
        status="active",
    )
    hidden_policy = Policy(
        id=611,
        slug="hidden-policy",
        title="Hidden policy",
        benefit_detail="2만원 할인",
        region="전국",
        status="hidden",
    )
    trip = Trip(
        id=612,
        owner_id=user.id,
        title="Visibility trip",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        region="전국",
        status="draft",
    )
    sqlite_db_session.add_all(
        [
            user,
            active_policy,
            hidden_policy,
            trip,
            UserSavedPolicy(user_id=user.id, policy_id=active_policy.id),
            UserSavedPolicy(user_id=user.id, policy_id=hidden_policy.id),
            TripPolicy(trip_id=trip.id, policy_id=active_policy.id),
            TripPolicy(trip_id=trip.id, policy_id=hidden_policy.id),
        ]
    )
    sqlite_db_session.commit()
    return user


def test_policy_repository_list_excludes_hidden_rows(sqlite_db_session) -> None:
    add_visibility_policy_rows(sqlite_db_session)

    assert [policy.slug for policy in policy_repository.list_policies(sqlite_db_session)] == ["active-policy"]
    assert policy_repository.get_policy_by_slug(sqlite_db_session, "hidden-policy") is None
    assert policy_repository.get_policy_by_slug_any_status(sqlite_db_session, "hidden-policy").slug == "hidden-policy"


def test_policy_repository_saved_list_excludes_hidden_rows(sqlite_db_session) -> None:
    user = add_visibility_policy_rows(sqlite_db_session)

    assert [policy.slug for policy in policy_repository.list_saved_policies(sqlite_db_session, user_id=user.id)] == [
        "active-policy"
    ]


def test_policy_repository_applied_lists_exclude_hidden_rows(sqlite_db_session) -> None:
    user = add_visibility_policy_rows(sqlite_db_session)

    assert [policy.slug for policy in policy_repository.list_applied_policies(sqlite_db_session, user_id=user.id)] == [
        "active-policy"
    ]
    assert [
        link.policy.slug
        for link in policy_repository.list_applied_policy_links(sqlite_db_session, user_id=user.id)
    ] == ["active-policy"]


def test_add_policy_to_trip_rejects_hidden_policy_slug_in_db_path(sqlite_db_session) -> None:
    user = make_user(70, "Hidden Slug User")
    hidden_policy = Policy(
        id=710,
        slug="hidden-policy",
        title="Hidden policy",
        benefit_detail="2만원 할인",
        region="전국",
        status="hidden",
    )
    trip = Trip(
        id=711,
        owner_id=user.id,
        title="Hidden slug trip",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        region="전국",
        status="draft",
    )
    sqlite_db_session.add_all([user, hidden_policy, trip])
    sqlite_db_session.commit()

    with pytest.raises(trip_service.TripServiceError) as error:
        trip_service.add_policy_to_trip(sqlite_db_session, user, str(trip.id), "hidden-policy")

    assert error.value.status_code == 404
    assert error.value.detail == "Policy not found"
    assert sqlite_db_session.query(TripPolicy).count() == 0


def test_delete_trip_deletes_owned_numeric_trip_and_detaches_recommendations(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    detached: list[int] = []
    deleted: list[Trip] = []

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_owned_trip_by_id",
        lambda db, trip_id, user_id: trip
        if db is fake_db and trip_id == 7 and user_id == 1
        else None,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "detach_recommendations_from_trip",
        lambda _db, *, trip_id: detached.append(trip_id),
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "delete_trip",
        lambda _db, target_trip: deleted.append(target_trip),
    )

    payload = trip_service.delete_trip("7", fake_db, user)

    assert payload == {"tripId": "7", "deleted": True}
    assert detached == [7]
    assert deleted == [trip]
    assert fake_db.commits == 1


def test_delete_trip_returns_none_for_missing_or_unowned_trip(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    lookup_calls: list[int] = []

    def missing_lookup(_db, trip_id, _user_id):
        lookup_calls.append(trip_id)
        return None

    monkeypatch.setattr(trip_service.trip_repository, "get_owned_trip_by_id", missing_lookup)

    assert trip_service.delete_trip("001", fake_db, user) is None
    assert trip_service.delete_trip("7", fake_db, user) is None
    assert lookup_calls == [7]
    assert fake_db.commits == 0


def test_update_trip_status_persists_confirmed_status(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    trip.status = "draft"
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )

    payload = trip_service.update_trip_status(
        fake_db,
        user,
        "7",
        UpdateTripStatusRequest(status="confirmed"),
    )

    assert trip.status == "confirmed"
    assert payload["status"] == "confirmed"
    assert fake_db.commits == 1


def test_viewer_member_cannot_update_trip_status(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(2)
    trip = make_trip()
    trip.status = "draft"
    trip.members[0].role = "viewer"
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )

    try:
        trip_service.update_trip_status(
            fake_db,
            user,
            "7",
            UpdateTripStatusRequest(status="confirmed"),
        )
    except trip_service.TripServiceError as error:
        assert error.status_code == 403
        assert error.detail == "Trip edit permission required"
    else:
        raise AssertionError("expected TripServiceError")

    assert trip.status == "draft"
    assert fake_db.commits == 0


def test_viewer_member_cannot_add_policy_to_trip(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(2)
    trip = make_trip()
    trip.members[0].role = "viewer"
    policy = Policy(id=4, slug="travelmonth-58", title="Official benefit")
    added_links: list[dict[str, int]] = []
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )
    monkeypatch.setattr(
        trip_service.policy_repository,
        "get_policy_by_slug",
        lambda *_args, **_kwargs: policy,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "add_trip_policy",
        lambda _db, **kwargs: added_links.append(kwargs),
    )

    try:
        trip_service.add_policy_to_trip(fake_db, user, "7", "travelmonth-58")
    except trip_service.TripServiceError as error:
        assert error.status_code == 403
        assert error.detail == "Trip edit permission required"
    else:
        raise AssertionError("expected TripServiceError")

    assert added_links == []
    assert fake_db.commits == 0


def test_remove_policy_from_trip_deletes_existing_link(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    policy = trip.policies[0].policy
    removed_links: list[TripPolicy] = []

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )
    monkeypatch.setattr(
        trip_service.policy_repository,
        "get_policy_by_slug",
        lambda *_args, **_kwargs: policy,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_trip_policy",
        lambda *_args, **_kwargs: trip.policies[0],
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "remove_trip_policy",
        lambda _db, link: removed_links.append(link),
    )

    result = trip_service.remove_policy_from_trip(fake_db, user, "7", "fixture-policy")

    assert result == {"tripId": "7", "policyId": "fixture-policy", "added": False}
    assert removed_links == [trip.policies[0]]
    assert fake_db.commits == 1


def test_remove_policy_from_trip_is_idempotent_when_link_missing(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    policy = trip.policies[0].policy
    removed_links: list[TripPolicy] = []

    monkeypatch.setattr(trip_service.trip_repository, "get_accessible_trip_by_id", lambda *_args, **_kwargs: trip)
    monkeypatch.setattr(trip_service.policy_repository, "get_policy_by_slug", lambda *_args, **_kwargs: policy)
    monkeypatch.setattr(trip_service.trip_repository, "get_trip_policy", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(trip_service.trip_repository, "remove_trip_policy", lambda _db, link: removed_links.append(link))

    result = trip_service.remove_policy_from_trip(fake_db, user, "7", "fixture-policy")

    assert result == {"tripId": "7", "policyId": "fixture-policy", "added": False}
    assert removed_links == []
    assert fake_db.commits == 0


def test_add_policy_to_trip_resolves_stay_discount_alias_to_canonical(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    stay_policy = make_stay_policy()
    stay_record = make_stay_record()
    added_links: list[dict[str, int]] = []

    monkeypatch.setattr(trip_service.trip_repository, "get_accessible_trip_by_id", lambda *_args, **_kwargs: trip)
    monkeypatch.setattr(trip_service.policy_repository, "list_policies", lambda db: [stay_policy] if db is fake_db else [])
    monkeypatch.setattr(
        trip_service.external_source_repository,
        "get_external_source_record_by_id",
        lambda db, record_id: stay_record if db is fake_db and record_id == 88 else None,
    )
    monkeypatch.setattr(trip_service.policy_repository, "get_policy_by_slug", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(trip_service.trip_repository, "get_trip_policy", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        trip_service.trip_repository,
        "add_trip_policy",
        lambda _db, **kwargs: added_links.append(kwargs),
    )

    result = trip_service.add_policy_to_trip(fake_db, user, "7", "stay-discount-gangwon-goseong")

    assert result == {"tripId": "7", "policyId": "stay-discount-gangwon-goseong", "added": True}
    assert added_links == [{"trip_id": 7, "policy_id": 88}]
    assert fake_db.commits == 1


def test_add_policy_to_trip_rejects_hidden_stay_discount_alias(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    hidden_stay_policy = make_stay_policy()
    hidden_stay_policy.status = "hidden"
    stay_record = make_stay_record()
    added_links: list[dict[str, int]] = []

    monkeypatch.setattr(trip_service.trip_repository, "get_accessible_trip_by_id", lambda *_args, **_kwargs: trip)
    monkeypatch.setattr(
        trip_service.policy_repository,
        "list_policies",
        lambda db: [hidden_stay_policy] if db is fake_db else [],
    )
    monkeypatch.setattr(
        trip_service.external_source_repository,
        "get_external_source_record_by_id",
        lambda db, record_id: stay_record if db is fake_db and record_id == 88 else None,
    )
    monkeypatch.setattr(trip_service.policy_repository, "get_policy_by_slug", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        trip_service.trip_repository,
        "add_trip_policy",
        lambda _db, **kwargs: added_links.append(kwargs),
    )

    with pytest.raises(trip_service.TripServiceError) as error:
        trip_service.add_policy_to_trip(fake_db, user, "7", "stay-discount-gangwon-goseong")

    assert error.value.status_code == 404
    assert error.value.detail == "Policy not found"
    assert added_links == []
    assert fake_db.commits == 0


def test_remove_policy_from_trip_resolves_stay_discount_alias_to_canonical(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    stay_policy = make_stay_policy()
    stay_record = make_stay_record()
    link = TripPolicy(id=100, trip_id=7, policy_id=88)
    link.policy = stay_policy
    removed_links: list[TripPolicy] = []

    monkeypatch.setattr(trip_service.trip_repository, "get_accessible_trip_by_id", lambda *_args, **_kwargs: trip)
    monkeypatch.setattr(trip_service.policy_repository, "list_policies", lambda db: [stay_policy] if db is fake_db else [])
    monkeypatch.setattr(
        trip_service.external_source_repository,
        "get_external_source_record_by_id",
        lambda db, record_id: stay_record if db is fake_db and record_id == 88 else None,
    )
    monkeypatch.setattr(trip_service.policy_repository, "get_policy_by_slug", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_trip_policy",
        lambda _db, **kwargs: link if kwargs["trip_id"] == 7 and kwargs["policy_id"] == 88 else None,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "remove_trip_policy",
        lambda _db, removed_link: removed_links.append(removed_link),
    )

    result = trip_service.remove_policy_from_trip(fake_db, user, "7", "stay-discount-gangwon-samcheok")

    assert result == {"tripId": "7", "policyId": "stay-discount-gangwon-samcheok", "added": False}
    assert removed_links == [link]
    assert fake_db.commits == 1


def test_add_place_to_trip_day_persists_place_and_returns_updated_trip(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip
        if db is fake_db and trip_id == 7 and user_id == 1
        else None,
    )

    def add_place_stub(_db, **kwargs):
        captured.update(kwargs)
        place = TripPlace(
            id=2,
            trip_day_id=kwargs["trip_day_id"],
            place_name=kwargs["place_name"],
            address=kwargs["address"],
            latitude=Decimal(str(kwargs["latitude"])) if kwargs["latitude"] is not None else None,
            longitude=Decimal(str(kwargs["longitude"])) if kwargs["longitude"] is not None else None,
            visit_time=kwargs["visit_time"],
            order_num=kwargs["order_num"],
            memo=kwargs["memo"],
        )
        place.category_group_code = kwargs["category_group_code"]
        place.category_group_name = kwargs["category_group_name"]
        place.place_url = kwargs["place_url"]
        place.source_provider = kwargs["source_provider"]
        place.external_place_id = kwargs["external_place_id"]
        trip.days[0].places.append(place)
        return place

    monkeypatch.setattr(trip_service.trip_repository, "add_trip_place", add_place_stub)

    payload = trip_service.add_place_to_trip_day(
        fake_db,
        user,
        "7",
        1,
        CreateTripPlaceRequest(
            expectedRevision=1,
            time="14:30",
            label="Cafe stop",
            meta="Dessert",
            address="Gangwon road 1",
            latitude=38.1,
            longitude=128.6,
            category="Food",
            categoryCode="FD6",
            placeUrl="http://place.map.kakao.com/food-1",
            sourceProvider="kakao_local",
            externalPlaceId="food-1",
        ),
    )

    assert captured["trip_day_id"] == 1
    assert captured["place_name"] == "Cafe stop"
    assert captured["visit_time"] == time(14, 30)
    assert captured["order_num"] == 2
    assert captured["address"] == "Gangwon road 1"
    assert captured["latitude"] == 38.1
    assert captured["longitude"] == 128.6
    assert captured["category_group_name"] == "Food"
    assert captured["category_group_code"] == "FD6"
    assert captured["place_url"] == "http://place.map.kakao.com/food-1"
    assert captured["source_provider"] == "kakao_local"
    assert captured["external_place_id"] == "food-1"
    added = payload["days"][1][-1]
    assert added["id"] == "2"
    assert added["time"] == "14:30"
    assert added["label"] == "Cafe stop"
    assert added["meta"] == "Dessert"
    assert added["address"] == "Gangwon road 1"
    assert added["categoryCode"] == "FD6"
    assert added["sourceProvider"] == "kakao_local"
    assert added["externalPlaceId"] == "food-1"
    assert fake_db.commits == 1


class FakeRecommendationProvider:
    def __init__(self, candidates_by_code):
        self.candidates_by_code = candidates_by_code

    def search(self, *, area_name: str, city: str, category_group_code: str):
        return list(self.candidates_by_code.get(category_group_code, []))


def _recommendation_candidate(external_id: str, title: str, category_code: str = "FD6"):
    return itinerary_recommendations.ExternalPlaceCandidate(
        source_provider="kakao_local",
        external_place_id=external_id,
        title=title,
        category_group_code=category_code,
        category_group_name="Food" if category_code == "FD6" else "Attraction",
        address="Jeju road 1",
        latitude=33.4,
        longitude=126.5,
        place_url=f"http://place.map.kakao.com/{external_id}",
    )


def test_list_recommendations_excludes_existing_trip_places(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    trip.days[0].places[0].source_provider = "kakao_local"
    trip.days[0].places[0].external_place_id = "same-place"
    trip.days[0].places[0].place_name = "Existing Food"
    provider = FakeRecommendationProvider(
        {
            "FD6": [
                _recommendation_candidate("same-place", "Different title"),
                _recommendation_candidate("new-title", "Existing Food"),
                _recommendation_candidate("new-food", "New Food"),
            ]
        }
    )

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip
        if db is fake_db and trip_id == 7 and user_id == 1
        else None,
    )
    monkeypatch.setattr(trip_service, "_build_external_place_provider", lambda: provider)

    items = trip_service.list_recommendations(fake_db, user, "7")

    assert items is not None
    assert [item["externalPlaceId"] for item in items] == ["new-food"]
    assert items[0]["categoryGroup"] == "food"
    assert items[0]["suggestedDay"] == 1
    assert items[0]["sourceType"] == "freshCandidate"


def test_list_recommendations_marks_saved_summary_fallback(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    stored_recommendation = Recommendation(
        id=1,
        user_id=user.id,
        trip_id=trip.id,
        query="trip_create",
        result=[
            {
                "label": "attraction",
                "title": "Saved summary spot",
                "meta": "Day 1",
                "reason": "일정 생성 시 저장된 추천 요약입니다.",
            }
        ],
    )

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip
        if db is fake_db and trip_id == 7 and user_id == 1
        else None,
    )
    monkeypatch.setattr(trip_service, "_build_external_place_provider", lambda: None)
    monkeypatch.setattr(
        trip_service.trip_repository,
        "list_recommendations",
        lambda db, trip_id, user_id: [stored_recommendation]
        if db is fake_db and trip_id == 7 and user_id == 1
        else [],
    )

    items = trip_service.list_recommendations(fake_db, user, "7")

    assert items is not None
    assert items[0]["title"] == "Saved summary spot"
    assert items[0]["sourceType"] == "savedSummary"


def test_list_recommendations_backfills_to_ten_after_duplicate_filtering(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    trip.days[0].places[0].source_provider = "kakao_local"
    trip.days[0].places[0].external_place_id = "spot-1"
    trip.days[0].places[0].place_name = "Spot 1"
    provider = FakeRecommendationProvider(
        {
            "AT4": [
                _recommendation_candidate(f"spot-{index}", f"Spot {index}", "AT4")
                for index in range(1, 8)
            ],
            "FD6": [
                _recommendation_candidate(f"food-{index}", f"Food {index}", "FD6")
                for index in range(1, 8)
            ],
            "CE7": [
                _recommendation_candidate(f"cafe-{index}", f"Cafe {index}", "CE7")
                for index in range(1, 5)
            ],
            "AD5": [
                _recommendation_candidate(f"stay-{index}", f"Stay {index}", "AD5")
                for index in range(1, 5)
            ],
        }
    )

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip
        if db is fake_db and trip_id == 7 and user_id == 1
        else None,
    )
    monkeypatch.setattr(trip_service, "_build_external_place_provider", lambda: provider)

    items = trip_service.list_recommendations(fake_db, user, "7")

    assert items is not None
    counts: dict[str, int] = {}
    for item in items:
        counts[str(item["categoryGroup"])] = counts.get(str(item["categoryGroup"]), 0) + 1
    assert len(items) >= 10
    assert all(item["externalPlaceId"] != "spot-1" for item in items)
    assert counts["attraction"] >= 3
    assert counts["food"] >= 3
    assert counts["stay"] >= 2


def test_list_recommendations_filters_duplicates_before_final_ten_slice(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    duplicate_specs = [
        *(("spot", index, "Spot") for index in range(1, 4)),
        *(("food", index, "Food") for index in range(1, 4)),
        *(("stay", index, "Stay") for index in range(1, 3)),
        ("spot", 4, "Spot"),
    ]
    trip.days[0].places = [
        TripPlace(
            id=index,
            trip_day_id=1,
            place_name=f"{title_prefix} {candidate_index}",
            visit_time=time(9, 0),
            order_num=index,
            source_provider="kakao_local",
            external_place_id=f"{prefix}-{candidate_index}",
        )
        for index, (prefix, candidate_index, title_prefix) in enumerate(duplicate_specs, start=1)
    ]
    provider = FakeRecommendationProvider(
        {
            "AT4": [
                _recommendation_candidate(f"spot-{index}", f"Spot {index}", "AT4")
                for index in range(1, 7)
            ],
            "FD6": [
                _recommendation_candidate(f"food-{index}", f"Food {index}", "FD6")
                for index in range(1, 7)
            ],
            "CE7": [
                _recommendation_candidate(f"cafe-{index}", f"Cafe {index}", "CE7")
                for index in range(1, 7)
            ],
            "AD5": [
                _recommendation_candidate(f"stay-{index}", f"Stay {index}", "AD5")
                for index in range(1, 6)
            ],
        }
    )

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip
        if db is fake_db and trip_id == 7 and user_id == 1
        else None,
    )
    monkeypatch.setattr(trip_service, "_build_external_place_provider", lambda: provider)

    items = trip_service.list_recommendations(fake_db, user, "7")

    assert items is not None
    assert len(items) >= 10
    returned_ids = {item["externalPlaceId"] for item in items}
    duplicate_ids = {f"{prefix}-{index}" for prefix, index, _title_prefix in duplicate_specs}
    assert returned_ids.isdisjoint(duplicate_ids)


def test_list_recommendations_assigns_suggested_day_round_robin(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    day_two = TripDay(id=2, trip_id=7, day_number=2, date=date(2026, 6, 16))
    day_two.places = []
    trip.days.append(day_two)
    provider = FakeRecommendationProvider(
        {
            "FD6": [
                _recommendation_candidate("food-1", "Food 1"),
                _recommendation_candidate("food-2", "Food 2"),
            ],
            "AT4": [_recommendation_candidate("spot-1", "Spot 1", "AT4")],
        }
    )

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip
        if db is fake_db and trip_id == 7 and user_id == 1
        else None,
    )
    monkeypatch.setattr(trip_service, "_build_external_place_provider", lambda: provider)

    items = trip_service.list_recommendations(fake_db, user, "7")

    assert items is not None
    assert [item["suggestedDay"] for item in items[:3]] == [1, 2, 1]


def test_update_trip_place_changes_existing_place(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )

    payload = trip_service.update_trip_place(
        fake_db,
        user,
        "7",
        1,
        UpdateTripPlaceRequest(expectedRevision=1, time="10:15", label="Updated peak", meta="New memo"),
    )

    updated = payload["days"][1][0]
    assert updated["id"] == "1"
    assert updated["time"] == "10:15"
    assert updated["label"] == "Updated peak"
    assert updated["meta"] == "New memo"
    assert payload["revision"] == 2
    assert fake_db.commits == 1


def test_update_trip_place_rejects_stale_revision_without_mutating(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "bump_trip_revision_if_current",
        lambda *_args, **_kwargs: False,
    )

    with pytest.raises(trip_service.TripServiceError) as error:
        trip_service.update_trip_place(
            fake_db,
            user,
            "7",
            1,
            UpdateTripPlaceRequest(expectedRevision=1, label="Stale edit"),
        )

    assert error.value.status_code == 409
    assert error.value.detail == "Trip has changed. Refresh before saving."
    assert trip.days[0].places[0].place_name == "Sunrise peak"
    assert fake_db.commits == 0


def test_move_trip_place_reorders_places_within_same_day(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    trip.days[0].places.append(
        TripPlace(
            id=2,
            trip_day_id=1,
            place_name="Cafe stop",
            visit_time=time(14, 30),
            order_num=2,
            memo="Dessert",
        )
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )

    payload = trip_service.move_trip_place(
        fake_db,
        user,
        "7",
        2,
        MoveTripPlaceRequest(expectedRevision=1, dayNumber=1, position=1),
    )

    assert [place.order_num for place in trip.days[0].places] == [1, 2]
    assert payload["days"][1][0]["label"] == "Cafe stop"
    assert payload["days"][1][1]["label"] == "Sunrise peak"
    assert fake_db.commits == 1


def test_move_trip_place_moves_place_to_another_day(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    second_day = TripDay(id=2, trip_id=7, day_number=2, date=date(2026, 6, 16))
    second_day.places = [
        TripPlace(
            id=2,
            trip_day_id=2,
            place_name="Lunch stop",
            visit_time=time(12, 0),
            order_num=1,
            memo="Food",
        )
    ]
    trip.days.append(second_day)
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )

    payload = trip_service.move_trip_place(
        fake_db,
        user,
        "7",
        1,
        MoveTripPlaceRequest(expectedRevision=1, dayNumber=2, position=2),
    )

    moved_place = second_day.places[1]
    assert trip.days[0].places == []
    assert moved_place.id == 1
    assert moved_place.trip_day_id == 2
    assert [place.order_num for place in second_day.places] == [1, 2]
    assert payload["days"][2][-1]["label"] == "Sunrise peak"
    assert fake_db.commits == 1


def test_delete_trip_place_removes_existing_place(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    deleted: list[TripPlace] = []
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )

    def delete_place_stub(_db, place):
        deleted.append(place)
        trip.days[0].places.remove(place)

    monkeypatch.setattr(trip_service.trip_repository, "delete_trip_place", delete_place_stub)

    payload = trip_service.delete_trip_place(fake_db, user, "7", 1, 1)

    assert deleted[0].id == 1
    assert payload["days"][1] == []
    assert fake_db.commits == 1


def test_trip_place_crud_returns_404_for_missing_day_or_place(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )

    for action in (
        lambda: trip_service.add_place_to_trip_day(
            fake_db,
            user,
            "7",
            99,
            CreateTripPlaceRequest(expectedRevision=1, time="12:00", label="Missing day", meta=""),
        ),
        lambda: trip_service.update_trip_place(
            fake_db,
            user,
            "7",
            999,
            UpdateTripPlaceRequest(expectedRevision=1, label="Missing place"),
        ),
        lambda: trip_service.delete_trip_place(fake_db, user, "7", 999, 1),
        lambda: trip_service.move_trip_place(
            fake_db,
            user,
            "7",
            1,
            MoveTripPlaceRequest(expectedRevision=1, dayNumber=99, position=1),
        ),
    ):
        try:
            action()
        except trip_service.TripServiceError as error:
            assert error.status_code == 404
            assert error.detail == "Trip not found"
        else:
            raise AssertionError("expected TripServiceError")

    assert fake_db.commits == 0


def test_repository_add_trip_place_accepts_kakao_metadata(sqlite_db_session) -> None:
    user = UserModel(
        email="owner@example.com",
        password_hash="hashed",
        nickname="Owner",
        onboarding_completed=True,
    )
    sqlite_db_session.add(user)
    sqlite_db_session.flush()

    trip = trip_service.trip_repository.create_trip(
        sqlite_db_session,
        owner_id=user.id,
        title="속초",
        start_date=date(2026, 7, 12),
        end_date=date(2026, 7, 13),
        status="draft",
        region="강원 속초시",
        travel_area_id="gangwon-sokcho-goseong-yangyang",
        participant_count=2,
        description="식사 위주",
    )
    trip_day = trip_service.trip_repository.add_trip_day(
        sqlite_db_session,
        trip_id=trip.id,
        day_number=1,
        date_value=date(2026, 7, 12),
    )

    place = trip_service.trip_repository.add_trip_place(
        sqlite_db_session,
        trip_day_id=trip_day.id,
        place_name="속초 중앙시장",
        visit_time=time(13, 0),
        order_num=1,
        memo="식사 추천 장소",
        address="강원 속초시 중앙로 47",
        latitude=Decimal("38.2041234"),
        longitude=Decimal("128.5901234"),
        source_provider="kakao_local",
        external_place_id="12345",
        category_group_code="FD6",
        category_group_name="음식점",
        place_url="http://place.map.kakao.com/12345",
    )

    assert place.source_provider == "kakao_local"
    assert place.external_place_id == "12345"
    assert place.category_group_code == "FD6"
    assert place.category_group_name == "음식점"
    assert place.place_url == "http://place.map.kakao.com/12345"
    assert str(place.latitude) == "38.2041234"
    assert str(place.longitude) == "128.5901234"


def test_repository_bump_trip_revision_if_current_is_atomic(sqlite_db_session) -> None:
    user = UserModel(
        email="owner-revision@example.com",
        password_hash="hashed",
        nickname="Owner",
        onboarding_completed=True,
    )
    sqlite_db_session.add(user)
    sqlite_db_session.flush()
    trip = trip_service.trip_repository.create_trip(
        sqlite_db_session,
        owner_id=user.id,
        title="Revision trip",
        start_date=date(2026, 7, 12),
        end_date=date(2026, 7, 13),
        status="draft",
        region="강원",
        travel_area_id=None,
        participant_count=1,
        description=None,
    )
    sqlite_db_session.commit()

    assert trip.revision == 1
    assert trip_service.trip_repository.bump_trip_revision_if_current(
        sqlite_db_session,
        trip_id=trip.id,
        expected_revision=1,
    ) is True
    assert trip_service.trip_repository.bump_trip_revision_if_current(
        sqlite_db_session,
        trip_id=trip.id,
        expected_revision=1,
    ) is False
    sqlite_db_session.commit()
    sqlite_db_session.refresh(trip)
    assert trip.revision == 2


def test_move_trip_place_rejects_invalid_position(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    trip = make_trip()
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )

    try:
        trip_service.move_trip_place(
            fake_db,
            user,
            "7",
            1,
            MoveTripPlaceRequest(expectedRevision=1, dayNumber=1, position=2),
        )
    except trip_service.TripServiceError as error:
        assert error.status_code == 422
        assert error.detail == "Invalid place position"
    else:
        raise AssertionError("expected TripServiceError")

    assert fake_db.commits == 0


def test_viewer_member_cannot_edit_trip_places(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(2)
    trip = make_trip()
    trip.members[0].role = "viewer"
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: trip,
    )

    for action in (
        lambda: trip_service.add_place_to_trip_day(
            fake_db,
            user,
            "7",
            1,
            CreateTripPlaceRequest(expectedRevision=1, time="12:00", label="Viewer add", meta=""),
        ),
        lambda: trip_service.update_trip_place(
            fake_db,
            user,
            "7",
            1,
            UpdateTripPlaceRequest(expectedRevision=1, label="Viewer edit"),
        ),
        lambda: trip_service.delete_trip_place(fake_db, user, "7", 1, 1),
        lambda: trip_service.move_trip_place(
            fake_db,
            user,
            "7",
            1,
            MoveTripPlaceRequest(expectedRevision=1, dayNumber=1, position=1),
        ),
    ):
        try:
            action()
        except trip_service.TripServiceError as error:
            assert error.status_code == 403
            assert error.detail == "Trip edit permission required"
        else:
            raise AssertionError("expected TripServiceError")

    assert fake_db.commits == 0


def test_recommendation_mapper_ignores_invalid_items() -> None:
    items = trip_service._recommendation_items(
        [
            {"label": "CA", "title": "Cafe", "meta": "Day 2", "reason": "Good route"},
            "invalid",
        ]
    )

    assert items == [
        {
            "label": "CA",
            "title": "Cafe",
            "meta": "Day 2",
            "reason": "Good route",
            "sourceType": "savedSummary",
        }
    ]


def test_invite_to_api_computes_display_flags() -> None:
    now = trip_service.security.utc_now_naive()
    invite = make_invite(role="viewer")
    invite.created_at = now - timedelta(days=1)
    invite.expires_at = now + timedelta(days=30)

    payload = trip_service.invite_to_api(invite, trip_id=7)

    assert payload["id"] == "9"
    assert payload["tripId"] == "7"
    assert payload["inviteUrl"] == "http://127.0.0.1:5173/invites/abc/accept"
    assert payload["invited"] is True
    assert payload["copied"] is False
    assert payload["role"] == "viewer"
    assert payload["alreadyMember"] is False


def test_invite_to_api_uses_public_frontend_base_url(monkeypatch) -> None:
    class PublicSettings:
        def frontend_base_url(self) -> str:
            return "https://travel-hunter.co.kr"

    monkeypatch.setattr(trip_service, "settings", PublicSettings())
    now = trip_service.security.utc_now_naive()
    invite = make_invite(role="viewer")
    invite.created_at = now - timedelta(days=1)
    invite.expires_at = now + timedelta(days=30)

    payload = trip_service.invite_to_api(invite, trip_id=7)

    assert payload["inviteUrl"] == "https://travel-hunter.co.kr/invites/abc/accept"


def test_get_invite_state_returns_role_specific_links(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(2, "Editor")
    trip = make_trip()
    viewer_invite = make_invite(role="viewer")
    viewer_invite.id = 10
    viewer_invite.invite_token = "viewer-token"
    editor_invite = make_invite(role="editor")
    editor_invite.id = 11
    editor_invite.invite_token = "editor-token"

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip
        if db is fake_db and trip_id == 7 and user_id == 2
        else None,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_latest_active_invite",
        lambda db, **kwargs: {"viewer": viewer_invite, "editor": editor_invite}.get(kwargs.get("role"))
        if db is fake_db and kwargs["trip_id"] == 7
        else None,
    )

    payload = trip_service.get_invite_state(fake_db, user, "7")

    assert payload is not None
    assert payload["tripId"] == "7"
    assert payload["viewer"]["role"] == "viewer"
    assert payload["editor"]["role"] == "editor"
    assert payload["viewer"]["inviteToken"] != payload["editor"]["inviteToken"]
    assert fake_db.commits == 1


def test_confirm_invite_sent_preserves_other_role_invite_token(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(2, "Editor")
    trip = make_trip()
    existing_editor = make_invite(role="editor")
    existing_editor.invite_token = "editor-token"
    created_invites: list[TripInvite] = []

    monkeypatch.setattr(
        trip_service.trip_repository, "get_accessible_trip_by_id", lambda db, trip_id, user_id: trip
        if db is fake_db and trip_id == 7 and user_id == 2
        else None,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_latest_active_invite",
        lambda db, **kwargs: existing_editor
        if db is fake_db and kwargs["trip_id"] == 7 and kwargs.get("role") == "editor"
        else None,
    )

    def create_invite_stub(_db, **kwargs):
        invite = make_invite(role=kwargs["role"])
        invite.id = 10 + len(created_invites)
        invite.invite_token = kwargs["invite_token"]
        invite.expires_at = kwargs["expires_at"]
        created_invites.append(invite)
        return invite

    monkeypatch.setattr(trip_service.trip_repository, "create_invite", create_invite_stub)
    monkeypatch.setattr(trip_service, "_new_invite_token", lambda: "viewer-token")

    viewer_payload = trip_service.confirm_invite_sent(fake_db, user, "7", "viewer")
    editor_payload = trip_service.confirm_invite_sent(fake_db, user, "7", "editor")

    assert viewer_payload is not None
    assert editor_payload is not None
    assert viewer_payload["role"] == "viewer"
    assert viewer_payload["inviteToken"] == "viewer-token"
    assert editor_payload["role"] == "editor"
    assert editor_payload["inviteToken"] == "editor-token"
    assert existing_editor.role == "editor"
    assert len(created_invites) == 1
    assert fake_db.commits == 2


def test_confirm_invite_sent_rejects_viewer(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(2, "Viewer")
    trip = make_trip()
    trip.members[0].role = "viewer"
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip
        if db is fake_db and trip_id == 7 and user_id == 2
        else None,
    )

    try:
        trip_service.confirm_invite_sent(fake_db, user, "7", "editor")
        raise AssertionError("expected TripServiceError")
    except trip_service.TripServiceError as error:
        assert error.status_code == 403
        assert error.detail == "Trip edit permission required"
    assert fake_db.commits == 0


def test_send_invite_email_returns_sent_status(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(2, "Editor")
    trip = make_trip()
    invite = make_invite(role="viewer")
    invite.invite_token = "viewer-token"
    sent_payload: dict[str, str] = {}
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip
        if db is fake_db and trip_id == 7 and user_id == 2
        else None,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_latest_active_invite",
        lambda _db, **kwargs: invite if kwargs.get("role") == "viewer" else None,
    )
    monkeypatch.setattr(
        trip_service.email_service,
        "send_trip_invite_email",
        lambda **kwargs: sent_payload.update(kwargs),
    )

    result = trip_service.send_invite_email(
        fake_db,
        user,
        "7",
        SendInviteEmailRequest(email="friend@example.com", role="viewer"),
    )

    assert result is not None
    assert result["deliveryStatus"] == "sent"
    assert result["invite"]["role"] == "viewer"
    assert sent_payload["to_email"] == "friend@example.com"
    assert sent_payload["invite_url"].endswith("/invites/viewer-token/accept")
    assert invite.role == "viewer"
    assert fake_db.commits == 1


def test_send_invite_email_rejects_viewer(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(2, "Viewer")
    trip = make_trip()
    trip.members[0].role = "viewer"
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip
        if db is fake_db and trip_id == 7 and user_id == 2
        else None,
    )

    try:
        trip_service.send_invite_email(
            fake_db,
            user,
            "7",
            SendInviteEmailRequest(email="friend@example.com", role="viewer"),
        )
        raise AssertionError("expected TripServiceError")
    except trip_service.TripServiceError as error:
        assert error.status_code == 403
        assert error.detail == "Trip edit permission required"

    assert fake_db.commits == 0


def test_send_invite_email_returns_fallback_when_smtp_not_configured(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(2, "Editor")
    trip = make_trip()
    invite = make_invite(role="editor")
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip
        if db is fake_db and trip_id == 7 and user_id == 2
        else None,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_latest_active_invite",
        lambda _db, **kwargs: invite if kwargs.get("role") == "editor" else None,
    )

    def raise_not_configured(**_kwargs):
        raise trip_service.email_service.EmailNotConfiguredError("Email delivery is not configured")

    monkeypatch.setattr(trip_service.email_service, "send_trip_invite_email", raise_not_configured)

    result = trip_service.send_invite_email(
        fake_db,
        user,
        "7",
        SendInviteEmailRequest(email="friend@example.com"),
    )

    assert result is not None
    assert result["deliveryStatus"] == "notConfigured"
    assert result["invite"]["inviteUrl"].endswith("/invites/abc/accept")
    assert fake_db.commits == 1


def install_create_trip_stubs(monkeypatch, *, policy: Policy | None = None):
    captured: dict[str, object] = {"trip_days": [], "trip_places": [], "recommendations": []}
    created_trip = make_trip()
    created_trip.id = 11

    def create_trip_stub(db, **kwargs):
        captured["create_trip"] = kwargs
        created_trip.status = kwargs["status"]
        created_trip.title = kwargs["title"]
        created_trip.start_date = kwargs["start_date"]
        created_trip.end_date = kwargs["end_date"]
        created_trip.region = kwargs["region"]
        created_trip.travel_area_id = kwargs["travel_area_id"]
        created_trip.participant_count = kwargs["participant_count"]
        created_trip.description = kwargs["description"]
        return created_trip

    def add_trip_day_stub(_db, *, trip_id, day_number, date_value):
        captured["trip_days"].append(
            {
                "trip_id": trip_id,
                "day_number": day_number,
                "date_value": date_value,
            }
        )
        return TripDay(id=day_number, trip_id=trip_id, day_number=day_number, date=date_value)

    def add_trip_place_stub(_db, **kwargs):
        captured["trip_places"].append(kwargs)

    def add_recommendation_stub(_db, **kwargs):
        captured["recommendations"].append(kwargs)

    monkeypatch.setattr(trip_service.trip_repository, "create_trip", create_trip_stub)
    monkeypatch.setattr(trip_service.trip_repository, "add_trip_member", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(trip_service.trip_repository, "add_trip_day", add_trip_day_stub)
    monkeypatch.setattr(trip_service.trip_repository, "add_trip_place", add_trip_place_stub)
    monkeypatch.setattr(trip_service.trip_repository, "add_recommendation", add_recommendation_stub)
    monkeypatch.setattr(trip_service, "_ensure_invite", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda *_args, **_kwargs: created_trip,
    )
    monkeypatch.setattr(trip_service.policy_repository, "get_policy_by_slug", lambda *_args, **_kwargs: policy)

    def add_trip_policy_stub(_db, **kwargs):
        captured["add_trip_policy"] = kwargs
        if policy is not None and kwargs["policy_id"] == policy.id:
            link = TripPolicy(id=99, trip_id=kwargs["trip_id"], policy_id=policy.id)
            link.policy = policy
            created_trip.policies = [link]

    monkeypatch.setattr(trip_service.trip_repository, "add_trip_policy", add_trip_policy_stub)
    return captured


def test_create_trip_with_travel_area_id_stores_resolved_area(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    captured = install_create_trip_stubs(monkeypatch)
    area = SimpleNamespace(
        id="gangwon-sokcho-goseong-yangyang",
        name="Sokcho-Goseong-Yangyang",
    )
    monkeypatch.setattr(trip_service, "get_travel_area", lambda area_id: area if area_id == area.id else None)

    created = trip_service.create_trip(
        fake_db,
        user,
        CreateTripRequest(
            travelAreaId="gangwon-sokcho-goseong-yangyang",
            style="Sea",
            durationDays=2,
        ),
    )

    assert created["travelAreaId"] == "gangwon-sokcho-goseong-yangyang"
    assert "Sokcho-Goseong-Yangyang" in created["title"]
    assert captured["create_trip"]["region"] == "Sokcho-Goseong-Yangyang"
    assert captured["create_trip"]["travel_area_id"] == "gangwon-sokcho-goseong-yangyang"
    assert captured["create_trip"]["participant_count"] == 1


def test_kakao_itinerary_provider_queries_multiple_keywords_and_dedupes() -> None:
    class FakeKakaoClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def search_keyword(self, *, query: str, category_group_code: str):
            self.calls.append({"query": query, "category_group_code": category_group_code})
            if len(self.calls) == 1:
                return [
                    KakaoLocalPlace(
                        external_place_id="same-id",
                        name="Same place",
                        category_name="Food",
                        category_group_code="FD6",
                        category_group_name="Food",
                        phone="051-123-4567",
                        address="Busan road",
                        latitude=35.1,
                        longitude=129.1,
                        place_url="http://place.map.kakao.com/same-id",
                    )
                ]
            return [
                KakaoLocalPlace(
                    external_place_id="same-id",
                    name="Same place duplicate",
                    category_name="Food",
                    category_group_code="FD6",
                    category_group_name="Food",
                    phone="051-123-4567",
                    address="Busan road",
                    latitude=35.1,
                    longitude=129.1,
                    place_url="http://place.map.kakao.com/same-id",
                ),
                KakaoLocalPlace(
                    external_place_id=f"new-{len(self.calls)}",
                    name=f"New place {len(self.calls)}",
                    category_name="Food",
                    category_group_code="FD6",
                    category_group_name="Food",
                    phone="051-987-6543",
                    address="Busan road",
                    latitude=35.2,
                    longitude=129.2,
                    place_url=f"http://place.map.kakao.com/new-{len(self.calls)}",
                ),
            ]

    client = FakeKakaoClient()
    provider = trip_service.KakaoItineraryPlaceProvider(client)

    candidates = provider.search(area_name="Busan", city="Busan", category_group_code="FD6")

    assert len(client.calls) == 2
    assert all(call["category_group_code"] == "FD6" for call in client.calls)
    assert [candidate.external_place_id for candidate in candidates] == ["same-id", "new-2"]
    assert candidates[0].phone == "051-123-4567"
    assert candidates[1].phone == "051-987-6543"


def test_create_trip_persists_participant_count_without_fake_members(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    captured = install_create_trip_stubs(monkeypatch)

    created = trip_service.create_trip(
        fake_db,
        user,
        CreateTripRequest(region="Busan", participantCount=4, durationDays=2),
    )

    assert created["participantCount"] == 4
    assert created["people"] == ["Test User", "Minseo"]
    assert captured["create_trip"]["participant_count"] == 4


def test_create_trip_request_allows_ten_participants() -> None:
    request = CreateTripRequest(region="Busan", participantCount=10, durationDays=2)

    assert request.participantCount == 10


def test_create_trip_request_rejects_more_than_ten_participants() -> None:
    with pytest.raises(ValidationError):
        CreateTripRequest(region="Busan", participantCount=11, durationDays=2)


def test_create_trip_with_unknown_travel_area_id_returns_400(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    monkeypatch.setattr(trip_service, "get_travel_area", lambda _area_id: None)

    with pytest.raises(trip_service.TripServiceError) as error:
        trip_service.create_trip(
            fake_db,
            user,
            CreateTripRequest(travelAreaId="missing-area"),
        )

    assert error.value.status_code == 400
    assert error.value.detail == "Travel area not found"
    assert fake_db.commits == 0


def test_create_trip_region_only_remains_legacy_compatible(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    captured = install_create_trip_stubs(monkeypatch)

    created = trip_service.create_trip(
        fake_db,
        user,
        CreateTripRequest(region="Gangwon", durationDays=2),
    )

    assert created["travelAreaId"] is None
    assert "Gangwon" in created["title"]
    assert captured["create_trip"]["region"] == "Gangwon"
    assert captured["create_trip"]["travel_area_id"] is None


def test_create_trip_initializes_empty_days_without_recommendation_side_effects(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    captured = install_create_trip_stubs(monkeypatch)

    def fail_generate_auto_course(**_kwargs):
        raise AssertionError("create_trip must not generate itinerary recommendations")

    monkeypatch.setattr(trip_service.itinerary_recommendations, "generate_auto_course", fail_generate_auto_course)

    trip_service.create_trip(
        fake_db,
        user,
        CreateTripRequest(region="제주", style="자연", durationDays=2),
    )

    assert len(captured["trip_days"]) == 2
    assert captured["trip_places"] == []
    assert captured["recommendations"] == []
    assert fake_db.commits == 1


def test_create_trip_persists_empty_days_and_no_recommendation_rows_in_db(sqlite_db_session, monkeypatch) -> None:
    def fail_generate_auto_course(**_kwargs):
        raise AssertionError("create_trip must not generate itinerary recommendations")

    monkeypatch.setattr(trip_service.itinerary_recommendations, "generate_auto_course", fail_generate_auto_course)
    user = UserModel(
        email="empty-course@example.com",
        password_hash="hashed",
        nickname="Empty Course",
        onboarding_completed=True,
    )
    sqlite_db_session.add(user)
    sqlite_db_session.commit()

    created = trip_service.create_trip(
        sqlite_db_session,
        user,
        CreateTripRequest(
            region="부산",
            style="맛집",
            startDate=date(2026, 7, 12),
            endDate=date(2026, 7, 14),
            title="Busan empty-course verification",
        ),
    )

    assert created["title"] == "Busan empty-course verification"
    assert sorted(created["days"].keys()) == [1, 2, 3]
    assert all(day_places == [] for day_places in created["days"].values())
    assert sqlite_db_session.query(TripPlace).count() == 0
    assert sqlite_db_session.query(Recommendation).count() == 0


def test_create_trip_with_unsupported_region_still_initializes_empty_days(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    captured = install_create_trip_stubs(monkeypatch)

    trip_service.create_trip(
        fake_db,
        user,
        CreateTripRequest(region="미지원", style="자연", durationDays=2),
    )

    assert len(captured["trip_days"]) == 2
    assert captured["trip_places"] == []
    assert captured["recommendations"] == []
    assert fake_db.commits == 1


def test_create_trip_uses_region_and_style_payload(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    captured = install_create_trip_stubs(monkeypatch)

    result = trip_service.create_trip(
        fake_db,
        user,
        CreateTripRequest(region="Busan", style="Food"),
    )

    assert result["id"] == "11"
    assert result["status"] == "draft"
    assert captured["create_trip"]["status"] == "draft"
    assert captured["create_trip"]["title"] == "Busan 3일 여행"
    assert captured["create_trip"]["region"] == "Busan"
    assert captured["create_trip"]["description"] == "Food"
    assert fake_db.commits == 1


def test_create_trip_prefers_request_title_over_generated_title(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    captured = install_create_trip_stubs(monkeypatch)

    trip_service.create_trip(
        fake_db,
        user,
        CreateTripRequest(title="Custom Trip", region="Busan", durationDays=4),
    )

    assert captured["create_trip"]["title"] == "Custom Trip"


def test_create_trip_prefers_description_over_style(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    captured = install_create_trip_stubs(monkeypatch)

    trip_service.create_trip(
        fake_db,
        user,
        CreateTripRequest(region="Jeju", style="Food", description="Custom memo"),
    )

    assert captured["create_trip"]["description"] == "Custom memo"


def test_create_trip_uses_duration_days_for_date_range_and_days(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    captured = install_create_trip_stubs(monkeypatch)

    trip_service.create_trip(
        fake_db,
        user,
        CreateTripRequest(region="Jeju", style="Rest", durationDays=7),
    )

    assert captured["create_trip"]["start_date"] == date(2026, 6, 15)
    assert captured["create_trip"]["end_date"] == date(2026, 6, 21)
    assert captured["trip_days"] == [
        {"trip_id": 11, "day_number": 1, "date_value": date(2026, 6, 15)},
        {"trip_id": 11, "day_number": 2, "date_value": date(2026, 6, 16)},
        {"trip_id": 11, "day_number": 3, "date_value": date(2026, 6, 17)},
        {"trip_id": 11, "day_number": 4, "date_value": date(2026, 6, 18)},
        {"trip_id": 11, "day_number": 5, "date_value": date(2026, 6, 19)},
        {"trip_id": 11, "day_number": 6, "date_value": date(2026, 6, 20)},
        {"trip_id": 11, "day_number": 7, "date_value": date(2026, 6, 21)},
    ]


def test_create_trip_uses_request_date_range_for_dates_and_days(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    captured = install_create_trip_stubs(monkeypatch)

    trip_service.create_trip(
        fake_db,
        user,
        CreateTripRequest(region="Busan", style="Food", startDate=date(2026, 7, 12), endDate=date(2026, 7, 18)),
    )

    assert captured["create_trip"]["title"] == "Busan 7일 여행"
    assert captured["create_trip"]["start_date"] == date(2026, 7, 12)
    assert captured["create_trip"]["end_date"] == date(2026, 7, 18)
    assert captured["trip_days"] == [
        {"trip_id": 11, "day_number": 1, "date_value": date(2026, 7, 12)},
        {"trip_id": 11, "day_number": 2, "date_value": date(2026, 7, 13)},
        {"trip_id": 11, "day_number": 3, "date_value": date(2026, 7, 14)},
        {"trip_id": 11, "day_number": 4, "date_value": date(2026, 7, 15)},
        {"trip_id": 11, "day_number": 5, "date_value": date(2026, 7, 16)},
        {"trip_id": 11, "day_number": 6, "date_value": date(2026, 7, 17)},
        {"trip_id": 11, "day_number": 7, "date_value": date(2026, 7, 18)},
    ]


def test_create_trip_links_policy_when_policy_slug_is_present(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    policy = Policy(id=3, slug="fixture-policy", title="Vacation policy", benefit_amount=300000)
    captured = install_create_trip_stubs(monkeypatch, policy=policy)

    trip_service.create_trip(fake_db, user, CreateTripRequest(policySlug="fixture-policy"))

    assert captured["add_trip_policy"] == {"trip_id": 11, "policy_id": 3}


def test_create_trip_with_stay_discount_alias_links_canonical_and_echoes_alias(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    stay_policy = make_stay_policy()
    stay_record = make_stay_record()
    captured = install_create_trip_stubs(monkeypatch, policy=stay_policy)
    monkeypatch.setattr(trip_service.policy_repository, "list_policies", lambda db: [stay_policy] if db is fake_db else [])
    monkeypatch.setattr(
        trip_service.external_source_repository,
        "get_external_source_record_by_id",
        lambda db, record_id: stay_record if db is fake_db and record_id == 88 else None,
    )

    payload = trip_service.create_trip(
        fake_db,
        user,
        CreateTripRequest(policySlug="stay-discount-gyeongnam-goseong"),
    )

    assert captured["add_trip_policy"] == {"trip_id": 11, "policy_id": 88}
    assert payload["linkedPolicies"][0]["slug"] == "stay-discount-gyeongnam-goseong"
    assert payload["linkedPolicies"][0]["title"] == "[고성] 2026 대한민국 숙박세일 페스타 숙박 할인"
    assert payload["linkedPolicies"][0]["region"] == "경남"


def test_create_trip_rejects_unknown_policy_slug(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    install_create_trip_stubs(monkeypatch, policy=None)

    try:
        trip_service.create_trip(fake_db, user, CreateTripRequest(policySlug="missing-policy"))
    except trip_service.TripServiceError as error:
        assert error.status_code == 404
        assert error.detail == "Policy not found"
    else:
        raise AssertionError("expected TripServiceError")

    assert fake_db.commits == 0


def test_accept_invite_marks_acceptance_and_adds_member(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(3, "Friend")
    invite = make_invite(role="viewer")
    captured_membership: dict[str, object] = {}

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_active_invite_by_token",
        lambda db, *, invite_token, now: invite
        if db is fake_db and invite_token == "abc"
        else None,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_trip_member",
        lambda *_args, **_kwargs: None,
    )

    def add_member_stub(_db, **kwargs):
        captured_membership.update(kwargs)

    monkeypatch.setattr(trip_service.trip_repository, "add_trip_member", add_member_stub)

    payload = trip_service.accept_invite(fake_db, user, "abc")

    assert payload is not None
    assert payload["tripId"] == "7"
    assert payload["acceptedAt"] is not None
    assert payload["invited"] is True
    assert payload["alreadyMember"] is False
    assert invite.accepted_at is not None
    assert captured_membership == {"trip_id": 7, "user_id": 3, "role": "viewer"}
    assert fake_db.commits == 1


def test_accept_invite_is_idempotent_for_existing_member(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(3, "Friend")
    accepted_at = datetime(2026, 5, 5, 0, 0, 0)
    invite = make_invite(role="editor", accepted_at=accepted_at)
    added_members: list[dict[str, object]] = []

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_active_invite_by_token",
        lambda *_args, **_kwargs: invite,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_trip_member",
        lambda *_args, **_kwargs: TripMember(id=4, trip_id=7, user_id=3, role="editor"),
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "add_trip_member",
        lambda _db, **kwargs: added_members.append(kwargs),
    )

    payload = trip_service.accept_invite(fake_db, user, "abc")

    assert payload is not None
    assert payload["acceptedAt"] == "2026-05-05T00:00:00Z"
    assert payload["alreadyMember"] is True
    assert invite.accepted_at == accepted_at
    assert added_members == []
    assert fake_db.commits == 1


def test_accept_invite_rejects_new_member_when_actual_participants_are_full(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(11, "Late Friend")
    trip = make_trip()
    for user_id in range(3, 11):
        trip.members.append(
            TripMember(id=10 + user_id, trip_id=7, user_id=user_id, role="viewer"),
        )
    invite = make_invite(role="viewer")
    invite.trip = trip
    added_members: list[dict[str, object]] = []

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_active_invite_by_token",
        lambda *_args, **_kwargs: invite,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_trip_member",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "add_trip_member",
        lambda _db, **kwargs: added_members.append(kwargs),
    )

    with pytest.raises(trip_service.TripServiceError) as error:
        trip_service.accept_invite(fake_db, user, "abc")

    assert error.value.status_code == 409
    assert error.value.detail == "Trip participant limit reached"
    assert invite.accepted_at is None
    assert added_members == []
    assert fake_db.commits == 0


def test_accept_invite_stays_idempotent_for_existing_member_when_trip_is_full(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(10, "Existing Friend")
    trip = make_trip()
    existing_member = TripMember(id=30, trip_id=7, user_id=10, role="viewer")
    for user_id in range(3, 10):
        trip.members.append(
            TripMember(id=10 + user_id, trip_id=7, user_id=user_id, role="viewer"),
        )
    trip.members.append(existing_member)
    invite = make_invite(role="viewer")
    invite.trip = trip
    added_members: list[dict[str, object]] = []

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_active_invite_by_token",
        lambda *_args, **_kwargs: invite,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_trip_member",
        lambda *_args, **_kwargs: existing_member,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "add_trip_member",
        lambda _db, **kwargs: added_members.append(kwargs),
    )

    payload = trip_service.accept_invite(fake_db, user, "abc")

    assert payload is not None
    assert payload["alreadyMember"] is True
    assert invite.accepted_at is not None
    assert added_members == []
    assert fake_db.commits == 1


def test_accept_invite_treats_trip_owner_without_member_row_as_already_member(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(1, "Owner")
    trip = make_trip()
    trip.members = []
    invite = make_invite(role="viewer")
    invite.trip = trip
    added_members: list[dict[str, object]] = []

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_active_invite_by_token",
        lambda *_args, **_kwargs: invite,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_trip_member",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        trip_service.trip_repository,
        "add_trip_member",
        lambda _db, **kwargs: added_members.append(kwargs),
    )

    payload = trip_service.accept_invite(fake_db, user, "abc")

    assert payload is not None
    assert payload["alreadyMember"] is True
    assert added_members == []
    assert fake_db.commits == 1


def test_accept_invite_returns_none_for_missing_or_expired_token(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user(3, "Friend")
    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_active_invite_by_token",
        lambda *_args, **_kwargs: None,
    )

    assert trip_service.accept_invite(fake_db, user, "missing") is None
    assert fake_db.commits == 0


def test_get_trip_recommendations_use_date_category_and_fresh_external_gate(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    trip = make_trip()
    trip.region = "강원"
    trip.travel_area_id = "gangwon-sokcho-goseong-yangyang"
    trip.title = "속초 2박 휴식 여행"
    trip.description = "호텔에서 쉬는 일정"
    linked_policy = trip.policies[0].policy
    linked_policy.slug = "fixture-policy"
    linked_policy.region = "전국"
    matching_local = Policy(
        id=4,
        slug="travelmonth-local-half",
        title="속초 대한민국 반값여행 지원",
        benefit_detail="최대 20만원 환급",
        benefit_amount=200000,
        region="강원",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 7, 31),
        source_category="local_half_trip",
        external_source_record_id=4,
        verification_status="fresh",
    )
    nationwide_stay = Policy(
        id=5,
        slug="travelmonth-stay",
        title="대한민국 숙박세일 페스타 숙박 할인",
        benefit_detail="2/3/5/7만원 할인권",
        benefit_amount=70000,
        region="전국",
        start_date=date(2026, 6, 11),
        end_date=date(2026, 7, 31),
        source_category="stay_discount",
        policy_type="숙박",
        external_source_record_id=5,
        verification_status="fresh",
    )
    stale_stay = Policy(
        id=6,
        slug="travelmonth-stale-stay",
        title="속초 숙박 할인",
        benefit_detail="5만원 할인",
        benefit_amount=50000,
        region="강원",
        start_date=date(2026, 6, 1),
        end_date=date(2026, 7, 31),
        source_category="stay_discount",
        external_source_record_id=6,
        verification_status="stale",
    )
    ended_before_trip = Policy(
        id=7,
        slug="old-gangwon-benefit",
        title="강원 지난 혜택",
        benefit_detail="1만원 할인",
        benefit_amount=10000,
        region="강원",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
        source_category="regional_benefit",
        external_source_record_id=7,
        verification_status="fresh",
    )

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip if db is fake_db and trip_id == 7 and user_id == 1 else None,
    )
    monkeypatch.setattr(
        trip_service.policy_repository,
        "list_policies",
        lambda db: [linked_policy, nationwide_stay, stale_stay, ended_before_trip, matching_local] if db is fake_db else [],
    )

    payload = trip_service.get_trip("7", fake_db, user)

    assert payload is not None
    assert [policy["slug"] for policy in payload["recommendedPolicies"]] == [
        "travelmonth-local-half",
    ]
    assert payload["recommendedPolicies"][0]["title"] == "[속초] 대한민국 반값여행 지원"


def test_trip_recommendation_candidates_expand_stay_discount_aliases(monkeypatch) -> None:
    fake_db = object()
    stay_policy = make_stay_policy()
    stay_record = make_stay_record()

    monkeypatch.setattr(trip_service.policy_repository, "list_policies", lambda db: [stay_policy] if db is fake_db else [])
    monkeypatch.setattr(
        trip_service.external_source_repository,
        "get_external_source_record_by_id",
        lambda db, record_id: stay_record if db is fake_db and record_id == 88 else None,
    )

    candidates = trip_service._list_recommended_policy_candidates(fake_db)

    assert [candidate["slug"] for candidate in candidates] == [
        "stay-discount-gangwon-goseong",
        "stay-discount-gangwon-samcheok",
        "stay-discount-gyeongnam-goseong",
    ]
    assert all(candidate["canonicalSlug"] == "travelmonth-88" for candidate in candidates)
    assert [candidate["title"] for candidate in candidates] == [
        "[고성] 2026 대한민국 숙박세일 페스타 숙박 할인",
        "[삼척] 2026 대한민국 숙박세일 페스타 숙박 할인",
        "[고성] 2026 대한민국 숙박세일 페스타 숙박 할인",
    ]
    assert [candidate["region"] for candidate in candidates] == ["강원", "강원", "경남"]
    assert "travelmonth-88" not in [candidate["slug"] for candidate in candidates]


def test_trip_recommendation_candidates_hide_stay_canonical_when_alias_payload_missing(monkeypatch) -> None:
    fake_db = object()
    stay_policy = make_stay_policy()
    stay_record = make_stay_record()
    stay_record.raw_payload = {}

    monkeypatch.setattr(trip_service.policy_repository, "list_policies", lambda db: [stay_policy] if db is fake_db else [])
    monkeypatch.setattr(
        trip_service.external_source_repository,
        "get_external_source_record_by_id",
        lambda db, record_id: stay_record if db is fake_db and record_id == 88 else None,
    )

    assert trip_service._list_recommended_policy_candidates(fake_db) == []


def test_trip_recommendations_do_not_show_stay_aliases_when_canonical_linked(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    trip = make_trip()
    stay_policy = make_stay_policy()
    stay_record = make_stay_record()
    trip.region = "강원"
    trip.travel_area_id = "gangwon-sokcho-goseong-yangyang"
    trip.policies[0].policy = stay_policy

    monkeypatch.setattr(
        trip_service.trip_repository,
        "get_accessible_trip_by_id",
        lambda db, trip_id, user_id: trip if db is fake_db and trip_id == 7 and user_id == 1 else None,
    )
    monkeypatch.setattr(trip_service.policy_repository, "list_policies", lambda db: [stay_policy] if db is fake_db else [])
    monkeypatch.setattr(
        trip_service.external_source_repository,
        "get_external_source_record_by_id",
        lambda db, record_id: stay_record if db is fake_db and record_id == 88 else None,
    )

    payload = trip_service.get_trip("7", fake_db, user)

    assert payload is not None
    assert payload["recommendedPolicies"] == []


def test_recommended_policies_use_candidate_style_tags_for_rule_score() -> None:
    trip = make_trip()
    trip.region = "전국"
    trip.description = "호텔에서 쉬는 휴식 여행"
    trip.policies = []
    candidates = [
        {
            "slug": "generic-coupon",
            "title": "전국 여행 쿠폰",
            "amount": "1만원",
            "region": "전국",
            "benefitAmount": 10000,
            "startDate": date(2026, 6, 1),
            "endDate": date(2026, 7, 31),
            "sourceCategory": "regional_benefit",
            "policyType": "",
            "tags": [],
            "styles": [],
            "sortId": 1,
        },
        {
            "slug": "rest-style-coupon",
            "title": "전국 여행 쿠폰",
            "amount": "1만원",
            "region": "전국",
            "benefitAmount": 10000,
            "startDate": date(2026, 6, 1),
            "endDate": date(2026, 7, 31),
            "sourceCategory": "regional_benefit",
            "policyType": "",
            "tags": ["숙박"],
            "styles": ["휴식"],
            "sortId": 99,
        },
    ]

    recommended = trip_service._recommended_policies(trip, candidates, limit=2)

    assert [policy["slug"] for policy in recommended] == [
        "rest-style-coupon",
        "generic-coupon",
    ]
