# hERG development-only calibration execution

## Governed outcome

Authorization `HERG_DEVELOPMENT_ONLY_CALIBRATION_EXECUTION` produced **`HERG_PLATT_CALIBRATED_CANDIDATE_FROZEN`**. The sealed 515-record TRAIN-only OOF package was the only adaptive scientific evidence. VALIDATION and TEST scientific access and PubChem adaptive access were all zero.

The selected candidate is `HERG_V1_CAL_PLATT_B7BDD44F7E47`, canonical SHA-256 `b7bdd44f7e471199553f4a8a82e63aa2f4862091a565a9a6ade273de152788f1`, with state `INACTIVE_CALIBRATED_CANDIDATE`. The original `herg_v1` remains unchanged and registered; no activation, production switch, external evaluation, or deployment occurred.

## Source and protocol

The OOF manifest SHA-256 was `60cc014422cacf44030fba5ca8b0c2b23d5c8b081cb1e00b3ef21d0ce8954c5e`. It contained 515 complete, unique TRAIN predictions: 364 positive, 151 negative, and 361 scaffold groups. The partition-resolution manifest, base model, dataset, split, OOF feature matrix, upstream post-seal results, PubChem nonreuse lock, and TEST nonreuse contract all verified before fitting.

The calibration protocol was frozen before record-level loading under SHA-256 `e04609a4e57adf636645f008ad5d8a5ff4208c35fd51da67d6ea7d72afec213d`. NONE, logistic Platt scaling, and isotonic regression were compared using a new five-fold `StratifiedGroupKFold` assignment (shuffle enabled, seed 2718). Every calibrated evaluation probability came from a calibrator fitted without that record or its scaffold group. Coverage was 515/515 with zero leakage, missing values, or duplicates.

## Development-only results

| Method | ECE | Brier | Log loss | Intercept | Slope | ROC-AUC | PR-AUC | Stability |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| NONE | 0.105337 | 0.140362 | 0.445869 | 0.210721 | 1.582267 | 0.868314 | 0.940118 | baseline |
| Platt | 0.061004 | 0.132715 | 0.419344 | 0.025062 | 0.971400 | 0.863638 | 0.936181 | STABLE |
| Isotonic | 0.058273 | 0.132385 | 0.835432 | 0.400951 | 0.366948 | 0.851585 | 0.923481 | UNSTABLE |

Platt passed every prospectively frozen practical-benefit and discrimination-preservation rule. Isotonic was rejected despite lower ECE and Brier because log loss deteriorated severely, discrimination constraints failed, and fold stability was unacceptable.

The paired 2,000-repetition scaffold-group bootstrap (seed 314159) estimated Platt-minus-NONE mean changes of −0.007586 for Brier (95% percentile CI −0.015181 to 0.000131), −0.026405 for log loss (−0.049520 to −0.002126), and −0.040011 for ECE (−0.077826 to 0.006064). Favorable fractions were 97.35%, 98.55%, and 95.70%, respectively. Isotonic's mean log-loss change was +0.388047 (95% CI +0.070237 to +0.802754).

## Candidate contracts

After selection, exactly one final Platt calibrator was fitted on all 515 sealed OOF pairs. Its artifact SHA-256 is `afb85e4a03ddd1b1e47285829dcc788858493eb68d6855721b2016c9fb0ac3e4`. No model weights or molecular features were used or changed.

The base operational threshold remains **0.5 in raw-probability space**. Threshold-dependent calibrated metrics are development diagnostics only; candidate metadata records `OPERATIONAL_THRESHOLD_NOT_AUTHORIZED_FOR_CALIBRATED_SPACE`. The frozen TRAIN Morgan/Tanimoto applicability domain is unchanged. Tree-level standard deviation is preserved explicitly as `raw_model_uncertainty`, describing base-model disagreement rather than uncertainty in the calibration transform.

The consumed PubChem cohort remains `HISTORICAL_EXTERNAL_DISCRIMINATION_EVIDENCE` and is `PROHIBITED_FOR_CALIBRATED_CANDIDATE_SELECTION`. It does not validate calibrated probabilities. A new untouched external source with independently frozen one-time evaluation is required before activation can be considered.

## Integrity and seal

The base model SHA-256 remains `0e0d07a5347c6027c12e2b86946588eb3c66330a80df499fda7a92d3c6721081`; dataset, split, feature code, threshold, registry, AD, and uncertainty contracts remained unchanged. The validator passed 184/184 substantive checks.

The governed phase manifest SHA-256 is `b7659f3ac4b491cd40913f9085fa77e9b2293ff28bdd9f5fccafb6754ab4befd`. External post-seal verification found zero missing, unexpected, size-mismatched, or hash-mismatched files.
