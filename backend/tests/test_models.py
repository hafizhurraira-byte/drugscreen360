from fastapi.testclient import TestClient
import requests

from app.main import app
from app.models.schemas import (
    CompoundIdentity,
    DescriptorSet,
    PlaceholderModule,
    RecommendedTest,
    RuleEvaluation,
    ScreeningRequest,
    ScreeningReport,
)
from app.services.admet_toxicity_engine import evaluate_admet_toxicity
from app.services.admet_predictor_service import predict_admet
from app.services.admet_external_provider import check_external_provider_status, predict_external_admet
from app.services.local_admet_model import check_local_admet_model_status, predict_local_admet
from app.services.reports import build_docx_report, build_pdf_report

client = TestClient(app)


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _disable_external_provider(monkeypatch):
    monkeypatch.setenv("ADMET_PROVIDER_ENABLED", "false")
    monkeypatch.delenv("ADMET_PROVIDER_BASE_URL", raising=False)
    monkeypatch.delenv("ADMET_PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("ADMET_PROVIDER_MOCK_MODE", raising=False)


def _configure_local_model(monkeypatch, tmp_path, enabled="true"):
    model_dir = tmp_path / "admet"
    model_dir.mkdir()
    monkeypatch.setenv("LOCAL_ADMET_MODEL_ENABLED", enabled)
    monkeypatch.setenv("LOCAL_ADMET_MODEL_DIR", str(model_dir))
    monkeypatch.setenv("LOCAL_ADMET_MODEL_TIMEOUT_SECONDS", "30")
    return model_dir


def test_models_status_returns_rule_based_available():
    response = client.get("/api/models/status")
    assert response.status_code == 200
    body = response.json()
    assert any(model["model_id"] == "rule_based_admet_v1" for model in body["available_models"])
    assert any(model["status"] == "unavailable" for model in body["unavailable_models"])
    all_models = body["available_models"] + body["unavailable_models"]
    assert any(model["model_id"] == "external_admet_provider_v1" for model in all_models)
    assert any(model["model_id"] == "local_admet_model" for model in all_models)


def test_local_model_disabled_returns_unavailable_group(monkeypatch, tmp_path):
    model_dir = _configure_local_model(monkeypatch, tmp_path, enabled="false")
    info = check_local_admet_model_status()
    assert info.status == "disabled"
    assert info.enabled is False
    assert info.model_dir == str(model_dir)
    response = client.get("/api/models/status")
    unavailable_ids = [model["model_id"] for model in response.json()["unavailable_models"]]
    assert "local_admet_model" in unavailable_ids


def test_local_model_enabled_missing_manifest_returns_unavailable(monkeypatch, tmp_path):
    _configure_local_model(monkeypatch, tmp_path)
    info = check_local_admet_model_status()
    assert info.status == "unavailable"
    assert info.manifest_found is False
    assert "model_manifest.json" in info.warning


def test_local_model_invalid_manifest_returns_error(monkeypatch, tmp_path):
    model_dir = _configure_local_model(monkeypatch, tmp_path)
    (model_dir / "model_manifest.json").write_text("{not valid json", encoding="utf-8")
    info = check_local_admet_model_status()
    assert info.status == "error"
    assert info.manifest_found is True
    assert "invalid JSON" in info.warning


def test_local_model_missing_artifacts_returns_unavailable(monkeypatch, tmp_path):
    model_dir = _configure_local_model(monkeypatch, tmp_path)
    (model_dir / "model_manifest.json").write_text(
        '{"model_id":"local_admet_model_v1","model_name":"Local ADMET Model","version":"1.0","tasks":["herg"],"limitations":"test","artifact_files":["missing.pkl"]}',
        encoding="utf-8",
    )
    info = check_local_admet_model_status()
    assert info.status == "unavailable"
    assert info.manifest_found is True
    assert info.artifacts_found is False
    assert "missing.pkl" in info.warning


def test_model_status_endpoint_includes_local_model_details(monkeypatch, tmp_path):
    model_dir = _configure_local_model(monkeypatch, tmp_path, enabled="false")
    response = client.get("/api/models/status")
    assert response.status_code == 200
    models = response.json()["available_models"] + response.json()["unavailable_models"]
    local = next(model for model in models if model["model_id"] == "local_admet_model")
    assert local["enabled"] is False
    assert local["model_dir"] == str(model_dir)
    assert local["manifest_found"] is False


def test_external_provider_unavailable_when_disabled(monkeypatch):
    _disable_external_provider(monkeypatch)
    info = check_external_provider_status()
    assert info.model_id == "external_admet_provider_v1"
    assert info.status == "unavailable"
    assert info.warning == "External ADMET provider is not configured."


def test_external_provider_unavailable_without_base_url(monkeypatch):
    monkeypatch.setenv("ADMET_PROVIDER_ENABLED", "true")
    monkeypatch.delenv("ADMET_PROVIDER_BASE_URL", raising=False)
    monkeypatch.delenv("ADMET_PROVIDER_MOCK_MODE", raising=False)
    info = check_external_provider_status()
    assert info.status == "unavailable"
    assert info.base_url_configured is False


def test_external_provider_health_check_handles_timeout(monkeypatch):
    monkeypatch.setenv("ADMET_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("ADMET_PROVIDER_BASE_URL", "https://example.test")
    monkeypatch.setenv("ADMET_PROVIDER_MOCK_MODE", "false")

    def fake_get(*args, **kwargs):
        raise requests.Timeout()

    monkeypatch.setattr("app.services.admet_external_provider.requests.get", fake_get)
    info = check_external_provider_status()
    assert info.status == "error"
    assert "timed out" in info.warning


def test_external_provider_prediction_parses_valid_response(monkeypatch):
    monkeypatch.setenv("ADMET_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("ADMET_PROVIDER_BASE_URL", "https://example.test")
    monkeypatch.setenv("ADMET_PROVIDER_MOCK_MODE", "false")

    monkeypatch.setattr("app.services.admet_external_provider.requests.get", lambda *args, **kwargs: _FakeResponse())

    def fake_post(*args, **kwargs):
        return _FakeResponse(
            payload={
                "model_id": "real-provider",
                "model_name": "Configured Test Provider",
                "version": "1.0",
                "predictions": [
                    {
                        "task_name": "herg",
                        "prediction_label": "low_risk",
                        "prediction_score": 0.21,
                        "probability": 0.21,
                        "confidence": "medium",
                        "limitations": "test provider output",
                    }
                ],
                "warnings": [],
            }
        )

    monkeypatch.setattr("app.services.admet_external_provider.requests.post", fake_post)
    bundle = predict_external_admet("CCO")
    assert bundle.model_status == "available"
    assert bundle.predictions[0].prediction_label == "low_risk"


def test_external_provider_invalid_response_returns_error(monkeypatch):
    monkeypatch.setenv("ADMET_PROVIDER_ENABLED", "true")
    monkeypatch.setenv("ADMET_PROVIDER_BASE_URL", "https://example.test")
    monkeypatch.setenv("ADMET_PROVIDER_MOCK_MODE", "false")
    monkeypatch.setattr("app.services.admet_external_provider.requests.get", lambda *args, **kwargs: _FakeResponse())
    monkeypatch.setattr("app.services.admet_external_provider.requests.post", lambda *args, **kwargs: _FakeResponse(payload={"unexpected": []}))
    bundle = predict_external_admet("CCO")
    assert bundle.model_status == "error"
    assert "could not be parsed" in bundle.warnings[0]


def test_unavailable_placeholder_models_return_unavailable_not_fake_predictions():
    response = client.post(
        "/api/models/predict-admet",
        json={"smiles": "CCO", "models": ["external_admet_service"], "include_unavailable": True},
    )
    assert response.status_code == 200
    output = response.json()["model_outputs"][0]
    assert output["model_status"] == "unavailable"
    assert output["predictions"][0]["prediction_label"] == "not_available"


def test_predict_admet_does_not_fake_local_model_predictions(monkeypatch, tmp_path):
    _configure_local_model(monkeypatch, tmp_path, enabled="false")
    response = client.post(
        "/api/models/predict-admet",
        json={"smiles": "CCO", "models": ["local_admet_model"], "include_unavailable": True},
    )
    assert response.status_code == 200
    output = response.json()["model_outputs"][0]
    assert output["model_status"] == "disabled"
    assert output["predictions"] == []
    assert response.json()["model_status_summary"]["local_model_available"] is False


def test_screening_still_works_when_local_model_unavailable(monkeypatch, tmp_path):
    _configure_local_model(monkeypatch, tmp_path, enabled="false")
    response = predict_admet("CCO", ["rule_based_admet_v1", "local_admet_model"], True)
    assert response.model_outputs[0].model_id == "rule_based_admet_v1"
    local = next(item for item in response.model_outputs if item.model_id == "local_admet_model")
    assert local.predictions == []
    assert response.model_status_summary["local_model_available"] is False


def test_predict_admet_valid_smiles():
    response = client.post(
        "/api/models/predict-admet",
        json={"smiles": "CCO", "models": ["rule_based_admet_v1"], "include_unavailable": True},
    )
    assert response.status_code == 200
    assert response.json()["canonical_smiles"] == "CCO"
    assert response.json()["model_outputs"][0]["model_status"] == "available"
    assert response.json()["model_status_summary"]["rule_based_used"] is True


def test_predict_admet_handles_external_unavailable(monkeypatch):
    _disable_external_provider(monkeypatch)
    response = client.post(
        "/api/models/predict-admet",
        json={"smiles": "CCO", "models": ["rule_based_admet_v1", "external_admet_provider_v1"], "include_unavailable": True},
    )
    assert response.status_code == 200
    body = response.json()
    external = next(item for item in body["model_outputs"] if item["model_id"] == "external_admet_provider_v1")
    assert external["model_status"] == "unavailable"
    assert body["model_status_summary"]["external_model_available"] is False


def test_predict_admet_invalid_smiles_returns_clean_error():
    response = client.post("/api/models/predict-admet", json={"smiles": "C1CC", "models": ["rule_based_admet_v1"]})
    assert response.status_code == 422
    assert "Invalid SMILES" in response.json()["detail"]


def test_model_comparison_handles_unavailable_models():
    response = client.post("/api/models/compare", json={"smiles": "CCO", "selected_models": ["rule_based_admet_v1", "local_admet_model"]})
    assert response.status_code == 200
    body = response.json()
    assert "unavailable" in body["agreement_summary"]


def test_report_includes_prediction_model_status():
    smiles = "CCO"
    admet = evaluate_admet_toxicity(smiles)
    report = ScreeningReport(
        disclaimer="test",
        input=ScreeningRequest(query=smiles, input_type="smiles"),
        compound_identity=CompoundIdentity(
            compound_name="Ethanol",
            pubchem_cid=None,
            canonical_smiles=smiles,
            isomeric_smiles=smiles,
            molecular_formula="C2H6O",
            molecular_weight=46.07,
            iupac_name="ethanol",
            synonyms=[],
            pubchem_source_link=None,
        ),
        physicochemical_properties=DescriptorSet(
            molecular_weight=46.07,
            logp=-0.001,
            tpsa=20.23,
            hydrogen_bond_donors=1,
            hydrogen_bond_acceptors=1,
            rotatable_bonds=0,
            formal_charge=0,
            ring_count=0,
            aromatic_ring_count=0,
            fraction_csp3=1.0,
        ),
        drug_likeness=RuleEvaluation(
            lipinski_rule_of_5={"passed": True},
            veber_rule={"passed": True},
            basic_drug_likeness_status="Good",
            developability_risk="Low",
            reasons=[],
        ),
        admet_placeholder=PlaceholderModule(status="placeholder", message="placeholder", future_outputs=[]),
        toxicity_placeholder=PlaceholderModule(status="placeholder", message="placeholder", future_outputs=[]),
        admet_toxicity_v1=admet,
        model_predictions=predict_admet(smiles, ["rule_based_admet_v1", "external_admet_provider_v1", "local_admet_model"], True),
        required_lab_tests=[RecommendedTest(name="Solubility assay", priority="Standard", reason="test")],
        go_no_go_recommendation={"decision": "Proceed"},
        limitations=[],
    )
    assert build_pdf_report(report).startswith(b"%PDF")
    assert build_docx_report(report)[:2] == b"PK"


def test_mock_mode_clearly_labeled_and_disabled_by_default(monkeypatch):
    _disable_external_provider(monkeypatch)
    assert check_external_provider_status().status != "mock"

    monkeypatch.setenv("ADMET_PROVIDER_MOCK_MODE", "true")
    bundle = predict_external_admet("CCO")
    assert bundle.model_status == "mock"
    assert "software testing only" in bundle.warnings[0]
