# BETA-P3 engine selection decision

## Candidates reviewed

ADMET-AI 2.0.1, a DeepChem-based pretrained option, and the required no-integration disposition were reviewed. The detailed evidence matrix is in `docs/beta_p3_adme_candidate_review.md`.

## Evidence sources

Only official repositories, licence files, package metadata, documentation, release tags, the peer-reviewed ADMET-AI publication, and TDC's official licence boundary were used.

## Licence findings

ADMET-AI code is MIT-licensed. That code licence was not treated as a model-weight licence. Inspection of the 2.0.1 wheel and source archive confirmed and hashed ten bundled pretrained `.pt` weights, but found no separate official grant explicitly covering them. Both archives also bundle a DrugBank-derived CSV that the model loads by default, without DrugBank licence, version, or permission evidence; DrugBank states that use or redistribution requires a licence and citation. ADMET-AI identifies TDC datasets, while TDC directs users to dataset-specific terms; endpoint-by-endpoint training-data rights remain unresolved. DeepChem code is MIT-licensed, but there is no selected model artifact whose weight and dataset licences can be reviewed.

Technical licence review was completed from official published terms. Formal legal review may still be required before any commercial deployment.

## Scientific findings

The ADMET-AI paper describes v1 models. Upstream states that v2 was retrained from scratch and its predictions do not exactly match v1, so published v1 metrics cannot be silently transferred to v2.0.1. Endpoint metadata provides useful names, units, sample sizes, and metrics, but no endpoint can pass while weight and dataset gates remain unresolved. DrugBank percentiles are contextual comparisons, not an applicability-domain method. A model-native uncertainty contract was not established.

DeepChem provides model-building and restoration infrastructure, not a specific frozen, validated ADME engine meeting this phase's requirements.

## Runtime findings

ADMET-AI supports local CPU/GPU inference and requires Python 3.11 or newer with Chemprop, Torch, RDKit, and Lightning. Its official frozen environment differs substantially from the main application. No installation or probe was performed because archive inspection failed the mandatory asset-rights gate; creating an environment or loading weights would add risk without changing the selection decision.

## Risk findings

- ADMET-AI: high licence risk, high v2 scientific-transfer risk, medium dependency-isolation risk.
- DeepChem option: high qualification risk because no concrete pretrained artifact exists.
- No integration: no new scientific/runtime risk and preserves all current governance.

## Selected engine

None.

## Selected version

None.

## Selected endpoints

None. Approved endpoint count is zero.

## Rejected endpoints

All ADMET-AI v2.0.1 endpoints remain unapproved as a group because mandatory weight-licence and training-data gates fail before endpoint activation. This is not an endpoint-specific scientific rejection.

## Rejected candidates

- ADMET-AI 2.0.1: `NOT_SELECTED_LICENCE`; additionally blocked pending v2-specific validation and reproducibility qualification.
- DeepChem pretrained option: `NOT_SELECTED_NO_QUALIFIED_PRETRAINED_ARTIFACT`.

## Conditions of approval

Future reconsideration requires explicit official pretrained-weight terms, endpoint-by-endpoint dataset rights, a frozen v2 artifact/endpoint manifest with hashes, v2-specific validation evidence, and a controlled isolated runtime probe. These conditions must be satisfied before adapter implementation or registry activation.

## Deployment permissions

No new deployment profile is permitted. No public, demo, CI, beta, or local-research execution approval is granted.

## Activation recommendation

`NO_CANDIDATE_APPROVED`. Do not register or activate an external pretrained ADME engine.

## Remaining blockers

1. Explicit model-weight licence evidence for ADMET-AI v2.0.1.
2. DrugBank provenance, version, permission, and redistribution evidence for the bundled CSV, or an authoritative package without that asset.
3. Endpoint-by-endpoint training and benchmark dataset terms.
4. Frozen v2-specific validation evidence and classification semantics.
5. Runtime manifest and isolated reproducibility, download, determinism, performance, domain, and uncertainty probes.

