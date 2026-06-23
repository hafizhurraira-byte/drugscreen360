import json
import sqlite3
from typing import Any, Dict, Optional
from app.database import get_connection, init_db

COMMON_TARGET_EQUIVALENCES = {
    "egfr": {"egfr", "erbb1", "erbb-1", "epidermal growth factor receptor", "epidermalgrowthfactorreceptor"},
    "her2": {"her2", "erbb2", "receptor tyrosine-protein kinase erbb-2", "receptortyrosineproteinkinaseerbb2", "erbb-2"},
    "cox2": {"cox2", "cox-2", "ptgs2", "prostaglandin-endoperoxide synthase 2", "prostaglandinendoperoxidesynthase2"},
    "dpp4": {"dpp4", "dpp-4", "dipeptidyl peptidase 4", "dipeptidylpeptidase4"},
    "ache": {"ache", "acetylcholinesterase"},
    "ar": {"ar", "androgen receptor", "androgenreceptor"},
    "vegfr2": {"vegfr2", "kdr", "vascular endothelial growth factor receptor 2", "vascularendothelialgrowthfactorreceptor2"},
    "bcr-abl": {"bcr-abl", "bcr-abl1", "bcr/abl", "abl1 fusion", "bcr-abl tyrosine kinase", "bcr-abl fusion protein", "bcrabl", "bcrabl1", "abl1fusion", "bcrabltyrosinekinase", "bcrablfusionprotein"}
}

def are_targets_equivalent(user_target: Optional[str], resolved_target: Optional[str]) -> bool:
    if not user_target or not resolved_target:
        return False
    
    u_raw = user_target.strip()
    r_raw = resolved_target.strip()
    
    # Direct normalized comparison
    u_norm = "".join(c for c in u_raw.lower() if c.isalnum())
    r_norm = "".join(c for c in r_raw.lower() if c.isalnum())
    
    if u_norm == r_norm:
        return True
        
    # Group comparison
    for group in COMMON_TARGET_EQUIVALENCES.values():
        normalized_group = { "".join(c for c in item.lower() if c.isalnum()) for item in group }
        if u_norm in normalized_group and r_norm in normalized_group:
            return True
            
    # Substring match for longer names
    if u_norm in r_norm or r_norm in u_norm:
        if len(u_norm) >= 4 or len(r_norm) >= 4:
            return True
            
    return False

def resolve_target_status(user_target: Optional[str], resolved_target: Optional[str], priority_score: float = 100) -> str:
    if not user_target or not resolved_target:
        return "no_match"
    
    u_raw = user_target.strip()
    r_raw = resolved_target.strip()
    
    if u_raw.lower() == r_raw.lower():
        return "exact_symbol_match"
        
    u_norm = "".join(c for c in u_raw.lower() if c.isalnum())
    r_norm = "".join(c for c in r_raw.lower() if c.isalnum())
    
    if u_norm == r_norm:
        return "full_name_match"
        
    # Check groups
    for group in COMMON_TARGET_EQUIVALENCES.values():
        normalized_group = { "".join(c for c in item.lower() if c.isalnum()) for item in group }
        if u_norm in normalized_group and r_norm in normalized_group:
            return "synonym_match"
            
    if are_targets_equivalent(user_target, resolved_target):
        return "synonym_match"
        
    if priority_score < 40:
        return "ambiguous_match"
        
    return "mismatch_warning"

