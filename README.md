# DrugScreen360

DrugScreen360 is an MVP web platform for single-molecule drug lookup and rule-based screening report generation.

It uses PubChem for compound identity, RDKit for molecular descriptors and 2D structure images, SQLite for screening history, ReportLab for PDF export, and python-docx for DOCX export.

Drug Finder V1 adds ChEMBL-based target search, active candidate retrieval, transparent rule-based candidate ranking, and batch candidate screening.

ADMET/Toxicity Engine V1 adds transparent descriptor and structural-alert rules for early screening. It is not a validated AI, ML, ADMET, or toxicology prediction model.

Disease Finder V1 adds Open Targets disease search and ranked therapeutic target prioritization, then connects selected targets into the existing ChEMBL molecule finder and screening workflow.

Evidence Quality Engine V1 adds transparent ChEMBL bioactivity evidence scoring for target-linked candidate molecules. It helps flag whether a compound is supported by strong, moderate, weak, or uncertain public activity metadata.

## Important Disclaimer

This report is computational and decision-support only. It does not prove safety, efficacy, clinical success, regulatory approval, or market readiness.

## Current MVP Features

- Input one compound by drug name, PubChem CID, SMILES, InChI, or InChIKey.
- Resolve compound identity from PubChem.
- Generate an RDKit 2D molecule structure image.
- Calculate RDKit physicochemical descriptors.
- Evaluate Lipinski Rule of 5 and Veber Rule.
- Generate basic drug-likeness and developability risk.
- Generate a transparent rule-based experimental test planner.
- Save screening history in SQLite.
- Reload previous screening reports from history.
- Export JSON, PDF, and DOCX reports.
- Clearly label ADMET and toxicity sections as placeholder / future modules.
- Search ChEMBL targets by keyword, such as `EGFR` or `COX2`.
- Retrieve and rank active ChEMBL molecules for a selected target.
- Batch screen selected candidates and export comparison results as JSON or CSV.
- Run ADMET/Toxicity V1 rule-based assessment for single molecules and batch candidates.
- Search diseases through Open Targets, rank associated targets, and hand selected targets into ChEMBL candidate discovery.
- Score target-linked candidates with Evidence Quality Engine V1.
- Include evidence score, potency quality, and final candidate priority in Drug Finder and Disease Finder comparisons.

## Project Structure

```text
drugscreen360/
  backend/
    app/
      main.py
      constants.py
      database.py
      models/
      routers/
      services/
    tests/
    requirements.txt
    pytest.ini
  frontend/
    src/
    package.json
  scripts/
    start_backend.ps1
    start_frontend.ps1
    start_all.ps1
    run_tests.ps1
    backup_local_data.ps1
  docker-compose.yml
  VERSION
  README.md
```

## How to Run DrugScreen360 Locally

### Option A: Manual PowerShell

Backend:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360\backend"
.\.venv312\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Frontend:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360\frontend"
npm run dev -- --host 127.0.0.1 --port 5173
```

### Option B: One-Command Scripts

Run all checks:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
.\scripts\run_tests.ps1
```

Start backend and frontend in separate PowerShell windows:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
.\scripts\start_all.ps1
```

Start only backend:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
.\scripts\start_backend.ps1
```

Start only frontend:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
.\scripts\start_frontend.ps1
```

Backup local data:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
.\scripts\backup_local_data.ps1
```

### Option C: Docker Compose

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
docker compose up --build
```

Stop Docker containers:

```powershell
docker compose down
```

Docker runs the backend on `http://127.0.0.1:8010` and the frontend on `http://127.0.0.1:5173`. SQLite data is stored in a Docker volume.

### Environment Files

Copy the examples only if you need local overrides:

```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

Do not put real API keys into source control.

### Troubleshooting

- Backend port already in use: change `--port 8010` or stop the process using that port.
- Frontend cannot fetch backend: confirm `frontend\.env` has `VITE_API_BASE_URL=http://127.0.0.1:8010`.
- Missing `.env`: local defaults work without `.env`; use `.env.example` only for overrides.
- Python environment not activated: run `.\.venv312\Scripts\Activate.ps1` before backend commands.
- `ModuleNotFoundError: fastapi`: install dependencies inside `.venv312` with `pip install -r requirements.txt`.
- `npm` package errors: run `npm install` inside `frontend`.
- RDKit install issue: use Python 3.12 and install from `backend\requirements.txt`.
- Database/cache reset: stop the app and delete local `*.sqlite3` files or use the System tab `Clear Cache` button.

## Installation

