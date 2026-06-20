from fastapi import APIRouter

from app.models.model_registry_models import (
    CompareModelsRequest,
    CompareModelsResponse,
    ModelStatusResponse,
    PredictAdmetRequest,
    PredictAdmetResponse,
)
from app.services.admet_predictor_service import compare_models, predict_admet
from app.services.model_registry import model_status_response

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/status", response_model=ModelStatusResponse)
def models_status():
    return model_status_response()


@router.post("/predict-admet", response_model=PredictAdmetResponse)
def predict_admet_endpoint(payload: PredictAdmetRequest):
    return predict_admet(payload.smiles, payload.models, payload.include_unavailable)


@router.post("/compare", response_model=CompareModelsResponse)
def compare_models_endpoint(payload: CompareModelsRequest):
    return compare_models(payload.smiles, payload.selected_models)
