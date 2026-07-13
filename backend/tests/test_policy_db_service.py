from datetime import date

from app.models import Policy as PolicyModel
from app.models import ExternalSourceRecord
from app.models import PolicyDocument
from app.models import User as UserModel
from app.models import UserSavedPolicy
from app.services import policies as policy_service
from app.services.policy_structured_detail import build_structured_detail_from_policy


def make_policy() -> PolicyModel:
    policy = PolicyModel(
        id=1,
        slug="fixture-policy",
        title="Local Vacation Support",
        organization="Travel Hunter",
        policy_type="지역할인",
        description="Domestic travel support",
        benefit_amount=300000,
        benefit_detail="Up to 300000 KRW",
        target_condition="Domestic resident\nAt least one night\nReceipt required",
        region="National",
        end_date=date(2026, 10, 31),
        official_url="https://www.mcst.go.kr/site/s_notice/press/pressView.jsp?pMenuCD=0302000000&pSeq=22267",
        apply_url=None,
        policy_comment="Support for domestic travel expenses.",
    )
    policy.documents = [
        PolicyDocument(document_name="ID card"),
        PolicyDocument(document_name="Accommodation receipt"),
    ]
    return policy


def test_policy_to_api_preserves_contract_shape() -> None:
    payload = policy_service.policy_to_api(make_policy())

    assert set(payload) == {
        "id",
        "slug",
        "label",
        "tag",
        "title",
        "org",
        "region",
        "deadline",
        "amount",
        "summary",
        "match",
        "category",
        "requirements",
        "documents",
        "structuredDetail",
        "officialUrl",
        "applyUrl",
        "sourceType",
    }
    assert payload["id"] == "fixture-policy"
    assert payload["slug"] == "fixture-policy"
    assert payload["label"] == "FI"
    assert payload["deadline"] == "2026-10-31"
    assert payload["amount"] == "Up to 300000 KRW"
    assert payload["match"] == 90
    assert payload["requirements"] == [
        "Domestic resident",
        "At least one night",
        "Receipt required",
    ]
    assert payload["documents"] == ["ID card", "Accommodation receipt"]
    assert payload["structuredDetail"] is None
    assert payload["officialUrl"] == "https://www.mcst.go.kr/site/s_notice/press/pressView.jsp?pMenuCD=0302000000&pSeq=22267"
    assert payload["applyUrl"] is None
    assert payload["sourceType"] == "internal"
    assert payload["category"] == "지역할인"


def test_policy_to_api_includes_structured_detail_when_present() -> None:
    policy = make_policy()
    policy.structured_detail = {
        "benefits": [{"title": "혜택", "description": "숙박비 할인", "amount": "최대 7만원"}],
        "conditions": [{"title": "대상", "description": "비수도권 숙박 예약자"}],
        "periods": [],
        "links": [{"label": "공식 안내", "url": "https://example.com"}],
        "documents": [],
        "notices": [],
    }

    payload = policy_service.policy_to_api(policy)

    assert payload["structuredDetail"] == policy.structured_detail


def test_policy_to_api_sanitizes_structured_detail_links_and_keys() -> None:
    policy = make_policy()
    policy.structured_detail = {
        "benefits": [{"title": "혜택", "description": "숙박비 할인", "rawPayload": "secret"}],
        "conditions": [],
        "periods": [],
        "links": [
            {"label": "공식 안내", "url": "https://example.com/ok", "rawPayload": {"internal": True}},
            {"label": "위험 링크", "url": "javascript:alert(1)"},
        ],
        "documents": [],
        "notices": [],
    }

    payload = policy_service.policy_to_api(policy)

    assert payload["structuredDetail"] == {
        "benefits": [{"title": "혜택", "description": "숙박비 할인"}],
        "conditions": [],
        "periods": [],
        "links": [{"label": "공식 안내", "url": "https://example.com/ok"}],
        "documents": [],
        "notices": [],
    }


