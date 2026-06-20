from typing import Any, Literal

from pydantic import BaseModel, Field

from app.constants import DISCLAIMER


class ProjectDiseaseContext(BaseModel):
    query: str | None = None
    disease_name: str | None = None
    disease_id: str | None = None
    description: str | None = None


class ProjectDiseaseTargetContext(BaseModel):
    gene_symbol: str | None = None
    target_name: str | None = None
    open_targets_target_id: str | None = None
    association_score: float | None = None
    ranking_reason: str | None = None


class ProjectChemblTargetContext(BaseModel):
    target_chembl_id: str | None = None
    preferred_name: str | None = None
    organism: str | None = None
    target_type: str | None = None
    accession: str | None = None
    target_priority_score: int | None = None
    target_ranking_reason: str | None = None


class ProjectSimilarityContext(BaseModel):
    reference_query: str | None = None
    reference_compound_name: str | None = None
    reference_pubchem_cid: int | None = None
    reference_smiles: str | None = None
    source: str | None = None
    threshold: int | None = None
    limit: int | None = None
    candidates_found: int = 0


class ProjectReportPayload(BaseModel):
    project_id: str | None = None
    workflow_type: Literal["disease_to_candidate", "target_to_candidate", "similarity_to_candidate"]
    title: str = "DrugScreen360 Project Screening Report"
    disease: ProjectDiseaseContext | None = None
    disease_target: ProjectDiseaseTargetContext | None = None
    chembl_target: ProjectChemblTargetContext | None = None
    similarity: ProjectSimilarityContext | None = None
    retrieved_candidate_count: int = 0
    selected_candidate_count: int = 0
    screened_candidate_count: int = 0
    batch_screening_results: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


class ProjectReportCreateRequest(BaseModel):
    title: str | None = None
    payload: ProjectReportPayload


class ProjectReportCreateResponse(BaseModel):
    project_report_id: int
    summary: dict[str, Any]
    saved: bool = True


class ProjectReportStored(BaseModel):
    id: int
    title: str
    workflow_type: str
    disease_name: str | None = None
    disease_id: str | None = None
    target_symbol: str | None = None
    chembl_target_id: str | None = None
    candidate_count: int
    screened_count: int
    top_candidate: str | None = None
    payload: ProjectReportPayload
    created_at: str
