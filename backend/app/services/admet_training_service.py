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


def get_admet_dashboard_summary() -> dict[str, Any]:
    init_db()
    total_runs = 0
    dataset_count = 0
    latest_run = None
    best_clf = None
    best_reg = None
    
    with get_connection() as connection:
        row_runs = connection.execute("SELECT COUNT(*) FROM admet_training_runs").fetchone()
        total_runs = row_runs[0] if row_runs else 0
        
        row_datasets = connection.execute("SELECT COUNT(DISTINCT dataset_id) FROM admet_training_runs").fetchone()
        dataset_count = row_datasets[0] if row_datasets else 0
        
        row_latest = connection.execute("SELECT * FROM admet_training_runs ORDER BY datetime(created_at) DESC, id DESC LIMIT 1").fetchone()
        if row_latest:
            latest_run = _run_from_row(row_latest).model_dump()
            
        clf_rows = connection.execute("SELECT * FROM admet_training_runs WHERE task_type = 'binary_classification'").fetchall()
        best_clf_score = -1.0
        for r in clf_rows:
            run_data = _run_from_row(r).model_dump()
            metrics = run_data.get("metric_summary") or {}
            score = 0.0
            roc_auc = metrics.get("roc_auc")
            if isinstance(roc_auc, (int, float)):
                score = float(roc_auc)
            else:
                f1 = metrics.get("f1")
                if isinstance(f1, (int, float)):
                    score = float(f1)
            
            if score > best_clf_score:
                best_clf_score = score
                best_clf = run_data
                
        reg_rows = connection.execute("SELECT * FROM admet_training_runs WHERE task_type = 'regression'").fetchall()
        best_reg_score = -9999.0
        for r in reg_rows:
            run_data = _run_from_row(r).model_dump()
            metrics = run_data.get("metric_summary") or {}
            r2 = metrics.get("r2")
            score = -9999.0
            if isinstance(r2, (int, float)):
                score = float(r2)
            else:
                rmse = metrics.get("rmse")
                if isinstance(rmse, (int, float)) and rmse > 0:
                    score = -float(rmse)
            
            if score > best_reg_score:
                best_reg_score = score
                best_reg = run_data

    from app.services.admet_trained_model_service import discover_trained_models, get_active_trained_model_info
    from app.services.admet_validation_service import get_latest_external_validation_by_model
    discovered = discover_trained_models()
    for model in discovered:
        latest_val = get_latest_external_validation_by_model(model["model_id"])
        if latest_val:
            model["external_validation_status"] = "validated"
            model["latest_external_validation"] = {
                "run_id": latest_val["id"],
                "dataset_id": latest_val["external_dataset_id"],
                "valid_count": latest_val["valid_count"],
                "metric_summary": {k: v for k, v in latest_val["metric_summary"].items() if k not in {"observed_vs_predicted", "prediction_probabilities"}},
                "calibration_status": latest_val.get("calibration_summary", {}).get("calibration_status") or "available",
                "calibration_ece": latest_val.get("calibration_summary", {}).get("expected_calibration_error"),
                "warnings": latest_val["warnings"],
                "created_at": latest_val["created_at"],
            }
            is_poor = any("overfitting" in w.lower() or "poorly calibrated" in w.lower() for w in latest_val["warnings"])
            if is_poor:
                model["external_validation_status"] = "poor_performance"
        else:
            model["external_validation_status"] = "no_validation"
            model["latest_external_validation"] = None
            
    total_artifacts = len(discovered)
    invalid_count = sum(1 for m in discovered if m.get("status") == "invalid")
    active_status = get_active_trained_model_info()
    
    active_model_domain_info = {
        "domain_summary_available": False,
        "descriptor_stats": {},
        "training_record_count": 0,
        "recent_evaluations_count": {
            "inside": 0,
            "borderline": 0,
            "outside": 0,
            "unknown": 0
        }
    }
    if active_status and active_status.get("status") == "available":
        active_model_id = active_status.get("model_id")
        try:
            from app.services.admet_domain_service import get_domain_summary_by_model, get_recent_evaluations_count
            domain_sum = get_domain_summary_by_model(active_model_id)
            if domain_sum:
                active_model_domain_info["domain_summary_available"] = True
                active_model_domain_info["descriptor_stats"] = domain_sum["descriptor_stats"]
                active_model_domain_info["training_record_count"] = domain_sum["training_record_count"]
            active_model_domain_info["recent_evaluations_count"] = get_recent_evaluations_count(active_model_id)
        except:
            pass

    warnings = []
    if total_runs == 0:
        warnings.append("No training runs recorded. Train models in the ADMET training tab.")
    if invalid_count > 0:
        warnings.append(f"There are {invalid_count} invalid trained models. Review their folder structures.")
        
    return {
        "total_training_runs": total_runs,
        "total_trained_model_artifacts": total_artifacts,
        "active_trained_model_status": active_status,
        "available_trained_models": discovered,
        "failed_invalid_model_count": invalid_count,
        "dataset_count_used_for_training": dataset_count,
        "latest_training_run_summary": latest_run,
        "best_classification_model": best_clf,
        "best_regression_model": best_reg,
        "warnings": warnings,
        "scientific_limitations": LIMITATIONS,
        "active_model_domain_info": active_model_domain_info,
    }



