from fastapi.testclient import TestClient

from app.db import session as db_session
from app.main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_health_is_ok() -> None:
    client = _client()
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    root_res = client.get("/health")
    assert root_res.status_code == 200
    assert root_res.json() == {"status": "ok"}


def test_ready_ok_when_database_answers(monkeypatch) -> None:
    monkeypatch.setattr(db_session, "ping_database", lambda: None)
    client = _client()
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}
    root_ready = client.get("/ready")
    assert root_ready.status_code == 200
    assert root_ready.json() == {"status": "ready", "database": "ok"}


def test_ready_503_when_database_unreachable(monkeypatch) -> None:
    def boom() -> None:
        raise ConnectionError("db down")

    monkeypatch.setattr(db_session, "ping_database", boom)
    response = _client().get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unreachable"}


def test_openapi_docs_available() -> None:
    client = _client()
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    assert "/api/v1/health" in spec["paths"]
    assert "/api/v1/ready" in spec["paths"]
