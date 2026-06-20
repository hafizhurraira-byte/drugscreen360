import json
from typing import Any

from fastapi import HTTPException

from app.database import get_connection, init_db
from app.models.project_workspace_models import (
    ProjectAttachRequest,
    ProjectCreateRequest,
    ProjectDetail,
    ProjectItem,
    ProjectSummary,
    ProjectUpdateRequest,
)
from app.services.model_registry import model_status_response

PROJECT_LIMITATIONS = [
    "Saved projects organize local DrugScreen360 records only.",
    "Project workspaces do not prove safety, efficacy, clinical success, regulatory approval, or market readiness.",
    "Attached items retain their original computational and rule-based limitations.",
]


def _model_summary() -> dict[str, Any]:
    status = model_status_response()
    return {
        "available_models": [model.model_id for model in status["available_models"]],
        "unavailable_models": [model.model_id for model in status["unavailable_models"]],
        "limitations": status["limitations"],
    }


def _project_from_row(row, item_count: int = 0, export_count: int = 0, latest_activity: str | None = None) -> ProjectSummary:
    return ProjectSummary(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        disease_area=row["disease_area"],
        target_name=row["target_name"],
        project_type=row["project_type"],
        status=row["status"],
        notes=row["notes"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        attached_item_count=item_count,
        export_count=export_count,
        latest_activity=latest_activity or row["updated_at"],
        model_status_summary=_model_summary(),
        warnings=[] if row["status"] != "archived" else ["Project is archived."],
        limitations=PROJECT_LIMITATIONS,
    )


def _item_from_row(row) -> ProjectItem:
    return ProjectItem(
        id=row["id"],
        project_id=row["project_id"],
        item_type=row["item_type"],
        item_id=row["item_id"],
        item_title=row["item_title"],
        metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
        created_at=row["created_at"],
    )


def create_project(payload: ProjectCreateRequest) -> ProjectSummary:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO projects (title, description, disease_area, target_name, project_type, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.title,
                payload.description,
                payload.disease_area,
                payload.target_name,
                payload.project_type,
                payload.status,
                payload.notes,
            ),
        )
        project_id = int(cursor.lastrowid)
        row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _project_from_row(row)


def _project_row(project_id: int):
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return row


def list_projects() -> list[ProjectSummary]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM projects ORDER BY datetime(updated_at) DESC, id DESC").fetchall()
        summaries = []
        for row in rows:
            item_count = connection.execute("SELECT COUNT(*) AS count FROM project_items WHERE project_id = ?", (row["id"],)).fetchone()["count"]
            export_count = connection.execute("SELECT COUNT(*) AS count FROM project_exports WHERE project_id = ?", (row["id"],)).fetchone()["count"]
            latest = connection.execute(
                """
                SELECT MAX(activity) AS latest FROM (
                    SELECT updated_at AS activity FROM projects WHERE id = ?
                    UNION ALL
                    SELECT created_at AS activity FROM project_items WHERE project_id = ?
                    UNION ALL
                    SELECT created_at AS activity FROM project_exports WHERE project_id = ?
                )
                """,
                (row["id"], row["id"], row["id"]),
            ).fetchone()["latest"]
            summaries.append(_project_from_row(row, item_count, export_count, latest))
    return summaries


def get_project(project_id: int) -> ProjectDetail:
    row = _project_row(project_id)
    init_db()
    with get_connection() as connection:
        item_rows = connection.execute("SELECT * FROM project_items WHERE project_id = ? ORDER BY datetime(created_at) DESC, id DESC", (project_id,)).fetchall()
        export_rows = connection.execute("SELECT * FROM project_exports WHERE project_id = ? ORDER BY datetime(created_at) DESC, id DESC", (project_id,)).fetchall()
        item_count = len(item_rows)
        export_count = len(export_rows)
        latest = connection.execute(
            """
            SELECT MAX(activity) AS latest FROM (
                SELECT updated_at AS activity FROM projects WHERE id = ?
                UNION ALL
                SELECT created_at AS activity FROM project_items WHERE project_id = ?
                UNION ALL
                SELECT created_at AS activity FROM project_exports WHERE project_id = ?
            )
            """,
            (project_id, project_id, project_id),
        ).fetchone()["latest"]
    summary = _project_from_row(row, item_count, export_count, latest)
    return ProjectDetail(
        **summary.model_dump(),
        items=[_item_from_row(item) for item in item_rows],
        exports=[dict(item) for item in export_rows],
    )


def update_project(project_id: int, payload: ProjectUpdateRequest) -> ProjectSummary:
    _project_row(project_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return get_project(project_id)
    allowed = ["title", "description", "disease_area", "target_name", "project_type", "status", "notes"]
    assignments = [f"{key} = ?" for key in allowed if key in updates]
    values = [updates[key] for key in allowed if key in updates]
    values.append(project_id)
    init_db()
    with get_connection() as connection:
        connection.execute(
            f"UPDATE projects SET {', '.join(assignments)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )
        row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _project_from_row(row)


def archive_project(project_id: int) -> ProjectSummary:
    return update_project(project_id, ProjectUpdateRequest(status="archived"))


def attach_project_item(project_id: int, payload: ProjectAttachRequest) -> ProjectItem:
    _project_row(project_id)
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO project_items (project_id, item_type, item_id, item_title, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, payload.item_type, payload.item_id, payload.item_title, json.dumps(payload.metadata)),
        )
        connection.execute("UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
        row = connection.execute("SELECT * FROM project_items WHERE id = ?", (int(cursor.lastrowid),)).fetchone()
    return _item_from_row(row)


def project_summary(project_id: int) -> ProjectSummary:
    detail = get_project(project_id)
    return ProjectSummary(**detail.model_dump(exclude={"items", "exports"}))


def link_project_export(project_id: int, export_id: int, filename: str) -> None:
    _project_row(project_id)
    init_db()
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO project_exports (project_id, export_id, filename) VALUES (?, ?, ?)",
            (project_id, export_id, filename),
        )
        connection.execute("UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
