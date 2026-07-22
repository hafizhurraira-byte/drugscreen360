import hashlib
import json
from typing import Any

from fastapi import HTTPException
from rdkit import Chem, DataStructs
from rdkit.Chem import rdMolDescriptors
from rdkit.Chem.Scaffolds import MurckoScaffold

from app.services.admet_trained_model_service import discover_trained_models, get_active_trained_model_info
from app.services.version import app_version


SCIENTIFIC_NOTICE = (
    "Computational decision-support only. Predictions, rules, and rankings require experimental "
    "validation and qualified scientific review."
)

ADMET_ENDPOINT_CATALOG = [
    {
        "endpoint_id": "intestinal_absorption",
        "category": "absorption",
        "display_name": "Intestinal Absorption",
        "task_type": "classification",
        "units": None,
        "activation_policy_id": "admet_absorption_classification_v1",
    },
    {
        "endpoint_id": "caco2_permeability",
        "category": "absorption",
        "display_name": "Caco-2 / Permeability",
        "task_type": "regression_or_classification",
        "units": "assay dependent",
        "activation_policy_id": "admet_absorption_permeability_v1",
    },
    {
        "endpoint_id": "plasma_protein_binding",
        "category": "distribution",
        "display_name": "Plasma Protein Binding",
        "task_type": "regression_or_classification",
        "units": "percent bound or assay dependent",
        "activation_policy_id": "admet_distribution_ppb_v1",
    },
    {
        "endpoint_id": "bbb_penetration",
        "category": "distribution",
        "display_name": "BBB Penetration",
        "task_type": "classification",
        "units": None,
        "activation_policy_id": "admet_distribution_bbb_v1",
    },
    {
        "endpoint_id": "cyp_inhibition",
        "category": "metabolism",
        "display_name": "CYP Inhibition / Substrate Risk",
        "task_type": "classification",
        "units": "isoform dependent",
        "activation_policy_id": "admet_metabolism_cyp_v1",
    },
    {
        "endpoint_id": "clearance",
        "category": "excretion",
        "display_name": "Clearance",
        "task_type": "regression",
        "units": "assay dependent",
        "activation_policy_id": "admet_excretion_clearance_v1",
    },
    {
        "endpoint_id": "hepatotoxicity",
        "category": "toxicity",
        "display_name": "Hepatotoxicity",
        "task_type": "classification",
        "units": None,
        "activation_policy_id": "admet_toxicity_hepatotoxicity_v1",
    },
    {
        "endpoint_id": "herg_cardiotoxicity",
        "category": "toxicity",
        "display_name": "hERG / Cardiotoxicity",
        "task_type": "classification",
        "units": None,
        "activation_policy_id": "admet_toxicity_herg_v1",
    },
    {
        "endpoint_id": "toxicity_concern",
        "category": "toxicity",
        "display_name": "General Toxicity Concern",
        "task_type": "classification",
        "units": None,
        "activation_policy_id": "admet_toxicity_concern_v1",
    },
]

FUTURE_PROVIDER_CONTRACTS = [
    {
        "provider_type": "DockingProvider",
        "status": "not_implemented",
        "input_contract": ["protein_structure_or_pdb_id", "ligand_smiles_or_structure", "binding_site_definition"],
        "output_contract": ["pose_file", "score", "engine", "engine_version", "limitations", "provenance"],
        "failure_handling": "Return unavailable/error with engine provenance. Do not create fake docking scores.",
    },
    {
        "provider_type": "MDProvider",
        "status": "not_implemented",
        "input_contract": ["structure", "ligand", "force_field", "simulation_protocol"],
        "output_contract": ["trajectory_reference", "stability_summary", "engine", "engine_version", "limitations"],
        "failure_handling": "Return unavailable/error. Do not create fake trajectories or stability claims.",
    },
    {
        "provider_type": "MoleculeGenerator",
        "status": "not_implemented",
        "input_contract": ["objective", "constraints", "seed_candidates", "model_id"],
        "output_contract": ["generated_smiles", "scoring_trace", "model_version", "limitations"],
        "failure_handling": "Return not_implemented unless a real governed generator is connected.",
    },
    {
        "provider_type": "LeadOptimizer",
        "status": "not_implemented",
        "input_contract": ["compound_candidate", "optimization_objectives", "evidence_package"],
        "output_contract": ["proposed_modifications", "rationale", "provenance", "limitations"],
        "failure_handling": "Return not_implemented. Do not imply optimized leads are validated.",
    },
]

