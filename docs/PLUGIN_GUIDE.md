# Predictor plugin guide

Install a plugin as `plugins/<plugin-id>/plugin.json` plus its Python module; core code does not need modification.

```json
{"plugin_id":"my-model","module":"plugin.py","enabled":false,"license":"Apache-2.0","version":"1.0.0"}
```

The module exports `create_adapter()`. Its object must have a unique string `model_id` and callable `is_available()`, `get_model_info()`, and `predict(smiles)` methods. `get_model_info()` returns the existing `ModelInfo`; `predict()` returns the existing `ModelPredictionBundle`.

Plugins default to disabled. Before enabling one, review source and weight licences, pin dependencies, record artifact/configuration hashes, test malformed inputs, and register validation/domain/uncertainty evidence. Plugins execute as trusted code in the API process; this is intentionally not a security sandbox. Use `DRUGSCREEN360_PLUGIN_DIRECTORY` to point at an alternate reviewed directory. Restart the API after changing plugins because discovery is cached.
