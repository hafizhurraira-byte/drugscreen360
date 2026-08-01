import json
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.database import get_connection, init_db
from app.models.scientific_engine_models import EngineCreate, EngineVersionCreate, LicenceReview
from app.services import scientific_engine_registry_service as registry


ADMET = {
    "bbbp_v1": ("bbbp", "Blood-Brain Barrier Penetration v1", "binary classification", "BBBP", "VALIDATED_FOR_SCOPE",
                ["Benchmark classification only; not proof of human CNS exposure."]),
    "esol_v1": ("esol", "ESOL Aqueous Solubility v1", "regression", "logS", "VALIDATED_FOR_SCOPE",
                ["Model-derived logS is not measured solubility.", "Approximate interval undercovers externally and is not guaranteed confidence."]),
    "herg_v1": ("herg", "hERG Inhibition Concern v1", "binary classification", "hERG inhibition risk", "VALIDATED_FOR_SCOPE",
                ["Calibration review/recalibration is recommended.", "Low predicted risk is not proof of cardiac safety."]),
    "clintox_cttox_v1": ("clintox_cttox", "ClinTox CT_TOX v1", "binary classification", "CT_TOX", "REJECTED",
                          ["Held-out toxic-positive recall and F1 were zero; hard activation blocker.", "Excluded from production prediction and candidate ranking."]),
}


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _active(table: str, key_column: str, key: str) -> dict[str, Any]:
    with get_connection() as connection:
        row = connection.execute(f"SELECT * FROM {table} WHERE {key_column} = ?", (key,)).fetchone()
    return dict(row) if row else {}


def _permissions(internet: bool = False) -> list[dict[str, Any]]:
    return [
        {"deployment_profile": "LOCAL_RESEARCH", "permitted": True},
        {"deployment_profile": "LOCAL_DEMO", "permitted": True},
        {"deployment_profile": "PUBLIC_DEMO", "permitted": not internet, "reason": "Requires live internet" if internet else None},
        {"deployment_profile": "CI_TEST", "permitted": not internet, "reason": "Live provider is not required in CI" if internet else None},
    ]


def _model_manifest(root: Path, endpoint: str, model_id: str) -> tuple[dict[str, Any], Path | None]:
    path = root / "backend" / "models" / "admet" / endpoint / model_id / "registration_manifest.json"
    manifest = _load(path)
    artifact = Path(manifest.get("artifact_path", "")) if manifest.get("artifact_path") else None
    return manifest, artifact


