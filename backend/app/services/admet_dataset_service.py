import csv
import json
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from rdkit import Chem

from app.database import get_connection, init_db
from app.models.admet_dataset_models import DatasetRecord, DatasetUploadResponse, DatasetValidationSummary
from app.models.project_workspace_models import ProjectAttachRequest
from app.services.descriptors import calculate_descriptors, parse_smiles
from app.services.project_workspace_service import attach_project_item

MAX_DATASET_SIZE = 8 * 1024 * 1024
MAX_DATASET_ROWS = 5000
ALLOWED_EXTENSIONS = {".csv", ".tsv", ".txt", ".sdf"}
LIMITATIONS = [
    "ADMET Dataset Import prepares labeled datasets only. It does not train models or generate predictions.",
    "Labels are imported from the uploaded file only; DrugScreen360 does not invent missing ADMET values.",
    "Curated datasets still require scientific review, assay provenance checks, and licensing review before model training.",
]


def _descriptor_dict(smiles: str) -> dict[str, Any]:
    descriptors = calculate_descriptors(smiles).model_dump()
    return {
        "molecular_weight": descriptors.get("molecular_weight"),
        "logp": descriptors.get("logp"),
        "tpsa": descriptors.get("tpsa"),
        "hbd": descriptors.get("hydrogen_bond_donors"),
        "hba": descriptors.get("hydrogen_bond_acceptors"),
        "rotatable_bonds": descriptors.get("rotatable_bonds"),
        "ring_count": descriptors.get("ring_count"),
        "aromatic_ring_count": descriptors.get("aromatic_ring_count"),
        "formal_charge": descriptors.get("formal_charge"),
        "fraction_csp3": descriptors.get("fraction_csp3"),
    }


def _canonicalize(smiles: str) -> str:
    mol = parse_smiles(smiles.strip())
    return Chem.MolToSmiles(mol, canonical=True)


def _read_table(file_name: str, content: bytes) -> tuple[list[dict[str, Any]], list[str]]:
    extension = Path(file_name).suffix.lower()
    text = content.decode("utf-8-sig", errors="replace")
    delimiter = "\t" if extension in {".tsv", ".txt"} and "\t" in text.splitlines()[0] else ","
    reader = csv.DictReader(StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="Dataset is empty or missing a header row.")
    return [dict(row, row_number=index) for index, row in enumerate(reader, start=2)], list(reader.fieldnames)


def _read_sdf(content: bytes, label_column: str, smiles_column: str, compound_name_column: str | None) -> tuple[list[dict[str, Any]], list[str]]:
    supplier = Chem.ForwardSDMolSupplier(BytesIO(content), sanitize=True, removeHs=False)
    rows = []
    fields = {label_column, smiles_column}
    if compound_name_column:
        fields.add(compound_name_column)
    for index, mol in enumerate(supplier, start=1):
        if mol is None:
            rows.append({"row_number": index, smiles_column: "", label_column: "", "_parse_error": "RDKit could not parse SDF molecule."})
            continue
        props = mol.GetPropsAsDict()
        fields.update(str(key) for key in props.keys())
        rows.append(
            {
                **{str(key): value for key, value in props.items()},
                "row_number": index,
                smiles_column: Chem.MolToSmiles(mol, canonical=True),
                compound_name_column or "compound_name": mol.GetProp("_Name") if mol.HasProp("_Name") else props.get(compound_name_column or "compound_name"),
            }
        )
    return rows, list(fields)


def _require_column(columns: list[str], column_name: str, label: str) -> None:
    if column_name not in columns:
        raise HTTPException(status_code=422, detail=f"{label} column '{column_name}' was not found in the uploaded dataset.")


