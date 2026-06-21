from fastapi import APIRouter, Response

from app.models.validation_planner_models import ExperimentalValidationPlanRequest, ExperimentalValidationPlanResponse
from app.services.validation_planner_service import (
    create_validation_plan,
    get_validation_plan,
    list_validation_plans,
    validation_plan_csv,
    validation_plan_report_json,
)

router = APIRouter(prefix="/validation-planner", tags=["validation-planner"])


@router.post("/create", response_model=ExperimentalValidationPlanResponse)
def create_validation_plan_endpoint(payload: ExperimentalValidationPlanRequest):
    return create_validation_plan(payload)


@router.get("/plans")
def list_validation_plans_endpoint():
    return list_validation_plans()


@router.get("/plans/{plan_id}", response_model=ExperimentalValidationPlanResponse)
def get_validation_plan_endpoint(plan_id: int):
    return get_validation_plan(plan_id)


@router.get("/plans/{plan_id}/report.json")
def validation_plan_report_json_endpoint(plan_id: int):
    return validation_plan_report_json(plan_id)


@router.get("/plans/{plan_id}/csv")
def validation_plan_csv_endpoint(plan_id: int):
    return Response(
        validation_plan_csv(plan_id),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-validation-plan-{plan_id}.csv"'},
    )
