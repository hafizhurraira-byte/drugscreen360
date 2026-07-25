import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.database import get_connection, init_db


M2D1_PROTOCOL_HASH = "cfaa5070cf08bcec98519545a5e16989cb670a7da60a2f8d14eb04ce485e586f"

M2D1_COHORT_HASHES = {
    "bbbp": "98fc9170891712ea5c19d555263a19e50e0734dee0044c65e4a4f7f1151102b5",
    "esol": "1be64b60fb5cc68b7f19b36a979b4553f452fd8b959872df5c05610d38f2556c",
    "herg": "8d7593b76194761a8670f2dbf4af19a015349774cfb7a233a9cc5e425f93f209",
}

M2D1_DATASET_IDS = {
    "bbbp": "B3DB classification",
    "esol": "AqSolDB",
    "herg": "PubChem AID 588834",
}

WARNING_SEVERITY = {
    "EXTERNAL_VALIDATION_SUPPORTS_ACTIVE": "CAUTION",
    "ACTIVE_WITH_STRONGER_WARNING": "STRONG_WARNING",
    "RECALIBRATION_RECOMMENDED": "STRONG_WARNING",
}


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _coerce_metric(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("value")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _key_metrics(endpoint: str, metrics: dict[str, Any]) -> dict[str, Any]:
    if endpoint in {"bbbp", "herg"}:
        return {
            "auroc": _coerce_metric(metrics.get("auroc")),
            "auprc": _coerce_metric(metrics.get("auprc")),
            "f1": _coerce_metric(metrics.get("f1")),
            "recall": _coerce_metric(metrics.get("recall")),
            "specificity": _coerce_metric(metrics.get("specificity")),
            "balanced_accuracy": _coerce_metric(metrics.get("balanced_accuracy")),
            "brier_score": _coerce_metric(metrics.get("brier_score")),
            "ece": _coerce_metric(metrics.get("ece")),
        }
    return {
        "mae": _coerce_metric(metrics.get("mae")),
        "rmse": _coerce_metric(metrics.get("rmse")),
        "r2": _coerce_metric(metrics.get("r2")),
        "pearson": _coerce_metric(metrics.get("pearson")),
        "spearman": _coerce_metric(metrics.get("spearman")),
        "residual_bias": _coerce_metric(metrics.get("residual_mean") or metrics.get("residual_bias")),
    }


def _calibration_summary(endpoint: str, result: dict[str, Any]) -> dict[str, Any]:
    metrics = result.get("metrics") or {}
    if endpoint == "esol":
        conformal = result.get("conformal") or result.get("interval") or {}
        return {
            "nominal_coverage": _coerce_metric(conformal.get("nominal_coverage")) or 0.9,
            "external_observed_coverage": _coerce_metric(
                conformal.get("observed_external_coverage")
                or conformal.get("external_observed_coverage")
                or metrics.get("external_observed_coverage")
            ),
            "internal_test_coverage": _coerce_metric(conformal.get("internal_test_coverage") or metrics.get("internal_test_coverage")),
            "status": "undercovered_external_interval",
        }
    return {
        "brier_score": _coerce_metric(metrics.get("brier_score")),
        "ece": _coerce_metric(metrics.get("ece")),
        "status": "poor_probability_calibration" if endpoint == "herg" else "externally_evaluated",
    }


def _row_to_summary(row: Any) -> dict[str, Any]:
    data = dict(row)
    metrics = _loads(data.get("metrics_json"), {})
    domain = _loads(data.get("domain_metrics_json"), {})
    calibration = _loads(data.get("calibration_summary_json"), {})
    limitations = _loads(data.get("limitations_json"), [])
    return {
        "available": True,
        "id": data.get("id"),
        "endpoint": data.get("endpoint_key"),
        "model_id": data.get("model_id"),
        "model_version": data.get("model_version"),
        "model_hash": data.get("model_hash"),
        "evidence_decision": data.get("final_evidence_decision"),
        "external_validation_status": data.get("final_evidence_decision"),
        "activation_recommendation": data.get("activation_recommendation"),
        "dataset_id": data.get("external_dataset_id"),
        "dataset_version": data.get("external_dataset_version"),
        "cohort_size": data.get("external_sample_count"),
        "external_sample_count": data.get("external_sample_count"),
        "cohort_hash": data.get("external_cohort_hash"),
        "protocol_hash": data.get("protocol_hash"),
        "independence_status": data.get("independence_decision"),
        "key_metrics": _key_metrics(data.get("endpoint_key"), metrics),
        "metrics": metrics,
        "domain_summary": domain,
        "calibration_summary": calibration,
        "limitations": limitations,
        "warning_severity": WARNING_SEVERITY.get(data.get("final_evidence_decision"), "UNAVAILABLE"),
        "evidence_hash": data.get("evidence_hash"),
        "evidence_timestamp": data.get("created_at"),
    }


def unavailable_external_evidence() -> dict[str, Any]:
    return {
        "available": False,
        "external_validation_status": "not_available",
        "evidence_decision": "not_available",
        "warning_severity": "UNAVAILABLE",
        "limitations": ["Frozen M2D-1 external validation evidence has not been imported for this endpoint."],
    }


def get_latest_endpoint_external_evidence(endpoint: str, model_id: str | None = None) -> dict[str, Any]:
    init_db()
    sql = """
        SELECT * FROM admet_endpoint_external_validation_evidence
        WHERE endpoint_key = ?
    """
    args: list[Any] = [endpoint]
    if model_id:
        sql += " AND model_id = ?"
        args.append(model_id)
    sql += " ORDER BY datetime(created_at) DESC, id DESC LIMIT 1"
    with get_connection() as connection:
        row = connection.execute(sql, tuple(args)).fetchone()
    return _row_to_summary(row) if row else unavailable_external_evidence()


def list_endpoint_external_evidence() -> list[dict[str, Any]]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT e.*
            FROM admet_endpoint_external_validation_evidence e
            JOIN (
                SELECT endpoint_key, model_id, MAX(id) AS latest_id
                FROM admet_endpoint_external_validation_evidence
                GROUP BY endpoint_key, model_id
            ) latest ON latest.latest_id = e.id
            ORDER BY e.endpoint_key
            """
        ).fetchall()
    return [_row_to_summary(row) for row in rows]


def external_warning_messages(endpoint: str, evidence: dict[str, Any], domain_status: str | None = None) -> list[str]:
    if not evidence.get("available"):
        return ["External validation evidence has not been imported for this endpoint."]
    messages: list[str] = []
    if endpoint == "bbbp":
        messages.extend([
            "M2D-1 external validation supports continued BBBP research use (B3DB N=6146; AUROC 0.9121; specificity 0.6435).",
            "BBBP prediction is not proof of human CNS exposure; BBB penetration may be desirable or undesirable depending on project context.",
        ])
        if domain_status == "OUT_OF_DOMAIN":
            messages.append("BBBP OUT_OF_DOMAIN external performance was materially lower (AUROC 0.6552).")
    elif endpoint == "esol":
        messages.extend([
            "M2D-1 AqSolDB validation: MAE 1.0270 logS, RMSE 1.4577 logS, R2 0.6309.",
            "Nominal 90% validation-derived prediction intervals achieved only 61.47% external coverage; treat interval bounds as approximate research uncertainty.",
            "Source independence has provenance limitations.",
        ])
        if domain_status == "OUT_OF_DOMAIN":
            messages.append("ESOL OUT_OF_DOMAIN external RMSE was 2.5884; do not confidently rank from predicted solubility alone.")
    elif endpoint == "herg":
        messages.extend([
            "M2D-1 hERG validation: AUROC 0.9003, AUPRC 0.7134, recall 0.8227, specificity 0.8058.",
            "hERG external ECE was 0.2665; raw probabilities are not reliable absolute risk probabilities and recalibration review is recommended.",
            "Low predicted hERG probability is not cardiac-safety clearance.",
            "Source independence has provenance limitations.",
        ])
        if domain_status == "OUT_OF_DOMAIN":
            messages.append("hERG OUT_OF_DOMAIN performance was weaker; interpret class and probability with reduced reliability.")
    return messages


def import_m2d1_external_validation(
    ledger_path: str | Path,
    endpoints: list[str] | None = None,
    dry_run: bool = True,
    imported_by: str = "local_maintenance_import",
) -> dict[str, Any]:
    from app.services.admet_endpoint_model_service import ENDPOINTS

    ledger_file = Path(ledger_path)
    try:
        ledger = json.loads(ledger_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read M2D-1 ledger: {exc}") from exc
    if ledger.get("protocol", {}).get("sha256") != M2D1_PROTOCOL_HASH:
        raise HTTPException(status_code=400, detail="M2D-1 protocol hash mismatch.")

    curation = {item.get("endpoint"): item for item in ledger.get("curation", [])}
    requested = endpoints or ["bbbp", "esol", "herg"]
    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    init_db()
    with get_connection() as connection:
        for endpoint in requested:
            result = (ledger.get("results") or {}).get(endpoint)
            spec = ENDPOINTS.get(endpoint)
            try:
                if not spec or endpoint == "clintox_cttox":
                    raise ValueError(f"Unsupported M2D-1 endpoint: {endpoint}")
                if not result:
                    raise ValueError("Endpoint result missing from ledger.")
                if result.get("model_hash") != spec.get("expected_hash"):
                    raise ValueError("Model hash mismatch.")
                if result.get("curated_dataset_hash") != M2D1_COHORT_HASHES[endpoint]:
                    raise ValueError("External cohort hash mismatch.")
                metrics = result.get("metrics") or {}
                if not metrics:
                    raise ValueError("External metrics are missing.")
                final_decision = result.get("final_decision") or result.get("final_evidence_decision")
                if final_decision not in WARNING_SEVERITY:
                    raise ValueError("Unsupported or missing final evidence decision.")
                calibration = _calibration_summary(endpoint, result)
                limitations = result.get("limitations") or []
                payload = {
                    "endpoint_key": endpoint,
                    "model_id": spec["model_id"],
                    "model_version": spec["version"],
                    "model_hash": result["model_hash"],
                    "external_dataset_id": M2D1_DATASET_IDS[endpoint],
                    "external_dataset_version": "v1",
                    "external_cohort_hash": result["curated_dataset_hash"],
                    "protocol_hash": M2D1_PROTOCOL_HASH,
                    "independence_decision": result.get("independence_decision") or "not_reported",
                    "external_sample_count": int(metrics.get("n") or result.get("external_n") or curation.get(endpoint, {}).get("primary") or 0),
                    "exact_overlap_exclusions": int(curation.get(endpoint, {}).get("overlap") or 0),
                    "scaffold_overlap_count": int(result.get("scaffold_overlap_count") or 0),
                    "metrics": metrics,
                    "domain_metrics": result.get("domain_metrics") or {},
                    "calibration_summary": calibration,
                    "final_evidence_decision": final_decision,
                    "activation_recommendation": result.get("activation_recommendation") or "not_reported",
                    "limitations": limitations,
                    "evidence_source": "M2D-1 frozen external-validation ledger",
                }
                evidence_hash = _sha256_text(payload)
                if dry_run:
                    imported.append({"endpoint": endpoint, "status": "validated", "evidence_hash": evidence_hash})
                    continue
                existing = connection.execute(
                    "SELECT id FROM admet_endpoint_external_validation_evidence WHERE evidence_hash = ?",
                    (evidence_hash,),
                ).fetchone()
                if existing:
                    skipped.append({"endpoint": endpoint, "status": "already_imported", "id": existing["id"], "evidence_hash": evidence_hash})
                    continue
                connection.execute(
                    """
                    INSERT INTO admet_endpoint_external_validation_evidence (
                        endpoint_key, model_id, model_version, model_hash, external_dataset_id,
                        external_dataset_version, external_cohort_hash, protocol_hash, independence_decision,
                        external_sample_count, exact_overlap_exclusions, scaffold_overlap_count, metrics_json,
                        domain_metrics_json, calibration_summary_json, final_evidence_decision,
                        activation_recommendation, limitations_json, evidence_source, evidence_hash, imported_by
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["endpoint_key"],
                        payload["model_id"],
                        payload["model_version"],
                        payload["model_hash"],
                        payload["external_dataset_id"],
                        payload["external_dataset_version"],
                        payload["external_cohort_hash"],
                        payload["protocol_hash"],
                        payload["independence_decision"],
                        payload["external_sample_count"],
                        payload["exact_overlap_exclusions"],
                        payload["scaffold_overlap_count"],
                        json.dumps(metrics, sort_keys=True),
                        json.dumps(payload["domain_metrics"], sort_keys=True),
                        json.dumps(calibration, sort_keys=True),
                        payload["final_evidence_decision"],
                        payload["activation_recommendation"],
                        json.dumps(limitations, sort_keys=True),
                        payload["evidence_source"],
                        evidence_hash,
                        imported_by,
                    ),
                )
                imported.append({"endpoint": endpoint, "status": "imported", "evidence_hash": evidence_hash})
            except Exception as exc:
                failed.append({"endpoint": endpoint, "error": str(exc)})
        if failed and not dry_run:
            connection.rollback()
            raise HTTPException(status_code=400, detail={"message": "M2D-1 evidence import failed.", "failed": failed})
    if failed and dry_run:
        raise HTTPException(status_code=400, detail={"message": "M2D-1 evidence validation failed.", "failed": failed})
    return {"dry_run": dry_run, "imported": imported, "skipped": skipped, "failed": failed}
