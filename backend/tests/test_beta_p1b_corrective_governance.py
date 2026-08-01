import pytest
from fastapi import HTTPException

from app.services import admet_endpoint_model_service as admet
from app.services import scientific_engine_registry_service as registry


def test_exact_framework_version_match_passes(monkeypatch):
    monkeypatch.setattr(registry, "package_version", lambda _: "1.5.2")
    result = registry.sklearn_joblib_compatibility({"package_versions": {"sklearn": "1.5.2"}})
    assert result["runtime_compatibility_status"] == "EXACT_VERSION_MATCH" and result["execution_allowed"] is True


@pytest.mark.parametrize("metadata,runtime", [
    ({"package_versions": {"sklearn": "1.9.0"}}, "1.5.2"),
    ({}, "1.5.2"),
    ({"package_versions": {"sklearn": "1.9.0"}}, None),
])
def test_unverified_runtime_versions_fail_closed(monkeypatch, metadata, runtime):
    if runtime is None:
        from importlib.metadata import PackageNotFoundError
        monkeypatch.setattr(registry, "package_version", lambda _: (_ for _ in ()).throw(PackageNotFoundError()))
    else:
        monkeypatch.setattr(registry, "package_version", lambda _: runtime)
    result = registry.sklearn_joblib_compatibility(metadata)
    assert result["execution_allowed"] is False
    assert result["runtime_compatibility_status"] in {"VERSION_MISMATCH_UNVERIFIED", "UNKNOWN"}


def test_hash_failure_precedes_compatibility(monkeypatch):
    monkeypatch.setattr(registry, "package_version", lambda _: "1.9.0")
    result = registry.sklearn_joblib_compatibility({"package_versions": {"sklearn": "1.9.0"}}, artifact_hash_verified=False)
    assert result["runtime_compatibility_status"] == "UNKNOWN"
    assert "hash" in result["compatibility_reason"].lower()


def test_runtime_mismatch_returns_structured_error_without_loading(monkeypatch, tmp_path):
    monkeypatch.setattr(admet, "get_active_endpoint", lambda _: {"status": "ACTIVE"})
    monkeypatch.setattr(admet, "_artifact_dir", lambda _: tmp_path)
    monkeypatch.setattr(admet, "verify_admet_artifact", lambda *_: {
        "valid": False,
        "hashes": {"model.joblib": admet.ENDPOINTS["bbbp"]["expected_hash"]},
        "errors": ["model_runtime_version_mismatch"],
        "runtime_compatibility": {
            "artifact_framework": "scikit-learn", "artifact_framework_version": "1.9.0",
            "runtime_framework": "scikit-learn", "runtime_framework_version": "1.5.2",
            "serialization_format": "joblib/pickle", "runtime_compatibility_status": "VERSION_MISMATCH_UNVERIFIED",
            "compatibility_reason": "unverified", "execution_allowed": False, "fallback_used": False,
        },
    })
    monkeypatch.setattr(admet.joblib, "load", lambda *_: pytest.fail("unsafe artifact was loaded"))
    with pytest.raises(HTTPException) as exc:
        admet._load_bundle("bbbp")
    assert exc.value.status_code == 409
    assert exc.value.detail["error"] == "model_runtime_version_mismatch"
    assert exc.value.detail["execution_allowed"] is False and exc.value.detail["fallback_used"] is False
