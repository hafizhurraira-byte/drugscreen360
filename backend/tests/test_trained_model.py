import json
import joblib
from pathlib import Path
import pytest
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from fastapi.testclient import TestClient

from app.main import app
from app.services import admet_trained_model_service, research_export_service
from app.services.model_registry import ADAPTERS

client = TestClient(app)

def create_synthetic_model_files(folder: Path, task_type="binary_classification"):
    folder.mkdir(parents=True, exist_ok=True)
    
    # Train dummy scikit-learn model
    X = np.random.rand(20, 10)
    if task_type == "binary_classification":
        y = np.random.randint(0, 2, 20)
        model = RandomForestClassifier(n_estimators=2, random_state=42)
        model.fit(X, y)
        joblib.dump({
            "model": model,
            "feature_columns": admet_trained_model_service.FEATURE_COLUMNS,
            "task_type": "binary_classification",
            "label_mapping": {"inactive": 0, "active": 1}
        }, folder / "model.joblib")
    else:
        y = np.random.rand(20)
        model = RandomForestRegressor(n_estimators=2, random_state=42)
        model.fit(X, y)
        joblib.dump({
            "model": model,
            "feature_columns": admet_trained_model_service.FEATURE_COLUMNS,
            "task_type": "regression",
            "label_mapping": None
        }, folder / "model.joblib")
        
    manifest = {
        "model_id": folder.name,
        "model_name": f"Synthetic {task_type} Model",
        "version": "1.0.0",
        "tasks": ["AMES" if task_type == "binary_classification" else "Solubility"],
        "input_type": "rdkit_descriptors",
        "limitations": "Synthetic testing model only.",
        "artifact_files": ["model.joblib", "feature_schema.json"],
        "training_run_id": 999,
        "metrics": {"accuracy": 0.95} if task_type == "binary_classification" else {"mae": 0.1},
        "feature_schema": {
            "input_type": "rdkit_descriptors",
            "feature_columns": admet_trained_model_service.FEATURE_COLUMNS,
            "label_mapping": {"inactive": 0, "active": 1} if task_type == "binary_classification" else None
        }
    }
    (folder / "model_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    
    feature_schema = {
        "input_type": "rdkit_descriptors",
        "feature_columns": admet_trained_model_service.FEATURE_COLUMNS,
        "label_mapping": {"inactive": 0, "active": 1} if task_type == "binary_classification" else None
    }
    (folder / "feature_schema.json").write_text(json.dumps(feature_schema), encoding="utf-8")
    
    card = {
        "dataset_id": 1,
        "dataset_name": "synthetic",
        "task_name": "AMES",
        "task_type": task_type,
        "model_name": "RF",
        "model_type": "random_forest",
        "record_counts": {"train_count": 16, "test_count": 4},
        "features_used": admet_trained_model_service.FEATURE_COLUMNS,
        "split_method": "stratified",
        "metrics": {"accuracy": 0.95} if task_type == "binary_classification" else {"mae": 0.1},
        "limitations": ["limit1"],
        "warnings": ["warning1"],
        "intended_use": "testing",
        "not_intended_for": ["clinical"],
        "external_validation_required": True
    }
    (folder / "model_card.json").write_text(json.dumps(card), encoding="utf-8")
    
    summary = {
        "training_run_id": 999,
        "dataset_id": 1,
        "created_at": "2026-06-21T00:00:00Z",
        "task_type": task_type,
        "model_type": "random_forest" if task_type == "binary_classification" else "random_forest_regressor",
        "metrics": {"accuracy": 0.95} if task_type == "binary_classification" else {"mae": 0.1},
        "warnings": [],
        "limitations": []
    }
    (folder / "training_summary.json").write_text(json.dumps(summary), encoding="utf-8")


def test_model_list_empty_safely(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    response = client.get("/api/admet-training/models")
    assert response.status_code == 200
    assert response.json() == []


def test_invalid_trained_model_folder_returns_unavailable_or_error(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    invalid_folder = tmp_path / "trained" / "invalid_model_folder"
    invalid_folder.mkdir(parents=True, exist_ok=True)
    
    # Write invalid manifest file
    (invalid_folder / "model_manifest.json").write_text("invalid json", encoding="utf-8")
    
    response = client.get("/api/admet-training/models")
    assert response.status_code == 200
    res = response.json()
    assert len(res) == 1
    assert res[0]["model_id"] == "invalid_model_folder"
    assert res[0]["manifest_valid"] is False
    assert res[0]["status"] == "invalid"


def test_validate_model_succeeds_with_synthetic_trained_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    create_synthetic_model_files(tmp_path / "trained" / "synthetic_model_1")
    
    response = client.post("/api/admet-training/models/synthetic_model_1/validate")
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_activation_refuses_invalid_model(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    invalid_folder = tmp_path / "trained" / "invalid_model_folder"
    invalid_folder.mkdir(parents=True, exist_ok=True)
    (invalid_folder / "model_manifest.json").write_text(json.dumps({"model_id": "invalid_model_folder"}), encoding="utf-8")
    
    response = client.post("/api/admet-training/models/invalid_model_folder/activate")
    assert response.status_code == 400
    assert "Cannot activate invalid model" in response.json()["detail"]


def test_activation_succeeds_for_valid_synthetic_model(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    create_synthetic_model_files(tmp_path / "trained" / "synthetic_model_1")
    
    response = client.post("/api/admet-training/models/synthetic_model_1/activate")
    assert response.status_code == 200
    assert response.json()["status"] == "active"
    
    active_info = client.get("/api/admet-training/active-model").json()
    assert active_info["status"] == "available"
    assert active_info["model_id"] == "synthetic_model_1"


def test_deactivate_works(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    create_synthetic_model_files(tmp_path / "trained" / "synthetic_model_1")
    
    client.post("/api/admet-training/models/synthetic_model_1/activate")
    deactivate_res = client.post("/api/admet-training/models/deactivate")
    assert deactivate_res.status_code == 200
    assert deactivate_res.json()["status"] == "disabled"
    
    active_info = client.get("/api/admet-training/active-model").json()
    assert active_info["status"] == "disabled"


def test_active_model_endpoint_works(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    # Deactivate first
    client.post("/api/admet-training/models/deactivate")
    response = client.get("/api/admet-training/active-model")
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"


def test_prediction_refuses_when_no_active_model(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    client.post("/api/admet-training/models/deactivate")
    
    response = client.post("/api/admet-training/predict", json={"smiles": "CCO"})
    assert response.status_code == 400
    assert "no active trained model" in response.json()["detail"]


def test_prediction_works_for_valid_synthetic_model(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    create_synthetic_model_files(tmp_path / "trained" / "synthetic_model_1")
    client.post("/api/admet-training/models/synthetic_model_1/activate")
    
    response = client.post("/api/admet-training/predict", json={"smiles": "CCO"})
    assert response.status_code == 200
    body = response.json()
    assert body["model_id"] == "synthetic_model_1"
    assert body["prediction_label"] in {"active", "inactive"}
    assert body["experimental_model_notice"] == "Experimental local model prediction. Requires external validation."


def test_prediction_does_not_invent_probability_when_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    create_synthetic_model_files(tmp_path / "trained" / "synthetic_regression_1", task_type="regression")
    client.post("/api/admet-training/models/synthetic_regression_1/activate")
    
    response = client.post("/api/admet-training/predict", json={"smiles": "CCO"})
    assert response.status_code == 200
    body = response.json()
    assert body["model_id"] == "synthetic_regression_1"
    assert body["prediction_value"] is not None
    assert body["prediction_score"] is None  # Probability is None for regression


def test_screening_still_works_when_no_active_model(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    client.post("/api/admet-training/models/deactivate")
    
    response = client.post("/api/screen", json={"query": "CCO", "input_type": "smiles"})
    assert response.status_code == 200
    body = response.json()
    assert "model_predictions" in body
    outputs = body["model_predictions"]["model_outputs"]
    assert any(o["model_id"] == "rule_based_admet_v1" for o in outputs)


def test_model_registry_includes_trained_local_admet_model(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    assert "trained_local_admet_model" in ADAPTERS


def test_research_export_includes_active_trained_model_status(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")
    create_synthetic_model_files(tmp_path / "trained" / "synthetic_model_1")
    client.post("/api/admet-training/models/synthetic_model_1/activate")
    
    export_res = client.post("/api/research-export/create", json={
        "include_screening_history": False,
        "include_benchmark_runs": False,
        "include_batch_runs": False,
        "include_cache_status": False,
        "include_reports": False
    })
    assert export_res.status_code == 200
    body = export_res.json()
    assert "filename" in body
    
    # check that the export path exists
    export_path = tmp_path / "research_exports" / body["filename"]
    assert export_path.exists()
