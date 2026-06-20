from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_examples_returns_example_groups():
    response = client.get("/api/examples")
    assert response.status_code == 200
    body = response.json()
    assert "single_molecule" in body
    assert "drug_finder" in body
    assert "disease_finder" in body
    assert "similarity_finder" in body
    assert any(item["name"] == "Aspirin" for item in body["single_molecule"])


def test_workflow_templates_return_actions():
    response = client.get("/api/examples/workflows")
    assert response.status_code == 200
    body = response.json()
    assert any(item["name"] == "Find EGFR Candidates" for item in body["workflows"])


def test_demo_egfr_candidates_are_demo_labeled():
    response = client.get("/api/demo/egfr-candidates")
    assert response.status_code == 200
    body = response.json()
    assert body["data_source"] == "demo"
    assert body["candidates"][0]["target_chembl_id"] == "CHEMBL203"
    assert "Demo data" in body["candidates"][0]["source"]


def test_demo_breast_cancer_targets_are_demo_labeled():
    response = client.get("/api/demo/breast-cancer-targets")
    assert response.status_code == 200
    body = response.json()
    assert body["data_source"] == "demo"
    assert body["targets"][0]["suggested_chembl_query"] == "EGFR"


def test_demo_similarity_is_demo_labeled():
    response = client.get("/api/demo/similarity/caffeine")
    assert response.status_code == 200
    body = response.json()
    assert body["data_source"] == "demo"
    assert body["similar_compounds"][0]["compound_name"] == "Theophylline"
