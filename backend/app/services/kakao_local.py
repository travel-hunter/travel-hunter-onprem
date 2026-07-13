from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings, settings


KAKAO_LOCAL_KEYWORD_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_LOCAL_DEFAULT_SIZE = 15
KAKAO_LOCAL_DEFAULT_SORT = "accuracy"


class KakaoLocalConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class KakaoLocalPlace:
    external_place_id: str
    name: str
    category_name: str | None
    category_group_code: str | None
    category_group_name: str | None
    phone: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    place_url: str | None


class KakaoLocalSearchProvider(Protocol):
    def search_keyword(
        self,
        *,
        query: str,
        category_group_code: str | None = None,
        page: int = 1,
        size: int = KAKAO_LOCAL_DEFAULT_SIZE,
        sort: str = KAKAO_LOCAL_DEFAULT_SORT,
    ) -> list[KakaoLocalPlace]:
        ...


def validate_kakao_local_settings(settings_obj: Settings = settings) -> None:
    if not settings_obj.kakao_local_enabled:
        return
    if not settings_obj.kakao_local_rest_api_key:
        raise KakaoLocalConfigurationError(
            "KAKAO_LOCAL_REST_API_KEY is required when KAKAO_LOCAL_ENABLED=true."
        )
    if settings_obj.kakao_local_timeout_seconds <= 0:
        raise KakaoLocalConfigurationError(
            "KAKAO_LOCAL_TIMEOUT_SECONDS must be greater than 0."
        )


def parse_float_or_none(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_place_payload(document: dict[str, Any]) -> KakaoLocalPlace:
    external_id = str(document.get("id", "")).strip()
    if not external_id:
        raise ValueError("Kakao Local document is missing id.")

    return KakaoLocalPlace(
        external_place_id=external_id,
        name=str(document.get("place_name", "")).strip(),
        category_name=(document.get("category_name") or None) or None,
        category_group_code=(document.get("category_group_code") or None) or None,
        category_group_name=(document.get("category_group_name") or None) or None,
        phone=(document.get("phone") or None) or None,
        address=(document.get("address_name") or document.get("road_address_name") or None)
        if document.get("address_name") or document.get("road_address_name")
        else None,
        latitude=parse_float_or_none(document.get("y")),
        longitude=parse_float_or_none(document.get("x")),
        place_url=(document.get("place_url") or None) if isinstance(document, dict) else None,
    )


class KakaoLocalClient:
    def __init__(
        self,
        *,
        settings_obj: Settings = settings,
        http_get: callable = httpx.get,
    ) -> None:
        validate_kakao_local_settings(settings_obj)
        self._settings = settings_obj
        self._http_get = http_get

    def search_keyword(
        self,
        *,
        query: str,
        category_group_code: str | None = None,
        page: int = 1,
        size: int = KAKAO_LOCAL_DEFAULT_SIZE,
        sort: str = KAKAO_LOCAL_DEFAULT_SORT,
    ) -> list[KakaoLocalPlace]:
        key = self._settings.kakao_local_rest_api_key.strip()
        if not key:
            raise KakaoLocalConfigurationError(
                "KAKAO_LOCAL_REST_API_KEY is required."
            )
        params = {
            "query": query.strip(),
            "page": page,
            "size": size,
            "sort": sort,
        }
        if category_group_code:
            params["category_group_code"] = category_group_code

        try:
            response = self._http_get(
                KAKAO_LOCAL_KEYWORD_SEARCH_URL,
                headers={"Authorization": f"KakaoAK {key}"},
                params=params,
                timeout=self._settings.kakao_local_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise KakaoLocalConfigurationError(str(exc))

        documents = payload.get("documents", []) if isinstance(payload, dict) else []
        if not isinstance(documents, list):
            return []
        places: list[KakaoLocalPlace] = []
        for document in documents:
            if not isinstance(document, dict):
                continue
            try:
                places.append(_to_place_payload(document))
            except ValueError:
                continue
        return places


def build_kakao_local_client(
    settings_obj: Settings = settings,
) -> KakaoLocalSearchProvider | None:
    if not settings_obj.kakao_local_enabled:
        return None
    return KakaoLocalClient(settings_obj=settings_obj)
