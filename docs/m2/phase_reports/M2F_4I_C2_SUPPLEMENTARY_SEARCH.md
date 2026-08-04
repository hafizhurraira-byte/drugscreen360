# M2F-4I-C2 — Deep Supplementary Dataset Recovery and Qualification

## Phase status

**Scientific decision:** `NO_SUITABLE_DATASET`

**Execution status:** `BLOCKED_VALIDATION`

The scientific qualification workflow completed successfully. The final
validation status was blocked only because the Git repository branch and commit
did not match the repository identity frozen in the original execution
protocol.

The repository mismatch did not affect dataset extraction, provenance review,
assay qualification, molecular standardization, label mapping, overlap
analysis, analogue analysis, reproducibility, or the final scientific dataset
decision.

## Objective

The objective of M2F-4I-C2 was to identify and qualify an independent public
supplementary dataset for external validation of the frozen ERA v2 candidate.

The phase searched official publication, repository, and government sources
for compound-level human estrogen-receptor functional agonism data with:

- explicit positive and inactive records;
- molecular structures or stable identifiers;
- adequate concentration coverage;
- cytotoxicity or interference information;
- documented provenance and licensing;
- sufficient independence from development data;
- sufficient overlap-clean sample size.

## Dataset identified

A promising EPA/FDA dataset was identified:

- **Publication DOI:** `10.1093/toxsci/kfac019`
- **PubMed ID:** `35172002`
- **Repository:** Dryad
- **Dataset DOI:** `10.5061/dryad.s4mw6m97m`
- **Laboratory:** U.S. EPA Center for Computational Toxicology and Exposure
- **Assay:** AIME-VM7Luc estrogen-receptor transactivation assay
- **Chemical library:** 768 ToxCast chemicals
- **Repository version:** v2

The dataset was downloaded manually from the official Dryad record and
processed under the frozen M2F-4I-C2 protocol.

## Source files qualified

### Assay workbook

`AIME-ERTA_384_Tables_All_Submission_v2.xlsx`

- Size: 2,890,003 bytes
- SHA-256:
  `7EC9F58209059FB2AC731B2D247B05B014BB17DDC881CB59BDD6B586B2EC6A0A`
- Scope:
  - 768 chemicals;
  - 4,612 assay records;
  - chemical identity tables;
  - activity calls;
  - concentration-response outputs;
  - cytotoxicity information;
  - structure and metabolism-related tables.

### Supplementary README

`README_AIME-ERTA_384_Manuscript_Sup_Data_v2.docx`

- Size: 17,177 bytes
- SHA-256:
  `E95E8A7F02D9CC826B24D5E9A23607F01CF1C7B1DD1F5E677190480986BC1673`
- Scope:
  - table definitions;
  - publication provenance;
  - assay and supplementary-file descriptions.

The raw files are governed externally and are not included in this repository.

## Provenance and rights

- Provenance classification: `PROVENANCE_COMPLETE`
- Rights classification: `RIGHTS_CLEAR_WITH_ATTRIBUTION`

The publication, repository record, laboratory, source version, compound
identifiers, and file hashes were reconciled.

## Assay compatibility

- Compatibility classification:
  `FUNCTIONAL_ERA_AGONIST_WITH_DEFENSIBLE_MAPPING`
- Compatibility score: `13/14`
- Primary endpoint: AEID 2490, metabolism-negative ER transactivation
- Paired cytotoxicity endpoint: AEID 2491
- Concentration range: approximately 0.002–200 µM
- Replicates: 3

The assay provides defensible functional ER agonist evidence. A limitation is
that the measured response is predominantly, but not exclusively, mediated by
ERα.

## Molecular identity and standardization

- Raw endpoint records: 769
- Structures resolved: 645
- Raw structure-resolution rate: 83.88%
- Final eligible-set structure resolution: 100%

Ambiguous chemical names were not converted into inferred structures.

Standardization included:

- RDKit molecular cleanup;
- fragment-parent selection;
- charge normalization;
- organic-structure validation;
- canonical and isomeric SMILES;
- standard InChIKey and connectivity key;
- Murcko scaffold generation.

## Label policy

The following source-derived mapping was applied:

- `hitc = 1` → provisional positive;
- `hitc = 0` → explicit negative;
- `hitc = -1` → inconclusive.

Missing observations were not classified as negatives.

