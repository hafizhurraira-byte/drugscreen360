from datetime import datetime, timezone
from typing import Protocol

from app.models.model_registry_models import ModelInfo, ModelPredictionBundle, PredictionResult
from app.services.admet_toxicity_engine import evaluate_admet_toxicity
from app.services.admet_external_provider import check_external_provider_status, predict_external_admet
from app.services.local_admet_model import check_local_admet_model_status, predict_local_admet
from app.services.admet_trained_model_service import get_active_trained_model_info, predict_trained_model
from app.services.admet_endpoint_model_service import list_admet_models, predict_admet_endpoints
from app.services.plugin_service import discover_plugins, load_plugin_adapters


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


class LocalAdmetModelAdapter:
    model_id = "local_admet_model"
    model_name = "Local ADMET Model Adapter"

    def is_available(self) -> bool:
        return self.get_model_info().status == "available"

    def get_model_info(self) -> ModelInfo:
        return check_local_admet_model_status()

    def predict(self, smiles: str) -> ModelPredictionBundle:
        return predict_local_admet(smiles)


class TrainedLocalAdmetModelAdapter:
    model_id = "trained_local_admet_model"
    model_name = "Experimental Trained Local ADMET Model"

    def is_available(self) -> bool:
        return self.get_model_info().status == "available"

    def get_model_info(self) -> ModelInfo:
        info = get_active_trained_model_info()
        status = info["status"]
        warning = "; ".join(info.get("warnings", [])) if info.get("warnings") else None
        tasks = [info["task_name"]] if info.get("task_name") else ["admet_task"]
        version = info.get("version")
        limitations = [
            "Experimental local model prediction. Requires external validation.",
            "All predictions are dataset-dependent and computationally inferred."
        ]
        return ModelInfo(
            model_id=self.model_id,
            model_name=self.model_name,
            model_type="trained_local_model",
            prediction_tasks=tasks,
            status=status,
            input_type="smiles",
            version=version,
            source=f"Trained model: {info.get('model_name')}" if info.get("model_name") else "Local trained models directory",
            limitations=limitations,
            last_checked_at=_now(),
            enabled=status == "available",
            model_dir=None,
            manifest_found=status != "unavailable",
            artifacts_found=status == "available",
            warning=warning,
        )

    def predict(self, smiles: str) -> ModelPredictionBundle:
        info = self.get_model_info()
        if info.status != "available":
            return ModelPredictionBundle(
                model_id=self.model_id,
                model_name=self.model_name,
                model_status=info.status,
                prediction_source="Trained model unavailable",
                confidence="None",
                predictions=[],
                raw_output=None,
                warnings=[info.warning or "Trained local model is not active."],
                limitations=info.limitations,
            )
        try:
            res = predict_trained_model(smiles)
            pred_label = res["prediction_label"] if res["prediction_label"] is not None else str(res["prediction_value"])
            predictions = [
                PredictionResult(
                    task_name=res["task_name"],
                    prediction_label=pred_label,
                    prediction_score=res["prediction_score"],
                    probability=res["prediction_score"],
                    confidence="Experimental local model prediction. Requires external validation.",
                    model_id=self.model_id,
                    model_name=self.model_name,
                    model_status="available",
                    limitations=res["limitations"],
                    warnings=res["warnings"] + ["Experimental local model prediction. Requires external validation."],
                    domain_status=res.get("domain_status"),
                    uncertainty_level=res.get("uncertainty_level"),
                    nearest_training_distance=res.get("nearest_training_distance"),
                    out_of_range_features=res.get("out_of_range_features"),
                )
            ]
            explanation_summary = {
                "domain_status": res.get("domain_status") or "not_available",
                "uncertainty_level": res.get("uncertainty_level") or "unknown",
                "top_features": [],
                "evidence_strength": "not_calculated",
                "warning": "Detailed evidence strength is available from /api/admet-explain/prediction.",
            }
            try:
                from app.services.admet_explain_service import _important_features
                from app.services.admet_trained_model_service import discover_trained_models

                actual_model_id = res.get("model_id")
                summary = next((item for item in discover_trained_models() if item["model_id"] == actual_model_id), None)
                if summary:
                    features, _, _ = _important_features(summary)
                    explanation_summary["top_features"] = [feature.model_dump() for feature in features[:3]]
            except Exception as exc:
                explanation_summary["warning"] = f"Short explanation summary unavailable: {exc}"

            return ModelPredictionBundle(
                model_id=self.model_id,
                model_name=self.model_name,
                model_status="available",
                prediction_source=f"Experimental trained local model ({res['model_name']})",
                confidence="Experimental local model prediction. Requires external validation.",
                predictions=predictions,
                raw_output=res,
                warnings=res["warnings"] + ["Experimental local model prediction. Requires external validation."],
                limitations=res["limitations"],
                metadata={"explanation_summary": explanation_summary},
            )
        except Exception as e:
            return ModelPredictionBundle(
                model_id=self.model_id,
                model_name=self.model_name,
                model_status="error",
                prediction_source="Trained model prediction error",
                confidence="None",
                predictions=[],
                raw_output=None,
                warnings=[f"Failed to generate prediction: {e}"],
                limitations=info.limitations,
            )


