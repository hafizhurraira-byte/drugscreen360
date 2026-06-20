from datetime import datetime, timezone
from typing import Protocol

from app.models.model_registry_models import ModelInfo, ModelPredictionBundle, PredictionResult
from app.services.admet_toxicity_engine import evaluate_admet_toxicity
from app.services.admet_external_provider import check_external_provider_status, predict_external_admet

TASKS = [
    "solubility",
    "permeability",
    "BBB/CNS",
    "CYP inhibition",
    "hERG risk",
    "Ames mutagenicity",
    "hepatotoxicity",
    "general toxicity",
    "clearance/metabolism",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PredictorAdapter(Protocol):
    model_id: str

    def is_available(self) -> bool:
        ...

    def get_model_info(self) -> ModelInfo:
        ...

    def predict(self, smiles: str) -> ModelPredictionBundle:
        ...


class RuleBasedAdmetAdapter:
    model_id = "rule_based_admet_v1"
    model_name = "DrugScreen360 Rule-Based ADMET/Tox MVP"

    def is_available(self) -> bool:
        return True

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            model_id=self.model_id,
            model_name=self.model_name,
            model_type="rule_based",
            prediction_tasks=TASKS,
            status="available",
            version="1.0",
            source="Internal DrugScreen360 transparent rules",
            limitations=[
                "Rule-based early screen only.",
                "Not a validated ML, clinical, or regulatory prediction model.",
                "CYP, hERG, Ames, hepatotoxicity, and carcinogenicity models are not implemented.",
            ],
            last_checked_at=_now(),
        )

    def predict(self, smiles: str) -> ModelPredictionBundle:
        assessment = evaluate_admet_toxicity(smiles)
        info = self.get_model_info()
        predictions = [
            PredictionResult(
                task_name="solubility",
                prediction_label=assessment.solubility.solubility_risk,
                confidence=assessment.overall.confidence_level,
                model_id=self.model_id,
                model_name=self.model_name,
                model_status="available",
                limitations=info.limitations,
                warnings=assessment.solubility.reasons,
            ),
            PredictionResult(
                task_name="permeability",
                prediction_label=assessment.absorption.absorption_risk,
                confidence=assessment.overall.confidence_level,
                model_id=self.model_id,
                model_name=self.model_name,
                model_status="available",
                limitations=info.limitations,
                warnings=assessment.absorption.reasons,
            ),
            PredictionResult(
                task_name="BBB/CNS",
                prediction_label=assessment.bbb_cns_flag.bbb_exposure_flag,
                confidence=assessment.overall.confidence_level,
                model_id=self.model_id,
                model_name=self.model_name,
                model_status="available",
                limitations=[assessment.bbb_cns_flag.limitation],
                warnings=assessment.bbb_cns_flag.reasons,
            ),
            PredictionResult(
                task_name="general toxicity",
                prediction_label=assessment.structural_alerts.structural_alert_risk,
                prediction_score=assessment.overall.overall_admet_tox_concern_score,
                confidence=assessment.overall.confidence_level,
                model_id=self.model_id,
                model_name=self.model_name,
                model_status="available",
                limitations=assessment.limitations,
                warnings=assessment.structural_alerts.reasons,
            ),
            PredictionResult(
                task_name="CYP inhibition",
                prediction_label="not_implemented",
                confidence="Low",
                model_id=self.model_id,
                model_name=self.model_name,
                model_status="available",
                limitations=[assessment.metabolism_status.limitation],
                warnings=["No CYP inhibition model is implemented in the rule-based adapter."],
            ),
            PredictionResult(
                task_name="hERG risk",
                prediction_label="not_implemented",
                confidence="Low",
                model_id=self.model_id,
                model_name=self.model_name,
                model_status="available",
                limitations=[assessment.herg_status.limitation],
                warnings=["No hERG prediction model is implemented."],
            ),
            PredictionResult(
                task_name="Ames mutagenicity",
                prediction_label="not_implemented",
                confidence="Low",
                model_id=self.model_id,
                model_name=self.model_name,
                model_status="available",
                limitations=[assessment.ames_genotoxicity_status.limitation],
                warnings=["No Ames prediction model is implemented."],
            ),
            PredictionResult(
                task_name="hepatotoxicity",
                prediction_label="not_implemented",
                confidence="Low",
                model_id=self.model_id,
                model_name=self.model_name,
                model_status="available",
                limitations=[assessment.hepatotoxicity_status.limitation],
                warnings=["No hepatotoxicity prediction model is implemented."],
            ),
        ]
        return ModelPredictionBundle(
            model_id=self.model_id,
            model_name=self.model_name,
            model_status="available",
            prediction_source="Rule-based",
            confidence=assessment.overall.confidence_level,
            predictions=predictions,
            raw_output=assessment.model_dump(),
            warnings=["Only rule-based ADMET/Tox screening is available. No validated ML toxicity model is currently active."],
            limitations=assessment.limitations,
        )


