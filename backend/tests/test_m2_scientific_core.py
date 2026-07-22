from fastapi.testclient import TestClient

from app.main import app
from app.services import m2_scientific_core_service


client = TestClient(app)


def test_m2_status_exposes_multi_endpoint_admet_metadata(monkeypatch):
    monkeypatch.setattr(
        m2_scientific_core_service,
        "discover_trained_models",
        lambda: [
            {
                "model_id": "tox_model_1",
                "task_name": "toxicity_concern",
                "task_type": "binary_classification",
                "status": "valid",
            }
        ],
    )
    monkeypatch.setattr(
        m2_scientific_core_service,
        "get_active_trained_model_info",
        lambda: {"status": "available", "model_id": "tox_model_1"},
    )

    body = client.get("/api/m2/admet/endpoints").json()
    tox = next(item for item in body if item["endpoint_id"] == "toxicity_concern")
    herg = next(item for item in body if item["endpoint_id"] == "herg_cardiotoxicity")

    assert tox["status"] == "active"
    assert tox["activation_policy_id"] == "admet_toxicity_concern_v1"
    assert tox["applicability_domain_required"] is True
    assert herg["status"] == "unavailable"
    assert "No trained local model" in herg["limitations"][0]


def test_activation_gate_passes_and_fails_family_specific_policy():
    good = client.post(
        "/api/m2/activation-gate/evaluate",
        json={
            "model_family": "admet_toxicity",
            "metadata": {
                "dataset_version": "dataset-sha",
                "sample_count": 80,
                "split_integrity_status": "passed",
                "leakage_status": "passed",
                "metrics": {"balanced_accuracy": 0.7, "precision": 0.7, "recall": 0.6, "f1": 0.65},
                "random_state": 42,
                "feature_schema": {"feature_columns": ["molecular_weight"]},
                "applicability_domain_status": "available",
            },
        },
    ).json()
    bad = client.post(
        "/api/m2/activation-gate/evaluate",
        json={"model_family": "activity", "metadata": {"sample_count": 10, "metrics": {}}},
    ).json()

    assert good["activation_state"] == "ACTIVATION_ELIGIBLE"
    assert bad["activation_state"] == "VALIDATION_FAILED"
    assert any(not check["passed"] and check["name"] == "external_validation" for check in bad["checks"])


def test_split_integrity_detects_record_and_scaffold_leakage():
    body = client.post(
        "/api/m2/split-integrity/check",
        json={
            "records": [
                {"smiles": "CCO", "partition": "train", "label": 0},
                {"smiles": "CCO", "partition": "test", "label": 0},
                {"smiles": "c1ccccc1", "partition": "validation", "label": 1},
                {"smiles": "not-smiles", "partition": "train", "label": 1},
                {"smiles": "CCN", "partition": "unknown", "label": 1},
            ]
        },
    ).json()

    assert body["status"] == "failed"
    assert body["duplicate_count"] == 1
    assert body["overlap_pairs"][0]["overlap_count"] == 1
    assert body["rejected_records"]
    assert body["dataset_version_hash"]
    assert body["split_hash"]


def test_applicability_domain_uses_real_morgan_similarity():
    body = client.post(
        "/api/m2/applicability-domain/assess",
        json={"query_smiles": "CCO", "training_smiles": ["CCO", "CCN", "c1ccccc1"], "threshold": 0.35},
    ).json()

    assert body["method"] == "morgan_fingerprint_nearest_neighbor"
    assert body["nearest_similarity"] == 1.0
    assert body["domain_status"] == "in_domain"
    assert body["fingerprint_parameters"]["radius"] == 2


def test_uncertainty_contract_does_not_create_fake_confidence():
    no_probability = client.post(
        "/api/m2/uncertainty/contract",
        json={"prediction": {"prediction_label": "toxic", "model_id": "m1", "model_version": "v1"}},
    ).json()
    outside_domain = client.post(
        "/api/m2/uncertainty/contract",
        json={"prediction": {"prediction_label": "toxic", "probability": 0.95, "domain_status": "out_of_domain", "calibration_status": "calibration_good"}},
    ).json()

    assert no_probability["confidence"] == "not_available"
    assert "No probability" in no_probability["warnings"][0]
    assert outside_domain["confidence"] == "low"
    assert outside_domain["uncertainty"] == "high"


def test_future_provider_contracts_are_explicitly_not_implemented():
    providers = client.get("/api/m2/future-providers/status").json()
    assert {item["provider_type"] for item in providers} >= {"DockingProvider", "MDProvider", "MoleculeGenerator", "LeadOptimizer"}
    assert all(item["status"] == "not_implemented" for item in providers)


def test_async_job_lifecycle_contract_is_available_without_changing_execution():
    body = client.get("/api/m2/jobs/lifecycle").json()
    assert body["lifecycle"] == ["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]
    assert "model_training" in body["covered_operations"]
    assert "input_snapshot" in body["required_metadata"]
    assert body["status"] == "contract_defined_synchronous_execution_preserved"


def test_candidate_ranking_explanation_reports_missing_dimensions_without_fake_scores():
    body = client.post(
        "/api/m2/ranking/explain",
        json={"candidate": {"compound_name": "Aspirin", "admet": {"rule_based": "review"}}, "scoring_profile": "balanced_admet"},
    ).json()

    unavailable = [item for item in body["dimensions"] if item["status"] == "unavailable"]
    assert body["compound_name"] == "Aspirin"
    assert unavailable
    assert "No real evidence" in unavailable[0]["limitation"]


def test_repurposing_candidate_classification_distinguishes_sources():
    approved = client.post("/api/m2/repurposing/classify", json={"candidate": {"max_phase": 4}}).json()
    predicted = client.post("/api/m2/repurposing/classify", json={"candidate": {"trained_model_prediction": {"model_available": True}}}).json()
    generated = client.post("/api/m2/repurposing/classify", json={"candidate": {"source_type": "generated"}}).json()

    assert approved["candidate_type"] == "approved_drug"
    assert predicted["candidate_type"] == "predicted_candidate"
    assert generated["candidate_type"] == "generated_molecule"
    assert generated["warnings"]


def test_scientific_core_status_lists_unsupported_capabilities():
    body = client.get("/api/m2/scientific-core/status").json()
    assert body["m2_status"] == "drug_discovery_scientific_core_hardening"
    assert "docking" in body["unsupported_capabilities"]
    assert "computational decision-support only" in body["scientific_notice"].lower()
