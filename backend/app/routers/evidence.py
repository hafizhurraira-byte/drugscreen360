from fastapi import APIRouter

from app.models.evidence_models import EvidenceBatchRequest, EvidenceBatchResponse, EvidenceCandidateRequest, EvidenceQualityAssessment
from app.services.evidence_history import save_evidence_summary
from app.services.evidence_quality import evaluate_batch_evidence, evaluate_candidate_evidence

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.post("/evaluate-candidate", response_model=EvidenceQualityAssessment)
def evaluate_candidate(payload: EvidenceCandidateRequest):
    assessment = evaluate_candidate_evidence(payload.candidate, check_bindingdb=payload.check_bindingdb)
    save_evidence_summary(payload.candidate, assessment)
    return assessment


@router.post("/evaluate-batch", response_model=EvidenceBatchResponse)
def evaluate_batch(payload: EvidenceBatchRequest):
    response = evaluate_batch_evidence(payload.candidates, check_bindingdb=payload.check_bindingdb)
    for item in response.evidence_table:
        save_evidence_summary(item, item.evidence)
    return response
