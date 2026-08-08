# hERG development calibration partition resolution

## Outcome

The partition-resolution preflight concluded `HERG_TRAIN_OOF_GENERATION_REQUIRES_AUTHORIZATION`. No model was loaded or executed, no temporary model was trained, no calibrator was fitted, and no candidate was created.

## Prior invalid partitions

The prior 4,171-record recalibration package is derived entirely from the consumed PubChem AID 588834 external-validation cohort. Those records remain historical external evidence and are permanently prohibited for calibrator fitting, calibration-method selection, threshold selection, hyperparameter selection, candidate selection, or probability-transformation selection.

## Frozen development lineage

The authoritative `herg_curated_v1` scaffold split remains unchanged:

| Partition | N | Positive | Negative | Unique structures | Scaffold groups | Historical role |
|---|---:|---:|---:|---:|---:|---|
| TRAIN | 515 | 364 | 151 | 515 | 361 | Model fitting |
| VALIDATION | 65 | 42 | 23 | 65 | 44 | Model/feature selection |
| TEST | 65 | 38 | 27 | 65 | Historical held-out confirmation |

The dataset, split, base candidate, feature representation, `0.5` threshold, applicability-domain contract, and uncertainty contract were hash-verified and not changed.

## Existing development predictions

No genuine hERG TRAIN out-of-fold or cross-validation prediction artifact exists. Training generated VALIDATION probabilities in memory, but persisted only aggregate metrics. VALIDATION was used to rank 12 feature/model candidates and select `rf_300_balanced` with `morgan_desc`, so it is assigned:

`ALREADY_CONSUMED_FOR_MODEL_SELECTION_DIAGNOSTIC_ONLY`

The only persisted internal row-level hERG prediction artifact is protected TEST output. It is ineligible for calibration development.

## Protected boundaries

- TEST is prohibited for calibrator fitting, method comparison, threshold selection, and hyperparameter optimization.
- PubChem adaptive access remains zero.
- VALIDATION is diagnostic-only and cannot be redefined as clean calibration confirmation.
- Threshold `0.5` remains the operational raw-score threshold.
- Any calibrated-probability threshold interpretation or mapping requires separate authorization.

## Selected future design

Designs based on existing TRAIN OOF, nested existing OOF, or pre-existing eligible VALIDATION predictions are infeasible. The only valid remaining design is new TRAIN-only OOF generation.

The proposed execution, which is not yet authorized, is:

- five `StratifiedGroupKFold` folds grouped by frozen scaffold identity;
- shuffle enabled with seed `1729`;
- five temporary models using the frozen candidate recipe;
- unchanged Morgan radius 2/2,048-bit plus eight-descriptor features;
- every TRAIN record predicted once by a fold model that excluded its scaffold;
- VALIDATION, TEST, and all external data excluded;
- production `herg_v1` never modified.

Estimated execution is five temporary random-forest fits, approximately 5–20 CPU minutes, under 2 GB RAM, and under 20 MB of governed outputs.

## Calibration adequacy and future policy

- NONE baseline: adequate
- Platt: `ADEQUATE_FOR_PLATT`
- Isotonic: `MARGINAL_FOR_ISOTONIC`; nested stability assessment required
- Beta calibration: excluded

After authorized OOF generation, calibration fitting/selection would remain nested within TRAIN OOF pairs. A non-NONE selection would create a distinct inactive calibrated candidate. A new independent untouched external validation source would be required before activation.

## Next authorization

Required permission label:

`AUTHORIZE_HERG_TRAIN_ONLY_OOF_GENERATION`

No calibration fitting, external evaluation, activation, or deployment is authorized by this documentation.
