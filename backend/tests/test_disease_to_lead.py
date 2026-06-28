import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import (
    chembl_service,
    disease_to_lead_service,
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
    assert len(body["discovered_candidates"]) >= 1
    assert any(candidate["compound_name"] == "Aspirin" for candidate in body["discovered_candidates"])
    assert body["discovered_candidates"][0]["molecule_chembl_id"] == "CHEMBL25"
    assert len(body["similar_candidates"]) == 1
    assert body["similar_candidates"][0]["molecule_chembl_id"] == "CHEMBL26"
    assert body["project_id"] is not None
    assert body["screening_summary"]["total_analyzed"] > 0
    assert body["lead_prioritization_run_id"] is not None
    assert body["validation_plan_id"] is not None
    assert body["planner_status"] == "completed"
    assert body["final_report_id"] is not None
    report_id = body["final_report_id"]
    report_json = client.get(f"/api/final-report/reports/{report_id}/json")
    report_pdf = client.get(f"/api/final-report/reports/{report_id}/pdf")
    report_docx = client.get(f"/api/final-report/reports/{report_id}/docx")
    assert report_json.status_code == 200
    assert report_pdf.status_code == 200
    assert report_pdf.content.startswith(b"%PDF")
    assert report_docx.status_code == 200
    assert report_docx.content[:2] == b"PK"
    assert "Computational decision-support report only" in str(report_json.json())
    assert DEMO_NOTICE in body["scientific_notice"]


def test_disease_to_lead_planner_unavailable_does_not_crash(monkeypatch, tmp_path):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
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
    monkeypatch.setattr(similarity_service, "search_similar_compounds", lambda *args, **kwargs: ("Aspirin", [], None, None))
    monkeypatch.setattr(disease_to_lead_service, "create_validation_plan", lambda payload: (_ for _ in ()).throw(Exception("Not Found")))

    response = client.post(
        "/api/disease-to-lead/run",
        json={"disease_name": "breast cancer", "target_name": "EGFR", "known_compound": "Caffeine", "candidate_limit": 5, "similarity_limit": 5, "analysis_depth": "quick"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["planner_status"] == "warning"
    assert body["validation_plan_id"] is None
    assert "validation_plan" in body["missing_steps"]
    assert any("Validation planning could not be completed" in warning for warning in body["warnings"])
    assert "Not Found" not in " ".join(body["warnings"])
    assert DEMO_NOTICE in body["scientific_notice"]


def test_disease_to_lead_missing_candidates_marks_planner_not_available(monkeypatch, tmp_path):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
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
    monkeypatch.setattr(chembl_service, "get_target_candidates", lambda target_id, limit=10: [])
    monkeypatch.setattr(similarity_service, "search_similar_compounds", lambda *args, **kwargs: ("Caffeine", [], None, None))

    response = client.post(
        "/api/disease-to-lead/run",
        json={"disease_name": "breast cancer", "target_name": "EGFR", "candidate_limit": 5, "similarity_limit": 5, "analysis_depth": "quick"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["planner_status"] == "not_available"
    assert body["validation_plan_id"] is None
    assert any("No valid candidate set is available for validation planning" in warning for warning in body["warnings"])
    assert "Not Found" not in " ".join(body["warnings"])


def test_disease_to_lead_chembl_500_uses_known_compound_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(final_report_service, "REPORT_DIR", tmp_path / "final_project_reports")
    monkeypatch.setattr(disease_to_lead_service, "resolve_compound", lambda *args, **kwargs: (_ for _ in ()).throw(Exception("PubChem unavailable")))
    monkeypatch.setattr(chembl_service, "search_targets", lambda query: (_ for _ in ()).throw(Exception("ChEMBL returned HTTP 500")))
    monkeypatch.setattr(chembl_service, "get_target_candidates", lambda target_id, limit=10: (_ for _ in ()).throw(Exception("ChEMBL returned HTTP 500")))
    monkeypatch.setattr(open_targets_service, "search_diseases", lambda query: [])
    monkeypatch.setattr(open_targets_service, "get_disease_targets", lambda disease_id, limit=5: [])
    monkeypatch.setattr(similarity_service, "search_similar_compounds", lambda *args, **kwargs: ("Aspirin", [], None, None))

    response = client.post(
        "/api/disease-to-lead/run",
        json={
            "disease_name": "breast cancer",
            "target_name": "EGFR",
            "known_compound": "Aspirin",
            "candidate_limit": 5,
            "similarity_limit": 5,
            "analysis_depth": "quick",
        },
    )

    assert response.status_code == 200
    body = response.json()
    warnings = " ".join(body["warnings"])
    assert body["project_id"] is not None
    assert body["selected_candidates"]
    assert body["selected_candidates"][0]["compound_name"] == "Aspirin"
    assert body["final_report_id"] is not None
    assert client.get(f"/api/final-report/reports/{body['final_report_id']}/json").status_code == 200
    assert client.get(f"/api/final-report/reports/{body['final_report_id']}/pdf").status_code == 200
    assert client.get(f"/api/final-report/reports/{body['final_report_id']}/docx").status_code == 200
    assert "External candidate discovery is temporarily unavailable" in warnings
    assert "Known compound was used as a fallback starting candidate." in body["warnings"]
    assert "ChEMBL returned HTTP 500" not in warnings
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
    assert "No candidates could be retrieved" in response.json()["detail"]
