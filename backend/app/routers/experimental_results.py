from fastapi import APIRouter, File, Form, Response, UploadFile

from app.models.experimental_results_models import ExperimentalResultCreateRequest, ExperimentalResultBatchResponse
from app.services.experimental_results_service import (
    compare_experimental_feedback,
    create_experimental_results,
    experimental_feedback_report_json,
    experimental_results_csv,
    get_experimental_feedback,
    get_experimental_result_batch,
    import_experimental_results_csv,
    list_experimental_feedback,
    list_experimental_result_batches,
)
from app.models.experimental_results_models import ExperimentalFeedbackCompareRequest, ExperimentalFeedbackResponse

results_router = APIRouter(prefix="/experimental-results", tags=["experimental-results"])
feedback_router = APIRouter(prefix="/experimental-feedback", tags=["experimental-feedback"])


@results_router.post("/create", response_model=ExperimentalResultBatchResponse)
def create_results_endpoint(payload: ExperimentalResultCreateRequest):
    return create_experimental_results(payload)


@results_router.post("/import-csv", response_model=ExperimentalResultBatchResponse)
async def import_csv_endpoint(
    file: UploadFile = File(...),
    project_id: int | None = Form(None),
    validation_plan_id: int | None = Form(None),
):
    content = await file.read()
    return import_experimental_results_csv(content, file.filename or "experimental_results.csv", project_id, validation_plan_id)


@results_router.get("/batches")
def list_batches_endpoint():
    return list_experimental_result_batches()


@results_router.get("/batches/{batch_id}", response_model=ExperimentalResultBatchResponse)
def get_batch_endpoint(batch_id: int):
    return get_experimental_result_batch(batch_id)


@results_router.get("/batches/{batch_id}/csv")
def get_batch_csv_endpoint(batch_id: int):
    return Response(
        experimental_results_csv(batch_id),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-experimental-results-{batch_id}.csv"'},
    )


@feedback_router.post("/compare", response_model=ExperimentalFeedbackResponse)
def compare_feedback_endpoint(payload: ExperimentalFeedbackCompareRequest):
    return compare_experimental_feedback(payload)


@feedback_router.get("/summaries")
def list_feedback_endpoint():
    return list_experimental_feedback()


@feedback_router.get("/summaries/{feedback_id}", response_model=ExperimentalFeedbackResponse)
def get_feedback_endpoint(feedback_id: int):
    return get_experimental_feedback(feedback_id)


@feedback_router.get("/summaries/{feedback_id}/report.json")
def get_feedback_report_endpoint(feedback_id: int):
    return experimental_feedback_report_json(feedback_id)
