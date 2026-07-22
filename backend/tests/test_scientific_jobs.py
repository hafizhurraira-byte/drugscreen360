import time

from fastapi.testclient import TestClient

from app.main import app
from app.services import admet_training_service


client = TestClient(app)


def _csv(rows: int = 24) -> bytes:
    lines = ["compound_name,smiles,label"]
    smiles = ["CCO", "CCN", "CCC", "CCCl", "c1ccccc1", "CC(=O)O"]
    for index in range(rows):
        lines.append(f"Mol {index},{smiles[index % len(smiles)]},{'active' if index % 2 else 'inactive'}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _upload():
    return client.post(
        "/api/admet-datasets/upload",
        data={"dataset_name": "job training dataset", "task_name": "toxicity_concern", "label_column": "label", "smiles_column": "smiles", "compound_name_column": "compound_name"},
        files={"file": ("training.csv", _csv(), "text/csv")},
    ).json()["dataset_id"]


def test_async_training_job_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_training_service, "TRAINED_DIR", tmp_path / "trained")
    dataset_id = _upload()
    response = client.post("/api/admet-training/train/job", json={"dataset_id": dataset_id, "task_type": "auto", "model_type": "random_forest"})
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    for _ in range(60):
        job = client.get(f"/api/admet-training/jobs/{job_id}").json()
        if job["status"] in {"SUCCEEDED", "FAILED"}:
            break
        time.sleep(0.1)

    assert job["status"] == "SUCCEEDED"
    assert job["output_references"]["status"] == "completed"
    assert job["progress"] == 1.0

