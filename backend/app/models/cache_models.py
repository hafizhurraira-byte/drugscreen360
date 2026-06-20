from pydantic import BaseModel


class CacheMetadata(BaseModel):
    data_source: str = "live_api"
    cache_hit: bool = False
    cached_at: str | None = None
    expires_at: str | None = None


class CacheStats(BaseModel):
    total_cached_items: int
    items_by_source: dict[str, int]
    expired_items: int
    total_hits: int
    most_used_cached_queries: list[dict]


class CacheItem(BaseModel):
    id: int
    cache_key: str
    source: str
    query_type: str
    query_value: str
    created_at: str
    expires_at: str
    hit_count: int
    last_accessed_at: str | None = None
