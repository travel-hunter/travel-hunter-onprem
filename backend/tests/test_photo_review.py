"""사진 검토(0047): 수집은 후보만, 관리자 확정만 앱 사진이 된다. 운영과 같은 autoflush=False 세션에서 시험한다."""

from __future__ import annotations

import itertools
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.api.routes import admin as admin_routes
from app.db.base import Base
from app.main import app
from app.models import (
    AdminAuditLog,
    PhotoReviewCandidate,
    PhotoReviewTarget,
    Policy,
    PolicyPhotoAssignment,
    RegionPhoto,
    User,
)
from app.services import photo_review
from app.services.photo_criteria import ImageProbeError
from app.services.region_photos import build_region_photo_index
from app.services.tour_api import TourApiAreaCode, TourApiConfigurationError, TourApiSpot

ID_MODELS = (Policy, PhotoReviewTarget, PhotoReviewCandidate, RegionPhoto, PolicyPhotoAssignment, AdminAuditLog)


@pytest.fixture
def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    # 운영 세션과 같이 autoflush 를 끈다. BigInteger PK 는 sqlite 가 자동으로 안 매기므로 넣기 전에 매긴다.
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    counter = itertools.count(1000)

    def assign_id(_mapper, _connection, target) -> None:
        if target.id is None:
            target.id = next(counter)

    for model in ID_MODELS:
        event.listen(model, "before_insert", assign_id)
    try:
        yield session_factory
    finally:
        for model in ID_MODELS:
            event.remove(model, "before_insert", assign_id)


@pytest.fixture
def db(factory) -> Session:
    with factory() as session:
        yield session


@pytest.fixture(autouse=True)
def fresh_job():
    photo_review._job = photo_review.CollectJob()
    yield
    photo_review._job = photo_review.CollectJob()


def spot(content_id: str, *, addr: str = "전라남도 영광군 법성면", title: str | None = None, **overrides) -> TourApiSpot:
    data: dict[str, object] = {
        "content_id": content_id,
        "title": title or f"관광지 {content_id}",
        "first_image": f"http://tong.visitkorea.or.kr/{content_id}.jpg",
        "first_image2": f"http://tong.visitkorea.or.kr/{content_id}_t.jpg",
        "addr1": addr,
        "area_code": "38",
        "sigungu_code": "14",
        "copyright_type": "Type1",
        "content_type_id": "12",
    }
    data.update(overrides)
    return TourApiSpot(**data)  # type: ignore[arg-type]


class Provider:
    """전남(38) · 영광군(14). 시군 목록은 분류마다 c{분류}-{번호}, 도 전체 목록은 s-{번호} + 시군 사진 몇 장."""

    def __init__(self, *, per_type: int = 10, search: list[TourApiSpot] | None = None) -> None:
        self.per_type = per_type
        self.search = search or []
        self.calls: list[tuple] = []

    def list_area_codes(self, *, area_code=None):
        if area_code == "38":
            return [TourApiAreaCode(code="14", name="영광군"), TourApiAreaCode(code="16", name="완도군")]
        return [TourApiAreaCode(code="38", name="전라남도"), TourApiAreaCode(code="35", name="경상북도")]

    def list_area_spots(self, *, area_code, sigungu_code=None, rows=10, content_type_id="12", page=1):
        self.calls.append(("list", area_code, sigungu_code, content_type_id, page))
        if page > 2:
            return []
        start = (page - 1) * self.per_type
        if sigungu_code:
            return [spot(f"c{content_type_id}-{n}", content_type_id=content_type_id) for n in range(start, start + self.per_type)]
        return [spot("c12-0"), *[spot(f"s-{n}", addr="전라남도 담양군") for n in range(start, start + self.per_type)]]

    def search_spots_by_keyword(self, *, keyword, rows=10, content_type_id="12"):
        self.calls.append(("search", keyword, content_type_id))
        return self.search


def landscape(_url: str):
    return (1200, 800)


def add_policy(db: Session, policy_id: int = 1, *, city: str | None = "영광", title: str = "[영광] 대한민국 반값여행 지원") -> Policy:
    policy = Policy(id=policy_id, slug=f"policy-{policy_id}", title=title, region="전남", city=city, status="active")
    db.add(policy)
    db.flush()
    return policy