def test_policy_to_api_omits_empty_structured_detail_for_fallback() -> None:
    policy = make_policy()
    policy.structured_detail = {
        "benefits": [],
        "conditions": [],
        "periods": [],
        "links": [],
        "documents": [],
        "notices": [],
    }

    payload = policy_service.policy_to_api(policy)

    assert payload["structuredDetail"] is None


def test_policy_to_api_uses_benefit_amount_fallback_when_detail_missing() -> None:
    policy = make_policy()
    policy.benefit_detail = None
    policy.benefit_amount = 300000

    payload = policy_service.policy_to_api(policy)

    assert payload["amount"] == "최대 30만원"
    assert payload["tag"] == "최대 30만원"


def test_policy_to_api_returns_empty_amount_when_benefit_fields_missing() -> None:
    policy = make_policy()
    policy.benefit_detail = None
    policy.benefit_amount = None

    payload = policy_service.policy_to_api(policy)

    assert payload["amount"] == ""


def test_policy_to_api_preserves_apply_and_official_urls_separately() -> None:
    policy = make_policy()
    policy.apply_url = "https://apply.example/policy"
    policy.official_url = "https://official.example/policy"

    payload = policy_service.policy_to_api(policy)

    assert payload["applyUrl"] == "https://apply.example/policy"
    assert payload["officialUrl"] == "https://official.example/policy"


def test_policy_to_api_omits_unsafe_top_level_urls() -> None:
    policy = make_policy()
    policy.apply_url = "javascript:alert(1)"
    policy.official_url = "https:///missing-host"

    payload = policy_service.policy_to_api(policy)

    assert payload["applyUrl"] is None
    assert payload["officialUrl"] is None


def test_policy_to_api_requirement_fallback_splits_and_sanitizes_target_condition() -> None:
    policy = make_policy()
    policy.target_condition = "국내 거주자\n숙박 영수증 제출\n문의전화 1660-3067\n모바일 앱 신청"

    payload = policy_service.policy_to_api(policy)

    assert payload["requirements"] == ["국내 거주자", "숙박 영수증 제출", "모바일 앱 신청"]


def test_built_structured_detail_matches_policy_api_fallback_fields() -> None:
    policy = make_policy()
    policy.benefit_detail = "숙박비 5만원 지원"
    policy.target_condition = "국내 거주자\n숙박 영수증 제출"
    policy.apply_url = "https://apply.example/policy"
    policy.official_url = "https://official.example/policy"

    payload = policy_service.policy_to_api(policy)
    detail = build_structured_detail_from_policy(policy)

    assert [item["description"] for item in detail["conditions"]] == payload["requirements"]
    assert detail["benefits"] == [
        {"title": "혜택", "description": "숙박비 5만원 지원", "amount": "숙박비 5만원 지원"}
    ]
    assert detail["links"] == [
        {"label": "신청하기", "url": "https://apply.example/policy"},
        {"label": "공식 안내", "url": "https://official.example/policy"},
    ]


def test_build_structured_detail_filters_unsafe_policy_links() -> None:
    policy = make_policy()
    policy.apply_url = "javascript:alert(1)"
    policy.official_url = "https://example.com/official"

    detail = build_structured_detail_from_policy(policy)

    assert detail["links"] == [{"label": "공식 안내", "url": "https://example.com/official"}]


def test_policy_to_api_filters_phone_contact_requirements() -> None:
    policy = make_policy()
    policy.target_condition = "1660-3067\n문의전화 1660-3067 특이사항 지정관광지 방문 인증\n국내 거주자"

    payload = policy_service.policy_to_api(policy)

    assert payload["requirements"] == ["국내 거주자"]


def test_local_half_trip_policy_title_uses_bracketed_city_prefix() -> None:
    policy = make_policy()
    policy.slug = "travelmonth-101"
    policy.title = "합천 대한민국 반값여행 지원"
    policy.region = "경남"
    policy.source_category = "local_half_trip"

    payload = policy_service.policy_to_api(policy)

    assert payload["title"] == "[합천] 대한민국 반값여행 지원"
    assert payload["region"] == "경남"


