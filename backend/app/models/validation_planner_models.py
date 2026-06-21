from typing import Any, Literal

from pydantic import BaseModel, Field


AssayPriority = Literal["essential", "recommended", "optional", "not_applicable"]


class ValidationCandidateInput(BaseModel):
    compound_name: str | None = None
    smiles: str | None = None
    canonical_smiles: str | None = None
    compound_id: str | None = None
    target_name: str | None = None
    priority_label: str | None = None
    domain_status: str | None = None
    uncertainty_level: str | None = None
    external_validation_status: str | None = None
    evidence_strength: str | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExperimentalValidationPlanRequest(BaseModel):
    source_type: str = "manual"
    project_id: int | None = None
    source_run_id: int | None = None
    plan_title: str | None = None
    candidates: list[ValidationCandidateInput] = Field(default_factory=list)
    manual_smiles_text: str | None = None
    max_candidates: int = 10
    include_toxicity_assays: bool = True
    include_adme_assays: bool = True
    include_target_assays: bool = True
    include_controls: bool = True


class RecommendedAssay(BaseModel):
    assay_name: str
    assay_category: str
    recommendation_priority: AssayPriority
    reason: str
    linked_computational_evidence: list[str] = Field(default_factory=list)
    suggested_readout: str
    suggested_controls: list[str] = Field(default_factory=list)
    decision_threshold_guidance: str
    expected_interpretation: str
    limitations: str
    safety_note: str


class ValidationPlanCandidateResult(BaseModel):
    compound_name: str | None = None
    compound_id: str | None = None
    smiles: str
    canonical_smiles: str | None = None
    valid: bool
    invalid_reason: str | None = None
    priority_label: str | None = None
    source_type: str
    source_id: str | None = None
    descriptors: dict[str, Any] = Field(default_factory=dict)
    rule_based_admet_summary: dict[str, Any] = Field(default_factory=dict)
    domain_status: str = "not available"
    uncertainty_level: str = "unknown"
    external_validation_status: str = "not available"
    evidence_strength: str = "not available"
    recommended_assays: list[RecommendedAssay] = Field(default_factory=list)
    decision_points: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommended_next_step: str


class ExperimentalValidationPlanResponse(BaseModel):
    plan_id: int
    project_id: int | None = None
    source_type: str
    plan_title: str
    candidate_count: int
    candidate_plans: list[ValidationPlanCandidateResult]
    overall_recommendations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    scientific_notice: str = "Experimental planning support only. Actual assay design must be reviewed by qualified laboratory personnel."
    created_at: str | None = None


class ExperimentalValidationPlanRunSummary(BaseModel):
    plan_id: int
    project_id: int | None = None
    source_type: str
    plan_title: str
    candidate_count: int
    essential_assay_count: int
    recommended_assay_count: int
    optional_assay_count: int
    warnings: list[str] = Field(default_factory=list)
    created_at: str | None = None


class ValidationPlanExportResponse(BaseModel):
    plan_id: int
    csv_url: str
    json_url: str
