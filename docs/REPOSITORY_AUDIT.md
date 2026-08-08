# Repository audit

The application is a modular FastAPI/React research system, not the small MVP implied by the API description. Its strongest existing assets are governed scientific-engine records, versioned model artifacts, dataset/domain validation, external-evidence workflows, transparent failure states, persistent caching, and multi-format reports.

Integration opportunities addressed here: shared configuration, opt-in predictor discovery, normalized multi-objective scoring, HTML reporting, and bounded RDKit calculation caches. The existing explainability, registry, reporting, and chemistry services were reused.

Duplication remains in several endpoint-specific ranking formulas, RDKit fingerprint constructors, report table builders, and HTTP retry loops. Consolidating them now could change frozen outputs, so they are documented rather than mechanically unified. The 117 KB final-report service is cohesive by output but expensive to maintain; extract only when a concrete change requires it. Static analysis did not justify deleting scientific/governance code whose entry points may be data-driven.

Likely performance costs are synchronous provider calls, repeated model discovery/loading, per-section final-report queries, domain nearest-neighbour scans, and image generation. Descriptor/fingerprint hot paths are now cached. Database-query consolidation and endpoint profiling need representative production data before optimization.

Scientific gaps: SHAP and molecular-fragment attribution are not universally available; model-native global feature importance remains explicitly non-causal. Docking and 3D visualization are inactive because their runtimes and protocols are absent. No prediction result, threshold, dataset, model weight, or activation state was changed.
