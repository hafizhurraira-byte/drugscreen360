import hashlib
import json
import math
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from fastapi import HTTPException
from rdkit import Chem, DataStructs
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdFingerprintGenerator

from app.database import get_connection, init_db
from app.services.admet_endpoint_external_evidence_service import (
    external_warning_messages,
    get_latest_endpoint_external_evidence,
    unavailable_external_evidence,
)
from app.services.scientific_engine_registry_service import sklearn_joblib_compatibility


SCIENTIFIC_NOTICE = (
    "Computational decision-support only. ADMET model predictions are not measured properties, "
    "clinical safety evidence, efficacy evidence, regulatory evidence, or experimental validation."
)
REQUIRED_FILES = [
    "model.joblib",
    "model_manifest.json",
    "metrics.json",
    "feature_schema.json",
    "training_metadata.json",
    "split_reference.json",
    "domain_reference.npz",
    "uncertainty_metadata.json",
    "calibration_metadata.json",
    "freeze_record.json",
]
COMPACT_DOMAIN_FILES = ["domain_fingerprints.npz", "domain_reference_manifest.json", "domain_reference_freeze_record.json"]

ENDPOINTS: dict[str, dict[str, Any]] = {
    "bbbp": {
        "display_name": "Blood-Brain Barrier Penetration",
        "task_type": "binary_classification",
        "prediction_label": "bbb_penetrant",
        "version": "v1",
        "model_id": "bbbp_v1",
        "expected_hash": "e08d91c7febb4b8cc82ca71c7b46ff8afccb6d12debd217f9b563c13bee8500b",
        "external_dir": "bbbp_v1",
        "eligible": True,
        "mandatory_warnings": [
            "BBBP TEST specificity was 0.3922; do not describe this model as highly specific.",
            "Benchmark BBBP classification only; not proof of human CNS exposure.",
        ],
    },
    "esol": {
        "display_name": "Aqueous Solubility",
        "task_type": "regression",
        "prediction_label": "logS",
        "units": "log10 mol/L",
        "version": "v1",
        "model_id": "esol_v1",
        "expected_hash": "c91ac8c3c5cec08dd1cb4417c969e18cdb1ef0148d599c4badbc72db093fec10",
        "external_dir": "esol_v1",
        "eligible": True,
        "mandatory_warnings": [
            "ESOL nominal 90% interval achieved 86.17% TEST coverage; do not claim validated 90% coverage.",
            "Model-derived logS is not a measured solubility result.",
        ],
    },
    "herg": {
        "display_name": "hERG Inhibition Concern",
        "task_type": "binary_classification",
        "prediction_label": "herg_inhibitor",
        "version": "v1",
        "model_id": "herg_v1",
        "expected_hash": "0e0d07a5347c6027c12e2b86946588eb3c66330a80df499fda7a92d3c6721081",
        "external_dir": "herg_v1",
        "eligible": True,
        "mandatory_warnings": [
            "hERG TEST N=65; small-test-set limitation must be reviewed.",
            "hERG TEST ECE was 0.1385; calibration is imperfect.",
            "Low predicted hERG risk is not cardiac safety clearance.",
        ],
    },
    "clintox_cttox": {
        "display_name": "ClinTox Toxicity Concern",
        "task_type": "binary_classification",
        "prediction_label": "toxicity_concern",
        "version": "v1",
        "model_id": "clintox_cttox_v1",
        "expected_hash": "524e68e123b6478a1e50ba8df48625beebf7007138f8b8401a2105d895cdb1c7",
        "external_dir": "clintox_cttox_v1",
        "eligible": False,
        "mandatory_warnings": [
            "ClinTox TEST recall was 0 and F1 was 0; this is a hard activation blocker.",
            "ClinTox is registered for transparency only and must not provide production predictions.",
        ],
    },
}
_DOMAIN_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}
_DOMAIN_CACHE_LOCK = threading.Lock()
_MAX_DOMAIN_CACHE_ENTRIES = 4
_MAX_DOMAIN_REFERENCE_BYTES = 25 * 1024 * 1024


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _registration_root() -> Path:
    return _repo_root() / "backend" / "models" / "admet"


