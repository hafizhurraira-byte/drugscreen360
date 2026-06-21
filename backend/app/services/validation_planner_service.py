import csv
import json
from io import StringIO
from typing import Any

from fastapi import HTTPException
from rdkit import Chem

from app.database import get_connection, init_db
from app.models.project_workspace_models import ProjectAttachRequest
from app.models.validation_planner_models import (
    ExperimentalValidationPlanRequest,
    ExperimentalValidationPlanResponse,
    ExperimentalValidationPlanRunSummary,
    RecommendedAssay,
    ValidationCandidateInput,
    ValidationPlanCandidateResult,
)
from app.services.admet_lead_service import get_lead_prioritization_run
from app.services.admet_toxicity_engine import evaluate_admet_toxicity
from app.services.descriptors import calculate_descriptors, parse_smiles
from app.services.project_workspace_service import attach_project_item, get_project
from app.services.rules import evaluate_rules

SCIENTIFIC_NOTICE = "Experimental planning support only. Actual assay design must be reviewed by qualified laboratory personnel."
THRESHOLD_GUIDANCE = "Define acceptance thresholds according to laboratory SOPs, literature standards, assay platform validation, and qualified laboratory review."
SAFETY_NOTE = "Plan only; no experiment has been performed. Laboratory work requires qualified personnel, approved SOPs, risk assessment, and institutional safety review."
LIMITATIONS = [
    "Assay recommendations are planning support only and are not experimental results.",
    "No clinical safety, efficacy, regulatory approval, or market readiness is implied.",
    "Recommendations use available computational evidence only; missing data is shown rather than inferred.",
    "Actual assay design, control selection, acceptance criteria, and interpretation require qualified laboratory review.",
]
PRIORITY_ORDER = {"not_applicable": 0, "optional": 1, "recommended": 2, "essential": 3}


def _priority_depth(priority_label: str | None) -> str:
    value = (priority_label or "").lower()
    if value == "high_priority_for_review":
        return "essential"
    if value == "medium_priority_for_review":
        return "recommended"
    if value in {"low_priority_for_review", "deprioritize"}:
        return "optional"
    if value == "insufficient_data":
        return "essential"
    return "recommended"


def _parse_manual_text(text: str | None) -> list[ValidationCandidateInput]:
    if not text:
        return []
    output: list[ValidationCandidateInput] = []
    for index, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = line.replace(",", "\t").split("\t")
        smiles = parts[0].strip()
        name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else f"Manual candidate {index}"
        output.append(ValidationCandidateInput(compound_name=name, smiles=smiles, metadata={"source_line": index}))
    return output


def _project_candidates(project_id: int, limit: int) -> list[ValidationCandidateInput]:
    detail = get_project(project_id)
    output: list[ValidationCandidateInput] = []
    for item in detail.items:
        metadata = dict(item.metadata or {})
        candidates = metadata.get("top_candidates") or metadata.get("candidate_plans") or metadata.get("ranked_candidates")
        if isinstance(candidates, list):
            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                smiles = candidate.get("canonical_smiles") or candidate.get("smiles")
                if smiles:
                    output.append(_candidate_from_record(candidate, f"project_item_{item.id}"))
                    if len(output) >= limit:
                        return output
        smiles = (
            metadata.get("canonical_smiles")
            or metadata.get("smiles")
            or metadata.get("query_smiles")
            or (metadata.get("compound") or {}).get("canonical_smiles")
        )
        if smiles:
            output.append(
                ValidationCandidateInput(
                    compound_name=metadata.get("compound_name") or item.item_title,
                    smiles=smiles,
                    compound_id=metadata.get("compound_id") or metadata.get("molecule_chembl_id"),
                    target_name=metadata.get("target_name") or detail.target_name,
                    priority_label=metadata.get("priority_label"),
                    metadata={**metadata, "source_id": f"project_item_{item.id}"},
                )
            )
            if len(output) >= limit:
                return output
    return output


