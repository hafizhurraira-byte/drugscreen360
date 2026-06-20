from app.models.finder_models import CandidateMolecule, DrugLikenessPreview
from app.services.descriptors import calculate_descriptors
from app.models.evidence_models import EvidenceCandidateInput
from app.services.evidence_quality import evaluate_candidate_evidence
from app.services.rules import evaluate_rules


def remove_duplicate_molecules(candidates: list[CandidateMolecule]) -> list[CandidateMolecule]:
    best_by_key: dict[str, CandidateMolecule] = {}
    for candidate in candidates:
        key = candidate.molecule_chembl_id or candidate.canonical_smiles
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = candidate
            continue
        current_value = current.activity_value if current.activity_value is not None else float("inf")
        new_value = candidate.activity_value if candidate.activity_value is not None else float("inf")
        if new_value < current_value:
            best_by_key[key] = candidate
    return list(best_by_key.values())


def _potency_score(activity_value: float | None) -> float:
    if activity_value is None or activity_value <= 0:
        return 0
    if activity_value <= 1:
        return 100
    if activity_value <= 10:
        return 92
    if activity_value <= 100:
        return 82
    if activity_value <= 1000:
        return 65
    if activity_value <= 10000:
        return 35
    return 10


def _data_quality_score(candidate: CandidateMolecule) -> float:
    score = 0
    if candidate.molecule_chembl_id:
        score += 20
    if candidate.compound_name:
        score += 10
    if candidate.canonical_smiles:
        score += 25
    if candidate.activity_type:
        score += 10
    if candidate.activity_value is not None:
        score += 20
    if candidate.activity_units:
        score += 10
    if candidate.target_chembl_id:
        score += 5
    return min(score, 100)


def _drug_likeness_preview(smiles: str) -> tuple[DrugLikenessPreview, float]:
    try:
        descriptors = calculate_descriptors(smiles)
        rules = evaluate_rules(descriptors)
    except Exception as exc:
        return DrugLikenessPreview(error=f"Invalid SMILES: {exc}"), 0

    lipinski_pass = bool(rules.lipinski_rule_of_5["passed"])
    veber_pass = bool(rules.veber_rule["passed"])
    score = 0
    if lipinski_pass:
        score += 60
    if veber_pass:
        score += 40
    return (
        DrugLikenessPreview(
            molecular_weight=descriptors.molecular_weight,
            logp=descriptors.logp,
            tpsa=descriptors.tpsa,
            lipinski_pass=lipinski_pass,
            veber_pass=veber_pass,
        ),
        score,
    )


def rank_candidates(candidates: list[CandidateMolecule], prefer_human: bool = True) -> list[CandidateMolecule]:
    ranked_pool = []
    for candidate in remove_duplicate_molecules(candidates):
        if not candidate.canonical_smiles:
            continue
        preview, likeness_score = _drug_likeness_preview(candidate.canonical_smiles)
        potency_score = _potency_score(candidate.activity_value)
        quality_score = _data_quality_score(candidate)
        evidence = evaluate_candidate_evidence(
            EvidenceCandidateInput(
                molecule_chembl_id=candidate.molecule_chembl_id,
                compound_name=candidate.compound_name,
                canonical_smiles=candidate.canonical_smiles,
                target_chembl_id=candidate.target_chembl_id,
                target_name=candidate.target_name,
                activity_type=candidate.activity_type,
                activity_value=candidate.activity_value,
                activity_units=candidate.activity_units,
                assay_type=candidate.assay_type,
                confidence_score=candidate.confidence_score,
                relation=candidate.relation,
                assay_description=candidate.assay_description,
                source=candidate.source,
            )
        )
        human_bonus = 5 if prefer_human and candidate.target_name else 0
        overall = round(
            (potency_score * 0.28)
            + (evidence.evidence_score * 0.3)
            + (quality_score * 0.14)
            + (likeness_score * 0.23)
            + human_bonus,
            2,
        )

        candidate.potency_score = round(potency_score, 2)
        candidate.data_quality_score = round(quality_score, 2)
        candidate.evidence_score = evidence.evidence_score
        candidate.evidence_level = evidence.evidence_level
        candidate.potency_quality = evidence.potency_quality
        candidate.evidence_reasons = evidence.evidence_reasons
        candidate.evidence_warnings = evidence.warnings
        candidate.evidence_recommended_action = evidence.recommended_action
        candidate.drug_likeness_preview = preview
        candidate.overall_candidate_score = min(overall, 100)
        candidate.ranking_reason = (
            "Ranked by potency, ChEMBL evidence quality, valid SMILES, data completeness, duplicate removal, "
            "and RDKit Lipinski/Veber preview. This does not prove clinical efficacy."
        )
        ranked_pool.append(candidate)

    ranked_pool.sort(
        key=lambda item: (
            -item.overall_candidate_score,
            item.activity_value if item.activity_value is not None else float("inf"),
            item.molecule_chembl_id,
        )
    )
    for index, candidate in enumerate(ranked_pool, start=1):
        candidate.candidate_rank = index
    return ranked_pool