def test_db_policy_service_uses_repository_boundary(monkeypatch) -> None:
    fake_db = object()
    policy = make_policy()

    monkeypatch.setattr(
        policy_service.policy_repository,
        "list_policies",
        lambda db: [policy] if db is fake_db else [],
    )
    monkeypatch.setattr(
        policy_service.policy_repository,
        "get_policy_by_slug_any_status",
        lambda db, slug: policy if db is fake_db and slug == "fixture-policy" else None,
    )
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "list_regional_benefit_recommendation_records",
        lambda db: [] if db is fake_db else [],
    )
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "get_external_source_record_by_policy_slug",
        lambda db, slug: None,
    )

    policies = policy_service.list_policies(fake_db)
    detail = policy_service.get_policy("fixture-policy", fake_db)
    missing = policy_service.get_policy("missing", fake_db)

    assert policies[0]["slug"] == "fixture-policy"
    assert detail is not None
    assert detail["title"] == "Local Vacation Support"
    assert missing is None


def make_external_record() -> ExternalSourceRecord:
    return ExternalSourceRecord(
        id=58,
        source_name="여행가는 달",
        source_type="official",
        source_category="regional_benefit",
        external_id="tm-58",
        canonical_key="busan-photo-benefit",
        detail_url="https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
        title="부산 야경투어 여행가는 달 할인",
        organizer_text="부산관광공사",
        region="부산",
        is_nationwide=False,
        status_text="진행중",
        status="active",
        end_date=date(2026, 6, 30),
        benefit_text="부산 야경투어 상품 할인",
        benefit_value_text="최대 2만원",
        extracted_amount_krw=20000,
        tags=["사진", "체험"],
        inferred_travel_styles=["사진", "체험"],
        confidence=0.8,
        field_completeness=0.9,
        freshness_status="fresh",
    )


def test_db_policy_list_uses_normalized_policies_without_raw_external_merge(monkeypatch) -> None:
    fake_db = object()
    policy = make_policy()
    external_record = make_external_record()

    monkeypatch.setattr(
        policy_service.policy_repository,
        "list_policies",
        lambda db: [policy] if db is fake_db else [],
    )
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "list_regional_benefit_recommendation_records",
        lambda db: [external_record] if db is fake_db else [],
    )

    payload = policy_service.list_policies(fake_db)

    assert [policy_payload["slug"] for policy_payload in payload] == ["fixture-policy"]
    assert external_record.title not in [policy_payload["title"] for policy_payload in payload]
    return

    assert [policy_payload["slug"] for policy_payload in payload] == [
        "fixture-policy",
        "travelmonth-58",
    ]
    collected = payload[1]
    assert collected["sourceType"] == "external"
    assert collected["title"] == "부산 야경투어 여행가는 달 할인"
    assert collected["org"] == "부산관광공사"
    assert collected["region"] == "부산"
    assert collected["deadline"] == "2026-06-30"
    assert collected["amount"] == "최대 2만원"
    assert collected["tag"] == "최대 2만원"
    assert collected["category"] == "지역할인"
    assert collected["officialUrl"] == "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do"
    assert collected["applyUrl"] is None


def test_db_policy_detail_resolves_collected_external_benefit_slug(monkeypatch) -> None:
    fake_db = object()
    external_record = make_external_record()

    monkeypatch.setattr(policy_service.policy_repository, "get_policy_by_slug_any_status", lambda *_args: None)
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "get_external_source_record_by_policy_slug",
        lambda db, slug: external_record if db is fake_db and slug == "travelmonth-58" else None,
    )

    detail = policy_service.get_policy("travelmonth-58", fake_db)

    assert detail is not None
    assert detail["slug"] == "travelmonth-58"
    assert detail["sourceType"] == "external"
    assert detail["actionStatus"] == "infoOnly"

