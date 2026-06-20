from app.models.schemas import DescriptorSet, PlaceholderModule, RecommendedTest, RuleEvaluation


def evaluate_rules(d: DescriptorSet) -> RuleEvaluation:
    lipinski_violations = []
    if d.molecular_weight > 500:
        lipinski_violations.append("Molecular weight is greater than 500.")
    if d.logp > 5:
        lipinski_violations.append("LogP is greater than 5.")
    if d.hydrogen_bond_donors > 5:
        lipinski_violations.append("Hydrogen bond donors are greater than 5.")
    if d.hydrogen_bond_acceptors > 10:
        lipinski_violations.append("Hydrogen bond acceptors are greater than 10.")

    veber_violations = []
    if d.rotatable_bonds > 10:
        veber_violations.append("Rotatable bonds are greater than 10.")
    if d.tpsa > 140:
        veber_violations.append("TPSA is greater than 140 A^2.")

    all_violations = lipinski_violations + veber_violations
    caution_reasons = list(all_violations)

    if d.formal_charge != 0:
        caution_reasons.append("Compound has a non-zero formal charge.")
    if d.logp < -1:
        caution_reasons.append("Very low LogP may indicate permeability risk.")
    if d.tpsa > 90:
        caution_reasons.append("TPSA above 90 A^2 may reduce passive permeability and CNS exposure.")
    if d.ring_count > 6:
        caution_reasons.append("High ring count may increase structural complexity.")

    if len(all_violations) == 0 and len(caution_reasons) <= 1:
        status = "Good"
        risk = "Low"
    elif len(all_violations) <= 2 and len(caution_reasons) <= 4:
        status = "Warning"
        risk = "Medium"
    else:
        status = "Poor"
        risk = "High"

    return RuleEvaluation(
        lipinski_rule_of_5={
            "passed": len(lipinski_violations) <= 1,
            "violation_count": len(lipinski_violations),
            "violations": lipinski_violations,
        },
        veber_rule={
            "passed": len(veber_violations) == 0,
            "violation_count": len(veber_violations),
            "violations": veber_violations,
        },
        basic_drug_likeness_status=status,
        developability_risk=risk,
        reasons=caution_reasons or ["No major rule-based developability warnings in the MVP screen."],
    )


def plan_experimental_tests(d: DescriptorSet, rules: RuleEvaluation) -> list[RecommendedTest]:
    tests = [
        RecommendedTest(
            name="Solubility assay",
            priority="Standard",
            reason="Baseline developability screen for any small-molecule candidate.",
        ),
        RecommendedTest(
            name="Microsomal stability",
            priority="Standard",
            reason="Estimates metabolic stability before more expensive studies.",
        ),
        RecommendedTest(
            name="Plasma protein binding",
            priority="Standard",
            reason="Supports exposure and free-drug interpretation.",
        ),
        RecommendedTest(
            name="Caco-2 permeability",
            priority="Standard",
            reason="Screens intestinal permeability risk.",
        ),
        RecommendedTest(
            name="CYP inhibition panel",
            priority="Standard",
            reason="Screens common drug-drug interaction risk.",
        ),
        RecommendedTest(
            name="hERG assay",
            priority="Standard",
            reason="Baseline cardiotoxicity liability screen.",
        ),
        RecommendedTest(
            name="Ames test",
            priority="Standard",
            reason="Baseline mutagenicity screen.",
        ),
        RecommendedTest(
            name="Cytotoxicity assay",
            priority="Standard",
            reason="General early toxicity screen.",
        ),
        RecommendedTest(
            name="Hepatocyte toxicity assay",
            priority="Standard",
            reason="Early liver toxicity screen.",
        ),
    ]

    if d.logp > 5 or d.molecular_weight > 500:
        tests.append(
            RecommendedTest(
                name="Formulation and solubility optimization screen",
                priority="High",
                reason="High LogP or molecular weight can create solubility and exposure risk.",
            )
        )
    if d.tpsa > 140 or d.rotatable_bonds > 10:
        tests.append(
            RecommendedTest(
                name="Enhanced permeability assessment",
                priority="High",
                reason="Veber rule violation suggests oral absorption risk.",
            )
        )
    if rules.developability_risk in {"Medium", "High"}:
        tests.extend(
            [
                RecommendedTest(
                    name="Acute toxicity study",
                    priority="Recommended",
                    reason="Needed before advancing beyond early screening.",
                ),
                RecommendedTest(
                    name="Repeat-dose toxicity study",
                    priority="Recommended",
                    reason="Supports nonclinical safety assessment for repeated exposure.",
                ),
                RecommendedTest(
                    name="Toxicokinetics",
                    priority="Recommended",
                    reason="Links systemic exposure to toxicity findings.",
                ),
            ]
        )
    if rules.developability_risk == "High":
        tests.extend(
            [
                RecommendedTest(
                    name="Genotoxicity package",
                    priority="High",
                    reason="High rule-based risk warrants stronger long-term safety screening.",
                ),
                RecommendedTest(
                    name="Reproductive toxicity if needed",
                    priority="Recommended",
                    reason="Needed depending on indication, treatment duration, and target population.",
                ),
            ]
        )

    return tests


def build_decision(rules: RuleEvaluation, tests: list[RecommendedTest]) -> dict:
    high_priority_tests = [test.name for test in tests if test.priority == "High"]

    if rules.developability_risk == "Low":
        decision = "Proceed"
    elif rules.developability_risk == "Medium":
        decision = "Proceed with caution"
    elif len(high_priority_tests) <= 2:
        decision = "Needs optimization"
    else:
        decision = "Do not proceed without major redesign"

    return {
        "decision": decision,
        "basis": "Transparent rule-based MVP decision using RDKit descriptors, Lipinski, Veber, and test-planner rules.",
        "main_reasons": rules.reasons,
        "high_priority_followups": high_priority_tests,
    }


def build_placeholder_modules() -> tuple[PlaceholderModule, PlaceholderModule]:
    return (
        PlaceholderModule(
            status="placeholder / future module",
            message="Prediction model not yet integrated. This section currently contains rule-based placeholders and future-module labels.",
            future_outputs=[
                "Absorption risk",
                "Distribution and BBB risk",
                "CYP metabolism risk",
                "Clearance and excretion estimates",
            ],
        ),
        PlaceholderModule(
            status="placeholder / future module",
            message="Prediction model not yet integrated. This section currently contains rule-based placeholders and future-module labels.",
            future_outputs=[
                "hERG inhibition probability",
                "Hepatotoxicity risk",
                "Ames mutagenicity risk",
                "Carcinogenicity and reproductive toxicity risk",
            ],
        ),
    )
