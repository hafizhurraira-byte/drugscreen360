from pathlib import Path

from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app
from app.models.project_report_models import ProjectReportPayload
from app.services.project_reports import build_project_docx, build_project_pdf, build_project_summary

client = TestClient(app)


def _payload(workflow_type="disease_to_candidate"):
    payload = {
        "workflow_type": workflow_type,
        "disease": {
            "query": "breast cancer",
            "disease_name": "breast cancer",
            "disease_id": "MONDO_0007254",
            "description": "Malignant neoplasm involving the breast",
        }
        if workflow_type == "disease_to_candidate"
        else None,
        "disease_target": {
            "gene_symbol": "EGFR",
            "target_name": "epidermal growth factor receptor",
            "open_targets_target_id": "ENSG00000146648",
            "association_score": 0.82,
            "ranking_reason": "Mock ranked target",
        }
        if workflow_type == "disease_to_candidate"
        else None,
        "chembl_target": {
            "target_chembl_id": "CHEMBL203",
            "preferred_name": "Epidermal growth factor receptor",
            "organism": "Homo sapiens",
            "target_type": "SINGLE PROTEIN",
            "accession": "P00533",
            "target_priority_score": 65,
            "target_ranking_reason": "human target; single protein target",
        },
        "retrieved_candidate_count": 50,
        "selected_candidate_count": 1,
        "screened_candidate_count": 1,
        "batch_screening_results": {
            "comparison_table": [
                {
                    "compound": "Example inhibitor",
                    "molecule_chembl_id": "CHEMBL_EXAMPLE",
                    "canonical_smiles": "CCO",
                    "target_name": "EGFR",
                    "activity_type": "IC50",
                    "activity_value": 50,
                    "activity_units": "nM",
                    "evidence_level": "Strong",
                    "evidence_score": 91,
                    "molecular_weight": 180.1,
                    "logp": 2.1,
                    "tpsa": 60.2,
                    "lipinski_pass": True,
                    "veber_pass": True,
                    "drug_likeness_status": "Good",
                    "developability_risk": "Low",
                    "overall_admet_tox_concern_score": 35,
                    "concern_level": "Low",
                    "decision": "Proceed",
                    "final_candidate_priority": "Higher priority",
                    "recommended_next_step": "Confirm with orthogonal assays.",
                }
            ]
        },
        "limitations": ["Rule-based MVP only."],
    }
    return payload


def test_project_report_payload_validation():
    payload = ProjectReportPayload.model_validate(_payload())
    assert payload.workflow_type == "disease_to_candidate"
    assert payload.disease.disease_name == "breast cancer"


def test_project_report_pdf_and_docx_generation():
    payload = ProjectReportPayload.model_validate(_payload())
    assert build_project_pdf(payload).startswith(b"%PDF")
    assert build_project_docx(payload).startswith(b"PK")


def test_project_report_summary_includes_context():
    payload = ProjectReportPayload.model_validate(_payload())
    summary = build_project_summary(payload)
    assert summary["selected_disease"] == "breast cancer"
    assert summary["selected_chembl_target"] == "CHEMBL203"
    assert summary["top_candidate"] == "Example inhibitor"


def test_project_report_create_and_export_endpoints(monkeypatch, tmp_path):
    import app.database as database

    monkeypatch.setattr(database, "DB_PATH", Path(tmp_path) / "project-report.sqlite3")
    init_db()
    response = client.post("/api/project-report/create", json={"payload": _payload(), "title": "Test Project Report"})
    assert response.status_code == 200
    report_id = response.json()["project_report_id"]

    read_response = client.get(f"/api/project-report/{report_id}")
    assert read_response.status_code == 200
    assert read_response.json()["payload"]["chembl_target"]["target_chembl_id"] == "CHEMBL203"

    assert client.get(f"/api/project-report/{report_id}/pdf").content.startswith(b"%PDF")
    assert client.get(f"/api/project-report/{report_id}/docx").content.startswith(b"PK")
    assert "Example inhibitor" in client.get(f"/api/project-report/{report_id}/csv").text


def test_project_report_handles_empty_optional_fields():
    payload = ProjectReportPayload.model_validate(_payload("target_to_candidate"))
    assert payload.disease is None
    assert build_project_pdf(payload).startswith(b"%PDF")
