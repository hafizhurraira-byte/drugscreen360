import copy
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pytest
from fastapi import HTTPException

from app import database
from app.services import admet_endpoint_model_service as service
from app.services.admet_lead_service import prioritize_leads
from app.models.admet_lead_models import LeadCandidateInput, LeadPrioritizationRequest


class TinyClassifier:
    def predict(self, x):
        return np.ones(x.shape[0], dtype=int)

    def predict_proba(self, x):
        return np.tile(np.array([[0.3, 0.7]]), (x.shape[0], 1))


class TinyRegressor:
    def predict(self, x):
        return np.full(x.shape[0], -2.4)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fake_artifact(tmp_path, endpoint="bbbp", task="classification", model=None, specificity=0.39215686274509803, recall=0.95, f1=0.88):
    folder = tmp_path / endpoint
    folder.mkdir()
    joblib.dump(model or (TinyClassifier() if task == "classification" else TinyRegressor()), folder / "model.joblib")
    _write_json(folder / "model_manifest.json", {
        "model_id": service.ENDPOINTS[endpoint]["model_id"],
        "task_type": task,
        "limitations": ["research-use-only baseline model"],
    })
    _write_json(folder / "feature_schema.json", {"feature_set": "morgan", "radius": 2, "bits": 2048, "feature_dimension": 2048})
    _write_json(folder / "training_metadata.json", {
        "split_enforced": True,
        "internal_resplitting_disabled": True,
        "dataset_hash": f"{endpoint}-dataset-hash",
        "split_hash": f"{endpoint}-split-hash",
    })
    test_metrics = {"recall": recall, "f1": f1, "specificity": specificity, "ece": 0.078, "auroc": 0.84, "auprc": {"value": 0.93}}
    _write_json(folder / "metrics.json", {
        "selected_validation_metrics": {"auprc": {"value": 0.9}},
        "test_metrics": test_metrics,
        "baseline_comparison": {"selected_beats_baseline": endpoint != "clintox_cttox"},
    })
    _write_json(folder / "split_reference.json", {"split_file": "", "partitions": {"TRAIN": []}})
    np.savez(folder / "domain_reference.npz", thresholds=np.array([0.4, 0.2]), train_nn=np.array([1.0]))
    _write_json(folder / "uncertainty_metadata.json", {"method": "tree_prediction_std"})
    _write_json(folder / "calibration_metadata.json", {"classification_calibration": "raw predicted probabilities", "conformal_interval": {"test_observed_coverage": 0.8616600790513834}})
    _write_json(folder / "freeze_record.json", {
        "model_hash_sha256": _hash(folder / "model.joblib"),
        "activation_gate": {"result": "NOT_ELIGIBLE" if endpoint == "clintox_cttox" else "ACTIVATION_ELIGIBLE"},
    })
    return folder


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "admet-endpoint.sqlite3")
    monkeypatch.setattr(service, "_manifest_path", lambda endpoint: tmp_path / "registry" / endpoint / service.ENDPOINTS[endpoint]["model_id"] / "registration_manifest.json")
    original = copy.deepcopy(service.ENDPOINTS)
    monkeypatch.setattr(service, "ENDPOINTS", original)
    return tmp_path


def test_register_gate_activate_history_and_deactivate_endpoint(isolated_registry):
    folder = _fake_artifact(isolated_registry, "bbbp")
    service.ENDPOINTS["bbbp"]["expected_hash"] = _hash(folder / "model.joblib")

    registration = service.register_admet_artifact("bbbp", folder)
    gate = service.evaluate_admet_activation_gate("bbbp")
    activated = service.activate_admet_endpoint("bbbp", initiated_by="pytest")
    status = service.admet_model_status("bbbp")
    deactivated = service.deactivate_admet_endpoint("bbbp", initiated_by="pytest")
    history = service.admet_activation_history("bbbp")["history"]

    assert registration["model_id"] == "bbbp_v1"
    assert gate["activation_state"] == "ACTIVATION_ELIGIBLE"
    assert activated["status"] == "ACTIVE"
    assert status["active"] is True
    assert deactivated["status"] == "DISABLED"
    assert len(history) == 2


