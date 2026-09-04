from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote

from app.data.administrative_areas import ADMINISTRATIVE_AREAS_BY_SIDO, ADMINISTRATIVE_AREAS_SOURCE_AS_OF
from app.data.travel_areas import TravelArea, get_travel_area, list_travel_areas

AreaType = Literal["whole", "recommended", "administrative", "policy"]

SUPPORTED_SIDOS = (
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "경기",
    "강원",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "제주",
)


@dataclass(frozen=True)
class TravelAreaOption:
    id: str
    name: str
    sido: str
    area_type: AreaType
    included_cities: tuple[str, ...]


@dataclass(frozen=True)
class TravelAreaCatalog:
    sido: str
    source_as_of: str
    whole_area: TravelAreaOption
    recommended_areas: tuple[TravelAreaOption, ...]
    administrative_areas: tuple[TravelAreaOption, ...]


def make_whole_area_id(sido: str) -> str:
    return f"whole:{quote(sido.strip(), safe='')}"


def make_administrative_area_id(sido: str, locality: str) -> str:
    return f"admin:{quote(sido.strip(), safe='')}:{quote(locality.strip(), safe='')}"


def list_supported_sidos() -> tuple[str, ...]:
    return SUPPORTED_SIDOS


def list_travel_area_catalog(sido: str) -> TravelAreaCatalog:
    normalized_sido = sido.strip()
    if normalized_sido not in ADMINISTRATIVE_AREAS_BY_SIDO:
        raise ValueError("Unsupported travel area sido")

    recommended_areas = tuple(
        _recommended_option(area)
        for area in list_travel_areas()
        if area.sido == normalized_sido and not _is_legacy_whole_area(area)
    )
    administrative_areas = tuple(
        _administrative_option(normalized_sido, locality)
        for locality in ADMINISTRATIVE_AREAS_BY_SIDO[normalized_sido]
    )
    return TravelAreaCatalog(
        sido=normalized_sido,
        source_as_of=ADMINISTRATIVE_AREAS_SOURCE_AS_OF,
        whole_area=_whole_option(normalized_sido),
        recommended_areas=recommended_areas,
        administrative_areas=administrative_areas,
    )


def resolve_travel_area(area_id: str | None) -> TravelArea | None:
    return get_travel_area(area_id)


def _whole_option(sido: str) -> TravelAreaOption:
    return TravelAreaOption(
        id=make_whole_area_id(sido),
        name=f"{sido} 전체",
        sido=sido,
        area_type="whole",
        included_cities=(sido,),
    )


def _recommended_option(area: TravelArea) -> TravelAreaOption:
    return TravelAreaOption(
        id=area.id,
        name=area.name,
        sido=area.sido,
        area_type="recommended",
        included_cities=area.included_cities,
    )


def _administrative_option(sido: str, locality: str) -> TravelAreaOption:
    return TravelAreaOption(
        id=make_administrative_area_id(sido, locality),
        name=locality,
        sido=sido,
        area_type="administrative",
        included_cities=(_normalize_included_city(locality),),
    )


def _normalize_included_city(locality: str) -> str:
    for suffix in ("시", "군"):
        if locality.endswith(suffix):
            return locality.removesuffix(suffix)
    return locality


def _is_legacy_whole_area(area: TravelArea) -> bool:
    return area.id.endswith("-all") and area.name == f"{area.sido} 전체"
