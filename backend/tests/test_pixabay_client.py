"""Pixabay fallback client tests use canned responses only."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import httpx
import pytest

from app.core.config import Settings
from app.services.pixabay import (
    PixabayConfigurationError,
    PixabayClient,
    build_pixabay_client,
    validate_pixabay_settings,
)


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "pixabay_enabled": True,
        "pixabay_api_key": "test-pixabay-key",
        "pixabay_timeout_seconds": 5.0,
    }
    values.update(overrides)
    return replace(Settings(), **values)  # type: ignore[arg-type]


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def test_disabled_settings_build_no_provider() -> None:
    assert build_pixabay_client(replace(Settings(), pixabay_enabled=False)) is None


def test_enabled_without_key_raises_configuration_error() -> None:
    with pytest.raises(PixabayConfigurationError):
        validate_pixabay_settings(make_settings(pixabay_api_key=""))


def test_search_images_normalizes_photo_and_attribution() -> None:
    calls: list[dict[str, Any]] = []
    payload = {
        "hits": [
            {
                "id": 123,
                "tags": "river, landscape",
                "largeImageURL": "https://cdn.example.test/full.jpg",
                "webformatURL": "https://cdn.example.test/thumb.jpg",
                "user": "photographer",
                "pageURL": "https://pixabay.com/photos/123/",
            }
        ]
    }

    client = PixabayClient(
        settings_obj=make_settings(),
        http_get=lambda url, **kwargs: (
            calls.append({"url": url, **kwargs}) or FakeResponse(payload)
        ),
    )

    images = client.search_images(query="공주 풍경", rows=8)

    assert len(images) == 1
    assert images[0].content_id == "123"
    assert images[0].image_url.endswith("full.jpg")
    assert images[0].thumbnail_url.endswith("thumb.jpg")
    assert images[0].attribution == "Photo: photographer via Pixabay"
    assert calls[0]["params"]["q"] == "공주 풍경"
    assert calls[0]["params"]["safesearch"] == "true"
    assert calls[0]["params"]["image_type"] == "photo"


def test_http_error_does_not_include_api_key_in_error() -> None:
    secret = "must-not-appear-in-error"
    response = httpx.Response(
        401,
        request=httpx.Request("GET", f"https://pixabay.com/api/?key={secret}"),
    )

    class ErrorResponse:
        def raise_for_status(self) -> None:
            response.raise_for_status()

        def json(self) -> dict[str, Any]:
            raise AssertionError("unreachable")

    client = PixabayClient(
        settings_obj=make_settings(pixabay_api_key=secret),
        http_get=lambda url, **kwargs: ErrorResponse(),
    )

    with pytest.raises(PixabayConfigurationError) as error:
        client.search_images(query="공주", rows=3)

    assert secret not in str(error.value)
