# DrugScreen360 overnight hardening report

Date: 2026-08-06  
Repository baseline: `main` at `44bfdbc26335244c4adcfed880d73f5a483d401c`

## Completed work

- Audited the existing FastAPI/React architecture and reused its mature chemistry, model-registry, explainability, validation, caching, and reporting services.
- Added JSON-compatible YAML configuration with environment overrides and an environment template.
- Added opt-in `/plugins/<id>/` predictor discovery without changing built-in adapters. Plugins remain disabled by default and use the existing prediction contract.
- Added validated, configurable multi-objective ranking for EGFR, ADMET, confidence, inverse uncertainty, and applicability domain at `POST /api/platform/rank`.
- Added self-contained scientific HTML reports at `POST /api/platform/report/html`, including compound structure, supplied predictions/ADMET/confidence/uncertainty/explanations/ranking, charts, metadata, timestamp, and RDKit version.
- Added bounded in-process caches for repeated descriptor and Morgan-fingerprint calculations while retaining the persistent remote-response cache.
- Removed unused LGPL `chardet`; replaced out-of-allowlist ISC `lucide-react` with MIT `react-icons`; updated vulnerable PostCSS to 8.5.24.
- Added focused unit/API/report/ranking/plugin/cache tests and the requested architecture, registry, plugin, scoring, licence, and repository-audit documents.

No model weight, threshold, dataset, prediction algorithm, frozen result, database migration, activation state, or existing ranking formula was changed.

## Modified files

Core integration: `backend/app/main.py`, `backend/app/config.py`, `backend/app/models/platform_models.py`, `backend/app/routers/platform.py`, `backend/app/services/multi_objective_scoring_service.py`, `backend/app/services/scientific_html_report_service.py`, `backend/app/services/plugin_service.py`, `backend/app/services/model_registry.py`, and `backend/app/models/model_registry_models.py`.

Performance: `backend/app/services/descriptors.py`, `backend/app/services/similarity_service.py`.

Dependencies/UI: `backend/requirements.txt`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/App.jsx`, `.env.example`, `config/platform.yaml`.

Tests/docs: `backend/tests/test_platform_extensions.py`, `plugins/README.md`, and the new documents under `docs/`.

## Validation evidence

- Focused backend regression set: 30 passed (`test_platform_extensions`, `test_trained_model`, `test_finder`).
- New extension suite alone: 4 passed.
- Backend import/bytecode compilation: passed.
- `pip check`: no broken requirements.
- Backend collection: 343 tests collected successfully.
- Full backend suite: inconclusive; one monolithic run reached a 15-minute timeout with no pytest output, and three parallel file batches reached an 8-minute orchestration timeout. No failure trace was emitted. This is recorded as a test-runtime bottleneck, not reported as a pass.
- Frontend tests: passed.
- Frontend production build: passed (Vite 6.4.3).
- `npm audit --audit-level=moderate`: zero vulnerabilities.
- `git diff --check`: passed.

There is no configured backend linter or static type-check command, and none was invented or silently substituted.

## Remaining tasks and known limitations

- SHAP is not installed. Existing trained-model explainability exposes model-native feature importance or coefficients and clearly labels them global/non-causal. Universal local SHAP and validated molecular-fragment attribution remain unimplemented; adding them requires estimator-specific background datasets and scientific validation.
- AutoDock Vina, DeepChem, Chemprop, XGBoost, py3Dmol, and NGL are not installed or scientifically configured. The registry can govern future adapters, but placeholder scientific results were not created.
- HTML charting uses dependency-free accessible tables/bars and RDKit 2D structures. Fingerprint similarity is available in the existing similarity workflow but is not fabricated when a report request lacks a reference molecule.
- Plugins are trusted in-process Python, not an isolation/security boundary. Use containers or a worker boundary if third-party untrusted code must be accepted.
- In-process LRU caches are per worker and reset on restart. Add a shared cache only after multi-worker profiling demonstrates a need.
- The active global Python environment differs from several pinned backend versions. Production validation should use a fresh environment built exactly from `backend/requirements.txt`.

## Scientific and licence risks

- Multi-objective weights express prioritization policy, not biological truth. Preserve weights with each report and do not tune them on protected evaluation data.
- Explanations, applicability-domain classifications, and uncertainty are model/dataset dependent and must not be interpreted as causal, clinical, or regulatory evidence.
- Plugin code, model weights, training data, and reference-database terms require separate review; a permissive code licence alone is insufficient.
- Direct declared dependencies now fit the requested allowlist. A production SBOM and transitive Python audit should be generated inside the pinned deployment environment before release.

## Recommendations

1. Profile backend tests per file in CI with elapsed-time and network isolation; then set explicit unit/integration markers and timeouts.
2. Pilot SHAP on one validated tree model using a frozen training-only background set before extending the response contract.
3. Add a Vina or 3D viewer adapter only with an explicit protocol, fixed versions, licence evidence, artifact hashes, and validation fixtures.
4. Measure final-report database query counts with representative projects before consolidating its large assembler.
