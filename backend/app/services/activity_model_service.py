import hashlib
import json
import math
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from fastapi import HTTPException
from rdkit import Chem, DataStructs
from rdkit.Chem import rdMolDescriptors

from app.database import get_connection, init_db


SCIENTIFIC_NOTICE = (
    "Computational decision-support only. EGFR activity predictions are model predictions, "
    "not measured activity, clinical evidence, safety evidence, efficacy evidence, or regulatory evidence."
)
EXPECTED_EGFR_V2_MODEL_HASH = "7bd850e41d877a0d3c1c39dde42914ba67fa81142962c7ca7e67d7707f1b6c61"
EGFR_TARGET_KEY = "EGFR"
REQUIRED_FILES = [
    "model.joblib",
    "model_manifest.json",
    "feature_schema.json",
    "training_metadata.json",
    "metrics.json",
    "domain_reference.npz",
    "freeze_record.json",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _activity_root() -> Path:
    return _repo_root() / "backend" / "models" / "activity" / "egfr"


def _default_external_egfr_v2_dir() -> Path:
    return Path(os.getenv("DRUGDESIGN360_EGFR_V2_ARTIFACT_DIR", r"D:\DRUG CONJUGATE\DRUGDESIGN360_REAL_DATA\models\egfr_activity_v2"))


def _registry_manifest_path() -> Path:
    return _activity_root() / "egfr_p00533_pic50_rf_morgan_v2" / "registration_manifest.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path, default: Any | None = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {} if default is None else default


def _registered_artifact_dir() -> Path | None:
    manifest_path = _registry_manifest_path()
    if manifest_path.exists():
        manifest = _load_json(manifest_path)
        path = manifest.get("artifact_path") or manifest.get("source_artifact_path")
        if path:
            return Path(path)
    fallback = _default_external_egfr_v2_dir()
    return fallback if fallback.exists() else None


def _canonical_smiles(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles or "")
    if not mol:
        raise HTTPException(status_code=422, detail="Invalid SMILES: RDKit could not parse the molecule.")
    return Chem.MolToSmiles(mol, canonical=True)


def _fingerprint_bits(smiles: str, radius: int = 2, n_bits: int = 2048) -> np.ndarray:
    mol = Chem.MolFromSmiles(smiles)
    if not mol:
        raise HTTPException(status_code=422, detail="Invalid SMILES: RDKit could not parse the molecule.")
    fp = rdMolDescriptors.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)
    arr = np.zeros((n_bits,), dtype=np.uint8)
    DataStructs.ConvertToNumpyArray(fp, arr)
    return arr


def _is_egfr_target(target: str | None) -> bool:
    normalized = (target or "").strip().upper()
    return normalized in {"EGFR", "P00533", "CHEMBL203", "ERBB1", "HUMAN EGFR"}


def verify_egfr_v2_artifact(artifact_dir: str | Path | None = None) -> dict[str, Any]:
    folder = Path(artifact_dir) if artifact_dir else (_registered_artifact_dir() or _default_external_egfr_v2_dir())
    errors: list[str] = []
    hashes: dict[str, str] = {}
    for name in REQUIRED_FILES:
        path = folder / name
        if not path.exists():
            errors.append(f"{name} is missing.")
            continue
        hashes[name] = _sha256(path)
    if hashes.get("model.joblib") and hashes["model.joblib"] != EXPECTED_EGFR_V2_MODEL_HASH:
        errors.append("model.joblib SHA256 does not match the frozen EGFR v2 hash.")

    manifest = _load_json(folder / "model_manifest.json")
    freeze = _load_json(folder / "freeze_record.json")
    metrics = _load_json(folder / "metrics.json")
    if manifest.get("target") != "EGFR" or manifest.get("target_chembl_id") != "CHEMBL203":
        errors.append("Model manifest target identity is not EGFR/CHEMBL203.")
    if freeze.get("model_hash") != EXPECTED_EGFR_V2_MODEL_HASH:
        errors.append("Freeze record model hash does not match the frozen EGFR v2 hash.")
    if metrics.get("activation_gate", {}).get("decision") != "ACTIVATE_RECOMMENDED":
        errors.append("External activation gate did not recommend activation.")
    return {
        "valid": not errors,
        "artifact_dir": str(folder),
        "model_id": manifest.get("model_id") or "egfr_activity_v2",
        "model_name": manifest.get("model_name") or "EGFR activity model v2",
        "hashes": hashes,
        "errors": errors,
        "warnings": [
            "Observed 90% conformal interval coverage on BindingDB final holdout was 83.37%; report as undercoverage."
        ],
    }


