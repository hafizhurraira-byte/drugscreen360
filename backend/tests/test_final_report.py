import zipfile
from io import BytesIO

from docx import Document
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


def _docx_text(content: bytes) -> str:
    document = Document(BytesIO(content))
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    table_cells = [
        cell.text
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    ]
    return "\n".join(paragraphs + table_cells)


def _create_project_with_candidate_matrix():
    project = client.post(
        "/api/projects/create",
        json={
            "title": "Disease-to-Lead EGFR Review",
            "description": "Project-scoped final report test.",
            "disease_area": "breast cancer",
            "target_name": "EGFR",
            "project_type": "disease_screening",
            "status": "active",
        },
    ).json()
    candidates = [
        ("Aspirin", "CHEMBL_ASPIRIN", 180.16, 1.19, 63.6, "Pass", "Pass", "Low", "Reasonable follow-up candidate"),
        ("Caffeine", "CHEMBL_CAFFEINE", 194.19, -0.1, 61.8, "Pass", "Pass", "Low", "Review with caution"),
        ("Ibuprofen", "CHEMBL_IBUPROFEN", 206.28, 3.5, 37.3, "Pass", "Pass", "Moderate", "Review with caution"),
        ("Acetaminophen", "CHEMBL_APAP", 151.16, 0.5, 49.3, "Pass", "Pass", "Low", "Review with caution"),
        ("Metformin", "CHEMBL_METFORMIN", 129.16, -1.4, 88.9, "Pass", "Pass", "Low", "Review with caution"),
        ("Benzene", "CHEMBL_BENZENE", 78.11, 2.1, 0, "Pass", "Pass", "Review", "Insufficient evidence"),
    ]
    for index, (name, chembl_id, mw, logp, tpsa, lipinski, veber, admet, decision) in enumerate(candidates, start=1):
        response = client.post(
            f"/api/projects/{project['id']}/attach-item",
            json={
                "item_type": "drug_finder_batch",
                "item_id": f"candidate-{index}",
                "item_title": name,
                "metadata": {
                    "workflow_type": "disease_to_lead",
                    "candidate_name": name,
                    "compound_name": name,
                    "molecule_chembl_id": chembl_id,
                    "target_name": "EGFR",
                    "candidate_limit": 5,
                    "similarity_limit": 5,
                    "analysis_depth": "Quick",
                    "molecular_weight": mw,
                    "logp": logp,
                    "tpsa": tpsa,
                    "lipinski_status": lipinski,
                    "veber_status": veber,
                    "admet_risk_summary": admet,
                    "evidence_level": "not evaluated",
                    "evidence_score": None,
                    "model_prediction_status": "rule_based_only",
                    "decision": decision,
                    "decision_reason": f"{name} is a computational candidate for review using available descriptor and rule-based ADMET data.",
                },
            },
        )
        assert response.status_code == 200
    return project


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


def test_project_final_report_docx_is_readable_and_project_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    monkeypatch.setattr(final_report_service, "get_active_trained_model_info", lambda: None)
    project = _create_project_with_candidate_matrix()
    response = _create_final(project_id=project["id"])
    assert response.status_code == 200
    body = response.json()
    assert "active_trained_model" in body["missing_sections"]
    assert "external_validation" in body["missing_sections"]
    assert "experimental_feedback" in body["missing_sections"]

    docx_response = client.get(body["generated_files"]["docx"])
    assert docx_response.status_code == 200
    text = _docx_text(docx_response.content)
    assert "Top Candidate Table" in text
    assert "ADMET & Drug-Likeness Summary" in text
    assert "Aspirin" in text
    assert "No active trained ADMET model was available" in text
    assert "External validation/calibration was not available" in text
    assert "No user-entered experimental results were imported" in text
    assert "Computational decision-support report only" in text
    assert '"ranked_candidates"' not in text
    assert "metric_summary_json" not in text
    assert "[{" not in text
    assert "{'" not in text


def test_project_final_report_json_stays_structured_and_limits_top_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    monkeypatch.setattr(final_report_service, "get_active_trained_model_info", lambda: None)
    project = _create_project_with_candidate_matrix()
    body = _create_final(project_id=project["id"]).json()
    report = client.get(body["generated_files"]["json"]).json()
    assert "sections" in report
    assert "concise_report" in report
    top_table = report["concise_report"]["top_candidate_table"]
    assert top_table[0][0] == "Rank"
    assert len(top_table) == 6
    assert report["concise_report"]["workflow_input_summary"]["Disease"] == "breast cancer"
    assert report["concise_report"]["workflow_input_summary"]["Target"] == "EGFR"
    assert report["concise_report"]["model_evidence_summary"]["status"] == "not available"
    assert report["concise_report"]["external_validation_summary"]["status"] == "not available"
    assert report["concise_report"]["experimental_feedback_summary"]["status"] == "not available"


def test_saved_final_report_metadata_returns_correct_missing_sections(tmp_path, monkeypatch):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    monkeypatch.setattr(final_report_service, "get_active_trained_model_info", lambda: None)
    project = _create_project_with_candidate_matrix()
    report_id = _create_final(project_id=project["id"]).json()["report_id"]
    response = client.get(f"/api/final-report/reports/{report_id}")
    assert response.status_code == 200
    body = response.json()
    assert "active_trained_model" in body["missing_sections"]
    assert "external_validation" in body["missing_sections"]
    assert "experimental_feedback" in body["missing_sections"]


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
