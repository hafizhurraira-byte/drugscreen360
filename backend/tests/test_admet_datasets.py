from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _dataset_csv() -> bytes:
    return (
        "compound_name,smiles,herg_label,source\n"
        "Aspirin,CC(=O)OC1=CC=CC=C1C(=O)O,low,example\n"
        "Aspirin duplicate,CC(=O)Oc1ccccc1C(=O)O,low,example\n"
        "Bad row,not_a_smiles,high,example\n"
        "Missing label,CCO,,example\n"
    ).encode("utf-8")


def _upload_dataset(project_id=None):
    data = {
        "dataset_name": "hERG curation test",
        "task_name": "hERG",
        "label_column": "herg_label",
        "smiles_column": "smiles",
        "compound_name_column": "compound_name",
        "notes": "unit test dataset",
    }
    if project_id:
        data["project_id"] = str(project_id)
    return client.post(
        "/api/admet-datasets/upload",
        data=data,
        files={"file": ("admet.csv", _dataset_csv(), "text/csv")},
    )


def test_admet_dataset_csv_upload_works():
    response = _upload_dataset()
    assert response.status_code == 200
    body = response.json()
    assert body["dataset_id"] > 0
    assert body["summary"]["total_rows"] == 4
    assert body["summary"]["valid_molecules"] == 2
    assert body["summary"]["invalid_smiles"] == 1
    assert body["summary"]["missing_labels"] == 1
    assert body["summary"]["duplicate_molecules"] == 1


def test_admet_dataset_descriptors_and_no_fake_predictions():
    body = _upload_dataset().json()
    preview = body["records_preview"]
    valid = next(item for item in preview if item["is_valid"])
    assert valid["descriptors"]["molecular_weight"] > 0
    assert "prediction" not in valid["descriptors"]
    assert "model" not in valid["descriptors"]


def test_admet_dataset_list_detail_records_and_summary():
    dataset_id = _upload_dataset().json()["dataset_id"]
    assert any(item["id"] == dataset_id for item in client.get("/api/admet-datasets/list").json())
    detail = client.get(f"/api/admet-datasets/{dataset_id}")
    records = client.get(f"/api/admet-datasets/{dataset_id}/records")
    summary = client.get(f"/api/admet-datasets/{dataset_id}/summary")
    assert detail.status_code == 200
    assert records.status_code == 200
    assert summary.status_code == 200
    assert len(records.json()) == 4
    assert summary.json()["label_distribution"]["low"] == 2


def test_admet_dataset_exports_work():
    dataset_id = _upload_dataset().json()["dataset_id"]
    csv_response = client.get(f"/api/admet-datasets/{dataset_id}/curated.csv")
    report_response = client.get(f"/api/admet-datasets/{dataset_id}/curation-report.json")
    assert csv_response.status_code == 200
    assert "canonical_smiles" in csv_response.text
    assert "molecular_weight" in csv_response.text
    assert report_response.status_code == 200
    assert report_response.json()["scientific_scope"].startswith("Dataset curation only")


def test_admet_dataset_active_project_attachment():
    project = client.post(
        "/api/projects/create",
        json={"title": "ADMET Dataset Project", "project_type": "general_research", "status": "active"},
    ).json()
    dataset_id = _upload_dataset(project["id"]).json()["dataset_id"]
    detail = client.get(f"/api/projects/{project['id']}").json()
    assert any(item["item_type"] == "admet_dataset" and item["item_id"] == str(dataset_id) for item in detail["items"])


def test_admet_dataset_invalid_file_type_rejected():
    response = client.post(
        "/api/admet-datasets/upload",
        data={"dataset_name": "bad", "label_column": "label", "smiles_column": "smiles"},
        files={"file": ("bad.xlsx", b"bad", "application/octet-stream")},
    )
    assert response.status_code == 415
