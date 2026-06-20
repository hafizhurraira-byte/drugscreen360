from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.research_export_models import ResearchExportCreateResponse, ResearchExportListItem, ResearchExportRequest
from app.services.research_export_service import create_research_export, get_research_export_path, list_research_exports

router = APIRouter(prefix="/research-export", tags=["research-export"])


@router.post("/create", response_model=ResearchExportCreateResponse)
def create_research_export_endpoint(payload: ResearchExportRequest):
    return create_research_export(payload)


@router.get("/list", response_model=list[ResearchExportListItem])
def list_research_exports_endpoint():
    return list_research_exports()


@router.get("/{export_id}/download")
def download_research_export(export_id: int):
    path = get_research_export_path(export_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Research export package not found.")
    return FileResponse(path, media_type="application/zip", filename=path.name)
