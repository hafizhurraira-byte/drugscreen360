from typing import Literal

from pydantic import BaseModel, Field

from app.models.admet_models import AdmetToxicityAssessment
from app.models.cache_models import CacheMetadata
from app.models.evidence_models import EvidenceQualityAssessment
from app.models.model_registry_models import PredictAdmetResponse


InputType = Literal["name", "cid", "smiles", "inchi", "inchikey"]


class ScreeningRequest(BaseModel):
    query: str = Field(..., min_length=1, examples=["Aspirin"])
    input_type: InputType = Field(default="name")


class CompoundIdentity(BaseModel):
    compound_name: str | None
    pubchem_cid: int | None
    canonical_smiles: str | None
    isomeric_smiles: str | None
    molecular_formula: str | None
    molecular_weight: float | None
    iupac_name: str | None
    synonyms: list[str]
    pubchem_source_link: str | None
    structure_image_base64: str | None = None
    cache_metadata: CacheMetadata | None = None


class DescriptorSet(BaseModel):
    molecular_weight: float
    logp: float
    tpsa: float
    hydrogen_bond_donors: int
    hydrogen_bond_acceptors: int
    rotatable_bonds: int
    formal_charge: int
    ring_count: int
    aromatic_ring_count: int
    fraction_csp3: float


class RuleEvaluation(BaseModel):
    lipinski_rule_of_5: dict
    veber_rule: dict
    basic_drug_likeness_status: Literal["Good", "Warning", "Poor"]
    developability_risk: Literal["Low", "Medium", "High"]
    reasons: list[str]


class RecommendedTest(BaseModel):
    name: str
    priority: Literal["Standard", "Recommended", "High"]
    reason: str


class PlaceholderModule(BaseModel):
    status: str
    message: str
    future_outputs: list[str]


class ScreeningReport(BaseModel):
    screening_id: int | None = None
    disclaimer: str
    input: ScreeningRequest
    compound_identity: CompoundIdentity
    physicochemical_properties: DescriptorSet
    drug_likeness: RuleEvaluation
    admet_placeholder: PlaceholderModule
    toxicity_placeholder: PlaceholderModule
    admet_toxicity_v1: AdmetToxicityAssessment | None = None
    model_predictions: PredictAdmetResponse | None = None
    evidence_quality: EvidenceQualityAssessment | None = None
    required_lab_tests: list[RecommendedTest]
    go_no_go_recommendation: dict
    limitations: list[str]


class ScreeningHistoryItem(BaseModel):
    id: int
    input_query: str
    input_type: InputType
    compound_name: str | None
    pubchem_cid: int | None
    canonical_smiles: str | None
    drug_likeness_status: str
    developability_risk: str
    decision: str
    created_at: str


class ScreeningHistoryDetail(ScreeningHistoryItem):
    descriptor_summary: dict
    drug_likeness_result: dict
    report: ScreeningReport
