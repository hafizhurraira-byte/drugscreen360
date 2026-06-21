from fastapi import APIRouter, HTTPException, Response
from typing import Any

from app.models.admet_validation_models import ExternalValidationRunRequest, ExternalValidationRunSummary
from app.services.admet_validation_service import (
    run_external_validation,
    get_external_validation_runs,
    get_external_validation_run_detail,
    get_external_validation_metrics_csv,
)

router = APIRouter(prefix="/admet-validation", tags=["admet-validation"])

@router.post("/external/run")
def start_external_validation(payload: ExternalValidationRunRequest, project_id: int | None = None):
    return run_external_validation(payload, project_id)

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

@router.get("/external/runs/{run_id}/metrics.csv")
def external_validation_run_metrics_csv(run_id: int):
    csv_text = get_external_validation_metrics_csv(run_id)
    return Response(content=csv_text, media_type="text/csv")

@router.get("/external/runs/{run_id}/report.json")
def external_validation_run_report_json(run_id: int):
    return get_external_validation_run_detail(run_id)
