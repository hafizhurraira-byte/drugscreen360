from io import BytesIO

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.constants import DISCLAIMER
from app.models.schemas import ScreeningHistoryDetail, ScreeningHistoryItem, ScreeningRequest, ScreeningReport
from app.services.admet_toxicity_engine import evaluate_admet_toxicity
from app.services.descriptors import calculate_descriptors, parse_smiles, render_structure_image_base64
from app.services.history import (
    delete_all_history,
    delete_history_item,
    get_history_detail,
    list_history,
    save_screening_report,
    update_report_id,
)
from app.services.admet_predictor_service import predict_admet
from app.services.pubchem import PubChemNotFoundError, PubChemUnavailableError, resolve_compound
from app.services.reports import build_docx_report, build_pdf_report
from app.services.rules import (
    build_decision,
    build_placeholder_modules,
    evaluate_rules,
    plan_experimental_tests,
)

router = APIRouter(tags=["screening"])


@router.post("/screen", response_model=ScreeningReport)
def screen_compound(payload: ScreeningRequest):
    if payload.input_type == "smiles":
        parse_smiles(payload.query)

    try:
        identity = resolve_compound(payload.query, payload.input_type)
    except PubChemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PubChemUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    smiles = identity.canonical_smiles or identity.isomeric_smiles
    if not smiles:
        raise HTTPException(
            status_code=422,
            detail="PubChem did not return a usable SMILES string for this compound.",
        )

    descriptors = calculate_descriptors(smiles)
    identity.structure_image_base64 = render_structure_image_base64(smiles)
    rules = evaluate_rules(descriptors)
    admet_toxicity = evaluate_admet_toxicity(smiles, descriptors)
    model_predictions = predict_admet(smiles, ["rule_based_admet_v1", "local_admet_model", "external_admet_service", "tox_model_adapter"], True)
    lab_tests = plan_experimental_tests(descriptors, rules)
    decision = build_decision(rules, lab_tests)
    admet_placeholder, toxicity_placeholder = build_placeholder_modules()

    report = ScreeningReport(
        disclaimer=DISCLAIMER,
        input=payload,
        compound_identity=identity,
        physicochemical_properties=descriptors,
        drug_likeness=rules,
        admet_placeholder=admet_placeholder,
        toxicity_placeholder=toxicity_placeholder,
        admet_toxicity_v1=admet_toxicity,
        model_predictions=model_predictions,
        required_lab_tests=lab_tests,
        go_no_go_recommendation=decision,
        limitations=[
            "This MVP uses PubChem lookup, RDKit descriptors, and transparent rules only.",
            "No validated ADMET, toxicity, docking, clinical, or regulatory approval model is implemented yet.",
            "Results should be reviewed by qualified medicinal chemistry, toxicology, and regulatory experts.",
            "Experimental testing is required before any safety, efficacy, clinical, or market-readiness claim.",
        ],
    )
    screening_id = save_screening_report(report)
    update_report_id(screening_id, report)
    return report


@router.get("/screening/history", response_model=list[ScreeningHistoryItem])
def get_screening_history():
    return list_history()


@router.get("/screening/history/{screening_id}", response_model=ScreeningHistoryDetail)
def get_screening_history_item(screening_id: int):
    detail = get_history_detail(screening_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Screening history item not found.")
    return detail


@router.delete("/screening/history")
def clear_screening_history():
    deleted_count = delete_all_history()
    return {"deleted": True, "deleted_count": deleted_count}


@router.delete("/screening/history/{screening_id}")
def delete_screening_history_item(screening_id: int):
    deleted = delete_history_item(screening_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Screening history item not found.")
    return {"deleted": True, "id": screening_id}


@router.get("/report/{screening_id}/pdf")
def export_pdf_report(screening_id: int):
    detail = get_history_detail(screening_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Screening history item not found.")
    pdf_bytes = build_pdf_report(detail.report)
    filename = f"drugscreen360-report-{screening_id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/report/{screening_id}/docx")
def export_docx_report(screening_id: int):
    detail = get_history_detail(screening_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Screening history item not found.")
    docx_bytes = build_docx_report(detail.report)
    filename = f"drugscreen360-report-{screening_id}.docx"
    return StreamingResponse(
        BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
