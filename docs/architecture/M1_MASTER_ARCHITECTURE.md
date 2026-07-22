# DRUGDESIGN 360 M1 Master Architecture

This document freezes the intended long-term DRUGDESIGN 360 architecture. It is a target architecture, not a claim that every capability currently exists.

Source-of-truth constraint: `docs/architecture/CURRENT_STATE_GAP_ANALYSIS.md` defines the current implemented platform state as of M1.

## Architecture Baseline

Baseline name: M1 Architecture Baseline v1

Status: Frozen for M2 planning

Future architecture changes require an explicit Architecture Decision Record. Silent drift from this baseline is not allowed.

## 1. Platform Mission

DRUGDESIGN 360 is one unified research-use computational evidence platform for connecting biomedical problems, mechanisms, targets, compounds, model evidence, laboratory planning, and curated learning loops.

The platform supports scientific decision-making by organizing evidence and computational outputs. It does not autonomously diagnose, prescribe, clinically validate treatments, or prove safety, efficacy, regulatory approval, or market readiness.

## 2. Scientific Scope

The long-term platform may support:

- Disease, mechanism, gene, pathway, and target interpretation.
- Drug repurposing and molecular screening.
- ADMET/toxicity modeling and evidence review.
- Candidate ranking and computational validation planning.
- Patient-specific research assessment when appropriate data and governance exist.
- Laboratory planning and result ingestion.
- Controlled model learning from curated, versioned evidence.

Current implemented scope is narrower: local single-user DrugScreen360 compound screening, external source lookup, ADMET dataset curation/training/validation, disease-to-lead orchestration, reporting, and research export.

## 3. Non-Goals

The platform must not claim or imply:

- Autonomous clinical diagnosis.
- Medical prescription or treatment recommendation.
- Clinical safety, clinical efficacy, approval, or regulatory readiness.
- Real docking, molecular dynamics, de novo molecule generation, or precision medicine before those systems are implemented and validated.
- Automatic production retraining from user interaction.
- Experimental validation unless a user imports real experimental observations.

## 4. Five-System Architecture

### A. Diagnosis & Mechanism Intelligence

Interprets research problems, symptoms, diseases, mechanisms, genes, pathways, and targets. It produces evidence-labelled hypotheses and target candidates.

Valid entry paths:

- Problem/symptoms/phenotype-first: problem interpretation -> hypotheses -> evidence gaps -> recommended confirmatory tests -> mechanism analysis.
- Confirmed disease-first: confirmed disease context -> mechanism -> genes/pathways -> target prioritization.

The platform must clearly distinguish hypothesis generation from confirmed diagnosis.

### B. Drug Discovery 360

Owns compound discovery, repurposing, screening, similarity, molecular evidence, activity/selectivity architecture, ADMET/toxicity evidence, lead optimization architecture, and candidate ranking.

Drug repurposing is primarily owned here. Precision Medicine may consume repurposing candidates and re-rank them with patient-specific molecular and clinical research evidence, but it must not duplicate the repurposing engine.

### C. Precision Medicine

Owns patient-specific molecular profiles, personalized research assessment, genotype/phenotype context, and cohort-aware interpretation. It remains separate from general drug discovery.

### D. Laboratory Intelligence

Owns experiment planning, assay recommendation, laboratory result ingestion, experimental observation tracking, and comparison of observed results with computational expectations.

### E. Shared Evidence & Learning Core

Owns evidence provenance, evidence quality grading, dataset curation, model registry, model validation, calibration, applicability domain, uncertainty, explainability governance, controlled learning, and model activation gates.

## 5. Shared Platform Infrastructure

Shared infrastructure includes:

- API gateway and routing.
- Authentication and access control when multi-user mode exists.
- Database and storage.
- Project/workspace management.
- Report generation and research export.
- Audit logging and reproducibility metadata.
- Background job orchestration when long tasks are introduced.
- UI shell and shared components.
- System readiness and health checks.

SQLite remains acceptable for local, single-user V1. Repository/service boundaries must allow later migration to PostgreSQL or another production database. M1 does not migrate databases.

Future UI remains one application with module workspaces: Diagnosis & Mechanism, Drug Discovery, Precision Medicine, Laboratory Intelligence, and Evidence / Models / Administration. The current monolithic `App.jsx` must be decomposed incrementally without changing scientific behavior or tests.

