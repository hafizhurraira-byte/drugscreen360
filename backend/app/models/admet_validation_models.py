from pydantic import BaseModel, Field
from typing import Any

class ExternalValidationRunRequest(BaseModel):
    model_id: str = Field(..., min_length=1)
    external_dataset_id: int
    notes: str | None = None

class ExternalValidationRunSummary(BaseModel):
    id: int
    model_id: str
    training_run_id: int | None = None
    external_dataset_id: int
    task_name: str | None = None
    task_type: str
    status: str
    valid_count: int
    invalid_count: int
    metric_summary: dict[str, Any] = Field(default_factory=dict)
    calibration_summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    notes: str | None = None
    created_at: str
