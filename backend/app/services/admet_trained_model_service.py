import json
from pathlib import Path
from typing import Any
from fastapi import HTTPException
from app.database import get_connection, init_db
from app.services.descriptors import calculate_descriptors, parse_smiles
from datetime import datetime, timezone

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

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def discover_trained_models() -> list[dict[str, Any]]:
    models = []
    if not TRAINED_DIR.exists():
        return models
    for folder in TRAINED_DIR.iterdir():
        if not folder.is_dir():
            continue
        
        manifest_path = folder / "model_manifest.json"
        model_path = folder / "model.joblib"
        model_card_path = folder / "model_card.json"
        feature_schema_path = folder / "feature_schema.json"
        training_summary_path = folder / "training_summary.json"
        
        manifest_valid = False
        manifest_data = {}
        manifest_found = manifest_path.exists()
        
        if manifest_found:
            try:
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest_valid = True
            except:
                pass
                
        model_id = manifest_data.get("model_id") or folder.name
        model_name = manifest_data.get("model_name") or folder.name
        version = manifest_data.get("version") or "unknown"
        training_run_id = manifest_data.get("training_run_id")
        
        task_name = None
        if manifest_data.get("tasks"):
            task_name = manifest_data["tasks"][0]
            
        summary_data = {}
        if training_summary_path.exists():
            try:
                summary_data = json.loads(training_summary_path.read_text(encoding="utf-8"))
            except:
                pass
                
        task_type = summary_data.get("task_type") or manifest_data.get("feature_schema", {}).get("task_type")
        model_type = summary_data.get("model_type") or manifest_data.get("model_type")
        created_at = summary_data.get("created_at")
        
        artifact_found = model_path.exists()
        model_card_found = model_card_path.exists()
        feature_schema_found = feature_schema_path.exists()
        
        errors = []
        if not manifest_found:
            errors.append("model_manifest.json is missing")
        elif not manifest_valid:
            errors.append("model_manifest.json is invalid JSON")
        if not artifact_found:
            errors.append("model.joblib is missing")
        if not feature_schema_found:
            errors.append("feature_schema.json is missing")
            
        status = "valid" if not errors else "invalid"
        
        models.append({
            "model_id": model_id,
            "training_run_id": training_run_id,
            "task_name": task_name,
            "task_type": task_type,
            "model_name": model_name,
            "model_type": model_type,
            "version": version,
            "created_at": created_at,
            "artifact_dir": str(folder),
            "manifest_valid": manifest_valid,
            "artifact_found": artifact_found,
            "model_card_found": model_card_found,
            "feature_schema_found": feature_schema_found,
            "status": status,
            "warnings": errors
        })
    return models

def validate_trained_model(model_id: str) -> dict[str, Any]:
    models = discover_trained_models()
    model_summary = next((m for m in models if m["model_id"] == model_id), None)
    if not model_summary:
        raise HTTPException(status_code=404, detail=f"Trained model '{model_id}' not found.")
        
    folder = Path(model_summary["artifact_dir"])
    errors = []
    warnings = []
    
    manifest_path = folder / "model_manifest.json"
    artifact_path = folder / "model.joblib"
    feature_schema_path = folder / "feature_schema.json"
    
    if not manifest_path.exists():
        errors.append("model_manifest.json is missing.")
    if not artifact_path.exists():
        errors.append("model.joblib is missing.")
    if not feature_schema_path.exists():
        errors.append("feature_schema.json is missing.")
        
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"Failed to parse model_manifest.json: {e}")
            
    feature_schema = {}
    if feature_schema_path.exists():
        try:
            feature_schema = json.loads(feature_schema_path.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"Failed to parse feature_schema.json: {e}")
            
    model_data = None
    if artifact_path.exists():
        try:
            import joblib
            model_data = joblib.load(artifact_path)
            if not isinstance(model_data, dict) or "model" not in model_data:
                errors.append("model.joblib is invalid or corrupted (missing 'model' key).")
        except Exception as e:
            errors.append(f"Failed to load model.joblib: {e}")
            
    if feature_schema:
        feature_columns = feature_schema.get("feature_columns", [])
        if feature_columns != FEATURE_COLUMNS:
            errors.append(f"Feature columns in feature_schema.json do not match expected schema: {FEATURE_COLUMNS}")
        if feature_schema.get("input_type") != "rdkit_descriptors":
            errors.append(f"Unsupported input type in schema: {feature_schema.get('input_type')}")
            
    if model_data:
        feature_columns_joblib = model_data.get("feature_columns", [])
        if feature_columns_joblib != FEATURE_COLUMNS:
            errors.append(f"Feature columns in model.joblib do not match expected schema: {FEATURE_COLUMNS}")
            
    task_type = model_summary["task_type"]
    if task_type not in {"binary_classification", "regression"}:
        errors.append(f"Unsupported task type: {task_type}. Must be 'binary_classification' or 'regression'.")
        
    valid = len(errors) == 0
    return {
        "model_id": model_id,
        "valid": valid,
        "errors": errors,
        "warnings": warnings
    }

