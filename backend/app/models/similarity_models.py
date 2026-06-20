from typing import Literal

from pydantic import BaseModel, Field

from app.models.cache_models import CacheMetadata
from app.models.finder_models import CandidateScreeningSummary, DrugLikenessPreview
from app.models.schemas import CompoundIdentity, InputType


SimilaritySource = Literal["auto", "chembl", "pubchem", "chembl_or_pubchem"]


class SimilaritySearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    input_type: InputType = "name"
    source: SimilaritySource = "auto"
    threshold: int = Field(default=70, ge=40, le=100)
    limit: int = Field(default=25, ge=1, le=50)


class SimilarCompound(BaseModel):
    similarity_rank: int | None = None
    compound_name: str | None = None
    pubchem_cid: int | None = None
    molecule_chembl_id: str | None = None
    canonical_smiles: str
    similarity_score: float
    molecular_formula: str | None = None
    molecular_weight: float | None = None
    source: str
    drug_likeness_preview: DrugLikenessPreview | None = None
    data_quality_score: float = 0
    analog_priority_score: float = 0
    ranking_reason: str = ""


class SimilaritySearchResponse(BaseModel):
    reference_compound: CompoundIdentity
    similar_compounds: list[SimilarCompound]
    data_source: str
    cache_metadata: CacheMetadata | None = None
    limitations: list[str]


class SimilarityScreenRequest(BaseModel):
    reference_compound: CompoundIdentity | None = None
    selected_compounds: list[SimilarCompound]
    max_candidates: int = Field(default=10, ge=1, le=25)


class SimilarityScreenResponse(BaseModel):
    screened_count: int
    results: list[CandidateScreeningSummary]
    comparison_table: list[dict]
    limitations: list[str]
