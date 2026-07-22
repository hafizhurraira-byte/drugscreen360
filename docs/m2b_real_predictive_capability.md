# M2B Real Predictive Capability Activation

Status: M2B implementation branch.

DrugScreen360 remains a research-use computational decision-support platform. M2B does not add clinical validation, treatment recommendation, regulatory approval, experimental efficacy claims, docking, molecular dynamics, generative chemistry, or precision medicine.

## 1. Executive Summary

M2B connects the existing real local ADMET training/prediction path to stricter predictive governance:

- trained ADMET artifacts now persist split lineage and dataset hashes when generated through the training service
- activation now passes through a family-specific activation gate
- activation history records previous and new active models with rollback target metadata
- prediction responses expose model/version/dataset/domain/confidence provenance
- lightweight local job endpoints wrap existing training and external validation functions
- activity and selectivity remain unavailable unless real bounded datasets are supplied

No new real endpoint model is fabricated in this branch.

## 2. Dataset Inventory

| Path | Git state | Classification | Endpoint(s) | Rows | Training support | External validation support | Notes |
|---|---:|---|---|---:|---|---|---|
| `backend/app/demo_data/demo_admet_dataset.csv` | tracked | TEST_FIXTURE / SYNTHETIC demo | `demo_toxicity` | 5 | No | No | Demo-only labels; not scientific evidence. |
| `backend/app/demo_data/demo_candidates.json` | tracked | TEST_FIXTURE / SYNTHETIC demo | demo candidates | small | No | No | Software demonstration only. |
| `backend/app/demo_data/demo_experimental_results.csv` | tracked | TEST_FIXTURE / SYNTHETIC demo | demo feedback | small | No | No | Not real experimental evidence. |
| `data/training/clintox.csv` | untracked | REAL_PUBLIC / UNCLEAR provenance in repo | `CT_TOX`, `FDA_APPROVED` | 1484 | Yes, after import/curation | Yes only if split into independent validation subset or separate source | Appears ClinTox-derived; provenance/license should be documented before commit. |
| `data/training/drugscreen360_clintox_full_cttox.csv` | untracked | REAL_PUBLIC / CURATED local derivative | `toxicity_concern`, `CT_TOX`, `FDA_APPROVED` | 1484 | Yes, after import/curation | Not independent if derived from same source as training | Useful local training asset; not committed in M2B. |
| `backend/models/admet/trained/dataset_1365_*` | untracked | CURATED model artifact | `toxicity_concern` | from local DB/model card | Discoverable | Requires validation run records | Older artifact lacks M2B split hashes; not newly activation-eligible until regenerated. |
| `backend/models/admet/trained/dataset_1479_*` | untracked | CURATED model artifact | `toxicity_concern` | from local DB/model card | Discoverable | Requires validation run records | Older artifact lacks M2B split hashes; not newly activation-eligible until regenerated. |

No large raw datasets were committed or moved.

## 3. Real Endpoints Supported

The only real locally trainable endpoint currently supported by known local assets is:

- canonical endpoint: `toxicity_concern`
- category: toxicity
- task type: binary classification
- label definition: ClinTox-derived toxicity concern where imported/curated by the user
- units: not applicable
- feature schema: RDKit descriptors used by the existing ADMET training service

Other M2A endpoint catalog entries remain unavailable unless a real endpoint-specific dataset is imported and trained.

## 4. Models Trained

M2B does not train or commit new production models automatically.

Existing training remains user-driven through ADMET Model Studio or API:

- `POST /api/admet-training/train`
- `POST /api/admet-training/train/job`

Generated artifacts include:

- `model.joblib`
- `feature_schema.json`
- `split_manifest.json`
- `model_manifest.json`
- `model_card.json`
- `training_summary.json`

## 5. Split Policies

The current training service uses deterministic `train_test_split` with the provided random seed. M2B persists:

- train record IDs
- test record IDs
- dataset version hash
- split hash
- split policy note

Scaffold-aware splitting is available as a diagnostic through M2A split-integrity checks, but is not forced for every endpoint.

## 6. Leakage Safeguards

M2B records split hashes and dataset hashes for newly trained models. M2A split checks can detect:

- invalid partition names
- invalid SMILES
- duplicate molecules
- canonical SMILES overlap
- scaffold overlap

Older artifacts without split manifests are discoverable but fail strict activation eligibility.

## 7. Validation Results

Training metrics remain held-out internal metrics only. Training metrics are not external validation.

External validation remains available through:

