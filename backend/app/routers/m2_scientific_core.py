from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.m2_scientific_core_service import (
    activity_model_status,
    assess_fingerprint_domain,
    build_uncertainty_contract,
    check_split_integrity,
    classify_repurposing_candidate,
    endpoint_aware_admet_status,
    evaluate_activation_gate,
    explain_candidate_ranking,
    m2_scientific_core_status,
    selectivity_model_status,
    FUTURE_PROVIDER_CONTRACTS,
    JOB_LIFECYCLE_CONTRACT,
)


router = APIRouter(prefix="/m2", tags=["m2-scientific-core"])


class DomainAssessRequest(BaseModel):
    query_smiles: str
    training_smiles: list[str] = Field(default_factory=list)
    threshold: float = 0.35


class SplitIntegrityRequest(BaseModel):
    records: list[dict[str, Any]] = Field(default_factory=list)


class ActivationGateRequest(BaseModel):
    model_family: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class UncertaintyContractRequest(BaseModel):
    prediction: dict[str, Any] = Field(default_factory=dict)


class RankingExplainRequest(BaseModel):
    candidate: dict[str, Any] = Field(default_factory=dict)
    scoring_profile: str = "balanced_admet"


class RepurposingClassifyRequest(BaseModel):
    candidate: dict[str, Any] = Field(default_factory=dict)


@router.get("/scientific-core/status")
def scientific_core_status():
    return m2_scientific_core_status()


@router.get("/admet/endpoints")
def admet_endpoints():
    return endpoint_aware_admet_status()


@router.get("/activity/status")
def activity_status():
    return activity_model_status()


@router.get("/selectivity/status")
def selectivity_status():
    return selectivity_model_status()


@router.get("/future-providers/status")
def future_providers_status():
    return FUTURE_PROVIDER_CONTRACTS


@router.get("/jobs/lifecycle")
def job_lifecycle_status():
    return JOB_LIFECYCLE_CONTRACT


@router.post("/applicability-domain/assess")
def applicability_domain(payload: DomainAssessRequest):
    return assess_fingerprint_domain(payload.query_smiles, payload.training_smiles, payload.threshold)


@router.post("/split-integrity/check")
def split_integrity(payload: SplitIntegrityRequest):
    return check_split_integrity(payload.records)


@router.post("/activation-gate/evaluate")
def activation_gate(payload: ActivationGateRequest):
    return evaluate_activation_gate(payload.model_family, payload.metadata)


@router.post("/uncertainty/contract")
def uncertainty_contract(payload: UncertaintyContractRequest):
    return build_uncertainty_contract(payload.prediction)


@router.post("/ranking/explain")
def ranking_explain(payload: RankingExplainRequest):
    return explain_candidate_ranking(payload.candidate, payload.scoring_profile)


@router.post("/repurposing/classify")
def repurposing_classify(payload: RepurposingClassifyRequest):
    return classify_repurposing_candidate(payload.candidate)
