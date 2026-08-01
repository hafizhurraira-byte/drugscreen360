import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import database
from app.database import get_connection, init_db
from app.main import app
from app.models.scientific_engine_models import EngineCreate, EngineVersionCreate
from app.services import scientific_engine_migration_service as migration
from app.services import scientific_engine_reconciliation_service as reconciliation
from app.services import scientific_engine_registry_service as registry


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "registry.sqlite3")
    init_db()
    with get_connection() as connection:
        connection.execute("INSERT INTO activity_active_models (target_key,model_id,status) VALUES ('EGFR','','DISABLED')")
        for endpoint, model_id in (("bbbp", "bbbp_v1"), ("esol", "esol_v1"), ("herg", "herg_v1")):
            connection.execute("INSERT INTO admet_endpoint_active_models (endpoint_key,model_id,status) VALUES (?,?, 'ACTIVE')", (endpoint, model_id))
    return tmp_path


def test_dry_run_is_deterministic_and_writes_nothing(isolated):
    first = migration.migrate("dry-run", isolated)
    second = migration.migrate("dry-run", isolated)
    assert first == second and first["engine_count"] == 11 and not first["writes_performed"]
    with get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM scientific_engines").fetchone()[0] == 0


def test_apply_is_idempotent_and_verify_succeeds(isolated):
    assert migration.migrate("apply", isolated)["engine_count"] == 11
    assert migration.migrate("apply", isolated)["engine_count"] == 11
    assert {item["outcome"] for item in migration.migrate("verify", isolated)["results"]} == {"VERIFIED"}
    with get_connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM scientific_engines").fetchone()[0] == 11
        assert connection.execute("SELECT COUNT(*) FROM scientific_engine_legacy_links").fetchone()[0] == 11


def test_corrective_apply_rewrites_governance_without_activation_history(isolated):
    migration.migrate("apply", isolated, "bbbp_v1")
    with get_connection() as connection:
        row = connection.execute("SELECT record_json FROM scientific_engine_versions WHERE engine_id='bbbp_v1'").fetchone()
        old = json.loads(row[0]); old["activation_status"] = "ACTIVE_BETA"; old.pop("beta_eligibility_status", None)
        connection.execute("UPDATE scientific_engine_versions SET record_json=? WHERE engine_id='bbbp_v1'", (registry._json(old),))
    corrected = migration.migrate("apply", isolated, "bbbp_v1")
    current = registry.get_version("bbbp_v1", "v1")
    assert corrected["results"][0]["outcome"] == "CORRECTED"
    assert current["activation_status"] == "INACTIVE" and current["beta_eligibility_status"].startswith("BLOCKED_")
    assert registry.history("bbbp_v1") == []
    assert migration.migrate("apply", isolated, "bbbp_v1")["results"][0]["outcome"] == "IMPORTED"


def test_single_engine_migration_and_missing_verify(isolated):
    report = migration.migrate("apply", isolated, "rdkit_toolkit")
    assert report["results"][0]["engine_id"] == "rdkit_toolkit"
    missing = migration.migrate("verify", isolated, "bbbp_v1")
    assert missing["results"][0]["outcome"] == "MISSING"


def test_conflicting_duplicate_fails_closed(isolated):
    migration.migrate("apply", isolated, "rdkit_toolkit")
    with get_connection() as connection:
        connection.execute("UPDATE scientific_engine_versions SET record_json='{}' WHERE engine_id='rdkit_toolkit'")
        connection.execute("DELETE FROM scientific_engine_legacy_links WHERE engine_id='rdkit_toolkit'")
    with pytest.raises(HTTPException, match="Conflicting"):
        migration.migrate("apply", isolated, "rdkit_toolkit")


def test_engine_specific_states_and_warnings_are_preserved(isolated):
    migration.migrate("apply", isolated)
    assert registry.get_version("egfr_activity_v2", "v2")["activation_status"] == "INACTIVE"
    for model_id in ("bbbp_v1", "esol_v1", "herg_v1"):
        governed = registry.get_version(model_id, "v1")
        assert governed["legacy_execution_status"] == "ACTIVE"
        assert governed["activation_status"] == "INACTIVE"
        assert governed["beta_eligibility_status"] in {"BLOCKED_LICENCE", "BLOCKED_CONFIGURATION"}
        assert "LICENCE_UNRESOLVED" in governed["beta_blocked_reasons"]
    assert "undercover" in " ".join(registry.get_version("esol_v1", "v1")["known_limitations"]).lower()
    assert "cardiac safety" in " ".join(registry.get_version("herg_v1", "v1")["known_limitations"]).lower()
    clintox = registry.get_version("clintox_cttox_v1", "v1")
    assert clintox["activation_status"] == "BLOCKED_VALIDATION" and clintox["scientific_validation_status"] == "REJECTED"
    assert "recall and F1 were zero" in clintox["known_limitations"][0]


