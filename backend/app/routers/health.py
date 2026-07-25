from datetime import datetime, timezone

from fastapi import APIRouter

from app.database import get_connection
from app.services.cache_service import cache_stats
from app.services.admet_trained_model_service import discover_trained_models, get_active_trained_model_info
from app.services.admet_validation_service import get_latest_external_validation_by_model
from app.services.activity_model_service import egfr_activity_model_status
from app.services.model_registry import model_status_response
from app.services.version import app_version

router = APIRouter(tags=["health"])

SCIENTIFIC_NOTICE = (
    "DrugScreen360 is computational decision-support only. It does not prove safety, efficacy, "
    "clinical success, regulatory approval, or market readiness. Experimental and clinical "
    "interpretation requires qualified scientific review."
)


def _database_status() -> dict:
    try:
        with get_connection() as connection:
            connection.execute("SELECT 1").fetchone()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def _cache_status() -> dict:
    try:
        stats = cache_stats()
        return {
            "status": "ok",
            "total_cached_items": stats.get("total_cached_items", 0),
            "expired_items": stats.get("expired_items", 0),
            "total_hits": stats.get("total_hits", 0),
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.get("/health")
def health_check():
    model_status = model_status_response()
    return {
        "status": "ok",
        "app_name": "DrugScreen360",
        "version": app_version(),
        "database": _database_status(),
        "cache": _cache_status(),
        "model_registry": {
            "available_count": len(model_status["available_models"]),
            "unavailable_count": len(model_status["unavailable_models"]),
            "available_models": [model.model_id for model in model_status["available_models"]],
            "unavailable_models": [model.model_id for model in model_status["unavailable_models"]],
            "supported_tasks": model_status["supported_tasks"],
            "limitations": model_status["limitations"],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/system/release-health")
def release_health_check():
    database = _database_status()
    cache = _cache_status()
    model_status = model_status_response()
    enabled_features = [
        "single_molecule_screening",
        "drug_finder",
        "disease_finder",
        "similarity_finder",
        "batch_upload",
        "validation_benchmarking",
        "admet_dataset_curation",
        "admet_model_training_pipeline",
        "trained_model_activation_prediction",
        "model_performance_dashboard",
        "external_validation_calibration",
        "applicability_domain_uncertainty",
        "prediction_explainability",
        "lead_prioritization",
        "experimental_validation_planner",
        "experimental_results_feedback",
        "guided_demo_workflow",
        "final_end_to_end_project_report",
        "research_export_package",
        "saved_project_workspaces",
    ]
    unavailable_features = [
        "validated_clinical_prediction",
        "regulatory_readiness_assessment",
        "automatic_wet_lab_validation",
        "docking",
        "generative_molecule_design",
        "login_or_multi_user_auth",
    ]
    return {
        "app_name": "DrugScreen360",
        "version_label": app_version(),
        "mvp_status": "local_mvp_release_candidate",
        "backend_ok": True,
        "database_ok": database.get("status") == "ok",
        "cache_ok": cache.get("status") == "ok",
        "key_modules": {
            "screening": "available",
            "finder_workflows": "available",
            "admet_dataset_and_training": "available",
            "model_registry": "available",
            "project_workspaces": "available",
            "reporting_and_exports": "available",
            "guided_demo_workflow": "available",
        },
        "enabled_features": enabled_features,
        "unavailable_features": unavailable_features,
        "major_module_count": len(enabled_features),
        "model_registry": {
            "available_count": len(model_status["available_models"]),
            "unavailable_count": len(model_status["unavailable_models"]),
            "available_models": [model.model_id for model in model_status["available_models"]],
        },
        "scientific_notice": SCIENTIFIC_NOTICE,
        "demo_available": True,
        "report_generation_available": True,
        "research_export_available": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/system/readiness")
def system_readiness():
    active = get_active_trained_model_info()
    active_status = active.get("status", "unavailable")
    latest_validation = None
    validation_status = "not_available"
    calibration_status = "not_available"
    warnings = list(active.get("warnings") or [])
    actions = []

    artifact_status = "usable" if active_status == "available" else active_status
    if active_status == "available" and active.get("model_id"):
        latest_validation = get_latest_external_validation_by_model(active["model_id"])
        if latest_validation:
            validation_status = latest_validation.get("validation_evidence_status") or "externally_validated"
            calibration_status = latest_validation.get("calibration_evidence_status") or latest_validation.get("calibration_summary", {}).get("calibration_quality") or latest_validation.get("calibration_summary", {}).get("calibration_status") or "not_available"
            warnings.extend(latest_validation.get("warnings") or [])
        else:
            actions.append("Run external validation/calibration")
    elif active_status in {"missing", "error"}:
        actions.append("Reactivate a valid trained model")
    else:
        actions.append("Train and activate a compatible ADMET model")

    valid_models = [model for model in discover_trained_models() if model.get("status") == "valid"]
    if not valid_models:
        actions.append("Upload/curate an ADMET dataset and train a local model")
    if validation_status == "not_available":
        actions.append("Generate a Disease-to-Lead report after validation for stronger evidence")

    demo_ready = active_status == "available"
    if demo_ready and latest_validation:
        overall = "Ready"
    elif active_status == "available":
        overall = "Partially Ready"
    elif active_status in {"missing", "error"}:
        overall = "Action Needed"
    else:
        overall = "Not Ready"

    egfr_activity = egfr_activity_model_status()

    return {
        "app_version": app_version(),
        "backend_status": "ok",
        "overall_status": overall,
        "active_model_status": active_status,
        "active_model_id": active.get("model_id"),
        "active_model_name": active.get("model_name"),
        "task_name": active.get("task_name"),
        "model_version": active.get("version"),
        "artifact_status": artifact_status,
        "latest_external_validation_status": validation_status,
        "latest_external_validation_run": latest_validation,
        "calibration_status": calibration_status,
        "report_generation_ready": active_status == "available",
        "demo_ready": demo_ready,
        "valid_trained_model_count": len(valid_models),
        "activity_modeling": {
            "egfr": egfr_activity,
            "supported_target_count": 1 if egfr_activity.get("trained") else 0,
            "universal_activity_model": False,
        },
        "warnings": warnings,
        "recommended_next_actions": list(dict.fromkeys(actions)),
        "scientific_notice": SCIENTIFIC_NOTICE,
    }
