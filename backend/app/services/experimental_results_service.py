import csv
import json
from io import StringIO
from typing import Any

from fastapi import HTTPException
from rdkit import Chem

from app.database import get_connection, init_db
from app.models.experimental_results_models import (
    CandidateExperimentalFeedback,
    ExperimentalFeedbackCompareRequest,
    ExperimentalFeedbackResponse,
    ExperimentalResultBatchResponse,
    ExperimentalResultBatchSummary,
    ExperimentalResultCreateRequest,
    ExperimentalResultInput,
    InvalidExperimentalResultRow,
    SavedExperimentalResult,
)
from app.models.project_workspace_models import ProjectAttachRequest
from app.services.admet_lead_service import get_lead_prioritization_run
from app.services.descriptors import parse_smiles
from app.services.project_workspace_service import attach_project_item
from app.services.validation_planner_service import get_validation_plan

SCIENTIFIC_NOTICE = "Experimental feedback summary only. Interpretation requires qualified scientific review."
LIMITATIONS = [
    "Experimental results are user-entered or imported; DrugScreen360 does not create or simulate wet-lab results.",
    "Feedback labels compare available experimental result direction against available computational context only.",
    "A single assay result is not clinical validation and does not prove safety, efficacy, regulatory approval, or market readiness.",
    "Model retraining is not performed by this feedback workflow.",
]
CSV_COLUMNS = [
    "compound_name",
    "smiles",
    "canonical_smiles",
    "assay_name",
    "assay_category",
    "measured_value",
    "measurement_unit",
    "qualitative_result",
    "result_direction",
    "replicate_count",
    "notes",
]
VALID_DIRECTIONS = {"favorable", "unfavorable", "neutral", "inconclusive", "not_applicable"}


def _canonicalize(smiles: str | None) -> tuple[str | None, str | None]:
    if not smiles or not smiles.strip():
        return None, None
    try:
        mol = parse_smiles(smiles.strip())
        return Chem.MolToSmiles(mol, canonical=True), None
    except Exception as exc:
        return None, f"Invalid SMILES: {exc}"


def _validate_result(item: ExperimentalResultInput, row_number: int) -> tuple[SavedExperimentalResult | None, InvalidExperimentalResultRow | None]:
    if not item.assay_name.strip():
        return None, InvalidExperimentalResultRow(row_number=row_number, input_value=item.compound_name, error_reason="assay_name is required.")
    if not item.assay_category.strip():
        return None, InvalidExperimentalResultRow(row_number=row_number, input_value=item.compound_name, error_reason="assay_category is required.")
    if item.result_direction not in VALID_DIRECTIONS:
        return None, InvalidExperimentalResultRow(row_number=row_number, input_value=item.result_direction, error_reason="result_direction is invalid.")
    canonical = item.canonical_smiles
    if item.smiles and not canonical:
        canonical, error = _canonicalize(item.smiles)
        if error:
            return None, InvalidExperimentalResultRow(row_number=row_number, input_value=item.smiles, error_reason=error)
    return (
        SavedExperimentalResult(
            compound_name=item.compound_name,
            smiles=item.smiles,
            canonical_smiles=canonical,
            assay_name=item.assay_name.strip(),
            assay_category=item.assay_category.strip(),
            measured_value=item.measured_value,
            measurement_unit=item.measurement_unit,
            qualitative_result=item.qualitative_result,
            result_direction=item.result_direction,
            replicate_count=item.replicate_count,
            notes=item.notes,
        ),
        None,
    )


