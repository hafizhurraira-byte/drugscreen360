# ADMET Model Studio v0.17

## Purpose

ADMET Model Studio gives non-technical users a guided path to upload a labelled ADMET dataset, train an experimental local model, validate the saved artifact, activate it, test a prediction, and then run Disease-to-Lead reporting without using PowerShell or Swagger.

This is computational decision-support only. It does not prove safety, efficacy, clinical success, regulatory approval, or market readiness.

## Workflow

1. Open **Advanced Tools -> ADMET Model Studio**.
2. Upload a CSV/TSV/TXT/SDF dataset or select an existing curated dataset.
3. Review the dataset validation summary.
4. Train a local baseline model.
5. Review metrics and the model card.
6. Validate the discovered model artifact.
7. Activate the valid model.
8. Test the active model with a SMILES string.
9. Run Disease-to-Lead and generate the final report.

## ClinTox Example Fields

Use the ClinTox-derived toxicity dataset with:

- Dataset name: `ClinTox toxicity concern full dataset`
- Task name: `toxicity_concern`
- SMILES column: `smiles`
- Label column: `toxicity_concern`
- Compound name column: leave empty if not present
- Notes: `Authentic ClinTox CT_TOX mapped to toxicity_concern for trained local ADMET/toxicity model.`

## Training Defaults

- Task type: `binary_classification`
- Model type: `random_forest`
- Test size: `0.2`
- Random state: `42`

The backend trains only from valid curated molecules with labels. It does not invent labels or predictions.

## Activate and Verify

After training, validate the model. Activate only if validation succeeds. The Active Model Status panel should show:

- `status`
- `model_id`
- `model_name`
- `version`
- `task_name`
- `task_type`
- `model_type`
- `artifact_dir`

External validation and calibration may remain pending in v0.17 and must be treated as missing evidence.

## Disease-to-Lead Report

After activation, run Disease-to-Lead with an example such as:

- Disease: `non-small cell lung cancer`
- Target: `EGFR`
- Known compound: `Erlotinib`

The active trained model appears in the final report only when compatible evidence can be produced for the candidate compound.

## Limitations

- Local models are experimental baseline models.
- Performance depends on uploaded dataset quality, labels, assay definitions, and class balance.
- External validation and calibration remain required before scientific use.
- Applicability-domain and uncertainty checks must be reviewed.
- Reports are computational decision-support and require qualified scientific review.
