import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.database import get_connection
from app.models.scientific_engine_models import (
    ActivationRequest,
    ActivationStatus,
    DeactivationRequest,
    EngineCreate,
    EngineVersionCreate,
    LicenceReview,
    ValidationReview,
)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _public(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _public(item)
            for key, item in value.items()
            if key.lower() not in {"path", "secret", "credentials", "api_key", "token"}
            and not key.lower().endswith(("_path", "_secret", "_api_key", "_token"))
        }
    if isinstance(value, list):
        return [_public(item) for item in value]
    if isinstance(value, str) and (Path(value).is_absolute() or value.startswith(("/home/", "/Users/"))):
        return "[REDACTED]"
    return value


def register_engine(payload: EngineCreate) -> dict[str, Any]:
    data = payload.model_dump(mode="json")
    with get_connection() as connection:
        current = connection.execute("SELECT * FROM scientific_engines WHERE engine_id = ?", (payload.engine_id,)).fetchone()
        if current:
            existing = dict(current)
            tasks = data.pop("task_types")
            comparable = {**data, "task_types_json": _json(tasks)}
            if all(existing[key] == value for key, value in comparable.items()):
                return get_engine(payload.engine_id)
            raise HTTPException(409, "Conflicting engine registration")
        connection.execute(
            """INSERT INTO scientific_engines
               (engine_id, engine_name, engine_family, engine_class, provider_name, task_types_json,
                description, repository, official_documentation, publication, maintainer, registry_schema_version)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (payload.engine_id, payload.engine_name, payload.engine_family, payload.engine_class.value,
             payload.provider_name, _json(payload.task_types), payload.description, payload.repository,
             payload.official_documentation, payload.publication, payload.maintainer, payload.registry_schema_version),
        )
    return get_engine(payload.engine_id)


def register_version(engine_id: str, payload: EngineVersionCreate) -> dict[str, Any]:
    get_engine(engine_id)
    data = payload.model_dump(mode="json")
    permissions = data.pop("deployment_permissions")
    record = _json(data)
    with get_connection() as connection:
        current = connection.execute(
            "SELECT record_json FROM scientific_engine_versions WHERE engine_id = ? AND engine_version = ?",
            (engine_id, payload.engine_version),
        ).fetchone()
        if current:
            stored_permissions = [dict(row) for row in connection.execute(
                "SELECT deployment_profile, permitted, reason FROM scientific_engine_deployment_permissions WHERE engine_id = ? AND engine_version = ? ORDER BY deployment_profile",
                (engine_id, payload.engine_version),
            )]
            normalized = sorted(({**item, "permitted": int(item["permitted"])} for item in permissions), key=lambda x: x["deployment_profile"])
            if current["record_json"] == record and stored_permissions == normalized:
                return get_version(engine_id, payload.engine_version)
            raise HTTPException(409, "Conflicting engine-version registration")
        connection.execute(
            "INSERT INTO scientific_engine_versions (engine_id, engine_version, record_json) VALUES (?, ?, ?)",
            (engine_id, payload.engine_version, record),
        )
        connection.executemany(
            "INSERT INTO scientific_engine_deployment_permissions VALUES (?, ?, ?, ?, ?)",
            [(engine_id, payload.engine_version, item["deployment_profile"], int(item["permitted"]), item.get("reason")) for item in permissions],
        )
    return get_version(engine_id, payload.engine_version)


def get_engine(engine_id: str) -> dict[str, Any]:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM scientific_engines WHERE engine_id = ?", (engine_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Scientific engine not found")
    result = dict(row)
    result["task_types"] = json.loads(result.pop("task_types_json"))
    return _public(result)


def get_version(engine_id: str, version: str) -> dict[str, Any]:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM scientific_engine_versions WHERE engine_id = ? AND engine_version = ?", (engine_id, version)
        ).fetchone()
        permissions = connection.execute(
            "SELECT deployment_profile, permitted, reason FROM scientific_engine_deployment_permissions WHERE engine_id = ? AND engine_version = ? ORDER BY deployment_profile",
            (engine_id, version),
        ).fetchall()
        licence = connection.execute(
            "SELECT record_json, created_at FROM scientific_engine_licence_reviews WHERE engine_id = ? AND engine_version = ? ORDER BY id DESC LIMIT 1",
            (engine_id, version),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Scientific engine version not found")
    result = json.loads(row["record_json"])
    result.update(engine_id=engine_id, registered_at=row["registered_at"], last_verified_at=row["last_verified_at"], retired_at=row["retired_at"])
    result["deployment_permissions"] = [{**dict(item), "permitted": bool(item["permitted"])} for item in permissions]
    result["licence_review"] = ({**json.loads(licence["record_json"]), "recorded_at": licence["created_at"]} if licence else None)
    return _public(result)


def list_engines(limit: int, offset: int) -> dict[str, Any]:
    with get_connection() as connection:
        total = connection.execute("SELECT COUNT(*) FROM scientific_engines").fetchone()[0]
        ids = connection.execute("SELECT engine_id FROM scientific_engines ORDER BY engine_id LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    return {"items": [get_engine(row["engine_id"]) for row in ids], "total": total, "limit": limit, "offset": offset}


def list_versions(engine_id: str) -> list[dict[str, Any]]:
    get_engine(engine_id)
    with get_connection() as connection:
        rows = connection.execute("SELECT engine_version FROM scientific_engine_versions WHERE engine_id = ? ORDER BY engine_version", (engine_id,)).fetchall()
    return [get_version(engine_id, row["engine_version"]) for row in rows]


def add_licence_review(engine_id: str, version: str, payload: LicenceReview) -> dict[str, Any]:
    get_version(engine_id, version)
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO scientific_engine_licence_reviews (engine_id, engine_version, record_json) VALUES (?, ?, ?)",
            (engine_id, version, _json(payload.model_dump(mode="json"))),
        )
    return get_version(engine_id, version)


def update_validation(engine_id: str, version: str, payload: ValidationReview) -> dict[str, Any]:
    current = get_version(engine_id, version)
    current["scientific_validation_status"] = payload.scientific_validation_status.value
    current["validation_review"] = payload.model_dump(mode="json")
    return _update_record(engine_id, version, current)


def verify_artifact(engine_id: str, version: str, artifact_exists: bool, artifact_hash: str | None) -> dict[str, Any]:
    current = get_version(engine_id, version)
    expected = current.get("artifact_hash")
    if not artifact_exists:
        current["technical_status"] = "ARTIFACT_MISSING"
    elif not expected or artifact_hash != expected:
        current["technical_status"] = "ARTIFACT_HASH_MISMATCH"
    else:
        current["technical_status"] = "AVAILABLE"
    return _update_record(engine_id, version, current, verified=True)


def verify_local_artifact(engine_id: str, version: str, path: str) -> dict[str, Any]:
    artifact = Path(path)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact.is_file() else None
    return verify_artifact(engine_id, version, artifact.is_file(), digest)


def _update_record(engine_id: str, version: str, public_record: dict[str, Any], verified: bool = False) -> dict[str, Any]:
    for key in ("engine_id", "registered_at", "last_verified_at", "retired_at", "deployment_permissions", "licence_review"):
        public_record.pop(key, None)
    with get_connection() as connection:
        connection.execute(
            f"UPDATE scientific_engine_versions SET record_json = ?{', last_verified_at = CURRENT_TIMESTAMP' if verified else ''} WHERE engine_id = ? AND engine_version = ?",
            (_json(public_record), engine_id, version),
        )
    return get_version(engine_id, version)


def _eligibility(version: dict[str, Any], target: ActivationStatus, profile: str) -> tuple[str, str] | None:
    licence = (version.get("licence_review") or {}).get("licence_review_status", "UNKNOWN")
    allowed_licences = {"APPROVED_BETA"} if target == ActivationStatus.ACTIVE_BETA else {"APPROVED_RESEARCH", "APPROVED_BETA"}
    if licence not in allowed_licences:
        return "BLOCKED_LICENCE", f"Licence status {licence} does not permit {target.value}"
    if version["scientific_validation_status"] == "REJECTED" or (target == ActivationStatus.ACTIVE_BETA and version["scientific_validation_status"] != "VALIDATED_FOR_SCOPE"):
        return "BLOCKED_VALIDATION", "Scientific validation does not permit activation"
    if version["technical_status"] != "AVAILABLE" or not version.get("artifact_hash"):
        return "BLOCKED_ARTIFACT", "A present, hash-matching artifact is required"
    if not version.get("supported_endpoints") or not version.get("input_schema_version") or not version.get("output_schema_version") or not version.get("known_limitations"):
        return "BLOCKED_CONFIGURATION", "Endpoint, schema, and limitation declarations are required"
    permission = next((item for item in version["deployment_permissions"] if item["deployment_profile"] == profile), None)
    if not permission or not permission["permitted"]:
        return "BLOCKED_CONFIGURATION", f"Deployment profile {profile} is not permitted"
    return None


def activate(engine_id: str, version: str, payload: ActivationRequest) -> dict[str, Any]:
    if engine_id in {"egfr_activity_v2", "bbbp_v1", "esol_v1", "herg_v1", "clintox_cttox_v1"}:
        raise HTTPException(409, "Existing model-specific activation gate remains authoritative")
    if payload.activation_status not in {ActivationStatus.ACTIVE_RESEARCH, ActivationStatus.ACTIVE_BETA}:
        raise HTTPException(409, "Activation target must be ACTIVE_RESEARCH or ACTIVE_BETA")
    current = get_version(engine_id, version)
    blocked = _eligibility(current, payload.activation_status, payload.deployment_profile.value)
    if blocked:
        raise HTTPException(409, {"activation_status": blocked[0], "reason": blocked[1]})
    previous = current["activation_status"]
    current["activation_status"] = payload.activation_status.value
    _update_record(engine_id, version, current)
    _history(engine_id, version, previous, payload.activation_status.value, payload.reason, payload.initiated_by)
    return get_version(engine_id, version)


def deactivate(engine_id: str, version: str, payload: DeactivationRequest) -> dict[str, Any]:
    current = get_version(engine_id, version)
    previous = current["activation_status"]
    current["activation_status"] = "INACTIVE"
    _update_record(engine_id, version, current)
    _history(engine_id, version, previous, "INACTIVE", payload.reason, payload.initiated_by)
    return get_version(engine_id, version)


def _history(engine_id: str, version: str, previous: str, new: str, reason: str, initiated_by: str) -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO scientific_engine_activation_history (engine_id, engine_version, previous_status, new_status, reason, initiated_by) VALUES (?, ?, ?, ?, ?, ?)",
            (engine_id, version, previous, new, reason, initiated_by),
        )


def history(engine_id: str) -> list[dict[str, Any]]:
    get_engine(engine_id)
    with get_connection() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM scientific_engine_activation_history WHERE engine_id = ? ORDER BY id", (engine_id,))]


def discover(filters: dict[str, str | bool | None], limit: int, offset: int) -> dict[str, Any]:
    with get_connection() as connection:
        rows = connection.execute("SELECT engine_id, engine_version FROM scientific_engine_versions ORDER BY engine_id, engine_version").fetchall()
    items = []
    for row in rows:
        item = get_version(row["engine_id"], row["engine_version"])
        engine = get_engine(row["engine_id"])
        checks = {
            "search": (filters.get("search", "").lower() in f"{engine['engine_name']} {engine['description']} {engine['provider_name']}".lower()) if filters.get("search") else True,
            "engine_class": engine["engine_class"] == filters.get("engine_class") if filters.get("engine_class") else True,
            "task_type": filters.get("task_type") in engine["task_types"] if filters.get("task_type") else True,
            "endpoint": filters.get("endpoint") in item["supported_endpoints"] if filters.get("endpoint") else True,
            "organism": filters.get("organism") in item["supported_organisms"] if filters.get("organism") else True,
            "target": filters.get("target") in item["supported_targets"] if filters.get("target") else True,
            "target_class": filters.get("target_class") in item["supported_target_classes"] if filters.get("target_class") else True,
            "molecule_type": filters.get("molecule_type") in item["supported_molecule_types"] if filters.get("molecule_type") else True,
            "scientific_validation_status": item["scientific_validation_status"] == filters.get("scientific_validation_status") if filters.get("scientific_validation_status") else True,
            "activation_status": item["activation_status"] == filters.get("activation_status") if filters.get("activation_status") else True,
            "licence_status": (item.get("licence_review") or {}).get("licence_review_status", "UNKNOWN") == filters.get("licence_status") if filters.get("licence_status") else True,
            "execution_mode": (item["local_execution_supported"] if filters.get("execution_mode") == "local" else item["api_execution_supported"]) if filters.get("execution_mode") else True,
            "deployment_profile": any(p["deployment_profile"] == filters.get("deployment_profile") and p["permitted"] for p in item["deployment_permissions"]) if filters.get("deployment_profile") else True,
            "active_only": item["activation_status"].startswith("ACTIVE_") if filters.get("active_only") else True,
            "runtime_health_status": item["runtime_health_status"] == filters.get("runtime_health_status") if filters.get("runtime_health_status") else True,
            "blocked_state": (item["activation_status"].startswith("BLOCKED_") or item["technical_status"].startswith("ARTIFACT_")) if filters.get("blocked_state") else True,
        }
        if all(checks.values()):
            items.append({**engine, "version": item})
    return {"items": items[offset:offset + limit], "total": len(items), "limit": limit, "offset": offset}


def licence_summary() -> dict[str, int]:
    with get_connection() as connection:
        rows = connection.execute("SELECT record_json FROM scientific_engine_licence_reviews WHERE id IN (SELECT MAX(id) FROM scientific_engine_licence_reviews GROUP BY engine_id, engine_version)").fetchall()
    result: dict[str, int] = {}
    for row in rows:
        status = json.loads(row["record_json"])["licence_review_status"]
        result[status] = result.get(status, 0) + 1
    return result


def integrity() -> dict[str, Any]:
    from app.services.scientific_engine_reconciliation_service import integrity as expanded_integrity
    return expanded_integrity()
