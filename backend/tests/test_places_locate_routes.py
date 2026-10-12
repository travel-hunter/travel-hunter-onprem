from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api.dependencies import get_current_user
from app.db.session import get_optional_db
from app.main import app
from app.models import User
from app.services import address_fill
from app.services.geo_reference import GeoHit
from tests.test_address_fill import FakeDb


def client_as(user):
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_optional_db] = lambda: FakeDb()
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_locate_needs_login() -> None:
    assert client_as(None).post("/api/places/locate", json={"latitude": 34.74, "longitude": 127.76}).status_code == 401


def test_locate_returns_the_parcel_and_says_whether_its_center_is_close(monkeypatch) -> None:
    monkeypatch.setattr(address_fill.geo_repository, "locate",
                        lambda db, points, **_: [GeoHit("parcel", 77, "4215011500100010000", "강릉시 견소동 1", 37.77, 128.95, 85.0)])
    body = client_as(User(id=1, nickname="t", email="t@example.com")).post("/api/places/locate", json={"latitude": 37.7712, "longitude": 128.9480}).json()
    assert body == {"fill": {"kind": "parcel", "id": 77, "pnu": "4215011500100010000", "address": "강릉시 견소동 1", "latitude": 37.77, "longitude": 128.95, "distanceMeters": 85}, "nearCenter": False}


def test_locate_without_any_shape_or_with_a_broken_lookup_is_an_empty_answer(monkeypatch) -> None:
    client = client_as(User(id=1, nickname="t", email="t@example.com"))
    monkeypatch.setattr(address_fill.geo_repository, "locate", lambda db, points, **_: [None])
    assert client.post("/api/places/locate", json={"latitude": 37.0, "longitude": 125.0}).json() == {"fill": None, "nearCenter": False}
    monkeypatch.setattr(address_fill.geo_repository, "locate", lambda db, points, **_: (_ for _ in ()).throw(OperationalError("SELECT", {}, Exception("down"))))
    assert client.post("/api/places/locate", json={"latitude": 37.0, "longitude": 125.0}).json() == {"fill": None, "nearCenter": False}


def test_a_programming_error_in_locate_is_not_hidden_as_an_empty_answer(monkeypatch) -> None:
    # DB 실패만 '지번 없음'과 같은 빈 답이다. 코드 결함은 500 으로 올라가 화면이 '지번을 확인하지 못했어요'를 보인다(코덱스 재검토 MEDIUM 과 같은 원칙).
    # 예외 자체는 TestClient 에 닿지 않는다 - RequestContextMiddleware(core/request_context.py)가 잡아 로그를 남기고 500 JSON 을 직접 보낸다(다시 올리지 않는다). 그래서 pytest.raises 가 아니라 응답을 본다
    monkeypatch.setattr(address_fill.geo_repository, "locate", lambda db, points, **_: (_ for _ in ()).throw(ValueError("bad row")))
    response = client_as(User(id=1, nickname="t", email="t@example.com")).post("/api/places/locate", json={"latitude": 37.0, "longitude": 125.0})
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal Server Error"
    assert "fill" not in response.json()   # 빈 답({"fill": null, "nearCenter": false})으로 숨기지 않았다


def test_locate_refuses_points_outside_korea_and_unknown_fields() -> None:
    client = client_as(User(id=1, nickname="t", email="t@example.com"))
    assert client.post("/api/places/locate", json={"latitude": 40.0, "longitude": 127.0}).status_code == 422
    assert client.post("/api/places/locate", json={"latitude": 37.0, "longitude": 127.0, "name": "카카오 이름"}).status_code == 422
