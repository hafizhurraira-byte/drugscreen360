from pydantic import BaseModel
from app.models.cache_models import CacheMetadata


class DiseaseMatch(BaseModel):
    disease_id: str
    name: str
    description: str | None = None
    entity_type: str | None = None
    source: str = "Open Targets"


class DiseaseSearchResponse(BaseModel):
    query: str
    diseases: list[DiseaseMatch]
    cache_metadata: CacheMetadata | None = None


class DiseaseTarget(BaseModel):
    disease_target_rank: int | None = None
    target_id: str
    approved_symbol: str | None = None
    approved_name: str | None = None
    biotype: str | None = None
    organism: str | None = None
    overall_association_score: float = 0
    genetic_association_score: float | None = None
    known_drug_score: float | None = None
    affected_pathway_score: float | None = None
    literature_score: float | None = None
    animal_model_score: float | None = None
    rna_expression_score: float | None = None
    data_quality_score: float = 0
    final_target_priority_score: float = 0
    ranking_reason: str
    suggested_chembl_query: str | None = None


class DiseaseTargetsResponse(BaseModel):
    disease_id: str
    targets: list[DiseaseTarget]
    cache_metadata: CacheMetadata | None = None
    limitation: str = (
        "Open Targets scores prioritize biological and therapeutic relevance. "
        "They do not prove that modulating this target will be safe or effective."
    )
