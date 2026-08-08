# DrugScreen360 predictor plugins

Create one directory per plugin containing `plugin.json` and a Python module. Plugins are disabled unless the manifest explicitly sets `"enabled": true`.

```json
{"plugin_id":"example","module":"plugin.py","enabled":false,"license":"Apache-2.0","version":"1.0.0"}
```

The module must expose `create_adapter()`. The returned object must have a unique `model_id` plus `is_available()`, `get_model_info()`, and `predict(smiles)` methods matching the existing predictor adapter contract. Local plugin code is trusted code and executes in the API process; review its license, provenance, hashes, and dependencies before enabling it.
