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
