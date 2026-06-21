import csv
import json
from io import StringIO
from typing import Any

from fastapi import HTTPException

from app.database import get_connection, init_db
from app.models.project_workspace_models import (
    CandidateDecisionMatrixRow,
    ProjectActiveOption,
    ProjectAttachRequest,
    ProjectCreateRequest,
    ProjectDashboardResponse,
    ProjectDetail,
    ProjectItem,
    ProjectSummary,
    ProjectUpdateRequest,
)
from app.services.model_registry import model_status_response

PROJECT_LIMITATIONS = [
    "Saved projects organize local DrugScreen360 records only.",
    "Project workspaces do not prove safety, efficacy, clinical success, regulatory approval, or market readiness.",
    "Attached items retain their original computational and rule-based limitations.",
]


def _model_summary() -> dict[str, Any]:
    status = model_status_response()
    from app.services.admet_trained_model_service import get_active_trained_model_info
    active_trained = get_active_trained_model_info()
    
    external_val_summary = None
    active_model_domain_summary = None
    
    if active_trained and active_trained.get("status") in {"available", "active"}:
        model_id = active_trained.get("model_id")
        from app.services.admet_validation_service import get_latest_external_validation_by_model
        try:
            latest_run = get_latest_external_validation_by_model(model_id)
            if latest_run:
                external_val_summary = {
                    "run_id": latest_run["id"],
                    "status": latest_run["status"],
                    "metric_summary": {k: v for k, v in latest_run["metric_summary"].items() if k not in {"observed_vs_predicted", "prediction_probabilities"}},
                    "warnings": latest_run["warnings"],
                    "created_at": latest_run["created_at"]
                }
        except:
            pass
            
        from app.services.admet_domain_service import get_domain_summary_by_model
        try:
            domain_sum = get_domain_summary_by_model(model_id)
            if domain_sum:
                active_model_domain_summary = {
                    "status": "available",
                    "training_record_count": domain_sum["training_record_count"],
                    "task_type": domain_sum["task_type"],
                    "dataset_name": domain_sum["dataset_name"],
                    "warnings": domain_sum["warnings"]
                }
        except:
            pass
            
    return {
        "available_models": [model.model_id for model in status["available_models"]],
        "unavailable_models": [model.model_id for model in status["unavailable_models"]],
        "limitations": status["limitations"],
        "active_trained_model": active_trained if active_trained.get("status") in {"available", "active"} else None,
        "active_model_external_validation": external_val_summary,
        "active_model_domain_summary": active_model_domain_summary
    }




def _project_from_row(row, item_count: int = 0, export_count: int = 0, latest_activity: str | None = None) -> ProjectSummary:
    return ProjectSummary(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        disease_area=row["disease_area"],
        target_name=row["target_name"],
        project_type=row["project_type"],
        status=row["status"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        attached_item_count=item_count,
        export_count=export_count,
        latest_activity=latest_activity or row["updated_at"],
        model_status_summary=_model_summary(),
        warnings=[] if row["status"] != "archived" else ["Project is archived."],
        limitations=PROJECT_LIMITATIONS,
    )


def _item_from_row(row) -> ProjectItem:
    return ProjectItem(
        id=row["id"],
        project_id=row["project_id"],
        item_type=row["item_type"],
        item_id=row["item_id"],
        item_title=row["item_title"],
        metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
        created_at=row["created_at"],
    )


def create_project(payload: ProjectCreateRequest) -> ProjectSummary:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO projects (title, description, disease_area, target_name, project_type, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.title,
                payload.description,
                payload.disease_area,
                payload.target_name,
                payload.project_type,
                payload.status,
                payload.notes,
            ),
        )
        project_id = int(cursor.lastrowid)
        row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _project_from_row(row)


def _project_row(project_id: int):
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return row