Long-running work eventually moves out of synchronous HTTP handling. This includes model training, external validation, docking, molecular dynamics, batch screening, molecular generation, and large report workflows. Conceptual job lifecycle: `QUEUED -> RUNNING -> SUCCEEDED / FAILED / CANCELLED`, with job ID, progress, timestamps, logs/status, provenance, input snapshot, output references, and reproducibility metadata. Implementation is deferred to M2.

## 6. End-to-End Workflows

Long-term conceptual flow:

```text
Problem / research question / symptoms / disease / target / patient data
-> problem interpretation
-> disease hypotheses when appropriate
-> evidence and recommended confirmatory tests
-> mechanism analysis
-> genes/pathways
-> target prioritization
-> existing treatment assessment
-> drug repurposing
-> molecular screening
-> novel molecule generation
-> lead optimization
-> activity/selectivity
-> ADMET/toxicity
-> ranked candidate package
-> patient-specific personalization when appropriate
-> experimental planning
-> laboratory validation
-> experimental result ingestion
-> evidence curation
-> controlled model learning and activation
```

Not every workflow requires every step. Missing data must remain visible.

## 7. Research Mode vs Patient-Specific Mode

Research mode:

- Default mode.
- Uses public databases, uploaded datasets, computational models, and user-provided research context.
- Produces research evidence packages and computational decision-support reports.

Patient-specific mode:

- Future capability only.
- Requires patient consent, privacy controls, data security, clinical governance, and qualified oversight.
- Must not reuse general drug discovery outputs as patient treatment recommendations.

## 8. Human Oversight Boundaries

Human review is required for:

- Interpreting disease, mechanism, and target hypotheses.
- Selecting datasets for training or validation.
- Approving model activation.
- Reviewing model limitations and external validation.
- Designing experiments.
- Interpreting experimental observations.
- Any clinical or regulatory interpretation.

## 9. Scientific Evidence Hierarchy

Evidence must be labelled as one of:

1. Established external fact.
2. Database-derived evidence.
3. Literature-derived evidence.
4. Computational inference.
5. Model prediction.
6. Simulation.
7. Experimental observation.
8. Clinically validated evidence.

Higher categories cannot be inferred from lower categories without the corresponding real evidence.

## 10. Model Governance Principles

- Active models and candidate models are separate.
- Every model output must include model identity, version, dataset lineage, method, validation status, confidence/uncertainty when available, and applicability-domain status when available.
- Missing model evidence must be shown as missing, not replaced with fake values.
- Training metrics are not external validation.
- External validation must use labelled validation data and must warn about overlap.
- Rollback and model retirement must be possible.

## 11. Laboratory Integration Philosophy

Laboratory Intelligence begins as integration software: planning, result import, observation provenance, and comparison against computational expectations.

It is not proprietary hardware, not a laboratory automation controller, and not proof that experiments were performed. Results become experimental observations only when imported or connected from real sources.

## 12. Controlled Learning Philosophy

Learning is controlled:

```text
Evidence/result
-> quality control
-> curation
-> versioned dataset
-> candidate model training
-> validation
-> benchmark against active model
-> scientific activation gate
-> approved active model
```

User interaction must not automatically retrain or activate production models.

Experimental observations do not automatically become training data. Required path: `ExperimentalObservation -> provenance verification -> QC -> scientific review/curation -> CuratedEvidenceRecord -> versioned dataset -> training eligibility`. Training eligibility is an explicit state: `training_eligible` or `not_training_eligible`.

Model activation does not use one universal threshold. Each model family requires a family-specific activation policy considering dataset provenance/version, data quality, duplicate/leakage checks, train/validation/test separation, held-out performance, external validation where appropriate, calibration, applicability domain, uncertainty behavior, benchmark versus active model/baseline, reproducibility, and failure/rollback criteria.

## 13. Current Platform Mapping

Current implementation maps as follows:

- Diagnosis & Mechanism Intelligence: Open Targets disease/target lookup and target ranking.
- Drug Discovery 360: PubChem/ChEMBL lookup, RDKit descriptors, rules, similarity, ADMET/toxicity triage, local ADMET prediction, lead prioritization.
- Precision Medicine: not implemented.
- Laboratory Intelligence: validation planner and experimental result import/comparison.
- Evidence & Learning Core: evidence quality, ADMET dataset curation, model training, external validation/calibration, model registry, model evidence resolver, cache.
- Shared Platform Infrastructure: FastAPI app, SQLite schema, React SPA, reports, research export, projects, readiness, scripts, Docker, CI.

## 14. V1/V2/V3 Evolution

### V1: Research Drug Discovery Platform

