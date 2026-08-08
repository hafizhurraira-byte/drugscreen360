# hERG external-validation source feasibility

## Governed outcome

The model-blind feasibility phase returned `HERG_EXTERNAL_SOURCE_MANUAL_ACQUISITION_REQUIRED`. It did not construct an external dataset, load or execute `herg_v1`, load or execute the Platt calibrator, generate predictions, calculate external metrics, tune a threshold, activate a candidate, or deploy anything.

The target remains inactive candidate `HERG_V1_CAL_PLATT_B7BDD44F7E47` (SHA-256 `b7bdd44f7e471199553f4a8a82e63aa2f4862091a565a9a6ade273de152788f1`). The authoritative calibration package is the 184/184-check execution sealed under manifest `b7659f3ac4b491cd40913f9085fa77e9b2293ff28bdd9f5fccafb6754ab4befd`. The compact `563425…bd890` package is superseded; unsealed incomplete workspaces are quarantined and excluded from dependency resolution.

## Frozen source requirements

Sources require experimental human hERG/KCNH2 evidence, resolvable chemical structures, compound-level labels, traceable assay provenance, an interpretable activity definition, experimentally tested positives and negatives, auditable independence, and assessable validation-use rights. Tier 1 is manual or automated patch clamp with concentration response; Tier 2 is another high-quality functional concentration-response assay; Tier 3 is a traceable curated functional classification.

Preferred size is at least 300 compounds, 50 positives, and 100 negatives. Acceptable size is at least 150 compounds, 25 positives, and 75 negatives. Source ranking excluded predictions, expected model performance, and chemical-space favorability.

## Sources assessed

The provisional primary source is the GSK IonWorks Barracuda/PatchXpress 353-compound study reported by Gillie et al. It is an original Tier-1 automated patch-clamp study and provisionally independent of the consumed PubChem screen. Manual resolution is required because public availability of the complete compound identities and result table, class balance, overlap, and validation-use terms has not been confirmed.

Backups are the open Polak et al. 263-molecule electrophysiology compilation, after its mixed literature lineage is checked against development sources, and the Tox21 10K hERG screen only after excluding and stratifying its documented shared lineage with AID 588834. ChEMBL remains conditional because it aggregates mixed origins likely to overlap development and consumed sources. CiPA/HESI panels are biologically strong but too small alone. BindingDB was rejected as a primary source because functional evidence and experimentally tested negatives are not assured. hERGCentral/MLSMR was rejected for shared consumed lineage.

## Future qualification

Future acquisition must preserve immutable raw files and provenance, resolve structures, freeze label handling, and exclude exact, connectivity, parent, tautomer, and shared-lineage overlap against hERG TRAIN, VALIDATION, TEST, and consumed PubChem identities. PubChem predictions, errors, residuals, and calibration outcomes remain prohibited.

The proposed close-analogue audit uses Morgan radius 2, 2,048 bits, and Tanimoto, with 0.85 frozen as the primary flag and sensitivity reporting at 0.80 and 0.90. Close analogues are flagged for stratified analysis unless a future protocol prospectively requires exclusion.

One independent source is preferred. Pooling is permitted only if no single source meets acceptable class counts and must retain source identity, source-stratified metrics, predeclared conflict handling, structure deduplication, and heterogeneity analysis.

Future one-time evaluation must freeze ROC-AUC, PR-AUC, Brier score, log loss, 10-bin equal-width ECE, calibration slope/intercept, and applicability-domain strata before model execution. The operational threshold remains 0.5 in raw-probability space; calibrated-space operational threshold remains unauthorized.

## Seal and next phase

The validator passed 148/148 checks. The phase manifest SHA-256 is `2f0120e96c2ec2a8fd9de4299274937714dad4533daa7c9a6105b92c180f0a2f`; independent post-seal verification found zero missing, unexpected, size-mismatched, or hash-mismatched files.

Next action: manually obtain or confirm the GSK compound-level supplement and validation-use terms under a separately authorized acquisition-and-qualification phase. No external evaluation is authorized.
