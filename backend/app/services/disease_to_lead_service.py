import uuid
from typing import Any
from fastapi import HTTPException

from app.models.disease_to_lead_models import DiseaseToLeadRequest
from app.services import open_targets_service, chembl_service, similarity_service
from app.services.pubchem import resolve_compound
from app.services.descriptors import calculate_descriptors
from app.services.rules import evaluate_rules, build_decision, plan_experimental_tests
from app.services.admet_toxicity_engine import evaluate_admet_toxicity
from app.services.admet_predictor_service import predict_admet
from app.services.project_workspace_service import create_project, attach_project_item
from app.models.project_workspace_models import ProjectCreateRequest, ProjectAttachRequest
from app.services.admet_lead_service import prioritize_leads
from app.models.admet_lead_models import LeadPrioritizationRequest, LeadCandidateInput
from app.services.validation_planner_service import create_validation_plan
from app.models.validation_planner_models import ExperimentalValidationPlanRequest, ValidationCandidateInput
from app.services.final_report_service import create_final_project_report
from app.models.final_report_models import FinalProjectReportRequest

FRIENDLY_EXTERNAL_WARNING = "External candidate discovery is temporarily unavailable. Continuing with known/demo candidate data where possible."
NO_CANDIDATE_WARNING = "No candidates could be retrieved. Enter a known compound or run the guided demo."
KNOWN_COMPOUND_SMILES = {
    "aspirin": "CC(=O)OC1=CC=CC=C1C(=O)O",
    "caffeine": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
    "ibuprofen": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",
    "acetaminophen": "CC(=O)NC1=CC=C(C=C1)O",
    "paracetamol": "CC(=O)NC1=CC=C(C=C1)O",
    "metformin": "CN(C)C(=N)NC(=N)N",
}


def _add_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _known_compound_candidate(name: str | None) -> dict[str, Any] | None:
    if not name:
        return None
    cleaned = name.strip()
    if not cleaned:
        return None
    try:
        identity = resolve_compound(cleaned, "name")
        if identity.canonical_smiles:
            return {
                "molecule_chembl_id": f"KNOWN-{cleaned.upper().replace(' ', '-')}",
                "compound_name": identity.compound_name or cleaned,
                "canonical_smiles": identity.canonical_smiles,
                "activity_type": "not_available",
                "activity_value": None,
                "activity_units": None,
                "target_chembl_id": "known_compound_fallback",
                "source": "known_compound_fallback",
                "ranking_reason": "Known compound supplied by user; used because external candidate discovery was unavailable or incomplete.",
            }
    except Exception:
        fallback_smiles = KNOWN_COMPOUND_SMILES.get(cleaned.lower())
        if fallback_smiles:
            return {
                "molecule_chembl_id": f"KNOWN-{cleaned.upper().replace(' ', '-')}",
                "compound_name": cleaned,
                "canonical_smiles": fallback_smiles,
                "activity_type": "not_available",
                "activity_value": None,
                "activity_units": None,
                "target_chembl_id": "known_compound_fallback",
                "source": "known_compound_fallback",
                "ranking_reason": "Local known-compound fallback used because external lookup was unavailable.",
            }
    return None


