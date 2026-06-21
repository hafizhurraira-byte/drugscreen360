import json
import zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.services import admet_training_service, research_export_service, admet_validation_service
import app.database

client = TestClient(fastapi_app)


@pytest.fixture(autouse=True)
def setup_validation_test(tmp_path, monkeypatch):
    # Isolated DB
    import app.database
    monkeypatch.setattr(app.database, "DB_PATH", tmp_path / "test_isolated_val.sqlite3")
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


def test_external_validation_failures():
    # 1. Validation refuses invalid model ID
    res = client.post(
        "/api/admet-validation/external/run",
        json={"model_id": "non_existent_model", "external_dataset_id": 1}
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]

    # Upload classification training dataset and train model
    ds_train = _upload("Train Clf", "AMES", rows=24, numeric=False)
    train_id = ds_train["dataset_id"]
    res_train = client.post(
        "/api/admet-training/train",
        json={"dataset_id": train_id, "task_type": "binary_classification", "model_type": "random_forest"}
    )
    assert res_train.status_code == 200
    model_id = res_train.json()["artifact"]["model_id"]

    # 2. Validation refuses incompatible dataset (numeric labels for classification model)
    ds_compat = _upload("Val Reg", "Solubility", rows=24, numeric=True)
    compat_id = ds_compat["dataset_id"]
    res_val = client.post(
        "/api/admet-validation/external/run",
        json={"model_id": model_id, "external_dataset_id": compat_id}
    )
    assert res_val.status_code == 422

    # 3. Validation refuses dataset with fewer than 10 records
    ds_small = _upload("Val Small", "AMES", rows=8, numeric=False)
    small_id = ds_small["dataset_id"]
    res_val2 = client.post(
        "/api/admet-validation/external/run",
        json={"model_id": model_id, "external_dataset_id": small_id}
    )
    assert res_val2.status_code == 422
    assert "at least 10 valid compatible records" in res_val2.json()["detail"]


def test_classification_and_regression_validation_works(tmp_path, monkeypatch):
    # --- Classification Validation ---
    ds_train_clf = _upload("Train Clf", "AMES", rows=24, numeric=False)
    res_train_clf = client.post(
        "/api/admet-training/train",
        json={"dataset_id": ds_train_clf["dataset_id"], "task_type": "binary_classification", "model_type": "random_forest"}
    )
    model_clf_id = res_train_clf.json()["artifact"]["model_id"]

    # Create project
    proj_res = client.post("/api/projects/create", json={
        "title": "Val Project Test",
        "project_type": "general_research",
        "status": "active"
    })
    project_id = proj_res.json()["id"]

    # Upload independent external validation dataset
    ds_val_clf = _upload("Val Clf", "AMES", rows=24, numeric=False)
    
    # Run validation
    res_val_clf = client.post(
        f"/api/admet-validation/external/run?project_id={project_id}",
        json={"model_id": model_clf_id, "external_dataset_id": ds_val_clf["dataset_id"], "notes": "Independent AMES test set"}
    )
    assert res_val_clf.status_code == 200
    val_clf = res_val_clf.json()
    assert val_clf["model_id"] == model_clf_id
    assert val_clf["task_type"] == "binary_classification"
    assert val_clf["status"] == "completed"
    assert val_clf["valid_count"] == 24
    assert "accuracy" in val_clf["metric_summary"]
    assert "f1" in val_clf["metric_summary"]
    assert "confusion_matrix" in val_clf["metric_summary"]
    assert "roc_auc" in val_clf["metric_summary"]
    assert val_clf["calibration_summary"]["calibration_status"] == "available"
    assert "expected_calibration_error" in val_clf["calibration_summary"]
    assert "brier_score" in val_clf["calibration_summary"]

    run_id = val_clf["id"]

    # Verify project item attached
    proj_detail = client.get(f"/api/projects/{project_id}").json()
    assert any(x["item_type"] == "admet_external_validation" for x in proj_detail["items"])

    # Test Metrics CSV endpoint
    res_csv = client.get(f"/api/admet-validation/external/runs/{run_id}/metrics.csv")
    assert res_csv.status_code == 200
    assert "accuracy," in res_csv.text
    assert "brier_score," in res_csv.text

    # Test Report JSON endpoint
    res_report = client.get(f"/api/admet-validation/external/runs/{run_id}/report.json")
    assert res_report.status_code == 200
    assert res_report.json()["id"] == run_id

    # Test Run Summary endpoint
    res_sum = client.get(f"/api/admet-validation/external/runs/{run_id}/summary")
    assert res_sum.status_code == 200

    # --- Regression Validation ---
    ds_train_reg = _upload("Train Reg", "Solubility", rows=24, numeric=True)
    res_train_reg = client.post(
        "/api/admet-training/train",
        json={"dataset_id": ds_train_reg["dataset_id"], "task_type": "regression", "model_type": "random_forest_regressor"}
    )
    model_reg_id = res_train_reg.json()["artifact"]["model_id"]

    ds_val_reg = _upload("Val Reg", "Solubility", rows=24, numeric=True)
    res_val_reg = client.post(
        "/api/admet-validation/external/run",
        json={"model_id": model_reg_id, "external_dataset_id": ds_val_reg["dataset_id"]}
    )
    assert res_val_reg.status_code == 200
    val_reg = res_val_reg.json()
    assert val_reg["task_type"] == "regression"
    assert "mae" in val_reg["metric_summary"]
    assert "rmse" in val_reg["metric_summary"]
    assert "r2" in val_reg["metric_summary"]
    assert "observed_vs_predicted" in val_reg["metric_summary"]
    assert "residual_summary" in val_reg["metric_summary"]
    assert val_reg["calibration_summary"]["calibration_status"] == "not applicable"


def test_research_export_includes_validation_files(tmp_path, monkeypatch):
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")

    # Train model
    ds_train = _upload("Train Export", "AMES", rows=24, numeric=False)
    res_train = client.post(
        "/api/admet-training/train",
        json={"dataset_id": ds_train["dataset_id"], "task_type": "binary_classification", "model_type": "random_forest"}
    )
    model_id = res_train.json()["artifact"]["model_id"]

    # Run validation
    ds_val = _upload("Val Export", "AMES", rows=24, numeric=False)
    client.post(
        "/api/admet-validation/external/run",
        json={"model_id": model_id, "external_dataset_id": ds_val["dataset_id"]}
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
    
    export_path = tmp_path / "research_exports" / body["filename"]
    assert export_path.exists()
    
    with zipfile.ZipFile(export_path, "r") as zf:
        names = zf.namelist()
        assert any("ADMET_EXTERNAL_VALIDATION/limitations.md" in name for name in names)
        assert any("ADMET_EXTERNAL_VALIDATION/runs/run_" in name for name in names)
        assert any("_report.json" in name for name in names)
        assert any("_metrics.csv" in name for name in names)
        assert any("_calibration_summary.json" in name for name in names)
        assert any("_internal_vs_external_comparison.json" in name for name in names)
