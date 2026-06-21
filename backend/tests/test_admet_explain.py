import json
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services import admet_explain_service, admet_training_service, admet_trained_model_service, research_export_service

client = TestClient(app)


def _csv(rows: int = 32, numeric: bool = False) -> bytes:
    lines = ["compound_name,smiles,label"]
    smiles = [
        "CCO",
        "CCN",
        "CCC",
        "CCCl",
        "c1ccccc1",
        "CC(=O)O",
        "CC(C)O",
        "CCOC",
    ]
    for index in range(rows):
        label = str(float(index) / 10.0) if numeric else ("active" if index % 2 else "inactive")
        lines.append(f"Explain Mol {index},{smiles[index % len(smiles)]},{label}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _train_model(tmp_path, monkeypatch, model_type="random_forest"):
    monkeypatch.setattr(admet_training_service, "TRAINED_DIR", tmp_path / "trained")
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    monkeypatch.setattr(admet_explain_service, "EXPLANATION_REPORT_DIR", tmp_path / "admet_explanation_reports")
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")
    response = client.post(
        "/api/admet-datasets/upload",
        data={
            "dataset_name": f"explain {model_type} dataset",
            "task_name": "hERG",
            "label_column": "label",
            "smiles_column": "smiles",
            "compound_name_column": "compound_name",
        },
        files={"file": ("explain.csv", _csv(), "text/csv")},
    )
    assert response.status_code == 200
    dataset_id = response.json()["dataset_id"]
    train = client.post(
        "/api/admet-training/train",
        json={"dataset_id": dataset_id, "task_type": "binary_classification", "model_type": model_type, "random_state": 9},
    )
    assert train.status_code == 200
    return train.json()["artifact"]["model_id"]


def test_explanation_refuses_invalid_smiles(tmp_path, monkeypatch):
    model_id = _train_model(tmp_path, monkeypatch)
    response = client.post("/api/admet-explain/prediction", json={"model_id": model_id, "smiles": "not_smiles"})
    assert response.status_code == 422
    assert "Invalid SMILES" in response.json()["detail"]


def test_explanation_refuses_invalid_model():
    response = client.post("/api/admet-explain/prediction", json={"model_id": "missing_model", "smiles": "CCO"})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_random_forest_explanation_returns_real_feature_importance(tmp_path, monkeypatch):
    model_id = _train_model(tmp_path, monkeypatch, "random_forest")
    response = client.post("/api/admet-explain/prediction", json={"model_id": model_id, "smiles": "CCO"})
    assert response.status_code == 200
    body = response.json()
    assert body["model_id"] == model_id
    assert body["scientific_notice"] == "Computational explanation only. Requires experimental and external validation."
    assert body["important_features"]
    assert all(item["source"] == "model_feature_importance" for item in body["important_features"])
    assert body["evidence_strength"] in {"moderate_internal_only", "weak_internal", "uncertain", "externally_supported", "externally_weak"}
    assert "shap" not in json.dumps(body).lower()
    assert "lime" not in json.dumps(body).lower()


def test_logistic_explanation_returns_coefficients_only(tmp_path, monkeypatch):
    model_id = _train_model(tmp_path, monkeypatch, "logistic_regression")
    response = client.post("/api/admet-explain/prediction", json={"model_id": model_id, "smiles": "CCO"})
    assert response.status_code == 200
    body = response.json()
    assert body["important_features"]
    assert all(item["source"] == "linear_model_coefficient" for item in body["important_features"])


def test_evidence_strength_reflects_missing_external_validation(tmp_path, monkeypatch):
    model_id = _train_model(tmp_path, monkeypatch, "random_forest")
    response = client.post("/api/admet-explain/prediction", json={"model_id": model_id, "smiles": "CCO"})
    body = response.json()
    assert body["external_validation_status"]["status"] == "not_available"
    assert body["evidence_strength"] in {"moderate_internal_only", "weak_internal", "uncertain"}


def test_outside_domain_prediction_produces_warning(tmp_path, monkeypatch):
    model_id = _train_model(tmp_path, monkeypatch, "random_forest")
    response = client.post(
        "/api/admet-explain/prediction",
        json={"model_id": model_id, "smiles": "C1=CC=C2C(=C1)C3=CC=CC=C3C2C4=CC=CC=C4C5=CC=CC=C5"},
    )
    assert response.status_code == 200
    body = response.json()
    if body["domain_status"] == "outside_domain":
        assert any("outside" in warning.lower() for warning in body["warnings"])


def test_explanation_report_generation_and_downloads(tmp_path, monkeypatch):
    model_id = _train_model(tmp_path, monkeypatch, "random_forest")
    created = client.post(
        "/api/admet-explain/report/create",
        json={"model_id": model_id, "smiles": "CCO", "formats": ["json", "pdf", "docx"]},
    )
    assert created.status_code == 200
    body = created.json()
    assert set(body["available_formats"]) == {"json", "pdf", "docx"}
    report_id = body["report_id"]
    assert client.get(f"/api/admet-explain/reports/{report_id}/json").status_code == 200
    assert client.get(f"/api/admet-explain/reports/{report_id}/pdf").status_code == 200
    assert client.get(f"/api/admet-explain/reports/{report_id}/docx").status_code == 200
    reports = client.get("/api/admet-explain/reports")
    assert reports.status_code == 200
    assert any(item["report_id"] == report_id for item in reports.json())


def test_research_export_includes_explainability_files(tmp_path, monkeypatch):
    model_id = _train_model(tmp_path, monkeypatch, "random_forest")
    created = client.post(
        "/api/admet-explain/report/create",
        json={"model_id": model_id, "smiles": "CCO", "formats": ["json"]},
    )
    assert created.status_code == 200
    export = client.post(
        "/api/research-export/create",
        json={
            "include_screening_history": False,
            "include_benchmark_runs": False,
            "include_batch_runs": False,
            "include_cache_status": False,
            "include_reports": False,
        },
    )
    assert export.status_code == 200
    assert "ADMET_EXPLAINABILITY" in export.json()["included_sections"]
    download = client.get(export.json()["download_url"])
    assert download.status_code == 200
    with zipfile.ZipFile(BytesIO(download.content)) as archive:
        names = archive.namelist()
    assert any("ADMET_EXPLAINABILITY/explanation_summaries.json" in name for name in names)
    assert any("ADMET_EXPLAINABILITY/limitations.md" in name for name in names)