def _save_batch(
    payload: ExperimentalResultCreateRequest,
    accepted: list[SavedExperimentalResult],
    invalid_rows: list[InvalidExperimentalResultRow],
    warnings: list[str],
) -> ExperimentalResultBatchResponse:
    init_db()
    summary = {
        "scientific_notice": SCIENTIFIC_NOTICE,
        "invalid_rows": [row.model_dump() for row in invalid_rows],
        "limitations": LIMITATIONS,
    }
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO experimental_result_batches (
                project_id, validation_plan_id, source_type, result_count, accepted_count,
                rejected_count, summary_json, warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.project_id,
                payload.validation_plan_id,
                payload.source_type,
                len(accepted) + len(invalid_rows),
                len(accepted),
                len(invalid_rows),
                json.dumps(summary),
                json.dumps(warnings),
            ),
        )
        batch_id = int(cursor.lastrowid)
        saved: list[SavedExperimentalResult] = []
        for item in accepted:
            row_cursor = connection.execute(
                """
                INSERT INTO experimental_results (
                    batch_id, project_id, validation_plan_id, compound_name, smiles, canonical_smiles,
                    assay_name, assay_category, measured_value, measurement_unit, qualitative_result,
                    result_direction, replicate_count, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    payload.project_id,
                    payload.validation_plan_id,
                    item.compound_name,
                    item.smiles,
                    item.canonical_smiles,
                    item.assay_name,
                    item.assay_category,
                    item.measured_value,
                    item.measurement_unit,
                    item.qualitative_result,
                    item.result_direction,
                    item.replicate_count,
                    item.notes,
                ),
            )
            saved.append(item.model_copy(update={"id": int(row_cursor.lastrowid), "batch_id": batch_id, "project_id": payload.project_id, "validation_plan_id": payload.validation_plan_id}))
    response = ExperimentalResultBatchResponse(
        result_batch_id=batch_id,
        project_id=payload.project_id,
        validation_plan_id=payload.validation_plan_id,
        source_type=payload.source_type,
        result_count=len(accepted) + len(invalid_rows),
        accepted_count=len(accepted),
        rejected_count=len(invalid_rows),
        saved_results=saved,
        invalid_rows=invalid_rows,
        warnings=warnings,
        scientific_notice=SCIENTIFIC_NOTICE,
    )
    if payload.project_id:
        _attach_results_to_project(payload.project_id, response)
    return response


def _attach_results_to_project(project_id: int, response: ExperimentalResultBatchResponse) -> None:
    try:
        attach_project_item(
            project_id,
            ProjectAttachRequest(
                item_type="experimental_result_batch",
                item_id=str(response.result_batch_id),
                item_title=f"Experimental Results Batch #{response.result_batch_id}",
                metadata={
                    "workflow_type": "experimental_results",
                    "result_batch_id": response.result_batch_id,
                    "validation_plan_id": response.validation_plan_id,
                    "accepted_count": response.accepted_count,
                    "rejected_count": response.rejected_count,
                    "results": [item.model_dump() for item in response.saved_results],
                    "scientific_notice": response.scientific_notice,
                },
            ),
        )
    except Exception:
        pass


def _attach_feedback_to_project(project_id: int, response: ExperimentalFeedbackResponse) -> None:
    try:
        attach_project_item(
            project_id,
            ProjectAttachRequest(
                item_type="experimental_feedback_summary",
                item_id=str(response.feedback_id),
                item_title=f"Experimental Feedback Summary #{response.feedback_id}",
                metadata={
                    "workflow_type": "experimental_feedback",
                    "feedback_id": response.feedback_id,
                    "result_batch_id": response.result_batch_id,
                    "supported_count": response.supported_count,
                    "contradicted_count": response.contradicted_count,
                    "inconclusive_count": response.inconclusive_count,
                    "not_comparable_count": response.not_comparable_count,
                    "overall_feedback_label": response.overall_feedback_label,
                    "candidate_feedback": [item.model_dump() for item in response.candidate_feedback],
                    "scientific_notice": response.scientific_notice,
                },
            ),
        )
    except Exception:
        pass


def create_experimental_results(payload: ExperimentalResultCreateRequest) -> ExperimentalResultBatchResponse:
    if not payload.results:
        raise HTTPException(status_code=422, detail="No experimental results were provided.")
    accepted: list[SavedExperimentalResult] = []
    invalid_rows: list[InvalidExperimentalResultRow] = []
    for index, item in enumerate(payload.results, start=1):
        result, invalid = _validate_result(item, index)
        if invalid:
            invalid_rows.append(invalid)
        elif result:
            accepted.append(result)
    warnings = []
    if invalid_rows:
        warnings.append(f"{len(invalid_rows)} row(s) were rejected and preserved with reasons.")
    if not accepted:
        warnings.append("No valid experimental results were saved.")
    return _save_batch(payload, accepted, invalid_rows, warnings)


def import_experimental_results_csv(content: bytes, filename: str, project_id: int | None, validation_plan_id: int | None) -> ExperimentalResultBatchResponse:
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV experimental result imports are supported in this endpoint.")
    text = content.decode("utf-8-sig")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV header row is required.")
    rows = []
    invalid_rows: list[InvalidExperimentalResultRow] = []
    for index, row in enumerate(reader, start=2):
        normalized = {str(key).strip().lower(): value for key, value in row.items()}
        try:
            rows.append(
                ExperimentalResultInput(
                    compound_name=normalized.get("compound_name"),
                    smiles=normalized.get("smiles"),
                    canonical_smiles=normalized.get("canonical_smiles") or None,
                    assay_name=normalized.get("assay_name") or "",
                    assay_category=normalized.get("assay_category") or "",
                    measured_value=normalized.get("measured_value"),
                    measurement_unit=normalized.get("measurement_unit"),
                    qualitative_result=normalized.get("qualitative_result"),
                    result_direction=(normalized.get("result_direction") or "").strip().lower(),  # type: ignore[arg-type]
                    replicate_count=int(normalized["replicate_count"]) if (normalized.get("replicate_count") or "").strip().isdigit() else None,
                    notes=normalized.get("notes"),
                    source_type="csv_import",
                )
            )
        except Exception as exc:
            invalid_rows.append(InvalidExperimentalResultRow(row_number=index, input_value=str(row), error_reason=str(exc)))
    payload = ExperimentalResultCreateRequest(project_id=project_id, validation_plan_id=validation_plan_id, source_type="csv_import", results=rows)
    response = create_experimental_results(payload)
    if invalid_rows:
        response.invalid_rows.extend(invalid_rows)
        response.rejected_count += len(invalid_rows)
        response.result_count += len(invalid_rows)
        response.warnings.append(f"{len(invalid_rows)} malformed CSV row(s) were rejected.")
    return response


def _row_to_saved(row: Any) -> SavedExperimentalResult:
    return SavedExperimentalResult(
        id=row["id"],
        batch_id=row["batch_id"],
        project_id=row["project_id"],
        validation_plan_id=row["validation_plan_id"],
        compound_name=row["compound_name"],
        smiles=row["smiles"],
        canonical_smiles=row["canonical_smiles"],
        assay_name=row["assay_name"],
        assay_category=row["assay_category"],
        measured_value=row["measured_value"],
        measurement_unit=row["measurement_unit"],
        qualitative_result=row["qualitative_result"],
        result_direction=row["result_direction"],
        replicate_count=row["replicate_count"],
        notes=row["notes"],
        created_at=row["created_at"],
    )


def get_experimental_result_batch(batch_id: int) -> ExperimentalResultBatchResponse:
    init_db()
    with get_connection() as connection:
        batch = connection.execute("SELECT * FROM experimental_result_batches WHERE id = ?", (batch_id,)).fetchone()
        rows = connection.execute("SELECT * FROM experimental_results WHERE batch_id = ? ORDER BY id", (batch_id,)).fetchall()
    if not batch:
        raise HTTPException(status_code=404, detail="Experimental result batch not found.")
    summary = json.loads(batch["summary_json"]) if batch["summary_json"] else {}
    return ExperimentalResultBatchResponse(
        result_batch_id=batch["id"],
        project_id=batch["project_id"],
        validation_plan_id=batch["validation_plan_id"],
        source_type=batch["source_type"],
        result_count=batch["result_count"],
        accepted_count=batch["accepted_count"],
        rejected_count=batch["rejected_count"],
        saved_results=[_row_to_saved(row) for row in rows],
        invalid_rows=[InvalidExperimentalResultRow.model_validate(item) for item in summary.get("invalid_rows", [])],
        warnings=json.loads(batch["warnings_json"]) if batch["warnings_json"] else [],
        scientific_notice=SCIENTIFIC_NOTICE,
        created_at=batch["created_at"],
    )


def list_experimental_result_batches() -> list[ExperimentalResultBatchSummary]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM experimental_result_batches ORDER BY datetime(created_at) DESC, id DESC LIMIT 50"
        ).fetchall()
    return [
        ExperimentalResultBatchSummary(
            result_batch_id=row["id"],
            project_id=row["project_id"],
            validation_plan_id=row["validation_plan_id"],
            source_type=row["source_type"],
            result_count=row["result_count"],
            accepted_count=row["accepted_count"],
            rejected_count=row["rejected_count"],
            warnings=json.loads(row["warnings_json"]) if row["warnings_json"] else [],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def experimental_results_csv(batch_id: int) -> str:
    batch = get_experimental_result_batch(batch_id)
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for item in batch.saved_results:
        writer.writerow(item.model_dump())
    return output.getvalue()


def _validation_plan_context(plan_id: int | None) -> dict[str, dict[str, Any]]:
    if not plan_id:
        return {}
    try:
        plan = get_validation_plan(plan_id)
    except Exception:
        return {}
    context = {}
    for candidate in plan.candidate_plans:
        if not candidate.canonical_smiles:
            continue
        context[candidate.canonical_smiles] = {
            "source": "validation_plan",
            "priority_label": candidate.priority_label,
            "domain_status": candidate.domain_status,
            "uncertainty_level": candidate.uncertainty_level,
            "evidence_strength": candidate.evidence_strength,
            "admet": candidate.rule_based_admet_summary,
            "recommended_assays": [assay.model_dump() for assay in candidate.recommended_assays],
        }
    return context


def _lead_context(run_id: int | None) -> dict[str, dict[str, Any]]:
    if not run_id:
        return {}
    try:
        run = get_lead_prioritization_run(run_id)
    except Exception:
        return {}
    context = {}
    for candidate in run.ranked_candidates:
        if candidate.canonical_smiles:
            context[candidate.canonical_smiles] = {
                "source": "lead_prioritization",
                "priority_label": candidate.priority_label,
                "domain_status": candidate.domain_status,
                "uncertainty_level": candidate.uncertainty_level,
                "evidence_strength": candidate.explainability_evidence_strength,
                "admet": candidate.rule_based_admet_summary,
                "ranking_score": candidate.total_score,
            }
    return context


def _risk_is_high(context: dict[str, Any], assay_category: str) -> bool:
    admet = context.get("admet") or {}
    concern = str(admet.get("concern_level") or "").lower()
    structural = str(admet.get("structural_alert_risk") or "").lower()
    solubility = str(admet.get("solubility_risk") or "").lower()
    absorption = str(admet.get("absorption_risk") or "").lower()
    category = assay_category.lower()
    if concern == "high" or structural == "high":
        return True
    if "solub" in category and solubility in {"medium", "high"}:
        return True
    if ("permeability" in category or "adme" in category) and absorption in {"medium", "high"}:
        return True
    return False


def _recommended_for_assay(context: dict[str, Any], assay_name: str, assay_category: str) -> bool:
    for assay in context.get("recommended_assays") or []:
        name = str(assay.get("assay_name") or "").lower()
        category = str(assay.get("assay_category") or "").lower()
        if assay_name.lower() in name or name in assay_name.lower():
            return True
        if assay_category.lower() and assay_category.lower() in category:
            return True
    return False


def _feedback_for_result(result: SavedExperimentalResult, context: dict[str, Any]) -> CandidateExperimentalFeedback:
    direction = result.result_direction
    has_context = bool(context)
    domain = context.get("domain_status") or "not available"
    uncertainty = context.get("uncertainty_level") or "unknown"
    evidence = context.get("evidence_strength") or "not available"
    priority = context.get("priority_label")
    risk_high = _risk_is_high(context, result.assay_category)
    assay_was_recommended = _recommended_for_assay(context, result.assay_name, result.assay_category)
    ranking_feedback = "ranking_inconclusive"

    if direction in {"neutral", "inconclusive", "not_applicable"}:
        label = "inconclusive"
        explanation = "The experimental result direction is neutral, inconclusive, or not applicable, so it cannot support or contradict the computational context."
        next_step = "Repeat or use an orthogonal assay if this result is important for the project decision."
    elif not has_context:
        label = "insufficient_context"
        explanation = "No linked computational prediction, prioritization, or validation-plan context was available for comparison."
        next_step = "Link this result to a validation plan, lead prioritization run, model prediction, or project record before interpreting agreement."
    elif direction == "unfavorable" and (risk_high or assay_was_recommended):
        label = "prediction_supported"
        explanation = "The unfavorable assay direction is consistent with a prior computational risk flag or recommended follow-up assay."
        next_step = "Investigate the risk with repeat or orthogonal confirmation before progressing the candidate."
    elif direction == "favorable" and risk_high:
        label = "prediction_contradicted"
        explanation = "The favorable assay direction challenges a prior high computational risk signal."
        next_step = "Review assay conditions and consider orthogonal confirmation before downgrading the computational concern."
    elif direction == "favorable" and priority in {"high_priority_for_review", "medium_priority_for_review"}:
        label = "prediction_supported"
        explanation = "The favorable assay direction is consistent with a candidate previously prioritized for review."
        next_step = "Do not escalate based on one result; collect additional ADME/tox and target-relevant evidence."
        ranking_feedback = "ranking_supported"
    elif direction == "unfavorable" and priority in {"high_priority_for_review", "medium_priority_for_review"}:
        label = "prediction_contradicted"
        explanation = "The unfavorable assay direction questions a candidate previously prioritized for review."
        next_step = "Investigate contradiction between ranking and assay result; repeat or use an orthogonal assay."
        ranking_feedback = "ranking_questioned"
    elif direction == "favorable":
        label = "inconclusive" if not assay_was_recommended else "prediction_supported"
        explanation = "The favorable result is useful but does not strongly map to a prior risk flag without additional context."
        next_step = "Collect additional ADME/tox evidence before changing candidate priority."
    else:
        label = "not_comparable"
        explanation = "The result direction could not be compared to the available computational context."
        next_step = "Review assay category, computational evidence, and data links."

    if ranking_feedback == "ranking_inconclusive" and priority:
        if label == "prediction_supported":
            ranking_feedback = "ranking_supported"
        elif label == "prediction_contradicted":
            ranking_feedback = "ranking_questioned"

    return CandidateExperimentalFeedback(
        compound_name=result.compound_name,
        canonical_smiles=result.canonical_smiles,
        assay_name=result.assay_name,
        assay_category=result.assay_category,
        experimental_result_summary={
            "measured_value": result.measured_value,
            "measurement_unit": result.measurement_unit,
            "qualitative_result": result.qualitative_result,
            "result_direction": result.result_direction,
            "replicate_count": result.replicate_count,
            "notes": result.notes,
        },
        linked_computational_prediction=context,
        domain_status=domain,
        uncertainty_level=uncertainty,
        evidence_strength=evidence,
        feedback_label=label,  # type: ignore[arg-type]
        ranking_feedback=ranking_feedback,
        explanation=explanation,
        recommended_next_step=next_step,
        limitations=LIMITATIONS,
    )


def _validation_plan_followup_status(plan_id: int | None, results: list[SavedExperimentalResult]) -> str:
    if not plan_id:
        return "not_evaluated"
    try:
        plan = get_validation_plan(plan_id)
    except Exception:
        return "not_evaluated"
    recommended = []
    for candidate in plan.candidate_plans:
        for assay in candidate.recommended_assays:
            recommended.append((candidate.canonical_smiles, assay.assay_name.lower(), assay.assay_category.lower()))
    if not recommended:
        return "no_recommended_assays"
    matched = 0
    for result in results:
        for smiles, assay_name, assay_category in recommended:
            if smiles and result.canonical_smiles and smiles != result.canonical_smiles:
                continue
            if result.assay_name.lower() in assay_name or assay_name in result.assay_name.lower() or result.assay_category.lower() in assay_category:
                matched += 1
                break
    if matched == 0:
        return "no_results_entered"
    if matched < len(recommended):
        return "partially_completed"
    return "results_entered"


def compare_experimental_feedback(payload: ExperimentalFeedbackCompareRequest) -> ExperimentalFeedbackResponse:
    batch = get_experimental_result_batch(payload.result_batch_id)
    plan_id = payload.validation_plan_id or batch.validation_plan_id
    context_by_smiles = _validation_plan_context(plan_id)
    lead_context = _lead_context(payload.lead_prioritization_run_id)
    for smiles, context in lead_context.items():
        context_by_smiles[smiles] = {**context_by_smiles.get(smiles, {}), **context}

    feedback = []
    warnings = []
    for result in batch.saved_results:
        context = context_by_smiles.get(result.canonical_smiles or "", {})
        if not context:
            warnings.append(f"No computational context was found for {result.compound_name or result.canonical_smiles or result.assay_name}.")
        feedback.append(_feedback_for_result(result, context))

    supported = sum(1 for item in feedback if item.feedback_label == "prediction_supported")
    contradicted = sum(1 for item in feedback if item.feedback_label == "prediction_contradicted")
    inconclusive = sum(1 for item in feedback if item.feedback_label in {"inconclusive", "insufficient_context"})
    not_comparable = sum(1 for item in feedback if item.feedback_label == "not_comparable")
    if contradicted:
        overall = "review_required_due_to_contradictions"
    elif supported and not (inconclusive or not_comparable):
        overall = "computational_context_partly_supported"
    elif supported:
        overall = "mixed_or_partial_support"
    else:
        overall = "inconclusive_or_not_comparable"
    followup_status = _validation_plan_followup_status(plan_id, batch.saved_results)
    if followup_status == "results_entered":
        followup_status = "feedback_generated"

    summary = {
        "candidate_feedback": [item.model_dump() for item in feedback],
        "overall_feedback_label": overall,
        "validation_plan_followup_status": followup_status,
        "limitations": LIMITATIONS,
        "scientific_notice": SCIENTIFIC_NOTICE,
    }
    agreement = {
        "supported_count": supported,
        "contradicted_count": contradicted,
        "inconclusive_count": inconclusive,
        "not_comparable_count": not_comparable,
    }
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO prediction_feedback_summaries (
                project_id, result_batch_id, linked_model_id, linked_prioritization_run_id,
                linked_validation_plan_id, feedback_summary_json, agreement_summary_json, warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.project_id or batch.project_id,
                payload.result_batch_id,
                payload.model_id,
                payload.lead_prioritization_run_id,
                plan_id,
                json.dumps(summary),
                json.dumps(agreement),
                json.dumps(list(dict.fromkeys(warnings))),
            ),
        )
        feedback_id = int(cursor.lastrowid)
    response = ExperimentalFeedbackResponse(
        feedback_id=feedback_id,
        project_id=payload.project_id or batch.project_id,
        result_batch_id=payload.result_batch_id,
        linked_model_id=payload.model_id,
        linked_prioritization_run_id=payload.lead_prioritization_run_id,
        linked_validation_plan_id=plan_id,
        compared_result_count=len(feedback),
        supported_count=supported,
        contradicted_count=contradicted,
        inconclusive_count=inconclusive,
        not_comparable_count=not_comparable,
        candidate_feedback=feedback,
        overall_feedback_label=overall,
        validation_plan_followup_status=followup_status,
        warnings=list(dict.fromkeys(warnings)),
        limitations=LIMITATIONS,
        scientific_notice=SCIENTIFIC_NOTICE,
    )
    if response.project_id:
        _attach_feedback_to_project(response.project_id, response)
    return response


def get_experimental_feedback(feedback_id: int) -> ExperimentalFeedbackResponse:
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM prediction_feedback_summaries WHERE id = ?", (feedback_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Experimental feedback summary not found.")
    summary = json.loads(row["feedback_summary_json"])
    agreement = json.loads(row["agreement_summary_json"])
    return ExperimentalFeedbackResponse(
        feedback_id=row["id"],
        project_id=row["project_id"],
        result_batch_id=row["result_batch_id"],
        linked_model_id=row["linked_model_id"],
        linked_prioritization_run_id=row["linked_prioritization_run_id"],
        linked_validation_plan_id=row["linked_validation_plan_id"],
        compared_result_count=len(summary.get("candidate_feedback", [])),
        supported_count=agreement.get("supported_count", 0),
        contradicted_count=agreement.get("contradicted_count", 0),
        inconclusive_count=agreement.get("inconclusive_count", 0),
        not_comparable_count=agreement.get("not_comparable_count", 0),
        candidate_feedback=[CandidateExperimentalFeedback.model_validate(item) for item in summary.get("candidate_feedback", [])],
        overall_feedback_label=summary.get("overall_feedback_label", "inconclusive_or_not_comparable"),
        validation_plan_followup_status=summary.get("validation_plan_followup_status", "not_evaluated"),
        warnings=json.loads(row["warnings_json"]) if row["warnings_json"] else [],
        limitations=summary.get("limitations") or LIMITATIONS,
        scientific_notice=summary.get("scientific_notice") or SCIENTIFIC_NOTICE,
        created_at=row["created_at"],
    )


def list_experimental_feedback() -> list[dict[str, Any]]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM prediction_feedback_summaries ORDER BY datetime(created_at) DESC, id DESC LIMIT 50"
        ).fetchall()
    output = []
    for row in rows:
        agreement = json.loads(row["agreement_summary_json"]) if row["agreement_summary_json"] else {}
        summary = json.loads(row["feedback_summary_json"]) if row["feedback_summary_json"] else {}
        output.append(
            {
                "feedback_id": row["id"],
                "project_id": row["project_id"],
                "result_batch_id": row["result_batch_id"],
                "linked_validation_plan_id": row["linked_validation_plan_id"],
                "overall_feedback_label": summary.get("overall_feedback_label"),
                "supported_count": agreement.get("supported_count", 0),
                "contradicted_count": agreement.get("contradicted_count", 0),
                "inconclusive_count": agreement.get("inconclusive_count", 0),
                "not_comparable_count": agreement.get("not_comparable_count", 0),
                "created_at": row["created_at"],
            }
        )
    return output


def experimental_feedback_report_json(feedback_id: int) -> dict[str, Any]:
    feedback = get_experimental_feedback(feedback_id)
    return {
        **feedback.model_dump(),
        "report_type": "experimental_prediction_feedback",
        "no_fake_results_statement": "This report contains only user-entered or imported experimental results. DrugScreen360 does not simulate assay outcomes.",
    }
