from typing import Any

from pydantic import BaseModel, Field


class FinalProjectReportRequest(BaseModel):
    project_id: int | None = None
    report_title: str = "DrugScreen360 Final Project Report"
    include_screening: bool = True
    include_admet_prediction: bool = True
    include_model_training: bool = True
    include_external_validation: bool = True
    include_applicability_domain: bool = True
    include_explainability: bool = True
    include_lead_prioritization: bool = True
    include_validation_planner: bool = True
    include_experimental_feedback: bool = True
    formats: list[str] = Field(default_factory=lambda: ["json", "pdf", "docx"])


class FinalProjectReportSection(BaseModel):
    section_id: str
    title: str
    included: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    records: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class FinalProjectReportSummary(BaseModel):
    project_name: str | None = None
    generated_at: str
    molecule_or_candidate_count: int = 0
    top_candidates: list[dict[str, Any]] = Field(default_factory=list)
    main_findings: list[str] = Field(default_factory=list)
    main_warnings: list[str] = Field(default_factory=list)
    next_recommended_steps: list[str] = Field(default_factory=list)


class FinalProjectReportResponse(BaseModel):
    report_id: int
    report_title: str
    project_id: int | None = None
    generated_files: dict[str, str] = Field(default_factory=dict)
    included_sections: list[str] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    scientific_notice: str = "Computational decision-support report only. Experimental and clinical interpretation requires qualified scientific review."
    created_at: str | None = None


class FinalProjectReportExportResponse(BaseModel):
    report_id: int
    json_url: str | None = None
    pdf_url: str | None = None
    docx_url: str | None = None
