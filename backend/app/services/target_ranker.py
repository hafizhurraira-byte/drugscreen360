from app.models.finder_models import TargetResult

LOWER_CONFIDENCE_TYPES = {"PROTEIN-PROTEIN INTERACTION", "CHIMERIC PROTEIN", "PROTEIN FAMILY"}


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _label(score: int) -> str:
    if score >= 60:
        return "Best match"
    if score >= 35:
        return "Good match"
    return "Lower-confidence match"


def score_target(target: TargetResult, query: str) -> TargetResult:
    query_norm = _norm(query)
    name_norm = _norm(target.preferred_name)
    type_norm = (target.target_type or "").strip().upper()
    organism_norm = _norm(target.organism)
    accession_norm = _norm(target.accession)
    reasons = []
    score = 0

    if query_norm and name_norm == query_norm:
        score += 30
        reasons.append("preferred name exactly matches query")
    elif query_norm and query_norm in name_norm:
        score += 16
        reasons.append("preferred name contains query")

    if organism_norm == "homo sapiens":
        score += 25
        reasons.append("human target")
    elif organism_norm:
        score -= 10
        reasons.append("non-human target")

    if type_norm == "SINGLE PROTEIN":
        score += 30
        reasons.append("single protein target")
    elif type_norm in LOWER_CONFIDENCE_TYPES:
        score -= 25
        reasons.append(f"{target.target_type} is lower priority for small-molecule retrieval")
    elif type_norm:
        score -= 5
        reasons.append(f"{target.target_type} target type is less direct")

    if accession_norm:
        score += 10
        reasons.append("accession present")

    if query_norm and accession_norm and query_norm == accession_norm:
        score += 10
        reasons.append("query matches accession")

    score = max(0, min(score, 100))
    target.target_priority_score = score
    target.target_priority_label = _label(score)
    target.target_ranking_reason = "; ".join(reasons) or "Limited target metadata available."
    return target


def rank_targets(targets: list[TargetResult], query: str) -> list[TargetResult]:
    scored = [score_target(target, query) for target in targets]
    return sorted(
        scored,
        key=lambda target: (
            -target.target_priority_score,
            target.target_type != "SINGLE PROTEIN",
            target.organism != "Homo sapiens",
            target.preferred_name or "",
            target.target_chembl_id,
        ),
    )
