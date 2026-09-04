import pytest

from app.services.travel_area_catalog import (
    list_supported_sidos,
    list_travel_area_catalog,
    resolve_travel_area,
)


EXPECTED_SIDOS = (
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

EXPECTED_ADMINISTRATIVE_COUNTS = {
    "서울": 25,
    "부산": 16,
    "대구": 9,
    "인천": 10,
    "광주": 5,
    "대전": 5,
    "울산": 5,
    "세종": 0,
    "경기": 31,
    "강원": 18,
    "충북": 11,
    "충남": 15,
    "전북": 14,
    "전남": 22,
    "경북": 22,
    "경남": 18,
    "제주": 2,
}


def test_catalog_covers_all_sidos_with_one_whole_area() -> None:
    assert list_supported_sidos() == EXPECTED_SIDOS
    for sido in EXPECTED_SIDOS:
        catalog = list_travel_area_catalog(sido)
        assert catalog.whole_area.area_type == "whole"
        assert catalog.whole_area.sido == sido
        assert catalog.whole_area.name == f"{sido} 전체"


def test_catalog_exposes_previously_missing_localities() -> None:
    assert {item.name for item in list_travel_area_catalog("경기").administrative_areas} >= {"수원시", "용인시", "연천군"}
    assert {item.name for item in list_travel_area_catalog("강원").administrative_areas} >= {"춘천시", "태백시", "양구군"}
    assert {item.name for item in list_travel_area_catalog("전남").administrative_areas} >= {"목포시", "강진군", "신안군"}


def test_jeju_separates_curated_and_administrative_areas() -> None:
    catalog = list_travel_area_catalog("제주")
    assert {item.id for item in catalog.recommended_areas} >= {"jeju-east", "jeju-west"}
    assert [item.name for item in catalog.administrative_areas] == ["제주시", "서귀포시"]


def test_catalog_option_ids_are_unique() -> None:
    option_ids = [
        option.id
        for sido in EXPECTED_SIDOS
        for catalog in (list_travel_area_catalog(sido),)
        for option in (catalog.whole_area, *catalog.recommended_areas, *catalog.administrative_areas)
    ]

    assert len(option_ids) == len(set(option_ids))


def test_administrative_counts_match_snapshot_contract() -> None:
    counts = {
        sido: len(list_travel_area_catalog(sido).administrative_areas)
        for sido in EXPECTED_SIDOS
    }

    assert counts == EXPECTED_ADMINISTRATIVE_COUNTS
    assert list_travel_area_catalog("세종").administrative_areas == ()


@pytest.mark.parametrize(
    ("area_id", "name"),
    [
        ("whole:%EC%A0%9C%EC%A3%BC", "제주 전체"),
        ("admin:%EC%A0%9C%EC%A3%BC:%EC%84%9C%EA%B7%80%ED%8F%AC%EC%8B%9C", "서귀포시"),
        ("jeju-west", "제주 서부"),
        ("policy-region:%EC%A0%84%EB%82%A8:%EA%B0%95%EC%A7%84", "강진"),
    ],
)
def test_resolver_supports_every_id_family(area_id: str, name: str) -> None:
    area = resolve_travel_area(area_id)

    assert area is not None
    assert area.name == name


def test_resolver_rejects_unknown_whole_and_administrative_ids() -> None:
    assert resolve_travel_area("whole:%EC%97%86%EB%8A%94%EC%A7%80%EC%97%AD") is None
    assert resolve_travel_area("admin:%EC%A0%9C%EC%A3%BC:%EC%97%86%EB%8A%94%EC%8B%9C") is None
