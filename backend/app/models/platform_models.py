from typing import Any

from pydantic import BaseModel, Field, model_validator


class ScoringWeights(BaseModel):
    egfr: float = Field(ge=0)
    admet: float = Field(ge=0)
    confidence: float = Field(ge=0)
    uncertainty: float = Field(ge=0)
    applicability_domain: float = Field(ge=0)

    @model_validator(mode="after")
    def require_weight(self):
        if not any(self.model_dump().values()):
            raise ValueError("At least one scoring weight must be positive")
        return self


class CandidateScoreInput(BaseModel):
    candidate_id: str = Field(min_length=1)
    egfr: float = Field(ge=0, le=1)
    admet: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    uncertainty: float = Field(ge=0, le=1, description="Higher means more uncertain")
    applicability_domain: float = Field(ge=0, le=1)


class RankingRequest(BaseModel):
    candidates: list[CandidateScoreInput] = Field(min_length=1)
    weights: ScoringWeights | None = None


class CandidateScore(BaseModel):
    candidate_id: str
    rank: int
    overall_score: float
    contributions: dict[str, float]
    explanation: str


class RankingResponse(BaseModel):
    weights: ScoringWeights
    candidates: list[CandidateScore]


class ScientificHtmlReportRequest(BaseModel):
    title: str = "DrugScreen360 Scientific Report"
    compound: dict[str, Any]
    predictions: list[dict[str, Any]] = Field(default_factory=list)
    admet: dict[str, Any] = Field(default_factory=dict)
    confidence: dict[str, Any] = Field(default_factory=dict)
    uncertainty: dict[str, Any] = Field(default_factory=dict)
    explainability: dict[str, Any] = Field(default_factory=dict)
    ranking: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
