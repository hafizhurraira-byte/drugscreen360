# DrugScreen360 Release Notes

## v0.1.0-local-mvp

Release type: local MVP / private first release

Version: `0.1.0-local-mvp`

DrugScreen360 v0.1.0-local-mvp is a local-first drug screening and report-generation MVP. It is designed for decision support, workflow demonstration, and internal review. It does not prove safety, efficacy, clinical success, regulatory approval, or market readiness.

## Major Features

- Single-molecule screening from drug name, PubChem CID, SMILES, InChI, or InChIKey.
- PubChem compound lookup with local cache support.
- RDKit descriptors and 2D structure rendering.
- Lipinski, Veber, drug-likeness, developability risk, and go/no-go recommendation.
- Rule-based ADMET/Toxicity V1 with clear limitations.
- Evidence Quality Engine V1 for target-linked ChEMBL candidates.
- Drug Finder V1 using ChEMBL target search and candidate retrieval.
- Disease Finder V1 using Open Targets disease-to-target workflow.
- Similarity Finder V1 for analog discovery and screening.
- Batch Compound Library Upload V1 for CSV, TXT/SMI, SDF, and MOL files.
- Validation & Benchmarking V1 with local benchmark compounds.
- Example Library and Demo Mode for presentations and slow API fallback.
- Project-level, single-candidate, batch-upload, and benchmark report exports.
- JSON, CSV, PDF, and DOCX export support where appropriate.
- Performance + Local Cache V1 for PubChem, ChEMBL, Open Targets, and related lookups.
- Model registry with safe external ADMET provider adapter that is unavailable by default unless configured.
- Deployment / One-Command Run V1 with PowerShell scripts and Docker Compose.

## Supported Workflows

- Screen one molecule and export a report.
- Search a target, retrieve ChEMBL candidates, screen selected candidates, and compare results.
- Search a disease, review ranked Open Targets therapeutic targets, find molecules through ChEMBL, and screen candidates.
- Search similar compounds from a reference molecule, screen selected analogs, and export a project report.
- Upload a local compound library, validate compounds, screen valid molecules, rank outputs, and export a batch report.
- Run internal benchmark sets and export validation reports.

## Endpoint Summary

- `GET /api/health`
- `POST /api/screen`
- `GET /api/screening/history`
- `GET /api/report/{screening_id}/pdf`
- `GET /api/report/{screening_id}/docx`
- `GET /api/finder/targets`
- `GET /api/finder/target/{target_chembl_id}/candidates`
- `POST /api/finder/screen-candidates`
- `GET /api/disease-finder/diseases`
- `GET /api/disease-finder/disease/{disease_id}/targets`
- `POST /api/similarity/search`
- `POST /api/similarity/screen-selected`
- `POST /api/batch-library/parse`
- `POST /api/batch-library/screen`
- `GET /api/benchmark/compounds`
- `POST /api/benchmark/run`
- `GET /api/models/status`
- `POST /api/models/predict-admet`
- `GET /api/cache/stats`
- `DELETE /api/cache/clear`
- `GET /api/examples`
- `GET /api/examples/workflows`
- `POST /api/project-report/create`

## Testing Status

- Backend test suite: `96 passed`.
- Frontend utility tests: passed.
- Frontend production build: passed.
- Docker Compose configuration: valid.
- Backup script: verified locally.

## Known Limitations

- Rule-based ADMET/Tox is not a validated ML, clinical, toxicology, or regulatory prediction model.
- External ADMET provider adapter is unavailable by default and only calls a real service when explicitly configured.
- Mock provider mode is for software testing only and must not be used scientifically.
- Evidence scoring reflects public metadata quality only and does not prove target engagement, efficacy, or safety.
- Disease-target associations from Open Targets prioritize biological/therapeutic relevance but do not prove a target is safe or effective.
- Similarity search does not prove shared activity, mechanism, safety, or regulatory acceptability.
- SQLite is suitable for a local MVP, not multi-user production deployment.
- Public API results depend on PubChem, ChEMBL, Open Targets, and network availability.

## Next Planned Features

- Optional validated open-source ADMET model integration through the model registry.
- More robust provider adapters with documented validation status.
- Expanded BindingDB support where legally and technically practical.
- More benchmark datasets and benchmark comparison summaries.
- User-facing report templates for different research workflows.
- Better Docker production profile for shared local-network demos.
