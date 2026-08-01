from fastapi import APIRouter, Query

from app.models.scientific_engine_models import (
    ActivationRequest, ActivationStatus, ArtifactVerification, DeactivationRequest, DeploymentProfile,
    EngineCreate, EngineVersionCreate, LicenceReview, LicenceStatus, ValidationReview, ValidationStatus,
)
from app.services import scientific_engine_registry_service as registry

router = APIRouter(prefix="/scientific-engines", tags=["scientific-engines"])


@router.get("")
def list_engines(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    return registry.list_engines(limit, offset)


@router.get("/discover")
def discover(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), task_type: str | None = None,
             endpoint: str | None = None, organism: str | None = None, target: str | None = None,
             target_class: str | None = None, molecule_type: str | None = None,
             execution_mode: str | None = Query(None, pattern="^(local|api)$"), deployment_profile: DeploymentProfile | None = None,
             scientific_validation_status: ValidationStatus | None = None, licence_status: LicenceStatus | None = None,
             activation_status: ActivationStatus | None = None, active_only: bool = False):
    return registry.discover(locals(), limit, offset)


@router.get("/licence-summary")
def licence_summary():
    return registry.licence_summary()


@router.get("/integrity")
def integrity():
    return registry.integrity()


@router.post("/register", status_code=201)
def register(payload: EngineCreate):
    return registry.register_engine(payload)


@router.get("/{engine_id}")
def detail(engine_id: str):
    return registry.get_engine(engine_id)


@router.get("/{engine_id}/versions")
def versions(engine_id: str):
    return registry.list_versions(engine_id)


@router.post("/{engine_id}/versions", status_code=201)
def register_version(engine_id: str, payload: EngineVersionCreate):
    return registry.register_version(engine_id, payload)


@router.get("/{engine_id}/versions/{version}")
def version_detail(engine_id: str, version: str):
    return registry.get_version(engine_id, version)


@router.get("/{engine_id}/history")
def history(engine_id: str):
    return registry.history(engine_id)


@router.post("/{engine_id}/versions/{version}/licence-review")
def licence_review(engine_id: str, version: str, payload: LicenceReview):
    return registry.add_licence_review(engine_id, version, payload)


@router.post("/{engine_id}/versions/{version}/validation-review")
def validation_review(engine_id: str, version: str, payload: ValidationReview):
    return registry.update_validation(engine_id, version, payload)


@router.post("/{engine_id}/versions/{version}/activate")
def activate(engine_id: str, version: str, payload: ActivationRequest):
    return registry.activate(engine_id, version, payload)


@router.post("/{engine_id}/versions/{version}/deactivate")
def deactivate(engine_id: str, version: str, payload: DeactivationRequest):
    return registry.deactivate(engine_id, version, payload)


@router.post("/{engine_id}/versions/{version}/verify-artifact")
def verify_artifact(engine_id: str, version: str, payload: ArtifactVerification):
    return registry.verify_artifact(engine_id, version, payload.artifact_exists, payload.artifact_hash)
