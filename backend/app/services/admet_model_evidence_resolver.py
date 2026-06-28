import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from rdkit import Chem

from app.database import get_connection, init_db
from app.services.descriptors import parse_smiles, calculate_descriptors
from app.services.admet_trained_model_service import (
    get_active_trained_model_info,
    predict_trained_model,
    discover_trained_models,
    validate_trained_model
)
from app.services.admet_domain_service import evaluate_domain_internal
from app.services.admet_validation_service import get_latest_external_validation_by_model
from app.services.admet_explain_service import explain_prediction
from app.models.admet_explain_models import AdmetPredictionExplainRequest

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def resolve_model_evidence(
    candidate_name: str,
    smiles: str,
    descriptors: Optional[Dict[str, Any]] = None,
    project_id: Optional[int] = None,
    disease_to_lead_run_id: Optional[int] = None,
    requested_tasks: Optional[List[str]] = None,
    active_model_preference: Optional[str] = None
) -> Dict[str, Any]:
    """
    For a candidate molecule, resolves the best available compatible ADMET model evidence.
    """
    # Initialize defaults for unresolved model
    result = {
        "model_available": False,
        "active_model_id": None,
        "model_name": None,
        "model_type": None,
        "task_type": None,
        "endpoint_predicted": None,
        "prediction_value": None,
        "prediction_label": None,
        "prediction_probability": None,
        "confidence_level": "None",
        "uncertainty_score": 0.0,
        "uncertainty_level": "unknown",
        "applicability_domain_status": "not_available",
        "distance_to_training_domain": None,
        "calibration_status": "uncalibrated",
        "external_validation_status": "not_validated",
        "explanation_available": False,
        "feature_contributions": [],
        "model_limitations": [],
        "evidence_strength": "rule_based_only",
        "missing_evidence": ["trained model prediction"],
        "resolution_reason": "No active trained ADMET model was available.",
        "failure_reason": "no_active_model"
    }

    # 1. Parse SMILES and validate molecule
    try:
        mol = parse_smiles(smiles)
        canonical = Chem.MolToSmiles(mol, canonical=True)
    except Exception as exc:
        result["resolution_reason"] = f"Invalid SMILES structure: {exc}"
        result["failure_reason"] = "unsupported_smiles"
        result["evidence_strength"] = "unavailable"
        result["missing_evidence"].append("valid molecule structure")
        return result

    # 2. Get active trained model info
    active_info = get_active_trained_model_info()
    status = active_info.get("status")

    if status == "disabled" or status == "unavailable" or not active_info.get("model_id"):
        result["resolution_reason"] = "No active trained ADMET model is currently selected in the system."
        result["failure_reason"] = "no_active_model"
        return result

    if status in {"error", "missing"}:
        result["resolution_reason"] = f"Active model is in error state: {'; '.join(active_info.get('warnings', []))}"
        result["failure_reason"] = "model_file_missing"
        return result

    model_id = active_info["model_id"]
    model_name = active_info["model_name"]
    model_task = active_info.get("task_name")
    model_task_type = active_info.get("task_type")

    # 3. Check requested task compatibility
    # If requested_tasks is specified, check if model_task matches any of the requested tasks
    if requested_tasks and model_task not in requested_tasks:
        result["resolution_reason"] = f"Active model '{model_name}' predicted task '{model_task}' is not compatible with requested tasks: {requested_tasks}."
        result["failure_reason"] = "no_compatible_model_for_task"
        return result

    # Check descriptors/features availability
    if not descriptors:
        try:
            descriptors = calculate_descriptors(canonical).model_dump()
        except Exception as exc:
            result["resolution_reason"] = f"Could not calculate features for SMILES: {exc}"
            result["failure_reason"] = "insufficient_features"
            return result

    # 4. Generate predictions
    try:
        pred = predict_trained_model(canonical, model_id)
    except Exception as exc:
        result["resolution_reason"] = f"Prediction execution failed: {exc}"
        result["failure_reason"] = "prediction_failed"
        return result

    # Successfully resolved prediction
    result["model_available"] = True
    result["active_model_id"] = model_id
    result["model_name"] = model_name
    result["model_type"] = "trained_local_model"
    result["task_type"] = model_task_type
    result["endpoint_predicted"] = model_task
    result["prediction_value"] = pred.get("prediction_value")
    result["prediction_label"] = pred.get("prediction_label")
    result["prediction_probability"] = pred.get("prediction_score") # prediction_score represents class probability
    
    # Applicability Domain and Uncertainty
    domain_status = pred.get("domain_status") or "not_available"
    uncertainty_level = pred.get("uncertainty_level") or "unknown"
    result["applicability_domain_status"] = domain_status
    result["distance_to_training_domain"] = pred.get("nearest_training_distance")
    
    # Uncertainty score mapping (0.0 to 1.0)
    uncertainty_score = 0.5
    if uncertainty_level == "high":
        uncertainty_score = 0.9
        result["confidence_level"] = "Low"
    elif uncertainty_level == "moderate":
        uncertainty_score = 0.5
        result["confidence_level"] = "Medium"
    elif uncertainty_level == "low":
        uncertainty_score = 0.1
        result["confidence_level"] = "High"
    else:
        result["confidence_level"] = "Medium"
    result["uncertainty_level"] = uncertainty_level
    result["uncertainty_score"] = uncertainty_score

    # 5. External Validation and Calibration status
    latest_val = get_latest_external_validation_by_model(model_id)
    if latest_val:
        result["external_validation_status"] = latest_val.get("validation_evidence_status") or "validated"
        cal_summary = latest_val.get("calibration_summary") or {}
        if cal_summary.get("is_calibrated") or cal_summary.get("calibrated_model_saved"):
            result["calibration_status"] = "calibrated"
        elif cal_summary.get("calibration_status") == "available":
            result["calibration_status"] = cal_summary.get("calibration_quality") or "calibration_evaluated"
        else:
            result["calibration_status"] = "uncalibrated"
    else:
        result["external_validation_status"] = "not_validated"
        result["calibration_status"] = "uncalibrated"

    # 6. Feature explanations
    try:
        explain_res = explain_prediction(
            AdmetPredictionExplainRequest(
                model_id=model_id,
                smiles=canonical,
                include_domain=True,
                include_external_validation=True,
                project_id=project_id
            )
        )
        result["explanation_available"] = True
        
        # Pull top features
        top_feats = []
        if explain_res.important_features:
            for feat in explain_res.important_features[:3]:
                top_feats.append({
                    "feature_name": getattr(feat, "feature_name", getattr(feat, "feature", "")),
                    "importance": getattr(feat, "importance", getattr(feat, "value", 0.0)),
                    "direction": getattr(feat, "direction", "unknown"),
                    "description": getattr(feat, "description", getattr(feat, "interpretation", ""))
                })
        result["feature_contributions"] = top_feats
        
        # Map evidence strength
        strength = explain_res.evidence_strength
        if strength == "externally_supported":
            result["evidence_strength"] = "strong_model_evidence"
        elif strength == "strong_internal_only":
            result["evidence_strength"] = "strong_model_evidence"
        elif strength == "moderate_internal_only":
            result["evidence_strength"] = "moderate_model_evidence"
        elif strength in ("weak_internal", "externally_weak", "uncertain"):
            result["evidence_strength"] = "weak_model_evidence"
        else:
            result["evidence_strength"] = "weak_model_evidence"
            
    except Exception as exc:
        result["explanation_available"] = False
        result["evidence_strength"] = "weak_model_evidence"
        
    result["model_limitations"] = pred.get("limitations") or []
    
    # Calculate missing evidence list
    missing = []
    if result["external_validation_status"] != "validated":
        missing.append("external validation")
    if result["calibration_status"] not in {"calibrated", "calibration_good", "calibration_moderate", "calibration_poor", "calibration_evaluated", "partially_calibrated", "uncalibrated"}:
        missing.append("model calibration")
    if domain_status == "outside_domain":
        missing.append("inside-domain sample data")
    
    result["missing_evidence"] = missing
    result["resolution_reason"] = f"Resolved predictions from compatible active model '{model_name}' on task '{model_task}'."
    result["failure_reason"] = None

    return result


