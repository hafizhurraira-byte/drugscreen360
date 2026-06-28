import json
from fastapi import APIRouter, HTTPException
from typing import Any, Dict, List, Optional

from app.database import get_connection, init_db
from app.models.admet_model_evidence_models import (
    ResolveEvidenceRequest,
    BatchResolveEvidenceRequest,
    ModelEvidenceStatusResponse,
    ModelEvidenceReadinessResponse
)
from app.services.admet_model_evidence_resolver import (
    resolve_model_evidence,
    batch_resolve_model_evidence
)
from app.services.admet_trained_model_service import (
    get_active_trained_model_info,
    discover_trained_models
)
from app.services.admet_validation_service import get_latest_external_validation_by_model

router = APIRouter(prefix="/admet-model-evidence", tags=["admet-model-evidence"])

@router.get("/status", response_model=ModelEvidenceStatusResponse)
def get_model_evidence_status():
    """
    Returns the active model status and its capabilities.
    """
    active_info = get_active_trained_model_info()
    status = active_info.get("status")
    
    if status != "available":
        return ModelEvidenceStatusResponse(
            status=status if status else "unavailable",
            validation_status="not_validated",
            calibration_status="uncalibrated",
            domain_available=False,
            explainability_available=False
        )
        
    model_id = active_info["model_id"]
    latest_val = get_latest_external_validation_by_model(model_id)
    validation_status = "validated" if latest_val else "not_validated"
    
    calibration_status = "uncalibrated"
    if latest_val:
        cal_summary = latest_val.get("calibration_summary") or {}
        if cal_summary.get("is_calibrated") or cal_summary.get("calibrated_model_saved"):
            calibration_status = "calibrated"

    return ModelEvidenceStatusResponse(
        active_model_id=model_id,
        model_name=active_info.get("model_name"),
        status=status,
        task_name=active_info.get("task_name"),
        task_type=active_info.get("task_type"),
        validation_status=validation_status,
        calibration_status=calibration_status,
        domain_available=True,
        explainability_available=True
    )

@router.post("/resolve")
def resolve_evidence_endpoint(payload: ResolveEvidenceRequest):
    """
    Resolves model evidence for a single candidate.
    """
    return resolve_model_evidence(
        candidate_name=payload.candidate_name,
        smiles=payload.smiles,
        descriptors=payload.descriptors,
        project_id=payload.project_id,
        disease_to_lead_run_id=payload.disease_to_lead_run_id,
        requested_tasks=payload.requested_tasks,
        active_model_preference=payload.active_model_preference
    )

@router.post("/batch-resolve")
def batch_resolve_evidence_endpoint(payload: BatchResolveEvidenceRequest):
    """
    Resolves model evidence for multiple candidates in batch and saves the run.
    """
    candidates_list = [c.model_dump() for c in payload.candidates]
    return batch_resolve_model_evidence(
        candidates=candidates_list,
        project_id=payload.project_id,
        disease_to_lead_run_id=payload.disease_to_lead_run_id,
        requested_tasks=payload.requested_tasks
    )

@router.get("/readiness", response_model=ModelEvidenceReadinessResponse)
def get_model_evidence_readiness():
    """
    Evaluates system readiness for generating trained model evidence.
    """
    init_db()
    
    # 1. Dataset check
    curated_dataset_available = False
    with get_connection() as connection:
        row = connection.execute("SELECT COUNT(*) FROM admet_datasets").fetchone()
        if row and row[0] > 0:
            curated_dataset_available = True
            
    # 2. Trained model check
    trained_models = discover_trained_models()
    trained_model_available = len(trained_models) > 0
    
    # 3. Active model check
    active_info = get_active_trained_model_info()
    model_active = active_info.get("status") == "available"
    
    model_artifact_exists = False
    model_compatible = False
    external_validation_available = False
    calibration_available = False
    
    if active_info.get("status") == "missing":
        model_id = active_info.get("model_id")
    elif model_active and active_info.get("model_id"):
        model_id = active_info["model_id"]
        # Find this model summary
        summary = next((m for m in trained_models if m["model_id"] == model_id), None)
        if summary:
            model_artifact_exists = summary.get("artifact_found", False)
            model_compatible = summary.get("status") == "valid"
            
        latest_val = get_latest_external_validation_by_model(model_id)
        if latest_val:
            external_validation_available = True
            cal_summary = latest_val.get("calibration_summary") or {}
            if cal_summary.get("is_calibrated") or cal_summary.get("calibrated_model_saved") or cal_summary.get("calibration_status") in {"available", "calibrated", "partially_calibrated", "uncalibrated"}:
                calibration_available = True
                
    # Determine readiness status
    if active_info.get("status") == "missing":
        status = "Not ready"
        next_action = "Clear or reactivate a valid trained model"
    elif model_active and model_compatible and external_validation_available and calibration_available:
        status = "Ready"
        next_action = "Rerun prediction"
    elif model_active and model_compatible:
        status = "Partially ready"
        next_action = "Validate/calibrate model"
    elif trained_model_available:
        status = "Not ready"
        next_action = "Activate model"
    elif curated_dataset_available:
        status = "Not ready"
        next_action = "Train model"
    else:
        status = "Not ready"
        next_action = "Import dataset"
        
    return ModelEvidenceReadinessResponse(
        status=status,
        curated_dataset_available=curated_dataset_available,
        trained_model_available=trained_model_available,
        model_active=model_active,
        model_artifact_exists=model_artifact_exists,
        model_compatible=model_compatible,
        external_validation_available=external_validation_available,
        calibration_available=calibration_available,
        next_action=next_action
    )

@router.get("/project/{project_id}")
def get_project_model_evidence_runs(project_id: int):
    """
    Retrieves previous model evidence runs associated with a project.
    """
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM admet_model_evidence_runs WHERE project_id = ? ORDER BY id DESC LIMIT 50",
            (project_id,)
        ).fetchall()
        
    runs = []
    for r in rows:
        runs.append({
            "id": r["id"],
            "project_id": r["project_id"],
            "disease_to_lead_run_id": r["disease_to_lead_run_id"],
            "active_model_id": r["active_model_id"],
            "candidate_count": r["candidate_count"],
            "evidence_available_count": r["evidence_available_count"],
            "outside_domain_count": r["outside_domain_count"],
            "high_uncertainty_count": r["high_uncertainty_count"],
            "model_task_type": r["model_task_type"],
            "summary": json.loads(r["summary_json"]),
            "warnings": json.loads(r["warnings_json"]) if r["warnings_json"] else [],
            "created_at": r["created_at"]
        })
    return runs