def _candidate_from_record(record: dict[str, Any], source_id: str | None = None) -> ValidationCandidateInput:
    return ValidationCandidateInput(
        compound_name=record.get("compound_name") or record.get("candidate_name") or record.get("name"),
        compound_id=record.get("compound_id") or record.get("molecule_chembl_id") or record.get("source_id"),
        smiles=record.get("canonical_smiles") or record.get("smiles"),
        canonical_smiles=record.get("canonical_smiles"),
        target_name=record.get("target_name") or record.get("target"),
        priority_label=record.get("priority_label"),
        domain_status=record.get("domain_status"),
        uncertainty_level=record.get("uncertainty_level"),
        external_validation_status=record.get("external_validation_warning") or record.get("external_validation_status"),
        evidence_strength=record.get("explainability_evidence_strength") or record.get("evidence_strength"),
        warnings=record.get("warnings") or [],
        metadata={**record, "source_id": source_id or record.get("source_id")},
    )


def _latest_lead_run_id() -> int | None:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id FROM admet_lead_prioritization_runs ORDER BY datetime(created_at) DESC, id DESC LIMIT 1"
        ).fetchone()
    return int(row["id"]) if row else None


def _lead_candidates(run_id: int | None, limit: int) -> list[ValidationCandidateInput]:
    resolved = run_id or _latest_lead_run_id()
    if not resolved:
        raise HTTPException(status_code=404, detail="No ADMET lead prioritization run was found.")
    run = get_lead_prioritization_run(resolved)
    output = []
    for candidate in run.ranked_candidates:
        if candidate.excluded:
            continue
        output.append(_candidate_from_record(candidate.model_dump(), f"lead_prioritization_run_{resolved}"))
        if len(output) >= limit:
            break
    return output


def _load_candidates(payload: ExperimentalValidationPlanRequest) -> list[ValidationCandidateInput]:
    limit = max(1, min(payload.max_candidates or 10, 50))
    candidates = list(payload.candidates)
    candidates.extend(_parse_manual_text(payload.manual_smiles_text))
    if payload.source_type == "active_project":
        if not payload.project_id:
            raise HTTPException(status_code=422, detail="Select a project before creating a plan from active project candidates.")
        candidates.extend(_project_candidates(payload.project_id, limit))
    if payload.source_type == "lead_prioritization":
        candidates.extend(_lead_candidates(payload.source_run_id, limit))
    return candidates[:limit]


def _make_assay(
    assay_name: str,
    assay_category: str,
    priority: str,
    reason: str,
    evidence: list[str],
    readout: str,
    controls: list[str],
    interpretation: str,
    limitations: str,
) -> RecommendedAssay:
    return RecommendedAssay(
        assay_name=assay_name,
        assay_category=assay_category,
        recommendation_priority=priority,  # type: ignore[arg-type]
        reason=reason,
        linked_computational_evidence=evidence,
        suggested_readout=readout,
        suggested_controls=controls,
        decision_threshold_guidance=THRESHOLD_GUIDANCE,
        expected_interpretation=interpretation,
        limitations=limitations,
        safety_note=SAFETY_NOTE,
    )


def _add_assay(assays: dict[str, RecommendedAssay], assay: RecommendedAssay) -> None:
    existing = assays.get(assay.assay_name)
    if not existing or PRIORITY_ORDER[assay.recommendation_priority] > PRIORITY_ORDER[existing.recommendation_priority]:
        assays[assay.assay_name] = assay
    elif existing:
        merged = list(dict.fromkeys([*existing.linked_computational_evidence, *assay.linked_computational_evidence]))
        existing.linked_computational_evidence = merged


def _general_controls(include_controls: bool) -> list[str]:
    if not include_controls:
        return []
    return ["vehicle control", "positive control where validated", "negative control where validated", "reference compound if available"]


def _admet_summary_from_metadata(metadata: dict[str, Any], computed: dict[str, Any]) -> dict[str, Any]:
    stored = metadata.get("rule_based_admet_summary") or metadata.get("admet_tox_summary") or {}
    if isinstance(stored, dict):
        merged = {**computed, **stored}
    else:
        merged = computed
    return merged


