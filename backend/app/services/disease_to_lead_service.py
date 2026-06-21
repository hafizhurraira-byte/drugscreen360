import uuid
from typing import Any
from fastapi import HTTPException

from app.models.disease_to_lead_models import DiseaseToLeadRequest
from app.services import open_targets_service, chembl_service, similarity_service
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

def run_disease_to_lead_workflow(payload: DiseaseToLeadRequest) -> dict[str, Any]:
    warnings = []
    missing_steps = []
    
    # 1. Target Discovery
    target_id = None
    target_name = payload.target_name
    
    if target_name:
        try:
            targets = chembl_service.search_targets(target_name)
            if targets:
                # Select the best target (single protein/human)
                human_target = next((t for t in targets if t.organism == "Homo sapiens"), None)
                selected_t = human_target or targets[0]
                target_id = selected_t.target_chembl_id
                target_name = selected_t.preferred_name or selected_t.target_chembl_id
            else:
                warnings.append(f"No ChEMBL target found for target_name: {target_name}")
        except Exception as e:
            warnings.append(f"ChEMBL target search failed: {e}")
            
    if not target_id and payload.disease_name:
        # Search Open Targets
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
                    except:
                        pass
                else:
                    warnings.append(f"No Open Targets associated with disease: {payload.disease_name}")
            else:
                warnings.append(f"No Open Targets disease found matching: {payload.disease_name}")
        except Exception as e:
            warnings.append(f"Open Targets disease search failed: {e}")
            
    # Fallback: search ChEMBL with disease name
    if not target_id and payload.disease_name:
        try:
            targets = chembl_service.search_targets(payload.disease_name)
            if targets:
                selected_t = targets[0]
                target_id = selected_t.target_chembl_id
                target_name = selected_t.preferred_name or selected_t.target_chembl_id
        except Exception as e:
            warnings.append(f"ChEMBL fallback target search failed: {e}")
            
    if not target_id:
        raise HTTPException(
            status_code=400,
            detail=f"Could not resolve target for disease: '{payload.disease_name}' and target: '{payload.target_name}'."
        )
        
    # 2. Candidate Discovery
    candidates = []
    try:
        raw_candidates = chembl_service.get_target_candidates(target_id, limit=payload.candidate_limit)
        candidates = [c.model_dump() for c in raw_candidates]
    except Exception as e:
        warnings.append(f"Could not load candidates from ChEMBL for target {target_id}: {e}")
        missing_steps.append("candidate_discovery")
        
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
        except Exception as e:
            warnings.append(f"Similarity expansion failed for reference compound '{ref_compound}': {e}")
            missing_steps.append("similarity_expansion")
            
    # 4. Project Initialization
    project_id = payload.project_id
    if not project_id:
        try:
            proj = create_project(
                ProjectCreateRequest(
                    title=f"Disease-to-Lead: {payload.disease_name or target_name}",
                    description=f"Auto-generated Disease-to-Lead workflow for disease '{payload.disease_name}' and target '{target_name}'.",
                    disease_area=payload.disease_name or "General",
                    target_name=target_name,
                    project_type="disease_screening",
                    status="active",
                    notes="Auto-generated workspace from Disease-to-Lead One-Click Workflow."
                )
            )
            project_id = proj.id
        except Exception as e:
            warnings.append(f"Failed to create new project: {e}")
            
    # Attach candidates to project
    attached_candidate_ids = []
    for c in candidates:
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
                
    # Attach similar compounds
    for s in similar_candidates:
        if project_id:
            try:
                attach_project_item(
                    project_id,
                    ProjectAttachRequest(
                        item_type="similarity_analog",
                        item_id=s["molecule_chembl_id"],
                        item_title=s.get("compound_name") or s["molecule_chembl_id"],
                        metadata={
                            "smiles": s["canonical_smiles"],
                            "similarity_score": s.get("similarity_score"),
                            "parent_compound": ref_compound
                        }
                    )
                )
            except:
                pass

    # 5. Full Screening & ADMET Analysis
    # Analyze first 3-5 candidates depending on depth
    analysis_candidates = candidates
    if payload.analysis_depth == "quick":
        analysis_candidates = candidates[:3]
    elif payload.analysis_depth == "standard":
        analysis_candidates = candidates[:5]
        
    analysis_similars = similar_candidates
    if payload.analysis_depth == "quick":
        analysis_similars = similar_candidates[:3]
    elif payload.analysis_depth == "standard":
        analysis_similars = similar_candidates[:5]
        
    all_compounds_to_analyze = []
    seen_smiles = set()
    
    for c in analysis_candidates:
        sm = c["canonical_smiles"]
        if sm and sm not in seen_smiles:
            seen_smiles.add(sm)
            all_compounds_to_analyze.append((c.get("compound_name") or c["molecule_chembl_id"], sm))
            
    for s in analysis_similars:
        sm = s["canonical_smiles"]
        if sm and sm not in seen_smiles:
            seen_smiles.add(sm)
            all_compounds_to_analyze.append((s.get("compound_name") or s["molecule_chembl_id"], sm))
            
    screening_results = []
    admet_results = []
    
    for name, smiles in all_compounds_to_analyze:
        try:
            desc = calculate_descriptors(smiles)
            rules = evaluate_rules(desc)
            admet_tox = evaluate_admet_toxicity(smiles, desc)
            
            model_predictions = predict_admet(
                smiles,
                ["rule_based_admet_v1", "trained_local_admet_model"],
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
    for c in analysis_candidates:
        lead_inputs.append(
            LeadCandidateInput(
                compound_name=c.get("compound_name") or c["molecule_chembl_id"],
                smiles=c["canonical_smiles"],
                compound_id=c["molecule_chembl_id"]
            )
        )
    for s in analysis_similars:
        lead_inputs.append(
            LeadCandidateInput(
                compound_name=s.get("compound_name") or s["molecule_chembl_id"],
                smiles=s["canonical_smiles"],
                compound_id=s["molecule_chembl_id"]
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
            
    # 7. Validation Planner
    validation_plan_id = None
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
                    plan_title=f"Validation Plan: {payload.disease_name or target_name}",
                    candidates=validation_candidates,
                    include_toxicity_assays=True,
                    include_cyp_assays=True,
                    include_herg_assays=True,
                    include_hepatotoxicity_assays=True,
                    custom_assays=[]
                )
            )
            validation_plan_id = val_res.plan_id
        except Exception as e:
            warnings.append(f"Validation planner failed: {e}")
            missing_steps.append("validation_plan")
            
    # 8. Final Report Generation
    final_report_id = None
    if project_id:
        try:
            report_res = create_final_project_report(
                FinalProjectReportRequest(
                    project_id=project_id,
                    include_screening=True,
                    include_admet=True,
                    include_explainability=True,
                    include_prioritization=True,
                    include_validation=True,
                    include_experimental_feedback=True
                )
            )
            final_report_id = report_res.report_id
        except Exception as e:
            warnings.append(f"Final report generation failed: {e}")
            missing_steps.append("final_report")
            
    return {
        "workflow_id": str(uuid.uuid4()),
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
        "final_report_id": final_report_id,
        "warnings": warnings,
        "missing_steps": missing_steps,
        "scientific_notice": "Computational estimate only. Requires experimental and external validation."
    }
