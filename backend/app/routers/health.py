from datetime import datetime, timezone

from fastapi import APIRouter

from app.database import get_connection
from app.services.cache_service import cache_stats
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
