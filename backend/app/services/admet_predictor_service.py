import json

from fastapi import HTTPException
from rdkit import Chem

from app.constants import DISCLAIMER
from app.database import get_connection, init_db
from app.models.model_registry_models import CompareModelsResponse, ModelPredictionBundle, PredictAdmetResponse
from app.services.descriptors import parse_smiles
from app.services.model_registry import get_adapters


def _canonical_smiles(smiles: str) -> str:
    mol = parse_smiles(smiles)
    canonical = Chem.MolToSmiles(mol, canonical=True)
    if not canonical:
        raise HTTPException(status_code=422, detail="Invalid SMILES: canonicalization failed.")
    return canonical


def log_prediction(smiles: str, bundle: ModelPredictionBundle) -> None:
    init_db()
    with get_connection() as connection:
        for prediction in bundle.predictions:
            connection.execute(
                """
                INSERT INTO model_prediction_logs (
                    smiles, model_id, task_name, prediction_label, prediction_score,
                    confidence, status, warnings_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    smiles,
                    bundle.model_id,
                    prediction.task_name,
                    prediction.prediction_label,
                    prediction.prediction_score,
                    prediction.confidence,
                    bundle.model_status,
                    json.dumps(prediction.warnings),
                ),
            )


def predict_admet(smiles: str, model_ids: list[str], include_unavailable: bool = True) -> PredictAdmetResponse:
    canonical = _canonical_smiles(smiles)
    outputs = []
    warnings = []
    for adapter in get_adapters(model_ids):
        if not adapter.is_available() and not include_unavailable:
            continue
        bundle = adapter.predict(canonical)
        outputs.append(bundle)
        warnings.extend(bundle.warnings)
        log_prediction(canonical, bundle)
    if not outputs:
        warnings.append("No requested models are available.")
    real_available = any(item.model_status == "available" and item.model_id != "rule_based_admet_v1" for item in outputs)
    mock_used = any(item.model_status == "mock" for item in outputs)
    rule_based_used = any(item.model_id == "rule_based_admet_v1" and item.model_status == "available" for item in outputs)
    external_bundle = next((item for item in outputs if item.model_id == "external_admet_provider_v1"), None)
    local_bundle = next((item for item in outputs if item.model_id == "local_admet_model"), None)
    trained_bundle = next((item for item in outputs if item.model_id == "trained_local_admet_model"), None)
    external_warning = "; ".join(external_bundle.warnings) if external_bundle and external_bundle.warnings else None
    local_warning = "; ".join(local_bundle.warnings) if local_bundle and local_bundle.warnings else None
    trained_warning = "; ".join(trained_bundle.warnings) if trained_bundle and trained_bundle.warnings else None
    model_status_summary = {
        "rule_based_used": rule_based_used,
        "external_model_used": bool(external_bundle and external_bundle.model_status in {"available", "mock"}),
        "external_model_available": bool(external_bundle and external_bundle.model_status == "available"),
        "external_model_status": external_bundle.model_status if external_bundle else "not_requested",
        "external_model_warning": external_warning,
        "local_model_used": bool(local_bundle and local_bundle.model_status == "available"),
        "local_model_available": bool(local_bundle and local_bundle.model_status == "available"),
        "local_model_status": local_bundle.model_status if local_bundle else "not_requested",
        "local_model_warning": local_warning,
        "trained_model_used": bool(trained_bundle and trained_bundle.model_status == "available"),
        "trained_model_available": bool(trained_bundle and trained_bundle.model_status == "available"),
        "trained_model_status": trained_bundle.model_status if trained_bundle else "not_requested",
        "trained_model_warning": trained_warning,
        "mock_provider_used": mock_used,
    }
    interpretation = (
        "Rule-based ADMET/Tox output plus available model outputs. Review disagreements cautiously."
        if real_available

        else "Only rule-based ADMET/Tox screening is available. No validated ML toxicity model is currently active."
    )
    if mock_used:
        interpretation += " Mock predictions are active for software testing only and are not scientifically valid."
    return PredictAdmetResponse(
        canonical_smiles=canonical,
        model_outputs=outputs,
        combined_interpretation=interpretation,
        warnings=list(dict.fromkeys(warnings)),
        model_status_summary=model_status_summary,
        disclaimer=DISCLAIMER,
    )


def compare_models(smiles: str, model_ids: list[str]) -> CompareModelsResponse:
    response = predict_admet(smiles, model_ids, include_unavailable=True)
    available = [item for item in response.model_outputs if item.model_status in {"available", "mock"}]
    unavailable = [item for item in response.model_outputs if item.model_status not in {"available", "mock"}]
    agreement = (
        f"{len(available)} available model output(s), {len(unavailable)} unavailable model adapter(s). "
        "No real ML/external model agreement can be assessed unless additional available models are configured."
    )
    return CompareModelsResponse(
        canonical_smiles=response.canonical_smiles,
        model_outputs=response.model_outputs,
        agreement_summary=agreement,
        final_cautious_interpretation=response.combined_interpretation,
        disclaimer=response.disclaimer,
    )
