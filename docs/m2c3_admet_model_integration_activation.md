# M2C-3 ADMET Model Integration and Controlled Activation

## Scope

M2C-3 integrates frozen M2C-2 multi-endpoint ADMET artifacts into DRUGDESIGN 360 by verified local reference. It does not retrain, refit, recalibrate, resplit, or modify any frozen model artifact.

DrugScreen360 remains computational decision-support only. These models do not prove safety, efficacy, clinical validity, regulatory readiness, or experimental outcomes.

## Model Identities

| Endpoint | Model ID | Task | Label | Gate State |
|---|---|---|---|---|
| BBBP | `bbbp_v1` | binary classification | `bbb_penetrant` | activation eligible with low-specificity warning |
| ESOL | `esol_v1` | regression | `logS` | activation eligible with interval undercoverage warning |
| hERG | `herg_v1` | binary classification | `herg_inhibitor` | activation eligible with small-test and calibration warnings |
| ClinTox CT_TOX | `clintox_cttox_v1` | binary classification | `toxicity_concern` | not eligible |

## Artifact Registration Strategy

The application stores small registration manifests under `backend/models/admet/<endpoint>/<model_id>/registration_manifest.json`. These manifests reference external frozen artifacts and verify SHA256 hashes before registration. Large `model.joblib` files and raw/curated datasets are not copied into Git.

Use:

```powershell
python scripts\maintenance\register_m2c3_admet_models.py --artifact-root "D:\DRUG CONJUGATE\DRUGDESIGN360_REAL_DATA\models\admet" --endpoint all --overwrite
```

Add `--activate` only after local tests and smoke checks pass. ClinTox is never activated by the script.

## Frozen Hashes

| Endpoint | Expected `model.joblib` SHA256 |
|---|---|
| BBBP | `e08d91c7febb4b8cc82ca71c7b46ff8afccb6d12debd217f9b563c13bee8500b` |
| ESOL | `c91ac8c3c5cec08dd1cb4417c969e18cdb1ef0148d599c4badbc72db093fec10` |
| hERG | `0e0d07a5347c6027c12e2b86946588eb3c66330a80df499fda7a92d3c6721081` |
| ClinTox CT_TOX | `524e68e123b6478a1e50ba8df48625beebf7007138f8b8401a2105d895cdb1c7` |

## Dataset and Split Lineage

Each artifact must include `training_metadata.json`, `split_reference.json`, `feature_schema.json`, `metrics.json`, `domain_reference.npz`, `uncertainty_metadata.json`, `calibration_metadata.json`, and `freeze_record.json`. Registration fails closed when required files, dataset hashes, split hashes, frozen split metadata, TEST metrics, or model hashes are missing.

## Application-Side Gates

The application re-evaluates gates before activation. Common checks include artifact integrity, dataset lineage, split lineage, frozen split enforcement, TEST metrics, baseline comparison, applicability-domain metadata, and endpoint-specific scientific warnings.

## Endpoint Warnings

BBBP: TEST specificity was 0.3922. A positive prediction is benchmark BBBP-class membership, not proof of human CNS exposure.

ESOL: nominal 90% conformal intervals achieved 86.17% TEST coverage. Predicted logS and derived molar solubility are model-derived, not measured.

hERG: TEST N was 65 and TEST ECE was 0.1385. A low predicted hERG concern is not cardiac safety clearance.

ClinTox: TEST recall and F1 were both 0. This is a hard blocker. The model is discoverable for transparency, unavailable for public prediction, and excluded from ranking.

## Prediction APIs

- `GET /api/admet/models`
- `GET /api/admet/models/{endpoint}/status`
- `GET /api/admet/models/{endpoint}/metrics`
- `GET /api/admet/models/{endpoint}/history`
- `POST /api/admet/models/register`
- `POST /api/admet/models/{endpoint}/activation-gate`
- `POST /api/admet/models/{endpoint}/activate`
- `POST /api/admet/models/{endpoint}/deactivate`
- `POST /api/admet/predict`
- `POST /api/admet/batch-predict`

Prediction responses include endpoint, model identity, artifact hash, dataset and split hashes, activation state, nearest training similarity, applicability-domain status, uncertainty, calibration metadata, TEST metrics, warnings, limitations, and `MODEL_PREDICTION` evidence type.

## Applicability Domain

Predictions use Morgan radius 2, 2048-bit fingerprints and endpoint-specific frozen thresholds. `BORDERLINE` and `OUT_OF_DOMAIN` results are warning states and should reduce confidence in ranking and reporting.

## Candidate Ranking and Disease-to-Lead

Only active BBBP, ESOL, and hERG models can influence ranking. BBBP is context-aware and should not be globally rewarded. ESOL contributes bounded developability evidence. hERG contributes a risk penalty. ClinTox contributes no model score and remains explicit missing/rejected evidence.

Disease-to-Lead consumes the unified ADMET model adapter alongside existing rule-based and trained local ADMET evidence. Partial endpoint failures are preserved instead of crashing the workflow.

## Reports and Frontend

Final reports include endpoint-level model evidence and clearly distinguish `MODEL PREDICTION`, `RULE-BASED HEURISTIC`, `DATABASE EVIDENCE`, `EXPERIMENTAL OBSERVATION`, and `UNAVAILABLE/REJECTED MODEL`.

The System Readiness panel displays endpoint-specific ADMET status, active endpoint count, gate state, and ClinTox rejection.

## Rollback and Deactivation

Endpoint activations are independent. If no prior eligible model exists, deactivation returns that endpoint to unavailable state. ClinTox is not a rollback candidate.

## Limitations

The current models are research-grade baseline computational models. They are not clinical toxicity, pharmacokinetic, solubility, or cardiotoxicity assays. External validation beyond M2C-2 artifacts remains endpoint- and dataset-dependent.

## Next Recommended Phase

M2C-4 should persist compact training fingerprints in each artifact to avoid rebuilding applicability-domain references from local curated CSVs during high-throughput prediction.