JOB_LIFECYCLE_CONTRACT = {
    "status": "contract_defined_synchronous_execution_preserved",
    "lifecycle": ["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"],
    "covered_operations": ["model_training", "external_validation"],
    "future_operations": ["docking", "molecular_dynamics", "batch_screening", "molecular_generation"],
    "required_metadata": [
        "job_id",
        "job_type",
        "created_at",
        "started_at",
        "ended_at",
        "progress",
        "status",
        "input_snapshot",
        "output_references",
        "logs_or_errors",
        "model_provenance",
        "dataset_provenance",
        "reproducibility_metadata",
    ],
    "local_v1_strategy": "Keep current synchronous endpoints stable while exposing a migration-ready job contract.",
    "migration_path": "A local queue can be introduced first, then Redis/Celery/RQ or another distributed worker when multi-user scale requires it.",
}

RANKING_DIMENSIONS = [
    "activity",
    "selectivity",
    "admet",
    "toxicity",
    "drug_likeness",
    "structural_alerts",
    "applicability_domain",
    "uncertainty_confidence",
    "evidence_quality",
    "novelty_similarity",
    "synthetic_feasibility",
]


def _canonical_smiles(smiles: str) -> str | None:
    mol = Chem.MolFromSmiles(smiles or "")
    if not mol:
        return None
    return Chem.MolToSmiles(mol, canonical=True)


def _scaffold(smiles: str) -> str | None:
    mol = Chem.MolFromSmiles(smiles or "")
    if not mol:
        return None
    try:
        return MurckoScaffold.MurckoScaffoldSmiles(mol=mol) or None
    except Exception:
        return None


def _json_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_endpoint(value: str | None) -> str:
    return (value or "").strip().lower().replace(" ", "_").replace("-", "_")


def endpoint_aware_admet_status() -> list[dict[str, Any]]:
    models = discover_trained_models()
    active = get_active_trained_model_info()
    active_id = active.get("model_id") if active.get("status") == "available" else None
    by_task: dict[str, list[dict[str, Any]]] = {}
    for model in models:
        task = _normalize_endpoint(model.get("task_name"))
        if task:
            by_task.setdefault(task, []).append(model)

    endpoints = []
    for item in ADMET_ENDPOINT_CATALOG:
        endpoint_id = item["endpoint_id"]
        endpoint_models = by_task.get(endpoint_id, [])
        active_model = next((m for m in endpoint_models if m.get("model_id") == active_id), None)
        candidate_models = [m for m in endpoint_models if m.get("model_id") != active_id]
        status = "active" if active_model else "candidate_available" if candidate_models else "unavailable"
        endpoints.append({
            **item,
            "status": status,
            "active_model_id": active_model.get("model_id") if active_model else None,
            "candidate_model_ids": [m.get("model_id") for m in candidate_models],
            "dataset_provenance_status": "from_model_card_when_available" if endpoint_models else "not_available",
            "validation_status": "requires_external_validation_for_scientific_use",
            "applicability_domain_required": True,
            "uncertainty_required": True,
            "limitations": [] if endpoint_models else ["No trained local model is available for this endpoint."],
        })
    return endpoints


def activity_model_status() -> dict[str, Any]:
    return {
        "status": "architecture_ready_untrained",
        "model_family": "activity",
        "scope": "target_specific",
        "supported_task_types": ["binary_classification", "regression"],
        "required_dataset_contract": {
            "target_id": "required",
            "target_name": "required",
            "assay_type": "required",
            "smiles_column": "required",
            "activity_label_or_value_column": "required",
            "units": "required for regression",
            "transformation": "required when pIC50/pKi/pKd or log transforms are used",
            "provenance": "required",
        },
        "activation_state": "DRAFT",
        "limitations": ["No universal activity model is active. A bounded target-specific labelled dataset is required."],
    }


def selectivity_model_status() -> dict[str, Any]:
    return {
        "status": "architecture_ready_untrained",
        "model_family": "selectivity",
        "required_dataset_contract": {
            "on_target": "required",
            "off_target_panel": "required",
            "activity_units_and_transforms": "required",
            "candidate_identity": "required",
            "provenance": "required",
        },
        "output_contract": ["target_panel_predictions", "on_target_vs_off_target_margin", "evidence_provenance"],
        "activation_state": "DRAFT",
        "limitations": ["No selectivity model is active. Selectivity predictions are unavailable until real panel data are supplied."],
    }


