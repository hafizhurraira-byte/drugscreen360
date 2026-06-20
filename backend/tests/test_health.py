from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_works():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app_name"] == "DrugScreen360"


def test_health_includes_version():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["version"] == "0.1.0-local-mvp"


def test_health_includes_model_registry_summary():
    response = client.get("/api/health")
    body = response.json()
    assert "model_registry" in body
    assert "rule_based_admet_v1" in body["model_registry"]["available_models"]
    assert "supported_tasks" in body["model_registry"]


def test_health_database_status_handled_safely():
    response = client.get("/api/health")
    body = response.json()
    assert body["database"]["status"] in {"ok", "error"}
    assert body["cache"]["status"] in {"ok", "error"}
