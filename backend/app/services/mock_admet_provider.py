MOCK_WARNING = "Mock predictions are for software testing only and must not be used scientifically."
TASKS = ["solubility", "permeability", "bbb", "cyp_inhibition", "herg", "ames", "hepatotoxicity", "general_toxicity"]


def mock_predict(smiles: str) -> dict:
    return {
        "model_id": "external_admet_provider_v1",
        "model_name": "External ADMET Provider Adapter Mock",
        "version": "mock-1.0",
        "predictions": [
            {
                "task_name": task,
                "prediction_label": "mock_not_scientific",
                "prediction_score": None,
                "probability": None,
                "confidence": "none",
                "limitations": MOCK_WARNING,
            }
            for task in TASKS
        ],
        "warnings": [MOCK_WARNING],
    }
