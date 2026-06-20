import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.database import get_connection, init_db
from app.models.cache_models import CacheMetadata

TTL_DAYS = {
    "compound_lookup": 30,
    "chembl_target_search": 7,
    "chembl_candidate_search": 7,
    "disease_search": 7,
    "disease_target_search": 7,
    "bindingdb_support_check": 7,
    "evidence_lookup": 7,
    "similarity_search": 7,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def make_cache_key(source: str, query_type: str, query_value: str) -> str:
    raw = f"{source}:{query_type}:{query_value}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached_response(source: str, query_type: str, query_value: str) -> tuple[dict[str, Any] | None, CacheMetadata]:
    init_db()
    cache_key = make_cache_key(source, query_type, query_value)
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM api_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
        if row is None:
            return None, CacheMetadata()

        expires_at = datetime.fromisoformat(row["expires_at"])
        metadata = CacheMetadata(
            data_source="cache",
            cache_hit=True,
            cached_at=row["created_at"],
            expires_at=row["expires_at"],
        )
        if expires_at <= _now():
            return None, CacheMetadata(data_source="live_api", cache_hit=False, cached_at=row["created_at"], expires_at=row["expires_at"])

        connection.execute(
            """
            UPDATE api_cache
            SET hit_count = hit_count + 1, last_accessed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (row["id"],),
        )
        return json.loads(row["response_json"]), metadata


def set_cached_response(source: str, query_type: str, query_value: str, response: dict[str, Any]) -> CacheMetadata:
    init_db()
    cache_key = make_cache_key(source, query_type, query_value)
    created = _now()
    expires = created + timedelta(days=TTL_DAYS.get(query_type, 7))
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO api_cache (
                cache_key, source, query_type, query_value, response_json,
                created_at, expires_at, hit_count, last_accessed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                response_json = excluded.response_json,
                created_at = excluded.created_at,
                expires_at = excluded.expires_at,
                last_accessed_at = excluded.last_accessed_at
            """,
            (cache_key, source, query_type, query_value, json.dumps(response), _iso(created), _iso(expires), _iso(created)),
        )
    return CacheMetadata(data_source="live_api", cache_hit=False, cached_at=_iso(created), expires_at=_iso(expires))


def get_or_set_cache(source: str, query_type: str, query_value: str, fetcher):
    cached, metadata = get_cached_response(source, query_type, query_value)
    if cached is not None:
        return cached, metadata
    response = fetcher()
    metadata = set_cached_response(source, query_type, query_value, response)
    return response, metadata


def cache_stats() -> dict[str, Any]:
    init_db()
    now = _iso(_now())
    with get_connection() as connection:
        total = connection.execute("SELECT COUNT(*) AS count FROM api_cache").fetchone()["count"]
        expired = connection.execute("SELECT COUNT(*) AS count FROM api_cache WHERE expires_at <= ?", (now,)).fetchone()["count"]
        hits = connection.execute("SELECT COALESCE(SUM(hit_count), 0) AS count FROM api_cache").fetchone()["count"]
        by_source = {
            row["source"]: row["count"]
            for row in connection.execute("SELECT source, COUNT(*) AS count FROM api_cache GROUP BY source").fetchall()
        }
        most_used = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, source, query_type, query_value, hit_count, created_at, expires_at
                FROM api_cache
                ORDER BY hit_count DESC, datetime(last_accessed_at) DESC
                LIMIT 10
                """
            ).fetchall()
        ]
    return {
        "total_cached_items": total,
        "items_by_source": by_source,
        "expired_items": expired,
        "total_hits": hits,
        "most_used_cached_queries": most_used,
    }


def list_cache_items() -> list[dict[str, Any]]:
    init_db()
    with get_connection() as connection:
        return [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, cache_key, source, query_type, query_value, created_at,
                       expires_at, hit_count, last_accessed_at
                FROM api_cache
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT 200
                """
            ).fetchall()
        ]


def delete_cache_item(cache_id: int) -> bool:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM api_cache WHERE id = ?", (cache_id,))
        return cursor.rowcount > 0


def clear_cache() -> int:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM api_cache")
        return cursor.rowcount
