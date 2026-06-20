import csv
import json
import math
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from joblib import dump
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from app.database import get_connection, init_db
from app.models.admet_training_models import (
    AdmetModelArtifactSummary,
    AdmetModelCard,
    AdmetTrainingRequest,
    AdmetTrainingResponse,
    AdmetTrainingRunSummary,
)
from app.models.project_workspace_models import ProjectAttachRequest
from app.services.admet_dataset_service import get_dataset_records, get_dataset_row
from app.services.project_workspace_service import attach_project_item
from app.services.version import app_version

TRAINED_DIR = Path(__file__).resolve().parents[3] / "backend" / "models" / "admet" / "trained"
FEATURE_COLUMNS = [
    "molecular_weight",
    "logp",
    "tpsa",
    "hbd",
    "hba",
    "rotatable_bonds",
    "ring_count",
    "aromatic_ring_count",
    "formal_charge",
    "fraction_csp3",
]
LIMITATIONS = [
    "This is an experimental baseline model trained only from the uploaded curated dataset.",
    "No clinical safety, efficacy, regulatory approval, or market readiness is implied.",
    "External validation, assay provenance review, calibration, and expert review are required before scientific use.",
]
BINARY_LABELS = {
    "1": 1,
    "0": 0,
    "true": 1,
    "false": 0,
    "active": 1,
    "inactive": 0,
    "toxic": 1,
    "non-toxic": 0,
    "nontoxic": 0,
    "positive": 1,
    "negative": 0,
    "pass": 1,
    "fail": 0,
    "yes": 1,
    "no": 0,
    "high": 1,
    "low": 0,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_training_rows(dataset_id: int) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    dataset = get_dataset_row(dataset_id)
    records = get_dataset_records(dataset_id)
    rows = []
    warnings = []
    for record in records:
        if not record.is_valid or not record.canonical_smiles or not record.label_value or not record.descriptors:
            continue
        features = []
        missing = []
        for column in FEATURE_COLUMNS:
            value = record.descriptors.get(column)
            if value is None:
                missing.append(column)
                break
            features.append(float(value))
        if missing:
            warnings.append(f"Record {record.id} skipped because descriptor {missing[0]} is missing.")
            continue
        rows.append({"record": record, "features": features, "label": str(record.label_value).strip()})
    return dataset, rows, warnings


def _detect_task_type(labels: list[str], requested: str) -> tuple[str, list[Any], dict[str, int]]:
    normalized = [label.strip().lower() for label in labels]
    if requested in {"auto", "binary_classification"} and all(label in BINARY_LABELS for label in normalized):
        encoded = [BINARY_LABELS[label] for label in normalized]
        if len(set(encoded)) < 2:
            raise HTTPException(status_code=422, detail="Training refused: binary classification requires at least two classes.")
        return "binary_classification", encoded, {label: BINARY_LABELS[label] for label in sorted(set(normalized))}
    numeric_values = []
    numeric = True
    for label in labels:
        try:
            numeric_values.append(float(label))
        except ValueError:
            numeric = False
            break
    if requested in {"auto", "regression"} and numeric:
        return "regression", numeric_values, {}
    if requested == "binary_classification":
        raise HTTPException(status_code=422, detail="Training refused: labels could not be mapped to supported binary classes.")
    if requested == "regression":
        raise HTTPException(status_code=422, detail="Training refused: regression labels must be numeric.")
    raise HTTPException(status_code=422, detail="Training refused: task type could not be determined from labels. Fix labels or specify a supported task type.")


def _model_for(task_type: str, model_type: str, random_state: int):
    if task_type == "binary_classification":
        if model_type == "logistic_regression":
            return LogisticRegression(max_iter=1000, random_state=random_state), "Logistic Regression Baseline"
        return RandomForestClassifier(n_estimators=120, random_state=random_state, class_weight="balanced"), "Random Forest Classifier Baseline"
    return RandomForestRegressor(n_estimators=120, random_state=random_state), "Random Forest Regressor Baseline"


def _classification_metrics(model, x_test, y_test) -> dict[str, Any]:
    y_pred = model.predict(x_test)
    metrics = {
        "accuracy": round(float(accuracy_score(y_test, y_pred)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_test, y_pred)), 4),
        "precision": round(float(precision_score(y_test, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_test, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_test, y_pred, zero_division=0)), 4),
        "confusion_matrix": confusion_matrix(y_test, y_pred, labels=[0, 1]).tolist(),
    }
    if len(set(y_test)) == 2 and hasattr(model, "predict_proba"):
        try:
            metrics["roc_auc"] = round(float(roc_auc_score(y_test, model.predict_proba(x_test)[:, 1])), 4)
        except Exception as exc:
            metrics["roc_auc"] = f"not available: {exc}"
    else:
        metrics["roc_auc"] = "not available: test set does not contain both classes"
    return metrics


