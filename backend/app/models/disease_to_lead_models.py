from typing import Any
from pydantic import BaseModel, Field

class DiseaseToLeadRequest(BaseModel):
    disease_name: str
    target_name: str | None = None
    known_compound: str | None = None
    candidate_limit: int = Field(default=10, ge=1, le=25)
    similarity_limit: int = Field(default=10, ge=1, le=25)
    analysis_depth: str = Field(default="standard")  # quick, standard, full
    project_id: int | None = None

class DiseaseToLeadResponse(BaseModel):
    workflow_id: str
    project_id: int | None = None
    disease_name: str
    target_name: str | None = None
    discovered_candidates: list[dict[str, Any]]
    similar_candidates: list[dict[str, Any]]
    selected_candidates: list[dict[str, Any]]
    screening_summary: dict[str, Any]
    admet_summary: dict[str, Any]
    lead_prioritization_run_id: int | None = None
    validation_plan_id: int | None = None
    final_report_id: int | None = None
    warnings: list[str]
    missing_steps: list[str]
    scientific_notice: str = "Computational estimate only. Requires experimental and external validation."
