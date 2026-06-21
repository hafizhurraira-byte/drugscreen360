import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.services import research_export_service

client = TestClient(app)


ASPIRIN = "CC(=O)OC1=CC=CC=C1C(=O)O"


def _create_plan():
    response = client.post(
        "/api/validation-planner/create",
        json={
            "source_type": "manual",
            "plan_title": "Feedback plan",
            "candidates": [
                {
                    "compound_name": "Aspirin",
                    "smiles": ASPIRIN,
                    "priority_label": "high_priority_for_review",
                    "metadata": {
                        "rule_based_admet_summary": {
                            "concern_level": "High",
                            "structural_alert_risk": "High",
                            "solubility_risk": "Medium",
                            "absorption_risk": "Medium",
                        }
                    },
                }
            ],
        },
    )
    assert response.status_code == 200
    return response.json()["plan_id"]


def _create_result(**extra):
    payload = {
        "results": [
            {
                "compound_name": "Aspirin",
                "smiles": ASPIRIN,
                "assay_name": "Cytotoxicity follow-up assay",
                "assay_category": "cytotoxicity",
                "measured_value": "not provided",
                "measurement_unit": "",
                "qualitative_result": "User-entered result",
                "result_direction": "unfavorable",
                "replicate_count": 3,
                "notes": "Real user-provided result for testing.",
            }
        ],
        "source_type": "manual",
    }
    payload.update(extra)
    return client.post("/api/experimental-results/create", json=payload)


def test_manual_experimental_result_creation_works():
    response = _create_result()
    assert response.status_code == 200
    body = response.json()
    assert body["accepted_count"] == 1
    assert body["rejected_count"] == 0
    assert body["scientific_notice"] == "Experimental feedback summary only. Interpretation requires qualified scientific review."
    assert body["saved_results"][0]["canonical_smiles"]


