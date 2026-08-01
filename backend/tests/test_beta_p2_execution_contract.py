from importlib.metadata import version as package_version

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import database
from app.database import init_db
from app.main import app
from app.models.schemas import CompoundIdentity
from app.models.scientific_engine_models import ScientificEngineExecutionRequest
from app.services.scientific_engine_adapter_service import (
    AdapterRegistry, BlockedBbbpAdapter, MedicinalChemistryRulesAdapter,
    PubChemCompoundAdapter, RdkitDescriptorAdapter, ScientificEngineExecutionService,
)


def payload(engine="rdkit_toolkit", version=None, task="DESCRIPTOR_CALCULATION", endpoint="molecular_descriptors", inputs=None, **extra):
    return {"contract_version": "1.0", "engine_id": engine, "engine_version": version or package_version("rdkit"), "task_type": task, "endpoint": endpoint, "inputs": inputs or {"molecule": {"smiles": "CCO"}}, "parameters": {}, "execution_context": {"deployment_profile": "CI_TEST", "requested_by": "pytest", "research_only": True}, **extra}


def ready(engine_id="rdkit_toolkit", adapter_id="rdkit_descriptor_adapter"):
    return {"engine_id": engine_id, "engine_name": engine_id, "engine_class": "CHEMISTRY_TOOLKIT", "scientific_validation_status": "VALIDATED_FOR_SCOPE", "licence_review": {"licence_review_status": "APPROVED_BETA"}, "activation_status": "ACTIVE_BETA", "technical_status": "AVAILABLE", "runtime_health_status": "HEALTHY", "runtime_compatibility_status": "NOT_APPLICABLE", "execution_allowed": True, "adapter_id": adapter_id, "adapter_version": "1.0", "known_limitations": ["Research-use test fixture."], "deployment_permissions": [{"deployment_profile": "CI_TEST", "permitted": True}]}


def service(adapter, state=None, persist=False):
    adapters = AdapterRegistry(); adapters.register(adapter)
    record = state or ready(adapter.engine_id, adapter.adapter_id)
    return ScientificEngineExecutionService(adapters, lambda *_: record, lambda *_: {"engine_name": adapter.engine_id, "engine_class": record.get("engine_class")}, persist=persist)


def test_contract_validation_and_stable_hashes():
    request = ScientificEngineExecutionRequest.model_validate(payload())
    one = service(RdkitDescriptorAdapter(request.engine_version)).run(request)
    two = service(RdkitDescriptorAdapter(request.engine_version)).run(request)
    assert one["status"] == "SUCCESS" and one["provenance"]["input_hash"] == two["provenance"]["input_hash"]
    assert one["provenance"]["parameter_hash"] == two["provenance"]["parameter_hash"]
    for change in ({"contract_version": "2.0"}, {"research_only": False}):
        broken = payload()
        if "research_only" in change: broken["execution_context"].update(change)
        else: broken.update(change)
        with pytest.raises(ValidationError): ScientificEngineExecutionRequest.model_validate(broken)


@pytest.mark.parametrize("change,status", [
    ({"licence_review": {"licence_review_status": "UNKNOWN"}}, "BLOCKED_LICENCE"),
    ({"scientific_validation_status": "REJECTED"}, "BLOCKED_SCIENTIFIC_VALIDATION"),
    ({"activation_status": "INACTIVE"}, "BLOCKED_ACTIVATION"),
    ({"technical_status": "ARTIFACT_MISSING"}, "BLOCKED_ARTIFACT"),
    ({"runtime_compatibility_status": "VERSION_MISMATCH_UNVERIFIED", "execution_allowed": False}, "BLOCKED_RUNTIME"),
    ({"deployment_permissions": [{"deployment_profile": "CI_TEST", "permitted": False}]}, "BLOCKED_DEPLOYMENT"),
])
def test_governance_fails_closed(change, status):
    adapter = RdkitDescriptorAdapter(package_version("rdkit")); state = ready(); state.update(change)
    result = service(adapter, state).run(ScientificEngineExecutionRequest.model_validate(payload()))
    assert result["status"] == status and result["result"] is None


