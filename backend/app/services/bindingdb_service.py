import requests

from app.models.evidence_models import BindingDbEvidence, EvidenceCandidateInput

BINDINGDB_URL = "https://www.bindingdb.org/rwd/bind/chemsearch/marvin/MolStructure.jsp"


class BindingDbUnavailableError(Exception):
    pass


def check_bindingdb_support(candidate: EvidenceCandidateInput, timeout: int = 8) -> BindingDbEvidence:
    if not candidate.canonical_smiles:
        return BindingDbEvidence(
            bindingdb_checked=False,
            limitation="BindingDB support was not checked because canonical SMILES was missing.",
        )

    try:
        response = requests.get(BINDINGDB_URL, timeout=timeout)
    except requests.Timeout:
        return BindingDbEvidence(
            bindingdb_checked=False,
            limitation="BindingDB request timed out. ChEMBL evidence was still evaluated.",
        )
    except requests.RequestException:
        return BindingDbEvidence(
            bindingdb_checked=False,
            limitation="BindingDB was unavailable. ChEMBL evidence was still evaluated.",
        )

    if response.status_code >= 400:
        return BindingDbEvidence(
            bindingdb_checked=False,
            limitation=f"BindingDB returned HTTP {response.status_code}. ChEMBL evidence was still evaluated.",
        )

    return BindingDbEvidence(
        bindingdb_checked=True,
        bindingdb_support_found=False,
        target_name=candidate.target_name,
        ligand_name=candidate.compound_name,
        source_url="https://www.bindingdb.org/",
        limitation=(
            "BindingDB live support check is available as a safe availability probe in V1. "
            "Detailed affinity parsing is reserved for a later integration."
        ),
    )