def _admet(root: Path, model_id: str) -> dict[str, Any]:
    endpoint, name, task, scope, validation, limitations = ADMET[model_id]
    manifest, artifact = _model_manifest(root, endpoint, model_id)
    verification = manifest.get("verification") or {}
    training = verification.get("training_metadata") or {}
    feature = verification.get("feature_schema") or {}
    domain = verification.get("domain_reference_manifest") or manifest.get("domain_reference") or {}
    metrics = _load(artifact / "metrics.json") if artifact else {}
    uncertainty = _load(artifact / "uncertainty_metadata.json") if artifact else {}
    calibration = _load(artifact / "calibration_metadata.json") if artifact else {}
    runtime_sklearn = package_version("scikit-learn")
    trained_sklearn = (training.get("package_versions") or {}).get("sklearn")
    runtime_mismatch = bool(trained_sklearn and trained_sklearn != runtime_sklearn)
    if runtime_mismatch:
        limitations = limitations + [f"Artifact was produced with scikit-learn {trained_sklearn}; installed runtime is {runtime_sklearn}."]
    active = _active("admet_endpoint_active_models", "endpoint_key", endpoint)
    active_state = active.get("status") == "ACTIVE" and active.get("model_id") == model_id
    artifact_ok = bool(verification.get("valid") and artifact and artifact.exists())
    external = {}
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM admet_endpoint_external_validation_evidence WHERE endpoint_key = ? AND model_id = ? ORDER BY id DESC LIMIT 1",
            (endpoint, model_id),
        ).fetchone()
        if row:
            external = {key: (json.loads(value) if key.endswith("_json") else value) for key, value in dict(row).items() if key not in {"id", "imported_by"}}
    return {
        "engine": dict(engine_id=model_id, engine_name=name, engine_family="admet_endpoint_model", engine_class="INTERNAL_MODEL",
                       provider_name="DrugScreen360", task_types=["ADME_PREDICTION" if endpoint != "clintox_cttox" else "TOXICITY_PREDICTION"],
                       description=f"Governed {task} engine for {scope}."),
        "version": dict(engine_version="v1", adapter_id="admet_endpoint_model_service", adapter_version="1",
                        runtime_type="python_joblib", package_name="scikit-learn", package_version=runtime_sklearn,
                        artifact_identifier=model_id, artifact_hash=manifest.get("artifact_hash"), model_hash=manifest.get("artifact_hash"),
                        input_schema_version="smiles_v1", output_schema_version="admet_endpoint_v1", supported_endpoints=[scope],
                        supported_organisms=[], supported_targets=[], supported_target_classes=[], supported_molecule_types=["SMALL_MOLECULE"],
                        local_execution_supported=True, api_execution_supported=False, internet_required=False, credentials_required=False,
                        training_data_information=None, dataset_hash=training.get("dataset_hash"), split_hash=training.get("split_hash"),
                        decision_threshold=None if endpoint == "esol" else 0.5, prediction_unit="log10 mol/L" if endpoint == "esol" else "probability",
                        feature_representation=feature.get("fingerprint") or feature.get("feature_set"),
                        applicability_domain_method=(f"{domain.get('similarity_metric')} nearest-training fingerprint similarity" if domain else None),
                        uncertainty_method=(uncertainty.get("method") or ("conformal interval" if endpoint == "esol" else "probability and domain assessment")),
                        known_limitations=limitations + list(manifest.get("warnings") or []), technical_status="AVAILABLE" if artifact_ok else "ARTIFACT_MISSING",
                        scientific_validation_status=validation, model_status="EXPERIMENTAL_INTERNAL" if endpoint == "clintox_cttox" else "INTERNAL_VALIDATED",
                        activation_status="BLOCKED_VALIDATION" if endpoint == "clintox_cttox" else ("ACTIVE_BETA" if active_state else "INACTIVE"),
                        runtime_health_status="DEGRADED" if artifact_ok and runtime_mismatch else ("HEALTHY" if artifact_ok and active_state else ("UNAVAILABLE" if not artifact_ok else "UNKNOWN")),
                        authoritative_state=active.get("status", "UNAVAILABLE"), blocked_reason=(limitations[0] if endpoint == "clintox_cttox" else None),
                        internal_validation=metrics or None, external_validation=external or None,
                        calibration_status="UNDERCOVERAGE" if endpoint == "esol" else ("RECALIBRATION_RECOMMENDED" if endpoint == "herg" else (calibration.get("classification_calibration") or None)),
                        deployment_permissions=_permissions()),
        "link": dict(legacy_system="admet_endpoint_governance", legacy_record_type="endpoint_model", legacy_record_id=endpoint,
                     authoritative_state_source="admet_endpoint_active_models + registration_manifest", snapshot={"model_id": model_id, "activation_status": active.get("status", "UNAVAILABLE"), "model_hash": manifest.get("artifact_hash"), "endpoint": scope, "artifact_available": artifact_ok, "validation_status": validation}),
    }


def _egfr(root: Path) -> dict[str, Any]:
    manifest_path = root / "backend" / "models" / "activity" / "egfr" / "egfr_p00533_pic50_rf_morgan_v2" / "registration_manifest.json"
    manifest = _load(manifest_path)
    active = _active("activity_active_models", "target_key", "EGFR")
    artifact = Path(manifest.get("artifact_path", "")) if manifest.get("artifact_path") else None
    artifact_ok = bool(manifest.get("verification", {}).get("valid") and artifact and artifact.exists())
    metrics = _load(artifact / "metrics.json") if artifact else {}
    training = _load(artifact / "training_metadata.json") if artifact else {}
    runtime_sklearn = package_version("scikit-learn")
    trained_sklearn = (training.get("package_versions") or {}).get("sklearn")
    runtime_mismatch = bool(trained_sklearn and trained_sklearn != runtime_sklearn)
    limitations = manifest.get("limitations") or ["Target-specific model only."]
    if runtime_mismatch:
        limitations = limitations + [f"Artifact was produced with scikit-learn {trained_sklearn}; installed runtime is {runtime_sklearn}."]
    active_state = active.get("status") == "ACTIVE" and active.get("model_id") == "egfr_activity_v2"
    reason = "Authoritative activity state is disabled; no automatic reactivation." if active.get("status") == "DISABLED" else ("Artifact unavailable" if not artifact_ok else "Inactive governance state")
    return {
        "engine": dict(engine_id="egfr_activity_v2", engine_name="EGFR Activity Model v2", engine_family="target_activity", engine_class="INTERNAL_MODEL",
                       provider_name="DrugScreen360", task_types=["POTENCY_PREDICTION"], description="Target-specific EGFR pIC50 regression model."),
        "version": dict(engine_version="v2", adapter_id="activity_model_service", adapter_version="2", runtime_type="python_joblib",
                        package_name="scikit-learn", artifact_identifier="egfr_activity_v2", artifact_hash=manifest.get("artifact_hash"), model_hash=manifest.get("artifact_hash"),
                        input_schema_version="smiles_target_v1", output_schema_version="activity_prediction_v2", supported_endpoints=["pIC50"],
                        supported_organisms=["Homo sapiens"], supported_targets=["EGFR", "P00533", "CHEMBL203"], supported_target_classes=["protein kinase"],
                        package_version=runtime_sklearn, supported_molecule_types=["SMALL_MOLECULE"], local_execution_supported=True, known_limitations=limitations,
                        dataset_hash=training.get("dataset_hash"), split_hash=training.get("split_hash"), prediction_unit="pIC50", feature_representation="RDKit Morgan fingerprint",
                        internal_validation=metrics or None,
                        technical_status="AVAILABLE" if artifact_ok else "ARTIFACT_MISSING", scientific_validation_status="VALIDATED_FOR_SCOPE" if manifest else "UNREVIEWED",
                        model_status="INTERNAL_VALIDATED", activation_status="ACTIVE_BETA" if active_state else "INACTIVE",
                        runtime_health_status="DEGRADED" if artifact_ok and runtime_mismatch else ("HEALTHY" if artifact_ok and active_state else ("UNAVAILABLE" if not artifact_ok else "UNKNOWN")),
                        applicability_domain_method="Morgan fingerprint nearest-neighbour domain assessment" if manifest else None,
                        uncertainty_method="Conformal prediction interval with documented undercoverage" if manifest else None,
                        authoritative_state=active.get("status", "UNAVAILABLE"), blocked_reason=reason, deployment_permissions=_permissions()),
        "link": dict(legacy_system="activity_model_governance", legacy_record_type="target_model", legacy_record_id="EGFR",
                     authoritative_state_source="activity_active_models + registration_manifest", snapshot={"model_id": "egfr_activity_v2", "activation_status": active.get("status", "UNAVAILABLE"), "model_hash": manifest.get("artifact_hash"), "endpoint": "pIC50", "target": "EGFR", "artifact_available": artifact_ok, "validation_status": "VALIDATED_FOR_SCOPE" if manifest else "UNREVIEWED"}),
    }


