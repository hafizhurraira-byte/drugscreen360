from typing import Any

import requests

from app.models.cache_models import CacheMetadata
from app.models.disease_models import DiseaseMatch, DiseaseTarget
from app.services.cache_service import get_cached_response, set_cached_response

OPEN_TARGETS_GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"


class OpenTargetsError(Exception):
    pass


class OpenTargetsUnavailableError(OpenTargetsError):
    pass


last_cache_metadata = CacheMetadata()


SEARCH_QUERY = """
query SearchDiseases($query: String!) {
  search(queryString: $query, entityNames: ["disease"], page: {index: 0, size: 20}) {
    hits {
      id
      name
      description
      entity
    }
  }
}
"""

TARGETS_QUERY = """
query DiseaseTargets($diseaseId: String!, $size: Int!) {
  disease(efoId: $diseaseId) {
    associatedTargets(page: {index: 0, size: $size}) {
      rows {
        score
        target {
          id
          approvedSymbol
          approvedName
          biotype
        }
        datatypeScores {
          id
          score
        }
      }
    }
  }
}
"""


def _graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    last_exc = None
    for attempt in range(2):
        try:
            response = requests.post(
                OPEN_TARGETS_GRAPHQL_URL,
                json={"query": query, "variables": variables},
                timeout=25,
            )
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
            raise OpenTargetsUnavailableError("Open Targets request timed out. Please try again later.") from last_exc
        raise OpenTargetsUnavailableError("Could not reach Open Targets. Please check the connection and try again.") from last_exc

    if response.status_code >= 400:
        raise OpenTargetsUnavailableError(f"Open Targets returned HTTP {response.status_code}. Please try again later.")
    try:
        payload = response.json()
    except ValueError as exc:
        raise OpenTargetsUnavailableError("Open Targets returned an unreadable response. Please try again later.") from exc
    if payload.get("errors"):
        raise OpenTargetsUnavailableError("Open Targets GraphQL returned an error for this request.")
    return payload.get("data") or {}


def search_diseases(query: str) -> list[DiseaseMatch]:
    global last_cache_metadata
    cache_value = query.strip().lower()
    cached, metadata = get_cached_response("open_targets", "disease_search", cache_value)
    if cached is None:
        data = _graphql(SEARCH_QUERY, {"query": query})
        metadata = set_cached_response("open_targets", "disease_search", cache_value, data)
    else:
        data = cached
    last_cache_metadata = metadata
    hits = ((data.get("search") or {}).get("hits")) or []
    diseases = []
    for hit in hits:
        disease_id = hit.get("id")
        name = hit.get("name")
        if not disease_id or not name:
            continue
        diseases.append(
            DiseaseMatch(
                disease_id=disease_id,
                name=name,
                description=hit.get("description"),
                entity_type=hit.get("entity"),
            )
        )
    return diseases


def _score_map(row: dict[str, Any]) -> dict[str, float]:
    mapping = {}
    for item in row.get("datatypeScores") or []:
        key = item.get("id")
        score = item.get("score")
        if key and score is not None:
            mapping[key] = float(score)
    return mapping


def _data_quality_score(target: dict[str, Any], scores: dict[str, float]) -> float:
    score = 0
    if target.get("id"):
        score += 15
    if target.get("approvedSymbol"):
        score += 20
    if target.get("approvedName"):
        score += 15
    if target.get("biotype"):
        score += 10
    score += min(len(scores) * 6, 30)
    return min(score, 100)


def rank_disease_targets(rows: list[dict[str, Any]]) -> list[DiseaseTarget]:
    targets = []
    for row in rows:
        target = row.get("target") or {}
        target_id = target.get("id")
        if not target_id:
            continue
        scores = _score_map(row)
        overall = float(row.get("score") or 0)
        quality = _data_quality_score(target, scores)
        known_drug = scores.get("known_drug")
        genetic = scores.get("genetic_association")
        final = round((overall * 70) + ((known_drug or 0) * 12) + ((genetic or 0) * 10) + (quality * 0.08), 2)
        symbol = target.get("approvedSymbol")
        item = DiseaseTarget(
            target_id=target_id,
            approved_symbol=symbol,
            approved_name=target.get("approvedName"),
            biotype=target.get("biotype"),
            organism=None,
            overall_association_score=round(overall, 4),
            genetic_association_score=genetic,
            known_drug_score=known_drug,
            affected_pathway_score=scores.get("affected_pathway"),
            literature_score=scores.get("literature"),
            animal_model_score=scores.get("animal_model"),
            rna_expression_score=scores.get("rna_expression"),
            data_quality_score=round(quality, 2),
            final_target_priority_score=min(final, 100),
            ranking_reason=(
                "Ranked by Open Targets overall association score, known-drug evidence, genetic evidence, "
                "data completeness, and target symbol/name availability. This does not prove efficacy or safety."
            ),
            suggested_chembl_query=symbol or target.get("approvedName"),
        )
        targets.append(item)

    targets.sort(key=lambda item: (-item.final_target_priority_score, -item.overall_association_score, item.target_id))
    for index, target in enumerate(targets, start=1):
        target.disease_target_rank = index
    return targets


def get_disease_targets(disease_id: str, limit: int = 25) -> list[DiseaseTarget]:
    global last_cache_metadata
    cache_value = f"{disease_id}:{limit}"
    cached, metadata = get_cached_response("open_targets", "disease_target_search", cache_value)
    if cached is None:
        data = _graphql(TARGETS_QUERY, {"diseaseId": disease_id, "size": limit})
        metadata = set_cached_response("open_targets", "disease_target_search", cache_value, data)
    else:
        data = cached
    last_cache_metadata = metadata
    rows = ((((data.get("disease") or {}).get("associatedTargets") or {}).get("rows")) or [])
    return rank_disease_targets(rows)
