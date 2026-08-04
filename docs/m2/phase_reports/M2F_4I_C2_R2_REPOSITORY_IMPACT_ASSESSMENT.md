# M2F-4I-C2-R2 Repository Impact Assessment

## Objective

Determine whether substantive repository differences present during M2F-4I-C2 affected the scientific qualification of the EPA/FDA AIME-VM7Luc external evidence source.

## Repository identities

- Frozen scientific base: `214a45c640eb9f57d657d832ad020ac9da75e9ef`
- Repository observed during C2: `19a3c843b0634eb9344d63f0077bdff7725c8c0d`
- Current merged main: `33df56e52d5c12db7aeda3c7a4aef7cc72801789`

The earlier reconciliation failed because the observed commit was not documentation-only. It contained scientific and operational scripts, training-data artifacts, model-registration artifacts, and generated diagnostics.

## Actual-use and dependency assessment

The sealed C2 workflow used its archived scientific script, the governed source workbook and README, permitted TRAIN and VALIDATION identity inventories, Python, pandas, NumPy, and RDKit. It did not import repository modules or load repository training datasets, model registrations, candidate binaries, activation records, or configuration files. Repository access was limited to read-only branch, commit, and tracked-diff metadata.

The candidate binary was not accessed, loaded, or executed. No training, prediction, probability generation, threshold application, calibration, or metric calculation occurred. The consumed TEST and the prior governed TEST-evaluation scientific contents remained protected.

## Isolated reproduction

Two isolated deterministic reproductions used the sealed inputs, policies, permitted development identities, label mapping, cytotoxicity rules, standardization semantics, and frozen overlap/analogue thresholds.

Both reproductions matched the sealed result record-for-record:

- Raw endpoint records: 769
- Resolved structures: 645
- Eligible before overlap: 541
- Exact overlaps: 459
- Parent overlaps: 480
- Additional very-close analogue exclusions: 11
- Final total: 109
- Positives: 20
- Negatives: 89
- Identity-and-label projection SHA-256: `063382700691CFB28293BC95AE283BE71FC4EF42CB9642E3D2778FFEA46B5462`

No record-level differences were found.

## Adjudication

`C2_SCIENTIFIC_VALIDITY_CONFIRMED_WITH_NONIMPACTING_REPOSITORY_DEVIATION`

The repository divergence was substantive, but the changed artifacts were unused by C2 and the scientific output was independently reproduced. The sealed C2 result remains valid: the EPA/FDA source is a qualified diagnostic source with 109 compounds and remains below the 150-compound external-dataset gate.

The R2 validator passed 220/220 checks. The governed R2 manifest SHA-256 is `6AA24D39DDB750EE32EBED8B7F0630C8FC49A2589BD4FEBB4C75F4690BBAA3CC` and external post-seal verification passed.

## Governance status

- Candidate: `INACTIVE_CANDIDATE`
- Candidate executed: no
- Consumed TEST reused: no
- External dataset lock: none
- M2F-4J permission: no
