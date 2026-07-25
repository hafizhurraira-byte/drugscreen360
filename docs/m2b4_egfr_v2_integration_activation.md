# M2B-4 EGFR v2 Integration and Controlled Activation

## Model Identity

- Model family: activity
- Scope: target-specific only
- Target: EGFR
- UniProt: P00533
- ChEMBL target: CHEMBL203
- Endpoint: IC50
- Model label: pIC50 regression
- Model ID: `egfr_activity_v2`
- Model artifact hash: `7bd850e41d877a0d3c1c39dde42914ba67fa81142962c7ca7e67d7707f1b6c61`

## Artifact Source and Registration

Frozen source artifact:

`D:\DRUG CONJUGATE\DRUGDESIGN360_REAL_DATA\models\egfr_activity_v2\`

The application registers the artifact by verified reference under:

`backend\models\activity\egfr\egfr_p00533_pic50_rf_morgan_v2\registration_manifest.json`

The binary model is not copied into source control by default. Use:

```powershell
python .\scripts\maintenance\register_egfr_v2_model.py
```

To activate after tests and gate review:

```powershell
python .\scripts\maintenance\register_egfr_v2_model.py --activate
```

## Scientific Performance

ChEMBL TEST, N=921:

- MAE 0.6357
- RMSE 0.8602
- R2 0.5438
- Pearson 0.7412
- Spearman 0.7382

BindingDB final holdout, N=1203:

- MAE 0.6288
- RMSE 0.9094
- R2 0.7077
- Pearson 0.8419
- Spearman 0.8499
- Residual bias 0.0386

## Domain Behavior

- IN_DOMAIN N=1065, RMSE 0.7682, R2 0.7466
- BORDERLINE N=103, RMSE 1.5934, R2 0.2795
- OUT_OF_DOMAIN N=35, RMSE 1.7307, R2 -0.1457

OUT_OF_DOMAIN predictions must be treated as low-reliability research output.

## Uncertainty and Conformal Warning

Uncertainty uses Random Forest tree prediction dispersion.

- Pearson uncertainty vs absolute error: 0.4789
- Spearman uncertainty vs absolute error: 0.5173
- Nominal conformal coverage: 90%
- Observed BindingDB final-holdout coverage: 83.37%

The observed coverage is below nominal and must remain visible in API responses and reports.

## APIs

- `GET /api/activity/models`
- `GET /api/activity/models/egfr/status`
- `GET /api/activity/models/egfr/metrics`
- `POST /api/activity/models/egfr/register`
- `POST /api/activity/models/egfr/activation-gate`
- `POST /api/activity/models/egfr/activate`
- `POST /api/activity/models/egfr/deactivate`
- `GET /api/activity/models/egfr/history`
- `POST /api/activity/predict`
- `POST /api/activity/egfr/predict`
- `POST /api/activity/batch-predict`

Unsupported targets return unavailable state. They are not silently routed to EGFR.

## Ranking, Disease-to-Lead, and Reporting

Candidate ranking consumes EGFR activity predictions only when candidate or project target context resolves to EGFR/P00533/CHEMBL203. The prediction contributes a bounded score bonus and applies penalties for BORDERLINE or OUT_OF_DOMAIN status.

Disease-to-Lead passes target context into ranking, so unrelated targets preserve prior behavior.

Final JSON/PDF/DOCX reports include EGFR activity evidence as MODEL PREDICTION with model hash, pIC50, model-derived IC50_nM, domain status, uncertainty, conformal interval, observed coverage, and limitations.

## Activation Gate and Rollback

The application-side gate verifies artifact hash, target identity, dataset lineage, split lineage, holdout exclusion before freeze, ChEMBL TEST metrics, BindingDB final-holdout metrics, v1 external improvement, frozen domain thresholds, uncertainty metadata, conformal undercoverage disclosure, and external activation recommendation.

Controlled activation writes target-specific activity state for EGFR only. Deactivation returns EGFR activity capability to unavailable state. EGFR v1 is not activated as a normal fallback because it failed external validation.

## Limitations

- EGFR v2 is not a universal activity model.
- Predicted IC50 is not measured IC50.
- Retrospective external validation is not clinical or prospective experimental validation.
- No safety, efficacy, clinical, regulatory, therapeutic, or market-readiness claim is made.
- Selectivity is not inferred.

## Next Step

After controlled activation, run a Disease-to-Lead EGFR smoke test and verify report provenance before considering UI polish or broader target-specific activity model work.