def _recommend_assays(
    candidate: ValidationCandidateInput,
    descriptors: dict[str, Any],
    admet_summary: dict[str, Any],
    payload: ExperimentalValidationPlanRequest,
) -> tuple[list[RecommendedAssay], list[dict[str, Any]], list[str], str]:
    assays: dict[str, RecommendedAssay] = {}
    warnings = list(candidate.warnings or [])
    decision_points: list[dict[str, Any]] = []
    controls = _general_controls(payload.include_controls)
    priority_depth = _priority_depth(candidate.priority_label)
    concern_level = str(admet_summary.get("concern_level") or "not available")
    solubility_risk = str(admet_summary.get("solubility_risk") or "not available")
    absorption_risk = str(admet_summary.get("absorption_risk") or "not available")
    structural_risk = str(admet_summary.get("structural_alert_risk") or "not available")
    domain_status = (candidate.domain_status or candidate.metadata.get("domain_status") or "not available").lower()
    uncertainty = (candidate.uncertainty_level or candidate.metadata.get("uncertainty_level") or "unknown").lower()
    evidence_strength = (candidate.evidence_strength or candidate.metadata.get("explainability_evidence_strength") or "not available").lower()
    external_status = (candidate.external_validation_status or candidate.metadata.get("external_validation_warning") or "not available").lower()
    mw = float(descriptors.get("molecular_weight") or 0)
    logp = float(descriptors.get("logp") or 0)
    tpsa = float(descriptors.get("tpsa") or 0)
    rotatable = float(descriptors.get("rotatable_bonds") or 0)

    if payload.include_adme_assays:
        sol_priority = "essential" if solubility_risk == "High" or logp > 4 or mw > 500 else "recommended"
        _add_assay(
            assays,
            _make_assay(
                "Kinetic and thermodynamic solubility assay",
                "Solubility",
                sol_priority,
                "Solubility risk should be checked before interpreting downstream potency or toxicity assays.",
                [f"solubility_risk={solubility_risk}", f"LogP={logp:.2f}", f"MW={mw:.2f}"],
                "aqueous solubility estimate under assay-relevant conditions",
                controls,
                "Low solubility would challenge progression or require formulation/salt/chemistry optimization before deeper profiling.",
                "Solubility depends on pH, salt form, formulation, and assay platform; this plan does not define a protocol.",
            ),
        )
        perm_priority = "essential" if absorption_risk == "High" or tpsa > 140 or rotatable > 10 else "recommended"
        _add_assay(
            assays,
            _make_assay(
                "Caco-2 or PAMPA permeability assay",
                "Permeability",
                perm_priority,
                "Permeability should be assessed when absorption or descriptor-based oral developability is uncertain.",
                [f"absorption_risk={absorption_risk}", f"TPSA={tpsa:.2f}", f"rotatable_bonds={rotatable:.0f}"],
                "apparent permeability or passive permeability readout",
                controls,
                "Poor permeability would support caution around oral exposure assumptions and may require optimization.",
                "Transporter effects, solubility limits, and assay conditions can affect interpretation.",
            ),
        )
        _add_assay(
            assays,
            _make_assay(
                "Microsomal and hepatocyte stability",
                "Metabolic stability",
                priority_depth if priority_depth in {"essential", "recommended"} else "recommended",
                "Metabolic stability is a core follow-up for candidates kept under review.",
                ["candidate selected for computational follow-up"],
                "remaining parent compound over time and intrinsic clearance estimate",
                controls,
                "Rapid turnover would support a need for metabolism optimization or additional pharmacokinetic review.",
                "This is planning guidance only; species, cofactors, and matrix choice require expert design.",
            ),
        )
        _add_assay(
            assays,
            _make_assay(
                "CYP inhibition panel",
                "Drug-drug interaction risk",
                "recommended",
                "CYP liability is not predicted by the MVP; a real assay is needed if the candidate advances.",
                ["CYP prediction not implemented or not considered definitive"],
                "inhibition signal against a qualified CYP panel",
                controls,
                "Meaningful CYP inhibition would trigger DDI risk review and possible deprioritization or redesign.",
                "The app does not predict CYP inhibition here; panel selection must follow laboratory and project context.",
            ),
        )
        _add_assay(
            assays,
            _make_assay(
                "Plasma protein binding",
                "Distribution",
                "optional" if priority_depth == "optional" else "recommended",
                "Binding information helps interpret free exposure once a candidate is kept for further ADME review.",
                ["candidate selected for follow-up"],
                "fraction unbound in plasma or relevant matrix",
                controls,
                "Very high binding may affect free exposure interpretation and follow-up study design.",
                "Binding assays are matrix- and species-dependent and do not prove efficacy or safety.",
            ),
        )

    if payload.include_toxicity_assays:
        tox_priority = "essential" if concern_level == "High" or structural_risk in {"Medium", "High"} else "recommended"
        _add_assay(
            assays,
            _make_assay(
                "Cytotoxicity / cell viability assay",
                "Cytotoxicity",
                tox_priority,
                "General cell viability should be checked when computational toxicity concern or structural alerts are present.",
                [f"overall_concern={concern_level}", f"structural_alert_risk={structural_risk}"],
                "cell viability across an appropriate concentration range",
                controls,
                "Observed cytotoxicity would support caution and may require concentration adjustment, redesign, or additional toxicity profiling.",
                "Cell-line choice, exposure time, and compound solubility can strongly affect interpretation.",
            ),
        )
        _add_assay(
            assays,
            _make_assay(
                "hERG patch clamp or validated hERG screen",
                "Cardiotoxicity",
                "essential" if concern_level == "High" or priority_depth == "essential" else "recommended",
                "hERG is not faked by DrugScreen360; direct experimental follow-up is required if a candidate advances.",
                ["hERG model not implemented or not definitive", f"priority_label={candidate.priority_label or 'not available'}"],
                "hERG current inhibition or validated surrogate readout",
                controls,
                "A concerning signal would require cardiotoxicity risk review before progression.",
                "This is not a protocol or safety determination; platform and thresholds require qualified review.",
            ),
        )
        _add_assay(
            assays,
            _make_assay(
                "Ames test / in vitro genotoxicity package",
                "Genotoxicity",
                "essential" if structural_risk in {"Medium", "High"} else "recommended",
                "Mutagenicity is not faked by the app; structural alerts or candidate advancement require confirmatory testing.",
                [f"structural_alert_risk={structural_risk}", "Ames prediction not implemented or not definitive"],
                "mutation or genotoxicity signal in qualified assays",
                controls,
                "A positive signal would support stopping, redesigning, or escalating expert toxicology review.",
                "Assay selection and interpretation must follow validated guidelines and qualified toxicology review.",
            ),
        )
        _add_assay(
            assays,
            _make_assay(
                "Hepatocyte toxicity assay",
                "Hepatotoxicity",
                "essential" if concern_level == "High" else "recommended",
                "Hepatotoxicity is not proven computationally and should be assessed experimentally for advancing candidates.",
                [f"overall_concern={concern_level}", "hepatotoxicity model not implemented or not definitive"],
                "cell health, stress, or injury markers in relevant hepatic system",
                controls,
                "A concerning signal would support hepatotoxicity review, exposure margin evaluation, or redesign.",
                "In vitro hepatotoxicity assays do not alone establish in vivo or clinical safety.",
            ),
        )

    if payload.include_target_assays and candidate.target_name:
        _add_assay(
            assays,
            _make_assay(
                "Target-specific biochemical assay",
                "Target engagement",
                "recommended",
                "Target-linked computational or public-data context should be confirmed experimentally.",
                [f"target={candidate.target_name}"],
                "target activity, binding, or inhibition readout appropriate to the target",
                controls,
                "A weak or absent target signal would challenge target-linked prioritization.",
                "Target assay design depends on target biology, assay format, and qualified experimental validation.",
            ),
        )
        _add_assay(
            assays,
            _make_assay(
                "Cell-based functional assay",
                "Functional biology",
                "optional" if priority_depth == "optional" else "recommended",
                "A cellular assay can help test whether target modulation translates into a relevant biological response.",
                [f"target={candidate.target_name}"],
                "functional pathway or phenotype readout",
                controls,
                "Discordance between biochemical and cell-based results would require mechanism and exposure review.",
                "Cellular assays do not prove clinical efficacy and need orthogonal confirmation.",
            ),
        )

    if domain_status == "outside_domain":
        warnings.append("Candidate is outside the model applicability domain; computational predictions should be treated as unreliable.")
        _add_assay(
            assays,
            _make_assay(
                "Orthogonal confirmatory ADMET panel",
                "Evidence reliability",
                "essential",
                "Outside-domain predictions should not be relied on without broad experimental confirmation.",
                ["domain_status=outside_domain"],
                "orthogonal ADME and toxicity readouts selected for the project context",
                controls,
                "Consistent acceptable results across orthogonal assays would reduce concern; discordant results require redesign or retesting.",
                "The planner does not select exact protocols or acceptance criteria.",
            ),
        )

    if uncertainty == "high":
        warnings.append("Prediction uncertainty is high; repeat or orthogonal validation is recommended before relying on the ranking.")
        _add_assay(
            assays,
            _make_assay(
                "Repeat / orthogonal validation check",
                "Uncertainty follow-up",
                "essential",
                "High uncertainty means a single computational output should not drive progression.",
                ["uncertainty_level=high"],
                "repeatability or independent orthogonal assay signal",
                controls,
                "Non-reproducible or discordant results would support deprioritization or more data collection.",
                "Repeat design depends on assay platform and qualified laboratory SOPs.",
            ),
        )

    if evidence_strength in {"weak_internal", "externally_weak", "uncertain", "not_available"} and priority_depth == "essential":
        _add_assay(
            assays,
            _make_assay(
                "Minimum validation panel before progression",
                "Evidence quality",
                "essential",
                "A high-priority candidate with weak or missing evidence requires a minimum validation panel before progression.",
                [f"evidence_strength={evidence_strength}"],
                "combined solubility, permeability, toxicity, and project-relevant activity readouts",
                controls,
                "Failure in core panel assays would support redesign or deprioritization despite computational priority.",
                "This panel is conceptual; assay composition and thresholds require expert review.",
            ),
        )

    if external_status in {"missing", "not available", "not_available", "unknown"}:
        warnings.append("External validation support is missing or not available for this candidate/model context.")

    if candidate.priority_label == "insufficient_data" or not evidence_strength or evidence_strength == "not available":
        _add_assay(
            assays,
            _make_assay(
                "Data completion and compound identity confirmation",
                "Data readiness",
                "essential" if candidate.priority_label == "insufficient_data" else "recommended",
                "Missing or insufficient evidence should be resolved before wet-lab prioritization.",
                ["missing evidence or insufficient-data priority label"],
                "confirmed identity, purity/context metadata, and complete computational fields",
                controls,
                "Incomplete identity or metadata should pause downstream experimental prioritization.",
                "This is a data-readiness check and not an efficacy or safety assay.",
            ),
        )

    decision_points.append(
        {
            "question": "Does experimental evidence support continuing this candidate?",
            "supportive_pattern": "Core assays produce project-acceptable readouts under validated SOPs and no major toxicity, solubility, permeability, or target-engagement concern emerges.",
            "challenge_pattern": "Assays show poor solubility/permeability, strong toxicity/genotoxicity/cardiotoxicity concern, weak target signal, or non-reproducible results.",
            "guidance": THRESHOLD_GUIDANCE,
        }
    )
    if domain_status == "outside_domain":
        decision_points.append(
            {
                "question": "Can outside-domain computational evidence be trusted?",
                "supportive_pattern": "Independent experimental assays align with the intended risk interpretation.",
                "challenge_pattern": "Orthogonal assays conflict with computational output or show unacceptable risk.",
                "guidance": "Outside-domain predictions should remain low-confidence until independently supported.",
            }
        )

    ordered = sorted(assays.values(), key=lambda item: (-PRIORITY_ORDER[item.recommendation_priority], item.assay_category, item.assay_name))
    if any(item.recommendation_priority == "essential" for item in ordered):
        next_step = "Run essential confirmatory assays before relying on computational priority."
    elif ordered:
        next_step = "Review recommended assays with qualified laboratory personnel and select a focused validation panel."
    else:
        next_step = "Complete missing candidate data before experimental planning."
    return ordered, decision_points, list(dict.fromkeys(warnings)), next_step


