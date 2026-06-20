from fastapi import APIRouter

from app.models.admet_models import AdmetEvaluateRequest, AdmetToxicityAssessment
from app.services.admet_toxicity_engine import evaluate_admet_toxicity

router = APIRouter(prefix="/admet", tags=["admet"])


@router.post("/evaluate", response_model=AdmetToxicityAssessment)
def evaluate_admet(payload: AdmetEvaluateRequest):
    return evaluate_admet_toxicity(payload.smiles)