def run_disease_to_lead_workflow(payload: DiseaseToLeadRequest) -> dict[str, Any]:
    warnings = []
    missing_steps = []
    
    # Import context helpers
    from app.services.disease_to_lead_context import (
        resolve_target_status,
        are_targets_equivalent,
        deduplicate_candidates,
        save_disease_to_lead_run,
        update_disease_to_lead_run_report
    )
    
    # 1. Target Discovery (target-first)
    target_id = None
    target_name = payload.target_name
    target_resolution_status = "no_match"
    target_organism = "Homo sapiens"
    target_confidence = 100.0
    
    if target_name:
        try:
            targets = chembl_service.search_targets(target_name)
            if targets:
                # Select the best target (single protein/human)
                human_target = next((t for t in targets if t.organism == "Homo sapiens"), None)
                selected_t = human_target or targets[0]
                target_id = selected_t.target_chembl_id
                target_name = selected_t.preferred_name or selected_t.target_chembl_id
                target_organism = selected_t.organism or "Homo sapiens"
                
                # Check confidence/equivalence
                priority_score = getattr(selected_t, 'target_priority_score', 100)
                target_resolution_status = resolve_target_status(payload.target_name, target_name, priority_score)
                target_confidence = float(priority_score)
                
                if target_resolution_status == "mismatch_warning":
                    warnings.append("Resolved target differs from user-entered target. Please verify target selection before interpretation.")
                elif target_resolution_status == "ambiguous_match":
                    warnings.append("Target resolution was ambiguous. Verify target selection.")
            else:
                target_resolution_status = "no_match"
                warnings.append(f"No ChEMBL target found for target_name: {payload.target_name}")
        except Exception:
            target_resolution_status = "no_match"
            _add_warning(warnings, FRIENDLY_EXTERNAL_WARNING)
            
    if not target_id and not payload.target_name and payload.disease_name:
        # ONLY fall back to searching target by disease if target_name was not provided
        try:
            diseases = open_targets_service.search_diseases(payload.disease_name)
            if diseases:
                disease = diseases[0]
                ot_targets = open_targets_service.get_disease_targets(disease.disease_id, limit=5)
                if ot_targets:
                    symbol = ot_targets[0].approved_symbol
                    try:
                        targets = chembl_service.search_targets(symbol)
                        if targets:
                            human_target = next((t for t in targets if t.organism == "Homo sapiens"), None)
                            selected_t = human_target or targets[0]
                            target_id = selected_t.target_chembl_id
                            target_name = selected_t.preferred_name or selected_t.target_chembl_id
                            target_organism = selected_t.organism or "Homo sapiens"
                            target_resolution_status = "synonym_match"
                    except Exception:
                        _add_warning(warnings, FRIENDLY_EXTERNAL_WARNING)
                        pass
                else:
                    warnings.append(f"No Open Targets associated with disease: {payload.disease_name}")
            else:
                warnings.append(f"No Open Targets disease found matching: {payload.disease_name}")
        except Exception:
            _add_warning(warnings, FRIENDLY_EXTERNAL_WARNING)
            
        # Fallback: search ChEMBL with disease name
        if not target_id:
            try:
                targets = chembl_service.search_targets(payload.disease_name)
                if targets:
                    selected_t = targets[0]
                    target_id = selected_t.target_chembl_id
                    target_name = selected_t.preferred_name or selected_t.target_chembl_id
                    target_organism = selected_t.organism or "Homo sapiens"
                    target_resolution_status = "full_name_match"
            except Exception:
                _add_warning(warnings, FRIENDLY_EXTERNAL_WARNING)
                
    if not target_id:
        known = _known_compound_candidate(payload.known_compound)
        if known:
            target_id = "known_compound_fallback"
            target_name = payload.target_name or "Known compound fallback"
            target_resolution_status = "synonym_match" if payload.target_name else "no_match"
            _add_warning(warnings, FRIENDLY_EXTERNAL_WARNING)
        else:
            raise HTTPException(
                status_code=400,
                detail="No candidates could be retrieved. Enter a known compound or run the guided demo."
            )
        
    # 2. Candidate Discovery
    candidates = []
    try:
        raw_candidates = chembl_service.get_target_candidates(target_id, limit=payload.candidate_limit)
        candidates = [c.model_dump() for c in raw_candidates]
    except Exception:
        _add_warning(warnings, FRIENDLY_EXTERNAL_WARNING)
        missing_steps.append("candidate_discovery")
    known_candidate = _known_compound_candidate(payload.known_compound)
    if known_candidate and not any(c.get("canonical_smiles") == known_candidate["canonical_smiles"] for c in candidates):
        candidates.insert(0, known_candidate)
        _add_warning(warnings, "Known compound was used as a fallback starting candidate.")
    if not candidates:
        _add_warning(warnings, NO_CANDIDATE_WARNING)
        
    # 3. Similarity Expansion
    similar_candidates = []
    ref_compound = payload.known_compound
    
    # If no known compound is provided but we have candidates, expand similarity on the first candidate
    if not ref_compound and candidates:
        ref_compound = candidates[0].get("compound_name") or candidates[0].get("molecule_chembl_id")
        
    if ref_compound:
        try:
            _, raw_similars, _, _ = similarity_service.search_similar_compounds(
                query=ref_compound,
                input_type="name" if not ref_compound.startswith("CHEMBL") else "chembl_id",
                source="chembl",
                threshold=70,
                limit=payload.similarity_limit
            )
            similar_candidates = [s.model_dump() for s in raw_similars]
        except Exception:
            _add_warning(warnings, "Similarity expansion is unavailable right now. Continuing with available candidates.")
            missing_steps.append("similarity_expansion")
            
    # Deduplicate combined candidates
    combined_candidates = candidates + similar_candidates
    unique_candidates = deduplicate_candidates(combined_candidates)
    duplicate_records_removed = len(combined_candidates) - len(unique_candidates)
            
    # 4. Project Initialization
    project_id = payload.project_id
    if not project_id:
        try:
            proj = create_project(
                ProjectCreateRequest(
                    title=f"Disease-to-Lead: {payload.disease_name or target_name}".strip(),
                    description=f"Auto-generated Disease-to-Lead workflow for disease '{payload.disease_name}' and target '{target_name}'.",
                    disease_area=payload.disease_name or "General",
                    target_name=target_name,
                    project_type="disease_screening",
                    status="active",
                    notes="Auto-generated workspace from Disease-to-Lead One-Click Workflow."
                )
            )
            project_id = proj.id
        except Exception:
            _add_warning(
                warnings,
                "Could not create a project automatically. Please create/select a project before generating final reports.",
            )
            
    # Attach unique candidates to project
    attached_candidate_ids = []
    for c in unique_candidates:
        if project_id:
            try:
                attached = attach_project_item(
                    project_id,
                    ProjectAttachRequest(
                        item_type="chembl_candidate",
                        item_id=c["molecule_chembl_id"],
                        item_title=c.get("compound_name") or c["molecule_chembl_id"],
                        metadata={
                            "smiles": c["canonical_smiles"],
                            "activity_value": c.get("activity_value"),
                            "activity_units": c.get("activity_units"),
                            "target_name": target_name
                        }
                    )
                )
                attached_candidate_ids.append(attached.item_id)
            except:
                pass

    # 5. Full Screening & ADMET Analysis
    # Analyze first 3-5 candidates depending on depth
    analysis_candidates = unique_candidates
    if payload.analysis_depth == "quick":
        analysis_candidates = unique_candidates[:3]
    elif payload.analysis_depth == "standard":
        analysis_candidates = unique_candidates[:5]
        
    screening_results = []
    admet_results = []
    
    for c in analysis_candidates:
        name = c.get("compound_name") or c["molecule_chembl_id"]
        smiles = c.get("canonical_smiles") or c.get("smiles")
        if not smiles:
            continue
        try:
            desc = calculate_descriptors(smiles)
            rules = evaluate_rules(desc)
            admet_tox = evaluate_admet_toxicity(smiles, desc)
            
            model_predictions = predict_admet(
                smiles,
                ["rule_based_admet_v1", "trained_local_admet_model", "multi_endpoint_admet_v1"],
                True
            )
            
            screening_results.append({
                "compound_name": name,
                "smiles": smiles,
                "descriptors": desc.model_dump(),
                "lipinski": rules.lipinski_rule_of_5,
                "veber": rules.veber_rule,
                "developability_risk": rules.developability_risk,
                "concern_level": admet_tox.overall.concern_level
            })
            
            admet_results.append({
                "compound_name": name,
                "smiles": smiles,
                "overall_concern": admet_tox.overall.concern_level,
                "absorption": admet_tox.absorption.absorption_risk,
                "solubility": admet_tox.solubility.solubility_risk,
                "descriptors": desc.model_dump(),
                "model_predictions": model_predictions.model_dump()
            })
            
            if project_id:
                try:
                    attach_project_item(
                        project_id,
                        ProjectAttachRequest(
                            item_type="screening_run",
                            item_id=name,
                            item_title=f"Screening: {name}",
                            metadata={
                                "smiles": smiles,
                                "developability_risk": rules.developability_risk,
                                "concern_level": admet_tox.overall.concern_level
                            }
                        )
                    )
                except:
                    pass
        except Exception as e:
            warnings.append(f"Screening/ADMET analysis failed for compound '{name}': {e}")
            
    # 6. Lead Prioritization
    lead_run_id = None
    lead_inputs = []
    for c in unique_candidates:
        lead_inputs.append(
            LeadCandidateInput(
                compound_name=c.get("compound_name") or c["molecule_chembl_id"],
                smiles=c.get("canonical_smiles") or c.get("smiles"),
                compound_id=c["molecule_chembl_id"],
                metadata={"target_name": target_name, "target_chembl_id": target_id}
            )
        )
        
    if lead_inputs:
        try:
            lead_res = prioritize_leads(
                LeadPrioritizationRequest(
                    source_type="manual",
                    project_id=project_id,
                    scoring_profile="balanced_admet",
                    candidates=lead_inputs,
                    include_trained_model=True,
                    include_domain=True,
                    include_explainability=True
                )
            )
            lead_run_id = lead_res.run_id
        except Exception as e:
            warnings.append(f"Lead prioritization failed: {e}")
            missing_steps.append("lead_ranking")
            lead_res = None
    else:
        lead_res = None
            
    # 7. Validation Planner
    validation_plan_id = None
    planner_status = "not_available"
    val_res = None
    validation_candidates = []
    for li in lead_inputs[:5]:
        validation_candidates.append(
            ValidationCandidateInput(
                compound_name=li.compound_name,
                smiles=li.smiles,
                compound_id=li.compound_id,
                priority_label="high_priority_for_review",
                evidence_strength="Moderate",
                warnings=["Computational priority review required."]
            )
        )
        
    if validation_candidates:
        try:
            val_res = create_validation_plan(
                ExperimentalValidationPlanRequest(
                    source_type="manual",
                    project_id=project_id,
                    plan_title=f"Validation Plan: {payload.disease_name or target_name}".strip(),
                    candidates=validation_candidates,
                    include_toxicity_assays=True,
                    include_cyp_assays=True,
                    include_herg_assays=True,
                    include_hepatotoxicity_assays=True,
                    custom_assays=[]
                )
            )
            validation_plan_id = val_res.plan_id
            planner_status = "completed"
        except Exception as e:
            planner_status = "warning"
            warnings.append(
                "Validation planning could not be completed for the current candidates. "
                "You can still review screening, ranking, and report outputs."
            )
            missing_steps.append("validation_plan")
    else:
        warnings.append("No valid candidate set is available for validation planning. Run candidate discovery or lead prioritization first.")
        missing_steps.append("validation_plan")

    # Save the run context snapshot to database
    workflow_id = str(uuid.uuid4())
    
    # Extract prioritization details
    ranked_candidates_data = []
    if lead_res:
        ranked_candidates_data = [c.model_dump() if hasattr(c, "model_dump") else c for c in lead_res.ranked_candidates]
        
    # Extract validation planner results
    validation_planner_results = {}
    if val_res:
        recommended_assays = []
        for cp in val_res.candidate_plans:
            comp_name = cp.compound_name or cp.compound_id
            for assay in cp.recommended_assays:
                recommended_assays.append({
                    "compound_name": comp_name,
                    "assay_name": assay.assay_name,
                    "recommendation_priority": assay.recommendation_priority,
                    "rationale": getattr(assay, "reason", getattr(assay, "rationale", ""))
                })
        validation_planner_results = {
            "plan_title": val_res.plan_title,
            "recommended_assays": recommended_assays
        }
        
    missing_evidence_summary = []
    for c in (ranked_candidates_data or unique_candidates):
        missing_evidence_summary.append({
            "compound_name": c.get("compound_name") or c.get("molecule_chembl_id") or c.get("compound_id") or "Unnamed",
            "missing_evidence": c.get("missing_evidence") or []
        })
        
    run_data = {
        "workflow_id": workflow_id,
        "project_id": project_id,
        "report_id": None,
        "disease_name_raw": payload.disease_name,
        "disease_name_normalized": (payload.disease_name or "").strip(),
        "user_entered_target_raw": payload.target_name,
        "user_entered_target_normalized": (payload.target_name or "").strip(),
        "resolved_target_name": target_name,
        "resolved_target_id": target_id,
        "resolved_target_gene_symbol": target_name,
        "resolved_target_organism": target_organism,
        "target_resolution_confidence": target_confidence,
        "target_resolution_status": target_resolution_status,
        "known_compound_raw": payload.known_compound,
        "known_compound_normalized": (payload.known_compound or "").strip(),
        "known_compound_id": known_candidate.get("molecule_chembl_id") if known_candidate else None,
        "candidate_limit": payload.candidate_limit,
        "similarity_limit": payload.similarity_limit,
        "analysis_depth": payload.analysis_depth,
        "scoring_profile": "balanced_admet",
        "generated_candidate_list": combined_candidates,
        "deduplicated_candidate_list": unique_candidates,
        "duplicate_records_removed": duplicate_records_removed,
        "admet_results": admet_results,
        "prioritization_results": {
            "ranked_candidates": ranked_candidates_data or unique_candidates,
            "warnings": warnings
        },
        "validation_planner_results": validation_planner_results,
        "missing_evidence_summary": missing_evidence_summary
    }
    
    run_id = save_disease_to_lead_run(run_data)
            
    # 8. Final Report Generation
    final_report_id = None
    if project_id:
        try:
            report_res = create_final_project_report(
                FinalProjectReportRequest(
                    project_id=project_id,
                    report_title=f"Disease-to-Lead Final Report: {payload.disease_name or target_name}".strip(),
                    include_screening=True,
                    include_admet_prediction=True,
                    include_model_training=True,
                    include_external_validation=True,
                    include_applicability_domain=True,
                    include_explainability=True,
                    include_lead_prioritization=True,
                    include_validation_planner=True,
                    include_experimental_feedback=True,
                    formats=["json", "pdf", "docx"],
                    report_mode="concise_disease_to_lead_report",
                    disease_to_lead_run_id=run_id,
                    disease_name=payload.disease_name,
                    user_entered_target=payload.target_name,
                    resolved_target=target_name,
                    known_compound=payload.known_compound,
                    candidate_limit=payload.candidate_limit,
                    similarity_limit=payload.similarity_limit,
                    analysis_depth=payload.analysis_depth
                )
            )
            final_report_id = report_res.report_id
            update_disease_to_lead_run_report(run_id, final_report_id)
        except Exception as e:
            _add_warning(warnings, f"Final report could not be generated right now. Error: {e}")
            missing_steps.append("final_report")
            
    return {
        "workflow_id": workflow_id,
        "disease_to_lead_run_id": run_id,
        "project_id": project_id,
        "disease_name": payload.disease_name,
        "target_name": target_name,
        "discovered_candidates": candidates,
        "similar_candidates": similar_candidates,
        "selected_candidates": [c for c in candidates if c["molecule_chembl_id"] in attached_candidate_ids] or candidates[:5],
        "screening_summary": {
            "total_analyzed": len(screening_results),
            "results": screening_results
        },
        "admet_summary": {
            "total_analyzed": len(admet_results),
            "results": admet_results
        },
        "lead_prioritization_run_id": lead_run_id,
        "validation_plan_id": validation_plan_id,
        "planner_status": planner_status,
        "final_report_id": final_report_id,
        "warnings": warnings,
        "missing_steps": missing_steps,
        "scientific_notice": "Computational estimate only. Requires experimental and external validation."
    }

