# BETA-P2 universal scientific-engine adapter

## Architecture and governance

The minimal in-process adapter interface supports request validation, runtime checks, execution, normalization, and metadata. Registration is explicit; duplicate engine/version pairs fail, exact versions are required, registry adapter declarations are checked, and no dynamic import, remote code loading, or automatic download exists.

The execution service resolves the P1 registry and applies this deterministic blocker priority before adapter code runs:

1. rejected scientific validation;
2. unresolved or ineligible licence;
3. inactive activation state;
4. missing or unverified artifact/technical state;
5. incompatible runtime;
6. prohibited deployment;
7. absent or unsupported adapter/task/endpoint.

`PUBLIC_DEMO` and `LOCAL_DEMO` require `APPROVED_BETA` plus `ACTIVE_BETA`. `LOCAL_RESEARCH` and isolated `CI_TEST` accept research or beta approval and an active research/beta state. CI success tests inject deterministic governance records; real records are never changed. Every failure is fail-closed and has no fallback.

## Reference adapters

- `rdkit_descriptor_adapter` 1.0 accepts one non-mixture SMILES and returns a bounded descriptor set, original and canonical SMILES. It reuses the existing descriptor service.
- `medicinal_chemistry_rules_adapter` 1.0 returns only existing Lipinski and Veber evaluations and explicitly labels them screening heuristics.
- `pubchem_compound_evidence_adapter` 1.0 accepts one name, CID, or canonical-SMILES query, reuses the existing provider service, caps synonyms at 12, and is tested only with a mock.
- `bbbp_blocked_adapter` 1.0 is declarative. Governance stops BBBP before artifact deserialization or prediction.

Actual P1 licence and activation states remain authoritative, so all four normal registry-backed paths currently block. The UI shows the decision and standardized domain, uncertainty, limitations, and provenance.

## Limits, safety, and compatibility

The initial synchronous contract accepts one molecule/query, a maximum 30-second requested timeout, and at most 20 parameters. Database output is bounded. Larger/future batch work uses the existing scientific-job bridge; no queue was added. Provider retries remain those already bounded by the reused PubChem service.

Legacy ADMET, EGFR, ranking, Disease-to-Lead, and report routes are untouched and are not redirected through P2. No model, dataset, threshold, calibration, licence, or activation record changes in this phase.

Known limitations: no real engine is currently eligible; synchronous batch execution is intentionally absent; running jobs cannot always be interrupted after starting because the existing thread executor preserves safe cancellation semantics; audit retrieval returns metadata, not normalized scientific output; and external PubChem availability/terms remain unresolved.

## BETA-P3 handoff

BETA-P3 may select and review pretrained ADME engines, but it must first resolve licence, scientific validation, artifact, runtime, and activation requirements without weakening this contract.
