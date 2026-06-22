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


def test_concise_disease_to_lead_report_quality(tmp_path, monkeypatch):
    from docx import Document
    
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    
    # 1. Create a project
    project = client.post("/api/projects/create", json={"title": "EGFR Lead Optimization Project", "project_type": "general_research", "status": "active"}).json()
    project_id = project["id"]
    
    # 2. Run prioritization to populate candidates
    lead = client.post(
        "/api/admet-leads/prioritize",
        json={
            "project_id": project_id,
            "source_type": "manual",
            "candidates": [
                {"compound_name": "Aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O"},
                {"compound_name": "Ibuprofen", "smiles": "CC(C)Cc1ccc(cc1)C(C)C(=O)O"}
            ],
            "include_trained_model": False,
            "include_domain": False,
            "include_explainability": False,
        },
    )
    assert lead.status_code == 200
    run_id = lead.json()["run_id"]
    
    # 3. Create a validation plan
    plan = client.post(
        "/api/validation-planner/create",
        json={
            "project_id": project_id,
            "source_type": "manual",
            "plan_title": "Validation Plan: EGFR Test",
            "candidates": [
                {"compound_name": "Aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O", "compound_id": "Aspirin"}
            ]
        }
    )
    assert plan.status_code == 200
    plan_id = plan.json()["plan_id"]
    
    # 4. Generate the final report in concise mode
    report_response = client.post(
        "/api/final-report/create",
        json={
            "project_id": project_id,
            "report_title": "Disease-to-Lead Final Concise Report",
            "report_mode": "concise_disease_to_lead_report",
            "prioritization_run_id": run_id,
            "validation_plan_id": plan_id,
            "formats": ["json", "pdf", "docx"],
        }
    )
    assert report_response.status_code == 200
    report_id = report_response.json()["report_id"]
    
    # 5. Download the DOCX via the real download endpoint
    download_response = client.get(f"/api/final-report/reports/{report_id}/docx")
    assert download_response.status_code == 200
    assert "wordprocessingml" in download_response.headers["content-type"]
    
    # 6. Open with python-docx and scan content
    doc_bytes = BytesIO(download_response.content)
    doc = Document(doc_bytes)
    
    # Extract all text from paragraphs and tables
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                full_text.append(cell.text)
                
    combined_text = "\n".join(full_text)
    
    # Assertions for 13 clean sections (checking presence of section headers / key text)
    expected_sections = [
        "Executive Summary",
        "Workflow Input Table",
        "Workflow Completion Table",
        "Top Candidate Table",
        "Top Candidate Interpretation",
        "ADMET & Drug-likeness Summary",
        "Model Evidence Summary",
        "External Validation Summary",
        "Experimental Feedback Summary",
        "Validation Planner Summary",
        "Limitations",
        "Recommended Next Steps",
        "Reproducibility"
    ]
    for section in expected_sections:
        assert section in combined_text, f"Missing expected section: {section}"
        
    # Assertions for forbidden strings
    forbidden_strings = [
        "Top Candidates: [{",
        '{"rank"',
        '"compound_name"',
        '"score_components"',
        '"descriptors"',
        "Stored records summarized",
        "Latest Training Runs: [{",
        "Available Models: [{",
        "Unavailable Models: [{",
        "Missing sections: none"
    ]
    for forbidden in forbidden_strings:
        assert forbidden not in combined_text, f"Found forbidden string: '{forbidden}'"
        
    # Assertions for fallbacks (since experimental results don't exist, and active model is likely unavailable)
    assert "External validation/calibration was not available for this project." in combined_text
    assert "No user-entered experimental assay results were imported. Experimental feedback comparison was not performed." in combined_text
    assert "No active trained ADMET model was available. This report used descriptor-based and rule-based evidence only." in combined_text