def _manifest_path(endpoint: str) -> Path:
    spec = _spec(endpoint)
    return _registration_root() / endpoint / spec["model_id"] / "registration_manifest.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clear_domain_reference_cache(endpoint: str | None = None) -> None:
    with _DOMAIN_CACHE_LOCK:
        if endpoint is None:
            _DOMAIN_CACHE.clear()
        else:
            for key in [item for item in _DOMAIN_CACHE if item[0] == endpoint]:
                _DOMAIN_CACHE.pop(key, None)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _spec(endpoint: str) -> dict[str, Any]:
    key = (endpoint or "").strip().lower()
    if key not in ENDPOINTS:
        raise HTTPException(status_code=404, detail=f"Unsupported ADMET endpoint: {endpoint}")
    return ENDPOINTS[key]


def _artifact_dir(endpoint: str) -> Path | None:
    manifest = _load_json(_manifest_path(endpoint))
    path = manifest.get("artifact_path") or manifest.get("source_artifact_path")
    return Path(path) if path else None


def _canonical(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles or "")
    if not mol:
        raise HTTPException(status_code=422, detail="Invalid SMILES: RDKit could not parse the molecule.")
    return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)


def _features(smiles: str, schema: dict[str, Any]) -> np.ndarray:
    mol = Chem.MolFromSmiles(smiles)
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=int(schema.get("radius", 2)), fpSize=int(schema.get("bits", 2048)))
    fp = gen.GetFingerprint(mol)
    arr = np.zeros((int(schema.get("bits", 2048)),), dtype=np.float32)
    DataStructs.ConvertToNumpyArray(fp, arr)
    if schema.get("feature_set") == "morgan_desc":
        desc = np.array([
            Descriptors.MolWt(mol),
            Crippen.MolLogP(mol),
            Descriptors.TPSA(mol),
            Lipinski.NumHDonors(mol),
            Lipinski.NumHAcceptors(mol),
            Lipinski.NumRotatableBonds(mol),
            Lipinski.RingCount(mol),
            Lipinski.FractionCSP3(mol),
        ], dtype=np.float32)
        arr = np.concatenate([arr, desc])
    if int(schema.get("feature_dimension", len(arr))) != len(arr):
        raise HTTPException(status_code=500, detail="Feature dimension mismatch for registered ADMET model.")
    return arr.reshape(1, -1)


