from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version as package_version
import json
import platform
import time
from typing import Any, Callable
from uuid import uuid4

from fastapi import HTTPException
from rdkit import Chem

from app.database import get_connection, init_db
from app.models.scientific_engine_models import ScientificEngineExecutionRequest
from app.services import scientific_engine_registry_service as registry_service
from app.services.descriptors import calculate_descriptors, parse_smiles
from app.services.pubchem import PubChemLookupError, PubChemUnavailableError, resolve_compound
from app.services.rules import evaluate_rules


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class ScientificEngineAdapter(ABC):
    adapter_id = ""
    adapter_version = "1.0"
    engine_id = ""
    engine_version = ""
    tasks: tuple[str, ...] = ()
    endpoints: tuple[str, ...] = ()
    allowed_parameters: frozenset[str] = frozenset()
    registry_adapter_ids: tuple[str, ...] = ()

    def metadata(self) -> dict[str, Any]:
        return {"adapter_id": self.adapter_id, "adapter_version": self.adapter_version, "supported_engines": [{"engine_id": self.engine_id, "engine_version": self.engine_version}], "supported_tasks": list(self.tasks), "supported_endpoints": list(self.endpoints), "runtime_status": self.check_runtime()["status"]}

    def validate_request(self, request: ScientificEngineExecutionRequest) -> None:
        unknown = set(request.parameters) - self.allowed_parameters
        if unknown:
            raise ValueError(f"Unsupported parameters: {', '.join(sorted(unknown))}")

    def check_runtime(self) -> dict[str, str]:
        return {"status": "HEALTHY"}

    @abstractmethod
    def execute(self, request: ScientificEngineExecutionRequest) -> dict[str, Any]: ...

    def normalize_result(self, result: dict[str, Any]) -> dict[str, Any]:
        return result


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[tuple[str, str], ScientificEngineAdapter] = {}

    def register(self, adapter: ScientificEngineAdapter) -> None:
        key = (adapter.engine_id, adapter.engine_version)
        if key in self._adapters:
            raise ValueError(f"Duplicate adapter registration for {key[0]} {key[1]}")
        self._adapters[key] = adapter

    def resolve(self, engine_id: str, engine_version: str) -> ScientificEngineAdapter | None:
        return self._adapters.get((engine_id, engine_version))

    def list(self) -> list[dict[str, Any]]:
        return [adapter.metadata() for adapter in self._adapters.values()]


def _molecule(request: ScientificEngineExecutionRequest):
    molecule = request.inputs.get("molecule")
    if not isinstance(molecule, dict) or not isinstance(molecule.get("smiles"), str) or not molecule["smiles"].strip():
        raise ValueError("inputs.molecule.smiles is required")
    smiles = molecule["smiles"].strip()
    if "." in smiles:
        raise ValueError("Mixtures are not supported")
    return smiles, parse_smiles(smiles)


class RdkitDescriptorAdapter(ScientificEngineAdapter):
    adapter_id, engine_id, tasks, endpoints = "rdkit_descriptor_adapter", "rdkit_toolkit", ("DESCRIPTOR_CALCULATION",), ("molecular_descriptors",)
    registry_adapter_ids = ("rdkit",)

    def __init__(self, engine_version: str): self.engine_version = engine_version

    def execute(self, request):
        smiles, mol = _molecule(request)
        values = calculate_descriptors(smiles).model_dump()
        values["topological_polar_surface_area"] = values.pop("tpsa")
        values["heavy_atom_count"] = mol.GetNumHeavyAtoms()
        return {"result_type": "descriptor_set", "original_smiles": smiles, "canonical_smiles": Chem.MolToSmiles(mol, canonical=True), "values": values}


class MedicinalChemistryRulesAdapter(ScientificEngineAdapter):
    adapter_id, adapter_version, engine_id, engine_version = "medicinal_chemistry_rules_adapter", "1.0", "medicinal_chemistry_rule_filters", "1"
    tasks, endpoints = ("STRUCTURAL_ALERTS",), ("medicinal_chemistry_alerts",)
    registry_adapter_ids = ("rules.py + admet_rules.py",)

    def execute(self, request):
        smiles, _ = _molecule(request)
        rules = evaluate_rules(calculate_descriptors(smiles)).model_dump()
        return {"result_type": "rule_filter_set", "lipinski": rules["lipinski_rule_of_5"], "veber": rules["veber_rule"], "developability_risk": rules["developability_risk"], "reasons": rules["reasons"]}