def _static_engines() -> list[dict[str, Any]]:
    try:
        rdkit_version = package_version("rdkit")
    except Exception:
        rdkit_version = None
    entries = [
        ("rdkit_toolkit", "RDKit Chemistry Toolkit", "CHEMISTRY_TOOLKIT", ["MOLECULE_STANDARDIZATION", "DESCRIPTOR_CALCULATION", "FINGERPRINT_GENERATION", "SIMILARITY_ANALYSIS", "STRUCTURAL_ALERTS"], False, rdkit_version, "rdkit", "BSD-3-Clause", "RDKit calculations depend on valid molecular structures and configured algorithms."),
        ("medicinal_chemistry_rule_filters", "Medicinal Chemistry Rule Filters", "RULE_BASED_TOOL", ["DRUG_LIKENESS", "STRUCTURAL_ALERTS", "ADME_PREDICTION"], False, "1", "rules.py + admet_rules.py", None, "RULE_BASED_HEURISTIC; rules are screening aids, not trained-model predictions."),
        ("pubchem_connector", "PubChem PUG REST Connector", "DATABASE_CONNECTOR", ["COMPOUND_IDENTITY", "DATABASE_EVIDENCE_RETRIEVAL"], True, "PUG_REST", "pubchem.py", None, "Remote records are database evidence, not predictions; local demo fallback is labelled."),
        ("chembl_connector", "ChEMBL API Connector", "DATABASE_CONNECTOR", ["TARGET_IDENTIFICATION", "KNOWN_LIGAND_RECOVERY", "DATABASE_EVIDENCE_RETRIEVAL"], True, "API", "chembl_service.py", None, "Remote availability and source-record quality vary."),
        ("bindingdb_connector", "BindingDB Availability Connector", "DATABASE_CONNECTOR", ["KNOWN_LIGAND_RECOVERY", "DATABASE_EVIDENCE_RETRIEVAL"], True, "web", "bindingdb_service.py", None, "Current implementation is an availability probe, not full affinity parsing."),
        ("open_targets_connector", "Open Targets Platform Connector", "DATABASE_CONNECTOR", ["DISEASE_SIGNATURE_RECOVERY", "TARGET_IDENTIFICATION", "DATABASE_EVIDENCE_RETRIEVAL"], True, "GraphQL_v4", "open_targets_service.py", None, "Association evidence does not prove causality, efficacy, or safety."),
    ]
    return [{
        "engine": dict(engine_id=eid, engine_name=name, engine_family="toolkit" if cls != "DATABASE_CONNECTOR" else "external_database", engine_class=cls,
                       provider_name="DrugScreen360" if cls != "DATABASE_CONNECTOR" else name.split()[0], task_types=tasks, description=limitation),
        "version": dict(engine_version=ver or "UNKNOWN", adapter_id=adapter, adapter_version="1", runtime_type="python_library" if not internet else "remote_api",
                        package_name="rdkit" if eid == "rdkit_toolkit" else None, package_version=ver if eid == "rdkit_toolkit" else None,
                        input_schema_version="smiles_v1" if cls != "DATABASE_CONNECTOR" else "provider_query_v1", output_schema_version="evidence_v1",
                        supported_endpoints=tasks, supported_molecule_types=["SMALL_MOLECULE"] if cls != "DATABASE_CONNECTOR" else [],
                        local_execution_supported=not internet, api_execution_supported=internet, internet_required=internet, credentials_required=False,
                        known_limitations=[limitation], technical_status="AVAILABLE", scientific_validation_status="DOCUMENTED",
                        activation_status="ACTIVE_RESEARCH", runtime_health_status="UNKNOWN" if internet else "HEALTHY", failure_policy="FAIL_CLOSED",
                        fallback_policy="NO_FALLBACK", authoritative_state="IMPLEMENTED", deployment_permissions=_permissions(internet)),
        "licence": dict(code_licence=licence, licence_review_status="NOT_REVIEWED"),
        "link": dict(legacy_system="application_service", legacy_record_type="implemented_service", legacy_record_id=adapter,
                     authoritative_state_source=adapter, snapshot={"implementation_status": "IMPLEMENTED", "adapter_id": adapter}),
    } for eid, name, cls, tasks, internet, ver, adapter, licence, limitation in entries]


