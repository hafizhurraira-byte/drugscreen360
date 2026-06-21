from pathlib import Path
import sqlite3
import os
from urllib.parse import unquote, urlparse


def _database_path() -> Path:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url.startswith("sqlite:///"):
        parsed = urlparse(database_url)
        if parsed.netloc:
            return Path(unquote(f"//{parsed.netloc}{parsed.path}"))
        path = unquote(parsed.path)
        if path.startswith("/./"):
            path = path[1:]
        if os.name != "nt" and path.startswith("//"):
            path = path[1:]
        if path.startswith("/") and not path.startswith("//") and len(path) > 2 and path[2] == ":":
            path = path.lstrip("/")
        db_path = Path(path)
        return db_path if db_path.is_absolute() else Path.cwd() / db_path
    return Path(__file__).resolve().parents[2] / "drugscreen360.sqlite3"


DB_PATH = _database_path()


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS screening_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_query TEXT NOT NULL,
                input_type TEXT NOT NULL,
                compound_name TEXT,
                pubchem_cid INTEGER,
                canonical_smiles TEXT,
                descriptor_summary TEXT NOT NULL,
                drug_likeness_result TEXT NOT NULL,
                decision TEXT NOT NULL,
                report_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS finder_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                selected_target TEXT,
                candidates_found INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS finder_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id INTEGER,
                molecule_chembl_id TEXT,
                compound_name TEXT,
                canonical_smiles TEXT,
                activity_type TEXT,
                activity_value REAL,
                activity_units TEXT,
                target_chembl_id TEXT,
                source TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(search_id) REFERENCES finder_searches(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS batch_screening_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_count INTEGER NOT NULL,
                summary_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS disease_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                selected_disease_id TEXT,
                selected_disease_name TEXT,
                targets_found INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS disease_target_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id INTEGER,
                target_id TEXT,
                approved_symbol TEXT,
                approved_name TEXT,
                association_score REAL,
                final_target_priority_score REAL,
                selected_target INTEGER NOT NULL DEFAULT 0,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(search_id) REFERENCES disease_searches(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS evidence_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                molecule_identifier TEXT,
                target_identifier TEXT,
                target_name TEXT,
                evidence_score INTEGER NOT NULL,
                evidence_level TEXT NOT NULL,
                potency_quality TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                workflow_type TEXT NOT NULL,
                disease_name TEXT,
                disease_id TEXT,
                target_symbol TEXT,
                chembl_target_id TEXT,
                candidate_count INTEGER NOT NULL DEFAULT 0,
                screened_count INTEGER NOT NULL DEFAULT 0,
                top_candidate TEXT,
                report_payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS api_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                query_type TEXT NOT NULL,
                query_value TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                hit_count INTEGER NOT NULL DEFAULT 0,
                last_accessed_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS similarity_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reference_query TEXT NOT NULL,
                reference_compound_name TEXT,
                source TEXT NOT NULL,
                threshold INTEGER NOT NULL,
                candidates_found INTEGER NOT NULL DEFAULT 0,
                selected_candidate_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS similarity_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id INTEGER,
                compound_name TEXT,
                pubchem_cid INTEGER,
                molecule_chembl_id TEXT,
                canonical_smiles TEXT,
                similarity_score REAL,
                source TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(search_id) REFERENCES similarity_searches(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS benchmark_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                selected_group TEXT,
                total_tested INTEGER NOT NULL,
                passed INTEGER NOT NULL,
                review INTEGER NOT NULL,
                failed INTEGER NOT NULL,
                result_payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS model_prediction_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                smiles TEXT NOT NULL,
                model_id TEXT NOT NULL,
                task_name TEXT NOT NULL,
                prediction_label TEXT NOT NULL,
                prediction_score REAL,
                confidence TEXT,
                status TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS uploaded_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                total_rows INTEGER NOT NULL,
                valid_count INTEGER NOT NULL,
                invalid_count INTEGER NOT NULL,
                duplicate_count INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS uploaded_batch_compounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER NOT NULL,
                row_number INTEGER NOT NULL,
                compound_name TEXT,
                compound_id TEXT,
                original_smiles TEXT,
                canonical_smiles TEXT,
                valid INTEGER NOT NULL,
                error_reason TEXT,
                descriptors_json TEXT,
                source TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(batch_id) REFERENCES uploaded_batches(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS batch_library_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id INTEGER,
                screened_count INTEGER NOT NULL,
                failed_count INTEGER NOT NULL,
                result_payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(batch_id) REFERENCES uploaded_batches(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS research_exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                title TEXT,
                notes TEXT,
                included_sections TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                disease_area TEXT,
                target_name TEXT,
                project_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                item_type TEXT NOT NULL,
                item_id TEXT NOT NULL,
                item_title TEXT,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                export_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(export_id) REFERENCES research_exports(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_workspace_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                filename_pdf TEXT NOT NULL,
                filename_docx TEXT NOT NULL,
                filename_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                warnings_json TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_active_option (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                project_id INTEGER,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admet_datasets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                task_name TEXT,
                label_column TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                record_count INTEGER NOT NULL,
                valid_count INTEGER NOT NULL,
                invalid_count INTEGER NOT NULL,
                duplicate_count INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                notes TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admet_dataset_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id INTEGER NOT NULL,
                compound_name TEXT,
                original_smiles TEXT,
                canonical_smiles TEXT,
                label_value TEXT,
                is_valid INTEGER NOT NULL,
                invalid_reason TEXT,
                duplicate_group TEXT,
                descriptors_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(dataset_id) REFERENCES admet_datasets(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admet_training_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id INTEGER NOT NULL,
                task_name TEXT,
                task_type TEXT NOT NULL,
                model_name TEXT NOT NULL,
                model_type TEXT NOT NULL,
                status TEXT NOT NULL,
                train_count INTEGER NOT NULL,
                test_count INTEGER NOT NULL,
                metric_summary_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                artifact_dir TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(dataset_id) REFERENCES admet_datasets(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admet_model_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                training_run_id INTEGER NOT NULL,
                model_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                version TEXT NOT NULL,
                task_name TEXT,
                task_type TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                manifest_path TEXT NOT NULL,
                model_card_path TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                FOREIGN KEY(training_run_id) REFERENCES admet_training_runs(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admet_active_model (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                model_id TEXT,
                status TEXT NOT NULL,
                activated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admet_external_validation_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id TEXT NOT NULL,
                training_run_id INTEGER,
                external_dataset_id INTEGER NOT NULL,
                task_name TEXT,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL,
                valid_count INTEGER NOT NULL,
                invalid_count INTEGER NOT NULL,
                metric_summary_json TEXT NOT NULL,
                calibration_summary_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(external_dataset_id) REFERENCES admet_datasets(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admet_domain_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id TEXT NOT NULL,
                training_run_id INTEGER,
                smiles TEXT NOT NULL,
                canonical_smiles TEXT NOT NULL,
                domain_status TEXT NOT NULL,
                uncertainty_level TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admet_prediction_explanations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id TEXT NOT NULL,
                training_run_id INTEGER,
                smiles TEXT NOT NULL,
                canonical_smiles TEXT NOT NULL,
                prediction_summary_json TEXT NOT NULL,
                explanation_summary_json TEXT NOT NULL,
                evidence_strength TEXT NOT NULL,
                domain_status TEXT NOT NULL,
                uncertainty_level TEXT NOT NULL,
                report_files_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admet_lead_prioritization_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                source_type TEXT NOT NULL,
                candidate_count INTEGER NOT NULL,
                ranked_count INTEGER NOT NULL,
                excluded_count INTEGER NOT NULL,
                scoring_profile TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS admet_lead_prioritization_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                compound_name TEXT,
                smiles TEXT NOT NULL,
                canonical_smiles TEXT NOT NULL,
                rank INTEGER NOT NULL,
                priority_label TEXT NOT NULL,
                score_summary_json TEXT NOT NULL,
                warnings_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(run_id) REFERENCES admet_lead_prioritization_runs(id)
            )
            """
        )



