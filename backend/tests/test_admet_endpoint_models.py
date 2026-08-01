import copy
import hashlib
import json
from importlib.metadata import version as package_version
from pathlib import Path

import joblib
import numpy as np
import pytest
from fastapi import HTTPException

from app import database
from app.services import admet_endpoint_model_service as service
from app.services import admet_endpoint_external_evidence_service as external_service
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
        "package_versions": {"sklearn": package_version("scikit-learn")},
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
    if endpoint != "clintox_cttox":
        query = service._packed_query_fingerprint("CCO", {"feature_set": "morgan", "radius": 2, "bits": 2048, "feature_dimension": 2048})
        np.savez_compressed(
            folder / "domain_fingerprints.npz",
            packed_fingerprints=np.array([query], dtype=np.uint8),
            record_ids=np.array(["train_1"], dtype="<U7"),
            canonical_smiles_hashes=np.array(["hash_1"], dtype="<U64"),
            fingerprint_bit_length=np.array([2048], dtype=np.int32),
            fingerprint_count=np.array([1], dtype=np.int32),
            deterministic_order_hash=np.array(["order"], dtype="<U64"),
        )
        training = json.loads((folder / "training_metadata.json").read_text())
        schema = json.loads((folder / "feature_schema.json").read_text())
        domain_hash = _hash(folder / "domain_fingerprints.npz")
        schema_hash = service._schema_hash(schema, training, endpoint, service.ENDPOINTS[endpoint]["model_id"])
        _write_json(folder / "domain_reference_manifest.json", {
            "domain_reference_version": "m2c4_v1",
            "endpoint_key": endpoint,
            "model_id": service.ENDPOINTS[endpoint]["model_id"],
            "domain_artifact_filename": "domain_fingerprints.npz",
            "domain_artifact_sha256": domain_hash,
            "domain_schema_hash": schema_hash,
            "fingerprint_count": 1,
            "thresholds": [0.4, 0.2],
            "dataset_hash": training["dataset_hash"],
            "split_hash": training["split_hash"],
            "similarity_metric": "Tanimoto",
            "parity_validation": {"domain_label_mismatch_count": 0},
        })
        _write_json(folder / "domain_reference_freeze_record.json", {
            "thresholds_unchanged": True,
            "model_retrained": False,
            "model_modified": False,
        })
    return folder


