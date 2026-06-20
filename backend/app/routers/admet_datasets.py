from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response

from app.models.admet_dataset_models import DatasetRecord, DatasetUploadResponse, DatasetValidationSummary
from app.services.admet_dataset_service import (
    curation_report,
    curated_csv,
    dataset_summary,
    get_dataset_records,
    get_dataset_row,
    list_admet_datasets,
    upload_admet_dataset,
)

router = APIRouter(prefix="/admet-datasets", tags=["admet-datasets"])


@router.post("/upload", response_model=DatasetUploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    dataset_name: str = Form(...),
    label_column: str = Form(...),
    smiles_column: str = Form("smiles"),
    task_name: str | None = Form(None),
    compound_name_column: str | None = Form(None),
    notes: str | None = Form(None),
    project_id: int | None = Form(None),
):
    content = await file.read()
    return upload_admet_dataset(
        file.filename or "admet_dataset",
        content,
        dataset_name,
        task_name,
        label_column,
        smiles_column,
        compound_name_column,
        notes,
        project_id,
    )


@router.get("/list")
def list_datasets():
    return list_admet_datasets()


@router.get("/{dataset_id}")
def dataset_detail(dataset_id: int):
    dataset = get_dataset_row(dataset_id)
    dataset["summary"] = dataset_summary(dataset_id).model_dump()
    return dataset


@router.get("/{dataset_id}/records", response_model=list[DatasetRecord])
def dataset_records(dataset_id: int):
    return get_dataset_records(dataset_id)


@router.get("/{dataset_id}/summary", response_model=DatasetValidationSummary)
def dataset_summary_endpoint(dataset_id: int):
    return dataset_summary(dataset_id)


@router.get("/{dataset_id}/curated.csv")
def dataset_curated_csv(dataset_id: int):
    return Response(
        curated_csv(dataset_id),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="drugscreen360-admet-dataset-{dataset_id}-curated.csv"'},
    )


@router.get("/{dataset_id}/curation-report.json")
def dataset_curation_report(dataset_id: int):
    return curation_report(dataset_id)
