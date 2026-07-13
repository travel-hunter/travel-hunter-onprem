from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from app.models import User
from app.repositories import users as user_repository


ADJECTIVES = [
    "알뜰한",
    "느긋한",
    "용감한",
    "반짝이는",
    "부지런한",
    "상쾌한",
    "꼼꼼한",
    "즐거운",
]

NOUNS = [
    "여행자",
    "혜택헌터",
    "바다탐험가",
    "도시산책가",
    "휴가설계자",
    "정책수집가",
    "지도탐험가",
    "일정메이커",
]


class NicknameServiceError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def generate_random_nickname() -> str:
    adjective = secrets.choice(ADJECTIVES)
    noun = secrets.choice(NOUNS)
    suffix = secrets.randbelow(900) + 100
    return f"{adjective}{noun}{suffix}"


def normalize_nickname(value: str) -> str:
    nickname = value.strip()
    if len(nickname) < 2:
        raise NicknameServiceError(422, "Nickname must be at least 2 characters")
    if len(nickname) > 20:
        raise NicknameServiceError(422, "Nickname must be at most 20 characters")
    return nickname


def update_nickname(db: Session, user: User, nickname: str) -> User:
    user.nickname = normalize_nickname(nickname)
    user_repository.mark_nickname_setup_completed(db, user)
    db.commit()
    db.refresh(user)
    return user
