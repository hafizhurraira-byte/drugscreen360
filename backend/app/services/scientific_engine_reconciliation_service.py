import json
from typing import Any

from fastapi import HTTPException

from app.database import get_connection
from app.services import scientific_engine_registry_service as registry


def _links(engine_id: str | None = None, version: str | None = None):
    query = "SELECT * FROM scientific_engine_legacy_links WHERE 1=1"
    values: list[str] = []
    if engine_id:
        query += " AND engine_id=?"
        values.append(engine_id)
    if version:
        query += " AND engine_version=?"
        values.append(version)
    query += " ORDER BY engine_id, engine_version, id"
    with get_connection() as connection:
        return connection.execute(query, values).fetchall()


def _live_state(link) -> dict[str, Any]:
    snapshot = json.loads(link["snapshot_json"])
    with get_connection() as connection:
        if link["legacy_system"] == "admet_endpoint_governance":
            row = connection.execute("SELECT model_id,status FROM admet_endpoint_active_models WHERE endpoint_key=?", (link["legacy_record_id"],)).fetchone()
            return {**snapshot, "activation_status": row["status"] if row else "UNAVAILABLE", "model_id": row["model_id"] if row else snapshot.get("model_id")}
        if link["legacy_system"] == "activity_model_governance":
            row = connection.execute("SELECT model_id,status FROM activity_active_models WHERE target_key=?", (link["legacy_record_id"],)).fetchone()
            return {**snapshot, "activation_status": row["status"] if row else "UNAVAILABLE", "model_id": row["model_id"] if row and row["model_id"] else snapshot.get("model_id")}
    return snapshot


def reconcile(engine_id: str | None = None, version: str | None = None, record_run: bool = False) -> dict[str, Any]:
    if engine_id:
        registry.get_engine(engine_id)
    links = _links(engine_id, version)
    if engine_id and version and not links:
        try:
            registry.get_version(engine_id, version)
        except HTTPException:
            raise
        return {"items": [{"engine_id": engine_id, "engine_version": version, "state": "LEGACY_LINK_MISSING", "recommended_action": "Create a reviewed authoritative legacy link."}], "read_only": True}
    items = []
    for link in links:
        current = registry.get_version(link["engine_id"], link["engine_version"])
        live = _live_state(link)
        expected_active = "ACTIVE_BETA" if live.get("activation_status") == "ACTIVE" else ("BLOCKED_VALIDATION" if current.get("scientific_validation_status") == "REJECTED" else "INACTIVE")
        checks = {
            "model_hash": current.get("model_hash") == live.get("model_hash") if live.get("model_hash") else None,
            "activation_state": current.get("activation_status") == expected_active if link["legacy_system"] in {"admet_endpoint_governance", "activity_model_governance"} else None,
            "endpoint": live.get("endpoint") in current.get("supported_endpoints", []) if live.get("endpoint") else None,
            "validation": current.get("scientific_validation_status") == live.get("validation_status") if live.get("validation_status") else None,
            "artifact": bool(live.get("artifact_available")) if "artifact_available" in live else None,
            "licence_resolved": (current.get("licence_review") or {}).get("licence_review_status") not in {None, "UNKNOWN", "NOT_REVIEWED", "UNDER_REVIEW"},
        }
        failed = [name for name, passed in checks.items() if passed is False]
        if "model_hash" in failed:
            state = "HASH_MISMATCH"
        elif "activation_state" in failed:
            state = "STATE_MISMATCH"
        elif "endpoint" in failed:
            state = "ENDPOINT_MISMATCH"
        elif "validation" in failed:
            state = "VALIDATION_MISMATCH"
        elif "artifact" in failed:
            state = "ARTIFACT_UNAVAILABLE"
        elif "licence_resolved" in failed:
            state = "LICENCE_UNRESOLVED"
        else:
            state = "CONSISTENT"
        items.append({"engine_id": link["engine_id"], "engine_version": link["engine_version"], "state": state,
                      "checks": checks, "recommended_action": "Review and update governance evidence; no automatic repair was performed." if state != "CONSISTENT" else "None."})
    report = {"items": items, "read_only": True, "repairs_performed": 0}
    if record_run:
        with get_connection() as connection:
            connection.execute("INSERT INTO scientific_engine_reconciliation_runs (report_json) VALUES (?)", (registry._json(report),))
    return report


