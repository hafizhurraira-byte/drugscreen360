import csv
import json
import platform
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from app.database import get_connection, init_db
from app.models.batch_library_models import BatchLibraryScreenResponse
from app.models.benchmark_models import BenchmarkRunResponse
from app.models.project_report_models import ProjectReportPayload
from app.models.research_export_models import ResearchExportRequest, ResearchExportCreateResponse, ResearchExportListItem
from app.models.schemas import ScreeningReport
from app.services.batch_library_service import batch_library_csv, batch_library_docx, batch_library_pdf
from app.services.benchmark_service import benchmark_csv, benchmark_docx, benchmark_pdf
from app.services.cache_service import cache_stats
from app.services.local_admet_model import validate_local_admet_model
from app.services.model_registry import model_status_response
from app.services.project_reports import build_project_csv, build_project_docx, build_project_pdf
from app.services.project_workspace_service import (
    get_project,
    link_project_export,
    project_dashboard,
    project_decision_matrix_csv,
    project_recommendations_markdown,
)
from app.services.project_workspace_reports import REPORT_DIR
from app.services.reports import build_docx_report, build_pdf_report
from app.services.version import app_version

EXPORT_DIR = Path(__file__).resolve().parents[2] / "research_exports"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d_%H-%M-%S")


def _json_bytes(data: Any) -> bytes:
    return json.dumps(data, indent=2, default=str).encode("utf-8")


