from fastapi import APIRouter

from app.models.project_workspace_models import (
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
