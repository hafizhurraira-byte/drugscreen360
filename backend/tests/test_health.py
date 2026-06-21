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


def test_release_health_endpoint_works():
    response = client.get("/api/system/release-health")
    assert response.status_code == 200
    body = response.json()
    assert body["app_name"] == "DrugScreen360"
    assert body["mvp_status"] == "local_mvp_release_candidate"
    assert body["backend_ok"] is True
    assert body["demo_available"] is True
    assert body["report_generation_available"] is True
    assert body["research_export_available"] is True


def test_release_health_includes_scientific_notice():
    body = client.get("/api/system/release-health").json()
    assert "computational decision-support only" in body["scientific_notice"].lower()
    assert "does not prove safety" in body["scientific_notice"].lower()
    assert "qualified scientific review" in body["scientific_notice"].lower()


def test_release_health_lists_available_and_unavailable_features():
    body = client.get("/api/system/release-health").json()
    assert "guided_demo_workflow" in body["enabled_features"]
    assert "final_end_to_end_project_report" in body["enabled_features"]
    assert "research_export_package" in body["enabled_features"]
    assert "validated_clinical_prediction" in body["unavailable_features"]
