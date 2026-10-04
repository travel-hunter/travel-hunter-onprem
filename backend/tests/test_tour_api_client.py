"""TourAPI client tests — canned responses only, no real HTTP."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.core.logging import JsonFormatter
from app.services.tour_api import (
    CONTENT_TYPE_TOURIST_SPOT,
    TourApiConfigurationError,
    TourApiClient,
    build_tour_api_client,
    validate_tour_api_settings,
)


def make_settings(**overrides: object) -> Settings:
    fields: dict[str, object] = {
        "tour_api_enabled": True,
        "tour_api_service_key": "test-service-key",
        "tour_api_base_url": "https://apis.data.go.kr/B551011/KorService2",
        "tour_api_timeout_seconds": 5.0,
    }
    fields.update(overrides)
    return replace(Settings(), **fields)  # type: ignore[arg-type]


def tour_api_body(items: object) -> dict[str, Any]:
    return {
        "response": {
            "header": {"resultCode": "0000", "resultMsg": "OK"},
            "body": {"items": {"item": items}, "numOfRows": 10, "totalCount": 2},
        }
    }


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def make_client(payload: dict[str, Any], calls: list[dict[str, Any]] | None = None) -> TourApiClient:
    def fake_get(url: str, **kwargs: Any) -> FakeResponse:
        if calls is not None:
            calls.append({"url": url, **kwargs})
        return FakeResponse(payload)

    return TourApiClient(settings_obj=make_settings(), http_get=fake_get)


SPOT_ITEM = {
    "contentid": "126508",
    "title": "두륜산 케이블카",
    "firstimage": "https://tong.visitkorea.or.kr/cms/resource/1.jpg",
    "firstimage2": "https://tong.visitkorea.or.kr/cms/resource/1_t.jpg",
    "addr1": "전라남도 해남군 삼산면",
    "areacode": "38",
    "sigungucode": "16",
}


def test_disabled_settings_build_none() -> None:
    disabled = replace(Settings(), tour_api_enabled=False)
    assert build_tour_api_client(disabled) is None


def test_enabled_without_key_raises_configuration_error() -> None:
    with pytest.raises(TourApiConfigurationError):
        validate_tour_api_settings(make_settings(tour_api_service_key=""))


def test_enabled_with_bad_timeout_raises_configuration_error() -> None:
    with pytest.raises(TourApiConfigurationError):
        validate_tour_api_settings(make_settings(tour_api_timeout_seconds=0))


def test_list_area_spots_parses_items_list() -> None:
    calls: list[dict[str, Any]] = []
    client = make_client(tour_api_body([SPOT_ITEM]), calls)
    spots = client.list_area_spots(area_code="38", sigungu_code="16")
    assert len(spots) == 1
    spot = spots[0]
    assert spot.content_id == "126508"
    assert spot.first_image is not None
    assert spot.first_image.endswith("1.jpg")
    assert spot.addr1 is not None and spot.addr1.startswith("전라남도")
    params = calls[0]["params"]
    assert params["contentTypeId"] == CONTENT_TYPE_TOURIST_SPOT
    assert params["areaCode"] == "38"
    assert params["sigunguCode"] == "16"


def test_items_single_dict_is_handled() -> None:
    client = make_client(tour_api_body(SPOT_ITEM))
    spots = client.list_area_spots(area_code="38")
    assert len(spots) == 1


def test_items_empty_string_is_handled() -> None:
    # TourAPI는 결과가 없을 때 items를 빈 문자열로 내려보내는 것으로 알려져 있다.
    client = make_client(tour_api_body(""))
    assert client.list_area_spots(area_code="38") == []


def test_broken_item_is_skipped_not_fatal() -> None:
    broken = {"title": "id 없는 항목"}
    client = make_client(tour_api_body([broken, SPOT_ITEM]))
    spots = client.list_area_spots(area_code="38")
    assert len(spots) == 1
    assert spots[0].content_id == "126508"


def test_search_spots_by_keyword_sends_keyword() -> None:
    calls: list[dict[str, Any]] = []
    client = make_client(tour_api_body([SPOT_ITEM]), calls)
    spots = client.search_spots_by_keyword(keyword="해남 관광지")
    assert len(spots) == 1
    assert calls[0]["params"]["keyword"] == "해남 관광지"


def test_list_area_codes_parses_codes() -> None:
    payload = tour_api_body(
        [
            {"code": "38", "name": "전라남도"},
            {"code": "35", "name": "경상북도"},
        ]
    )
    client = make_client(payload)
    codes = client.list_area_codes()
    assert [(c.code, c.name) for c in codes] == [
        ("38", "전라남도"),
        ("35", "경상북도"),
    ]


def test_current_api_path_decodes_an_encoded_service_key_once() -> None:
    calls: list[dict[str, Any]] = []
    encoded_key = "test%2Fservice%2Bkey"
    client = TourApiClient(
        settings_obj=make_settings(
            tour_api_service_key=encoded_key,
            tour_api_base_url="https://apis.data.go.kr/B551011/KorService2",
        ),
        http_get=lambda url, **kwargs: (
            calls.append({"url": url, **kwargs}) or FakeResponse(tour_api_body([]))
        ),
    )

    client.list_area_codes()

    assert calls[0]["url"].endswith("/KorService2/areaCode2")
    assert calls[0]["params"]["serviceKey"] == "test/service+key"


def test_http_error_does_not_include_service_key_in_configuration_error() -> None:
    secret = "must-not-appear-in-error"
    request = httpx.Request(
        "GET", f"https://example.test/areaCode2?serviceKey={secret}"
    )
    response = httpx.Response(400, request=request)

    def failing_get(url: str, **kwargs: Any) -> FakeResponse:
        del url, kwargs

        class ErrorResponse:
            def raise_for_status(self) -> None:
                response.raise_for_status()

            def json(self) -> dict[str, Any]:
                raise AssertionError("unreachable")

        return ErrorResponse()  # type: ignore[return-value]

    client = TourApiClient(
        settings_obj=make_settings(tour_api_service_key=secret),
        http_get=failing_get,
    )

    with pytest.raises(TourApiConfigurationError) as error:
        client.list_area_codes()

    assert secret not in str(error.value)


def test_area_based_page_asks_one_whole_country_type_page_and_keeps_the_total() -> None:
    calls: list[dict[str, Any]] = []
    client = make_client(tour_api_body([{"contentid": "1", "mapx": "127.7", "mapy": "34.7"}]), calls)
    page = client.list_area_based_page(content_type_id="39", page=3, rows=1000, timeout=60.0)

    assert page.items == [{"contentid": "1", "mapx": "127.7", "mapy": "34.7"}]
    assert page.total_count == 2   # tour_api_body 의 totalCount
    assert calls[0]["url"].endswith("/areaBasedList2")
    params = calls[0]["params"]
    assert {key: params[key] for key in ("contentTypeId", "pageNo", "numOfRows", "arrange")} == {
        "contentTypeId": "39", "pageNo": 3, "numOfRows": 1000, "arrange": "A",
    }
    assert "areaCode" not in params   # 전국
    assert calls[0]["timeout"] == 60.0


def test_area_based_page_refuses_an_error_code_or_a_missing_total_instead_of_an_empty_page() -> None:
    quota = {"response": {"header": {"resultCode": "22", "resultMsg": "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"}}}
    with pytest.raises(TourApiConfigurationError, match="resultCode 22"):
        make_client(quota).list_area_based_page(content_type_id="12", page=1, rows=1000)
    no_total = {"response": {"header": {"resultCode": "0000", "resultMsg": "OK"}, "body": {"items": ""}}}
    with pytest.raises(TourApiConfigurationError, match="totalCount"):
        make_client(no_total).list_area_based_page(content_type_id="12", page=1, rows=1000)


def test_an_http_error_logged_with_its_traceback_never_carries_the_service_key() -> None:
    # 2026-10-02 개발서버: 사진 후보 수집이 TourAPI HTTP 오류를 logger.exception 으로 남기며 키가 든 주소가 로그에 실렸다
    def http_get(url: str, *, params: dict[str, object], timeout: float) -> httpx.Response:
        return httpx.Response(500, request=httpx.Request("GET", url, params=params))

    client = TourApiClient(settings_obj=make_settings(), http_get=http_get)
    with pytest.raises(TourApiConfigurationError) as error:
        client.list_area_based_page(content_type_id="12", page=1, rows=10)
    record = logging.LogRecord("x", logging.ERROR, __file__, 1, "public_places_sync_failed", None,
                               (error.type, error.value, error.tb))
    assert "test-service-key" not in JsonFormatter().format(record)
