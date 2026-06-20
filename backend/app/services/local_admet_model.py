import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.model_registry_models import ModelInfo, ModelPredictionBundle

LOCAL_MODEL_ID = "local_admet_model"
LOCAL_MODEL_NAME = "Local ADMET Model Adapter"
DEFAULT_TASKS = [
    "solubility",
    "permeability",
    "bbb",
    "cyp_inhibition",
    "herg",
    "ames",
    "hepatotoxicity",
    "general_toxicity",
]
NO_IMPLEMENTATION_WARNING = (
    "Local model manifest/artifacts may be present, but no supported predictor implementation is active. "
    "No local model prediction was generated."
)


@dataclass
class LocalAdmetConfig:
    enabled: bool
    model_dir: Path
    timeout_seconds: int


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def get_local_admet_config() -> LocalAdmetConfig:
    raw_dir = os.getenv("LOCAL_ADMET_MODEL_DIR", "backend/models/admet").strip() or "backend/models/admet"
    model_dir = Path(raw_dir)
    if not model_dir.is_absolute():
        model_dir = _project_root() / model_dir
    return LocalAdmetConfig(
        enabled=os.getenv("LOCAL_ADMET_MODEL_ENABLED", "false").lower() == "true",
        model_dir=model_dir,
        timeout_seconds=int(os.getenv("LOCAL_ADMET_MODEL_TIMEOUT_SECONDS", "30") or 30),
    )


def _manifest_path(config: LocalAdmetConfig) -> Path:
    return config.model_dir / "model_manifest.json"


def _read_manifest(config: LocalAdmetConfig) -> dict[str, Any]:
    return json.loads(_manifest_path(config).read_text(encoding="utf-8"))


def _artifact_status(config: LocalAdmetConfig, manifest: dict[str, Any]) -> tuple[bool, list[str]]:
    artifact_files = manifest.get("artifact_files") or []
    missing = [str(name) for name in artifact_files if not (config.model_dir / str(name)).exists()]
    return len(missing) == 0, missing


def _info(
    *,
    config: LocalAdmetConfig,
    status: str,
    tasks: list[str] | None = None,
    version: str | None = None,
    limitations: list[str] | None = None,
    warning: str | None = None,
    manifest_found: bool = False,
    artifacts_found: bool = False,
) -> ModelInfo:
    return ModelInfo(
        model_id=LOCAL_MODEL_ID,
        model_name=LOCAL_MODEL_NAME,
        model_type="local_model_adapter",
        prediction_tasks=tasks or DEFAULT_TASKS,
        status=status,
        input_type="smiles",
        version=version,
        source="Local model directory",
        limitations=limitations or ["No real local ADMET model is active."],
        last_checked_at=_now(),
        enabled=config.enabled,
        model_dir=str(config.model_dir),
        manifest_found=manifest_found,
        artifacts_found=artifacts_found,
        warning=warning,
    )


def check_local_admet_model_status() -> ModelInfo:
    config = get_local_admet_config()
    manifest_path = _manifest_path(config)
    if not config.enabled:
        return _info(
            config=config,
            status="disabled",
            warning="Local ADMET model is disabled by LOCAL_ADMET_MODEL_ENABLED=false.",
            manifest_found=manifest_path.exists(),
            artifacts_found=False,
        )
    if not manifest_path.exists():
        return _info(
            config=config,
            status="unavailable",
            warning="Local ADMET model is enabled, but model_manifest.json was not found.",
            manifest_found=False,
            artifacts_found=False,
        )
    try:
        manifest = _read_manifest(config)
    except json.JSONDecodeError as exc:
        return _info(
            config=config,
            status="error",
            warning=f"Local ADMET model manifest is invalid JSON: {exc}",
            manifest_found=True,
            artifacts_found=False,
        )
    tasks = [str(task) for task in manifest.get("tasks") or DEFAULT_TASKS]
    limitations = [str(manifest.get("limitations") or "Local model limitations were not provided.")]
    artifacts_found, missing = _artifact_status(config, manifest)
    if not artifacts_found:
        return _info(
            config=config,
            status="unavailable",
            tasks=tasks,
            version=str(manifest.get("version")) if manifest.get("version") else None,
            limitations=limitations,
            warning=f"Local ADMET model artifacts are missing: {', '.join(missing)}",
            manifest_found=True,
            artifacts_found=False,
        )
    return _info(
        config=config,
        status="unavailable",
        tasks=tasks,
        version=str(manifest.get("version")) if manifest.get("version") else None,
        limitations=limitations + ["A supported local predictor loader has not been implemented yet."],
        warning=NO_IMPLEMENTATION_WARNING,
        manifest_found=True,
        artifacts_found=True,
    )


def predict_local_admet(smiles: str) -> ModelPredictionBundle:
    info = check_local_admet_model_status()
    return ModelPredictionBundle(
        model_id=info.model_id,
        model_name=info.model_name,
        model_status=info.status,
        prediction_source="Local model unavailable",
        confidence="None",
        predictions=[],
        raw_output=None,
        warnings=[info.warning or "Local ADMET model is unavailable. No prediction was generated."],
        limitations=info.limitations,
        metadata={
            "enabled": info.enabled,
            "model_dir": info.model_dir,
            "manifest_found": info.manifest_found,
            "artifacts_found": info.artifacts_found,
        },
    )