def add_admin(db: Session) -> User:
    admin = User(id=10, email="admin@example.com", nickname="admin", role="admin")
    db.add(admin)
    db.flush()
    return admin


def target(db: Session, key: str) -> PhotoReviewTarget:
    return db.scalars(select(PhotoReviewTarget).where(PhotoReviewTarget.target_key == key)).one()


def images(t: PhotoReviewTarget) -> list[str]:
    return [c.image_url for c in t.candidates]


def test_collect_fills_the_city_first_then_its_policies_and_the_sido_row_without_overlap(db: Session) -> None:
    add_policy(db)
    add_policy(db, 2, city=None, title="전남 섬 여행 지원")   # 시군이 없는 정책이 도 전체 줄을 쓴다
    summary = photo_review.collect_candidates(db, Provider(), size_of=landscape)

    city, policy, sido = target(db, "region:전남|영광"), target(db, "policy:1"), target(db, "region:전남|")
    assert summary.targets_created == 4
    assert [len(t.candidates) for t in (city, policy, sido)] == [6, 6, 6]
    # 관광지 · 쇼핑 · 축제를 번갈아, 시군이 먼저 고르고 정책은 그다음 사진을 받는다
    assert [c.provider_content_id for c in city.candidates] == ["c12-0", "c38-0", "c15-0", "c12-1", "c38-1", "c15-1"]
    assert [c.provider_content_id for c in policy.candidates][:3] == ["c12-2", "c38-2", "c15-2"]
    all_images = images(city) + images(policy) + images(sido)
    assert len(all_images) == len(set(all_images))
    # 도 전체 줄은 시군 사진(c12-0)을 다시 쓰지 않는다
    assert "http://tong.visitkorea.or.kr/c12-0.jpg" not in images(sido)
    assert all(c.source == "collect" and c.image_width == 1200 for c in city.candidates)
    # 수집은 앱에 사진을 내걸지 않는다
    assert db.scalars(select(RegionPhoto)).all() == []
    assert db.scalars(select(PolicyPhotoAssignment)).all() == []


def test_collect_tops_up_to_six_and_leaves_decided_targets_alone(db: Session) -> None:
    add_policy(db)
    provider = Provider()
    photo_review.collect_candidates(db, provider, size_of=landscape)
    city = target(db, "region:전남|영광")
    city.status = "approved"
    policy = target(db, "policy:1")
    db.delete(policy.candidates[0])
    db.flush()
    db.expire_all()

    summary = photo_review.collect_candidates(db, provider, size_of=landscape)

    assert summary.decided_skipped == 1
    assert summary.candidates_added == 1
    assert len(target(db, "policy:1").candidates) == 6


def test_hidden_policies_and_unused_rows_are_neither_listed_nor_collected(db: Session) -> None:
    add_policy(db)
    hidden = add_policy(db, 2, title="[영광] 끝난 혜택")
    hidden.status = "hidden"
    db.add(PhotoReviewTarget(target_key="region:경북|안동", target_type="region", sido="경북", city="안동", status="pending"))
    db.flush()

    photo_review.collect_candidates(db, Provider(), size_of=landscape)

    assert target(db, "region:경북|안동").candidates == []
    assert db.scalars(select(PhotoReviewTarget).where(PhotoReviewTarget.target_key == "policy:2")).first() is None
    region = photo_review.list_targets(db, unit="region", status=None)
    assert [item["city"] for item in region["items"]] == ["영광"] and region["items"][0]["benefitCount"] == 1
    assert [item["policySlug"] for item in photo_review.list_targets(db, unit="policy", status=None)["items"]] == ["policy-1"]


def test_a_migrated_policy_target_without_a_city_takes_the_title_city(db: Session) -> None:
    # 0047 이 policies.city(비어 있음)로 만든 숙박세일 대상 - 제목의 [영광] 으로 그 시군 후보를 받는다
    add_policy(db, city=None, title="[영광] 2026 대한민국 숙박세일 페스타 숙박 할인")
    db.add(PhotoReviewTarget(target_key="policy:1", target_type="policy", sido="전남", city="", policy_id=1, status="pending"))
    db.flush()

    photo_review.collect_candidates(db, Provider(), size_of=landscape)

    policy = target(db, "policy:1")
    assert policy.city == "영광"
    assert all(c.provider_content_id.startswith("c") for c in policy.candidates) and len(policy.candidates) == 6


