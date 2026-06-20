from fastapi import APIRouter, HTTPException, Query

from app.models.finder_models import (
    BatchScreeningRequest,
    BatchScreeningResponse,
    CandidateScreeningSummary,
    FinderCandidatesResponse,
    FinderTargetsResponse,
)
from app.models.evidence_models import EvidenceCandidateInput
from app.services import chembl_service
from app.services.admet_toxicity_engine import evaluate_admet_toxicity
from app.services.admet_predictor_service import predict_admet
from app.services.descriptors import calculate_descriptors, parse_smiles
from app.services.evidence_quality import evaluate_candidate_evidence
from app.services.evidence_history import save_evidence_summary
from app.services.finder_history import save_batch_screening_run, save_finder_search
from app.services.rules import build_decision, evaluate_rules, plan_experimental_tests

router = APIRouter(prefix="/finder", tags=["finder"])


def _final_priority(developability_risk: str, concern_level: str, decision: str, evidence_level: str | None) -> str:
    if evidence_level in {"Weak", "Uncertain"}:
        return "Treat cautiously"
    if concern_level == "High" or developability_risk == "High":
        return "Requires optimization"
    if decision == "Proceed" and concern_level == "Low":
        return "Higher priority"
    if decision in {"Proceed", "Proceed with caution"} and concern_level in {"Low", "Medium"}:
        return "Review priority"
    return "Lower priority"


@router.get("/targets", response_model=FinderTargetsResponse)
def find_targets(query: str = Query(..., min_length=1)):
    try:
        targets = chembl_service.search_targets(query)
    except chembl_service.ChEMBLUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not targets:
        raise HTTPException(status_code=404, detail=f"No ChEMBL targets found for '{query}'.")
    save_finder_search(query=query, selected_target=None, candidates=[])
    return FinderTargetsResponse(query=query, targets=targets, cache_metadata=chembl_service.last_cache_metadata)


@router.get("/target/{target_chembl_id}/candidates", response_model=FinderCandidatesResponse)
def find_target_candidates(target_chembl_id: str, limit: int = Query(default=50, ge=1, le=50)):
    try:
        candidates = chembl_service.get_target_candidates(target_chembl_id, limit=limit)
    except chembl_service.ChEMBLUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail="No usable ChEMBL candidates found with nM activity, molecule ID, and canonical SMILES.",
        )
    save_finder_search(query=target_chembl_id, selected_target=target_chembl_id, candidates=candidates)
    return FinderCandidatesResponse(
        target_chembl_id=target_chembl_id,
        candidates=candidates,
        cache_metadata=chembl_service.last_cache_metadata,
    )


@router.post("/screen-candidates", response_model=BatchScreeningResponse)
def screen_candidates(payload: BatchScreeningRequest):
    selected = payload.candidates[: payload.max_candidates]
    if len(payload.candidates) > payload.max_candidates:
        raise HTTPException(status_code=422, detail=f"Too many candidates selected. Maximum is {payload.max_candidates}.")
    if not selected:
        raise HTTPException(status_code=422, detail="At least one candidate is required.")

    results = []
    for candidate in selected:
        parse_smiles(candidate.canonical_smiles)
        descriptors = calculate_descriptors(candidate.canonical_smiles)
        rules = evaluate_rules(descriptors)
        admet_tox = evaluate_admet_toxicity(candidate.canonical_smiles, descriptors)
        model_predictions = predict_admet(candidate.canonical_smiles, ["rule_based_admet_v1", "external_admet_provider_v1", "local_admet_model"], True)
        rule_model = model_predictions.model_outputs[0] if model_predictions.model_outputs else None
        model_summary = model_predictions.model_status_summary
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
            )
        )
        save_evidence_summary(candidate, evidence)
        tests = plan_experimental_tests(descriptors, rules)
        decision = build_decision(rules, tests)
        followups = [test.name for test in tests] + admet_tox.recommended_followup_tests
        priority = _final_priority(
            rules.developability_risk, admet_tox.overall.concern_level, decision["decision"], evidence.evidence_level
        )
        results.append(
            CandidateScreeningSummary(
                compound=candidate.compound_name or candidate.molecule_chembl_id,
                potency_rank=candidate.candidate_rank,
                molecule_chembl_id=candidate.molecule_chembl_id,
                canonical_smiles=candidate.canonical_smiles,
                molecular_weight=descriptors.molecular_weight,
                logp=descriptors.logp,
                tpsa=descriptors.tpsa,
                lipinski_pass=bool(rules.lipinski_rule_of_5["passed"]),
                veber_pass=bool(rules.veber_rule["passed"]),
                drug_likeness_status=rules.basic_drug_likeness_status,
                developability_risk=rules.developability_risk,
                decision=decision["decision"],
                target_name=candidate.target_name,
                activity_type=candidate.activity_type,
                activity_value=candidate.activity_value,
                activity_units=candidate.activity_units,
                evidence_level=evidence.evidence_level,
                evidence_score=evidence.evidence_score,
                potency_quality=evidence.potency_quality,
                evidence_warnings=evidence.warnings,
                recommended_next_step=evidence.recommended_action,
                absorption_risk=admet_tox.absorption.absorption_risk,
                solubility_risk=admet_tox.solubility.solubility_risk,
                bbb_flag=admet_tox.bbb_cns_flag.bbb_exposure_flag,
                structural_alert_risk=admet_tox.structural_alerts.structural_alert_risk,
                overall_admet_tox_concern_score=admet_tox.overall.overall_admet_tox_concern_score,
                concern_level=admet_tox.overall.concern_level,
                confidence_level=admet_tox.overall.confidence_level,
                final_candidate_priority=priority,
                required_tests=list(dict.fromkeys(followups)),
                admet_prediction_source=rule_model.prediction_source if rule_model else "Rule-based",
                model_status=rule_model.model_status if rule_model else "available",
                model_confidence=rule_model.confidence if rule_model else admet_tox.overall.confidence_level,
                model_warnings=model_predictions.warnings,
                rule_based_used=bool(model_summary.get("rule_based_used", True)),
                external_model_used=bool(model_summary.get("external_model_used", False)),
                external_model_available=bool(model_summary.get("external_model_available", False)),
                external_model_warning=model_summary.get("external_model_warning"),
            )
        )

    comparison_table = [item.model_dump() for item in results]
    response = BatchScreeningResponse(
        screened_count=len(results),
        results=results,
        comparison_table=comparison_table,
        limitations=[
            "Batch screening uses RDKit descriptors and transparent rules only.",
            "Candidate ranking and screening do not prove clinical efficacy, safety, or regulatory readiness.",
            "ADMET/Toxicity V1 is a rule-based early screen; CYP, hERG, Ames/genotoxicity, and hepatotoxicity models are not implemented.",
            "Evidence quality reflects available public bioactivity metadata only.",
        ],
    )
    response.batch_run_id = save_batch_screening_run(response)
    return response
