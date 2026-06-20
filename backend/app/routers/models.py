from fastapi import APIRouter

from app.models.model_registry_models import (
    CompareModelsRequest,
    CompareModelsResponse,
    ModelStatusResponse,
    PredictAdmetRequest,
    PredictAdmetResponse,
)
from app.services.admet_predictor_service import compare_models, predict_admet
from app.services.local_admet_model import local_admet_manifest_preview, validate_local_admet_model
from app.services.model_registry import model_status_response

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/status", response_model=ModelStatusResponse)
def models_status():
    return model_status_response()


@router.get("/local-admet/validate")
def validate_local_admet():
    return validate_local_admet_model()


@router.get("/local-admet/manifest-preview")
def preview_local_admet_manifest():
    return local_admet_manifest_preview()


@router.post("/predict-admet", response_model=PredictAdmetResponse)
def predict_admet_endpoint(payload: PredictAdmetRequest):
    return predict_admet(payload.smiles, payload.models, payload.include_unavailable)


@router.post("/compare", response_model=CompareModelsResponse)
def compare_models_endpoint(payload: CompareModelsRequest):
    return compare_models(payload.smiles, payload.selected_models)
