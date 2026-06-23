import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace

from app.main import app
from app.database import init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    init_db()

def test_status_no_active_model(monkeypatch):
    def mock_get_info():
        return {"status": "unavailable", "model_id": None}
    monkeypatch.setattr("app.routers.admet_model_evidence.get_active_trained_model_info", mock_get_info)

    response = client.get("/api/admet-model-evidence/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["active_model_id"] is None
    assert body["domain_available"] is False

def test_status_with_active_model(monkeypatch):
    def mock_get_info():
        return {
            "status": "available",
            "model_id": "model_abc_123",
            "model_name": "Test Model",
            "task_name": "hERG",
            "task_type": "binary_classification"
        }
    def mock_val(model_id):
        return {
            "id": 1,
            "model_id": model_id,
            "calibration_summary": {"is_calibrated": True}
        }
    monkeypatch.setattr("app.routers.admet_model_evidence.get_active_trained_model_info", mock_get_info)
    monkeypatch.setattr("app.routers.admet_model_evidence.get_latest_external_validation_by_model", mock_val)

    response = client.get("/api/admet-model-evidence/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "available"
    assert body["active_model_id"] == "model_abc_123"
    assert body["validation_status"] == "validated"
    assert body["calibration_status"] == "calibrated"

def test_resolve_no_active_model(monkeypatch):
    def mock_get_info():
        return {"status": "disabled", "model_id": None}
    monkeypatch.setattr("app.services.admet_model_evidence_resolver.get_active_trained_model_info", mock_get_info)

    payload = {
        "candidate_name": "Aspirin",
        "smiles": "CC(=O)Oc1ccccc1C(=O)O"
    }
    response = client.post("/api/admet-model-evidence/resolve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["model_available"] is False
    assert body["active_model_id"] is None
    assert "No active trained ADMET model" in body["resolution_reason"]

def test_resolve_with_active_model(monkeypatch):
    def mock_get_info():
        return {
            "status": "available",
            "model_id": "model_abc_123",
            "model_name": "Test Model",
            "task_name": "hERG",
            "task_type": "binary_classification"
        }
    def mock_predict(smiles, model_id):
        return {
            "prediction_value": 1.0,
            "prediction_label": "active",
            "prediction_score": 0.85,
            "domain_status": "inside_domain",
            "uncertainty_level": "low",
            "nearest_training_distance": 0.12,
            "limitations": []
        }
    def mock_val(model_id):
        return {
            "id": 1,
            "model_id": model_id,
            "calibration_summary": {"is_calibrated": True}
        }
    def mock_explain(request):
        return SimpleNamespace(
            important_features=[
                SimpleNamespace(feature="MW", value=0.45, interpretation="Molecular weight"),
                SimpleNamespace(feature="LogP", value=0.35, interpretation="LogP partition coefficient")
            ],
            evidence_strength="externally_supported"
        )

    monkeypatch.setattr("app.services.admet_model_evidence_resolver.get_active_trained_model_info", mock_get_info)
    monkeypatch.setattr("app.services.admet_model_evidence_resolver.predict_trained_model", mock_predict)
    monkeypatch.setattr("app.services.admet_model_evidence_resolver.get_latest_external_validation_by_model", mock_val)
    monkeypatch.setattr("app.services.admet_model_evidence_resolver.explain_prediction", mock_explain)

    payload = {
        "candidate_name": "Aspirin",
        "smiles": "CC(=O)Oc1ccccc1C(=O)O",
        "requested_tasks": ["hERG"]
    }
    response = client.post("/api/admet-model-evidence/resolve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["model_available"] is True
    assert body["active_model_id"] == "model_abc_123"
    assert body["prediction_label"] == "active"
    assert body["confidence_level"] == "High"
    assert body["uncertainty_score"] == 0.1
    assert body["evidence_strength"] == "strong_model_evidence"
    assert body["external_validation_status"] == "validated"
    assert body["calibration_status"] == "calibrated"

def test_resolve_incompatible_task(monkeypatch):
    def mock_get_info():
        return {
            "status": "available",
            "model_id": "model_abc_123",
            "model_name": "Test Model",
            "task_name": "hERG",
            "task_type": "binary_classification"
        }
    monkeypatch.setattr("app.services.admet_model_evidence_resolver.get_active_trained_model_info", mock_get_info)

    payload = {
        "candidate_name": "Aspirin",
        "smiles": "CC(=O)Oc1ccccc1C(=O)O",
        "requested_tasks": ["Solubility"]
    }
    response = client.post("/api/admet-model-evidence/resolve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["model_available"] is False
    assert "not compatible" in body["resolution_reason"]
    assert body["failure_reason"] == "no_compatible_model_for_task"

def test_batch_resolve_and_project_runs(monkeypatch):
    def mock_get_info():
        return {
            "status": "available",
            "model_id": "model_abc_123",
            "model_name": "Test Model",
            "task_name": "hERG",
            "task_type": "binary_classification"
        }
    def mock_predict(smiles, model_id):
        return {
            "prediction_value": 0.0,
            "prediction_label": "inactive",
            "prediction_score": 0.15,
            "domain_status": "outside_domain",
            "uncertainty_level": "high",
            "nearest_training_distance": 0.85,
            "limitations": []
        }
    def mock_val(model_id):
        return None
    def mock_explain(request):
        return SimpleNamespace(
            important_features=[],
            evidence_strength="weak_internal"
        )

    monkeypatch.setattr("app.services.admet_model_evidence_resolver.get_active_trained_model_info", mock_get_info)
    monkeypatch.setattr("app.services.admet_model_evidence_resolver.predict_trained_model", mock_predict)
    monkeypatch.setattr("app.services.admet_model_evidence_resolver.get_latest_external_validation_by_model", mock_val)
    monkeypatch.setattr("app.services.admet_model_evidence_resolver.explain_prediction", mock_explain)

    payload = {
        "candidates": [
            {"compound_name": "Aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O"},
            {"compound_name": "Water", "smiles": "O"}
        ],
        "project_id": 999
    }
    response = client.post("/api/admet-model-evidence/batch-resolve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["candidate_count"] == 2
    assert body["evidence_available_count"] == 2
    assert body["outside_domain_count"] == 2
    assert body["high_uncertainty_count"] == 2
    assert body["project_id"] == 999

    # Now retrieve project runs
    proj_response = client.get("/api/admet-model-evidence/project/999")
    assert proj_response.status_code == 200
    runs = proj_response.json()
    assert len(runs) >= 1
    assert runs[0]["project_id"] == 999
    assert runs[0]["candidate_count"] == 2

def test_readiness_wizard(monkeypatch):
    response = client.get("/api/admet-model-evidence/readiness")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "next_action" in body
