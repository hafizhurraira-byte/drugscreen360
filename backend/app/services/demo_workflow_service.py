import csv
import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.models.admet_lead_models import LeadCandidateInput, LeadPrioritizationRequest
from app.models.demo_workflow_models import (
    DEMO_SCIENTIFIC_NOTICE,
    DemoProjectCreateResponse,
    DemoWorkflowRequest,
    DemoWorkflowRunResponse,
    DemoWorkflowStatusResponse,
)
from app.models.experimental_results_models import (
    ExperimentalFeedbackCompareRequest,
    ExperimentalResultCreateRequest,
    ExperimentalResultInput,
)
from app.models.final_report_models import FinalProjectReportRequest
from app.models.project_workspace_models import ProjectAttachRequest, ProjectCreateRequest
from app.models.research_export_models import ResearchExportRequest
from app.models.validation_planner_models import ExperimentalValidationPlanRequest, ValidationCandidateInput
from app.services.admet_lead_service import prioritize_leads
from app.services.experimental_results_service import compare_experimental_feedback, create_experimental_results
from app.services.final_report_service import create_final_project_report
from app.services.project_workspace_service import attach_project_item, create_project, get_project
from app.services.research_export_service import create_research_export
from app.services.validation_planner_service import create_validation_plan

DEMO_DIR = Path(__file__).resolve().parents[1] / "demo_data"
DEMO_STEP_ORDER = [
    "create_project",
    "load_candidates",
    "run_screening_demo_evidence",
    "prioritize_leads",
    "generate_validation_plan",
    "add_demo_experimental_feedback",
    "generate_final_report",
    "create_research_export",
]


def _load_json(name: str) -> Any:
    return json.loads((DEMO_DIR / name).read_text(encoding="utf-8"))


def _load_demo_results() -> list[dict[str, str]]:
    with (DEMO_DIR / "demo_experimental_results.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _demo_metadata(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "demo_mode": True,
        "data_source": "demo",
        "demo_label": DEMO_SCIENTIFIC_NOTICE,
        "scientific_notice": DEMO_SCIENTIFIC_NOTICE,
        **(extra or {}),
    }


def _step(step_id: str, label: str, status: str, artifact: dict[str, Any] | None = None, warning: str | None = None) -> dict[str, Any]:
    data = {"step_id": step_id, "label": label, "status": status}
    if artifact:
        data["artifact"] = artifact
    if warning:
        data["warning"] = warning
    return data


def _candidate_inputs(limit: int = 5) -> list[LeadCandidateInput]:
    candidates = _load_json("demo_candidates.json")[:limit]
    return [
        LeadCandidateInput(
            compound_name=item["compound_name"],
            smiles=item["smiles"],
            compound_id=item["compound_id"],
            metadata=_demo_metadata({"source_workflow": "guided_demo_workflow"}),
        )
        for item in candidates
    ]


def _validation_inputs(candidates: list[LeadCandidateInput]) -> list[ValidationCandidateInput]:
    return [
        ValidationCandidateInput(
            compound_name=item.compound_name,
            smiles=item.smiles,
            compound_id=item.compound_id,
            priority_label="demo_candidate_for_review",
            evidence_strength="demo_only",
            warnings=[DEMO_SCIENTIFIC_NOTICE],
            metadata=_demo_metadata({"source_workflow": "guided_demo_workflow"}),
        )
        for item in candidates
    ]


def _create_base_project(title: str) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    project = create_project(
        ProjectCreateRequest(
            title=title,
            description="Guided demo workspace created by DrugScreen360.",
            disease_area="Demo oncology/toxicity workflow",
            target_name="Demo target context",
            project_type="general_research",
            status="active",
            notes=f"{DEMO_SCIENTIFIC_NOTICE} Demo records should not be interpreted as real experimental evidence.",
        )
    )
    created_items = []
    candidates = _load_json("demo_candidates.json")
    for item in candidates:
        attached = attach_project_item(
            project.id,
            ProjectAttachRequest(
                item_type="demo_candidate",
                item_id=item["compound_id"],
                item_title=item["compound_name"],
                metadata=_demo_metadata(
                    {
                        "workflow_type": "guided_demo_workflow",
                        "candidate_name": item["compound_name"],
                        "compound_id": item["compound_id"],
                        "smiles": item["smiles"],
                        "decision": "demo_only_not_a_scientific_decision",
                        "evidence_level": "demo_only",
                        "model_prediction_status": "not evaluated in demo candidate seed",
                    }
                ),
            ),
        )
        created_items.append(attached.model_dump())
    steps = [
        _step("create_project", "Create demo project", "completed", {"project_id": project.id}),
        _step("load_candidates", "Load demo candidates", "completed", {"candidate_count": len(candidates)}),
        _step(
            "run_screening_demo_evidence",
            "Attach demo candidate evidence",
            "completed",
            {"item_count": len(created_items)},
            DEMO_SCIENTIFIC_NOTICE,
        ),
    ]
    return project.id, created_items, steps


