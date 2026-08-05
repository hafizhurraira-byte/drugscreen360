# M2F-4J external evaluation protocol freeze

## Outcome

`M2F4J_EXTERNAL_EVALUATION_PROTOCOL_FROZEN`

The one-time external evaluation protocol is frozen. The candidate remains inactive, M2F-4K remains unauthorized, and no candidate loading, prediction, metric calculation, consumed TEST access, or dataset modification occurred.

## Frozen identities

- Candidate: `ERA_V2_REDEV_CANDIDATE_RF_BD08B61A`
- Candidate SHA-256: `BD08B61AD6B57A0CB6F2A55C4B476CF07578A73A94DABBC95A9D6D7CBA4ED77B`
- Candidate state: `INACTIVE_CANDIDATE`
- Dataset: ERA Independent External Validation Dataset v1.0.0
- Dataset content SHA-256: `7F3351D05138E89B1F9C6BA6633200F98AC2DEC42BF3396F249ECEE3E201B625`
- Dataset CSV SHA-256: `6A3CB2EEF13E7BBFCB0963096925BC3FAE0F0D72E322945810C56E2D62B8D903`
- Dataset JSONL SHA-256: `1977340A3ED4B517BC99DA12E8B3DA8D5382423CA9CA3FBCEE1EB355B9F12C21`
- Expected records: 199 (35 positive, 164 negative; AIME 109, EPA 90)

## Feature and prediction contracts

The candidate uses a 4,096-bit Morgan fingerprint with radius 2 and chirality enabled. Frozen canonical SMILES are used without evaluation-time re-standardization. Feature order is bit index 0–4095, and invalid structures abort before prediction. A deterministic public-structure fixture passed repeated feature-hash, dimensionality, and invalid-input checks.

The positive-class Random Forest output is oriented so higher scores mean ERα agonist positive. The frozen threshold is `0.6525760971`, selected from TRAIN-only repeated group-aware out-of-fold predictions using the maximum-MCC policy. External or source-specific threshold optimization and post-hoc prediction transformations are prohibited.

## Metrics and intervals

The frozen protocol reports ROC-AUC, PR-AUC, balanced accuracy, MCC, sensitivity, specificity, precision, NPV, F1, accuracy, Brier score, and TP/TN/FP/FN. Candidate scores are probability-like but uncalibrated; calibration assessment is descriptive only, and Platt or isotonic refitting is prohibited.

Two-sided 95% intervals use Wilson intervals for proportions and 2,000 fixed-seed (`20260802`) stratified percentile bootstrap replicates for ROC-AUC, PR-AUC, and other metrics. At least 1,900 valid replicates are required.

## Stratification, domain, and uncertainty

Results are reported overall, by AIME/EPA source, by AIME/EPA-ATG/EPA-OT program, and by endpoint-evidence stratum. EPA endpoint strata overlap and must not be summed as mutually exclusive. Source-specific thresholds are prohibited.

Applicability domain reuses maximum TRAIN Morgan-2048 Tanimoto similarity:

- `IN_DOMAIN`: similarity ≥0.34
- `BORDERLINE`: similarity ≥0.2278561827956989 and <0.34
- `OUT_OF_DOMAIN`: similarity <0.2278561827956989

No external-data AD refitting or primary exclusion of out-of-domain records is permitted. Uncertainty is the standard deviation of positive-class probability across the 300 frozen trees. It is descriptive and cannot alter predictions.

## Gates and one-time control

Integrity gates require exact candidate, dataset, schema, feature, threshold, and protocol hashes; all 199 records; a read-only dataset; no protected TEST access; and intact single-use execution control.

Scientific conditions reproduce prior candidate governance:

- Supportive requires PR-AUC ≥0.45, ROC-AUC ≥0.78, MCC ≥0.40, balanced accuracy ≥0.67, sensitivity ≥0.35, and specificity ≥0.90.
- Mixed requires PR-AUC above external prevalence, ROC-AUC ≥0.72, MCC ≥0.25, balanced accuracy ≥0.62, sensitivity ≥0.25, specificity ≥0.85, at least one positive prediction, and finite scores.
- Failure to meet all minimum conditions is unsupportive.

Source-direction inconsistency forces mixed interpretation even when overall supportive gates pass. Candidate activation remains a separate governance decision.

M2F-4K requires a separate explicit authorization record and atomic single-use lock. Any prediction consumes the authorization. A partial run must stop and seal its evidence; deletion and automatic rerun are prohibited.

## Protocol lock

- Protocol status: `FROZEN_EXTERNAL_EVALUATION_PROTOCOL`
- Protocol SHA-256: `B63E6E0E4B4E8F1CD21B03D395C56592F6DB9266990DAD84617A8B058E3565B1`
- Feature-contract hash: `6277703353F4271E6D1C3DFB5C017AC88422413AD092EB52B22F6D28E2BFB1A4`
- Execution-control hash: `B35671C3684741D1C915719B7A57F494B8B0F38B6302E8F661E70D1052DBEFC6`
- Decision-gate hash: `B1F91E6FD5F948C308CAEEA8022E6DFFB2B5814118D1C3A5CFE7A9B294727F61`
- File-manifest SHA-256: `687AE7CFD1EE8DB74DD0301588969F88673D8AE603E25425D38CE6926A576F06`
- Validator: 176/176 checks passed with no warnings.
- Post-seal verification: pass with zero missing, unexpected, size-mismatched, or hash-mismatched files.
- Current authorization: `M2F4K_NOT_AUTHORIZED`
- Next administrative action: `EXPLICIT_M2F4K_AUTHORIZATION_ONLY`
