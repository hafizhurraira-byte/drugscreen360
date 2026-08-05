# M2F-4L ERA v2 candidate lifecycle closure

## Final disposition

`RETAINED_RESEARCH_ONLY_INACTIVE_CANDIDATE`

The lifecycle of `ERA_V2_REDEV_CANDIDATE_RF_BD08B61A` is closed. The candidate remains inactive and is prohibited from activation, deployment, production integration, clinical or regulatory use, and characterization as externally validated.

Candidate SHA-256: `BD08B61AD6B57A0CB6F2A55C4B476CF07578A73A94DABBC95A9D6D7CBA4ED77B`.

## Frozen evaluation lineage

- Dataset: ERA Independent External Validation Dataset v1.0.0
- Dataset-content SHA-256: `7F3351D05138E89B1F9C6BA6633200F98AC2DEC42BF3396F249ECEE3E201B625`
- Protocol SHA-256: `B63E6E0E4B4E8F1CD21B03D395C56592F6DB9266990DAD84617A8B058E3565B1`
- Evaluation run: `M2F4K_ERA_EXT_20260806_V1`
- Evaluation manifest SHA-256: `B34899C1A47ADA665911AFF49DA9345C48B7CF9069924CDEBC0A6522F5F5C519`
- Evaluation integrity: pass
- Scientific disposition: `EXTERNAL_VALIDATION_UNSUPPORTIVE`
- Authorization consumed: yes
- Attempts/successes: 1/1
- Future rerun: prohibited

## Principal findings

The one-time independent evaluation retained high specificity but insufficient sensitivity:

| Metric | Value |
|---|---:|
| ROC-AUC | 0.7260 |
| PR-AUC | 0.4237 |
| Balanced accuracy | 0.5756 |
| MCC | 0.2181 |
| Sensitivity | 0.2000 |
| Specificity | 0.9512 |
| Precision | 0.4667 |
| NPV | 0.8478 |
| F1 | 0.2800 |
| Accuracy | 0.8191 |
| Brier score | 0.1555 |

The confusion matrix was TP 7, TN 156, FP 8, and FN 28. The evaluation passed integrity controls but failed the prospectively frozen performance gates. No alternative threshold was tested or implied as a remedy.

## Consumed dataset and research-only boundary

The 199-record dataset is now `CONSUMED_ONE_TIME_EXTERNAL_EVALUATION_DATASET`. It cannot be used for threshold, model, hyperparameter, feature, calibration, retraining, ranking, or another confirmatory evaluation of a derived candidate.

Permitted uses are limited to governed audit, reproducibility verification, publication reporting, non-adaptive descriptive failure analysis, and historical comparison with explicit consumed-dataset disclosure.

The candidate may be retained only for scientific audit, methodological comparison, failure analysis, research documentation, and governed retrospective benchmarking. Rerun, threshold adjustment, recalibration, activation, deployment, and production integration are prohibited.

## ERA v3 redevelopment boundary

The future cycle is named `ERA_V3_GOVERNED_REDEVELOPMENT`. Its charter does not authorize training or prescribe a final model design. It requires:

- a new candidate identity and SHA;
- a revised governed development dataset;
- no adaptive use of the consumed 199-record dataset;
- a new independent external source or prospectively frozen untouched holdout;
- predeclared features and development-only threshold selection;
- sensitivity-oriented objectives balanced against specificity;
- frozen class-imbalance handling;
- source-aware and scaffold-aware validation;
- governed applicability-domain, uncertainty, and calibration methods;
- a new one-time evaluation authorization;
- no inherited activation eligibility from ERA v2.

## Governance seal

- M2F-4L decision: `M2F4L_CANDIDATE_RETAINED_RESEARCH_ONLY_AND_LIFECYCLE_CLOSED`
- Validator: 129/129 checks passed with no warnings.
- Closure manifest SHA-256: `21F05361022B4B0BC44C206BB141CFED4B1BA04875BE1C762E92740A3916732B`
- Post-seal verification: pass with zero missing, unexpected, size-mismatched, or hash-mismatched files.

Any scientific claim must disclose the one-time, integrity-valid but externally unsupportive evaluation, the high-specificity/low-sensitivity behavior, candidate inactivity, frozen prospective controls, consumed dataset, and prohibition on rerun or post-hoc adjustment.
