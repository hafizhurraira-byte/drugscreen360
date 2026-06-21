import json
import math
from pathlib import Path
from typing import Any
from fastapi import HTTPException
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors, DataStructs

from app.database import get_connection, init_db
from app.services.descriptors import calculate_descriptors, parse_smiles
from app.services.admet_trained_model_service import discover_trained_models

FEATURE_COLUMNS = [
    "molecular_weight",
    "logp",
    "tpsa",
    "hbd",
    "hba",
    "rotatable_bonds",
    "ring_count",
    "aromatic_ring_count",
    "formal_charge",
    "fraction_csp3",
]

_DOMAIN_STATS_CACHE = {}


def _get_active_project_id() -> int | None:
    init_db()
    with get_connection() as connection:
        # Check active project
        row = connection.execute("SELECT project_id FROM project_active_option WHERE id = 1").fetchone()
        if row:
            return row["project_id"]
    return None


def get_or_calculate_domain_stats(model_id: str) -> dict[str, Any]:
    """
    Computes means, standard deviations, min, max, z-scores, centroid distance percentiles,
    and Morgan fingerprints for the training dataset used to build a model.
    Caches results in memory to speed up evaluations.
    """
    if model_id in _DOMAIN_STATS_CACHE:
        return _DOMAIN_STATS_CACHE[model_id]

    models = discover_trained_models()
    model_summary = next((m for m in models if m["model_id"] == model_id), None)
    if not model_summary:
        raise HTTPException(status_code=404, detail=f"Trained model '{model_id}' not found.")

    training_run_id = model_summary.get("training_run_id")
    dataset_id = None

    # Try reading from model card first
    folder = Path(model_summary["artifact_dir"])
    card_path = folder / "model_card.json"
    dataset_name = "Training Dataset"
    if card_path.exists():
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
            dataset_id = card.get("dataset_id")
            dataset_name = card.get("dataset_name") or dataset_name
        except:
            pass

    # Fallback to database training run lookup
    if not dataset_id and training_run_id:
        init_db()
        with get_connection() as conn:
            row = conn.execute("SELECT dataset_id, task_name FROM admet_training_runs WHERE id = ?", (training_run_id,)).fetchone()
            if row:
                dataset_id = row["dataset_id"]
                if row["task_name"]:
                    dataset_name = row["task_name"]

    if not dataset_id:
        raise ValueError("Could not resolve dataset_id for the model.")

    from app.services.admet_dataset_service import get_dataset_records
    records = get_dataset_records(dataset_id)

    X_train = []
    smiles_train = []
    names_train = []

    for r in records:
        if not r.is_valid or not r.canonical_smiles or not r.descriptors:
            continue
        features = []
        missing = False
        for col in FEATURE_COLUMNS:
            val = r.descriptors.get(col)
            if val is None:
                # Fallback for HBD/HBA names
                if col == "hbd":
                    val = r.descriptors.get("hydrogen_bond_donors")
                elif col == "hba":
                    val = r.descriptors.get("hydrogen_bond_acceptors")
            if val is None:
                missing = True
                break
            features.append(float(val))
        if missing:
            continue
        X_train.append(features)
        smiles_train.append(r.canonical_smiles)
        names_train.append(r.compound_name or f"Record #{r.id}")

    N = len(X_train)
    if N < 10:
        raise ValueError(f"Training dataset has too few valid records ({N} < 10) to compute domain stats.")

    # Calculate min, max, mean, std
    mins = [min(X_train[i][j] for i in range(N)) for j in range(10)]
    maxs = [max(X_train[i][j] for i in range(N)) for j in range(10)]
    means = [sum(X_train[i][j] for i in range(N)) / N for j in range(10)]
    stds = []
    for j in range(10):
        variance = sum((X_train[i][j] - means[j])**2 for i in range(N)) / N
        std = math.sqrt(variance)
        stds.append(std if std > 1e-6 else 1e-6)

    # Standardize training dataset
    Z_train = []
    for i in range(N):
        z_vector = [(X_train[i][j] - means[j]) / stds[j] for j in range(10)]
        Z_train.append(z_vector)

    # Distance to training centroid for each training molecule
    d_centroid_train = [math.sqrt(sum(Z_train[i][j]**2 for j in range(10))) for i in range(N)]
    sorted_d_centroid = sorted(d_centroid_train)
    p95_centroid = sorted_d_centroid[min(int(N * 0.95), N - 1)]
    p99_centroid = sorted_d_centroid[min(int(N * 0.99), N - 1)]

    # Compute fingerprints
    fps_train = []
    for s in smiles_train:
        try:
            mol = Chem.MolFromSmiles(s)
            fp = rdMolDescriptors.GetMorganFingerprintAsBitVect(mol, 2, nBits=1024)
            fps_train.append(fp)
        except:
            fps_train.append(None)

    stats = {
        "model_id": model_id,
        "training_run_id": training_run_id,
        "dataset_name": dataset_name,
        "task_type": model_summary.get("task_type"),
        "task_name": model_summary.get("task_name"),
        "record_count": N,
        "mins": mins,
        "maxs": maxs,
        "means": means,
        "stds": stds,
        "X_train": X_train,
        "Z_train": Z_train,
        "smiles_train": smiles_train,
        "names_train": names_train,
        "fps_train": fps_train,
        "p95_centroid": p95_centroid,
        "p99_centroid": p99_centroid,
    }

    _DOMAIN_STATS_CACHE[model_id] = stats
    return stats


