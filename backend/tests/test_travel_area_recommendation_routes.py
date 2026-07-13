from fastapi.testclient import TestClient

from app.api.routes import recommendations as recommendation_routes
from app.main import app
from app.schemas.recommendations import TravelAreaRecommendationResponse


client = TestClient(app)


def clear_overrides() -> None:
    app.dependency_overrides.pop(recommendation_routes.get_optional_db, None)


def test_travel_area_route_passes_query_options(monkeypatch) -> None:
    fake_db = object()
    captured = {}
    app.dependency_overrides[recommendation_routes.get_optional_db] = lambda: fake_db

    def fake_recommend_travel_areas(
        db,
        *,
        sido=None,
        query=None,
        mode=None,
        style=None,
        limit=6,
    ):
        assert db is fake_db
        captured.update({"sido": sido, "query": query, "mode": mode, "style": style, "limit": limit})
        return TravelAreaRecommendationResponse(mode="search", sido=sido, query=query, emptyReason=None, items=[])

    monkeypatch.setattr(
        recommendation_routes.travel_area_service,
        "recommend_travel_areas",
        fake_recommend_travel_areas,
    )

    try:
        response = client.get("/api/recommendations/travel-areas?sido=강원&query=속초&mode=nationwide&style=바다&limit=2")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert captured == {"sido": "강원", "query": "속초", "mode": "nationwide", "style": "바다", "limit": 2}
    assert response.json() == {"mode": "search", "sido": "강원", "query": "속초", "items": [], "emptyReason": None}


def test_travel_area_route_rejects_invalid_limit() -> None:
    response = client.get("/api/recommendations/travel-areas?limit=0")

    assert response.status_code == 422