- `POST /api/admet-validation/external/run`
- `POST /api/admet-validation/external/run/job`

## 8. External Validation

The existing validation service computes classification metrics and calibration where probabilities exist. M2B does not invent external validation runs. If no independent validation dataset is uploaded, reports must continue to show validation as unavailable or pending.

## 9. Calibration

Calibration evidence is dataset-dependent and comes from the external validation service. M2B exposes calibration status in prediction/report provenance where available, but does not fabricate calibrated probabilities.

## 10. Applicability Domain

Live predictions continue to call the existing applicability-domain service. M2B exposes domain method and nearest-similarity fields in trained-model prediction responses when available.

## 11. Uncertainty Methods

Classification confidence is based on real model probability only when the model exposes `predict_proba`. Regression confidence remains unavailable unless a defensible uncertainty method is implemented later.

Out-of-domain predictions are downgraded through warnings and uncertainty labels.

## 12. Activation Policies

Activation now requires:

- valid model artifact
- valid feature schema
- dataset version hash
- split hash
- required metrics for the model family
- reproducibility metadata
- applicability-domain availability

Current ADMET policies:

- `admet_toxicity_activation_v1`: requires balanced accuracy, precision, recall, F1
- `admet_regression_activation_v1`: requires MAE

No model becomes active simply because training succeeded.

## 13. Active Models

Active models are still stored in `admet_active_model`. M2B adds append-only activation history in `admet_model_activation_history`.

Rollback endpoint:

- `POST /api/admet-training/models/rollback`

Rollback uses the most recent recorded rollback target. It does not fabricate or repair missing artifacts.

## 14. Activity Model Status

Activity model training remains unavailable unless a real target-specific dataset with assay provenance, units, target identity, and quality filters is supplied. No universal activity model is implemented.

## 15. Selectivity Status

Selectivity modeling remains unavailable without real on-target/off-target panel evidence. No generic selectivity predictions are generated.

## 16. Background Job Architecture

M2B adds a lightweight local job runner backed by SQLite and a small thread pool.

Job states:

```text
QUEUED -> RUNNING -> SUCCEEDED / FAILED / CANCELLED
```

Job endpoints:

- `POST /api/admet-training/train/job`
- `GET /api/admet-training/jobs`
- `GET /api/admet-training/jobs/{job_id}`
- `POST /api/admet-training/jobs/{job_id}/cancel`
- `POST /api/admet-validation/external/run/job`
- `GET /api/admet-validation/external/jobs`
- `GET /api/admet-validation/external/jobs/{job_id}`
- `POST /api/admet-validation/external/jobs/{job_id}/cancel`

Cancellation is safe for queued jobs. Running Python/scikit-learn jobs are not force-killed.

## 17. Candidate Ranking Integration

Existing candidate ranking can consume trained-model prediction evidence where available. M2B does not fabricate activity/selectivity dimensions. Missing evidence remains visible.

## 18. Disease-to-Lead Integration

Disease-to-Lead reports continue to use active compatible trained ADMET model evidence when available. If no strict activation-eligible model is active, reports continue with descriptor/rule-based evidence and clear missing-model warnings.

## 19. Reporting Changes

M2A report provenance remains active. M2B prediction responses now expose:

- evidence type
- model version
- dataset version hash
- validation status
- calibration status
- confidence type/value
- uncertainty type/value
- domain method
- nearest similarity when available

## 20. Frontend Changes

ADMET Model Studio includes a short M2B notice explaining:

- split lineage
- activation eligibility
- rollback audit trail
- lightweight training/validation job status
- old artifacts without split manifests need regeneration/revalidation

No frontend redesign was performed.

## 21. Scientific Limitations

- Trained does not mean scientifically valid.
- Active does not mean clinically valid.
- External validation requires a real independent labelled dataset.
- Calibration is dataset-dependent.
- Out-of-domain predictions require caution.
- Rule-based heuristics are not trained model predictions.
- Demo data are not scientific evidence.

## 22. Unsupported Capabilities

Still unsupported:

- docking
- molecular dynamics
- generative chemistry
- lead optimization engine
- target-specific activity model training
- selectivity model training
- precision medicine
- clinical decision support

## 23. Exact Next Milestone

Recommended next milestone:

1. Add scaffold-split option to the ADMET training request.
2. Add activation eligibility preview in ADMET Model Studio.
3. Curate and document one commit-safe real endpoint fixture or external reference manifest.
4. Add target-specific ChEMBL activity dataset assembly with assay-quality filters.
5. Require external validation for promotion beyond local research demos.