def test_local_half_trip_raw_fallback_title_uses_bracketed_city_prefix(monkeypatch) -> None:
    fake_db = object()
    external_record = make_external_record()
    external_record.source_category = "local_half_trip"
    external_record.source_name = "대한민국 반값여행"
    external_record.title = "합천 대한민국 반값여행 지원"
    external_record.region = "경남"
    external_record.city = "합천"

    monkeypatch.setattr(policy_service.policy_repository, "get_policy_by_slug_any_status", lambda *_args: None)
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "get_external_source_record_by_policy_slug",
        lambda db, slug: external_record if db is fake_db and slug == "travelmonth-58" else None,
    )

    detail = policy_service.get_policy("travelmonth-58", fake_db)

    assert detail is not None
    assert detail["title"] == "[합천] 대한민국 반값여행 지원"


def test_external_policy_category_uses_official_source_not_travel_styles() -> None:
    record = make_external_record()
    record.collected_page_url = "https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do"
    record.inferred_travel_styles = ["맛집", "사진"]

    payload = policy_service.external_source_record_to_policy_api(record)

    assert payload["category"] == "교통"


def test_external_policy_to_api_omits_unsafe_top_level_official_url() -> None:
    record = make_external_record()
    record.detail_url = "ftp://travel.example/policy"
    record.collected_page_url = "javascript:alert(1)"

    payload = policy_service.external_source_record_to_policy_api(record)

    assert payload["officialUrl"] is None
    assert payload["applyUrl"] is None


def test_external_policy_category_scores_text_before_regional_default() -> None:
    record = make_external_record()
    record.source_category = "regional_benefit"
    record.title = "남도 기차둘레길 1박 2일 최대 35% 할인행사"
    record.benefit_text = "남도 기차 여행상품 최대 35% 할인"
    record.collected_page_url = "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do"

    payload = policy_service.external_source_record_to_policy_api(record)

    assert payload["category"] == "교통"


def test_external_policy_fallback_copy_uses_official_benefit_wording() -> None:
    record = make_external_record()
    record.benefit_value_text = None
    record.benefit_text = None

    payload = policy_service.external_source_record_to_policy_api(record)

    assert payload["amount"] == "혜택 확인 필요"
    assert payload["tag"] == "여행상품"
    assert payload["summary"] == "공식 혜택 안내를 확인해 주세요."
    assert payload["documents"] == ["혜택 안내 확인"]


class FakeDb:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


def make_user() -> UserModel:
    return UserModel(id=7, email="friend@travel.kr", nickname="Friend")


