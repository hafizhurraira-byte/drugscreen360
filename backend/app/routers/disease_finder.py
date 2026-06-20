from fastapi import APIRouter, HTTPException, Query

from app.models.disease_models import DiseaseSearchResponse, DiseaseTargetsResponse
from app.services import open_targets_service
from app.services.disease_history import save_disease_search

router = APIRouter(prefix="/disease-finder", tags=["disease-finder"])


@router.get("/diseases", response_model=DiseaseSearchResponse)
def search_diseases(query: str = Query(..., min_length=1)):
    try:
        diseases = open_targets_service.search_diseases(query)
    except open_targets_service.OpenTargetsUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not diseases:
        raise HTTPException(status_code=404, detail=f"No Open Targets disease matches found for '{query}'.")
    save_disease_search(query=query, disease_id=None, disease_name=None, targets=[])
    return DiseaseSearchResponse(query=query, diseases=diseases, cache_metadata=open_targets_service.last_cache_metadata)


@router.get("/disease/{disease_id}/targets", response_model=DiseaseTargetsResponse)
def get_disease_targets(disease_id: str, limit: int = Query(default=25, ge=1, le=100)):
    try:
        targets = open_targets_service.get_disease_targets(disease_id, limit=limit)
    except open_targets_service.OpenTargetsUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not targets:
        raise HTTPException(status_code=404, detail="No associated Open Targets targets found for this disease.")
    save_disease_search(query=disease_id, disease_id=disease_id, disease_name=None, targets=targets)
    return DiseaseTargetsResponse(
        disease_id=disease_id,
        targets=targets,
        cache_metadata=open_targets_service.last_cache_metadata,
    )
