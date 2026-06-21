from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.models.final_report_models import FinalProjectReportRequest, FinalProjectReportResponse
from app.services.final_report_service import (
    create_final_project_report,
    final_report_file_path,
    get_final_project_report,
    list_final_project_reports,
)

router = APIRouter(prefix="/final-report", tags=["final-report"])


@router.post("/create", response_model=FinalProjectReportResponse)
def create_final_report_endpoint(payload: FinalProjectReportRequest):
    return create_final_project_report(payload)


@router.get("/reports")
def list_final_reports_endpoint():
    return list_final_project_reports()


@router.get("/reports/{report_id}", response_model=FinalProjectReportResponse)
def get_final_report_endpoint(report_id: int):
    return get_final_project_report(report_id)


@router.get("/reports/{report_id}/json")
def final_report_json_endpoint(report_id: int):
    path = final_report_file_path(report_id, "json")
    return FileResponse(path, media_type="application/json", filename=path.name)


@router.get("/reports/{report_id}/pdf")
def final_report_pdf_endpoint(report_id: int):
    path = final_report_file_path(report_id, "pdf")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.get("/reports/{report_id}/docx")
def final_report_docx_endpoint(report_id: int):
    path = final_report_file_path(report_id, "docx")
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=path.name)