def register_egfr_v2_artifact(source_dir: str | Path | None = None, copy_required_files: bool = False, overwrite: bool = False) -> dict[str, Any]:
    source = Path(source_dir) if source_dir else _default_external_egfr_v2_dir()
    verification = verify_egfr_v2_artifact(source)
    if not verification["valid"]:
        raise HTTPException(status_code=400, detail={"message": "EGFR v2 artifact verification failed.", "errors": verification["errors"]})

    target = _registry_manifest_path().parent
    target.mkdir(parents=True, exist_ok=True)
    artifact_path = source
    copied: list[str] = []
    if copy_required_files:
        artifact_path = target
        for name in REQUIRED_FILES:
            dst = target / name
            if dst.exists() and not overwrite:
                raise HTTPException(status_code=409, detail=f"{dst} already exists. Use overwrite only when intentionally replacing a registration copy.")
            shutil.copy2(source / name, dst)
            if _sha256(dst) != _sha256(source / name):
                raise HTTPException(status_code=500, detail=f"Hash mismatch after copying {name}.")
            copied.append(name)

    manifest = {
        "model_id": "egfr_activity_v2",
        "model_family": "activity",
        "target_key": EGFR_TARGET_KEY,
        "target_name": "EGFR",
        "target_gene_symbol": "EGFR",
        "uniprot_id": "P00533",
        "target_chembl_id": "CHEMBL203",
        "endpoint": "IC50",
        "transformed_label": "pIC50",
        "task_type": "regression",
        "model_version": "v2",
        "artifact_path": str(artifact_path),
        "source_artifact_path": str(source),
        "artifact_hash": EXPECTED_EGFR_V2_MODEL_HASH,
        "registered_at": _now(),
        "copied_files": copied,
        "verification": verification,
        "limitations": [
            "Target-specific EGFR/P00533/CHEMBL203 model only.",
            "Prediction is not a measured IC50.",
            "External validation is retrospective computational validation, not clinical validation.",
        ],
    }
    _registry_manifest_path().write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def egfr_activity_model_status() -> dict[str, Any]:
    registered = _registry_manifest_path().exists()
    artifact_dir = _registered_artifact_dir()
    verification = verify_egfr_v2_artifact(artifact_dir) if artifact_dir else {"valid": False, "errors": ["EGFR v2 artifact is not registered or discoverable."]}
    active = get_active_activity_model("EGFR")
    return {
        "implemented": True,
        "trained": verification.get("valid", False),
        "externally_validated": verification.get("valid", False),
        "active": active.get("status") == "ACTIVE",
        "clinical_validity": False,
        "research_use_only": True,
        "supported_target_count": 1,
        "supported_target": "EGFR/P00533/CHEMBL203",
        "registered": registered,
        "artifact_status": "usable" if verification.get("valid") else "invalid_or_missing",
        "activation_status": active.get("status"),
        "model_id": active.get("model_id") or "egfr_activity_v2",
        "artifact_dir": verification.get("artifact_dir"),
        "warnings": verification.get("warnings", []) + verification.get("errors", []),
        "scientific_notice": SCIENTIFIC_NOTICE,
    }