def test_collect_applies_the_criteria_and_skips_an_unreachable_image(db: Session) -> None:
    add_policy(db)

    class Picky(Provider):
        def list_area_spots(self, **kwargs):
            good = super().list_area_spots(**kwargs)
            if not kwargs.get("sigungu_code") or kwargs.get("content_type_id") != "12":
                return []
            return [
                spot("bad-type", copyright_type="Type2"),
                spot("hall", title="영광군 공영주차장"),
                spot("far", addr="경상북도 안동시"),
                spot("down"),
                *good,
            ]

    def size_of(url: str):
        if "down" in url:
            raise ImageProbeError("timeout")
        return (1200, 800)

    summary = photo_review.collect_candidates(db, Picky(), size_of=size_of)

    ids = [c.provider_content_id for c in target(db, "region:전남|영광").candidates]
    assert not {"bad-type", "hall", "far", "down"} & set(ids)
    assert summary.probe_failures >= 1


def test_city_without_a_sigungu_code_gets_no_candidates_instead_of_the_sido_list(db: Session) -> None:
    add_policy(db, city="가상", title="[가상] 혜택")
    photo_review.collect_candidates(db, Provider(), size_of=landscape)
    assert target(db, "region:전남|가상").candidates == []


def test_approve_publishes_the_photo_and_records_the_decision(db: Session) -> None:
    add_policy(db)
    admin = add_admin(db)
    photo_review.collect_candidates(db, Provider(), size_of=landscape)
    city = target(db, "region:전남|영광")
    chosen = city.candidates[2]

    photo_review.approve(db, str(city.id), str(chosen.id), admin)

    assert city.status == "approved" and city.approved_candidate_id == chosen.id and city.decided_by_user_id == 10
    resolved = build_region_photo_index(db).resolve("전남", "영광")
    assert resolved is not None and resolved.image_url == chosen.image_url
    assert resolved.attribution == "사진: 한국관광공사 · 공공누리 제1유형"
    log = db.scalars(select(AdminAuditLog)).one()
    assert (log.action, log.target_id) == ("photo_review.approve", "region:전남|영광")


def test_none_and_reopen_take_the_photo_down(db: Session) -> None:
    add_policy(db)
    admin = add_admin(db)
    photo_review.collect_candidates(db, Provider(), size_of=landscape)
    city = target(db, "region:전남|영광")
    photo_review.approve(db, str(city.id), str(city.candidates[0].id), admin)

    photo_review.reopen(db, str(city.id), admin)
    assert city.status == "pending" and city.approved_candidate_id is None
    assert build_region_photo_index(db).resolve("전남", "영광") is None

    photo_review.approve(db, str(city.id), str(city.candidates[1].id), admin)
    photo_review.mark_none(db, str(city.id), admin)
    assert city.status == "none"
    assert build_region_photo_index(db).resolve("전남", "영광") is None


def test_a_policy_left_alone_inherits_the_city_photo_and_its_own_photo_wins(db: Session) -> None:
    add_policy(db)
    admin = add_admin(db)
    photo_review.collect_candidates(db, Provider(), size_of=landscape)
    city, policy = target(db, "region:전남|영광"), target(db, "policy:1")
    photo_review.approve(db, str(city.id), str(city.candidates[0].id), admin)
    photo_review.mark_none(db, str(policy.id), admin)

    index = build_region_photo_index(db)
    assert index.resolve_policy(1, "전남", "영광").image_url == city.candidates[0].image_url
    item = photo_review.list_targets(db, unit="policy", status=None)["items"][0]
    assert item["inheritedPhoto"]["imageUrl"] == city.candidates[0].image_url
    assert item["policySlug"] == "policy-1" and item["status"] == "none" and item["decidedAt"].endswith("Z")

    photo_review.reopen(db, str(policy.id), admin)
    photo_review.approve(db, str(policy.id), str(policy.candidates[0].id), admin)
    assert build_region_photo_index(db).resolve_policy(1, "전남", "영광").image_url == policy.candidates[0].image_url


