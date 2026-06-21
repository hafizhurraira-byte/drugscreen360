import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.services import final_report_service, research_export_service

client = TestClient(app)


def _create_final(**extra):
    payload = {
        "report_title": "DrugScreen360 Final Project Report",
        "include_screening": True,
        "include_admet_prediction": True,
        "include_model_training": True,
        "include_external_validation": True,
        "include_applicability_domain": True,
        "include_explainability": True,
        "include_lead_prioritization": True,
        "include_validation_planner": True,
        "include_experimental_feedback": True,
        "formats": ["json", "pdf", "docx"],
    }
    payload.update(extra)
    return client.post("/api/final-report/create", json=payload)


def test_final_report_creation_works_with_minimal_data(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    response = _create_final()
    assert response.status_code == 200
    body = response.json()
    assert body["report_id"]
    assert body["generated_files"]["json"].endswith("/json")
    assert "Computational decision-support report only" in body["scientific_notice"]
    assert body["missing_sections"] is not None


def test_final_report_creation_works_with_project_data(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    project = client.post("/api/projects/create", json={"title": "Final Report Project", "project_type": "general_research", "status": "active"}).json()
    lead = client.post(
        "/api/admet-leads/prioritize",
        json={
            "project_id": project["id"],
            "source_type": "manual",
            "candidates": [{"compound_name": "Ethanol", "smiles": "CCO"}],
            "include_trained_model": False,
            "include_domain": False,
            "include_explainability": False,
        },
    )
    assert lead.status_code == 200
    response = _create_final(project_id=project["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project["id"]
    assert "lead_prioritization" in body["included_sections"]


def test_final_report_missing_sections_are_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    response = _create_final(
        include_external_validation=True,
        include_applicability_domain=True,
        include_explainability=True,
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["missing_sections"], list)


def test_json_pdf_docx_endpoints_work(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    report_id = _create_final().json()["report_id"]
    json_response = client.get(f"/api/final-report/reports/{report_id}/json")
    pdf_response = client.get(f"/api/final-report/reports/{report_id}/pdf")
    docx_response = client.get(f"/api/final-report/reports/{report_id}/docx")
    assert json_response.status_code == 200
    assert pdf_response.status_code == 200
    assert docx_response.status_code == 200
    assert b"DrugScreen360 Final Project Report" in json_response.content
    assert pdf_response.headers["content-type"].startswith("application/pdf")
    assert "wordprocessingml" in docx_response.headers["content-type"]


def test_no_fake_experimental_results_or_clinical_claims(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    report_id = _create_final().json()["report_id"]
    report = client.get(f"/api/final-report/reports/{report_id}/json").json()
    serialized = str(report).lower()
    assert "confirmed safe" not in serialized
    assert "drug approved" not in serialized
    assert "clinically validated" not in serialized
    assert "simulated assay result" not in serialized
    assert "no experimental results are generated" in serialized


def test_project_attachment_works(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    project = client.post("/api/projects/create", json={"title": "Attached Final Report", "project_type": "general_research", "status": "active"}).json()
    response = _create_final(project_id=project["id"])
    assert response.status_code == 200
    detail = client.get(f"/api/projects/{project['id']}").json()
    assert any(item["item_type"] == "final_project_report" for item in detail["items"])


def test_research_export_includes_final_report_files(tmp_path, monkeypatch):
    final_dir = tmp_path / "final_project_reports"
    export_dir = tmp_path / "research_exports"
    monkeypatch.setattr(final_report_service, "REPORT_DIR", final_dir)
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", export_dir)
    response = _create_final()
    assert response.status_code == 200
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
    download = client.get(export.json()["download_url"])
    assert download.status_code == 200
    with zipfile.ZipFile(BytesIO(download.content)) as archive:
        names = archive.namelist()
    assert any("FINAL_PROJECT_REPORTS/" in name for name in names)
    assert any(name.endswith(".json") and "final_project_report" in name for name in names)


def test_report_list_endpoint_works(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    report_id = _create_final().json()["report_id"]
    response = client.get("/api/final-report/reports")
    assert response.status_code == 200
    assert any(item["report_id"] == report_id for item in response.json())