class UnavailableAdapter:
    def __init__(self, model_id: str, model_name: str, model_type: str, source: str):
        self.model_id = model_id
        self.model_name = model_name
        self.model_type = model_type
        self.source = source

    def is_available(self) -> bool:
        return False

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            model_id=self.model_id,
            model_name=self.model_name,
            model_type=self.model_type,
            prediction_tasks=TASKS,
            status="unavailable",
            version=None,
            source=self.source,
            limitations=["No configured real model is installed or available for this adapter."],
            last_checked_at=_now(),
        )

    def predict(self, smiles: str) -> ModelPredictionBundle:
        info = self.get_model_info()
        return ModelPredictionBundle(
            model_id=self.model_id,
            model_name=self.model_name,
            model_status="unavailable",
            prediction_source="Model unavailable",
            confidence="None",
            predictions=[
                PredictionResult(
                    task_name=task,
                    prediction_label="not_available",
                    confidence="None",
                    model_id=self.model_id,
                    model_name=self.model_name,
                    model_status="unavailable",
                    limitations=info.limitations,
                    warnings=[f"{self.model_name} is unavailable; no prediction was generated."],
                )
                for task in TASKS
            ],
            warnings=[f"{self.model_name} is unavailable. No fake prediction was generated."],
            limitations=info.limitations,
        )


class ExternalAdmetProviderAdapter:
    model_id = "external_admet_provider_v1"
    model_name = "External ADMET Provider Adapter"

    def is_available(self) -> bool:
        return self.get_model_info().status in {"available", "mock"}

    def get_model_info(self) -> ModelInfo:
        return check_external_provider_status()

    def predict(self, smiles: str) -> ModelPredictionBundle:
        return predict_external_admet(smiles)


ADAPTERS: dict[str, PredictorAdapter] = {
    "rule_based_admet_v1": RuleBasedAdmetAdapter(),
    "external_admet_provider_v1": ExternalAdmetProviderAdapter(),
    "local_admet_model": UnavailableAdapter("local_admet_model", "Local ADMET Model Adapter", "ml_placeholder", "Local configured model"),
    "external_admet_service": UnavailableAdapter("external_admet_service", "External ADMET Service Adapter", "external_placeholder", "External service"),
    "tox_model_adapter": UnavailableAdapter("tox_model_adapter", "Toxicity Model Adapter", "ml_placeholder", "Future toxicity model"),
}


def get_adapters(model_ids: list[str] | None = None) -> list[PredictorAdapter]:
    if not model_ids:
        return list(ADAPTERS.values())
    return [ADAPTERS[model_id] for model_id in model_ids if model_id in ADAPTERS]


def model_status_response():
    infos = [adapter.get_model_info() for adapter in ADAPTERS.values()]
    return {
        "available_models": [info for info in infos if info.status in {"available", "mock"}],
        "unavailable_models": [info for info in infos if info.status not in {"available", "mock"}],
        "supported_tasks": TASKS,
        "limitations": [
            "Only rule-based ADMET/Tox screening is available by default unless an external provider is configured.",
            "Unavailable adapters do not generate fake predictions.",
            "Mock provider mode is for software testing only and must not be used scientifically.",
            "No clinical or regulatory validation is implied.",
        ],
    }
