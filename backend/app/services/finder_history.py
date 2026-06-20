import json

from app.database import get_connection, init_db
from app.models.finder_models import BatchScreeningResponse, CandidateMolecule


def save_finder_search(query: str, selected_target: str | None, candidates: list[CandidateMolecule]) -> int:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO finder_searches (query, selected_target, candidates_found)
            VALUES (?, ?, ?)
            """,
            (query, selected_target, len(candidates)),
        )
        search_id = int(cursor.lastrowid)
        for candidate in candidates:
            connection.execute(
                """
                INSERT INTO finder_candidates (
                    search_id, molecule_chembl_id, compound_name, canonical_smiles,
                    activity_type, activity_value, activity_units, target_chembl_id, source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    search_id,
                    candidate.molecule_chembl_id,
                    candidate.compound_name,
                    candidate.canonical_smiles,
                    candidate.activity_type,
                    candidate.activity_value,
                    candidate.activity_units,
                    candidate.target_chembl_id,
                    candidate.source,
                ),
            )
        return search_id


def save_batch_screening_run(response: BatchScreeningResponse) -> int:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO batch_screening_runs (candidate_count, summary_json)
            VALUES (?, ?)
            """,
            (response.screened_count, json.dumps(response.comparison_table)),
        )
        return int(cursor.lastrowid)
