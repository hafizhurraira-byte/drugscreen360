from typing import Any, Literal

from pydantic import BaseModel, Field


ProjectStatus = Literal["active", "review", "completed", "archived"]
ProjectType = Literal[
    "single_molecule",
    "target_screening",
    "disease_screening",
    "similarity_screening",
    "batch_screening",
    "validation",
    "general_research",
]


class ProjectCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str | None = None
    disease_area: str | None = None
    target_name: str | None = None
    project_type: ProjectType = "general_research"
    status: ProjectStatus = "active"
    notes: str | None = None


class ProjectUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    disease_area: str | None = None
    target_name: str | None = None
    project_type: ProjectType | None = None
    status: ProjectStatus | None = None
    notes: str | None = None


class ProjectItem(BaseModel):
    id: int
    project_id: int
    item_type: str
    item_id: str
    item_title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ProjectSummary(BaseModel):
    id: int
    title: str
    description: str | None = None
    disease_area: str | None = None
    target_name: str | None = None
    project_type: ProjectType
    status: ProjectStatus
    notes: str | None = None
    created_at: str
    updated_at: str
    attached_item_count: int = 0
    export_count: int = 0
    latest_activity: str | None = None
    model_status_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ProjectActiveOption(BaseModel):
    id: int
    title: str
    project_type: ProjectType
    status: ProjectStatus
    disease_area: str | None = None
    target_name: str | None = None
    updated_at: str


class ProjectDetail(ProjectSummary):
    items: list[ProjectItem] = Field(default_factory=list)
    exports: list[dict[str, Any]] = Field(default_factory=list)


class ProjectAttachRequest(BaseModel):
    item_type: str = Field(..., min_length=1)
    item_id: str = Field(..., min_length=1)
    item_title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateDecisionMatrixRow(BaseModel):
    candidate_name: str = "not available"
    compound_id: str | None = None
    source_id: str | None = None
    source_workflow: str
    target_name: str | None = None
    disease_area: str | None = None
    molecular_weight: float | str | None = None
    logp: float | str | None = None
    tpsa: float | str | None = None
    lipinski_status: str = "not available"
    veber_status: str = "not available"
    admet_risk_summary: str = "not evaluated"
    evidence_level: str = "not evaluated"
    evidence_score: float | str | None = None
    model_prediction_status: str = "not available"
    decision_label: str
    decision_reason: str
    missing_data_warnings: list[str] = Field(default_factory=list)


class ProjectDashboardResponse(BaseModel):
    project: ProjectDetail
    summary_cards: dict[str, Any] = Field(default_factory=dict)
    item_counts: dict[str, int] = Field(default_factory=dict)
    candidate_matrix: list[CandidateDecisionMatrixRow] = Field(default_factory=list)
    model_status_summary: dict[str, Any] = Field(default_factory=dict)
    risk_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