def test_invalid_smiles_handled_safely():
    response = _create_result(
        results=[
            {
                "compound_name": "Bad",
                "smiles": "not_a_smiles",
                "assay_name": "Cytotoxicity",
                "assay_category": "cytotoxicity",
                "result_direction": "favorable",
            }
        ]
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted_count"] == 0
    assert body["rejected_count"] == 1
    assert "Invalid SMILES" in body["invalid_rows"][0]["error_reason"]


def test_csv_import_works():
    csv_text = (
        "compound_name,smiles,assay_name,assay_category,measured_value,measurement_unit,qualitative_result,result_direction,replicate_count,notes\n"
        f"Aspirin,{ASPIRIN},Solubility assay,solubility,not provided,,acceptable solubility,favorable,2,user import\n"
    )
    response = client.post(
        "/api/experimental-results/import-csv",
        files={"file": ("results.csv", csv_text.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["accepted_count"] == 1


def test_csv_invalid_rows_are_reported():
    csv_text = (
        "compound_name,smiles,assay_name,assay_category,result_direction\n"
        "Bad,not_a_smiles,Cytotoxicity,cytotoxicity,favorable\n"
        f"Aspirin,{ASPIRIN},Cytotoxicity,cytotoxicity,favorable\n"
    )
    response = client.post(
        "/api/experimental-results/import-csv",
        files={"file": ("results.csv", csv_text.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["accepted_count"] == 1
    assert body["rejected_count"] == 1
    assert body["invalid_rows"]


def test_result_batch_listing_and_csv_work():
    batch_id = _create_result().json()["result_batch_id"]
    listing = client.get("/api/experimental-results/batches")
    csv_response = client.get(f"/api/experimental-results/batches/{batch_id}/csv")
    assert listing.status_code == 200
    assert any(item["result_batch_id"] == batch_id for item in listing.json())
    assert csv_response.status_code == 200
    assert "assay_name" in csv_response.text


def test_feedback_comparison_works_with_manual_result():
    plan_id = _create_plan()
    result = _create_result(validation_plan_id=plan_id, source_type="validation_plan_followup")
    assert result.status_code == 200
    batch_id = result.json()["result_batch_id"]
    response = client.post(
        "/api/experimental-feedback/compare",
        json={"result_batch_id": batch_id, "validation_plan_id": plan_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["feedback_id"]
    assert body["compared_result_count"] == 1
    assert body["candidate_feedback"][0]["feedback_label"] in {
        "prediction_supported",
        "prediction_contradicted",
        "inconclusive",
        "not_comparable",
        "insufficient_context",
    }
    assert body["scientific_notice"] == "Experimental feedback summary only. Interpretation requires qualified scientific review."


def test_feedback_labels_are_conservative():
    plan_id = _create_plan()
    result = _create_result(validation_plan_id=plan_id)
    feedback = client.post("/api/experimental-feedback/compare", json={"result_batch_id": result.json()["result_batch_id"], "validation_plan_id": plan_id})
    assert feedback.status_code == 200
    serialized = str(feedback.json()).lower()
    assert "confirmed safe" not in serialized
    assert "clinically validated" not in serialized
    assert "drug approved" not in serialized


def test_validation_plan_followup_status_works():
    plan_id = _create_plan()
    result = _create_result(validation_plan_id=plan_id)
    feedback = client.post("/api/experimental-feedback/compare", json={"result_batch_id": result.json()["result_batch_id"], "validation_plan_id": plan_id})
    assert feedback.status_code == 200
    assert feedback.json()["validation_plan_followup_status"] in {
        "partially_completed",
        "feedback_generated",
        "results_entered",
        "no_results_entered",
    }


def test_lead_prioritization_feedback_works():
    lead = client.post(
        "/api/admet-leads/prioritize",
        json={
            "source_type": "manual",
            "candidates": [{"compound_name": "Aspirin", "smiles": ASPIRIN}],
            "include_trained_model": False,
            "include_domain": False,
            "include_explainability": False,
        },
    )
    assert lead.status_code == 200
    result = _create_result(results=[{
        "compound_name": "Aspirin",
        "smiles": ASPIRIN,
        "assay_name": "Solubility assay",
        "assay_category": "solubility",
        "result_direction": "favorable",
    }])
    feedback = client.post(
        "/api/experimental-feedback/compare",
        json={"result_batch_id": result.json()["result_batch_id"], "lead_prioritization_run_id": lead.json()["run_id"]},
    )
    assert feedback.status_code == 200
    assert feedback.json()["candidate_feedback"][0]["ranking_feedback"] in {
        "ranking_supported",
        "ranking_questioned",
        "ranking_inconclusive",
    }


def test_project_attachment_works():
    project = client.post("/api/projects/create", json={"title": "Experimental Feedback Project", "project_type": "general_research", "status": "active"}).json()
    result = _create_result(project_id=project["id"])
    assert result.status_code == 200
    feedback = client.post("/api/experimental-feedback/compare", json={"project_id": project["id"], "result_batch_id": result.json()["result_batch_id"]})
    assert feedback.status_code == 200
    detail = client.get(f"/api/projects/{project['id']}").json()
    assert any(item["item_type"] == "experimental_result_batch" for item in detail["items"])
    assert any(item["item_type"] == "experimental_feedback_summary" for item in detail["items"])


def test_research_export_includes_experimental_result_files(tmp_path, monkeypatch):
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")
    result = _create_result()
    feedback = client.post("/api/experimental-feedback/compare", json={"result_batch_id": result.json()["result_batch_id"]})
    assert feedback.status_code == 200
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
    assert any("EXPERIMENTAL_RESULTS/result_batches/" in name for name in names)
    assert any("EXPERIMENTAL_RESULTS/feedback_summaries/" in name for name in names)
    assert any("EXPERIMENTAL_RESULTS/scientific_notice.md" in name for name in names)


def test_report_json_endpoint_works():
    result = _create_result()
    feedback = client.post("/api/experimental-feedback/compare", json={"result_batch_id": result.json()["result_batch_id"]})
    feedback_id = feedback.json()["feedback_id"]
    report = client.get(f"/api/experimental-feedback/summaries/{feedback_id}/report.json")
    assert report.status_code == 200
    assert report.json()["feedback_id"] == feedback_id
    assert "does not simulate assay outcomes" in report.json()["no_fake_results_statement"]


def test_no_fake_experimental_results_are_generated():
    result = _create_result()
    serialized = str(result.json()).lower()
    assert "simulated" not in serialized
    assert "generated result" not in serialized