def _build_summary(records: list[DatasetRecord]) -> DatasetValidationSummary:
    label_distribution: dict[str, int] = {}
    canonical_values = set()
    descriptor_success = 0
    for record in records:
        if record.label_value not in (None, ""):
            label_distribution[str(record.label_value)] = label_distribution.get(str(record.label_value), 0) + 1
        if record.canonical_smiles:
            canonical_values.add(record.canonical_smiles)
        if record.descriptors:
            descriptor_success += 1
    invalid_smiles = sum(1 for record in records if record.invalid_reason and "SMILES" in record.invalid_reason)
    missing_labels = sum(1 for record in records if record.invalid_reason and "label" in record.invalid_reason.lower())
    duplicates = sum(1 for record in records if record.duplicate_group)
    warnings = []
    if invalid_smiles:
        warnings.append(f"{invalid_smiles} row(s) have invalid or missing SMILES.")
    if missing_labels:
        warnings.append(f"{missing_labels} row(s) have missing labels.")
    if duplicates:
        warnings.append(f"{duplicates} duplicate canonical molecule row(s) detected.")
    return DatasetValidationSummary(
        total_rows=len(records),
        valid_molecules=sum(1 for record in records if record.is_valid),
        invalid_smiles=invalid_smiles,
        missing_labels=missing_labels,
        duplicate_molecules=duplicates,
        unique_canonical_molecules=len(canonical_values),
        label_distribution=label_distribution,
        descriptor_success_count=descriptor_success,
        descriptor_failure_count=len(records) - descriptor_success,
        warnings=warnings,
        recommended_next_steps=[
            "Review invalid SMILES and missing-label rows before model training.",
            "Review duplicate molecules and choose a documented aggregation strategy.",
            "Confirm assay definitions, units, thresholds, and dataset licensing before training any real model.",
        ],
    )