class MultiEndpointAdmetAdapter:
    model_id = "multi_endpoint_admet_v1"
    model_name = "M2C Multi-Endpoint ADMET Models"

    def is_available(self) -> bool:
        return any(item.get("active") for item in list_admet_models()["models"])

    def get_model_info(self) -> ModelInfo:
        models = list_admet_models()["models"]
        active = [item["endpoint"] for item in models if item.get("active")]
        return ModelInfo(
            model_id=self.model_id,
            model_name=self.model_name,
            model_type="endpoint_specific_trained_models",
            prediction_tasks=active or ["bbbp", "esol", "herg", "clintox_cttox"],
            status="available" if active else "unavailable",
            version="v1",
            source="Registered M2C-2 frozen ADMET artifacts",
            limitations=[
                "Research-use computational predictions only.",
                "ClinTox v1 is rejected and does not provide production predictions.",
                "Endpoint-specific warnings must be reviewed.",
            ],
            last_checked_at=_now(),
            warning=None if active else "No active M2C endpoint models are available.",
        )

    def predict(self, smiles: str) -> ModelPredictionBundle:
        info = self.get_model_info()
        if info.status != "available":
            return ModelPredictionBundle(
                model_id=self.model_id,
                model_name=self.model_name,
                model_status="unavailable",
                prediction_source="M2C endpoint models unavailable",
                confidence="None",
                predictions=[],
                warnings=[info.warning or "No active endpoint models are available."],
                limitations=info.limitations,
            )
        raw = predict_admet_endpoints(smiles, ["bbbp", "esol", "herg", "clintox_cttox"])
        predictions = []
        warnings = []
        for item in raw["results"]:
            warnings.extend(item.get("warnings") or [])
            pred = item.get("prediction") or {}
            score = pred.get("predicted_logS")
            label = str(pred.get("predicted_class") if "predicted_class" in pred else pred.get("predicted_logS", item.get("status")))
            probability = next((v for k, v in pred.items() if k.startswith("probability_")), None)
            predictions.append(
                PredictionResult(
                    task_name=item["endpoint"],
                    prediction_label=label,
                    prediction_score=score if isinstance(score, (int, float)) else probability,
                    probability=probability,
                    confidence="Model prediction with endpoint-specific limitations" if item.get("status") == "available" else "None",
                    model_id=self.model_id,
                    model_name=self.model_name,
                    model_status="available" if item.get("status") == "available" else "unavailable",
                    limitations=item.get("limitations") or [],
                    warnings=item.get("warnings") or [],
                    domain_status=item.get("domain_status"),
                    uncertainty_level="endpoint_specific",
                )
            )
        return ModelPredictionBundle(
            model_id=self.model_id,
            model_name=self.model_name,
            model_status="available",
            prediction_source="M2C frozen endpoint-specific ADMET models",
            confidence="Endpoint-specific; review domain and calibration warnings",
            predictions=predictions,
            raw_output=raw,
            warnings=list(dict.fromkeys(warnings)),
            limitations=info.limitations,
        )


ADAPTERS: dict[str, PredictorAdapter] = {
    "rule_based_admet_v1": RuleBasedAdmetAdapter(),
    "external_admet_provider_v1": ExternalAdmetProviderAdapter(),
    "local_admet_model": LocalAdmetModelAdapter(),
    "trained_local_admet_model": TrainedLocalAdmetModelAdapter(),
    "multi_endpoint_admet_v1": MultiEndpointAdmetAdapter(),
    "external_admet_service": UnavailableAdapter("external_admet_service", "External ADMET Service Adapter", "external_placeholder", "External service"),
    "tox_model_adapter": UnavailableAdapter("tox_model_adapter", "Toxicity Model Adapter", "ml_placeholder", "Future toxicity model"),
}


def get_adapters(model_ids: list[str] | None = None) -> list[PredictorAdapter]:
    adapters = {**ADAPTERS, **load_plugin_adapters()}
    if not model_ids:
        return list(adapters.values())
    return [adapters[model_id] for model_id in model_ids if model_id in adapters]


def model_status_response():
    infos = [adapter.get_model_info() for adapter in get_adapters()]
    return {
        "available_models": [info for info in infos if info.status in {"available", "mock"}],
        "unavailable_models": [info for info in infos if info.status not in {"available", "mock"}],
        "supported_tasks": TASKS,
        "plugins": list(discover_plugins()),
        "limitations": [
            "Only rule-based ADMET/Tox screening is available by default unless an external provider is configured.",
            "Unavailable adapters do not generate fake predictions.",
            "Mock provider mode is for software testing only and must not be used scientifically.",
            "No clinical or regulatory validation is implied.",
        ],
    }
