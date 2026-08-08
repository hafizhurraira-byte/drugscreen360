# hERG TRAIN-only OOF prediction package

The authorization `AUTHORIZE_HERG_TRAIN_ONLY_OOF_GENERATION` permitted one bounded development-only operation. Five temporary `rf_300_balanced` models were trained with deterministic `StratifiedGroupKFold` (`n_splits=5`, scaffold groups, shuffle enabled, seed 1729) on the frozen 515-record TRAIN partition: 364 positive, 151 negative, and 361 scaffold groups.

Every TRAIN record received exactly one holdout probability from a model that saw neither that record nor its scaffold group. Coverage was 515/515 with no missing, duplicate, invalid, or scaffold-leaking predictions. Fold sizes were 102, 104, 104, 102, and 103, and every fold contained both classes. The five models are retained only as reproducibility evidence and are marked `TEMPORARY_OOF_FOLD_MODEL`, `NOT_REGISTERABLE`, `NOT_ACTIVATABLE`, and `NOT_DEPLOYABLE`.

The unchanged input contract was Morgan radius 2 with 2,048 bits followed by the eight frozen RDKit descriptors, for 2,056 features. The base `herg_v1` candidate, dataset, split, and frozen threshold remained unchanged. The production model was neither loaded nor executed.

Development-only OOF diagnostics were ROC-AUC 0.868314, PR-AUC 0.940118, Brier score 0.140362, log loss 0.445869, and 10-bin equal-width ECE 0.105337. At the unchanged diagnostic threshold 0.5, balanced accuracy was 0.747189 and MCC was 0.522132. These are not final candidate-validation metrics.

VALIDATION scientific access, TEST scientific access, and adaptive PubChem access were all zero. No calibrator was fitted, no threshold was tuned, and no candidate was created, activated, or deployed. The validator passed 148/148 checks and external post-seal verification found zero missing, unexpected, size-mismatched, or hash-mismatched files.

The package decision is `HERG_TRAIN_ONLY_OOF_PACKAGE_FROZEN`, with calibration readiness `OOF_READY_FOR_CALIBRATION`. Calibration is not authorized by this result. Any development-only comparison of NONE, Platt, or isotonic requires separate `HERG_DEVELOPMENT_ONLY_CALIBRATION_EXECUTION` authorization; TEST and PubChem remain prohibited, and new independent external validation remains required.
