import importlib.util
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import platform_config


def plugin_root() -> Path:
    configured = Path(platform_config()["plugin_directory"])
    return configured if configured.is_absolute() else Path(__file__).resolve().parents[2] / configured


@lru_cache(maxsize=1)
def discover_plugins() -> tuple[dict[str, Any], ...]:
    root = plugin_root()
    results = []
    for path in sorted(root.glob("*/plugin.json")) if root.exists() else []:
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(manifest.get("plugin_id"), str) or not manifest["plugin_id"]:
                raise ValueError("plugin_id must be a non-empty string")
            results.append({**manifest, "path": str(path.parent), "status": "enabled" if manifest.get("enabled") is True else "disabled"})
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            results.append({"plugin_id": path.parent.name, "path": str(path.parent), "status": "invalid", "error": str(exc)})
    return tuple(results)


@lru_cache(maxsize=1)
def load_plugin_adapters() -> dict[str, Any]:
    adapters = {}
    for manifest in discover_plugins():
        if manifest["status"] != "enabled":
            continue
        module_path = Path(manifest["path"]) / manifest.get("module", "plugin.py")
        spec = importlib.util.spec_from_file_location(f"drugscreen360_plugin_{manifest['plugin_id']}", module_path)
        if not spec or not spec.loader:
            raise ValueError(f"Cannot load plugin module: {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        adapter = module.create_adapter()
        methods = ("is_available", "get_model_info", "predict")
        if not isinstance(getattr(adapter, "model_id", None), str) or not all(callable(getattr(adapter, name, None)) for name in methods):
            raise ValueError(f"Plugin {manifest['plugin_id']} does not implement the predictor adapter contract")
        if adapter.model_id in adapters:
            raise ValueError(f"Duplicate plugin model_id: {adapter.model_id}")
        adapters[adapter.model_id] = adapter
    return adapters
