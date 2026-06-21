from fastapi import APIRouter

from app.models.demo_workflow_models import (
    DemoProjectCreateResponse,
    DemoWorkflowRequest,
    DemoWorkflowRunResponse,
    DemoWorkflowStatusResponse,
)
from app.services.demo_workflow_service import create_demo_project, demo_workflow_status, run_demo_workflow

router = APIRouter(prefix="/demo-workflow", tags=["demo-workflow"])


@router.post("/create-project", response_model=DemoProjectCreateResponse)
def create_demo_project_endpoint():
    return create_demo_project()


@router.post("/run", response_model=DemoWorkflowRunResponse)
def run_demo_workflow_endpoint(payload: DemoWorkflowRequest):
    return run_demo_workflow(payload)


@router.get("/status/{project_id}", response_model=DemoWorkflowStatusResponse)
def demo_workflow_status_endpoint(project_id: int):
    return demo_workflow_status(project_id)
