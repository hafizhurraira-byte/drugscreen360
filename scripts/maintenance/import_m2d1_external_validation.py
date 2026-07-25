"""Import frozen M2D-1 ADMET external-validation evidence.

This utility intentionally does not activate, deactivate, retrain, recalibrate,
or alter thresholds. It only validates and inserts immutable governance evidence.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.admet_endpoint_external_evidence_service import import_m2d1_external_validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate/import M2D-1 frozen external-validation evidence.")
    parser.add_argument("--ledger", required=True, help="Path to m2d1_master_results.json")
    parser.add_argument("--endpoint", action="append", choices=["bbbp", "esol", "herg"], help="Endpoint to import; repeatable. Defaults to all.")
    parser.add_argument("--apply", action="store_true", help="Insert records. Without this flag the utility runs a dry-run validation.")
    parser.add_argument("--imported-by", default="local_maintenance_import", help="Audit label for imported_by.")
    args = parser.parse_args()
    try:
        result = import_m2d1_external_validation(
            Path(args.ledger),
            endpoints=args.endpoint,
            dry_run=not args.apply,
            imported_by=args.imported_by,
        )
    except Exception as exc:
        detail = getattr(exc, "detail", str(exc))
        print(f"M2D-1 import failed: {detail}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
