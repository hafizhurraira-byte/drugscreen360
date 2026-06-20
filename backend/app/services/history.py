import json

from app.database import get_connection, init_db
from app.models.schemas import ScreeningHistoryDetail, ScreeningHistoryItem, ScreeningReport


def save_screening_report(report: ScreeningReport) -> int:
    init_db()
    descriptor_summary = report.physicochemical_properties.model_dump()
    drug_likeness_result = report.drug_likeness.model_dump()
    decision = report.go_no_go_recommendation["decision"]

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO screening_history (
                input_query,
                input_type,
                compound_name,
                pubchem_cid,
                canonical_smiles,
                descriptor_summary,
                drug_likeness_result,
                decision,
                report_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.input.query,
                report.input.input_type,
                report.compound_identity.compound_name,
                report.compound_identity.pubchem_cid,
                report.compound_identity.canonical_smiles,
                json.dumps(descriptor_summary),
                json.dumps(drug_likeness_result),
                decision,
                report.model_dump_json(),
            ),
        )
        return int(cursor.lastrowid)


def update_report_id(screening_id: int, report: ScreeningReport) -> None:
    report.screening_id = screening_id
    with get_connection() as connection:
        connection.execute(
            "UPDATE screening_history SET report_json = ? WHERE id = ?",
            (report.model_dump_json(), screening_id),
        )


def list_history() -> list[ScreeningHistoryItem]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, input_query, input_type, compound_name, pubchem_cid, canonical_smiles,
                   drug_likeness_result, decision, created_at
            FROM screening_history
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 50
            """
        ).fetchall()

    items = []
    for row in rows:
        drug_likeness = json.loads(row["drug_likeness_result"])
        items.append(
            ScreeningHistoryItem(
                id=row["id"],
                input_query=row["input_query"],
                input_type=row["input_type"],
                compound_name=row["compound_name"],
                pubchem_cid=row["pubchem_cid"],
                canonical_smiles=row["canonical_smiles"],
                drug_likeness_status=drug_likeness["basic_drug_likeness_status"],
                developability_risk=drug_likeness["developability_risk"],
                decision=row["decision"],
                created_at=row["created_at"],
            )
        )
    return items


def get_history_detail(screening_id: int) -> ScreeningHistoryDetail | None:
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM screening_history WHERE id = ?",
            (screening_id,),
        ).fetchone()

    if row is None:
        return None

    descriptor_summary = json.loads(row["descriptor_summary"])
    drug_likeness_result = json.loads(row["drug_likeness_result"])
    report = ScreeningReport.model_validate_json(row["report_json"])
    return ScreeningHistoryDetail(
        id=row["id"],
        input_query=row["input_query"],
        input_type=row["input_type"],
        compound_name=row["compound_name"],
        pubchem_cid=row["pubchem_cid"],
        canonical_smiles=row["canonical_smiles"],
        descriptor_summary=descriptor_summary,
        drug_likeness_result=drug_likeness_result,
        drug_likeness_status=drug_likeness_result["basic_drug_likeness_status"],
        developability_risk=drug_likeness_result["developability_risk"],
        decision=row["decision"],
        report=report,
        created_at=row["created_at"],
    )


def delete_history_item(screening_id: int) -> bool:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM screening_history WHERE id = ?", (screening_id,))
        return cursor.rowcount > 0


def delete_all_history() -> int:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM screening_history")
        return cursor.rowcount