def _fake_m2d1_ledger(tmp_path: Path) -> Path:
    payload = {
        "protocol": {"sha256": external_service.M2D1_PROTOCOL_HASH},
        "curation": [
            {"endpoint": "bbbp", "primary": 6146, "overlap": 1659},
            {"endpoint": "esol", "primary": 8882, "overlap": 1098},
            {"endpoint": "herg", "primary": 4171, "overlap": 73},
        ],
        "results": {
            "bbbp": {
                "model_hash": service.ENDPOINTS["bbbp"]["expected_hash"],
                "curated_dataset_hash": external_service.M2D1_COHORT_HASHES["bbbp"],
                "metrics": {"n": 6146, "auroc": 0.9121, "auprc": 0.9361, "f1": 0.8546, "recall": 0.9339, "specificity": 0.6435, "balanced_accuracy": 0.7887, "brier_score": 0.1219, "ece": 0.0529},
                "domain_metrics": {"IN_DOMAIN": {"auroc": 0.9462}, "OUT_OF_DOMAIN": {"auroc": 0.6552}},
                "independence_decision": "PROSPECTIVE_INDEPENDENT",
                "final_decision": "EXTERNAL_VALIDATION_SUPPORTS_ACTIVE",
                "activation_recommendation": "preserve_active_with_documented_external_validation_warning",
                "limitations": ["not proof of human CNS exposure"],
            },
            "esol": {
                "model_hash": service.ENDPOINTS["esol"]["expected_hash"],
                "curated_dataset_hash": external_service.M2D1_COHORT_HASHES["esol"],
                "metrics": {"n": 8882, "mae": 1.0270, "rmse": 1.4577, "r2": 0.6309, "pearson": 0.7961, "spearman": 0.7804, "residual_bias": 0.1285},
                "domain_metrics": {"IN_DOMAIN": {"rmse": 1.1893}, "OUT_OF_DOMAIN": {"rmse": 2.5884}},
                "conformal": {"nominal_coverage": 0.9, "external_observed_coverage": 0.6147, "internal_test_coverage": 0.8617},
                "independence_decision": "NON_OVERLAPPING_WITH_PROVENANCE_LIMITATION",
                "final_decision": "ACTIVE_WITH_STRONGER_WARNING",
                "activation_recommendation": "preserve_active_with_stronger_interval_warning",
                "limitations": ["interval undercoverage externally"],
            },
            "herg": {
                "model_hash": service.ENDPOINTS["herg"]["expected_hash"],
                "curated_dataset_hash": external_service.M2D1_COHORT_HASHES["herg"],
                "metrics": {"n": 4171, "auroc": 0.9003, "auprc": 0.7134, "f1": 0.5444, "recall": 0.8227, "specificity": 0.8058, "balanced_accuracy": 0.8143, "brier_score": 0.1490, "ece": 0.2665},
                "domain_metrics": {"IN_DOMAIN": {"auroc": 0.9261}, "OUT_OF_DOMAIN": {"auroc": 0.7675}},
                "independence_decision": "NON_OVERLAPPING_WITH_PROVENANCE_LIMITATION",
                "final_decision": "RECALIBRATION_RECOMMENDED",
                "activation_recommendation": "preserve_active_but_review_recalibration",
                "limitations": ["raw probabilities are poorly calibrated externally"],
            },
        },
    }
    path = tmp_path / "m2d1_master_results.json"
    _write_json(path, payload)
    return path


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "admet-endpoint.sqlite3")
    monkeypatch.setattr(service, "_manifest_path", lambda endpoint: tmp_path / "registry" / endpoint / service.ENDPOINTS[endpoint]["model_id"] / "registration_manifest.json")
    original = copy.deepcopy(service.ENDPOINTS)
    monkeypatch.setattr(service, "ENDPOINTS", original)
    service.clear_domain_reference_cache()
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
    assert status["compact_domain_reference_verified"] is True
    assert status["domain_reference_count"] == 1
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


def test_m2d1_external_evidence_import_status_prediction_and_idempotency(isolated_registry):
    folders = {
        "bbbp": _fake_artifact(isolated_registry, "bbbp"),
        "esol": _fake_artifact(isolated_registry, "esol", task="regression"),
        "herg": _fake_artifact(isolated_registry, "herg"),
    }
    for endpoint, folder in folders.items():
        service.ENDPOINTS[endpoint]["expected_hash"] = _hash(folder / "model.joblib")
        service.register_admet_artifact(endpoint, folder)
        service.activate_admet_endpoint(endpoint, initiated_by="pytest")

    ledger = _fake_m2d1_ledger(isolated_registry)
    dry_run = external_service.import_m2d1_external_validation(ledger)
    first = external_service.import_m2d1_external_validation(ledger, dry_run=False, imported_by="pytest")
    second = external_service.import_m2d1_external_validation(ledger, dry_run=False, imported_by="pytest")
    status = service.admet_model_status("herg")
    prediction = service.predict_admet_endpoints("CCO", ["bbbp", "esol", "herg", "clintox_cttox"])["results"]

    assert {item["endpoint"] for item in dry_run["imported"]} == {"bbbp", "esol", "herg"}
    assert len(first["imported"]) == 3
    assert len(second["skipped"]) == 3
    assert status["active"] is True
    assert status["external_evidence_decision"] == "RECALIBRATION_RECOMMENDED"
    assert status["warning_severity"] == "STRONG_WARNING"
    bbbp = next(item for item in prediction if item["endpoint"] == "bbbp")
    esol = next(item for item in prediction if item["endpoint"] == "esol")
    herg = next(item for item in prediction if item["endpoint"] == "herg")
    clintox = next(item for item in prediction if item["endpoint"] == "clintox_cttox")
    assert bbbp["external_validation"]["evidence_decision"] == "EXTERNAL_VALIDATION_SUPPORTS_ACTIVE"
    assert esol["external_validation"]["calibration_summary"]["external_observed_coverage"] == pytest.approx(0.6147)
    assert any("61.47%" in warning for warning in esol["warnings"])
    assert herg["external_validation"]["key_metrics"]["ece"] == pytest.approx(0.2665)
    assert any("recalibration" in warning.lower() for warning in herg["warnings"])
    assert clintox["status"] == "unavailable"
    assert clintox["external_validation"]["available"] is False


