from pathlib import Path

from fastapi.testclient import TestClient

from app.database import init_db
from app.main import app
from app.models.schemas import (
    CompoundIdentity,
    DescriptorSet,
    PlaceholderModule,
    RuleEvaluation,
    ScreeningRequest,
    ScreeningReport,
)
from app.services.descriptors import calculate_descriptors
from app.services.history import get_history_detail, list_history, save_screening_report, update_report_id
from app.services import pubchem
from app.services.cache_service import clear_cache
from app.services.pubchem import resolve_compound
from app.services.rules import build_decision, evaluate_rules, plan_experimental_tests


client = TestClient(app)


def setup_function():
    clear_cache()


def test_aspirin_lookup(monkeypatch):
    def fake_get_json(url):
        if url.endswith("/cids/JSON"):
            return {"IdentifierList": {"CID": [2244]}}
        if "/property/" in url:
            return {
                "PropertyTable": {
                    "Properties": [
                        {
                            "CID": 2244,
                            "MolecularFormula": "C9H8O4",
                            "MolecularWeight": "180.16",
                            "SMILES": "CC(=O)OC1=CC=CC=C1C(=O)O",
                            "IUPACName": "2-acetyloxybenzoic acid",
                            "Title": "Aspirin",
                        }
                    ]
                }
            }
        return {"InformationList": {"Information": [{"Synonym": ["Aspirin"]}]}}

    monkeypatch.setattr(pubchem, "_get_json", fake_get_json)
    identity = resolve_compound("Aspirin", "name")
    assert identity.pubchem_cid == 2244
    assert identity.compound_name
    assert identity.canonical_smiles


def test_invalid_smiles_returns_validation_error():
    response = client.post("/api/screen", json={"query": "not-a-valid-smiles", "input_type": "smiles"})
    assert response.status_code == 422
    assert "Invalid SMILES" in response.json()["detail"]


def test_unknown_compound_returns_not_found(monkeypatch):
    from app.routers import screening

    def fake_resolve_compound(query, input_type):
        raise pubchem.PubChemNotFoundError("Compound not found in PubChem.")

    monkeypatch.setattr(screening, "resolve_compound", fake_resolve_compound)
    response = client.post(
        "/api/screen",
        json={"query": "DrugScreen360DefinitelyUnknownCompound999999", "input_type": "name"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_descriptor_calculation_for_aspirin_smiles():
    descriptors = calculate_descriptors("CC(=O)OC1=CC=CC=C1C(=O)O")
    assert 179 < descriptors.molecular_weight < 181
    assert descriptors.hydrogen_bond_donors == 1
    assert descriptors.hydrogen_bond_acceptors == 3


def test_lipinski_and_veber_logic():
    good = calculate_descriptors("CC(=O)OC1=CC=CC=C1C(=O)O")
    good_rules = evaluate_rules(good)
    assert good_rules.lipinski_rule_of_5["passed"] is True
    assert good_rules.veber_rule["passed"] is True
    assert good_rules.basic_drug_likeness_status == "Good"

    poor = DescriptorSet(
        molecular_weight=650,
        logp=7,
        tpsa=170,
        hydrogen_bond_donors=7,
        hydrogen_bond_acceptors=13,
        rotatable_bonds=14,
        formal_charge=1,
        ring_count=8,
        aromatic_ring_count=4,
        fraction_csp3=0.2,
    )
    poor_rules = evaluate_rules(poor)
    assert poor_rules.lipinski_rule_of_5["passed"] is False
    assert poor_rules.veber_rule["passed"] is False
    assert poor_rules.developability_risk == "High"


def test_screening_history_save(monkeypatch, tmp_path):
    import app.database as database

    monkeypatch.setattr(database, "DB_PATH", Path(tmp_path) / "history.sqlite3")
    init_db()

    descriptors = calculate_descriptors("CC(=O)OC1=CC=CC=C1C(=O)O")
    rules = evaluate_rules(descriptors)
    tests = plan_experimental_tests(descriptors, rules)
    report = ScreeningReport(
        disclaimer="test disclaimer",
        input=ScreeningRequest(query="Aspirin", input_type="name"),
        compound_identity=CompoundIdentity(
            compound_name="Aspirin",
            pubchem_cid=2244,
            canonical_smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
            isomeric_smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
            molecular_formula="C9H8O4",
            molecular_weight=180.16,
            iupac_name="2-acetyloxybenzoic acid",
            synonyms=["Aspirin"],
            pubchem_source_link="https://pubchem.ncbi.nlm.nih.gov/compound/2244",
            structure_image_base64=None,
        ),
        physicochemical_properties=descriptors,
        drug_likeness=rules,
        admet_placeholder=PlaceholderModule(status="placeholder", message="placeholder", future_outputs=[]),
        toxicity_placeholder=PlaceholderModule(status="placeholder", message="placeholder", future_outputs=[]),
        required_lab_tests=tests,
        go_no_go_recommendation=build_decision(rules, tests),
        limitations=["test limitation"],
    )

    screening_id = save_screening_report(report)
    update_report_id(screening_id, report)
    detail = get_history_detail(screening_id)

    assert detail is not None
    assert detail.id == screening_id
    assert detail.compound_name == "Aspirin"
    assert detail.report.screening_id == screening_id


def test_clear_screening_history_endpoint(monkeypatch, tmp_path):
    import app.database as database

    monkeypatch.setattr(database, "DB_PATH", Path(tmp_path) / "clear-history.sqlite3")
    init_db()

    descriptors = calculate_descriptors("CC(=O)OC1=CC=CC=C1C(=O)O")
    rules = evaluate_rules(descriptors)
    report = ScreeningReport(
        disclaimer="test disclaimer",
        input=ScreeningRequest(query="Aspirin", input_type="name"),
        compound_identity=CompoundIdentity(
            compound_name="Aspirin",
            pubchem_cid=2244,
            canonical_smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
            isomeric_smiles="CC(=O)OC1=CC=CC=C1C(=O)O",
            molecular_formula="C9H8O4",
            molecular_weight=180.16,
            iupac_name="2-acetyloxybenzoic acid",
            synonyms=["Aspirin"],
            pubchem_source_link="https://pubchem.ncbi.nlm.nih.gov/compound/2244",
            structure_image_base64=None,
        ),
        physicochemical_properties=descriptors,
        drug_likeness=rules,
        admet_placeholder=PlaceholderModule(status="placeholder", message="placeholder", future_outputs=[]),
        toxicity_placeholder=PlaceholderModule(status="placeholder", message="placeholder", future_outputs=[]),
        required_lab_tests=[],
        go_no_go_recommendation=build_decision(rules, []),
        limitations=["test limitation"],
    )
    save_screening_report(report)

    response = client.delete("/api/screening/history")

    assert response.status_code == 200
    assert response.json()["deleted_count"] == 1
    assert list_history() == []