def get_training_run_dashboard(run_id: int) -> dict[str, Any]:
    init_db()
    run = get_training_run(run_id)
    
    with get_connection() as connection:
        dataset_row = connection.execute("SELECT * FROM admet_datasets WHERE id = ?", (run.dataset_id,)).fetchone()
    
    dataset_summary = {}
    if dataset_row:
        dataset_summary = {
            "name": dataset_row["name"],
            "task_name": dataset_row["task_name"],
            "record_count": dataset_row["record_count"],
            "valid_count": dataset_row["valid_count"],
            "invalid_count": dataset_row["invalid_count"],
            "duplicate_count": dataset_row["duplicate_count"],
            "notes": dataset_row["notes"],
        }
    
    with get_connection() as connection:
        artifact_row = connection.execute("SELECT * FROM admet_model_artifacts WHERE training_run_id = ?", (run_id,)).fetchone()
    
    model_id = None
    validation_status = {"valid": False, "errors": ["No associated model artifact found in database."], "warnings": []}
    activation_readiness = False
    model_card_summary = None
    
    if artifact_row:
        model_id = artifact_row["model_id"]
        from app.services.admet_trained_model_service import validate_trained_model
        try:
            validation_status = validate_trained_model(model_id)
            activation_readiness = validation_status["valid"]
        except Exception as e:
            validation_status = {"valid": False, "errors": [f"Validation failed with error: {e}"], "warnings": []}
            
        try:
            model_card_summary = model_card(run_id)
        except:
            pass

    limitations = list(LIMITATIONS)
    if model_card_summary and model_card_summary.get("limitations"):
        limitations = model_card_summary["limitations"]
        
    warnings = list(run.warnings)
    if model_card_summary and model_card_summary.get("warnings"):
        for w in model_card_summary["warnings"]:
            if w not in warnings:
                warnings.append(w)
                
    confusion_matrix_data = run.metric_summary.get("confusion_matrix")
    roc_auc_val = run.metric_summary.get("roc_auc")
    roc_auc_availability = "available" if (roc_auc_val is not None and not str(roc_auc_val).startswith("not available")) else "not available"
    
    regression_metrics = None
    if run.task_type == "regression":
        regression_metrics = {
            "mae": run.metric_summary.get("mae", "not available"),
            "rmse": run.metric_summary.get("rmse", "not available"),
            "r2": run.metric_summary.get("r2", "not available"),
        }

    return {
        "training_run_id": run_id,
        "training_run_metadata": {
            "id": run.id,
            "dataset_id": run.dataset_id,
            "task_name": run.task_name,
            "task_type": run.task_type,
            "model_name": run.model_name,
            "model_type": run.model_type,
            "status": run.status,
            "created_at": run.created_at,
        },
        "dataset_summary": dataset_summary,
        "task_type": run.task_type,
        "model_type": run.model_type,
        "feature_list": FEATURE_COLUMNS,
        "train_count": run.train_count,
        "test_count": run.test_count,
        "metrics": run.metric_summary,
        "confusion_matrix": confusion_matrix_data,
        "roc_auc_availability": roc_auc_availability,
        "regression_metrics": regression_metrics,
        "model_card_summary": model_card_summary,
        "limitations": limitations,
        "activation_readiness": activation_readiness,
        "validation_status": validation_status,
        "warnings": warnings,
    }