def test_m2d1_external_evidence_rejects_integrity_mismatches(isolated_registry):
    service.ENDPOINTS["bbbp"]["expected_hash"] = "expected-model-hash"
    ledger = _fake_m2d1_ledger(isolated_registry)
    payload = json.loads(ledger.read_text())
    payload["protocol"]["sha256"] = "wrong"
    _write_json(ledger, payload)

    with pytest.raises(HTTPException):
        external_service.import_m2d1_external_validation(ledger, endpoints=["bbbp"])

    payload["protocol"]["sha256"] = external_service.M2D1_PROTOCOL_HASH
    payload["results"]["bbbp"]["model_hash"] = "wrong"
    _write_json(ledger, payload)
    with pytest.raises(HTTPException):
        external_service.import_m2d1_external_validation(ledger, endpoints=["bbbp"])


def test_missing_or_corrupt_artifact_fails_closed(isolated_registry):
    missing = service.verify_admet_artifact("bbbp", isolated_registry / "missing")
    folder = _fake_artifact(isolated_registry, "bbbp")
    service.ENDPOINTS["bbbp"]["expected_hash"] = "wrong-hash"
    corrupt = service.verify_admet_artifact("bbbp", folder)

    assert missing["valid"] is False
    assert corrupt["valid"] is False
    assert any("SHA256" in error for error in corrupt["errors"])


def test_compact_domain_reference_failure_modes_fail_closed(isolated_registry):
    folder = _fake_artifact(isolated_registry, "bbbp")
    service.ENDPOINTS["bbbp"]["expected_hash"] = _hash(folder / "model.joblib")
    (folder / "domain_fingerprints.npz").unlink()
    missing = service.verify_admet_artifact("bbbp", folder)

    folder = _fake_artifact(isolated_registry, "esol", task="regression")
    service.ENDPOINTS["esol"]["expected_hash"] = _hash(folder / "model.joblib")
    manifest = json.loads((folder / "domain_reference_manifest.json").read_text())
    manifest["domain_schema_hash"] = "wrong"
    _write_json(folder / "domain_reference_manifest.json", manifest)
    wrong_schema = service.verify_admet_artifact("esol", folder)

    assert missing["valid"] is False
    assert any("domain_fingerprints.npz" in error for error in missing["errors"])
    assert wrong_schema["valid"] is False
    assert any("schema" in error.lower() for error in wrong_schema["errors"])


def test_compact_domain_cache_reuse_and_clear(isolated_registry, monkeypatch):
    folder = _fake_artifact(isolated_registry, "bbbp")
    service.ENDPOINTS["bbbp"]["expected_hash"] = _hash(folder / "model.joblib")
    service.register_admet_artifact("bbbp", folder)
    service.activate_admet_endpoint("bbbp", initiated_by="pytest")
    service.predict_admet_endpoints("CCO", ["bbbp"])

    assert len(service._DOMAIN_CACHE) == 1
    service.clear_domain_reference_cache("bbbp")
    assert len(service._DOMAIN_CACHE) == 0


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
