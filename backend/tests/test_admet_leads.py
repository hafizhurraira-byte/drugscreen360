import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.services import admet_explain_service, admet_training_service, admet_trained_model_service, research_export_service

client = TestClient(app)


def _prioritize(candidates, **extra):
    payload = {
        "source_type": "manual",
        "scoring_profile": "balanced_admet",
        "candidates": candidates,
        "include_trained_model": False,
        "include_domain": False,
        "include_explainability": False,
    }
    payload.update(extra)
    return client.post("/api/admet-leads/prioritize", json=payload)


def _csv(rows: int = 32) -> bytes:
    lines = ["compound_name,smiles,label"]
    smiles = ["CCO", "CCN", "CCC", "CCCl", "c1ccccc1", "CC(=O)O", "CC(C)O", "CCOC"]
    for index in range(rows):
        label = "active" if index % 2 else "inactive"
        lines.append(f"Lead Mol {index},{smiles[index % len(smiles)]},{label}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _train_and_activate(tmp_path, monkeypatch):
    monkeypatch.setattr(admet_training_service, "TRAINED_DIR", tmp_path / "trained")
    monkeypatch.setattr(admet_trained_model_service, "TRAINED_DIR", tmp_path / "trained")
    monkeypatch.setattr(admet_explain_service, "EXPLANATION_REPORT_DIR", tmp_path / "admet_explanation_reports")
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")
    upload = client.post(
        "/api/admet-datasets/upload",
        data={
            "dataset_name": "lead model dataset",
            "task_name": "hERG",
            "label_column": "label",
            "smiles_column": "smiles",
            "compound_name_column": "compound_name",
        },
        files={"file": ("lead.csv", _csv(), "text/csv")},
    )
    assert upload.status_code == 200
    dataset_id = upload.json()["dataset_id"]
    train = client.post("/api/admet-training/train", json={"dataset_id": dataset_id, "task_type": "binary_classification", "model_type": "random_forest"})
    assert train.status_code == 200
    model_id = train.json()["artifact"]["model_id"]
    activate = client.post(f"/api/admet-training/models/{model_id}/activate")
    assert activate.status_code == 200
    return model_id


def test_manual_candidate_prioritization_works():
    response = _prioritize([
        {"compound_name": "Aspirin", "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"},
        {"compound_name": "Caffeine", "smiles": "Cn1cnc2c1c(=O)n(C)c(=O)n2C"},
    ])
    assert response.status_code == 200
    body = response.json()
    assert body["candidate_count"] == 2
    assert body["ranked_count"] == 2
    assert body["scientific_notice"] == "Computational prioritization only. Requires experimental validation."
    assert body["ranked_candidates"][0]["rank"] == 1
    assert body["ranked_candidates"][0]["priority_label"] in {
        "high_priority_for_review",
        "medium_priority_for_review",
        "low_priority_for_review",
        "deprioritize",
        "insufficient_data",
    }


def test_invalid_smiles_are_excluded_with_warning():
    response = _prioritize([
        {"compound_name": "Invalid", "smiles": "not_a_smiles"},
        {"compound_name": "Ethanol", "smiles": "CCO"},
    ])
    assert response.status_code == 200
    body = response.json()
    assert body["ranked_count"] == 1
    assert body["excluded_count"] == 1
    invalid = next(item for item in body["ranked_candidates"] if item["excluded"])
    assert "Invalid SMILES" in invalid["exclusion_reason"]


def test_ranking_without_trained_model_uses_rule_based_data_only():
    client.post("/api/admet-training/models/deactivate")
    response = _prioritize(
        [{"compound_name": "Ethanol", "smiles": "CCO"}],
        include_trained_model=True,
        include_domain=True,
        include_explainability=True,
    )
    assert response.status_code == 200
    body = response.json()
    assert "trained model evidence not available" in body["warnings"]
    row = body["ranked_candidates"][0]
    assert row["trained_model_prediction"] is None
    assert row["domain_status"] == "not available"
    assert row["explainability_evidence_strength"] == "not available"


def test_ranking_with_trained_model_adds_domain_and_explainability(tmp_path, monkeypatch):
    _train_and_activate(tmp_path, monkeypatch)
    response = _prioritize(
        [{"compound_name": "Ethanol", "smiles": "CCO"}],
        include_trained_model=True,
        include_domain=True,
        include_explainability=True,
    )
    assert response.status_code == 200
    row = response.json()["ranked_candidates"][0]
    assert row["trained_model_prediction"] is not None
    assert row["domain_status"] in {"inside_domain", "borderline", "outside_domain", "not_available"}
    assert row["uncertainty_level"] in {"low", "moderate", "high", "unknown"}
    assert row["explainability_evidence_strength"] != "not available"


def test_outside_domain_candidate_receives_uncertainty_penalty(tmp_path, monkeypatch):
    _train_and_activate(tmp_path, monkeypatch)
    response = _prioritize(
        [{"compound_name": "Large polyaromatic", "smiles": "C1=CC=C2C(=C1)C3=CC=CC=C3C2C4=CC=CC=C4C5=CC=CC=C5"}],
        include_trained_model=True,
        include_domain=True,
        include_explainability=False,
    )
    assert response.status_code == 200
    row = response.json()["ranked_candidates"][0]
    if row["domain_status"] == "outside_domain":
        assert "domain_penalty" in row["score_components"]
    assert "raw_score" in row["score_components"]


def test_csv_and_json_export_work():
    run_id = _prioritize([{"compound_name": "Ethanol", "smiles": "CCO"}]).json()["run_id"]
    csv_response = client.get(f"/api/admet-leads/runs/{run_id}/csv")
    json_response = client.get(f"/api/admet-leads/runs/{run_id}/report.json")
    assert csv_response.status_code == 200
    assert "priority_label" in csv_response.text
    assert json_response.status_code == 200
    assert json_response.json()["run_id"] == run_id


def test_project_attachment_works():
    project = client.post("/api/projects/create", json={"title": "Lead Project", "project_type": "general_research", "status": "active"}).json()
    response = _prioritize([{"compound_name": "Ethanol", "smiles": "CCO"}], project_id=project["id"])
    assert response.status_code == 200
    detail = client.get(f"/api/projects/{project['id']}").json()
    assert any(item["item_type"] == "admet_lead_prioritization" for item in detail["items"])


def test_research_export_includes_lead_prioritization(tmp_path, monkeypatch):
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")
    response = _prioritize([{"compound_name": "Ethanol", "smiles": "CCO"}])
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
    assert any("ADMET_LEAD_PRIORITIZATION/runs/" in name for name in names)
    assert any("ADMET_LEAD_PRIORITIZATION/limitations.md" in name for name in names)