def save_disease_to_lead_run(run_data: Dict[str, Any]) -> int:
    init_db()
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO disease_to_lead_runs (
                workflow_id, project_id, report_id,
                disease_name_raw, disease_name_normalized,
                user_entered_target_raw, user_entered_target_normalized,
                resolved_target_name, resolved_target_id,
                resolved_target_gene_symbol, resolved_target_organism,
                target_resolution_confidence, target_resolution_status,
                known_compound_raw, known_compound_normalized, known_compound_id,
                candidate_limit, similarity_limit, analysis_depth, scoring_profile,
                generated_candidate_list, deduplicated_candidate_list, duplicate_records_removed,
                admet_results, prioritization_results, validation_planner_results,
                missing_evidence_summary
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_data.get("workflow_id"),
                run_data.get("project_id"),
                run_data.get("report_id"),
                run_data.get("disease_name_raw"),
                run_data.get("disease_name_normalized"),
                run_data.get("user_entered_target_raw"),
                run_data.get("user_entered_target_normalized"),
                run_data.get("resolved_target_name"),
                run_data.get("resolved_target_id"),
                run_data.get("resolved_target_gene_symbol"),
                run_data.get("resolved_target_organism"),
                run_data.get("target_resolution_confidence"),
                run_data.get("target_resolution_status"),
                run_data.get("known_compound_raw"),
                run_data.get("known_compound_normalized"),
                run_data.get("known_compound_id"),
                run_data.get("candidate_limit"),
                run_data.get("similarity_limit"),
                run_data.get("analysis_depth"),
                run_data.get("scoring_profile"),
                json.dumps(run_data.get("generated_candidate_list") or []),
                json.dumps(run_data.get("deduplicated_candidate_list") or []),
                run_data.get("duplicate_records_removed", 0),
                json.dumps(run_data.get("admet_results") or []),
                json.dumps(run_data.get("prioritization_results") or []),
                json.dumps(run_data.get("validation_planner_results") or []),
                json.dumps(run_data.get("missing_evidence_summary") or [])
            )
        )
        run_id = int(cursor.lastrowid)
    return run_id

def get_disease_to_lead_run(run_id: Any) -> Optional[Dict[str, Any]]:
    if not run_id:
        return None
    init_db()
    
    # Try looking up by integer ID or string workflow_id (UUID)
    row = None
    with get_connection() as connection:
        if isinstance(run_id, int) or (isinstance(run_id, str) and run_id.isdigit()):
            row = connection.execute(
                "SELECT * FROM disease_to_lead_runs WHERE id = ?", (int(run_id),)
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT * FROM disease_to_lead_runs WHERE workflow_id = ?", (str(run_id),)
            ).fetchone()
            
    if not row:
        return None
        
    data = dict(row)
    # Parse JSON fields
    for field in [
        "generated_candidate_list", "deduplicated_candidate_list",
        "admet_results", "prioritization_results", "validation_planner_results",
        "missing_evidence_summary"
    ]:
        if data.get(field):
            try:
                data[field] = json.loads(data[field])
            except Exception:
                data[field] = []
        else:
            data[field] = []
            
    return data

def update_disease_to_lead_run_report(run_id: Any, report_id: int) -> None:
    if not run_id:
        return
    init_db()
    with get_connection() as connection:
        if isinstance(run_id, int) or (isinstance(run_id, str) and run_id.isdigit()):
            connection.execute(
                "UPDATE disease_to_lead_runs SET report_id = ? WHERE id = ?", (report_id, int(run_id))
            )
        else:
            connection.execute(
                "UPDATE disease_to_lead_runs SET report_id = ? WHERE workflow_id = ?", (report_id, str(run_id))
            )

def get_latest_disease_to_lead_run_for_project(project_id: int) -> Optional[Dict[str, Any]]:
    if not project_id:
        return None
    init_db()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM disease_to_lead_runs WHERE project_id = ? ORDER BY id DESC LIMIT 1",
            (project_id,)
        ).fetchone()
    if not row:
        return None
    
    # Parse same JSON fields
    data = dict(row)
    for field in [
        "generated_candidate_list", "deduplicated_candidate_list",
        "admet_results", "prioritization_results", "validation_planner_results",
        "missing_evidence_summary"
    ]:
        if data.get(field):
            try:
                data[field] = json.loads(data[field])
            except Exception:
                data[field] = []
        else:
            data[field] = []
    return data

def _get_parent_smiles(smiles: str) -> str:
    if not smiles:
        return ""
    fragments = smiles.split('.')
    if len(fragments) <= 1:
        return smiles
    fragments.sort(key=len, reverse=True)
    return fragments[0].strip()

