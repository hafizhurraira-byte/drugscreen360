import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.services import final_report_service, research_export_service

client = TestClient(app)


DEMO_NOTICE = "Demo data for software demonstration only. Not experimental or clinical evidence."


def test_demo_project_creation_works():
    response = client.post("/api/demo-workflow/create-project")
    assert response.status_code == 200
    body = response.json()
    assert body["demo_project_id"] > 0
    assert body["created_items"]
    assert DEMO_NOTICE in body["scientific_notice"]
    assert all(item["metadata"]["demo_mode"] for item in body["created_items"])


def test_demo_workflow_run_works(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")
    response = client.post(
        "/api/demo-workflow/run",
        json={
            "project_title": "DrugScreen360 Unit Demo Project",
            "include_screening": True,
            "include_lead_prioritization": True,
            "include_validation_plan": True,
            "include_experimental_feedback": True,
            "include_final_report": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["demo_project_id"] > 0
    assert body["final_report_id"]
    assert body["research_export_available"] is True
    assert "research_export_zip" in body["download_links"]
    assert any(step["step_id"] == "generate_final_report" and step["status"] == "completed" for step in body["workflow_steps"])
    assert DEMO_NOTICE in body["scientific_notice"]


def test_demo_records_are_clearly_labelled():
    body = client.post("/api/demo-workflow/create-project").json()
    detail = client.get(f"/api/projects/{body['demo_project_id']}").json()
    assert "Demo" in detail["title"]
    assert any(item["metadata"].get("demo_mode") is True for item in detail["items"])
    serialized = str(detail)
    assert DEMO_NOTICE in serialized


def test_demo_final_report_contains_demo_disclaimer(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")
    body = client.post("/api/demo-workflow/run", json={"project_title": "Demo Report Check"}).json()
    report = client.get(f"/api/final-report/reports/{body['final_report_id']}/json")
    assert report.status_code == 200
    serialized = str(report.json())
    assert DEMO_NOTICE in serialized
    assert "clinical evidence" in serialized.lower()


def test_demo_workflow_does_not_create_clinical_claims(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")
    body = client.post("/api/demo-workflow/run", json={"project_title": "Demo Claim Safety"}).json()
    report = client.get(f"/api/final-report/reports/{body['final_report_id']}/json").json()
    serialized = str(report).lower()
    forbidden = ["confirmed safe", "clinically validated", "drug approved", "regulatory ready", "market ready"]
    assert all(term not in serialized for term in forbidden)


def test_demo_research_export_includes_demo_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")
    body = client.post("/api/demo-workflow/run", json={"project_title": "Demo Export Check"}).json()
    response = client.get(body["download_links"]["research_export_zip"])
    assert response.status_code == 200
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        names = archive.namelist()
        manifest_name = next(name for name in names if name.endswith("DEMO_WORKFLOW/demo_manifest.json"))
        manifest_text = archive.read(manifest_name).decode("utf-8")
    assert "DEMO_WORKFLOW/demo_disclaimer.md" in "\n".join(names)
    assert DEMO_NOTICE in manifest_text


def test_demo_workflow_status_endpoint_works(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")
    body = client.post("/api/demo-workflow/run", json={"project_title": "Demo Status Check"}).json()
    response = client.get(f"/api/demo-workflow/status/{body['demo_project_id']}")
    assert response.status_code == 200
    status = response.json()
    assert "create_project" in status["completed_steps"]
    assert "load_candidates" in status["completed_steps"]
    assert status["generated_artifacts"]
    assert DEMO_NOTICE in status["scientific_notice"]


def test_invalid_demo_project_status_request_handled_safely():
    response = client.get("/api/demo-workflow/status/999999999")
    assert response.status_code == 404
