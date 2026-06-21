import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import (
    chembl_service,
    open_targets_service,
    similarity_service,
    final_report_service,
    research_export_service,
)
from app.models.finder_models import CandidateMolecule, TargetResult
from app.models.similarity_models import SimilarCompound
from app.models.disease_models import DiseaseMatch, DiseaseTarget

client = TestClient(app)

DEMO_NOTICE = "Computational estimate only. Requires experimental and external validation."


def test_disease_to_lead_workflow_success(tmp_path, monkeypatch):
    # Set directories to temp path
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    monkeypatch.setattr(research_export_service, "EXPORT_DIR", tmp_path / "research_exports")

    # Mock chembl target search
    monkeypatch.setattr(
        chembl_service,
        "search_targets",
        lambda query: [
            TargetResult(
                target_chembl_id="CHEMBL203",
                preferred_name="Epidermal growth factor receptor",
                organism="Homo sapiens",
                target_type="SINGLE PROTEIN",
                accession="P00533",
            )
        ],
    )

    # Mock open targets search
    monkeypatch.setattr(
        open_targets_service,
        "search_diseases",
        lambda query: [
            DiseaseMatch(
                disease_id="EFO_0000305",
                name="breast cancer",
                description="cancer",
                entity_type="disease",
                source="Open Targets",
            )
        ],
    )

    # Mock open targets targets
    monkeypatch.setattr(
        open_targets_service,
        "get_disease_targets",
        lambda disease_id, limit=5: [
            DiseaseTarget(
                target_id="ENSG00000146648",
                approved_symbol="EGFR",
                approved_name="epidermal growth factor receptor",
                biotype="protein_coding",
                organism="Homo sapiens",
                overall_association_score=0.9,
                known_drug_score=0.8,
                literature_score=0.7,
                genetic_association_score=0.6,
                final_target_priority_score=0.9,
                suggested_chembl_query="EGFR",
                disease_target_rank=1,
                ranking_reason="high rank",
            )
        ],
    )

    # Mock chembl target candidates
    monkeypatch.setattr(
        chembl_service,
        "get_target_candidates",
        lambda target_id, limit=10: [
            CandidateMolecule(
                molecule_chembl_id="CHEMBL25",
                canonical_smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
                compound_name="Aspirin",
                activity_type="IC50",
                activity_value=50.0,
                activity_units="nM",
                target_chembl_id="CHEMBL203",
            )
        ],
    )

    # Mock similarity search
    def mock_similarity(*args, **kwargs):
        return (
            "Aspirin",
            [
                SimilarCompound(
                    molecule_chembl_id="CHEMBL26",
                    canonical_smiles="CC(=O)NC1=CC=CC=C1C(=O)O",
                    compound_name="Salicylamide",
                    similarity_score=85.0,
                    source="ChEMBL",
                )
            ],
            None,
            None,
        )

    monkeypatch.setattr(similarity_service, "search_similar_compounds", mock_similarity)

    # POST payload
    payload = {
        "disease_name": "breast cancer",
        "target_name": "EGFR",
        "known_compound": "Aspirin",
        "candidate_limit": 5,
        "similarity_limit": 5,
        "analysis_depth": "quick",
    }

    response = client.post("/api/disease-to-lead/run", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["workflow_id"] is not None
    assert body["disease_name"] == "breast cancer"
    assert body["target_name"] == "Epidermal growth factor receptor"
    assert len(body["discovered_candidates"]) == 1
    assert body["discovered_candidates"][0]["molecule_chembl_id"] == "CHEMBL25"
    assert len(body["similar_candidates"]) == 1
    assert body["similar_candidates"][0]["molecule_chembl_id"] == "CHEMBL26"
    assert body["project_id"] is not None
    assert body["screening_summary"]["total_analyzed"] > 0
    assert body["lead_prioritization_run_id"] is not None
    assert body["validation_plan_id"] is not None
    assert body["final_report_id"] is not None
    assert DEMO_NOTICE in body["scientific_notice"]


def test_disease_to_lead_workflow_validation_error():
    # Invalid candidate_limit (too high)
    payload = {"disease_name": "breast cancer", "candidate_limit": 100}
    response = client.post("/api/disease-to-lead/run", json=payload)
    assert response.status_code == 422


def test_disease_to_lead_workflow_target_unresolved(monkeypatch):
    # Mock search target returning empty list
    monkeypatch.setattr(chembl_service, "search_targets", lambda query: [])
    monkeypatch.setattr(open_targets_service, "search_diseases", lambda query: [])

    payload = {"disease_name": "unknown_disease_abc", "target_name": "unknown_target_abc"}
    response = client.post("/api/disease-to-lead/run", json=payload)
    assert response.status_code == 400
    assert "Could not resolve target" in response.json()["detail"]
