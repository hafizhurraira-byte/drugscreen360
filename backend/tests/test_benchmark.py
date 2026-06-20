from fastapi.testclient import TestClient

from app.main import app
from app.models.benchmark_models import BenchmarkCompound
from app.models.cache_models import CacheMetadata
from app.models.schemas import CompoundIdentity
from app.services import benchmark_service
from app.services.benchmark_service import benchmark_csv, benchmark_docx, benchmark_pdf, evaluate_benchmark_item, run_benchmark

client = TestClient(app)


def _mock_screen_output():
    from app.services.admet_toxicity_engine import evaluate_admet_toxicity
    from app.services.descriptors import calculate_descriptors
    from app.services.rules import build_decision, evaluate_rules, plan_experimental_tests

    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    descriptors = calculate_descriptors(smiles)
    rules = evaluate_rules(descriptors)
    admet_tox = evaluate_admet_toxicity(smiles, descriptors)
    tests = plan_experimental_tests(descriptors, rules)
    identity = CompoundIdentity(
        compound_name="Aspirin",
        pubchem_cid=2244,
        canonical_smiles=smiles,
        isomeric_smiles=smiles,
        molecular_formula="C9H8O4",
        molecular_weight=180.16,
        iupac_name="2-acetyloxybenzoic acid",
        synonyms=["Aspirin"],
        pubchem_source_link="https://pubchem.ncbi.nlm.nih.gov/compound/2244",
        cache_metadata=CacheMetadata(data_source="cache", cache_hit=True),
    )
    return {"identity": identity, "descriptors": descriptors, "rules": rules, "admet_tox": admet_tox, "decision": build_decision(rules, tests)}


def test_benchmark_compounds_endpoint_returns_grouped_data():
    response = client.get("/api/benchmark/compounds")
    assert response.status_code == 200
    groups = response.json()["groups"]
    assert "common_reference_drugs" in groups
    assert any(item["id"] == "aspirin" for item in groups["common_reference_drugs"])


def test_benchmark_run_works_on_mocked_aspirin(monkeypatch):
    monkeypatch.setattr(benchmark_service, "_screen_item", lambda item: _mock_screen_output())
    response = client.post("/api/benchmark/run", json={"selected_ids": ["aspirin"]})
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total_tested"] == 1
    assert body["individual_results"][0]["compound"] == "Aspirin"
    assert body["model_status_summary"]["only_rule_based_output_used"] is True


def test_invalid_smiles_benchmark_passes_clean_error():
    item = BenchmarkCompound(
        id="invalid",
        name="Invalid SMILES",
        input_type="smiles",
        query="C1CC",
        expected_general_behavior="Should fail cleanly.",
        expected_warning_category="clean_validation_error",
        explanation="Invalid test.",
        group="chemistry_stress_tests",
    )
    result = evaluate_benchmark_item(item)
    assert result.status == "PASS"
    assert "Invalid SMILES" in result.clean_error


def test_benchmark_summary_counts_pass_review_fail(monkeypatch):
    def fake_item(item):
        if item.id == "aspirin":
            return _mock_screen_output()
        raise RuntimeError("forced failure")

    monkeypatch.setattr(benchmark_service, "_screen_item", fake_item)
    response = run_benchmark(["aspirin", "caffeine"], None, None)
    assert response.summary.total_tested == 2
    assert response.summary.passed + response.summary.review + response.summary.failed == 2


def test_benchmark_report_pdf_docx_json_csv_exports(monkeypatch):
    monkeypatch.setattr(benchmark_service, "_screen_item", lambda item: _mock_screen_output())
    response = client.post("/api/benchmark/run", json={"selected_ids": ["aspirin"]})
    run_id = response.json()["benchmark_run_id"]

    pdf = client.get(f"/api/benchmark/runs/{run_id}/pdf")
    docx = client.get(f"/api/benchmark/runs/{run_id}/docx")
    json_response = client.get(f"/api/benchmark/runs/{run_id}/json")
    csv_response = client.get(f"/api/benchmark/runs/{run_id}/csv")

    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert docx.status_code == 200
    assert docx.content[:2] == b"PK"
    assert json_response.status_code == 200
    assert csv_response.status_code == 200
    assert "compound" in csv_response.text


def test_benchmark_report_builders_direct(monkeypatch):
    monkeypatch.setattr(benchmark_service, "_screen_item", lambda item: _mock_screen_output())
    response = run_benchmark(["aspirin"], None, None)
    assert benchmark_pdf(response).startswith(b"%PDF")
    assert benchmark_docx(response)[:2] == b"PK"
    assert "Aspirin" in benchmark_csv(response)