def upload_admet_dataset(
    file_name: str,
    content: bytes,
    dataset_name: str,
    task_name: str | None,
    label_column: str,
    smiles_column: str,
    compound_name_column: str | None = None,
    notes: str | None = None,
    project_id: int | None = None,
) -> DatasetUploadResponse:
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded dataset is empty.")
    if len(content) > MAX_DATASET_SIZE:
        raise HTTPException(status_code=413, detail="Dataset is too large. Maximum size is 8 MB.")
    extension = Path(file_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported dataset type. Use CSV, TSV, TXT, or SDF.")
    if extension == ".sdf":
        raw_rows, columns = _read_sdf(content, label_column, smiles_column, compound_name_column)
    else:
        raw_rows, columns = _read_table(file_name, content)
    _require_column(columns, smiles_column, "SMILES")
    _require_column(columns, label_column, "Label")
    if compound_name_column:
        _require_column(columns, compound_name_column, "Compound name")
    if len(raw_rows) > MAX_DATASET_ROWS:
        raise HTTPException(status_code=422, detail=f"Too many rows. Maximum ADMET curation limit is {MAX_DATASET_ROWS}.")

    seen: dict[str, int] = {}
    records = []
    for raw in raw_rows:
        row_number = int(raw.get("row_number") or len(records) + 1)
        original_smiles = str(raw.get(smiles_column) or "").strip()
        label_value = str(raw.get(label_column) or "").strip()
        compound_name = str(raw.get(compound_name_column) or "").strip() if compound_name_column else str(raw.get("compound_name") or raw.get("name") or "").strip()
        invalid_reasons = []
        canonical = None
        descriptors = None
        duplicate_group = None
        if raw.get("_parse_error"):
            invalid_reasons.append(str(raw["_parse_error"]))
        if not original_smiles:
            invalid_reasons.append("Missing SMILES.")
        else:
            try:
                canonical = _canonicalize(original_smiles)
                descriptors = _descriptor_dict(canonical)
                if canonical in seen:
                    duplicate_group = f"duplicate_of_row_{seen[canonical]}"
                else:
                    seen[canonical] = row_number
            except Exception as exc:
                invalid_reasons.append(f"Invalid SMILES: {exc}")
        if not label_value:
            invalid_reasons.append("Missing label value.")
        records.append(
            DatasetRecord(
                row_number=row_number,
                compound_name=compound_name or None,
                original_smiles=original_smiles or None,
                canonical_smiles=canonical,
                label_value=label_value or None,
                is_valid=not invalid_reasons,
                invalid_reason="; ".join(invalid_reasons) or None,
                duplicate_group=duplicate_group,
                descriptors=descriptors,
            )
        )

    summary = _build_summary(records)
    status = "ready_for_review" if summary.valid_molecules else "needs_curation"
    dataset_id = _save_dataset(dataset_name, task_name, label_column, file_name, status, notes, records, summary)
    if project_id:
        attach_project_item(
            project_id,
            ProjectAttachRequest(
                item_type="admet_dataset",
                item_id=str(dataset_id),
                item_title=dataset_name,
                metadata={
                    "workflow_type": "admet_dataset_curation",
                    "task_name": task_name,
                    "label_column": label_column,
                    "record_count": summary.total_rows,
                    "valid_count": summary.valid_molecules,
                    "invalid_count": summary.total_rows - summary.valid_molecules,
                    "duplicate_count": summary.duplicate_molecules,
                    "decision": "dataset prepared for review",
                },
            ),
        )
    return DatasetUploadResponse(
        dataset_id=dataset_id,
        name=dataset_name,
        task_name=task_name,
        label_column=label_column,
        original_filename=file_name,
        record_count=summary.total_rows,
        valid_count=summary.valid_molecules,
        invalid_count=summary.total_rows - summary.valid_molecules,
        duplicate_count=summary.duplicate_molecules,
        status=status,
        summary=summary,
        records_preview=[record.model_copy(update={"dataset_id": dataset_id}) for record in records[:50]],
        limitations=LIMITATIONS,
    )


def _save_dataset(name: str, task_name: str | None, label_column: str, file_name: str, status: str, notes: str | None, records: list[DatasetRecord], summary: DatasetValidationSummary) -> int:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO admet_datasets (
                name, task_name, label_column, original_filename, record_count,
                valid_count, invalid_count, duplicate_count, status, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                task_name,
                label_column,
                file_name,
                summary.total_rows,
                summary.valid_molecules,
                summary.total_rows - summary.valid_molecules,
                summary.duplicate_molecules,
                status,
                notes,
            ),
        )
        dataset_id = int(cursor.lastrowid)
        for record in records:
            connection.execute(
                """
                INSERT INTO admet_dataset_records (
                    dataset_id, compound_name, original_smiles, canonical_smiles, label_value,
                    is_valid, invalid_reason, duplicate_group, descriptors_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_id,
                    record.compound_name,
                    record.original_smiles,
                    record.canonical_smiles,
                    record.label_value,
                    1 if record.is_valid else 0,
                    record.invalid_reason,
                    record.duplicate_group,
                    json.dumps(record.descriptors) if record.descriptors else None,
                ),
            )
    return dataset_id


def _record_from_row(row) -> DatasetRecord:
    return DatasetRecord(
        id=row["id"],
        dataset_id=row["dataset_id"],
        compound_name=row["compound_name"],
        original_smiles=row["original_smiles"],
        canonical_smiles=row["canonical_smiles"],
        label_value=row["label_value"],
        is_valid=bool(row["is_valid"]),
        invalid_reason=row["invalid_reason"],
        duplicate_group=row["duplicate_group"],
        descriptors=json.loads(row["descriptors_json"]) if row["descriptors_json"] else None,
        created_at=row["created_at"],
    )


def list_admet_datasets() -> list[dict[str, Any]]:
    init_db()
    with get_connection() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM admet_datasets ORDER BY datetime(created_at) DESC, id DESC").fetchall()]


def get_dataset_row(dataset_id: int) -> dict[str, Any]:
    init_db()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM admet_datasets WHERE id = ?", (dataset_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="ADMET dataset not found.")
    return dict(row)


def get_dataset_records(dataset_id: int) -> list[DatasetRecord]:
    get_dataset_row(dataset_id)
    init_db()
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM admet_dataset_records WHERE dataset_id = ? ORDER BY id", (dataset_id,)).fetchall()
    return [_record_from_row(row) for row in rows]


def dataset_summary(dataset_id: int) -> DatasetValidationSummary:
    return _build_summary(get_dataset_records(dataset_id))


def curated_csv(dataset_id: int) -> str:
    records = get_dataset_records(dataset_id)
    descriptor_keys = ["molecular_weight", "logp", "tpsa", "hbd", "hba", "rotatable_bonds", "ring_count", "aromatic_ring_count", "formal_charge", "fraction_csp3"]
    headers = ["compound_name", "original_smiles", "canonical_smiles", "label_value", "is_valid", "invalid_reason", "duplicate_group", *descriptor_keys]
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        row = record.model_dump()
        descriptors = row.pop("descriptors") or {}
        row.update(descriptors)
        writer.writerow(row)
    return output.getvalue()


def curation_report(dataset_id: int) -> dict[str, Any]:
    dataset = get_dataset_row(dataset_id)
    summary = dataset_summary(dataset_id)
    return {
        "dataset": dataset,
        "summary": summary.model_dump(),
        "limitations": LIMITATIONS,
        "scientific_scope": "Dataset curation only. No model training and no prediction outputs were generated.",
    }
