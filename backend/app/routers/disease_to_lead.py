from fastapi import APIRouter, HTTPException

from app.models.disease_to_lead_models import DiseaseToLeadRequest, DiseaseToLeadResponse
from app.services.disease_to_lead_service import run_disease_to_lead_workflow

router = APIRouter(prefix="/disease-to-lead", tags=["disease-to-lead"])

@router.post("/run", response_model=DiseaseToLeadResponse)
def run_workflow(payload: DiseaseToLeadRequest):
    try:
        result = run_disease_to_lead_workflow(payload)
        return DiseaseToLeadResponse(**result)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
