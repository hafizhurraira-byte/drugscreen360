from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import (
    CompoundIdentity,
    PlaceholderModule,
    ScreeningRequest,
    ScreeningReport,
)
from app.services.admet_toxicity_engine import evaluate_admet_toxicity
from app.services.admet_lead_service import _toxicity_evidence_summary
from app.services.descriptors import calculate_descriptors
from app.services.reports import build_docx_report, build_pdf_report
from app.services.rules import build_decision, evaluate_rules, plan_experimental_tests

client = TestClient(app)


def _sample_report(smiles: str = "CC(=O)OC1=CC=CC=C1C(=O)O") -> ScreeningReport:
    descriptors = calculate_descriptors(smiles)
    rules = evaluate_rules(descriptors)
    tests = plan_experimental_tests(descriptors, rules)
    return ScreeningReport(
        disclaimer="test disclaimer",
        input=ScreeningRequest(query=smiles, input_type="smiles"),
        compound_identity=CompoundIdentity(
            compound_name="Test compound",
            pubchem_cid=None,
            canonical_smiles=smiles,
            isomeric_smiles=smiles,
            molecular_formula=None,
            molecular_weight=descriptors.molecular_weight,
            iupac_name=None,
            synonyms=[],
            pubchem_source_link=None,
        ),
        physicochemical_properties=descriptors,
        drug_likeness=rules,
        admet_placeholder=PlaceholderModule(status="placeholder", message="placeholder", future_outputs=[]),
        toxicity_placeholder=PlaceholderModule(status="placeholder", message="placeholder", future_outputs=[]),
        admet_toxicity_v1=evaluate_admet_toxicity(smiles, descriptors),
        required_lab_tests=tests,
        go_no_go_recommendation=build_decision(rules, tests),
        limitations=["test limitation"],
    )


def test_low_risk_example_aspirin():
    assessment = evaluate_admet_toxicity("CC(=O)OC1=CC=CC=C1C(=O)O")
    assert assessment.absorption.absorption_risk == "Low"
    assert assessment.solubility.solubility_risk == "Low"
    assert assessment.herg_status.prediction_status == "Not implemented"


def test_high_mw_high_logp_gives_absorption_and_solubility_warnings():
    assessment = evaluate_admet_toxicity("CCCCCCCCCCCCCCCCCCCCc1ccccc1c2ccccc2c3ccccc3")
    assert assessment.absorption.absorption_risk in {"Medium", "High"}
    assert assessment.solubility.solubility_risk in {"Medium", "High"}
    assert assessment.overall.overall_admet_tox_concern_score >= 35


def test_nitro_aromatic_structural_alert():
    assessment = evaluate_admet_toxicity("O=[N+]([O-])c1ccccc1")
    assert "Nitro aromatic alert" in assessment.structural_alerts.structural_alerts
    assert assessment.structural_alerts.structural_alert_risk == "Medium"


def test_toxicity_evidence_summary_reports_endpoint_concerns_without_fake_predictions():
    assessment = evaluate_admet_toxicity("O=[N+]([O-])c1ccccc1")
    summary = assessment.toxicity_evidence_summary
    assert summary.toxicity_evidence_source == "rule-based"
    assert summary.ames_mutagenicity_concern == "Medium"
    assert summary.structural_toxicophore_concern == "Medium"
    assert summary.toxicity_concern_level in {"Low", "Medium", "High"}
    assert summary.recommended_followup_assay
    assert "no trained toxicity model prediction is inferred" in summary.evidence_note


def test_toxicity_evidence_summary_labels_real_trained_model_source_only_when_present():
    assessment = evaluate_admet_toxicity("O=[N+]([O-])c1ccccc1")
    summary = _toxicity_evidence_summary(
        assessment,
        {
            "model_available": True,
            "endpoint_predicted": "Ames mutagenicity",
            "prediction_label": "positive",
            "confidence_level": "Medium",
        },
    )
    assert summary["toxicity_evidence_source"] == "trained local model"
    assert summary["trained_model_endpoint"] == "Ames mutagenicity"
    assert summary["trained_model_prediction"] == "positive"


def test_admet_endpoint_invalid_smiles_returns_clean_error():
    response = client.post("/api/admet/evaluate", json={"smiles": "not-a-valid-smiles"})
    assert response.status_code == 422
    assert "Invalid SMILES" in response.json()["detail"]


def test_admet_tox_included_in_single_screening_response(monkeypatch):
    from app.routers import screening

    smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    monkeypatch.setattr(
        screening,
        "resolve_compound",
        lambda query, input_type: CompoundIdentity(
            compound_name="Aspirin-like",
            pubchem_cid=None,
            canonical_smiles=smiles,
            isomeric_smiles=smiles,
            molecular_formula=None,
            molecular_weight=180.16,
            iupac_name=None,
            synonyms=[],
            pubchem_source_link=None,
        ),
    )
    response = client.post(
        "/api/screen",
        json={"query": smiles, "input_type": "smiles"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["admet_toxicity_v1"]["overall"]["confidence_level"] in {"Low", "Medium"}


def test_admet_tox_included_in_batch_screening_response():
    response = client.post(
        "/api/finder/screen-candidates",
        json={
            "max_candidates": 10,
            "candidates": [
                {
                    "candidate_rank": 1,
                    "molecule_chembl_id": "CHEMBL_TEST",
                    "compound_name": "Aspirin-like",
                    "canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                }
            ],
        },
    )
    assert response.status_code == 200
    row = response.json()["comparison_table"][0]
    assert "overall_admet_tox_concern_score" in row
    assert "final_candidate_priority" in row


def test_pdf_docx_export_does_not_fail_with_admet_tox_section():
    report = _sample_report()
    assert build_pdf_report(report).startswith(b"%PDF")
    assert build_docx_report(report).startswith(b"PK")
