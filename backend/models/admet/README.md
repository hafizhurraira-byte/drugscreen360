# Local ADMET Model Folder

Place future real ADMET model artifacts in this folder.

Expected active manifest name:

```text
model_manifest.json
```

The included `model_manifest.example.json` is documentation only. DrugScreen360 does not treat it as an active model.

If `LOCAL_ADMET_MODEL_ENABLED=false`, the adapter is disabled. If enabled but `model_manifest.json` or listed artifact files are missing, the adapter reports `unavailable`. If the manifest is invalid JSON, the adapter reports `error`.

No real local model is bundled with this project, so predictions remain unavailable until a validated model and supported loader are supplied.