def test_db_save_policy_creates_idempotent_saved_policy(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    policy = make_policy()
    added_rows: list[dict[str, int]] = []

    monkeypatch.setattr(
        policy_service.policy_repository,
        "get_policy_by_slug",
        lambda db, slug: policy if db is fake_db and slug == "fixture-policy" else None,
    )
    monkeypatch.setattr(
        policy_service.policy_repository,
        "get_saved_policy",
        lambda *_args, **_kwargs: None,
    )

    def add_saved_policy_stub(_db, **kwargs):
        added_rows.append(kwargs)
        return UserSavedPolicy(id=1, **kwargs)

    monkeypatch.setattr(policy_service.policy_repository, "add_saved_policy", add_saved_policy_stub)

    payload = policy_service.save_policy("fixture-policy", fake_db, user)

    assert payload == {"policyId": "fixture-policy", "saved": True}
    assert added_rows == [{"user_id": 7, "policy_id": 1}]
    assert fake_db.commits == 1


def test_db_save_policy_returns_existing_saved_policy_without_duplicate(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    policy = make_policy()
    added_rows: list[dict[str, int]] = []

    monkeypatch.setattr(policy_service.policy_repository, "get_policy_by_slug", lambda *_args: policy)
    monkeypatch.setattr(
        policy_service.policy_repository,
        "get_saved_policy",
        lambda *_args, **_kwargs: UserSavedPolicy(id=1, user_id=7, policy_id=1),
    )
    monkeypatch.setattr(
        policy_service.policy_repository,
        "add_saved_policy",
        lambda _db, **kwargs: added_rows.append(kwargs),
    )

    payload = policy_service.save_policy("fixture-policy", fake_db, user)

    assert payload == {"policyId": "fixture-policy", "saved": True}
    assert added_rows == []
    assert fake_db.commits == 0


def test_db_save_policy_returns_none_for_unknown_policy(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()

    monkeypatch.setattr(policy_service.policy_repository, "get_policy_by_slug", lambda *_args: None)

    assert policy_service.save_policy("missing-policy", fake_db, user) is None
    assert fake_db.commits == 0


def test_db_list_saved_policies_maps_saved_rows(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    policy = make_policy()

    monkeypatch.setattr(
        policy_service.policy_repository,
        "list_saved_policies",
        lambda db, user_id: [policy] if db is fake_db and user_id == user.id else [],
    )

    payload = policy_service.list_saved_policies(fake_db, user)

    assert [policy_payload["slug"] for policy_payload in payload] == ["fixture-policy"]


def test_db_list_saved_policies_deduplicates_repository_rows(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    policy = make_policy()

    monkeypatch.setattr(
        policy_service.policy_repository,
        "list_saved_policies",
        lambda db, user_id: [policy, policy] if db is fake_db and user_id == user.id else [],
    )

    payload = policy_service.list_saved_policies(fake_db, user)

    assert [policy_payload["slug"] for policy_payload in payload] == ["fixture-policy"]


def test_db_list_applied_policies_maps_accessible_trip_policy_rows(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    policy = make_policy()

    monkeypatch.setattr(
        policy_service.policy_repository,
        "list_applied_policies",
        lambda db, user_id: [policy] if db is fake_db and user_id == user.id else [],
    )

    payload = policy_service.list_applied_policies(fake_db, user)

    assert [policy_payload["slug"] for policy_payload in payload] == ["fixture-policy"]


def test_db_remove_saved_policy_is_idempotent_for_existing_policy(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    policy = make_policy()
    removed_rows: list[dict[str, int]] = []

    monkeypatch.setattr(policy_service.policy_repository, "get_policy_by_slug", lambda *_args: policy)

    def remove_saved_policy_stub(_db, **kwargs):
        removed_rows.append(kwargs)
        return True

    monkeypatch.setattr(policy_service.policy_repository, "remove_saved_policy", remove_saved_policy_stub)

    payload = policy_service.remove_saved_policy("fixture-policy", fake_db, user)

    assert payload == {"policyId": "fixture-policy", "saved": False}
    assert removed_rows == [{"user_id": 7, "policy_id": 1}]
    assert fake_db.commits == 1


def test_policy_to_api_source_type_normalized_to_internal_external() -> None:
    policy_with_official_source = make_policy()
    policy_with_official_source.id = 90
    policy_with_official_source.slug = "official-source-policy"
    policy_with_official_source.source_type = "official_campaign"
    policy_with_official_source.external_source_record_id = None

    policy_with_unknown_source = make_policy()
    policy_with_unknown_source.id = 91
    policy_with_unknown_source.slug = "legacy-source-policy"
    policy_with_unknown_source.source_type = "legacy_source"
    policy_with_unknown_source.external_source_record_id = None

    policy_with_internal_source = make_policy()
    policy_with_internal_source.id = 92
    policy_with_internal_source.slug = "internal-source-policy"
    policy_with_internal_source.source_type = "INTERNAL"
    policy_with_internal_source.external_source_record_id = None

    policy_with_empty_source = make_policy()
    policy_with_empty_source.id = 94
    policy_with_empty_source.slug = "empty-source-policy"
    policy_with_empty_source.source_type = ""
    policy_with_empty_source.external_source_record_id = None

    policy_with_external_record = make_policy()
    policy_with_external_record.id = 93
    policy_with_external_record.slug = "external-linked-policy"
    policy_with_external_record.source_type = "internal"
    policy_with_external_record.external_source_record_id = 7

    assert policy_service.policy_to_api(policy_with_official_source)["sourceType"] == "external"
    assert policy_service.policy_to_api(policy_with_unknown_source)["sourceType"] == "external"
    assert policy_service.policy_to_api(policy_with_internal_source)["sourceType"] == "internal"
    assert policy_service.policy_to_api(policy_with_empty_source)["sourceType"] == "internal"
    assert policy_service.policy_to_api(policy_with_external_record)["sourceType"] == "external"


def make_stay_policy() -> PolicyModel:
    policy = PolicyModel(
        id=88,
        slug="travelmonth-88",
        title="2026 대한민국 숙박세일 페스타 숙박 할인",
        organization="문화체육관광부, 한국관광공사",
        policy_type="숙박",
        description="숙박 할인권 안내",
        benefit_amount=70000,
        benefit_detail="2/3/5/7만원 할인권",
        target_condition="발급기간: 2026.6.11~7.31\n사용방법: 참여 온라인 여행사에서 발급",
        region="비수도권 인구감소지역",
        end_date=date(2026, 7, 31),
        official_url="https://ktostay.visitkorea.or.kr/",
        apply_url=None,
        policy_comment="비수도권 인구감소지역 85개 지자체 숙박 할인",
        source_type="official_campaign",
        source_category="stay_discount",
        external_source_record_id=88,
        verification_status="fresh",
        status="active",
    )
    policy.documents = []
    return policy


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
        end_date=date(2026, 7, 31),
        benefit_text="2/3/5/7만원 할인권",
        benefit_value_text="2/3/5/7만원 할인권",
        extracted_amount_krw=70000,
        tags=["숙박", "인구감소지역"],
        inferred_travel_styles=["휴식"],
        confidence=90,
        field_completeness=90,
        freshness_status="fresh",
        raw_payload={
            "eligibleAreas": [
                {"sido": "강원", "cities": ["고성군", "삼척시"]},
                {"sido": "경남", "cities": ["고성군"]},
            ],
            "eligibleAreaCount": 3,
        },
    )


def test_stay_discount_list_projects_aliases_and_hides_canonical(monkeypatch) -> None:
    fake_db = object()
    canonical = make_stay_policy()
    record = make_stay_record()

    monkeypatch.setattr(policy_service.policy_repository, "list_policies", lambda db: [canonical] if db is fake_db else [])
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "get_external_source_record_by_id",
        lambda db, record_id: record if db is fake_db and record_id == 88 else None,
    )

    payload = policy_service.list_policies(fake_db)

    assert [item["slug"] for item in payload] == [
        "stay-discount-gangwon-goseong",
        "stay-discount-gangwon-samcheok",
        "stay-discount-gyeongnam-goseong",
    ]
    assert [item["title"] for item in payload] == [
        "[고성] 2026 대한민국 숙박세일 페스타 숙박 할인",
        "[삼척] 2026 대한민국 숙박세일 페스타 숙박 할인",
        "[고성] 2026 대한민국 숙박세일 페스타 숙박 할인",
    ]
    assert [item["region"] for item in payload] == ["강원", "강원", "경남"]
    assert all(item["sourceType"] == "external" for item in payload)
    assert all(item["category"] == "숙박" for item in payload)
    assert all(item.get("actionStatus") is None for item in payload)
    assert "travelmonth-88" not in [item["slug"] for item in payload]


def test_stay_discount_list_hides_canonical_when_alias_payload_missing(monkeypatch) -> None:
    fake_db = object()
    canonical = make_stay_policy()
    record = make_stay_record()
    record.raw_payload = {}

    monkeypatch.setattr(policy_service.policy_repository, "list_policies", lambda db: [canonical] if db is fake_db else [])
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "get_external_source_record_by_id",
        lambda db, record_id: record if db is fake_db and record_id == 88 else None,
    )

    assert policy_service.list_policies(fake_db) == []


def test_stay_discount_alias_detail_echoes_alias_slug(monkeypatch) -> None:
    fake_db = object()
    canonical = make_stay_policy()
    record = make_stay_record()

    monkeypatch.setattr(policy_service.policy_repository, "list_policies", lambda db: [canonical] if db is fake_db else [])
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "get_external_source_record_by_id",
        lambda db, record_id: record if db is fake_db and record_id == 88 else None,
    )
    monkeypatch.setattr(policy_service.policy_repository, "get_policy_by_slug_any_status", lambda *_args: None)
    monkeypatch.setattr(policy_service.external_source_repository, "get_external_source_record_by_policy_slug", lambda *_args: None)

    detail = policy_service.get_policy("stay-discount-gyeongnam-goseong", fake_db)

    assert detail is not None
    assert detail["slug"] == "stay-discount-gyeongnam-goseong"
    assert detail["id"] == "stay-discount-gyeongnam-goseong"
    assert detail["title"] == "[고성] 2026 대한민국 숙박세일 페스타 숙박 할인"
    assert detail["region"] == "경남"
    assert detail["amount"] == "최대 7만원"
    assert detail["summary"] == "비수도권 인구감소지역 숙박 예약 시 결제 금액과 숙박 조건에 따라 2만~7만원 할인권을 제공합니다."
    assert detail["requirements"] == [
        "7만원 미만 국내 숙박상품: 2만원 할인 (1박 이상)",
        "7만원 이상 국내 숙박상품: 3만원 할인 (1박 이상)",
        "14만원 미만 국내 숙박상품: 5만원 할인 (연박 이상)",
        "14만원 이상 국내 숙박상품: 7만원 할인 (연박 이상)",
        "참여 온라인 여행사에서 매일 오전 10시부터 선착순 발급",
        "입실기간: 2026.6.11~7.31",
    ]
    assert "7만원 미만* 국내 숙박상품 예약 시 2만원 할인" not in str(detail["summary"])
    assert detail["officialUrl"] == "https://ktostay.visitkorea.or.kr/"
    assert detail.get("actionStatus") is None


def test_hidden_policy_detail_returns_none_for_direct_slug(monkeypatch) -> None:
    fake_db = object()
    hidden_policy = make_policy()
    hidden_policy.status = "hidden"

    monkeypatch.setattr(
        policy_service.policy_repository,
        "get_policy_by_slug_any_status",
        lambda db, slug: hidden_policy if db is fake_db and slug == "fixture-policy" else None,
    )
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "get_external_source_record_by_policy_slug",
        lambda *_args: None,
    )

    assert policy_service.get_policy("fixture-policy", fake_db) is None


def test_hidden_policy_detail_returns_none_for_stay_alias(monkeypatch) -> None:
    fake_db = object()
    hidden_stay_policy = make_stay_policy()
    hidden_stay_policy.status = "hidden"
    record = make_stay_record()

    monkeypatch.setattr(
        policy_service.policy_repository,
        "list_policies",
        lambda db: [hidden_stay_policy] if db is fake_db else [],
    )
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "get_external_source_record_by_id",
        lambda db, record_id: record if db is fake_db and record_id == 88 else None,
    )
    monkeypatch.setattr(policy_service.policy_repository, "get_policy_by_slug_any_status", lambda *_args: None)
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "get_external_source_record_by_policy_slug",
        lambda *_args: None,
    )

    assert policy_service.get_policy("stay-discount-gangwon-goseong", fake_db) is None


