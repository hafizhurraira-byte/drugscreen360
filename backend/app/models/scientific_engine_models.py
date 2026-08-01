from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RegistryEnum(str, Enum):
    pass


class EngineClass(RegistryEnum):
    INTERNAL_MODEL = "INTERNAL_MODEL"
    EXTERNAL_PRETRAINED_MODEL = "EXTERNAL_PRETRAINED_MODEL"
    RULE_BASED_TOOL = "RULE_BASED_TOOL"
    DATABASE_CONNECTOR = "DATABASE_CONNECTOR"
    CHEMISTRY_TOOLKIT = "CHEMISTRY_TOOLKIT"
    STRUCTURAL_ENGINE = "STRUCTURAL_ENGINE"
    DOCKING_ENGINE = "DOCKING_ENGINE"
    SIMULATION_ENGINE = "SIMULATION_ENGINE"
    OMICS_ENGINE = "OMICS_ENGINE"
    PATHWAY_ENGINE = "PATHWAY_ENGINE"
    WORKFLOW_ENGINE = "WORKFLOW_ENGINE"


class TechnicalStatus(RegistryEnum):
    NOT_CHECKED = "NOT_CHECKED"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    MISCONFIGURED = "MISCONFIGURED"
    ARTIFACT_MISSING = "ARTIFACT_MISSING"
    ARTIFACT_HASH_MISMATCH = "ARTIFACT_HASH_MISMATCH"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"


class ValidationStatus(RegistryEnum):
    UNREVIEWED = "UNREVIEWED"
    DOCUMENTED = "DOCUMENTED"
    TECHNICALLY_VERIFIED = "TECHNICALLY_VERIFIED"
    SCIENTIFICALLY_REVIEWED = "SCIENTIFICALLY_REVIEWED"
    VALIDATED_FOR_SCOPE = "VALIDATED_FOR_SCOPE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REJECTED = "REJECTED"


class ModelStatus(RegistryEnum):
    EXTERNAL_VALIDATED = "EXTERNAL_VALIDATED"
    INTERNAL_VALIDATED = "INTERNAL_VALIDATED"
    EXPERIMENTAL_INTERNAL = "EXPERIMENTAL_INTERNAL"
    BASELINE = "BASELINE"
    UNSUPPORTED = "UNSUPPORTED"


class ActivationStatus(RegistryEnum):
    INACTIVE = "INACTIVE"
    ACTIVE_RESEARCH = "ACTIVE_RESEARCH"
    ACTIVE_BETA = "ACTIVE_BETA"
    BLOCKED_LICENCE = "BLOCKED_LICENCE"
    BLOCKED_VALIDATION = "BLOCKED_VALIDATION"
    BLOCKED_ARTIFACT = "BLOCKED_ARTIFACT"
    BLOCKED_CONFIGURATION = "BLOCKED_CONFIGURATION"
    RETIRED = "RETIRED"


class RuntimeHealthStatus(RegistryEnum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class LicenceStatus(RegistryEnum):
    NOT_REVIEWED = "NOT_REVIEWED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED_RESEARCH = "APPROVED_RESEARCH"
    APPROVED_BETA = "APPROVED_BETA"
    RESTRICTED = "RESTRICTED"
    COMMERCIAL_REVIEW_REQUIRED = "COMMERCIAL_REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class DeploymentProfile(RegistryEnum):
    LOCAL_RESEARCH = "LOCAL_RESEARCH"
    LOCAL_DEMO = "LOCAL_DEMO"
    PUBLIC_DEMO = "PUBLIC_DEMO"
    CI_TEST = "CI_TEST"


class EngineCreate(BaseModel):
    engine_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_.-]+$")
    engine_name: str = Field(min_length=1)
    engine_family: str = Field(min_length=1)
    engine_class: EngineClass
    provider_name: str = Field(min_length=1)
    task_types: list[str] = Field(min_length=1)
    description: str = Field(min_length=1)
    repository: str | None = None
    official_documentation: str | None = None
    publication: str | None = None
    maintainer: str | None = None
    registry_schema_version: str = "1.0"