def evaluate_egfr_v2_activation_gate() -> dict[str, Any]:
    verification = verify_egfr_v2_artifact()
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str):
        checks.append({"name": name, "passed": passed, "detail": detail})

    folder = Path(verification["artifact_dir"])
    metrics = _load_json(folder / "metrics.json")
    freeze = _load_json(folder / "freeze_record.json")
    training = _load_json(folder / "training_metadata.json")
    bindingdb = metrics.get("bindingdb_final_holdout", {}).get("overall", {})
    chembl = metrics.get("chembl_test", {}).get("overall", {})
    activation = metrics.get("activation_gate", {})

    add("artifact_hash", verification["valid"], "Frozen artifact files and model hash must match.")
    add("target_identity", training.get("target") == "EGFR" and training.get("target_chembl_id") == "CHEMBL203", "Target identity must be EGFR/CHEMBL203.")
    add("dataset_lineage", bool(training.get("chembl_dataset_hash") and training.get("bindingdb_dataset_hash")), "ChEMBL and BindingDB hashes must be present.")
    add("split_lineage", bool(training.get("bindingdb_split_hash")), "BindingDB augmentation/final-holdout split hash must be present.")
    add("leakage_controls", training.get("final_holdout_not_used_before_freeze") is True, "Final holdout must not be used before freeze.")
    add("heldout_metrics", all(k in chembl for k in {"mae", "rmse", "r2", "pearson", "spearman"}), "ChEMBL TEST metrics must be present.")
    add("external_metrics", all(k in bindingdb for k in {"mae", "rmse", "r2", "pearson", "spearman"}), "BindingDB final-holdout metrics must be present.")
    add("beats_v1_external", float(bindingdb.get("rmse", 99)) < 1.7538 and float(bindingdb.get("r2", -99)) > -0.1610, "Must materially improve v1 external performance.")
    add("domain_metadata", bool(freeze.get("domain_thresholds")), "Frozen applicability-domain thresholds must be present.")
    add("uncertainty_metadata", (folder / "uncertainty_metadata.json").exists() and (folder / "conformal_metadata.json").exists(), "Uncertainty and conformal metadata must be present.")
    add("conformal_disclosed", abs(float(metrics.get("bindingdb_final_holdout", {}).get("conformal_coverage", 0)) - 0.8337489609310058) < 1e-9, "Observed conformal undercoverage must be preserved.")
    add("activation_recommended", activation.get("decision") == "ACTIVATE_RECOMMENDED", "External workflow gate must recommend activation.")

    passed = all(check["passed"] for check in checks)
    return {
        "model_id": "egfr_activity_v2",
        "target": "EGFR",
        "activation_state": "ACTIVATION_ELIGIBLE" if passed else "VALIDATION_FAILED",
        "checks": checks,
        "warnings": ["90% conformal interval observed coverage was 83.37%; activation is research-use with calibration warning."],
        "scientific_notice": SCIENTIFIC_NOTICE,
    }


