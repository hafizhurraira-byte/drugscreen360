# BETA-P1A scientific-engine registry

## Purpose and architecture

The additive registry describes scientific engines without executing or changing them. `scientific_engines` stores identity; `scientific_engine_versions` stores versioned declarations; licence reviews, deployment permissions, and append-only activation history are separate tables. Foreign keys and composite primary keys preserve identity and prevent duplicate versions. Identical registration is idempotent; conflicting duplicates return HTTP 409.

Optional scientific facts remain null when unknown. Public responses recursively omit path-, credential-, token-, API-key-, and secret-named fields. The registry exposes bounded list/discovery APIs and never returns raw database rows.

## Governance

Technical, scientific-validation, model, activation, and runtime-health states remain separate. Beta activation requires `AVAILABLE`, `VALIDATED_FOR_SCOPE`, `APPROVED_BETA`, an artifact hash, explicit endpoints and schemas, limitations, and a permitted deployment profile. Research activation accepts `APPROVED_RESEARCH` or `APPROVED_BETA` but still rejects rejected validation and artifact/configuration failures.

Code, weights, training data, and database terms are recorded independently. Open-source code never implies weights, data, redistribution, or commercial permission. Failure defaults to `FAIL_CLOSED`; fallback defaults to `NO_FALLBACK`. Deployment profiles are `LOCAL_RESEARCH`, `LOCAL_DEMO`, `PUBLIC_DEMO`, and `CI_TEST`.

## Existing governance and migration

This phase does not migrate or activate existing models and does not replace the stricter EGFR/activity or endpoint-specific ADMET gates and histories. EGFR v2 keeps its current state; BBBP v1, ESOL v1, and hERG v1 remain active; ClinTox CT_TOX v1 remains `NOT_ELIGIBLE` and inactive. `ERA_FUNCTIONAL_AGONIST_V2` remains pending internal research and is not registered.

The deterministic BETA-P1B import will read existing activity/ADMET registration manifests, preserve exact IDs, versions, hashes and activation states, attach licence reviews only from reviewed evidence, and remain idempotent. Rule-based ADMET and biological database connectors follow the same process; unknown facts remain null.

## Discovery, limitations, and next phase

Discovery filters task, endpoint, organism, target, target class, molecule type, local/API execution, deployment profile, validation, licence, activation, and active-only state. There is no universal execution adapter, automatic download, seed import, or full frontend browser in P1A. Authorization remains the deployment's existing responsibility; this change adds no bypass. No training, recalibration, threshold, domain, uncertainty, ranking, report-scoring, or prediction behavior changes were made.

BETA-P1B adds the reviewed existing-engine import and registry user interface. M2 internal-model research remains separate until complete hash-verified governance evidence exists.

BETA-P1B is implemented in `docs/beta_p1b_existing_engine_migration.md` and `docs/beta_p1b_registry_ui.md`; it links to rather than replaces legacy governance.
