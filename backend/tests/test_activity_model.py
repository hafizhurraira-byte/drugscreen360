from fastapi.testclient import TestClient

from app.main import app
from app.services import activity_model_service
from app.services.activity_model_service import deactivate_activity_model
from app.models.admet_lead_models import LeadCandidateInput, LeadPrioritizationRequest
from app.services.admet_lead_service import prioritize_leads


client = TestClient(app)


ERLOTINIB = "C#Cc1cccc(Nc2ncnc3cc(OCCOC)c(OCCOC)cc23)c1"


def test_egfr_v2_artifact_integrity_and_gate():
    verification = activity_model_service.verify_egfr_v2_artifact()
    gate = activity_model_service.evaluate_egfr_v2_activation_gate()

    assert verification["valid"] is True
    assert verification["hashes"]["model.joblib"] == activity_model_service.EXPECTED_EGFR_V2_MODEL_HASH
    assert gate["activation_state"] == "ACTIVATION_ELIGIBLE"
    assert any("83.37" in warning for warning in gate["warnings"])


def test_register_activate_predict_and_deactivate_egfr_v2():
    registration = client.post("/api/activity/models/egfr/register", json={}).json()
    gate = client.post("/api/activity/models/egfr/activation-gate").json()
    activated = client.post("/api/activity/models/egfr/activate").json()
    prediction = client.post("/api/activity/egfr/predict", json={"smiles": ERLOTINIB}).json()
    unsupported = client.post("/api/activity/predict", json={"smiles": ERLOTINIB, "target": "ALK"}).json()
    batch = client.post(
        "/api/activity/batch-predict",
        json={"target": "EGFR", "candidates": [{"smiles": ERLOTINIB}, {"smiles": "C1CC"}]},
    ).json()
    deactivated = client.post("/api/activity/models/egfr/deactivate").json()

    assert registration["model_id"] == "egfr_activity_v2"
    assert gate["activation_state"] == "ACTIVATION_ELIGIBLE"
    assert activated["status"] == "ACTIVE"
    assert prediction["status"] == "available"
    assert prediction["target"] == "EGFR"
    assert prediction["evidence_type"] == "MODEL_PREDICTION"
    assert prediction["predicted_pIC50"] > 0
    assert prediction["predicted_IC50_nM"] > 0
    assert prediction["applicability_domain_status"] in {"IN_DOMAIN", "BORDERLINE", "OUT_OF_DOMAIN"}
    assert prediction["uncertainty_method"] == "random_forest_tree_prediction_standard_deviation"
    assert prediction["external_observed_coverage"] == 0.8337
    assert unsupported["status"] == "unavailable"
    assert batch["results"][0]["success"] is True
    assert batch["results"][1]["success"] is False
    assert deactivated["status"] == "DISABLED"


def test_m2_activity_status_reports_target_specific_not_universal():
    deactivate_activity_model("EGFR")
    body = client.get("/api/m2/activity/status").json()

    assert body["model_family"] == "activity"
    assert body["scope"] == "target_specific"
    assert body["supported_targets"][0]["supported_target"] == "EGFR/P00533/CHEMBL203"
    assert "universal" in body["limitations"][0].lower() or "target-specific" in body["limitations"][0].lower()


def test_egfr_ranking_uses_activity_prediction_only_for_egfr():
    client.post("/api/activity/models/egfr/register", json={})
    client.post("/api/activity/models/egfr/activate")
    egfr = prioritize_leads(
        LeadPrioritizationRequest(
            candidates=[LeadCandidateInput(compound_name="Erlotinib", smiles=ERLOTINIB, metadata={"target_name": "EGFR"})],
            include_trained_model=False,
            include_domain=False,
            include_explainability=False,
        )
    ).ranked_candidates[0]
    alk = prioritize_leads(
        LeadPrioritizationRequest(
            candidates=[LeadCandidateInput(compound_name="Erlotinib", smiles=ERLOTINIB, metadata={"target_name": "ALK"})],
            include_trained_model=False,
            include_domain=False,
            include_explainability=False,
        )
    ).ranked_candidates[0]
    deactivate_activity_model("EGFR")

    assert egfr.activity_model_prediction is not None
    assert egfr.score_components.get("egfr_activity_bonus") is not None
    assert alk.activity_model_prediction is None