def _regression_metrics(model, x_test, y_test) -> dict[str, Any]:
    y_pred = model.predict(x_test)
    return {
        "mae": round(float(mean_absolute_error(y_test, y_pred)), 4),
        "rmse": round(float(math.sqrt(mean_squared_error(y_test, y_pred))), 4),
        "r2": round(float(r2_score(y_test, y_pred)), 4) if len(y_test) > 1 else "not available: test set too small",
    }


def _save_run(dataset_id: int, task_name: str | None, task_type: str, model_name: str, model_type: str, train_count: int, test_count: int, metrics: dict[str, Any], warnings: list[str], artifact_dir: Path) -> int:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO admet_training_runs (
                dataset_id, task_name, task_type, model_name, model_type, status,
                train_count, test_count, metric_summary_json, warnings_json, artifact_dir
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (dataset_id, task_name, task_type, model_name, model_type, "completed", train_count, test_count, json.dumps(metrics), json.dumps(warnings), str(artifact_dir)),
        )
        return int(cursor.lastrowid)


def _save_artifact(run_id: int, artifact: AdmetModelArtifactSummary) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO admet_model_artifacts (
                training_run_id, model_id, model_name, version, task_name, task_type,
                artifact_path, manifest_path, model_card_path, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                artifact.model_id,
                artifact.model_name,
                artifact.version,
                artifact.task_name,
                artifact.task_type,
                artifact.artifact_path,
                artifact.manifest_path,
                artifact.model_card_path,
                artifact.status,
            ),
        )


