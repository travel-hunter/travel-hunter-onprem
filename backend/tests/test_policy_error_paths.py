from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.api.routes import policies as policy_routes
from app.main import app
from app.models import Policy as PolicyModel
from app.models import PolicyDocument
from app.models import User as UserModel
from app.services import policies as policy_service


client = TestClient(app)


def make_seed_like_policy() -> PolicyModel:
    policy = PolicyModel(
        id=1,
        slug="fixture-policy",
        title="Local Vacation Support",
        organization="Travel Hunter",
        policy_type="unsupported",
        description="Domestic travel support",
        benefit_amount=300000,
        benefit_detail="Up to 300000 cashback",
        target_condition="Domestic resident\nAt least one night\nReceipt required",
        region="National",
        end_date=date(2026, 10, 31),
        official_url="https://www.mcst.go.kr/site/s_notice/press/pressView.jsp?pMenuCD=0302000000&pSeq=22267",
        apply_url=None,
        policy_comment="Support for domestic travel expenses.",
    )
    policy.documents = [
        PolicyDocument(id=1, policy_id=1, document_name="ID card"),
        PolicyDocument(id=2, policy_id=1, document_name="Accommodation receipt"),
    ]
    return policy


def set_db_dependency_override(fake_db: object) -> None:
    app.dependency_overrides[policy_routes.get_optional_db] = lambda: fake_db


def clear_db_dependency_override() -> None:
    app.dependency_overrides.pop(policy_routes.get_optional_db, None)
    app.dependency_overrides.pop(policy_routes.get_current_user, None)


def make_user() -> UserModel:
    return UserModel(id=7, email="friend@travel.kr", nickname="Friend")


def test_db_mode_unknown_policy_slug_returns_404(monkeypatch) -> None:
    fake_db = object()

    monkeypatch.setattr(
        policy_service.policy_repository,
        "get_policy_by_slug_any_status",
        lambda db, slug: None if db is fake_db and slug == "missing-policy" else None,
    )
    set_db_dependency_override(fake_db)

    try:
        response = client.get("/api/policies/missing-policy")
    finally:
        clear_db_dependency_override()

    assert response.status_code == 404
    assert response.json() == {"detail": "Policy not found"}


def test_db_mode_known_policy_slug_preserves_response_contract(monkeypatch) -> None:
    fake_db = object()
    policy = make_seed_like_policy()

    monkeypatch.setattr(
        policy_service.policy_repository,
        "get_policy_by_slug_any_status",
        lambda db, slug: policy if db is fake_db and slug == "fixture-policy" else None,
    )
    set_db_dependency_override(fake_db)

    try:
        response = client.get("/api/policies/fixture-policy")
    finally:
        clear_db_dependency_override()

    payload = response.json()

    assert response.status_code == 200
    assert payload["id"] == "fixture-policy"
    assert payload["slug"] == "fixture-policy"
    assert payload["amount"] == "Up to 300000 cashback"
    assert payload["documents"] == ["ID card", "Accommodation receipt"]
    assert payload["officialUrl"] == "https://www.mcst.go.kr/site/s_notice/press/pressView.jsp?pMenuCD=0302000000&pSeq=22267"
    assert payload["applyUrl"] is None
    assert payload["sourceType"] == "internal"


def test_db_mode_policy_list_can_return_collected_external_benefits(monkeypatch) -> None:
    fake_db = object()
    monkeypatch.setattr(
        policy_service,
        "list_policies",
        lambda db: [
            {
                "id": "travelmonth-58",
                "slug": "travelmonth-58",
                "label": "부산",
                "tag": "최대 2만원",
                "title": "부산 야경투어 여행가는 달 할인",
                "org": "부산관광공사",
                "region": "부산",
                "deadline": "2026-06-30",
                "amount": "최대 2만원",
                "summary": "부산 야경투어 상품 할인",
                "match": 80,
                "category": "지역할인",
                "requirements": ["공식 안내에서 신청 조건을 확인하세요."],
                "documents": ["혜택 안내 확인"],
                "officialUrl": "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do",
                "applyUrl": None,
                "sourceType": "external",
            }
        ]
        if db is fake_db
        else [],
    )
    set_db_dependency_override(fake_db)

    try:
        response = client.get("/api/policies")
    finally:
        clear_db_dependency_override()

    assert response.status_code == 200
    assert response.json()[0]["slug"] == "travelmonth-58"
    assert response.json()[0]["sourceType"] == "external"


def test_db_policy_service_returns_none_when_repository_misses(monkeypatch) -> None:
    fake_db = object()

    monkeypatch.setattr(
        policy_service.policy_repository,
        "get_policy_by_slug_any_status",
        lambda db, slug: None,
    )

    assert policy_service.get_policy("missing-policy", fake_db) is None


