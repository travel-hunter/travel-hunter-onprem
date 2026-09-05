from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_lists_grouped_jeju_catalog() -> None:
    response = client.get("/api/travel-areas?sido=제주")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sido"] == "제주"
    assert payload["sourceAsOf"] == "2026-09-03"
    assert payload["wholeArea"]["areaType"] == "whole"
    assert payload["wholeArea"]["travelAreaName"] == "제주 전체"
    assert {item["travelAreaId"] for item in payload["recommendedAreas"]} >= {"jeju-east", "jeju-west"}
    assert [item["travelAreaName"] for item in payload["administrativeAreas"]] == ["제주시", "서귀포시"]


def test_rejects_unsupported_sido() -> None:
    response = client.get("/api/travel-areas?sido=없는지역")

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported travel area sido"


def test_rejects_missing_sido() -> None:
    response = client.get("/api/travel-areas")

    assert response.status_code == 422


def test_groups_large_sido_administrative_areas() -> None:
    response = client.get("/api/travel-areas?sido=경기")
    assert response.status_code == 200
    areas = response.json()["administrativeAreas"]
    groups = [area["group"] for area in areas]
    assert None not in groups
    assert groups[0] == "경기 북부"
    # 같은 권역이 이어져 나온다. 화면이 순서대로 접어 그린다.
    assert groups == sorted(groups, key=groups.index)


def test_leaves_small_sido_administrative_areas_flat() -> None:
    response = client.get("/api/travel-areas?sido=대전")
    assert response.status_code == 200
    areas = response.json()["administrativeAreas"]
    assert areas and all(area["group"] is None for area in areas)
