from typing import Any

from pydantic import BaseModel, Field


class ParsedCompound(BaseModel):
    row_number: int
    compound_name: str | None = None
    compound_id: str | None = None
    original_smiles: str | None = None
    canonical_smiles: str | None = None
    valid: bool
    duplicate: bool = False
    error_reason: str | None = None
    descriptors: dict[str, Any] | None = None
    source: str | None = None
    notes: str | None = None


class InvalidCompound(BaseModel):
    row_number: int
    input_value: str | None = None
    error_reason: str


class BatchParseResponse(BaseModel):
    batch_id: int
    file_name: str
    file_type: str
    total_rows: int
    valid_compounds: int
    invalid_compounds: int
    duplicates_detected: int
    parsed_compounds: list[ParsedCompound]
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str]


class BatchLibraryScreenRequest(BaseModel):
    batch_id: int | None = None
    compounds: list[ParsedCompound] = Field(default_factory=list)
    max_compounds: int = Field(default=100, ge=1, le=500)
    run_model_predictions: bool = True


class BatchLibraryResultRow(BaseModel):
    batch_rank: int | None = None
    row_number: int
    compound_name: str | None = None
    compound_id: str | None = None
    canonical_smiles: str
    molecular_weight: float
    logp: float
    tpsa: float
    lipinski_pass: bool
    veber_pass: bool
    drug_likeness_status: str
    developability_risk: str
    absorption_risk: str
    solubility_risk: str
    structural_alert_risk: str
    overall_admet_tox_concern_score: int
    concern_level: str
    decision: str
    evidence_level: str = "Not evaluated"
    evidence_note: str = "Evidence quality not evaluated because uploaded compounds are not target-linked candidates."
    admet_prediction_source: str
    model_status: str
    model_confidence: str
    model_warnings: list[str] = Field(default_factory=list)
    rule_based_used: bool = True
    external_model_used: bool = False
    external_model_available: bool = False
    external_model_warning: str | None = None
    required_tests: list[str] = Field(default_factory=list)
    batch_priority_score: float
    priority_label: str
    ranking_reason: str
    descriptors: dict[str, Any]
    drug_likeness: dict[str, Any]
    admet_toxicity: dict[str, Any]
    model_predictions: dict[str, Any] | None = None
    limitations: list[str] = Field(default_factory=list)


class BatchLibraryScreenResponse(BaseModel):
    batch_screening_id: int | None = None
    batch_id: int | None = None
    screened_count: int
    failed_count: int
    results: list[BatchLibraryResultRow]
    ranking_summary: dict[str, Any]
    warnings: list[str]
    model_status_summary: dict[str, Any]
    limitations: list[str]


class BatchLibraryRunStored(BaseModel):
    id: int
    batch_id: int | None = None
    screened_count: int
    failed_count: int
    payload: BatchLibraryScreenResponse
    created_at: str
