# Data and Evidence Architecture

DRUGDESIGN 360 uses one shared evidence model across all scientific modules. Every important result must carry provenance and evidence type.

## Evidence Types

Every scientific result must be labelled as exactly one primary evidence type:

- established external fact
- database-derived evidence
- literature-derived evidence
- computational inference
- model prediction
- simulation
- experimental observation
- clinically validated evidence

Secondary tags may be added, but the primary type must remain visible.

## Required Provenance Concepts

Each evidence record should be able to describe:

- entity
- result
- source
- source identifier
- source type
- evidence type
- evidence level
- method
- model
- model version
- dataset
- dataset version
- confidence
- uncertainty
- applicability domain
- validation status
- experimental status
- timestamp
- provenance chain
- reproducibility metadata

## Shared Evidence Record Concept

Conceptual fields:

```text
EvidenceRecord
  entity
  result
  evidence_type
  evidence_level
  source
  source_identifier
  method
  model_id
  model_version
  dataset_id
  dataset_version
  confidence
  uncertainty
  applicability_domain_status
  validation_status
  experimental_status
  timestamp
  provenance_chain
  reproducibility_metadata
```

No code schema is implemented in M1.

## Evidence Separation Rules

- Predicted values must not be presented as observed facts.
- Simulated results must not be called experimental observations.
- Database evidence must not be treated as clinical proof.
- Model outputs must not be stored or shown without model/version/dataset provenance.
- Training metrics must not be presented as external validation.
- User-entered experimental results must remain distinguishable from computational prediction feedback.
- Source, model, dataset, and method version history must not be overwritten or lost.

## Evidence Lifecycle

Evidence moves through:

```text
raw -> reviewed -> curated -> validated -> training_eligible / not_training_eligible
```

### Raw

Unreviewed imported data, external API result, or user-provided observation.

### Reviewed

Human or automated QC has checked basic validity, formatting, source identity, and evidence type.

### Curated

Entity normalization, units, labels, provenance, and duplicates have been resolved enough for reporting.

### Validated

Evidence has passed scientific/technical checks for its intended use. For models, this includes validation records and calibration status where relevant.

### Training Eligible

Curated and validated records approved for dataset versioning and model training. Training eligibility is not automatic.

### Not Training Eligible

Records may remain useful for reports or review while being excluded from model training because provenance, consent, QC, label quality, leakage risk, or scientific review is insufficient.

Experimental results follow:

```text
ExperimentalObservation
-> provenance verification
-> QC
-> scientific review/curation
-> CuratedEvidenceRecord
-> versioned dataset
-> training_eligible / not_training_eligible
```

Experimental observations must not automatically become model training data.

## Confidence and Uncertainty

Confidence must reflect evidence quality, not user desire. Uncertainty must remain visible when:

- model domain is unknown or outside domain.
- validation data is missing or overlapping.
- external source evidence is weak.
- experimental status is missing.
- labels are sparse, ambiguous, or imbalanced.

## Current Mapping

Current implemented evidence categories:

- PubChem properties: established external fact/database-derived evidence.
- Open Targets and ChEMBL values: database-derived evidence.
- RDKit descriptors, rules, similarity, prioritization: computational inference.
- Local ADMET models: model prediction.
- External validation/calibration metrics: computational inference over labelled validation data.
- User-imported lab CSV results: experimental observation if real user-entered observations.
- Clinical evidence: none.
- Simulation: none.

## Report Requirements

Reports must show:

- evidence type.
- source or method.
- model and dataset version when applicable.
- missing evidence.
- limitations.
- research-use-only notice.

Reports must not silently upgrade evidence level.

## Data and Script Organization

Future structure:

```text
data/
  raw/
  curated/
  fixtures/

scripts/
  dev/
  validation/
  migration/
  maintenance/
```

Rules:

- raw source data is immutable where possible.
- curated datasets are versioned.
- fixtures are small and test-focused.
- temporary debug scripts do not belong in product modules.
- scientific validation scripts must be reproducible and preserved.
- dataset provenance must never depend only on filename.

M1 does not move the current untracked data or helper scripts.
