from fastapi import APIRouter, HTTPException

from app.models.admet_domain_models import (
    DomainEvaluateRequest,
    DomainEvaluateResponse,
    DomainModelSummaryResponse,
    PredictWithDomainRequest,
    PredictWithDomainResponse,
)
from app.services.admet_domain_service import (
    evaluate_domain_internal,
    get_domain_summary_by_model,
)
from app.services.admet_trained_model_service import predict_trained_model, get_active_trained_model_info
from app.services.descriptors import parse_smiles

router = APIRouter(prefix="/api/admet-domain", tags=["admet-domain"])


@router.post("/evaluate", response_model=DomainEvaluateResponse)
def evaluate_domain(payload: DomainEvaluateRequest):
    # Validate SMILES structure first
    try:
        parse_smiles(payload.smiles)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid SMILES structure: {e}")

    try:
        res = evaluate_domain_internal(payload.model_id, payload.smiles, payload.top_k)
        # Ensure it conforms to the pydantic model structure
        return DomainEvaluateResponse(
            model_id=res["model_id"],
            training_run_id=res.get("training_run_id"),
            task_name=res.get("task_name"),
            task_type=res["task_type"],
            query_smiles=res["query_smiles"],
            canonical_smiles=res["canonical_smiles"],
            descriptor_values=res["descriptor_values"],
            descriptor_range_check=res["descriptor_range_check"],
            distance_summary=res["distance_summary"],
            nearest_neighbors=res["nearest_neighbors"],
            fingerprint_similarity=res["fingerprint_similarity"],
            domain_status=res["domain_status"],
            uncertainty_level=res["uncertainty_level"],
            warnings=res["warnings"],
            limitations=res["limitations"],
            scientific_notice=res.get("scientific_notice", "Computational estimate only. Requires experimental and external validation.")
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to evaluate domain: {e}")


@router.get("/model/{model_id}/summary", response_model=DomainModelSummaryResponse)
def get_domain_summary(model_id: str):
    res = get_domain_summary_by_model(model_id)
    if not res:
        raise HTTPException(status_code=404, detail=f"No domain summary available for model: {model_id}")
    return DomainModelSummaryResponse(
        descriptor_stats=res["descriptor_stats"],
        training_record_count=res["training_record_count"],
        task_type=res.get("task_type"),
        dataset_name=res.get("dataset_name"),
        domain_thresholds_used=res["domain_thresholds_used"],
        warnings=res["warnings"],
        limitations=res["limitations"],
    )


@router.post("/predict-with-domain", response_model=PredictWithDomainResponse)
def predict_with_domain(payload: PredictWithDomainRequest):
    # Validate SMILES structure first
    try:
        parse_smiles(payload.smiles)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid SMILES structure: {e}")

    model_id = payload.model_id
    if not model_id:
        active_info = get_active_trained_model_info()
        if active_info["status"] != "available":
            raise HTTPException(
                status_code=400,
                detail=f"Prediction failed: no active trained model or model is in status '{active_info['status']}'."
            )
        model_id = active_info["model_id"]

    try:
        pred_res = predict_trained_model(payload.smiles, model_id)
        domain_res = evaluate_domain_internal(model_id, payload.smiles)
        
        # Merge warning notices if applicable
        warnings = list(pred_res.get("warnings") or [])
        for w in domain_res.get("warnings") or []:
            if w not in warnings:
                warnings.append(w)
                
        return PredictWithDomainResponse(
            prediction=pred_res,
            domain_evaluation=domain_res,
            warnings=warnings,
            scientific_notice="Computational estimate only. Requires experimental and external validation."
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to perform prediction with domain: {e}")
