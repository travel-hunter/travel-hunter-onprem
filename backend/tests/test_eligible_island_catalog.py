"""Eligible island catalog lifecycle: diff, safety gates, atomic approval."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.db.base import Base
from app.models import AdminAuditLog, EligibleIsland, EligibleIslandCatalogSnapshot, User
from app.repositories.eligible_islands import (
    CATALOG_KEY_ISLAND_VISIT_2026 as KEY,
    EligibleIslandCatalogError,
    list_approved_entries,
    lock_catalog_row,
)
from app.services.eligible_island_catalog import (
    approve_snapshot,
    get_snapshot_diff,
    reject_snapshot,
    stage_snapshot,
)
from app.services.eligible_island_notice import ParsedIsland, SourceDocument

FETCHED_AT = datetime(2026, 9, 14, tzinfo=UTC)
DOCS = [SourceDocument("https://www.visitisland.kr/files/list.xlsx", "list.xlsx", "a" * 64)]


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with TestingSessionLocal() as session:
        yield session


@pytest.fixture
def admin(db: Session) -> User:
    user = User(id=10, email="admin@example.com", nickname="admin", role="admin")
    db.add(user)
    db.flush()
    return user


def make_entries(pairs) -> list[ParsedIsland]:
    return [ParsedIsland(name, name, jurisdiction) for name, jurisdiction in pairs]


def make_names(count: int) -> list[str]:
    return [f"섬{index:03d}" for index in range(count)]


def make_many(count: int) -> list[ParsedIsland]:
    return make_entries((name, "전남 신안군") for name in make_names(count))


def stage_fixture_snapshot(db: Session, entries, *, fingerprint: str = "f" * 64):
    return stage_snapshot(
        db,
        catalog_key=KEY,
        entries=entries,
        notice_url="https://www.visitisland.kr/notice/1",
        notice_title="대상 섬",
        documents=[SourceDocument(DOCS[0].url, DOCS[0].filename, fingerprint)],
        fetched_at=FETCHED_AT,
    )


_counter = iter(range(1, 10_000))


def approve_fixture_snapshot(db: Session, entries, admin: User):
    result = stage_fixture_snapshot(db, entries, fingerprint=f"{next(_counter):064d}")
    assert result.outcome == "created", result
    return approve_snapshot(db, catalog_key=KEY, snapshot_id=result.snapshot.id, admin=admin)


def approved_names(db: Session) -> set[str]:
    return {row.normalized_name for row in list_approved_entries(db, catalog_key=KEY)}


# --- staging ------------------------------------------------------------------------


def test_stage_snapshot_records_added_and_removed_counts(db: Session, admin: User) -> None:
    approve_fixture_snapshot(db, make_entries([("가거도", "전남 신안군"), ("홍도", "전남 신안군")]), admin)
    candidate = stage_fixture_snapshot(db, make_entries([("가거도", "전남 신안군"), ("흑산도", "전남 신안군")]))
    assert candidate.outcome == "created"
    snapshot = candidate.snapshot
    assert (snapshot.added_count, snapshot.removed_count, snapshot.changed_count) == (1, 1, 0)
    assert snapshot.review_status == "pending"


def test_stage_snapshot_counts_display_name_change_as_changed(db: Session, admin: User) -> None:
    approve_fixture_snapshot(db, [ParsedIsland("가거도", "가거도", "전남 신안군")], admin)
    candidate = stage_fixture_snapshot(db, [ParsedIsland("가거도(소흑산도)", "가거도", "전남 신안군")])
    assert candidate.outcome == "created"
    assert (candidate.snapshot.added_count, candidate.snapshot.removed_count, candidate.snapshot.changed_count) == (0, 0, 1)


def test_stage_identical_set_creates_no_snapshot(db: Session, admin: User) -> None:
    approved = approve_fixture_snapshot(db, make_entries([("가거도", "전남 신안군")]), admin)
    result = stage_fixture_snapshot(db, make_entries([("가거도", "전남 신안군")]))
    assert (result.outcome, result.snapshot) == ("identical", None)
    assert db.scalars(select(EligibleIslandCatalogSnapshot.id)).all() == [approved.id]


def test_stage_empty_entries_creates_no_snapshot(db: Session) -> None:
    result = stage_fixture_snapshot(db, [])
    assert (result.outcome, result.snapshot) == ("empty", None)
    assert db.scalar(select(EligibleIslandCatalogSnapshot.id)) is None


def test_large_shrink_preserves_approved_catalog(db: Session, admin: User) -> None:
    approve_fixture_snapshot(db, make_many(100), admin)
    result = stage_fixture_snapshot(db, make_many(69))
    assert (result.outcome, result.snapshot) == ("suspicious_shrink", None)
    assert approved_names(db) == set(make_names(100))
    assert db.scalar(select(EligibleIslandCatalogSnapshot.id).where(EligibleIslandCatalogSnapshot.review_status == "pending")) is None


def test_shrink_at_thirty_percent_is_still_a_candidate(db: Session, admin: User) -> None:
    approve_fixture_snapshot(db, make_many(100), admin)
    result = stage_fixture_snapshot(db, make_many(70))
    assert result.outcome == "created"
    assert result.snapshot.removed_count == 30


def test_stage_supersedes_older_pending(db: Session) -> None:
    first = stage_fixture_snapshot(db, make_entries([("가거도", "전남 신안군")]), fingerprint="1" * 64)
    second = stage_fixture_snapshot(db, make_entries([("홍도", "전남 신안군")]), fingerprint="2" * 64)
    assert db.get(EligibleIslandCatalogSnapshot, first.snapshot.id).review_status == "superseded"
    assert second.snapshot.review_status == "pending"


def test_same_name_different_jurisdiction_kept_through_approval(db: Session, admin: User) -> None:
    approve_fixture_snapshot(db, make_entries([("가거도", "전남 신안군"), ("가거도", "경남 통영시")]), admin)
    rows = list_approved_entries(db, catalog_key=KEY)
    assert [(row.normalized_name, row.jurisdiction_name) for row in rows] == [("가거도", "경남 통영시"), ("가거도", "전남 신안군")]


# --- approval / rejection -------------------------------------------------------------


def test_same_content_as_latest_pending_reuses_it_even_with_new_fingerprint(db: Session) -> None:
    # Google Sheets xlsx exports are not byte-stable: same islands, different bytes every run.
    first = stage_fixture_snapshot(db, make_entries([("가거도", "전남 신안군"), ("홍도", "전남 신안군")]), fingerprint="1" * 64)
    again = stage_fixture_snapshot(db, make_entries([("홍도", "전남 신안군"), ("가거도", "전남 신안군")]), fingerprint="2" * 64)
    assert (again.outcome, again.snapshot.id) == ("unchanged", first.snapshot.id)
    assert db.get(EligibleIslandCatalogSnapshot, first.snapshot.id).review_status == "pending"
    assert len(db.scalars(select(EligibleIslandCatalogSnapshot.id)).all()) == 1


def test_display_name_change_versus_latest_pending_is_a_new_snapshot(db: Session) -> None:
    first = stage_fixture_snapshot(db, [ParsedIsland("가거도", "가거도", "전남 신안군")], fingerprint="1" * 64)
    renamed = stage_fixture_snapshot(db, [ParsedIsland("가거도(소흑산도)", "가거도", "전남 신안군")], fingerprint="2" * 64)
    assert renamed.outcome == "created"
    assert db.get(EligibleIslandCatalogSnapshot, first.snapshot.id).review_status == "superseded"


def test_pending_snapshot_is_invisible_until_approved(db: Session, admin: User) -> None:
    approve_fixture_snapshot(db, make_entries([("가거도", "전남 신안군")]), admin)
    stage_fixture_snapshot(db, make_entries([("가거도", "전남 신안군"), ("홍도", "전남 신안군")]))
    assert approved_names(db) == {"가거도"}


def test_approve_replaces_catalog_atomically_and_records_audit(db: Session, admin: User) -> None:
    first = approve_fixture_snapshot(db, make_entries([("가거도", "전남 신안군"), ("홍도", "전남 신안군")]), admin)
    staged = stage_fixture_snapshot(db, make_entries([("가거도", "전남 신안군"), ("흑산도", "전남 신안군")]))
    approved = approve_snapshot(db, catalog_key=KEY, snapshot_id=staged.snapshot.id, admin=admin)

    assert approved.review_status == "approved"
    assert approved.reviewed_by_user_id == admin.id
    assert approved_names(db) == {"가거도", "흑산도"}
    assert {row.snapshot_id for row in db.scalars(select(EligibleIsland)).all()} == {approved.id}
    catalog = lock_catalog_row(db, catalog_key=KEY)
    assert catalog.approved_snapshot_id == approved.id
    assert db.get(EligibleIslandCatalogSnapshot, first.id).review_status == "approved"  # history kept
    log = db.scalar(select(AdminAuditLog).where(AdminAuditLog.action == "eligible_island_catalog.approve").order_by(AdminAuditLog.id.desc()))
    assert log is not None and log.target_id == str(approved.id)
    assert log.after_json["entryCount"] == 2


def test_approve_rejects_superseded_rejected_and_unknown(db: Session, admin: User) -> None:
    stale = stage_fixture_snapshot(db, make_entries([("가거도", "전남 신안군")]), fingerprint="1" * 64)
    stage_fixture_snapshot(db, make_entries([("홍도", "전남 신안군")]), fingerprint="2" * 64)
    with pytest.raises(EligibleIslandCatalogError, match="snapshot_not_pending"):
        approve_snapshot(db, catalog_key=KEY, snapshot_id=stale.snapshot.id, admin=admin)
    with pytest.raises(EligibleIslandCatalogError, match="snapshot_not_found"):
        approve_snapshot(db, catalog_key=KEY, snapshot_id=9999, admin=admin)
    assert approved_names(db) == set()


def test_reject_requires_note_and_preserves_approved(db: Session, admin: User) -> None:
    approve_fixture_snapshot(db, make_entries([("가거도", "전남 신안군")]), admin)
    staged = stage_fixture_snapshot(db, make_entries([("홍도", "전남 신안군")]))
    with pytest.raises(EligibleIslandCatalogError, match="note_required"):
        reject_snapshot(db, catalog_key=KEY, snapshot_id=staged.snapshot.id, admin=admin, note="  ")
    rejected = reject_snapshot(db, catalog_key=KEY, snapshot_id=staged.snapshot.id, admin=admin, note="wrong file")
    assert (rejected.review_status, rejected.review_note) == ("rejected", "wrong file")
    assert approved_names(db) == {"가거도"}
    with pytest.raises(EligibleIslandCatalogError, match="snapshot_not_pending"):
        approve_snapshot(db, catalog_key=KEY, snapshot_id=rejected.id, admin=admin)


def test_snapshot_diff_lists_added_removed_unchanged(db: Session, admin: User) -> None:
    approve_fixture_snapshot(db, make_entries([("가거도", "전남 신안군"), ("홍도", "전남 신안군")]), admin)
    staged = stage_fixture_snapshot(db, make_entries([("가거도", "전남 신안군"), ("흑산도", "전남 신안군")]))
    diff = get_snapshot_diff(db, catalog_key=KEY, snapshot_id=staged.snapshot.id)
    assert [item.normalized_name for item in diff.added] == ["흑산도"]
    assert [item.normalized_name for item in diff.removed] == ["홍도"]
    assert [item.normalized_name for item in diff.unchanged] == ["가거도"]
