"""Korea Tourism Organization TourAPI client for region photo lookup.

Follows the ``kakao_local.py`` client pattern: module constants, a dedicated
configuration error, frozen dataclass DTOs, a Protocol interface, settings
validation that no-ops when disabled, and a factory that returns ``None`` when
disabled so callers can skip gracefully.

The current public-data gateway uses KorService2 and its ``*2`` paths. The
base URL remains configurable for future provider migrations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import unquote

import httpx

from app.core.config import Settings, settings


AREA_CODE_PATH = "/areaCode2"
AREA_BASED_LIST_PATH = "/areaBasedList2"
SEARCH_KEYWORD_PATH = "/searchKeyword2"
CONTENT_TYPE_TOURIST_SPOT = "12"
TOUR_API_DEFAULT_ROWS = 10
# arrange=Q: 대표이미지가 있는 항목을 조회순으로. 실키 확보 후 실효성 재확인 대상.
TOUR_API_DEFAULT_ARRANGE = "Q"


class TourApiConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class TourApiAreaCode:
    code: str
    name: str


@dataclass(frozen=True)
class TourApiSpot:
    content_id: str
    title: str
    first_image: str | None
    first_image2: str | None
    addr1: str | None
    area_code: str | None
    sigungu_code: str | None
    # 저작권 유형(cpyrhtDivCd: Type1 공공누리 제1유형 · Type3 제3유형 변경금지)과 관광지 분류(cat3).
    # 2026-10-01 개발서버 실측: 목록 응답에 늘 온다. 사진 수집 기준(photo_criteria.py)이 쓴다.
    copyright_type: str | None = None
    category_code: str | None = None


class TourApiPhotoProvider(Protocol):
    def list_area_codes(
        self, *, area_code: str | None = None
    ) -> list[TourApiAreaCode]:
        ...

    def list_area_spots(
        self,
        *,
        area_code: str,
        sigungu_code: str | None = None,
        rows: int = TOUR_API_DEFAULT_ROWS,
    ) -> list[TourApiSpot]:
        ...

    def search_spots_by_keyword(
        self, *, keyword: str, rows: int = TOUR_API_DEFAULT_ROWS
    ) -> list[TourApiSpot]:
        ...


def validate_tour_api_settings(settings_obj: Settings = settings) -> None:
    if not settings_obj.tour_api_enabled:
        return
    if not settings_obj.tour_api_service_key:
        raise TourApiConfigurationError(
            "TOUR_API_SERVICE_KEY is required when TOUR_API_ENABLED=true."
        )
    if not settings_obj.tour_api_base_url:
        raise TourApiConfigurationError(
            "TOUR_API_BASE_URL is required when TOUR_API_ENABLED=true."
        )
    if settings_obj.tour_api_timeout_seconds <= 0:
        raise TourApiConfigurationError(
            "TOUR_API_TIMEOUT_SECONDS must be greater than 0."
        )


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _items_from_payload(payload: object) -> list[dict[str, Any]]:
    """TourAPI nests items at response.body.items.item.

    ``item`` can be a list, a single dict, or an empty string when there are
    no results. Anything unexpected parses to an empty list instead of
    raising.
    """

    if not isinstance(payload, dict):
        return []
    body = payload.get("response", {})
    if not isinstance(body, dict):
        return []
    body = body.get("body", {})
    if not isinstance(body, dict):
        return []
    items = body.get("items")
    if not isinstance(items, dict):
        return []
    item = items.get("item")
    if isinstance(item, list):
        return [entry for entry in item if isinstance(entry, dict)]
    if isinstance(item, dict):
        return [item]
    return []


def _to_area_code(entry: dict[str, Any]) -> TourApiAreaCode:
    code = _string_or_none(entry.get("code"))
    name = _string_or_none(entry.get("name"))
    if not code or not name:
        raise ValueError("TourAPI area code entry is missing code or name.")
    return TourApiAreaCode(code=code, name=name)


def _to_spot(entry: dict[str, Any]) -> TourApiSpot:
    content_id = _string_or_none(entry.get("contentid"))
    if not content_id:
        raise ValueError("TourAPI spot entry is missing contentid.")
    return TourApiSpot(
        content_id=content_id,
        title=_string_or_none(entry.get("title")) or "",
        first_image=_string_or_none(entry.get("firstimage")),
        first_image2=_string_or_none(entry.get("firstimage2")),
        addr1=_string_or_none(entry.get("addr1")),
        area_code=_string_or_none(entry.get("areacode")),
        sigungu_code=_string_or_none(entry.get("sigungucode")),
        copyright_type=_string_or_none(entry.get("cpyrhtDivCd")),
        category_code=_string_or_none(entry.get("cat3")),
    )


class TourApiClient:
    def __init__(
        self,
        *,
        settings_obj: Settings = settings,
        http_get: callable = httpx.get,
    ) -> None:
        validate_tour_api_settings(settings_obj)
        self._settings = settings_obj
        self._http_get = http_get

    def _request_items(
        self, path: str, params: dict[str, object]
    ) -> list[dict[str, Any]]:
        # data.go.kr presents both encoded and decoded service keys. httpx
        # encodes query values itself, so normalize an encoded copy once.
        key = unquote(self._settings.tour_api_service_key.strip())
        if not key:
            raise TourApiConfigurationError("TOUR_API_SERVICE_KEY is required.")
        base_url = self._settings.tour_api_base_url.rstrip("/")
        request_params: dict[str, object] = {
            "serviceKey": key,
            "MobileOS": "ETC",
            "MobileApp": "travel-hunter",
            "_type": "json",
            **params,
        }
        try:
            response = self._http_get(
                f"{base_url}{path}",
                params=request_params,
                timeout=self._settings.tour_api_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            # str(exc) contains the request URL, including serviceKey.
            raise TourApiConfigurationError(
                f"TourAPI request failed (HTTP {exc.response.status_code})."
            ) from None
        except httpx.HTTPError:
            raise TourApiConfigurationError("TourAPI request failed.") from None
        except ValueError:
            # JSON이 아닌 응답(키 오류 시 XML 등)도 설정 문제로 승격한다.
            raise TourApiConfigurationError(
                "TourAPI returned a non-JSON response."
            ) from None
        return _items_from_payload(payload)

    def list_area_codes(
        self, *, area_code: str | None = None
    ) -> list[TourApiAreaCode]:
        params: dict[str, object] = {"numOfRows": 100, "pageNo": 1}
        if area_code:
            params["areaCode"] = area_code
        codes: list[TourApiAreaCode] = []
        for entry in self._request_items(AREA_CODE_PATH, params):
            try:
                codes.append(_to_area_code(entry))
            except ValueError:
                continue
        return codes

    def list_area_spots(
        self,
        *,
        area_code: str,
        sigungu_code: str | None = None,
        rows: int = TOUR_API_DEFAULT_ROWS,
    ) -> list[TourApiSpot]:
        params: dict[str, object] = {
            "contentTypeId": CONTENT_TYPE_TOURIST_SPOT,
            "areaCode": area_code,
            "numOfRows": rows,
            "pageNo": 1,
            "arrange": TOUR_API_DEFAULT_ARRANGE,
        }
        if sigungu_code:
            params["sigunguCode"] = sigungu_code
        return self._parse_spots(self._request_items(AREA_BASED_LIST_PATH, params))

    def search_spots_by_keyword(
        self, *, keyword: str, rows: int = TOUR_API_DEFAULT_ROWS
    ) -> list[TourApiSpot]:
        params: dict[str, object] = {
            "keyword": keyword.strip(),
            "contentTypeId": CONTENT_TYPE_TOURIST_SPOT,
            "numOfRows": rows,
            "pageNo": 1,
            "arrange": TOUR_API_DEFAULT_ARRANGE,
        }
        return self._parse_spots(self._request_items(SEARCH_KEYWORD_PATH, params))

    @staticmethod
    def _parse_spots(entries: list[dict[str, Any]]) -> list[TourApiSpot]:
        spots: list[TourApiSpot] = []
        for entry in entries:
            try:
                spots.append(_to_spot(entry))
            except ValueError:
                continue
        return spots


def build_tour_api_client(
    settings_obj: Settings = settings,
) -> TourApiPhotoProvider | None:
    if not settings_obj.tour_api_enabled:
        return None
    return TourApiClient(settings_obj=settings_obj)
