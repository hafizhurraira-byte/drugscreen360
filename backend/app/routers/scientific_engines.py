import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from app.models.scientific_engine_models import (
    ActivationRequest, ActivationStatus, ArtifactVerification, DeactivationRequest, DeploymentProfile,
    EngineClass, EngineCreate, EngineVersionCreate, LicenceReview, LicenceStatus, RuntimeHealthStatus, ValidationReview, ValidationStatus,
)
from app.services import scientific_engine_registry_service as registry
from app.services import scientific_engine_migration_service as migration
from app.services import scientific_engine_reconciliation_service as reconciliation

router = APIRouter(prefix="/scientific-engines", tags=["scientific-engines"])


def _write_guard(request: Request, x_registry_admin_token: str | None = Header(None)):
    expected = os.getenv("SCIENTIFIC_ENGINE_ADMIN_TOKEN")
    if request.client and request.client.host in {"127.0.0.1", "::1", "testclient"}:
        return
    if expected and x_registry_admin_token and hmac.compare_digest(expected, x_registry_admin_token):
        return
    raise HTTPException(403, "Registry mutation is limited to local or authenticated administrators")


@router.get("")
def list_engines(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return registry.list_engines(limit, offset)


@router.get("/discover")
def discover(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), task_type: str | None = None,
             endpoint: str | None = None, organism: str | None = None, target: str | None = None,
             target_class: str | None = None, molecule_type: str | None = None,
             execution_mode: str | None = Query(None, pattern="^(local|api)$"), deployment_profile: DeploymentProfile | None = None,
             scientific_validation_status: ValidationStatus | None = None, licence_status: LicenceStatus | None = None,
             activation_status: ActivationStatus | None = None, runtime_health_status: RuntimeHealthStatus | None = None,
             engine_class: EngineClass | None = None, search: str | None = Query(None, max_length=100), blocked_state: bool = False, active_only: bool = False):
    return registry.discover(locals(), limit, offset)


@router.get("/licence-summary")
def licence_summary():
    return registry.licence_summary()


@router.get("/integrity")
def integrity():
    return registry.integrity()


@router.get("/summary")
def summary():
    return reconciliation.summary()


@router.get("/capabilities")
def capabilities():
    result = registry.discover({}, 100, 0)
    return {"items": [{"engine_id": item["engine_id"], "engine_name": item["engine_name"], "engine_class": item["engine_class"], "task_types": item["task_types"], "endpoints": item["version"]["supported_endpoints"]} for item in result["items"]]}


@router.post("/migration/dry-run", dependencies=[Depends(_write_guard)])
def migration_dry_run():
    return migration.migrate("dry-run")


@router.post("/migration/apply", dependencies=[Depends(_write_guard)])
def migration_apply():
    return migration.migrate("apply")


@router.get("/migration/status")
def migration_status():
    return migration.migration_status()


@router.get("/reconciliation")
def reconcile_all(limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
    report = reconciliation.reconcile(record_run=True)
    return {**report, "items": report["items"][offset:offset + limit], "total": len(report["items"]), "limit": limit, "offset": offset}


@router.post("/register", status_code=201, dependencies=[Depends(_write_guard)])
def register(payload: EngineCreate):
    return registry.register_engine(payload)


@router.get("/{engine_id}")
def detail(engine_id: str):
    return registry.get_engine(engine_id)


@router.get("/{engine_id}/reconciliation")
def reconcile_engine(engine_id: str):
    return reconciliation.reconcile(engine_id)


@router.get("/{engine_id}/versions")
def versions(engine_id: str):
    return registry.list_versions(engine_id)


@router.post("/{engine_id}/versions", status_code=201, dependencies=[Depends(_write_guard)])
def register_version(engine_id: str, payload: EngineVersionCreate):
    return registry.register_version(engine_id, payload)


@router.get("/{engine_id}/versions/{version}")
def version_detail(engine_id: str, version: str):
    return registry.get_version(engine_id, version)


@router.get("/{engine_id}/versions/{version}/reconciliation")
def reconcile_version(engine_id: str, version: str):
    return reconciliation.reconcile(engine_id, version)


@router.get("/{engine_id}/history")
def history(engine_id: str):
    return registry.history(engine_id)


@router.post("/{engine_id}/versions/{version}/licence-review", dependencies=[Depends(_write_guard)])
def licence_review(engine_id: str, version: str, payload: LicenceReview):
    return registry.add_licence_review(engine_id, version, payload)


@router.post("/{engine_id}/versions/{version}/validation-review", dependencies=[Depends(_write_guard)])
def validation_review(engine_id: str, version: str, payload: ValidationReview):
    return registry.update_validation(engine_id, version, payload)


@router.post("/{engine_id}/versions/{version}/activate", dependencies=[Depends(_write_guard)])
def activate(engine_id: str, version: str, payload: ActivationRequest):
    return registry.activate(engine_id, version, payload)


@router.post("/{engine_id}/versions/{version}/deactivate", dependencies=[Depends(_write_guard)])
def deactivate(engine_id: str, version: str, payload: DeactivationRequest):
    return registry.deactivate(engine_id, version, payload)


@router.post("/{engine_id}/versions/{version}/verify-artifact", dependencies=[Depends(_write_guard)])
def verify_artifact(engine_id: str, version: str, payload: ArtifactVerification):
    return registry.verify_artifact(engine_id, version, payload.artifact_exists, payload.artifact_hash)
