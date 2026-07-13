from datetime import datetime

from fastapi.testclient import TestClient

from app.api.routes import profile as profile_routes
from app.main import app
from app.models import User


client = TestClient(app)


class FakeDb:
    def __init__(self) -> None:
        self.flushed = False
        self.committed = False
        self.refreshed: object | None = None

    def add(self, _value: object) -> None:
        pass

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True

    def refresh(self, value: object) -> None:
        self.refreshed = value


def make_user() -> User:
    return User(
        id=1,
        email="test.user@example.com",
        nickname="Test User",
        preferred_regions="제주,부산",
        travel_style="휴식",
        travel_budget="1인 40만원 이하",
        onboarding_completed=False,
        nickname_setup_completed=False,
        profile_setup_skipped=False,
        created_at=datetime(2026, 5, 4, 0, 0, 0),
        updated_at=datetime(2026, 5, 4, 0, 0, 0),
    )


def clear_overrides() -> None:
    app.dependency_overrides.pop(profile_routes.get_current_user, None)
    app.dependency_overrides.pop(profile_routes.get_optional_db, None)


def test_db_me_returns_user_without_removed_personal_fields() -> None:
    user = make_user()
    app.dependency_overrides[profile_routes.get_current_user] = lambda: user

    try:
        response = client.get("/api/me", headers={"Authorization": "Bearer access-token"})
    finally:
        clear_overrides()

    assert response.status_code == 200
    payload = response.json()
    assert payload["preferredRegions"] == ["제주", "부산"]
    assert payload["nickname"] == "Test User"
    assert {
        "region",
        "birthDate",
        "gender",
        "residenceArea",
        "homeRegion",
        "phoneNumber",
        "phoneVerified",
    }.isdisjoint(payload)


def test_db_profile_requires_bearer_token() -> None:
    response = client.get("/api/me/profile")

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_db_get_profile_returns_current_user_profile() -> None:
    user = make_user()

    app.dependency_overrides[profile_routes.get_current_user] = lambda: user

    try:
        response = client.get("/api/me/profile", headers={"Authorization": "Bearer access-token"})
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == {
        "preferredRegions": ["제주", "부산"],
        "style": "휴식",
        "budget": "1인 40만원 이하",
    }


def test_db_get_profile_returns_nulls_for_unset_values() -> None:
    user = make_user()
    user.preferred_regions = None
    user.travel_style = None
    user.travel_budget = None

    app.dependency_overrides[profile_routes.get_current_user] = lambda: user

    try:
        response = client.get("/api/me/profile", headers={"Authorization": "Bearer access-token"})
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == {
        "preferredRegions": None,
        "style": None,
        "budget": None,
    }