def list_projects() -> list[ProjectSummary]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM projects ORDER BY datetime(updated_at) DESC, id DESC").fetchall()
        summaries = []
        for row in rows:
            item_count = connection.execute("SELECT COUNT(*) AS count FROM project_items WHERE project_id = ?", (row["id"],)).fetchone()["count"]
            export_count = connection.execute("SELECT COUNT(*) AS count FROM project_exports WHERE project_id = ?", (row["id"],)).fetchone()["count"]
            latest = connection.execute(
                """
                SELECT MAX(activity) AS latest FROM (
                    SELECT updated_at AS activity FROM projects WHERE id = ?
                    UNION ALL
                    SELECT created_at AS activity FROM project_items WHERE project_id = ?
                    UNION ALL
                    SELECT created_at AS activity FROM project_exports WHERE project_id = ?
                )
                """,
                (row["id"], row["id"], row["id"]),
            ).fetchone()["latest"]
            summaries.append(_project_from_row(row, item_count, export_count, latest))
    return summaries


def active_project_options() -> list[ProjectActiveOption]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, project_type, status, disease_area, target_name, updated_at
            FROM projects
            WHERE status != 'archived'
            ORDER BY datetime(updated_at) DESC, id DESC
            """
        ).fetchall()
    return [
        ProjectActiveOption(
            id=row["id"],
            title=row["title"],
            project_type=row["project_type"],
            status=row["status"],
            disease_area=row["disease_area"],
            target_name=row["target_name"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


def get_project(project_id: int) -> ProjectDetail:
    row = _project_row(project_id)
    init_db()
    with get_connection() as connection:
        item_rows = connection.execute("SELECT * FROM project_items WHERE project_id = ? ORDER BY datetime(created_at) DESC, id DESC", (project_id,)).fetchall()
        export_rows = connection.execute("SELECT * FROM project_exports WHERE project_id = ? ORDER BY datetime(created_at) DESC, id DESC", (project_id,)).fetchall()
        item_count = len(item_rows)
        export_count = len(export_rows)
        latest = connection.execute(
            """
            SELECT MAX(activity) AS latest FROM (
                SELECT updated_at AS activity FROM projects WHERE id = ?
                UNION ALL
                SELECT created_at AS activity FROM project_items WHERE project_id = ?
                UNION ALL
                SELECT created_at AS activity FROM project_exports WHERE project_id = ?
            )
            """,
            (project_id, project_id, project_id),
        ).fetchone()["latest"]
    summary = _project_from_row(row, item_count, export_count, latest)
    return ProjectDetail(
        **summary.model_dump(),
        items=[_item_from_row(item) for item in item_rows],
        exports=[dict(item) for item in export_rows],
    )


def update_project(project_id: int, payload: ProjectUpdateRequest) -> ProjectSummary:
    _project_row(project_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return get_project(project_id)
    allowed = ["title", "description", "disease_area", "target_name", "project_type", "status", "notes"]
    assignments = [f"{key} = ?" for key in allowed if key in updates]
    values = [updates[key] for key in allowed if key in updates]
    values.append(project_id)
    init_db()
    with get_connection() as connection:
        connection.execute(
            f"UPDATE projects SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )
        row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _project_from_row(row)


def archive_project(project_id: int) -> ProjectSummary:
    return update_project(project_id, ProjectUpdateRequest(status="archived"))


def attach_project_item(project_id: int, payload: ProjectAttachRequest) -> ProjectItem:
    _project_row(project_id)
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO project_items (project_id, item_type, item_id, item_title, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, payload.item_type, payload.item_id, payload.item_title, json.dumps(payload.metadata)),
        )
        connection.execute("UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
        row = connection.execute("SELECT * FROM project_items WHERE id = ?", (int(cursor.lastrowid),)).fetchone()
    return _item_from_row(row)


def project_summary(project_id: int) -> ProjectSummary:
    detail = get_project(project_id)
    return ProjectSummary(**detail.model_dump(exclude={"items", "exports"}))


def link_project_export(project_id: int, export_id: int, filename: str) -> None:
    _project_row(project_id)
    init_db()
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO project_exports (project_id, export_id, filename) VALUES (?, ?, ?)",
            (project_id, export_id, filename),
        )
        connection.execute("UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))


MATRIX_HEADERS = [
    "candidate_name",
    "compound_id",
    "source_id",
    "source_workflow",
    "target_name",
    "disease_area",
    "molecular_weight",
    "logp",
    "tpsa",
    "lipinski_status",
    "veber_status",
    "admet_risk_summary",
    "evidence_level",
    "evidence_score",
    "model_prediction_status",
    "decision_label",
    "decision_reason",
    "missing_data_warnings",
]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _json_loads(value: str | None) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


def _coalesce(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        current: Any = data
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                current = None
                break
        if current not in (None, "", [], {}):
            return current
    return None


def _numeric(value: Any) -> float | str | None:
    if value in (None, ""):
        return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return str(value)


def _status_from_bool(value: Any) -> str:
    if isinstance(value, bool):
        return "Pass" if value else "Fail"
    if isinstance(value, dict):
        for key in ("status", "label", "result"):
            if value.get(key):
                return str(value[key])
        if "passed" in value:
            return _status_from_bool(value["passed"])
    if value in (None, ""):
        return "not available"
    return str(value)


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if value in (None, ""):
        return []
    return [str(value)]


def _model_status_text(value: Any) -> str:
    if isinstance(value, dict):
        if value.get("status"):
            return str(value["status"])
        parts = []
        if value.get("available_models"):
            parts.append(f"available: {', '.join(str(item) for item in value['available_models'])}")
        if value.get("unavailable_models"):
            parts.append(f"unavailable: {', '.join(str(item) for item in value['unavailable_models'])}")
        return "; ".join(parts) or "not available"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "not available"
    return str(value) if value not in (None, "") else "not available"


def _screening_record(item_id: str) -> dict[str, Any] | None:
    try:
        record_id = int(item_id)
    except (TypeError, ValueError):
        return None
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM screening_history WHERE id = ?", (record_id,)).fetchone()
    if not row:
        return None
    report = _json_loads(row["report_json"])
    identity = _as_dict(report.get("compound_identity"))
    descriptors = _as_dict(report.get("descriptors"))
    drug_likeness = _as_dict(report.get("drug_likeness"))
    admet = _as_dict(report.get("admet_toxicity_v1"))
    overall = _as_dict(admet.get("overall_concern_score"))
    recommendation = _as_dict(report.get("go_no_go_recommendation"))
    return {
        "candidate_name": identity.get("compound_name") or row["compound_name"],
        "compound_id": identity.get("pubchem_cid") or row["pubchem_cid"],
        "source_id": row["id"],
        "source_workflow": "screening",
        "canonical_smiles": identity.get("canonical_smiles") or row["canonical_smiles"],
        "molecular_weight": descriptors.get("molecular_weight"),
        "logp": descriptors.get("logp"),
        "tpsa": descriptors.get("tpsa"),
        "lipinski_status": drug_likeness.get("lipinski_status") or drug_likeness.get("lipinski_rule_of_5"),
        "veber_status": drug_likeness.get("veber_status") or drug_likeness.get("veber_rule"),
        "admet_risk_summary": overall.get("concern_level") or _coalesce(admet, "absorption.absorption_risk"),
        "model_prediction_status": _coalesce(report, "prediction_model_status.summary", "model_status_summary.status"),
        "decision": recommendation.get("decision") or row["decision"],
        "decision_reason": recommendation.get("rationale"),
        "evidence_level": "not evaluated",
    }


def _batch_library_records(item_id: str) -> list[dict[str, Any]]:
    try:
        record_id = int(item_id)
    except (TypeError, ValueError):
        return []
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM batch_library_runs WHERE id = ?", (record_id,)).fetchone()
    if not row:
        return []
    payload = _json_loads(row["result_payload_json"])
    records = []
    for result in _as_list(payload.get("results")):
        result = _as_dict(result)
        descriptors = _as_dict(result.get("descriptors"))
        admet = _as_dict(result.get("admet_toxicity_v1"))
        overall = _as_dict(admet.get("overall_concern_score"))
        records.append(
            {
                **result,
                "candidate_name": result.get("compound_name") or result.get("name"),
                "compound_id": result.get("compound_id"),
                "source_id": result.get("row_number") or result.get("id"),
                "source_workflow": "batch_upload",
                "molecular_weight": descriptors.get("molecular_weight") or result.get("molecular_weight"),
                "logp": descriptors.get("logp") or result.get("logp"),
                "tpsa": descriptors.get("tpsa") or result.get("tpsa"),
                "admet_risk_summary": overall.get("concern_level") or result.get("concern_level"),
                "evidence_level": "not evaluated",
            }
        )
    return records


def _batch_screening_records(item_id: str, workflow: str) -> list[dict[str, Any]]:
    try:
        record_id = int(item_id)
    except (TypeError, ValueError):
        return []
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM batch_screening_runs WHERE id = ?", (record_id,)).fetchone()
    if not row:
        return []
    payload = _json_loads(row["summary_json"])
    return [
        {**_as_dict(result), "source_workflow": workflow, "source_id": _coalesce(_as_dict(result), "molecule_chembl_id", "pubchem_cid", "id")}
        for result in _as_list(payload.get("results"))
    ]


def _project_report_records(item_id: str) -> list[dict[str, Any]]:
    try:
        record_id = int(item_id)
    except (TypeError, ValueError):
        return []
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM project_reports WHERE id = ?", (record_id,)).fetchone()
    if not row:
        return []
    payload = _json_loads(row["report_payload_json"])
    batch = _as_dict(payload.get("batch_screening_results"))
    rows = _as_list(batch.get("comparison_table")) or _as_list(batch.get("results"))
    return [{**_as_dict(result), "source_workflow": "project_report", "source_id": _coalesce(_as_dict(result), "molecule_chembl_id", "compound_id", "id")} for result in rows]


def _records_for_item(item: ProjectItem) -> list[dict[str, Any]]:
    metadata = dict(item.metadata or {})
    metadata.setdefault("source_workflow", item.item_type)
    metadata.setdefault("source_id", item.item_id)
    metadata.setdefault("candidate_name", item.item_title)
    if item.item_type == "screening":
        record = _screening_record(item.item_id)
        return [{**metadata, **record}] if record else [metadata]
    if item.item_type == "batch_upload":
        records = _batch_library_records(item.item_id)
        return records or [metadata]
    if item.item_type in {"drug_finder_batch", "similarity_batch"}:
        records = _batch_screening_records(item.item_id, item.item_type)
        return records or [metadata]
    if item.item_type == "project_report":
        records = _project_report_records(item.item_id)
        return records or [metadata]
    if item.item_type == "admet_lead_prioritization":
        top_records = _as_list(metadata.get("top_candidates"))
        return [{**_as_dict(record), "source_workflow": item.item_type, "source_id": item.item_id} for record in top_records] or [metadata]
    if item.item_type == "experimental_validation_plan":
        plan_records = _as_list(metadata.get("candidate_plans"))
        return [{**_as_dict(record), "source_workflow": item.item_type, "source_id": item.item_id} for record in plan_records] or [metadata]
    return [metadata]


def _extract_row(data: dict[str, Any], item: ProjectItem, detail: ProjectDetail) -> CandidateDecisionMatrixRow:
    descriptors = _as_dict(data.get("descriptors")) or _as_dict(data.get("descriptor_summary"))
    drug_likeness = _as_dict(data.get("drug_likeness")) or _as_dict(data.get("drug_likeness_preview"))
    admet = _as_dict(data.get("admet_toxicity_v1")) or _as_dict(data.get("admet_tox_summary"))
    admet_overall = _as_dict(admet.get("overall_concern_score"))
    evidence = _as_dict(data.get("evidence")) or _as_dict(data.get("evidence_quality"))
    model_status = _as_dict(data.get("model_status_summary")) or _as_dict(data.get("model_status"))

    row_values = {
        "candidate_name": _coalesce(data, "candidate_name", "compound_name", "name", "molecule_name") or item.item_title or "not available",
        "compound_id": _coalesce(data, "compound_id", "molecule_chembl_id", "pubchem_cid"),
        "source_id": _coalesce(data, "source_id", "id") or item.item_id,
        "source_workflow": _coalesce(data, "source_workflow") or item.item_type,
        "target_name": _coalesce(data, "target_name", "target", "selected_target_name") or detail.target_name,
        "disease_area": _coalesce(data, "disease_area", "disease_name") or detail.disease_area,
        "molecular_weight": _numeric(_coalesce(data, "molecular_weight", "mw", "descriptor_summary.molecular_weight") or descriptors.get("molecular_weight")),
        "logp": _numeric(_coalesce(data, "logp", "descriptor_summary.logp") or descriptors.get("logp")),
        "tpsa": _numeric(_coalesce(data, "tpsa", "descriptor_summary.tpsa") or descriptors.get("tpsa")),
        "lipinski_status": _status_from_bool(_coalesce(data, "lipinski_status", "lipinski", "lipinski_pass") or drug_likeness.get("lipinski_status") or drug_likeness.get("lipinski_pass")),
        "veber_status": _status_from_bool(_coalesce(data, "veber_status", "veber", "veber_pass") or drug_likeness.get("veber_status") or drug_likeness.get("veber_pass")),
        "admet_risk_summary": _coalesce(data, "admet_risk_summary", "concern_level", "developability_risk") or admet_overall.get("concern_level") or "not evaluated",
        "evidence_level": _coalesce(data, "evidence_level", "evidence.evidence_level", "explainability_evidence_strength") or evidence.get("evidence_level") or "not evaluated",
        "evidence_score": _coalesce(data, "evidence_score", "evidence.evidence_score") or evidence.get("evidence_score"),
        "model_prediction_status": _model_status_text(_coalesce(data, "model_prediction_status", "prediction_source", "model_status") or model_status.get("status") or model_status),
    }
    missing = []
    for label, key in [
        ("molecular weight", "molecular_weight"),
        ("LogP", "logp"),
        ("TPSA", "tpsa"),
        ("Lipinski status", "lipinski_status"),
        ("ADMET/Tox risk", "admet_risk_summary"),
        ("evidence level", "evidence_level"),
        ("model prediction status", "model_prediction_status"),
    ]:
        value = row_values[key]
        if value in (None, "", "not available", "not evaluated"):
            missing.append(f"{label} is {value or 'not available'}.")
    missing.extend(_string_list(data.get("missing_data_warnings")))
    label, reason = _decision_for_row(row_values, _coalesce(data, "decision", "decision_label", "priority_label"), missing)
    return CandidateDecisionMatrixRow(**row_values, decision_label=label, decision_reason=reason, missing_data_warnings=missing)


def _decision_for_row(values: dict[str, Any], raw_decision: Any, missing: list[str]) -> tuple[str, str]:
    decision_text = str(raw_decision or "").lower()
    admet = str(values.get("admet_risk_summary") or "").lower()
    evidence = str(values.get("evidence_level") or "").lower()
    lipinski = str(values.get("lipinski_status") or "").lower()
    veber = str(values.get("veber_status") or "").lower()
    if len(missing) >= 4:
        return "Insufficient evidence", "Key descriptor, ADMET/Tox, evidence, or model-status fields are missing from the attached record."
    if "do not proceed" in decision_text or "high" in admet or "fail" in lipinski or "fail" in veber:
        return "Not recommended based on available data", "Available project data contains high risk, failed drug-likeness criteria, or a negative screening decision."
    if evidence in {"not evaluated", "uncertain", "weak"} or missing:
        return "Review with caution", "Some useful values are available, but evidence or model-status data is incomplete and needs review."
    if "proceed" in decision_text and evidence in {"strong", "moderate"} and "low" in admet:
        return "Strong follow-up candidate", "Available data shows a proceed-style decision, lower ADMET/Tox concern, and moderate or strong evidence metadata."
    if "proceed" in decision_text or "medium" in admet or evidence in {"strong", "moderate"}:
        return "Reasonable follow-up candidate", "Available data supports follow-up, but this remains a computational decision-support summary."
    return "Insufficient evidence", "The attached record does not contain enough candidate-level data for prioritization."


def _candidate_matrix(detail: ProjectDetail) -> list[CandidateDecisionMatrixRow]:
    rows: list[CandidateDecisionMatrixRow] = []
    for item in detail.items:
        for record in _records_for_item(item):
            rows.append(_extract_row(_as_dict(record), item, detail))
    return rows


def project_decision_matrix_csv(project_id: int) -> str:
    dashboard = project_dashboard(project_id)
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=MATRIX_HEADERS, extrasaction="ignore")
    writer.writeheader()
    for row in dashboard.candidate_matrix:
        data = row.model_dump()
        data["missing_data_warnings"] = " | ".join(data.get("missing_data_warnings", []))
        writer.writerow(data)
    return output.getvalue()


def project_recommendations_markdown(project_id: int) -> str:
    dashboard = project_dashboard(project_id)
    steps = "\n".join(f"- {item}" for item in dashboard.recommended_next_steps)
    warnings = "\n".join(f"- {item}" for item in dashboard.warnings) or "- None"
    return f"""# Project Recommendations

