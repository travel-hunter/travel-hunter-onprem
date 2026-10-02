"""통합 검색의 장소 찾기(place_search) - 바깥 HTTP 없이 가짜 카카오로. 주소 문자열은 카카오가 10/2 실제로 준 모양이다."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import app
from app.models import User
from app.services import place_search
from app.services.kakao_local import KakaoLocalArea, KakaoLocalClient, KakaoLocalPlace


def place(name: str, address: str, *, code: str = "AT4", category: str = "여행 > 관광,명소 > 섬", pid: str = "1") -> KakaoLocalPlace:
    return KakaoLocalPlace(
        external_place_id=pid, name=name, category_name=category, category_group_code=code, category_group_name=None,
        phone=None, address=address, latitude=34.74, longitude=127.76, place_url=f"http://place.map.kakao.com/{pid}",
    )


def area(address_name: str, r1: str, r2: str, r3: str, code: str) -> KakaoLocalArea:
    return KakaoLocalArea(address_name=address_name, region_1depth_name=r1, region_2depth_name=r2, region_3depth_name=r3,
                          b_code=code, latitude=34.7, longitude=127.7)


class FakeKakao:
    def __init__(self, places=(), areas=(), fail_keyword=False):
        self.places, self.areas, self.fail_keyword = list(places), list(areas), fail_keyword
        self.calls: list[tuple[str, str]] = []

    def search_keyword(self, *, query, size=15, **_):
        self.calls.append(("keyword", query))
        if self.fail_keyword:
            raise RuntimeError("kakao down")
        return self.places

    def search_address(self, *, query, size=30):
        self.calls.append(("address", query))
        return self.areas


def test_place_gets_the_map_region_and_city_from_its_kakao_address() -> None:
    kakao = FakeKakao(places=[
        place("오동도", "전남광주통합특별시 여수시 수정동 1-1", pid="a"),
        place("광주 양림동 펭귄마을", "전남광주통합특별시 남구 양림동 1", pid="b"),
        place("안목해변", "강원특별자치도 강릉시 견소동 286", pid="c"),
        place("웨스틴조선 부산", "부산 해운대구 우동 737", code="AD5", category="여행 > 숙박 > 호텔", pid="d"),
        place("빅트리", "경남 창원시 성산구 중앙동 1", pid="e"),
        place("성산일출봉", "제주특별자치도 서귀포시 성산읍 성산리 1", pid="f"),
    ])
    items = place_search.search_places("오동도", kakao)
    got = [(i["name"], i["sido"], i["city"]) for i in items]
    assert got == [
        ("오동도", "전남", "여수"),
        ("광주 양림동 펭귄마을", "광주", "남구"),   # 통합 주소의 구 = 광주
        ("안목해변", "강원", "강릉"),
        ("웨스틴조선 부산", "부산", "해운대"),
        ("빅트리", "경남", "창원"),
        ("성산일출봉", "제주", "서귀포"),
    ]
    first = items[0]
    assert first["kind"] == "place" and first["id"] == "kakao:a" and first["category"] == "섬"
    assert first["placeUrl"] == "http://place.map.kakao.com/a"
    assert kakao.calls == [("keyword", "오동도")]   # 장소 이름은 주소 검색을 부르지 않는다


def test_a_dong_name_also_asks_the_address_search_for_every_same_named_dong() -> None:
    kakao = FakeKakao(
        places=[place("빅트리", "경남 창원시 성산구 중앙동 1")],
        areas=[
            area("전남광주통합특별시 여수시 중앙동", "전남광주통합특별시", "여수시", "중앙동", "4613010100"),
            area("경기 성남시 중원구 중앙동", "경기", "성남시 중원구", "중앙동", "4113310100"),
            area("전북특별자치도 익산시 중앙동1가", "전북특별자치도", "익산시", "중앙동1가", "4514010100"),
            area("전남광주통합특별시 북구 중앙동", "전남광주통합특별시", "북구", "중앙동", "2917010100"),
        ],
    )
    items = place_search.search_places("중앙동", kakao)
    areas = [(i["name"], i["sido"], i["city"]) for i in items if i["kind"] == "area"]
    assert areas == [("여수시 중앙동", "전남", "여수"), ("성남시 중앙동", "경기", "성남"), ("익산시 중앙동1가", "전북", "익산"), ("북구 중앙동", "광주", "북구")]
    assert items[-1]["kind"] == "place"   # 구역 먼저, 장소는 그 뒤
    assert ("address", "중앙동") in kakao.calls


def test_short_or_disabled_or_failing_search_is_empty_not_an_error(monkeypatch) -> None:
    assert place_search.search_places("여", FakeKakao(places=[place("x", "서울 중구 1")])) == []
    monkeypatch.setattr(place_search, "build_kakao_local_client", lambda: None)
    assert place_search.search_places("오동도") == []
    assert place_search.search_places("오동도", FakeKakao(fail_keyword=True)) == []


def test_unknown_first_word_keeps_the_place_without_a_region() -> None:
    items = place_search.search_places("어딘가", FakeKakao(places=[place("어딘가", "대구경북통합특별시 안동시 1")]))
    assert items[0]["sido"] is None and items[0]["name"] == "어딘가"


def test_kakao_client_reads_only_region_rows_from_the_address_search() -> None:
    class Settings:
        kakao_local_enabled = True
        kakao_local_rest_api_key = "test-key"
        kakao_local_timeout_seconds = 5.0

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"documents": [
                {"address_type": "REGION", "address_name": "강원특별자치도 강릉시 학동", "x": "128.93", "y": "37.75",
                 "address": {"region_1depth_name": "강원특별자치도", "region_2depth_name": "강릉시", "region_3depth_name": "학동", "b_code": "5115010500"}},
                {"address_type": "ROAD_ADDR", "address_name": "강원 강릉시 학동길 1", "x": "128.9", "y": "37.7", "address": {}},
            ]}

    seen = {}

    def http_get(url, headers, params, timeout):
        seen.update(url=url, params=params)
        return Response()

    areas = KakaoLocalClient(settings_obj=Settings(), http_get=http_get).search_address(query="학동")
    assert [(a.region_2depth_name, a.region_3depth_name, a.latitude) for a in areas] == [("강릉시", "학동", 37.75)]
    assert seen["url"].endswith("/v2/local/search/address.json") and seen["params"]["analyze_type"] == "similar"


def test_places_route_needs_login_and_returns_camel_case_items(monkeypatch) -> None:
    client = TestClient(app)
    assert client.get("/api/places/search?query=오동도").status_code == 401

    user = User(id=1, email="u@example.com", nickname="u", onboarding_completed=True,
                created_at=datetime(2026, 10, 3), updated_at=datetime(2026, 10, 3))
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(place_search, "build_kakao_local_client", lambda: FakeKakao(places=[place("오동도", "전남광주통합특별시 여수시 수정동 1")]))
    try:
        found = client.get("/api/places/search?query=오동도")
        too_long = client.get("/api/places/search", params={"query": "가" * 81})
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert found.status_code == 200
    assert found.json() == [{
        "kind": "place", "id": "kakao:1", "name": "오동도", "category": "섬", "categoryCode": "AT4",
        "address": "전남광주통합특별시 여수시 수정동 1", "latitude": 34.74, "longitude": 127.76,
        "placeUrl": "http://place.map.kakao.com/1", "sido": "전남", "city": "여수",
    }]
    assert too_long.status_code == 422