def test_db_patch_profile_persists_current_user_profile() -> None:
    user = make_user()
    fake_db = FakeDb()

    app.dependency_overrides[profile_routes.get_current_user] = lambda: user
    app.dependency_overrides[profile_routes.get_optional_db] = lambda: fake_db

    try:
        response = client.patch(
            "/api/me/profile",
            json={"preferredRegions": ["부산", "강원"], "style": "맛집", "budget": "1인 30만원 이하"},
            headers={"Authorization": "Bearer access-token"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == {
        "preferredRegions": ["부산", "강원"],
        "style": "맛집",
        "budget": "1인 30만원 이하",
    }
    assert user.preferred_regions == "부산,강원"
    assert user.travel_style == "맛집"
    assert user.travel_budget == "1인 30만원 이하"
    assert user.onboarding_completed is True
    assert fake_db.flushed is True
    assert fake_db.committed is True


def test_db_patch_profile_rejects_removed_fields_with_422() -> None:
    user = make_user()
    fake_db = FakeDb()
    removed_payloads = [
        {"region": "부산"},
        {"birthDate": "2000-01-01"},
        {"gender": "female"},
        {"residenceArea": "서울"},
        {"phoneNumber": "01012345678"},
        {"phoneVerified": True},
    ]

    app.dependency_overrides[profile_routes.get_current_user] = lambda: user
    app.dependency_overrides[profile_routes.get_optional_db] = lambda: fake_db

    try:
        responses = [
            client.patch(
                "/api/me/profile",
                json=payload,
                headers={"Authorization": "Bearer access-token"},
            )
            for payload in removed_payloads
        ]
    finally:
        clear_overrides()

    assert [response.status_code for response in responses] == [422] * len(removed_payloads)
    assert fake_db.committed is False


def test_removed_contact_and_notification_routes_are_absent() -> None:
    user = make_user()
    fake_db = FakeDb()
    app.dependency_overrides[profile_routes.get_current_user] = lambda: user
    app.dependency_overrides[profile_routes.get_optional_db] = lambda: fake_db

    try:
        responses = [
            client.get("/api/me/contact", headers={"Authorization": "Bearer access-token"}),
            client.patch("/api/me/contact", json={}, headers={"Authorization": "Bearer access-token"}),
            client.post("/api/me/contact/verification/request", json={}, headers={"Authorization": "Bearer access-token"}),
            client.post("/api/me/contact/verification/confirm", json={"code": "123456"}, headers={"Authorization": "Bearer access-token"}),
            client.get("/api/me/notification-settings", headers={"Authorization": "Bearer access-token"}),
            client.patch("/api/me/notification-settings", json={"deadlineEnabled": False}, headers={"Authorization": "Bearer access-token"}),
            client.post("/api/webhooks/solapi", json=[]),
        ]
    finally:
        clear_overrides()

    assert [response.status_code for response in responses] == [404] * len(responses)


def test_db_patch_profile_clears_and_rejects_preferred_regions() -> None:
    user = make_user()
    fake_db = FakeDb()

    app.dependency_overrides[profile_routes.get_current_user] = lambda: user
    app.dependency_overrides[profile_routes.get_optional_db] = lambda: fake_db

    try:
        clear_response = client.patch(
            "/api/me/profile",
            json={"preferredRegions": []},
            headers={"Authorization": "Bearer access-token"},
        )
        invalid_response = client.patch(
            "/api/me/profile",
            json={"preferredRegions": ["부산", "달나라"]},
            headers={"Authorization": "Bearer access-token"},
        )
        too_many_response = client.patch(
            "/api/me/profile",
            json={"preferredRegions": ["서울", "부산", "대구", "인천"]},
            headers={"Authorization": "Bearer access-token"},
        )
    finally:
        clear_overrides()

    assert clear_response.status_code == 200
    assert clear_response.json()["preferredRegions"] is None
    assert user.preferred_regions is None
    assert invalid_response.status_code == 422
    assert too_many_response.status_code == 422


def test_db_post_profile_skip_marks_onboarding_complete_without_profile_values() -> None:
    user = make_user()
    fake_db = FakeDb()

    app.dependency_overrides[profile_routes.get_current_user] = lambda: user
    app.dependency_overrides[profile_routes.get_optional_db] = lambda: fake_db

    try:
        response = client.post(
            "/api/me/profile/skip",
            headers={"Authorization": "Bearer access-token"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == {
        "skipped": True,
        "onboardingCompleted": True,
    }
    assert user.onboarding_completed is True
    assert user.profile_setup_skipped is True
    assert fake_db.flushed is True
    assert fake_db.committed is True


def test_profile_options_return_all_broad_regions() -> None:
    response = client.get("/api/profile-options")

    assert response.status_code == 200
    assert response.json()["regions"] == [
        "서울",
        "부산",
        "대구",
        "인천",
        "광주",
        "대전",
        "울산",
        "세종",
        "경기",
        "강원",
        "충북",
        "충남",
        "전북",
        "전남",
        "경북",
        "경남",
        "제주",
    ]


def test_db_patch_nickname_accepts_internal_spaces() -> None:
    user = make_user()
    fake_db = FakeDb()

    app.dependency_overrides[profile_routes.get_current_user] = lambda: user
    app.dependency_overrides[profile_routes.get_optional_db] = lambda: fake_db

    try:
        response = client.patch(
            "/api/me/nickname",
            json={"nickname": "여행 헌터"},
            headers={"Authorization": "Bearer access-token"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["nickname"] == "여행 헌터"
    assert response.json()["nicknameSetupCompleted"] is True
    assert user.nickname == "여행 헌터"
    assert user.nickname_setup_completed is True
    assert fake_db.committed is True
    assert fake_db.refreshed is user