def test_toolkit_rules_and_connectors_are_distinct_evidence_types(isolated):
    migration.migrate("apply", isolated)
    assert registry.get_engine("rdkit_toolkit")["engine_class"] == "CHEMISTRY_TOOLKIT"
    rules = registry.get_version("medicinal_chemistry_rule_filters", "1")
    assert "RULE_BASED_HEURISTIC" in rules["known_limitations"][0]
    pubchem = registry.get_version("pubchem_connector", "PUG_REST")
    assert pubchem["internet_required"] is True and pubchem["applicability_domain_method"] is None
    assert rules["activation_status"] == pubchem["activation_status"] == "INACTIVE"
    assert rules["beta_eligibility_status"] == pubchem["beta_eligibility_status"] == "BLOCKED_LICENCE"


def test_reconciliation_detects_state_hash_endpoint_licence_and_artifact(isolated):
    migration.migrate("apply", isolated)
    baseline = reconciliation.reconcile("bbbp_v1", "v1")["items"][0]
    assert baseline["state"] == "ARTIFACT_UNAVAILABLE"
    with get_connection() as connection:
        row = connection.execute("SELECT record_json FROM scientific_engine_versions WHERE engine_id='bbbp_v1'").fetchone()
        data = json.loads(row[0]); data["model_hash"] = "wrong"
        connection.execute("UPDATE scientific_engine_versions SET record_json=? WHERE engine_id='bbbp_v1'", (registry._json(data),))
        link = connection.execute("SELECT id,snapshot_json FROM scientific_engine_legacy_links WHERE engine_id='bbbp_v1'").fetchone()
        snapshot = json.loads(link["snapshot_json"]); snapshot["model_hash"] = "expected"
        connection.execute("UPDATE scientific_engine_legacy_links SET snapshot_json=? WHERE id=?", (registry._json(snapshot), link["id"]))
    assert reconciliation.reconcile("bbbp_v1", "v1")["items"][0]["state"] == "HASH_MISMATCH"


def test_reconciliation_is_read_only_and_missing_link_is_reported(isolated):
    registry.register_engine(EngineCreate(engine_id="orphan", engine_name="Orphan", engine_family="test", engine_class="RULE_BASED_TOOL", provider_name="test", task_types=["TEST"], description="test"))
    registry.register_version("orphan", EngineVersionCreate(engine_version="1", adapter_id="test", adapter_version="1", runtime_type="python"))
    before = registry.get_version("orphan", "1")
    result = reconciliation.reconcile("orphan", "1")
    assert result["items"][0]["state"] == "LEGACY_LINK_MISSING"
    assert registry.get_version("orphan", "1") == before


def test_api_summary_capabilities_filters_reconciliation_and_redaction(isolated):
    migration.migrate("apply", isolated)
    client = TestClient(app)
    assert client.get("/api/scientific-engines/summary").json()["total_engines"] == 11
    assert client.get("/api/scientific-engines/capabilities").status_code == 200
    assert client.get("/api/scientific-engines/discover?engine_class=DATABASE_CONNECTOR").json()["total"] == 4
    assert client.get("/api/scientific-engines/discover?search=RDKit").json()["total"] == 1
    assert client.get("/api/scientific-engines/reconciliation").status_code == 200
    body = client.get("/api/scientific-engines/egfr_activity_v2/versions/v2").text
    assert "DRUG CONJUGATE" not in body and "DRUGDESIGN360_REAL_DATA" not in body
    readiness = client.get("/api/system/readiness").json()
    assert readiness["beta_approved_engine_count"] == 0
    assert readiness["runtime_compatibility_unverified_count"] > 0
    assert readiness["beta_approval_readiness"] == "BLOCKED"


def test_migration_api_is_local_admin_only(isolated):
    client = TestClient(app)
    assert client.post("/api/scientific-engines/migration/dry-run").status_code == 200