def create_demo_project() -> DemoProjectCreateResponse:
    project_id, created_items, steps = _create_base_project("DrugScreen360 Demo Project")
    return DemoProjectCreateResponse(
        demo_project_id=project_id,
        project_title="DrugScreen360 Demo Project",
        created_items=created_items,
        workflow_steps=steps,
        warnings=[DEMO_SCIENTIFIC_NOTICE],
    )


def run_demo_workflow(payload: DemoWorkflowRequest) -> DemoWorkflowRunResponse:
    project_id, created_items, steps = _create_base_project(payload.project_title)
    warnings = [DEMO_SCIENTIFIC_NOTICE]
    final_report_id = None
    research_export_id = None
    download_links: dict[str, str] = {}
    candidates = _candidate_inputs()

    lead_run_id = None
    if payload.include_lead_prioritization:
        try:
            lead = prioritize_leads(
                LeadPrioritizationRequest(
                    source_type="manual",
                    project_id=project_id,
                    scoring_profile="balanced_admet",
                    candidates=candidates,
                    include_trained_model=False,
                    include_domain=False,
                    include_explainability=False,
                )
            )
            lead_run_id = lead.run_id
            created_items.append({"item_type": "admet_lead_prioritization", "item_id": str(lead.run_id), "demo_mode": True})
            steps.append(_step("prioritize_leads", "Prioritize demo leads", "completed", {"run_id": lead.run_id}))
        except Exception as exc:
            message = f"Demo lead prioritization could not be completed: {exc}"
            warnings.append(message)
            steps.append(_step("prioritize_leads", "Prioritize demo leads", "warning", warning=message))

    validation_plan_id = None
    if payload.include_validation_plan:
        try:
            plan = create_validation_plan(
                ExperimentalValidationPlanRequest(
                    source_type="manual",
                    project_id=project_id,
                    plan_title="Guided Demo Validation Plan",
                    candidates=_validation_inputs(candidates[:3]),
                    include_toxicity_assays=True,
                    include_adme_assays=True,
                    include_target_assays=True,
                    include_controls=True,
                )
            )
            validation_plan_id = plan.plan_id
            created_items.append({"item_type": "experimental_validation_plan", "item_id": str(plan.plan_id), "demo_mode": True})
            steps.append(_step("generate_validation_plan", "Generate demo validation plan", "completed", {"plan_id": plan.plan_id}))
        except Exception as exc:
            message = f"Demo validation plan could not be completed: {exc}"
            warnings.append(message)
            steps.append(_step("generate_validation_plan", "Generate demo validation plan", "warning", warning=message))

    result_batch_id = None
    feedback_id = None
    if payload.include_experimental_feedback:
        try:
            result_rows = _load_demo_results()
            result_payload = ExperimentalResultCreateRequest(
                project_id=project_id,
                validation_plan_id=validation_plan_id,
                source_type="demo_synthetic",
                results=[
                    ExperimentalResultInput(
                        compound_name=row.get("compound_name"),
                        smiles=row.get("smiles"),
                        assay_name=row.get("assay_name") or "Demo assay",
                        assay_category=row.get("assay_category") or "demo",
                        measured_value=row.get("measured_value") or None,
                        measurement_unit=row.get("measurement_unit") or None,
                        qualitative_result=row.get("qualitative_result") or "Demo-only result placeholder",
                        result_direction=row.get("result_direction") or "inconclusive",
                        replicate_count=int(row["replicate_count"]) if row.get("replicate_count") else None,
                        notes=f"{row.get('notes') or ''} {DEMO_SCIENTIFIC_NOTICE}".strip(),
                        source_type="demo_synthetic",
                    )
                    for row in result_rows
                ],
            )
            batch = create_experimental_results(result_payload)
            result_batch_id = batch.result_batch_id
            feedback = compare_experimental_feedback(
                ExperimentalFeedbackCompareRequest(
                    project_id=project_id,
                    result_batch_id=result_batch_id,
                    lead_prioritization_run_id=lead_run_id,
                    validation_plan_id=validation_plan_id,
                )
            )
            feedback_id = feedback.feedback_id
            created_items.extend(
                [
                    {"item_type": "experimental_result_batch", "item_id": str(result_batch_id), "demo_mode": True},
                    {"item_type": "experimental_feedback_summary", "item_id": str(feedback_id), "demo_mode": True},
                ]
            )
            steps.append(
                _step(
                    "add_demo_experimental_feedback",
                    "Add demo experimental feedback",
                    "completed",
                    {"result_batch_id": result_batch_id, "feedback_id": feedback_id},
                    DEMO_SCIENTIFIC_NOTICE,
                )
            )
        except Exception as exc:
            message = f"Demo experimental feedback could not be completed: {exc}"
            warnings.append(message)
            steps.append(_step("add_demo_experimental_feedback", "Add demo experimental feedback", "warning", warning=message))

    if payload.include_final_report:
        try:
            final_report = create_final_project_report(
                FinalProjectReportRequest(
                    project_id=project_id,
                    report_title=f"{payload.project_title} - Final Demo Report",
                    include_screening=payload.include_screening,
                    include_admet_prediction=True,
                    include_model_training=True,
                    include_external_validation=True,
                    include_applicability_domain=True,
                    include_explainability=True,
                    include_lead_prioritization=payload.include_lead_prioritization,
                    include_validation_planner=payload.include_validation_plan,
                    include_experimental_feedback=payload.include_experimental_feedback,
                    formats=["json", "pdf", "docx"],
                )
            )
            final_report_id = final_report.report_id
            created_items.append({"item_type": "final_project_report", "item_id": str(final_report_id), "demo_mode": True})
            download_links.update(final_report.generated_files)
            steps.append(_step("generate_final_report", "Generate demo final report", "completed", {"report_id": final_report_id}))
        except Exception as exc:
            message = f"Demo final report could not be completed: {exc}"
            warnings.append(message)
            steps.append(_step("generate_final_report", "Generate demo final report", "warning", warning=message))

    try:
        export = create_research_export(
            ResearchExportRequest(
                project_id=project_id,
                project_title=payload.project_title,
                notes=f"Guided demo export. {DEMO_SCIENTIFIC_NOTICE}",
                include_reports=False,
                include_cache_status=True,
                include_benchmark_runs=False,
                include_batch_runs=False,
                include_screening_history=False,
            )
        )
        research_export_id = export.export_id
        download_links["research_export_zip"] = export.download_url
        steps.append(_step("create_research_export", "Create demo research export", "completed", {"export_id": export.export_id}))
    except Exception as exc:
        message = f"Demo research export could not be completed: {exc}"
        warnings.append(message)
        steps.append(_step("create_research_export", "Create demo research export", "warning", warning=message))

    return DemoWorkflowRunResponse(
        demo_project_id=project_id,
        project_title=payload.project_title,
        created_items=created_items,
        workflow_steps=steps,
        final_report_id=final_report_id,
        research_export_id=research_export_id,
        research_export_available=bool(research_export_id),
        download_links=download_links,
        warnings=warnings,
    )


