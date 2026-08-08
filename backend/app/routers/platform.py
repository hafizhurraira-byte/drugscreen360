from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.models.platform_models import RankingRequest, RankingResponse, ScientificHtmlReportRequest
from app.services.multi_objective_scoring_service import rank_multi_objective
from app.services.scientific_html_report_service import create_scientific_html_report

router = APIRouter(prefix="/platform", tags=["platform"])


@router.post("/rank", response_model=RankingResponse)
def rank_candidates(payload: RankingRequest):
    return rank_multi_objective(payload)


@router.post("/report/html", response_class=HTMLResponse)
def scientific_html_report(payload: ScientificHtmlReportRequest):
    return create_scientific_html_report(payload)
