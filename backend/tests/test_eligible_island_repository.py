"""Eligible island catalog schema and repository tests (sqlite in-memory)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.repositories.eligible_islands import (
    CATALOG_KEY_ISLAND_VISIT_2026,
    EligibleIslandCatalogError,
    add_snapshot_entry,
    create_snapshot,
    list_approved_entries,
    lock_catalog_row,
)


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with TestingSessionLocal() as session:
        yield session


def test_lock_catalog_row_materializes_code_owned_catalog(db: Session) -> None:
    catalog = lock_catalog_row(db, catalog_key=CATALOG_KEY_ISLAND_VISIT_2026)
    assert catalog.key == "island_visit_2026"
    assert catalog.approved_snapshot_id is None
    # 두 번 잠가도 같은 행이다 — 코드 소유 행은 중복 생성되지 않는다.
    again = lock_catalog_row(db, catalog_key=CATALOG_KEY_ISLAND_VISIT_2026)
    assert again.id == catalog.id


def test_lock_catalog_row_rejects_unknown_key(db: Session) -> None:
    with pytest.raises(EligibleIslandCatalogError, match="catalog_not_found"):
        lock_catalog_row(db, catalog_key="no_such_catalog")


def test_approved_entries_are_empty_before_any_approval(db: Session) -> None:
    assert list_approved_entries(db, catalog_key=CATALOG_KEY_ISLAND_VISIT_2026) == []


def test_same_name_is_retained_when_jurisdiction_differs(db: Session) -> None:
    snapshot = create_snapshot(db, catalog_key=CATALOG_KEY_ISLAND_VISIT_2026)
    add_snapshot_entry(db, snapshot=snapshot, name="가거도", jurisdiction="전남 신안군")
    add_snapshot_entry(db, snapshot=snapshot, name="가거도", jurisdiction="경남 통영시")
    db.commit()
    assert snapshot.entry_count == 2


def test_same_name_and_jurisdiction_is_rejected(db: Session) -> None:
    snapshot = create_snapshot(db, catalog_key=CATALOG_KEY_ISLAND_VISIT_2026)
    add_snapshot_entry(db, snapshot=snapshot, name="가거도", jurisdiction="전남 신안군")
    add_snapshot_entry(db, snapshot=snapshot, name="가거도", jurisdiction="전남 신안군")
    with pytest.raises(IntegrityError):
        db.commit()


def test_snapshot_starts_pending(db: Session) -> None:
    snapshot = create_snapshot(db, catalog_key=CATALOG_KEY_ISLAND_VISIT_2026)
    db.commit()
    assert snapshot.review_status == "pending"
    assert snapshot.entry_count == 0
