# ADMET External Validation & Calibration V0.18

## Purpose

Use this module to evaluate an active local ADMET model on an independent labelled validation dataset. It compares real uploaded labels against real model predictions and reports dataset-dependent metrics and calibration.

## Training Metrics vs External Validation

Training/test metrics come from the model-building split. External validation uses a separate uploaded labelled dataset. If the validation set overlaps the training set, treat the result as internal validation, not independent evidence.

## Required Validation File Columns

CSV, TSV, or TXT files should include:

- `smiles`
- a label column such as `toxicity_concern`
- optional `compound_name`

Example:

```csv
compound_name,smiles,toxicity_concern
Example A,CCO,0
Example B,CCN,1
```

## Run From ADMET Model Studio

1. Activate a trained local model.
2. Open **ADMET Model Studio**.
3. In **Step 9 - External Validation & Calibration**, upload a labelled validation file.
4. Confirm SMILES and label column names.
5. Run external validation.
6. Review metrics, confusion matrix, calibration bins, warnings, and independence status.
7. Rerun Disease-to-Lead to include validation evidence in the final report.

## Metrics

Binary classification reports accuracy, balanced accuracy, precision, recall, specificity, F1, ROC-AUC when available, average precision when available, and confusion matrix counts.

ROC-AUC and average precision are unavailable when the validation labels contain only one class.

## Calibration

When prediction probabilities are available, DrugScreen360 reports Brier score, expected calibration error, max calibration error, and calibration bins. Calibration is dataset-dependent and does not prove general model reliability.

## Possible Overlap

DrugScreen360 warns when validation data appears to overlap with training data by dataset ID, name, or canonical SMILES. Overlapping validation can still be useful for debugging, but it is not independent external validation.

## Report Integration

Disease-to-Lead final reports include the latest validation run for the active model, including metrics, calibration status, independence warnings, and limitations.

## Limitations

- No labels are invented.
- No predictions are faked.
- External validation applies only to the uploaded dataset.
- Computational decision-support only.
- Qualified scientific review and laboratory validation remain required.