def test_adapter_registry_exact_duplicate_and_support():
    adapter = RdkitDescriptorAdapter(package_version("rdkit")); registry = AdapterRegistry(); registry.register(adapter)
    assert registry.resolve(adapter.engine_id, adapter.engine_version) is adapter and registry.resolve(adapter.engine_id, "wrong") is None
    with pytest.raises(ValueError, match="Duplicate"): registry.register(adapter)
    request = ScientificEngineExecutionRequest.model_validate(payload(task="STRUCTURAL_ALERTS"))
    assert service(adapter).run(request)["status"] == "UNSUPPORTED_TASK"


def test_rdkit_and_rule_adapters_are_deterministic_and_reject_mixtures():
    request = ScientificEngineExecutionRequest.model_validate(payload())
    result = service(RdkitDescriptorAdapter(request.engine_version)).run(request)
    assert result["result"]["canonical_smiles"] == "CCO" and result["applicability_domain"]["status"] == "NOT_APPLICABLE"
    mixture = ScientificEngineExecutionRequest.model_validate(payload(inputs={"molecule": {"smiles": "CCO.O"}}))
    assert service(RdkitDescriptorAdapter(request.engine_version)).run(mixture)["status"] == "FAILED_VALIDATION"
    rules_request = ScientificEngineExecutionRequest.model_validate(payload("medicinal_chemistry_rule_filters", "1", "STRUCTURAL_ALERTS", "medicinal_chemistry_alerts"))
    rules = service(MedicinalChemistryRulesAdapter()).run(rules_request)
    assert rules["result"]["lipinski"]["passed"] and "screening heuristics" in rules["limitations"][-1]


def test_pubchem_mock_is_bounded_and_no_raw_payload():
    identity = CompoundIdentity(compound_name="Ethanol", pubchem_cid=702, canonical_smiles="CCO", isomeric_smiles="CCO", molecular_formula="C2H6O", molecular_weight=46.07, iupac_name="ethanol", synonyms=[str(i) for i in range(30)], pubchem_source_link="https://pubchem.ncbi.nlm.nih.gov/compound/702")
    adapter = PubChemCompoundAdapter(lambda *_: identity)
    request = ScientificEngineExecutionRequest.model_validate(payload("pubchem_connector", "PUG_REST", "DATABASE_EVIDENCE_RETRIEVAL", "compound_record", {"query": {"compound_name": "ethanol"}}))
    result = service(adapter, ready("pubchem_connector", adapter.adapter_id)).run(request)
    assert result["status"] == "SUCCESS" and len(result["result"]["synonyms"]) == 12 and "raw" not in result["result"]


def test_bbbp_governance_prevents_execute(monkeypatch):
    adapter = BlockedBbbpAdapter(); called = False
    def forbidden(_):
        nonlocal called; called = True; raise AssertionError
    monkeypatch.setattr(adapter, "execute", forbidden)
    state = ready("bbbp_v1", adapter.adapter_id); state.update(licence_review={"licence_review_status": "UNKNOWN"}, runtime_compatibility_status="VERSION_MISMATCH_UNVERIFIED", execution_allowed=False)
    request = ScientificEngineExecutionRequest.model_validate(payload("bbbp_v1", "v1", "ADME_PREDICTION", "bbbp_classification"))
    result = service(adapter, state).run(request)
    assert result["status"] == "BLOCKED_LICENCE" and not called and result["result"] is None


def test_audit_and_api_redaction(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "p2.sqlite3"); init_db()
    request = ScientificEngineExecutionRequest.model_validate(payload())
    result = service(RdkitDescriptorAdapter(request.engine_version), persist=True).run(request)
    with database.get_connection() as connection: row = dict(connection.execute("SELECT * FROM scientific_engine_executions").fetchone())
    assert row["input_hash"] == result["provenance"]["input_hash"] and "CCO" not in str(row) and "\\" not in str(row)
    assert TestClient(app).get("/api/scientific-engine-adapters").status_code == 200
