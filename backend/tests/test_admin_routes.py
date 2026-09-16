from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.routes import admin as admin_routes
from app.main import app
from app.models import User


client = TestClient(app)


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


def clear_overrides() -> None:
    app.dependency_overrides.pop(admin_routes.get_optional_db, None)
    app.dependency_overrides.pop(admin_routes.get_current_user, None)


def install_admin_dependencies(fake_db: object, user: User | None) -> None:
    app.dependency_overrides[admin_routes.get_optional_db] = lambda: fake_db
    if user is not None:
        app.dependency_overrides[admin_routes.get_current_user] = lambda: user


def test_admin_routes_reject_normal_users() -> None:
    fake_db = object()
    install_admin_dependencies(fake_db, make_user(2, role="user"))

    try:
        response = client.get("/api/admin/users")
    finally:
        clear_overrides()

    assert response.status_code == 403
    assert response.json() == {"detail": "Admin permission required"}


def test_admin_routes_list_users_for_admin(monkeypatch) -> None:
    fake_db = object()
    admin = make_user(1, role="admin")
    install_admin_dependencies(fake_db, admin)
    monkeypatch.setattr(
        admin_routes.admin_service,
        "list_users",
        lambda db, current_admin, **kwargs: {
            "items": [
                {
                    "id": "2",
                    "email": "user@example.com",
                    "nickname": "traveler",
                    "role": "user",
                    "onboardingCompleted": True,
                    "createdAt": "2026-05-27T00:00:00",
                    "updatedAt": "2026-05-27T00:00:00",
                }
            ],
            "total": 1,
            "limit": kwargs["limit"],
            "offset": kwargs["offset"],
        },
    )

    try:
        response = client.get("/api/admin/users")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["items"][0]["email"] == "user@example.com"


def test_admin_routes_external_source_summary_for_admin(monkeypatch) -> None:
    fake_db = object()
    admin = make_user(1, role="admin")
    install_admin_dependencies(fake_db, admin)
    monkeypatch.setattr(
        admin_routes.admin_service,
        "get_external_source_summary",
        lambda db, current_admin: {
            "items": [
                {
                    "sourceCategory": "local_half_trip",
                    "label": "반값여행",
                    "sourceName": "대한민국 반값여행",
                    "totalRecords": 16,
                    "activeRecords": 5,
                    "scheduledRecords": 7,
                    "endedRecords": 4,
                    "unknownRecords": 0,
                    "freshRecords": 5,
                    "promotedPolicyCount": 5,
                    "activePromotedPolicyCount": 5,
                    "latestFetchedAt": "2026-05-27T09:00:00",
                    "latestVerifiedAt": "2026-05-27T09:00:00",
                }
            ],
            "totalRecords": 16,
            "activeRecords": 5,
            "freshRecords": 5,
            "promotedPolicyCount": 5,
            "latestFetchedAt": "2026-05-27T09:00:00",
        },
    )

    try:
        response = client.get("/api/admin/external-sources/summary")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["items"][0]["label"] == "반값여행"


def test_admin_routes_list_pending_policy_review_candidates(monkeypatch) -> None:
    fake_db = object()
    admin = make_user(1, role="admin")
    install_admin_dependencies(fake_db, admin)
    candidate = SimpleNamespace(
        id=7, external_source_record_id=11, review_status="pending",
        change_kind="new", created_at=datetime(2026, 9, 13, 10, 0, 0)
    )
    record = SimpleNamespace(
        id=11, title="Island support", source_category="island_visit",
        detail_url=None, source_url="https://official.example/island", benefit_text="100000",
        region="Nationwide", city=None, status="scheduled", start_date=None, end_date=None
    )
    monkeypatch.setattr(
        admin_routes.policy_candidate_review,
        "list_pending_candidates",
        lambda db, *, limit, offset=0: [(candidate, record)],
    )
    monkeypatch.setattr(admin_routes.policy_candidate_review, "count_pending_candidates", lambda db: 1)

    try:
        response = client.get("/api/admin/policy-review-candidates")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["items"][0]["sourceCategory"] == "island_visit"
    assert response.json()["items"][0]["reviewStatus"] == "pending"


def test_admin_routes_list_collection_sources(monkeypatch) -> None:
    fake_db = object()
    admin = make_user(1, role="admin")
    install_admin_dependencies(fake_db, admin)
    source = SimpleNamespace(
        key="island_visit", display_name="Island Visit",
        official_url="https://official.example/island", source_category="island_visit",
        enabled=False, publication_mode="review", last_outcome=None,
        last_collected_at=None, last_error=None
    )
    monkeypatch.setattr(
        admin_routes.policy_collection_sources,
        "list_collection_sources",
        lambda db: [source],
    )

    try:
        response = client.get("/api/admin/policy-collection-sources")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["items"] == [{
        "key": "island_visit", "displayName": "Island Visit",
        "officialUrl": "https://official.example/island", "sourceCategory": "island_visit",
        "enabled": False, "publicationMode": "review", "expectedMinRecords": 0,
        "lastParsedCount": None, "autoApprovedLast24h": 0, "lastOutcome": None,
        "lastCollectedAt": None, "lastError": None
    }]


def _install_source_for_patch(monkeypatch, *, publication_mode: str = "review"):
    source = SimpleNamespace(
        key="local_half_trip", display_name="Korea Half-Price Travel",
        official_url="https://official.example/half", source_category="local_half_trip",
        enabled=True, publication_mode=publication_mode, expected_min_records=0, last_parsed_count=None,
        last_outcome=None, last_collected_at=None, last_error=None,
    )
    monkeypatch.setattr(admin_routes.policy_collection_sources, "get_collection_source_by_key", lambda db, *, key: source)

    def fake_update(db, *, source, enabled=None, publication_mode=None, expected_min_records=None):
        if enabled is not None:
            source.enabled = enabled
        if publication_mode is not None:
            source.publication_mode = publication_mode
        if expected_min_records is not None:
            source.expected_min_records = expected_min_records
        return source

    monkeypatch.setattr(admin_routes.policy_collection_sources, "update_collection_source", fake_update)
    return source