def _invalid_candidate(candidate: ValidationCandidateInput, payload: ExperimentalValidationPlanRequest, reason: str) -> ValidationPlanCandidateResult:
    assay = _make_assay(
        "Data completion and compound identity confirmation",
        "Data readiness",
        "essential",
        "A valid molecule representation is required before any assay plan can be interpreted.",
        [reason],
        "validated compound identity and parseable structure representation",
        _general_controls(payload.include_controls),
        "If identity or structure cannot be confirmed, downstream computational and experimental planning should pause.",
        "No experimental validation plan can compensate for an invalid or missing structure.",
    )
    return ValidationPlanCandidateResult(
        compound_name=candidate.compound_name,
        compound_id=candidate.compound_id,
        smiles=candidate.smiles or candidate.canonical_smiles or "",
        valid=False,
        invalid_reason=reason,
        priority_label=candidate.priority_label or "insufficient_data",
        source_type=payload.source_type,
        source_id=candidate.metadata.get("source_id"),
        recommended_assays=[assay],
        decision_points=[],
        warnings=[reason],
        limitations=LIMITATIONS,
        recommended_next_step="Fix or replace the molecule representation before wet-lab planning.",
    )


def _plan_candidate(candidate: ValidationCandidateInput, payload: ExperimentalValidationPlanRequest) -> ValidationPlanCandidateResult:
    raw_smiles = (candidate.canonical_smiles or candidate.smiles or "").strip()
    if not raw_smiles:
        return _invalid_candidate(candidate, payload, "Missing SMILES.")
    try:
        mol = parse_smiles(raw_smiles)
        canonical = Chem.MolToSmiles(mol, canonical=True)
    except Exception as exc:
        return _invalid_candidate(candidate, payload, f"Invalid SMILES: {exc}")

    descriptor_model = calculate_descriptors(canonical)
    descriptors = descriptor_model.model_dump()
    rules = evaluate_rules(descriptor_model)
    admet = evaluate_admet_toxicity(canonical, descriptor_model)
    computed_admet = {
        "concern_score": admet.overall.overall_admet_tox_concern_score,
        "concern_level": admet.overall.concern_level,
        "absorption_risk": admet.absorption.absorption_risk,
        "solubility_risk": admet.solubility.solubility_risk,
        "structural_alert_risk": admet.structural_alerts.structural_alert_risk,
        "developability_risk": rules.developability_risk,
        "drug_likeness_status": rules.basic_drug_likeness_status,
    }
    admet_summary = _admet_summary_from_metadata(candidate.metadata, computed_admet)
    assays, decision_points, warnings, next_step = _recommend_assays(candidate, descriptors, admet_summary, payload)
    return ValidationPlanCandidateResult(
        compound_name=candidate.compound_name,
        compound_id=candidate.compound_id,
        smiles=raw_smiles,
        canonical_smiles=canonical,
        valid=True,
        priority_label=candidate.priority_label,
        source_type=payload.source_type,
        source_id=candidate.metadata.get("source_id"),
        descriptors=descriptors,
        rule_based_admet_summary=admet_summary,
        domain_status=candidate.domain_status or candidate.metadata.get("domain_status") or "not available",
        uncertainty_level=candidate.uncertainty_level or candidate.metadata.get("uncertainty_level") or "unknown",
        external_validation_status=candidate.external_validation_status or candidate.metadata.get("external_validation_warning") or "not available",
        evidence_strength=candidate.evidence_strength or candidate.metadata.get("explainability_evidence_strength") or "not available",
        recommended_assays=assays,
        decision_points=decision_points,
        warnings=warnings,
        limitations=LIMITATIONS,
        recommended_next_step=next_step,
    )


