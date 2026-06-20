from fastapi import APIRouter, HTTPException

from app.models.finder_models import CandidateScreeningSummary
from app.models.similarity_models import SimilarityScreenRequest, SimilarityScreenResponse, SimilaritySearchRequest, SimilaritySearchResponse
from app.services.admet_toxicity_engine import evaluate_admet_toxicity
from app.services.admet_predictor_service import predict_admet
from app.services.descriptors import calculate_descriptors, parse_smiles
from app.services.pubchem import PubChemLookupError, PubChemNotFoundError, PubChemUnavailableError
from app.services.rules import build_decision, evaluate_rules, plan_experimental_tests
from app.services.similarity_service import (
    SimilarityNotFoundError,
    SimilarityUnavailableError,
    search_similar_compounds,
)

router = APIRouter(prefix="/similarity", tags=["similarity"])


def _analog_priority(developability_risk: str, concern_level: str, decision: str, similarity_score: float) -> str:
    if concern_level == "High" or developability_risk == "High":
        return "Requires optimization"
    if decision == "Proceed" and concern_level == "Low" and similarity_score >= 80:
        return "Higher priority analog"
    if decision in {"Proceed", "Proceed with caution"}:
        return "Review analog"
    return "Lower priority analog"


@router.post("/search", response_model=SimilaritySearchResponse)
def search_similarity(payload: SimilaritySearchRequest):
    try:
        reference, compounds, data_source, cache_metadata = search_similar_compounds(
            payload.query,
            payload.input_type,
            payload.source,
            payload.threshold,
            payload.limit,
        )
    except PubChemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PubChemUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PubChemLookupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except SimilarityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SimilarityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not compounds:
        raise HTTPException(status_code=404, detail="No similar compounds found for this reference molecule.")

    return SimilaritySearchResponse(
        reference_compound=reference,
        similar_compounds=compounds,
        data_source=data_source,
        cache_metadata=cache_metadata,
        limitations=[
            "Chemical similarity does not prove shared efficacy, safety, mechanism, or regulatory acceptability.",
            "Similarity Finder V1 uses public database results and RDKit descriptor previews only.",
            "ADMET/Tox remains a rule-based MVP; experimental testing and expert review are required.",
        ],
    )


@router.post("/screen-selected", response_model=SimilarityScreenResponse)
def screen_selected_analogs(payload: SimilarityScreenRequest):
    selected = payload.selected_compounds[: payload.max_candidates]
    if len(payload.selected_compounds) > payload.max_candidates:
        raise HTTPException(status_code=422, detail=f"Too many analogs selected. Maximum is {payload.max_candidates}.")
    if not selected:
        raise HTTPException(status_code=422, detail="At least one similar compound is required.")

    results = []
    comparison_table = []
    for compound in selected:
        parse_smiles(compound.canonical_smiles)
        descriptors = calculate_descriptors(compound.canonical_smiles)
        rules = evaluate_rules(descriptors)
        admet_tox = evaluate_admet_toxicity(compound.canonical_smiles, descriptors)
        model_predictions = predict_admet(compound.canonical_smiles, ["rule_based_admet_v1", "external_admet_provider_v1", "local_admet_model"], True)
        rule_model = model_predictions.model_outputs[0] if model_predictions.model_outputs else None
        model_summary = model_predictions.model_status_summary
        tests = plan_experimental_tests(descriptors, rules)
        decision = build_decision(rules, tests)
        priority = _analog_priority(
            rules.developability_risk,
            admet_tox.overall.concern_level,
            decision["decision"],
            compound.similarity_score,
        )
        summary = CandidateScreeningSummary(
            compound=compound.compound_name or compound.molecule_chembl_id or str(compound.pubchem_cid or "Analog"),
            potency_rank=compound.similarity_rank,
            molecule_chembl_id=compound.molecule_chembl_id,
            canonical_smiles=compound.canonical_smiles,
            molecular_weight=descriptors.molecular_weight,
            logp=descriptors.logp,
            tpsa=descriptors.tpsa,
            lipinski_pass=bool(rules.lipinski_rule_of_5["passed"]),
            veber_pass=bool(rules.veber_rule["passed"]),
            drug_likeness_status=rules.basic_drug_likeness_status,
            developability_risk=rules.developability_risk,
            decision=decision["decision"],
            target_name=None,
            activity_type=None,
            activity_value=None,
            activity_units=None,
            evidence_level="Not evaluated",
            evidence_score=None,
            potency_quality="Not target-linked",
            evidence_warnings=["Evidence quality not evaluated because this analog search is not target-linked."],
            recommended_next_step="Run target-linked bioactivity and experimental ADMET/toxicity follow-up before prioritization.",
            absorption_risk=admet_tox.absorption.absorption_risk,
            solubility_risk=admet_tox.solubility.solubility_risk,
            bbb_flag=admet_tox.bbb_cns_flag.bbb_exposure_flag,
            structural_alert_risk=admet_tox.structural_alerts.structural_alert_risk,
            overall_admet_tox_concern_score=admet_tox.overall.overall_admet_tox_concern_score,
            concern_level=admet_tox.overall.concern_level,
            confidence_level=admet_tox.overall.confidence_level,
            final_candidate_priority=priority,
            required_tests=list(dict.fromkeys([test.name for test in tests] + admet_tox.recommended_followup_tests)),
            admet_prediction_source=rule_model.prediction_source if rule_model else "Rule-based",
            model_status=rule_model.model_status if rule_model else "available",
            model_confidence=rule_model.confidence if rule_model else admet_tox.overall.confidence_level,
            model_warnings=model_predictions.warnings,
            rule_based_used=bool(model_summary.get("rule_based_used", True)),
            external_model_used=bool(model_summary.get("external_model_used", False)),
            external_model_available=bool(model_summary.get("external_model_available", False)),
            external_model_warning=model_summary.get("external_model_warning"),
        )
        results.append(summary)
        row = summary.model_dump()
        row.update(
            {
                "pubchem_cid": compound.pubchem_cid,
                "similarity_score": compound.similarity_score,
                "analog_priority_score": compound.analog_priority_score,
                "source": compound.source,
            }
        )
        comparison_table.append(row)

    return SimilarityScreenResponse(
        screened_count=len(results),
        results=results,
        comparison_table=comparison_table,
        limitations=[
            "Chemical similarity does not prove shared efficacy, safety, mechanism, or regulatory acceptability.",
            "Evidence quality is not evaluated unless analogs are linked to a target bioactivity record.",
            "ADMET/Toxicity V1 is a rule-based early screen only.",
        ],
    )
