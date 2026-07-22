import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Response

from app.models.admet_training_models import (
    AdmetTrainingRequest,
    AdmetTrainingResponse,
    AdmetTrainingRunSummary,
    DiscoveredModelSummary,
    DiscoveredModelDetail,
    ModelValidationResponse,
    ModelActivateRequest,
    ModelActivateResponse,
    ModelDeactivateResponse,
    ActiveModelResponse,
    TrainedModelPredictRequest,
    TrainedModelPredictionResponse,
    AdmetDashboardSummaryResponse,
    TrainingRunDashboardResponse,
    ModelComparisonItem,
    VisualDataResponse,
    DashboardAttachRequest,
)
from app.services.admet_training_service import (
    get_training_run,
    list_training_runs,
    metrics_csv,
    model_card,
    train_admet_model,
    training_summary,
    get_admet_dashboard_summary,
    get_training_run_dashboard,
    get_model_comparison,
    get_model_comparison_csv,
    get_run_plots_data,
)
from app.services.admet_trained_model_service import (
    discover_trained_models,
    validate_trained_model,
    activate_trained_model,
    deactivate_trained_model,
    get_active_trained_model_info,
    predict_trained_model,
    rollback_active_model,
)
from app.services.scientific_job_service import cancel_job, create_job, get_job, list_jobs

router = APIRouter(prefix="/admet-training", tags=["admet-training"])


@router.post("/train", response_model=AdmetTrainingResponse)
def train_model(payload: AdmetTrainingRequest):
    return train_admet_model(payload)


@router.post("/train/job")
def train_model_job(payload: AdmetTrainingRequest):
    return create_job(
        "admet_model_training",
        payload.model_dump(),
        lambda: train_admet_model(payload).model_dump(),
        {"model_family": "admet", "dataset_id": payload.dataset_id},
    )


@router.get("/jobs")
def admet_training_jobs():
    return [job for job in list_jobs() if job["job_type"] in {"admet_model_training", "admet_external_validation"}]


@router.get("/jobs/{job_id}")
def admet_training_job(job_id: int):
    return get_job(job_id)


@router.post("/jobs/{job_id}/cancel")
def cancel_admet_training_job(job_id: int):
    return cancel_job(job_id)


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


@router.get("/models", response_model=list[DiscoveredModelSummary])
def list_discovered_models():
    return discover_trained_models()


@router.get("/models/{model_id}", response_model=DiscoveredModelDetail)
def get_model_detail(model_id: str):
    models = discover_trained_models()
    model_summary = next((m for m in models if m["model_id"] == model_id), None)
    if not model_summary:
        raise HTTPException(status_code=404, detail="Trained model not found.")
        
    folder = Path(model_summary["artifact_dir"])
    manifest = {}
    if (folder / "model_manifest.json").exists():
        try:
            manifest = json.loads((folder / "model_manifest.json").read_text(encoding="utf-8"))
        except:
            pass
            
    card = {}
    if (folder / "model_card.json").exists():
        try:
            card = json.loads((folder / "model_card.json").read_text(encoding="utf-8"))
        except:
            pass
            
    feature_schema = {}
    if (folder / "feature_schema.json").exists():
        try:
            feature_schema = json.loads((folder / "feature_schema.json").read_text(encoding="utf-8"))
        except:
            pass

    split_manifest = {}
    if (folder / "split_manifest.json").exists():
        try:
            split_manifest = json.loads((folder / "split_manifest.json").read_text(encoding="utf-8"))
        except:
            pass
            
    summary = {}
    if (folder / "training_summary.json").exists():
        try:
            summary = json.loads((folder / "training_summary.json").read_text(encoding="utf-8"))
        except:
            pass
            
    metrics = summary.get("metrics") or manifest.get("metrics") or card.get("metrics") or {}
    limitations = card.get("limitations") or manifest.get("limitations") or []
    if isinstance(limitations, str):
        limitations = [limitations]
        
    warnings = model_summary.get("warnings") or []
    
    return DiscoveredModelDetail(
        manifest=manifest,
        model_card=card,
        metrics=metrics,
        feature_schema=feature_schema,
        split_manifest=split_manifest,
        limitations=limitations,
        warnings=warnings
    )


@router.post("/models/{model_id}/validate", response_model=ModelValidationResponse)
def validate_model_endpoint(model_id: str):
    return validate_trained_model(model_id)


@router.post("/models/{model_id}/activate", response_model=ModelActivateResponse)
def activate_model_endpoint(model_id: str, payload: ModelActivateRequest = None):
    project_id = payload.project_id if payload else None
    return activate_trained_model(model_id, project_id)


@router.post("/models/deactivate", response_model=ModelDeactivateResponse)
def deactivate_model_endpoint(payload: ModelActivateRequest = None):
    project_id = payload.project_id if payload else None
    return deactivate_trained_model(project_id)


@router.post("/models/rollback", response_model=ModelActivateResponse)
def rollback_model_endpoint():
    return rollback_active_model()


@router.get("/active-model", response_model=ActiveModelResponse)
def get_active_model_endpoint():
    return get_active_trained_model_info()


@router.post("/predict", response_model=TrainedModelPredictionResponse)
def predict_model_endpoint(payload: TrainedModelPredictRequest):
    return predict_trained_model(payload.smiles, payload.model_id, payload.project_id)


@router.get("/dashboard", response_model=AdmetDashboardSummaryResponse)
def get_dashboard_summary_endpoint():
    return get_admet_dashboard_summary()


@router.get("/runs/{run_id}/dashboard", response_model=TrainingRunDashboardResponse)
def get_run_dashboard_endpoint(run_id: int):
    return get_training_run_dashboard(run_id)


@router.get("/model-comparison", response_model=list[ModelComparisonItem])
def get_model_comparison_endpoint():
    return get_model_comparison()


@router.get("/model-comparison.csv")
def get_model_comparison_csv_endpoint():
    return Response(
        get_model_comparison_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="drugscreen360-admet-model-comparison.csv"'},
    )


@router.get("/runs/{run_id}/plots-data", response_model=VisualDataResponse)
def get_run_plots_data_endpoint(run_id: int):
    return get_run_plots_data(run_id)


@router.post("/dashboard/attach")
def attach_dashboard_endpoint(payload: DashboardAttachRequest):
    from app.models.project_workspace_models import ProjectAttachRequest
    from app.services.project_workspace_service import attach_project_item
    
    if payload.run_id:
        data = get_training_run_dashboard(payload.run_id)
        title = f"ADMET Model Dashboard: Run {payload.run_id} ({data['model_type']})"
        item_id = f"dashboard_run_{payload.run_id}"
    else:
        data = get_admet_dashboard_summary()
        title = "ADMET Model Dashboard Summary Snapshot"
        item_id = "dashboard_summary"
        
    attach_project_item(
        payload.project_id,
        ProjectAttachRequest(
            item_type="admet_model_dashboard",
            item_id=item_id,
            item_title=title,
            metadata=data
        )
    )
    return {"status": "success", "message": "Dashboard attached to project."}