def verify_admet_artifact(endpoint: str, artifact_dir: str | Path | None = None) -> dict[str, Any]:
    spec = _spec(endpoint)
    folder = Path(artifact_dir) if artifact_dir else _artifact_dir(endpoint)
    errors: list[str] = []
    hashes: dict[str, str] = {}
    if not folder or not folder.exists():
        return {"endpoint": endpoint, "valid": False, "errors": ["Artifact directory is not registered or does not exist."], "hashes": {}, "warnings": spec["mandatory_warnings"]}
    for name in REQUIRED_FILES:
        path = folder / name
        if not path.exists():
            errors.append(f"{name} is missing.")
        else:
            hashes[name] = _sha256(path)
    if spec["eligible"]:
        for name in COMPACT_DOMAIN_FILES:
            path = folder / name
            if not path.exists():
                errors.append(f"{name} is missing.")
            else:
                hashes[name] = _sha256(path)
    if hashes.get("model.joblib") != spec["expected_hash"]:
        errors.append("model.joblib SHA256 does not match the frozen expected hash.")
    manifest = _load_json(folder / "model_manifest.json")
    feature_schema = _load_json(folder / "feature_schema.json")
    training = _load_json(folder / "training_metadata.json")
    compatibility = sklearn_joblib_compatibility(training, hashes.get("model.joblib") == spec["expected_hash"])
    metrics = _load_json(folder / "metrics.json")
    freeze = _load_json(folder / "freeze_record.json")
    domain_manifest = _load_json(folder / "domain_reference_manifest.json")
    domain_freeze = _load_json(folder / "domain_reference_freeze_record.json")
    if manifest.get("model_id") != spec["model_id"]:
        errors.append("model_manifest.json model_id does not match endpoint.")
    if manifest.get("task_type") != ("classification" if spec["task_type"] == "binary_classification" else "regression"):
        errors.append("model_manifest.json task_type does not match endpoint.")
    if not training.get("split_enforced") or not training.get("internal_resplitting_disabled"):
        errors.append("Frozen split enforcement metadata is missing.")
    if not training.get("dataset_hash") or not training.get("split_hash"):
        errors.append("Dataset/split lineage is incomplete.")
    if hashes.get("model.joblib") == spec["expected_hash"] and not compatibility["execution_allowed"]:
        errors.append(f"model_runtime_version_mismatch: {compatibility['compatibility_reason']}")
    if not feature_schema.get("feature_dimension"):
        errors.append("Feature schema is incomplete.")
    if spec["eligible"]:
        if domain_manifest.get("endpoint_key") != endpoint or domain_manifest.get("model_id") != spec["model_id"]:
            errors.append("Compact domain reference endpoint/model metadata does not match.")
        if domain_manifest.get("domain_schema_hash") != _schema_hash(feature_schema, training, endpoint, manifest.get("model_id")):
            errors.append("Compact domain reference schema hash does not match model feature schema.")
        if domain_manifest.get("domain_artifact_sha256") and hashes.get("domain_fingerprints.npz") != domain_manifest.get("domain_artifact_sha256"):
            errors.append("Compact domain reference SHA256 does not match manifest.")
        if domain_manifest.get("dataset_hash") != training.get("dataset_hash") or domain_manifest.get("split_hash") != training.get("split_hash"):
            errors.append("Compact domain reference lineage does not match model training metadata.")
        if domain_manifest.get("parity_validation", {}).get("domain_label_mismatch_count") not in {0, None}:
            errors.append("Compact domain parity validation reported domain-label mismatches.")
        if domain_freeze.get("model_retrained") is not False or domain_freeze.get("thresholds_unchanged") is not True:
            errors.append("Compact domain freeze amendment is incomplete.")
    if not metrics.get("test_metrics") or not metrics.get("selected_validation_metrics"):
        errors.append("Validation or TEST metrics are missing.")
    gate = (freeze.get("activation_gate") or {}).get("result")
    if spec["eligible"] and gate != "ACTIVATION_ELIGIBLE":
        errors.append("Frozen external gate was not activation eligible.")
    if not spec["eligible"] and gate not in {"NOT_ELIGIBLE", "VALIDATION_FAILED"}:
        errors.append("Rejected endpoint does not carry a rejected gate state.")
    return {
        "endpoint": endpoint,
        "model_id": spec["model_id"],
        "valid": not errors,
        "artifact_dir": str(folder),
        "hashes": hashes,
        "errors": errors,
        "warnings": spec["mandatory_warnings"],
        "manifest": manifest,
        "feature_schema": feature_schema,
        "training_metadata": training,
        "metrics": metrics,
        "freeze_record": freeze,
        "domain_reference_manifest": domain_manifest,
        "domain_reference_freeze_record": domain_freeze,
        "runtime_compatibility": compatibility,
    }


def register_admet_artifact(endpoint: str, source_dir: str | Path, overwrite: bool = False) -> dict[str, Any]:
    spec = _spec(endpoint)
    verification = verify_admet_artifact(endpoint, source_dir)
    if not verification["valid"]:
        raise HTTPException(status_code=400, detail={"message": "ADMET artifact verification failed.", "errors": verification["errors"]})
    target = _manifest_path(endpoint)
    if target.exists() and not overwrite:
        raise HTTPException(status_code=409, detail="Registration already exists. Use overwrite only for intentional replacement.")
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "endpoint_key": endpoint,
        "model_id": spec["model_id"],
        "display_name": spec["display_name"],
        "task_type": spec["task_type"],
        "prediction_label": spec["prediction_label"],
        "version": spec["version"],
        "artifact_path": str(Path(source_dir)),
        "artifact_hash": spec["expected_hash"],
        "registered_at": _now(),
        "activation_gate_state": evaluate_admet_activation_gate(endpoint, source_dir)["activation_state"],
        "warnings": spec["mandatory_warnings"],
        "verification": {k: v for k, v in verification.items() if k not in {"metrics"}},
        "domain_reference": verification.get("domain_reference_manifest"),
    }
    target.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def list_admet_models() -> dict[str, Any]:
    return {"models": [admet_model_status(endpoint) for endpoint in ENDPOINTS], "scientific_notice": SCIENTIFIC_NOTICE}


