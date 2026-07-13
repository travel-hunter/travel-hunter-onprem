from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_health() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["service"] == "travel-hunter-backend"