Focus: harden Drug Discovery 360 and Evidence & Learning Core around existing capabilities. No clinical claims.

### V2: Precision Research Platform

Adds patient-specific research context, molecular profiles, cohort-aware interpretation, and privacy/governance controls. Still not clinical prescribing.

### V3: Closed-Loop Biomedical Discovery Platform

Adds controlled laboratory integration, curated evidence learning, validated model lifecycle, and closed-loop research operations under audit.

## 15. Architecture Invariants

Future PRs must preserve:

- Evidence-type separation.
- Research-use-only default language.
- No clinical/regulatory claims without explicit validated pathway.
- No uncontrolled online self-learning.
- No fake predictions, labels, simulations, or experimental observations.
- Current validated assets are preserved before refactoring.
- Model outputs require provenance and versioning.
- Missing evidence remains visible.
- Precision Medicine remains separated from general drug discovery.
- Laboratory Intelligence does not imply experiments happened.
- Frontend decomposition must not change scientific behavior.
- Drug repurposing is owned by Drug Discovery 360; Precision Medicine may only consume and re-rank candidates.
- Diagnosis hypothesis generation must remain separate from confirmed diagnosis workflows.
- SQLite V1 implementation must not block later repository/service migration to a production database.
- Long-running computations must use the conceptual job lifecycle when implemented.
- Model activation gates must be family-specific, not one universal metric threshold.
- Raw data, curated data, fixtures, and scripts must be organized by provenance and purpose before being productized.

## Architecture Decision Register

### ADR-001 Modular five-system platform
DRUGDESIGN 360 is organized into Diagnosis & Mechanism Intelligence, Drug Discovery 360, Precision Medicine, Laboratory Intelligence, and Shared Evidence & Learning Core, plus shared infrastructure.

### ADR-002 Shared Evidence & Learning Core
Evidence provenance, datasets, validation, model governance, and controlled learning are shared platform concerns, not per-feature afterthoughts.

### ADR-003 No uncontrolled online self-learning
User interaction, feedback, or imported data cannot automatically retrain or activate production models.

### ADR-004 Evidence-type separation is mandatory
Predictions, simulations, database facts, experimental observations, and clinical evidence must remain distinct.

### ADR-005 Drug Discovery 360 remains the first scientific core
M2 extends the existing compound screening, ADMET, validation, reporting, and Disease-to-Lead core instead of rebuilding it.

### ADR-006 Precision Medicine is separated from general drug discovery
Patient-specific assessment requires separate data governance, privacy, validation, and interpretation boundaries.

### ADR-007 Laboratory Intelligence begins as integration software, not proprietary hardware
The platform starts with planning, ingestion, provenance, and interpretation support.

### ADR-008 Existing validated assets are preserved before refactoring
Working services, tests, calibration logic, cache, and report generation are kept stable while architecture evolves.

### ADR-009 Clinical claims are prohibited without appropriate validation/regulatory pathway
The platform cannot describe outputs as diagnosis, prescription, clinical validation, treatment efficacy, safety proof, approval, or readiness.

### ADR-010 Monolithic frontend must eventually be decomposed without changing scientific behavior
The current `frontend/src/App.jsx` monolith is technical debt. Decomposition is allowed only behind behavior-preserving tests.

### ADR-011 Diagnosis supports two entry modes
Problem/symptom-first workflows generate hypotheses and evidence gaps. Confirmed disease-first workflows start from an accepted disease context. These modes must not be merged into a false diagnosis claim.

### ADR-012 Drug repurposing belongs to Drug Discovery 360
Repurposing is a Drug Discovery 360 responsibility. Precision Medicine consumes and re-ranks repurposing candidates when patient-specific research evidence exists.

### ADR-013 SQLite is V1-local, repositories must remain migration-ready
SQLite is acceptable for local single-user V1. Service boundaries must not assume SQLite forever.

### ADR-014 Long tasks require a future job lifecycle
Training, validation, docking, MD, batch screening, generation, and large reports must eventually use queued jobs with progress, provenance, input snapshots, outputs, logs, and reproducibility metadata.

### ADR-015 Model activation policies are family-specific
Diagnosis/mechanism, target prioritization, activity, selectivity, ADMET/toxicity, molecular generation/scoring, precision medicine, and laboratory outcome models each require separate activation policies.

### ADR-016 Data and scripts require purpose-based organization
Future structure is `data/raw`, `data/curated`, `data/fixtures`, and `scripts/dev`, `scripts/validation`, `scripts/migration`, `scripts/maintenance`. M1 does not move current files.