def admet_model_status(endpoint: str) -> dict[str, Any]:
    spec = _spec(endpoint)
    registered = _manifest_path(endpoint).exists()
    verification = verify_admet_artifact(endpoint) if registered else {"valid": False, "errors": ["not_registered"], "warnings": spec["mandatory_warnings"]}
    active = get_active_endpoint(endpoint)
    gate = evaluate_admet_activation_gate(endpoint) if registered and verification.get("valid") else {"activation_state": "NOT_REGISTERED" if not registered else "VALIDATION_FAILED"}
    domain_manifest = verification.get("domain_reference_manifest") or {}
    external_evidence = (
        get_latest_endpoint_external_evidence(endpoint, spec["model_id"])
        if endpoint != "clintox_cttox"
        else unavailable_external_evidence()
    )
    warnings = list(dict.fromkeys(
        (verification.get("warnings") or [])
        + (verification.get("errors") or [])
        + external_warning_messages(endpoint, external_evidence)
    ))
    return {
        "endpoint": endpoint,
        "display_name": spec["display_name"],
        "registered": registered,
        "trained": verification.get("valid", False),
        "active": active.get("status") == "ACTIVE",
        "activation_status": active.get("status", "UNAVAILABLE"),
        "gate_state": gate["activation_state"],
        "model_id": spec["model_id"],
        "version": spec["version"],
        "model_hash": spec["expected_hash"],
        "task_type": spec["task_type"],
        "prediction_label": spec["prediction_label"],
        "warnings": warnings,
        "compact_domain_reference_verified": bool(registered and verification.get("valid") and domain_manifest),
        "domain_reference_hash": domain_manifest.get("domain_artifact_sha256"),
        "domain_schema_hash": domain_manifest.get("domain_schema_hash"),
        "domain_reference_count": domain_manifest.get("fingerprint_count"),
        "external_validation_available": external_evidence.get("available", False),
        "external_validation_status": external_evidence.get("external_validation_status"),
        "external_evidence_decision": external_evidence.get("evidence_decision"),
        "external_dataset_id": external_evidence.get("dataset_id"),
        "external_dataset_version": external_evidence.get("dataset_version"),
        "external_sample_count": external_evidence.get("external_sample_count"),
        "external_independence_status": external_evidence.get("independence_status"),
        "external_metrics_summary": external_evidence.get("key_metrics"),
        "external_domain_summary": external_evidence.get("domain_summary"),
        "external_calibration_summary": external_evidence.get("calibration_summary"),
        "external_validation_timestamp": external_evidence.get("evidence_timestamp"),
        "external_protocol_hash": external_evidence.get("protocol_hash"),
        "external_cohort_hash": external_evidence.get("cohort_hash"),
        "external_limitations": external_evidence.get("limitations"),
        "activation_recommendation": external_evidence.get("activation_recommendation"),
        "warning_severity": "UNAVAILABLE" if endpoint == "clintox_cttox" else external_evidence.get("warning_severity", "UNAVAILABLE"),
        "clinical_validity": False,
        "research_use_only": True,
    }


