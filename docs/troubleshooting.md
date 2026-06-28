# Troubleshooting

DrugScreen360 is a local research-use computational decision-support app. Troubleshooting steps below are for local development and demo use only.

## Backend Not Running

Start the backend and frontend together:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
.\scripts\start_all.ps1
```

Backend health should be available at:

```text
http://127.0.0.1:8010/api/health
```

## Frontend Not Opening

Open:

```text
http://127.0.0.1:5173
```

If it does not load, start only the frontend:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
.\scripts\start_frontend.ps1
```

## Port Already in Use

Stop old local processes:

```powershell
taskkill /F /IM node.exe
taskkill /F /IM python.exe
```

Then restart:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
.\scripts\start_all.ps1
```

## Missing Active Model

Use ADMET Model Studio:

1. Upload or select a curated ADMET dataset.
2. Train a local model.
3. Validate the model artifact.
4. Activate the valid model.
5. Refresh active model status.

If no compatible model is active, reports should honestly say trained-model evidence is unavailable.

## `synthetic_model_1` Appears

If `synthetic_model_1` appears as the active model and the artifact directory is missing, it is stale and should not be treated as valid evidence. Reactivate a valid trained local model from ADMET Model Studio.

## External Validation Not Available

External validation/calibration requires an independent labelled validation dataset. Run the external validation step in ADMET Model Studio, then rerun the Disease-to-Lead report.

## Report Missing Model Evidence

Check:

- Active model status is `available`.
- The active model supports the report task, such as `toxicity_concern`.
- The artifact directory exists and validates.
- The Disease-to-Lead report was regenerated after activation.

## Report Missing External Validation Evidence

Check:

- A validation run exists for the active model.
- The validation run completed.
- The report was regenerated after validation.

## Failed Frontend Build

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360\frontend"
npm install
npm run build
```

## Failed Backend Tests

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360\backend"
.\.venv312\Scripts\Activate.ps1
python -m pytest
```

## Untracked Local Files

Check:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
git status --short
```

Do not commit generated reports, exports, databases, trained model artifacts, `.env` files, `node_modules`, or `frontend/dist`.

## Windows Paths With Spaces

Always quote paths:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
```

