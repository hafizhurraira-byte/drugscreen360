from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import get_connection, init_db
from app.main import app
from app.services import chembl_service, open_targets_service
from app.services.cache_service import get_cached_response, set_cached_response

client = TestClient(app)


def _tmp_db(monkeypatch, tmp_path):
    import app.database as database

    monkeypatch.setattr(database, "DB_PATH", Path(tmp_path) / "cache.sqlite3")
    init_db()


def test_cache_set_get(monkeypatch, tmp_path):
    _tmp_db(monkeypatch, tmp_path)
    set_cached_response("chembl", "chembl_target_search", "egfr", {"ok": True})
    cached, metadata = get_cached_response("chembl", "chembl_target_search", "egfr")
    assert cached == {"ok": True}
    assert metadata.cache_hit is True


def test_expired_cache_ignored(monkeypatch, tmp_path):
    _tmp_db(monkeypatch, tmp_path)
    set_cached_response("chembl", "chembl_target_search", "egfr", {"ok": True})
    expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with get_connection() as connection:
        connection.execute("UPDATE api_cache SET expires_at = ?", (expired,))
    cached, metadata = get_cached_response("chembl", "chembl_target_search", "egfr")
    assert cached is None
    assert metadata.cache_hit is False


def test_chembl_target_search_uses_cache_on_second_call(monkeypatch, tmp_path):
    _tmp_db(monkeypatch, tmp_path)
    calls = {"count": 0}

    def fake_get_json(path, params):
        calls["count"] += 1
        return {
            "targets": [
                {
                    "target_chembl_id": "CHEMBL203",
                    "pref_name": "Epidermal growth factor receptor",
                    "organism": "Homo sapiens",
                    "target_type": "SINGLE PROTEIN",
                    "target_components": [{"accession": "P00533"}],
                }
            ]
        }

    monkeypatch.setattr(chembl_service, "_get_json", fake_get_json)
    first = client.get("/api/finder/targets?query=EGFR")
    second = client.get("/api/finder/targets?query=EGFR")
    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1
    assert second.json()["cache_metadata"]["cache_hit"] is True


def test_chembl_candidate_retrieval_uses_cache_on_second_call(monkeypatch, tmp_path):
    _tmp_db(monkeypatch, tmp_path)
    calls = {"count": 0}

    def fake_get_json(path, params):
        calls["count"] += 1
        return {
            "activities": [
                {
                    "molecule_chembl_id": "CHEMBL1",
                    "canonical_smiles": "CCO",
                    "standard_type": "IC50",
                    "standard_value": "50",
                    "standard_units": "nM",
                    "target_pref_name": "EGFR",
                    "assay_type": "B",
                    "confidence_score": 9,
                    "standard_relation": "=",
                }
            ]
        }

    monkeypatch.setattr(chembl_service, "_get_json", fake_get_json)
    first = client.get("/api/finder/target/CHEMBL203/candidates?limit=5")
    second = client.get("/api/finder/target/CHEMBL203/candidates?limit=5")
    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1
    assert second.json()["cache_metadata"]["cache_hit"] is True


def test_open_targets_disease_search_uses_cache_on_second_call(monkeypatch, tmp_path):
    _tmp_db(monkeypatch, tmp_path)
    calls = {"count": 0}

    def fake_graphql(query, variables):
        calls["count"] += 1
        return {"search": {"hits": [{"id": "MONDO_0007254", "name": "breast cancer", "description": "desc", "entity": "disease"}]}}

    monkeypatch.setattr(open_targets_service, "_graphql", fake_graphql)
    first = client.get("/api/disease-finder/diseases?query=breast%20cancer")
    second = client.get("/api/disease-finder/diseases?query=breast%20cancer")
    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1
    assert second.json()["cache_metadata"]["cache_hit"] is True


def test_cache_clear_and_stats_endpoints(monkeypatch, tmp_path):
    _tmp_db(monkeypatch, tmp_path)
    set_cached_response("chembl", "chembl_target_search", "egfr", {"ok": True})
    stats = client.get("/api/cache/stats")
    assert stats.status_code == 200
    assert stats.json()["total_cached_items"] == 1
    response = client.delete("/api/cache/clear")
    assert response.status_code == 200
    assert response.json()["deleted_count"] == 1


def test_external_api_failure_returns_clean_error(monkeypatch, tmp_path):
    _tmp_db(monkeypatch, tmp_path)

    def fake_get_json(path, params):
        raise chembl_service.ChEMBLUnavailableError("ChEMBL is slow or unavailable right now.")

    monkeypatch.setattr(chembl_service, "_get_json", fake_get_json)
    response = client.get("/api/finder/targets?query=EGFR")
    assert response.status_code == 503
    assert "ChEMBL" in response.json()["detail"]
