from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.admet_explain_models import (
    AdmetExplanationReportCreateRequest,
    AdmetExplanationReportCreateResponse,
    AdmetExplanationReportListItem,
    AdmetPredictionExplainRequest,
    AdmetPredictionExplanationResponse,
)
from app.services.admet_explain_service import (
    create_explanation_report,
    explain_prediction,
    explanation_report_path,
    list_explanation_reports,
)

router = APIRouter(prefix="/admet-explain", tags=["admet-explain"])


@router.post("/prediction", response_model=AdmetPredictionExplanationResponse)
def explain_prediction_endpoint(payload: AdmetPredictionExplainRequest):
    return explain_prediction(payload)


@router.post("/report/create", response_model=AdmetExplanationReportCreateResponse)
def create_report_endpoint(payload: AdmetExplanationReportCreateRequest):
    return create_explanation_report(payload)


@router.get("/reports", response_model=list[AdmetExplanationReportListItem])
def list_reports_endpoint():
    return list_explanation_reports()


@router.get("/reports/{report_id}/{fmt}")
def download_report_endpoint(report_id: int, fmt: str):
    if fmt not in {"json", "pdf", "docx"}:
        raise HTTPException(status_code=404, detail="Unsupported explanation report format.")
    path = explanation_report_path(report_id, fmt)
    if not path:
        raise HTTPException(status_code=404, detail="Explanation report file not found.")
    media_types = {
        "json": "application/json",
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    return FileResponse(path, media_type=media_types[fmt], filename=path.name)
