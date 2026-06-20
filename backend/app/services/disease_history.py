import json

from app.database import get_connection, init_db
from app.models.disease_models import DiseaseTarget


def save_disease_search(query: str, disease_id: str | None, disease_name: str | None, targets: list[DiseaseTarget]) -> int:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO disease_searches (query, selected_disease_id, selected_disease_name, targets_found)
            VALUES (?, ?, ?, ?)
            """,
            (query, disease_id, disease_name, len(targets)),
        )
        search_id = int(cursor.lastrowid)
        for target in targets:
            connection.execute(
                """
                INSERT INTO disease_target_results (
                    search_id, target_id, approved_symbol, approved_name, association_score,
                    final_target_priority_score, selected_target, result_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    search_id,
                    target.target_id,
                    target.approved_symbol,
                    target.approved_name,
                    target.overall_association_score,
                    target.final_target_priority_score,
                    0,
                    json.dumps(target.model_dump()),
                ),
            )
        return search_id


def mark_selected_target(target_id: str) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute("UPDATE disease_target_results SET selected_target = 1 WHERE target_id = ?", (target_id,))