def discover_existing_engines(source_root: str | Path | None = None, engine_id: str | None = None) -> list[dict[str, Any]]:
    root = Path(source_root) if source_root else Path(__file__).resolve().parents[3]
    entries = [_egfr(root), *[_admet(root, model_id) for model_id in ADMET], *_static_engines()]
    return [item for item in entries if not engine_id or item["engine"]["engine_id"] == engine_id]


def _link(engine_id: str, version: str, link: dict[str, Any]) -> None:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM scientific_engine_legacy_links WHERE legacy_system=? AND legacy_record_type=? AND legacy_record_id=?",
                                 (link["legacy_system"], link["legacy_record_type"], link["legacy_record_id"])).fetchone()
        if row:
            if row["engine_id"] == engine_id and row["engine_version"] == version and json.loads(row["snapshot_json"]) == link["snapshot"]:
                return
            raise HTTPException(409, "Conflicting legacy link")
        connection.execute("""INSERT INTO scientific_engine_legacy_links
            (engine_id,engine_version,legacy_system,legacy_record_type,legacy_record_id,authoritative_state_source,snapshot_json)
            VALUES (?,?,?,?,?,?,?)""", (engine_id, version, link["legacy_system"], link["legacy_record_type"], link["legacy_record_id"], link["authoritative_state_source"], registry._json(link["snapshot"])))


def migrate(mode: str = "dry-run", source_root: str | Path | None = None, engine_id: str | None = None) -> dict[str, Any]:
    if mode not in {"dry-run", "apply", "verify"}:
        raise HTTPException(422, "Mode must be dry-run, apply, or verify")
    init_db()
    manifests = discover_existing_engines(source_root, engine_id)
    results = []
    for item in manifests:
        eid, version = item["engine"]["engine_id"], item["version"]["engine_version"]
        if mode == "apply":
            registry.register_engine(EngineCreate(**item["engine"]))
            registry.register_version(eid, EngineVersionCreate(**item["version"]))
            if item.get("licence"):
                current = registry.get_version(eid, version).get("licence_review")
                if not current:
                    registry.add_licence_review(eid, version, LicenceReview(**item["licence"]))
            _link(eid, version, item["link"])
            outcome = "IMPORTED"
        else:
            try:
                current = registry.get_version(eid, version)
                outcome = "VERIFIED" if current.get("model_hash") == item["version"].get("model_hash") and current.get("activation_status") == item["version"].get("activation_status") else "CONFLICT"
            except HTTPException:
                outcome = "WOULD_IMPORT" if mode == "dry-run" else "MISSING"
        results.append({"engine_id": eid, "engine_version": version, "outcome": outcome})
    report = {"mode": mode, "engine_count": len(results), "results": sorted(results, key=lambda x: x["engine_id"]), "writes_performed": mode == "apply"}
    if mode == "apply":
        with get_connection() as connection:
            connection.execute("INSERT INTO scientific_engine_migration_runs (mode, report_json) VALUES (?, ?)", (mode, registry._json(report)))
    return report


def migration_status() -> dict[str, Any]:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM scientific_engine_migration_runs ORDER BY id DESC LIMIT 1").fetchone()
    return ({**json.loads(row["report_json"]), "created_at": row["created_at"]} if row else {"mode": None, "engine_count": 0, "results": []})