def _canonical_smiles(smiles: str) -> Optional[str]:
    if not smiles:
        return None
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            canon_full = Chem.MolToSmiles(mol, canonical=True)
            parent = _get_parent_smiles(canon_full)
            pmol = Chem.MolFromSmiles(parent)
            if pmol:
                return Chem.MolToSmiles(pmol, canonical=True)
            return parent
    except Exception:
        pass
    return _get_parent_smiles(smiles)

def get_candidate_dedup_key(c: Dict[str, Any]) -> str:
    for smiles_key in ["smiles", "canonical_smiles"]:
        smiles = c.get(smiles_key)
        if smiles:
            canon = _canonical_smiles(smiles)
            if canon:
                return f"smiles:{canon}"
    cid = c.get("compound_id") or c.get("molecule_chembl_id")
    if cid:
        return f"id:{str(cid).strip().lower()}"
    name = c.get("compound_name")
    if name:
        return f"name:{str(name).strip().lower()}"
    return "unknown"

def candidate_quality_sort_key(c: Dict[str, Any]) -> tuple:
    has_valid_smiles = 0
    sm = c.get("canonical_smiles") or c.get("smiles")
    if sm:
        try:
            from rdkit import Chem
            mol = Chem.MolFromSmiles(sm)
            if mol:
                has_valid_smiles = 1
        except Exception:
            pass
            
    rank_val = c.get("rank") or c.get("candidate_rank")
    if rank_val is None:
        rank_val = 999999
    neg_rank = -int(rank_val)
    
    desc = c.get("descriptors") or {}
    desc_count = len([k for k, v in desc.items() if v is not None])
    
    score_fields = [
        "total_score", "activity_value", "potency_score", "data_quality_score",
        "evidence_score", "overall_candidate_score", "lipinski_status", "veber_status"
    ]
    score_count = len([f for f in score_fields if c.get(f) is not None])
    
    missing_ev = c.get("missing_evidence") or []
    neg_missing_count = -len(missing_ev)
    
    return (has_valid_smiles, neg_rank, desc_count, score_count, neg_missing_count)

def deduplicate_candidates(candidates: list) -> list:
    seen = {}
    for c in candidates:
        if not isinstance(c, dict):
            if hasattr(c, "model_dump"):
                c_dict = c.model_dump()
            elif hasattr(c, "__dict__"):
                c_dict = c.__dict__
            else:
                continue
        else:
            c_dict = c
            
        key = get_candidate_dedup_key(c_dict)
        if key not in seen:
            seen[key] = []
        seen[key].append(c_dict)
    
    deduped = []
    for key, group in seen.items():
        group.sort(key=candidate_quality_sort_key, reverse=True)
        deduped.append(group[0])
    return deduped