def check_split_integrity(records: list[dict[str, Any]]) -> dict[str, Any]:
    allowed = {"train", "validation", "test"}
    partitions: dict[str, set[str]] = {name: set() for name in allowed}
    scaffolds: dict[str, set[str]] = {name: set() for name in allowed}
    duplicates: dict[str, int] = {}
    warnings: list[str] = []
    rejected: list[dict[str, Any]] = []

    clean_records = []
    for idx, record in enumerate(records):
        partition = str(record.get("partition") or "").strip().lower()
        canonical = _canonical_smiles(record.get("canonical_smiles") or record.get("smiles") or "")
        if partition not in allowed:
            rejected.append({"row": idx + 1, "reason": "unknown partition"})
            continue
        if not canonical:
            rejected.append({"row": idx + 1, "reason": "invalid or missing SMILES"})
            continue
        partitions[partition].add(canonical)
        duplicates[canonical] = duplicates.get(canonical, 0) + 1
        scaffold = _scaffold(canonical)
        if scaffold:
            scaffolds[partition].add(scaffold)
        clean_records.append({"partition": partition, "canonical_smiles": canonical, "label": record.get("label")})

    overlap_pairs = []
    scaffold_overlap_pairs = []
    for left in allowed:
        for right in allowed:
            if left >= right:
                continue
            overlap = sorted(partitions[left] & partitions[right])
            if overlap:
                overlap_pairs.append({"left": left, "right": right, "overlap_count": len(overlap), "examples": overlap[:5]})
            scaffold_overlap = sorted(scaffolds[left] & scaffolds[right])
            if scaffold_overlap:
                scaffold_overlap_pairs.append({"left": left, "right": right, "overlap_count": len(scaffold_overlap), "examples": scaffold_overlap[:5]})

    duplicate_count = sum(count - 1 for count in duplicates.values() if count > 1)
    if overlap_pairs:
        warnings.append("Canonical SMILES overlap was detected across train/validation/test partitions.")
    if scaffold_overlap_pairs:
        warnings.append("Scaffold overlap was detected across partitions; consider scaffold-aware splitting for chemistry tasks.")
    if rejected:
        warnings.append("Some records were rejected because partition or SMILES fields were invalid.")

    return {
        "status": "failed" if overlap_pairs else "passed_with_warnings" if warnings else "passed",
        "record_count": len(records),
        "accepted_count": len(clean_records),
        "rejected_records": rejected,
        "partition_counts": {key: len(value) for key, value in partitions.items()},
        "duplicate_count": duplicate_count,
        "overlap_pairs": overlap_pairs,
        "scaffold_overlap_pairs": scaffold_overlap_pairs,
        "dataset_version_hash": _json_hash(clean_records),
        "split_hash": _json_hash({key: sorted(value) for key, value in partitions.items()}),
        "warnings": warnings,
    }


def assess_fingerprint_domain(query_smiles: str, training_smiles: list[str], threshold: float = 0.35) -> dict[str, Any]:
    query_mol = Chem.MolFromSmiles(query_smiles or "")
    if not query_mol:
        raise HTTPException(status_code=422, detail="Invalid query SMILES.")
    query_canonical = Chem.MolToSmiles(query_mol, canonical=True)
    fps = []
    for smiles in training_smiles:
        mol = Chem.MolFromSmiles(smiles or "")
        if mol:
            fps.append(rdMolDescriptors.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048))
    if not fps:
        return {
            "method": "morgan_fingerprint_nearest_neighbor",
            "status": "not_available",
            "nearest_similarity": None,
            "threshold": threshold,
            "domain_status": "not_available",
            "warnings": ["No valid training fingerprints were available."],
        }
    query_fp = rdMolDescriptors.GetMorganFingerprintAsBitVect(query_mol, 2, nBits=2048)
    similarities = [float(DataStructs.TanimotoSimilarity(query_fp, fp)) for fp in fps]
    nearest = max(similarities)
    domain_status = "in_domain" if nearest >= threshold else "borderline" if nearest >= max(0.0, threshold - 0.1) else "out_of_domain"
    return {
        "method": "morgan_fingerprint_nearest_neighbor",
        "fingerprint_parameters": {"type": "Morgan", "radius": 2, "n_bits": 2048},
        "query_canonical_smiles": query_canonical,
        "training_reference_count": len(fps),
        "nearest_similarity": round(nearest, 4),
        "mean_similarity": round(sum(similarities) / len(similarities), 4),
        "threshold": threshold,
        "borderline_threshold": max(0.0, threshold - 0.1),
        "domain_status": domain_status,
        "warnings": ["Out-of-domain predictions should not be interpreted with the same confidence as in-domain predictions."] if domain_status == "out_of_domain" else [],
        "scientific_notice": SCIENTIFIC_NOTICE,
    }


