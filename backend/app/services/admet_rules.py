from app.models.admet_models import AbsorptionAssessment, BbbCnsAssessment, MetabolismAssessment, SolubilityAssessment
from app.models.schemas import DescriptorSet


def assess_absorption(d: DescriptorSet) -> AbsorptionAssessment:
    reasons = []
    if d.molecular_weight > 500:
        reasons.append("MW > 500 may reduce oral absorption.")
    if d.logp > 5:
        reasons.append("LogP > 5 may create solubility/permeability risk.")
    if d.tpsa > 140:
        reasons.append("TPSA > 140 A^2 may reduce passive permeability.")
    if d.hydrogen_bond_donors > 5 or d.hydrogen_bond_acceptors > 10:
        reasons.append("Hydrogen bonding exceeds common oral drug-likeness ranges.")
    if d.rotatable_bonds > 10:
        reasons.append("Rotatable bonds > 10 may reduce permeability through high flexibility.")
    if d.formal_charge != 0:
        reasons.append("Non-zero formal charge may require permeability/transport follow-up.")

    if len(reasons) >= 3:
        risk = "High"
        flag = "Poor"
    elif reasons:
        risk = "Medium"
        flag = "Caution"
    else:
        risk = "Low"
        flag = "Favorable"

    return AbsorptionAssessment(
        absorption_risk=risk,
        oral_developability_flag=flag,
        reasons=reasons or ["No major descriptor-based oral absorption warnings."],
        recommended_followups=["Caco-2 permeability assay", "PAMPA permeability assay", "Oral formulation feasibility review"],
    )


def assess_solubility(d: DescriptorSet) -> SolubilityAssessment:
    reasons = []
    if d.logp > 4:
        reasons.append("LogP > 4 suggests increased solubility risk.")
    if d.molecular_weight > 500:
        reasons.append("MW > 500 can reduce aqueous solubility.")
    if d.aromatic_ring_count >= 3 and d.logp > 3:
        reasons.append("Aromatic ring count >= 3 with LogP > 3 may increase lipophilicity and poor solubility risk.")

    risk = "High" if len(reasons) >= 2 else "Medium" if reasons else "Low"
    followups = ["Kinetic solubility assay", "Thermodynamic solubility assay"]
    if risk in {"Medium", "High"}:
        followups.append("Salt/formulation screen")

    return SolubilityAssessment(
        solubility_risk=risk,
        reasons=reasons or ["No major descriptor-based solubility warnings."],
        recommended_followups=followups,
    )


def assess_bbb_cns(d: DescriptorSet) -> BbbCnsAssessment:
    limitation = "This is only a rule-based flag, not a validated CNS or BBB prediction."
    if d.tpsa > 120:
        return BbbCnsAssessment(
            bbb_exposure_flag="Unlikely",
            reasons=["TPSA > 120 A^2 generally disfavors passive BBB penetration."],
            limitation=limitation,
        )
    if d.tpsa < 90 and d.molecular_weight < 450 and 1 <= d.logp <= 4 and d.hydrogen_bond_donors <= 2:
        return BbbCnsAssessment(
            bbb_exposure_flag="Possible",
            reasons=["TPSA < 90, MW < 450, LogP 1-4, and low HBD are compatible with possible CNS exposure."],
            limitation=limitation,
        )
    return BbbCnsAssessment(
        bbb_exposure_flag="Caution",
        reasons=["Descriptors do not clearly rule in or rule out BBB exposure."],
        limitation=limitation,
    )


def assess_metabolism() -> MetabolismAssessment:
    return MetabolismAssessment(
        cyp_prediction_status="Not implemented",
        metabolism_risk_flag="Follow-up required",
        recommended_tests=[
            "Microsomal stability",
            "Hepatocyte stability",
            "CYP inhibition panel",
            "CYP induction panel if advanced development",
        ],
        limitation="No CYP substrate, inhibition, or induction prediction model is implemented in this MVP.",
    )
