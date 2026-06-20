from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.models.batch_library_models import BatchLibraryScreenRequest, BatchLibraryScreenResponse, BatchLibraryRunStored, BatchParseResponse
from app.services.batch_library_service import (
    batch_library_csv,
    batch_library_docx,
    batch_library_pdf,
    example_csv,
    example_smi,
    get_batch_library_run,
    list_batch_library_runs,
    parse_library_file,
    screen_batch_library,
)

router = APIRouter(prefix="/batch-library", tags=["batch-library"])


@router.post("/parse", response_model=BatchParseResponse)
async def parse_batch_library(file: UploadFile = File(...)):
    content = await file.read()
    return parse_library_file(file.filename or "uploaded_library", content)


@router.post("/screen", response_model=BatchLibraryScreenResponse)
def screen_batch_library_endpoint(payload: BatchLibraryScreenRequest):
    return screen_batch_library(payload.batch_id, payload.compounds, payload.max_compounds, payload.run_model_predictions)


@router.get("/runs", response_model=list[BatchLibraryRunStored])
def batch_library_runs():
    return list_batch_library_runs()


@router.get("/runs/{run_id}", response_model=BatchLibraryRunStored)
def batch_library_run_detail(run_id: int):
    run = get_batch_library_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Batch library run not found.")
    return run


@router.get("/runs/{run_id}/json")
def batch_library_json(run_id: int):
    run = get_batch_library_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Batch library run not found.")
    return run.payload


@router.get("/runs/{run_id}/csv")
def batch_library_csv_export(run_id: int):
    run = get_batch_library_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Batch library run not found.")
    return Response(
        batch_library_csv(run.payload),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-batch-library-{run_id}.csv"'},
    )


@router.get("/runs/{run_id}/pdf")
def batch_library_pdf_export(run_id: int):
    run = get_batch_library_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Batch library run not found.")
    return StreamingResponse(
        BytesIO(batch_library_pdf(run.payload)),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-batch-library-{run_id}.pdf"'},
    )


@router.get("/runs/{run_id}/docx")
def batch_library_docx_export(run_id: int):
    run = get_batch_library_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Batch library run not found.")
    return StreamingResponse(
        BytesIO(batch_library_docx(run.payload)),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-batch-library-{run_id}.docx"'},
    )


@router.get("/examples/example_compounds.csv")
def download_example_csv():
    return Response(
        example_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="example_compounds.csv"'},
    )


@router.get("/examples/example_compounds.smi")
def download_example_smi():
    return Response(
        example_smi(),
        media_type="text/plain",
        headers={"Content-Disposition": 'attachment; filename="example_compounds.smi"'},
    )