def train_admet_model(payload: AdmetTrainingRequest) -> AdmetTrainingResponse:
    dataset, rows, warnings = _load_training_rows(payload.dataset_id)
    if len(rows) < 20:
        raise HTTPException(status_code=422, detail=f"Training refused: at least 20 valid labelled records are required, found {len(rows)}.")
    labels = [row["label"] for row in rows]
    task_type, y, label_mapping = _detect_task_type(labels, payload.task_type)
    x = [row["features"] for row in rows]
    stratify = y if task_type == "binary_classification" else None
    try:
        x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=payload.test_size, random_state=payload.random_state, stratify=stratify)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Training refused: train/test split failed: {exc}") from exc
    model_type = payload.model_type
    if task_type == "regression" and model_type != "random_forest_regressor":
        model_type = "random_forest_regressor"
        warnings.append("Regression training uses random_forest_regressor.")
    model, model_name = _model_for(task_type, model_type, payload.random_state)
    model.fit(x_train, y_train)
    metrics = _classification_metrics(model, x_test, y_test) if task_type == "binary_classification" else _regression_metrics(model, x_test, y_test)
    created = _now()
    run_stub = created.replace(":", "-").replace(".", "-")
    artifact_dir = TRAINED_DIR / f"dataset_{payload.dataset_id}_{run_stub}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    run_id = _save_run(payload.dataset_id, dataset.get("task_name"), task_type, model_name, model_type, len(x_train), len(x_test), metrics, warnings, artifact_dir)
    model_id = f"trained_admet_dataset_{payload.dataset_id}_run_{run_id}"
    version = f"{app_version()}-run-{run_id}"
    dump({"model": model, "feature_columns": FEATURE_COLUMNS, "task_type": task_type, "label_mapping": label_mapping}, artifact_dir / "model.joblib")
    feature_schema = {"input_type": "rdkit_descriptors", "feature_columns": FEATURE_COLUMNS, "label_mapping": label_mapping}
    model_card = AdmetModelCard(
        dataset_id=payload.dataset_id,
        dataset_name=dataset["name"],
        task_name=dataset.get("task_name"),
        task_type=task_type,
        model_name=model_name,
        model_type=model_type,
        record_counts={"training_rows": len(rows), "train_count": len(x_train), "test_count": len(x_test)},
        features_used=FEATURE_COLUMNS,
        split_method=f"train_test_split test_size={payload.test_size}, random_state={payload.random_state}",
        metrics=metrics,
        limitations=LIMITATIONS,
        warnings=warnings,
        intended_use="Experimental baseline model development from a curated local ADMET dataset.",
        not_intended_for=["clinical decisions", "regulatory decisions", "safety claims", "efficacy claims", "market-readiness claims"],
    )
    manifest = {
        "model_id": model_id,
        "model_name": model_name,
        "version": version,
        "tasks": [dataset.get("task_name") or "admet_task"],
        "input_type": "rdkit_descriptors",
        "limitations": "Experimental baseline model. Requires external validation and a supported local adapter loader before prediction use.",
        "artifact_files": ["model.joblib", "feature_schema.json"],
        "training_run_id": run_id,
        "metrics": metrics,
        "feature_schema": feature_schema,
    }
    summary = {
        "training_run_id": run_id,
        "dataset_id": payload.dataset_id,
        "created_at": created,
        "task_type": task_type,
        "model_type": model_type,
        "metrics": metrics,
        "warnings": warnings,
        "limitations": LIMITATIONS,
    }
    (artifact_dir / "feature_schema.json").write_text(json.dumps(feature_schema, indent=2), encoding="utf-8")
    (artifact_dir / "model_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (artifact_dir / "model_card.json").write_text(model_card.model_dump_json(indent=2), encoding="utf-8")
    (artifact_dir / "training_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    artifact = AdmetModelArtifactSummary(
        model_id=model_id,
        model_name=model_name,
        version=version,
        task_name=dataset.get("task_name"),
        task_type=task_type,
        artifact_path=str(artifact_dir / "model.joblib"),
        manifest_path=str(artifact_dir / "model_manifest.json"),
        model_card_path=str(artifact_dir / "model_card.json"),
        status="completed",
    )
    _save_artifact(run_id, artifact)
    if payload.project_id:
        attach_project_item(
            payload.project_id,
            ProjectAttachRequest(
                item_type="admet_training_run",
                item_id=str(run_id),
                item_title=f"{model_name} for {dataset['name']}",
                metadata={
                    "workflow_type": "admet_model_training",
                    "dataset_id": payload.dataset_id,
                    "task_name": dataset.get("task_name"),
                    "task_type": task_type,
                    "model_type": model_type,
                    "train_count": len(x_train),
                    "test_count": len(x_test),
                    "metrics": metrics,
                    "decision": "experimental model trained for review",
                },
            ),
        )
    return AdmetTrainingResponse(
        training_run_id=run_id,
        dataset_id=payload.dataset_id,
        status="completed",
        task_type=task_type,
        model_type=model_type,
        train_count=len(x_train),
        test_count=len(x_test),
        metrics=metrics,
        warnings=warnings,
        artifact=artifact,
        model_card=model_card,
        next_steps=[
            "Review metrics and model card critically.",
            "Validate on an external dataset before any scientific use.",
            "Copy or configure the generated manifest only after adding a supported local model loader.",
        ],
        limitations=LIMITATIONS,
    )


def _run_from_row(row) -> AdmetTrainingRunSummary:
    return AdmetTrainingRunSummary(
        id=row["id"],
        dataset_id=row["dataset_id"],
        task_name=row["task_name"],
        task_type=row["task_type"],
        model_name=row["model_name"],
        model_type=row["model_type"],
        status=row["status"],
        train_count=row["train_count"],
        test_count=row["test_count"],
        metric_summary=json.loads(row["metric_summary_json"]),
        warnings=json.loads(row["warnings_json"]),
        artifact_dir=row["artifact_dir"],
        created_at=row["created_at"],
    )


def list_training_runs() -> list[AdmetTrainingRunSummary]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM admet_training_runs ORDER BY datetime(created_at) DESC, id DESC").fetchall()
    return [_run_from_row(row) for row in rows]


def get_training_run(run_id: int) -> AdmetTrainingRunSummary:
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM admet_training_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="ADMET training run not found.")
    return _run_from_row(row)


def _artifact_dir_for_run(run_id: int) -> Path:
    run = get_training_run(run_id)
    if not run.artifact_dir:
        raise HTTPException(status_code=404, detail="Training artifact directory is missing.")
    artifact_dir = Path(run.artifact_dir)
    if not artifact_dir.exists():
        raise HTTPException(status_code=404, detail="Training artifact directory was not found.")
    return artifact_dir


def model_card(run_id: int) -> dict[str, Any]:
    return json.loads((_artifact_dir_for_run(run_id) / "model_card.json").read_text(encoding="utf-8"))


def training_summary(run_id: int) -> dict[str, Any]:
    return json.loads((_artifact_dir_for_run(run_id) / "training_summary.json").read_text(encoding="utf-8"))


def metrics_csv(run_id: int) -> str:
    run = get_training_run(run_id)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "value"])
    for key, value in run.metric_summary.items():
        writer.writerow([key, json.dumps(value) if isinstance(value, (dict, list)) else value])
    return output.getvalue()
