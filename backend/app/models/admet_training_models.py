from typing import Any, Literal

from pydantic import BaseModel, Field


TaskType = Literal["auto", "binary_classification", "regression"]
ModelType = Literal["random_forest", "logistic_regression", "random_forest_regressor"]


class AdmetTrainingRequest(BaseModel):
    dataset_id: int
    task_type: TaskType = "auto"
    model_type: ModelType = "random_forest"
    test_size: float = Field(0.2, ge=0.1, le=0.5)
    random_state: int = 42
    notes: str | None = None
    project_id: int | None = None


class AdmetModelArtifactSummary(BaseModel):
    model_id: str
    model_name: str
    version: str
    task_name: str | None = None
    task_type: str
    artifact_path: str
    manifest_path: str
    model_card_path: str
    status: str


class AdmetModelCard(BaseModel):
    dataset_id: int
    dataset_name: str
    task_name: str | None = None
    task_type: str
    model_name: str
    model_type: str
    record_counts: dict[str, int]
    features_used: list[str]
    split_method: str
    metrics: dict[str, Any]
    limitations: list[str]
    warnings: list[str]
    intended_use: str
    not_intended_for: list[str]
    external_validation_required: bool = True


class AdmetTrainingRunSummary(BaseModel):
    id: int
    dataset_id: int
    task_name: str | None = None
    task_type: str
    model_name: str
    model_type: str
    status: str
    train_count: int
    test_count: int
    metric_summary: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    artifact_dir: str | None = None
    created_at: str


class AdmetTrainingResponse(BaseModel):
    training_run_id: int
    dataset_id: int
    status: str
    task_type: str
    model_type: str
    train_count: int
    test_count: int
    metrics: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    artifact: AdmetModelArtifactSummary
    model_card: AdmetModelCard
    next_steps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DiscoveredModelSummary(BaseModel):
    model_id: str
    training_run_id: int | None = None
    task_name: str | None = None
    task_type: str | None = None
    model_name: str | None = None
    model_type: str | None = None
    created_at: str | None = None
    artifact_dir: str
    manifest_valid: bool
    artifact_found: bool
    model_card_found: bool
    feature_schema_found: bool
    status: str
    warnings: list[str]


class DiscoveredModelDetail(BaseModel):
    manifest: dict[str, Any] | None = None
    model_card: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    feature_schema: dict[str, Any] | None = None
    limitations: list[str] = []
    warnings: list[str] = []


class ModelValidationResponse(BaseModel):
    model_id: str
    valid: bool
    errors: list[str]
    warnings: list[str]


class ModelActivateRequest(BaseModel):
    project_id: int | None = None


class ModelActivateResponse(BaseModel):
    model_id: str
    status: str
    warnings: list[str]


class ModelDeactivateResponse(BaseModel):
    status: str
    message: str


class ActiveModelResponse(BaseModel):
    status: str
    model_id: str | None = None
    model_name: str | None = None
    version: str | None = None
    task_name: str | None = None
    task_type: str | None = None
    warnings: list[str] = []


class TrainedModelPredictRequest(BaseModel):
    smiles: str
    model_id: str | None = None
    project_id: int | None = None


class TrainedModelPredictionResponse(BaseModel):
    prediction_label: str | None = None
    prediction_value: float | None = None
    prediction_score: float | None = None
    task_name: str
    task_type: str
    model_id: str
    model_name: str
    version: str
    features_used: list[str]
    warnings: list[str]
    limitations: list[str]
    experimental_model_notice: str


class AdmetDashboardSummaryResponse(BaseModel):
    total_training_runs: int
    total_trained_model_artifacts: int
    active_trained_model_status: dict[str, Any]
    available_trained_models: list[dict[str, Any]]
    failed_invalid_model_count: int
    dataset_count_used_for_training: int
    latest_training_run_summary: dict[str, Any] | None = None
    best_classification_model: dict[str, Any] | None = None
    best_regression_model: dict[str, Any] | None = None
    warnings: list[str] = []
    scientific_limitations: list[str] = []


class TrainingRunDashboardResponse(BaseModel):
    training_run_id: int
    training_run_metadata: dict[str, Any]
    dataset_summary: dict[str, Any]
    task_type: str
    model_type: str
    feature_list: list[str]
    train_count: int
    test_count: int
    metrics: dict[str, Any]
    confusion_matrix: list[list[int]] | None = None
    roc_auc_availability: str
    regression_metrics: dict[str, Any] | None = None
    model_card_summary: dict[str, Any] | None = None
    limitations: list[str] = []
    activation_readiness: bool
    validation_status: dict[str, Any]
    warnings: list[str] = []


class ModelComparisonItem(BaseModel):
    model_id: str
    training_run_id: int | None = None
    task_name: str | None = None
    task_type: str | None = None
    model_type: str | None = None
    dataset_name: str | None = None
    train_count: int | None = None
    test_count: int | None = None
    accuracy: Any = "not available"
    balanced_accuracy: Any = "not available"
    precision: Any = "not available"
    recall: Any = "not available"
    f1: Any = "not available"
    roc_auc: Any = "not available"
    mae: Any = "not available"
    rmse: Any = "not available"
    r2: Any = "not available"
    active_status: str
    validation_status: str
    created_at: str | None = None
    warnings: list[str] = []


class VisualDataResponse(BaseModel):
    confusion_matrix_data: list[list[int]] | None = None
    classification_metric_bars: dict[str, Any] | None = None
    regression_metric_bars: dict[str, Any] | None = None
    label_distribution: dict[str, int]
    feature_importance: Any = None
    prediction_probability_distribution: Any = None
    warnings: list[str] = []


class DashboardAttachRequest(BaseModel):
    project_id: int
    run_id: int | None = None

