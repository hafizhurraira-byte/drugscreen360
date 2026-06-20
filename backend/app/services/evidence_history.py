import json
from typing import Any

from app.database import get_connection, init_db
from app.models.evidence_models import EvidenceQualityAssessment


def save_evidence_summary(candidate: Any, evidence: EvidenceQualityAssessment) -> None:
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO evidence_summaries (
                molecule_identifier, target_identifier, target_name,
                evidence_score, evidence_level, potency_quality, warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                getattr(candidate, "molecule_chembl_id", None)
                or getattr(candidate, "canonical_smiles", None)
                or getattr(candidate, "compound_name", None),
                getattr(candidate, "target_chembl_id", None),
                getattr(candidate, "target_name", None),
                evidence.evidence_score,
                evidence.evidence_level,
                evidence.potency_quality,
                json.dumps(evidence.warnings),
            ),
        )
