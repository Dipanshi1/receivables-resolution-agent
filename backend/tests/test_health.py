"""Unit tests for the health check endpoint."""

from fastapi.testclient import TestClient


def test_v1_health_returns_ok(client: TestClient) -> None:
    """Verify GET /v1/health returns 200 with status ok."""
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_health_not_registered(client: TestClient) -> None:
    """Verify /health is not the primary endpoint and returns 404."""
    response = client.get("/health")
    assert response.status_code == 404
