from pydantic import BaseModel, Field


class BindingDbEvidence(BaseModel):
    bindingdb_checked: bool = False
    bindingdb_support_found: bool = False
    target_name: str | None = None
    ligand_name: str | None = None
    affinity_type: str | None = None
    affinity_value: float | None = None
    affinity_units: str | None = None
    source_url: str | None = None
    limitation: str = (
        "BindingDB support is optional in this MVP. If unavailable, evidence scoring relies on ChEMBL metadata only."
    )


class EvidenceCandidateInput(BaseModel):
    molecule_chembl_id: str | None = None
    compound_name: str | None = None
    canonical_smiles: str | None = None
    target_chembl_id: str | None = None
    target_name: str | None = None
    activity_type: str | None = None
    activity_value: float | None = None
    activity_units: str | None = None
    assay_type: str | None = None
    confidence_score: int | None = None
    relation: str | None = None
    assay_description: str | None = None
    source: str | None = "ChEMBL"


class EvidenceQualityAssessment(BaseModel):
    evidence_score: int = Field(ge=0, le=100)
    evidence_level: str
    potency_quality: str
    data_quality_score: int = Field(ge=0, le=100)
    target_confidence_summary: str
    evidence_reasons: list[str]
    warnings: list[str]
    recommended_action: str
    bindingdb_support: BindingDbEvidence
    limitation: str = (
        "Evidence quality reflects available public bioactivity metadata. "
        "It does not prove clinical efficacy, safety, or regulatory approval."
    )


class EvidenceCandidateRequest(BaseModel):
    candidate: EvidenceCandidateInput
    selected_target_name: str | None = None
    check_bindingdb: bool = False


class EvidenceBatchRequest(BaseModel):
    candidates: list[EvidenceCandidateInput]
    check_bindingdb: bool = False


class EvidenceBatchItem(BaseModel):
    candidate_key: str
    molecule_chembl_id: str | None = None
    compound_name: str | None = None
    target_name: str | None = None
    activity_type: str | None = None
    activity_value: float | None = None
    activity_units: str | None = None
    evidence: EvidenceQualityAssessment


class EvidenceBatchResponse(BaseModel):
    evaluated_count: int
    evidence_table: list[EvidenceBatchItem]
    batch_warnings: list[str]
