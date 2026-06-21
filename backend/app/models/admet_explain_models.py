from typing import Any, Literal

from pydantic import BaseModel, Field


EvidenceStrength = Literal[
    "strong_internal_only",
    "moderate_internal_only",
    "weak_internal",
    "externally_supported",
    "externally_weak",
    "uncertain",
    "not_available",
]


class AdmetPredictionExplainRequest(BaseModel):
    model_id: str | None = None
    smiles: str = Field(..., min_length=1)
    include_domain: bool = True
    include_external_validation: bool = True
    project_id: int | None = None


class AdmetDescriptorExplanation(BaseModel):
    feature: str
    query_value: float | None = None
    training_min: float | None = None
    training_max: float | None = None
    training_mean: float | None = None
    training_std: float | None = None
    status: str
    explanation: str


class AdmetImportantFeature(BaseModel):
    feature: str
    value: float
    rank: int
    source: str
    interpretation: str


class AdmetPredictionExplanationResponse(BaseModel):
    model_id: str
    model_name: str
    task_name: str | None = None
    task_type: str
    query_smiles: str
    canonical_smiles: str
    prediction_label: str | None = None
    prediction_value: float | None = None
    prediction_probability: float | None = None
    descriptor_values: dict[str, float | int | None]
    descriptor_explanations: list[AdmetDescriptorExplanation] = Field(default_factory=list)
    important_features: list[AdmetImportantFeature] = Field(default_factory=list)
    feature_contribution_summary: str
    domain_status: str
    uncertainty_level: str
    external_validation_status: dict[str, Any]
    evidence_strength: EvidenceStrength
    model_card_summary: dict[str, Any] = Field(default_factory=dict)
    training_summary: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    scientific_notice: str = "Computational explanation only. Requires experimental and external validation."


class AdmetExplanationReportCreateRequest(BaseModel):
    model_id: str | None = None
    smiles: str = Field(..., min_length=1)
    formats: list[Literal["json", "pdf", "docx"]] = Field(default_factory=lambda: ["json", "pdf", "docx"])
    project_id: int | None = None


class AdmetExplanationReportCreateResponse(BaseModel):
    report_id: int
    model_id: str
    created_at: str
    available_formats: list[str]
    json_url: str | None = None
    pdf_url: str | None = None
    docx_url: str | None = None
    warnings: list[str] = Field(default_factory=list)


class AdmetExplanationReportListItem(BaseModel):
    report_id: int
    model_id: str
    canonical_smiles: str
    evidence_strength: str
    domain_status: str
    uncertainty_level: str
    created_at: str
    available_formats: list[str]
    json_url: str | None = None
    pdf_url: str | None = None
    docx_url: str | None = None
