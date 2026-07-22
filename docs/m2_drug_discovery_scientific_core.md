# M2 Drug Discovery 360 Scientific Core Hardening

Status: implementation branch for the M2 hardening layer.

DrugScreen360 remains a research-use computational decision-support platform. M2 hardens evidence boundaries and model governance around the existing Drug Discovery 360 core. It does not add clinical validation, autonomous diagnosis, treatment recommendation, regulatory readiness, wet-lab proof, docking, molecular dynamics, or de novo molecule generation.

## What Was Implemented

M2 adds a lightweight scientific-core contract layer around existing services:

- Endpoint-aware ADMET model status.
- Activity model architecture status.
- Selectivity model architecture status.
- Split and leakage integrity checks.
- A reusable RDKit Morgan-fingerprint applicability-domain baseline.
- A unified uncertainty/confidence contract.
- Family-specific activation gate evaluation.
- Evidence-aware candidate ranking explanations.
- Repurposing candidate source classification.
- Explicit not-implemented provider contracts for docking, MD, molecular generation, and lead optimization.
- Candidate-level evidence provenance in final report JSON/PDF/DOCX outputs.

The implementation reuses existing v0.20 assets:

- RDKit descriptor and fingerprint infrastructure.
- Local ADMET trained-model discovery and active model status.
- External validation/calibration summaries.
- Final report JSON/PDF/DOCX generation.
- Existing Disease-to-Lead and ADMET Model Studio workflows.

## APIs Added

All endpoints are research-use-only status or safety contracts:

- `GET /api/m2/scientific-core/status`
- `GET /api/m2/admet/endpoints`
- `GET /api/m2/activity/status`
- `GET /api/m2/selectivity/status`
- `GET /api/m2/future-providers/status`
- `GET /api/m2/jobs/lifecycle`
- `POST /api/m2/applicability-domain/assess`
- `POST /api/m2/split-integrity/check`
- `POST /api/m2/activation-gate/evaluate`
- `POST /api/m2/uncertainty/contract`
- `POST /api/m2/ranking/explain`
- `POST /api/m2/repurposing/classify`

## Multi-Endpoint ADMET

The endpoint catalog covers:

- Absorption: intestinal absorption, Caco-2/permeability.
- Distribution: plasma protein binding, BBB penetration.
- Metabolism: CYP inhibition/substrate risk.
- Excretion: clearance.
- Toxicity: hepatotoxicity, hERG/cardiotoxicity, general toxicity concern.

The system reports each endpoint as:

- `active` when a valid active trained model supports the endpoint.
- `candidate_available` when trained artifacts exist but are not active.
- `unavailable` when no real trained model is present.

Unavailable endpoints remain unavailable. Rule-based heuristics are not silently substituted as trained predictions.

## Activity Model Architecture

M2 defines the contract for future target-specific activity models:

- Target identity.
- Assay type and provenance.
- Activity label or value column.
- Units and transformation metadata.
- Train/validation/test split policy.
- Duplicate and leakage checks.
- Applicability domain.
- Uncertainty.
- Family-specific activation gate.

No universal activity model is trained in M2.

## Selectivity Model Architecture

M2 defines a future selectivity contract:

- On-target evidence.
- Off-target panel evidence.
- On-target versus off-target margin.
- Target-panel provenance.
- Explicit unavailable state when no real selectivity model exists.

No selectivity predictions are generated in M2.

## Split And Leakage Safety

The split-integrity check accepts records with:

- `smiles` or `canonical_smiles`
- `partition`: `train`, `validation`, or `test`
- optional `label`

It reports:

- accepted and rejected rows
- duplicate canonical SMILES
- overlap across train/validation/test
- scaffold overlap where RDKit can compute Bemis-Murcko scaffolds
- dataset version hash
- split hash

Scaffold-aware grouping is supported as a safety diagnostic. It is not forced for every model family because the correct split policy is task-specific.

## Applicability Domain Method

M2 adds a reusable baseline:

- Morgan fingerprints
- radius 2
- 2048 bits
- nearest-neighbor Tanimoto similarity
- configurable threshold
- statuses: `in_domain`, `borderline`, `out_of_domain`, `not_available`

Out-of-domain outputs include warnings and should not be interpreted with the same confidence as in-domain outputs.

## Uncertainty And Confidence

