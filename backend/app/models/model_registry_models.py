from typing import Any, Literal

from pydantic import BaseModel, Field


ModelStatus = Literal["available", "unavailable", "disabled", "error", "missing", "mock"]


class ModelInfo(BaseModel):
    model_id: str
    model_name: str
    model_type: str
    prediction_tasks: list[str]
    status: ModelStatus
    input_type: str = "smiles"
    version: str | None = None
    source: str
    limitations: list[str]
    last_checked_at: str
    base_url_configured: bool | None = None
    api_key_configured: bool | None = None
    enabled: bool | None = None
    model_dir: str | None = None
    manifest_found: bool | None = None
    artifacts_found: bool | None = None
    warning: str | None = None


class PredictionResult(BaseModel):
    task_name: str
    prediction_label: str
    prediction_score: float | None = None
    probability: float | None = None
    confidence: str
    model_id: str
    model_name: str
    model_status: ModelStatus
    limitations: list[str]
    warnings: list[str] = Field(default_factory=list)
    domain_status: str | None = None
    uncertainty_level: str | None = None
    nearest_training_distance: float | None = None
    out_of_range_features: list[str] | None = None



class ModelPredictionBundle(BaseModel):
    model_id: str
    model_name: str
    model_status: ModelStatus
    prediction_source: str
    confidence: str
    predictions: list[PredictionResult]
    raw_output: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelStatusResponse(BaseModel):
    available_models: list[ModelInfo]
    unavailable_models: list[ModelInfo]
    supported_tasks: list[str]
    limitations: list[str]


class PredictAdmetRequest(BaseModel):
    smiles: str
    models: list[str] = Field(default_factory=lambda: ["rule_based_admet_v1"])
    include_unavailable: bool = True


class PredictAdmetResponse(BaseModel):
    canonical_smiles: str
    model_outputs: list[ModelPredictionBundle]
    combined_interpretation: str
    warnings: list[str]
    model_status_summary: dict[str, Any] = Field(default_factory=dict)
    disclaimer: str


class CompareModelsRequest(BaseModel):
    smiles: str
    selected_models: list[str] = Field(default_factory=lambda: ["rule_based_admet_v1", "local_admet_model", "external_admet_service"])


class CompareModelsResponse(BaseModel):
    canonical_smiles: str
    model_outputs: list[ModelPredictionBundle]
    agreement_summary: str
    final_cautious_interpretation: str
    disclaimer: str
