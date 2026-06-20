from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.schemas import InputType


BenchmarkStatus = Literal["PASS", "REVIEW", "FAIL"]


class BenchmarkCompound(BaseModel):
    id: str
    name: str
    input_type: InputType
    query: str
    expected_general_behavior: str
    expected_warning_category: str
    explanation: str
    data_source_label: str = "benchmark_local"
    group: str | None = None


class BenchmarkRunRequest(BaseModel):
    selected_ids: list[str] = Field(default_factory=list)
    group_name: str | None = None
    max_items: int | None = Field(default=None, ge=1, le=50)


class BenchmarkResultItem(BaseModel):
    benchmark_id: str
    compound: str
    group: str
    input_type: str
    query: str
    expected_behavior: str
    expected_warning_category: str
    status: BenchmarkStatus
    reason: str
    actual_decision: str | None = None
    drug_likeness: str | None = None
    developability_risk: str | None = None
    admet_tox_concern_score: int | None = None
    admet_tox_concern_level: str | None = None
    structural_alert_risk: str | None = None
    structural_alerts: list[str] = Field(default_factory=list)
    descriptor_summary: dict[str, Any] = Field(default_factory=dict)
    clean_error: str | None = None
    recommendation: str
    cache_metadata: dict[str, Any] | None = None


class BenchmarkSummary(BaseModel):
    total_tested: int
    passed: int
    review: int
    failed: int
    warning_count: int
    most_common_warnings: list[str]
    compounds_needing_review: list[str]


class BenchmarkRunResponse(BaseModel):
    benchmark_run_id: int | None = None
    title: str = "DrugScreen360 Validation & Benchmarking Report"
    selected_group: str | None = None
    summary: BenchmarkSummary
    individual_results: list[BenchmarkResultItem]
    mismatches: list[BenchmarkResultItem]
    limitations: list[str]
    model_status_summary: dict = Field(default_factory=dict)
    created_at: str | None = None


class BenchmarkRunStored(BaseModel):
    id: int
    title: str
    selected_group: str | None
    total_tested: int
    passed: int
    review: int
    failed: int
    payload: BenchmarkRunResponse
    created_at: str