Records with unresolved cytotoxicity confounding were excluded.

## Negative evidence

Before development-overlap filtering, 450 explicit qualified negatives remained
at each assessed concentration floor:

- ≥1 µM: 450
- ≥3 µM: 450
- ≥10 µM: 450
- ≥30 µM: 450

After all mandatory identity, quality, overlap, parent, and analogue exclusions,
89 qualified negatives remained.

## Source independence

- Independence score: `16/20`
- Classification:
  `INDEPENDENT_LABEL_CAMPAIGN_SHARED_LIBRARY_WITH_LIMITATIONS`

The experimental campaign differs from the development campaign associated
with PubChem AID 743079.

However, the use of a shared ToxCast compound-library lineage remains an
important limitation.

## Development-overlap audit

Substantial overlap with permitted development TRAIN and VALIDATION identities
was identified:

- Exact development overlaps: 459
- Parent development overlaps: 480
- Additional non-parent very-close analogue exclusions: 11
- Morgan radius: 2
- Fingerprint size: 2,048 bits
- Chirality: enabled
- Very-close analogue threshold: Tanimoto ≥0.85

All exact, parent, and mandatory very-close analogue overlaps were excluded.

The consumed protected TEST was not opened or used during this audit.

## Final qualified candidate dataset

After all frozen qualification and exclusion rules:

- Total eligible molecules: 109
- Positive compounds: 20
- Negative compounds: 89

Frozen minimum requirements:

- Total compounds: at least 150
- Positive compounds: at least 20
- Negative compounds: at least 75

The positive and negative requirements passed.

The total-size requirement failed:

- Required total: 150
- Obtained total: 109
- Deficit: 41 compounds

The dataset was therefore not frozen for external model evaluation.

## Final scientific decision

`NO_SUITABLE_DATASET`

The dataset is scientifically useful as a qualified diagnostic evidence source,
but it is not eligible as the final external-validation dataset because only
109 overlap-clean compounds remained.

The frozen sample-size requirement was not reduced to force progression.

## Candidate protection

- Candidate:
  `ERA_V2_REDEV_CANDIDATE_RF_BD08B61A`
- Candidate state: `INACTIVE_CANDIDATE`
- Candidate loaded: no
- Candidate executed: no
- Predictions generated: no
- Performance metrics calculated: no
- Frozen threshold applied: no
- Calibration applied: no
- Consumed TEST reused: no
- M2F-4F-B scientific contents accessed: no

## Reproducibility

Result: `REPRODUCIBLE`

The deterministic rebuild reproduced the record count and the frozen
identity-and-label projection hash.

## Repository identity validation issue

The frozen protocol expected:

- Branch: `main`
- Commit:
  `214a45c640eb9f57d657d832ad020ac9da75e9ef`

The execution environment contained:

- Branch: `docs/m2-era-v2-scientific-development-history`
- Commit:
  `19a3c843b0634eb9344d63f0077bdff7725c8c0d`

The repository had an empty tracked diff and was not modified by M2F-4I-C2.

The mismatch was caused by documentation work occurring after the original
protocol froze the expected repository identity. It did not alter the
scientific outcome.

Validator result:

- Passed: 152
- Total: 180
- Failed checks: repository-identity-dependent checks
- Scientific decision affected: no

## Final sealing

- Governed files: 129
- Manifest SHA-256:
  `B2B64AF60621C66C8765D20B04D2DB36D493C1D3FB2DDBA0373E3BE85C24F829`
- Post-seal verification: `PASS`
- Missing files: 0
- Unexpected files: 0
- Size mismatches: 0
- Hash mismatches: 0

The governed scientific workspace and raw data remain outside the public
repository.

## Current programme status

- External dataset frozen: no
- M2F-4J permission: `NO`
- Candidate activation: `INACTIVE_CANDIDATE`
- Candidate executed: `NO`
- External evaluation performed: `NO`
- Consumed TEST reuse: `NO`
- Partner outreach: active

## Recommended next action

Continue independent partner-data acquisition and search for an additional
compatible source.

A future compatible source must contribute enough new overlap-clean molecules
to exceed the frozen total-size requirement without weakening the scientific
or governance gates.

The current EPA/FDA dataset may be retained as a qualified diagnostic source and
may potentially contribute to a future multi-study dataset only when all
predefined compatibility, independence, provenance, label, and pooling
requirements are satisfied.
