"""Admin eligible island catalog review API — real sqlite session behind the routes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.routes import admin as admin_routes
from app.db.base import Base
from app.main import app
from app.models import EligibleIsland, User
from app.repositories.eligible_islands import CATALOG_KEY_ISLAND_VISIT_2026 as KEY
from app.services import eligible_island_notice
from app.services.eligible_island_catalog import approve_snapshot, stage_snapshot
from app.services.eligible_island_notice import EligibleIslandCollectionResult, ParsedIsland, SourceDocument

client = TestClient(app)
BASE = f"/api/admin/eligible-island-catalogs/{KEY}"
COLLECT_URL = f"{BASE}/collect"
SNAPSHOT_LIST_URL = f"{BASE}/snapshots"


def make_user(user_id: int, *, role: str) -> User:
    return User(
        id=user_id,
        email=f"user-{user_id}@example.com",
        nickname=f"user-{user_id}",
        role=role,
        onboarding_completed=True,
        created_at=datetime(2026, 5, 27, 0, 0, 0),
        updated_at=datetime(2026, 5, 27, 0, 0, 0),
    )


@pytest.fixture
def db() -> Session:
    # TestClient runs the app in another thread: share one in-memory connection across threads.
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with TestingSessionLocal() as session:
        yield session


@pytest.fixture
def admin(db: Session) -> User:
    user = make_user(1, role="admin")
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def as_admin(db: Session, admin: User):
    app.dependency_overrides[admin_routes.get_optional_db] = lambda: db
    app.dependency_overrides[admin_routes.get_current_user] = lambda: admin
    yield admin
    app.dependency_overrides.pop(admin_routes.get_optional_db, None)
    app.dependency_overrides.pop(admin_routes.get_current_user, None)


@pytest.fixture
def as_user(db: Session):
    app.dependency_overrides[admin_routes.get_optional_db] = lambda: db
    app.dependency_overrides[admin_routes.get_current_user] = lambda: make_user(2, role="user")
    yield
    app.dependency_overrides.pop(admin_routes.get_optional_db, None)
    app.dependency_overrides.pop(admin_routes.get_current_user, None)


def stage(db: Session, pairs, *, fingerprint: str):
    return stage_snapshot(
        db,
        catalog_key=KEY,
        entries=[ParsedIsland(name, name, jurisdiction) for name, jurisdiction in pairs],
        notice_url="https://www.visitisland.kr/notice/1",
        notice_title="대상 섬",
        documents=[SourceDocument("https://www.visitisland.kr/files/list.xlsx", "list.xlsx", fingerprint)],
        fetched_at=datetime(2026, 9, 14, tzinfo=UTC),
    )


def test_non_admin_cannot_collect_list_or_approve_catalog(as_user) -> None:
    assert client.post(COLLECT_URL).status_code == 403
    assert client.get(SNAPSHOT_LIST_URL).status_code == 403
    assert client.post(f"{SNAPSHOT_LIST_URL}/1/approve").status_code == 403


def test_unknown_catalog_is_404(as_admin) -> None:
    assert client.get("/api/admin/eligible-island-catalogs/nope/snapshots").status_code == 404
    assert client.post("/api/admin/eligible-island-catalogs/nope/collect").status_code == 404


def test_snapshot_item_has_catalog_diff_not_policy_review_fields(db: Session, as_admin) -> None:
    stage(db, [("가거도", "전남 신안군")], fingerprint="1" * 64)
    db.commit()
    body = client.get(SNAPSHOT_LIST_URL).json()
    item = body["items"][0]
    assert {"addedCount", "removedCount", "changedCount", "sourceNoticeUrl", "attachmentFiles", "reviewStatus"} <= set(item)
    assert "externalSourceRecordId" not in item
    assert item["attachmentFiles"] == [{"url": "https://www.visitisland.kr/files/list.xlsx", "filename": "list.xlsx", "sha256": "1" * 64}]
    assert (body["total"], body["approvedSnapshotId"], body["approvedEntryCount"]) == (1, None, 0)


def test_approve_then_detail_and_stale_approval_conflict(db: Session, as_admin) -> None:
    first = stage(db, [("가거도", "전남 신안군"), ("홍도", "전남 신안군")], fingerprint="1" * 64).snapshot
    db.commit()
    approved = client.post(f"{SNAPSHOT_LIST_URL}/{first.id}/approve")
    assert approved.status_code == 200
    assert (approved.json()["reviewStatus"], approved.json()["isCurrentApproved"]) == ("approved", True)
    assert sorted(row.normalized_name for row in db.scalars(select(EligibleIsland)).all()) == ["가거도", "홍도"]

    second = stage(db, [("가거도", "전남 신안군"), ("흑산도", "전남 신안군")], fingerprint="2" * 64).snapshot
    db.commit()
    detail = client.get(f"{SNAPSHOT_LIST_URL}/{second.id}").json()
    assert [row["normalizedName"] for row in detail["added"]] == ["흑산도"]
    assert [row["normalizedName"] for row in detail["removed"]] == ["홍도"]
    assert [row["normalizedName"] for row in detail["unchanged"]] == ["가거도"]
    assert (detail["addedTotal"], detail["removedTotal"], detail["unchangedTotal"]) == (1, 1, 1)
    assert detail["snapshot"]["isCurrentApproved"] is False

    # re-approving the already approved snapshot is a conflict, not a silent no-op
    assert client.post(f"{SNAPSHOT_LIST_URL}/{first.id}/approve").status_code == 409
    assert client.post(f"{SNAPSHOT_LIST_URL}/999/approve").status_code == 404
    assert client.get(f"{SNAPSHOT_LIST_URL}/abc").status_code == 404


def test_reject_requires_note_and_superseded_cannot_be_approved(db: Session, as_admin) -> None:
    stale = stage(db, [("가거도", "전남 신안군")], fingerprint="1" * 64).snapshot
    current = stage(db, [("홍도", "전남 신안군")], fingerprint="2" * 64).snapshot
    db.commit()
    assert client.post(f"{SNAPSHOT_LIST_URL}/{stale.id}/approve").status_code == 409
    assert client.post(f"{SNAPSHOT_LIST_URL}/{current.id}/reject", json={"note": ""}).status_code == 422
    assert client.post(f"{SNAPSHOT_LIST_URL}/{current.id}/reject", json={"note": "   "}).status_code == 422
    rejected = client.post(f"{SNAPSHOT_LIST_URL}/{current.id}/reject", json={"note": "wrong file"})
    assert rejected.status_code == 200
    assert (rejected.json()["reviewStatus"], rejected.json()["reviewNote"]) == ("rejected", "wrong file")
    assert db.scalar(select(EligibleIsland)) is None


def test_collect_reports_parser_failure_as_outcome_without_stack_trace(db: Session, as_admin, monkeypatch) -> None:
    monkeypatch.setattr(
        eligible_island_notice,
        "collect_eligible_island_catalog",
        lambda session, **kwargs: EligibleIslandCollectionResult(outcome="parser_changed", error="parser_changed: no rows"),
    )
    response = client.post(COLLECT_URL)
    assert response.status_code == 200
    assert response.json() == {"outcome": "parser_changed", "snapshotId": None, "entryCount": 0, "error": "parser_changed: no rows"}


def test_collect_uses_the_code_owned_notice_url(db: Session, as_admin, monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_collect(session, **kwargs):
        seen.update(kwargs)
        return EligibleIslandCollectionResult(outcome="created", snapshot_id=5, entry_count=3)

    monkeypatch.setattr(eligible_island_notice, "collect_eligible_island_catalog", fake_collect)
    response = client.post(COLLECT_URL)
    assert response.json() == {"outcome": "created", "snapshotId": "5", "entryCount": 3, "error": None}
    assert seen["catalog_key"] == KEY
    assert seen["notice_url"] == "https://www.visitisland.kr/promotion2"