def build_uncertainty_contract(payload: dict[str, Any]) -> dict[str, Any]:
    probability = payload.get("probability")
    domain_status = payload.get("applicability_domain") or payload.get("domain_status") or "not_available"
    validation_status = payload.get("validation_status") or "not_available"
    calibration_status = payload.get("calibration_status") or "not_available"
    confidence = "not_available"
    uncertainty = "unknown"
    method = "not_available"
    warnings = []
    if isinstance(probability, (int, float)):
        method = "classifier_probability_with_domain_penalty"
        centered = abs(float(probability) - 0.5) * 2.0
        if domain_status == "out_of_domain":
            confidence = "low"
            uncertainty = "high"
            warnings.append("Confidence reduced because the query is outside the applicability domain.")
        elif centered >= 0.7 and validation_status.startswith("externally_validated"):
            confidence = "high"
            uncertainty = "lower"
        elif centered >= 0.4:
            confidence = "medium"
            uncertainty = "moderate"
        else:
            confidence = "low"
            uncertainty = "high"
    else:
        warnings.append("No probability or defensible uncertainty estimate was available.")
    if calibration_status in {"calibration_poor", "uncalibrated"}:
        warnings.append("Calibration is missing or poor; probability confidence may be unreliable.")
    return {
        "prediction_value": payload.get("prediction_value"),
        "prediction_label": payload.get("prediction_label"),
        "confidence": confidence,
        "uncertainty": uncertainty,
        "applicability_domain": domain_status,
        "model_id": payload.get("model_id"),
        "model_version": payload.get("model_version"),
        "dataset_version": payload.get("dataset_version"),
        "validation_status": validation_status,
        "calibration_status": calibration_status,
        "method": method,
        "warnings": warnings,
    }


def evaluate_activation_gate(model_family: str, metadata: dict[str, Any]) -> dict[str, Any]:
    family = _normalize_endpoint(model_family)
    policies = activation_policies()
    policy = policies.get(family) or policies["default"]
    checks = []

    def add(name: str, passed: bool, detail: str):
        checks.append({"name": name, "passed": passed, "detail": detail})

    sample_count = int(metadata.get("sample_count") or metadata.get("train_count") or 0) + int(metadata.get("test_count") or 0)
    add("dataset_provenance", bool(metadata.get("dataset_provenance") or metadata.get("dataset_version")), "Dataset provenance/version is required.")
    add("split_integrity", metadata.get("split_integrity_status") in {"passed", "passed_with_warnings"}, "Train/validation/test split integrity must be documented.")
    add("leakage_check", metadata.get("leakage_status") in {"passed", "possible_overlap_reviewed"}, "Duplicate/leakage checks must pass or be reviewed.")
    add("minimum_sample_size", sample_count >= policy["minimum_sample_size"], f"Minimum sample size for {family or 'default'} is {policy['minimum_sample_size']}.")
    add("required_metrics", all(metric in (metadata.get("metrics") or {}) for metric in policy["required_metrics"]), f"Required metrics: {', '.join(policy['required_metrics'])}.")
    add("reproducibility", bool(metadata.get("random_state") is not None and metadata.get("feature_schema")), "Random state and feature schema are required.")
    if policy["external_validation_required"]:
        add("external_validation", str(metadata.get("external_validation_status") or "").startswith("externally_validated"), "External validation is required for activation eligibility.")
    if policy["calibration_required"]:
        add("calibration", metadata.get("calibration_status") in {"calibration_good", "calibration_moderate", "calibration_evaluated"}, "Calibration must be evaluated.")
    add("applicability_domain", metadata.get("applicability_domain_status") in {"available", "evaluated"}, "Applicability domain coverage must be available.")

    passed = all(check["passed"] for check in checks)
    state = "ACTIVATION_ELIGIBLE" if passed else "VALIDATION_FAILED"
    return {
        "model_family": family or "default",
        "activation_policy_id": policy["activation_policy_id"],
        "activation_state": state,
        "checks": checks,
        "warnings": [] if passed else ["Model is not activation eligible until failed checks are resolved."],
        "scientific_notice": SCIENTIFIC_NOTICE,
    }