def _csv_text(rows: list[dict[str, Any]], headers: list[str]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


def _rows(table: str, limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    with get_connection() as connection:
        return [
            dict(row)
            for row in connection.execute(
                f"SELECT * FROM {table} ORDER BY datetime(created_at) DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        ]


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[3],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except Exception:
        return None


def _backend_health_summary() -> dict[str, Any]:
    try:
        with get_connection() as connection:
            connection.execute("SELECT 1").fetchone()
        database = {"status": "ok"}
    except Exception as exc:
        database = {"status": "error", "message": str(exc)}
    try:
        cache = {"status": "ok", **cache_stats()}
    except Exception as exc:
        cache = {"status": "error", "message": str(exc)}
    return {"database": database, "cache": cache}


def _model_status_json() -> dict[str, Any]:
    status = model_status_response()
    models = status["available_models"] + status["unavailable_models"]
    return {
        "models": [model.model_dump() for model in models],
        "supported_tasks": status["supported_tasks"],
        "limitations": status["limitations"],
        "prediction_source_summary": {
            "rule_based_admet_v1": "available by default as transparent heuristic rules",
            "external_admet_provider_v1": "available only when a real provider is configured and healthy",
            "local_admet_model": "available only when a real local model, manifest, artifacts, and supported loader exist",
        },
    }


def _readme_export(title: str | None, warnings: list[str]) -> str:
    warning_text = "\n".join(f"- {warning}" for warning in warnings) or "- None"
    return f"""# DrugScreen360 Research Export Package

Project title: {title or "Untitled"}

This ZIP package contains stored DrugScreen360 data, model/cache status, reproducibility notes, scientific disclaimers, and regenerated reports where possible.

## Scientific Scope

This export is computational and decision-support only. It does not prove safety, efficacy, clinical success, regulatory approval, or market readiness.

## Storage Notes

DrugScreen360 exports records available in local SQLite storage. Some interactive workflows may not be stored as complete reports unless the user saved or generated a project/batch/benchmark report.

## Warnings

{warning_text}
"""


def _scientific_limitations() -> str:
    return """# Scientific Limitations

- Computational decision-support only.
- Not a replacement for laboratory validation.
- Not medical advice.
- No clinical efficacy or safety guarantee.
- No regulatory approval or market readiness is implied.
- Model predictions are unavailable unless real configured models exist.
- Rule-based ADMET/Tox is heuristic and not validated ML.
- Public database records may be incomplete, stale, duplicated, or inconsistent.
- Experimental testing and qualified expert review are required before advancing any candidate.
"""


def _environment_summary(created_at: str) -> str:
    requirements_path = Path(__file__).resolve().parents[2] / "requirements.txt"
    package_path = Path(__file__).resolve().parents[3] / "frontend" / "package.json"
    return f"""# Reproducibility Summary

- App version: {app_version()}
- Export timestamp: {created_at}
- Python version: {sys.version.split()[0]}
- Python implementation: {platform.python_implementation()}
- Backend dependencies source: {requirements_path}
- Frontend package source: {package_path}
- Local run command: .\\scripts\\start_all.ps1
- Local test command: .\\scripts\\run_tests.ps1
- Git commit hash: {_git_commit() or "Not available"}
"""


def _write_json(zip_file: zipfile.ZipFile, path: str, data: Any, manifest: list[dict[str, Any]]) -> None:
    zip_file.writestr(path, _json_bytes(data))
    manifest.append({"path": path, "type": "json"})


def _write_text(zip_file: zipfile.ZipFile, path: str, text: str, manifest: list[dict[str, Any]], file_type: str = "text") -> None:
    zip_file.writestr(path, text.encode("utf-8"))
    manifest.append({"path": path, "type": file_type})


def _write_bytes(zip_file: zipfile.ZipFile, path: str, content: bytes, manifest: list[dict[str, Any]], file_type: str) -> None:
    zip_file.writestr(path, content)
    manifest.append({"path": path, "type": file_type})


def _add_screening_reports(zip_file: zipfile.ZipFile, root: str, rows: list[dict[str, Any]], warnings: list[str], manifest: list[dict[str, Any]]) -> None:
    for row in rows:
        report_json = row.get("report_json")
        if not report_json:
            warnings.append(f"Screening history #{row.get('id')} had no report JSON.")
            continue
        try:
            report = ScreeningReport.model_validate_json(report_json)
            _write_json(zip_file, f"{root}/SCREENING_RESULTS/screening_{row['id']}.json", json.loads(report_json), manifest)
            _write_bytes(zip_file, f"{root}/REPORTS/screening_{row['id']}.pdf", build_pdf_report(report), manifest, "pdf")
            _write_bytes(zip_file, f"{root}/REPORTS/screening_{row['id']}.docx", build_docx_report(report), manifest, "docx")
        except Exception as exc:
            warnings.append(f"Could not regenerate screening report #{row.get('id')}: {exc}")


def _add_project_reports(zip_file: zipfile.ZipFile, root: str, rows: list[dict[str, Any]], warnings: list[str], manifest: list[dict[str, Any]]) -> None:
    for row in rows:
        try:
            payload_json = row["report_payload_json"]
            payload = ProjectReportPayload.model_validate_json(payload_json)
            _write_json(zip_file, f"{root}/SCREENING_RESULTS/project_report_{row['id']}.json", json.loads(payload_json), manifest)
            _write_text(zip_file, f"{root}/TABLES/project_report_{row['id']}.csv", build_project_csv(payload), manifest, "csv")
            _write_bytes(zip_file, f"{root}/REPORTS/project_report_{row['id']}.pdf", build_project_pdf(payload), manifest, "pdf")
            _write_bytes(zip_file, f"{root}/REPORTS/project_report_{row['id']}.docx", build_project_docx(payload), manifest, "docx")
        except Exception as exc:
            warnings.append(f"Could not regenerate project report #{row.get('id')}: {exc}")


def _add_benchmark_runs(zip_file: zipfile.ZipFile, root: str, rows: list[dict[str, Any]], warnings: list[str], manifest: list[dict[str, Any]]) -> None:
    for row in rows:
        try:
            payload_json = row["result_payload_json"]
            payload = BenchmarkRunResponse.model_validate_json(payload_json)
            _write_json(zip_file, f"{root}/BENCHMARK_RESULTS/benchmark_{row['id']}.json", json.loads(payload_json), manifest)
            _write_text(zip_file, f"{root}/TABLES/benchmark_{row['id']}.csv", benchmark_csv(payload), manifest, "csv")
            _write_bytes(zip_file, f"{root}/REPORTS/benchmark_{row['id']}.pdf", benchmark_pdf(payload), manifest, "pdf")
            _write_bytes(zip_file, f"{root}/REPORTS/benchmark_{row['id']}.docx", benchmark_docx(payload), manifest, "docx")
        except Exception as exc:
            warnings.append(f"Could not regenerate benchmark run #{row.get('id')}: {exc}")


def _add_batch_runs(zip_file: zipfile.ZipFile, root: str, rows: list[dict[str, Any]], warnings: list[str], manifest: list[dict[str, Any]]) -> None:
    for row in rows:
        try:
            payload_json = row["result_payload_json"]
            payload = BatchLibraryScreenResponse.model_validate_json(payload_json)
            _write_json(zip_file, f"{root}/BATCH_RESULTS/batch_upload_{row['id']}.json", json.loads(payload_json), manifest)
            _write_text(zip_file, f"{root}/TABLES/batch_upload_{row['id']}.csv", batch_library_csv(payload), manifest, "csv")
            _write_bytes(zip_file, f"{root}/REPORTS/batch_upload_{row['id']}.pdf", batch_library_pdf(payload), manifest, "pdf")
            _write_bytes(zip_file, f"{root}/REPORTS/batch_upload_{row['id']}.docx", batch_library_docx(payload), manifest, "docx")
        except Exception as exc:
            warnings.append(f"Could not regenerate batch upload run #{row.get('id')}: {exc}")


def _save_export(filename: str, title: str | None, notes: str | None, sections: list[str], warnings: list[str], file_path: Path) -> int:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO research_exports (filename, title, notes, included_sections, warnings_json, file_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (filename, title, notes, json.dumps(sections), json.dumps(warnings), str(file_path)),
        )
        return int(cursor.lastrowid)


def create_research_export(payload: ResearchExportRequest) -> ResearchExportCreateResponse:
    init_db()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    created = _now()
    created_at = created.isoformat()
    stamp = _timestamp(created)
    filename = f"DrugScreen360_Research_Export_{stamp}.zip"
    root = f"DrugScreen360_Research_Export_{stamp}"
    file_path = EXPORT_DIR / filename
    warnings: list[str] = []
    sections: list[str] = []
    manifest: list[dict[str, Any]] = []

    screening_rows = _rows("screening_history") if payload.include_screening_history else []
    project_rows = _rows("project_reports")
    benchmark_rows = _rows("benchmark_runs") if payload.include_benchmark_runs else []
    batch_rows = _rows("batch_library_runs") if payload.include_batch_runs else []
    batch_candidate_rows = _rows("batch_screening_runs") if payload.include_batch_runs else []
    similarity_rows = _rows("similarity_searches")
    finder_rows = _rows("finder_searches")
    cache_status = cache_stats() if payload.include_cache_status else {"status": "not_included"}
    health = _backend_health_summary()
    local_validation = validate_local_admet_model()
    model_status = _model_status_json()
    project_detail = get_project(payload.project_id) if payload.project_id else None

    metadata = {
        "app_name": "DrugScreen360",
        "app_version": app_version(),
        "export_timestamp": created_at,
        "workflow_type": "research_export_package",
        "project_id": payload.project_id,
        "project_title": payload.project_title or (project_detail.title if project_detail else None),
        "notes": payload.notes or (project_detail.notes if project_detail else None),
        "backend_health_summary": health,
        "database_status": health.get("database"),
        "cache_status": health.get("cache") if payload.include_cache_status else "not_included",
    }

    with zipfile.ZipFile(file_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        _write_json(zip_file, f"{root}/PROJECT_METADATA.json", metadata, manifest)
        if project_detail:
            sections.append("PROJECT_WORKSPACE")
            dashboard = project_dashboard(project_detail.id)
            _write_json(zip_file, f"{root}/PROJECT_WORKSPACE/project_detail.json", project_detail.model_dump(), manifest)
            _write_json(zip_file, f"{root}/PROJECT_WORKSPACE/attached_items.json", [item.model_dump() for item in project_detail.items], manifest)
            _write_json(zip_file, f"{root}/PROJECT_WORKSPACE/project_summary.json", project_detail.model_dump(exclude={"items", "exports"}), manifest)
            _write_json(zip_file, f"{root}/PROJECT_WORKSPACE/project_dashboard.json", dashboard.model_dump(), manifest)
            _write_text(zip_file, f"{root}/PROJECT_WORKSPACE/candidate_decision_matrix.csv", project_decision_matrix_csv(project_detail.id), manifest, "csv")
            _write_text(zip_file, f"{root}/PROJECT_WORKSPACE/project_recommendations.md", project_recommendations_markdown(project_detail.id), manifest, "markdown")
            with get_connection() as connection:
                workspace_report_rows = connection.execute(
                    "SELECT * FROM project_workspace_reports WHERE project_id = ? ORDER BY datetime(created_at) DESC, id DESC",
                    (project_detail.id,),
                ).fetchall()
            if workspace_report_rows:
                for report_row in workspace_report_rows:
                    for column, file_type in [("filename_pdf", "pdf"), ("filename_docx", "docx"), ("filename_json", "json")]:
                        report_path = REPORT_DIR / report_row[column]
                        if report_path.exists():
                            _write_bytes(zip_file, f"{root}/PROJECT_WORKSPACE/REPORTS/{report_path.name}", report_path.read_bytes(), manifest, file_type)
                        else:
                            warnings.append(f"Project workspace report file was missing: {report_row[column]}")
            else:
                _write_text(zip_file, f"{root}/PROJECT_WORKSPACE/REPORTS/no_project_workspace_reports.txt", "No generated project workspace reports were found for this project.", manifest)
            if not dashboard.candidate_matrix:
                warnings.append("Project dashboard did not find candidate-level attached data for a decision matrix.")
            warnings.append("Project-scoped export includes project metadata and attached item list. Older records may not be fully project-linked.")
        _write_json(zip_file, f"{root}/MODEL_STATUS.json", model_status, manifest)
        _write_json(zip_file, f"{root}/LOCAL_MODEL_VALIDATION.json", local_validation, manifest)
        if payload.include_cache_status:
            _write_json(zip_file, f"{root}/CACHE_STATUS.json", cache_status, manifest)
            sections.append("CACHE_STATUS")

        if payload.include_screening_history:
            sections.append("SCREENING_RESULTS")
            _write_json(zip_file, f"{root}/SCREENING_RESULTS/screening_history_records.json", screening_rows, manifest)
            _add_screening_reports(zip_file, root, screening_rows, warnings, manifest) if payload.include_reports else None
        else:
            warnings.append("Screening history was not included by request.")

        sections.append("PROJECT_REPORTS")
        _write_json(zip_file, f"{root}/SCREENING_RESULTS/project_report_records.json", project_rows, manifest)
        _add_project_reports(zip_file, root, project_rows, warnings, manifest) if payload.include_reports else None

        if payload.include_benchmark_runs:
            sections.append("BENCHMARK_RESULTS")
            _write_json(zip_file, f"{root}/BENCHMARK_RESULTS/benchmark_run_records.json", benchmark_rows, manifest)
            _add_benchmark_runs(zip_file, root, benchmark_rows, warnings, manifest) if payload.include_reports else None

        if payload.include_batch_runs:
            sections.append("BATCH_RESULTS")
            _write_json(zip_file, f"{root}/BATCH_RESULTS/batch_upload_run_records.json", batch_rows, manifest)
            _write_json(zip_file, f"{root}/BATCH_RESULTS/finder_similarity_batch_run_records.json", batch_candidate_rows, manifest)
            _add_batch_runs(zip_file, root, batch_rows, warnings, manifest) if payload.include_reports else None

        _write_json(zip_file, f"{root}/SCREENING_RESULTS/similarity_search_records.json", similarity_rows, manifest)
        _write_json(zip_file, f"{root}/SCREENING_RESULTS/finder_search_records.json", finder_rows, manifest)

        screening_summary = [
            {
                "id": row.get("id"),
                "input_query": row.get("input_query"),
                "input_type": row.get("input_type"),
                "compound_name": row.get("compound_name"),
                "pubchem_cid": row.get("pubchem_cid"),
                "decision": row.get("decision"),
                "created_at": row.get("created_at"),
            }
            for row in screening_rows
        ]
        benchmark_summary = [
            {
                "id": row.get("id"),
                "title": row.get("title"),
                "selected_group": row.get("selected_group"),
                "total_tested": row.get("total_tested"),
                "passed": row.get("passed"),
                "review": row.get("review"),
                "failed": row.get("failed"),
                "created_at": row.get("created_at"),
            }
            for row in benchmark_rows
        ]
        batch_summary = [
            {
                "id": row.get("id"),
                "batch_id": row.get("batch_id"),
                "screened_count": row.get("screened_count"),
                "failed_count": row.get("failed_count"),
                "created_at": row.get("created_at"),
            }
            for row in batch_rows
        ]
        model_rows = [
            {
                "model_id": model.get("model_id"),
                "status": model.get("status"),
                "model_type": model.get("model_type"),
                "version": model.get("version"),
                "warning": model.get("warning"),
            }
            for model in model_status["models"]
        ]
        _write_text(zip_file, f"{root}/TABLES/screening_summary.csv", _csv_text(screening_summary, ["id", "input_query", "input_type", "compound_name", "pubchem_cid", "decision", "created_at"]), manifest, "csv")
        _write_text(zip_file, f"{root}/TABLES/model_status.csv", _csv_text(model_rows, ["model_id", "status", "model_type", "version", "warning"]), manifest, "csv")
        _write_text(zip_file, f"{root}/TABLES/benchmark_summary.csv", _csv_text(benchmark_summary, ["id", "title", "selected_group", "total_tested", "passed", "review", "failed", "created_at"]), manifest, "csv")
        _write_text(zip_file, f"{root}/TABLES/batch_summary.csv", _csv_text(batch_summary, ["id", "batch_id", "screened_count", "failed_count", "created_at"]), manifest, "csv")
        sections.append("TABLES")

        _write_text(zip_file, f"{root}/DISCLAIMERS/scientific_limitations.md", _scientific_limitations(), manifest, "markdown")
        _write_text(zip_file, f"{root}/REPRODUCIBILITY/environment_summary.md", _environment_summary(created_at), manifest, "markdown")
        sections.extend(["DISCLAIMERS", "REPRODUCIBILITY", "MODEL_STATUS", "LOCAL_MODEL_VALIDATION"])

        if not payload.include_reports:
            warnings.append("Report regeneration was skipped by request.")
        if not project_rows:
            warnings.append("No stored project reports were found.")
        if not screening_rows and payload.include_screening_history:
            warnings.append("No stored screening history records were found.")
        if not batch_rows and payload.include_batch_runs:
            warnings.append("No stored batch upload runs were found.")
        if not benchmark_rows and payload.include_benchmark_runs:
            warnings.append("No stored benchmark runs were found.")

        _write_text(zip_file, f"{root}/README_EXPORT.md", _readme_export(payload.project_title, warnings), manifest, "markdown")
        _write_json(zip_file, f"{root}/MANIFEST.json", {"created_at": created_at, "files": manifest, "warnings": warnings}, manifest)

    sections = list(dict.fromkeys(sections))
    export_id = _save_export(filename, payload.project_title, payload.notes, sections, warnings, file_path)
    if payload.project_id:
        link_project_export(payload.project_id, export_id, filename)
    return ResearchExportCreateResponse(
        export_id=export_id,
        filename=filename,
        created_at=created_at,
        included_sections=sections,
        warnings=warnings,
        download_url=f"/api/research-export/{export_id}/download",
    )


def list_research_exports() -> list[ResearchExportListItem]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM research_exports ORDER BY datetime(created_at) DESC, id DESC LIMIT 25"
        ).fetchall()
    return [
        ResearchExportListItem(
            export_id=row["id"],
            filename=row["filename"],
            created_at=row["created_at"],
            included_sections=json.loads(row["included_sections"]),
            warnings=json.loads(row["warnings_json"]),
            download_url=f"/api/research-export/{row['id']}/download",
        )
        for row in rows
    ]


def get_research_export_path(export_id: int) -> Path | None:
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT file_path FROM research_exports WHERE id = ?", (export_id,)).fetchone()
    if not row:
        return None
    path = Path(row["file_path"])
    if not path.exists() or path.suffix.lower() != ".zip":
        return None
    return path
