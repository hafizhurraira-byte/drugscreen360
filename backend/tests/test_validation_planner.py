import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.services import research_export_service

client = TestClient(app)


def _create_plan(candidates, **extra):
    payload = {
        "source_type": "manual",
        "plan_title": "Test Validation Plan",
        "candidates": candidates,
        "include_toxicity_assays": True,
        "include_adme_assays": True,
        "include_target_assays": True,
        "include_controls": True,
    }
    payload.update(extra)
    return client.post("/api/validation-planner/create", json=payload)


def test_manual_validation_plan_works():
    response = _create_plan([
        {"compound_name": "Aspirin", "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"},
    ])
    assert response.status_code == 200
    body = response.json()
    assert body["candidate_count"] == 1
    assert body["scientific_notice"] == "Experimental planning support only. Actual assay design must be reviewed by qualified laboratory personnel."
    assays = body["candidate_plans"][0]["recommended_assays"]
    assert assays
    assert all("assay_result" not in assay for assay in assays)


def test_invalid_smiles_handled_safely():
    response = _create_plan([
        {"compound_name": "Invalid", "smiles": "not_a_smiles"},
    ])
    assert response.status_code == 200
    candidate = response.json()["candidate_plans"][0]
    assert candidate["valid"] is False
    assert "Invalid SMILES" in candidate["invalid_reason"]
    assert candidate["recommended_assays"][0]["assay_category"] == "Data readiness"


def test_toxicity_risk_recommends_toxicity_assay():
    response = _create_plan([
        {
            "compound_name": "Nitrobenzene",
            "smiles": "O=[N+]([O-])c1ccccc1",
            "metadata": {
                "rule_based_admet_summary": {
                    "concern_level": "High",
                    "structural_alert_risk": "High",
                    "solubility_risk": "Medium",
                    "absorption_risk": "Medium",
                }
            },
        }
    ])
    assert response.status_code == 200
    assays = response.json()["candidate_plans"][0]["recommended_assays"]
    names = {assay["assay_name"] for assay in assays}
    assert "Cytotoxicity / cell viability assay" in names
    assert "Ames test / in vitro genotoxicity package" in names
    assert any(assay["recommendation_priority"] == "essential" for assay in assays if assay["assay_category"] in {"Cytotoxicity", "Genotoxicity"})


def test_outside_domain_candidate_gets_strong_warning():
    response = _create_plan([
        {
            "compound_name": "Outside domain candidate",
            "smiles": "CCO",
            "domain_status": "outside_domain",
            "uncertainty_level": "high",
            "evidence_strength": "weak_internal",
            "priority_label": "high_priority_for_review",
        }
    ])
    assert response.status_code == 200
    candidate = response.json()["candidate_plans"][0]
    assert any("outside the model applicability domain" in warning for warning in candidate["warnings"])
    assert any(assay["assay_name"] == "Orthogonal confirmatory ADMET panel" for assay in candidate["recommended_assays"])


def test_insufficient_data_candidate_recommends_data_completion():
    response = _create_plan([
        {"compound_name": "Needs data", "smiles": "CCO", "priority_label": "insufficient_data"},
    ])
    assert response.status_code == 200
    assays = response.json()["candidate_plans"][0]["recommended_assays"]
    assert any(assay["assay_name"] == "Data completion and compound identity confirmation" for assay in assays)


def test_lead_prioritization_linked_plan_works():
    lead = client.post(
        "/api/admet-leads/prioritize",
        json={
            "source_type": "manual",
            "candidates": [{"compound_name": "Ethanol", "smiles": "CCO"}],
            "include_trained_model": False,
            "include_domain": False,
            "include_explainability": False,
        },
    )
    assert lead.status_code == 200
    response = client.post(
        "/api/validation-planner/create",
        json={
            "source_type": "lead_prioritization",
            "source_run_id": lead.json()["run_id"],
            "plan_title": "Lead-linked plan",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_type"] == "lead_prioritization"
    assert body["candidate_plans"][0]["priority_label"] is not None


def test_json_and_csv_endpoints_work():
    plan_id = _create_plan([{"compound_name": "Ethanol", "smiles": "CCO"}]).json()["plan_id"]
    json_response = client.get(f"/api/validation-planner/plans/{plan_id}/report.json")
    csv_response = client.get(f"/api/validation-planner/plans/{plan_id}/csv")
    assert json_response.status_code == 200
    assert json_response.json()["plan_id"] == plan_id
    assert json_response.json()["assay_result_status"].startswith("No experimental assay results")
    assert csv_response.status_code == 200
    assert "assay_name" in csv_response.text


def test_project_attachment_works():
    project = client.post("/api/projects/create", json={"title": "Validation Project", "project_type": "general_research", "status": "active"}).json()
    response = _create_plan(
        [{"compound_name": "Ethanol", "smiles": "CCO"}],
        project_id=project["id"],
    )
    assert response.status_code == 200
    detail = client.get(f"/api/projects/{project['id']}").json()
    assert any(item["item_type"] == "experimental_validation_plan" for item in detail["items"])


def test_research_export_includes_validation_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")
    response = _create_plan([{"compound_name": "Ethanol", "smiles": "CCO"}])
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
    assert any("EXPERIMENTAL_VALIDATION_PLANS/plans/" in name for name in names)
    assert any("EXPERIMENTAL_VALIDATION_PLANS/safety_notice.md" in name for name in names)


def test_no_fake_assay_results_are_generated():
    response = _create_plan([{"compound_name": "Ethanol", "smiles": "CCO"}])
    assert response.status_code == 200
    serialized = str(response.json()).lower()
    assert "observed_result" not in serialized
    assert "measured_value" not in serialized
    assert "assay_result" not in serialized
