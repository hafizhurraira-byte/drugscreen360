from app.models.evidence_models import (
    BindingDbEvidence,
    EvidenceBatchItem,
    EvidenceBatchResponse,
    EvidenceCandidateInput,
    EvidenceQualityAssessment,
)
from app.services.bindingdb_service import check_bindingdb_support

BINDING_TYPES = {"IC50", "KI", "KD"}
CELL_OR_FUNCTIONAL_TYPES = {"EC50", "AC50"}


def _activity_type(value: str | None) -> str | None:
    return value.upper() if value else None


def classify_potency(activity_type: str | None, activity_value: float | None, units: str | None) -> tuple[str, list[str]]:
    reasons = []
    normalized_type = _activity_type(activity_type)
    if activity_value is None:
        return "Very weak/uncertain", ["Activity value is missing."]
    if not units or units.lower() != "nm":
        reasons.append("Potency is not reported in nM, so ranking confidence is reduced.")
    if normalized_type in BINDING_TYPES:
        reasons.append(f"{normalized_type} is treated as direct target-binding evidence.")
    elif normalized_type in CELL_OR_FUNCTIONAL_TYPES:
        reasons.append(f"{normalized_type} is useful but less direct than IC50/Ki/Kd for binding ranking.")
    else:
        reasons.append("Activity type is missing or not a preferred IC50/Ki/Kd/EC50/AC50 field.")

    if activity_value <= 100 and normalized_type in BINDING_TYPES:
        return "Strong", reasons
    if activity_value <= 1000:
        return "Moderate", reasons
    if activity_value <= 10000:
        return "Weak", reasons
    return "Very weak/uncertain", reasons


def _data_quality(candidate: EvidenceCandidateInput) -> tuple[int, list[str], list[str]]:
    score = 0
    reasons = []
    warnings = []
    activity_type = _activity_type(candidate.activity_type)

    if candidate.activity_value is not None:
        score += 14
        reasons.append("Activity value is present.")
    else:
        warnings.append("Activity value is missing.")

    if candidate.activity_units and candidate.activity_units.lower() == "nm":
        score += 10
        reasons.append("Activity units are standardized as nM.")
    else:
        warnings.append("Activity units are missing or not nM.")

    if candidate.canonical_smiles:
        score += 12
        reasons.append("Canonical SMILES is present.")
    else:
        warnings.append("Canonical SMILES is missing.")

    if candidate.target_chembl_id:
        score += 10
        reasons.append("Target ChEMBL ID is present.")
    else:
        warnings.append("Target ChEMBL ID is missing.")

    if candidate.molecule_chembl_id:
        score += 10
        reasons.append("Molecule ChEMBL ID is present.")
    else:
        warnings.append("Molecule ChEMBL ID is missing.")

    if candidate.assay_type:
        score += 8
        reasons.append("Assay type metadata is present.")
    else:
        warnings.append("Assay type metadata is missing.")

    if activity_type in BINDING_TYPES:
        score += 14
        reasons.append("Activity type is preferred for target-binding evidence.")
    elif activity_type in CELL_OR_FUNCTIONAL_TYPES:
        score += 7
        warnings.append("Activity type is less direct than IC50/Ki/Kd for target-binding prioritization.")
    else:
        warnings.append("Activity type is not one of IC50, Ki, Kd, EC50, or AC50.")

    if candidate.confidence_score is not None:
        if candidate.confidence_score >= 8:
            score += 14
            reasons.append("ChEMBL assay confidence score is high.")
        elif candidate.confidence_score >= 5:
            score += 8
            warnings.append("ChEMBL assay confidence score is moderate.")
        else:
            score += 2
            warnings.append("ChEMBL assay confidence score is low.")
    else:
        warnings.append("ChEMBL assay confidence score is missing.")

    if candidate.relation in {"=", "<", "<="}:
        score += 8
        reasons.append("Activity relation supports interpretable potency.")
    else:
        warnings.append("Activity relation is missing or less interpretable.")

    return min(score, 100), reasons, warnings


def _level(score: int) -> str:
    if score >= 80:
        return "Strong"
    if score >= 55:
        return "Moderate"
    if score >= 30:
        return "Weak"
    return "Uncertain"


