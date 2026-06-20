from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import (
    CompoundIdentity,
    DescriptorSet,
    PlaceholderModule,
    RecommendedTest,
    RuleEvaluation,
    ScreeningRequest,
    ScreeningReport,
)
from app.services.admet_toxicity_engine import evaluate_admet_toxicity
from app.services.admet_predictor_service import predict_admet
from app.services.reports import build_docx_report, build_pdf_report

client = TestClient(app)


def test_models_status_returns_rule_based_available():
    response = client.get("/api/models/status")
    assert response.status_code == 200
    body = response.json()
    assert any(model["model_id"] == "rule_based_admet_v1" for model in body["available_models"])
    assert any(model["status"] == "unavailable" for model in body["unavailable_models"])


def test_unavailable_placeholder_models_return_unavailable_not_fake_predictions():
    response = client.post(
        "/api/models/predict-admet",
        json={"smiles": "CCO", "models": ["local_admet_model"], "include_unavailable": True},
    )
    assert response.status_code == 200
    output = response.json()["model_outputs"][0]
    assert output["model_status"] == "unavailable"
    assert output["predictions"][0]["prediction_label"] == "not_available"


def test_predict_admet_valid_smiles():
    response = client.post(
        "/api/models/predict-admet",
        json={"smiles": "CCO", "models": ["rule_based_admet_v1"], "include_unavailable": True},
    )
    assert response.status_code == 200
    assert response.json()["canonical_smiles"] == "CCO"
    assert response.json()["model_outputs"][0]["model_status"] == "available"


def test_predict_admet_invalid_smiles_returns_clean_error():
    response = client.post("/api/models/predict-admet", json={"smiles": "C1CC", "models": ["rule_based_admet_v1"]})
    assert response.status_code == 422
    assert "Invalid SMILES" in response.json()["detail"]


def test_model_comparison_handles_unavailable_models():
    response = client.post("/api/models/compare", json={"smiles": "CCO", "selected_models": ["rule_based_admet_v1", "local_admet_model"]})
    assert response.status_code == 200
    body = response.json()
    assert "unavailable" in body["agreement_summary"]


def test_report_includes_prediction_model_status():
    smiles = "CCO"
    admet = evaluate_admet_toxicity(smiles)
    report = ScreeningReport(
        disclaimer="test",
        input=ScreeningRequest(query=smiles, input_type="smiles"),
        compound_identity=CompoundIdentity(
            compound_name="Ethanol",
            pubchem_cid=None,
            canonical_smiles=smiles,
            isomeric_smiles=smiles,
            molecular_formula="C2H6O",
            molecular_weight=46.07,
            iupac_name="ethanol",
            synonyms=[],
            pubchem_source_link=None,
        ),
        physicochemical_properties=DescriptorSet(
            molecular_weight=46.07,
            logp=-0.001,
            tpsa=20.23,
            hydrogen_bond_donors=1,
            hydrogen_bond_acceptors=1,
            rotatable_bonds=0,
            formal_charge=0,
            ring_count=0,
            aromatic_ring_count=0,
            fraction_csp3=1.0,
        ),
        drug_likeness=RuleEvaluation(
            lipinski_rule_of_5={"passed": True},
            veber_rule={"passed": True},
            basic_drug_likeness_status="Good",
            developability_risk="Low",
            reasons=[],
        ),
        admet_placeholder=PlaceholderModule(status="placeholder", message="placeholder", future_outputs=[]),
        toxicity_placeholder=PlaceholderModule(status="placeholder", message="placeholder", future_outputs=[]),
        admet_toxicity_v1=admet,
        model_predictions=predict_admet(smiles, ["rule_based_admet_v1", "local_admet_model"], True),
        required_lab_tests=[RecommendedTest(name="Solubility assay", priority="Standard", reason="test")],
        go_no_go_recommendation={"decision": "Proceed"},
        limitations=[],
    )
    assert build_pdf_report(report).startswith(b"%PDF")
    assert build_docx_report(report)[:2] == b"PK"
