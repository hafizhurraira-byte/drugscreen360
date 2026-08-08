# hERG development-only calibration execution

## Governed outcome

The authorized TRAIN-only phase selected **Platt calibration** and created the scientifically distinct candidate `herg_v1_calibrated_v1` with state `INACTIVE_CALIBRATED_CANDIDATE`. The current `herg_v1` predictor remains unchanged and operational. Nothing was activated, deployed, or externally evaluated.

The source was the sealed 515-record hERG TRAIN OOF package. Its file-manifest SHA-256 was `60cc014422cacf44030fba5ca8b0c2b23d5c8b081cb1e00b3ef21d0ce8954c5e`; the prediction CSV SHA-256 was `e924d90ad44d4d971d858e8e37a7bebdbccd1c0ba888976b3a95c96431d4c1b2`. Both matched before scientific access.

## Leakage-resistant selection

NONE, Platt, and isotonic were compared using five-fold scaffold-group-preserving cross-fitting entirely within the 515 sealed TRAIN-derived OOF pairs. Each calibrator was fitted on four OOF folds and evaluated on the untouched fifth fold; held-out predictions were pooled only after every record had one cross-fitted calibrated probability. The final Platt calibrator was fitted on all 515 OOF pairs only after method selection.

The execution protocol fixed metric definitions, admissibility cutoffs, practical-equivalence rules, and isotonic safeguards before record-level outcomes were loaded. Platt was logistic regression on the clipped logit of the raw OOF probability. Isotonic used out-of-range clipping.

## Development-only results

| Method | ECE | Brier | Log loss | Calibration intercept | Calibration slope | ROC-AUC | PR-AUC | Decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| NONE | 0.105337 | 0.140362 | 0.445869 | 0.210721 | 1.582267 | 0.868314 | 0.940118 | admissible |
| Platt | 0.048890 | 0.133512 | 0.423306 | 0.051203 | 0.938319 | 0.865457 | 0.938726 | selected |
| Isotonic | 0.049250 | 0.132251 | 0.719354 | 0.363354 | 0.458791 | 0.853677 | 0.926556 | rejected |

Isotonic was rejected because log loss worsened and the frozen ROC-AUC and PR-AUC preservation limits were exceeded. Platt materially improved ECE, Brier score, log loss, calibration intercept, and calibration slope while remaining inside both discrimination-preservation limits.

At the unchanged diagnostic threshold of 0.5, Platt balanced accuracy was 0.744369 and MCC was 0.539329. These are development-only diagnostics; the threshold was not tuned. Applicability-domain and tree-level uncertainty methods were preserved unchanged.

## Candidate and validation status

`herg_v1_calibrated_v1` contains the final TRAIN-OOF-fitted Platt transformation and explicit lineage to `herg_v1`. It is inactive, non-deployable under this authorization, and does not replace or alter the base model.

The consumed PubChem cohort confers no calibration-validation status on the new candidate. A new untouched external validation source is required before activation can be considered under separate authorization. VALIDATION and TEST were not used for calibration fitting or selection; PubChem records, labels, predictions, residuals, ECE, and individual outcomes were not accessed adaptively.

## Integrity and seal

The base model SHA-256 remained `0e0d07a5347c6027c12e2b86946588eb3c66330a80df499fda7a92d3c6721081`. Dataset membership, labels, features, model weights, threshold 0.5, applicability-domain method, and uncertainty method were unchanged. The validator passed 27 of 27 checks.

The phase is sealed under manifest SHA-256 `5634257356b79584cd1c3307cc9e83db4284be398ac7009361b7abdf3f2bd890`. Independent post-seal verification found zero missing, unexpected, size-mismatched, or hash-mismatched files.