def test_stay_discount_raw_fallback_detail_uses_clean_display_copy(monkeypatch) -> None:
    fake_db = object()
    record = make_stay_record()
    record.raw_detail_text = (
        "7만원 미만* 국내 숙박상품 예약 시 2만원 할인 / "
        "7만원 이상 국내 숙박상품 예약 시 3만원 할인 / "
        "7만원 미만* 국내 숙박상품 예약 시 2만원 할인"
    )

    monkeypatch.setattr(policy_service.policy_repository, "get_policy_by_slug_any_status", lambda *_args: None)
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "get_external_source_record_by_policy_slug",
        lambda db, slug: record if db is fake_db and slug == "travelmonth-88" else None,
    )

    detail = policy_service.get_policy("travelmonth-88", fake_db)

    assert detail is not None
    assert detail["amount"] == "최대 7만원"
    assert detail["summary"] == "비수도권 인구감소지역 숙박 예약 시 결제 금액과 숙박 조건에 따라 2만~7만원 할인권을 제공합니다."
    assert detail["requirements"][:4] == [
        "7만원 미만 국내 숙박상품: 2만원 할인 (1박 이상)",
        "7만원 이상 국내 숙박상품: 3만원 할인 (1박 이상)",
        "14만원 미만 국내 숙박상품: 5만원 할인 (연박 이상)",
        "14만원 이상 국내 숙박상품: 7만원 할인 (연박 이상)",
    ]
    assert str(detail).count("7만원 미만*") == 0