def test_admin_routes_refuse_auto_publish_without_human_baseline(monkeypatch) -> None:
    fake_db = SimpleNamespace(commit=lambda: None, rollback=lambda: None)
    install_admin_dependencies(fake_db, make_user(1, role="admin"))
    source = _install_source_for_patch(monkeypatch)
    monkeypatch.setattr(admin_routes.policy_candidate_review, "human_baseline_admin_id", lambda db, *, source_category: None)

    try:
        response = client.patch(
            "/api/admin/policy-collection-sources/local_half_trip",
            json={"publicationMode": "auto_after_reviewed_baseline"},
        )
    finally:
        clear_overrides()

    assert response.status_code == 409
    assert response.json() == {"detail": "baseline_required"}
    assert source.publication_mode == "review"


def test_admin_routes_enable_auto_publish_with_baseline_and_threshold(monkeypatch) -> None:
    fake_db = SimpleNamespace(commit=lambda: None, rollback=lambda: None)
    install_admin_dependencies(fake_db, make_user(1, role="admin"))
    source = _install_source_for_patch(monkeypatch)
    monkeypatch.setattr(admin_routes.policy_candidate_review, "human_baseline_admin_id", lambda db, *, source_category: 1)

    try:
        response = client.patch(
            "/api/admin/policy-collection-sources/local_half_trip",
            json={"publicationMode": "auto_after_reviewed_baseline", "expectedMinRecords": 11},
        )
        negative = client.patch("/api/admin/policy-collection-sources/local_half_trip", json={"expectedMinRecords": -1})
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert (response.json()["publicationMode"], response.json()["expectedMinRecords"]) == ("auto_after_reviewed_baseline", 11)
    assert source.enabled is True  # untouched when omitted
    assert negative.status_code == 422


def test_admin_routes_expose_review_reason_on_candidates(monkeypatch) -> None:
    fake_db = object()
    install_admin_dependencies(fake_db, make_user(1, role="admin"))
    candidate = SimpleNamespace(
        id=7, external_source_record_id=11, review_status="pending", change_kind="material_change",
        review_reason="identity_changed", created_at=datetime(2026, 9, 14, 10, 0, 0),
    )
    record = SimpleNamespace(
        id=11, title="Renamed support", source_category="local_half_trip", detail_url=None,
        source_url="https://official.example/half", benefit_text="support", region="Gangwon", city=None,
        status="active", start_date=None, end_date=None,
    )
    monkeypatch.setattr(admin_routes.policy_candidate_review, "list_pending_candidates", lambda db, *, limit, offset=0: [(candidate, record)])
    monkeypatch.setattr(admin_routes.policy_candidate_review, "count_pending_candidates", lambda db: 1)

    try:
        response = client.get("/api/admin/policy-review-candidates")
    finally:
        clear_overrides()

    assert response.json()["items"][0]["reviewReason"] == "identity_changed"


def test_admin_routes_page_pending_policy_review_candidates(monkeypatch) -> None:
    fake_db = object()
    admin = make_user(1, role="admin")
    install_admin_dependencies(fake_db, admin)
    candidate = SimpleNamespace(id=71, external_source_record_id=11, review_status="pending", change_kind="new", created_at=datetime(2026, 9, 13, 10, 0, 0))
    record = SimpleNamespace(id=11, title="Island support", source_category="island_visit", detail_url=None, source_url="https://official.example/island", benefit_text="100000", region="Nationwide", city=None, status="scheduled", start_date=None, end_date=None)
    monkeypatch.setattr(admin_routes.policy_candidate_review, "list_pending_candidates", lambda db, *, limit, offset=0: [(candidate, record)])
    monkeypatch.setattr(admin_routes.policy_candidate_review, "count_pending_candidates", lambda db: 71)

    try:
        response = client.get("/api/admin/policy-review-candidates?limit=50&offset=50")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json()["total"] == 71
    assert response.json()["limit"] == 50
    assert response.json()["offset"] == 50


def test_admin_routes_batch_approve_selected_policy_review_candidates(monkeypatch) -> None:
    fake_db = SimpleNamespace(commit=lambda: None, rollback=lambda: None)
    admin = make_user(1, role="admin")
    install_admin_dependencies(fake_db, admin)
    captured = {}
    monkeypatch.setattr(admin_routes.policy_candidate_review, "approve_pending_candidates", lambda db, *, candidate_ids, approve_all, admin, note: captured.update(candidate_ids=candidate_ids, approve_all=approve_all) or [])

    try:
        response = client.post("/api/admin/policy-review-candidates/approve-batch", json={"candidateIds": ["7", "8"], "approveAll": False})
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert captured == {"candidate_ids": ["7", "8"], "approve_all": False}


def test_admin_routes_batch_approve_all_pending_policy_review_candidates(monkeypatch) -> None:
    fake_db = SimpleNamespace(commit=lambda: None, rollback=lambda: None)
    admin = make_user(1, role="admin")
    install_admin_dependencies(fake_db, admin)
    captured = {}
    monkeypatch.setattr(admin_routes.policy_candidate_review, "approve_pending_candidates", lambda db, *, candidate_ids, approve_all, admin, note: captured.update(candidate_ids=candidate_ids, approve_all=approve_all) or [])

    try:
        response = client.post("/api/admin/policy-review-candidates/approve-batch", json={"candidateIds": [], "approveAll": True})
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert captured == {"candidate_ids": [], "approve_all": True}
