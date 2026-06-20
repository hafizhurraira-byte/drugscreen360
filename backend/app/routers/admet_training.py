from fastapi import APIRouter
from fastapi.responses import Response

from app.models.admet_training_models import AdmetTrainingRequest, AdmetTrainingResponse, AdmetTrainingRunSummary
from app.services.admet_training_service import (
    get_training_run,
    list_training_runs,
    metrics_csv,
    model_card,
    train_admet_model,
    training_summary,
)

router = APIRouter(prefix="/admet-training", tags=["admet-training"])


@router.post("/train", response_model=AdmetTrainingResponse)
def train_model(payload: AdmetTrainingRequest):
    return train_admet_model(payload)


@router.get("/runs", response_model=list[AdmetTrainingRunSummary])
def training_runs():
    return list_training_runs()


@router.get("/runs/{run_id}", response_model=AdmetTrainingRunSummary)
def training_run_detail(run_id: int):
    return get_training_run(run_id)


@router.get("/runs/{run_id}/model-card")
def training_run_model_card(run_id: int):
    return model_card(run_id)


@router.get("/runs/{run_id}/training-summary")
def training_run_summary(run_id: int):
    return training_summary(run_id)


@router.get("/runs/{run_id}/metrics.csv")
def training_run_metrics_csv(run_id: int):
    return Response(
        metrics_csv(run_id),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-admet-training-{run_id}-metrics.csv"'},
    )