def summary() -> dict[str, Any]:
    report = reconcile()
    with get_connection() as connection:
        engines = connection.execute("SELECT COUNT(*) FROM scientific_engines").fetchone()[0]
        versions = connection.execute("SELECT COUNT(*) FROM scientific_engine_versions").fetchone()[0]
    detailed = []
    with get_connection() as connection:
        rows = connection.execute("SELECT engine_id,engine_version FROM scientific_engine_versions ORDER BY engine_id,engine_version").fetchall()
    for row in rows:
        detailed.append(registry.get_version(row["engine_id"], row["engine_version"]))
    count = lambda predicate: sum(1 for item in detailed if predicate(item))
    return {
        "total_engines": engines, "total_versions": versions,
        "active_research_engines": count(lambda x: x["activation_status"] == "ACTIVE_RESEARCH"),
        "active_beta_engines": count(lambda x: x["activation_status"] == "ACTIVE_BETA"),
        "licence_blocked": count(lambda x: (x.get("licence_review") or {}).get("licence_review_status", "UNKNOWN") in {"UNKNOWN", "NOT_REVIEWED", "UNDER_REVIEW", "BLOCKED"}),
        "validation_blocked": count(lambda x: x["activation_status"] == "BLOCKED_VALIDATION"),
        "artifact_blocked": count(lambda x: x["technical_status"] in {"ARTIFACT_MISSING", "ARTIFACT_HASH_MISMATCH"}),
        "runtime_unavailable": count(lambda x: x["runtime_health_status"] == "UNAVAILABLE"),
        "registry_mismatches": sum(1 for item in report["items"] if item["state"] not in {"CONSISTENT", "LICENCE_UNRESOLVED"}),
        "research_use_only": True,
    }


def integrity() -> dict[str, Any]:
    report = reconcile()
    with get_connection() as connection:
        counts = {
            "registered_engine_count": connection.execute("SELECT COUNT(*) FROM scientific_engines").fetchone()[0],
            "registered_version_count": connection.execute("SELECT COUNT(*) FROM scientific_engine_versions").fetchone()[0],
            "legacy_link_count": connection.execute("SELECT COUNT(*) FROM scientific_engine_legacy_links").fetchone()[0],
            "orphan_registry_records": connection.execute("SELECT COUNT(*) FROM scientific_engine_versions v LEFT JOIN scientific_engines e ON e.engine_id=v.engine_id WHERE e.engine_id IS NULL").fetchone()[0],
            "orphan_legacy_links": connection.execute("SELECT COUNT(*) FROM scientific_engine_legacy_links l LEFT JOIN scientific_engine_versions v ON v.engine_id=l.engine_id AND v.engine_version=l.engine_version WHERE v.engine_id IS NULL").fetchone()[0],
            "last_migration_run": connection.execute("SELECT created_at FROM scientific_engine_migration_runs ORDER BY id DESC LIMIT 1").fetchone(),
            "last_reconciliation_run": connection.execute("SELECT created_at FROM scientific_engine_reconciliation_runs ORDER BY id DESC LIMIT 1").fetchone(),
        }
    states = [item["state"] for item in report["items"]]
    summary_counts = summary()
    return {"registry_schema_status": "AVAILABLE", **{k: (v[0] if v else None) if k.startswith("last_") else v for k, v in counts.items()},
            "consistent_engine_count": states.count("CONSISTENT"), "mismatch_count": sum(s not in {"CONSISTENT", "LICENCE_UNRESOLVED"} for s in states),
            "licence_blocked_count": summary_counts["licence_blocked"], "validation_blocked_count": summary_counts["validation_blocked"],
            "artifact_blocked_count": summary_counts["artifact_blocked"], "runtime_unavailable_count": summary_counts["runtime_unavailable"],
            "unknown_licence_count": states.count("LICENCE_UNRESOLVED"), "duplicate_conflicts": 0,
            "status": "HEALTHY" if not any(s not in {"CONSISTENT", "LICENCE_UNRESOLVED"} for s in states) and not counts["orphan_registry_records"] and not counts["orphan_legacy_links"] else "DEGRADED"}
