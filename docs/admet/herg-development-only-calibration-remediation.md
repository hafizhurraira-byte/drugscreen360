# hERG development-only calibration remediation

## Governed outcome

The authorized development-only calibration phase stopped with `BLOCKED_EXTERNAL_DATA_CONTAMINATION`. No calibrator was fitted, no candidate was created, and no model was activated or deployed.

## Original candidate

- Candidate: `herg_v1`
- Model SHA-256: `0e0d07a5347c6027c12e2b86946588eb3c66330a80df499fda7a92d3c6721081`
- Model: 300-tree class-balanced random forest
- Features: RDKit Morgan radius 2, 2,048 bits plus eight descriptors
- Dataset SHA-256: `d158349057ba221b11504c9f03ec5bcab9f07577be0f24316e8c5cab8ef3cd04`
- Split SHA-256: `803405066130897ebcb0dff653c747e3b7851492da93d5721a6b4daac46cc9c0`
- Frozen threshold: `0.5`
- Calibration: raw predicted probabilities

All governed `herg_v1` artifacts were hashed before and after the phase and remained unchanged. It remains the current registered hERG candidate.

## Why remediation stopped

The existing recalibration directory was not a development-only partition. Its frozen M2D-3 protocol identifies the source as the already-observed PubChem AID 588834 external-validation cohort. Its 4,171 records were divided into 2,085 fit, 1,043 validation, and 1,043 confirmation records.

The new controlling protocol required `PUBCHEM_EXTERNAL_RECORDS_IN_CALIBRATION = 0`. The verified value was 4,171, so those partitions are prohibited for calibrator fitting or selection. Their zero molecule/scaffold overlap and adequate class counts do not cure the source-governance violation.

No record-level PubChem errors or predictions were opened during this phase. Historical PubChem ECE was not used as an optimization target.

## Methods and scientific outputs

The prospectively bounded method set would have been `NONE`, Platt, and isotonic if valid development-only partitions existed. Because lineage verification failed first:

- no calibration-selection protocol was frozen from outcomes;
- no NONE baseline was recomputed;
- no Platt or isotonic calibrator was fitted;
- no beta calibrator was considered;
- no development predictions or candidate comparison were generated;
- the `0.5` threshold was unchanged;
- binary prediction changes were not evaluated;
- applicability-domain thresholds and references were unchanged;
- tree-level prediction-standard-deviation uncertainty was unchanged.

## Candidate and external-validation status

No calibrated candidate identity or artifact exists. The prior PubChem evaluation remains consumed historical evidence for the base model only and is prohibited from adaptive calibration use. A new untouched external set is not yet the immediate next step: valid frozen development-only calibration partitions must first be established, followed by a new prospective calibration protocol and development-only comparison.

Activation, production replacement, external re-evaluation, and deployment remain prohibited.

## Validation and seal

The blocked-state validator passed 162 of 162 checks. The governed workspace was sealed, and external post-seal verification reported zero missing files, unexpected files, size mismatches, or hash mismatches.

## Next phase

Recommended next action: `RESOLVE_CALIBRATION_PARTITIONS`.

That phase must identify eligible records originating only from the frozen hERG development data, preserve the existing scaffold split and protected TEST boundary, and prove zero PubChem/external membership before calibration fitting is authorized.
