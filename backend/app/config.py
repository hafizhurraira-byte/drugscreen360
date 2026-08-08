import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "platform.yaml"


@lru_cache(maxsize=1)
def platform_config() -> dict[str, Any]:
    """Load the JSON-compatible YAML config and apply explicit env overrides."""
    path = Path(os.getenv("DRUGSCREEN360_CONFIG", DEFAULT_CONFIG))
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.setdefault("cors_origins", ["http://localhost:5173", "http://127.0.0.1:5173"])
    data.setdefault("plugin_directory", "plugins")
    data.setdefault("scoring_weights", {"egfr": 0.3, "admet": 0.25, "confidence": 0.2, "uncertainty": 0.15, "applicability_domain": 0.1})
    if value := os.getenv("CORS_ORIGINS"):
        data["cors_origins"] = [item.strip() for item in value.split(",") if item.strip()]
    if value := os.getenv("DRUGSCREEN360_PLUGIN_DIRECTORY"):
        data["plugin_directory"] = value
    return data
