import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import app
from app.services import research_export_service

client = TestClient(app)


def _create_export(tmp_path, monkeypatch, payload=None):
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")
    response = client.post(
        "/api/research-export/create",
        json=payload
        or {
            "project_title": "Test Export",
            "notes": "unit test",
            "include_reports": True,
            "include_cache_status": True,
            "include_benchmark_runs": True,
            "include_batch_runs": True,
            "include_screening_history": True,
        },
    )
    assert response.status_code == 200
    return response.json()


def _zip_names(export_id):
    response = client.get(f"/api/research-export/{export_id}/download")
    assert response.status_code == 200
    assert response.content[:2] == b"PK"
    archive = zipfile.ZipFile(BytesIO(response.content))
    return archive, archive.namelist()


def test_research_export_create_endpoint_works(tmp_path, monkeypatch):
    body = _create_export(tmp_path, monkeypatch)
    assert body["export_id"] > 0
    assert body["filename"].endswith(".zip")
    assert body["download_url"].endswith(f"/{body['export_id']}/download")


def test_research_export_zip_contains_required_files(tmp_path, monkeypatch):
    body = _create_export(tmp_path, monkeypatch)
    _, names = _zip_names(body["export_id"])
    assert any(name.endswith("README_EXPORT.md") for name in names)
    assert any(name.endswith("MANIFEST.json") for name in names)
    assert any(name.endswith("MODEL_STATUS.json") for name in names)
    assert any(name.endswith("LOCAL_MODEL_VALIDATION.json") for name in names)
    assert any(name.endswith("DISCLAIMERS/scientific_limitations.md") for name in names)


def test_research_export_download_endpoint_returns_zip(tmp_path, monkeypatch):
    body = _create_export(tmp_path, monkeypatch)
    response = client.get(f"/api/research-export/{body['export_id']}/download")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert response.content[:2] == b"PK"


def test_research_export_list_endpoint_works(tmp_path, monkeypatch):
    body = _create_export(tmp_path, monkeypatch)
    response = client.get("/api/research-export/list")
    assert response.status_code == 200
    assert any(item["export_id"] == body["export_id"] for item in response.json())


def test_research_export_handles_missing_reports_gracefully(tmp_path, monkeypatch):
    body = _create_export(
        tmp_path,
        monkeypatch,
        {
            "project_title": "Empty Export",
            "notes": None,
            "include_reports": True,
            "include_cache_status": True,
            "include_benchmark_runs": True,
            "include_batch_runs": True,
            "include_screening_history": True,
        },
    )
    assert isinstance(body["warnings"], list)


def test_research_export_does_not_include_env_or_secrets(tmp_path, monkeypatch):
    body = _create_export(tmp_path, monkeypatch)
    archive, names = _zip_names(body["export_id"])
    lowered = [name.lower() for name in names]
    assert not any(name.endswith(".env") for name in lowered)
    assert not any(".env" in name for name in lowered)
    combined_text = ""
    for name in names:
        if name.endswith((".json", ".md", ".csv")):
            combined_text += archive.read(name).decode("utf-8", errors="ignore")
    assert "ADMET_PROVIDER_API_KEY=" not in combined_text
    assert "Authorization: Bearer" not in combined_text