def test_search_keeps_only_same_sido_non_food_non_lodging_photos(db: Session) -> None:
    add_policy(db)
    found = [
        spot("food", content_type_id="39", title="굴비 정식"),
        spot("stay", content_type_id="32", title="법성포 펜션"),
        spot("far", addr="경상북도 안동시", title="하회마을"),
        spot("noaddr", addr=None, title="주소 없는 곳"),
        spot("temple", content_type_id="12", title="불갑사(영광)"),
        spot("market", content_type_id="38", title="법성포 굴비거리"),
    ]
    provider = Provider(search=found)
    photo_review.collect_candidates(db, provider, size_of=landscape)
    city = target(db, "region:전남|영광")

    photo_review.search(db, str(city.id), "  불갑사 ", provider, size_of=landscape)

    added = [c for c in city.candidates if c.source == "search"]
    assert [c.provider_content_id for c in added] == ["temple", "market"]
    assert {c.search_keyword for c in added} == {"불갑사"}
    assert ("search", "불갑사", None) in provider.calls   # 분류를 가리지 않고 찾는다


def test_more_adds_the_next_unused_photos(db: Session) -> None:
    add_policy(db)
    provider = Provider(per_type=4)
    photo_review.collect_candidates(db, provider, size_of=landscape)
    city = target(db, "region:전남|영광")
    before = set(images(city))

    photo_review.fetch_more(db, str(city.id), provider, size_of=landscape)

    after = images(city)
    assert len(after) == 12 and before < set(after)
    everyone = [c.image_url for c in db.scalars(select(PhotoReviewCandidate))]
    assert len(everyone) == len(set(everyone))
    assert any(call[0] == "list" and call[4] == 2 for call in provider.calls)   # 첫 쪽이 바닥나면 다음 쪽


def test_a_decided_target_must_be_reopened_before_more_or_search(db: Session) -> None:
    add_policy(db)
    admin = add_admin(db)
    provider = Provider()
    photo_review.collect_candidates(db, provider, size_of=landscape)
    city = target(db, "region:전남|영광")
    photo_review.mark_none(db, str(city.id), admin)

    with pytest.raises(photo_review.PhotoReviewError) as more:
        photo_review.fetch_more(db, str(city.id), provider, size_of=landscape)
    with pytest.raises(photo_review.PhotoReviewError) as found:
        photo_review.search(db, str(city.id), "불갑사", provider, size_of=landscape)
    assert more.value.status_code == found.value.status_code == 409


def test_unknown_target_and_candidate_are_not_found(db: Session) -> None:
    add_policy(db)
    admin = add_admin(db)
    photo_review.collect_candidates(db, Provider(), size_of=landscape)
    city = target(db, "region:전남|영광")
    for call in (
        lambda: photo_review.get_target(db, "abc"),
        lambda: photo_review.get_target(db, "999999"),
        lambda: photo_review.approve(db, str(city.id), "999999", admin),
    ):
        with pytest.raises(photo_review.PhotoReviewError) as error:
            call()
        assert error.value.status_code == 404


def test_list_counts_by_status_and_pending_total(db: Session) -> None:
    add_policy(db)
    admin = add_admin(db)
    photo_review.collect_candidates(db, Provider(), size_of=landscape)
    city = target(db, "region:전남|영광")
    photo_review.approve(db, str(city.id), str(city.candidates[0].id), admin)

    region = photo_review.list_targets(db, unit="region", status="pending")

    # 도 전체 줄은 쓰는 공개 정책이 없어(정책이 모두 시군 칸이 있다) 목록에 안 나온다
    assert region["items"] == []
    assert region["counts"] == {"pending": 0, "approved": 1, "none": 0, "all": 1}
    assert region["pendingTotal"] == 1   # 정책 하나
    approved = photo_review.list_targets(db, unit="region", status="approved")["items"][0]
    assert approved["photo"]["candidateId"] == str(city.candidates[0].id)
    assert approved["benefitCount"] == 1 and approved["candidateCount"] == 6


