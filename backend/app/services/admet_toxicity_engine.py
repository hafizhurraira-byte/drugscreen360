from app.models.admet_models import AdmetToxicityAssessment, OverallAdmetToxScore
from app.models.schemas import DescriptorSet
from app.services.admet_rules import assess_absorption, assess_bbb_cns, assess_metabolism, assess_solubility
from app.services.descriptors import calculate_descriptors, parse_smiles
from app.services.toxicity_rules import (
    ames_genotoxicity_status,
    assess_structural_alerts,
    hepatotoxicity_status,
    herg_status,
)


def _risk_points(risk: str, low: int, medium: int, high: int) -> int:
    return {"Low": low, "Medium": medium, "High": high}.get(risk, medium)


def _unique(items: list[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


def evaluate_admet_toxicity(smiles: str, descriptors: DescriptorSet | None = None) -> AdmetToxicityAssessment:
    parse_smiles(smiles)
    d = descriptors or calculate_descriptors(smiles)

    absorption = assess_absorption(d)
    solubility = assess_solubility(d)
    bbb = assess_bbb_cns(d)
    metabolism = assess_metabolism()
    structural = assess_structural_alerts(smiles)
    herg = herg_status()
    ames = ames_genotoxicity_status()
    liver = hepatotoxicity_status()

    admet_points = min(
        50,
        _risk_points(absorption.absorption_risk, 0, 12, 22)
        + _risk_points(solubility.solubility_risk, 0, 10, 18)
        + (5 if bbb.bbb_exposure_flag == "Possible" else 2 if bbb.bbb_exposure_flag == "Caution" else 0),
    )
    tox_points = _risk_points(structural.structural_alert_risk, 0, 15, 30)
    missing_uncertainty = 20
    total = min(100, admet_points + tox_points + missing_uncertainty)
    concern = "High" if total >= 65 else "Medium" if total >= 35 else "Low"
    confidence = "Medium" if total < 65 and structural.structural_alert_risk == "Low" else "Low"

    followups = _unique(
        absorption.recommended_followups
        + solubility.recommended_followups
        + metabolism.recommended_tests
        + herg.recommended_tests
        + ames.recommended_tests
        + liver.recommended_tests
    )

    return AdmetToxicityAssessment(
        absorption=absorption,
        solubility=solubility,
        bbb_cns_flag=bbb,
        metabolism_status=metabolism,
        structural_alerts=structural,
        herg_status=herg,
        ames_genotoxicity_status=ames,
        hepatotoxicity_status=liver,
        overall=OverallAdmetToxScore(
            admet_rule_concern=admet_points,
            toxicity_structural_alert_concern=tox_points,
            missing_model_uncertainty=missing_uncertainty,
            overall_admet_tox_concern_score=total,
            concern_level=concern,
            confidence_level=confidence,
            explanation=(
                "Transparent score from descriptor ADMET flags, broad structural alerts, and uncertainty "
                "because CYP, hERG, Ames/genotoxicity, and hepatotoxicity models are not implemented."
            ),
        ),
        recommended_followup_tests=followups,
        limitations=[
            "Rule-based early screen only; not a validated ADMET/toxicity prediction model.",
            "CYP, hERG, Ames/genotoxicity, carcinogenicity, and hepatotoxicity models are not implemented.",
            "Experimental assays and expert review are required before safety or development decisions.",
        ],
    )
