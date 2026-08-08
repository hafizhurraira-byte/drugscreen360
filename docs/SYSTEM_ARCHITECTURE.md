# System architecture

The React/Vite client calls a FastAPI API. Routers validate transport contracts and delegate to services. Chemistry uses RDKit; prediction routes through model adapters and the governed scientific-engine registry; SQLite currently stores projects, provenance, cached provider responses, registry state, and generated-report metadata. Artifact directories hold frozen models and domain references. Report services export JSON, PDF, DOCX, and now self-contained HTML.

Existing service boundaries already cover chemistry (`descriptors`, rules, similarity), prediction/inference (activity and ADMET services), explainability (`admet_explain_service`), model governance (model and scientific-engine registries), scoring (legacy rankers and the normalized multi-objective scorer), reporting, caching, and external evidence connectors. Docking is represented in the governed engine taxonomy but has no active adapter because AutoDock Vina is not installed or scientifically configured.

Configuration is loaded from JSON-compatible YAML in `config/platform.yaml`, with environment overrides documented in `.env.example`. This avoids another runtime dependency while remaining valid YAML. Repeated descriptor and fingerprint calculations use bounded in-process LRU caches; remote responses retain the existing persistent SQLite cache.

Important boundaries: model artifacts remain immutable; unavailable engines fail closed; external evidence is distinct from prediction; applicability domain and uncertainty accompany model evidence; plugins are trusted local code and disabled by default.

Known bottlenecks are repeated report-wide database reads in the large final-report assembler, synchronous external HTTP calls, model loading, and large domain-reference comparisons. Measure before changing these paths; batching DB reads and process-aware caches are the next justified optimizations.
