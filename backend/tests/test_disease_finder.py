from fastapi.testclient import TestClient

from app.main import app
from app.services.cache_service import clear_cache
from app.services import open_targets_service

client = TestClient(app)


def setup_function():
    clear_cache()


def test_disease_search_response_structure(monkeypatch):
    def fake_graphql(query, variables):
        return {
            "search": {
                "hits": [
                    {
                        "id": "EFO_0000305",
                        "name": "breast carcinoma",
                        "description": "A breast cancer disease match.",
                        "entity": "disease",
                    }
                ]
            }
        }

    monkeypatch.setattr(open_targets_service, "_graphql", fake_graphql)
    response = client.get("/api/disease-finder/diseases?query=breast%20cancer")

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "breast cancer"
    assert body["diseases"][0]["disease_id"] == "EFO_0000305"
    assert body["diseases"][0]["source"] == "Open Targets"


def test_no_disease_found_case(monkeypatch):
    monkeypatch.setattr(open_targets_service, "search_diseases", lambda query: [])
    response = client.get("/api/disease-finder/diseases?query=NoDisease")

    assert response.status_code == 404
    assert "No Open Targets disease matches" in response.json()["detail"]


def test_disease_target_retrieval_response_structure(monkeypatch):
    def fake_graphql(query, variables):
        return {
            "disease": {
                "associatedTargets": {
                    "rows": [
                        {
                            "score": 0.86,
                            "target": {
                                "id": "ENSG00000146648",
                                "approvedSymbol": "EGFR",
                                "approvedName": "epidermal growth factor receptor",
                                "biotype": "protein_coding",
                                "organism": {"scientificName": "Homo sapiens"},
                            },
                            "datatypeScores": [
                                {"id": "known_drug", "score": 0.7},
                                {"id": "genetic_association", "score": 0.4},
                                {"id": "literature", "score": 0.6},
                            ],
                        }
                    ]
                }
            }
        }

    monkeypatch.setattr(open_targets_service, "_graphql", fake_graphql)
    response = client.get("/api/disease-finder/disease/EFO_0000305/targets?limit=10")

    assert response.status_code == 200
    target = response.json()["targets"][0]
    assert target["approved_symbol"] == "EGFR"
    assert target["suggested_chembl_query"] == "EGFR"
    assert target["disease_target_rank"] == 1


def test_target_ranking_logic():
    rows = [
        {
            "score": 0.4,
            "target": {"id": "T2", "approvedSymbol": "LOW", "approvedName": "low target"},
            "datatypeScores": [],
        },
        {
            "score": 0.9,
            "target": {"id": "T1", "approvedSymbol": "HIGH", "approvedName": "high target"},
            "datatypeScores": [{"id": "known_drug", "score": 0.8}],
        },
    ]

    ranked = open_targets_service.rank_disease_targets(rows)
    assert ranked[0].approved_symbol == "HIGH"
    assert ranked[0].final_target_priority_score > ranked[1].final_target_priority_score


def test_open_targets_timeout_error_handling(monkeypatch):
    def fake_search(query):
        raise open_targets_service.OpenTargetsUnavailableError("Open Targets request timed out. Please try again later.")

    monkeypatch.setattr(open_targets_service, "search_diseases", fake_search)
    response = client.get("/api/disease-finder/diseases?query=breast%20cancer")

    assert response.status_code == 503
    assert "timed out" in response.json()["detail"]


def test_integration_shape_between_disease_target_and_chembl_search():
    rows = [
        {
            "score": 0.8,
            "target": {
                "id": "ENSG00000146648",
                "approvedSymbol": "EGFR",
                "approvedName": "epidermal growth factor receptor",
            },
            "datatypeScores": [{"id": "known_drug", "score": 0.5}],
        }
    ]
    target = open_targets_service.rank_disease_targets(rows)[0]
    assert target.suggested_chembl_query == "EGFR"
    assert target.target_id == "ENSG00000146648"