def test_clintox_registered_but_activation_and_prediction_are_refused(isolated_registry):
    folder = _fake_artifact(isolated_registry, "clintox_cttox", recall=0.0, f1=0.0)
    service.ENDPOINTS["clintox_cttox"]["expected_hash"] = _hash(folder / "model.joblib")

    service.register_admet_artifact("clintox_cttox", folder)
    gate = service.evaluate_admet_activation_gate("clintox_cttox")
    prediction = service.predict_admet_endpoints("CCO", ["clintox_cttox"])["results"][0]

    assert gate["activation_state"] == "NOT_ELIGIBLE"
    assert prediction["status"] == "unavailable"
    assert prediction["reason"] == "model_failed_activation_gate"
    with pytest.raises(HTTPException):
        service.activate_admet_endpoint("clintox_cttox", initiated_by="pytest")


def test_prediction_contracts_include_lineage_domain_uncertainty_and_partial_batch(isolated_registry, monkeypatch):
    bbbp = _fake_artifact(isolated_registry, "bbbp")
    esol = _fake_artifact(isolated_registry, "esol", task="regression")
    for endpoint, folder in {"bbbp": bbbp, "esol": esol}.items():
        service.ENDPOINTS[endpoint]["expected_hash"] = _hash(folder / "model.joblib")
        service.register_admet_artifact(endpoint, folder)
        service.activate_admet_endpoint(endpoint, initiated_by="pytest")
    monkeypatch.setattr(service, "_domain_status", lambda *args, **kwargs: (0.55, "IN_DOMAIN"))

    single = service.predict_admet_endpoints("CCO", ["bbbp", "esol", "herg", "clintox_cttox"])
    batch = service.batch_predict_admet_endpoints([{"smiles": "CCO"}, {"smiles": "not-smiles"}], ["bbbp"])

    bbbp_result = next(item for item in single["results"] if item["endpoint"] == "bbbp")
    esol_result = next(item for item in single["results"] if item["endpoint"] == "esol")
    herg_result = next(item for item in single["results"] if item["endpoint"] == "herg")
    clintox_result = next(item for item in single["results"] if item["endpoint"] == "clintox_cttox")

    assert bbbp_result["status"] == "available"
    assert bbbp_result["evidence_type"] == "MODEL_PREDICTION"
    assert bbbp_result["dataset_hash"] == "bbbp-dataset-hash"
    assert bbbp_result["domain_status"] == "IN_DOMAIN"
    assert "probability_bbb_penetrant" in bbbp_result["prediction"]
    assert esol_result["prediction"]["model_derived_solubility_mol_L"] > 0
    assert herg_result["status"] == "unavailable"
    assert clintox_result["reason"] == "model_failed_activation_gate"
    assert batch["results"][0]["success"] is True
    assert batch["results"][1]["success"] is False


def test_missing_or_corrupt_artifact_fails_closed(isolated_registry):
    missing = service.verify_admet_artifact("bbbp", isolated_registry / "missing")
    folder = _fake_artifact(isolated_registry, "bbbp")
    service.ENDPOINTS["bbbp"]["expected_hash"] = "wrong-hash"
    corrupt = service.verify_admet_artifact("bbbp", folder)

    assert missing["valid"] is False
    assert corrupt["valid"] is False
    assert any("SHA256" in error for error in corrupt["errors"])


def test_candidate_ranking_uses_active_admet_without_clintox(monkeypatch):
    monkeypatch.setattr(
        "app.services.admet_lead_service.predict_admet_endpoints",
        lambda smiles, endpoints=None: {
            "results": [
                {"endpoint": "herg", "status": "available", "prediction": {"probability_herg_inhibitor": 0.8}, "domain_status": "IN_DOMAIN", "warnings": []},
                {"endpoint": "esol", "status": "available", "prediction": {"predicted_logS": -2.0}, "domain_status": "IN_DOMAIN", "warnings": []},
                {"endpoint": "clintox_cttox", "status": "unavailable", "reason": "model_failed_activation_gate", "warnings": ["ClinTox rejected"]},
            ]
        },
    )

    result = prioritize_leads(
        LeadPrioritizationRequest(
            candidates=[LeadCandidateInput(compound_name="Example", smiles="CCO", metadata={"target_name": "EGFR"})],
            include_trained_model=False,
            include_domain=False,
            include_explainability=False,
        )
    ).ranked_candidates[0]

    assert result.admet_model_predictions is not None
    assert "herg_model_risk_penalty" in result.score_components
    assert "ClinTox model rejected" in result.missing_evidence
