import csv
import json
from io import StringIO
from typing import Any

from fastapi import HTTPException
from rdkit import Chem

from app.database import get_connection, init_db
from app.models.admet_explain_models import AdmetPredictionExplainRequest
from app.models.admet_lead_models import (
    LeadCandidateInput,
    LeadCandidateRankingResult,
    LeadPrioritizationRequest,
    LeadPrioritizationRunSummary,
)
from app.models.project_workspace_models import ProjectAttachRequest
from app.services.admet_domain_service import evaluate_domain_internal
from app.services.admet_explain_service import explain_prediction
from app.services.admet_toxicity_engine import evaluate_admet_toxicity
from app.services.admet_trained_model_service import get_active_trained_model_info, predict_trained_model
from app.services.descriptors import calculate_descriptors, parse_smiles
from app.services.admet_model_evidence_resolver import resolve_model_evidence
from app.services.project_workspace_service import attach_project_item, get_project
from app.services.rules import build_decision, evaluate_rules, plan_experimental_tests
from app.services.activity_model_service import predict_egfr_activity
from app.services.admet_endpoint_model_service import predict_admet_endpoints

SCIENTIFIC_NOTICE = "Computational prioritization only. Requires experimental validation."
LIMITATIONS = [
    "Ranking is computational decision-support only and is not a final drug decision.",
    "No clinical safety, efficacy, regulatory approval, or market readiness is implied.",
    "Trained-model evidence is used only when a real active model is available.",
    "Applicability domain, uncertainty, and explainability evidence are dataset-dependent.",
    "Missing evidence reduces confidence; missing values are not inferred or fabricated.",
]

PROFILE_WEIGHTS = {
    "balanced_admet": {"developability": 1.0, "admet": 1.0, "domain": 1.0, "evidence": 1.0},
    "toxicity_avoidance": {"developability": 0.8, "admet": 1.4, "domain": 1.0, "evidence": 1.0},
    "permeability_focused": {"developability": 1.2, "admet": 1.0, "domain": 1.0, "evidence": 0.8},
    "solubility_focused": {"developability": 1.0, "admet": 1.3, "domain": 0.9, "evidence": 0.8},
    "model_confidence_focused": {"developability": 0.8, "admet": 0.9, "domain": 1.4, "evidence": 1.4},
}
TOXICITY_MODEL_ENDPOINTS = {
    "overall_admet_concern",
    "ames",
    "ames mutagenicity",
    "ames_mutagenicity",
    "herg",
    "herg cardiotoxicity",
    "herg_cardiotoxicity",
    "hepatotoxicity",
    "liver_toxicity",
    "toxicity_concern",
}


def _status_from_bool(value: bool) -> str:
    return "pass" if value else "fail"


def _priority_label(score: float, missing_count: int) -> str:
    if missing_count >= 4:
        return "insufficient_data"
    if score >= 78:
        return "high_priority_for_review"
    if score >= 62:
        return "medium_priority_for_review"
    if score >= 45:
        return "low_priority_for_review"
    return "deprioritize"


def _parse_manual_text(text: str | None) -> list[LeadCandidateInput]:
    if not text:
        return []
    candidates = []
    for index, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.replace(",", "\t").split("\t")
        smiles = parts[0].strip()
        name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else f"Manual candidate {index}"
        candidates.append(LeadCandidateInput(compound_name=name, smiles=smiles, source_id=f"manual_line_{index}"))
    return candidates


def _project_candidates(project_id: int) -> list[LeadCandidateInput]:
    detail = get_project(project_id)
    output: list[LeadCandidateInput] = []
    for item in detail.items:
        metadata = item.metadata or {}
        smiles = (
            metadata.get("canonical_smiles")
            or metadata.get("smiles")
            or metadata.get("query_smiles")
            or metadata.get("compound", {}).get("canonical_smiles")
        )
        if smiles:
            output.append(
                LeadCandidateInput(
                    compound_name=metadata.get("compound_name") or item.item_title,
                    smiles=smiles,
                    compound_id=metadata.get("compound_id") or metadata.get("molecule_chembl_id"),
                    source_id=f"project_item_{item.id}",
                    metadata=metadata,
                )
            )
    return output


