import hashlib

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import database
from app.database import init_db
from app.main import app
from app.models.scientific_engine_models import ActivationRequest, DeactivationRequest, EngineCreate, EngineVersionCreate, LicenceReview
from app.services import scientific_engine_registry_service as registry


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "registry.sqlite3")
    init_db()
    return tmp_path


def engine():
    return EngineCreate(engine_id="example", engine_name="Example", engine_family="test", engine_class="INTERNAL_MODEL",
                        provider_name="DrugScreen360", task_types=["ADME_PREDICTION"], description="Test engine")


def version(**overrides):
    values = dict(engine_version="v1", adapter_id="example_adapter", adapter_version="1", runtime_type="python",
                  artifact_identifier="artifact.bin", artifact_hash="abc", input_schema_version="1", output_schema_version="1",
                  supported_endpoints=["BBBP"], supported_organisms=["Homo sapiens"], supported_molecule_types=["SMALL_MOLECULE"],
                  known_limitations=["Research-use test"], local_execution_supported=True,
                  deployment_permissions=[{"deployment_profile": "LOCAL_RESEARCH", "permitted": True},
                                          {"deployment_profile": "PUBLIC_DEMO", "permitted": True}])
    values.update(overrides)
    return EngineVersionCreate(**values)


def register_ready(licence="APPROVED_BETA", validation="VALIDATED_FOR_SCOPE"):
    registry.register_engine(engine())
    registry.register_version("example", version(technical_status="AVAILABLE", scientific_validation_status=validation))
    registry.add_licence_review("example", "v1", LicenceReview(licence_review_status=licence))


def test_registration_is_idempotent_and_conflicts_are_rejected(isolated_registry):
    assert registry.register_engine(engine()) == registry.register_engine(engine())
    with pytest.raises(HTTPException, match="Conflicting"):
        registry.register_engine(engine().model_copy(update={"engine_name": "Different"}))


def test_version_registration_preserves_nullable_unknowns_and_validates_enums(isolated_registry):
    registry.register_engine(engine())
    result = registry.register_version("example", version())
    assert result["training_data_information"] is result["applicability_domain_method"] is result["uncertainty_method"] is None
    with pytest.raises(ValueError):
        EngineVersionCreate(**{**version().model_dump(), "technical_status": "MADE_UP"})


@pytest.mark.parametrize("status", ["UNKNOWN", "NOT_REVIEWED", "UNDER_REVIEW", "BLOCKED"])
def test_unapproved_licences_block_beta(isolated_registry, status):
    register_ready(status)
    with pytest.raises(HTTPException) as exc:
        registry.activate("example", "v1", ActivationRequest(activation_status="ACTIVE_BETA", deployment_profile="PUBLIC_DEMO", initiated_by="test", reason="test"))
    assert exc.value.detail["activation_status"] == "BLOCKED_LICENCE"


def test_research_licence_only_permits_research(isolated_registry):
    register_ready("APPROVED_RESEARCH")
    assert registry.activate("example", "v1", ActivationRequest(activation_status="ACTIVE_RESEARCH", deployment_profile="LOCAL_RESEARCH", initiated_by="test", reason="test"))["activation_status"] == "ACTIVE_RESEARCH"
    with pytest.raises(HTTPException):
        registry.activate("example", "v1", ActivationRequest(activation_status="ACTIVE_BETA", deployment_profile="PUBLIC_DEMO", initiated_by="test", reason="test"))


def test_code_licence_does_not_imply_weights_or_data_permission(isolated_registry):
    registry.register_engine(engine())
    registry.register_version("example", version(technical_status="AVAILABLE", scientific_validation_status="VALIDATED_FOR_SCOPE"))
    result = registry.add_licence_review("example", "v1", LicenceReview(code_licence="MIT", licence_review_status="UNKNOWN"))
    assert result["licence_review"]["model_weights_licence"] is None
    with pytest.raises(HTTPException):
        registry.activate("example", "v1", ActivationRequest(activation_status="ACTIVE_BETA", deployment_profile="PUBLIC_DEMO", initiated_by="test", reason="test"))


@pytest.mark.parametrize("validation", ["UNREVIEWED", "REJECTED", "INSUFFICIENT_EVIDENCE"])
def test_unapproved_validation_blocks_beta(isolated_registry, validation):
    register_ready(validation=validation)
    with pytest.raises(HTTPException) as exc:
        registry.activate("example", "v1", ActivationRequest(activation_status="ACTIVE_BETA", deployment_profile="PUBLIC_DEMO", initiated_by="test", reason="test"))
    assert exc.value.detail["activation_status"] == "BLOCKED_VALIDATION"


def test_artifact_verification_fails_closed_and_never_returns_path(isolated_registry, tmp_path):
    registry.register_engine(engine())
    registry.register_version("example", version(artifact_hash=hashlib.sha256(b"ok").hexdigest()))
    artifact = tmp_path / "secret-machine-path.bin"
    artifact.write_bytes(b"wrong")
    assert registry.verify_local_artifact("example", "v1", str(artifact))["technical_status"] == "ARTIFACT_HASH_MISMATCH"
    artifact.unlink()
    missing = registry.verify_local_artifact("example", "v1", str(artifact))
    assert missing["technical_status"] == "ARTIFACT_MISSING" and "secret-machine-path" not in str(missing)


def test_activation_and_deactivation_append_immutable_history(isolated_registry):
    register_ready()
    registry.activate("example", "v1", ActivationRequest(activation_status="ACTIVE_BETA", deployment_profile="PUBLIC_DEMO", initiated_by="test", reason="approved"))
    registry.deactivate("example", "v1", DeactivationRequest(initiated_by="test", reason="maintenance"))
    assert [(event["previous_status"], event["new_status"]) for event in registry.history("example")] == [("INACTIVE", "ACTIVE_BETA"), ("ACTIVE_BETA", "INACTIVE")]


def test_existing_model_specific_gate_cannot_be_bypassed(isolated_registry):
    legacy = engine().model_copy(update={"engine_id": "clintox_cttox_v1"})
    registry.register_engine(legacy)
    registry.register_version(legacy.engine_id, version(technical_status="AVAILABLE", scientific_validation_status="VALIDATED_FOR_SCOPE"))
    registry.add_licence_review(legacy.engine_id, "v1", LicenceReview(licence_review_status="APPROVED_BETA"))
    with pytest.raises(HTTPException, match="authoritative"):
        registry.activate(legacy.engine_id, "v1", ActivationRequest(activation_status="ACTIVE_BETA", deployment_profile="PUBLIC_DEMO", initiated_by="test", reason="must fail"))


def test_discovery_filters(isolated_registry):
    register_ready()
    assert registry.discover({"task_type": "ADME_PREDICTION", "endpoint": "BBBP", "organism": "Homo sapiens", "deployment_profile": "PUBLIC_DEMO", "active_only": False}, 10, 0)["total"] == 1
    assert registry.discover({"endpoint": "HERG", "active_only": False}, 10, 0)["total"] == 0


def test_api_pagination_filter_validation_missing_and_redaction(isolated_registry):
    client = TestClient(app)
    assert client.post("/api/scientific-engines/register", json=engine().model_dump(mode="json")).status_code == 201
    assert client.get("/api/scientific-engines?limit=101").status_code == 422
    assert client.get("/api/scientific-engines/discover?execution_mode=remote").status_code == 422
    assert client.get("/api/scientific-engines/missing").status_code == 404
    assert not any("path" in key.lower() or "secret" in key.lower() for key in client.get("/api/scientific-engines/example").json())
