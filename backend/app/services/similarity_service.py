from typing import Any
from functools import lru_cache
from urllib.parse import quote

import requests
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator

from app.models.cache_models import CacheMetadata
from app.models.finder_models import DrugLikenessPreview
from app.models.schemas import CompoundIdentity, InputType
from app.models.similarity_models import SimilarCompound
from app.services.cache_service import get_cached_response, set_cached_response
from app.services.descriptors import calculate_descriptors, parse_smiles, render_structure_image_base64
from app.services.pubchem import BASE_URL as PUBCHEM_BASE_URL
from app.services.pubchem import PubChemLookupError, PubChemNotFoundError, PubChemUnavailableError, resolve_compound
from app.services.rules import evaluate_rules

CHEMBL_BASE_URL = "https://www.ebi.ac.uk/chembl/api/data"
last_cache_metadata = CacheMetadata()


class SimilaritySearchError(Exception):
    pass


class SimilarityUnavailableError(SimilaritySearchError):
    pass


class SimilarityNotFoundError(SimilaritySearchError):
    pass


def _get_json(url: str, timeout: int = 25) -> dict[str, Any]:
    last_exc = None
    for attempt in range(2):
        try:
            response = requests.get(url, timeout=timeout)
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
            raise SimilarityUnavailableError("Similarity source timed out. Try again, or use cached results if available.") from last_exc
        raise SimilarityUnavailableError("Could not reach the similarity source. Please check the connection and try again.") from last_exc

    if response.status_code == 404:
        raise SimilarityNotFoundError("No similar compounds found.")
    if response.status_code >= 400:
        raise SimilarityUnavailableError(f"Similarity source returned HTTP {response.status_code}. Please try again later.")
    try:
        return response.json()
    except ValueError as exc:
        raise SimilarityUnavailableError("Similarity source returned an unreadable response. Please try again later.") from exc


@lru_cache(maxsize=4096)
def _fingerprint(smiles: str):
    mol = parse_smiles(smiles)
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    return generator.GetFingerprint(mol)


def tanimoto_similarity(reference_smiles: str, candidate_smiles: str) -> float:
    return round(float(DataStructs.TanimotoSimilarity(_fingerprint(reference_smiles), _fingerprint(candidate_smiles))) * 100, 2)


def _preview(smiles: str) -> tuple[DrugLikenessPreview, float]:
    try:
        descriptors = calculate_descriptors(smiles)
        rules = evaluate_rules(descriptors)
    except Exception as exc:
        return DrugLikenessPreview(error=f"Invalid SMILES: {exc}"), 0
    score = 0
    if rules.lipinski_rule_of_5["passed"]:
        score += 55
    if rules.veber_rule["passed"]:
        score += 35
    if rules.developability_risk == "Low":
        score += 10
    elif rules.developability_risk == "High":
        score -= 15
    return (
        DrugLikenessPreview(
            molecular_weight=descriptors.molecular_weight,
            logp=descriptors.logp,
            tpsa=descriptors.tpsa,
            lipinski_pass=bool(rules.lipinski_rule_of_5["passed"]),
            veber_pass=bool(rules.veber_rule["passed"]),
        ),
        max(score, 0),
    )


def rank_similar_compounds(reference_smiles: str, compounds: list[SimilarCompound]) -> list[SimilarCompound]:
    ranked: list[SimilarCompound] = []
    seen: set[str] = set()
    for compound in compounds:
        if not compound.canonical_smiles:
            continue
        key = compound.molecule_chembl_id or str(compound.pubchem_cid or "") or compound.canonical_smiles
        if key in seen:
            continue
        seen.add(key)
        try:
            parse_smiles(compound.canonical_smiles)
        except Exception:
            continue
        if compound.similarity_score <= 0:
            compound.similarity_score = tanimoto_similarity(reference_smiles, compound.canonical_smiles)
        preview, likeness_score = _preview(compound.canonical_smiles)
        quality = 35
        if compound.pubchem_cid or compound.molecule_chembl_id:
            quality += 30
        if compound.compound_name:
            quality += 15
        if compound.molecular_weight:
            quality += 10
        if compound.molecular_formula:
            quality += 10
        compound.drug_likeness_preview = preview
        compound.data_quality_score = min(quality, 100)
        compound.analog_priority_score = round(
            (compound.similarity_score * 0.45) + (compound.data_quality_score * 0.2) + (likeness_score * 0.35),
            2,
        )
        compound.ranking_reason = (
            "Ranked by chemical similarity, valid SMILES, public identifier availability, data completeness, "
            "and RDKit Lipinski/Veber preview. Similarity does not prove shared efficacy or safety."
        )
        ranked.append(compound)
    ranked.sort(key=lambda item: (-item.analog_priority_score, -item.similarity_score, item.compound_name or ""))
    for index, compound in enumerate(ranked, start=1):
        compound.similarity_rank = index
    return ranked