def test_resolve_sigungu_code_matches_short_and_prefixed_names() -> None:
    codes = [TourApiAreaCode(code="14", name="영광군"), TourApiAreaCode(code="16", name="완도군")]
    assert photo_review.resolve_sigungu_code("영광", codes) == "14"
    assert photo_review.resolve_sigungu_code("없는곳", codes) is None
    busan = [TourApiAreaCode(code="3", name="동구"), TourApiAreaCode(code="7", name="부산진구")]
    assert photo_review.resolve_sigungu_code("부산동", busan, "부산") == "3"
    assert photo_review.resolve_sigungu_code("부산진", busan, "부산") == "7"


def test_merged_jeonnam_gwangju_address_matches_both() -> None:
    # 2026-10-01 실측: 전남 · 광주 관광지 주소가 모두 '전남광주통합특별시'로 시작한다
    assert photo_review.addr_matches_sido("전남광주통합특별시 영광군 법성면", "전남")
    assert photo_review.addr_matches_sido("전남광주통합특별시 동구", "광주")
    assert not photo_review.addr_matches_sido("전남광주통합특별시 영광군", "경북")


def test_region_keys_normalize_cities_and_add_one_sido_row() -> None:
    keys = photo_review.build_region_keys([("전남", "영광군"), ("전남", "영광"), ("전남", None), ("경북", "안동"), (None, "x")])
    assert keys == [("전남", "영광"), ("경북", "안동"), ("전남", ""), ("경북", "")]


def test_collect_commits_each_target_and_reports_progress(db: Session) -> None:
    add_policy(db)
    seen: list[tuple[int, int]] = []

    summary = photo_review.collect_candidates(
        db, Provider(), size_of=landscape, commit=True, progress=lambda s: seen.append((s.targets_done, s.targets_total))
    )

    assert seen[0] == (0, summary.targets_total) and seen[-1] == (summary.targets_total, summary.targets_total)
    assert len(seen) == summary.targets_total + 1
    db.rollback()   # 대상마다 저장됐으니 되돌려도 남는다
    assert len(target(db, "region:전남|영광").candidates) == 6


def test_collect_button_runs_in_the_background_and_records_the_run(factory, db: Session) -> None:
    add_policy(db)
    admin = add_admin(db)
    db.commit()

    job = photo_review.start_collect_job(
        admin, Provider(), size_of=landscape, session_factory=factory, spawn=lambda work: work()
    )

    status = photo_review.collect_status(db)
    assert job.error is None and status["running"] is False
    assert status["done"] == status["total"] > 0 and status["candidatesAdded"] > 0
    assert status["lastRun"]["candidatesAdded"] == status["candidatesAdded"]
    assert status["lastRun"]["at"].endswith("Z") and status["finishedAt"].endswith("Z")
    log = db.scalars(select(AdminAuditLog).where(AdminAuditLog.action == "photo_review.collect")).one()
    assert log.admin_user_id == 10 and log.after_json["targetsCreated"] == status["targetsCreated"]


def test_collect_button_refuses_a_second_run_while_one_is_running(factory, db: Session) -> None:
    add_policy(db)
    admin = add_admin(db)
    db.commit()
    waiting: list = []
    photo_review.start_collect_job(admin, Provider(), size_of=landscape, session_factory=factory, spawn=waiting.append)

    with pytest.raises(photo_review.PhotoReviewError) as busy:
        photo_review.start_collect_job(admin, Provider(), size_of=landscape, session_factory=factory, spawn=waiting.append)
    assert busy.value.status_code == 409 and photo_review.collect_status(db)["running"] is True

    waiting[0]()   # 첫 번째가 끝나면 다시 누를 수 있다
    photo_review.start_collect_job(admin, Provider(), size_of=landscape, session_factory=factory, spawn=lambda work: work())
    assert photo_review.collect_status(db)["running"] is False


def test_a_failed_collection_is_reported_without_a_run_record(factory, db: Session) -> None:
    add_policy(db)
    admin = add_admin(db)
    db.commit()

    class Down(Provider):
        def list_area_codes(self, *, area_code=None):
            raise TourApiConfigurationError("TourAPI request failed (HTTP 503).")

    photo_review.start_collect_job(admin, Down(), size_of=landscape, session_factory=factory, spawn=lambda work: work())

    status = photo_review.collect_status(db)
    assert status["running"] is False and status["error"] == "TourAPI request failed (HTTP 503)."
    assert status["lastRun"] is None


