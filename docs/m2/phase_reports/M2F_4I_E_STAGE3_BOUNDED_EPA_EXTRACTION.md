# M2F-4I-E Stage 3 — bounded EPA extraction and Stage 3-R1 adjudication

## Current status

`STAGE3R1_SOURCE_INTERNAL_POOL_READY_FOR_OVERLAP_AUDIT`

Stage 3-R1 supersedes the original qualification interpretation while preserving the original sealed Stage 3 package as historical evidence. The ERA v2 redevelopment candidate remains inactive. No development data, consumed TEST data, AIME records, model artifacts, overlap calculations, or analogue calculations were accessed.

## Governed source

- Release: EPA ToxCast invitroDB v4.3
- Archive SHA-256: `EE159E1CDD28996F85DB13E742700D8D76EF9D5BAF31E3B5E00D249899529C7B`
- Stage 2 manifest SHA-256: `0907578C864F6B14D041C8CB65BDA9766224E4FFE437E7D9F5B644E62F782B03`
- Historical Stage 3 manifest SHA-256: `F39CB4B48EF163F36745201307BD16F869C6BC29C0EAA1D407963921F6857D63`
- Superseding Stage 3-R1 manifest SHA-256: `98999A9C56B84A53CDE2FD86A4D750E4262901DD45B60B4D9010B27CCF9F89A8`

## Allowed endpoints

- `ATG_ERa_TRANS_up` — AEID 117
- `ATG_ERE_CIS_up` — AEID 75
- `OT_ERa_EREGFP_0120` — AEID 750
- `OT_ERa_EREGFP_0480` — AEID 751

`ACEA_T47D_80hr_Positive` remains diagnostic-only and is not validation evidence.

## Historical Stage 3 result

The original decision was `STAGE3_MANDATORY_FIELDS_UNRESOLVED`. It treated every absent chemical-endpoint `mc6` row as unresolved interference, producing zero qualified records. That package remains sealed and unchanged.

Historical source-internal counts were:

- Raw endpoint records: 13,209
- Usable-identity records: 7,106
- Identity exclusions: 6,103
- Qualified active / inactive endpoint records: 0 / 0
- Provisional eligible chemicals: 0

## Stage 3-R1 scientific correction

Official v4.3 documentation describes `mc6` as a sparse Level 6 curve-fit and hit-call caution table. Its release-note example assigns zero flags when a joined flag list is absent, notes that most active series have zero to two flags, and cautions that one to three flags may reflect assay design rather than a poor fit. An absent applicable row therefore means `NO_MC6_FLAG_GENERATED` / `NO_APPLICABLE_MC6_CAUTION_FLAG`; it does not mean experimental `INTERFERENCE_CLEAR`.

All 14 recovered methods were adjudicated by their actual meaning. None is an explicit assay-technology interference method. Cytotoxicity-related, false-positive, false-negative, borderline, range, efficacy, fit, and data-quality cautions are handled separately and with active/inactive-specific actions.

Two related implementation defects were also corrected from preserved checkpoints:

- AEIDs 750 and 751 share MC0 assay component 487; Stage 3 incorrectly joined AEID 751 through component 488.
- invitroDB v4.3 `hitc` is continuous; the official activity example uses `hitc >= 0.9`, not exact equality to 1.

The exact sample-to-chemical identity hierarchy was not broadened. The 6,103 records lacking a retained exact mapping remain failed closed; no name or similarity matching was used.

## Stage 3-R1 requalification

| Measure | Historical Stage 3 | Stage 3-R1 |
|---|---:|---:|
| Raw endpoint records | 13,209 | 13,209 |
| Usable identity | 7,106 | 7,106 |
| Identity exclusions | 6,103 | 6,103 |
| Concentration-supported records | 11,154 | 13,209 |
| Records with mc6 flags | treated generically | 12,213 |
| Records with no generated mc6 flags | treated unresolved | 996 |
| Explicit interference-related mc6 flags | not adjudicated | 0 |
| Qualified active endpoint-chemical records | 0 | 302 |
| Qualified inactive endpoint-chemical records | 0 | 2,549 |
| Indeterminate endpoint-chemical records | 137 | 521 |
| Excluded endpoint-chemical records | 12,178 | 8,943 |
| Provisional positive chemicals | 0 | 107 |
| Provisional negative chemicals | 0 | 645 |
| Endpoint-conflict chemicals | 0 | 76 |
| Eligible source-internal chemicals | 0 | 752 |

These remain `PRE_DEVELOPMENT_OVERLAP`, `PRE_PARENT_OVERLAP`, `PRE_CLOSE_ANALOGUE_EXCLUSION`, `PRE_AIME_POOLING`, and `NOT_FINAL_VALIDATION_COUNTS`. They do not establish final EPA feasibility.

## Validation and next boundary

The focused Stage 3-R1 validator passed 160/160 checks. External post-seal verification reported zero missing, unexpected, size-mismatched, or hash-mismatched files. The full 17.65 GB archive was not rescanned, decompressed, or imported.

The next governed action is the development-overlap and analogue audit using the sealed Stage 3-R1 contract. M2F-4J remains unauthorized.
