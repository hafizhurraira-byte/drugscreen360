from typing import Any

from pydantic import BaseModel, Field


class DatasetRecord(BaseModel):
    id: int | None = None
    row_number: int | None = None
    dataset_id: int | None = None
    compound_name: str | None = None
    original_smiles: str | None = None
    canonical_smiles: str | None = None
    label_value: str | None = None
    is_valid: bool
    invalid_reason: str | None = None
    duplicate_group: str | None = None
    descriptors: dict[str, Any] | None = None
    created_at: str | None = None


class DatasetValidationSummary(BaseModel):
    total_rows: int
    valid_molecules: int
    invalid_smiles: int
    missing_labels: int
    duplicate_molecules: int
    unique_canonical_molecules: int
    label_distribution: dict[str, int] = Field(default_factory=dict)
    descriptor_success_count: int = 0
    descriptor_failure_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)


class DatasetUploadResponse(BaseModel):
    dataset_id: int
    name: str
    task_name: str | None = None
    label_column: str
    original_filename: str
    record_count: int
    valid_count: int
    invalid_count: int
    duplicate_count: int
    status: str
    summary: DatasetValidationSummary
    records_preview: list[DatasetRecord] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DatasetCurationRequest(BaseModel):
    dataset_id: int
    remove_invalid: bool = False
    remove_duplicates: bool = False


class DatasetCurationResult(BaseModel):
    dataset_id: int
    summary: DatasetValidationSummary
    records: list[DatasetRecord]


class DatasetExportResponse(BaseModel):
    dataset_id: int
    curated_csv_url: str
    curation_report_json_url: str
    warnings: list[str] = Field(default_factory=list)
