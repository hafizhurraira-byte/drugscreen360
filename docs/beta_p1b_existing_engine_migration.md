# BETA-P1B existing-engine migration

## Scope and discovered engines

The deterministic migration imports eleven implemented capabilities: EGFR activity v2; BBBP, ESOL, hERG, and ClinTox CT_TOX v1; RDKit; grouped medicinal-chemistry rule filters; and the PubChem, ChEMBL, BindingDB, and Open Targets connectors. Placeholder external ADMET/tox adapters are contract-only and are not migrated. UniProt, Ensembl, NCBI Gene, Reactome, Gene Ontology, PDB, AlphaFold, docking, MD, and ESR1 execution were not found as current implemented services and are excluded.

Existing activity/ADMET tables, registration manifests, artifact verification, external-validation evidence, domain references, uncertainty/calibration metadata, and their hashes remain authoritative. Registry records summarize them; `scientific_engine_legacy_links` stores safe identifiers and a path-free reconciliation snapshot. It never changes or deletes legacy records.

## Mapping

Legacy `ACTIVE` predictive models map to `ACTIVE_BETA`; disabled or absent active rows map to `INACTIVE`; ClinTox maps to `REJECTED` and `BLOCKED_VALIDATION`. Verified artifacts map to `AVAILABLE`; missing or unverifiable artifacts map to `ARTIFACT_MISSING`. Toolkit/rule services map to `ACTIVE_RESEARCH`; remote connectors are implemented but runtime health remains `UNKNOWN` until called. Unknown licence facts remain `NOT_REVIEWED` or `UNKNOWN`; code terms never imply weights, data, redistribution, commercial, or provider-database permission.

BBBP retains its benchmark/CNS warning. ESOL retains interval-undercoverage and measured-solubility warnings. hERG retains calibration/recalibration and cardiac-safety warnings. ClinTox retains zero toxic-positive recall/F1 and remains excluded from production prediction/ranking. EGFR preserves the authoritative disabled state and is never automatically reactivated.

## CLI

From the repository root:

```powershell
backend\.venv312\Scripts\python.exe scripts\maintenance\import_beta_p1b_existing_engines.py --dry-run
backend\.venv312\Scripts\python.exe scripts\maintenance\import_beta_p1b_existing_engines.py --apply --output-report migration-report.json
backend\.venv312\Scripts\python.exe scripts\maintenance\import_beta_p1b_existing_engines.py --verify
```

Use `--engine-id ID` for one engine and `--source-root PATH` only for an explicit local administrative migration. Dry-run writes nothing. Apply is idempotent and conflicting identities, versions, or legacy links return an error. Verify reports missing/conflicting records. Reports are sorted and contain no artifact paths or secrets.

## Reconciliation and security

Reconciliation is read-only and reports `CONSISTENT`, missing/link/state/hash/endpoint/validation mismatches, unresolved licences, unavailable artifacts, or partial/not-applicable states. It recommends review and performs no scientific repair. Mutation/migration APIs accept local clients or an administrator token in `SCIENTIFIC_ENGINE_ADMIN_TOKEN`; read responses recursively redact machine paths and secret-shaped fields.

## BETA-P2 handoff

Execution still uses existing model/tool/provider services. BETA-P2 may add a standardized adapter contract after licence, artifact, schema, failure, and deployment gates are reconciled.

## Corrective governance note

Legacy execution is not beta approval. BBBP, ESOL, and hERG keep authoritative legacy `ACTIVE` records, but registry activation is `INACTIVE` and beta eligibility is blocked while licence review is unresolved. EGFR remains disabled/inactive. ClinTox remains blocked by rejected validation. Toolkits, rules, and connectors likewise remain inactive for governed registry execution until an appropriate licence review is recorded.

The frozen BBBP, ESOL, hERG, and ClinTox joblib artifacts record scikit-learn 1.9.0, while `backend/requirements.txt` and the controlled runtime provide 1.5.2. No authoritative 1.9.0 parity baseline or existing isolated runtime is available, so the correction uses fail-closed Option C: `MISCONFIGURED`, runtime `UNAVAILABLE`, `VERSION_MISMATCH_UNVERIFIED`, and `execution_allowed=false`. Hash verification occurs before compatibility evaluation; unsafe artifacts are never deserialized and no heuristic fallback is used. EGFR records scikit-learn 1.5.2 and exactly matches the runtime, but remains unavailable because its authoritative execution state is disabled and its licence is unresolved.
