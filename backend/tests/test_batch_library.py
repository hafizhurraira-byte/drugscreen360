from fastapi.testclient import TestClient

from app.main import app
from app.models.batch_library_models import ParsedCompound
from app.services.batch_library_service import parse_library_file, screen_batch_library

client = TestClient(app)


def test_parse_csv_with_valid_smiles():
    content = b"smiles,name,compound_id\nCCO,Ethanol,E1\nCC(=O)O,Acetic acid,A1\n"
    result = parse_library_file("test.csv", content)
    assert result.valid_compounds == 2
    assert result.invalid_compounds == 0


def test_parse_csv_with_invalid_smiles():
    content = b"smiles,name\nC1CC,Bad\nCCO,Good\n"
    result = parse_library_file("invalid.csv", content)
    assert result.valid_compounds == 1
    assert result.invalid_compounds == 1
    assert "Invalid SMILES" in result.parsed_compounds[0].error_reason


def test_parse_smi_file():
    result = parse_library_file("test.smi", b"CCO Ethanol\nCC(=O)O Acetic acid\n")
    assert result.total_rows == 2
    assert result.parsed_compounds[0].compound_name == "Ethanol"


def test_duplicate_detection():
    result = parse_library_file("dupes.smi", b"CCO First\nOCC Second\n")
    assert result.duplicates_detected == 1


def test_invalid_file_type_rejected():
    response = client.post("/api/batch-library/parse", files={"file": ("bad.xyz", b"CCO", "text/plain")})
    assert response.status_code == 415


def test_empty_file_rejected():
    response = client.post("/api/batch-library/parse", files={"file": ("empty.csv", b"", "text/csv")})
    assert response.status_code == 422


def test_screen_parsed_compounds():
    compound = ParsedCompound(row_number=1, compound_name="Ethanol", original_smiles="CCO", canonical_smiles="CCO", valid=True)
    response = screen_batch_library(None, [compound], 100, True)
    assert response.screened_count == 1
    assert response.results[0].evidence_level == "Not evaluated"
    assert response.results[0].batch_rank == 1


def test_batch_ranking_prefers_lower_risk():
    compounds = [
        ParsedCompound(row_number=1, compound_name="Ethanol", original_smiles="CCO", canonical_smiles="CCO", valid=True),
        ParsedCompound(row_number=2, compound_name="Greasy", original_smiles="CCCCCCCCCCCCCCCCCCCC", canonical_smiles="CCCCCCCCCCCCCCCCCCCC", valid=True),
    ]
    response = screen_batch_library(None, compounds, 100, True)
    assert response.results[0].batch_priority_score >= response.results[1].batch_priority_score


def test_batch_library_exports():
    parse_response = client.post(
        "/api/batch-library/parse",
        files={"file": ("test.csv", b"smiles,name\nCCO,Ethanol\n", "text/csv")},
    )
    batch_id = parse_response.json()["batch_id"]
    screen_response = client.post("/api/batch-library/screen", json={"batch_id": batch_id, "max_compounds": 100})
    run_id = screen_response.json()["batch_screening_id"]

    assert client.get(f"/api/batch-library/runs/{run_id}/json").status_code == 200
    csv_response = client.get(f"/api/batch-library/runs/{run_id}/csv")
    assert csv_response.status_code == 200
    assert "compound_name" in csv_response.text
    assert client.get(f"/api/batch-library/runs/{run_id}/pdf").content.startswith(b"%PDF")
    assert client.get(f"/api/batch-library/runs/{run_id}/docx").content[:2] == b"PK"
