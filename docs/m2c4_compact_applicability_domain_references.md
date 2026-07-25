# M2C-4 Compact Applicability-Domain References

## Problem Addressed

M2C-3 ADMET endpoint prediction rebuilt applicability-domain fingerprints at runtime by loading curated CSV files through the registered `split_reference.json`. M2C-4 removes that production dependency for active BBBP, ESOL, and hERG models.

## Compact Representation

The external artifact generator writes:

- `domain_fingerprints.npz`
- `domain_reference_manifest.json`
- `domain_reference_freeze_record.json`

`domain_fingerprints.npz` stores packed Morgan bit vectors as `uint8`, stable TRAIN record IDs, canonical SMILES hashes, bit length, fingerprint count, and deterministic order hash. It is loaded with `allow_pickle=False`.

## Frozen Feature Schema

| Endpoint | Fingerprint | Radius | Bits | Feature set for model | AD vector |
|---|---:|---:|---:|---|---|
| BBBP | RDKit Morgan | 2 | 2048 | Morgan | Morgan bit vector |
| ESOL | RDKit Morgan | 2 | 2048 | Morgan + 8 descriptors | Morgan bit vector |
| hERG | RDKit Morgan | 2 | 2048 | Morgan + 8 descriptors | Morgan bit vector |

Applicability-domain similarity remains exact Tanimoto over Morgan bit vectors. Model prediction features, thresholds, calibration, uncertainty, and activation state are unchanged.

## Artifact Results

| Endpoint | TRAIN count | File size | Domain artifact SHA256 | Schema hash |
|---|---:|---:|---|---|
| BBBP | 1571 | 149,853 bytes | `5ec43a15fc732042db0acb74385601ebe28e1ec1fb0306979c91637f036bc584` | `6fd3335cf892b9892c10da39eea7529aa2923da8ae124b6e07e8fe59ffb76921` |
| ESOL | 767 | 59,624 bytes | `9088eac34c9ede65eade3be5ace820a6ad6e73d36d9d6c10106b8b6b177c919a` | `bd81dcd905157d2b018843b4dfd1846f0b4f6dad957db119ee6c4e447ef1a41c` |
| hERG | 515 | 50,248 bytes | `68f02227162c05a2213d27268a7b8897a2d2f08325c46d1144de237c5cd3caf8` | `ecb3c08981fbcd79f7b79aaf5fbab147fd94768aa4c5632354bead4db164e862` |

Freeze-amendment hashes:

- BBBP: `cbb8fd87c67eab884ff90e2291692ffab36296af490222d8c005875cda6a1b8f`
- ESOL: `9d2e76f74d3ea1689e146e2cdaf16003a338e2cac1bf8c099c6088d2f47f54a8`
- hERG: `d15ccee9b419a4bc79ded0b621c12c316c2326cc1b81e42f3b813f80c3cf85f3`

## Threshold Preservation

Thresholds are read from the frozen M2C-2 domain reference and copied into the compact manifest:

- BBBP: IN `0.2911392405063291`, BORDERLINE `0.22007339449541286`
- ESOL: IN `0.2857142857142857`, BORDERLINE `0.19405192761605036`
- hERG: IN `0.2362121212121212`, BORDERLINE `0.18733568318473978`

Classification uses full-precision similarity before display rounding.

## Parity

| Endpoint | Records checked | Max similarity difference | Domain-label mismatches |
|---|---:|---:|---:|
| BBBP | 1965 | 0.0 | 0 |
| ESOL | 1116 | 0.0 | 0 |
| hERG | 645 | 0.0 | 0 |

## Runtime Behaviour

Prediction now fails closed for eligible endpoints when compact references are missing, corrupt, hash-mismatched, schema-mismatched, or unsafe object arrays. Runtime prediction no longer reads curated CSV files.

The cache is process-local, lazy, endpoint-specific, thread-guarded, and keyed by endpoint, model ID, and domain artifact hash. Cache entries include packed fingerprints, reference hashes, thresholds, schema hash, reference count, artifact hash, and estimated memory bytes. Tests can call `clear_domain_reference_cache()`.

## Performance Snapshot

Measured on the local workstation:

- Cold load, all three endpoint references: 1.5302 seconds
- Estimated cache memory, all three: 1,586,268 bytes
- 100 molecules, all three endpoints: 1.3237 seconds, 75.55 molecules/sec
- 1,000 molecules, all three endpoints: 13.7594 seconds, 72.68 molecules/sec
- 5,000 molecules, all three endpoints: 77.8458 seconds, 64.23 molecules/sec

These are local engineering benchmarks, not production scalability claims.

## API and Report Provenance

Prediction responses now include:

- `domain_reference_version`
- `domain_reference_hash`
- `domain_schema_hash`
- `domain_reference_count`
- `similarity_metric`
- `domain_thresholds`
- `compact_reference_used`

Final reports include compact-reference provenance in endpoint-specific ADMET model evidence rows.

## ClinTox Status

ClinTox CT_TOX v1 remains registered for transparency, NOT_ELIGIBLE, inactive, and unavailable for production prediction. M2C-4 does not generate or load a production compact reference for ClinTox.

## Limitations

Compact references accelerate and harden applicability-domain lookup only. They do not improve model performance, change model predictions, provide clinical validation, or replace endpoint-specific external validation.

## Next Phase

M2C-5 should consider model-load caching for the estimator objects themselves if batch prediction throughput becomes the bottleneck.
