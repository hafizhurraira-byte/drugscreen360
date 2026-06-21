from typing import Any

from pydantic import BaseModel, Field


DEMO_SCIENTIFIC_NOTICE = "Demo data for software demonstration only. Not experimental or clinical evidence."


class DemoWorkflowRequest(BaseModel):
    project_title: str = "DrugScreen360 Demo Project"
    include_screening: bool = True
    include_lead_prioritization: bool = True
    include_validation_plan: bool = True
    include_experimental_feedback: bool = True
    include_final_report: bool = True


class DemoProjectCreateResponse(BaseModel):
    demo_project_id: int
    project_title: str
    created_items: list[dict[str, Any]] = Field(default_factory=list)
    workflow_steps: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    scientific_notice: str = DEMO_SCIENTIFIC_NOTICE


class DemoWorkflowRunResponse(DemoProjectCreateResponse):
    final_report_id: int | None = None
    research_export_id: int | None = None
    research_export_available: bool = False
    download_links: dict[str, str] = Field(default_factory=dict)


class DemoWorkflowStatusResponse(BaseModel):
    project_id: int
    workflow_steps: list[dict[str, Any]] = Field(default_factory=list)
    completed_steps: list[str] = Field(default_factory=list)
    generated_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    missing_steps: list[str] = Field(default_factory=list)
    download_links: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    scientific_notice: str = DEMO_SCIENTIFIC_NOTICE
