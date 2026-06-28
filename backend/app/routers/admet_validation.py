from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from typing import Any

from app.models.admet_validation_models import ExternalValidationRunRequest, ExternalValidationRunSummary
from app.services.admet_validation_service import (
    run_external_validation,
    run_external_validation_upload,
    get_external_validation_runs,
    get_external_validation_run_detail,
    get_external_validation_records,
    get_external_validation_metrics_csv,
    get_external_validation_predictions_csv,
)

router = APIRouter(prefix="/admet-validation", tags=["admet-validation"])

@router.post("/external/run")
async def start_external_validation(request: Request, project_id: int | None = None):
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if not upload:
            raise HTTPException(status_code=422, detail="file is required.")
        return run_external_validation_upload(
            getattr(upload, "filename", None) or "external_validation.csv",
            await upload.read(),
            str(form.get("validation_dataset_name") or ""),
            str(form.get("smiles_column") or "smiles"),
            str(form.get("label_column") or ""),
            str(form.get("compound_name_column") or "") or None,
            str(form.get("task_name") or "") or None,
            str(form.get("model_id") or "") or None,
            str(form.get("positive_label") or "1"),
            str(form.get("negative_label") or "0"),
            float(form.get("decision_threshold") or 0.5),
            str(form.get("notes") or "") or None,
            int(form.get("project_id")) if form.get("project_id") else project_id,
        )
    return run_external_validation(ExternalValidationRunRequest(**(await request.json())), project_id)

@router.post("/external/run-upload")
async def start_external_validation_upload(
    file: UploadFile = File(...),
    validation_dataset_name: str = Form(...),
    smiles_column: str = Form("smiles"),
    label_column: str = Form(...),
    compound_name_column: str | None = Form(None),
    task_name: str | None = Form(None),
    model_id: str | None = Form(None),
    positive_label: str = Form("1"),
    negative_label: str = Form("0"),
    decision_threshold: float = Form(0.5),
    notes: str | None = Form(None),
    project_id: int | None = Form(None),
):
    return run_external_validation_upload(
        file.filename or "external_validation.csv",
        await file.read(),
        validation_dataset_name,
        smiles_column,
        label_column,
        compound_name_column,
        task_name,
        model_id,
        positive_label,
        negative_label,
        decision_threshold,
        notes,
        project_id,
    )

@router.get("/external/runs")
def list_external_validation_runs():
    return get_external_validation_runs()

@router.get("/external/runs/{run_id}")
def external_validation_run_detail(run_id: int):
    return get_external_validation_run_detail(run_id)

@router.get("/external/runs/{run_id}/summary")
def external_validation_run_summary(run_id: int):
    # Same payload is fine as it has everything needed by summary UI
    return get_external_validation_run_detail(run_id)

@router.get("/external/runs/{run_id}/records")
def external_validation_run_records(run_id: int):
    get_external_validation_run_detail(run_id)
    return get_external_validation_records(run_id)

@router.get("/external/runs/{run_id}/metrics.csv")
def external_validation_run_metrics_csv(run_id: int):
    csv_text = get_external_validation_metrics_csv(run_id)
    return Response(content=csv_text, media_type="text/csv")

@router.get("/external/runs/{run_id}/predictions.csv")
def external_validation_run_predictions_csv(run_id: int):
    csv_text = get_external_validation_predictions_csv(run_id)
    return Response(content=csv_text, media_type="text/csv")

@router.get("/external/runs/{run_id}/report.json")
def external_validation_run_report_json(run_id: int):
    return get_external_validation_run_detail(run_id)
