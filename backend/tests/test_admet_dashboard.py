import json
import joblib
import zipfile
from io import BytesIO
from pathlib import Path
import pytest
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from fastapi.testclient import TestClient

from app.main import app
from app.services import admet_training_service, research_export_service
from app.services.admet_trained_model_service import get_active_trained_model_info

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_dashboard_test(tmp_path, monkeypatch):
    # Isolated DB
    import app.database
    monkeypatch.setattr(app.database, "DB_PATH", tmp_path / "test_isolated_db.sqlite3")
    app.database.init_db()
    
    # Isolated trained model dirs
    monkeypatch.setattr(admet_training_service, "TRAINED_DIR", tmp_path / "trained")
    import app.services.admet_trained_model_service
    monkeypatch.setattr(app.services.admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")



def _csv(rows: int = 24, numeric: bool = False) -> bytes:
    lines = ["compound_name,smiles,label"]
    smiles = ["CCO", "CCN", "CCC", "CCCl", "c1ccccc1", "CC(=O)O"]
    for index in range(rows):
        label = str(float(index) / 10.0) if numeric else ("active" if index % 2 else "inactive")
        lines.append(f"Mol {index},{smiles[index % len(smiles)]},{label}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _upload(name: str, task: str, rows: int = 24, numeric: bool = False):
    return client.post(
        "/api/admet-datasets/upload",
        data={
            "dataset_name": name,
            "task_name": task,
            "label_column": "label",
            "smiles_column": "smiles",
            "compound_name_column": "compound_name",
        },
        files={"file": ("training.csv", _csv(rows, numeric), "text/csv")},
    ).json()


def test_dashboard_summary_empty():
    response = client.get("/api/admet-training/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["total_training_runs"] == 0
    assert body["total_trained_model_artifacts"] == 0
    assert len(body["scientific_limitations"]) > 0


def test_dashboard_and_comparison_runs():
    # 1. Train classification model
    ds_clf = _upload("Dataset Clf", "AMES", rows=24, numeric=False)
    clf_id = ds_clf["dataset_id"]
    res_clf = client.post(
        "/api/admet-training/train",
        json={"dataset_id": clf_id, "task_type": "binary_classification", "model_type": "random_forest"}
    )
    assert res_clf.status_code == 200
    run_clf_id = res_clf.json()["training_run_id"]
    
    # 2. Train regression model
    ds_reg = _upload("Dataset Reg", "Solubility", rows=24, numeric=True)
    reg_id = ds_reg["dataset_id"]
    res_reg = client.post(
        "/api/admet-training/train",
        json={"dataset_id": reg_id, "task_type": "regression", "model_type": "random_forest_regressor"}
    )
    assert res_reg.status_code == 200
    run_reg_id = res_reg.json()["training_run_id"]
    
    # 3. Test Dashboard Summary
    response = client.get("/api/admet-training/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["total_training_runs"] >= 2
    assert body["total_trained_model_artifacts"] >= 2
    assert body["latest_training_run_summary"] is not None
    assert body["best_classification_model"] is not None
    assert body["best_regression_model"] is not None
    
    # 4. Test Run Dashboard Detail
    detail_res = client.get(f"/api/admet-training/runs/{run_clf_id}/dashboard")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["training_run_id"] == run_clf_id
    assert detail["task_type"] == "binary_classification"
    assert "confusion_matrix" in detail
    assert detail["roc_auc_availability"] == "available"
    assert detail["activation_readiness"] is True
    
    # 5. Test Invalid Run ID
    detail_invalid = client.get("/api/admet-training/runs/999999/dashboard")
    assert detail_invalid.status_code == 404
    
    # 6. Test Model Comparison
    comp_res = client.get("/api/admet-training/model-comparison")
    assert comp_res.status_code == 200
    comparison = comp_res.json()
    assert len(comparison) >= 2
    
    # Find matching classification run row
    item_clf = next((x for x in comparison if x["training_run_id"] == run_clf_id), None)
    assert item_clf is not None
    assert item_clf["accuracy"] != "not available"
    assert item_clf["mae"] == "not available"
    
    # Find matching regression run row
    item_reg = next((x for x in comparison if x["training_run_id"] == run_reg_id), None)
    assert item_reg is not None
    assert item_reg["r2"] != "not available"
    assert item_reg["f1"] == "not available"
    
    # 7. Test Model Comparison CSV
    csv_res = client.get("/api/admet-training/model-comparison.csv")
    assert csv_res.status_code == 200
    csv_text = csv_res.text
    assert "model_id,training_run_id" in csv_text
    assert "accuracy" in csv_text
    assert "mae" in csv_text
    
    # 8. Test Visual plots data
    plots_res = client.get(f"/api/admet-training/runs/{run_clf_id}/plots-data")
    assert plots_res.status_code == 200
    plots = plots_res.json()
    assert "label_distribution" in plots
    assert plots["confusion_matrix_data"] is not None
    assert isinstance(plots["feature_importance"], dict)
    assert "molecular_weight" in plots["feature_importance"]
    assert isinstance(plots["prediction_probability_distribution"], list)
    assert len(plots["prediction_probability_distribution"]) > 0


def test_dashboard_project_attach():
    # Create project
    proj_res = client.post("/api/projects/create", json={
        "title": "Dashboard Project Test",
        "disease_area": "Oncology",
        "target_name": "EGFR",
        "project_type": "general_research",
        "status": "active"
    })
    assert proj_res.status_code == 200
    project_id = proj_res.json()["id"]
    
    # Attach summary snapshot
    attach_res = client.post("/api/admet-training/dashboard/attach", json={
        "project_id": project_id
    })
    assert attach_res.status_code == 200
    assert attach_res.json()["status"] == "success"
    
    # Verify attached item
    detail_res = client.get(f"/api/projects/{project_id}")
    assert detail_res.status_code == 200
    items = detail_res.json()["items"]
    assert any(x["item_type"] == "admet_model_dashboard" for x in items)


def test_research_export_includes_dashboard_files(tmp_path, monkeypatch):
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")
    
    # Train classifier model
    ds = _upload("Dataset Export", "AMES", rows=24, numeric=False)
    client.post(
        "/api/admet-training/train",
        json={"dataset_id": ds["dataset_id"], "task_type": "binary_classification", "model_type": "random_forest"}
    )
    
    # Run export
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
    
    export_path = tmp_path / "research_exports" / body["filename"]
    assert export_path.exists()
    
    # Read zip and check dashboard files
    with zipfile.ZipFile(export_path, "r") as zf:
        names = zf.namelist()
        
        # Look for dashboard_summary.json, model_comparison.csv, limitations.md
        assert any("ADMET_MODEL_DASHBOARD/dashboard_summary.json" in name for name in names)
        assert any("ADMET_MODEL_DASHBOARD/model_comparison.csv" in name for name in names)
        assert any("ADMET_MODEL_DASHBOARD/limitations.md" in name for name in names)
        assert any("ADMET_MODEL_DASHBOARD/training_run_dashboards/run_" in name for name in names)
