from fastapi.testclient import TestClient

from app.main import app
from app.models.finder_models import CandidateMolecule
from app.services.candidate_ranker import rank_candidates, remove_duplicate_molecules
from app.services import chembl_service
from app.services.cache_service import clear_cache
from app.services.target_ranker import rank_targets

client = TestClient(app)


def setup_function():
    clear_cache()


def test_target_search_route_response_structure_with_mocked_chembl(monkeypatch):
    def fake_get_json(path, params):
        assert path == "target/search"
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
    response = client.get("/api/finder/targets?query=EGFR")

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "EGFR"
    assert body["targets"][0]["target_chembl_id"] == "CHEMBL203"
    assert body["targets"][0]["accession"] == "P00533"
    assert body["targets"][0]["target_priority_label"] == "Best match"


def test_egfr_target_ranking_prefers_human_single_protein_over_interactions(monkeypatch):
    def fake_get_json(path, params):
        return {
            "targets": [
                {
                    "target_chembl_id": "CHEMBL4523747",
                    "pref_name": "EGFR/PPP1CA",
                    "organism": "Homo sapiens",
                    "target_type": "PROTEIN-PROTEIN INTERACTION",
                    "target_components": [{"accession": "P00533"}],
                },
                {
                    "target_chembl_id": "CHEMBL203",
                    "pref_name": "Epidermal growth factor receptor",
                    "organism": "Homo sapiens",
                    "target_type": "SINGLE PROTEIN",
                    "target_components": [{"accession": "P00533"}],
                },
            ]
        }

    monkeypatch.setattr(chembl_service, "_get_json", fake_get_json)
    response = client.get("/api/finder/targets?query=EGFR")

    assert response.status_code == 200
    targets = response.json()["targets"]
    assert targets[0]["target_chembl_id"] == "CHEMBL203"
    assert targets[0]["target_priority_score"] > targets[1]["target_priority_score"]


def test_human_single_protein_ranks_above_mouse_single_protein():
    ranked = rank_targets(
        [
            chembl_service.TargetResult(
                target_chembl_id="CHEMBL_MOUSE",
                preferred_name="Epidermal growth factor receptor",
                organism="Mus musculus",
                target_type="SINGLE PROTEIN",
                accession="Q01279",
            ),
            chembl_service.TargetResult(
                target_chembl_id="CHEMBL_HUMAN",
                preferred_name="Epidermal growth factor receptor",
                organism="Homo sapiens",
                target_type="SINGLE PROTEIN",
                accession="P00533",
            ),
        ],
        "EGFR",
    )

    assert ranked[0].target_chembl_id == "CHEMBL_HUMAN"


def test_protein_interaction_ranks_below_single_protein():
    ranked = rank_targets(
        [
            chembl_service.TargetResult(
                target_chembl_id="CHEMBL_PPI",
                preferred_name="EGFR/PPP1CA",
                organism="Homo sapiens",
                target_type="PROTEIN-PROTEIN INTERACTION",
                accession="P00533",
            ),
            chembl_service.TargetResult(
                target_chembl_id="CHEMBL_SINGLE",
                preferred_name="Epidermal growth factor receptor",
                organism="Homo sapiens",
                target_type="SINGLE PROTEIN",
                accession="P00533",
            ),
        ],
        "EGFR",
    )

    assert ranked[0].target_chembl_id == "CHEMBL_SINGLE"


def test_candidate_ranking_logic():
    candidates = [
        CandidateMolecule(
            molecule_chembl_id="CHEMBL_SLOW",
            canonical_smiles="CCO",
            activity_type="IC50",
            activity_value=1000,
            activity_units="nM",
            target_chembl_id="CHEMBL_TARGET",
        ),
        CandidateMolecule(
            molecule_chembl_id="CHEMBL_FAST",
            canonical_smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
            activity_type="IC50",
            activity_value=5,
            activity_units="nM",
            target_chembl_id="CHEMBL_TARGET",
        ),
    ]

    ranked = rank_candidates(candidates)
    assert ranked[0].molecule_chembl_id == "CHEMBL_FAST"
    assert ranked[0].candidate_rank == 1
    assert ranked[0].potency_score > ranked[1].potency_score


def test_duplicate_molecule_removal_keeps_best_potency():
    candidates = [
        CandidateMolecule(
            molecule_chembl_id="CHEMBL_DUP",
            canonical_smiles="CCO",
            activity_type="IC50",
            activity_value=100,
            activity_units="nM",
            target_chembl_id="CHEMBL_TARGET",
        ),
        CandidateMolecule(
            molecule_chembl_id="CHEMBL_DUP",
            canonical_smiles="CCO",
            activity_type="IC50",
            activity_value=10,
            activity_units="nM",
            target_chembl_id="CHEMBL_TARGET",
        ),
    ]

    deduped = remove_duplicate_molecules(candidates)
    assert len(deduped) == 1
    assert deduped[0].activity_value == 10


def test_batch_screening_invalid_smiles_handling():
    response = client.post(
        "/api/finder/screen-candidates",
        json={
            "max_candidates": 10,
            "candidates": [
                {
                    "molecule_chembl_id": "CHEMBL_BAD",
                    "compound_name": "Bad molecule",
                    "canonical_smiles": "not-a-valid-smiles",
                }
            ],
        },
    )
    assert response.status_code == 422
    assert "Invalid SMILES" in response.json()["detail"]


def test_batch_screening_endpoint():
    response = client.post(
        "/api/finder/screen-candidates",
        json={
            "max_candidates": 10,
            "candidates": [
                {
                    "molecule_chembl_id": "CHEMBL_ASPIRIN",
                    "compound_name": "Aspirin-like candidate",
                    "canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                    "activity_type": "IC50",
                    "activity_value": 20,
                    "activity_units": "nM",
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["screened_count"] == 1
    assert body["comparison_table"][0]["molecule_chembl_id"] == "CHEMBL_ASPIRIN"
    assert body["comparison_table"][0]["lipinski_pass"] is True


def test_no_target_found_case(monkeypatch):
    monkeypatch.setattr(chembl_service, "search_targets", lambda query: [])
    response = client.get("/api/finder/targets?query=DefinitelyNoTarget")

    assert response.status_code == 404
    assert "No ChEMBL targets found" in response.json()["detail"]


def test_no_candidates_response_is_clean(monkeypatch):
    monkeypatch.setattr(chembl_service, "get_target_candidates", lambda target_chembl_id, limit=50: [])

    response = client.get("/api/finder/target/CHEMBL_EMPTY/candidates")

    assert response.status_code == 404
    assert "No usable ChEMBL candidates found" in response.json()["detail"]
