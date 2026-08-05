# M2F-4I-E Stage 4 — development overlap and analogue audit

## Decision

`STAGE4_EPA_CONTRIBUTION_READY_FOR_POOLING`

Stage 4 leaves 90 overlap-clean EPA compounds suitable for a later governed AIME–EPA pooling phase. This is not a final external-validation dataset, and no model evaluation occurred.

## Provenance and safeguards

Stage 1, Stage 2, historical Stage 3, and superseding Stage 3-R1 manifests and post-seal results were verified. Stage 3-R1 supplied 752 eligible EPA chemicals: 107 provisional positives and 645 provisional negatives.

The sealed M2F-4I-C2-R2 AIME package was verified at 109 compounds (20 positive and 89 negative). The current candidate's authoritative development reference is the sealed M2F-4D train and validation identity set: 4,962 train plus 625 validation compounds, or 5,587 total. The 109-compound value previously associated with development is the AIME count, not the current redevelopment set. Protected TEST identities and evaluation data were not used.

The candidate remained inactive. Candidate loads, executions, predictions, metrics, consumed TEST access, and protected M2F-4F-B scientific access all remained zero.

## Structure standardization

The audit used Python 3.14.5 and RDKit 2026.03.3. Deterministic standardization applied RDKit cleanup, largest-organic-fragment selection, uncharging, explicit stereochemistry retention for full structures, stereochemistry-insensitive parents, and separate canonical-tautomer representations. Raw structures and removed fragments were preserved. Missing, partial, metal-containing, or incomplete standardized identities failed closed.

- EPA: 712/752 structure-usable; 40 quarantined
- Development: 5,551/5,587 structure-usable; 36 partial and not analogue-auditable
- AIME: 109/109 structure-usable
- EPA unique full structures: 712
- EPA unique connectivity identities: 709
- EPA unique standardized parents: 704
- EPA internal parent duplicates excluded: 8

## Overlap hierarchy

Exclusions used a single precedence order to avoid double-counting: structure quarantine, EPA internal duplicate, development exact full structure, connectivity equivalence, parent equivalence, canonical-tautomer equivalence, close analogue, then AIME duplicate handling.

| Sequential exclusion | EPA compounds |
|---|---:|
| Starting Stage 3-R1 eligible pool | 752 |
| Structure quarantine | 40 |
| EPA internal parent duplicates | 8 |
| Development exact full-structure overlap | 510 |
| Additional development connectivity overlap | 26 |
| Additional development parent overlap | 20 |
| Additional development tautomer overlap | 1 |
| Additional development close analogues | 14 |
| AIME duplicate label-discordance quarantine | 9 |
| AIME concordant exact/parent duplicates excluded from double counting | 34 |
| Overlap-clean EPA contribution | 90 |

The overlap-clean contribution contains 15 provisional positives and 75 provisional negatives.

## Analogue protocol

The pre-existing M2F-4I-C2 rule was reused: Morgan fingerprint, radius 2, 2,048 bits, chirality disabled, standardized-parent representation, exhaustive Tanimoto nearest neighbour, and operational threshold 0.85. The threshold predates this audit and was not selected to force feasibility.

| Threshold | Close analogues excluded | Remaining after preceding tiers |
|---:|---:|---:|
| 0.70 | 28 | 119 |
| 0.75 | 20 | 127 |
| 0.80 | 16 | 131 |
| 0.85 | 14 | 133 |
| 0.90 | 11 | 136 |

## AIME cross-source findings

Among EPA compounds reaching cross-source comparison, 40 had an AIME exact duplicate and three had an additional AIME parent duplicate. Nine duplicate relationships were label-discordant and were quarantined. Exact and parent duplicates are reserved for one future pooled representation. Close similarity was diagnostic only and did not infer or alter labels.

## Future pooled projection

Pooling has not occurred. If the sealed contributions are combined in the next governed phase, the projection is:

- AIME: 109 total, 20 positive, 89 negative
- EPA contribution: 90 total, 15 positive, 75 negative
- Projected pool: 199 total, 35 positive, 164 negative

The projected total, positive, and negative gates all pass, and the EPA contribution exceeds the minimum of 41.

## Validation, limitations, and next phase

The Stage 4 validator passed 210/210 checks. External post-seal verification reported zero missing, unexpected, size-mismatched, or hash-mismatched files.

Forty EPA structures and 36 development structures were not analogue-auditable and were handled fail-closed. Counts remain post-development-overlap, post-close-analogue exclusion, pre-final-AIME-pooling, and not final external-validation counts.

The next authorized scientific phase is governed AIME–EPA pooling and final dataset freeze. Model evaluation remains unauthorized.
