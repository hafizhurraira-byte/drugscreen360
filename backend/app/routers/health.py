from datetime import datetime, timezone

from fastapi import APIRouter

from app.database import get_connection
from app.services.cache_service import cache_stats
from app.services.model_registry import model_status_response
from app.services.version import app_version

router = APIRouter(tags=["health"])


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