def activate_trained_model(model_id: str, project_id: int | None = None) -> dict[str, Any]:
    validation = validate_trained_model(model_id)
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=f"Cannot activate invalid model. Errors: {', '.join(validation['errors'])}")
        
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO admet_active_model (id, model_id, status, activated_at)
            VALUES (1, ?, 'active', CURRENT_TIMESTAMP)
            """,
            (model_id,)
        )
        
    if project_id:
        try:
            from app.models.project_workspace_models import ProjectAttachRequest
            from app.services.project_workspace_service import attach_project_item
            models = discover_trained_models()
            model_summary = next((m for m in models if m["model_id"] == model_id), None)
            model_name = model_summary["model_name"] if model_summary else model_id
            attach_project_item(
                project_id,
                ProjectAttachRequest(
                    item_type="admet_model_activation",
                    item_id=model_id,
                    item_title=f"Activated Trained ADMET Model: {model_name}",
                    metadata={
                        "model_id": model_id,
                        "model_name": model_name,
                        "status": "active",
                        "activated_at": _now()
                    }
                )
            )
        except Exception as e:
            pass
            
    return {
        "model_id": model_id,
        "status": "active",
        "warnings": validation["warnings"]
    }

def deactivate_trained_model(project_id: int | None = None) -> dict[str, Any]:
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO admet_active_model (id, model_id, status, activated_at)
            VALUES (1, '', 'disabled', CURRENT_TIMESTAMP)
            """
        )
        
    if project_id:
        try:
            from app.models.project_workspace_models import ProjectAttachRequest
            from app.services.project_workspace_service import attach_project_item
            attach_project_item(
                project_id,
                ProjectAttachRequest(
                    item_type="admet_model_deactivation",
                    item_id="deactivated",
                    item_title="Deactivated Trained ADMET Model predictions",
                    metadata={
                        "status": "disabled",
                        "deactivated_at": _now()
                    }
                )
            )
        except:
            pass
            
    return {
        "status": "disabled",
        "message": "Trained ADMET model predictions deactivated successfully."
    }

def get_active_trained_model_info() -> dict[str, Any]:
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM admet_active_model WHERE id = 1").fetchone()
        
    if not row:
        return {"status": "unavailable"}
        
    status = row["status"]
    model_id = row["model_id"]
    
    if status == "disabled" or not model_id:
        return {"status": "disabled"}
        
    models = discover_trained_models()
    model_summary = next((m for m in models if m["model_id"] == model_id), None)
    if not model_summary:
        return {
            "status": "missing",
            "model_id": model_id,
            "warnings": [
                f"Active model directory not found for model ID '{model_id}'.",
                "Clear or reactivate a valid trained model.",
            ],
        }
        
    validation = validate_trained_model(model_id)
    if not validation["valid"]:
        return {
            "status": "error",
            "model_id": model_id,
            "model_name": model_summary["model_name"],
            "artifact_dir": model_summary.get("artifact_dir"),
            "warnings": validation["errors"]
        }
        
    return {
            "status": "available",
            "model_id": model_id,
            "model_name": model_summary["model_name"],
            "artifact_dir": model_summary.get("artifact_dir"),
            "version": model_summary.get("version") or "unknown",
            "task_name": model_summary.get("task_name"),
            "task_type": model_summary.get("task_type"),
            "model_type": model_summary.get("model_type"),
            "warnings": validation["warnings"]
    }