def test_db_policy_service_requires_session_in_db_mode(monkeypatch) -> None:

    with pytest.raises(RuntimeError, match="DB session is required"):
        policy_service.list_policies(None)

    with pytest.raises(RuntimeError, match="DB session is required"):
        policy_service.get_policy("missing-policy", None)


def test_db_saved_policy_requires_user(monkeypatch) -> None:
    fake_db = object()
    set_db_dependency_override(fake_db)
    app.dependency_overrides[policy_routes.get_current_user] = lambda: None

    try:
        response = client.post("/api/me/saved-policies/fixture-policy")
    finally:
        clear_db_dependency_override()

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_db_saved_policy_unknown_policy_returns_404(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    monkeypatch.setattr(policy_service, "save_policy", lambda *_args: None)
    set_db_dependency_override(fake_db)
    app.dependency_overrides[policy_routes.get_current_user] = lambda: user

    try:
        response = client.post("/api/me/saved-policies/missing-policy")
    finally:
        clear_db_dependency_override()

    assert response.status_code == 404
    assert response.json() == {"detail": "Policy not found"}


def test_db_saved_policy_returns_existing_response_shape(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    monkeypatch.setattr(
        policy_service,
        "save_policy",
        lambda policy_slug, db, current_user: {"policyId": policy_slug, "saved": True}
        if db is fake_db and current_user is user
        else None,
    )
    set_db_dependency_override(fake_db)
    app.dependency_overrides[policy_routes.get_current_user] = lambda: user

    try:
        response = client.post("/api/me/saved-policies/fixture-policy")
    finally:
        clear_db_dependency_override()

    assert response.status_code == 200
    assert response.json() == {"policyId": "fixture-policy", "saved": True}


def test_db_list_saved_policies_requires_user(monkeypatch) -> None:
    fake_db = object()
    set_db_dependency_override(fake_db)
    app.dependency_overrides[policy_routes.get_current_user] = lambda: None

    try:
        response = client.get("/api/me/saved-policies")
    finally:
        clear_db_dependency_override()

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_db_list_saved_policies_returns_policy_list(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    policy = make_seed_like_policy()
    monkeypatch.setattr(
        policy_service,
        "list_saved_policies",
        lambda db, current_user: [policy_service.policy_to_api(policy)]
        if db is fake_db and current_user is user
        else [],
    )
    set_db_dependency_override(fake_db)
    app.dependency_overrides[policy_routes.get_current_user] = lambda: user

    try:
        response = client.get("/api/me/saved-policies")
    finally:
        clear_db_dependency_override()

    assert response.status_code == 200
    assert response.json()[0]["slug"] == "fixture-policy"


def test_db_list_applied_policies_requires_user(monkeypatch) -> None:
    fake_db = object()
    set_db_dependency_override(fake_db)
    app.dependency_overrides[policy_routes.get_current_user] = lambda: None

    try:
        response = client.get("/api/me/applied-policies")
    finally:
        clear_db_dependency_override()

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_db_list_applied_policies_returns_policy_list(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    policy = make_seed_like_policy()
    monkeypatch.setattr(
        policy_service,
        "list_applied_policies",
        lambda db, current_user: [policy_service.policy_to_api(policy)]
        if db is fake_db and current_user is user
        else [],
    )
    set_db_dependency_override(fake_db)
    app.dependency_overrides[policy_routes.get_current_user] = lambda: user

    try:
        response = client.get("/api/me/applied-policies")
    finally:
        clear_db_dependency_override()

    assert response.status_code == 200
    assert response.json()[0]["slug"] == "fixture-policy"


def test_db_remove_saved_policy_requires_user(monkeypatch) -> None:
    fake_db = object()
    set_db_dependency_override(fake_db)
    app.dependency_overrides[policy_routes.get_current_user] = lambda: None

    try:
        response = client.delete("/api/me/saved-policies/fixture-policy")
    finally:
        clear_db_dependency_override()

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_db_remove_saved_policy_returns_existing_response_shape(monkeypatch) -> None:
    fake_db = object()
    user = make_user()
    monkeypatch.setattr(
        policy_service,
        "remove_saved_policy",
        lambda policy_slug, db, current_user: {"policyId": policy_slug, "saved": False}
        if db is fake_db and current_user is user
        else None,
    )
    set_db_dependency_override(fake_db)
    app.dependency_overrides[policy_routes.get_current_user] = lambda: user

    try:
        response = client.delete("/api/me/saved-policies/fixture-policy")
    finally:
        clear_db_dependency_override()

    assert response.status_code == 200
    assert response.json() == {"policyId": "fixture-policy", "saved": False}
