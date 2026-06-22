from pathlib import Path


def app_version() -> str:
    version_path = Path(__file__).resolve().parents[3] / "VERSION"
    try:
        return version_path.read_text(encoding="utf-8").strip() or "0.13.2"
    except OSError:
        return "0.13.2"
