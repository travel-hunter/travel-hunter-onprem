from fastapi.testclient import TestClient

from app.api.routes import recommendations as recommendation_routes
from app.main import app
from app.schemas.recommendations import RegionRecommendation


client = TestClient(app)


def clear_overrides() -> None:
    app.dependency_overrides.pop(recommendation_routes.get_optional_db, None)


def test_region_recommendation_route_returns_public_recommendations(monkeypatch) -> None:
    fake_db = object()
    app.dependency_overrides[recommendation_routes.get_optional_db] = lambda: fake_db

    def fake_recommend_regions(db, *, today=None, style=None, region=None, preferred_regions=None, limit=3):
        assert db is fake_db
        assert style == "맛집"
        assert region == "부산"
        assert preferred_regions == ["부산", "강원"]
        assert limit == 2
        return [
            RegionRecommendation(
                region="부산",
                title="부산이 지금 좋아요",
                reason="신청 가능한 지역 혜택이 많습니다.",
                policyCount=4,
                endingSoonCount=2,
                estimatedValueKrw=100000,
                score=86,
                styleMatchedCount=1,
            )
        ]

    monkeypatch.setattr(
        recommendation_routes.region_recommendation_service,
        "recommend_regions",
        fake_recommend_regions,
    )

    try:
        response = client.get("/api/recommendations/regions?style=맛집&region=부산&preferredRegions=부산&preferredRegions=강원&limit=2")
    finally:
        clear_overrides()

    assert response.status_code == 200
    assert response.json() == [
        {
            "region": "부산",
            "title": "부산이 지금 좋아요",
            "reason": "신청 가능한 지역 혜택이 많습니다.",
            "policyCount": 4,
            "endingSoonCount": 2,
            "estimatedValueKrw": 100000,
            "score": 86,
            "styleMatchedCount": 1,
        }
    ]
