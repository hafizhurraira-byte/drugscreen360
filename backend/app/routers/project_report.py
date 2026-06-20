from io import BytesIO

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.models.project_report_models import ProjectReportCreateRequest, ProjectReportCreateResponse, ProjectReportStored
from app.services.project_reports import (
    build_project_csv,
    build_project_docx,
    build_project_pdf,
    build_project_summary,
    get_project_report,
    save_project_report,
)

router = APIRouter(prefix="/project-report", tags=["project-report"])


@router.post("/create", response_model=ProjectReportCreateResponse)
def create_project_report(payload: ProjectReportCreateRequest):
    report_id = save_project_report(payload.payload, payload.title)
    return ProjectReportCreateResponse(project_report_id=report_id, summary=build_project_summary(payload.payload), saved=True)


@router.get("/{project_report_id}", response_model=ProjectReportStored)
def read_project_report(project_report_id: int):
    report = get_project_report(project_report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Project report not found.")
    return report


@router.get("/{project_report_id}/json")
def export_project_json(project_report_id: int):
    report = get_project_report(project_report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Project report not found.")
    return report.payload


@router.get("/{project_report_id}/csv")
def export_project_csv(project_report_id: int):
    report = get_project_report(project_report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Project report not found.")
    return Response(
        build_project_csv(report.payload),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-project-report-{project_report_id}.csv"'},
    )


@router.get("/{project_report_id}/pdf")
def export_project_pdf(project_report_id: int):
    report = get_project_report(project_report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Project report not found.")
    return StreamingResponse(
        BytesIO(build_project_pdf(report.payload)),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-project-report-{project_report_id}.pdf"'},
    )


@router.get("/{project_report_id}/docx")
def export_project_docx(project_report_id: int):
    report = get_project_report(project_report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Project report not found.")
    return StreamingResponse(
        BytesIO(build_project_docx(report.payload)),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-project-report-{project_report_id}.docx"'},
    )