class LicenceReview(BaseModel):
    code_licence: str | None = None
    model_weights_licence: str | None = None
    training_data_licence: str | None = None
    reference_database_terms: str | None = None
    academic_use_allowed: bool | None = None
    commercial_use_allowed: bool | None = None
    redistribution_allowed: bool | None = None
    model_weight_redistribution_allowed: bool | None = None
    citation_required: bool | None = None
    licence_review_status: LicenceStatus
    licence_reviewed_by: str | None = None
    licence_reviewed_at: str | None = None
    licence_evidence_reference: str | None = None
    licence_notes: str | None = None


class DeploymentPermission(BaseModel):
    deployment_profile: DeploymentProfile
    permitted: bool
    reason: str | None = None


class EngineVersionCreate(BaseModel):
    engine_version: str = Field(min_length=1)
    adapter_id: str = Field(min_length=1)
    adapter_version: str = Field(min_length=1)
    runtime_type: str = Field(min_length=1)
    package_name: str | None = None
    package_version: str | None = None
    container_digest: str | None = None
    artifact_identifier: str | None = None
    artifact_hash: str | None = None
    configuration_hash: str | None = None
    input_schema_version: str | None = None
    output_schema_version: str | None = None
    supported_endpoints: list[str] = []
    supported_organisms: list[str] = []
    supported_targets: list[str] = []
    supported_target_classes: list[str] = []
    supported_molecule_types: list[str] = []
    local_execution_supported: bool = False
    api_execution_supported: bool = False
    internet_required: bool = False
    credentials_required: bool = False
    hardware_requirements: dict[str, Any] | None = None
    training_data_information: dict[str, Any] | None = None
    applicability_domain_method: str | None = None
    uncertainty_method: str | None = None
    known_limitations: list[str] = []
    technical_status: TechnicalStatus = TechnicalStatus.NOT_CHECKED
    scientific_validation_status: ValidationStatus = ValidationStatus.UNREVIEWED
    model_status: ModelStatus | None = None
    activation_status: ActivationStatus = ActivationStatus.INACTIVE
    runtime_health_status: RuntimeHealthStatus = RuntimeHealthStatus.UNKNOWN
    failure_policy: str = Field(default="FAIL_CLOSED", pattern=r"^(FAIL_CLOSED|RETURN_PARTIAL|SKIP_ENDPOINT|RETRY_BOUNDED|MANUAL_REVIEW)$")
    fallback_policy: str = Field(default="NO_FALLBACK", pattern=r"^(NO_FALLBACK|FALLBACK_TO_SPECIFIC_ENGINE|FALLBACK_TO_RULE_BASED_WITH_LABEL|MANUAL_SELECTION_REQUIRED)$")
    timeout_policy: dict[str, Any] | None = None
    partial_result_policy: dict[str, Any] | None = None
    dataset_hash: str | None = None
    split_hash: str | None = None
    model_hash: str | None = None
    decision_threshold: float | None = None
    prediction_unit: str | None = None
    feature_representation: str | None = None
    internal_validation: dict[str, Any] | None = None
    external_validation: dict[str, Any] | None = None
    calibration_status: str | None = None
    authoritative_state: str | None = None
    blocked_reason: str | None = None
    deployment_permissions: list[DeploymentPermission] = []


class ValidationReview(BaseModel):
    scientific_validation_status: ValidationStatus
    reviewed_by: str = Field(min_length=1)
    notes: str | None = None


class ActivationRequest(BaseModel):
    activation_status: ActivationStatus
    deployment_profile: DeploymentProfile
    initiated_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class DeactivationRequest(BaseModel):
    initiated_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ArtifactVerification(BaseModel):
    artifact_hash: str | None = None
    artifact_exists: bool

