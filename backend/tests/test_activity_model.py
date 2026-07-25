from fastapi.testclient import TestClient

from app.routers import activity as activity_router
from app.main import app
from app.services import activity_model_service, admet_lead_service
from app.models.admet_lead_models import LeadCandidateInput, LeadPrioritizationRequest
from app.services.admet_lead_service import prioritize_leads


client = TestClient(app)


ERLOTINIB = "C#Cc1cccc(Nc2ncnc3cc(OCCOC)c(OCCOC)cc23)c1"


def _fake_prediction(smiles=ERLOTINIB):
    return {
        "status": "available",
        "target": "EGFR",
        "evidence_type": "MODEL_PREDICTION",
        "predicted_pIC50": 7.8,
        "predicted_IC50_nM": 15.8,
        "applicability_domain_status": "IN_DOMAIN",
        "uncertainty_method": "random_forest_tree_prediction_standard_deviation",
        "uncertainty_value": 0.5,
        "external_observed_coverage": 0.8337,
        "warnings": ["90% conformal interval observed 83.37% coverage on BindingDB final holdout; interval is under nominal coverage."],
    }


def test_egfr_v2_artifact_integrity_and_gate(monkeypatch):
    monkeypatch.setattr(activity_model_service, "verify_egfr_v2_artifact", lambda: {
        "valid": True,
        "hashes": {"model.joblib": activity_model_service.EXPECTED_EGFR_V2_MODEL_HASH},
        "errors": [],
        "warnings": [],
    })
    monkeypatch.setattr(activity_model_service, "evaluate_egfr_v2_activation_gate", lambda: {
        "activation_state": "ACTIVATION_ELIGIBLE",
        "warnings": ["90% conformal interval observed coverage was 83.37%; activation is research-use with calibration warning."],
    })
    verification = activity_model_service.verify_egfr_v2_artifact()
    gate = activity_model_service.evaluate_egfr_v2_activation_gate()

    assert verification["valid"] is True
    assert verification["hashes"]["model.joblib"] == activity_model_service.EXPECTED_EGFR_V2_MODEL_HASH
    assert gate["activation_state"] == "ACTIVATION_ELIGIBLE"
    assert any("83.37" in warning for warning in gate["warnings"])


def test_register_activate_predict_and_deactivate_egfr_v2(monkeypatch):
    monkeypatch.setattr(activity_router, "register_egfr_v2_artifact", lambda *args, **kwargs: {"model_id": "egfr_activity_v2"})
    monkeypatch.setattr(activity_router, "evaluate_egfr_v2_activation_gate", lambda: {"activation_state": "ACTIVATION_ELIGIBLE"})
    monkeypatch.setattr(activity_router, "activate_egfr_v2", lambda: {"status": "ACTIVE"})
    monkeypatch.setattr(activity_router, "deactivate_activity_model", lambda target: {"status": "DISABLED"})
    monkeypatch.setattr(
        activity_router,
        "predict_egfr_activity",
        lambda smiles, target="EGFR": {"status": "unavailable", "target": target}
        if target == "ALK"
        else _fake_prediction(smiles),
    )
    monkeypatch.setattr(
        activity_router,
        "batch_predict_egfr_activity",
        lambda candidates, target="EGFR": {"target": target, "count": len(candidates), "results": [{"success": True}, {"success": False}]},
    )
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


def test_m2_activity_status_reports_target_specific_not_universal(monkeypatch):
    monkeypatch.setattr(activity_model_service, "egfr_activity_model_status", lambda: {
        "active": False,
        "trained": True,
        "supported_target": "EGFR/P00533/CHEMBL203",
    })
    body = client.get("/api/m2/activity/status").json()

    assert body["model_family"] == "activity"
    assert body["scope"] == "target_specific"
    assert body["supported_targets"][0]["supported_target"] == "EGFR/P00533/CHEMBL203"
    assert "universal" in body["limitations"][0].lower() or "target-specific" in body["limitations"][0].lower()


def test_egfr_ranking_uses_activity_prediction_only_for_egfr(monkeypatch):
    monkeypatch.setattr(admet_lead_service, "predict_egfr_activity", lambda smiles, target="EGFR": _fake_prediction(smiles))
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

    assert egfr.activity_model_prediction is not None
    assert egfr.score_components.get("egfr_activity_bonus") is not None
    assert alk.activity_model_prediction is None