def _batch_run_candidates(run_id: int) -> list[LeadCandidateInput]:
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT result_payload_json FROM batch_library_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Batch upload run not found.")
    payload = json.loads(row["result_payload_json"])
    output = []
    for result in payload.get("results", []):
        smiles = result.get("canonical_smiles")
        if smiles:
            output.append(
                LeadCandidateInput(
                    compound_name=result.get("compound_name"),
                    smiles=smiles,
                    compound_id=result.get("compound_id"),
                    source_id=f"batch_library_run_{run_id}",
                    metadata=result,
                )
            )
    return output


def _load_candidates(payload: LeadPrioritizationRequest) -> list[LeadCandidateInput]:
    candidates = list(payload.candidates)
    candidates.extend(_parse_manual_text(payload.manual_smiles_text))
    if payload.source_type == "active_project" and payload.project_id:
        candidates.extend(_project_candidates(payload.project_id))
    if payload.source_type == "batch_upload" and payload.source_run_id:
        candidates.extend(_batch_run_candidates(payload.source_run_id))
    return candidates


def _candidate_target(candidate: LeadCandidateInput, payload: LeadPrioritizationRequest) -> str | None:
    metadata = candidate.metadata or {}
    target = metadata.get("target_name") or metadata.get("target") or metadata.get("target_chembl_id")
    if target:
        return str(target)
    if payload.project_id:
        try:
            project = get_project(payload.project_id)
            return project.target_name
        except Exception:
            return None
    return None


def _is_egfr_target(target: str | None) -> bool:
    return (target or "").strip().upper() in {"EGFR", "P00533", "CHEMBL203", "ERBB1", "HUMAN EGFR"}


def _is_cns_context(candidate: LeadCandidateInput, payload: LeadPrioritizationRequest) -> bool:
    text = " ".join(str(v) for v in (candidate.metadata or {}).values()).lower()
    if payload.project_id:
        try:
            project = get_project(payload.project_id)
            text += f" {project.disease_area or ''} {project.target_name or ''}".lower()
        except Exception:
            pass
    return any(token in text for token in ["cns", "brain", "glioma", "glioblastoma", "neuro", "alzheimer", "parkinson"])


def _toxicity_evidence_summary(admet, trained_prediction: dict[str, Any] | None) -> dict[str, Any]:
    summary = admet.toxicity_evidence_summary.model_dump() if getattr(admet, "toxicity_evidence_summary", None) else {}
    endpoint = str((trained_prediction or {}).get("endpoint_predicted") or "").strip().lower()
    if trained_prediction and trained_prediction.get("model_available") and endpoint in TOXICITY_MODEL_ENDPOINTS:
        prediction = trained_prediction.get("prediction_label")
        if prediction is None:
            prediction = trained_prediction.get("prediction_value")
        summary.update(
            {
                "toxicity_evidence_source": "trained local model",
                "trained_model_endpoint": trained_prediction.get("endpoint_predicted"),
                "trained_model_prediction": prediction,
                "trained_model_confidence": trained_prediction.get("confidence_level"),
                "evidence_note": "Trained local model toxicity evidence was included from an activated real artifact. This remains computational decision-support only.",
            }
        )
    return summary