def get_model_comparison() -> list[dict[str, Any]]:
    init_db()
    from app.services.admet_trained_model_service import discover_trained_models, get_active_trained_model_info, validate_trained_model
    discovered = discover_trained_models()
    active_info = get_active_trained_model_info()
    active_model_id = active_info.get("model_id") if active_info.get("status") == "active" else None
    
    with get_connection() as connection:
        run_rows = connection.execute("SELECT * FROM admet_training_runs").fetchall()
        runs_dict = {row["id"]: row for row in run_rows}
        
        dataset_rows = connection.execute("SELECT id, name FROM admet_datasets").fetchall()
        datasets_dict = {row["id"]: row["name"] for row in dataset_rows}
        
    comparison = []
    for model in discovered:
        model_id = model["model_id"]
        run_id = model["training_run_id"]
        
        task_name = model["task_name"]
        task_type = model["task_type"]
        model_type = model["model_type"]
        dataset_name = "unknown"
        train_count = None
        test_count = None
        created_at = model["created_at"]
        warnings = list(model["warnings"])
        
        accuracy = "not available"
        balanced_accuracy = "not available"
        precision = "not available"
        recall = "not available"
        f1 = "not available"
        roc_auc = "not available"
        mae = "not available"
        rmse = "not available"
        r2 = "not available"
        
        if run_id and run_id in runs_dict:
            run_row = runs_dict[run_id]
            dataset_id = run_row["dataset_id"]
            dataset_name = datasets_dict.get(dataset_id, "unknown")
            train_count = run_row["train_count"]
            test_count = run_row["test_count"]
            created_at = run_row["created_at"]
            
            metrics = json.loads(run_row["metric_summary_json"])
            if task_type == "binary_classification":
                accuracy = metrics.get("accuracy", "not available")
                balanced_accuracy = metrics.get("balanced_accuracy", "not available")
                precision = metrics.get("precision", "not available")
                recall = metrics.get("recall", "not available")
                f1 = metrics.get("f1", "not available")
                roc_auc = metrics.get("roc_auc", "not available")
            elif task_type == "regression":
                mae = metrics.get("mae", "not available")
                rmse = metrics.get("rmse", "not available")
                r2 = metrics.get("r2", "not available")
                
        active_status = "active" if model_id == active_model_id else "inactive"
        
        validation = validate_trained_model(model_id)
        validation_status = "valid" if validation["valid"] else "invalid"
        if validation["errors"]:
            for err in validation["errors"]:
                if err not in warnings:
                    warnings.append(err)
                    
        comparison.append({
            "model_id": model_id,
            "training_run_id": run_id,
            "task_name": task_name,
            "task_type": task_type,
            "model_type": model_type,
            "dataset_name": dataset_name,
            "train_count": train_count,
            "test_count": test_count,
            "accuracy": accuracy,
            "balanced_accuracy": balanced_accuracy,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "roc_auc": roc_auc,
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "active_status": active_status,
            "validation_status": validation_status,
            "created_at": created_at,
            "warnings": warnings,
        })
        
    return comparison


def get_model_comparison_csv() -> str:
    comparison = get_model_comparison()
    output = StringIO()
    writer = csv.writer(output)
    
    headers = [
        "model_id", "training_run_id", "task_name", "task_type", "model_type",
        "dataset_name", "train_count", "test_count", "accuracy", "balanced_accuracy",
        "precision", "recall", "f1", "roc_auc", "mae", "rmse", "r2",
        "active_status", "validation_status", "created_at", "warnings"
    ]
    writer.writerow(headers)
    
    for item in comparison:
        writer.writerow([
            item["model_id"],
            item["training_run_id"],
            item["task_name"],
            item["task_type"],
            item["model_type"],
            item["dataset_name"],
            item["train_count"],
            item["test_count"],
            item["accuracy"],
            item["balanced_accuracy"],
            item["precision"],
            item["recall"],
            item["f1"],
            item["roc_auc"],
            item["mae"],
            item["rmse"],
            item["r2"],
            item["active_status"],
            item["validation_status"],
            item["created_at"],
            "; ".join(item["warnings"])
        ])
        
    return output.getvalue()