def test_stay_discount_alias_save_uses_canonical_policy_id_and_echoes_alias(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    canonical = make_stay_policy()
    record = make_stay_record()
    added_rows: list[dict[str, int]] = []

    monkeypatch.setattr(policy_service.policy_repository, "list_policies", lambda db: [canonical] if db is fake_db else [])
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "get_external_source_record_by_id",
        lambda db, record_id: record if db is fake_db and record_id == 88 else None,
    )
    monkeypatch.setattr(policy_service.policy_repository, "get_policy_by_slug", lambda *_args: None)
    monkeypatch.setattr(policy_service.policy_repository, "get_saved_policy", lambda *_args, **_kwargs: None)

    def add_saved_policy_stub(_db, **kwargs):
        added_rows.append(kwargs)
        return UserSavedPolicy(id=1, **kwargs)

    monkeypatch.setattr(policy_service.policy_repository, "add_saved_policy", add_saved_policy_stub)

    payload = policy_service.save_policy("stay-discount-gyeongnam-goseong", fake_db, user)

    assert payload == {"policyId": "stay-discount-gyeongnam-goseong", "saved": True}
    assert added_rows == [{"user_id": 7, "policy_id": 88}]
    assert fake_db.commits == 1


def test_stay_discount_alias_save_deduplicates_canonical_saved_policy(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    canonical = make_stay_policy()
    record = make_stay_record()
    added_rows: list[dict[str, int]] = []

    monkeypatch.setattr(policy_service.policy_repository, "list_policies", lambda db: [canonical] if db is fake_db else [])
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "get_external_source_record_by_id",
        lambda db, record_id: record if db is fake_db and record_id == 88 else None,
    )
    monkeypatch.setattr(
        policy_service.policy_repository,
        "get_saved_policy",
        lambda *_args, **_kwargs: UserSavedPolicy(id=1, user_id=7, policy_id=88),
    )
    monkeypatch.setattr(
        policy_service.policy_repository,
        "add_saved_policy",
        lambda _db, **kwargs: added_rows.append(kwargs),
    )

    payload = policy_service.save_policy("stay-discount-gangwon-goseong", fake_db, user)

    assert payload == {"policyId": "stay-discount-gangwon-goseong", "saved": True}
    assert added_rows == []
    assert fake_db.commits == 0


def test_stay_discount_alias_remove_uses_canonical_policy_id_and_echoes_alias(monkeypatch) -> None:
    fake_db = FakeDb()
    user = make_user()
    canonical = make_stay_policy()
    record = make_stay_record()
    removed_rows: list[dict[str, int]] = []

    monkeypatch.setattr(policy_service.policy_repository, "list_policies", lambda db: [canonical] if db is fake_db else [])
    monkeypatch.setattr(
        policy_service.external_source_repository,
        "get_external_source_record_by_id",
        lambda db, record_id: record if db is fake_db and record_id == 88 else None,
    )
    monkeypatch.setattr(policy_service.policy_repository, "get_policy_by_slug", lambda *_args: None)

    def remove_saved_policy_stub(_db, **kwargs):
        removed_rows.append(kwargs)
        return True

    monkeypatch.setattr(policy_service.policy_repository, "remove_saved_policy", remove_saved_policy_stub)

    payload = policy_service.remove_saved_policy("stay-discount-gangwon-samcheok", fake_db, user)

    assert payload == {"policyId": "stay-discount-gangwon-samcheok", "saved": False}
    assert removed_rows == [{"user_id": 7, "policy_id": 88}]
    assert fake_db.commits == 1
