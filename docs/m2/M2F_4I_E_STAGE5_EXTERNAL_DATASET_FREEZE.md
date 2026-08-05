# M2F-4I-E Stage 5 external dataset freeze

## Outcome

`STAGE5_EXTERNAL_VALIDATION_DATASET_FROZEN`

The governed AIME–EPA dataset was pooled, qualified, validated, locked, and sealed without loading or executing the candidate and without accessing the consumed TEST split. Authorization is limited to `M2F-4J_PROTOCOL_FREEZE_ONLY`; model evaluation remains unauthorized.

## Dependencies

| Package | Manifest SHA-256 |
|---|---|
| Stage 1 | `DF6B1451C515C5E6BD2591ED8176E266C1060B5D66018A309C0B2FF673591C1E` |
| Stage 2 | `0907578C864F6B14D041C8CB65BDA9766224E4FFE437E7D9F5B644E62F782B03` |
| Stage 3 | `F39CB4B48EF163F36745201307BD16F869C6BC29C0EAA1D407963921F6857D63` |
| Stage 3-R1 | `98999A9C56B84A53CDE2FD86A4D750E4262901DD45B60B4D9010B27CCF9F89A8` |
| Stage 4 | `5FFC285081A8C39FA1DDFA915B8832355FAF3F514842A664F2850EFBFC6C0E11` |
| AIME C2-R2 | `6AA24D39DDB750EE32EBED8B7F0630C8FC49A2589BD4FEBB4C75F4690BBAA3CC` |

All required upstream integrity and post-seal checks passed.

## Pooling and qualification

- AIME input: 109 records (20 positive, 89 negative).
- Stage 4 EPA input: 90 records (15 positive, 75 negative).
- Only governed qualified AIME records and `EPA_OVERLAP_CLEAN_ELIGIBLE` records were admitted.
- Frozen Stage 4 structures and overlap decisions were reused; the analogue search was not rerun.
- Final exact, connectivity, and parent-identity reconciliation found no remaining duplicates.
- No label conflicts, unresolved identities, negative-eligibility failures, or QC exclusions remained.
- Labels remain traceable to experimental sources; all negative records retain documented concentration support.

## Frozen dataset

| Measure | Count |
|---|---:|
| Total | 199 |
| Positive | 35 |
| Negative | 164 |
| AIME | 109 |
| EPA | 90 |

Program contribution counts are AIME 109, EPA ATG 35, and EPA OT 77. These are evidence-contribution counts; a multi-endpoint EPA chemical can contribute to both EPA programs without creating duplicate dataset records.

Endpoint contribution counts are AIME VM7Luc 109, ATG ERa TRANS 31, ATG ERE CIS 29, OT ERa EREGFP 0120 72, and OT ERa EREGFP 0480 73.

All frozen gates pass: total ≥150, positive ≥20, and negative ≥75.

## Hashes and lock

- CSV SHA-256: `6A3CB2EEF13E7BBFCB0963096925BC3FAE0F0D72E322945810C56E2D62B8D903`
- JSONL SHA-256: `1977340A3ED4B517BC99DA12E8B3DA8D5382423CA9CA3FBCEE1EB355B9F12C21`
- Dataset content SHA-256: `7F3351D05138E89B1F9C6BA6633200F98AC2DEC42BF3396F249ECEE3E201B625`
- Row-order-independent identity-and-label hash: `3F66E4A693D38D33974EF12B5808BC6D16D48F4481DEE81AE086ADCA4A0AF397`
- Schema hash: `BAC0E385906133D4C739A6FB284D99A600251E04C387D6C50BA1FEC85E89B26B`
- Stage 5 manifest SHA-256: `E1A61952F26FFF19E3F073816F4D9FBA2EBB059D5C3E3B2AB9659E5514B23111`
- Dataset status: `FROZEN_INDEPENDENT_EXTERNAL_VALIDATION_DATASET`
- Validator: 184/184 checks passed, with no failures or warnings.
- External post-seal verification: pass; no missing, unexpected, size-mismatched, or hash-mismatched files.

## Safeguards and next phase

Candidate load, execution, prediction, metric, model-evaluation, consumed TEST, and M2F-4F-B access counters remained zero. The candidate remains `INACTIVE_CANDIDATE`. M2F-4K evaluation is not authorized.

The next permitted phase is M2F-4J protocol freezing only.