M2 defines a unified prediction contract:

- prediction label/value
- confidence
- uncertainty
- applicability-domain status
- model ID/version
- dataset version
- validation status
- calibration status
- method and warnings

The contract uses model probability only when it is actually present. It does not create fake precision or arbitrary confidence percentages.

## External Validation Hardening

The existing v0.18/v0.19 external validation service already computes:

- accuracy
- balanced accuracy
- precision
- recall/sensitivity
- specificity
- F1
- ROC-AUC when valid
- average precision when valid
- confusion matrix
- Brier score
- expected calibration error
- calibration bins
- overlap warnings

M2 preserves that service and exposes model/report contracts that keep validation status distinct from training metrics.

## Activation Policies

M2 adds family-specific activation gate evaluation. Activation states include:

- `DRAFT`
- `TRAINED`
- `VALIDATION_FAILED`
- `VALIDATION_PASSED`
- `ACTIVATION_ELIGIBLE`
- `ACTIVE`
- `RETIRED`

There is no universal threshold. Each model family requires a policy that can consider:

- dataset provenance and version
- split integrity
- leakage checks
- minimum sample size
- required metrics
- external validation where appropriate
- calibration where appropriate
- applicability domain
- reproducibility
- benchmark/rollback readiness

Training a model does not automatically mean it is activation eligible.

## Background Job Architecture

M2 freezes the local V1 job contract for long-running scientific operations:

```text
QUEUED -> RUNNING -> SUCCEEDED / FAILED / CANCELLED
```

Required job metadata:

- job ID
- job type
- created/start/end timestamps
- progress
- status
- input snapshot/reference
- output references
- logs/errors
- model and dataset provenance
- reproducibility metadata

Current training and validation endpoints remain synchronous to preserve v0.20 local workflows. Future M2 work can move them behind this contract without changing scientific behavior. A local lightweight queue is appropriate first; Redis/Celery/RQ-style distributed execution is deferred until multi-user or large-job operation requires it.

## Candidate Ranking Logic

M2 exposes a ranking-explanation contract that can account for:

- activity
- selectivity
- ADMET
- toxicity
- drug-likeness
- structural alerts
- applicability domain
- uncertainty/confidence
- evidence quality
- novelty/similarity
- synthetic feasibility

Unavailable dimensions are shown as unavailable and reduce confidence. They are not filled with fabricated scores.

## Repurposing Handling

Repurposing candidates are classified as:

- approved drug
- investigational compound
- database hit
- predicted candidate
- generated molecule

This classification helps avoid treating all candidates as equivalent. It does not imply clinical suitability or treatment value.

## Docking, MD, And Generative Interfaces

M2 adds architecture contracts only:

- `DockingProvider`
- `MDProvider`
- `MoleculeGenerator`
- `LeadOptimizer`

All are explicitly `not_implemented` unless a real governed provider is connected later. DrugScreen360 does not return docking scores, MD trajectories, or generated validated molecules in M2.

## Report Evidence Package

Final reports now include candidate-level provenance fields:

- evidence type
- source
- model name
- model version
- dataset version
- prediction
- confidence
- uncertainty
- applicability domain
- validation status
- limitations

Report evidence types remain separate:

- `FACT`
- `DATABASE EVIDENCE`
- `MODEL PREDICTION`
- `RULE-BASED HEURISTIC`
- `SIMULATION`
- `EXPERIMENTAL OBSERVATION`

## Real Datasets Used

No new real datasets are added in M2. Existing local user datasets and untracked training assets are preserved but not moved or committed by this branch.

Synthetic fixtures may be used only in tests and are not scientific evidence.

## Unsupported Capabilities

M2 does not implement:

- real docking
- molecular dynamics
- molecular generation
- target-specific activity model training
- selectivity model training
- clinical decision support
- autonomous diagnosis
- regulatory validation
- automatic production retraining

## Next Recommended Milestone

Recommended next M2 scope:

1. Persist explicit split assignments during ADMET training.
2. Add dataset/version hashes to model cards and manifests.
3. Convert synchronous training and external validation to the frozen job lifecycle.
4. Add endpoint-specific ADMET model training screens beyond `toxicity_concern`.
5. Add target-specific activity dataset ingestion and validation contracts.
6. Add benchmark comparisons against active models before activation.
