import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.model_registry_models import ModelInfo, ModelPredictionBundle

LOCAL_MODEL_ID = "local_admet_model"
LOCAL_MODEL_NAME = "Local ADMET Model Adapter"
SUPPORTED_ARTIFACT_EXTENSIONS = {".pkl", ".joblib", ".onnx", ".json"}
REQUIRED_MANIFEST_FIELDS = {
    "model_id",
    "model_name",
    "version",
    "tasks",
    "input_type",
    "limitations",
    "artifact_files",
}
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


def validate_local_admet_model() -> dict[str, Any]:
    config = get_local_admet_config()
    manifest_path = _manifest_path(config)
    errors: list[str] = []
    warnings: list[str] = []
    next_steps: list[str] = []
    manifest: dict[str, Any] | None = None
    manifest_valid = False
    artifact_count = 0
    artifacts_found = False
    missing_artifacts: list[str] = []
    supported_tasks: list[str] = []
    unsupported_artifacts: list[str] = []
    input_type = None
    version = None
    limitations = None

    if not config.enabled:
        warnings.append("Local ADMET model is disabled by LOCAL_ADMET_MODEL_ENABLED=false.")
        next_steps.append("Set LOCAL_ADMET_MODEL_ENABLED=true only after placing a real validated model manifest and artifacts.")

    if not manifest_path.exists():
        warnings.append("model_manifest.json was not found. model_manifest.example.json is documentation only.")
        next_steps.append("Create backend/models/admet/model_manifest.json from model_manifest.example.json when a real model is ready.")
        return {
            "status": "disabled" if not config.enabled else "unavailable",
            "enabled": config.enabled,
            "model_dir": str(config.model_dir),
            "manifest_path": str(manifest_path),
            "manifest_found": False,
            "manifest_valid": False,
            "artifact_count": 0,
            "artifacts_found": False,
            "missing_artifacts": [],
            "supported_tasks": [],
            "input_type": None,
            "version": None,
            "limitations": None,
            "errors": errors,
            "warnings": warnings,
            "next_steps": next_steps,
        }

    try:
        manifest = _read_manifest(config)
    except json.JSONDecodeError as exc:
        errors.append(f"model_manifest.json is invalid JSON: {exc}")
        next_steps.append("Fix model_manifest.json so it is valid JSON.")
        return {
            "status": "error",
            "enabled": config.enabled,
            "model_dir": str(config.model_dir),
            "manifest_path": str(manifest_path),
            "manifest_found": True,
            "manifest_valid": False,
            "artifact_count": 0,
            "artifacts_found": False,
            "missing_artifacts": [],
            "supported_tasks": [],
            "input_type": None,
            "version": None,
            "limitations": None,
            "errors": errors,
            "warnings": warnings,
            "next_steps": next_steps,
        }

    missing_fields = sorted(REQUIRED_MANIFEST_FIELDS - set(manifest.keys()))
    if missing_fields:
        errors.append(f"Missing required manifest field(s): {', '.join(missing_fields)}")
    tasks = manifest.get("tasks")
    artifact_files = manifest.get("artifact_files")
    if not isinstance(tasks, list) or not tasks:
        errors.append("Manifest field 'tasks' must be a non-empty list.")
    if not isinstance(artifact_files, list):
        errors.append("Manifest field 'artifact_files' must be a list.")

    supported_tasks = [str(task) for task in tasks] if isinstance(tasks, list) else []
    artifact_names = [str(item) for item in artifact_files] if isinstance(artifact_files, list) else []
    artifact_count = len(artifact_names)
    input_type = manifest.get("input_type")
    version = manifest.get("version")
    limitations = manifest.get("limitations")

    if artifact_count == 0:
        warnings.append("No artifact files are listed. The local model cannot be available without real artifacts.")
    for artifact in artifact_names:
        artifact_path = config.model_dir / artifact
        if artifact_path.suffix.lower() not in SUPPORTED_ARTIFACT_EXTENSIONS:
            unsupported_artifacts.append(artifact)
        if not artifact_path.exists():
            missing_artifacts.append(artifact)
    if unsupported_artifacts:
        errors.append(f"Unsupported artifact extension(s): {', '.join(unsupported_artifacts)}")
    if missing_artifacts:
        warnings.append(f"Missing artifact file(s): {', '.join(missing_artifacts)}")

    artifacts_found = artifact_count > 0 and not missing_artifacts and not unsupported_artifacts
    manifest_valid = not errors
    if not manifest_valid:
        status = "error"
        next_steps.append("Fix manifest errors before enabling local model checks.")
    elif not config.enabled:
        status = "disabled"
    elif not artifacts_found:
        status = "unavailable"
        next_steps.append("Place every artifact listed in model_manifest.json inside the local model directory.")
    else:
        status = "unavailable"
        warnings.append(NO_IMPLEMENTATION_WARNING)
        next_steps.append("Add a supported local predictor loader before scientific predictions can be generated.")

    next_steps.append("Scientifically validate any local model before using outputs for decision support.")
    return {
        "status": status,
        "enabled": config.enabled,
        "model_dir": str(config.model_dir),
        "manifest_path": str(manifest_path),
        "manifest_found": True,
        "manifest_valid": manifest_valid,
        "artifact_count": artifact_count,
        "artifacts_found": artifacts_found,
        "missing_artifacts": missing_artifacts,
        "supported_tasks": supported_tasks,
        "input_type": input_type,
        "version": version,
        "limitations": limitations,
        "errors": errors,
        "warnings": warnings,
        "next_steps": next_steps,
    }