def predict_trained_model(smiles: str, model_id: str | None = None, project_id: int | None = None) -> dict[str, Any]:
    if not model_id:
        active_info = get_active_trained_model_info()
        if active_info["status"] != "available":
            raise HTTPException(
                status_code=400,
                detail=f"Prediction failed: no active trained model or model is in status '{active_info['status']}'."
            )
        model_id = active_info["model_id"]
        
    validation = validate_trained_model(model_id)
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Prediction failed: model '{model_id}' is invalid: {', '.join(validation['errors'])}"
        )
        
    parse_smiles(smiles)
    
    models = discover_trained_models()
    model_summary = next((m for m in models if m["model_id"] == model_id), None)
    if not model_summary:
        raise HTTPException(status_code=404, detail=f"Model directory not found for model ID '{model_id}'.")
        
    folder = Path(model_summary["artifact_dir"])
    artifact_path = folder / "model.joblib"
    
    import joblib
    model_data = joblib.load(artifact_path)
    model = model_data["model"]
    feature_columns = model_data.get("feature_columns", FEATURE_COLUMNS)
    task_type = model_data.get("task_type", model_summary["task_type"])
    label_mapping = model_data.get("label_mapping")
    
    manifest_data = {}
    manifest_path = folder / "model_manifest.json"
    if manifest_path.exists():
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except:
            pass
            
    limitations = manifest_data.get("limitations")
    if isinstance(limitations, str):
        limitations = [limitations]
    elif not limitations:
        limitations = LIMITATIONS
        
    descriptors = calculate_descriptors(smiles).model_dump()
    features_dict = {
        "molecular_weight": descriptors.get("molecular_weight"),
        "logp": descriptors.get("logp"),
        "tpsa": descriptors.get("tpsa"),
        "hbd": descriptors.get("hydrogen_bond_donors"),
        "hba": descriptors.get("hydrogen_bond_acceptors"),
        "rotatable_bonds": descriptors.get("rotatable_bonds"),
        "ring_count": descriptors.get("ring_count"),
        "aromatic_ring_count": descriptors.get("aromatic_ring_count"),
        "formal_charge": descriptors.get("formal_charge"),
        "fraction_csp3": descriptors.get("fraction_csp3"),
    }
    
    feature_vector = [float(features_dict[col]) for col in feature_columns]
    
    warnings = []
    prediction_label = None
    prediction_value = None
    prediction_score = None
    
    if task_type == "binary_classification":
        pred_class = int(model.predict([feature_vector])[0])
        if label_mapping:
            reverse_mapping = {v: k for k, v in label_mapping.items()}
            prediction_label = str(reverse_mapping.get(pred_class, pred_class))
        else:
            prediction_label = "active" if pred_class == 1 else "inactive"
            
        if hasattr(model, "predict_proba"):
            try:
                proba = model.predict_proba([feature_vector])[0]
                prediction_score = float(proba[pred_class])
            except Exception as e:
                warnings.append(f"Could not compute probability: {e}")
    else:
        pred_val = float(model.predict([feature_vector])[0])
        prediction_value = pred_val
        units = manifest_data.get("units") or "units not specified"
        warnings.append(f"Predicted value: {pred_val} ({units})")
        
    model_name = model_summary["model_name"]
    version = manifest_data.get("version") or "unknown"
    task_name = model_summary["task_name"] or "admet_task"
    
    # Run applicability domain evaluation
    domain_status = "not_available"
    uncertainty_level = "unknown"
    nearest_training_distance = None
    out_of_range_features = []
    
    try:
        from app.services.admet_domain_service import evaluate_domain_internal
        domain_info = evaluate_domain_internal(model_id, smiles)
        if domain_info:
            domain_status = domain_info.get("domain_status", "not_available")
            uncertainty_level = domain_info.get("uncertainty_level", "unknown")
            nearest_training_distance = domain_info.get("distance_summary", {}).get("nearest_training_distance")
            out_of_range_features = domain_info.get("descriptor_range_check", {}).get("out_of_range_features", [])
            
            if domain_status == "outside_domain":
                warnings.append("Prediction is outside the model applicability domain and should be treated as unreliable.")
            elif domain_status == "borderline":
                warnings.append("Prediction is borderline inside the model applicability domain.")
    except Exception as e:
        warnings.append(f"Applicability domain not available: {e}")

    result = {
        "prediction_label": prediction_label,
        "prediction_value": prediction_value,
        "prediction_score": prediction_score,
        "task_name": task_name,
        "task_type": task_type,
        "model_id": model_id,
        "model_name": model_name,
        "version": version,
        "model_evidence_source": "trained local model",
        "features_used": feature_columns,
        "warnings": warnings,
        "limitations": limitations,
        "experimental_model_notice": "Experimental local model prediction. Requires external validation.",
        "domain_status": domain_status,
        "uncertainty_level": uncertainty_level,
        "nearest_training_distance": nearest_training_distance,
        "out_of_range_features": out_of_range_features,
    }
    
    if project_id:
        try:
            from app.models.project_workspace_models import ProjectAttachRequest
            from app.services.project_workspace_service import attach_project_item
            pred_str = prediction_label if prediction_label is not None else str(prediction_value)
            attach_project_item(
                project_id,
                ProjectAttachRequest(
                    item_type="admet_prediction_test",
                    item_id=model_id,
                    item_title=f"Prediction Test: {pred_str} ({model_name})",
                    metadata={
                        "smiles": smiles,
                        "model_id": model_id,
                        "model_name": model_name,
                        "prediction": pred_str,
                        "task_name": task_name,
                        "task_type": task_type,
                        "domain_status": domain_status,
                        "uncertainty_level": uncertainty_level,
                        "tested_at": _now()
                    }
                )
            )
        except:
            pass
            
    return result

