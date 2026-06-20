from typing import Any
from urllib.parse import quote

import requests

from app.models.cache_models import CacheMetadata
from app.models.schemas import CompoundIdentity, InputType
from app.services.cache_service import get_cached_response, set_cached_response

BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PROPERTIES = ",".join(
    [
        "MolecularFormula",
        "MolecularWeight",
        "CanonicalSMILES",
        "IsomericSMILES",
        "IUPACName",
        "Title",
    ]
)


class PubChemLookupError(Exception):
    pass


class PubChemNotFoundError(PubChemLookupError):
    pass


class PubChemUnavailableError(PubChemLookupError):
    pass


last_cache_metadata = CacheMetadata()


def _get_json(url: str) -> dict[str, Any]:
    last_exc = None
    for attempt in range(2):
        try:
            response = requests.get(url, timeout=15)
            break
        except requests.Timeout as exc:
            last_exc = exc
        except requests.RequestException as exc:
            last_exc = exc
        if attempt == 0:
            import time

            time.sleep(0.4)
    else:
        if isinstance(last_exc, requests.Timeout):
            raise PubChemUnavailableError("PubChem request timed out. Please try again later.") from last_exc
        raise PubChemUnavailableError("Could not reach PubChem. Please check the connection and try again.") from last_exc

    if response.status_code == 404:
        raise PubChemNotFoundError("Compound not found in PubChem.")
    if response.status_code >= 400:
        raise PubChemUnavailableError(f"PubChem returned HTTP {response.status_code}. Please try again later.")

    try:
        return response.json()
    except ValueError as exc:
        raise PubChemUnavailableError("PubChem returned an unreadable response. Please try again later.") from exc


def _cid_path(query: str, input_type: InputType) -> str:
    cleaned = quote(query.strip())
    if input_type == "cid":
        return f"compound/cid/{cleaned}"
    if input_type == "smiles":
        return f"compound/smiles/{cleaned}"
    if input_type == "inchi":
        return f"compound/inchi/{cleaned}"
    if input_type == "inchikey":
        return f"compound/inchikey/{cleaned}"
    return f"compound/name/{cleaned}"


def _extract_cid(data: dict[str, Any]) -> int:
    try:
        return int(data["IdentifierList"]["CID"][0])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise PubChemNotFoundError("PubChem did not return a CID for this input.") from exc


def _fetch_cid(query: str, input_type: InputType) -> int:
    if input_type == "cid":
        try:
            return int(query.strip())
        except ValueError as exc:
            raise PubChemLookupError("CID input must be a number.") from exc

    url = f"{BASE_URL}/{_cid_path(query, input_type)}/cids/JSON"
    return _extract_cid(_get_json(url))


def _fetch_properties(cid: int) -> dict[str, Any]:
    url = f"{BASE_URL}/compound/cid/{cid}/property/{PROPERTIES}/JSON"
    data = _get_json(url)
    try:
        return data["PropertyTable"]["Properties"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise PubChemLookupError("PubChem did not return compound properties.") from exc


def _fetch_synonyms(cid: int) -> list[str]:
    url = f"{BASE_URL}/compound/cid/{cid}/synonyms/JSON"
    try:
        data = _get_json(url)
        synonyms = data["InformationList"]["Information"][0].get("Synonym", [])
    except (PubChemLookupError, KeyError, IndexError, TypeError):
        return []
    return synonyms[:12]


def resolve_compound(query: str, input_type: InputType) -> CompoundIdentity:
    global last_cache_metadata
    cache_key = f"{input_type}:{query.strip().lower()}"
    cached, metadata = get_cached_response("pubchem", "compound_lookup", cache_key)
    if cached is not None:
        last_cache_metadata = metadata
        identity = CompoundIdentity.model_validate(cached)
        identity.cache_metadata = metadata
        return identity

    cid = _fetch_cid(query, input_type)
    props = _fetch_properties(cid)
    synonyms = _fetch_synonyms(cid)

    title = props.get("Title") or (synonyms[0] if synonyms else None)

    identity = CompoundIdentity(
        compound_name=title,
        pubchem_cid=cid,
        canonical_smiles=props.get("CanonicalSMILES") or props.get("ConnectivitySMILES") or props.get("SMILES"),
        isomeric_smiles=props.get("IsomericSMILES") or props.get("SMILES"),
        molecular_formula=props.get("MolecularFormula"),
        molecular_weight=float(props["MolecularWeight"]) if props.get("MolecularWeight") else None,
        iupac_name=props.get("IUPACName"),
        synonyms=synonyms,
        pubchem_source_link=f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
    )
    metadata = set_cached_response("pubchem", "compound_lookup", cache_key, identity.model_dump())
    last_cache_metadata = metadata
    identity.cache_metadata = metadata
    return identity
