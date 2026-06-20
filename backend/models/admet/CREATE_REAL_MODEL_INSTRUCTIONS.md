# Creating a Real Local ADMET Model

This folder is prepared for future real ADMET/toxicity model artifacts. DrugScreen360 does not include a real trained local model by default.

## Steps

1. Train or obtain a real ADMET model only if you have permission to use it.
2. Scientifically validate the model with appropriate benchmark datasets before using outputs for decision support.
3. Place the model artifact files in this folder.
4. Copy `model_manifest.example.json` to `model_manifest.json`.
5. Edit `model_manifest.json` so it describes the real model.
6. List every required artifact file in `artifact_files`.
7. Set `LOCAL_ADMET_MODEL_ENABLED=true` in your backend environment.
8. Open the System tab and run Local ADMET Model Validation.

## Manifest

The active manifest must be named:

```text
model_manifest.json
```

Example:

```json
{
  "model_id": "local_admet_model_v1",
  "model_name": "Local ADMET Model",
  "version": "0.1.0",
  "tasks": ["herg", "ames", "hepatotoxicity"],
  "input_type": "rdkit_descriptors",
  "limitations": "Describe the training data, validation limits, and intended use.",
  "artifact_files": ["model.joblib", "metadata.json"]
}
```

## Supported Artifact Extensions

- `.pkl`
- `.joblib`
- `.onnx`
- `.json`

Large model files are ignored by Git. Do not commit private, licensed, or proprietary model artifacts.

## Scientific Safety

DrugScreen360 will not generate local model predictions just because files exist. A supported predictor loader must be implemented and the model must be scientifically validated first.

Do not use unvalidated model outputs to claim safety, efficacy, clinical success, regulatory approval, or market readiness.
