from pydantic import BaseModel, Field
from app.models.cache_models import CacheMetadata


class TargetResult(BaseModel):
    target_chembl_id: str
    preferred_name: str | None = None
    organism: str | None = None
    target_type: str | None = None
    accession: str | None = None
    target_priority_score: int = 0
    target_priority_label: str = "Lower-confidence match"
    target_ranking_reason: str = ""


class DrugLikenessPreview(BaseModel):
    molecular_weight: float | None = None
    logp: float | None = None
    tpsa: float | None = None
    lipinski_pass: bool = False
    veber_pass: bool = False
    error: str | None = None


class CandidateMolecule(BaseModel):
    candidate_rank: int | None = None
    molecule_chembl_id: str
    compound_name: str | None = None
    canonical_smiles: str
    activity_type: str | None = None
    activity_value: float | None = None
    activity_units: str | None = None
    assay_type: str | None = None
    confidence_score: int | None = None
    relation: str | None = None
    assay_description: str | None = None
    target_name: str | None = None
    target_chembl_id: str
    source: str = "ChEMBL"
    potency_score: float = 0
    data_quality_score: float = 0
    evidence_score: int | None = None
    evidence_level: str | None = None
    potency_quality: str | None = None
    evidence_reasons: list[str] = Field(default_factory=list)
    evidence_warnings: list[str] = Field(default_factory=list)
    evidence_recommended_action: str | None = None
    drug_likeness_preview: DrugLikenessPreview | None = None
    overall_candidate_score: float = 0
    ranking_reason: str = ""


class FinderTargetsResponse(BaseModel):
    query: str
    targets: list[TargetResult]
    cache_metadata: CacheMetadata | None = None


class FinderCandidatesResponse(BaseModel):
    target_chembl_id: str
    candidates: list[CandidateMolecule]
    cache_metadata: CacheMetadata | None = None


class CandidateScreeningInput(BaseModel):
    candidate_rank: int | None = None
    molecule_chembl_id: str | None = None
    compound_name: str | None = None
    canonical_smiles: str
    target_chembl_id: str | None = None
    target_name: str | None = None
    activity_type: str | None = None
    activity_value: float | None = None
    activity_units: str | None = None
    assay_type: str | None = None
    confidence_score: int | None = None
    relation: str | None = None
    assay_description: str | None = None
    evidence_score: int | None = None
    evidence_level: str | None = None
    potency_quality: str | None = None
    data_quality_score: float | None = None
    evidence_warnings: list[str] = Field(default_factory=list)


class BatchScreeningRequest(BaseModel):
    candidates: list[CandidateScreeningInput]
    max_candidates: int = Field(default=10, ge=1, le=25)


class CandidateScreeningSummary(BaseModel):
    compound: str | None
    potency_rank: int | None = None
    molecule_chembl_id: str | None
    canonical_smiles: str
    molecular_weight: float
    logp: float
    tpsa: float
    lipinski_pass: bool
    veber_pass: bool
    drug_likeness_status: str
    developability_risk: str
    decision: str
    target_name: str | None = None
    activity_type: str | None = None
    activity_value: float | None = None
    activity_units: str | None = None
    evidence_level: str | None = None
    evidence_score: int | None = None
    potency_quality: str | None = None
    evidence_warnings: list[str] = Field(default_factory=list)
    recommended_next_step: str | None = None
    absorption_risk: str
    solubility_risk: str
    bbb_flag: str
    structural_alert_risk: str
    overall_admet_tox_concern_score: int
    concern_level: str
    confidence_level: str
    final_candidate_priority: str
    required_tests: list[str]
    admet_prediction_source: str | None = None
    model_status: str | None = None
    model_confidence: str | None = None
    model_warnings: list[str] = Field(default_factory=list)
    rule_based_used: bool = True
    external_model_used: bool = False
    external_model_available: bool = False
    external_model_warning: str | None = None
    model_predictions: dict | None = None



class BatchScreeningResponse(BaseModel):
    batch_run_id: int | None = None
    screened_count: int
    results: list[CandidateScreeningSummary]
    comparison_table: list[dict]
    limitations: list[str]
