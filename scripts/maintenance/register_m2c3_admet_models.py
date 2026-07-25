import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Register frozen M2C-3 ADMET endpoint models by verified reference.")
    parser.add_argument("--artifact-root", required=True, help="Directory containing bbbp_v1, esol_v1, herg_v1, and clintox_cttox_v1.")
    parser.add_argument("--endpoint", default="all", help="Endpoint key or all.")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing local registration manifests.")
    parser.add_argument("--activate", action="store_true", help="Activate eligible endpoints after registration and gate checks.")
    args = parser.parse_args()

    project_backend = Path(__file__).resolve().parents[2] / "backend"
    sys.path.insert(0, str(project_backend))

    from app.services.admet_endpoint_model_service import (
        ENDPOINTS,
        activate_admet_endpoint,
        evaluate_admet_activation_gate,
        register_admet_artifact,
    )

    root = Path(args.artifact_root)
    endpoints = list(ENDPOINTS) if args.endpoint == "all" else [args.endpoint]
    output = {"artifact_root": str(root), "registered": [], "gates": [], "activated": [], "skipped_activation": []}

    for endpoint in endpoints:
        spec = ENDPOINTS[endpoint]
        source = root / spec["external_dir"]
        registration = register_admet_artifact(endpoint, source, overwrite=args.overwrite)
        gate = evaluate_admet_activation_gate(endpoint)
        output["registered"].append({"endpoint": endpoint, "model_id": registration["model_id"], "artifact_hash": registration["artifact_hash"]})
        output["gates"].append(gate)
        if not args.activate:
            continue
        if endpoint == "clintox_cttox":
            output["skipped_activation"].append({"endpoint": endpoint, "reason": "ClinTox v1 is not activation eligible and is registered for transparency only."})
            continue
        if gate["activation_state"] != "ACTIVATION_ELIGIBLE":
            output["skipped_activation"].append({"endpoint": endpoint, "reason": "activation_gate_failed", "gate": gate})
            continue
        output["activated"].append(activate_admet_endpoint(endpoint, initiated_by="m2c3_maintenance_script"))

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
