from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.base import Base


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with TestingSessionLocal() as session:
        yield session


def test_builtin_source_rows_are_unique_and_review_gated(db: Session) -> None:
    from app.repositories.policy_collection_sources import list_collection_sources

    rows = list_collection_sources(db)

    assert {row.key for row in rows} == {
        "regional_benefit",
        "traffic_benefit",
        "local_half_trip",
        "digital_tourism_resident_card",
        "stay_discount",
        "island_visit",
    }
    assert len({row.key for row in rows}) == len(rows)
    assert {row.publication_mode for row in rows} == {"review"}


def test_admin_can_toggle_enabled_without_mutating_adapter_or_url(db: Session) -> None:
    from app.repositories.policy_collection_sources import (
        get_collection_source_by_key,
        update_collection_source_enabled,
    )

    source = get_collection_source_by_key(db, key="local_half_trip")
    assert source is not None
    adapter_key = source.adapter_key
    official_url = source.official_url

    update_collection_source_enabled(db, source=source, enabled=False)

    assert source.enabled is False
    assert source.adapter_key == adapter_key
    assert source.official_url == official_url


def test_new_island_source_starts_disabled_until_an_admin_enables_it(db: Session) -> None:
    from app.repositories.policy_collection_sources import get_collection_source_by_key

    source = get_collection_source_by_key(db, key="island_visit")

    assert source is not None
    assert source.enabled is False
    assert source.publication_mode == "review"



def test_builtin_source_initialization_ignores_a_stale_empty_key_snapshot(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import func, select

    from app.models import PolicyCollectionSource
    from app.repositories.policy_collection_sources import (
        BUILTIN_COLLECTION_SOURCES,
        ensure_builtin_collection_sources,
        list_collection_sources,
    )

    list_collection_sources(db)
    db.commit()

    class EmptyKeyResult:
        def all(self) -> list[str]:
            return []

    monkeypatch.setattr(db, "scalars", lambda _statement: EmptyKeyResult())

    ensure_builtin_collection_sources(db)

    count = db.scalar(select(func.count()).select_from(PolicyCollectionSource))
    assert count == len(BUILTIN_COLLECTION_SOURCES)
