# hERG independent external-dataset qualification

## Governed outcome

The model-blind qualification phase returned `HERG_HIGH_QUALITY_EXTERNAL_STRATA_FROZEN_POOL_INCOMPLETE`. HESI/FDA 2025 was the sole qualified independent Tier-1 lineage. After prospective labeling and exact/connectivity overlap removal against development and consumed PubChem identities, only 2 positive and 0 negative records remained eligible. This is below the frozen minimum, so no confirmatory external dataset was created or frozen.

The validator passed 240/240 checks. The sealed phase manifest SHA-256 is `8fb63fed700c539fc85cb892666b8c0df3042d9640ad5a5739262a77bb85db22`; the lock SHA-256 is `fa8bf2337045f02bd78164c47cf9be4bbac2d9bed513dca406bba9e3317f81e6`.

## Frozen label rule

Authorization `HERG_EXTERNAL_LABEL_RULE_10UM` was frozen before final labeling. Functional hERG measurements are positive at IC50 <= 10 µM (pIC50 >= 5.0) and negative above that boundary. Ambiguous censoring and materially discordant laboratory estimates crossing pIC50 5.0 are indeterminate. Missing values, database absence, non-hits, and untested compounds are never negatives.

## Source adjudication

The HESI/FDA resource is an original five-laboratory manual whole-cell patch-clamp study with corrected-concentration pIC50 estimates and qualifies as Tier 1. The Zenodo 5807719 and 8229536 resources remain source-mining compilations: their ChEMBL, PubChem, literature-compilation, patent, BindingDB, and modeling-dataset lineages cannot be treated as independent functional assays without record-level original-assay provenance. PubChem-derived records are also shared with the consumed external lineage.

The authors' development/evaluation splits in both Zenodo resources were treated as non-authoritative. Structure equivalence was audited across resources, but the compilations were not pooled into confirmatory evidence.

## Preserved safeguards

No production model or inactive Platt calibrator was loaded or executed. No predictions or external performance metrics were produced; no threshold was tuned; no TEST outcomes or PubChem outcomes were accessed; and no candidate was activated or deployed. The current `herg_v1` predictor and inactive calibrated candidate remain unchanged.

The next governed action is `BEGIN_HERG_ADDITIONAL_EXTERNAL_SOURCE_ACQUISITION`. A new source must supply traceable quantitative functional hERG evidence, experimentally supported negatives, resolvable structures, auditable independence, and sufficient overlap-surviving class counts before an external dataset can be frozen.