def evaluate_admet_activation_gate(endpoint: str, artifact_dir: str | Path | None = None) -> dict[str, Any]:
    spec = _spec(endpoint)
    verification = verify_admet_artifact(endpoint, artifact_dir)
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    metrics = verification.get("metrics") or {}
    test = metrics.get("test_metrics") or {}
    baseline = (metrics.get("baseline_comparison") or {})
    training = verification.get("training_metadata") or {}
    add("artifact_integrity", verification.get("valid", False), "Required files and frozen hashes must verify.")
    add("dataset_lineage", bool(training.get("dataset_hash")), "Dataset hash must be present.")
    add("split_lineage", bool(training.get("split_hash")), "Split hash must be present.")
    add("split_enforced", training.get("split_enforced") is True and training.get("internal_resplitting_disabled") is True, "No silent resplitting.")
    add("test_metrics_present", bool(test), "Held-out TEST metrics must be present.")
    add("baseline_comparison", baseline.get("selected_beats_baseline") is True or not spec["eligible"], "Model must beat simple baseline unless rejected endpoint.")
    if endpoint == "clintox_cttox":
        add("toxic_positive_detection", test.get("recall", 0) > 0 and test.get("f1", 0) > 0, "ClinTox recall=0 and F1=0 block activation.")
    if endpoint == "bbbp":
        add("specificity_disclosed", abs(float(test.get("specificity", 0)) - 0.39215686274509803) < 0.01, "Low TEST specificity must be disclosed.")
    if endpoint == "esol":
        conformal = (_load_json(Path(verification.get("artifact_dir", "")) / "calibration_metadata.json").get("conformal_interval") if verification.get("artifact_dir") else {}) or {}
        add("coverage_disclosed", abs(float(conformal.get("test_observed_coverage", 0)) - 0.8616600790513834) < 0.01, "Observed conformal undercoverage must be disclosed.")
    if endpoint == "herg":
        add("small_test_disclosed", True, "hERG TEST N=65 warning is mandatory.")
    passed = all(c["passed"] for c in checks) and spec["eligible"]
    return {
        "endpoint": endpoint,
        "model_id": spec["model_id"],
        "activation_state": "ACTIVATION_ELIGIBLE" if passed else "NOT_ELIGIBLE",
        "checks": checks,
        "warnings": spec["mandatory_warnings"],
        "scientific_notice": SCIENTIFIC_NOTICE,
    }


def get_active_endpoint(endpoint: str) -> dict[str, Any]:
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM admet_endpoint_active_models WHERE endpoint_key = ?", (endpoint,)).fetchone()
    if not row or row["status"] != "ACTIVE":
        return {"endpoint": endpoint, "status": "UNAVAILABLE", "model_id": row["model_id"] if row else None}
    return {"endpoint": endpoint, "status": "ACTIVE", "model_id": row["model_id"], "activated_at": row["activated_at"], "warnings": json.loads(row["warnings_json"] or "[]")}


def activate_admet_endpoint(endpoint: str, initiated_by: str = "local_api") -> dict[str, Any]:
    gate = evaluate_admet_activation_gate(endpoint)
    if gate["activation_state"] != "ACTIVATION_ELIGIBLE":
        raise HTTPException(status_code=400, detail={"message": "Activation gate failed.", "gate": gate})
    spec = _spec(endpoint)
    init_db()
    with get_connection() as connection:
        previous = connection.execute("SELECT model_id FROM admet_endpoint_active_models WHERE endpoint_key = ?", (endpoint,)).fetchone()
        previous_model_id = previous["model_id"] if previous else None
        connection.execute(
            """
            INSERT OR REPLACE INTO admet_endpoint_active_models (endpoint_key, model_id, status, warnings_json)
            VALUES (?, ?, 'ACTIVE', ?)
            """,
            (endpoint, spec["model_id"], json.dumps(gate["warnings"])),
        )
        connection.execute(
            """
            INSERT INTO admet_endpoint_activation_history (
                endpoint_key, previous_model_id, new_model_id, activation_state,
                validation_record_json, initiated_by, rollback_target_model_id
            )
            VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?)
            """,
            (endpoint, previous_model_id, spec["model_id"], json.dumps(gate), initiated_by, previous_model_id),
        )
    return {"endpoint": endpoint, "status": "ACTIVE", "model_id": spec["model_id"], "activation_gate": gate, "previous_model_id": previous_model_id}


def deactivate_admet_endpoint(endpoint: str, initiated_by: str = "local_api") -> dict[str, Any]:
    _spec(endpoint)
    init_db()
    with get_connection() as connection:
        previous = connection.execute("SELECT model_id FROM admet_endpoint_active_models WHERE endpoint_key = ?", (endpoint,)).fetchone()
        previous_model_id = previous["model_id"] if previous else None
        connection.execute(
            """
            INSERT OR REPLACE INTO admet_endpoint_active_models (endpoint_key, model_id, status, warnings_json)
            VALUES (?, '', 'DISABLED', '[]')
            """,
            (endpoint,),
        )
        connection.execute(
            """
            INSERT INTO admet_endpoint_activation_history (
                endpoint_key, previous_model_id, new_model_id, activation_state,
                validation_record_json, initiated_by, rollback_target_model_id
            )
            VALUES (?, ?, '', 'DISABLED', ?, ?, ?)
            """,
            (endpoint, previous_model_id, json.dumps({"reason": "deactivated"}), initiated_by, previous_model_id),
        )
    return {"endpoint": endpoint, "status": "DISABLED", "previous_model_id": previous_model_id}


