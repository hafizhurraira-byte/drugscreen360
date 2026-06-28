# v0.20 Release Preparation Notes

DrugScreen360 v0.20 is a packaging, documentation, and release-readiness pass. It does not change the v0.19 ADMET prediction logic, Disease-to-Lead scoring logic, external validation calculations, calibration calculations, or report evidence logic.

## Scope

- Update project version to `0.20.0`.
- Improve release-facing documentation for installation, demo use, troubleshooting, and release checks.
- Prepare folders for screenshots and example reports without committing generated private artifacts.
- Keep DrugScreen360 clearly labelled as computational decision-support and research-use-only.

## Preserved Behavior

The following v0.19 behaviors are intentionally preserved:

- Disease-to-Lead workflow.
- Local ADMET model training and activation.
- ADMET Model Studio.
- External validation and calibration review.
- System Readiness endpoint and panel.
- Stale `synthetic_model_1` detection.
- NSCLC / EGFR / Erlotinib demo prefill.
- Final JSON/PDF/DOCX report generation.

## Local Helper Files

Earlier local workspaces contained helper or data files such as:

- `backend/show_dataset_routes.py`
- `backend/show_dataset_upload_schema.py`
- `backend/show_training_api_schema.py`
- `backend/show_training_body_schema.py`
- `data/`
- `run_v018_external_validation.py`
- `upload_clintox_dataset.py`
- `v018_smoke_external_validation.csv`
- `v018_smoke_external_validation_12.csv`

These files are intentionally not included in this release-prep branch unless their provenance, size, and long-term usefulness are reviewed. Large datasets and one-off introspection scripts should stay outside the release package.

## Demo Asset Policy

Demo assets may be committed only when they are small, clearly documented, and safe for public review. Toy validation files must be labelled as smoke-test data only and must not be used for real model performance claims.

## Release Gates

Before tagging v0.20:

- Confirm `VERSION` is `0.20.0`.
- Run `.\scripts\run_tests.ps1`.
- Check the System Readiness panel in the browser.
- Run the NSCLC / EGFR / Erlotinib demo.
- Generate a final report and confirm the research-use-only notice is visible.
- Confirm no generated reports, databases, exports, trained model artifacts, `.env` files, `node_modules`, or `dist` files are staged.

