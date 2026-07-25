# M2D-2 External Validation Governance Integration

## Scope

M2D-2 integrates the frozen M2D-1 external-validation evidence into DRUGDESIGN 360 model governance, prediction responses, readiness status, candidate-ranking explanations, and final reports.

This phase does not retrain, refit, recalibrate, resplit, retune, activate, deactivate, or alter frozen applicability-domain thresholds.

## Evidence Sources

Authoritative ledger:

`D:\DRUG CONJUGATE\DRUGDESIGN360_REAL_DATA\external_validation\m2d1\m2d1_master_results.json`

Protocol SHA256:

`cfaa5070cf08bcec98519545a5e16989cb670a7da60a2f8d14eb04ce485e586f`

Imported endpoint evidence:

| Endpoint | External Cohort | N | Decision |
| --- | --- | ---: | --- |
| BBBP | B3DB classification | 6146 | EXTERNAL_VALIDATION_SUPPORTS_ACTIVE |
| ESOL | AqSolDB | 8882 | ACTIVE_WITH_STRONGER_WARNING |
| hERG | PubChem AID 588834 | 4171 | RECALIBRATION_RECOMMENDED |

ClinTox was not externally validated in M2D-1 and remains inactive / NOT_ELIGIBLE.

## Integrity Verification

The maintenance importer verifies:

- M2D-1 protocol hash
- endpoint support
- frozen model hash
- external cohort hash
- required metrics
- final evidence decision

The import fails closed on mismatches and is idempotent through a stable evidence hash.

## Database Integration

External evidence is stored in `admet_endpoint_external_validation_evidence` as append-only governance evidence. It includes model identity, model hash, external cohort hash, protocol hash, metrics, domain metrics, calibration summary, evidence decision, activation recommendation, limitations, evidence source, and `imported_by`.

Activation state is not modified by evidence import.

## Endpoint Decisions

BBBP remains ACTIVE. M2D-1 supports continued research use, but BBBP is still a benchmark classifier and not proof of human CNS exposure.

ESOL remains ACTIVE with stronger warnings. The nominal 90% validation-derived interval achieved only 61.47% external coverage, so interval bounds are approximate research uncertainty, not reliable 90% guarantees.

hERG remains ACTIVE with recalibration recommended. Discrimination remained useful, but external ECE was 0.2665, so raw probabilities are not reliable absolute risk probabilities.

ClinTox remains unavailable for production prediction because the activation gate failed.

## Prediction Responses

Active endpoint predictions now include a bounded `external_validation` block:

- `available`
- `evidence_decision`
- `dataset_id`
- `cohort_size`
- `independence_status`
- `key_metrics`
- `calibration_summary`
- `domain_summary`
- `limitations`
- `evidence_timestamp`

Warning severities are:

- BBBP: `CAUTION`
- ESOL: `STRONG_WARNING`
- hERG: `STRONG_WARNING`
- ClinTox: `UNAVAILABLE`

## Ranking And Disease-To-Lead

Candidate ranking consumes the same endpoint prediction contract and adds the external evidence decision and warning severity into score components. Existing weights and frozen predictions are unchanged.

Disease-to-Lead carries endpoint warnings and the external-validation block through `admet_model_predictions` into generated evidence packages and reports.

## Reporting

Final reports now include endpoint external-validation governance evidence in the External Validation section and candidate-level model-evidence rows. Reports distinguish model predictions from measured evidence and keep internal held-out validation separate from external validation.

## Frontend And Readiness

The System Readiness panel shows externally imported ADMET endpoints, endpoint decisions, cohort size, and warning text. No clinical, regulatory, diagnostic, therapeutic, or guaranteed safety claims are introduced.

## Import Process

Dry-run validation:

```powershell
python .\scripts\maintenance\import_m2d1_external_validation.py --ledger "D:\DRUG CONJUGATE\DRUGDESIGN360_REAL_DATA\external_validation\m2d1\m2d1_master_results.json"
```

Apply local governance import:

```powershell
python .\scripts\maintenance\import_m2d1_external_validation.py --ledger "D:\DRUG CONJUGATE\DRUGDESIGN360_REAL_DATA\external_validation\m2d1\m2d1_master_results.json" --apply --imported-by m2d2_local_import
```

The script does not change activation states.

## Scientific Limitations

External validation is not clinical validation. Predictions remain computational decision-support. BBBP, ESOL, and hERG evidence is endpoint-specific and dataset-dependent. Out-of-domain predictions require stronger caution. ClinTox remains rejected/unavailable until a future model passes a defensible activation gate.

## Recommended Next Phase

M2D-3 should review hERG recalibration options and ESOL interval calibration using training/validation-only procedures, with fresh governance records and no silent threshold changes.
