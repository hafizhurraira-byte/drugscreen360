from fastapi import APIRouter, Response

from app.models.project_workspace_models import (
    ProjectDashboardResponse,
    ProjectAttachRequest,
    ProjectCreateRequest,
    ProjectDetail,
    ProjectItem,
    ProjectSummary,
    ProjectUpdateRequest,
)
from app.services.project_workspace_service import (
    archive_project,
    attach_project_item,
    create_project,
    get_project,
    list_projects,
    project_dashboard,
    project_decision_matrix_csv,
    project_summary,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/create", response_model=ProjectSummary)
def create_project_endpoint(payload: ProjectCreateRequest):
    return create_project(payload)


@router.get("/list", response_model=list[ProjectSummary])
def list_projects_endpoint():
    return list_projects()


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project_endpoint(project_id: int):
    return get_project(project_id)


@router.put("/{project_id}", response_model=ProjectSummary)
def update_project_endpoint(project_id: int, payload: ProjectUpdateRequest):
    return update_project(project_id, payload)


@router.post("/{project_id}/attach-item", response_model=ProjectItem)
def attach_project_item_endpoint(project_id: int, payload: ProjectAttachRequest):
    return attach_project_item(project_id, payload)


@router.post("/{project_id}/archive", response_model=ProjectSummary)
def archive_project_endpoint(project_id: int):
    return archive_project(project_id)


@router.get("/{project_id}/summary", response_model=ProjectSummary)
def project_summary_endpoint(project_id: int):
    return project_summary(project_id)


@router.get("/{project_id}/dashboard", response_model=ProjectDashboardResponse)
def project_dashboard_endpoint(project_id: int):
    return project_dashboard(project_id)


@router.get("/{project_id}/decision-matrix.csv")
def project_decision_matrix_csv_endpoint(project_id: int):
    csv_text = project_decision_matrix_csv(project_id)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-project-{project_id}-decision-matrix.csv"'},
    )
