import json
import platform
import sys

result = {
    "executable": sys.executable,
    "python_version": sys.version,
    "platform": platform.platform(),
    "packages": {},
    "usable": True,
}

for package_name in ("numpy", "pandas", "rdkit"):
    try:
        module = __import__(package_name)
        result["packages"][package_name] = {
            "available": True,
            "version": getattr(module, "__version__", "UNKNOWN"),
        }
    except Exception as exc:
        result["packages"][package_name] = {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        result["usable"] = False

print(json.dumps(result, indent=2))
raise SystemExit(0 if result["usable"] else 2)