"""Per-trip (team) island support application progress: view, checks, transitions, checklist, visibility."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, Integer, create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import trips as trip_routes
from app.db.base import Base
from app.main import app
from app.models import Policy, Trip, TripDay, TripMember, TripPlace, TripPolicy
from app.models import User as UserModel
from app.models import policy_status
from app.repositories.eligible_islands import CATALOG_KEY_ISLAND_VISIT_2026
from app.schemas.trip import LinkedTripPolicy, UpdateTripPolicyApplicationRequest
from app.services import policies as policy_service
from app.services import trips as trip_service
from app.services.eligible_island_catalog import approve_snapshot, stage_snapshot
from app.services.eligible_island_notice import ParsedIsland, SourceDocument
from app.services.policy_semantic_mapping import map_external_source_semantics
from test_island_application_guide import island_record

ISLAND_SLUG = "travelmonth-81"
DOCUMENTS = [
    "신분증",
    "통장사본",
    "왕복 배편 승선권 혹은 영수증",
    "실 결제 영수증 (카드, 현금 영수증 또는 송금 계좌 이체 내역 등)",
    "OTA 이용 시, 예약 및 결제 내역",
]


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    mutated = []
    for table in Base.metadata.tables.values():
        for column in table.c:
            if column.primary_key and isinstance(column.type, BigInteger):
                mutated.append((column, column.type))
                column.type = Integer()
    try:
        Base.metadata.create_all(engine)
        with sessionmaker(bind=engine, expire_on_commit=False)() as session:
            yield session
        Base.metadata.drop_all(engine)
    finally:
        for column, original in mutated:
            column.type = original


def freeze(monkeypatch, day: date) -> None:
    monkeypatch.setattr(policy_status, "policy_visibility_date", lambda now=None: day)


def make_user(user_id: int, nickname: str, role: str = "user") -> UserModel:
    return UserModel(
        id=user_id,
        email=f"user-{user_id}@travel.kr",
        nickname=nickname,
        role=role,
        onboarding_completed=True,
        created_at=datetime(2026, 5, 4),
        updated_at=datetime(2026, 5, 4),
    )


def seed(
    db,
    *,
    start: date = date(2026, 10, 3),
    end: date = date(2026, 10, 4),
    place: str = "가거도",
    approved_islands: tuple[str, ...] = ("가거도",),
):
    owner, editor, viewer, admin = make_user(1, "Owner"), make_user(2, "Editor"), make_user(3, "Viewer"), make_user(50, "Admin", "admin")
    island = Policy(
        id=310,
        slug=ISLAND_SLUG,
        title="2026 섬 여행비 지원",
        region="전국",
        status="active",
        source_category="island_visit",
        benefit_detail="여행비 10만원",
        end_date=date(2026, 9, 21),
        structured_detail=map_external_source_semantics(island_record()).structured_detail,
    )
    plain = Policy(id=311, slug="plain", title="Plain", region="전국", status="active", source_category="local_half_trip")
    trip = Trip(id=900, owner_id=1, title="섬 여행", start_date=start, end_date=end, region="전남", status="draft", revision=1)
    db.add_all([owner, editor, viewer, admin, island, plain, trip])
    db.flush()
    db.add_all(
        [
            TripMember(trip_id=900, user_id=1, role="owner"),
            TripMember(trip_id=900, user_id=2, role="editor"),
            TripMember(trip_id=900, user_id=3, role="viewer"),
        ]
    )
    day = TripDay(id=901, trip_id=900, day_number=1, date=start)
    db.add(day)
    db.flush()
    db.add(TripPlace(id=902, trip_day_id=901, place_name=place, order_num=1))
    db.add_all([TripPolicy(id=903, trip_id=900, policy_id=310), TripPolicy(id=904, trip_id=900, policy_id=311)])
    db.commit()
    if approved_islands:
        staged = stage_snapshot(
            db,
            catalog_key=CATALOG_KEY_ISLAND_VISIT_2026,
            entries=[ParsedIsland(name, name, "전남 신안군") for name in approved_islands],
            notice_url="https://www.visitisland.kr/notice/1",
            notice_title="대상 섬",
            documents=[SourceDocument("https://www.visitisland.kr/files/list.xlsx", "list.xlsx", "f" * 64)],
            fetched_at=datetime(2026, 9, 14, tzinfo=UTC),
        )
        approve_snapshot(db, catalog_key=CATALOG_KEY_ISLAND_VISIT_2026, snapshot_id=staged.snapshot.id, admin=admin)
    return owner, editor, viewer


def linked(payload: dict, slug: str) -> dict | None:
    return next((item for item in payload["linkedPolicies"] if item["slug"] == slug), None)


def patch(db, user, **fields):
    return trip_service.update_trip_policy_application(
        db, user, "900", ISLAND_SLUG, UpdateTripPolicyApplicationRequest(**fields)
    )


# --- view and computed checks ----------------------------------------------------------------------


def test_trip_detail_carries_the_island_application_view(db, monkeypatch) -> None:
    freeze(monkeypatch, date(2026, 9, 19))
    owner, _, _ = seed(db)

    payload = trip_service.get_trip("900", db, owner)
    island = linked(payload, ISLAND_SLUG)

    assert island["deadline"] == "2026-09-21"
    application = island["application"]
    assert (application["status"], application["roundKey"]) == ("not_started", "2")
    assert application["checks"] == {
        "inTravelWindow": True,
        "meetsMinNights": True,
        "eligibleIslandMatched": True,
        "applyDeadline": "2026-09-21T18:00",
        "documentsDueDate": "2026-10-18",
    }
    assert [(item["key"], item["label"], item["checked"]) for item in application["checklist"]] == [(doc, doc, False) for doc in DOCUMENTS]
    assert (application["updatedAt"], application["updatedBy"]) == (None, None)
    assert LinkedTripPolicy(**island).application is not None

    plain = linked(payload, "plain")
    assert plain.get("application") is None
    assert plain["deadline"] is None


def test_checks_flag_a_day_trip_outside_the_window_without_an_island(db, monkeypatch) -> None:
    freeze(monkeypatch, date(2026, 9, 19))
    owner, _, _ = seed(db, start=date(2026, 12, 1), end=date(2026, 12, 1), place="목포역")

    checks = linked(trip_service.get_trip("900", db, owner), ISLAND_SLUG)["application"]["checks"]

    assert checks["inTravelWindow"] is False
    assert checks["meetsMinNights"] is False
    assert checks["eligibleIslandMatched"] is False
    assert checks["documentsDueDate"] == "2026-12-15"


def test_island_policy_stays_linked_after_the_apply_deadline_while_its_round_is_active(db, monkeypatch) -> None:
    owner, _, _ = seed(db)

    freeze(monkeypatch, date(2026, 10, 5))
    assert linked(trip_service.get_trip("900", db, owner), ISLAND_SLUG) is not None

    freeze(monkeypatch, date(2026, 11, 19))  # round 2 documents were due 11/18
    assert linked(trip_service.get_trip("900", db, owner), ISLAND_SLUG) is None


# --- updates --------------------------------------------------------------------------------------


def test_status_moves_one_step_at_a_time(db, monkeypatch) -> None:
    freeze(monkeypatch, date(2026, 9, 19))
    owner, _, _ = seed(db)

    view = patch(db, owner, status="applied")
    assert (view["status"], view["updatedBy"]) == ("applied", "Owner")
    assert view["updatedAt"] is not None

    with pytest.raises(trip_service.TripServiceError) as skipped:
        patch(db, owner, status="paid")
    assert (skipped.value.status_code, skipped.value.detail) == (409, "Invalid application status transition")

    assert patch(db, owner, status="selected")["status"] == "selected"
    assert patch(db, owner, status="applied")["status"] == "applied"  # one step back is allowed
    assert patch(db, owner, status="not_selected")["status"] == "not_selected"
    with pytest.raises(trip_service.TripServiceError) as terminal:
        patch(db, owner, status="traveled")
    assert terminal.value.status_code == 409


def test_checklist_persists_only_checked_documents_and_rejects_unknown_keys(db, monkeypatch) -> None:
    freeze(monkeypatch, date(2026, 9, 19))
    _, editor, _ = seed(db)

    patch(db, editor, checklist={"신분증": True, "통장사본": True})
    view = patch(db, editor, checklist={"통장사본": False})

    assert [item["key"] for item in view["checklist"] if item["checked"]] == ["신분증"]
    assert db.get(TripPolicy, 903).application_checklist == {"신분증": True}
    assert view["updatedBy"] == "Editor"

    with pytest.raises(trip_service.TripServiceError) as unknown:
        patch(db, editor, checklist={"주민등록등본": True})
    assert (unknown.value.status_code, unknown.value.detail) == (422, "Unknown application document")


def test_updates_need_an_editor_and_a_linked_island_policy(db, monkeypatch) -> None:
    freeze(monkeypatch, date(2026, 9, 19))
    owner, _, viewer = seed(db)

    with pytest.raises(trip_service.TripServiceError) as forbidden:
        patch(db, viewer, status="applied")
    assert forbidden.value.status_code == 403

    with pytest.raises(trip_service.TripServiceError) as not_island:
        trip_service.update_trip_policy_application(db, owner, "900", "plain", UpdateTripPolicyApplicationRequest(status="applied"))
    assert not_island.value.status_code == 404

    db.delete(db.get(TripPolicy, 903))
    db.commit()
    with pytest.raises(trip_service.TripServiceError) as unlinked:
        patch(db, owner, status="applied")
    assert unlinked.value.status_code == 404


def test_progress_can_be_updated_after_the_apply_deadline_while_the_round_is_active(db, monkeypatch) -> None:
    owner, _, _ = seed(db)
    freeze(monkeypatch, date(2026, 10, 5))

    assert patch(db, owner, status="applied")["status"] == "applied"

    freeze(monkeypatch, date(2026, 11, 19))
    with pytest.raises(trip_service.TripServiceError) as closed:
        patch(db, owner, status="selected")
    assert closed.value.status_code == 404


def test_applied_policy_links_show_each_trip_application_status(db, monkeypatch) -> None:
    owner, _, _ = seed(db)
    freeze(monkeypatch, date(2026, 10, 5))  # after the 9/21 card deadline, round still active
    link = db.get(TripPolicy, 903)
    link.application_status = "traveled"
    db.commit()

    groups = {group["policy"]["slug"]: group for group in policy_service.list_applied_policy_links(db, owner)}

    assert groups[ISLAND_SLUG]["linkedTrips"][0]["applicationStatus"] == "traveled"


# --- route ----------------------------------------------------------------------------------------


client = TestClient(app)


def test_application_route_delegates_and_maps_errors(monkeypatch) -> None:
    fake_db = object()
    user = make_user(1, "Owner")
    app.dependency_overrides[trip_routes.get_optional_db] = lambda: fake_db
    app.dependency_overrides[trip_routes.get_current_user] = lambda: user
    calls = []

    def fake_update(db, current_user, trip_id, policy_slug, payload):
        calls.append((db is fake_db, current_user is user, trip_id, policy_slug, payload.status, payload.checklist))
        if payload.status == "paid":
            raise trip_service.TripServiceError(409, "Invalid application status transition")
        return {
            "status": "applied",
            "roundKey": "2",
            "checklist": [{"key": "신분증", "label": "신분증", "checked": True}],
            "checks": {"inTravelWindow": True, "meetsMinNights": True, "eligibleIslandMatched": None, "applyDeadline": None, "documentsDueDate": None},
            "updatedAt": "2026-09-19T00:00:00Z",
            "updatedBy": "Owner",
        }

    monkeypatch.setattr(trip_routes.trip_service, "update_trip_policy_application", fake_update)
    try:
        ok = client.patch(f"/api/trips/7/policies/{ISLAND_SLUG}/application", json={"status": "applied", "checklist": {"신분증": True}})
        conflict = client.patch(f"/api/trips/7/policies/{ISLAND_SLUG}/application", json={"status": "paid"})
        invalid = client.patch(f"/api/trips/7/policies/{ISLAND_SLUG}/application", json={"status": "done"})
    finally:
        app.dependency_overrides.pop(trip_routes.get_optional_db, None)
        app.dependency_overrides.pop(trip_routes.get_current_user, None)

    assert ok.status_code == 200
    assert ok.json()["status"] == "applied"
    assert calls[0] == (True, True, "7", ISLAND_SLUG, "applied", {"신분증": True})
    assert (conflict.status_code, conflict.json()) == (409, {"detail": "Invalid application status transition"})
    assert invalid.status_code == 422
