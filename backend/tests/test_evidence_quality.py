from fastapi.testclient import TestClient

from app.main import app
from app.models.evidence_models import EvidenceCandidateInput
from app.services import bindingdb_service, chembl_service
from app.services.evidence_quality import evaluate_batch_evidence, evaluate_candidate_evidence

client = TestClient(app)


def _candidate(**overrides):
    data = {
        "molecule_chembl_id": "CHEMBL_STRONG",
        "compound_name": "Strong example",
        "canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
        "target_chembl_id": "CHEMBL203",
        "target_name": "EGFR",
        "activity_type": "IC50",
        "activity_value": 50,
        "activity_units": "nM",
        "assay_type": "B",
        "confidence_score": 9,
        "relation": "=",
        "assay_description": "Mock direct binding assay",
    }
    data.update(overrides)
    return EvidenceCandidateInput(**data)


def test_strong_evidence_example():
    evidence = evaluate_candidate_evidence(_candidate())

    assert evidence.evidence_level == "Strong"
    assert evidence.potency_quality == "Strong"
    assert evidence.evidence_score >= 80


def test_moderate_evidence_example():
    evidence = evaluate_candidate_evidence(_candidate(activity_value=500, confidence_score=6))

    assert evidence.evidence_level in {"Moderate", "Strong"}
    assert evidence.potency_quality == "Moderate"


def test_weak_evidence_due_to_missing_metadata():
    evidence = evaluate_candidate_evidence(
        _candidate(
            molecule_chembl_id=None,
            target_chembl_id=None,
            assay_type=None,
            confidence_score=None,
            relation=None,
            activity_type="EC50",
            activity_value=5000,
        )
    )

    assert evidence.evidence_level in {"Weak", "Uncertain"}
    assert evidence.warnings


def test_weak_evidence_due_to_missing_activity_value():
    evidence = evaluate_candidate_evidence(_candidate(activity_value=None))

    assert evidence.evidence_level in {"Weak", "Uncertain"}
    assert evidence.potency_quality == "Very weak/uncertain"


def test_duplicate_candidate_evidence_handling():
    response = evaluate_batch_evidence([_candidate(activity_value=1000), _candidate(activity_value=25)])

    assert response.evaluated_count == 1
    assert response.evidence_table[0].evidence.potency_quality == "Strong"


def test_batch_evidence_evaluation_endpoint():
    response = client.post(
        "/api/evidence/evaluate-batch",
        json={"candidates": [_candidate().model_dump()]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["evaluated_count"] == 1
    assert body["evidence_table"][0]["evidence"]["evidence_score"] >= 80


def test_bindingdb_unavailable_fallback_does_not_crash(monkeypatch):
    def fake_get(*args, **kwargs):
        raise bindingdb_service.requests.Timeout()

    monkeypatch.setattr(bindingdb_service.requests, "get", fake_get)
    response = bindingdb_service.check_bindingdb_support(_candidate())

    assert response.bindingdb_checked is False
    assert "timed out" in response.limitation


def test_evaluate_candidate_endpoint():
    response = client.post(
        "/api/evidence/evaluate-candidate",
        json={"candidate": _candidate().model_dump()},
    )

    assert response.status_code == 200
    assert response.json()["evidence_level"] == "Strong"


def test_drug_finder_candidate_response_includes_evidence_fields(monkeypatch):
    def fake_get_json(path, params):
        assert path == "activity"
        return {
            "activities": [
                {
                    "molecule_chembl_id": "CHEMBL_STRONG",
                    "molecule_pref_name": "Strong example",
                    "canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "standard_type": "IC50",
                    "standard_value": "25",
                    "standard_units": "nM",
                    "target_pref_name": "EGFR",
                    "assay_type": "B",
                    "confidence_score": 9,
                    "standard_relation": "=",
                    "assay_description": "Mock assay",
                }
            ]
        }

    monkeypatch.setattr(chembl_service, "_get_json", fake_get_json)
    response = client.get("/api/finder/target/CHEMBL203/candidates?limit=1")

    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["evidence_score"] >= 80
    assert candidate["evidence_level"] == "Strong"


def test_batch_screening_response_includes_evidence_fields():
    response = client.post(
        "/api/finder/screen-candidates",
        json={
            "max_candidates": 10,
            "candidates": [_candidate().model_dump()],
        },
    )

    assert response.status_code == 200
    row = response.json()["comparison_table"][0]
    assert row["evidence_score"] >= 80
    assert row["evidence_level"] == "Strong"
    assert row["final_candidate_priority"] in {"Higher priority", "Review priority", "Requires optimization"}
