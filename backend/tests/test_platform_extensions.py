import json

from fastapi.testclient import TestClient

from app.config import platform_config
from app.main import app
from app.models.platform_models import RankingRequest
from app.services.descriptors import calculate_descriptors
from app.services.multi_objective_scoring_service import rank_multi_objective
from app.services.plugin_service import discover_plugins, load_plugin_adapters


client = TestClient(app)


def test_multi_objective_ranking_is_deterministic_and_inverts_uncertainty():
    request = RankingRequest.model_validate({
        "candidates": [
            {"candidate_id": "low-uncertainty", "egfr": .8, "admet": .8, "confidence": .8, "uncertainty": .1, "applicability_domain": .8},
            {"candidate_id": "high-uncertainty", "egfr": .8, "admet": .8, "confidence": .8, "uncertainty": .9, "applicability_domain": .8},
        ]
    })
    result = rank_multi_objective(request)
    assert [item.candidate_id for item in result.candidates] == ["low-uncertainty", "high-uncertainty"]
    assert result.candidates[0].overall_score > result.candidates[1].overall_score


def test_html_report_escapes_input_and_embeds_structure():
    response = client.post("/api/platform/report/html", json={"title": "<unsafe>", "compound": {"canonical_smiles": "CCO"}})
    assert response.status_code == 200
    assert "&lt;unsafe&gt;" in response.text
    assert "data:image/png;base64," in response.text


def test_descriptor_cache_is_used():
    calculate_descriptors.cache_clear()
    calculate_descriptors("CCO")
    calculate_descriptors("CCO")
    assert calculate_descriptors.cache_info().hits == 1


def test_enabled_predictor_plugin_is_discovered(tmp_path, monkeypatch):
    folder = tmp_path / "sample"
    folder.mkdir()
    (folder / "plugin.json").write_text(json.dumps({"plugin_id": "sample", "module": "plugin.py", "enabled": True}), encoding="utf-8")
    (folder / "plugin.py").write_text("""class Adapter:\n model_id='sample-model'\n def is_available(self): return True\n def get_model_info(self): return None\n def predict(self, smiles): return smiles\ndef create_adapter(): return Adapter()\n""", encoding="utf-8")
    monkeypatch.setenv("DRUGSCREEN360_PLUGIN_DIRECTORY", str(tmp_path))
    platform_config.cache_clear()
    discover_plugins.cache_clear()
    load_plugin_adapters.cache_clear()
    assert load_plugin_adapters()["sample-model"].predict("CCO") == "CCO"
    load_plugin_adapters.cache_clear()
    discover_plugins.cache_clear()
    platform_config.cache_clear()
