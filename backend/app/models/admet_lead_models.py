from typing import Any, Literal

from pydantic import BaseModel, Field


ScoringProfile = Literal[
    "balanced_admet",
    "toxicity_avoidance",
    "permeability_focused",
    "solubility_focused",
    "model_confidence_focused",
]

PriorityLabel = Literal[
    "high_priority_for_review",
    "medium_priority_for_review",
    "low_priority_for_review",
    "deprioritize",
    "insufficient_data",
]


class LeadCandidateInput(BaseModel):
    compound_name: str | None = None
    smiles: str | None = None
    canonical_smiles: str | None = None
    compound_id: str | None = None
    source_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LeadPrioritizationRequest(BaseModel):
    source_type: str = "manual"
    project_id: int | None = None
    source_run_id: int | None = None
    scoring_profile: ScoringProfile = "balanced_admet"
    candidates: list[LeadCandidateInput] = Field(default_factory=list)
    manual_smiles_text: str | None = None
    include_trained_model: bool = True
    include_domain: bool = True
    include_explainability: bool = True


class LeadCandidateRankingResult(BaseModel):
    rank: int | None = None
    compound_name: str | None = None
    compound_id: str | None = None
    source_type: str
    source_id: str | None = None
    smiles: str
    canonical_smiles: str | None = None
    valid: bool
    excluded: bool = False
    exclusion_reason: str | None = None
    priority_label: PriorityLabel | None = None
    total_score: float | None = None
    score_components: dict[str, Any] = Field(default_factory=dict)
    descriptors: dict[str, Any] = Field(default_factory=dict)
    lipinski_status: str = "not evaluated"
    veber_status: str = "not evaluated"
    drug_likeness_status: str = "not evaluated"
    developability_risk: str = "not evaluated"
    rule_based_admet_summary: dict[str, Any] = Field(default_factory=dict)
    trained_model_prediction: dict[str, Any] | None = None
    domain_status: str = "not available"
    uncertainty_level: str = "unknown"
    external_validation_warning: str = "not available"
    explainability_evidence_strength: str = "not available"
    positive_factors: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    ranking_explanation: str
    recommended_next_validation_step: str
    warnings: list[str] = Field(default_factory=list)


class LeadPrioritizationRunSummary(BaseModel):
    run_id: int
    project_id: int | None = None
    source_type: str
    scoring_profile: str
    candidate_count: int
    ranked_count: int
    excluded_count: int
    ranked_candidates: list[LeadCandidateRankingResult]
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    scientific_notice: str = "Computational prioritization only. Requires experimental validation."
    created_at: str | None = None


class LeadPrioritizationExportResponse(BaseModel):
    run_id: int
    csv_url: str
    json_url: str