def _action(level: str, potency_quality: str) -> str:
    if level == "Strong" and potency_quality in {"Strong", "Moderate"}:
        return "Prioritize for screening, while confirming activity with orthogonal assays."
    if level == "Moderate":
        return "Review assay context and prioritize cautiously with confirmatory testing."
    if level == "Weak":
        return "Treat as a low-confidence hit until metadata and assay support improve."
    return "Do not prioritize without stronger target-linked bioactivity evidence."


def evaluate_candidate_evidence(
    candidate: EvidenceCandidateInput,
    check_bindingdb: bool = False,
    bindingdb: BindingDbEvidence | None = None,
) -> EvidenceQualityAssessment:
    potency_quality, potency_reasons = classify_potency(
        candidate.activity_type, candidate.activity_value, candidate.activity_units
    )
    data_quality_score, data_reasons, warnings = _data_quality(candidate)

    potency_score = {
        "Strong": 35,
        "Moderate": 25,
        "Weak": 12,
        "Very weak/uncertain": 2,
    }[potency_quality]
    evidence_score = min(100, round((data_quality_score * 0.65) + potency_score))

    if potency_quality == "Very weak/uncertain":
        evidence_score = min(evidence_score, 45)
    if candidate.activity_value is None:
        evidence_score = min(evidence_score, 28)

    evidence_level = _level(evidence_score)
    confidence = candidate.confidence_score
    if confidence is None:
        target_summary = "Target confidence metadata is missing."
    elif confidence >= 8:
        target_summary = f"ChEMBL confidence score {confidence} suggests strong target assignment."
    elif confidence >= 5:
        target_summary = f"ChEMBL confidence score {confidence} suggests moderate target assignment."
    else:
        target_summary = f"ChEMBL confidence score {confidence} suggests weak target assignment."

    if bindingdb is None:
        bindingdb = check_bindingdb_support(candidate) if check_bindingdb else BindingDbEvidence()

    reasons = potency_reasons + data_reasons
    if bindingdb.bindingdb_support_found:
        reasons.append("BindingDB support was found for the molecule/target context.")
        evidence_score = min(100, evidence_score + 5)
        evidence_level = _level(evidence_score)
    elif bindingdb.bindingdb_checked:
        warnings.append("BindingDB was checked but no detailed support was confirmed in this V1 integration.")

    return EvidenceQualityAssessment(
        evidence_score=int(evidence_score),
        evidence_level=evidence_level,
        potency_quality=potency_quality,
        data_quality_score=int(data_quality_score),
        target_confidence_summary=target_summary,
        evidence_reasons=list(dict.fromkeys(reasons)),
        warnings=list(dict.fromkeys(warnings)),
        recommended_action=_action(evidence_level, potency_quality),
        bindingdb_support=bindingdb,
    )


def _candidate_key(candidate: EvidenceCandidateInput) -> str:
    return candidate.molecule_chembl_id or candidate.canonical_smiles or f"{candidate.compound_name}:{candidate.target_name}"


def evaluate_batch_evidence(candidates: list[EvidenceCandidateInput], check_bindingdb: bool = False) -> EvidenceBatchResponse:
    best_by_key: dict[str, EvidenceBatchItem] = {}
    duplicate_count = 0

    for candidate in candidates:
        key = _candidate_key(candidate)
        evidence = evaluate_candidate_evidence(candidate, check_bindingdb=check_bindingdb)
        item = EvidenceBatchItem(
            candidate_key=key,
            molecule_chembl_id=candidate.molecule_chembl_id,
            compound_name=candidate.compound_name,
            target_name=candidate.target_name,
            activity_type=candidate.activity_type,
            activity_value=candidate.activity_value,
            activity_units=candidate.activity_units,
            evidence=evidence,
        )
        current = best_by_key.get(key)
        if current is None or item.evidence.evidence_score > current.evidence.evidence_score:
            best_by_key[key] = item
        else:
            duplicate_count += 1

    table = sorted(best_by_key.values(), key=lambda row: (-row.evidence.evidence_score, row.candidate_key))
    warnings = []
    if duplicate_count:
        warnings.append(f"{duplicate_count} duplicate candidate record(s) were collapsed by molecule identifier or SMILES.")
    if any(row.evidence.evidence_level in {"Weak", "Uncertain"} for row in table):
        warnings.append("One or more candidates have weak or uncertain evidence and should be treated cautiously.")

    return EvidenceBatchResponse(evaluated_count=len(table), evidence_table=table, batch_warnings=warnings)