def evaluate_domain_internal(model_id: str, smiles: str, top_k: int = 5) -> dict[str, Any]:
    """
    Core applicability domain calculation.
    """
    mol = parse_smiles(smiles)
    canonical = Chem.MolToSmiles(mol, canonical=True)
    if not canonical:
        raise HTTPException(status_code=422, detail="Invalid SMILES: canonicalization failed.")

    # Calculate descriptors
    descriptors = calculate_descriptors(smiles)
    desc_dict = descriptors.model_dump()
    features_dict = {
        "molecular_weight": desc_dict.get("molecular_weight"),
        "logp": desc_dict.get("logp"),
        "tpsa": desc_dict.get("tpsa"),
        "hbd": float(desc_dict.get("hydrogen_bond_donors")),
        "hba": float(desc_dict.get("hydrogen_bond_acceptors")),
        "rotatable_bonds": float(desc_dict.get("rotatable_bonds")),
        "ring_count": float(desc_dict.get("ring_count")),
        "aromatic_ring_count": float(desc_dict.get("aromatic_ring_count")),
        "formal_charge": float(desc_dict.get("formal_charge")),
        "fraction_csp3": desc_dict.get("fraction_csp3"),
    }
    q_features = [features_dict[col] for col in FEATURE_COLUMNS]

    try:
        stats = get_or_calculate_domain_stats(model_id)
    except Exception as e:
        # Domain cannot be computed
        return {
            "model_id": model_id,
            "training_run_id": None,
            "task_name": None,
            "task_type": "unknown",
            "query_smiles": smiles,
            "canonical_smiles": canonical,
            "descriptor_values": features_dict,
            "descriptor_range_check": {
                "in_range_features": [],
                "out_of_range_features": FEATURE_COLUMNS,
                "out_of_range_count": 10,
                "range_coverage_fraction": 0.0,
            },
            "distance_summary": {
                "distance_to_training_centroid": 999.0,
                "nearest_training_distance": 999.0,
                "centroid_distance_threshold_95": 0.0,
                "centroid_distance_threshold_99": 0.0,
                "distance_status": "not_available",
            },
            "nearest_neighbors": [],
            "fingerprint_similarity": {
                "max_tanimoto_similarity": 0.0,
                "mean_top_k_tanimoto_similarity": 0.0,
                "similarity_status": "low_similarity",
            },
            "domain_status": "not_available",
            "uncertainty_level": "unknown",
            "warnings": [f"Applicability domain not available: {e}"],
            "limitations": [
                "No training domain data could be parsed for this model.",
                "Predictions must be treated as completely unvalidated."
            ],
            "scientific_notice": "Computational estimate only. Requires experimental and external validation."
        }

    # Range check
    in_range = []
    out_range = []
    for j, col in enumerate(FEATURE_COLUMNS):
        val = q_features[j]
        if stats["mins"][j] <= val <= stats["maxs"][j]:
            in_range.append(col)
        else:
            out_range.append(col)

    range_coverage = len(in_range) / 10.0

    # Distance check (z-scores)
    z_query = [(q_features[j] - stats["means"][j]) / stats["stds"][j] for j in range(10)]
    d_centroid_query = math.sqrt(sum(z_query[j]**2 for j in range(10)))

    N = stats["record_count"]
    Z_train = stats["Z_train"]
    d_train = []
    for i in range(N):
        dist = math.sqrt(sum((z_query[j] - Z_train[i][j])**2 for j in range(10)))
        d_train.append(dist)

    nearest_dist = min(d_train)

    if d_centroid_query <= stats["p95_centroid"]:
        distance_status = "inside_domain"
    elif d_centroid_query <= stats["p99_centroid"]:
        distance_status = "borderline"
    else:
        distance_status = "outside_domain"

    # Fingerprints & Tanimoto similarity
    query_fp = None
    try:
        query_fp = rdMolDescriptors.GetMorganFingerprintAsBitVect(mol, 2, nBits=1024)
    except:
        pass

    tanimotos = []
    for i in range(N):
        sim = 0.0
        if query_fp and stats["fps_train"][i]:
            try:
                sim = float(DataStructs.TanimotoSimilarity(query_fp, stats["fps_train"][i]))
            except:
                pass
        tanimotos.append(sim)

    # Sort nearest neighbors by distance
    neighbor_indices = sorted(range(N), key=lambda idx: d_train[idx])
    neighbors_list = []
    for idx in neighbor_indices[:top_k]:
        neighbors_list.append({
            "compound_name": stats["names_train"][idx],
            "canonical_smiles": stats["smiles_train"][idx],
            "distance": round(d_train[idx], 4),
            "tanimoto_similarity": round(tanimotos[idx], 4),
        })

    # Tanimoto stats
    max_tanimoto = max(tanimotos) if tanimotos else 0.0
    sorted_tanimotos = sorted(tanimotos, reverse=True)
    top_k_tanimotos = sorted_tanimotos[:top_k]
    mean_top_k_tanimoto = sum(top_k_tanimotos) / len(top_k_tanimotos) if top_k_tanimotos else 0.0

    if max_tanimoto >= 0.7:
        sim_status = "high_similarity"
    elif max_tanimoto >= 0.5:
        sim_status = "moderate_similarity"
    else:
        sim_status = "low_similarity"

    # Map Domain Status & Uncertainty
    domain_status = distance_status
    if domain_status == "inside_domain":
        if max_tanimoto >= 0.7:
            uncertainty = "low"
        else:
            uncertainty = "moderate"
    elif domain_status == "borderline":
        uncertainty = "moderate"
    else:
        uncertainty = "high"

    # Warnings & Disclaimers
    warnings = []
    limitations = [
        "Computational applicability domain estimate only.",
        "Descriptor range check is heuristic and z-score Euclidean boundaries assume descriptor normality.",
        "Wet-lab validation and expert review are required before scientific decision-making."
    ]

    if N < 30:
        warnings.append(f"Training dataset size is very small (N={N} < 30). Centroid percentiles may be statistically unstable.")

    if domain_status == "outside_domain":
        warnings.append("Prediction molecule is outside the training applicability domain centroid (99th percentile exceeded).")
    elif domain_status == "borderline":
        warnings.append("Prediction molecule lies on the borderline of the training applicability domain centroid (95th-99th percentile).")

    if max_tanimoto < 0.5:
        warnings.append("Query molecule has low structural similarity (max Tanimoto < 0.5) to all training records.")

    # External Validation warnings
    from app.services.admet_validation_service import get_latest_external_validation_by_model
    latest_val = get_latest_external_validation_by_model(model_id)
    if not latest_val:
        warnings.append("No external validation available for this model.")
    else:
        is_poor = any("overfitting" in w.lower() or "poorly calibrated" in w.lower() for w in latest_val["warnings"])
        if is_poor:
            warnings.append("Model exhibits poor external validation calibration or overfitting markers.")

    res = {
        "model_id": model_id,
        "training_run_id": stats["training_run_id"],
        "task_name": stats["task_name"],
        "task_type": stats["task_type"],
        "query_smiles": smiles,
        "canonical_smiles": canonical,
        "descriptor_values": features_dict,
        "descriptor_range_check": {
            "in_range_features": in_range,
            "out_of_range_features": out_range,
            "out_of_range_count": len(out_range),
            "range_coverage_fraction": round(range_coverage, 2),
        },
        "distance_summary": {
            "distance_to_training_centroid": round(d_centroid_query, 4),
            "nearest_training_distance": round(nearest_dist, 4),
            "centroid_distance_threshold_95": round(stats["p95_centroid"], 4),
            "centroid_distance_threshold_99": round(stats["p99_centroid"], 4),
            "distance_status": distance_status,
        },
        "nearest_neighbors": neighbors_list,
        "fingerprint_similarity": {
            "max_tanimoto_similarity": round(max_tanimoto, 4),
            "mean_top_k_tanimoto_similarity": round(mean_top_k_tanimoto, 4),
            "similarity_status": sim_status,
        },
        "domain_status": domain_status,
        "uncertainty_level": uncertainty,
        "warnings": warnings,
        "limitations": limitations,
        "scientific_notice": "Computational estimate only. Requires experimental and external validation."
    }

    # Save to SQLite database
    try:
        save_domain_evaluation(
            model_id=res["model_id"],
            training_run_id=res["training_run_id"],
            smiles=res["query_smiles"],
            canonical_smiles=res["canonical_smiles"],
            domain_status=res["domain_status"],
            uncertainty_level=res["uncertainty_level"],
            summary=res,
            warnings=res["warnings"]
        )
    except:
        pass

    # Attach to active project if selected
    active_project_id = _get_active_project_id()
    if active_project_id:
        try:
            from app.models.project_workspace_models import ProjectAttachRequest
            from app.services.project_workspace_service import attach_project_item
            attach_project_item(
                active_project_id,
                ProjectAttachRequest(
                    item_type="admet_domain_evaluation",
                    item_id=model_id,
                    item_title=f"Domain Check: {domain_status.replace('_', ' ').title()} ({uncertainty.title()} Uncertainty)",
                    metadata={
                        "smiles": smiles,
                        "model_id": model_id,
                        "domain_status": domain_status,
                        "uncertainty_level": uncertainty,
                        "nearest_training_distance": round(nearest_dist, 4),
                        "out_of_range_features": out_range,
                        "evaluated_at": stats.get("created_at") or "just now"
                    }
                )
            )
        except:
            pass

    return res


