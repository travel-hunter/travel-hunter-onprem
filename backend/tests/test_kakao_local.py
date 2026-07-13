import httpx

from app.services.kakao_local import (
    KAKAO_LOCAL_DEFAULT_SIZE,
    KakaoLocalClient,
    KakaoLocalConfigurationError,
    KakaoLocalPlace,
    build_kakao_local_client,
    validate_kakao_local_settings,
)


def test_validate_kakao_local_settings_fails_when_enabled_without_key() -> None:
    settings = type("Settings", (), {"kakao_local_enabled": True, "kakao_local_rest_api_key": "", "kakao_local_timeout_seconds": 5})()
    try:
        validate_kakao_local_settings(settings)
        assert False, "expected KakaoLocalConfigurationError"
    except KakaoLocalConfigurationError:
        pass


def test_validate_kakao_local_settings_succeeds_with_key() -> None:
    settings = type("Settings", (), {"kakao_local_enabled": True, "kakao_local_rest_api_key": "test", "kakao_local_timeout_seconds": 5})()

    validate_kakao_local_settings(settings)


def response_payload(status_code: int, payload: dict) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("GET", "https://dapi.kakao.com/v2/local/search/keyword.json"),
    )


def test_build_kakao_local_client_returns_none_when_disabled() -> None:
    settings = type("Settings", (), {"kakao_local_enabled": False})()

    assert build_kakao_local_client(settings) is None


def test_search_keyword_maps_documents_and_uses_query_filters() -> None:
    calls: list[dict] = []

    def fake_get(url: str, *, headers: dict, params: dict, timeout: float) -> httpx.Response:
        calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        return response_payload(
            200,
            {
                "documents": [
                    {
                        "id": "26338954",
                        "place_name": "성산 일출봉",
                        "category_name": "관광>자연휴양",
                        "category_group_code": "AT4",
                        "category_group_name": "관광명소",
                        "address_name": "제주 제주시 수렴동 2454",
                        "road_address_name": "제주 제주시 용천로 56",
                        "phone": "064-123-4567",
                        "x": "126.1234567",
                        "y": "33.4567891",
                        "place_url": "http://place.map.kakao.com/26338954",
                    }
                ]
            },
        )

    client = KakaoLocalClient(
        settings_obj=type(
            "Settings",
            (),
            {
                "kakao_local_enabled": True,
                "kakao_local_rest_api_key": "test",
                "kakao_local_timeout_seconds": 5,
            },
        )(),
        http_get=fake_get,
    )
    places = client.search_keyword(query="제주 일출봉", category_group_code="AT4")

    assert len(places) == 1
    place = places[0]
    assert isinstance(place, KakaoLocalPlace)
    assert place.external_place_id == "26338954"
    assert place.name == "성산 일출봉"
    assert place.category_group_code == "AT4"
    assert place.category_group_name == "관광명소"
    assert place.category_name == "관광>자연휴양"
    assert place.phone == "064-123-4567"
    assert place.address == "제주 제주시 수렴동 2454"
    assert place.latitude == 33.4567891
    assert place.longitude == 126.1234567
    assert place.place_url == "http://place.map.kakao.com/26338954"
    assert calls[0]["url"] == "https://dapi.kakao.com/v2/local/search/keyword.json"
    assert calls[0]["params"]["query"] == "제주 일출봉"
    assert calls[0]["params"]["category_group_code"] == "AT4"
    assert calls[0]["params"]["size"] == KAKAO_LOCAL_DEFAULT_SIZE
    assert calls[0]["headers"]["Authorization"] == "KakaoAK test"


def test_search_keyword_skips_invalid_documents_and_returns_others() -> None:
    def fake_get(_url: str, *, headers: dict, params: dict, timeout: float) -> httpx.Response:
        return response_payload(
            200,
            {
                "documents": [
                    {"bad": "data"},
                    {
                        "id": "2",
                        "place_name": "해녀의 집",
                        "category_name": "음식점>해산물",
                        "category_group_code": "FD6",
                        "x": "128.0",
                        "y": "37.0",
                        "place_url": "http://place.map.kakao.com/2",
                    },
                ]
            },
        )

    client = KakaoLocalClient(
        settings_obj=type(
            "Settings",
            (),
            {
                "kakao_local_enabled": True,
                "kakao_local_rest_api_key": "test",
                "kakao_local_timeout_seconds": 5,
            },
        )(),
        http_get=fake_get,
    )
    places = client.search_keyword(query="제주")

    assert len(places) == 1
    assert places[0].name == "해녀의 집"
    assert places[0].external_place_id == "2"
