from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.activity_model_service import (
    activate_egfr_v2,
    activation_history,
    batch_predict_egfr_activity,
    deactivate_activity_model,
    egfr_activity_model_status,
    evaluate_egfr_v2_activation_gate,
    predict_egfr_activity,
    register_egfr_v2_artifact,
    verify_egfr_v2_artifact,
)


router = APIRouter(prefix="/activity", tags=["activity-models"])


class RegisterEgfrV2Request(BaseModel):
    source_dir: str | None = None
    copy_required_files: bool = False
    overwrite: bool = False


class ActivityPredictRequest(BaseModel):
    smiles: str
    target: str = "EGFR"


class ActivityBatchPredictRequest(BaseModel):
    target: str = "EGFR"
    candidates: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/models")
def activity_models():
    return {"models": [egfr_activity_model_status()]}


@router.get("/models/egfr/status")
def egfr_status():
    return egfr_activity_model_status()


@router.get("/models/egfr/metrics")
def egfr_metrics():
    status = egfr_activity_model_status()
    verification = verify_egfr_v2_artifact()
    return {"status": status, "verification": verification}


@router.post("/models/egfr/register")
def register_egfr(payload: RegisterEgfrV2Request):
    return register_egfr_v2_artifact(payload.source_dir, payload.copy_required_files, payload.overwrite)


@router.post("/models/egfr/activation-gate")
def egfr_activation_gate():
    return evaluate_egfr_v2_activation_gate()


@router.post("/models/egfr/activate")
def activate_egfr():
    return activate_egfr_v2()


@router.post("/models/egfr/deactivate")
def deactivate_egfr():
    return deactivate_activity_model("EGFR")


@router.get("/models/egfr/history")
def egfr_history():
    return activation_history("EGFR")


@router.post("/predict")
def predict_activity(payload: ActivityPredictRequest):
    return predict_egfr_activity(payload.smiles, payload.target)


@router.post("/egfr/predict")
def predict_egfr(payload: ActivityPredictRequest):
    return predict_egfr_activity(payload.smiles, "EGFR")


@router.post("/batch-predict")
def batch_predict_activity(payload: ActivityBatchPredictRequest):
    return batch_predict_egfr_activity(payload.candidates, payload.target)
