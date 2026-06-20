from pydantic import BaseModel


RiskLevel = str


class AdmetEvaluateRequest(BaseModel):
    smiles: str
    descriptors: dict | None = None


class RuleSection(BaseModel):
    status: str
    reasons: list[str]
    recommended_followups: list[str]
    limitation: str | None = None


class AbsorptionAssessment(BaseModel):
    absorption_risk: RiskLevel
    oral_developability_flag: str
    reasons: list[str]
    recommended_followups: list[str]


class SolubilityAssessment(BaseModel):
    solubility_risk: RiskLevel
    reasons: list[str]
    recommended_followups: list[str]


class BbbCnsAssessment(BaseModel):
    bbb_exposure_flag: str
    reasons: list[str]
    limitation: str


class MetabolismAssessment(BaseModel):
    cyp_prediction_status: str
    metabolism_risk_flag: str
    recommended_tests: list[str]
    limitation: str


class StructuralAlertsAssessment(BaseModel):
    structural_alerts: list[str]
    structural_alert_risk: RiskLevel
    reasons: list[str]


class NotImplementedToxicityAssessment(BaseModel):
    prediction_status: str
    followup_required: bool = True
    recommended_tests: list[str]
    limitation: str


class OverallAdmetToxScore(BaseModel):
    admet_rule_concern: int
    toxicity_structural_alert_concern: int
    missing_model_uncertainty: int
    overall_admet_tox_concern_score: int
    concern_level: RiskLevel
    confidence_level: str
    explanation: str


class AdmetToxicityAssessment(BaseModel):
    label: str = "Rule-based early screen. Not a validated ADMET/toxicity prediction model."
    absorption: AbsorptionAssessment
    solubility: SolubilityAssessment
    bbb_cns_flag: BbbCnsAssessment
    metabolism_status: MetabolismAssessment
    structural_alerts: StructuralAlertsAssessment
    herg_status: NotImplementedToxicityAssessment
    ames_genotoxicity_status: NotImplementedToxicityAssessment
    hepatotoxicity_status: NotImplementedToxicityAssessment
    overall: OverallAdmetToxScore
    recommended_followup_tests: list[str]
    limitations: list[str]
