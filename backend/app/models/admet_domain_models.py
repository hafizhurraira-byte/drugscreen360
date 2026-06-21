from typing import Any
from pydantic import BaseModel, Field


class DomainEvaluateRequest(BaseModel):
    model_id: str
    smiles: str
    top_k: int = Field(default=5, ge=1, le=50)


class DomainEvaluateResponse(BaseModel):
    model_id: str
    training_run_id: int | None = None
    task_name: str | None = None
    task_type: str
    query_smiles: str
    canonical_smiles: str
    descriptor_values: dict[str, float]
    descriptor_range_check: dict[str, Any]
    distance_summary: dict[str, Any]
    nearest_neighbors: list[dict[str, Any]]
    fingerprint_similarity: dict[str, Any]
    domain_status: str
    uncertainty_level: str
    warnings: list[str]
    limitations: list[str]
    scientific_notice: str = "Computational estimate only. Requires experimental and external validation."


class DomainModelSummaryResponse(BaseModel):
    descriptor_stats: dict[str, dict[str, float]]
    training_record_count: int
    task_type: str | None = None
    dataset_name: str | None = None
    domain_thresholds_used: dict[str, float]
    warnings: list[str]
    limitations: list[str]


class PredictWithDomainRequest(BaseModel):
    model_id: str | None = None
    smiles: str


class PredictWithDomainResponse(BaseModel):
    prediction: dict[str, Any]
    domain_evaluation: dict[str, Any]
    warnings: list[str]
    scientific_notice: str = "Computational estimate only. Requires experimental and external validation."
