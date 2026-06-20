import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.services import research_export_service

client = TestClient(app)


def _create_project():
    response = client.post(
        "/api/projects/create",
        json={
            "title": "Breast Cancer EGFR Workspace",
            "description": "Project workspace test",
            "disease_area": "breast cancer",
            "target_name": "EGFR",
            "project_type": "disease_screening",
            "status": "active",
            "notes": "initial notes",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_create_project_works():
    project = _create_project()
    assert project["id"] > 0
    assert project["title"] == "Breast Cancer EGFR Workspace"
    assert project["status"] == "active"


def test_list_projects_works():
    project = _create_project()
    response = client.get("/api/projects/list")
    assert response.status_code == 200
    assert any(item["id"] == project["id"] for item in response.json())


def test_get_project_detail_works():
    project = _create_project()
    response = client.get(f"/api/projects/{project['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == project["id"]
    assert "items" in body


def test_update_project_works():
    project = _create_project()
    response = client.put(f"/api/projects/{project['id']}", json={"status": "review", "notes": "review notes"})
    assert response.status_code == 200
    assert response.json()["status"] == "review"
    assert response.json()["notes"] == "review notes"


def test_archive_project_works():
    project = _create_project()
    response = client.post(f"/api/projects/{project['id']}/archive")
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_attach_item_works():
    project = _create_project()
    response = client.post(
        f"/api/projects/{project['id']}/attach-item",
        json={"item_type": "screening", "item_id": "1", "item_title": "Aspirin", "metadata": {"source": "unit-test"}},
    )
    assert response.status_code == 200
    assert response.json()["item_type"] == "screening"
    detail = client.get(f"/api/projects/{project['id']}").json()
    assert len(detail["items"]) >= 1


def test_project_summary_works():
    project = _create_project()
    client.post(
        f"/api/projects/{project['id']}/attach-item",
        json={"item_type": "benchmark", "item_id": "2", "item_title": "Benchmark", "metadata": {}},
    )
    response = client.get(f"/api/projects/{project['id']}/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["attached_item_count"] >= 1
    assert "model_status_summary" in body


def test_project_dashboard_handles_empty_project():
    project = _create_project()
    response = client.get(f"/api/projects/{project['id']}/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["project"]["id"] == project["id"]
    assert body["candidate_matrix"] == []
    assert any("No records are attached" in warning for warning in body["warnings"])


def test_project_dashboard_handles_attached_candidate_metadata():
    project = _create_project()
    client.post(
        f"/api/projects/{project['id']}/attach-item",
        json={
            "item_type": "drug_finder_batch",
            "item_id": "manual-egfr-1",
            "item_title": "EGFR candidate",
            "metadata": {
                "candidate_name": "Example EGFR compound",
                "molecule_chembl_id": "CHEMBL_TEST",
                "target_name": "EGFR",
                "molecular_weight": 420.2,
                "logp": 3.1,
                "tpsa": 86.4,
                "lipinski_status": "Pass",
                "veber_status": "Pass",
                "admet_risk_summary": "Low",
                "evidence_level": "Strong",
                "evidence_score": 88,
                "model_prediction_status": "rule_based_only",
                "decision": "Proceed",
            },
        },
    )
    response = client.get(f"/api/projects/{project['id']}/dashboard")
    assert response.status_code == 200
    matrix = response.json()["candidate_matrix"]
    assert matrix[0]["candidate_name"] == "Example EGFR compound"
    assert matrix[0]["decision_label"] == "Strong follow-up candidate"


def test_project_dashboard_returns_conservative_missing_data_warning():
    project = _create_project()
    client.post(
        f"/api/projects/{project['id']}/attach-item",
        json={"item_type": "screening", "item_id": "missing-record", "item_title": "Sparse item", "metadata": {}},
    )
    response = client.get(f"/api/projects/{project['id']}/dashboard")
    assert response.status_code == 200
    row = response.json()["candidate_matrix"][0]
    assert row["decision_label"] == "Insufficient evidence"
    assert row["model_prediction_status"] == "not available"
    assert row["missing_data_warnings"]


def test_project_decision_matrix_csv_endpoint_works():
    project = _create_project()
    client.post(
        f"/api/projects/{project['id']}/attach-item",
        json={"item_type": "screening", "item_id": "missing-record", "item_title": "Sparse item", "metadata": {}},
    )
    response = client.get(f"/api/projects/{project['id']}/decision-matrix.csv")
    assert response.status_code == 200
    assert "candidate_name" in response.text
    assert "Insufficient evidence" in response.text


def test_research_export_can_include_project_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")
    project = _create_project()
    response = client.post(
        "/api/research-export/create",
        json={"project_id": project["id"], "project_title": "Project Export", "include_reports": False},
    )
    assert response.status_code == 200
    export_id = response.json()["export_id"]
    download = client.get(f"/api/research-export/{export_id}/download")
    archive = zipfile.ZipFile(BytesIO(download.content))
    names = archive.namelist()
    assert any(name.endswith("PROJECT_WORKSPACE/project_detail.json") for name in names)
    assert any(name.endswith("PROJECT_WORKSPACE/project_dashboard.json") for name in names)
    assert any(name.endswith("PROJECT_WORKSPACE/candidate_decision_matrix.csv") for name in names)
    assert any(name.endswith("PROJECT_WORKSPACE/project_recommendations.md") for name in names)


def test_invalid_project_id_handled_safely():
    assert client.get("/api/projects/999999999").status_code == 404
    assert client.post("/api/projects/999999999/archive").status_code == 404
    assert client.get("/api/projects/999999999/dashboard").status_code == 404
    assert client.get("/api/projects/999999999/decision-matrix.csv").status_code == 404
    response = client.post(
        "/api/projects/999999999/attach-item",
        json={"item_type": "screening", "item_id": "1"},
    )
    assert response.status_code == 404
