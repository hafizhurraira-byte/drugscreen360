import csv
import json
import math
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
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
from fastapi import HTTPException

from app.database import get_connection, init_db
from app.models.admet_validation_models import ExternalValidationRunRequest, ExternalValidationRunSummary
from app.models.project_workspace_models import ProjectAttachRequest
from app.services.admet_dataset_service import get_dataset_records, get_dataset_row
from app.services.admet_dataset_service import upload_admet_dataset
from app.services.admet_trained_model_service import discover_trained_models, get_active_trained_model_info, validate_trained_model, FEATURE_COLUMNS
from app.services.project_workspace_service import attach_project_item
from app.services.admet_training_service import BINARY_LABELS

LIMITATIONS = [
    "External validation is dataset-dependent. Performance metrics apply only to the selected validation dataset.",
    "Computational validation only. This evaluation does not imply clinical efficacy, safety, regulatory approval, or market readiness.",
    "Validation results should be reviewed by qualified experts alongside laboratory assay data.",
]

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _run_from_row(row) -> dict[str, Any]:
    dataset = None
    try:
        dataset = get_dataset_row(row["external_dataset_id"])
    except Exception:
        dataset = None
    return {
        "id": row["id"],
        "validation_run_id": row["id"],
        "model_id": row["model_id"],
        "training_run_id": row["training_run_id"],
        "external_dataset_id": row["external_dataset_id"],
        "validation_dataset_name": dataset.get("name") if dataset else None,
        "original_filename": dataset.get("original_filename") if dataset else None,
        "task_name": row["task_name"],
        "task_type": row["task_type"],
        "status": row["status"],
        "valid_count": row["valid_count"],
        "invalid_count": row["invalid_count"],
        "metric_summary": json.loads(row["metric_summary_json"]) if row["metric_summary_json"] else {},
        "calibration_summary": json.loads(row["calibration_summary_json"]) if row["calibration_summary_json"] else {},
        "warnings": json.loads(row["warnings_json"]) if row["warnings_json"] else [],
        "notes": row["notes"],
        "created_at": row["created_at"],
    }

def _parse_binary_label(value: Any, positive_label: str = "1", negative_label: str = "0") -> int | None:
    text = str(value).strip()
    norm = text.lower()
    if text == str(positive_label).strip() or norm == str(positive_label).strip().lower():
        return 1
    if text == str(negative_label).strip() or norm == str(negative_label).strip().lower():
        return 0
    return BINARY_LABELS.get(norm)

def _validation_status(warnings: list[str], calibration_summary: dict[str, Any]) -> dict[str, str]:
    independence = "likely_independent"
    if any("may overlap" in w.lower() or "same as the model training dataset" in w.lower() for w in warnings):
        independence = "high_overlap"
    elif any("small" in w.lower() for w in warnings):
        independence = "unknown"

    cal_status = calibration_summary.get("calibration_status", "not_available")
    if cal_status == "available":
        ece = calibration_summary.get("expected_calibration_error")
        if isinstance(ece, (int, float)):
            if ece <= 0.05:
                cal_status = "calibration_good"
            elif ece <= 0.15:
                cal_status = "calibration_moderate"
            else:
                cal_status = "calibration_poor"
        else:
            cal_status = "calibration_evaluated"

    validation_status = "externally_validated_with_warnings" if warnings else "externally_validated"
    if independence == "high_overlap":
        validation_status = "internally_validated_only"
    return {
        "validation_evidence_status": validation_status,
        "calibration_evidence_status": cal_status,
        "independence_status": independence,
    }

def run_external_validation_upload(
    file_name: str,
    content: bytes,
    validation_dataset_name: str,
    smiles_column: str,
    label_column: str,
    compound_name_column: str | None = None,
    task_name: str | None = None,
    model_id: str | None = None,
    positive_label: str = "1",
    negative_label: str = "0",
    decision_threshold: float = 0.5,
    notes: str | None = None,
    project_id: int | None = None,
) -> dict[str, Any]:
    if not model_id:
        active = get_active_trained_model_info()
        if active.get("status") != "available":
            raise HTTPException(status_code=400, detail="No active compatible trained ADMET model is available. Validate and activate a trained model first.")
        model_id = active["model_id"]
        task_name = task_name or active.get("task_name")
    dataset = upload_admet_dataset(
        file_name,
        content,
        validation_dataset_name,
        task_name,
        label_column,
        smiles_column,
        compound_name_column,
        notes,
        project_id,
    )
    return run_external_validation(
        ExternalValidationRunRequest(
            model_id=model_id,
            external_dataset_id=dataset.dataset_id,
            positive_label=positive_label,
            negative_label=negative_label,
            decision_threshold=decision_threshold,
            notes=notes,
        ),
        project_id,
    )