Open Windows PowerShell:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360"
```

### Backend

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360\backend"
py -3.12 -m venv .venv312
.\.venv312\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest
```

Run the backend:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Backend:

```text
http://127.0.0.1:8010
```

API docs:

```text
http://127.0.0.1:8010/docs
```

Use Python 3.12 for this project. Do not run the backend with Python 3.14. If you see `ModuleNotFoundError: No module named 'fastapi'`, the usual cause is that PowerShell is using the system Python instead of the `.venv312` environment.

### Frontend

Open another PowerShell window:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360\frontend"
npm install
npm run dev
```

Frontend:

```text
http://127.0.0.1:5173
```

The frontend reads the backend URL from `frontend/.env`:

```text
VITE_API_BASE_URL=http://127.0.0.1:8010
```

## API Endpoints

```text
GET    /
GET    /api/health
POST   /api/screen
GET    /api/screening/history
GET    /api/screening/history/{id}
DELETE /api/screening/history/{id}
GET    /api/report/{screening_id}/pdf
GET    /api/report/{screening_id}/docx
GET    /api/finder/targets?query=EGFR
GET    /api/finder/target/{target_chembl_id}/candidates
POST   /api/finder/screen-candidates
POST   /api/similarity/search
POST   /api/similarity/screen-selected
GET    /api/examples
GET    /api/examples/workflows
GET    /api/demo/egfr-candidates
GET    /api/demo/breast-cancer-targets
GET    /api/demo/similarity/aspirin
GET    /api/demo/similarity/caffeine
GET    /api/benchmark/compounds
POST   /api/benchmark/run
GET    /api/benchmark/runs
GET    /api/benchmark/runs/{id}
GET    /api/benchmark/runs/{id}/pdf
GET    /api/benchmark/runs/{id}/docx
GET    /api/benchmark/runs/{id}/json
GET    /api/benchmark/runs/{id}/csv
GET    /api/models/status
POST   /api/models/predict-admet
POST   /api/models/compare
POST   /api/batch-library/parse
POST   /api/batch-library/screen
GET    /api/batch-library/runs
GET    /api/batch-library/runs/{id}
GET    /api/batch-library/runs/{id}/json
GET    /api/batch-library/runs/{id}/csv
GET    /api/batch-library/runs/{id}/pdf
GET    /api/batch-library/runs/{id}/docx
GET    /api/batch-library/examples/example_compounds.csv
GET    /api/batch-library/examples/example_compounds.smi
POST   /api/admet/evaluate
GET    /api/disease-finder/diseases?query=breast%20cancer
GET    /api/disease-finder/disease/{disease_id}/targets
POST   /api/evidence/evaluate-candidate
POST   /api/evidence/evaluate-batch
POST   /api/project-report/create
GET    /api/project-report/{project_report_id}
GET    /api/project-report/{project_report_id}/pdf
GET    /api/project-report/{project_report_id}/docx
GET    /api/project-report/{project_report_id}/json
GET    /api/project-report/{project_report_id}/csv
GET    /api/cache/stats
GET    /api/cache/items
DELETE /api/cache/items/{id}
DELETE /api/cache/clear
POST   /api/cache/refresh
```

## Performance And Local Cache V1

DrugScreen360 now stores successful public API responses in local SQLite cache so repeated PubChem, ChEMBL, and Open Targets workflows are faster and less dependent on repeated live calls.

Cached sources:

- PubChem compound lookup
- ChEMBL target search
- ChEMBL candidate retrieval
- Open Targets disease search
- Open Targets disease-target association retrieval

Default cache TTL values:

- PubChem compound lookup: 30 days
- ChEMBL target search: 7 days
- ChEMBL candidate retrieval: 7 days
- Open Targets disease search: 7 days
- Open Targets disease-target associations: 7 days
- BindingDB support checks, when used: 7 days

API responses include cache metadata where available:

- `data_source`: `live_api` or `cache`
- `cache_hit`: `true` or `false`
- `cached_at`
- `expires_at`

The frontend shows subtle labels such as `Live API`, `Cached`, or `Cached, expires in X days`. The local `System` tab shows backend status, cache totals, source counts, hit counts, cached items, and a clear-cache control.

### Cache Verification

1. Open Drug Finder.
2. Search `EGFR`.
3. Confirm the first search shows `Live API`.
4. Search `EGFR` again.
5. Confirm the second search shows `Cached` or the API response has `cache_hit: true`.

Cache admin examples:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8010/api/cache/stats"
Invoke-RestMethod -Uri "http://127.0.0.1:8010/api/cache/items"
Invoke-RestMethod -Uri "http://127.0.0.1:8010/api/cache/clear" -Method Delete
```