def _score_candidate(
    candidate: LeadCandidateInput,
    payload: LeadPrioritizationRequest,
    active_model: dict[str, Any],
) -> LeadCandidateRankingResult:
    raw_smiles = candidate.canonical_smiles or candidate.smiles or ""
    warnings: list[str] = []
    if not raw_smiles.strip():
        return LeadCandidateRankingResult(
            compound_name=candidate.compound_name,
            compound_id=candidate.compound_id,
            source_type=payload.source_type,
            source_id=candidate.source_id,
            smiles=raw_smiles,
            valid=False,
            excluded=True,
            exclusion_reason="Missing SMILES.",
            ranking_explanation="Candidate excluded because no SMILES was provided.",
            recommended_next_validation_step="Provide a valid SMILES string before ranking.",
            warnings=["Missing SMILES."],
        )

    try:
        mol = parse_smiles(raw_smiles)
        canonical = Chem.MolToSmiles(mol, canonical=True)
    except Exception as exc:
        return LeadCandidateRankingResult(
            compound_name=candidate.compound_name,
            compound_id=candidate.compound_id,
            source_type=payload.source_type,
            source_id=candidate.source_id,
            smiles=raw_smiles,
            valid=False,
            excluded=True,
            exclusion_reason=f"Invalid SMILES: {exc}",
            ranking_explanation="Candidate excluded because RDKit could not parse the molecule.",
            recommended_next_validation_step="Fix or replace the SMILES before prioritization.",
            warnings=[f"Invalid SMILES: {exc}"],
        )

    descriptors = calculate_descriptors(canonical)
    rules = evaluate_rules(descriptors)
    tests = plan_experimental_tests(descriptors, rules)
    decision = build_decision(rules, tests)
    admet = evaluate_admet_toxicity(canonical, descriptors)
    weights = PROFILE_WEIGHTS[payload.scoring_profile]
    score = 100.0
    positive_factors: list[str] = []
    risk_factors: list[str] = []
    missing_evidence: list[str] = []
    components: dict[str, Any] = {}

    lipinski_pass = bool(rules.lipinski_rule_of_5["passed"])
    veber_pass = bool(rules.veber_rule["passed"])
    if lipinski_pass:
        positive_factors.append("Lipinski rule passes.")
    else:
        penalty = 12 * weights["developability"]
        score -= penalty
        risk_factors.append("Lipinski rule has violations.")
        components["lipinski_penalty"] = round(penalty, 2)
    if veber_pass:
        positive_factors.append("Veber rule passes.")
    else:
        penalty = 10 * weights["developability"]
        score -= penalty
        risk_factors.append("Veber rule has violations.")
        components["veber_penalty"] = round(penalty, 2)

    developability_penalty = {"Low": 0, "Medium": 14, "High": 30}.get(rules.developability_risk, 16) * weights["developability"]
    admet_penalty = {"Low": 0, "Medium": 16, "High": 34}.get(admet.overall.concern_level, 18) * weights["admet"]
    score -= developability_penalty + admet_penalty
    components["developability_penalty"] = round(developability_penalty, 2)
    components["admet_tox_penalty"] = round(admet_penalty, 2)
    if rules.developability_risk == "Low":
        positive_factors.append("Rule-based developability risk is low.")
    else:
        risk_factors.append(f"Rule-based developability risk is {rules.developability_risk}.")
    if admet.overall.concern_level == "Low":
        positive_factors.append("Rule-based ADMET/Tox concern is low.")
    else:
        risk_factors.append(f"Rule-based ADMET/Tox concern is {admet.overall.concern_level}.")

    trained_prediction = None
    activity_prediction = None
    admet_model_predictions = None
    domain_status = "not available"
    uncertainty_level = "unknown"
    external_warning = "not available"
    evidence_strength = "not available"

    if active_model.get("status") == "available":
        try:
            evidence = resolve_model_evidence(
                candidate_name=candidate.compound_name or candidate.compound_id or "Unnamed",
                smiles=canonical,
                descriptors=descriptors.model_dump() if hasattr(descriptors, "model_dump") else descriptors,
                project_id=payload.project_id
            )
            if evidence.get("model_available"):
                trained_prediction = evidence
                domain_status = evidence.get("applicability_domain_status") or domain_status
                uncertainty_level = evidence.get("uncertainty_level") or uncertainty_level
                evidence_strength = evidence.get("evidence_strength") or evidence_strength
                external_warning = "validated" if evidence.get("external_validation_status") == "validated" else "not available"
        except Exception as exc:
            warnings.append(f"Model resolver could not execute: {exc}")

    if payload.include_trained_model:
        if trained_prediction is not None:
            positive_factors.append("Active trained-model prediction was available.")
        else:
            missing_evidence.append("trained model prediction")
            warnings.append("trained model evidence not available")
            score -= 8 * weights["evidence"]
    else:
        missing_evidence.append("trained model prediction not requested")

    if _is_egfr_target(_candidate_target(candidate, payload)):
        try:
            activity_prediction = predict_egfr_activity(canonical, "EGFR")
            predicted = activity_prediction.get("predicted_pIC50")
            domain = activity_prediction.get("applicability_domain_status")
            if isinstance(predicted, (int, float)):
                activity_bonus = min(8.0, max(0.0, float(predicted) - 6.0) * 2.0)
                score += activity_bonus
                components["egfr_activity_bonus"] = round(activity_bonus, 2)
                positive_factors.append(f"EGFR v2 predicted pIC50 {predicted:.2f} ({domain}).")
            if domain == "BORDERLINE":
                score -= 5
                components["egfr_activity_domain_penalty"] = 5
                risk_factors.append("EGFR activity prediction is borderline in applicability domain.")
            elif domain == "OUT_OF_DOMAIN":
                score -= 12
                components["egfr_activity_domain_penalty"] = 12
                risk_factors.append("EGFR activity prediction is out-of-domain and low reliability.")
            warnings.extend(activity_prediction.get("warnings") or [])
        except Exception as exc:
            missing_evidence.append("EGFR activity prediction")
            warnings.append(f"EGFR activity prediction unavailable: {getattr(exc, 'detail', exc)}")

    try:
        admet_model_predictions = predict_admet_endpoints(canonical, ["bbbp", "esol", "herg", "clintox_cttox"])
        for endpoint_result in admet_model_predictions.get("results", []):
            endpoint = endpoint_result.get("endpoint")
            if endpoint_result.get("status") != "available":
                if endpoint == "clintox_cttox":
                    missing_evidence.append("ClinTox model rejected")
                continue
            pred = endpoint_result.get("prediction") or {}
            domain = endpoint_result.get("domain_status")
            if endpoint == "herg":
                prob = pred.get("probability_herg_inhibitor")
                if isinstance(prob, (int, float)):
                    penalty = round(float(prob) * 14 * weights["admet"], 2)
                    score -= penalty
                    components["herg_model_risk_penalty"] = penalty
                    risk_factors.append(f"hERG model inhibitor probability {prob:.2f} ({domain}); not cardiac safety evidence.")
            elif endpoint == "esol":
                logs = pred.get("predicted_logS")
                if isinstance(logs, (int, float)):
                    adjustment = max(-6.0, min(4.0, (float(logs) + 3.0) * 1.5))
                    score += adjustment
                    components["esol_model_developability_adjustment"] = round(adjustment, 2)
                    positive_factors.append(f"ESOL model-derived logS {logs:.2f} ({domain}).")
            elif endpoint == "bbbp":
                prob = pred.get("probability_bbb_penetrant")
                if isinstance(prob, (int, float)) and _is_cns_context(candidate, payload):
                    adjustment = round((float(prob) - 0.5) * 6, 2)
                    score += adjustment
                    components["bbbp_contextual_adjustment"] = adjustment
                    positive_factors.append(f"BBBP benchmark probability {prob:.2f} used only because CNS context was detected.")
            if domain == "BORDERLINE":
                score -= 2
                risk_factors.append(f"{endpoint} model prediction is borderline in applicability domain.")
            elif domain == "OUT_OF_DOMAIN":
                score -= 5
                risk_factors.append(f"{endpoint} model prediction is out-of-domain.")
            warnings.extend(endpoint_result.get("warnings") or [])
    except Exception as exc:
        warnings.append(f"ADMET endpoint model predictions unavailable: {getattr(exc, 'detail', exc)}")

    if payload.include_domain:
        if trained_prediction is not None:
            if domain_status == "outside_domain":
                penalty = 18 * weights["domain"]
                score -= penalty
                risk_factors.append("Candidate is outside the trained model applicability domain.")
                components["domain_penalty"] = round(penalty, 2)
            elif domain_status == "borderline":
                penalty = 10 * weights["domain"]
                score -= penalty
                risk_factors.append("Candidate is borderline in the trained model applicability domain.")
                components["domain_penalty"] = round(penalty, 2)
            else:
                positive_factors.append("Candidate is inside the trained model applicability domain.")

            if uncertainty_level == "high":
                penalty = 12 * weights["domain"]
                score -= penalty
                risk_factors.append("Prediction uncertainty is high.")
                components["uncertainty_penalty"] = round(penalty, 2)
            elif uncertainty_level == "moderate":
                penalty = 5 * weights["domain"]
                score -= penalty
                risk_factors.append("Prediction uncertainty is moderate.")
                components["uncertainty_penalty"] = round(penalty, 2)
        else:
            missing_evidence.append("applicability domain")
            score -= 6 * weights["domain"]
    else:
        missing_evidence.append("applicability domain not requested")

    if payload.include_explainability:
        if trained_prediction is not None and evidence_strength != "not available":
            score_strength = "not_available"
            if evidence_strength == "strong_model_evidence":
                score_strength = "externally_supported" if external_warning == "validated" else "strong_internal_only"
            elif evidence_strength == "moderate_model_evidence":
                score_strength = "moderate_internal_only"
            elif evidence_strength == "weak_model_evidence":
                score_strength = "externally_weak" if external_warning == "validated" else "weak_internal"
            
            evidence_penalty = {
                "externally_supported": -3,
                "strong_internal_only": 0,
                "moderate_internal_only": 4,
                "weak_internal": 14,
                "externally_weak": 18,
                "uncertain": 10,
                "not_available": 8,
            }.get(score_strength, 8) * weights["evidence"]
            score -= evidence_penalty
            components["explainability_evidence_penalty"] = round(evidence_penalty, 2)
            if score_strength in {"externally_supported", "strong_internal_only", "moderate_internal_only"}:
                positive_factors.append(f"Explainability evidence strength is {score_strength}.")
            else:
                risk_factors.append(f"Explainability evidence strength is {score_strength}.")
        else:
            missing_evidence.append("explainability evidence")
            score -= 8 * weights["evidence"]
    else:
        missing_evidence.append("explainability not requested")

    missing_penalty = min(12, len(missing_evidence) * 3)
    score -= missing_penalty
    components["missing_data_penalty"] = missing_penalty
    final_score = round(max(0, min(100, score)), 2)
    label = _priority_label(final_score, len(missing_evidence))
    if label == "insufficient_data":
        recommended = "Collect missing trained-model/domain/explainability evidence and run basic assays before prioritizing."
    elif label in {"high_priority_for_review", "medium_priority_for_review"}:
        recommended = "Review experimentally: solubility, permeability, metabolic stability, hERG/Ames follow-up as appropriate."
    elif label == "low_priority_for_review":
        recommended = "Review only after addressing highlighted risk factors or comparing against stronger candidates."
    else:
        recommended = "Deprioritize for now unless medicinal chemistry redesign or additional evidence resolves risks."

    components["raw_score"] = final_score
    return LeadCandidateRankingResult(
        compound_name=candidate.compound_name,
        compound_id=candidate.compound_id,
        source_type=payload.source_type,
        source_id=candidate.source_id,
        smiles=raw_smiles,
        canonical_smiles=canonical,
        valid=True,
        excluded=False,
        priority_label=label,
        total_score=final_score,
        score_components=components,
        descriptors=descriptors.model_dump(),
        lipinski_status=_status_from_bool(lipinski_pass),
        veber_status=_status_from_bool(veber_pass),
        drug_likeness_status=rules.basic_drug_likeness_status,
        developability_risk=rules.developability_risk,
        rule_based_admet_summary={
            "concern_score": admet.overall.overall_admet_tox_concern_score,
            "concern_level": admet.overall.concern_level,
            "absorption_risk": admet.absorption.absorption_risk,
            "solubility_risk": admet.solubility.solubility_risk,
            "structural_alert_risk": admet.structural_alerts.structural_alert_risk,
            "toxicity_evidence_summary": _toxicity_evidence_summary(admet, trained_prediction),
        },
        trained_model_prediction=trained_prediction,
        activity_model_prediction=activity_prediction,
        admet_model_predictions=admet_model_predictions,
        domain_status=domain_status,
        uncertainty_level=uncertainty_level,
        external_validation_warning=external_warning,
        explainability_evidence_strength=evidence_strength,
        positive_factors=positive_factors,
        risk_factors=risk_factors,
        missing_evidence=missing_evidence,
        ranking_explanation="Ranked from available descriptors, rule-based ADMET/Tox, trained-model/domain/explainability evidence when available, and missing-data penalties.",
        recommended_next_validation_step=recommended,
        warnings=warnings,
    )