def save_domain_evaluation(
    model_id: str,
    training_run_id: int | None,
    smiles: str,
    canonical_smiles: str,
    domain_status: str,
    uncertainty_level: str,
    summary: dict,
    warnings: list[str]
) -> int:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO admet_domain_evaluations (
                model_id, training_run_id, smiles, canonical_smiles,
                domain_status, uncertainty_level, summary_json, warnings_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model_id,
                training_run_id,
                smiles,
                canonical_smiles,
                domain_status,
                uncertainty_level,
                json.dumps(summary),
                json.dumps(warnings)
            )
        )
        return int(cursor.lastrowid)


def get_recent_evaluations_count(model_id: str) -> dict[str, int]:
    init_db()
    counts = {
        "inside": 0,
        "borderline": 0,
        "outside": 0,
        "unknown": 0
    }
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT domain_status, COUNT(*) FROM admet_domain_evaluations WHERE model_id = ? GROUP BY domain_status",
            (model_id,)
        ).fetchall()
        for row in rows:
            status = row[0]
            count = row[1]
            if status == "inside_domain":
                counts["inside"] = count
            elif status == "borderline":
                counts["borderline"] = count
            elif status == "outside_domain":
                counts["outside"] = count
            else:
                counts["unknown"] = count
    return counts


def get_domain_summary_by_model(model_id: str) -> dict[str, Any] | None:
    try:
        stats = get_or_calculate_domain_stats(model_id)
    except:
        return None

    descriptor_stats = {}
    for j, col in enumerate(FEATURE_COLUMNS):
        # We can extract actual min/max/mean/std from calculated training stats
        descriptor_stats[col] = {
            "min": round(stats["mins"][j], 4),
            "max": round(stats["maxs"][j], 4),
            "mean": round(stats["means"][j], 4),
            "std": round(stats["stds"][j], 4),
        }

    warnings = []
    if stats["record_count"] < 30:
        warnings.append(f"Training dataset size is very small (N={stats['record_count']} < 30). Centroid percentiles may be statistically unstable.")

    # Check for external validation
    from app.services.admet_validation_service import get_latest_external_validation_by_model
    latest_val = get_latest_external_validation_by_model(model_id)
    if not latest_val:
        warnings.append("No external validation available for this model.")

    return {
        "descriptor_stats": descriptor_stats,
        "training_record_count": stats["record_count"],
        "task_type": stats["task_type"],
        "dataset_name": stats["dataset_name"],
        "domain_thresholds_used": {
            "centroid_distance_threshold_95": round(stats["p95_centroid"], 4),
            "centroid_distance_threshold_99": round(stats["p99_centroid"], 4),
        },
        "warnings": warnings,
        "limitations": [
            "Descriptor range check is heuristic and z-score Euclidean boundaries assume descriptor normality.",
            "Wet-lab validation and expert review are required before scientific decision-making."
        ]
    }


def get_domain_summaries_all() -> list[dict[str, Any]]:
    models = discover_trained_models()
    summaries = []
    for m in models:
        m_id = m["model_id"]
        summary = get_domain_summary_by_model(m_id)
        if summary:
            summary["model_id"] = m_id
            summaries.append(summary)
    return summaries


def get_domain_evaluations_all() -> list[dict[str, Any]]:
    init_db()
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM admet_domain_evaluations ORDER BY id DESC").fetchall()
    evals = []
    for row in rows:
        try:
            summary = json.loads(row["summary_json"])
        except:
            summary = {}
        evals.append({
            "id": row["id"],
            "model_id": row["model_id"],
            "training_run_id": row["training_run_id"],
            "smiles": row["smiles"],
            "canonical_smiles": row["canonical_smiles"],
            "domain_status": row["domain_status"],
            "uncertainty_level": row["uncertainty_level"],
            "summary": summary,
            "warnings": json.loads(row["warnings_json"]) if row["warnings_json"] else [],
            "created_at": row["created_at"],
        })
    return evals
