from pydantic import BaseModel, Field


class ProjectWorkspaceReportCreateRequest(BaseModel):
    include_candidate_matrix: bool = True
    include_model_status: bool = True
    include_reproducibility: bool = True
    include_limitations: bool = True


class ProjectWorkspaceReportCreateResponse(BaseModel):
    report_id: int
    project_id: int
    created_at: str
    available_formats: list[str] = Field(default_factory=lambda: ["pdf", "docx", "json"])
    pdf_url: str
    docx_url: str
    json_url: str
    warnings: list[str] = Field(default_factory=list)


class ProjectWorkspaceReportListItem(ProjectWorkspaceReportCreateResponse):
    filename_pdf: str
    filename_docx: str
    filename_json: str