def local_admet_manifest_preview() -> dict[str, Any]:
    config = get_local_admet_config()
    manifest_path = _manifest_path(config)
    if not manifest_path.exists():
        return {
            "status": "unavailable",
            "manifest_path": str(manifest_path),
            "manifest_found": False,
            "message": "model_manifest.json was not found. model_manifest.example.json is documentation only.",
            "manifest": None,
        }
    try:
        manifest = _read_manifest(config)
    except json.JSONDecodeError as exc:
        return {
            "status": "error",
            "manifest_path": str(manifest_path),
            "manifest_found": True,
            "message": f"model_manifest.json is invalid JSON: {exc}",
            "manifest": None,
        }
    return {
        "status": "ok",
        "manifest_path": str(manifest_path),
        "manifest_found": True,
        "message": "Manifest preview contains metadata only. Binary artifact contents are never returned.",
        "manifest": manifest,
    }


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
    validation = validate_local_admet_model()
    if validation["status"] == "disabled":
        return _info(
            config=config,
            status="disabled",
            warning="; ".join(validation["warnings"]) or "Local ADMET model is disabled.",
            manifest_found=validation["manifest_found"],
            artifacts_found=validation["artifacts_found"],
        )
    if validation["status"] == "unavailable":
        return _info(
            config=config,
            status="unavailable",
            tasks=validation["supported_tasks"] or DEFAULT_TASKS,
            version=str(validation["version"]) if validation["version"] else None,
            limitations=[str(validation["limitations"])] if validation["limitations"] else ["No real local ADMET model is active."],
            warning="; ".join(validation["warnings"]) or "Local ADMET model is unavailable.",
            manifest_found=validation["manifest_found"],
            artifacts_found=validation["artifacts_found"],
        )
    if validation["status"] == "error":
        return _info(
            config=config,
            status="error",
            tasks=validation["supported_tasks"] or DEFAULT_TASKS,
            version=str(validation["version"]) if validation["version"] else None,
            limitations=[str(validation["limitations"])] if validation["limitations"] else ["Local model manifest has validation errors."],
            warning="; ".join(validation["errors"]) or "Local ADMET model validation failed.",
            manifest_found=validation["manifest_found"],
            artifacts_found=validation["artifacts_found"],
        )
    return _info(
        config=config,
        status="unavailable",
        tasks=validation["supported_tasks"] or DEFAULT_TASKS,
        version=str(validation["version"]) if validation["version"] else None,
        limitations=[str(validation["limitations"])] if validation["limitations"] else ["A supported local predictor loader has not been implemented yet."],
        warning=NO_IMPLEMENTATION_WARNING,
        manifest_found=validation["manifest_found"],
        artifacts_found=validation["artifacts_found"],
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