class PubChemCompoundAdapter(ScientificEngineAdapter):
    adapter_id, adapter_version, engine_id, engine_version = "pubchem_compound_evidence_adapter", "1.0", "pubchem_connector", "PUG_REST"
    tasks, endpoints = ("DATABASE_EVIDENCE_RETRIEVAL",), ("compound_record",)
    registry_adapter_ids = ("pubchem.py",)

    def __init__(self, provider: Callable = resolve_compound): self.provider = provider

    def execute(self, request):
        query = request.inputs.get("query")
        if not isinstance(query, dict): raise ValueError("inputs.query is required")
        choices = [(key, value) for key, value in query.items() if key in {"compound_name", "cid", "canonical_smiles"} and value not in {None, ""}]
        if len(choices) != 1: raise ValueError("Exactly one supported PubChem query is required")
        key, value = choices[0]
        identity = self.provider(str(value), {"compound_name": "name", "cid": "cid", "canonical_smiles": "smiles"}[key]).model_dump()
        return {"result_type": "compound_record", "cid": identity.get("pubchem_cid"), "title": identity.get("compound_name"), "canonical_smiles": identity.get("canonical_smiles"), "isomeric_smiles": identity.get("isomeric_smiles"), "molecular_formula": identity.get("molecular_formula"), "molecular_weight": identity.get("molecular_weight"), "synonyms": (identity.get("synonyms") or [])[:12], "source_identifier": identity.get("pubchem_source_link")}


class BlockedBbbpAdapter(ScientificEngineAdapter):
    adapter_id, adapter_version, engine_id, engine_version = "bbbp_blocked_adapter", "1.0", "bbbp_v1", "v1"
    tasks, endpoints = ("ADME_PREDICTION",), ("bbbp_classification",)
    registry_adapter_ids = ("admet_endpoint_model_service",)
    def execute(self, request): raise RuntimeError("Blocked BBBP adapter must never execute")


def default_adapter_registry() -> AdapterRegistry:
    result = AdapterRegistry()
    try: rdkit_version = package_version("rdkit")
    except PackageNotFoundError: rdkit_version = "UNKNOWN"
    for adapter in (RdkitDescriptorAdapter(rdkit_version), MedicinalChemistryRulesAdapter(), PubChemCompoundAdapter(), BlockedBbbpAdapter()): result.register(adapter)
    return result


