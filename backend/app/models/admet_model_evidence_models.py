from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

class CandidateEvidenceInput(BaseModel):
    compound_name: Optional[str] = None
    compound_id: Optional[str] = None
    smiles: str
    descriptors: Optional[Dict[str, Any]] = None

class ResolveEvidenceRequest(BaseModel):
    candidate_name: str
    smiles: str
    descriptors: Optional[Dict[str, Any]] = None
    project_id: Optional[int] = None
    disease_to_lead_run_id: Optional[int] = None
    requested_tasks: Optional[List[str]] = None
    active_model_preference: Optional[str] = None

class BatchResolveEvidenceRequest(BaseModel):
    candidates: List[CandidateEvidenceInput]
    project_id: Optional[int] = None
    disease_to_lead_run_id: Optional[int] = None
    requested_tasks: Optional[List[str]] = None

class ModelEvidenceStatusResponse(BaseModel):
    active_model_id: Optional[str] = None
    model_name: Optional[str] = None
    status: str
    task_name: Optional[str] = None
    task_type: Optional[str] = None
    validation_status: str
    calibration_status: str
    domain_available: bool
    explainability_available: bool

class ModelEvidenceReadinessResponse(BaseModel):
    status: str  # Ready, Partially ready, Not ready
    curated_dataset_available: bool
    trained_model_available: bool
    model_active: bool
    model_artifact_exists: bool
    model_compatible: bool
    external_validation_available: bool
    calibration_available: bool
    next_action: str