def admet_activation_history(endpoint: str) -> dict[str, Any]:
    _spec(endpoint)
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM admet_endpoint_activation_history WHERE endpoint_key = ? ORDER BY id DESC LIMIT 25",
            (endpoint,),
        ).fetchall()
    return {"endpoint": endpoint, "history": [dict(row) for row in rows]}


def _load_bundle(endpoint: str):
    status = get_active_endpoint(endpoint)
    if status.get("status") != "ACTIVE":
        raise HTTPException(status_code=400, detail="No active model is available for this ADMET endpoint.")
    folder = _artifact_dir(endpoint)
    verification = verify_admet_artifact(endpoint, folder)
    if not verification["valid"]:
        compatibility = verification.get("runtime_compatibility") or {}
        if verification.get("hashes", {}).get("model.joblib") == _spec(endpoint)["expected_hash"] and not compatibility.get("execution_allowed", False):
            raise HTTPException(status_code=409, detail={"error": "model_runtime_version_mismatch", "engine_id": _spec(endpoint)["model_id"], **compatibility})
        raise HTTPException(status_code=400, detail={"message": "Registered artifact failed verification.", "errors": verification["errors"]})
    return (
        joblib.load(folder / "model.joblib"),
        verification,
        _load_json(folder / "feature_schema.json"),
        _load_json(folder / "metrics.json"),
        _load_json(folder / "calibration_metadata.json"),
        _load_domain_reference(endpoint, folder, verification),
    )


