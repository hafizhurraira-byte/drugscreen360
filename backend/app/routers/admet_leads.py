from fastapi import APIRouter, Response

from app.models.admet_lead_models import LeadPrioritizationRequest, LeadPrioritizationRunSummary
from app.services.admet_lead_service import (
    get_lead_prioritization_run,
    lead_prioritization_csv,
    lead_prioritization_report_json,
    list_lead_prioritization_runs,
    prioritize_leads,
)

router = APIRouter(prefix="/admet-leads", tags=["admet-leads"])


@router.post("/prioritize", response_model=LeadPrioritizationRunSummary)
def prioritize_leads_endpoint(payload: LeadPrioritizationRequest):
    return prioritize_leads(payload)


@router.get("/runs")
def list_runs_endpoint():
    return list_lead_prioritization_runs()


@router.get("/runs/{run_id}", response_model=LeadPrioritizationRunSummary)
def get_run_endpoint(run_id: int):
    return get_lead_prioritization_run(run_id)


@router.get("/runs/{run_id}/csv")
def get_run_csv_endpoint(run_id: int):
    return Response(
        lead_prioritization_csv(run_id),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-lead-prioritization-{run_id}.csv"'},
    )


@router.get("/runs/{run_id}/report.json")
def get_run_json_endpoint(run_id: int):
    return lead_prioritization_report_json(run_id)
