from datetime import datetime

import pytest

from app.models import User as UserModel
from app.services import nicknames


class FakeDb:
    def __init__(self) -> None:
        self.committed = False
        self.refreshed: object | None = None
        self.added: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.committed = True

    def flush(self) -> None:
        pass

    def refresh(self, value: object) -> None:
        self.refreshed = value


def make_user() -> UserModel:
    return UserModel(
        id=1,
        email="test.user@example.com",
        nickname="기존닉네임",
        created_at=datetime(2026, 5, 4, 0, 0, 0),
        updated_at=datetime(2026, 5, 4, 0, 0, 0),
    )


def test_generate_random_nickname_uses_adjective_noun_number_pattern() -> None:
    nickname = nicknames.generate_random_nickname()

    assert any(nickname.startswith(adjective) for adjective in nicknames.ADJECTIVES)
    assert any(noun in nickname for noun in nicknames.NOUNS)
    assert nickname[-3:].isdigit()


def test_update_nickname_trims_and_persists() -> None:
    db = FakeDb()
    user = make_user()

    updated = nicknames.update_nickname(db, user, "  알뜰한 여행자 482  ")

    assert updated.nickname == "알뜰한 여행자 482"
    assert db.committed is True
    assert db.refreshed is user


def test_update_nickname_rejects_invalid_lengths() -> None:
    with pytest.raises(nicknames.NicknameServiceError):
        nicknames.update_nickname(FakeDb(), make_user(), "A")

    with pytest.raises(nicknames.NicknameServiceError):
        nicknames.update_nickname(FakeDb(), make_user(), "가" * 21)
