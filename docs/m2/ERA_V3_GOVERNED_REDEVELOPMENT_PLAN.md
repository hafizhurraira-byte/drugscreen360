# ERA v3 governed redevelopment plan

## Status and boundary

`ERA_V3_GOVERNED_REDEVELOPMENT_PLAN_FROZEN`

ERA v2 is closed as `RETAINED_RESEARCH_ONLY_INACTIVE_CANDIDATE`. Its one-time external dataset is consumed and cannot be used for training, validation, feature/model/threshold selection, calibration, candidate ranking, or another confirmatory evaluation. ERA v3 planning used only sealed aggregate lessons; no consumed records, predictions, or model weights were accessed.

No ERA v3 candidate, SHA, training run, prediction, metric, threshold, calibration, or activation authorization exists yet.

## Scientific objectives

ERA v3 must improve positive-class recall and reduce false negatives while preserving a predeclared specificity floor. Balanced accuracy and MCC matter alongside ROC-AUC and PR-AUC; accuracy alone is insufficient. Experimental labels, concentration-supported negatives, positive chemical-space coverage, source/scaffold diversity, lineage separation, applicability domain, and uncertainty governance remain mandatory.

## Data and labels

Prioritize independently measured human ERα functional agonist assays with exact chemical identity, concentration response, maximum tested concentration, assay technology, campaign, cytotoxicity, analytical QC, interference, replicates, and complete lineage.

Labels remain positive, negative, indeterminate, or excluded. Positives require experimental functional agonism. Negatives require explicit inactive evidence and documented exposure. Missing data are never negative; model labels, unresolved conflicts, prohibited Tox21 evidence, binding-only, ERβ-only, antagonist-only, identity-incomplete, and concentration-unsupported evidence are excluded.

## Split and leakage strategy

The primary design is `HYBRID_SCAFFOLD_PLUS_SOURCE_CONNECTED_COMPONENT_SPLIT`. Connected groups bind exact/parent identity, scaffold, predeclared close analogues, replicates, relationships, and source lineage before assignment to TRAIN, VALIDATION, and protected TEST.

Positive scarcity is handled through new experimental acquisition, repeated group-aware validation, and explicit feasibility reporting—not duplication before grouping. Protected TEST remains single-access and cannot select models or thresholds.

## Features and models

The bounded feature comparison includes:

- Morgan-2048 bit fingerprints;
- Morgan-2048 count fingerprints;
- a small physicochemical descriptor set;
- MACCS-167 keys;
- Morgan plus descriptors.

Pretrained encoders are deferred unless simpler representations plateau and licensing, commercial permission, offline weights, reproducibility, and dependency burden pass review.

The compute-efficient model shortlist is class-weighted logistic regression, balanced-subsample random forest, descriptor-based histogram gradient boosting, and a development-calibrated linear candidate. Fixed small grids, deterministic seeds, identical group-aware folds, and manifest-based selection are required. No winner is selected in planning.

## Imbalance, threshold, and calibration

Evaluate class weighting, balanced tree subsampling, justified source balancing, and genuine experimental positive enrichment. Synthetic structures, model-generated positives, and naive duplication before scaffold grouping are prohibited.

The primary threshold objective is development-only: maximize sensitivity subject to specificity ≥0.85, MCC >0, and balanced accuracy ≥0.60; break ties using balanced accuracy then MCC. If no threshold satisfies the constraints, the candidate is ineligible. TEST and external optimization are prohibited.

Calibration options are NONE, Platt, isotonic, and validated beta calibration, using development cross-fitting only. Calibrated and uncalibrated variants are separate candidates; TEST/external fitting is prohibited.

## Applicability domain and uncertainty

The primary AD method is maximum TRAIN Morgan Tanimoto, with descriptor distance diagnostic. Thresholds and categories are frozen from TRAIN before validation; external refitting is prohibited, and out-of-domain records remain visible.

Uncertainty candidates include tree disagreement, repeated-model variance, development bootstrap disagreement, development-calibrated conformal prediction, and distance uncertainty. Selection and thresholds use development data only, with reporting by error, label, source, and domain.

## Validation and external evidence

Internal validation requires repeated hybrid-group cross-validation, source-stratified reporting, zero scaffold leakage, confidence intervals, calibration, AD, uncertainty, and error analysis. Planned minimum eligibility includes sensitivity ≥0.50, specificity ≥0.85, balanced accuracy ≥0.65, MCC ≥0.30, ROC-AUC ≥0.75, PR-AUC above prevalence by a frozen margin, valid folds, and no material source-direction reversal.

ERA v3 requires a genuinely new external source or prospectively untouched holdout. Planning targets are at least 150 total, 25 positive, and 100 negative records; these are targets, not claims of availability. Identity, concentration support, exact/parent/analogue exclusion, provenance, prospective protocol freeze, one-time authorization, source strata, and rerun prohibition are required.

## Roadmap

The stop-gated path runs V3-P0 through V3-P13: closure verification, source feasibility, curation protocol, dataset freeze, split audit, feature protocol, bounded benchmark, threshold/calibration selection, internal TEST, inactive candidate lock, new external acquisition, protocol freeze, one-time evaluation, and activation-or-closure review.

The next authorized phase is `V3-P1_NEW_DATA_SOURCE_FEASIBILITY`. Start with metadata-only source feasibility and stop early if independent data cannot meet scientific requirements. Large acquisition, deep models, and pretrained dependencies are deferred until justified.

## Seal

- Validator: 160/160 checks passed with no warnings.
- Planning manifest SHA-256: `A9594B6A4D1AACAB6C823834425D2A47693645CE97EA511E1D7CE8CE23A5ED46`
- Post-seal verification: pass with zero missing, unexpected, size-mismatched, or hash-mismatched files.
- Current authorization: planning frozen; V3-P1 source feasibility only.
