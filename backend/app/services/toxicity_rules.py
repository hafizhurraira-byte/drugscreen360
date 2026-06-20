from rdkit import Chem

from app.models.admet_models import NotImplementedToxicityAssessment, StructuralAlertsAssessment


SMARTS_ALERTS = {
    "Nitro aromatic alert": "[N+](=O)[O-]",
    "Aldehyde alert": "[CX3H1](=O)[#6]",
    "Aniline alert": "c[NH2]",
    "Michael acceptor-like enone": "C=CC(=O)",
}


def assess_structural_alerts(smiles: str) -> StructuralAlertsAssessment:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("Invalid SMILES for structural alert assessment.")

    alerts = []
    for label, smarts in SMARTS_ALERTS.items():
        pattern = Chem.MolFromSmarts(smarts)
        if pattern is not None and mol.HasSubstructMatch(pattern):
            alerts.append(label)

    if len(alerts) >= 2:
        risk = "High"
    elif alerts:
        risk = "Medium"
    else:
        risk = "Low"

    return StructuralAlertsAssessment(
        structural_alerts=alerts,
        structural_alert_risk=risk,
        reasons=alerts or ["No broad SMARTS-based structural alerts found in this MVP screen."],
    )


def herg_status() -> NotImplementedToxicityAssessment:
    return NotImplementedToxicityAssessment(
        prediction_status="Not implemented",
        recommended_tests=["hERG patch clamp or validated hERG screen"],
        limitation="No hERG prediction model is implemented in this MVP.",
    )


def ames_genotoxicity_status() -> NotImplementedToxicityAssessment:
    return NotImplementedToxicityAssessment(
        prediction_status="Not implemented",
        recommended_tests=["Ames test", "In vitro micronucleus assay", "Chromosomal aberration assay if needed"],
        limitation="No Ames, mutagenicity, carcinogenicity, or genotoxicity prediction model is implemented in this MVP.",
    )


def hepatotoxicity_status() -> NotImplementedToxicityAssessment:
    return NotImplementedToxicityAssessment(
        prediction_status="Not implemented",
        recommended_tests=[
            "Hepatocyte toxicity assay",
            "Liver enzyme panel in later nonclinical studies",
            "Repeat-dose toxicity study if moving forward",
        ],
        limitation="No hepatotoxicity prediction model is implemented in this MVP.",
    )