## Example Library And Demo Mode V1

The frontend includes an `Examples` tab for ready-to-run demonstrations:

- Single Molecule examples: Aspirin, Caffeine, Ibuprofen, Metformin, Imatinib, Tamoxifen, Erlotinib, Acetaminophen
- Drug Finder examples: EGFR, ESR1, ERBB2, PIK3CA, COX2, JAK2, BRAF, VEGFA, ROCK2
- Disease Finder examples: breast cancer, lung cancer, Alzheimer disease, idiopathic pulmonary fibrosis, diabetes, colorectal cancer, prostate cancer, rheumatoid arthritis
- Similarity Finder examples: Aspirin, Caffeine, Ibuprofen, Metformin, Imatinib, Erlotinib

Workflow templates are also available:

1. Screen Aspirin
2. Find EGFR Candidates
3. Breast Cancer to Candidate Screening
4. Caffeine Similarity Search

Demo fallback is controlled in the `System` tab with `Use Demo Fallback When Live APIs Fail`. It is enabled by default for the local MVP. When a supported live API workflow fails, the app asks before loading demo data and shows a visible `Demo data` label.

Demo fallback limitations:

- Demo records are for UI demonstration only.
- Demo data is not complete or current.
- Demo data must not be treated as live PubChem, ChEMBL, or Open Targets evidence.
- Demo workflows do not prove safety, efficacy, mechanism, regulatory readiness, or market readiness.

Recommended demo workflow:

1. Open `Examples`.
2. Run Aspirin screening.
3. Open EGFR in Drug Finder.
4. Batch screen two EGFR candidates.
5. Export a project report.
6. Open breast cancer in Disease Finder.
7. Open Caffeine in Similarity Finder.
8. Repeat a search and check cache/demo labels.

The `System` tab includes a local QA checklist. Checklist status is saved in browser `localStorage`, not the backend.

## Validation & Benchmarking V1

Validation & Benchmarking V1 is an internal rule-behavior check for DrugScreen360. It does not clinically or regulatorily validate the platform.

Benchmark groups:

- Common reference drugs: Aspirin, Caffeine, Ibuprofen, Acetaminophen/Paracetamol, Metformin, Warfarin, Imatinib, Erlotinib, Tamoxifen
- Warning compounds: Doxorubicin, Thalidomide, Cisplatin, Diclofenac, Amiodarone, Ketoconazole, Clozapine
- Chemistry stress tests: invalid SMILES, very high MW, very high LogP, high TPSA, nitro aromatic alert, aldehyde alert

Status logic:

- `PASS`: output is broadly consistent with expected rule behavior.
- `REVIEW`: output is technically valid but does not strongly match the expectation.
- `FAIL`: invalid behavior, crash, missing required section, or wrong validation handling.

Exports:

- Benchmark PDF
- Benchmark DOCX
- Benchmark JSON
- Benchmark CSV

Limitations:

- This benchmark checks internal rule behavior only.
- It does not validate clinical safety, efficacy, regulatory approval, or market readiness.
- Benchmark expectations are broad sanity checks, not clinical truth labels.
- Named compound tests may depend on PubChem/cache availability.

Recommended demo:

1. Open `Validation`.
2. Run Common Drug Set.
3. Run Warning Compound Set.
4. Run Stress Tests.
5. Export Benchmark PDF.
6. Review REVIEW/FAIL cases and rule-improvement recommendations.

## Real ADMET/Toxicity Predictor Integration V1

DrugScreen360 now has a safe model-adapter architecture for future real ADMET/toxicity predictors.

Current adapters:

- `rule_based_admet_v1`: available, wraps the existing transparent DrugScreen360 ADMET/Tox rules.
- `local_admet_model`: unavailable placeholder until a real local model is configured.
- `external_admet_service`: unavailable placeholder until a real external service is configured.
- `tox_model_adapter`: unavailable placeholder until a real toxicity model is configured.

Important behavior:

- Unavailable adapters return `model_status: unavailable`.
- Unavailable adapters return `prediction_label: not_available`.
- No fake ML predictions are generated.
- Rule-based ADMET/Tox remains visible as the fallback baseline.
- No clinical or regulatory validation is claimed.

Developer path for future real models:

1. Add an adapter in `backend/app/services/model_registry.py`.
2. Implement `is_available()`, `predict(smiles)`, and `get_model_info()`.
3. Return `PredictionResult` objects with task name, label, score/probability if available, confidence, limitations, and warnings.
4. Add the adapter to `ADAPTERS`.
5. Add tests proving unavailable states do not generate fake values and available states return real configured outputs.

Prediction logs are stored in SQLite table `model_prediction_logs`.

## Batch Compound Library Upload V1

Batch Upload lets users parse and screen their own molecule libraries.

Supported formats:

- CSV: required `smiles`; optional `name`, `compound_id`, `source`, `notes`
- CSV aliases: `SMILES`, `canonical_smiles`, `molecule_smiles`, `compound_name`, `molecule_name`, `id`
- TXT/SMI: one compound per line, either `SMILES` or `SMILES name`
- SDF: parsed with RDKit
- MOL: single molecule file parsed with RDKit

Limits:

- Max file size: 5 MB
- Max parsed compounds: 500
- Default screening limit: 100 valid compounds

Workflow:

1. Open `Batch Upload`.
2. Download the example CSV or prepare your own file.
3. Upload and parse the file.
4. Review valid, invalid, and duplicate rows.
5. Screen valid compounds.
6. Review ranked compounds and details.
7. Export JSON, CSV, PDF, or DOCX.

Ranking is transparent and rule-based. Higher priority is assigned to compounds with lower developability risk, lower ADMET/Tox concern, Lipinski/Veber pass, available model status, and valid data.

Limitations:

- Uploaded compounds are not target-linked, so evidence quality is not evaluated.
- Results use computational descriptors and rule-based/model-adapter outputs only.
- Results do not prove safety, efficacy, clinical success, regulatory approval, or market readiness.

## Project-Level Report Export V1

Project-Level Report Export V1 creates a full project summary from either workflow:

```text
Disease Finder -> select disease -> select ranked target -> find ChEMBL candidates -> screen candidates -> export project report
```

```text
Drug Finder -> search target -> select ChEMBL target -> screen candidates -> export project report
```

The project report includes:

- Executive summary
- Disease context when the workflow starts from Disease Finder
- Open Targets selected target context when available
- ChEMBL target selection details
- Candidate retrieval summary
- Candidate comparison table
- Top candidate detail
- Required experimental test plan
- Final recommendation
- Limitations
- References/data sources

Available exports:

- Project PDF
- Project DOCX
- Project JSON
- Project CSV

The project report remains decision-support only. It does not prove safety, efficacy, clinical success, regulatory approval, or market readiness.

### Project Report Workflow

1. Search disease or target.
2. Select target.
3. Load ChEMBL candidates.
4. Select candidates.
5. Run batch screening.
6. Export project PDF, DOCX, JSON, or CSV.

## Similarity Finder V1

Similarity Finder expands one reference molecule into public-database analog candidates, then sends selected analogs through the existing screening, ADMET/Tox, comparison, and project report workflow.

Workflow:

1. Enter a reference molecule as drug name, PubChem CID, SMILES, InChI, or InChIKey.
2. Choose source: `Auto`, `ChEMBL`, or `PubChem`.
3. Set similarity threshold and result limit.
4. Search similar compounds.
5. Review analog candidates with similarity score, identifiers, SMILES, and RDKit drug-likeness preview.
6. Select analogs.
7. Screen selected analogs.
8. Compare drug-likeness, developability risk, and ADMET/Tox rule-based concern.
9. Export Similarity JSON, CSV, Project PDF, or Project DOCX.

Example reference molecules:

- Aspirin
- Caffeine
- Ibuprofen
- Metformin
- SMILES: `CC(=O)OC1=CC=CC=C1C(=O)O`

Similarity ranking is transparent and rule-based. It considers:

- Higher Tanimoto similarity score
- Valid canonical SMILES
- PubChem CID or ChEMBL ID availability
- Data completeness
- RDKit Lipinski/Veber preview
- Developability risk warnings

Important limitations:

- Chemical similarity does not prove shared efficacy, safety, mechanism, or regulatory acceptability.
- Public databases may be incomplete or slow.
- Similarity Finder V1 is compound expansion only, not docking, ML, or generative design.
- ADMET/Tox remains a rule-based MVP and must be followed by experimental testing and expert review.

## Evidence Quality Engine V1

Evidence Quality Engine V1 evaluates whether a target-linked candidate molecule has strong, moderate, weak, or uncertain public bioactivity support.

It uses available ChEMBL activity metadata:

- Activity type: `IC50`, `Ki`, `Kd`, `EC50`, or `AC50`
- Standard value and units
- Molecule ChEMBL ID
- Target ChEMBL ID
- Canonical SMILES
- Assay type
- ChEMBL confidence score
- Activity relation
- Assay description when available

Potency quality is classified as:

- `Strong`: IC50/Ki/Kd <= 100 nM
- `Moderate`: 100-1000 nM
- `Weak`: 1000-10000 nM
- `Very weak/uncertain`: >10000 nM or missing activity value

Evidence score also rewards complete metadata, nM units, preferred direct binding activity types, valid molecule and target identifiers, assay type, interpretable relation, and higher ChEMBL confidence score.

Example interpretations:

- `IC50 50 nM` with complete molecule, target, assay, relation, and confidence metadata = strong evidence.
- `EC50 5000 nM` with missing assay confidence or incomplete metadata = weak evidence.

Evidence quality is used in final candidate priority together with potency, drug-likeness preview, ADMET/Tox concern, and data completeness. Potency alone should not dominate candidate priority.

### Evidence API Test

```powershell
$body = @{
  candidate = @{
    molecule_chembl_id = "CHEMBL_TEST"
    compound_name = "Example EGFR inhibitor"
    canonical_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
    target_chembl_id = "CHEMBL203"
    target_name = "EGFR"
    activity_type = "IC50"
    activity_value = 50
    activity_units = "nM"
    assay_type = "B"
    confidence_score = 9
    relation = "="
    assay_description = "Mock direct binding assay"
  }
} | ConvertTo-Json -Depth 6

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/evidence/evaluate-candidate" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

### Evidence Limitations

- Evidence quality reflects available public bioactivity metadata only.
- It does not prove clinical efficacy, safety, selectivity, mechanism, regulatory approval, or market readiness.
- BindingDB support is optional in V1 and safely falls back if unavailable.
- Weak or incomplete metadata should trigger confirmatory experiments and expert review.

## Disease Finder V1

Disease Finder V1 creates this workflow:

```text
Disease -> ranked therapeutic targets -> candidate molecules -> screening -> ADMET/Tox comparison
```

It uses the Open Targets GraphQL API:

```text
https://api.platform.opentargets.org/api/v4/graphql
```

Open Targets association scores are used for prioritization only. They do not prove that modulating a target will be safe, effective, clinically successful, or regulatory-ready.

### Example Disease Searches

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/disease-finder/diseases?query=breast%20cancer" `
  -Method Get
```

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/disease-finder/diseases?query=idiopathic%20pulmonary%20fibrosis" `
  -Method Get
```

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/disease-finder/diseases?query=Alzheimer%20disease" `
  -Method Get
```

### Example Disease Target Retrieval

Replace `EFO_0000305` with the selected disease ID from disease search.

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/disease-finder/disease/EFO_0000305/targets" `
  -Method Get