def run_external_validation(payload: ExternalValidationRunRequest, project_id: int | None = None) -> dict[str, Any]:
    init_db()
    
    # 1. Discover and validate model
    models = discover_trained_models()
    model_summary = next((m for m in models if m["model_id"] == payload.model_id), None)
    if not model_summary:
        raise HTTPException(status_code=404, detail=f"Trained model '{payload.model_id}' not found.")
        
    validation = validate_trained_model(payload.model_id)
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=f"Cannot validate using an invalid model. Errors: {', '.join(validation['errors'])}")
        
    # 2. Get dataset and records
    dataset = get_dataset_row(payload.external_dataset_id)
    records = get_dataset_records(payload.external_dataset_id)
    
    warnings = []
    
    # Check if external dataset is the same as training dataset
    training_dataset_id = model_summary.get("training_run_id")  # In our project, training run id can lead to dataset id
    # We can also get dataset_id from the model card if it's there
    model_dir = Path(model_summary["artifact_dir"])
    model_card_path = model_dir / "model_card.json"
    train_dataset_id = None
    if model_card_path.exists():
        try:
            mcard = json.loads(model_card_path.read_text(encoding="utf-8"))
            train_dataset_id = mcard.get("dataset_id")
        except:
            pass
            
    train_smiles = set()
    if train_dataset_id:
        try:
            train_dataset = get_dataset_row(int(train_dataset_id))
            if (train_dataset.get("name") or "").strip().lower() == (dataset.get("name") or "").strip().lower():
                warnings.append("This validation dataset may overlap with the training dataset. Treat results as internal validation, not independent external validation.")
            for rec in get_dataset_records(int(train_dataset_id)):
                if rec.canonical_smiles:
                    train_smiles.add(rec.canonical_smiles)
        except Exception:
            pass
    if train_dataset_id == payload.external_dataset_id:
        warnings.append("External validation dataset is the same as the model training dataset. Use an independent dataset for rigorous validation.")
        
    # 3. Filter valid records & align types
    X = []
    y_true = []
    valid_records = []
    skipped_records = []
    
    task_type = model_summary["task_type"]
    
    invalid_count = 0
    for record in records:
        if not record.is_valid or not record.canonical_smiles or record.label_value in (None, "") or not record.descriptors:
            invalid_count += 1
            skipped_records.append((record, record.invalid_reason or "Invalid molecule, missing label, or missing descriptors."))
            continue
            
        features = []
        missing = False
        for col in FEATURE_COLUMNS:
            val = record.descriptors.get(col)
            if val is None:
                missing = True
                break
            features.append(float(val))
            
        if missing:
            invalid_count += 1
            skipped_records.append((record, "Missing required descriptor values."))
            continue
            
        # Try converting label
        lbl = str(record.label_value).strip()
        if task_type == "binary_classification":
            parsed = _parse_binary_label(lbl, payload.positive_label, payload.negative_label)
            if parsed is not None:
                y_true.append(parsed)
                X.append(features)
                valid_records.append(record)
            else:
                invalid_count += 1
                skipped_records.append((record, f"Unparseable binary label: {lbl}"))
        else:
            try:
                y_true.append(float(lbl))
                X.append(features)
                valid_records.append(record)
            except ValueError:
                invalid_count += 1
                skipped_records.append((record, f"Unparseable numeric label: {lbl}"))
                
    valid_count = len(X)
    if valid_count < 10:
        raise HTTPException(status_code=422, detail=f"External validation refused: dataset must contain at least 10 valid compatible records, found {valid_count}.")
        
    if valid_count < 30:
        warnings.append(f"Validation dataset is small (N = {valid_count}). A minimum of 30 records is strongly recommended for stable metrics.")
    if train_smiles:
        overlap_count = sum(1 for record in valid_records if record.canonical_smiles in train_smiles)
        overlap_fraction = overlap_count / valid_count if valid_count else 0.0
        if overlap_fraction >= 0.5:
            warnings.append(f"This validation dataset may overlap with the training dataset. Treat results as internal validation, not independent external validation. overlap_count={overlap_count}, overlap_fraction={overlap_fraction:.2f}")
        elif overlap_count:
            warnings.append(f"Possible training/validation overlap detected: overlap_count={overlap_count}, overlap_fraction={overlap_fraction:.2f}.")
        
    # 4. Load scikit-learn model and run predictions
    try:
        import joblib
        model_data = joblib.load(model_dir / "model.joblib")
        model = model_data["model"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load model file model.joblib: {exc}")
        
    # Run predictions
    y_prob = None
    if task_type == "binary_classification" and hasattr(model, "predict_proba"):
        try:
            y_prob = model.predict_proba(X)[:, 1]
            y_pred = np.array([1 if float(p) >= float(payload.decision_threshold) else 0 for p in y_prob])
        except Exception:
            y_pred = model.predict(X)
            y_prob = None
    else:
        y_pred = model.predict(X)
    
    metric_summary = {}
    calibration_summary = {}
    
    # 5. Calculate metrics and calibration
    if task_type == "binary_classification":
        acc = float(accuracy_score(y_true, y_pred))
        bal_acc = float(balanced_accuracy_score(y_true, y_pred))
        prec = float(precision_score(y_true, y_pred, zero_division=0))
        rec = float(recall_score(y_true, y_pred, zero_division=0))
        f1 = float(f1_score(y_true, y_pred, zero_division=0))
        conf_mat = confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist()
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
        specificity = float(tn / (tn + fp)) if (tn + fp) else 0.0
        
        class_dist = {"active": y_true.count(1), "inactive": y_true.count(0)}
        pred_dist = {"active": list(y_pred).count(1), "inactive": list(y_pred).count(0)}
        
        metric_summary = {
            "accuracy": round(acc, 4),
            "balanced_accuracy": round(bal_acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "specificity": round(specificity, 4),
            "f1": round(f1, 4),
            "confusion_matrix": conf_mat,
            "confusion_matrix_counts": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
            "false_positive_count": int(fp),
            "false_negative_count": int(fn),
            "positive_rate_actual": round(class_dist["active"] / valid_count, 4),
            "positive_rate_predicted": round(pred_dist["active"] / valid_count, 4),
            "class_distribution": class_dist,
            "prediction_distribution": pred_dist
        }
        
        # Calibration curve and probabilities
        if y_prob is not None:
            try:
                prob_list = [round(float(p), 4) for p in y_prob]
                metric_summary["prediction_probabilities"] = prob_list
                
                if len(set(y_true)) == 2:
                    metric_summary["roc_auc"] = round(float(roc_auc_score(y_true, y_prob)), 4)
                    metric_summary["average_precision"] = round(float(average_precision_score(y_true, y_prob)), 4)
                else:
                    metric_summary["roc_auc"] = "not available: test set does not contain both classes"
                    metric_summary["average_precision"] = "not available: test set does not contain both classes"
                    
                # Compute calibration curve
                cal_data = _compute_calibration_curve(y_true, y_prob)
                calibration_summary = cal_data
                ece = cal_data.get("expected_calibration_error", 0.0)
                if ece > 0.15:
                    warnings.append(f"Model probabilities are poorly calibrated (ECE = {ece:.4f}). Predictions may be overconfident.")
            except Exception as e:
                metric_summary["roc_auc"] = f"not available: {e}"
                calibration_summary = {"calibration_status": "error", "reason": str(e)}
        else:
            metric_summary["roc_auc"] = "not available: model does not support probability output"
            metric_summary["average_precision"] = "not available: model does not support probability output"
            calibration_summary = {"calibration_status": "not available", "reason": "model does not support probability output"}
            
    else:  # regression
        mae = float(mean_absolute_error(y_true, y_pred))
        rmse = float(math.sqrt(mean_squared_error(y_true, y_pred)))
        r2 = float(r2_score(y_true, y_pred)) if len(y_true) > 1 else "not available: dataset too small"
        
        obs_pred = [[round(float(o), 4), round(float(p), 4)] for o, p in zip(y_true, y_pred)]
        residuals = [float(o - p) for o, p in zip(y_true, y_pred)]
        
        res_summary = {
            "mean": round(float(np.mean(residuals)), 4),
            "std": round(float(np.std(residuals)), 4),
            "min": round(float(np.min(residuals)), 4),
            "max": round(float(np.max(residuals)), 4)
        }
        
        metric_summary = {
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "r2": round(r2, 4) if isinstance(r2, float) else r2,
            "observed_vs_predicted": obs_pred,
            "residual_summary": res_summary
        }
        calibration_summary = {"calibration_status": "not applicable", "reason": "regression model, residual summary included instead"}

    # 6. Compare with internal metrics
    comparison = {}
    if mcard := model_summary.get("model_card_found"):
        try:
            mcard_data = json.loads(model_card_path.read_text(encoding="utf-8"))
            internal_metrics = mcard_data.get("metrics") or {}
            
            # Check drop
            overfit = False
            drop_details = []
            if task_type == "binary_classification":
                int_f1 = internal_metrics.get("f1")
                ext_f1 = metric_summary.get("f1")
                if isinstance(int_f1, (int, float)) and isinstance(ext_f1, (int, float)):
                    f1_diff = int_f1 - ext_f1
                    if f1_diff > 0.15:
                        overfit = True
                        drop_details.append(f"F1 score drop of {f1_diff:.4f}")
            else:
                int_r2 = internal_metrics.get("r2")
                ext_r2 = metric_summary.get("r2")
                if isinstance(int_r2, (int, float)) and isinstance(ext_r2, (int, float)):
                    r2_diff = int_r2 - ext_r2
                    if r2_diff > 0.20:
                        overfit = True
                        drop_details.append(f"R2 score drop of {r2_diff:.4f}")
                        
                int_mae = internal_metrics.get("mae")
                ext_mae = metric_summary.get("mae")
                if isinstance(int_mae, (int, float)) and isinstance(ext_mae, (int, float)) and int_mae > 0:
                    mae_increase = (ext_mae - int_mae) / int_mae
                    if mae_increase > 0.30:
                        overfit = True
                        drop_details.append(f"MAE increase of {mae_increase * 100:.1f}%")
                        
            if overfit:
                warnings.append(f"Potential overfitting detected: external validation performance is substantially lower than training/test performance ({', '.join(drop_details)}).")
                
            comparison = {
                "internal_metrics": internal_metrics,
                "external_metrics": {k: v for k, v in metric_summary.items() if k not in {"observed_vs_predicted", "prediction_probabilities"}},
                "overfitting_detected": overfit,
                "performance_drop_details": drop_details
            }
        except Exception as e:
            comparison = {"error": f"Failed to calculate comparison: {e}"}

    # 7. Save validation run to database
    with get_connection() as connection:
        status_info = _validation_status(warnings, calibration_summary)
        cursor = connection.execute(
            """
            INSERT INTO admet_external_validation_runs (
                model_id, training_run_id, external_dataset_id, task_name, task_type, status,
                valid_count, invalid_count, metric_summary_json, calibration_summary_json, warnings_json, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.model_id,
                model_summary.get("training_run_id"),
                payload.external_dataset_id,
                dataset.get("task_name"),
                task_type,
                "completed",
                valid_count,
                invalid_count,
                json.dumps(metric_summary),
                json.dumps(calibration_summary),
                json.dumps(warnings),
                payload.notes
            )
        )
        run_id = int(cursor.lastrowid)
        for index, record in enumerate(valid_records):
            prob = float(y_prob[index]) if y_prob is not None else None
            connection.execute(
                """
                INSERT INTO admet_external_validation_records (
                    run_id, row_number, compound_name, original_smiles, canonical_smiles,
                    actual_label, predicted_label, prediction_score, uncertainty, domain_status,
                    is_valid, invalid_reason, warning
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    record.row_number,
                    record.compound_name,
                    record.original_smiles,
                    record.canonical_smiles,
                    str(record.label_value),
                    str(int(y_pred[index])) if task_type == "binary_classification" else str(float(y_pred[index])),
                    prob,
                    None,
                    None,
                    1,
                    None,
                    None,
                ),
            )
        for record, reason in skipped_records[:500]:
            connection.execute(
                """
                INSERT INTO admet_external_validation_records (
                    run_id, row_number, compound_name, original_smiles, canonical_smiles,
                    actual_label, predicted_label, prediction_score, uncertainty, domain_status,
                    is_valid, invalid_reason, warning
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    record.row_number,
                    record.compound_name,
                    record.original_smiles,
                    record.canonical_smiles,
                    str(record.label_value) if record.label_value is not None else None,
                    None,
                    None,
                    None,
                    None,
                    0,
                    reason,
                    reason,
                ),
            )

    # 8. Attach to active project if selected
    if project_id:
        try:
            attach_project_item(
                project_id,
                ProjectAttachRequest(
                    item_type="admet_external_validation",
                    item_id=str(run_id),
                    item_title=f"External Validation: {payload.model_id} on {dataset['name']}",
                    metadata={
                        "run_id": run_id,
                        "model_id": payload.model_id,
                        "dataset_name": dataset["name"],
                        "task_type": task_type,
                        "valid_count": valid_count,
                        "metric_summary": {k: v for k, v in metric_summary.items() if k not in {"observed_vs_predicted", "prediction_probabilities"}},
                        **status_info,
                    }
                )
            )
        except Exception as e:
            warnings.append(f"Failed to attach validation run to project: {e}")
            
    return get_external_validation_run_detail(run_id)

def _compute_calibration_curve(y_true, y_prob, n_bins=10) -> dict[str, Any]:
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bins = []
    ece = 0.0
    mce = 0.0
    n_samples = len(y_true)
    
    brier_score = float(np.mean((np.array(y_prob) - np.array(y_true)) ** 2)) if n_samples > 0 else 0.0
    
    for i in range(n_bins):
        bin_min = float(bin_edges[i])
        bin_max = float(bin_edges[i+1])
        
        if i == n_bins - 1:
            indices = [idx for idx, p in enumerate(y_prob) if bin_min <= p <= bin_max]
        else:
            indices = [idx for idx, p in enumerate(y_prob) if bin_min <= p < bin_max]
            
        bin_count = len(indices)
        if bin_count > 0:
            bin_y_true = [y_true[idx] for idx in indices]
            bin_y_prob = [y_prob[idx] for idx in indices]
            
            mean_predicted = float(np.mean(bin_y_prob))
            observed_positive_rate = float(np.mean(bin_y_true))
            gap = abs(observed_positive_rate - mean_predicted)
            
            bins.append({
                "bin_index": i,
                "bin_start": round(bin_min, 2),
                "bin_end": round(bin_max, 2),
                "bin_min": round(bin_min, 2),
                "bin_max": round(bin_max, 2),
                "mean_predicted_probability": round(mean_predicted, 4),
                "mean_predicted": round(mean_predicted, 4),
                "observed_positive_rate": round(observed_positive_rate, 4),
                "accuracy": round(observed_positive_rate, 4),
                "count": bin_count
            })
            ece += (bin_count / n_samples) * gap
            mce = max(mce, gap)
        else:
            bins.append({
                "bin_index": i,
                "bin_start": round(bin_min, 2),
                "bin_end": round(bin_max, 2),
                "bin_min": round(bin_min, 2),
                "bin_max": round(bin_max, 2),
                "mean_predicted_probability": 0.0,
                "mean_predicted": 0.0,
                "observed_positive_rate": 0.0,
                "accuracy": 0.0,
                "count": 0
            })
    status = "calibrated" if ece <= 0.05 else "partially_calibrated" if ece <= 0.15 else "uncalibrated"
            
    return {
        "calibration_status": "available",
        "calibration_quality": status,
        "bins": bins,
        "expected_calibration_error": round(ece, 4),
        "max_calibration_error": round(mce, 4),
        "brier_score": round(brier_score, 4)
    }

def get_external_validation_runs() -> list[dict[str, Any]]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM admet_external_validation_runs ORDER BY datetime(created_at) DESC, id DESC").fetchall()
    return [_run_from_row(row) for row in rows]

def get_external_validation_run_detail(run_id: int) -> dict[str, Any]:
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM admet_external_validation_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="ADMET external validation run not found.")
        
    detail = _run_from_row(row)
    
    # Add comparison block dynamically
    models = discover_trained_models()
    model_summary = next((m for m in models if m["model_id"] == detail["model_id"]), None)
    
    comparison = {}
    if model_summary:
        model_dir = Path(model_summary["artifact_dir"])
        model_card_path = model_dir / "model_card.json"
        if model_card_path.exists():
            try:
                mcard_data = json.loads(model_card_path.read_text(encoding="utf-8"))
                internal_metrics = mcard_data.get("metrics") or {}
                external_metrics = {k: v for k, v in detail["metric_summary"].items() if k not in {"observed_vs_predicted", "prediction_probabilities"}}
                
                # Check overfitting
                overfit = False
                drop_details = []
                task_type = detail["task_type"]
                if task_type == "binary_classification":
                    int_f1 = internal_metrics.get("f1")
                    ext_f1 = external_metrics.get("f1")
                    if isinstance(int_f1, (int, float)) and isinstance(ext_f1, (int, float)):
                        if int_f1 - ext_f1 > 0.15:
                            overfit = True
                            drop_details.append("F1 score drop > 0.15")
                else:
                    int_r2 = internal_metrics.get("r2")
                    ext_r2 = external_metrics.get("r2")
                    if isinstance(int_r2, (int, float)) and isinstance(ext_r2, (int, float)):
                        if int_r2 - ext_r2 > 0.20:
                            overfit = True
                            drop_details.append("R2 score drop > 0.20")
                            
                comparison = {
                    "internal_metrics": internal_metrics,
                    "external_metrics": external_metrics,
                    "overfitting_detected": overfit,
                    "performance_drop_details": drop_details
                }
            except:
                pass
                
    detail["comparison"] = comparison
    detail.update(_validation_status(detail["warnings"], detail.get("calibration_summary") or {}))
    detail["records_preview"] = get_external_validation_records(detail["id"], limit=25)
    detail["limitations"] = LIMITATIONS
    return detail

def get_external_validation_records(run_id: int, limit: int | None = None) -> list[dict[str, Any]]:
    init_db()
    sql = "SELECT * FROM admet_external_validation_records WHERE run_id = ? ORDER BY id"
    params: tuple[Any, ...] = (run_id,)
    if limit:
        sql += " LIMIT ?"
        params = (run_id, limit)
    with get_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [dict(row) for row in rows]

def get_external_validation_metrics_csv(run_id: int) -> str:
    detail = get_external_validation_run_detail(run_id)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "value"])
    for key, value in detail["metric_summary"].items():
        if key not in {"confusion_matrix", "observed_vs_predicted", "prediction_probabilities", "class_distribution", "prediction_distribution"}:
            writer.writerow([key, value])
            
    # Add calibration score if available
    cal = detail.get("calibration_summary") or {}
    if cal.get("calibration_status") == "available":
        writer.writerow(["expected_calibration_error", cal.get("expected_calibration_error")])
        writer.writerow(["brier_score", cal.get("brier_score")])
        
    return output.getvalue()

def get_external_validation_predictions_csv(run_id: int) -> str:
    get_external_validation_run_detail(run_id)
    records = get_external_validation_records(run_id)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["row_number", "compound_name", "original_smiles", "canonical_smiles", "actual_label", "predicted_label", "prediction_score", "is_valid", "invalid_reason"])
    for row in records:
        writer.writerow([row.get("row_number"), row.get("compound_name"), row.get("original_smiles"), row.get("canonical_smiles"), row.get("actual_label"), row.get("predicted_label"), row.get("prediction_score"), row.get("is_valid"), row.get("invalid_reason")])
    return output.getvalue()

def get_latest_external_validation_by_model(model_id: str) -> dict[str, Any] | None:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM admet_external_validation_runs WHERE model_id = ? ORDER BY datetime(created_at) DESC, id DESC LIMIT 1",
            (model_id,)
        ).fetchone()
    if not row:
        return None
    return get_external_validation_run_detail(row["id"])