def _schema_hash(schema: dict[str, Any], training: dict[str, Any], endpoint: str, model_id: str) -> str:
    payload = {
        "schema_version": "m2c4_domain_schema_v1",
        "fingerprint_algorithm": schema.get("fingerprint", "RDKit Morgan"),
        "radius": int(schema.get("radius", 2)),
        "bit_length": int(schema.get("bits", 2048)),
        "use_chirality": bool(schema.get("use_chirality", False)),
        "use_features": bool(schema.get("use_features", False)),
        "vector_type": "bit_vector",
        "similarity_metric": "Tanimoto",
        "source_split": "TRAIN",
        "molecule_standardisation": "RDKit canonical SMILES, isomericSmiles=True",
        "rdkit_version": schema.get("rdkit_version") or training.get("package_versions", {}).get("rdkit"),
        "endpoint": endpoint,
        "model_id": model_id,
        "dataset_hash": training.get("dataset_hash"),
        "split_hash": training.get("split_hash"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _load_domain_reference(endpoint: str, artifact_dir: Path, verification: dict[str, Any]) -> dict[str, Any]:
    manifest = verification.get("domain_reference_manifest") or {}
    artifact = artifact_dir / manifest.get("domain_artifact_filename", "domain_fingerprints.npz")
    artifact_hash = _sha256(artifact) if artifact.exists() else ""
    cache_key = (endpoint, verification["manifest"].get("model_id", ""), artifact_hash)
    with _DOMAIN_CACHE_LOCK:
        cached = _DOMAIN_CACHE.get(cache_key)
        if cached:
            return cached
    if not artifact.exists() or artifact_hash != manifest.get("domain_artifact_sha256"):
        raise HTTPException(status_code=400, detail="domain_reference_unavailable_or_invalid")
    if artifact.stat().st_size > _MAX_DOMAIN_REFERENCE_BYTES:
        raise HTTPException(status_code=400, detail="domain_reference_unavailable_or_invalid")
    expected_schema_hash = _schema_hash(verification["feature_schema"], verification["training_metadata"], endpoint, verification["manifest"].get("model_id"))
    if manifest.get("domain_schema_hash") != expected_schema_hash:
        raise HTTPException(status_code=400, detail="domain_reference_unavailable_or_invalid")
    with np.load(artifact, allow_pickle=False) as data:
        packed = data["packed_fingerprints"]
        record_ids = data["record_ids"]
        smiles_hashes = data["canonical_smiles_hashes"]
        if packed.dtype != np.uint8 or record_ids.dtype.kind == "O" or smiles_hashes.dtype.kind == "O":
            raise HTTPException(status_code=400, detail="domain_reference_unavailable_or_invalid")
        reference = {
            "packed_fingerprints": packed.copy(),
            "record_ids": record_ids.astype(str).copy(),
            "canonical_smiles_hashes": smiles_hashes.astype(str).copy(),
            "thresholds": tuple(float(x) for x in manifest["thresholds"]),
            "artifact_hash": artifact_hash,
            "schema_hash": manifest["domain_schema_hash"],
            "reference_count": int(manifest["fingerprint_count"]),
            "similarity_metric": manifest.get("similarity_metric", "Tanimoto"),
            "estimated_memory_bytes": int(packed.nbytes + record_ids.nbytes + smiles_hashes.nbytes),
            "version": manifest.get("domain_reference_version", "m2c4_v1"),
        }
    if reference["reference_count"] != len(reference["packed_fingerprints"]):
        raise HTTPException(status_code=400, detail="domain_reference_unavailable_or_invalid")
    with _DOMAIN_CACHE_LOCK:
        if len(_DOMAIN_CACHE) >= _MAX_DOMAIN_CACHE_ENTRIES:
            _DOMAIN_CACHE.pop(next(iter(_DOMAIN_CACHE)))
        _DOMAIN_CACHE[cache_key] = reference
    return reference


def _packed_query_fingerprint(smiles: str, schema: dict[str, Any]) -> np.ndarray:
    mol = Chem.MolFromSmiles(smiles)
    gen = rdFingerprintGenerator.GetMorganGenerator(
        radius=int(schema.get("radius", 2)),
        fpSize=int(schema.get("bits", 2048)),
        includeChirality=bool(schema.get("use_chirality", False)),
        useBondTypes=True,
    )
    arr = np.zeros((int(schema.get("bits", 2048)),), dtype=np.uint8)
    DataStructs.ConvertToNumpyArray(gen.GetFingerprint(mol), arr)
    return np.packbits(arr, bitorder="big")


def _domain_status(smiles: str, domain: dict[str, Any], schema: dict[str, Any], artifact_dir: Path) -> dict[str, Any]:
    query = _packed_query_fingerprint(smiles, schema)
    packed = domain["packed_fingerprints"]
    intersection = np.unpackbits(np.bitwise_and(packed, query), axis=1, bitorder="big").sum(axis=1)
    union = np.unpackbits(np.bitwise_or(packed, query), axis=1, bitorder="big").sum(axis=1)
    similarities = np.divide(intersection, union, out=np.zeros_like(intersection, dtype=float), where=union != 0)
    nearest_index = int(np.argmax(similarities))
    nearest = float(similarities[nearest_index])
    in_threshold, borderline_threshold = domain["thresholds"]
    status = "IN_DOMAIN" if nearest >= in_threshold else "BORDERLINE" if nearest >= borderline_threshold else "OUT_OF_DOMAIN"
    return {
        "nearest_training_similarity": nearest,
        "domain_status": status,
        "nearest_reference_index": nearest_index,
        "nearest_reference_hash": str(domain["canonical_smiles_hashes"][nearest_index]),
        "domain_reference_version": domain["version"],
        "domain_reference_hash": domain["artifact_hash"],
        "domain_schema_hash": domain["schema_hash"],
        "domain_reference_count": domain["reference_count"],
        "similarity_metric": domain["similarity_metric"],
        "domain_thresholds": {"in_domain": in_threshold, "borderline": borderline_threshold},
        "compact_reference_used": True,
    }


def predict_admet_endpoints(smiles: str, endpoints: list[str] | None = None) -> dict[str, Any]:
    canonical = _canonical(smiles)
    requested = endpoints or ["bbbp", "esol", "herg"]
    results = []
    for endpoint in requested:
        endpoint = endpoint.strip().lower()
        spec = _spec(endpoint)
        if endpoint == "clintox_cttox":
            results.append({
                "endpoint": endpoint,
                "status": "unavailable",
                "reason": "model_failed_activation_gate",
                "model_id": spec["model_id"],
                "external_validation": unavailable_external_evidence(),
                "warning_severity": "UNAVAILABLE",
                "warnings": spec["mandatory_warnings"],
            })
            continue
        try:
            model, verification, schema, metrics, calibration, domain = _load_bundle(endpoint)
            x = _features(canonical, schema)
            folder = Path(verification["artifact_dir"])
            domain_result = _domain_status(canonical, domain, schema, folder)
            nearest = domain_result["nearest_training_similarity"]
            domain_state = domain_result["domain_status"]
            task = spec["task_type"]
            raw_pred = model.predict(x)[0]
            tree_values = []
            for est in np.ravel(getattr(model, "estimators_", [])):
                tree_values.append(float(est.predict_proba(x)[:, 1][0]) if task == "binary_classification" and hasattr(est, "predict_proba") else float(est.predict(x)[0]))
            uncertainty = float(np.std(tree_values)) if tree_values else None
            if task == "binary_classification":
                prob = float(model.predict_proba(x)[:, 1][0])
                result = {
                    "predicted_class": int(prob >= 0.5),
                    f"probability_{spec['prediction_label']}": prob,
                    "decision_threshold": 0.5,
                }
            else:
                value = float(raw_pred)
                result = {
                    "predicted_logS": value,
                    "units": spec.get("units"),
                    "model_derived_solubility_mol_L": float(math.pow(10, value)),
                    "conformal_interval": calibration.get("conformal_interval"),
                }
            external_evidence = get_latest_endpoint_external_evidence(endpoint, spec["model_id"])
            warnings = spec["mandatory_warnings"] + external_warning_messages(endpoint, external_evidence, domain_state)
            if domain_state != "IN_DOMAIN":
                warnings.append(f"{endpoint} prediction is {domain_state}; interpret with reduced confidence.")
            results.append({
                "endpoint": endpoint,
                "status": "available",
                "display_name": spec["display_name"],
                "evidence_type": "MODEL_PREDICTION",
                "model_id": spec["model_id"],
                "model_version": spec["version"],
                "artifact_hash": spec["expected_hash"],
                "dataset_hash": verification["training_metadata"].get("dataset_hash"),
                "split_hash": verification["training_metadata"].get("split_hash"),
                "activation_status": "ACTIVE",
                "nearest_training_similarity": nearest,
                "domain_status": domain_state,
                **domain_result,
                "uncertainty_method": "tree_prediction_std",
                "uncertainty_value": uncertainty,
                "calibration_status": calibration.get("classification_calibration") or "not_applicable",
                "external_validation": external_evidence,
                "warning_severity": external_evidence.get("warning_severity", "UNAVAILABLE"),
                "test_metrics": metrics.get("test_metrics"),
                "warnings": list(dict.fromkeys(warnings)),
                "limitations": list(dict.fromkeys((verification["manifest"].get("limitations") or []) + external_evidence.get("limitations", []) + spec["mandatory_warnings"])),
                "prediction": result,
            })
        except Exception as exc:
            results.append({
                "endpoint": endpoint,
                "status": "unavailable",
                "reason": getattr(exc, "detail", str(exc)),
                "external_validation": get_latest_endpoint_external_evidence(endpoint, spec["model_id"]),
                "warnings": spec["mandatory_warnings"],
            })
    return {"canonical_smiles": canonical, "results": results, "scientific_notice": SCIENTIFIC_NOTICE}


def batch_predict_admet_endpoints(candidates: list[dict[str, Any]], endpoints: list[str] | None = None, max_batch: int = 50) -> dict[str, Any]:
    if len(candidates) > max_batch:
        raise HTTPException(status_code=422, detail=f"Batch size exceeds maximum of {max_batch}.")
    rows = []
    for item in candidates:
        try:
            rows.append({"success": True, "input": item, "prediction": predict_admet_endpoints(item.get("smiles") or "", endpoints)})
        except Exception as exc:
            rows.append({"success": False, "input": item, "error": getattr(exc, "detail", str(exc))})
    return {"count": len(rows), "results": rows, "scientific_notice": SCIENTIFIC_NOTICE}