class ScientificEngineExecutionService:
    def __init__(self, adapters: AdapterRegistry | None = None, version_resolver: Callable = registry_service.get_version, engine_resolver: Callable = registry_service.get_engine, persist: bool = True):
        self.adapters, self.version_resolver, self.engine_resolver, self.persist = adapters or default_adapter_registry(), version_resolver, engine_resolver, persist

    @staticmethod
    def _block(version, request):
        if version.get("scientific_validation_status") == "REJECTED": return "BLOCKED_SCIENTIFIC_VALIDATION", "VALIDATION_REJECTED", "SCIENTIFIC_VALIDATION"
        licence = (version.get("licence_review") or {}).get("licence_review_status", "UNKNOWN")
        allowed = {"APPROVED_BETA"} if request.execution_context.deployment_profile.value in {"PUBLIC_DEMO", "LOCAL_DEMO"} else {"APPROVED_RESEARCH", "APPROVED_BETA"}
        if licence not in allowed: return "BLOCKED_LICENCE", "LICENCE_UNRESOLVED", "LICENCE_GOVERNANCE"
        if version.get("activation_status") not in ({"ACTIVE_BETA"} if request.execution_context.deployment_profile.value in {"PUBLIC_DEMO", "LOCAL_DEMO"} else {"ACTIVE_RESEARCH", "ACTIVE_BETA"}): return "BLOCKED_ACTIVATION", "ENGINE_INACTIVE", "ACTIVATION_GOVERNANCE"
        if version.get("technical_status") not in {"AVAILABLE", "NOT_APPLICABLE"}: return "BLOCKED_ARTIFACT", "ARTIFACT_UNVERIFIED", "ARTIFACT_VERIFICATION"
        if not version.get("execution_allowed", False) or version.get("runtime_compatibility_status") not in {"EXACT_VERSION_MATCH", "COMPATIBILITY_VERIFIED", "COMPATIBLE", "NOT_APPLICABLE"}: return "BLOCKED_RUNTIME", "RUNTIME_INCOMPATIBLE", "RUNTIME_COMPATIBILITY"
        permission = next((p for p in version.get("deployment_permissions", []) if p["deployment_profile"] == request.execution_context.deployment_profile.value), None)
        if not permission or not permission.get("permitted"): return "BLOCKED_DEPLOYMENT", "DEPLOYMENT_NOT_PERMITTED", "DEPLOYMENT_POLICY"

    def run(self, request: ScientificEngineExecutionRequest, execute: bool = True) -> dict[str, Any]:
        started, execution_id = time.perf_counter(), f"exec-{uuid4()}"
        request_id = request.request_id or f"req-{uuid4()}"
        try:
            engine, version = self.engine_resolver(request.engine_id), self.version_resolver(request.engine_id, request.engine_version)
        except HTTPException:
            return self._result(request, request_id, execution_id, "ADAPTER_NOT_FOUND", None, None, ("ENGINE_NOT_FOUND", "REGISTRY_RESOLUTION", "registry_resolution"), started)
        blocked = self._block(version, request)
        adapter = self.adapters.resolve(request.engine_id, request.engine_version)
        if blocked: return self._result(request, request_id, execution_id, blocked[0], engine, version, (blocked[1], blocked[2], "governance"), started)
        if not adapter: return self._result(request, request_id, execution_id, "ADAPTER_NOT_FOUND", engine, version, ("ADAPTER_NOT_FOUND", "ADAPTER_RESOLUTION", "adapter_resolution"), started)
        if version.get("adapter_id") not in {adapter.adapter_id, *adapter.registry_adapter_ids}: return self._result(request, request_id, execution_id, "ADAPTER_NOT_FOUND", engine, version, ("ADAPTER_REGISTRY_MISMATCH", "ADAPTER_RESOLUTION", "adapter_resolution"), started)
        if request.task_type not in adapter.tasks: return self._result(request, request_id, execution_id, "UNSUPPORTED_TASK", engine, version, ("UNSUPPORTED_TASK", "ADAPTER_RESOLUTION", "adapter_resolution"), started)
        if request.endpoint not in adapter.endpoints: return self._result(request, request_id, execution_id, "UNSUPPORTED_ENDPOINT", engine, version, ("UNSUPPORTED_ENDPOINT", "ADAPTER_RESOLUTION", "adapter_resolution"), started)
        try: adapter.validate_request(request)
        except ValueError as exc: return self._result(request, request_id, execution_id, "FAILED_VALIDATION", engine, version, ("INVALID_REQUEST", "REQUEST_VALIDATION", "request_validation", str(exc)), started)
        if not execute: return self._result(request, request_id, execution_id, "SUCCESS", engine, version, None, started, {"result_type": "validation", "execution_allowed": True}, persist=False)
        try: result = adapter.normalize_result(adapter.execute(request))
        except (ValueError, HTTPException) as exc: return self._result(request, request_id, execution_id, "FAILED_VALIDATION", engine, version, ("INVALID_INPUT", "INPUT_PROCESSING", "input_processing", str(getattr(exc, "detail", exc))), started)
        except PubChemUnavailableError as exc: return self._result(request, request_id, execution_id, "EXECUTION_FAILED", engine, version, ("PROVIDER_UNAVAILABLE", "ENGINE_EXECUTION", "engine_execution", str(exc)), started)
        except PubChemLookupError as exc: return self._result(request, request_id, execution_id, "EXECUTION_FAILED", engine, version, ("PROVIDER_LOOKUP_FAILED", "ENGINE_EXECUTION", "engine_execution", str(exc)), started)
        except Exception: return self._result(request, request_id, execution_id, "EXECUTION_FAILED", engine, version, ("ENGINE_EXECUTION_FAILED", "ENGINE_EXECUTION", "engine_execution"), started)
        return self._result(request, request_id, execution_id, "SUCCESS", engine, version, None, started, result)

    def _result(self, request, request_id, execution_id, status, engine, version, error, started, result=None, persist=True):
        adapter = self.adapters.resolve(request.engine_id, request.engine_version)
        duration = round((time.perf_counter() - started) * 1000, 3)
        evidence = "DATABASE_EVIDENCE" if request.engine_id == "pubchem_connector" else "RULE_BASED_HEURISTIC" if request.engine_id in {"rdkit_toolkit", "medicinal_chemistry_rule_filters"} else "MODEL_PREDICTION"
        limitations = list((version or {}).get("known_limitations") or [])
        if request.engine_id == "medicinal_chemistry_rule_filters": limitations.append("These filters are screening heuristics and do not establish efficacy, safety, toxicity, or developability.")
        errors = [] if not error else [{"code": error[0], "message": error[3] if len(error) > 3 else error[0].replace("_", " ").title(), "category": error[1], "stage": error[2], "retryable": error[0] in {"PROVIDER_UNAVAILABLE"}, "blocked_reason": error[0], "details": {}}]
        provenance = {"input_hash": _hash(request.inputs), "parameter_hash": _hash(request.parameters), "engine_registry_record": {"engine_id": request.engine_id, "engine_version": request.engine_version}, "adapter_version": adapter.adapter_version if adapter else None, "execution_date": datetime.now(timezone.utc).isoformat(), "runtime_environment": {"python": platform.python_version(), "system": platform.system()}, "package_versions": {}, "random_seed": request.random_seed, "output_hash": _hash(result) if result is not None else None, "deployment_profile": request.execution_context.deployment_profile.value}
        payload = {"contract_version": "1.0", "request_id": request_id, "execution_id": execution_id, "engine": {"engine_id": request.engine_id, "engine_name": (engine or {}).get("engine_name"), "engine_version": request.engine_version, "adapter_id": adapter.adapter_id if adapter else (version or {}).get("adapter_id"), "adapter_version": adapter.adapter_version if adapter else (version or {}).get("adapter_version"), "engine_class": (engine or {}).get("engine_class"), "model_status": (version or {}).get("model_status"), "validation_status": (version or {}).get("scientific_validation_status"), "licence_status": ((version or {}).get("licence_review") or {}).get("licence_review_status", "UNKNOWN"), "activation_status": (version or {}).get("activation_status"), "runtime_health": (version or {}).get("runtime_health_status")}, "task": {"task_type": request.task_type, "endpoint": request.endpoint, "target_id": request.target_id, "organism": request.organism, "molecule_type": request.molecule_type}, "status": status, "result": result, "evidence": {"evidence_type": evidence, "source_type": (engine or {}).get("engine_class"), "source_id": request.engine_id, "experimental_status": "NOT_EXPERIMENTAL", "prediction_status": "NOT_EXECUTED" if result is None else "EXECUTED"}, "applicability_domain": {"status": "NOT_APPLICABLE" if evidence != "MODEL_PREDICTION" else "DOMAIN_UNKNOWN", "method": None, "value": None, "in_domain_threshold": None, "borderline_threshold": None, "reference_set": None, "limitations": []}, "uncertainty": {"status": "NOT_APPLICABLE" if evidence != "MODEL_PREDICTION" else "UNKNOWN", "method": "NOT_APPLICABLE" if evidence != "MODEL_PREDICTION" else "UNKNOWN", "value": None, "lower_bound": None, "upper_bound": None, "confidence_level": None, "calibration_status": None, "limitations": []}, "provenance": provenance, "limitations": limitations, "warnings": [], "errors": errors, "timing": {"duration_ms": duration}}
        if self.persist and persist: self._audit(payload)
        return registry_service._public(payload)

    @staticmethod
    def _audit(payload):
        init_db()
        with get_connection() as connection:
            connection.execute("""INSERT INTO scientific_engine_executions (execution_id, request_id, engine_id, engine_version, adapter_id, adapter_version, task_type, endpoint, deployment_profile, status, input_hash, parameter_hash, output_hash, duration_ms, error_code) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (payload["execution_id"], payload["request_id"], payload["engine"]["engine_id"], payload["engine"]["engine_version"], payload["engine"]["adapter_id"], payload["engine"]["adapter_version"], payload["task"]["task_type"], payload["task"]["endpoint"], payload["provenance"]["deployment_profile"], payload["status"], payload["provenance"]["input_hash"], payload["provenance"]["parameter_hash"], payload["provenance"]["output_hash"], payload["timing"]["duration_ms"], payload["errors"][0]["code"] if payload["errors"] else None))