def activation_policies() -> dict[str, dict[str, Any]]:
    return {
        "admet_toxicity": {
            "activation_policy_id": "admet_toxicity_activation_v1",
            "minimum_sample_size": 20,
            "required_metrics": ["balanced_accuracy", "precision", "recall", "f1"],
            "external_validation_required": False,
            "calibration_required": False,
        },
        "activity": {
            "activation_policy_id": "activity_target_specific_activation_v1",
            "minimum_sample_size": 50,
            "required_metrics": ["balanced_accuracy", "precision", "recall"],
            "external_validation_required": True,
            "calibration_required": True,
        },
        "selectivity": {
            "activation_policy_id": "selectivity_panel_activation_v1",
            "minimum_sample_size": 50,
            "required_metrics": ["selectivity_margin_validation"],
            "external_validation_required": True,
            "calibration_required": False,
        },
        "default": {
            "activation_policy_id": "family_specific_activation_policy_required",
            "minimum_sample_size": 20,
            "required_metrics": ["validation_metric"],
            "external_validation_required": True,
            "calibration_required": True,
        },
    }


def explain_candidate_ranking(candidate: dict[str, Any], scoring_profile: str = "balanced_admet") -> dict[str, Any]:
    dimensions = []
    for dim in RANKING_DIMENSIONS:
        raw = candidate.get(dim) or candidate.get(f"{dim}_summary") or candidate.get(f"{dim}_status")
        available = raw is not None
        dimensions.append({
            "dimension": dim,
            "status": "available" if available else "unavailable",
            "evidence_type": _dimension_evidence_type(dim, raw),
            "value": raw if available else None,
            "contributed": available,
            "limitation": None if available else "No real evidence was available for this ranking dimension.",
        })
    penalties = candidate.get("penalties") or []
    rejection_reasons = candidate.get("rejection_reasons") or []
    uncertainty_caveats = candidate.get("uncertainty_caveats") or []
    return {
        "compound_name": candidate.get("compound_name") or "Unnamed",
        "scoring_profile": scoring_profile,
        "dimensions": dimensions,
        "weights_profile": "profile-specific weights apply only to available evidence; missing evidence is penalized rather than fabricated",
        "penalties": penalties,
        "rejection_reasons": rejection_reasons,
        "uncertainty_caveats": uncertainty_caveats or ["Missing dimensions reduce ranking confidence."],
        "scientific_notice": SCIENTIFIC_NOTICE,
    }


def _dimension_evidence_type(dim: str, value: Any) -> str:
    if value is None:
        return "MISSING"
    if dim in {"activity", "selectivity", "evidence_quality"}:
        return "DATABASE EVIDENCE"
    if dim in {"admet", "toxicity", "drug_likeness", "structural_alerts"}:
        return "RULE-BASED HEURISTIC"
    if dim in {"applicability_domain", "uncertainty_confidence"}:
        return "MODEL PREDICTION"
    return "COMPUTATIONAL INFERENCE"


def classify_repurposing_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    source = str(candidate.get("source_type") or candidate.get("candidate_source") or "").lower()
    max_phase = candidate.get("max_phase")
    if max_phase in {4, "4"} or "approved" in source:
        kind = "approved_drug"
    elif max_phase in {1, 2, 3, "1", "2", "3"} or "investigational" in source:
        kind = "investigational_compound"
    elif "generated" in source:
        kind = "generated_molecule"
    elif candidate.get("trained_model_prediction"):
        kind = "predicted_candidate"
    else:
        kind = "database_hit"
    return {
        "candidate_type": kind,
        "provenance": candidate.get("provenance") or candidate.get("data_source") or "not_available",
        "evidence_classification": "database-derived evidence" if kind in {"approved_drug", "investigational_compound", "database_hit"} else "model prediction" if kind == "predicted_candidate" else "generated architecture placeholder",
        "warnings": ["Generated molecules are not implemented as validated DrugScreen360 evidence."] if kind == "generated_molecule" else [],
    }


def m2_scientific_core_status() -> dict[str, Any]:
    endpoints = endpoint_aware_admet_status()
    active_endpoints = [item for item in endpoints if item["status"] == "active"]
    return {
        "app_name": "DrugScreen360",
        "app_version": app_version(),
        "m2_status": "drug_discovery_scientific_core_hardening",
        "admet_endpoints": endpoints,
        "activity_model": activity_model_status(),
        "selectivity_model": selectivity_model_status(),
        "future_providers": FUTURE_PROVIDER_CONTRACTS,
        "job_lifecycle": JOB_LIFECYCLE_CONTRACT,
        "activation_policies": activation_policies(),
        "active_endpoint_count": len(active_endpoints),
        "unsupported_capabilities": ["docking", "molecular_dynamics", "de_novo_generation", "lead_optimization_engine"],
        "scientific_notice": SCIENTIFIC_NOTICE,
    }
