from fastapi.testclient import TestClient

from src.main import app


def test_health_returns_200():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "hhh-audit-service"
    assert "cpu_percent" in body
    assert "ram_mb" in body
    assert "threads" in body
    assert "uptime_seconds" in body


def test_health_no_auth_required():
    client = TestClient(app)
    # no Authorization header
    response = client.get("/health")
    assert response.status_code == 200