def _chembl_similarity(smiles: str, threshold: int, limit: int) -> list[SimilarCompound]:
    safe_smiles = quote(smiles, safe="")
    url = f"{CHEMBL_BASE_URL}/similarity/{safe_smiles}/{threshold}.json?limit={limit}"
    data = _get_json(url)
    compounds = []
    for item in data.get("molecules", []):
        structures = item.get("molecule_structures") or {}
        properties = item.get("molecule_properties") or {}
        candidate_smiles = structures.get("canonical_smiles")
        if not candidate_smiles:
            continue
        raw_similarity = item.get("similarity")
        try:
            similarity = float(raw_similarity)
            if similarity <= 1:
                similarity *= 100
        except (TypeError, ValueError):
            similarity = tanimoto_similarity(smiles, candidate_smiles)
        compounds.append(
            SimilarCompound(
                compound_name=item.get("pref_name"),
                molecule_chembl_id=item.get("molecule_chembl_id"),
                canonical_smiles=candidate_smiles,
                similarity_score=round(similarity, 2),
                molecular_formula=properties.get("full_molformula"),
                molecular_weight=float(properties.get("full_mwt")) if properties.get("full_mwt") else None,
                source="ChEMBL",
            )
        )
    return compounds


def _pubchem_properties(cids: list[int]) -> list[dict[str, Any]]:
    if not cids:
        return []
    cid_text = ",".join(str(cid) for cid in cids)
    props = "MolecularFormula,MolecularWeight,CanonicalSMILES,Title"
    url = f"{PUBCHEM_BASE_URL}/compound/cid/{cid_text}/property/{props}/JSON"
    data = _get_json(url)
    return data.get("PropertyTable", {}).get("Properties", [])


def _pubchem_similarity(smiles: str, threshold: int, limit: int) -> list[SimilarCompound]:
    safe_smiles = quote(smiles, safe="")
    url = f"{PUBCHEM_BASE_URL}/compound/fastsimilarity_2d/smiles/{safe_smiles}/cids/JSON?Threshold={threshold}&MaxRecords={limit}"
    data = _get_json(url, timeout=30)
    cids = [int(cid) for cid in data.get("IdentifierList", {}).get("CID", [])[:limit]]
    compounds = []
    for item in _pubchem_properties(cids):
        candidate_smiles = item.get("CanonicalSMILES")
        if not candidate_smiles:
            continue
        compounds.append(
            SimilarCompound(
                compound_name=item.get("Title"),
                pubchem_cid=int(item.get("CID")) if item.get("CID") else None,
                canonical_smiles=candidate_smiles,
                similarity_score=tanimoto_similarity(smiles, candidate_smiles),
                molecular_formula=item.get("MolecularFormula"),
                molecular_weight=float(item.get("MolecularWeight")) if item.get("MolecularWeight") else None,
                source="PubChem",
            )
        )
    return compounds


def resolve_reference(query: str, input_type: InputType) -> CompoundIdentity:
    if input_type == "smiles":
        parse_smiles(query)
    identity = resolve_compound(query, input_type)
    smiles = identity.canonical_smiles or identity.isomeric_smiles
    if not smiles:
        raise PubChemLookupError("Reference compound did not include a usable SMILES string.")
    identity.structure_image_base64 = render_structure_image_base64(smiles)
    return identity


def search_similar_compounds(query: str, input_type: InputType, source: str, threshold: int, limit: int) -> tuple[CompoundIdentity, list[SimilarCompound], str, CacheMetadata]:
    global last_cache_metadata
    reference = resolve_reference(query, input_type)
    smiles = reference.canonical_smiles or reference.isomeric_smiles or ""
    source_key = "chembl" if source in {"auto", "chembl_or_pubchem"} else source
    cache_value = f"{source_key}:{smiles}:{threshold}:{limit}"
    cached, metadata = get_cached_response(source_key, "similarity_search", cache_value)
    if cached is not None:
        last_cache_metadata = metadata
        compounds = [SimilarCompound.model_validate(item) for item in cached.get("similar_compounds", [])]
        return reference, compounds, cached.get("data_source", source_key), metadata

    if source_key == "pubchem":
        compounds = _pubchem_similarity(smiles, threshold, limit)
        data_source = "PubChem"
    else:
        try:
            compounds = _chembl_similarity(smiles, threshold, limit)
            data_source = "ChEMBL"
        except SimilaritySearchError:
            if source not in {"auto", "chembl_or_pubchem"}:
                raise
            compounds = _pubchem_similarity(smiles, threshold, limit)
            data_source = "PubChem"

    ranked = rank_similar_compounds(smiles, compounds)[:limit]
    metadata = set_cached_response(
        source_key,
        "similarity_search",
        cache_value,
        {"data_source": data_source, "similar_compounds": [item.model_dump() for item in ranked]},
    )
    last_cache_metadata = metadata
    return reference, ranked, data_source, metadata
