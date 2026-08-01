# Targeted BETA-P3 OpenADMET scientific review

## Identity and generation

The exact repository commit reviewed is `6fb7782db474a9c9198d4ace3a5c6b6a6abb304b` dated 2026-06-18. The model card calls the current model v2 and says it uses enhanced ChEMBL curation that removes censored values and changes outlier filtering. Commit `4750ead01f0a8314d565f347013da74babf3d5c5` is titled `Update model to V2`.

However, both the exact frozen `anvil_recipe.yaml` and `recipe_components/metadata.yaml` declare `version: v1` and `build_number: 0`. This unresolved model-generation mismatch prevents a defensible registry version and artifact/recipe parity claim.

## Training and validation evidence

- Training resource: a ChEMBL 35-derived curated permeability/LogD/PPB multitask table.
- Five targets: `logD`, `caco2_atob_LogPapp`, `caco2_btoa_LogPapp`, `mppb_LogUnbound`, `hppb_LogUnbound`.
- Architecture: five-task ChemProp model initialized from CheMeleon.
- Recipe split: shuffle splitter with `train_size: 1.0`, `val_size: 0.0`, and `test_size: 0.0` for final fitting.
- Evaluation recipe: repeated five-fold cross-validation is declared.
- Endpoint sample counts: not stated in the model card/recipe and not derived because training tables were not downloaded after the licence failure.
- Exact v2 metrics: no endpoint-level frozen validation report was established from the reviewed card/recipe.
- External comparison: the model card links an ExpansionRx comparison; this was not treated as broad external validation or a licence substitute.
- Scientific status: `DOCUMENTED_BASELINE`, not externally or production validated.

## Five endpoint definitions

All endpoints remain unapproved because the licence and generation gates fail.

### `logd`

- Upstream column: `logD`
- Display name: LogD
- Category: distribution / physicochemical
- Species: not applicable
- Type: regression
- Raw unit: dimensionless log-ratio as upstream-labelled
- Transformation: none
- Derived values: none
- Experimental meaning/training label: distribution coefficient from the curated upstream table; pH is not stated
- Domain: `DOMAIN_UNKNOWN`
- Uncertainty: `UNKNOWN`
- Limitation: experimental pH and conditions must not be assumed
- Approval: blocked

### `caco2_papp_atob`

- Upstream column: `caco2_atob_LogPapp`
- Display name: Caco-2 permeability Papp A→B
- Category: absorption
- Species: human cell-line assay
- Type: regression
- Raw unit: `log10(cm/s)`
- Transformation: preserve raw; verified derived value is `10^raw × 10^6`
- Derived unit: `10^-6 cm/s`
- Experimental meaning: apparent permeability from apical to basolateral direction
- Domain: `DOMAIN_UNKNOWN`
- Uncertainty: `UNKNOWN`
- Limitation: does not establish human intestinal absorption or bioavailability
- Approval: blocked

### `caco2_papp_btoa`

- Upstream column: `caco2_btoa_LogPapp`
- Display name: Caco-2 permeability Papp B→A
- Category: absorption
- Species: human cell-line assay
- Type: regression
- Raw unit: `log10(cm/s)`
- Transformation: preserve raw; verified derived value is `10^raw × 10^6`
- Derived unit: `10^-6 cm/s`
- Experimental meaning: apparent permeability from basolateral to apical direction
- Domain: `DOMAIN_UNKNOWN`
- Uncertainty: `UNKNOWN`
- Limitation: no efflux ratio or absorption claim is authorized
- Approval: blocked

### `human_ppb`

- Upstream column: `hppb_LogUnbound`
- Display name: Human plasma protein binding
- Category: distribution
- Species: human
- Type: regression
- Raw unit: `log10(% unbound)`
- Transformation: preserve raw; `% unbound = 10^raw`; `% bound = 100 - % unbound`
- Derived units: percent
- Experimental meaning: plasma unbound/bound fraction label
- Domain: `DOMAIN_UNKNOWN`
- Uncertainty: `UNKNOWN`
- Limitation: does not establish in-vivo free-drug exposure
- Approval: blocked

### `mouse_ppb`

- Upstream column: `mppb_LogUnbound`
- Display name: Mouse plasma protein binding
- Category: distribution
- Species: mouse
- Type: regression
- Raw unit: `log10(% unbound)`
- Transformation: preserve raw; `% unbound = 10^raw`; `% bound = 100 - % unbound`
- Derived units: percent
- Experimental meaning: mouse plasma unbound/bound fraction label
- Domain: `DOMAIN_UNKNOWN`
- Uncertainty: `UNKNOWN`
- Limitation: distinct from human PPB and not interchangeable
- Approval: blocked

## Claims deliberately not made

No experimental accuracy, external validation, clinical utility, absorption, bioavailability, in-vivo exposure, calibrated uncertainty, applicability-domain coverage, or safety claim is made.