```

### Disease Finder Workflow

1. Search disease, for example `breast cancer`.
2. Select the best Open Targets disease match.
3. Review ranked associated targets.
4. Click `Find Molecules` for a selected target.
5. Select the matching ChEMBL target.
6. Retrieve candidate molecules.
7. Select molecules and run batch screening.
8. Compare potency, drug-likeness, developability risk, and ADMET/Tox risk.

### Disease Finder Limitations

- Open Targets scores prioritize biological and therapeutic relevance only.
- Target association does not prove clinical efficacy.
- Target modulation may still be unsafe, ineffective, or non-developable.
- ChEMBL candidate availability depends on public activity records.
- Candidate screening remains rule-based and decision-support only.

## ADMET/Toxicity Engine V1

ADMET/Toxicity V1 uses RDKit descriptors and broad SMARTS-based structural alerts to create an early rule-based concern summary.

It includes:

- Absorption / oral developability flag
- Solubility risk
- BBB/CNS exposure flag
- Metabolism readiness status
- Broad structural alert summary
- Overall ADMET/Tox concern score
- Recommended experimental follow-up tests

The following are explicitly not implemented as validated prediction models:

- CYP substrate/inhibition/induction prediction
- hERG prediction
- Ames/genotoxicity prediction
- Carcinogenicity prediction
- Hepatotoxicity prediction

These sections are labelled as `Not implemented` and recommend experimental follow-up assays.

### Example ADMET/Toxicity API Test

```powershell
$body = @{
  smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/admet/evaluate" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

### ADMET/Toxicity V1 Limitations

- Rule-based early screen only.
- Not a validated ADMET or toxicity prediction model.
- Does not replace hERG, Ames, CYP, hepatotoxicity, nonclinical, clinical, or regulatory testing.
- Confidence is intentionally limited to Low or Medium.
- Experimental assays and expert review are required before development decisions.

## Drug Finder V1

Drug Finder V1 is a candidate-finding layer for the existing screening engine. It does not add ML ADMET models, docking, AI molecule generation, or claims of clinical efficacy.

The finder currently uses the official ChEMBL REST API through ordinary HTTPS requests. No extra ChEMBL client package is required.

## Target Selection Guidance

ChEMBL target search can return several target types for the same gene or protein keyword. For example, `EGFR` may return protein-protein interactions, protein families, chimeric proteins, mouse targets, and the human single-protein target.

For small-molecule candidate retrieval, DrugScreen360 now prioritizes:

- exact gene/protein symbol or preferred-name matches where available
- `Homo sapiens` targets
- `SINGLE PROTEIN` targets
- targets with accession metadata
- preferred names that contain the search query

Protein-protein interactions, chimeric proteins, protein families, and non-human targets are ranked lower because they are usually less direct for first-pass small-molecule candidate retrieval.

If no candidates are found for a selected target, choose another ChEMBL target match, preferably a human `SINGLE PROTEIN` target. The UI will show the selected target metadata and suggest the next best human single-protein match when available.

Example: an `EGFR` search should prefer `CHEMBL203`, the human single-protein epidermal growth factor receptor target, above EGFR protein-protein interaction records.

### Example Target Search: EGFR

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/finder/targets?query=EGFR" `
  -Method Get
```

### Example Target Search: COX2

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/finder/targets?query=COX2" `
  -Method Get
```

### Example Candidate Retrieval

Replace `CHEMBL203` with the selected target ID from the target-search response.

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/finder/target/CHEMBL203/candidates" `
  -Method Get
```

### Example Finder Workflow

1. Search target, for example `EGFR`.
2. Select the correct ChEMBL target.
3. Retrieve ranked candidates for that target.
4. Select candidates in the frontend.
5. Run batch screening.
6. Compare MW, LogP, TPSA, Lipinski, Veber, developability risk, and decision.
7. Review evidence score, potency quality, ADMET/Tox concern, and final candidate priority.

Candidate ranking is transparent and rule-based. It considers lower nM potency, ChEMBL evidence quality, valid canonical SMILES, fewer missing fields, duplicate removal, and RDKit Lipinski/Veber preview. It does not prove clinical efficacy, safety, or regulatory approval.

## Aspirin Test Command

```powershell
$body = @{
  query = "Aspirin"
  input_type = "name"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8010/api/screen" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

The response includes a `screening_id`. Use that ID for PDF and DOCX export.

## PDF Export

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:8010/api/report/1/pdf" `
  -OutFile "DrugScreen360-Aspirin.pdf"
```

PDF export uses ReportLab and should work on Windows through `pip install -r requirements.txt`.

## DOCX Export

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:8010/api/report/1/docx" `
  -OutFile "DrugScreen360-Aspirin.docx"
```

DOCX export uses `python-docx` and should work on Windows through `pip install -r requirements.txt`.

## Run Tests

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360\backend"
.\.venv312\Scripts\Activate.ps1
python -m pytest
```

Frontend utility checks:

```powershell
cd "D:\DRUG CONJUGATE\drugscreen360\frontend"
npm test
```

Current tests cover:

- Aspirin lookup
- Invalid SMILES
- Unknown compound
- Descriptor calculation
- Lipinski and Veber rule logic
- Screening history save
- Mocked ChEMBL target search route structure
- Candidate ranking logic
- Duplicate molecule removal
- Batch screening endpoint
- Finder invalid SMILES handling
- No target found case
- Mocked Open Targets disease search
- Mocked Open Targets disease target retrieval
- Disease target ranking logic
- Open Targets timeout/error handling
- Disease-target to ChEMBL query handoff shape
- ADMET/Toxicity V1 low-risk and high-risk rule examples
- Nitro aromatic structural alert
- ADMET/Tox inclusion in single and batch screening
- PDF/DOCX export with ADMET/Tox section
- Evidence Quality V1 strong, moderate, weak, and missing-value examples
- Evidence batch duplicate handling
- BindingDB unavailable fallback
- Drug Finder and batch screening evidence fields
- Clear all screening history endpoint
- Frontend raw input validation, PubChem CID validation, stable candidate selection keys, and target handoff helpers
- ChEMBL target priority ranking for human single-protein matches
- No-candidates response handling
- Local API cache set/get and expired-cache handling
- Cache metadata on repeated ChEMBL/Open Targets calls
- Cache stats and clear-cache endpoints
- Clean external API failure handling
- Frontend cache label utility logic
- Similarity Finder V1 search, ranking, cache hit, analog screening, and similarity project report support
- Example Library and demo fallback endpoints
- Frontend QA checklist helper logic
- Validation & Benchmarking dataset, runner, exports, and report builders
- Batch Compound Library Upload parsing, screening, ranking, and exports

## Manual Testing Checklist

### Example Library And Demo Mode

1. Open `Examples`.
2. Click `Run Screening` on Aspirin.
3. Confirm Screening opens and a report is generated.
4. Open EGFR in Drug Finder and confirm the target query is filled.
5. Open breast cancer in Disease Finder and confirm the disease query is filled.
6. Open Caffeine in Similarity Finder and confirm source/threshold are filled.
7. In `System`, confirm `Use Demo Fallback When Live APIs Fail` is visible.
8. If a supported live call fails, accept demo fallback and confirm the `Demo data` label appears.
9. In `System`, mark QA checklist items as Pass/Fail and refresh the page.
10. Confirm checklist statuses persist.

### Validation & Benchmarking

1. Open `Validation`.
2. Click `Run Common Drug Set`.
3. Confirm summary cards and results table appear.
4. Click `Run Warning Compound Set`.
5. Click `Run Stress Tests`.
6. Open a result with `Details`.
7. Export Benchmark PDF, DOCX, JSON, and CSV.
8. Review REVIEW/FAIL cases and recommendations.

### Batch Compound Library Upload

1. Open `Batch Upload`.
2. Click `Download Example CSV`.
3. Upload the example CSV.
4. Click `Parse File`.
5. Confirm valid/invalid/duplicate counts and preview table appear.
6. Click `Screen Valid Compounds`.
7. Open a compound details panel.
8. Export Batch Upload PDF, DOCX, CSV, and JSON.
9. Try a CSV containing invalid SMILES such as `C1CC`.
10. Try an unsupported file type and confirm a clean error.

### Single Molecule Screening

1. Open `http://127.0.0.1:5173`.
2. In Screening, enter `Aspirin` with input type `Drug name`.
3. Run screening and confirm the report dashboard appears.
4. Export JSON, PDF, and DOCX.
5. Click a history item and confirm the input box contains only the raw query, not formatted text such as `Input: ...`.

### Invalid Input Handling

1. Select input type `PubChem CID`.
2. Enter `Input: 2244 Input type: PubChem CID`.
3. Run screening.
4. Confirm the UI shows `PubChem CID must be a number.`
5. Clear the field and run again.
6. Confirm the UI shows `Please enter a compound name, CID, SMILES, InChI, or InChIKey.`

### Drug Finder Candidate Selection

1. Open Drug Finder.
2. Search `EGFR`.
3. Pick a human single-protein ChEMBL target if available.
4. Click `Candidates`.
5. Confirm candidate rows show checkboxes.
6. Select two candidates.
7. Confirm selected rows are highlighted and the counter updates.
8. Click `Clear Selection` and confirm the counter returns to zero.

### Batch Screening And Export

1. Select one to three Drug Finder candidates.
2. Click `Screen Selected Candidates`.
3. Confirm the Candidate Comparison dashboard appears.
4. Confirm the table includes activity, evidence, MW, LogP, TPSA, Lipinski, Veber, risk, ADMET/Tox, decision, priority, and next step.
5. Click `Export Batch JSON`.
6. Click `Export Batch CSV`.
7. Confirm `Project Report` appears.
8. Click `Export Project PDF`, `Export Project DOCX`, `Export Project JSON`, and `Export Project CSV`.

### Similarity Finder

1. Open Similarity Finder.
2. Search `Aspirin` with input type `Drug name`, source `Auto`, threshold `70`, and limit `25`.
3. Confirm the reference compound card appears.
4. Confirm similar compounds appear with similarity score, source, and drug-likeness preview.
5. Select one to three analogs.
6. Click `Screen Selected Analogs`.
7. Confirm the similarity comparison dashboard appears.
8. Export Similarity JSON and CSV.
9. Export Project PDF and DOCX.
10. Repeat the same search and confirm the cache label changes to `Cached`.

### Disease Finder To Drug Finder Workflow

1. Open Disease Finder.
2. Search `breast cancer`.
3. Select a disease match.
4. In ranked targets, click `Find Molecules` for a target such as `EGFR` if present.
5. Confirm the app switches to Drug Finder, uses the target symbol as the ChEMBL query, and loads the preferred matching target/candidates where available.
6. Select candidates and run batch screening.
7. Export the project report and confirm disease context is included.

### Cache Miss Then Cache Hit

1. Open the `System` tab and click `Clear Cache`.
2. Open Drug Finder and search `EGFR`.
3. Confirm the target search label shows `Live API`.
4. Search `EGFR` again.
5. Confirm the label shows `Cached`.
6. Open Disease Finder and search `breast cancer`.
7. Confirm the first disease search shows `Live API`.
8. Search `breast cancer` again.
9. Confirm the disease search shows `Cached`.
10. Return to `System` and click `Refresh Cache Stats`.
11. Confirm cached items appear for `chembl` and `open_targets`.

### Deployment / One-Command Run Checklist

1. Run `.\scripts\run_tests.ps1`.
2. Run `.\scripts\start_all.ps1`.
3. Open `http://127.0.0.1:5173`.
4. Open `System`.
5. Click `Refresh System Health`.
6. Confirm backend reachable is `yes`, version is `0.1.0-local-mvp`, database status is `ok`, cache status is `ok`, and model registry counts are visible.
7. Run Aspirin screening.
8. Run EGFR Drug Finder.
9. Run Batch Upload with the example CSV.
10. Run `.\scripts\backup_local_data.ps1` and confirm a new timestamped folder appears under `backups`.

## External ADMET Provider Adapter V1

DrugScreen360 includes a safe external-provider adapter for future real ADMET/toxicity services. By default it is unavailable and no external prediction call is made. The rule-based ADMET/Tox adapter remains the fallback baseline.

Backend environment example:

```powershell
$env:ADMET_PROVIDER_ENABLED="false"
$env:ADMET_PROVIDER_BASE_URL=""
$env:ADMET_PROVIDER_API_KEY=""
$env:ADMET_PROVIDER_TIMEOUT_SECONDS="30"
$env:ADMET_PROVIDER_MOCK_MODE="false"
```

Expected provider endpoint:

`POST {ADMET_PROVIDER_BASE_URL}/predict`

Payload:

```json
{
  "smiles": "CCO",
  "tasks": [
    "solubility",
    "permeability",
    "bbb",
    "cyp_inhibition",
    "herg",
    "ames",
    "hepatotoxicity",
    "general_toxicity"
  ]
}
```

Expected response:

```json
{
  "model_id": "provider_model_id",
  "model_name": "Configured ADMET Provider",
  "version": "1.0",
  "predictions": [
    {
      "task_name": "herg",
      "prediction_label": "low_risk",
      "prediction_score": 0.21,
      "probability": 0.21,
      "confidence": "medium",
      "limitations": "Provider-specific limitation text."
    }
  ],
  "warnings": []
}
```

Behavior:

- If `ADMET_PROVIDER_ENABLED=false` or `ADMET_PROVIDER_BASE_URL` is empty, `/api/models/status` returns `external_admet_provider_v1` as unavailable.
- If configured but the health check or prediction call fails, the adapter returns `error` with a clear warning.
- If response parsing fails, the adapter returns `error` and does not fake missing tasks.
- If `ADMET_PROVIDER_MOCK_MODE=true`, outputs are labeled `mock` and include: `Mock predictions are for software testing only and must not be used scientifically.`
- Mock mode is disabled by default and should not be used for scientific reporting.

Manual check:

1. Open `System`.
2. Click `Refresh Model Status`.
3. Confirm `External ADMET Provider Adapter` is shown.
4. With default settings, confirm status is `unavailable` and the warning says the provider is not configured.
5. Run Aspirin screening and confirm the report still shows rule-based ADMET/Tox output.

## Known Limitations

- External ADMET/toxicity model integration requires a real configured provider.
- If no provider is configured, only the rule-based ADMET/Tox adapter is active.
- The current decision engine is rule-based and transparent, not an ML model.
- Evidence Quality Engine V1 scores metadata quality only. It is not an efficacy model.
- PubChem availability affects lookup by name, CID, InChI, InChIKey, and SMILES.
- SQLite is suitable for the MVP, not multi-user production scale.
- Reports are screening-support documents only, not regulatory submissions.

## Future Modules

- ADMET model integration
- Toxicity model integration
- Expanded BindingDB affinity parsing
- Disease-target search refinements
- Docking module
- Validated open-source ADMET models
- External API integrations where legally allowed
- Model confidence scoring
- Calibration against benchmark datasets

## Not Included Yet

- Login
- Payment
- Docking
- AI molecule generation
