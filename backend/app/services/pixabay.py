"""Optional Pixabay image-search client for policy-photo fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings, settings


PIXABAY_API_URL = "https://pixabay.com/api/"


class PixabayConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PixabayImage:
    content_id: str
    image_url: str
    thumbnail_url: str | None
    alt_text: str
    attribution: str


class PixabayPhotoProvider(Protocol):
    def search_images(self, *, query: str, rows: int) -> list[PixabayImage]:
        ...


def validate_pixabay_settings(settings_obj: Settings = settings) -> None:
    if not settings_obj.pixabay_enabled:
        return
    if not settings_obj.pixabay_api_key:
        raise PixabayConfigurationError(
            "PIXABAY_API_KEY is required when PIXABAY_ENABLED=true."
        )
    if settings_obj.pixabay_timeout_seconds <= 0:
        raise PixabayConfigurationError(
            "PIXABAY_TIMEOUT_SECONDS must be greater than 0."
        )


class PixabayClient:
    def __init__(
        self,
        *,
        settings_obj: Settings = settings,
        http_get: callable = httpx.get,
    ) -> None:
        validate_pixabay_settings(settings_obj)
        self._settings = settings_obj
        self._http_get = http_get

    def search_images(self, *, query: str, rows: int) -> list[PixabayImage]:
        try:
            response = self._http_get(
                PIXABAY_API_URL,
                params={
                    "key": self._settings.pixabay_api_key,
                    "q": query.strip(),
                    "image_type": "photo",
                    "safesearch": "true",
                    "per_page": rows,
                },
                timeout=self._settings.pixabay_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise PixabayConfigurationError(
                f"Pixabay request failed (HTTP {exc.response.status_code})."
            ) from None
        except httpx.HTTPError:
            raise PixabayConfigurationError("Pixabay request failed.") from None
        except ValueError:
            raise PixabayConfigurationError(
                "Pixabay returned a non-JSON response."
            ) from None

        hits = payload.get("hits", []) if isinstance(payload, dict) else []
        if not isinstance(hits, list):
            return []
        images: list[PixabayImage] = []
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            content_id = hit.get("id")
            image_url = hit.get("largeImageURL") or hit.get("webformatURL")
            if content_id is None or not isinstance(image_url, str) or not image_url:
                continue
            thumbnail_url = hit.get("webformatURL")
            title = str(hit.get("tags") or "Pixabay image")
            photographer = str(hit.get("user") or "Pixabay contributor")
            images.append(
                PixabayImage(
                    content_id=str(content_id),
                    image_url=image_url,
                    thumbnail_url=thumbnail_url
                    if isinstance(thumbnail_url, str) and thumbnail_url
                    else None,
                    alt_text=title,
                    attribution=f"Photo: {photographer} via Pixabay",
                )
            )
        return images


def build_pixabay_client(
    settings_obj: Settings = settings,
) -> PixabayPhotoProvider | None:
    if not settings_obj.pixabay_enabled:
        return None
    return PixabayClient(settings_obj=settings_obj)
