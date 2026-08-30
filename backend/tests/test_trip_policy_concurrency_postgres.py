"""일정당 숙박세일 정책 하나 규칙이 동시 요청에서도 지켜지는지 본다.

`add_policy_to_trip` 은 확인 후 삽입 구조라, 잠금이 없으면 서로 다른 숙박세일
정책을 동시에 요청했을 때 두 요청이 모두 "기존 없음"을 보고 각각 삽입한다.
DB 제약도 (trip_id, policy_id) 뿐이라 이를 막지 못한다.

SQLite 는 FOR UPDATE 를 조용히 생략하므로 이 검증은 PostgreSQL 이 필요하다.
기본 실행에서는 건너뛰고, 로컬 db 컨테이너가 떠 있을 때 환경변수로 켠다.

    RUN_POSTGRES_CONCURRENCY_TESTS=1 pytest tests/test_trip_policy_concurrency_postgres.py
"""

from __future__ import annotations

import os
import threading
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models import Policy, Trip, TripPolicy, User
from app.services import trips as trip_service

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_CONCURRENCY_TESTS") != "1",
    reason="set RUN_POSTGRES_CONCURRENCY_TESTS=1 for PostgreSQL concurrency tests",
)

TRIP_ID = 990_001
USER_ID = 990_002
GOSEONG_ID = 990_003
SAMCHEOK_ID = 990_004


def _url() -> str:
    return os.getenv(
        "POSTGRES_CONCURRENCY_TEST_DATABASE_URL",
        "postgresql+psycopg://travelhunter:travelhunter@127.0.0.1:55432/travelhunter",
    )


@pytest.fixture
def seeded_engine():
    engine = create_engine(_url())
    _cleanup(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        session.add_all(
            [
                User(
                    id=USER_ID,
                    email=f"concurrency-{USER_ID}@travel.kr",
                    nickname="Concurrency User",
                    onboarding_completed=True,
                    created_at=datetime(2026, 5, 4),
                    updated_at=datetime(2026, 5, 4),
                ),
                Policy(
                    id=GOSEONG_ID,
                    slug=f"stay-discount-concurrency-goseong-{GOSEONG_ID}",
                    title="[고성] 2026 대한민국 숙박세일 페스타 숙박 할인",
                    benefit_detail="최대 7만원",
                    region="강원",
                    status="active",
                    source_category="stay_discount",
                ),
                Policy(
                    id=SAMCHEOK_ID,
                    slug=f"stay-discount-concurrency-samcheok-{SAMCHEOK_ID}",
                    title="[삼척] 2026 대한민국 숙박세일 페스타 숙박 할인",
                    benefit_detail="최대 7만원",
                    region="강원",
                    status="active",
                    source_category="stay_discount",
                ),
                Trip(
                    id=TRIP_ID,
                    owner_id=USER_ID,
                    title="Concurrency trip",
                    start_date=date(2026, 7, 1),
                    end_date=date(2026, 7, 2),
                    region="강원",
                    status="draft",
                ),
            ]
        )
        session.commit()
    try:
        yield engine
    finally:
        _cleanup(engine)
        engine.dispose()


def _cleanup(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("delete from trip_policies where trip_id = :trip_id"),
            {"trip_id": TRIP_ID},
        )
        connection.execute(text("delete from trips where id = :id"), {"id": TRIP_ID})
        connection.execute(
            text("delete from policies where id in (:a, :b)"),
            {"a": GOSEONG_ID, "b": SAMCHEOK_ID},
        )
        connection.execute(text("delete from users where id = :id"), {"id": USER_ID})


def test_two_sessions_cannot_attach_two_stay_discount_areas(seeded_engine) -> None:
    Session = sessionmaker(bind=seeded_engine, expire_on_commit=False)
    started = threading.Barrier(2)
    outcomes: dict[str, object] = {}

    def attach(name: str, policy_id: int) -> None:
        with Session() as session:
            user = session.get(User, USER_ID)
            slug = session.get(Policy, policy_id).slug
            # 두 세션이 같은 지점에서 출발해야 경쟁이 재현된다.
            started.wait(timeout=10)
            try:
                trip_service.add_policy_to_trip(session, user, str(TRIP_ID), slug)
                outcomes[name] = "added"
            except trip_service.TripServiceError as error:
                outcomes[name] = error.status_code
            except Exception as error:  # noqa: BLE001 - 실패 원인을 그대로 보고 싶다
                outcomes[name] = repr(error)

    first = threading.Thread(target=attach, args=("first", GOSEONG_ID))
    second = threading.Thread(target=attach, args=("second", SAMCHEOK_ID))
    first.start()
    second.start()
    first.join(timeout=20)
    second.join(timeout=20)

    results = sorted(str(value) for value in outcomes.values())
    assert results == ["409", "added"], f"unexpected outcomes: {outcomes}"

    with Session() as session:
        linked = (
            session.query(TripPolicy).filter(TripPolicy.trip_id == TRIP_ID).count()
        )
    assert linked == 1