Project: {dashboard.project.title}

These recommendations are based only on records attached to this local DrugScreen360 project.

## Next Steps

{steps}

## Warnings

{warnings}

## Scientific Scope

This is not a clinical recommendation. It does not prove safety, efficacy, regulatory approval, or market readiness. Laboratory validation and expert review are required.
"""


def project_dashboard(project_id: int) -> ProjectDashboardResponse:
    detail = get_project(project_id)
    item_counts: dict[str, int] = {}
    for item in detail.items:
        item_counts[item.item_type] = item_counts.get(item.item_type, 0) + 1
    matrix = _candidate_matrix(detail)
    risk_counts: dict[str, int] = {}
    evidence_counts: dict[str, int] = {}
    decision_counts: dict[str, int] = {}
    high_risk_candidates = []
    insufficient = 0
    for row in matrix:
        risk = str(row.admet_risk_summary or "not evaluated")
        evidence = row.evidence_level or "not evaluated"
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
        evidence_counts[evidence] = evidence_counts.get(evidence, 0) + 1
        decision_counts[row.decision_label] = decision_counts.get(row.decision_label, 0) + 1
        if "high" in risk.lower() or row.decision_label == "Not recommended based on available data":
            high_risk_candidates.append(row.candidate_name)
        if row.decision_label == "Insufficient evidence":
            insufficient += 1
    warnings = list(detail.warnings)
    if not detail.items:
        warnings.append("No records are attached to this project yet.")
    if detail.items and not matrix:
        warnings.append("Attached records did not contain candidate-level data for a decision matrix.")
    if insufficient:
        warnings.append(f"{insufficient} candidate row(s) have insufficient evidence or missing project metadata.")
    recommended = []
    if not detail.items:
        recommended.append("Attach screening, batch, project report, or benchmark records to build a useful dashboard.")
    if matrix:
        recommended.append("Review rows labelled Insufficient evidence before using them for follow-up planning.")
        recommended.append("Prioritize laboratory validation for any candidate kept for further study.")
    else:
        recommended.append("Run or attach candidate screening results with descriptors, ADMET/Tox summaries, and decisions.")
    if high_risk_candidates:
        recommended.append("Review high-risk candidates carefully before considering additional experimental work.")
    if item_counts.get("experimental_validation_plan"):
        recommended.append("Review the latest experimental validation plan before scheduling wet-lab work.")
    recommended.append("Confirm all public database and rule-based outputs with qualified expert review.")
    return ProjectDashboardResponse(
        project=detail,
        summary_cards={
            "attached_items": detail.attached_item_count,
            "candidate_rows": len(matrix),
            "insufficient_evidence_rows": insufficient,
            "exports": detail.export_count,
            "latest_activity": detail.latest_activity,
        },
        item_counts=item_counts,
        candidate_matrix=matrix,
        model_status_summary=detail.model_status_summary,
        risk_summary={
            "admet_risk_counts": risk_counts,
            "evidence_level_counts": evidence_counts,
            "decision_label_counts": decision_counts,
            "high_risk_candidates": high_risk_candidates,
        },
        warnings=warnings,
        limitations=[
            *PROJECT_LIMITATIONS,
            "The candidate decision matrix uses available saved data only and does not infer missing values.",
            "Decision labels are conservative project-review labels, not clinical recommendations.",
        ],
        recommended_next_steps=recommended,
    )
