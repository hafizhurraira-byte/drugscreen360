from fastapi import APIRouter, HTTPException

from app.models.cache_models import CacheItem, CacheStats
from app.services.cache_service import cache_stats, clear_cache, delete_cache_item, list_cache_items

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/stats", response_model=CacheStats)
def get_cache_stats():
    return cache_stats()


@router.get("/items", response_model=list[CacheItem])
def get_cache_items():
    return list_cache_items()


@router.delete("/items/{cache_id}")
def delete_cache(cache_id: int):
    if not delete_cache_item(cache_id):
        raise HTTPException(status_code=404, detail="Cache item not found.")
    return {"deleted": True, "id": cache_id}


@router.delete("/clear")
def clear_all_cache():
    deleted_count = clear_cache()
    return {"deleted": True, "deleted_count": deleted_count}


@router.post("/refresh")
def refresh_cache():
    return {"status": "not_implemented", "message": "Refresh is available by re-running searches after clearing or expiry."}
