from typing import Any, Literal

from pydantic import BaseModel, Field


ResultDirection = Literal["favorable", "unfavorable", "neutral", "inconclusive", "not_applicable"]
FeedbackLabel = Literal[
    "prediction_supported",
    "prediction_contradicted",
    "inconclusive",
    "not_comparable",
    "insufficient_context",
]


class ExperimentalResultInput(BaseModel):
    compound_name: str | None = None
    smiles: str | None = None
    canonical_smiles: str | None = None
    assay_name: str
    assay_category: str
    measured_value: str | None = None
    measurement_unit: str | None = None
    qualitative_result: str | None = None
    result_direction: ResultDirection
    assay_date: str | None = None
    replicate_count: int | None = None
    notes: str | None = None
    source_type: str = "manual"


class ExperimentalResultCreateRequest(BaseModel):
    project_id: int | None = None
    validation_plan_id: int | None = None
    source_type: str = "manual"
    results: list[ExperimentalResultInput] = Field(default_factory=list)


class InvalidExperimentalResultRow(BaseModel):
    row_number: int
    input_value: str | None = None
    error_reason: str


class SavedExperimentalResult(BaseModel):
    id: int | None = None
    batch_id: int | None = None
    project_id: int | None = None
    validation_plan_id: int | None = None
    compound_name: str | None = None
    smiles: str | None = None
    canonical_smiles: str | None = None
    assay_name: str
    assay_category: str
    measured_value: str | None = None
    measurement_unit: str | None = None
    qualitative_result: str | None = None
    result_direction: str
    replicate_count: int | None = None
    notes: str | None = None
    created_at: str | None = None


class ExperimentalResultBatchResponse(BaseModel):
    result_batch_id: int
    project_id: int | None = None
    validation_plan_id: int | None = None
    source_type: str
    result_count: int
    accepted_count: int
    rejected_count: int
    saved_results: list[SavedExperimentalResult] = Field(default_factory=list)
    invalid_rows: list[InvalidExperimentalResultRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    scientific_notice: str = "Experimental feedback summary only. Interpretation requires qualified scientific review."
    created_at: str | None = None


class ExperimentalResultBatchSummary(BaseModel):
    result_batch_id: int
    project_id: int | None = None
    validation_plan_id: int | None = None
    source_type: str
    result_count: int
    accepted_count: int
    rejected_count: int
    warnings: list[str] = Field(default_factory=list)
    created_at: str | None = None


class ExperimentalFeedbackCompareRequest(BaseModel):
    project_id: int | None = None
    result_batch_id: int
    model_id: str | None = None
    lead_prioritization_run_id: int | None = None
    validation_plan_id: int | None = None


class CandidateExperimentalFeedback(BaseModel):
    compound_name: str | None = None
    canonical_smiles: str | None = None
    assay_name: str
    assay_category: str
    experimental_result_summary: dict[str, Any] = Field(default_factory=dict)
    linked_computational_prediction: dict[str, Any] = Field(default_factory=dict)
    domain_status: str = "not available"
    uncertainty_level: str = "unknown"
    evidence_strength: str = "not available"
    feedback_label: FeedbackLabel
    ranking_feedback: str = "ranking_inconclusive"
    explanation: str
    recommended_next_step: str
    limitations: list[str] = Field(default_factory=list)


class ExperimentalFeedbackResponse(BaseModel):
    feedback_id: int
    project_id: int | None = None
    result_batch_id: int
    linked_model_id: str | None = None
    linked_prioritization_run_id: int | None = None
    linked_validation_plan_id: int | None = None
    compared_result_count: int
    supported_count: int
    contradicted_count: int
    inconclusive_count: int
    not_comparable_count: int
    candidate_feedback: list[CandidateExperimentalFeedback] = Field(default_factory=list)
    overall_feedback_label: str
    validation_plan_followup_status: str = "not_evaluated"
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    scientific_notice: str = "Experimental feedback summary only. Interpretation requires qualified scientific review."
    created_at: str | None = None
