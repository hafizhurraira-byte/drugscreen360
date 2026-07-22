# System Module Boundaries

This document defines ownership boundaries for the long-term DRUGDESIGN 360 architecture. It is conceptual; no code schemas are implemented here.

## Canonical Handoff Objects

- `ProblemContext`
- `DiseaseHypothesis`
- `MechanismProfile`
- `TargetCandidate`
- `DrugDiscoveryProject`
- `CompoundCandidate`
- `EvidencePackage`
- `TreatmentCandidate`
- `PatientMolecularProfile`
- `PersonalizedAssessment`
- `ExperimentPlan`
- `ExperimentalObservation`
- `CuratedEvidenceRecord`
- `ModelCandidate`
- `ModelValidationRecord`

Future long-running work also uses a conceptual job record with job ID, progress, timestamps, logs/status, provenance, input snapshot, output references, and reproducibility metadata.

## A. Diagnosis & Mechanism Intelligence

Purpose: interpret disease/problem context, mechanism hypotheses, genes/pathways, and target candidates.

Accepted inputs:

- `ProblemContext`
- disease names
- symptoms or research questions
- target hints
- external disease/target databases

Outputs:

- `DiseaseHypothesis`
- `MechanismProfile`
- `TargetCandidate`
- evidence-labelled confirmatory-test recommendations

Owned responsibilities:

- Problem/symptoms/phenotype-first interpretation as hypothesis generation.
- Confirmed disease-first mechanism and target analysis.
- Disease/target interpretation.
- Mechanism and pathway summarization.
- Target prioritization based on disease association evidence.

Not owned:

- Compound ADMET scoring.
- Patient-specific treatment assessment.
- Laboratory result ingestion.
- Model activation.
- autonomous diagnosis.

Dependencies:

- Shared Evidence & Learning Core.
- External sources such as Open Targets.

Interfaces:

- Sends `TargetCandidate` and `EvidencePackage` to Drug Discovery 360.
- Sends disease/mechanism context to Precision Medicine when patient-specific mode exists.

Validation requirements:

- Source provenance.
- Evidence-level labelling.
- No autonomous diagnosis claims.
- Hypothesis generation clearly separated from confirmed diagnosis context.

Current repository mapping:

- `backend/app/services/open_targets_service.py`
- `backend/app/services/target_ranker.py`
- `backend/app/routers/disease_finder.py`
- `disease_searches`, `disease_target_results`

Future capabilities:

- Mechanism graphs.
- pathway enrichment.
- literature-derived mechanism evidence.
- confirmatory test recommendation as research support.

## B. Drug Discovery 360

Purpose: discover, screen, rank, and package compound candidates.

Accepted inputs:

- `DrugDiscoveryProject`
- `TargetCandidate`
- `CompoundCandidate`
- SMILES/name/CID/InChI
- curated model evidence

Outputs:

- ranked `CompoundCandidate` list
- candidate-level `EvidencePackage`
- lead prioritization summaries
- report-ready candidate package

Owned responsibilities:

- RDKit descriptors.
- rule-based drug-likeness and ADMET/toxicity triage.
- ChEMBL/PubChem molecule evidence.
- drug repurposing.
- similarity search.
- activity/selectivity/docking/MD/generation architecture when implemented.
- lead prioritization.

Not owned:

- Diagnosis.
- patient-specific assessment.
- wet-lab observation truth.
- model lifecycle governance.
- patient-specific re-ranking of repurposing candidates.

Dependencies:

- Diagnosis & Mechanism Intelligence.
- Shared Evidence & Learning Core.
- Shared Platform Infrastructure.

Interfaces:

- Receives `TargetCandidate`.
- Sends `CompoundCandidate` and `EvidencePackage`.
- Requests model predictions through Evidence & Learning Core.
- Sends optional `ExperimentPlan` requests to Laboratory Intelligence.
- Sends repurposing candidates to Precision Medicine for patient-specific research re-ranking when that module exists.

Validation requirements:

- descriptor reproducibility.
- source IDs for external compounds.
- model provenance.
- missing evidence warnings.

Current repository mapping:

- `descriptors.py`, `rules.py`, `admet_rules.py`, `admet_toxicity_engine.py`, `toxicity_rules.py`
- `similarity_service.py`, `chembl_service.py`, `pubchem_service.py`
- `admet_predictor_service.py`, `admet_trained_model_service.py`
- `admet_lead_service.py`, `candidate_ranker.py`
- screening, finder, similarity, lead prioritization tables

Future capabilities:

- real multi-endpoint ADMET.
- activity and selectivity models.
- docking architecture.
- MD architecture.
- molecular generation architecture.
- lead optimization architecture.

## C. Precision Medicine

Purpose: patient-specific research assessment when appropriate governance exists.

Accepted inputs:

- `PatientMolecularProfile`
- patient-specific variants or omics data
- disease context
- candidate treatments

Outputs:

- `PersonalizedAssessment`
- patient-context evidence warnings

Owned responsibilities:

- molecular profile interpretation.
- patient-specific research hypotheses.
- patient-specific re-ranking of Drug Discovery 360 repurposing candidates.
- cohort/context matching when validated.

Not owned:

- general drug discovery scoring.
- primary drug repurposing engine.
- clinical prescription.
- diagnosis.
- laboratory execution.

Dependencies:

- Diagnosis & Mechanism Intelligence.
- Drug Discovery 360.
- Shared Evidence & Learning Core.
- security/privacy infrastructure.

Interfaces:

- Receives `TreatmentCandidate` and `EvidencePackage`.
- Receives repurposing candidates from Drug Discovery 360.
- Returns `PersonalizedAssessment`.

Validation requirements:

- privacy and consent controls.
- clinical governance before any clinical use.
- no treatment recommendation claims.

Current repository mapping:

- None. This module is missing and deferred.

Future capabilities:

- patient molecular profile import.
- variant/pathway interpretation.
- personalized risk/context overlays.

## D. Laboratory Intelligence

Purpose: plan experiments and ingest real experimental observations.

Accepted inputs:

- `CompoundCandidate`
- `EvidencePackage`
- requested validation questions
- result CSVs or connected lab outputs

Outputs:

- `ExperimentPlan`
- `ExperimentalObservation`
- feedback comparison summaries

Owned responsibilities:

- experimental planning support.
- assay/control/readout guidance.
- experimental result ingestion.
- comparison against computational predictions.

Not owned:

- claiming experiments were performed without imported observations.
- clinical interpretation.
- model activation.
- compound ranking core.

Dependencies:

- Drug Discovery 360.
- Shared Evidence & Learning Core.

Interfaces:

- Receives candidates/evidence.
- Sends `ExperimentalObservation` to Evidence & Learning Core for provenance verification, QC, review, curation, and explicit training eligibility assessment.

Validation requirements:

- source, date, units, replicate count when available.
- result direction separated from model prediction.
- qualified lab review warning.

Current repository mapping:

- `validation_planner_service.py`
- `experimental_results_service.py`
- experimental validation/result/feedback tables

Future capabilities:

- lab information system connectors.
- protocol metadata.
- observation quality control.

## E. Shared Evidence & Learning Core

Purpose: common evidence, provenance, datasets, model governance, validation, and learning.

Accepted inputs:

- `CuratedEvidenceRecord`
- datasets
- model artifacts
- validation records
- external/database/literature evidence

Outputs:

- `EvidencePackage`
- `ModelCandidate`
- `ModelValidationRecord`
- active model status

Owned responsibilities:

- evidence-type separation.
- provenance chain.
- evidence quality grading.
- dataset curation.
- explicit `training_eligible` / `not_training_eligible` state for curated evidence records.
- model registry.
- model training lineage.
- validation/calibration.
- applicability domain.
- uncertainty.
- explainability governance.
- controlled activation.

Not owned:

- disease interpretation.
- compound workflow orchestration.
- patient treatment decisions.
- wet-lab execution.

Dependencies:

- all scientific modules.
- shared storage.

Interfaces:

- Provides evidence and model services to every module.
- Receives curated observations and datasets.

Validation requirements:

- versioned datasets and models.
- no uncontrolled self-learning.
- external validation separate from training metrics.
- experimental observations cannot become training data without provenance verification, QC, scientific review/curation, and versioned dataset release.

Current repository mapping:

- `evidence_quality.py`
- `admet_dataset_service.py`
- `admet_training_service.py`
- `admet_validation_service.py`
- `model_registry.py`
- `admet_model_evidence_resolver.py`
- `cache_service.py`
- `bindingdb_service.py` prototype
- ADMET dataset/model/validation/cache tables

Future capabilities:

- unified evidence graph.
- literature evidence ingestion.
- model benchmark registry.
- dataset release management.

## F. Shared Platform Infrastructure

Purpose: common application runtime, persistence, UI shell, reports, exports, and operations.

Accepted inputs:

- project metadata.
- report requests.
- system configuration.
- module outputs.

Outputs:

- reports.
- research exports.
- project dashboards.
- readiness/status responses.

Owned responsibilities:

- FastAPI app shell.
- database schema and migrations.
- React app shell.
- project workspaces.
- report/export generation.
- scripts, Docker, CI.
- health/readiness.
- future job lifecycle for long-running tasks.

Not owned:

- scientific scoring logic.
- clinical governance.
- model validation science.

Dependencies:

- all modules.

Interfaces:

- Hosts module APIs.
- packages `EvidencePackage` and workflow outputs into reports.

Validation requirements:

- generated artifacts are traceable.
- no private/generated artifacts committed.
- readiness must not upgrade missing evidence.

Current repository mapping:

- `main.py`, `database.py`
- `final_report_service.py`, `reports.py`, `project_workspace_reports.py`, `research_export_service.py`
- `project_workspace_service.py`, `history.py`, `version.py`
- React/Vite frontend, scripts, Docker, CI

Future capabilities:

- modular frontend.
- background jobs.
- multi-user security if required.
- operational audit logs.

Frontend architecture remains one unified application with module workspaces: Diagnosis & Mechanism, Drug Discovery, Precision Medicine, Laboratory Intelligence, and Evidence / Models / Administration. It is not five separate applications.

Database strategy: SQLite is acceptable for local single-user V1. Repository and service boundaries must remain migration-ready for PostgreSQL or another production database.
