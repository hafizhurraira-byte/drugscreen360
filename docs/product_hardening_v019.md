# Product Hardening, Demo Mode, and Readiness V0.19

## Purpose

V0.19 makes DrugScreen360 easier to demonstrate and safer to operate as a research-use computational decision-support platform.

It does not add clinical, diagnostic, regulatory, therapeutic, safety, efficacy, or market-readiness claims.

## Standard Demo Workflow

Open **Disease-to-Lead Workflow** and click **Load NSCLC / EGFR / Erlotinib Demo**.

The demo pre-fills:

- Disease: `non-small cell lung cancer`
- Target: `EGFR`
- Known compound: `Erlotinib`
- Candidate limit: `5`
- Similarity limit: `5`
- Analysis depth: `quick`

Then click **Run Complete Disease-to-Lead Analysis**.

The final report can include active trained-model evidence, external validation/calibration evidence, and warnings when evidence is missing or limited.

## System Readiness

Open **System** and refresh health.

The **System Readiness** panel reports:

- app version
- active trained ADMET model status
- active model ID/name/task/version
- artifact status
- latest external validation status
- calibration status
- demo readiness
- next recommended actions

Statuses are intentionally simple: `Ready`, `Partially Ready`, `Not Ready`, and `Action Needed`.

## Stale Active Model Handling

If the active model points to a missing artifact directory, readiness shows an action-needed state and recommends reactivating a valid trained model.

This prevents stale entries such as `synthetic_model_1` from being treated as valid model evidence.

## Reactivating a Model

Use **ADMET Model Studio**:

1. Refresh discovered trained models.
2. Select a valid trained model.
3. Validate it.
4. Activate it.
5. Refresh active model status.

## External Validation

Run external validation/calibration from **ADMET Model Studio Step 9** using a real labelled validation dataset.

Warnings are expected when:

- validation sets are small
- validation data overlaps training data
- calibration is poor
- ROC-AUC is unavailable because only one label class is present

## Demo Assets

Local helper scripts and smoke files such as `upload_clintox_dataset.py`, `run_v018_external_validation.py`, and `v018_smoke_external_validation*.csv` are intentionally not committed as product assets in v0.19.

Only curated, small, documented, provenance-clear examples should be promoted into `examples/` in a future PR.

## Limitations

DrugScreen360 remains computational decision-support only. External validation and calibration are dataset-dependent. Qualified scientific review and experimental validation remain required.
