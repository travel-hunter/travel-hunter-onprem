"""3단계 담는 흐름(카카오 운영정책) - 일정 장소는 공공데이터 값과 사용자가 쓴 값만 저장한다.
DB 는 운영과 같은 autoflush=False 세션의 SQLite 다. TripPlace 의 BigInteger 기본키는 SQLite 가 자동 증가시키지 않아 시험 동안만 Integer 로 바꾼다."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Iterator
from datetime import date, datetime, time
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import BigInteger, Integer, create_engine, event, func, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.dependencies import get_current_user
from app.data.travel_areas import get_travel_area, make_policy_region_area_id
from app.db.base import Base
from app.db.session import get_optional_db
from app.main import app
from app.models import PublicPlace, Recommendation, Trip, TripDay, TripMember, TripPlace, User
from app.schemas.trip import CreateTripPlacesRequest, CreateTripPlaceRequest, CustomPlaceInput, PublicPlaceRef, UpdateTripPlaceRequest
from app.services import trips as trip_service
from app.services.geo_reference import GeoHit
from app.services.public_places import name_key, public_place_item, secure_photo_url
from app.services.travel_area_catalog import make_administrative_area_id, make_whole_area_id
from app.services.trip_public_places import area_scope

SYNCED = datetime(2026, 10, 5, 3, 0)
ODONGDO_PHOTO = "http://tong.visitkorea.or.kr/cms/resource/a.jpg"
TOUR_REF = {"source": "tourapi", "sourceId": "126508"}


def register_md5(dbapi_connection, _record) -> None:
    # 추천 순서는 Postgres 내장 md5() 로 정한다. SQLite 에는 없어서 연결마다 같은 이름으로 등록한다
    dbapi_connection.create_function("md5", 1, lambda value: hashlib.md5(str(value).encode()).hexdigest())


@pytest.fixture
def db() -> Iterator[Session]:
    # StaticPool · check_same_thread=False: TestClient 가 라우트를 다른 스레드에서 돌린다. autoflush 는 운영처럼 끈다
    swapped = [(c, c.type) for t in Base.metadata.tables.values() for c in t.c if c.primary_key and isinstance(c.type, BigInteger)]
    for column, _ in swapped:
        column.type = Integer()
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", register_md5)
    try:
        Base.metadata.create_all(bind=engine)
        with sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)() as session:
            yield session
    finally:
        for column, original in swapped:
            column.type = original


@pytest.fixture
def api(db: Session) -> Iterator[Callable[[User], TestClient]]:
    client = TestClient(app)

    def login(user: User) -> TestClient:
        app.dependency_overrides[get_optional_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: user
        return client

    yield login
    app.dependency_overrides.pop(get_optional_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def make_user(user_id: int, nickname: str) -> User:
    return User(id=user_id, email=f"user-{user_id}@travel.kr", nickname=nickname, onboarding_completed=True)


def seed_trip(db: Session, *, travel_area_id: str | None = None) -> tuple[User, Trip]:
    """일정 7번(이틀, 첫 사용자가 owner, revision 1) 하나."""

    owner = make_user(1, "Owner")
    trip = Trip(
        id=7, owner_id=1, title="여수 여행", status="confirmed", revision=1, start_date=date(2026, 10, 10),
        end_date=date(2026, 10, 11), region="여수", travel_area_id=travel_area_id, participant_count=1,
    )
    db.add_all([owner, trip, TripDay(id=1, trip_id=7, day_number=1, date=date(2026, 10, 10)),
                TripDay(id=2, trip_id=7, day_number=2, date=date(2026, 10, 11))])
    db.commit()
    return owner, trip


def seed_viewer(db: Session) -> User:
    viewer = make_user(2, "Viewer")
    db.add_all([viewer, TripMember(trip_id=7, user_id=2, role="viewer")])
    db.commit()
    return viewer


def public_place(source_id: str = "126508", *, source: str = "tourapi", name: str = "오동도", category: str = "sight",
                 sido: str = "전남", city: str = "여수", lat: float = 34.7443, lng: float = 127.7663,
                 photo: str | None = ODONGDO_PHOTO, address: str | None = "전남광주통합특별시 여수시 오동도로 222") -> PublicPlace:
    return PublicPlace(
        source=source, source_id=source_id, name=name, name_key=name_key(name), address=address, latitude=lat, longitude=lng,
        category=category, sido=sido, city=city, photo_url=photo, photo_license="Type3" if photo else None, synced_at=SYNCED,
    )


def saved_places(db: Session) -> list[TripPlace]:
    db.expire_all()
    return list(db.scalars(select(TripPlace).order_by(TripPlace.id)))


def revision_of(db: Session, trip_id: int = 7) -> int:
    db.expire_all()
    return db.scalar(select(Trip.revision).where(Trip.id == trip_id))


OLD_KAKAO_FIELDS = {
    "label": "카카오가게", "meta": "음식점 > 한식 · 전남 여수시", "address": "전남 여수시 수정동 1", "latitude": 34.7443,
    "longitude": 127.7663, "category": "음식점", "categoryCode": "FD6", "placeUrl": "https://place.map.kakao.com/1",
    "sourceProvider": "kakao", "externalPlaceId": "1",
}


@pytest.mark.parametrize("field", sorted(OLD_KAKAO_FIELDS))
def test_add_requests_reject_every_old_kakao_field(field: str) -> None:
    body = {"time": "10:00", "customPlace": {"name": "내 장소"}, field: OLD_KAKAO_FIELDS[field]}
    with pytest.raises(ValidationError) as single:
        CreateTripPlaceRequest(expectedRevision=1, **body)
    assert single.value.errors()[0]["type"] == "extra_forbidden"
    with pytest.raises(ValidationError):
        CreateTripPlacesRequest(expectedRevision=1, places=[body])


def test_an_add_request_needs_exactly_one_of_public_or_custom_place() -> None:
    with pytest.raises(ValidationError):
        CreateTripPlaceRequest(expectedRevision=1, time="10:00")
    with pytest.raises(ValidationError):
        CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF, customPlace={"name": "내 장소"})
    assert CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF).customPlace is None
    assert CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "내 장소"}).publicPlace is None


def test_public_ref_and_kakao_place_id_shapes() -> None:
    assert PublicPlaceRef(source="sangga", sourceId="MA0101").sourceId == "MA0101"
    for bad_ref in ({"source": "kakao", "sourceId": "1"}, {"source": "tourapi", "sourceId": ""}, {"source": "tourapi", "sourceId": "9" * 41}):
        with pytest.raises(ValidationError):
            PublicPlaceRef(**bad_ref)
    assert CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF, kakaoPlaceId="1234567890").kakaoPlaceId == "1234567890"
    for bad_id in ("abc", "12a", "", "1" * 21, "12 34"):
        with pytest.raises(ValidationError):
            CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF, kakaoPlaceId=bad_id)


def test_secure_photo_url_upgrades_only_the_tour_api_host() -> None:
    assert secure_photo_url("http://tong.visitkorea.or.kr/cms/a.jpg") == "https://tong.visitkorea.or.kr/cms/a.jpg"
    assert secure_photo_url("https://tong.visitkorea.or.kr/cms/a.jpg") == "https://tong.visitkorea.or.kr/cms/a.jpg"
    assert secure_photo_url("http://example.com/a.jpg") == "http://example.com/a.jpg"
    assert secure_photo_url(None) is None
    assert public_place_item(public_place(), 0)["photoUrl"] == "https://tong.visitkorea.or.kr/cms/resource/a.jpg"


def test_public_add_saves_only_the_public_values_and_the_kakao_link(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()

    payload = trip_service.add_place_to_trip_day(
        db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, time="12:30", publicPlace=TOUR_REF, kakaoPlaceId="12345"),
    )

    (row,) = saved_places(db)
    assert (row.place_name, row.address, row.place_origin) == ("오동도", "전남광주통합특별시 여수시 오동도로 222", "public")
    assert (float(row.latitude), float(row.longitude)) == (34.7443, 127.7663)
    assert (row.public_source, row.public_source_id, row.public_category) == ("tourapi", "126508", "sight")
    assert (row.photo_url, row.photo_license) == ("https://tong.visitkorea.or.kr/cms/resource/a.jpg", "Type3")
    assert (row.memo, row.category_group_code, row.category_group_name, row.user_label) == (None, None, None, None)
    assert (row.source_provider, row.external_place_id, row.place_url) == ("kakao", "12345", "https://place.map.kakao.com/12345")
    assert row.visit_time.strftime("%H:%M") == "12:30"
    assert (row.order_num, revision_of(db)) == (1, 2)
    added = payload["days"][1][0]
    assert (added["label"], added["meta"], added["placeOrigin"], added["publicCategory"]) == ("오동도", row.address, "public", "sight")
    assert (added["publicSource"], added["publicSourceId"], added["photoLicense"], added["needsConfirmation"]) == ("tourapi", "126508", "Type3", False)
    assert added["placeUrl"] == "https://place.map.kakao.com/12345" and added["externalPlaceId"] == "12345"
    assert added["memo"] is None   # 새로 담은 행은 메모가 비어 있다(수정으로 채운다)


def test_a_public_add_without_a_kakao_id_keeps_no_kakao_link(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF))
    (row,) = saved_places(db)
    assert (row.source_provider, row.external_place_id, row.place_url) == (None, None, None)


def test_custom_add_keeps_only_the_typed_name_and_the_kakao_link(db: Session) -> None:
    owner, _ = seed_trip(db)
    trip_service.add_place_to_trip_day(
        db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": " 우리 아지트 "}, kakaoPlaceId="777"),
    )
    payload = trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=2, customPlace={"name": "이름만"}))

    named, plain = saved_places(db)
    assert (named.place_name, named.place_origin, named.address, named.latitude, named.longitude) == ("우리 아지트", "custom", None, None, None)
    assert (named.public_source, named.public_source_id, named.public_category, named.photo_url, named.photo_license) == (None,) * 5
    assert (named.category_group_code, named.category_group_name, named.memo, named.geo_kind, named.geo_pnu) == (None,) * 5
    assert (named.source_provider, named.external_place_id, named.place_url) == ("kakao", "777", "https://place.map.kakao.com/777")
    assert (plain.place_name, plain.latitude, plain.longitude, plain.place_url) == ("이름만", None, None, None)
    assert [place["label"] for place in payload["days"][1]] == ["우리 아지트", "이름만"]
    assert [place["latitude"] for place in payload["days"][1]] == [None, None]


def test_batch_add_mixes_public_and_custom_places_in_one_revision(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add_all([public_place(), public_place("MA01", source="sangga", name="카페마레 여수점", category="cafe", photo=None)])
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "먼저 담은 곳"}))

    payload = trip_service.add_places_to_trip_day(
        db, owner, "7", 1,
        CreateTripPlacesRequest(expectedRevision=2, places=[
            {"publicPlace": TOUR_REF, "kakaoPlaceId": "11"},
            {"customPlace": {"name": "직접 적은 곳"}},
            {"publicPlace": {"source": "sangga", "sourceId": "MA01"}, "time": "15:00"},
            {"publicPlace": TOUR_REF},   # 같은 공공데이터 장소를 또 담아도 된다
        ]),
    )

    rows = saved_places(db)
    assert [row.place_name for row in rows] == ["먼저 담은 곳", "오동도", "직접 적은 곳", "카페마레 여수점", "오동도"]
    assert [row.order_num for row in rows] == [1, 2, 3, 4, 5]
    assert [row.place_origin for row in rows] == ["custom", "public", "custom", "public", "public"]
    assert [row.public_category for row in rows] == [None, "sight", None, "cafe", "sight"]
    assert [row.external_place_id for row in rows] == [None, "11", None, None, None]
    assert rows[3].visit_time.strftime("%H:%M") == "15:00" and rows[3].photo_url is None
    assert revision_of(db) == 3 and payload["revision"] == 3   # 묶음은 한 번만 올린다


def test_a_missing_public_place_is_404_and_writes_nothing(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()

    with pytest.raises(trip_service.TripServiceError) as single:
        trip_service.add_place_to_trip_day(
            db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, publicPlace={"source": "tourapi", "sourceId": "000"}),
        )
    with pytest.raises(trip_service.TripServiceError) as batch:
        trip_service.add_places_to_trip_day(
            db, owner, "7", 1,
            CreateTripPlacesRequest(expectedRevision=1, places=[{"publicPlace": TOUR_REF}, {"publicPlace": {"source": "sangga", "sourceId": "000"}}]),
        )

    assert (single.value.status_code, single.value.detail) == (404, "Public place not found")
    assert (batch.value.status_code, batch.value.detail) == (404, "Public place not found")
    assert saved_places(db) == [] and revision_of(db) == 1   # 앞의 장소가 있어도 하나도 쓰지 않고 revision 도 그대로


def test_stale_revision_and_viewer_are_refused_without_writes(db: Session) -> None:
    owner, _ = seed_trip(db)
    viewer = seed_viewer(db)
    db.add(public_place())
    db.commit()

    with pytest.raises(trip_service.TripServiceError) as stale:
        trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=9, publicPlace=TOUR_REF))
    with pytest.raises(trip_service.TripServiceError) as forbidden:
        trip_service.add_places_to_trip_day(
            db, viewer, "7", 1, CreateTripPlacesRequest(expectedRevision=1, places=[{"publicPlace": {"source": "tourapi", "sourceId": "000"}}]),
        )
    with pytest.raises(trip_service.TripServiceError) as no_day:
        trip_service.add_places_to_trip_day(db, owner, "7", 9, CreateTripPlacesRequest(expectedRevision=1, places=[{"publicPlace": TOUR_REF}]))

    assert stale.value.status_code == 409
    assert forbidden.value.status_code == 403   # 권한 확인이 공공데이터 조회보다 먼저다
    assert (no_day.value.status_code, no_day.value.detail) == (404, "Trip day not found")
    assert saved_places(db) == [] and revision_of(db) == 1


def test_add_routes_answer_with_the_new_fields_and_refuse_the_old_ones(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()
    client = api(owner)

    added = client.post("/api/trips/7/days/1/places", json={"expectedRevision": 1, "publicPlace": TOUR_REF, "kakaoPlaceId": "12345"})
    batch = client.post(
        "/api/trips/7/days/2/places/batch",
        json={"expectedRevision": 2, "places": [{"customPlace": {"name": "내 장소"}}, {"publicPlace": TOUR_REF}]},
    )
    old_single = client.post("/api/trips/7/days/1/places", json={"expectedRevision": 3, "label": "카카오가게", "sourceProvider": "kakao"})
    old_batch = client.post("/api/trips/7/days/1/places/batch", json={"expectedRevision": 3, "places": [{"label": "카카오가게"}]})
    missing = client.post("/api/trips/7/days/1/places", json={"expectedRevision": 3, "publicPlace": {"source": "tourapi", "sourceId": "000"}})

    assert added.status_code == 200 and batch.status_code == 200
    place = added.json()["days"]["1"][0]
    assert (place["label"], place["placeOrigin"], place["publicCategory"], place["photoLicense"]) == ("오동도", "public", "sight", "Type3")
    assert place["photoUrl"].startswith("https://") and place["needsConfirmation"] is False
    assert [item["placeOrigin"] for item in batch.json()["days"]["2"]] == ["custom", "public"]
    assert (old_single.status_code, old_batch.status_code) == (422, 422)
    # 화면은 이 오류 종류(모르는 필드)를 보고 '새로 고침'을 안내한다(과제 9 의 isStaleScreenError) - 422 모양이 바뀌면 여기서 걸린다
    for old in (old_single, old_batch):
        assert "extra_forbidden" in {error["type"] for error in old.json()["detail"]}
    assert (missing.status_code, missing.json()) == (404, {"detail": "Public place not found"})
    assert revision_of(db) == 3 and len(saved_places(db)) == 3


@pytest.mark.parametrize(("path", "body", "extra"), [
    ("/api/trips/7/days/1/places", {"expectedRevision": 1, "publicPlace": {**TOUR_REF, "name": "카카오가 준 이름"}}, "name"),
    ("/api/trips/7/days/1/places/batch",
     {"expectedRevision": 1, "places": [{"customPlace": {"name": "내 장소", "address": "카카오가 준 주소"}}]}, "address"),
])
def test_unknown_fields_inside_public_or_custom_place_are_refused_and_nothing_is_written(
    db: Session, api: Callable[[User], TestClient], path: str, body: dict[str, object], extra: str
) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()

    response = api(owner).post(path, json=body)

    assert response.status_code == 422
    assert [(error["type"], error["loc"][-1]) for error in response.json()["detail"]] == [("extra_forbidden", extra)]
    assert saved_places(db) == [] and revision_of(db) == 1   # 숨은 값을 조용히 버리고 담지 않는다


def test_itinerary_places_tell_new_rows_from_old_kakao_rows() -> None:
    owner = make_user(1, "Owner")
    trip = Trip(id=7, owner_id=1, title="t", status="confirmed", revision=1, start_date=date(2026, 10, 10), end_date=date(2026, 10, 10), participant_count=1)
    trip.owner, trip.members, trip.policies, trip.invites, trip.recommendations = owner, [], [], [], []
    day = TripDay(id=1, trip_id=7, day_number=1, date=date(2026, 10, 10))
    day.places = [
        TripPlace(id=1, trip_day_id=1, place_name="카카오 예전 행", order_num=1, source_provider="kakao", external_place_id="1",
                  memo="음식점 > 한식 · 전남 여수시"),
        TripPlace(id=2, trip_day_id=1, place_name="로컬 예전 행", order_num=2, source_provider="kakao_local", external_place_id="2"),
        TripPlace(id=3, trip_day_id=1, place_name="카탈로그 예전 행", order_num=3),
        TripPlace(id=4, trip_day_id=1, place_name="오동도", order_num=4, place_origin="public", public_source="tourapi", public_source_id="126508",
                  public_category="sight", photo_url="https://tong.visitkorea.or.kr/a.jpg", photo_license="Type3", source_provider="kakao", external_place_id="4"),
        TripPlace(id=5, trip_day_id=1, place_name="나만의 곳", order_num=5, place_origin="custom", source_provider="kakao", external_place_id="5",
                  memo="일몰 때 가기"),
        TripPlace(id=6, trip_day_id=1, place_name="오동도", order_num=6, place_origin="public", public_source="tourapi", public_source_id="126508",
                  public_category="sight", user_label="내가 부르는 이름"),
    ]
    trip.days = [day]

    places = trip_service.trip_to_api(trip, owner, recommended_policies=[])["days"][1]

    assert [place["needsConfirmation"] for place in places] == [True, True, False, False, False, False]   # 카카오 값을 가진 예전 행만
    assert [place["placeOrigin"] for place in places] == [None, None, None, "public", "custom", "public"]
    assert [place["label"] for place in places] == ["카카오 예전 행", "로컬 예전 행", "카탈로그 예전 행", "오동도", "나만의 곳", "내가 부르는 이름"]   # 사용자 이름이 있으면 그것
    assert (places[3]["publicSource"], places[3]["publicSourceId"], places[3]["publicCategory"]) == ("tourapi", "126508", "sight")
    assert (places[3]["photoUrl"], places[3]["photoLicense"]) == ("https://tong.visitkorea.or.kr/a.jpg", "Type3")
    assert places[0]["publicSource"] is None and places[0]["photoUrl"] is None
    assert [place["memo"] for place in places] == ["음식점 > 한식 · 전남 여수시", None, None, None, "일몰 때 가기", None]   # 저장된 메모 그대로
    assert (places[0]["meta"], places[4]["meta"]) == ("음식점 > 한식 · 전남 여수시", "일몰 때 가기")   # meta 는 메모가 있으면 메모


LEGACY_ID = 10


def seed_legacy_place(db: Session, **overrides: object) -> TripPlace:
    """3단계 이전에 카카오 값으로 저장된 행(이름 · 주소 · 좌표 · 분류가 카카오 값, memo 는 '분류 · 주소' 문구)."""

    values: dict[str, object] = dict(
        id=LEGACY_ID, trip_day_id=1, place_name="카카오에서온가게이름", address="전남 여수시 수정동 1", latitude=Decimal("34.7443000"),
        longitude=Decimal("127.7663000"), source_provider="kakao", external_place_id="777", category_group_code="FD6",
        category_group_name="음식점", place_url="https://place.map.kakao.com/777", memo="음식점 > 한식 · 전남 여수시 수정동 1",
        visit_time=time(12, 0), order_num=1,
    )
    place = TripPlace(**{**values, **overrides})
    db.add(place)
    db.commit()
    return place


def row_values(place: TripPlace) -> dict[str, object]:
    return {column.name: getattr(place, column.name) for column in TripPlace.__table__.columns}


def patch(db: Session, user: User, place_id: int, revision: int, **fields: object) -> dict[str, object]:
    return trip_service.update_trip_place(db, user, "7", place_id, UpdateTripPlaceRequest(expectedRevision=revision, **fields))


def test_update_requests_check_name_memo_and_replacement_rules() -> None:
    assert UpdateTripPlaceRequest(expectedRevision=1, label="  새 이름  ").label == "새 이름"
    assert UpdateTripPlaceRequest(expectedRevision=1, label="가" * 100, memo="나" * 500).memo == "나" * 500
    for bad in ({"label": ""}, {"label": "   "}, {"label": "가" * 101}, {"memo": "나" * 501}, {"meta": "옛 필드"}, {"address": "주소"},
                {"publicPlace": TOUR_REF, "customPlace": {"name": "내 장소"}},
                {"publicPlace": {**TOUR_REF, "name": "카카오 이름"}}, {"customPlace": {"name": "내 장소", "address": "카카오 주소"}}):
        with pytest.raises(ValidationError):
            UpdateTripPlaceRequest(expectedRevision=1, **bad)
    assert UpdateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF).customPlace is None


def test_a_time_only_patch_leaves_a_legacy_row_untouched(db: Session) -> None:
    owner, _ = seed_trip(db)
    legacy = seed_legacy_place(db)
    before = row_values(legacy)

    payload = patch(db, owner, LEGACY_ID, 1, time="15:30")

    (row,) = saved_places(db)
    assert row.visit_time.strftime("%H:%M") == "15:30"
    assert {**row_values(row), "visit_time": before["visit_time"]} == before   # 시간만 바뀌고 카카오 값은 그대로(변환 없음)
    assert row.place_origin is None and revision_of(db) == 2
    shown = payload["days"][1][0]
    assert (shown["needsConfirmation"], shown["placeOrigin"], shown["label"]) == (True, None, "카카오에서온가게이름")
    assert shown["memo"] == before["memo"]   # 변환하지 않았으니 메모도 그대로


def test_a_new_name_turns_a_legacy_row_into_a_custom_place_and_drops_the_kakao_values(db: Session) -> None:
    owner, _ = seed_trip(db)
    seed_legacy_place(db)

    payload = patch(db, owner, LEGACY_ID, 1, label=" 우리 단골집 ")

    (row,) = saved_places(db)
    assert (row.place_name, row.place_origin) == ("우리 단골집", "custom")
    assert (row.address, row.latitude, row.longitude, row.memo) == (None, None, None, None)
    assert (row.category_group_code, row.category_group_name) == (None, None)
    assert (row.public_source, row.public_source_id, row.public_category, row.photo_url, row.photo_license, row.user_label) == (None,) * 6
    assert (row.source_provider, row.external_place_id, row.place_url) == ("kakao", "777", "https://place.map.kakao.com/777")   # 링크는 남긴다
    assert row.visit_time.strftime("%H:%M") == "12:00"
    shown = payload["days"][1][0]
    assert (shown["needsConfirmation"], shown["placeOrigin"], shown["meta"], shown["memo"]) == (False, "custom", "", None)


def test_a_custom_place_replaces_a_legacy_row_with_a_geo_reference(db: Session, monkeypatch) -> None:
    owner, _ = seed_trip(db)
    use_geo(monkeypatch)
    seed_legacy_place(db)

    patch(db, owner, LEGACY_ID, 1, customPlace={"name": "오동도 근처", "geoRef": {"kind": "parcel", "id": 4401, "pin": True}}, time="18:00")
    (pinned,) = saved_places(db)
    assert (pinned.place_name, pinned.place_origin, pinned.address, pinned.memo) == ("오동도 근처", "custom", GEO.address, None)
    assert (pinned.geo_kind, pinned.geo_pnu) == ("parcel", GEO.pnu)
    assert (float(pinned.latitude), float(pinned.longitude)) == (GEO.latitude, GEO.longitude)   # 카카오 좌표가 아니라 공공데이터 중심
    assert (pinned.category_group_code, pinned.category_group_name, pinned.external_place_id) == (None, None, "777")
    assert pinned.visit_time.strftime("%H:%M") == "18:00"

    patch(db, owner, LEGACY_ID, 2, customPlace={"name": "주소는 안 채움"})
    (plain,) = saved_places(db)
    assert (plain.place_name, plain.address, plain.latitude, plain.longitude, plain.geo_kind, plain.geo_pnu) == ("주소는 안 채움", None, None, None, None, None)


def test_a_public_place_replaces_a_legacy_row_with_the_public_values(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()
    seed_legacy_place(db)

    patch(db, owner, LEGACY_ID, 1, publicPlace=TOUR_REF)

    (row,) = saved_places(db)
    assert (row.place_name, row.address, row.place_origin) == ("오동도", "전남광주통합특별시 여수시 오동도로 222", "public")
    assert (float(row.latitude), float(row.longitude)) == (34.7443, 127.7663)
    assert (row.public_source, row.public_source_id, row.public_category) == ("tourapi", "126508", "sight")
    assert (row.photo_url, row.photo_license) == ("https://tong.visitkorea.or.kr/cms/resource/a.jpg", "Type3")
    assert (row.category_group_code, row.category_group_name, row.memo) == (None, None, None)   # 카카오 분류 · '분류 · 주소' 문구를 지운다
    assert (row.source_provider, row.external_place_id, row.place_url) == ("kakao", "777", "https://place.map.kakao.com/777")


def test_renaming_a_public_row_stores_the_users_name_apart_and_keeps_the_public_values(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()
    trip_service.add_place_to_trip_day(
        db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF, kakaoPlaceId="12345"),
    )
    (added,) = saved_places(db)
    before = row_values(added)

    shown = patch(db, owner, added.id, 2, label="  내가 부르는 이름  ")["days"][1][0]

    (row,) = saved_places(db)
    assert row.user_label == "내가 부르는 이름"
    assert {**row_values(row), "user_label": None} == before   # 사용자 이름 말고는 한 열도 안 바뀐다 - 공공데이터 이름 · 주소 · 좌표 · 사진 · 출처 · 카카오 링크 그대로
    assert (row.place_name, row.place_origin) == ("오동도", "public")   # 이름이 섞이지 않는다
    assert (shown["label"], shown["placeOrigin"], shown["publicSourceId"]) == ("내가 부르는 이름", "public", "126508")   # 화면 이름은 사용자 이름

    patch(db, owner, added.id, 3, label="또 다른 이름")
    assert saved_places(db)[0].user_label == "또 다른 이름"


def test_renaming_a_custom_row_changes_its_name_itself(db: Session, monkeypatch) -> None:
    owner, _ = seed_trip(db)
    use_geo(monkeypatch)
    trip_service.add_place_to_trip_day(
        db, owner, "7", 1,
        CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "내 장소", "geoRef": {"kind": "parcel", "id": 4401, "pin": True}}),
    )
    (placed,) = saved_places(db)

    shown = patch(db, owner, placed.id, 2, label="새 이름")["days"][1][0]

    (row,) = saved_places(db)
    assert (row.place_name, row.user_label, row.place_origin) == ("새 이름", None, "custom")   # 나만의 장소는 이름 자체가 사용자 이름이다
    assert (row.address, row.geo_kind, row.geo_pnu) == (GEO.address, "parcel", GEO.pnu)   # 이름만 바뀐다 - 주소 · 출처는 그대로
    assert (float(row.latitude), float(row.longitude)) == (GEO.latitude, GEO.longitude)   # 좌표도 GEO 중심 그대로
    assert shown["label"] == "새 이름"


def test_replacing_a_row_drops_the_users_name_but_a_label_sent_along_still_applies(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add_all([public_place(), public_place("MA01", source="sangga", name="카페마레 여수점", category="cafe", photo=None)])
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF))
    (placed,) = saved_places(db)
    patch(db, owner, placed.id, 2, label="내가 부르는 이름")
    assert saved_places(db)[0].user_label == "내가 부르는 이름"

    patch(db, owner, placed.id, 3, publicPlace={"source": "sangga", "sourceId": "MA01"})   # 다른 장소로 바꾸면 예전 사용자 이름은 버린다
    row = saved_places(db)[0]
    assert (row.place_name, row.user_label) == ("카페마레 여수점", None)

    patch(db, owner, placed.id, 4, label="우리 카페")
    patch(db, owner, placed.id, 5, customPlace={"name": "내가 찍은 곳"})
    row = saved_places(db)[0]
    assert (row.place_name, row.place_origin, row.user_label) == ("내가 찍은 곳", "custom", None)

    shown = patch(db, owner, placed.id, 6, publicPlace=TOUR_REF, label="한꺼번에")["days"][1][0]   # label 이 함께 오면 바뀐 행에 적용한다
    row = saved_places(db)[0]
    assert (row.place_name, row.place_origin, row.user_label, shown["label"]) == ("오동도", "public", "한꺼번에", "한꺼번에")


def test_a_memo_is_the_users_own_text_and_an_empty_one_clears_it(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF))
    (added,) = saved_places(db)

    shown = patch(db, owner, added.id, 2, memo="  일몰 때 가기  ")["days"][1][0]
    assert (shown["memo"], shown["meta"]) == ("일몰 때 가기", "일몰 때 가기")   # 응답에 메모가 따로 오고, meta 는 메모가 있으면 메모
    (row,) = saved_places(db)
    assert (row.memo, row.place_origin, row.public_source_id, row.photo_license) == ("일몰 때 가기", "public", "126508", "Type3")   # 공공데이터 열은 그대로

    cleared = patch(db, owner, added.id, 3, memo="")["days"][1][0]
    assert saved_places(db)[0].memo is None
    assert (cleared["memo"], cleared["meta"]) == (None, "전남광주통합특별시 여수시 오동도로 222")   # 메모가 없으면 meta 는 주소
    patch(db, owner, added.id, 4, memo="다시 적음")
    patch(db, owner, added.id, 5, memo=None)
    assert saved_places(db)[0].memo is None


def test_switching_a_new_row_between_public_and_custom_keeps_the_users_memo(db: Session) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place())
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "내 장소"}))
    placed = saved_places(db)[0]
    patch(db, owner, placed.id, 2, memo="내 메모")

    patch(db, owner, placed.id, 3, publicPlace=TOUR_REF)
    row = saved_places(db)[0]
    assert (row.place_name, row.place_origin, row.memo) == ("오동도", "public", "내 메모")   # 예전 카카오 행이 아니면 메모를 지우지 않는다

    patch(db, owner, placed.id, 4, customPlace={"name": "다시 내 장소"})
    row = saved_places(db)[0]
    assert (row.place_name, row.place_origin, row.memo) == ("다시 내 장소", "custom", "내 메모")
    assert (row.public_source, row.public_source_id, row.public_category, row.photo_url, row.address) == (None,) * 5


def test_a_missing_public_place_in_a_patch_is_404_and_changes_nothing(db: Session) -> None:
    owner, _ = seed_trip(db)
    legacy = seed_legacy_place(db)
    before = row_values(legacy)

    with pytest.raises(trip_service.TripServiceError) as error:
        patch(db, owner, LEGACY_ID, 1, publicPlace={"source": "tourapi", "sourceId": "000"}, time="15:00")

    assert (error.value.status_code, error.value.detail) == (404, "Public place not found")
    assert row_values(saved_places(db)[0]) == before and revision_of(db) == 1


def test_patch_routes_convert_legacy_rows_and_refuse_old_fields(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db)
    seed_legacy_place(db)
    client = api(owner)

    old_field = client.patch(f"/api/trips/7/places/{LEGACY_ID}", json={"expectedRevision": 1, "meta": "옛 메모"})
    renamed = client.patch(f"/api/trips/7/places/{LEGACY_ID}", json={"expectedRevision": 1, "label": "우리 단골집"})

    assert old_field.status_code == 422
    assert renamed.status_code == 200
    shown = renamed.json()["days"]["1"][0]
    assert (shown["label"], shown["placeOrigin"], shown["needsConfirmation"], shown["address"]) == ("우리 단골집", "custom", False, None)


@pytest.mark.parametrize(("replacement", "extra"), [
    ({"publicPlace": {**TOUR_REF, "latitude": 34.7443}}, "latitude"),
    ({"customPlace": {"name": "내 장소", "address": "카카오 주소"}}, "address"),
])
def test_unknown_fields_inside_public_or_custom_place_of_a_patch_are_refused_and_change_nothing(
    db: Session, api: Callable[[User], TestClient], replacement: dict[str, object], extra: str
) -> None:
    owner, _ = seed_trip(db)
    before = row_values(seed_legacy_place(db))

    response = api(owner).patch(f"/api/trips/7/places/{LEGACY_ID}", json={"expectedRevision": 1, **replacement})

    assert response.status_code == 422
    assert [(error["type"], error["loc"][-1]) for error in response.json()["detail"]] == [("extra_forbidden", extra)]
    assert row_values(saved_places(db)[0]) == before and revision_of(db) == 1


def seed_candidate_places(db: Session) -> None:
    db.add_all([
        public_place("T1", name="오동도횟집", category="food", photo=None, lat=34.7446, lng=127.7666),
        public_place("T2", source="sangga", name="오동도횟집바다", category="food", photo=None, lat=34.7447, lng=127.7667),
        public_place("T3", source="sangga", name="오동도횟집별관", category="food", photo=None, lat=34.7448, lng=127.7668),
        public_place("T4", source="sangga", name="오동도횟집본점", category="food", photo=None, lat=34.7449, lng=127.7669),
        public_place("FAR", name="오동도횟집먼곳", category="food", photo=None, lat=35.2, lng=128.2),
        public_place("OTHER", name="전혀 다른 가게", category="food", photo=None),
    ])
    db.commit()


def test_public_candidates_for_a_legacy_row_are_the_nearest_three_public_places(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db)
    seed_candidate_places(db)
    seed_legacy_place(db, place_name="오동도횟")   # 공공데이터 이름 네 곳에 들어 있다(포함) - 먼 곳 · 다른 이름은 후보가 아니다

    response = api(owner).get(f"/api/trips/7/places/{LEGACY_ID}/public-candidates")

    assert response.status_code == 200
    body = response.json()
    assert [place["sourceId"] for place in body["places"]] == ["T1", "T2", "T3"]   # 가까운 순 최대 3곳
    assert set(body["places"][0]) == {"source", "sourceId", "name", "address", "latitude", "longitude", "category", "sido", "city",
                                      "photoUrl", "photoLicense", "distanceMeters"}


def test_an_exact_name_is_returned_as_the_single_candidate(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db)
    db.add(public_place(name="오동도", category="sight"))
    db.commit()
    seed_legacy_place(db, place_name="오동도", category_group_code="AT4")

    response = api(owner).get(f"/api/trips/7/places/{LEGACY_ID}/public-candidates")

    assert [place["sourceId"] for place in response.json()["places"]] == ["126508"]


def test_public_candidates_are_empty_unless_the_row_is_a_legacy_row_with_a_point(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db)
    seed_candidate_places(db)
    seed_legacy_place(db, id=11, place_name="오동도횟집", place_origin="public")   # 새 방식 행
    seed_legacy_place(db, id=12, place_name="오동도횟집", place_origin="custom")
    seed_legacy_place(db, id=13, place_name="오동도횟집", latitude=None, longitude=None)   # 좌표 없는 예전 행
    seed_legacy_place(db, id=14, place_name="오동도횟집", source_provider=None, external_place_id=None)   # 카카오가 아닌 예전 행
    client = api(owner)

    for place_id in (11, 12, 13, 14):
        assert client.get(f"/api/trips/7/places/{place_id}/public-candidates").json() == {"places": []}


def test_public_candidates_need_an_editor_and_a_place_of_the_trip(db: Session, api: Callable[[User], TestClient]) -> None:
    seed_trip(db)
    viewer = seed_viewer(db)
    seed_legacy_place(db)

    assert api(viewer).get(f"/api/trips/7/places/{LEGACY_ID}/public-candidates").status_code == 403
    assert api(make_user(99, "Outsider")).get(f"/api/trips/7/places/{LEGACY_ID}/public-candidates").status_code == 404
    assert api(db.get(User, 1)).get("/api/trips/7/places/999/public-candidates").status_code == 404


def test_public_candidates_never_log_or_store_the_kakao_values(
    db: Session, api: Callable[[User], TestClient], caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner, _ = seed_trip(db)
    seed_candidate_places(db)
    legacy = seed_legacy_place(db, place_name="오동도횟집바다전망")
    before = row_values(legacy)
    monkeypatch.setattr(trip_service.logger, "handlers", [caplog.handler])   # uvicorn.error 로그도 이 시험에서 보이게(앱이 따로 모아 둔 것을 시험 동안만 caplog 로)
    caplog.set_level(logging.DEBUG)

    response = api(owner).get(f"/api/trips/7/places/{LEGACY_ID}/public-candidates")

    assert response.status_code == 200
    assert [place["sourceId"] for place in response.json()["places"]] == ["T1", "T2"]   # 이 이름을 품은 공공데이터 이름 두 곳
    for value in ("오동도횟집바다전망", "34.7443", "127.7663", "수정동", "place.map.kakao.com/777"):
        assert value not in caplog.text   # 로그에 남기지 않는다
    assert "오동도횟집바다전망" not in response.text   # 응답에도 카카오 값은 없다
    assert row_values(saved_places(db)[0]) == before and revision_of(db) == 1   # 읽기만 한다 - 행도 revision 도 그대로
    assert db.scalar(select(func.count()).select_from(PublicPlace)) == 6   # 공공데이터 표에 카카오 값을 더하지 않는다


YEOSU_AREA = "jeonnam-yeosu-suncheon"   # 전남 · 여수, 순천


def set_area(db: Session, area_id: str | None, trip_id: int = 7) -> None:
    db.get(Trip, trip_id).travel_area_id = area_id
    db.commit()


def recommended(db: Session, user: User, trip_handle: str = "7") -> list[dict[str, object]]:
    db.expire_all()   # 시험이 직접 심은 행도 보이게 - 요청마다 새 세션인 운영과 같다
    return trip_service.list_recommendations(db, user, trip_handle) or []


def recommended_ids(db: Session, user: User, trip_handle: str = "7") -> list[str]:
    return [str(item["publicSourceId"]) for item in recommended(db, user, trip_handle)]


AREA_ROWS = (
    ("Y1", "오동도", "전남", "여수"), ("S1", "순천만", "전남", "순천"), ("G1", "광양매화마을", "전남", "광양"),
    ("E1", "서울숲", "서울", "성동"), ("GW", "강원 고성 통일전망대", "강원", "고성"), ("GN", "경남 고성 공룡박물관", "경남", "고성"),
    ("SJ1", "세종호수공원", "세종", "한솔동"), ("SJ2", "조치원역", "세종", "조치원읍"),
    ("JJ1", "협재해변", "제주", "제주"), ("JJ2", "천지연폭포", "제주", "서귀포"),
)


@pytest.mark.parametrize(("area_id", "expected"), [
    (YEOSU_AREA, {"Y1", "S1"}),   # 시도 + 포함 시군
    (make_whole_area_id("전남"), {"Y1", "S1", "G1"}),   # whole: 은 시도 전체
    (make_administrative_area_id("전남", "여수시"), {"Y1"}),
    (make_administrative_area_id("강원", "고성군"), {"GW"}),   # 같은 시군 이름이 두 시도에 있어도 시도와 함께 건다
    (make_administrative_area_id("경남", "고성군"), {"GN"}),
    ("gyeongnam-tongyeong-geoje-goseong", {"GN"}),
    ("sejong-all", {"SJ1", "SJ2"}),   # 세종의 시군 자리는 읍 · 동 이름 - 시도만으로 고른다
    (make_whole_area_id("세종"), {"SJ1", "SJ2"}),
    (make_policy_region_area_id("세종", "세종"), {"SJ1", "SJ2"}),   # 정책에서 온 세종 지역도 시도만으로 고른다
    ("jeju-all", {"JJ1", "JJ2"}),   # 옛 *-all 은 시도 전체
    ("jeju-seogwipo", {"JJ2"}),
    ("not-an-area", set()),
    (None, set()),
])
def test_recommendations_follow_the_trip_area(db: Session, area_id: str | None, expected: set[str]) -> None:
    owner, _ = seed_trip(db, travel_area_id=area_id)
    db.add_all(public_place(source_id, name=name, sido=sido, city=city) for source_id, name, sido, city in AREA_ROWS)
    db.commit()

    assert set(recommended_ids(db, owner)) == expected


def test_area_scope_reads_whole_legacy_whole_sejong_and_city_areas() -> None:
    assert area_scope(get_travel_area(YEOSU_AREA)) == ("전남", ("여수", "순천"))
    assert area_scope(get_travel_area(make_whole_area_id("전남"))) == ("전남", None)
    assert area_scope(get_travel_area("jeju-all")) == ("제주", None)
    assert area_scope(get_travel_area("sejong-all")) == ("세종", None)
    assert area_scope(get_travel_area(make_administrative_area_id("제주", "제주시"))) == ("제주", ("제주",))   # 제주시 하나는 시도 전체가 아니다
    assert area_scope(None) is None


def test_photo_first_then_tourapi_without_photo_then_store_data(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add_all([
        public_place("STORE", source="sangga", name="가게식당", category="food", photo=None),
        public_place("NOPHOTO", name="사진없는식당", category="food", photo=None),
        public_place("PHOTO", name="사진있는식당", category="food"),
    ])
    db.commit()

    assert recommended_ids(db, owner) == ["PHOTO", "NOPHOTO", "STORE"]


def test_order_is_fixed_per_trip_and_follows_md5_of_the_source_id_and_trip_id(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add_all([
        Trip(id=8, owner_id=1, title="두 번째 여행", status="confirmed", revision=1, start_date=date(2026, 11, 1), end_date=date(2026, 11, 1),
             region="여수", travel_area_id=YEOSU_AREA, participant_count=1),
        TripDay(id=3, trip_id=8, day_number=1, date=date(2026, 11, 1)),
    ])
    ids = [f"A{n:02d}" for n in range(12)]
    db.add_all(public_place(source_id, name=f"명소{source_id}") for source_id in ids)
    db.commit()

    def expected(trip_id: int) -> list[str]:
        return sorted(ids, key=lambda source_id: hashlib.md5(f"{source_id}{trip_id}".encode()).hexdigest())

    first = recommended_ids(db, owner, "7")
    assert first == expected(7)
    assert recommended_ids(db, owner, "7") == first   # 다시 불러도 같다
    assert recommended_ids(db, owner, "8") == expected(8) != first   # 일정이 다르면 다르게 섞인다


def test_a_balanced_mix_comes_first_then_the_groups_take_turns(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add_all(
        [public_place(f"S{n:02d}", name=f"명소{n}", category="sight") for n in range(10)]
        + [public_place(f"F{n:02d}", name=f"식당{n}", category="food") for n in range(10)]
        + [public_place(f"H{n:02d}", name=f"숙소{n}", category="stay") for n in range(10)]
    )
    db.commit()

    groups = [str(item["categoryGroup"]) for item in recommended(db, owner)]

    assert groups[:8] == ["attraction"] * 3 + ["food"] * 3 + ["stay"] * 2   # 관광 3 · 음식 3 · 숙박 2 를 먼저
    assert groups[8:] == ["attraction", "food", "stay"] * 3 + ["attraction"]   # 남는 10자리는 세 묶음이 번갈아
    assert len(groups) == 18

    set_area(db, "jeju-seogwipo")
    db.add_all([public_place(f"X{n}", name=f"서귀포명소{n}", sido="제주", city="서귀포") for n in range(5)])
    db.commit()
    assert len(recommended(db, owner)) == 5   # 모자라면 있는 만큼만 - 가짜로 채우지 않는다


def test_places_already_in_the_trip_are_left_out_by_key_and_by_name(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add_all([
        public_place("126508", name="오동도"),   # 같은 공공데이터 장소를 이미 담았다
        public_place("MA01", source="sangga", name="카페 마레 여수점", category="cafe", photo=None),   # 같은 이름의 나만의 장소가 있다
        public_place("T9", name="순천만"),   # 같은 이름의 예전 카카오 행이 있다
        public_place("KEEP", name="향일암"),
    ])
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, publicPlace=TOUR_REF))
    patch(db, owner, saved_places(db)[0].id, 2, label="내가 부르는 이름")   # 사용자 이름을 붙여도 같은 공공데이터 장소로 센다(공공데이터 이름 · 출처 열이 그대로다)
    sunk = db.get(PublicPlace, ("tourapi", "126508"))
    sunk.name, sunk.name_key = "오동도 해상공원", name_key("오동도 해상공원")   # 그 뒤 공공데이터 쪽 이름이 바뀌어 이름으로는 못 거르는 경우도 (출처, ID)로 거른다
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=3, customPlace={"name": "카페마레 여수점"}))
    seed_legacy_place(db, place_name="순천만")

    assert recommended_ids(db, owner) == ["KEEP"]


def test_store_arts_and_sports_are_left_out_but_libraries_and_historic_sites_stay(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add_all([
        public_place("GYM", source="sangga", name="동네헬스장", category="leisure", photo=None),
        public_place("LIB", source="sangga", name="여수도서관", category="culture", photo=None),
        public_place("RAFT", name="레포츠체험", category="leisure"),
    ])
    db.commit()

    assert sorted(recommended_ids(db, owner)) == ["LIB", "RAFT"]


def test_without_usable_public_places_the_saved_summary_is_used(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add(Recommendation(user_id=1, trip_id=7, query="trip_create", result=[
        {"label": "attraction", "title": "저장된 요약 장소", "meta": "Day 1", "reason": "일정 생성 시 저장된 추천 요약입니다."},
    ]))
    db.commit()

    empty_table = recommended(db, owner)   # 표가 비었다
    db.add(public_place())
    db.commit()
    with_places = recommended(db, owner)
    set_area(db, None)
    no_area = recommended(db, owner)   # 지역을 못 가린다

    assert [(item["title"], item["sourceType"]) for item in empty_table] == [("저장된 요약 장소", "savedSummary")]
    assert [(item["title"], item["sourceType"]) for item in with_places] == [("오동도", "public_place")]   # 공공데이터가 있으면 요약은 쓰지 않는다
    assert [(item["title"], item["sourceType"]) for item in no_area] == [("저장된 요약 장소", "savedSummary")]


def test_suggested_days_go_round_the_trip_days(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add_all(public_place(f"P{n}", name=f"명소{n}") for n in range(5))
    db.commit()

    assert [item["suggestedDay"] for item in recommended(db, owner)] == [1, 2, 1, 2, 1]


def test_a_public_recommendation_has_the_documented_shape(db: Session) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add_all([public_place(), public_place("MA01", source="sangga", name="카페마레", category="cafe", photo=None, address=None)])
    db.commit()

    sight, cafe = recommended(db, owner)

    assert sight == {
        "id": "public:tourapi:126508", "label": "오동도", "title": "오동도", "meta": "관광지 · 전남광주통합특별시 여수시 오동도로 222",
        "reason": "여수 일정에 추가로 검토할 만한 공공데이터 장소입니다.", "categoryGroup": "attraction", "categoryCode": None,
        "categoryName": None, "phone": None, "address": "전남광주통합특별시 여수시 오동도로 222", "latitude": 34.7443, "longitude": 127.7663,
        "placeUrl": None, "suggestedDay": 1, "aiReview": None, "sourceProvider": None, "externalPlaceId": None, "sourceType": "public_place",
        "publicSource": "tourapi", "publicSourceId": "126508", "publicCategory": "sight",
        "photoUrl": "https://tong.visitkorea.or.kr/cms/resource/a.jpg", "photoLicense": "Type3",
    }
    assert (cafe["categoryGroup"], cafe["meta"], cafe["address"], cafe["photoUrl"], cafe["publicCategory"]) == ("cafe", "카페", None, None, "cafe")


def test_recommendation_route_answers_with_public_places_and_the_saved_summary(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    db.add(Recommendation(user_id=1, trip_id=7, query="trip_create", result=[{"label": "a", "title": "저장 요약", "meta": "m", "reason": "r"}]))
    db.commit()
    client = api(owner)

    summary = client.get("/api/trips/7/recommendations")
    db.add_all([public_place(), public_place("MA01", source="sangga", name="카페마레", category="cafe", photo=None)])
    db.commit()
    public = client.get("/api/trips/7/recommendations")

    assert [item["sourceType"] for item in summary.json()] == ["savedSummary"]
    assert public.status_code == 200
    assert [(item["sourceType"], item["categoryGroup"], item["publicSource"]) for item in public.json()] == [
        ("public_place", "attraction", "tourapi"), ("public_place", "cafe", "sangga"),
    ]
    assert public.json()[0]["photoLicense"] == "Type3" and public.json()[0]["placeUrl"] is None


def test_area_center_is_the_median_of_the_area_places(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    viewer = seed_viewer(db)
    db.add_all([
        public_place("C1", name="가", lat=34.0, lng=127.0), public_place("C2", name="나", lat=35.0, lng=128.0),
        public_place("C3", name="다", lat=37.0, lng=131.0),   # 멀리 있는 하나가 평균(35.33)을 끌어도 중앙값은 그대로
        public_place("OUT", name="다른지역", sido="서울", city="성동", lat=37.5, lng=127.0),
        public_place("STORE", source="sangga", name="가게", category="food", photo=None, lat=36.9, lng=130.9),   # TourAPI 가 있으면 가게는 보지 않는다
    ])
    db.commit()

    assert api(owner).get("/api/trips/7/area-center").json() == {"latitude": 35.0, "longitude": 128.0}
    assert api(viewer).get("/api/trips/7/area-center").status_code == 200   # 보기 권한이면 된다
    assert api(make_user(99, "Outsider")).get("/api/trips/7/area-center").status_code == 404

    db.add(public_place("C4", name="라", lat=36.0, lng=129.0))
    db.commit()
    assert api(owner).get("/api/trips/7/area-center").json() == {"latitude": 35.5, "longitude": 128.5}   # 짝수 개면 가운데 둘의 평균


def test_area_center_falls_back_to_store_data_and_is_null_without_places(db: Session, api: Callable[[User], TestClient]) -> None:
    owner, _ = seed_trip(db, travel_area_id=YEOSU_AREA)
    client = api(owner)
    assert client.get("/api/trips/7/area-center").json() == {"latitude": None, "longitude": None}   # 표가 비었다

    db.add_all([public_place("S1", source="sangga", name="가게1", category="food", photo=None, lat=34.7, lng=127.7),
                public_place("S2", source="sangga", name="가게2", category="food", photo=None, lat=34.9, lng=127.9)])
    db.commit()
    assert client.get("/api/trips/7/area-center").json() == pytest.approx({"latitude": 34.8, "longitude": 127.8})   # TourAPI 가 없으면 상가정보

    set_area(db, None)
    assert client.get("/api/trips/7/area-center").json() == {"latitude": None, "longitude": None}   # 지역을 못 가린다


GEO = GeoHit("parcel", 4401, "1213010200100010006", "전남광주통합특별시 여수시 수정동 1-6", 34.744764, 127.767783, 0.0)


def use_geo(monkeypatch, *, found=True, error: Exception | None = None) -> list[tuple]:
    calls: list[tuple] = []

    def get_by_ref(db, kind, feature_id):
        calls.append((kind, feature_id))
        if error is not None:
            raise error
        return GEO if found else None

    monkeypatch.setattr(trip_service.geo_repository, "get_by_ref", get_by_ref)
    return calls


def test_a_geo_reference_with_a_pin_fills_the_address_and_the_public_center(db: Session, monkeypatch) -> None:
    owner, _ = seed_trip(db)
    calls = use_geo(monkeypatch)
    payload = trip_service.add_place_to_trip_day(
        db, owner, "7", 1,
        CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "오동도", "geoRef": {"kind": "parcel", "id": 4401, "pin": True}}, kakaoPlaceId="777"),
    )
    (row,) = saved_places(db)
    assert calls == [("parcel", 4401)]
    assert (row.place_name, row.place_origin, row.address, row.geo_kind, row.geo_pnu) == ("오동도", "custom", GEO.address, "parcel", GEO.pnu)
    assert (float(row.latitude), float(row.longitude)) == (GEO.latitude, GEO.longitude)
    assert payload["days"][1][0]["geoKind"] == "parcel" and payload["days"][1][0]["meta"] == GEO.address


def test_a_geo_reference_without_a_pin_keeps_only_the_address(db: Session, monkeypatch) -> None:
    owner, _ = seed_trip(db)
    use_geo(monkeypatch)
    trip_service.add_place_to_trip_day(
        db, owner, "7", 1,
        CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "넓은 공원", "geoRef": {"kind": "parcel", "id": 4401, "pin": False}}),
    )
    (row,) = saved_places(db)
    assert (row.address, row.latitude, row.longitude, row.geo_kind) == (GEO.address, None, None, "parcel")


def test_custom_place_takes_only_a_name_and_an_optional_geo_reference() -> None:
    # 옛 test_custom_place_name_and_point_rules 의 이름 규칙을 옮겨 왔다(좌표 규칙은 아래 거부 시험이 대신한다)
    assert CustomPlaceInput(name="  내 장소  ").name == "내 장소"   # 앞뒤 공백은 뺀다
    assert CustomPlaceInput(name="가" * 100).name == "가" * 100
    for bad_name in ("", "   ", "가" * 101):
        with pytest.raises(ValidationError):
            CustomPlaceInput(name=bad_name)
    assert CustomPlaceInput(name="내 장소").geoRef is None
    ref = CustomPlaceInput(name="오동도", geoRef={"kind": "building", "id": 7, "pin": False}).geoRef
    assert (ref.kind, ref.id, ref.pin) == ("building", 7, False)


def test_refuses_raw_coordinates_in_a_custom_place(db: Session, api: Callable[[User], TestClient]) -> None:
    # 데브톡 151842: 지도에서 찍은 좌표는 저장 · 활용 불가 - 서버가 받지 않는다(코덱스 HIGH)
    for bad in ({"name": "a", "latitude": 34.7, "longitude": 127.7}, {"name": "a", "address": "카카오 주소"},
                {"name": "a", "geoRef": {"kind": "parcel", "id": 1, "pin": True, "latitude": 34.7}},
                {"name": "a", "geoRef": {"kind": "road", "id": 1, "pin": True}}, {"name": "a", "geoRef": {"kind": "parcel", "id": 0, "pin": True}},
                {"name": "a", "geoRef": {"kind": "parcel", "id": 2**63, "pin": True}}):   # BIGINT 위로 넘는 id 는 DB 오류(500)가 아니라 422
        with pytest.raises(ValidationError):
            CustomPlaceInput(**bad)

    # 요청으로도 막힌다 - 조작한 요청이 좌표를 실어 보내면 422, 앞에 정상 장소가 있어도 아무것도 쓰지 않고 revision 도 그대로
    owner, _ = seed_trip(db)
    client = api(owner)
    pinned = {"name": "찍은 곳", "latitude": 34.7, "longitude": 127.7}
    single = client.post("/api/trips/7/days/1/places", json={"expectedRevision": 1, "customPlace": pinned})
    batch = client.post(
        "/api/trips/7/days/1/places/batch",
        json={"expectedRevision": 1, "places": [{"customPlace": {"name": "이름만"}}, {"customPlace": pinned}]},
    )
    for response in (single, batch):
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert {error["type"] for error in errors} == {"extra_forbidden"}
        assert sorted(error["loc"][-1] for error in errors) == ["latitude", "longitude"]
    assert saved_places(db) == [] and revision_of(db) == 1


def test_a_geo_reference_gone_after_the_monthly_refresh_is_404_and_writes_nothing(db: Session, monkeypatch) -> None:
    owner, _ = seed_trip(db)
    use_geo(monkeypatch, found=False)
    with pytest.raises(trip_service.TripServiceError) as missing:
        trip_service.add_places_to_trip_day(
            db, owner, "7", 1,
            CreateTripPlacesRequest(expectedRevision=1, places=[{"customPlace": {"name": "a"}}, {"customPlace": {"name": "오동도", "geoRef": {"kind": "parcel", "id": 4401, "pin": True}}}]),
        )
    assert (missing.value.status_code, missing.value.detail) == (404, "Address reference not found")
    assert saved_places(db) == [] and revision_of(db) == 1


def test_a_missing_geo_table_is_503_writes_nothing_and_leaves_the_session_usable(db: Session, monkeypatch, caplog) -> None:
    # 실제 실패: 이 SQLite 시험 DB 에는 geo 표가 없다(적재 전 · 마이그레이션 직후와 같다). 가짜를 쓰지 않는다(코덱스 재검토 MEDIUM)
    owner, _ = seed_trip(db)
    monkeypatch.setattr(trip_service.logger, "handlers", [caplog.handler])   # uvicorn.error 로그는 앱이 따로 모아 두고 위로 안 올린다(propagate 끔) - 이 시험 동안만 caplog 로
    caplog.set_level(logging.WARNING)
    with pytest.raises(trip_service.TripServiceError) as unavailable:
        trip_service.add_place_to_trip_day(
            db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "오동도", "geoRef": {"kind": "parcel", "id": 4401, "pin": True}}),
        )
    assert (unavailable.value.status_code, unavailable.value.detail) == (503, "Address lookup is unavailable")
    assert db.execute(text("SELECT 1")).scalar() == 1   # SAVEPOINT 로 되돌려 세션이 살아 있다
    assert saved_places(db) == [] and revision_of(db) == 1
    assert "geo.parcel" not in caplog.text and "trip_place_geo_ref_failed error=OperationalError" in caplog.text


def test_a_programming_error_in_the_geo_lookup_is_not_hidden_as_503(db: Session, monkeypatch) -> None:
    owner, _ = seed_trip(db)
    use_geo(monkeypatch, error=ValueError("pnu must be 19 digits"))
    with pytest.raises(ValueError):
        trip_service.add_place_to_trip_day(
            db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "오동도", "geoRef": {"kind": "parcel", "id": 4401, "pin": True}}),
        )


def test_switching_a_geo_custom_place_to_a_public_place_clears_the_geo_columns(db: Session, monkeypatch) -> None:
    owner, _ = seed_trip(db)
    use_geo(monkeypatch)
    db.add(public_place())
    db.commit()
    trip_service.add_place_to_trip_day(db, owner, "7", 1, CreateTripPlaceRequest(expectedRevision=1, customPlace={"name": "오동도", "geoRef": {"kind": "parcel", "id": 4401, "pin": True}}))
    (row,) = saved_places(db)
    trip_service.update_trip_place(db, owner, "7", row.id, UpdateTripPlaceRequest(expectedRevision=2, publicPlace=TOUR_REF))
    db.refresh(row)
    assert (row.place_origin, row.geo_kind, row.geo_pnu) == ("public", None, None)