def get_run_plots_data(run_id: int) -> dict[str, Any]:
    init_db()
    run = get_training_run(run_id)
    
    label_dist = {}
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT label_value, COUNT(*) as c FROM admet_dataset_records WHERE dataset_id = ? AND is_valid = 1 GROUP BY label_value",
            (run.dataset_id,)
        ).fetchall()
        for r in rows:
            label_dist[str(r["label_value"])] = r["c"]
            
    confusion_matrix_data = None
    classification_metric_bars = None
    regression_metric_bars = None
    
    if run.task_type == "binary_classification":
        confusion_matrix_data = run.metric_summary.get("confusion_matrix")
        classification_metric_bars = {
            "accuracy": run.metric_summary.get("accuracy"),
            "balanced_accuracy": run.metric_summary.get("balanced_accuracy"),
            "precision": run.metric_summary.get("precision"),
            "recall": run.metric_summary.get("recall"),
            "f1": run.metric_summary.get("f1"),
            "roc_auc": run.metric_summary.get("roc_auc"),
        }
    else:
        regression_metric_bars = {
            "mae": run.metric_summary.get("mae"),
            "rmse": run.metric_summary.get("rmse"),
            "r2": run.metric_summary.get("r2"),
        }
        
    feature_importance = "feature importance not available for this model type"
    prob_dist = "not available"
    warnings = []
    
    with get_connection() as connection:
        artifact_row = connection.execute("SELECT * FROM admet_model_artifacts WHERE training_run_id = ?", (run_id,)).fetchone()
        
    if artifact_row:
        model_path = Path(artifact_row["artifact_path"])
        if model_path.exists():
            try:
                import joblib
                model_data = joblib.load(model_path)
                clf = model_data.get("model")
                
                if clf and hasattr(clf, "feature_importances_"):
                    raw_importances = clf.feature_importances_
                    importances_dict = {}
                    for i, col in enumerate(FEATURE_COLUMNS):
                        if i < len(raw_importances):
                            importances_dict[col] = round(float(raw_importances[i]), 6)
                    total_imp = sum(importances_dict.values())
                    if total_imp > 0:
                        feature_importance = {k: round(v / total_imp, 6) for k, v in importances_dict.items()}
                    else:
                        feature_importance = importances_dict
                else:
                    feature_importance = "feature importance not available for this model type"
                    
                if clf and run.task_type == "binary_classification" and hasattr(clf, "predict_proba"):
                    records = get_dataset_records(run.dataset_id)
                    X = []
                    for r in records:
                        if not r.is_valid or not r.descriptors:
                            continue
                        features = []
                        missing = False
                        for col in FEATURE_COLUMNS:
                            val = r.descriptors.get(col)
                            if val is None:
                                missing = True
                                break
                            features.append(float(val))
                        if not missing:
                            X.append(features)
                            
                    if X:
                        probs = clf.predict_proba(X)[:, 1]
                        prob_dist = [round(float(p), 4) for p in probs]
                    else:
                        prob_dist = []
            except Exception as e:
                warnings.append(f"Could not load model file to extract feature importances or probabilities: {e}")
        else:
            warnings.append("Model artifact file does not exist on disk.")
    else:
        warnings.append("No model artifact associated with this training run.")
        
    return {
        "confusion_matrix_data": confusion_matrix_data,
        "classification_metric_bars": classification_metric_bars,
        "regression_metric_bars": regression_metric_bars,
        "label_distribution": label_dist,
        "feature_importance": feature_importance,
        "prediction_probability_distribution": prob_dist,
        "warnings": warnings,
    }
