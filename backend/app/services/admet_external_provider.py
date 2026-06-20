import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from app.models.model_registry_models import ModelInfo, ModelPredictionBundle, PredictionResult
from app.services.mock_admet_provider import MOCK_WARNING, mock_predict

PROVIDER_TASKS = ["solubility", "permeability", "bbb", "cyp_inhibition", "herg", "ames", "hepatotoxicity", "general_toxicity"]


@dataclass
class ExternalProviderConfig:
    enabled: bool
    base_url: str
    api_key: str
    timeout_seconds: int
    mock_mode: bool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_external_provider_config() -> ExternalProviderConfig:
    return ExternalProviderConfig(
        enabled=os.getenv("ADMET_PROVIDER_ENABLED", "false").lower() == "true",
        base_url=os.getenv("ADMET_PROVIDER_BASE_URL", "").strip().rstrip("/"),
        api_key=os.getenv("ADMET_PROVIDER_API_KEY", "").strip(),
        timeout_seconds=int(os.getenv("ADMET_PROVIDER_TIMEOUT_SECONDS", "30") or 30),
        mock_mode=os.getenv("ADMET_PROVIDER_MOCK_MODE", "false").lower() == "true",
    )


def _headers(config: ExternalProviderConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    return headers


def check_external_provider_status() -> ModelInfo:
    config = get_external_provider_config()
    if config.mock_mode:
        return ModelInfo(
            model_id="external_admet_provider_v1",
            model_name="External ADMET Provider Adapter",
            model_type="external_api",
            prediction_tasks=PROVIDER_TASKS,
            status="mock",
            version="mock",
            source="Mock provider",
            limitations=[MOCK_WARNING],
            last_checked_at=_now(),
            base_url_configured=bool(config.base_url),
            api_key_configured=bool(config.api_key),
            warning=MOCK_WARNING,
        )
    if not config.enabled or not config.base_url:
        return ModelInfo(
            model_id="external_admet_provider_v1",
            model_name="External ADMET Provider Adapter",
            model_type="external_api",
            prediction_tasks=PROVIDER_TASKS,
            status="unavailable",
            version=None,
            source="External configured provider",
            limitations=["External ADMET provider is not configured."],
            last_checked_at=_now(),
            base_url_configured=bool(config.base_url),
            api_key_configured=bool(config.api_key),
            warning="External ADMET provider is not configured.",
        )
    try:
        response = requests.get(f"{config.base_url}/health", headers=_headers(config), timeout=config.timeout_seconds)
        if response.status_code >= 400:
            return _error_info(config, f"External ADMET provider health check returned HTTP {response.status_code}.")
    except requests.Timeout:
        return _error_info(config, "External ADMET provider health check timed out.")
    except requests.RequestException as exc:
        return _error_info(config, f"External ADMET provider health check failed: {exc}")
    return ModelInfo(
        model_id="external_admet_provider_v1",
        model_name="External ADMET Provider Adapter",
        model_type="external_api",
        prediction_tasks=PROVIDER_TASKS,
        status="available",
        version=None,
        source=config.base_url,
        limitations=["External provider output depends on the configured service and its validation status."],
        last_checked_at=_now(),
        base_url_configured=True,
        api_key_configured=bool(config.api_key),
        warning=None,
    )


def _error_info(config: ExternalProviderConfig, warning: str) -> ModelInfo:
    return ModelInfo(
        model_id="external_admet_provider_v1",
        model_name="External ADMET Provider Adapter",
        model_type="external_api",
        prediction_tasks=PROVIDER_TASKS,
        status="error",
        version=None,
        source=config.base_url or "External configured provider",
        limitations=["External ADMET provider is configured but failing."],
        last_checked_at=_now(),
        base_url_configured=bool(config.base_url),
        api_key_configured=bool(config.api_key),
        warning=warning,
    )


def predict_external_admet(smiles: str) -> ModelPredictionBundle:
    config = get_external_provider_config()
    info = check_external_provider_status()
    if info.status == "mock":
        return _bundle_from_provider_response(smiles, mock_predict(smiles), "mock", "Mock provider", [MOCK_WARNING], {"data_source": "mock"})
    if info.status != "available":
        return _unavailable_bundle(info)
    try:
        response = requests.post(
            f"{config.base_url}/predict",
            headers=_headers(config),
            json={"smiles": smiles, "tasks": PROVIDER_TASKS},
            timeout=config.timeout_seconds,
        )
        if response.status_code >= 400:
            return _error_bundle(info, f"External ADMET provider returned HTTP {response.status_code}.")
        data = response.json()
    except requests.Timeout:
        return _error_bundle(info, "External ADMET provider prediction timed out.")
    except (requests.RequestException, ValueError) as exc:
        return _error_bundle(info, f"External ADMET provider prediction failed: {exc}")
    try:
        return _bundle_from_provider_response(smiles, data, "available", "External ADMET provider", [], {"base_url_configured": True})
    except (KeyError, TypeError, ValueError) as exc:
        return _error_bundle(info, f"External ADMET provider response could not be parsed: {exc}")


def _bundle_from_provider_response(smiles: str, data: dict[str, Any], status: str, source: str, extra_warnings: list[str], metadata: dict[str, Any]) -> ModelPredictionBundle:
    predictions = []
    for item in data.get("predictions", []):
        task = item["task_name"]
        predictions.append(
            PredictionResult(
                task_name=task,
                prediction_label=str(item.get("prediction_label", "not_available")),
                prediction_score=item.get("prediction_score"),
                probability=item.get("probability"),
                confidence=str(item.get("confidence", "unknown")),
                model_id="external_admet_provider_v1",
                model_name=data.get("model_name") or "External ADMET Provider Adapter",
                model_status=status,
                limitations=[str(item.get("limitations", "External provider limitations were not supplied."))],
                warnings=[],
            )
        )
    if not predictions:
        raise ValueError("missing predictions")
    warnings = list(data.get("warnings") or []) + extra_warnings
    return ModelPredictionBundle(
        model_id="external_admet_provider_v1",
        model_name=data.get("model_name") or "External ADMET Provider Adapter",
        model_status=status,
        prediction_source=source,
        confidence="provider_supplied" if status == "available" else "none",
        predictions=predictions,
        raw_output=data,
        warnings=warnings,
        limitations=["External provider predictions are not clinical or regulatory validation."] + (extra_warnings or []),
        metadata=metadata,
    )


def _unavailable_bundle(info: ModelInfo) -> ModelPredictionBundle:
    return ModelPredictionBundle(
        model_id=info.model_id,
        model_name=info.model_name,
        model_status=info.status,
        prediction_source="External provider unavailable",
        confidence="None",
        predictions=[
            PredictionResult(
                task_name=task,
                prediction_label="not_available",
                confidence="None",
                model_id=info.model_id,
                model_name=info.model_name,
                model_status=info.status,
                limitations=info.limitations,
                warnings=[info.warning or "External ADMET provider is unavailable."],
            )
            for task in PROVIDER_TASKS
        ],
        warnings=[info.warning or "External ADMET provider is not configured."],
        limitations=info.limitations,
        metadata={"base_url_configured": info.base_url_configured, "api_key_configured": info.api_key_configured},
    )


def _error_bundle(info: ModelInfo, warning: str) -> ModelPredictionBundle:
    info.status = "error"
    info.warning = warning
    return _unavailable_bundle(info)
