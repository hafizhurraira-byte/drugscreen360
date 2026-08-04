# M2F-4I-E Stage 3 — bounded EPA extraction

## Status

`STAGE3_MANDATORY_FIELDS_UNRESOLVED`

Stage 3 streamed the official EPA ToxCast invitroDB v4.3 archive and extracted only the four provisionally allowed human ERα functional endpoints. The candidate remained inactive, and no development data, consumed TEST data, AIME records, or model artifacts were accessed.

## Governed source

- Release: EPA ToxCast invitroDB v4.3
- Archive SHA-256: `EE159E1CDD28996F85DB13E742700D8D76EF9D5BAF31E3B5E00D249899529C7B`
- Stage 2 manifest SHA-256: `0907578C864F6B14D041C8CB65BDA9766224E4FFE437E7D9F5B644E62F782B03`
- Stage 3 manifest SHA-256: `F39CB4B48EF163F36745201307BD16F869C6BC29C0EAA1D407963921F6857D63`

## Allowed endpoints

- `ATG_ERa_TRANS_up` — AEID 117
- `ATG_ERE_CIS_up` — AEID 75
- `OT_ERa_EREGFP_0120` — AEID 750
- `OT_ERa_EREGFP_0480` — AEID 751

`ACEA_T47D_80hr_Positive` remained diagnostic-only and was not extracted as validation evidence.

## Extraction and qualification

The gzip archive was streamed with bounded memory and early AEID/assay-component filtering. It was never expanded to disk or imported into MySQL. Qualification preserved exact source identity, tested concentrations, activity, fitted AC50 and efficacy, cytotoxicity, analytical QC, interference flags, and replicate evidence.

Source-internal, pre-overlap counts:

- Raw endpoint records: 13,209
- Unique raw chemicals: 5,094
- Qualified active endpoint records: 0
- Qualified inactive endpoint records: 0
- Indeterminate endpoint records: 137
- Excluded endpoint records: 12,178
- Provisional eligible chemicals: 0
- Scale indicator: `LESS_THAN_41`

These are `PRE_DEVELOPMENT_OVERLAP`, `PRE_PARENT_OVERLAP`, `PRE_CLOSE_ANALOGUE_EXCLUSION`, `PRE_AIME_POOLING`, and `NOT_FINAL_VALIDATION_COUNTS`.

## Safeguards and decision

Missing activity was never interpreted as inactivity. Records failed closed for identity, concentration, mandatory analytical QC, cytotoxicity, or interference limitations. In particular, absence of a joined `mc6` flag was not treated as explicit interference-clear evidence.

The focused validator passed 140/140 checks, and external post-seal verification reported zero missing, unexpected, size-mismatched, or hash-mismatched files. Development overlap and analogue analysis have not occurred.

## Next phase

Resolve or formally adjudicate mandatory chemical-level interference evidence before any development-overlap or analogue-audit phase. No M2F-4J authorization is granted.
