from fastapi.testclient import TestClient

from app.main import app
from app.models.project_report_models import ProjectReportPayload
from app.models.schemas import CompoundIdentity
from app.models.similarity_models import SimilarCompound
from app.services.cache_service import clear_cache
from app.services.project_reports import build_project_docx, build_project_pdf
from app.services import similarity_service
from app.services.similarity_service import rank_similar_compounds

client = TestClient(app)


def setup_function():
    clear_cache()


def _reference():
    return CompoundIdentity(
        compound_name="Aspirin",
        pubchem_cid=2244,
        canonical_smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
        isomeric_smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
        molecular_formula="C9H8O4",
        molecular_weight=180.16,
        iupac_name="2-acetyloxybenzoic acid",
        synonyms=["Aspirin"],
        pubchem_source_link="https://pubchem.ncbi.nlm.nih.gov/compound/2244",
    )


def test_valid_smiles_similarity_request(monkeypatch):
    monkeypatch.setattr(similarity_service, "resolve_reference", lambda query, input_type: _reference())
    monkeypatch.setattr(
        similarity_service,
        "_chembl_similarity",
        lambda smiles, threshold, limit: [
            SimilarCompound(
                compound_name="Analog A",
                molecule_chembl_id="CHEMBL_A",
                canonical_smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
                similarity_score=100,
                source="ChEMBL",
            )
        ],
    )
    response = client.post(
        "/api/similarity/search",
        json={"query": "CC(=O)OC1=CC=CC=C1C(=O)O", "input_type": "smiles", "source": "chembl", "threshold": 70, "limit": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reference_compound"]["compound_name"] == "Aspirin"
    assert body["similar_compounds"][0]["molecule_chembl_id"] == "CHEMBL_A"
    assert body["cache_metadata"]["cache_hit"] is False


def test_invalid_smiles_returns_clean_error():
    response = client.post(
        "/api/similarity/search",
        json={"query": "C1CC", "input_type": "smiles", "source": "chembl", "threshold": 70, "limit": 10},
    )
    assert response.status_code == 422
    assert "Invalid SMILES" in response.json()["detail"]


def test_similarity_ranking_sorts_higher_similarity_first():
    ranked = rank_similar_compounds(
        "CCO",
        [
            SimilarCompound(compound_name="Low", canonical_smiles="CCCO", similarity_score=55, source="Mock"),
            SimilarCompound(compound_name="High", canonical_smiles="CCO", similarity_score=100, source="Mock", pubchem_cid=1),
        ],
    )
    assert ranked[0].compound_name == "High"
    assert ranked[0].similarity_rank == 1


def test_missing_smiles_candidate_is_excluded():
    ranked = rank_similar_compounds(
        "CCO",
        [
            SimilarCompound(compound_name="Missing", canonical_smiles="", similarity_score=90, source="Mock"),
            SimilarCompound(compound_name="Valid", canonical_smiles="CCO", similarity_score=100, source="Mock"),
        ],
    )
    assert [item.compound_name for item in ranked] == ["Valid"]


def test_cache_hit_on_repeated_similarity_search(monkeypatch):
    calls = {"count": 0}
    monkeypatch.setattr(similarity_service, "resolve_reference", lambda query, input_type: _reference())

    def fake_similarity(smiles, threshold, limit):
        calls["count"] += 1
        return [
            SimilarCompound(
                compound_name="Analog A",
                molecule_chembl_id="CHEMBL_A",
                canonical_smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
                similarity_score=100,
                source="ChEMBL",
            )
        ]

    monkeypatch.setattr(similarity_service, "_chembl_similarity", fake_similarity)
    payload = {"query": "Aspirin", "input_type": "name", "source": "chembl", "threshold": 70, "limit": 10}
    first = client.post("/api/similarity/search", json=payload)
    second = client.post("/api/similarity/search", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1
    assert second.json()["cache_metadata"]["cache_hit"] is True


def test_screen_selected_endpoint_uses_screening_logic():
    response = client.post(
        "/api/similarity/screen-selected",
        json={
            "selected_compounds": [
                {
                    "compound_name": "Ethanol analog",
                    "canonical_smiles": "CCO",
                    "similarity_score": 80,
                    "source": "Mock",
                }
            ],
            "max_candidates": 10,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["screened_count"] == 1
    assert body["comparison_table"][0]["decision"]
    assert body["comparison_table"][0]["evidence_level"] == "Not evaluated"


def test_project_report_supports_similarity_workflow():
    payload = ProjectReportPayload.model_validate(
        {
            "workflow_type": "similarity_to_candidate",
            "similarity": {
                "reference_query": "Aspirin",
                "reference_compound_name": "Aspirin",
                "reference_pubchem_cid": 2244,
                "reference_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                "source": "auto",
                "threshold": 70,
                "limit": 25,
                "candidates_found": 1,
            },
            "retrieved_candidate_count": 1,
            "selected_candidate_count": 1,
            "screened_candidate_count": 1,
            "batch_screening_results": {
                "comparison_table": [
                    {
                        "compound": "Analog",
                        "pubchem_cid": 123,
                        "similarity_score": 82,
                        "molecular_weight": 180.1,
                        "logp": 1.2,
                        "tpsa": 60,
                        "developability_risk": "Low",
                        "concern_level": "Low",
                        "overall_admet_tox_concern_score": 25,
                        "decision": "Proceed",
                        "final_candidate_priority": "Review analog",
                    }
                ]
            },
        }
    )
    assert payload.workflow_type == "similarity_to_candidate"
    assert build_project_pdf(payload).startswith(b"%PDF")
    assert build_project_docx(payload)[:2] == b"PK"
