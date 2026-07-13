from datetime import datetime

from app.models import User
from app.schemas.user import ProfileUpdate
from app.services import profile as profile_service


class FakeDb:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flushed = False
        self.committed = False

    def add(self, value: object) -> None:
        self.added.append(value)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True


def make_user() -> User:
    return User(
        id=1,
        email="test.user@example.com",
        nickname="테스트 사용자",
        preferred_regions="제주,부산",
        travel_style="휴식",
        travel_budget="1인 40만원 이하",
        onboarding_completed=False,
        nickname_setup_completed=False,
        profile_setup_skipped=False,
        created_at=datetime(2026, 5, 4, 0, 0, 0),
        updated_at=datetime(2026, 5, 4, 0, 0, 0),
    )


def test_profile_to_api_returns_nulls_for_missing_values() -> None:
    user = make_user()
    user.preferred_regions = None
    user.travel_style = None
    user.travel_budget = None

    assert profile_service.profile_to_api(user) == {
        "preferredRegions": None,
        "style": None,
        "budget": None,
    }


def test_profile_to_api_parses_preferred_regions() -> None:
    user = make_user()

    assert profile_service.profile_to_api(user)["preferredRegions"] == ["제주", "부산"]


def test_update_profile_persists_partial_values_and_marks_onboarding_complete() -> None:
    db = FakeDb()
    user = make_user()

    result = profile_service.update_profile(
        db,  # type: ignore[arg-type]
        user,
        ProfileUpdate(style="맛집"),
    )

    assert result == {"preferredRegions": ["제주", "부산"], "style": "맛집", "budget": "1인 40만원 이하"}
    assert user.travel_style == "맛집"
    assert user.travel_budget == "1인 40만원 이하"
    assert user.onboarding_completed is True
    assert user.updated_at != datetime(2026, 5, 4, 0, 0, 0)
    assert db.added == [user]
    assert db.flushed is True
    assert db.committed is True


def test_update_profile_persists_preferred_regions_as_comma_string() -> None:
    db = FakeDb()
    user = make_user()

    result = profile_service.update_profile(
        db,  # type: ignore[arg-type]
        user,
        ProfileUpdate(preferredRegions=["부산", "강원", "부산"]),
    )

    assert result["preferredRegions"] == ["부산", "강원"]
    assert user.preferred_regions == "부산,강원"


def test_update_profile_clears_preferred_regions_with_empty_list_or_null() -> None:
    db = FakeDb()
    user = make_user()

    result = profile_service.update_profile(
        db,  # type: ignore[arg-type]
        user,
        ProfileUpdate(preferredRegions=[]),
    )
    assert result["preferredRegions"] is None
    assert user.preferred_regions is None

    user.preferred_regions = "부산,강원"
    result = profile_service.update_profile(
        db,  # type: ignore[arg-type]
        user,
        ProfileUpdate(preferredRegions=None),
    )
    assert result["preferredRegions"] is None
    assert user.preferred_regions is None


def test_update_profile_rejects_invalid_or_too_many_preferred_regions() -> None:
    db = FakeDb()
    user = make_user()

    try:
        profile_service.update_profile(
            db,  # type: ignore[arg-type]
            user,
            ProfileUpdate(preferredRegions=["부산", "달나라"]),
        )
    except profile_service.ProfileServiceError as error:
        assert error.status_code == 422
    else:
        raise AssertionError("invalid preferred region should be rejected")

    try:
        profile_service.update_profile(
            db,  # type: ignore[arg-type]
            user,
            ProfileUpdate(preferredRegions=["서울", "부산", "대구", "인천"]),
        )
    except profile_service.ProfileServiceError as error:
        assert error.status_code == 422
    else:
        raise AssertionError("more than three preferred regions should be rejected")


def test_skip_profile_setup_marks_skip_and_onboarding_complete() -> None:
    db = FakeDb()
    user = make_user()

    result = profile_service.skip_profile_setup(
        db,  # type: ignore[arg-type]
        user,
    )

    assert result["onboardingCompleted"] is True
    assert result["nicknameSetupCompleted"] is False
    assert user.onboarding_completed is True
    assert user.profile_setup_skipped is True
    assert user.preferred_regions == "제주,부산"
    assert db.added == [user]
    assert db.flushed is True
    assert db.committed is True