def _overall_recommendations(results: list[ValidationPlanCandidateResult]) -> list[str]:
    essential = sum(1 for result in results for assay in result.recommended_assays if assay.recommendation_priority == "essential")
    invalid = sum(1 for result in results if not result.valid)
    recommendations = [
        "Review assay choices, controls, acceptance criteria, and safety requirements with qualified laboratory personnel.",
        "Treat the plan as experimental planning support only; no assays have been performed.",
    ]
    if essential:
        recommendations.append(f"Address {essential} essential assay recommendation(s) before relying on computational prioritization.")
    if invalid:
        recommendations.append(f"Resolve {invalid} invalid or incomplete molecule record(s) before experimental planning.")
    if any(result.domain_status == "outside_domain" for result in results):
        recommendations.append("Outside-domain candidates need orthogonal confirmation before computational predictions are trusted.")
    return recommendations


def _save_plan(payload: ExperimentalValidationPlanRequest, response: ExperimentalValidationPlanResponse) -> int:
    init_db()
    summary = response.model_dump(exclude={"plan_id", "created_at"})
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO experimental_validation_plans (
                project_id, source_type, candidate_count, plan_title, summary_json, warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.project_id,
                payload.source_type,
                response.candidate_count,
                response.plan_title,
                json.dumps(summary),
                json.dumps(response.warnings),
            ),
        )
        plan_id = int(cursor.lastrowid)
        for candidate in response.candidate_plans:
            connection.execute(
                """
                INSERT INTO experimental_validation_plan_candidates (
                    plan_id, compound_name, smiles, canonical_smiles, priority_label,
                    recommended_assays_json, decision_points_json, warnings_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    candidate.compound_name,
                    candidate.smiles,
                    candidate.canonical_smiles,
                    candidate.priority_label,
                    json.dumps([assay.model_dump() for assay in candidate.recommended_assays]),
                    json.dumps(candidate.decision_points),
                    json.dumps(candidate.warnings),
                ),
            )
    return plan_id


def _attach_to_project(project_id: int, plan_id: int, response: ExperimentalValidationPlanResponse) -> None:
    try:
        essential = sum(1 for result in response.candidate_plans for assay in result.recommended_assays if assay.recommendation_priority == "essential")
        attach_project_item(
            project_id,
            ProjectAttachRequest(
                item_type="experimental_validation_plan",
                item_id=str(plan_id),
                item_title=response.plan_title,
                metadata={
                    "workflow_type": "experimental_validation_planner",
                    "plan_id": plan_id,
                    "source_type": response.source_type,
                    "candidate_count": response.candidate_count,
                    "essential_assay_count": essential,
                    "candidate_plans": [item.model_dump() for item in response.candidate_plans],
                    "decision": "experimental planning support only",
                    "scientific_notice": response.scientific_notice,
                },
            ),
        )
    except Exception:
        pass


def create_validation_plan(payload: ExperimentalValidationPlanRequest) -> ExperimentalValidationPlanResponse:
    candidates = _load_candidates(payload)
    if not candidates:
        raise HTTPException(status_code=422, detail="No candidates were provided for validation planning.")
    title = payload.plan_title or "DrugScreen360 Experimental Validation Plan"
    candidate_plans = [_plan_candidate(candidate, payload) for candidate in candidates]
    warnings = list(dict.fromkeys([warning for result in candidate_plans for warning in result.warnings]))
    response = ExperimentalValidationPlanResponse(
        plan_id=0,
        project_id=payload.project_id,
        source_type=payload.source_type,
        plan_title=title,
        candidate_count=len(candidate_plans),
        candidate_plans=candidate_plans,
        overall_recommendations=_overall_recommendations(candidate_plans),
        warnings=warnings,
        limitations=LIMITATIONS,
        scientific_notice=SCIENTIFIC_NOTICE,
    )
    plan_id = _save_plan(payload, response)
    response.plan_id = plan_id
    if payload.project_id:
        _attach_to_project(payload.project_id, plan_id, response)
    return response


def get_validation_plan(plan_id: int) -> ExperimentalValidationPlanResponse:
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM experimental_validation_plans WHERE id = ?", (plan_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Experimental validation plan not found.")
    summary = json.loads(row["summary_json"])
    return ExperimentalValidationPlanResponse(
        plan_id=row["id"],
        project_id=row["project_id"],
        source_type=row["source_type"],
        plan_title=row["plan_title"],
        candidate_count=row["candidate_count"],
        candidate_plans=[ValidationPlanCandidateResult.model_validate(item) for item in summary.get("candidate_plans", [])],
        overall_recommendations=summary.get("overall_recommendations", []),
        warnings=json.loads(row["warnings_json"]) if row["warnings_json"] else [],
        limitations=summary.get("limitations") or LIMITATIONS,
        scientific_notice=summary.get("scientific_notice") or SCIENTIFIC_NOTICE,
        created_at=row["created_at"],
    )


def list_validation_plans() -> list[ExperimentalValidationPlanRunSummary]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM experimental_validation_plans ORDER BY datetime(created_at) DESC, id DESC LIMIT 50"
        ).fetchall()
    summaries = []
    for row in rows:
        plan = get_validation_plan(row["id"])
        essential = sum(1 for result in plan.candidate_plans for assay in result.recommended_assays if assay.recommendation_priority == "essential")
        recommended = sum(1 for result in plan.candidate_plans for assay in result.recommended_assays if assay.recommendation_priority == "recommended")
        optional = sum(1 for result in plan.candidate_plans for assay in result.recommended_assays if assay.recommendation_priority == "optional")
        summaries.append(
            ExperimentalValidationPlanRunSummary(
                plan_id=plan.plan_id,
                project_id=plan.project_id,
                source_type=plan.source_type,
                plan_title=plan.plan_title,
                candidate_count=plan.candidate_count,
                essential_assay_count=essential,
                recommended_assay_count=recommended,
                optional_assay_count=optional,
                warnings=plan.warnings,
                created_at=plan.created_at,
            )
        )
    return summaries


def validation_plan_report_json(plan_id: int) -> dict[str, Any]:
    plan = get_validation_plan(plan_id)
    return {
        **plan.model_dump(),
        "report_type": "experimental_validation_plan",
        "assay_result_status": "No experimental assay results are generated or claimed by this report.",
    }


def validation_plan_csv(plan_id: int) -> str:
    plan = get_validation_plan(plan_id)
    output = StringIO()
    fieldnames = [
        "plan_id",
        "compound_name",
        "canonical_smiles",
        "priority_label",
        "assay_name",
        "assay_category",
        "recommendation_priority",
        "reason",
        "linked_computational_evidence",
        "suggested_readout",
        "suggested_controls",
        "decision_threshold_guidance",
        "expected_interpretation",
        "limitations",
        "safety_note",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for candidate in plan.candidate_plans:
        for assay in candidate.recommended_assays:
            writer.writerow(
                {
                    "plan_id": plan.plan_id,
                    "compound_name": candidate.compound_name,
                    "canonical_smiles": candidate.canonical_smiles,
                    "priority_label": candidate.priority_label,
                    "assay_name": assay.assay_name,
                    "assay_category": assay.assay_category,
                    "recommendation_priority": assay.recommendation_priority,
                    "reason": assay.reason,
                    "linked_computational_evidence": " | ".join(assay.linked_computational_evidence),
                    "suggested_readout": assay.suggested_readout,
                    "suggested_controls": " | ".join(assay.suggested_controls),
                    "decision_threshold_guidance": assay.decision_threshold_guidance,
                    "expected_interpretation": assay.expected_interpretation,
                    "limitations": assay.limitations,
                    "safety_note": assay.safety_note,
                }
            )
    return output.getvalue()


def latest_validation_plan_summary() -> dict[str, Any]:
    try:
        plans = list_validation_plans()
    except Exception:
        return {"status": "not_available"}
    if not plans:
        return {"status": "not_available"}
    latest = plans[0]
    return {
        "status": "available",
        "latest_plan": latest.model_dump(),
        "next_recommended_step": "Review essential assays with qualified laboratory personnel before relying on computational prioritization.",
    }