def demo_workflow_status(project_id: int) -> DemoWorkflowStatusResponse:
    try:
        project = get_project(project_id)
    except HTTPException:
        raise
    completed_steps = {"create_project"} if project else set()
    artifacts = []
    warnings = []
    demo_items = []
    for item in project.items:
        metadata = item.metadata or {}
        if metadata.get("demo_mode") or metadata.get("data_source") == "demo" or "demo" in item.item_type:
            demo_items.append(item)
        if item.item_type == "demo_candidate":
            completed_steps.add("load_candidates")
            completed_steps.add("run_screening_demo_evidence")
        if item.item_type == "admet_lead_prioritization":
            completed_steps.add("prioritize_leads")
        if item.item_type == "experimental_validation_plan":
            completed_steps.add("generate_validation_plan")
        if item.item_type in {"experimental_result_batch", "experimental_feedback_summary"}:
            completed_steps.add("add_demo_experimental_feedback")
        if item.item_type == "final_project_report":
            completed_steps.add("generate_final_report")
        artifacts.append(
            {
                "item_type": item.item_type,
                "item_id": item.item_id,
                "item_title": item.item_title,
                "demo_mode": bool(metadata.get("demo_mode") or "demo" in item.item_type),
            }
        )
    if project.exports:
        completed_steps.add("create_research_export")
    if not demo_items:
        warnings.append("Project exists, but no guided-demo-labelled items were found.")
    missing = [step for step in DEMO_STEP_ORDER if step not in completed_steps]
    links = {}
    for item in project.items:
        if item.item_type == "final_project_report":
            links["final_report_json"] = f"/api/final-report/reports/{item.item_id}/json"
            links["final_report_pdf"] = f"/api/final-report/reports/{item.item_id}/pdf"
            links["final_report_docx"] = f"/api/final-report/reports/{item.item_id}/docx"
    if project.exports:
        latest_export = project.exports[0]
        links["research_export_zip"] = f"/api/research-export/{latest_export['export_id']}/download"
    steps = [
        _step(step, step.replace("_", " ").title(), "completed" if step in completed_steps else "missing")
        for step in DEMO_STEP_ORDER
    ]
    return DemoWorkflowStatusResponse(
        project_id=project_id,
        workflow_steps=steps,
        completed_steps=[step for step in DEMO_STEP_ORDER if step in completed_steps],
        generated_artifacts=artifacts,
        missing_steps=missing,
        download_links=links,
        warnings=warnings,
    )
