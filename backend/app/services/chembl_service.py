from typing import Any

import requests

from app.models.cache_models import CacheMetadata
from app.models.finder_models import CandidateMolecule, TargetResult
from app.services.candidate_ranker import rank_candidates
from app.services.cache_service import get_cached_response, set_cached_response
from app.services.target_ranker import rank_targets

CHEMBL_BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
ACTIVITY_TYPES = {"IC50", "KI", "KD", "EC50", "AC50"}


class ChEMBLError(Exception):
    pass


class ChEMBLUnavailableError(ChEMBLError):
    pass


last_cache_metadata = CacheMetadata()


def _get_json(path: str, params: dict[str, Any]) -> dict[str, Any]:
    last_exc = None
    for attempt in range(2):
        try:
            response = requests.get(f"{CHEMBL_BASE_URL}/{path}.json", params=params, timeout=20)
            break
        except requests.Timeout as exc:
            last_exc = exc
        except requests.RequestException as exc:
            last_exc = exc
        if attempt == 0:
            import time

            time.sleep(0.5)
    else:
        if isinstance(last_exc, requests.Timeout):
            raise ChEMBLUnavailableError("ChEMBL is slow or unavailable right now. Try again, or use cached results if available.") from last_exc
        raise ChEMBLUnavailableError("Could not reach ChEMBL. Please check the connection and try again.") from last_exc

    if response.status_code >= 400:
        raise ChEMBLUnavailableError(f"ChEMBL returned HTTP {response.status_code}. Please try again later.")
    try:
        return response.json()
    except ValueError as exc:
        raise ChEMBLUnavailableError("ChEMBL returned an unreadable response. Please try again later.") from exc


def search_targets(query: str, limit: int = 20) -> list[TargetResult]:
    global last_cache_metadata
    cache_value = f"{query.strip().lower()}:{limit}"
    cached, metadata = get_cached_response("chembl", "chembl_target_search", cache_value)
    if cached is None:
        data = _get_json("target/search", {"q": query, "limit": limit})
        metadata = set_cached_response("chembl", "chembl_target_search", cache_value, data)
    else:
        data = cached
    last_cache_metadata = metadata
    targets = []
    for item in data.get("targets", []):
        target_id = item.get("target_chembl_id")
        if not target_id:
            continue
        accession = None
        components = item.get("target_components") or []
        if components:
            accession = components[0].get("accession")
        targets.append(
            TargetResult(
                target_chembl_id=target_id,
                preferred_name=item.get("pref_name"),
                organism=item.get("organism"),
                target_type=item.get("target_type"),
                accession=accession,
            )
        )
    return rank_targets(targets, query)


def get_target_candidates(target_chembl_id: str, limit: int = 50) -> list[CandidateMolecule]:
    global last_cache_metadata
    cache_value = f"{target_chembl_id}:{limit}"
    cached, metadata = get_cached_response("chembl", "chembl_candidate_search", cache_value)
    if cached is None:
        data = _get_json(
            "activity",
            {
                "target_chembl_id": target_chembl_id,
                "standard_units": "nM",
                "limit": 200,
            },
        )
        metadata = set_cached_response("chembl", "chembl_candidate_search", cache_value, data)
    else:
        data = cached
    last_cache_metadata = metadata
    candidates = []
    for item in data.get("activities", []):
        activity_type = (item.get("standard_type") or "").upper()
        smiles = item.get("canonical_smiles")
        molecule_id = item.get("molecule_chembl_id")
        raw_value = item.get("standard_value")
        if activity_type not in ACTIVITY_TYPES or not smiles or not molecule_id or raw_value in {None, ""}:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue

        candidates.append(
            CandidateMolecule(
                molecule_chembl_id=molecule_id,
                compound_name=item.get("molecule_pref_name"),
                canonical_smiles=smiles,
                activity_type=activity_type,
                activity_value=value,
                activity_units=item.get("standard_units") or "nM",
                assay_type=item.get("assay_type"),
                confidence_score=item.get("confidence_score"),
                relation=item.get("standard_relation"),
                assay_description=item.get("assay_description") or item.get("description"),
                target_name=item.get("target_pref_name"),
                target_chembl_id=target_chembl_id,
            )
        )
    return rank_candidates(candidates)[:limit]
