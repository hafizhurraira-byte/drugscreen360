import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.scientific_engine_migration_service import migrate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate existing DrugScreen360 engines into the beta registry.")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--verify", action="store_true")
    parser.add_argument("--engine-id")
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--output-report", type=Path)
    args = parser.parse_args()
    mode = "apply" if args.apply else "verify" if args.verify else "dry-run"
    report = migrate(mode, args.source_root, args.engine_id)
    output = json.dumps(report, indent=2, sort_keys=True)
    if args.output_report:
        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        args.output_report.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 1 if any(item["outcome"] in {"CONFLICT", "MISSING"} for item in report["results"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
