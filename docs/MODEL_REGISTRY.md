# Model registry

DrugScreen360 has two complementary registries. `model_registry.py` is the backwards-compatible prediction facade used by `/api/models/*`; the governed scientific-engine registry stores versioned artifacts, validation, licence, deployment, applicability-domain, uncertainty, and activation state. New work must reuse these registries rather than create a third source of truth.

Each predictor exposes `model_id`, availability, `ModelInfo`, and `predict(smiles)`. Model metadata should identify the version, training date, metrics, code/model/data licences, artifact hash, applicability-domain method, uncertainty method, validation state, and limitations. The governed registry is authoritative when fields overlap.

Built-in adapters remain unchanged. Locally reviewed plugins are merged by `get_adapters()` and appear in `/api/models/status`. Registry or plugin failure must not produce a synthetic scientific result.

Model weights and frozen thresholds are artifacts, never configuration defaults. Activation remains an explicit governed operation.