def _save_run(payload: LeadPrioritizationRequest, results: list[LeadCandidateRankingResult], warnings: list[str]) -> int:
    ranked = [item for item in results if not item.excluded]
    excluded = [item for item in results if item.excluded]
    summary = {
        "source_type": payload.source_type,
        "scoring_profile": payload.scoring_profile,
        "scientific_notice": SCIENTIFIC_NOTICE,
        "ranked_candidates": [item.model_dump() for item in ranked],
        "excluded_candidates": [item.model_dump() for item in excluded],
        "limitations": LIMITATIONS,
    }
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO admet_lead_prioritization_runs (
                project_id, source_type, candidate_count, ranked_count, excluded_count,
                scoring_profile, summary_json, warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.project_id,
                payload.source_type,
                len(results),
                len(ranked),
                len(excluded),
                payload.scoring_profile,
                json.dumps(summary),
                json.dumps(warnings),
            ),
        )
        run_id = int(cursor.lastrowid)
        for item in ranked:
            connection.execute(
                """
                INSERT INTO admet_lead_prioritization_candidates (
                    run_id, compound_name, smiles, canonical_smiles, rank,
                    priority_label, score_summary_json, warnings_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    item.compound_name,
                    item.smiles,
                    item.canonical_smiles,
                    item.rank,
                    item.priority_label,
                    item.model_dump_json(),
                    json.dumps(item.warnings),
                ),
            )
    return run_id


def _attach_to_project(project_id: int, run_id: int, response: LeadPrioritizationRunSummary) -> None:
    try:
        top = response.ranked_candidates[:3]
        attach_project_item(
            project_id,
            ProjectAttachRequest(
                item_type="admet_lead_prioritization",
                item_id=str(run_id),
                item_title=f"ADMET Lead Prioritization Run #{run_id}",
                metadata={
                    "workflow_type": "admet_lead_prioritization",
                    "run_id": run_id,
                    "source_type": response.source_type,
                    "scoring_profile": response.scoring_profile,
                    "ranked_count": response.ranked_count,
                    "excluded_count": response.excluded_count,
                    "top_candidates": [item.model_dump() for item in top],
                    "decision": "computational prioritization for review only",
                    "scientific_notice": response.scientific_notice,
                },
            ),
        )
    except Exception:
        pass


def prioritize_leads(payload: LeadPrioritizationRequest) -> LeadPrioritizationRunSummary:
    candidates = _load_candidates(payload)
    if not candidates:
        raise HTTPException(status_code=422, detail="No candidates were provided for lead prioritization.")

    active_model = get_active_trained_model_info() if payload.include_trained_model or payload.include_domain or payload.include_explainability else {"status": "not_requested"}
    warnings: list[str] = []
    if active_model.get("status") != "available" and (payload.include_trained_model or payload.include_domain or payload.include_explainability):
        warnings.append("trained model evidence not available")

    results = [_score_candidate(candidate, payload, active_model) for candidate in candidates]
    ranked = sorted([item for item in results if not item.excluded], key=lambda item: item.total_score or 0, reverse=True)
    for index, item in enumerate(ranked, start=1):
        item.rank = index
    excluded = [item for item in results if item.excluded]
    for item in results:
        warnings.extend(item.warnings)
    warnings = list(dict.fromkeys(warnings))
    run_id = _save_run(payload, ranked + excluded, warnings)
    response = LeadPrioritizationRunSummary(
        run_id=run_id,
        project_id=payload.project_id,
        source_type=payload.source_type,
        scoring_profile=payload.scoring_profile,
        candidate_count=len(results),
        ranked_count=len(ranked),
        excluded_count=len(excluded),
        ranked_candidates=ranked + excluded,
        warnings=warnings,
        limitations=LIMITATIONS,
        scientific_notice=SCIENTIFIC_NOTICE,
    )
    if payload.project_id:
        _attach_to_project(payload.project_id, run_id, response)
    return response


def get_lead_prioritization_run(run_id: int) -> LeadPrioritizationRunSummary:
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM admet_lead_prioritization_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="ADMET lead prioritization run not found.")
    summary = json.loads(row["summary_json"])
    candidates = [LeadCandidateRankingResult.model_validate(item) for item in summary.get("ranked_candidates", []) + summary.get("excluded_candidates", [])]
    return LeadPrioritizationRunSummary(
        run_id=row["id"],
        project_id=row["project_id"],
        source_type=row["source_type"],
        scoring_profile=row["scoring_profile"],
        candidate_count=row["candidate_count"],
        ranked_count=row["ranked_count"],
        excluded_count=row["excluded_count"],
        ranked_candidates=candidates,
        warnings=json.loads(row["warnings_json"]) if row["warnings_json"] else [],
        limitations=summary.get("limitations") or LIMITATIONS,
        scientific_notice=summary.get("scientific_notice") or SCIENTIFIC_NOTICE,
        created_at=row["created_at"],
    )


def list_lead_prioritization_runs() -> list[dict[str, Any]]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM admet_lead_prioritization_runs ORDER BY datetime(created_at) DESC, id DESC LIMIT 50"
        ).fetchall()
    return [
        {
            "run_id": row["id"],
            "project_id": row["project_id"],
            "source_type": row["source_type"],
            "candidate_count": row["candidate_count"],
            "ranked_count": row["ranked_count"],
            "excluded_count": row["excluded_count"],
            "scoring_profile": row["scoring_profile"],
            "warnings": json.loads(row["warnings_json"]) if row["warnings_json"] else [],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def lead_prioritization_csv(run_id: int) -> str:
    run = get_lead_prioritization_run(run_id)
    output = StringIO()
    headers = [
        "rank",
        "compound_name",
        "compound_id",
        "canonical_smiles",
        "priority_label",
        "total_score",
        "drug_likeness_status",
        "developability_risk",
        "admet_concern_level",
        "domain_status",
        "uncertainty_level",
        "evidence_strength",
        "warnings",
        "recommended_next_validation_step",
    ]
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    for item in run.ranked_candidates:
        writer.writerow({
            "rank": item.rank,
            "compound_name": item.compound_name,
            "compound_id": item.compound_id,
            "canonical_smiles": item.canonical_smiles,
            "priority_label": item.priority_label,
            "total_score": item.total_score,
            "drug_likeness_status": item.drug_likeness_status,
            "developability_risk": item.developability_risk,
            "admet_concern_level": item.rule_based_admet_summary.get("concern_level"),
            "domain_status": item.domain_status,
            "uncertainty_level": item.uncertainty_level,
            "evidence_strength": item.explainability_evidence_strength,
            "warnings": "; ".join(item.warnings),
            "recommended_next_validation_step": item.recommended_next_validation_step,
        })
    return output.getvalue()


def lead_prioritization_report_json(run_id: int) -> dict[str, Any]:
    return get_lead_prioritization_run(run_id).model_dump()


def latest_lead_prioritization_summary() -> dict[str, Any]:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM admet_lead_prioritization_runs ORDER BY datetime(created_at) DESC, id DESC LIMIT 1"
        ).fetchone()
        counts = connection.execute(
            """
            SELECT priority_label, COUNT(*) AS c
            FROM admet_lead_prioritization_candidates
            GROUP BY priority_label
            """
        ).fetchall()
    if not row:
        return {"status": "not_available", "latest_run": None, "priority_label_counts": {}}
    summary = json.loads(row["summary_json"])
    return {
        "status": "available",
        "latest_run": {
            "run_id": row["id"],
            "source_type": row["source_type"],
            "scoring_profile": row["scoring_profile"],
            "ranked_count": row["ranked_count"],
            "excluded_count": row["excluded_count"],
            "top_candidates": summary.get("ranked_candidates", [])[:3],
            "created_at": row["created_at"],
        },
        "priority_label_counts": {count["priority_label"]: count["c"] for count in counts},
        "scientific_notice": SCIENTIFIC_NOTICE,
    }
