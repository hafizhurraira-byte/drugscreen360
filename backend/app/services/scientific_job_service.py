import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import HTTPException

from app.database import get_connection, init_db


_EXECUTOR = ThreadPoolExecutor(max_workers=2)
_RUNNING: dict[int, Any] = {}
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_job(row) -> dict[str, Any]:
    return {
        "job_id": row["id"],
        "job_type": row["job_type"],
        "status": row["status"],
        "progress": row["progress"],
        "input_snapshot": json.loads(row["input_snapshot_json"] or "{}"),
        "output_references": json.loads(row["output_references_json"] or "{}"),
        "error": row["error"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "logs": json.loads(row["logs_json"] or "[]"),
        "provenance": json.loads(row["provenance_json"] or "{}"),
    }


def _update(job_id: int, **values: Any) -> None:
    if not values:
        return
    assignments = ", ".join(f"{key} = ?" for key in values)
    params = list(values.values()) + [job_id]
    with get_connection() as connection:
        connection.execute(f"UPDATE scientific_jobs SET {assignments} WHERE id = ?", params)


def create_job(job_type: str, input_snapshot: dict[str, Any], runner: Callable[[], Any], provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO scientific_jobs (job_type, status, progress, input_snapshot_json, provenance_json)
            VALUES (?, 'QUEUED', 0, ?, ?)
            """,
            (job_type, json.dumps(input_snapshot), json.dumps(provenance or {})),
        )
        job_id = int(cursor.lastrowid)

    def run():
        with get_connection() as connection:
            row = connection.execute("SELECT status FROM scientific_jobs WHERE id = ?", (job_id,)).fetchone()
        if row and row["status"] == "CANCELLED":
            return
        _update(job_id, status="RUNNING", progress=0.1, started_at=_now(), logs_json=json.dumps(["Job started."]))
        try:
            output = runner()
            _update(
                job_id,
                status="SUCCEEDED",
                progress=1.0,
                ended_at=_now(),
                output_references_json=json.dumps(output, default=str),
                logs_json=json.dumps(["Job started.", "Job completed."]),
            )
        except Exception as exc:
            _update(job_id, status="FAILED", ended_at=_now(), error=str(exc), logs_json=json.dumps(["Job started.", f"Job failed: {exc}"]))

    with _LOCK:
        _RUNNING[job_id] = _EXECUTOR.submit(run)
    return get_job(job_id)


def list_jobs() -> list[dict[str, Any]]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM scientific_jobs ORDER BY id DESC LIMIT 50").fetchall()
    return [_row_to_job(row) for row in rows]


def get_job(job_id: int) -> dict[str, Any]:
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM scientific_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Scientific job not found.")
    return _row_to_job(row)


def cancel_job(job_id: int) -> dict[str, Any]:
    job = get_job(job_id)
    if job["status"] not in {"QUEUED", "RUNNING"}:
        return job
    future = _RUNNING.get(job_id)
    if future and not future.cancel():
        raise HTTPException(status_code=409, detail="Job is already running and cannot be interrupted safely.")
    _update(job_id, status="CANCELLED", ended_at=_now(), progress=job["progress"], logs_json=json.dumps(job["logs"] + ["Job cancelled."]))
    return get_job(job_id)