def batch_resolve_model_evidence(
    candidates: List[Dict[str, Any]],
    project_id: Optional[int] = None,
    disease_to_lead_run_id: Optional[int] = None,
    requested_tasks: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Batch resolves model evidence for multiple candidates and logs the run to the database.
    """
    init_db()
    
    active_info = get_active_trained_model_info()
    active_model_id = active_info.get("model_id") if active_info.get("status") == "available" else None
    
    resolved_candidates = []
    evidence_available_count = 0
    outside_domain_count = 0
    high_uncertainty_count = 0
    model_task_type = active_info.get("task_type")
    
    warnings = []
    if not active_model_id:
        warnings.append("No active trained ADMET model is available for this run.")

    for c in candidates:
        name = c.get("compound_name") or c.get("compound_id") or "Unnamed"
        smiles = c.get("smiles") or c.get("canonical_smiles")
        desc = c.get("descriptors")
        
        evidence = resolve_model_evidence(
            candidate_name=name,
            smiles=smiles,
            descriptors=desc,
            project_id=project_id,
            disease_to_lead_run_id=disease_to_lead_run_id,
            requested_tasks=requested_tasks
        )
        
        resolved_candidates.append({
            "candidate_name": name,
            "smiles": smiles,
            "canonical_smiles": smiles, # fallback
            "evidence": evidence
        })
        
        if evidence["model_available"]:
            evidence_available_count += 1
            if evidence["applicability_domain_status"] == "outside_domain":
                outside_domain_count += 1
            if evidence["confidence_level"] == "Low":
                high_uncertainty_count += 1

    # Log to admet_model_evidence_runs
    summary = {
        "candidate_count": len(candidates),
        "evidence_available_count": evidence_available_count,
        "outside_domain_count": outside_domain_count,
        "high_uncertainty_count": high_uncertainty_count,
        "warnings": warnings,
        "candidates": resolved_candidates
    }
    
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO admet_model_evidence_runs (
                project_id, disease_to_lead_run_id, active_model_id, candidate_count,
                evidence_available_count, outside_domain_count, high_uncertainty_count,
                model_task_type, summary_json, warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                disease_to_lead_run_id,
                active_model_id,
                len(candidates),
                evidence_available_count,
                outside_domain_count,
                high_uncertainty_count,
                model_task_type,
                json.dumps(summary),
                json.dumps(warnings)
            )
        )
        run_id = int(cursor.lastrowid)
        
        for rc in resolved_candidates:
            ev = rc["evidence"]
            connection.execute(
                """
                INSERT INTO admet_model_evidence_candidates (
                    run_id, candidate_name, smiles, canonical_smiles, model_available,
                    prediction_json, domain_json, uncertainty_json, explainability_json,
                    evidence_strength, missing_evidence_json, warnings_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    rc["candidate_name"],
                    rc["smiles"],
                    rc["smiles"],
                    1 if ev["model_available"] else 0,
                    json.dumps({
                        "prediction_value": ev["prediction_value"],
                        "prediction_label": ev["prediction_label"],
                        "prediction_probability": ev["prediction_probability"],
                        "endpoint_predicted": ev["endpoint_predicted"],
                        "model_name": ev["model_name"]
                    }),
                    json.dumps({
                        "domain_status": ev["applicability_domain_status"],
                        "distance": ev["distance_to_training_domain"]
                    }),
                    json.dumps({
                        "confidence_level": ev["confidence_level"],
                        "uncertainty_score": ev["uncertainty_score"]
                    }),
                    json.dumps({
                        "explanation_available": ev["explanation_available"],
                        "feature_contributions": ev["feature_contributions"]
                    }),
                    ev["evidence_strength"],
                    json.dumps(ev["missing_evidence"]),
                    json.dumps([ev["resolution_reason"]] if ev["resolution_reason"] else [])
                )
            )
            
    return {
        "run_id": run_id,
        "project_id": project_id,
        "disease_to_lead_run_id": disease_to_lead_run_id,
        "active_model_id": active_model_id,
        "candidate_count": len(candidates),
        "evidence_available_count": evidence_available_count,
        "outside_domain_count": outside_domain_count,
        "high_uncertainty_count": high_uncertainty_count,
        "model_task_type": model_task_type,
        "resolved_candidates": resolved_candidates,
        "warnings": warnings,
        "created_at": _now()
    }
