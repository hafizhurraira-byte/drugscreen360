# AI Model and Learning Architecture

This document defines controlled model governance for DRUGDESIGN 360.

## Controlled Learning Loop

Required loop:

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

Prohibited loop:

```text
user interaction -> automatic production retraining
```

User activity, reports, feedback, and imported results may create evidence records. They must not automatically retrain or activate production models.

Experimental results must pass provenance verification, QC, scientific review/curation, versioned dataset release, and explicit `training_eligible` status before they can enter model training. Otherwise they remain `not_training_eligible`.

## Model Registry

The registry tracks:

- model ID.
- model name.
- model family.
- task.
- status.
- artifact location.
- dataset lineage.
- training lineage.
- validation records.
- calibration status.
- activation state.
- retirement or rollback state.

## Active vs Candidate Models

Candidate models:

- may be trained or imported.
- may have incomplete validation.
- cannot be used as production evidence unless activated.

Active models:

- passed validation gates.
- have pinned artifact paths.
- have versioned metadata.
- can be used in reports with limitations.

Broken/stale active models must be marked unavailable and must not be treated as usable evidence.

## Dataset Lineage

Every training or validation dataset must track:

- dataset ID.
- source.
- version.
- label mapping.
- curation status.
- duplicate handling.
- excluded rows.
- training eligibility.

## Training Lineage

Every training run must track:

- dataset version.
- features.
- algorithm.
- parameters.
- random seed.
- split method.
- metrics.
- artifact hash/path when available.
- model card.

## Family-Specific Activation Gates

There is no universal activation threshold. Each model family needs its own activation policy.

Every activation policy must consider at minimum:

- dataset provenance and version.
- data quality.
- duplicate/leakage checks.
- train/validation/test separation.
- held-out performance.
- external validation where scientifically appropriate.
- calibration.
- applicability domain.
- uncertainty behavior.
- benchmark versus active model or baseline.
- reproducibility.
- failure and rollback criteria.
- loadable artifact.
- compatible feature schema.
- task compatibility.
- scientific limitations.

## External Validation and Calibration

External validation must use labelled data not assumed to be independent. Overlap warnings must be shown when validation data appears to overlap training data.

Calibration outputs are dataset-dependent. Poor calibration must not be hidden.

## Applicability Domain and Uncertainty

Predictions should include applicability-domain and uncertainty status when available. Outside-domain or unknown-domain predictions must be downgraded in confidence.

## Explainability

Explainability outputs must state their method:

- feature importance.
- coefficients.
- descriptor comparison.
- local explanation if truly implemented.

Simplified diagnostics must not be called real SHAP values unless a real SHAP implementation is present.

## Rollback, Retirement, and Version Pinning

The system must support:

- deactivation.
- rollback to prior valid model.
- retirement of obsolete models.
- version pinning in reports.
- audit trail of activation changes.

## Model Families

Conceptual model families may include:

- diagnosis/mechanism reasoning.
- target prioritization.
- activity prediction.
- selectivity prediction.
- ADMET/toxicity.
- molecular generation.
- precision medicine.
- laboratory outcome prediction.

Not all models must be trained internally. Deterministic algorithms, external validated models, APIs, and locally trained models may coexist under the same governance model.

## Current Mapping

Current implemented model capability is local ADMET/toxicity baseline training and validation through ADMET Model Studio, plus rule-based predictors and external provider adapters. Docking, molecular generation, precision medicine models, and laboratory outcome prediction are not implemented.
