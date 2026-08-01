from fastapi import APIRouter, HTTPException, Query

from app.database import get_connection
from app.models.scientific_engine_models import ScientificEngineExecutionRequest
from app.services.scientific_engine_adapter_service import ScientificEngineExecutionService, default_adapter_registry
from app.services.scientific_job_service import create_job

router = APIRouter(tags=["scientific-engine-executions"])


def _service(): return ScientificEngineExecutionService()


@router.post("/scientific-engine-executions/validate")
def validate_execution(request: ScientificEngineExecutionRequest):
    return _service().run(request, execute=False)


@router.post("/scientific-engine-executions/execute")
def execute(request: ScientificEngineExecutionRequest):
    if request.execution_mode == "ASYNC":
        raise HTTPException(409, {"code": "ASYNC_REQUIRED", "message": "Use the jobs endpoint for asynchronous execution."})
    return _service().run(request)


@router.post("/scientific-engine-executions/jobs", status_code=202)
def submit_job(request: ScientificEngineExecutionRequest):
    safe = {"request_hash": __import__("hashlib").sha256(request.model_dump_json().encode()).hexdigest(), "engine_id": request.engine_id, "engine_version": request.engine_version, "task_type": request.task_type, "endpoint": request.endpoint}
    return create_job("SCIENTIFIC_ENGINE_EXECUTION", safe, lambda: _service().run(request), {"contract_version": request.contract_version})


@router.get("/scientific-engine-executions")
def list_executions(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    with get_connection() as connection:
        total = connection.execute("SELECT COUNT(*) FROM scientific_engine_executions").fetchone()[0]
        rows = connection.execute("SELECT * FROM scientific_engine_executions ORDER BY started_at DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
    return {"items": [dict(row) for row in rows], "total": total, "limit": limit, "offset": offset}


@router.get("/scientific-engine-executions/{execution_id}")
def execution_detail(execution_id: str):
    with get_connection() as connection: row = connection.execute("SELECT * FROM scientific_engine_executions WHERE execution_id = ?", (execution_id,)).fetchone()
    if not row: raise HTTPException(404, "Scientific engine execution not found")
    return dict(row)


@router.get("/scientific-engine-adapters")
def list_adapters(): return {"items": default_adapter_registry().list()}


@router.get("/scientific-engine-adapters/{adapter_id}")
def adapter_detail(adapter_id: str):
    item = next((item for item in default_adapter_registry().list() if item["adapter_id"] == adapter_id), None)
    if not item: raise HTTPException(404, "Scientific engine adapter not found")
    return item