def activate_egfr_v2(initiated_by: str = "local_api") -> dict[str, Any]:
    gate = evaluate_egfr_v2_activation_gate()
    if gate["activation_state"] != "ACTIVATION_ELIGIBLE":
        failed = [c["name"] for c in gate["checks"] if not c["passed"]]
        raise HTTPException(status_code=400, detail=f"Cannot activate EGFR v2 activity model: activation gate failed ({', '.join(failed)}).")
    init_db()
    with get_connection() as connection:
        previous = connection.execute("SELECT model_id FROM activity_active_models WHERE target_key = ?", (EGFR_TARGET_KEY,)).fetchone()
        previous_model_id = previous["model_id"] if previous and previous["model_id"] else None
        connection.execute(
            """
            INSERT OR REPLACE INTO activity_active_models (target_key, model_id, status, activated_at)
            VALUES (?, ?, 'ACTIVE', CURRENT_TIMESTAMP)
            """,
            (EGFR_TARGET_KEY, "egfr_activity_v2"),
        )
        connection.execute(
            """
            INSERT INTO activity_model_activation_history (
                target_key, previous_model_id, new_model_id, activation_state,
                validation_record_json, initiated_by, rollback_target_model_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (EGFR_TARGET_KEY, previous_model_id, "egfr_activity_v2", "ACTIVE", json.dumps(gate), initiated_by, previous_model_id),
        )
    return {"target": "EGFR", "model_id": "egfr_activity_v2", "status": "ACTIVE", "previous_model_id": previous_model_id, "activation_gate": gate}


def deactivate_activity_model(target: str = "EGFR", initiated_by: str = "local_api") -> dict[str, Any]:
    if not _is_egfr_target(target):
        raise HTTPException(status_code=404, detail="No target-specific activity model is registered for this target.")
    init_db()
    with get_connection() as connection:
        previous = connection.execute("SELECT model_id FROM activity_active_models WHERE target_key = ?", (EGFR_TARGET_KEY,)).fetchone()
        previous_model_id = previous["model_id"] if previous and previous["model_id"] else None
        connection.execute(
            """
            INSERT OR REPLACE INTO activity_active_models (target_key, model_id, status, activated_at)
            VALUES (?, '', 'DISABLED', CURRENT_TIMESTAMP)
            """,
            (EGFR_TARGET_KEY,),
        )
        connection.execute(
            """
            INSERT INTO activity_model_activation_history (
                target_key, previous_model_id, new_model_id, activation_state,
                validation_record_json, initiated_by, rollback_target_model_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (EGFR_TARGET_KEY, previous_model_id, "", "DISABLED", json.dumps({"reason": "deactivated"}), initiated_by, previous_model_id),
        )
    return {"target": "EGFR", "status": "DISABLED", "previous_model_id": previous_model_id}


def get_active_activity_model(target: str = "EGFR") -> dict[str, Any]:
    if not _is_egfr_target(target):
        return {"status": "UNAVAILABLE", "reason": "no active validated target-specific model"}
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM activity_active_models WHERE target_key = ?", (EGFR_TARGET_KEY,)).fetchone()
    if not row or row["status"] != "ACTIVE" or row["model_id"] != "egfr_activity_v2":
        return {"status": "UNAVAILABLE", "model_id": row["model_id"] if row else None, "reason": "EGFR v2 is not active."}
    verification = verify_egfr_v2_artifact()
    if not verification["valid"]:
        return {"status": "FAILED", "model_id": row["model_id"], "warnings": verification["errors"]}
    return {"status": "ACTIVE", "model_id": row["model_id"], "target": "EGFR", "artifact_dir": verification["artifact_dir"], "activated_at": row["activated_at"], "warnings": verification["warnings"]}


def _load_prediction_bundle() -> tuple[Any, dict[str, Any], dict[str, Any], dict[str, Any], np.lib.npyio.NpzFile]:
    active = get_active_activity_model("EGFR")
    if active.get("status") != "ACTIVE":
        raise HTTPException(status_code=400, detail="No active EGFR activity model is available.")
    folder = Path(active["artifact_dir"])
    return (
        joblib.load(folder / "model.joblib"),
        _load_json(folder / "model_manifest.json"),
        _load_json(folder / "metrics.json"),
        _load_json(folder / "freeze_record.json"),
        np.load(folder / "domain_reference.npz", allow_pickle=True),
    )


def predict_egfr_activity(smiles: str, target: str = "EGFR") -> dict[str, Any]:
    if not _is_egfr_target(target):
        return {"status": "unavailable", "reason": "no active validated target-specific model", "target": target, "scientific_notice": SCIENTIFIC_NOTICE}
    canonical = _canonical_smiles(smiles)
    model, manifest, metrics, freeze, domain = _load_prediction_bundle()
    feature = _fingerprint_bits(canonical).reshape(1, -1)
    predicted_pic50 = float(model.predict(feature)[0])
    tree_preds = [float(est.predict(feature)[0]) for est in getattr(model, "estimators_", [])]
    uncertainty = float(np.std(tree_preds)) if tree_preds else None

    train_bits = domain["train_bits"].astype(np.uint8)
    query = feature.astype(np.uint8)[0]
    intersection = np.logical_and(train_bits, query).sum(axis=1)
    union = np.logical_or(train_bits, query).sum(axis=1)
    sims = np.divide(intersection, union, out=np.zeros_like(intersection, dtype=float), where=union != 0)
    nearest = float(np.max(sims)) if len(sims) else None
    thresholds = freeze.get("domain_thresholds") or {}
    in_threshold = float(thresholds.get("in_domain", domain["in_domain_threshold"].item()))
    border_threshold = float(thresholds.get("borderline", domain["borderline_threshold"].item()))
    domain_status = "IN_DOMAIN" if nearest is not None and nearest >= in_threshold else "BORDERLINE" if nearest is not None and nearest >= border_threshold else "OUT_OF_DOMAIN"
    conformal = float(freeze.get("conformal_threshold") or 0)
    warnings = []
    if domain_status == "BORDERLINE":
        warnings.append("Borderline applicability domain: do not treat this as high-confidence activity evidence.")
    if domain_status == "OUT_OF_DOMAIN":
        warnings.append("Out-of-domain EGFR activity prediction: display only as low-reliability research output.")
    warnings.append("90% conformal interval observed 83.37% coverage on BindingDB final holdout; interval is under nominal coverage.")

    return {
        "status": "available",
        "target": "EGFR",
        "target_identifiers": {"gene_symbol": "EGFR", "uniprot_id": "P00533", "chembl_target_id": "CHEMBL203"},
        "endpoint": "IC50",
        "task_type": "regression",
        "canonical_smiles": canonical,
        "predicted_pIC50": predicted_pic50,
        "predicted_IC50_nM": float(math.pow(10, 9 - predicted_pic50)),
        "evidence_type": "MODEL_PREDICTION",
        "model_id": "egfr_activity_v2",
        "model_name": manifest.get("model_name"),
        "model_version": "v2",
        "artifact_hash": EXPECTED_EGFR_V2_MODEL_HASH,
        "dataset_lineage": {
            "sources": ["ChEMBL EGFR curated v2", "BindingDB augmentation subset"],
            "external_validation": "BindingDB final holdout",
        },
        "validation_status": "externally_validated_research_use",
        "activation_status": "ACTIVE",
        "nearest_training_similarity": nearest,
        "applicability_domain_status": domain_status,
        "domain_thresholds": {"in_domain": in_threshold, "borderline": border_threshold},
        "uncertainty_method": "random_forest_tree_prediction_standard_deviation",
        "uncertainty_value": uncertainty,
        "interval_nominal_coverage": 0.90,
        "interval_lower": predicted_pic50 - conformal,
        "interval_upper": predicted_pic50 + conformal,
        "external_observed_coverage": 0.8337,
        "calibration_warning": "Observed external conformal coverage was below nominal 90%.",
        "metrics_summary": {
            "chembl_test": metrics.get("chembl_test", {}).get("overall"),
            "bindingdb_final_holdout": metrics.get("bindingdb_final_holdout", {}).get("overall"),
        },
        "warnings": warnings,
        "limitations": manifest.get("limitations") or [],
        "scientific_notice": SCIENTIFIC_NOTICE,
    }


def batch_predict_egfr_activity(items: list[dict[str, Any]], target: str = "EGFR", max_batch: int = 100) -> dict[str, Any]:
    if len(items) > max_batch:
        raise HTTPException(status_code=422, detail=f"Batch size exceeds local maximum of {max_batch}.")
    results = []
    for index, item in enumerate(items, start=1):
        try:
            results.append({"index": index, "success": True, "input": item, "prediction": predict_egfr_activity(item.get("smiles") or "", target)})
        except Exception as exc:
            results.append({"index": index, "success": False, "input": item, "error": str(getattr(exc, "detail", exc))})
    return {"target": target, "count": len(items), "results": results, "scientific_notice": SCIENTIFIC_NOTICE}


def activation_history(target: str = "EGFR") -> list[dict[str, Any]]:
    if not _is_egfr_target(target):
        return []
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM activity_model_activation_history WHERE target_key = ? ORDER BY id DESC LIMIT 20",
            (EGFR_TARGET_KEY,),
        ).fetchall()
    return [dict(row) | {"validation_record": _load_json_text(row["validation_record_json"])} for row in rows]


def _load_json_text(value: str) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return value