def create_disease_to_lead_run_snapshot(request: Any) -> int:
    disease_name = (request.disease_name or "breast cancer").strip()
    user_target = (request.user_entered_target or "EGFR").strip()
    resolved_target = (request.resolved_target or "EGFR").strip()
    known_compound = (request.known_compound or "").strip()
    
    raw_candidates = []
    scoring_profile = "balanced_admet"
    warnings = []
    
    init_db()
    with get_connection() as connection:
        run_row = None
        if request.prioritization_run_id:
            run_row = connection.execute(
                "SELECT * FROM admet_lead_prioritization_runs WHERE id = ?",
                (request.prioritization_run_id,)
            ).fetchone()
        elif request.project_id:
            run_row = connection.execute(
                "SELECT * FROM admet_lead_prioritization_runs WHERE project_id = ? ORDER BY id DESC LIMIT 1",
                (request.project_id,)
            ).fetchone()
            
        if run_row:
            scoring_profile = run_row["scoring_profile"] or "balanced_admet"
            summary = json.loads(run_row["summary_json"]) if run_row["summary_json"] else {}
            raw_candidates = summary.get("ranked_candidates", [])
            warnings = json.loads(run_row["warnings_json"]) if run_row["warnings_json"] else []
            
        plan_row = None
        if request.validation_plan_id:
            plan_row = connection.execute(
                "SELECT * FROM experimental_validation_plans WHERE id = ?",
                (request.validation_plan_id,)
            ).fetchone()
        elif request.project_id:
            plan_row = connection.execute(
                "SELECT * FROM experimental_validation_plans WHERE project_id = ? ORDER BY id DESC LIMIT 1",
                (request.project_id,)
            ).fetchone()
            
        validation_planner_results = {}
        if plan_row:
            validation_planner_results = {
                "plan_title": plan_row["plan_title"],
                "recommended_assays": []
            }
            plan_summary = json.loads(plan_row["summary_json"]) if plan_row["summary_json"] else {}
            candidate_plans = plan_summary.get("candidate_plans", [])
            for cp in candidate_plans:
                comp_name = cp.get("compound_name") or cp.get("compound_id")
                for assay in cp.get("recommended_assays", []):
                    validation_planner_results["recommended_assays"].append({
                        "compound_name": comp_name,
                        "assay_name": assay.get("assay_name"),
                        "recommendation_priority": assay.get("recommendation_priority"),
                        "rationale": assay.get("rationale")
                    })

    target_resolution_status = resolve_target_status(user_target, resolved_target)
    unique_candidates = deduplicate_candidates(raw_candidates)
    duplicate_records_removed = len(raw_candidates) - len(unique_candidates)
    
    admet_results = []
    for c in unique_candidates:
        admet_results.append({
            "compound_name": c.get("compound_name") or c.get("compound_id") or "Unnamed",
            "smiles": c.get("smiles") or c.get("canonical_smiles") or "N/A",
            "overall_concern": c.get("rule_based_admet_summary", {}).get("concern_level", "low_concern"),
            "absorption": c.get("absorption_risk") or "low_absorption_risk",
            "solubility": c.get("solubility_risk") or "high_solubility",
            "descriptors": c.get("descriptors") or {}
        })
        
    missing_evidence_summary = []
    for c in unique_candidates:
        missing_evidence_summary.append({
            "compound_name": c.get("compound_name") or c.get("compound_id") or "Unnamed",
            "missing_evidence": c.get("missing_evidence") or []
        })
        
    import uuid
    run_data = {
        "workflow_id": str(uuid.uuid4()),
        "project_id": request.project_id,
        "report_id": None,
        "disease_name_raw": request.disease_name or disease_name,
        "disease_name_normalized": disease_name,
        "user_entered_target_raw": request.user_entered_target or user_target,
        "user_entered_target_normalized": user_target,
        "resolved_target_name": resolved_target,
        "resolved_target_id": resolved_target,
        "resolved_target_gene_symbol": resolved_target,
        "resolved_target_organism": "Homo sapiens",
        "target_resolution_confidence": 100.0 if target_resolution_status == "exact_symbol_match" else 80.0,
        "target_resolution_status": target_resolution_status,
        "known_compound_raw": request.known_compound or known_compound,
        "known_compound_normalized": known_compound,
        "known_compound_id": f"KNOWN-{known_compound.upper().replace(' ', '-')}" if known_compound else None,
        "candidate_limit": request.candidate_limit or 10,
        "similarity_limit": request.similarity_limit or 10,
        "analysis_depth": request.analysis_depth or "standard",
        "scoring_profile": scoring_profile,
        "generated_candidate_list": raw_candidates,
        "deduplicated_candidate_list": unique_candidates,
        "duplicate_records_removed": duplicate_records_removed,
        "admet_results": admet_results,
        "prioritization_results": {
            "ranked_candidates": raw_candidates,
            "warnings": warnings
        },
        "validation_planner_results": validation_planner_results,
        "missing_evidence_summary": missing_evidence_summary
    }
    
    return save_disease_to_lead_run(run_data)

