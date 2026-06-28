from fastapi.testclient import TestClient

from app.routers import health
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
    assert response.json()["version"] == "0.19.0"


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


def test_system_readiness_without_active_model(monkeypatch):
    monkeypatch.setattr(health, "get_active_trained_model_info", lambda: {"status": "unavailable"})
    monkeypatch.setattr(health, "discover_trained_models", lambda: [])
    body = client.get("/api/system/readiness").json()
    assert body["overall_status"] == "Not Ready"
    assert "Train and activate a compatible ADMET model" in body["recommended_next_actions"]
    assert "computational decision-support only" in body["scientific_notice"].lower()


def test_system_readiness_flags_stale_synthetic_model(monkeypatch):
    monkeypatch.setattr(
        health,
        "get_active_trained_model_info",
        lambda: {"status": "missing", "model_id": "synthetic_model_1", "warnings": ["Active model directory not found for model ID 'synthetic_model_1'."]},
    )
    monkeypatch.setattr(health, "discover_trained_models", lambda: [{"model_id": "real_model", "status": "valid"}])
    body = client.get("/api/system/readiness").json()
    assert body["overall_status"] == "Action Needed"
    assert body["active_model_id"] == "synthetic_model_1"
    assert body["artifact_status"] == "missing"
    assert "Reactivate a valid trained model" in body["recommended_next_actions"]


def test_system_readiness_with_external_validation(monkeypatch):
    monkeypatch.setattr(
        health,
        "get_active_trained_model_info",
        lambda: {"status": "available", "model_id": "real_model", "model_name": "Real RF", "task_name": "toxicity_concern", "version": "0.19.0-test"},
    )
    monkeypatch.setattr(health, "discover_trained_models", lambda: [{"model_id": "real_model", "status": "valid"}])
    monkeypatch.setattr(
        health,
        "get_latest_external_validation_by_model",
        lambda model_id: {"id": 42, "validation_evidence_status": "externally_validated", "calibration_evidence_status": "calibration_moderate", "warnings": []},
    )
    body = client.get("/api/system/readiness").json()
    assert body["overall_status"] == "Ready"
    assert body["latest_external_validation_run"]["id"] == 42
    assert body["calibration_status"] == "calibration_moderate"


