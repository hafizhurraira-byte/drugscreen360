import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Register frozen EGFR v2 activity model artifact.")
    parser.add_argument("--source-dir", default=os.getenv("DRUGDESIGN360_EGFR_V2_ARTIFACT_DIR", ""))
    parser.add_argument("--copy-required-files", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2] / "backend"
    sys.path.insert(0, str(project_root))

    from app.services.activity_model_service import (
        activate_egfr_v2,
        evaluate_egfr_v2_activation_gate,
        register_egfr_v2_artifact,
    )

    registration = register_egfr_v2_artifact(args.source_dir, args.copy_required_files, args.overwrite)
    gate = evaluate_egfr_v2_activation_gate()
    result = {"registration": registration, "activation_gate": gate, "activated": None}
    if args.activate:
        result["activated"] = activate_egfr_v2("maintenance_script")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
