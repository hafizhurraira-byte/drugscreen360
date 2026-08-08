from app.config import platform_config
from app.models.platform_models import CandidateScore, RankingRequest, RankingResponse, ScoringWeights


def rank_multi_objective(request: RankingRequest) -> RankingResponse:
    weights = request.weights or ScoringWeights.model_validate(platform_config()["scoring_weights"])
    raw_weights = weights.model_dump()
    total_weight = sum(raw_weights.values())
    scored = []
    for candidate in request.candidates:
        values = candidate.model_dump(exclude={"candidate_id"})
        values["uncertainty"] = 1 - values["uncertainty"]
        contributions = {name: round(values[name] * weight / total_weight * 100, 4) for name, weight in raw_weights.items()}
        score = round(sum(contributions.values()), 2)
        strongest = max(contributions, key=contributions.get)
        weakest = min(contributions, key=contributions.get)
        scored.append((candidate.candidate_id, score, contributions, strongest, weakest))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return RankingResponse(
        weights=weights,
        candidates=[
            CandidateScore(
                candidate_id=item[0],
                rank=index,
                overall_score=item[1],
                contributions=item[2],
                explanation=f"The largest weighted contribution is {item[3]}; the smallest is {item[4]}. Uncertainty is scored inversely.",
            )
            for index, item in enumerate(scored, 1)
        ],
    )
