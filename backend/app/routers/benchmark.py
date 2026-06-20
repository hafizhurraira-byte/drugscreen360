from io import BytesIO

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.models.benchmark_models import BenchmarkRunRequest, BenchmarkRunResponse, BenchmarkRunStored
from app.services.benchmark_service import (
    benchmark_csv,
    benchmark_docx,
    benchmark_pdf,
    get_benchmark_run,
    list_benchmark_runs,
    load_benchmark_groups,
    run_benchmark,
)

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@router.get("/compounds")
def benchmark_compounds():
    return {"groups": {group: [item.model_dump() for item in items] for group, items in load_benchmark_groups().items()}}


@router.post("/run", response_model=BenchmarkRunResponse)
def run_benchmark_endpoint(payload: BenchmarkRunRequest):
    return run_benchmark(payload.selected_ids, payload.group_name, payload.max_items)


@router.get("/runs", response_model=list[BenchmarkRunStored])
def benchmark_runs():
    return list_benchmark_runs()


@router.get("/runs/{run_id}", response_model=BenchmarkRunStored)
def benchmark_run_detail(run_id: int):
    run = get_benchmark_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Benchmark run not found.")
    return run


@router.get("/runs/{run_id}/json")
def benchmark_json(run_id: int):
    run = get_benchmark_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Benchmark run not found.")
    return run.payload


@router.get("/runs/{run_id}/csv")
def benchmark_csv_export(run_id: int):
    run = get_benchmark_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Benchmark run not found.")
    return Response(
        benchmark_csv(run.payload),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-benchmark-{run_id}.csv"'},
    )


@router.get("/runs/{run_id}/pdf")
def benchmark_pdf_export(run_id: int):
    run = get_benchmark_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Benchmark run not found.")
    return StreamingResponse(
        BytesIO(benchmark_pdf(run.payload)),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-benchmark-{run_id}.pdf"'},
    )


@router.get("/runs/{run_id}/docx")
def benchmark_docx_export(run_id: int):
    run = get_benchmark_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Benchmark run not found.")
    return StreamingResponse(
        BytesIO(benchmark_docx(run.payload)),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-benchmark-{run_id}.docx"'},
    )
