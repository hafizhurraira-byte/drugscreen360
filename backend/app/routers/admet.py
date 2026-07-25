from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.models.admet_models import AdmetEvaluateRequest, AdmetToxicityAssessment
from app.services.admet_endpoint_model_service import (
    activate_admet_endpoint,
    admet_activation_history,
    admet_model_status,
    batch_predict_admet_endpoints,
    deactivate_admet_endpoint,
    evaluate_admet_activation_gate,
    list_admet_models,
    predict_admet_endpoints,
    register_admet_artifact,
    verify_admet_artifact,
)
from app.services.admet_toxicity_engine import evaluate_admet_toxicity

router = APIRouter(prefix="/admet", tags=["admet"])


class RegisterAdmetModelRequest(BaseModel):
    endpoint: str
    source_dir: str
    overwrite: bool = False


class AdmetEndpointPredictRequest(BaseModel):
    smiles: str
    endpoints: list[str] = Field(default_factory=lambda: ["bbbp", "esol", "herg"])


class AdmetEndpointBatchPredictRequest(BaseModel):
    candidates: list[dict] = Field(default_factory=list)
    endpoints: list[str] = Field(default_factory=lambda: ["bbbp", "esol", "herg"])


@router.post("/evaluate", response_model=AdmetToxicityAssessment)
def evaluate_admet(payload: AdmetEvaluateRequest):
    return evaluate_admet_toxicity(payload.smiles)


@router.get("/models")
def models():
    return list_admet_models()


@router.get("/models/{endpoint}/status")
def model_status(endpoint: str):
    return admet_model_status(endpoint)


@router.get("/models/{endpoint}/metrics")
def model_metrics(endpoint: str):
    return verify_admet_artifact(endpoint)


@router.get("/models/{endpoint}/history")
def model_history(endpoint: str):
    return admet_activation_history(endpoint)


@router.post("/models/register")
def register_model(payload: RegisterAdmetModelRequest):
    return register_admet_artifact(payload.endpoint, payload.source_dir, payload.overwrite)


@router.post("/models/{endpoint}/activation-gate")
def activation_gate(endpoint: str):
    return evaluate_admet_activation_gate(endpoint)


@router.post("/models/{endpoint}/activate")
def activate_model(endpoint: str):
    return activate_admet_endpoint(endpoint)


@router.post("/models/{endpoint}/deactivate")
def deactivate_model(endpoint: str):
    return deactivate_admet_endpoint(endpoint)


@router.post("/predict")
def predict(payload: AdmetEndpointPredictRequest):
    return predict_admet_endpoints(payload.smiles, payload.endpoints)


@router.post("/batch-predict")
def batch_predict(payload: AdmetEndpointBatchPredictRequest):
    return batch_predict_admet_endpoints(payload.candidates, payload.endpoints)
