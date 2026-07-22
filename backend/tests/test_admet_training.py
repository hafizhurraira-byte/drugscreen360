from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services import admet_training_service

client = TestClient(app)


def _csv(rows: int = 24, numeric: bool = False) -> bytes:
    lines = ["compound_name,smiles,label"]
    smiles = ["CCO", "CCN", "CCC", "CCCl", "c1ccccc1", "CC(=O)O"]
    for index in range(rows):
        label = str(float(index) / 10.0) if numeric else ("active" if index % 2 else "inactive")
        lines.append(f"Mol {index},{smiles[index % len(smiles)]},{label}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _upload(rows: int = 24, numeric: bool = False):
    return client.post(
        "/api/admet-datasets/upload",
        data={"dataset_name": "training dataset", "task_name": "hERG", "label_column": "label", "smiles_column": "smiles", "compound_name_column": "compound_name"},
        files={"file": ("training.csv", _csv(rows, numeric), "text/csv")},
    ).json()


def test_training_refuses_too_few_valid_records():
    dataset_id = _upload(rows=10)["dataset_id"]
    response = client.post("/api/admet-training/train", json={"dataset_id": dataset_id})
    assert response.status_code == 422
    assert "at least 20 valid labelled records" in response.json()["detail"]


def test_binary_classification_training_creates_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_training_service, "TRAINED_DIR", tmp_path / "trained")
    dataset_id = _upload(rows=28)["dataset_id"]
    response = client.post("/api/admet-training/train", json={"dataset_id": dataset_id, "task_type": "auto", "model_type": "random_forest", "random_state": 7})
    assert response.status_code == 200
    body = response.json()
    assert body["task_type"] == "binary_classification"
    assert "accuracy" in body["metrics"]
    artifact_dir = Path(body["artifact"]["artifact_path"]).parent
    assert (artifact_dir / "model.joblib").exists()
    assert (artifact_dir / "model_manifest.json").exists()
    assert (artifact_dir / "model_card.json").exists()
    assert (artifact_dir / "feature_schema.json").exists()
    assert (artifact_dir / "split_manifest.json").exists()
    manifest = (artifact_dir / "model_manifest.json").read_text(encoding="utf-8")
    assert "artifact_files" in manifest
    split_manifest = (artifact_dir / "split_manifest.json").read_text(encoding="utf-8")
    assert "dataset_version_hash" in split_manifest
    assert "split_hash" in split_manifest
    assert "prediction" not in body["metrics"]


def test_endpoint_label_column_maps_to_real_admet_task(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_training_service, "TRAINED_DIR", tmp_path / "trained")
    response = client.post(
        "/api/admet-datasets/upload",
        data={
            "dataset_name": "Ames endpoint dataset",
            "label_column": "ames_mutagenicity",
            "smiles_column": "smiles",
            "compound_name_column": "compound_name",
        },
        files={"file": ("ames.csv", _csv(rows=28).replace(b",label", b",ames_mutagenicity"), "text/csv")},
    )
    assert response.status_code == 200
    dataset = response.json()
    assert dataset["task_name"] == "Ames mutagenicity"

    trained = client.post("/api/admet-training/train", json={"dataset_id": dataset["dataset_id"]})
    assert trained.status_code == 200
    assert trained.json()["artifact"]["task_name"] == "Ames mutagenicity"


def test_regression_training_works(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_training_service, "TRAINED_DIR", tmp_path / "trained")
    dataset_id = _upload(rows=24, numeric=True)["dataset_id"]
    response = client.post("/api/admet-training/train", json={"dataset_id": dataset_id, "task_type": "regression", "model_type": "random_forest_regressor"})
    assert response.status_code == 200
    assert response.json()["task_type"] == "regression"
    assert "mae" in response.json()["metrics"]


def test_training_run_endpoints_and_model_card(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_training_service, "TRAINED_DIR", tmp_path / "trained")
    dataset_id = _upload(rows=24)["dataset_id"]
    run_id = client.post("/api/admet-training/train", json={"dataset_id": dataset_id}).json()["training_run_id"]
    assert client.get("/api/admet-training/runs").status_code == 200
    detail = client.get(f"/api/admet-training/runs/{run_id}")
    card = client.get(f"/api/admet-training/runs/{run_id}/model-card")
    summary = client.get(f"/api/admet-training/runs/{run_id}/training-summary")
    metrics = client.get(f"/api/admet-training/runs/{run_id}/metrics.csv")
    assert detail.status_code == 200
    assert card.json()["external_validation_required"] is True
    assert summary.json()["training_run_id"] == run_id
    assert "metric,value" in metrics.text


def test_training_active_project_attachment(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_training_service, "TRAINED_DIR", tmp_path / "trained")
    project = client.post("/api/projects/create", json={"title": "Training Project", "project_type": "general_research", "status": "active"}).json()
    dataset_id = _upload(rows=24)["dataset_id"]
    run_id = client.post("/api/admet-training/train", json={"dataset_id": dataset_id, "project_id": project["id"]}).json()["training_run_id"]
    detail = client.get(f"/api/projects/{project['id']}").json()
    assert any(item["item_type"] == "admet_training_run" and item["item_id"] == str(run_id) for item in detail["items"])
