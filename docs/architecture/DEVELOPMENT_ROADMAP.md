# Development Roadmap

## BETA-P3 pretrained ADME qualification

BETA-P3 completed the bounded official-source review of ADMET-AI, a DeepChem-based pretrained option, and no integration. No candidate passed every mandatory gate: ADMET-AI has unresolved explicit weight and endpoint-dataset rights plus v2-specific validation gaps, while no qualified frozen DeepChem ADME artifact was identified. No runtime, adapter, registry record, endpoint, or activation was added. See `docs/beta_p3_adme_candidate_review.md` and `docs/beta_p3_engine_selection_decision.md`.

This roadmap sequences DRUGDESIGN 360 from the current DrugScreen360 MVP toward the long-term five-system platform.

## Platform Versions

### V1: Research Drug Discovery Platform

Research-use compound screening, ADMET/toxicity evidence, model governance foundations, Disease-to-Lead workflows, reporting, and research export.

V1 is research-grade only. It may support research hypotheses, disease/mechanism investigation, target prioritization, drug discovery, experimental planning, and future research-grade personalized analysis. It must not claim autonomous diagnosis, clinical prescription, guaranteed treatment selection, clinical validation, or regulatory approval.

### V2: Precision Research Platform

Adds patient-specific research profiles, privacy/governance controls, and personalized assessment workflows. Not a prescribing tool.

### V3: Closed-Loop Biomedical Discovery Platform

Adds controlled laboratory integration, curated feedback, governed learning loops, and stronger cross-module evidence.

## M1 — Architecture Freeze

Objective: freeze target architecture and boundaries before production feature expansion.

Major deliverables:

- current-state audit.
- master architecture.
- module boundaries.
- shared evidence model.
- model/learning architecture.
- roadmap.
- architecture baseline freeze.

Scientific validation required:

- consistency with factual current state.
- no false capability upgrades.
- research-use-only language.

Dependencies:

- existing code audit.

Deferred:

- production feature implementation.
- refactors.
- schema migrations.

Exit criteria:

- architecture docs reviewed and accepted.
- future PR invariants defined.
- M1 Architecture Baseline v1 frozen for M2 planning.

## M2 — Drug Discovery 360 Scientific Core

Objective: extend and harden the existing drug discovery core instead of rebuilding it.

Major deliverables:

- real multi-endpoint ADMET models.
- activity model architecture.
- selectivity model architecture.
- improved external validation.
- applicability-domain enforcement.
- uncertainty reporting.
- asynchronous training architecture.
- background job lifecycle architecture for `QUEUED -> RUNNING -> SUCCEEDED / FAILED / CANCELLED`.
- model activation gates.
- docking architecture.
- molecular dynamics architecture.
- molecule generation architecture.
- lead optimization architecture.
- stronger candidate ranking.

Scientific validation required:

- benchmark datasets.
- leakage checks.
- calibration review.
- domain checks.
- evidence grading.

Dependencies:

- M1 architecture.
- existing RDKit, ChEMBL, PubChem, Open Targets, ADMET training/validation stack.

Deferred:

- precision medicine.
- laboratory automation.
- clinical claims.

Exit criteria:

- stronger Drug Discovery 360 reports without false evidence upgrades.
- tests preserve existing workflows.

## M3 — Evidence & Learning Core

BETA-P1A adds the non-executing scientific-engine registry and licence-governance foundation described in `docs/beta_p1a_scientific_engine_registry.md`; existing-engine migration and the registry UI are deferred to BETA-P1B.

BETA-P1B migrates implemented engines through deterministic manifests, adds read-only legacy reconciliation, and exposes the registry UI. Universal execution remains deferred to BETA-P2.

BETA-P1B corrective governance separates legacy execution from beta approval and blocks joblib model loading when artifact/runtime scikit-learn compatibility is unverified. No dependency upgrade, artifact rewrite, or prediction fallback is performed.

Objective: build the shared evidence and governed learning foundation.

Major deliverables:

- shared evidence record model.
- provenance chain.
- dataset versioning.
- model benchmark registry.
- family-specific activation policies.
- activation audit trail.
- rollback/retirement workflow.

Scientific validation required:

- evidence-type separation tests.
- provenance completeness checks.
- model/dataset lineage checks.

Dependencies:

- M1, M2.

Deferred:

- automatic production retraining.

Exit criteria:

- every important result is provenance-labelled.
- active models are governed and auditable.

## M4 — Diagnosis & Mechanism Intelligence

Objective: add disease, mechanism, pathway, and target intelligence.

Major deliverables:

- problem/symptoms/phenotype-first hypothesis workflow.
- confirmed disease-first mechanism workflow.
- mechanism profiles.
- gene/pathway analysis.
- target candidate packages.
- literature/database evidence integration.
- confirmatory-test recommendation as research support.

Scientific validation required:

- source provenance.
- evidence grading.
- no autonomous diagnosis claims.
- hypothesis generation separated from confirmed diagnosis context.

Dependencies:

- Evidence & Learning Core.

Deferred:

- patient-specific care decisions.

Exit criteria:

- disease/mechanism outputs feed Drug Discovery 360 cleanly.

## M5 — Precision Medicine

Objective: add patient-specific research assessment under strict governance.

Major deliverables:

- patient molecular profile concept.
- privacy/security architecture.
- personalized assessment workflow.
- cohort/context evidence.

Scientific validation required:

- privacy review.
- clinical governance boundaries.
- validation of interpretation methods.

Dependencies:

- M3, M4.

Deferred:

- prescribing.
- clinical decision automation.

Exit criteria:

- patient-specific mode remains distinct and research-labelled.

## M6 — Laboratory Intelligence

Objective: strengthen experimental planning and observation ingestion.

Major deliverables:

- experiment plan objects.
- observation provenance.
- assay metadata.
- result quality checks.
- lab connector architecture.

Scientific validation required:

- unit/source/replicate checks.
- qualified lab review boundaries.

Dependencies:

- M3 and Drug Discovery candidate packages.

Deferred:

- proprietary hardware.
- autonomous lab execution.

Exit criteria:

- real observations can be curated without being confused with predictions.

## M7 — Closed-Loop Biomedical Discovery

Objective: connect evidence, models, discovery, and lab observations into a governed closed loop.

Major deliverables:

- curated observation-to-dataset pipeline.
- benchmark against active models.
- controlled activation gate.
- cross-module evidence packages.

Scientific validation required:

- end-to-end audit trail.
- reproducible model lineage.
- external validation.
- rollback path.

Dependencies:

- M2-M6.

Deferred:

- uncontrolled self-learning.
- clinical automation.

Exit criteria:

- closed-loop research operation works under audit and evidence-type separation.
# BETA-P2 universal execution foundation

The versioned scientific-engine request/result/error contract, fail-closed adapter registry, reference adapters, execution audit, existing-job bridge, and minimal Scientific Engines execution panel are implemented in BETA-P2. See `docs/beta_p2_universal_engine_adapter.md` and `docs/beta_p2_execution_contract.md`. Existing scientific APIs remain parallel and unchanged; governed model adoption is deferred to BETA-P3.