def test_list_tells_how_many_targets_the_next_collection_adds_and_fills(db: Session) -> None:
    add_policy(db)
    add_policy(db, 2, city="가상", title="[가상] 혜택")   # 시군 코드가 없어 후보를 못 받는 곳

    before = photo_review.list_targets(db, unit="region", status=None)
    assert (before["newTargets"], before["shortTargets"]) == (4, 0)   # 시군 둘 · 정책 둘

    photo_review.collect_candidates(db, Provider(), size_of=landscape)
    after = photo_review.list_targets(db, unit="region", status=None)
    assert (after["newTargets"], after["shortTargets"]) == (0, 2)   # 가상 시군 · 가상 정책은 0장


# ---------- 라우트 ----------

client = TestClient(app)


def _user(role: str) -> User:
    return User(id=1, email="a@example.com", nickname="a", role=role, onboarding_completed=True,
                created_at=datetime(2026, 10, 2), updated_at=datetime(2026, 10, 2))


def _install(fake_db: object, user: User) -> None:
    app.dependency_overrides[admin_routes.get_optional_db] = lambda: fake_db
    app.dependency_overrides[admin_routes.get_current_user] = lambda: user


def _clear() -> None:
    app.dependency_overrides.pop(admin_routes.get_optional_db, None)
    app.dependency_overrides.pop(admin_routes.get_current_user, None)


def test_photo_review_routes_are_admin_only() -> None:
    _install(object(), _user("user"))
    try:
        response = client.get("/api/admin/photo-review/targets")
    finally:
        _clear()
    assert response.status_code == 403


def test_more_and_search_need_the_tour_api(monkeypatch) -> None:
    _install(object(), _user("admin"))
    monkeypatch.setattr(admin_routes, "build_tour_api_client", lambda: None)
    try:
        more = client.post("/api/admin/photo-review/targets/1/more")
        found = client.post("/api/admin/photo-review/targets/1/search", json={"keyword": "죽녹원"})
        empty = client.post("/api/admin/photo-review/targets/1/search", json={"keyword": ""})
    finally:
        _clear()
    assert (more.status_code, found.status_code) == (503, 503)
    assert empty.status_code == 422


def test_collect_button_route_needs_the_tour_api_and_reports_a_running_job(monkeypatch) -> None:
    _install(object(), _user("admin"))
    monkeypatch.setattr(admin_routes, "build_tour_api_client", lambda: None)
    try:
        disabled = client.post("/api/admin/photo-review/collect")
    finally:
        _clear()
    assert disabled.status_code == 503

    def busy(*_args, **_kwargs):
        raise photo_review.PhotoReviewError(409, "Photo candidate collection is already running")

    _install(object(), _user("admin"))
    monkeypatch.setattr(admin_routes, "build_tour_api_client", lambda: object())
    monkeypatch.setattr(admin_routes.photo_review, "start_collect_job", busy)
    try:
        running = client.post("/api/admin/photo-review/collect")
    finally:
        _clear()
    assert running.status_code == 409


def test_collect_status_route_is_admin_only() -> None:
    _install(object(), _user("user"))
    try:
        response = client.get("/api/admin/photo-review/collect")
    finally:
        _clear()
    assert response.status_code == 403


def test_route_maps_service_errors_and_rolls_back(monkeypatch) -> None:
    class FakeSession:
        rolled_back = False

        def rollback(self) -> None:
            self.rolled_back = True

        def commit(self) -> None:  # pragma: no cover - 실패한 결정은 커밋하지 않는다
            raise AssertionError("must not commit")

    def missing(*_args, **_kwargs):
        raise photo_review.PhotoReviewError(404, "Photo review target not found")

    session = FakeSession()
    _install(session, _user("admin"))
    monkeypatch.setattr(admin_routes.photo_review, "get_target", missing)
    monkeypatch.setattr(admin_routes.photo_review, "mark_none", missing)
    try:
        got = client.get("/api/admin/photo-review/targets/999")
        none = client.post("/api/admin/photo-review/targets/999/none")
    finally:
        _clear()
    assert (got.status_code, none.status_code) == (404, 404)
    assert session.rolled_back
